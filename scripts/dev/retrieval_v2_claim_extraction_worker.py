from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_candidate_prompt as candidate_prompt  # noqa: E402
from scripts.dev import retrieval_v2_claim_candidate_triage as candidate_triage  # noqa: E402
from scripts.dev import retrieval_v2_claim_cache as fs_cache  # noqa: E402
from scripts.dev import retrieval_v2_claim_cache_pg as pg_cache  # noqa: E402
from scripts.dev import retrieval_v2_claim_quality as claim_quality  # noqa: E402
from scripts.dev import retrieval_v2_clean_runner as clean_runner  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import (  # noqa: E402
    DEFAULT_PG_SCHEMA,
    DEFAULT_V3_DSN_ENV,
    render_sql,
    schema_cursor,
)


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_RUN_ROOT = ROOT / "tmp" / "retrieval_v2_claim_extraction_runs"


class ClaimExtractionWorkerError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def stable_hash(value: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def text(value: Any) -> str:
    return str(value or "").strip()


def write_json(path: Path | None, payload: Mapping[str, Any]) -> None:
    if path is None:
        print(pretty_json(payload), end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ClaimExtractionWorkerError(f"{path}: expected JSON object")
    return payload


def optional_int(value: Any) -> int | None:
    raw = text(value)
    return int(raw) if raw else None


def provider_default_filter_ineligible_slices(judge_provider: str) -> bool:
    del judge_provider
    return False


def claim_slice_filter_report(candidates: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    filtered = json.loads(stable_json(candidates))
    kept: list[dict[str, Any]] = []
    filtered_rows: list[dict[str, Any]] = []
    reason_counts: dict[str, int] = {}
    by_object: dict[str, dict[str, Any]] = {}
    for row in filtered.get("candidate_slices") or []:
        if not isinstance(row, Mapping):
            continue
        eligibility = claim_quality.slice_claim_eligibility(row)
        object_name = text(row.get("object_name"))
        if eligibility.get("claim_eligible") is False:
            reasons = [text(reason) for reason in eligibility.get("reasons") or [] if text(reason)]
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            current = by_object.setdefault(object_name, {"filtered_slice_count": 0, "reason_counts": {}})
            current["filtered_slice_count"] += 1
            for reason in reasons:
                current["reason_counts"][reason] = current["reason_counts"].get(reason, 0) + 1
            filtered_rows.append(
                {
                    "slice_code": text(row.get("slice_code")),
                    "object_name": object_name,
                    "reasons": reasons,
                    "risk_flags": list(eligibility.get("risk_flags") or []),
                    "mention_role": eligibility.get("mention_role"),
                    "support_level_hint": eligibility.get("support_level_hint"),
                }
            )
            continue
        kept.append(dict(row))
    original_count = len([row for row in candidates.get("candidate_slices") or [] if isinstance(row, Mapping)])
    filtered["candidate_slices"] = kept
    stats = dict(filtered.get("stats") or {})
    stats["candidate_slices_before_ineligible_filter"] = original_count
    stats["candidate_slices"] = len(kept)
    stats["ineligible_candidate_slices_filtered"] = len(filtered_rows)
    filtered["stats"] = stats
    report = {
        "enabled": True,
        "input_slice_count": original_count,
        "kept_slice_count": len(kept),
        "filtered_slice_count": len(filtered_rows),
        "reason_counts": dict(sorted(reason_counts.items())),
        "by_object": {
            name: {
                **payload,
                "reason_counts": dict(sorted((payload.get("reason_counts") or {}).items())),
            }
            for name, payload in sorted(by_object.items())
        },
        "filtered_slices": filtered_rows,
    }
    return filtered, report


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def target_dir_name(job: Mapping[str, Any]) -> str:
    target_code = text(job.get("target_code")) or "target"
    rule_code = text(job.get("rule_code")) or "claim_only"
    return f"{target_code}_{rule_code}_{stable_hash(job.get('idem_key') or job, length=8)}"


def candidates_identity(candidates: Mapping[str, Any]) -> dict[str, str]:
    task_identity = candidates.get("task_identity") if isinstance(candidates.get("task_identity"), Mapping) else {}
    target_profile = candidates.get("target_profile") if isinstance(candidates.get("target_profile"), Mapping) else {}
    rule = candidates.get("rule") if isinstance(candidates.get("rule"), Mapping) else {}
    return {
        "emperor_name": text(task_identity.get("emperor_name") or target_profile.get("primary_name")),
        "target_code": text(task_identity.get("target_code")),
        "rule_code": text(task_identity.get("rule_code") or rule.get("rule_code")),
        "capture_profile": text(task_identity.get("capture_profile") or candidates.get("capture_profile")),
    }


def job_from_candidates(
    *,
    candidates_path: Path,
    cache_root: Path,
    run_root: Path,
    priority: int = 100,
) -> dict[str, Any]:
    candidates = read_json(candidates_path)
    slices = [row for row in candidates.get("candidate_slices") or [] if isinstance(row, Mapping)]
    identity = candidates_identity(candidates)
    idem_payload = {
        "candidates_path": str(candidates_path),
        "slice_hashes": [fs_cache.slice_hash_from_row(row) for row in slices],
        "cache_root": str(cache_root),
    }
    idem_key = "CLMEXT|" + stable_hash(idem_payload, length=24)
    job_code = "CLMEXT-" + stable_hash(idem_key, length=16)
    return {
        "job_code": job_code,
        "idem_key": idem_key,
        "status": "ready",
        "priority": max(1, int(priority)),
        "emperor_name": identity["emperor_name"],
        "target_code": identity["target_code"],
        "rule_code": identity["rule_code"] or "claim_extraction_only",
        "capture_profile": identity["capture_profile"],
        "candidate_payload_path": str(candidates_path),
        "run_root": str(run_root / job_code),
        "cache_root": str(cache_root),
        "uncovered_slice_count": len(slices),
        "job_payload": {
            "source": "enqueue-from-candidates",
            "candidates_path": str(candidates_path),
            "cache_root": str(cache_root),
            "slice_count": len(slices),
            "slice_hashes": idem_payload["slice_hashes"],
        },
    }


def apply_schema(target_dsn: str, *, schema_name: str = DEFAULT_PG_SCHEMA) -> None:
    psycopg, dict_row = import_psycopg()
    sql = (ROOT / "db" / "migrations" / "20260708_retrieval_v2_claim_extraction_jobs.sql").read_text(encoding="utf-8")
    with psycopg.connect(target_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(render_sql(sql, schema_name=schema_name))
        conn.commit()


def upsert_job(cur: Any, job: Mapping[str, Any]) -> int:
    cur.execute(
        """
        insert into retrieval_v2.claim_extraction_jobs (
            job_code, idem_key, status, priority, emperor_name, target_code, rule_code,
            capture_profile, candidate_payload_path, run_root, cache_root, uncovered_slice_count, job_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        on conflict (idem_key) do update set
            priority = least(retrieval_v2.claim_extraction_jobs.priority, excluded.priority),
            candidate_payload_path = excluded.candidate_payload_path,
            run_root = excluded.run_root,
            cache_root = excluded.cache_root,
            uncovered_slice_count = excluded.uncovered_slice_count,
            job_payload = retrieval_v2.claim_extraction_jobs.job_payload || excluded.job_payload,
            status = case
                when retrieval_v2.claim_extraction_jobs.status::text in ('succeeded', 'running', 'cancelled')
                    then retrieval_v2.claim_extraction_jobs.status
                else excluded.status
            end,
            updated_at = now()
        returning id
        """,
        (
            job["job_code"],
            job["idem_key"],
            job["status"],
            job["priority"],
            job["emperor_name"],
            job["target_code"],
            job["rule_code"],
            job["capture_profile"],
            job["candidate_payload_path"],
            job["run_root"],
            job["cache_root"],
            job["uncovered_slice_count"],
            stable_json(job["job_payload"]),
        ),
    )
    return int(cur.fetchone()["id"])


def enqueue_job(*, dsn: str, job: Mapping[str, Any], schema_name: str = DEFAULT_PG_SCHEMA) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            job_id = upsert_job(cur, job)
        conn.commit()
    return {"job_id": job_id, "job_code": job["job_code"], "idem_key": job["idem_key"]}


def claim_ready_job(*, dsn: str, worker_id: str, lease_minutes: int = 120, schema_name: str = DEFAULT_PG_SCHEMA) -> dict[str, Any] | None:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                with picked as (
                    select id
                      from retrieval_v2.claim_extraction_jobs
                     where status in ('ready', 'retry_wait')
                       and attempt_count < max_attempts
                       and (lease_until is null or lease_until < now())
                     order by priority, created_at
                     limit 1
                     for update skip locked
                )
                update retrieval_v2.claim_extraction_jobs j
                   set status = 'running',
                       attempt_count = attempt_count + 1,
                       locked_by = %s,
                       locked_at = now(),
                       lease_until = now() + (%s::text || ' minutes')::interval,
                       last_error = null,
                       updated_at = now()
                  from picked
                 where j.id = picked.id
                returning j.*
                """,
                (worker_id, lease_minutes),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def fetch_next_ready_job(*, dsn: str, schema_name: str = DEFAULT_PG_SCHEMA) -> dict[str, Any] | None:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                select *
                  from retrieval_v2.claim_extraction_jobs
                 where status in ('ready', 'retry_wait')
                   and attempt_count < max_attempts
                   and (lease_until is null or lease_until < now())
                 order by priority, created_at
                 limit 1
                """
            )
            row = cur.fetchone()
    return dict(row) if row else None


def create_job_run(cur: Any, *, job: Mapping[str, Any], worker_id: str, run_code: str, input_fingerprint: str) -> int:
    cur.execute(
        """
        insert into retrieval_v2.claim_extraction_job_runs (
            run_code, job_id, worker_id, status, input_fingerprint, run_root, run_payload
        )
        values (%s, %s, %s, 'running', %s, %s, %s::jsonb)
        returning id
        """,
        (
            run_code,
            int(job["id"]),
            worker_id,
            input_fingerprint,
            text(job.get("run_root")),
            stable_json({"job_code": job.get("job_code"), "candidate_payload_path": job.get("candidate_payload_path")}),
        ),
    )
    return int(cur.fetchone()["id"])


def finish_job_run(
    cur: Any,
    *,
    run_id: int,
    job_id: int,
    status: str,
    output_fingerprint: str = "",
    claim_count: int = 0,
    usage_payload: Mapping[str, Any] | None = None,
    error_type: str = "",
    error_msg: str = "",
    run_payload: Mapping[str, Any] | None = None,
) -> None:
    cur.execute(
        """
        update retrieval_v2.claim_extraction_job_runs
           set status = %s,
               ended_at = now(),
               output_fingerprint = %s,
               claim_count = %s,
               usage_payload = %s::jsonb,
               error_type = %s,
               error_msg = %s,
               run_payload = run_payload || %s::jsonb
         where id = %s
        """,
        (
            status,
            output_fingerprint,
            claim_count,
            stable_json(usage_payload or {}),
            error_type,
            error_msg,
            stable_json(run_payload or {}),
            run_id,
        ),
    )
    if status == "succeeded":
        cur.execute(
            """
            update retrieval_v2.claim_extraction_jobs
               set status = 'succeeded',
                   locked_by = null,
                   locked_at = null,
                   lease_until = null,
                   last_error = null,
                   updated_at = now()
             where id = %s
            """,
            (job_id,),
        )
    elif status == "failed":
        cur.execute(
            """
            update retrieval_v2.claim_extraction_jobs
               set status = (
                       case when attempt_count >= max_attempts then 'failed' else 'retry_wait' end
                   )::retrieval_v2.rv2_claim_extraction_job_status,
                   locked_by = null,
                   locked_at = null,
                   lease_until = null,
                   last_error = %s,
                   updated_at = now()
             where id = %s
            """,
            (error_msg, job_id),
        )


def job_plan(job: Mapping[str, Any]) -> dict[str, Any]:
    candidates_path = resolve_path(text(job.get("candidate_payload_path")))
    run_root = resolve_path(text(job.get("run_root")))
    cache_root = resolve_path(text(job.get("cache_root"))) if text(job.get("cache_root")) else fs_cache.DEFAULT_CACHE_ROOT
    return {
        "job_code": job.get("job_code"),
        "candidate_payload_path": str(candidates_path),
        "run_root": str(run_root),
        "cache_root": str(cache_root),
        "uncovered_slice_count": int(job.get("uncovered_slice_count") or 0),
        "execute_effect": "claim-only judge -> filesystem claim cache -> optional PG claim cache",
    }


def write_mini_run_artifacts(
    *,
    job: Mapping[str, Any],
    candidates: Mapping[str, Any],
    judge_payload: Mapping[str, Any],
    judge_result: Mapping[str, Any],
    run_root: Path,
    filter_report: Mapping[str, Any] | None = None,
    triage_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    person_dir = run_root / target_dir_name(job)
    person_dir.mkdir(parents=True, exist_ok=True)
    task_identity = candidates.get("task_identity") if isinstance(candidates.get("task_identity"), Mapping) else {}
    task = {
        "target_code": text(job.get("target_code")) or text(task_identity.get("target_code")),
        "emperor_name": text(job.get("emperor_name")) or text(task_identity.get("emperor_name")),
        "rule_code": text(job.get("rule_code")) or text(task_identity.get("rule_code")),
        "capture_profile": text(job.get("capture_profile")) or text(candidates.get("capture_profile")),
        "capture_mode": "claim_extraction_worker",
    }
    fs_cache.write_json(person_dir / "task.final.json", task)
    fs_cache.write_json(person_dir / "candidates.final.json", candidates)
    fs_cache.write_json(person_dir / "judge_result.final.json", judge_payload)
    claim_count = len(judge_payload.get("claims") or [])
    summary = {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v2_claim_extraction_worker.py",
        "run_root": str(run_root),
        "targets": [task["emperor_name"]],
        "elapsed_seconds": judge_result.get("elapsed_seconds"),
        "clean_policy": {
            "judge_mode": candidate_prompt.CLAIM_EXTRACTION_ONLY_MODE,
            "extractor_version": candidate_prompt.CLAIM_EXTRACTOR_VERSION,
            "judge_provider": judge_result.get("provider") or clean_runner.DEFAULT_JUDGE_PROVIDER,
            "ineligible_slice_filter": filter_report or {"enabled": False},
            "candidate_triage": triage_report or {"enabled": False},
        },
        "people": [
            {
                "name": task["emperor_name"],
                "target_code": task["target_code"],
                "rule_code": task["rule_code"],
                "run_dir": str(person_dir),
                "candidate_slices": len(candidates.get("candidate_slices") or []),
                "judge_status": judge_payload.get("status"),
                "judge_elapsed_seconds": judge_result.get("elapsed_seconds"),
                "judge_usage": judge_result.get("usage") or {},
                "claim_count": claim_count,
                "files": {
                    "final_task": str(person_dir / "task.final.json"),
                    "final_candidates": str(person_dir / "candidates.final.json"),
                    "final_judge_result": str(person_dir / "judge_result.final.json"),
                    "claim_slice_filter_report": str(run_root / "claim_slice_filter_report.json") if filter_report else None,
                    "claim_candidate_triage": str(person_dir / "claim_candidate_triage.json") if triage_report and triage_report.get("enabled") else None,
                },
            }
        ],
        "totals": {
            "candidate_slices": len(candidates.get("candidate_slices") or []),
            "claim_count": claim_count,
            "usage": judge_result.get("usage") or {},
        },
    }
    if filter_report:
        fs_cache.write_json(run_root / "claim_slice_filter_report.json", filter_report)
    if triage_report and triage_report.get("enabled"):
        fs_cache.write_json(person_dir / "claim_candidate_triage.json", triage_report)
    fs_cache.write_json(run_root / "summary.json", summary)
    return summary


def execute_job(
    *,
    job: Mapping[str, Any],
    codex_bin: str,
    judge_timeout_seconds: int,
    judge_shard_size: int,
    judge_shard_workers: int,
    judge_provider: str = clean_runner.DEFAULT_JUDGE_PROVIDER,
    judge_model: str | None = None,
    judge_api_key_env: str = clean_runner.DEEPSEEK_API_KEY_ENV,
    judge_base_url: str | None = None,
    judge_thinking: str | None = None,
    judge_max_tokens: int | None = None,
    filter_ineligible_slices: bool | None = None,
    candidate_triage_provider: str = candidate_triage.TRIAGE_PROVIDER_NONE,
    candidate_triage_duplicate_text_similarity: float = candidate_triage.DEFAULT_DUPLICATE_TEXT_SIMILARITY,
    import_pg: bool,
    dsn_env: str,
    schema_name: str,
) -> dict[str, Any]:
    candidates_path = resolve_path(text(job.get("candidate_payload_path")))
    candidates = read_json(candidates_path)
    run_root = resolve_path(text(job.get("run_root")))
    cache_root = resolve_path(text(job.get("cache_root"))) if text(job.get("cache_root")) else fs_cache.DEFAULT_CACHE_ROOT
    person_dir = run_root / target_dir_name(job)
    person_dir.mkdir(parents=True, exist_ok=True)
    filter_enabled = provider_default_filter_ineligible_slices(judge_provider) if filter_ineligible_slices is None else bool(filter_ineligible_slices)
    filter_report: dict[str, Any] | None = None
    triage_report: dict[str, Any] | None = None
    judge_candidates = candidates
    if filter_enabled:
        judge_candidates, filter_report = claim_slice_filter_report(candidates)
    judge_candidates, triage_report = candidate_triage.triage_candidates(
        judge_candidates,
        provider=candidate_triage_provider,
        model=judge_model,
        api_key_env=judge_api_key_env,
        base_url=judge_base_url,
        timeout_seconds=min(judge_timeout_seconds, candidate_triage.DEFAULT_TIMEOUT_SECONDS),
        thinking=judge_thinking,
        max_tokens=judge_max_tokens or candidate_triage.DEFAULT_MAX_TOKENS,
        duplicate_text_similarity=candidate_triage_duplicate_text_similarity,
    )
    judge_result = clean_runner.run_judge(
        candidates=judge_candidates,
        prompt_path=person_dir / "judge_prompt.round0.md",
        person_dir=person_dir,
        round_index=0,
        codex_runner=clean_runner.run_codex,
        codex_bin=codex_bin,
        timeout_seconds=judge_timeout_seconds,
        judge_shard_size=judge_shard_size,
        judge_shard_workers=judge_shard_workers,
        judge_mode=candidate_prompt.CLAIM_EXTRACTION_ONLY_MODE,
        judge_provider=judge_provider,
        judge_model=judge_model,
        judge_api_key_env=judge_api_key_env,
        judge_base_url=judge_base_url,
        judge_thinking=judge_thinking,
        judge_max_tokens=judge_max_tokens,
    )
    judge_payload = dict(judge_result["payload"])
    judge_payload["_elapsed_seconds"] = judge_result["elapsed_seconds"]
    judge_payload["_usage"] = judge_result["usage"]
    summary = write_mini_run_artifacts(
        job=job,
        candidates=judge_candidates,
        judge_payload=judge_payload,
        judge_result=judge_result,
        run_root=run_root,
        filter_report=filter_report,
        triage_report=triage_report,
    )
    fs_import = fs_cache.import_run(run_root, cache_root)
    pg_import: dict[str, Any] | None = None
    if import_pg:
        pg_import = pg_cache.apply_cache_to_pg(
            cache_root=cache_root,
            env_file=None,
            dsn_env=dsn_env,
            schema_name=schema_name,
            execute=True,
            last_run_codes=[text(fs_import.get("run_code"))],
        )
    return {
        "run_root": str(run_root),
        "summary": summary,
        "filesystem_import": fs_import,
        "pg_import": pg_import,
        "claim_count": summary["totals"]["claim_count"],
        "usage": judge_result["usage"],
        "judge_provider": judge_result.get("provider") or clean_runner.DEFAULT_JUDGE_PROVIDER,
    }


def extract_from_candidates(
    *,
    candidates_path: Path,
    cache_root: Path,
    run_root: Path,
    codex_bin: str = "codex",
    judge_timeout_seconds: int = 1800,
    judge_shard_size: int = 4,
    judge_shard_workers: int = 4,
    judge_provider: str = clean_runner.DEFAULT_JUDGE_PROVIDER,
    judge_model: str | None = None,
    judge_api_key_env: str = clean_runner.DEEPSEEK_API_KEY_ENV,
    judge_base_url: str | None = None,
    judge_thinking: str | None = None,
    judge_max_tokens: int | None = None,
    filter_ineligible_slices: bool | None = None,
    candidate_triage_provider: str = candidate_triage.TRIAGE_PROVIDER_NONE,
    candidate_triage_duplicate_text_similarity: float = candidate_triage.DEFAULT_DUPLICATE_TEXT_SIMILARITY,
    import_pg: bool = False,
    dsn_env: str = DEFAULT_DSN_ENV,
    schema_name: str = DEFAULT_PG_SCHEMA,
) -> dict[str, Any]:
    job = job_from_candidates(candidates_path=candidates_path, cache_root=cache_root, run_root=run_root)
    job["status"] = "shadow"
    result = execute_job(
        job=job,
        codex_bin=codex_bin,
        judge_timeout_seconds=judge_timeout_seconds,
        judge_shard_size=judge_shard_size,
        judge_shard_workers=judge_shard_workers,
        judge_provider=judge_provider,
        judge_model=judge_model,
        judge_api_key_env=judge_api_key_env,
        judge_base_url=judge_base_url,
        judge_thinking=judge_thinking,
        judge_max_tokens=judge_max_tokens,
        filter_ineligible_slices=filter_ineligible_slices,
        candidate_triage_provider=candidate_triage_provider,
        candidate_triage_duplicate_text_similarity=candidate_triage_duplicate_text_similarity,
        import_pg=import_pg,
        dsn_env=dsn_env,
        schema_name=schema_name,
    )
    return {
        "ok": True,
        "status": "succeeded",
        "mode": "extract_from_candidates",
        "job": job,
        "result": result,
    }


def once(
    *,
    dsn: str,
    worker_id: str,
    execute: bool,
    codex_bin: str = "codex",
    judge_timeout_seconds: int = 1800,
    judge_shard_size: int = 4,
    judge_shard_workers: int = 4,
    judge_provider: str = clean_runner.DEFAULT_JUDGE_PROVIDER,
    judge_model: str | None = None,
    judge_api_key_env: str = clean_runner.DEEPSEEK_API_KEY_ENV,
    judge_base_url: str | None = None,
    judge_thinking: str | None = None,
    judge_max_tokens: int | None = None,
    filter_ineligible_slices: bool | None = None,
    candidate_triage_provider: str = candidate_triage.TRIAGE_PROVIDER_NONE,
    candidate_triage_duplicate_text_similarity: float = candidate_triage.DEFAULT_DUPLICATE_TEXT_SIMILARITY,
    import_pg: bool = True,
    dsn_env: str = DEFAULT_DSN_ENV,
    schema_name: str = DEFAULT_PG_SCHEMA,
) -> dict[str, Any]:
    job = claim_ready_job(dsn=dsn, worker_id=worker_id, schema_name=schema_name) if execute else fetch_next_ready_job(dsn=dsn, schema_name=schema_name)
    if job is None:
        return {"ok": True, "status": "idle", "job": None}
    plan = job_plan(job)
    run_code = "CLMRUN-" + stable_hash([job.get("job_code"), time.time()], length=16)
    input_fingerprint = stable_hash(job)
    if not execute:
        return {"ok": True, "status": "planned", "job": dict(job), "plan": plan}
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            run_id = create_job_run(cur, job=job, worker_id=worker_id, run_code=run_code, input_fingerprint=input_fingerprint)
        conn.commit()
    try:
        result = execute_job(
            job=job,
            codex_bin=codex_bin,
            judge_timeout_seconds=judge_timeout_seconds,
            judge_shard_size=judge_shard_size,
            judge_shard_workers=judge_shard_workers,
            judge_provider=judge_provider,
            judge_model=judge_model,
            judge_api_key_env=judge_api_key_env,
            judge_base_url=judge_base_url,
            judge_thinking=judge_thinking,
            judge_max_tokens=judge_max_tokens,
            filter_ineligible_slices=filter_ineligible_slices,
            candidate_triage_provider=candidate_triage_provider,
            candidate_triage_duplicate_text_similarity=candidate_triage_duplicate_text_similarity,
            import_pg=import_pg,
            dsn_env=dsn_env,
            schema_name=schema_name,
        )
    except Exception as exc:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            with conn.cursor() as raw_cur:
                cur = schema_cursor(raw_cur, schema_name=schema_name)
                finish_job_run(
                    cur,
                    run_id=run_id,
                    job_id=int(job["id"]),
                    status="failed",
                    error_type=exc.__class__.__name__,
                    error_msg=str(exc)[:1000],
                )
            conn.commit()
        raise
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            finish_job_run(
                cur,
                run_id=run_id,
                job_id=int(job["id"]),
                status="succeeded",
                output_fingerprint=stable_hash(result),
                claim_count=int(result.get("claim_count") or 0),
                usage_payload=result.get("usage") or {},
                run_payload=result,
            )
        conn.commit()
    return {"ok": True, "status": "succeeded", "job": dict(job), "result": result}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claim-only extraction worker for uncovered retrieval_v2 candidate slices.")
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("apply-schema", help="Apply claim extraction queue schema.")
    schema.add_argument("--env-file", type=Path)
    schema.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    schema.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)

    enqueue = sub.add_parser("enqueue-from-candidates", help="Create one claim extraction job from uncovered candidates JSON.")
    enqueue.add_argument("--candidates", type=Path, required=True)
    enqueue.add_argument("--cache-root", type=Path, required=True)
    enqueue.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    enqueue.add_argument("--priority", type=int, default=100)
    enqueue.add_argument("--env-file", type=Path)
    enqueue.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    enqueue.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    enqueue.add_argument("--output-json", type=Path)

    extract = sub.add_parser("extract-from-candidates", help="Run claim extraction directly from candidates JSON; defaults to no PG import.")
    extract.add_argument("--candidates", type=Path, required=True)
    extract.add_argument("--cache-root", type=Path, required=True)
    extract.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    extract.add_argument("--env-file", type=Path)
    extract.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    extract.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    extract.add_argument("--codex-bin", default="codex")
    extract.add_argument("--judge-timeout", type=int, default=1800)
    extract.add_argument("--judge-shard-size", type=int, default=4)
    extract.add_argument("--judge-shard-workers", type=int, default=4)
    extract.add_argument("--judge-provider", choices=["codex", "deepseek"], default=os.environ.get("EMPEROR_EVAL_CLAIM_PROVIDER") or os.environ.get("EMPEROR_EVAL_JUDGE_PROVIDER") or clean_runner.DEFAULT_JUDGE_PROVIDER)
    extract.add_argument("--judge-model", default=os.environ.get("EMPEROR_EVAL_CLAIM_MODEL") or os.environ.get(clean_runner.DEEPSEEK_MODEL_ENV))
    extract.add_argument("--judge-api-key-env", default=clean_runner.DEEPSEEK_API_KEY_ENV)
    extract.add_argument("--judge-base-url", default=os.environ.get(clean_runner.DEEPSEEK_BASE_URL_ENV))
    extract.add_argument("--judge-thinking", choices=["enabled", "disabled"], default=os.environ.get("DEEPSEEK_THINKING") or clean_runner.DEFAULT_DEEPSEEK_THINKING)
    extract.add_argument("--judge-max-tokens", type=int, default=optional_int(os.environ.get(clean_runner.DEEPSEEK_MAX_TOKENS_ENV)))
    extract.add_argument("--candidate-triage-provider", choices=[candidate_triage.TRIAGE_PROVIDER_NONE, candidate_triage.TRIAGE_PROVIDER_DEEPSEEK], default=candidate_triage.TRIAGE_PROVIDER_NONE, help="Optional DeepSeek duplicate suggestion; only mechanically verified near-duplicates are deferred from Codex.")
    extract.add_argument("--candidate-triage-duplicate-text-similarity", type=float, default=candidate_triage.DEFAULT_DUPLICATE_TEXT_SIMILARITY)
    extract_filter = extract.add_mutually_exclusive_group()
    extract_filter.add_argument("--filter-ineligible-slices", dest="filter_ineligible_slices", action="store_true")
    extract_filter.add_argument("--no-filter-ineligible-slices", dest="filter_ineligible_slices", action="store_false")
    extract.set_defaults(filter_ineligible_slices=None)
    extract.add_argument("--import-pg", action="store_true", help="Opt in to PG import; default is filesystem cache only.")
    extract.add_argument("--output-json", type=Path)

    plan = sub.add_parser("plan", help="Show the next ready claim extraction job without taking a lease.")
    plan.add_argument("--env-file", type=Path)
    plan.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    plan.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    plan.add_argument("--worker-id", default="retrieval_v2_claim_extraction_worker")
    plan.add_argument("--output-json", type=Path)

    once_cmd = sub.add_parser("once", help="Claim and optionally execute one ready job.")
    once_cmd.add_argument("--env-file", type=Path)
    once_cmd.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    once_cmd.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    once_cmd.add_argument("--worker-id", default="retrieval_v2_claim_extraction_worker")
    once_cmd.add_argument("--execute", action="store_true")
    once_cmd.add_argument("--codex-bin", default="codex")
    once_cmd.add_argument("--judge-timeout", type=int, default=1800)
    once_cmd.add_argument("--judge-shard-size", type=int, default=4)
    once_cmd.add_argument("--judge-shard-workers", type=int, default=4)
    once_cmd.add_argument("--judge-provider", choices=["codex", "deepseek"], default=os.environ.get("EMPEROR_EVAL_CLAIM_PROVIDER") or os.environ.get("EMPEROR_EVAL_JUDGE_PROVIDER") or clean_runner.DEFAULT_JUDGE_PROVIDER)
    once_cmd.add_argument("--judge-model", default=os.environ.get("EMPEROR_EVAL_CLAIM_MODEL") or os.environ.get(clean_runner.DEEPSEEK_MODEL_ENV))
    once_cmd.add_argument("--judge-api-key-env", default=clean_runner.DEEPSEEK_API_KEY_ENV)
    once_cmd.add_argument("--judge-base-url", default=os.environ.get(clean_runner.DEEPSEEK_BASE_URL_ENV))
    once_cmd.add_argument("--judge-thinking", choices=["enabled", "disabled"], default=os.environ.get("DEEPSEEK_THINKING") or clean_runner.DEFAULT_DEEPSEEK_THINKING)
    once_cmd.add_argument("--judge-max-tokens", type=int, default=optional_int(os.environ.get(clean_runner.DEEPSEEK_MAX_TOKENS_ENV)))
    once_cmd.add_argument("--candidate-triage-provider", choices=[candidate_triage.TRIAGE_PROVIDER_NONE, candidate_triage.TRIAGE_PROVIDER_DEEPSEEK], default=candidate_triage.TRIAGE_PROVIDER_NONE, help="Optional DeepSeek duplicate suggestion; only mechanically verified near-duplicates are deferred from Codex.")
    once_cmd.add_argument("--candidate-triage-duplicate-text-similarity", type=float, default=candidate_triage.DEFAULT_DUPLICATE_TEXT_SIMILARITY)
    once_filter = once_cmd.add_mutually_exclusive_group()
    once_filter.add_argument("--filter-ineligible-slices", dest="filter_ineligible_slices", action="store_true")
    once_filter.add_argument("--no-filter-ineligible-slices", dest="filter_ineligible_slices", action="store_false")
    once_cmd.set_defaults(filter_ineligible_slices=None)
    once_cmd.add_argument("--no-import-pg", action="store_true")
    once_cmd.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "env_file", None) is not None:
        load_env_file(args.env_file)
    if args.command == "apply-schema":
        dsn = resolve_dsn(args.dsn_env)
        apply_schema(dsn, schema_name=args.pg_schema)
        payload = {"ok": True, "action": "apply_schema", "schema_name": args.pg_schema}
    elif args.command == "enqueue-from-candidates":
        dsn = resolve_dsn(args.dsn_env)
        job = job_from_candidates(candidates_path=args.candidates, cache_root=args.cache_root, run_root=args.run_root, priority=args.priority)
        payload = {"ok": True, "schema_name": args.pg_schema, "job": job, "enqueue": enqueue_job(dsn=dsn, job=job, schema_name=args.pg_schema)}
    elif args.command == "extract-from-candidates":
        payload = extract_from_candidates(
            candidates_path=args.candidates,
            cache_root=args.cache_root,
            run_root=args.run_root,
            codex_bin=args.codex_bin,
            judge_timeout_seconds=args.judge_timeout,
            judge_shard_size=args.judge_shard_size,
            judge_shard_workers=args.judge_shard_workers,
            judge_provider=args.judge_provider,
            judge_model=args.judge_model,
            judge_api_key_env=args.judge_api_key_env,
            judge_base_url=args.judge_base_url,
            judge_thinking=args.judge_thinking,
            judge_max_tokens=args.judge_max_tokens,
            filter_ineligible_slices=args.filter_ineligible_slices,
            candidate_triage_provider=args.candidate_triage_provider,
            candidate_triage_duplicate_text_similarity=args.candidate_triage_duplicate_text_similarity,
            import_pg=bool(args.import_pg),
            dsn_env=args.dsn_env,
            schema_name=args.pg_schema,
        )
    elif args.command == "plan":
        dsn = resolve_dsn(args.dsn_env)
        job = fetch_next_ready_job(dsn=dsn, schema_name=args.pg_schema)
        payload = {"ok": True, "status": "idle", "job": None} if job is None else {"ok": True, "status": "planned", "job": dict(job), "plan": job_plan(job)}
    elif args.command == "once":
        dsn = resolve_dsn(args.dsn_env)
        payload = once(
            dsn=dsn,
            worker_id=args.worker_id,
            execute=bool(args.execute),
            codex_bin=args.codex_bin,
            judge_timeout_seconds=args.judge_timeout,
            judge_shard_size=args.judge_shard_size,
            judge_shard_workers=args.judge_shard_workers,
            judge_provider=args.judge_provider,
            judge_model=args.judge_model,
            judge_api_key_env=args.judge_api_key_env,
            judge_base_url=args.judge_base_url,
            judge_thinking=args.judge_thinking,
            judge_max_tokens=args.judge_max_tokens,
            filter_ineligible_slices=args.filter_ineligible_slices,
            candidate_triage_provider=args.candidate_triage_provider,
            candidate_triage_duplicate_text_similarity=args.candidate_triage_duplicate_text_similarity,
            import_pg=not bool(args.no_import_pg),
            dsn_env=args.dsn_env,
            schema_name=args.pg_schema,
        )
    else:  # pragma: no cover
        raise ClaimExtractionWorkerError(f"unsupported command: {args.command}")
    write_json(getattr(args, "output_json", None), payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
