from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_claim_cache as claim_cache  # noqa: E402
from scripts.dev import retrieval_v2_claim_extraction_worker as claim_worker  # noqa: E402
from scripts.dev import retrieval_v2_claim_plan_quality as claim_plan_quality  # noqa: E402
from scripts.dev import retrieval_v2_claim_quality as claim_quality  # noqa: E402
from scripts.dev import retrieval_v2_object_source_cache as object_cache  # noqa: E402
from scripts.dev.retrieval_v2_contracts import alias_script_variants, source_hints_from_source_targets, unique_strings  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, render_sql, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_OUTPUT_ROOT = ROOT / "tmp" / "retrieval_v2_object_source_cache_runs"
DEFAULT_PAGE_CACHE_ROOT = ROOT / "tmp" / "retrieval_v2_source_pages"
DEFAULT_CLAIM_CACHE_ROOT = ROOT / "tmp" / "retrieval_v2_claim_cache"
PROFILE_SIGNAL_WEIGHTS = {
    "historical_core": 80,
    "core": 70,
    "top": 70,
    "major": 55,
    "important": 40,
    "major_sycophant": 65,
    "major_power_holder": 65,
    "power_abuse_actor": 60,
    "chancellor": 60,
    "prime_minister": 60,
    "minister": 45,
    "founding_minister": 55,
    "founding_merit": 55,
    "merit_official": 45,
    "general": 45,
    "military_commander": 45,
    "strategist": 45,
    "empress": 40,
    "consort": 35,
    "relative": 35,
    "rebel": 35,
    "top_talent": 55,
    "historical_talent": 55,
    "major_talent": 45,
    "important_talent": 35,
    "丞相": 60,
    "相臣": 60,
    "权臣": 60,
    "奸臣": 55,
    "功臣": 55,
    "开国功臣": 55,
    "名将": 45,
    "将领": 45,
    "谋臣": 45,
    "后妃": 40,
    "外戚": 35,
}
PROFILE_LAYER_PRIORITY = {
    "core_positive_objects": 120,
    "negative_or_reversal_objects": 95,
    "supplemental_objects": 70,
    "adjacent_split_objects": 30,
}
PROFILE_LAYER_IMPORTANCE = {
    "core_positive_objects": "core",
    "negative_or_reversal_objects": "important",
    "supplemental_objects": "important",
}


class ObjectSourceCacheWorkerError(RuntimeError):
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


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8", newline="\n")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ObjectSourceCacheWorkerError(f"{path}: expected JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ObjectSourceCacheWorkerError(f"{path}:{line_no}: expected JSON object")
        rows.append(payload)
    return rows


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def list_texts(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if text(value) else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [text(item) for item in value if text(item)]
    return []


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def seed_identity(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    emperor_counts: dict[str, int] = {}
    profile_counts: dict[str, int] = {}
    for row in rows:
        for key, counts in (("target_emperor", emperor_counts), ("emperor_name", emperor_counts)):
            value = text(row.get(key))
            if value:
                counts[value] = counts.get(value, 0) + 1
                break
        profile = text(row.get("capture_profile") or row.get("source_profile"))
        if profile:
            profile_counts[profile] = profile_counts.get(profile, 0) + 1
    emperor_name = max(emperor_counts.items(), key=lambda item: item[1])[0] if emperor_counts else ""
    capture_profile = max(profile_counts.items(), key=lambda item: item[1])[0] if profile_counts else ""
    return {"emperor_name": emperor_name, "capture_profile": capture_profile}


def profile_signal_name(row: Mapping[str, Any]) -> str:
    return text(row.get("person_name") or row.get("object_name") or row.get("name"))


def merge_profile_signal(current: Mapping[str, Any] | None, row: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(current or {})
    for key, value in row.items():
        if key == "priority_score":
            merged[key] = max(int(merged.get(key) or 0), int(value or 0))
        elif key == "profile_layers":
            layers = list_texts(merged.get(key)) + list_texts(value)
            merged[key] = sorted(set(layers))
        elif key == "profile_source_persons":
            persons = list_texts(merged.get(key)) + list_texts(value)
            merged[key] = sorted(set(persons))
        elif key not in merged or merged.get(key) in (None, "", [], {}):
            merged[key] = value
    return merged


def profile_layer_signal_rows(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    object_layers = row.get("object_layers")
    if not isinstance(object_layers, Mapping):
        return []
    profile_person = text(row.get("person") or row.get("emperor_name") or row.get("target_emperor"))
    object_aliases = row.get("object_search_aliases") if isinstance(row.get("object_search_aliases"), Mapping) else {}
    signals: list[dict[str, Any]] = []
    for layer, names in object_layers.items():
        layer_name = text(layer)
        if not layer_name:
            continue
        for index, name in enumerate(list_texts(names)):
            priority = PROFILE_LAYER_PRIORITY.get(layer_name, 10)
            signals.append(
                {
                    "person_name": name,
                    "object_name": name,
                    "profile_layer": layer_name,
                    "profile_layers": [layer_name],
                    "profile_source_persons": [profile_person] if profile_person else [],
                    "priority_score": max(1, priority - min(index, 20)),
                    "object_importance": PROFILE_LAYER_IMPORTANCE.get(layer_name, ""),
                    "aliases": list_texts(object_aliases.get(name)) if isinstance(object_aliases, Mapping) else [],
                    "generated_from_profile_object_layers": True,
                }
            )
    return signals


def profile_seed_rows(
    *,
    profile_path: Path,
    emperor_name: str,
    capture_profile: str = "personnel_political_wide",
    include_layers: Sequence[str] = (),
    max_objects: int = 0,
) -> list[dict[str, Any]]:
    layers = {text(layer) for layer in include_layers if text(layer)}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for profile in read_jsonl(profile_path):
        if not profile_signal_row_matches_target(profile, emperor_name):
            continue
        query_profile_id = text(profile.get("query_profile_id"))
        for signal in profile_layer_signal_rows(profile):
            object_name = profile_signal_name(signal)
            layer = text(signal.get("profile_layer"))
            if not object_name or object_name in seen:
                continue
            if layers and layer not in layers:
                continue
            aliases = seed_aliases_for_object(object_name, list_texts(signal.get("aliases")))
            source_hints, matched_source_targets = profile_source_hints_for_object(profile, object_name=object_name, aliases=aliases)
            rows.append(
                {
                    "person_name": object_name,
                    "target_emperor": emperor_name,
                    "capture_profile": capture_profile,
                    "aliases": aliases,
                    "source_hints": source_hints,
                    "source_target_refs": matched_source_targets,
                    "profile_layer": layer,
                    "query_profile_id": query_profile_id,
                    "source": "profile_object_layers",
                }
            )
            seen.add(object_name)
            if max_objects > 0 and len(rows) >= max_objects:
                return rows
    return rows


def seed_aliases_for_object(object_name: str, aliases: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen = {object_name}
    for alias in [*aliases, *alias_script_variants(object_name)]:
        clean = text(alias)
        if not clean or clean in seen:
            continue
        result.append(clean)
        seen.add(clean)
    return result


def profile_source_hints_for_object(profile: Mapping[str, Any], *, object_name: str, aliases: Sequence[str]) -> tuple[list[str], list[str]]:
    source_targets = list_texts(profile.get("source_targets"))
    if not source_targets:
        return [], []
    search_terms = unique_strings([object_name, *aliases, *alias_script_variants(object_name)])
    normalized_terms = [text(term).replace(" ", "") for term in search_terms if text(term)]
    matched_targets = [
        target
        for target in source_targets
        if any(term and term in target.replace(" ", "") for term in normalized_terms)
    ]
    targeted_hints = source_hints_from_source_targets(matched_targets)
    fallback_hints = source_hints_from_source_targets(source_targets)
    return unique_strings([*targeted_hints, *fallback_hints]), matched_targets


def build_profile_seed(
    *,
    profile_path: Path,
    emperor_name: str,
    output_seed_jsonl: Path,
    capture_profile: str = "personnel_political_wide",
    include_layers: Sequence[str] = (),
    max_objects: int = 0,
) -> dict[str, Any]:
    rows = profile_seed_rows(
        profile_path=profile_path,
        emperor_name=emperor_name,
        capture_profile=capture_profile,
        include_layers=include_layers,
        max_objects=max_objects,
    )
    write_jsonl(output_seed_jsonl, rows)
    by_layer: dict[str, int] = {}
    for row in rows:
        layer = text(row.get("profile_layer")) or "unknown"
        by_layer[layer] = by_layer.get(layer, 0) + 1
    return {
        "ok": True,
        "status": "seed_written",
        "profile_path": str(profile_path),
        "emperor_name": emperor_name,
        "capture_profile": capture_profile,
        "output_seed_jsonl": str(output_seed_jsonl),
        "seed_count": len(rows),
        "by_layer": dict(sorted(by_layer.items())),
        "object_names": [str(row.get("person_name")) for row in rows],
        "execute_effect": "write object source cache seed jsonl only; no enqueue, no PG write, no judge execution",
    }


def profile_signal_row_matches_target(row: Mapping[str, Any], target_person: str) -> bool:
    target = text(target_person)
    if not target:
        return True
    owner = text(row.get("person") or row.get("emperor_name") or row.get("target_emperor"))
    return not owner or owner == target


def load_profile_signals(path: Path | None, *, priority_objects: Sequence[str] = (), target_person: str = "") -> dict[str, dict[str, Any]]:
    signals: dict[str, dict[str, Any]] = {}
    if path is not None:
        for row in read_jsonl(path):
            if not profile_signal_row_matches_target(row, target_person):
                continue
            name = profile_signal_name(row)
            if not name:
                for signal in profile_layer_signal_rows(row):
                    signal_name = profile_signal_name(signal)
                    if signal_name:
                        signals[signal_name] = merge_profile_signal(signals.get(signal_name), signal)
                continue
            signals[name] = merge_profile_signal(signals.get(name), row)
    for name in priority_objects:
        clean = text(name)
        if not clean:
            continue
        current = dict(signals.get(clean) or {})
        current["manual_priority"] = True
        current["priority_score"] = max(int(current.get("priority_score") or 0), 100)
        signals[clean] = current
    return signals


def profile_signal_score(row: Mapping[str, Any] | None) -> tuple[int, list[str]]:
    if not isinstance(row, Mapping):
        return 0, []
    score = int(row.get("priority_score") or row.get("claim_priority_score") or 0)
    reasons: list[str] = []
    if score:
        reasons.append(f"priority_score={score}")
    for field in ("importance_tier", "object_importance", "person_tier", "talent_grade", "object_type", "profile_role"):
        value = text(row.get(field))
        if not value:
            continue
        weight = PROFILE_SIGNAL_WEIGHTS.get(value, 0)
        if weight:
            score += weight
            reasons.append(f"{field}:{value}+{weight}")
    for field in ("profile_tags", "role_tags", "object_roles", "roles"):
        for value in list_texts(row.get(field)):
            weight = PROFILE_SIGNAL_WEIGHTS.get(value, 0)
            if weight:
                score += weight
                reasons.append(f"{field}:{value}+{weight}")
    if row.get("manual_priority"):
        reasons.append("manual_priority")
    for layer in list_texts(row.get("profile_layers")):
        reasons.append(f"profile_layer:{layer}")
    return score, reasons


def default_job_output_root(seed_jsonl: Path, job_code: str, output_root: Path) -> Path:
    base = seed_jsonl.stem.replace(" ", "_") or "seed"
    return output_root / f"{base}_{job_code.lower()}"


def job_from_seed(
    *,
    seed_jsonl: Path,
    output_root: Path | None = None,
    page_cache_root: Path | None = None,
    priority: int = 100,
    build_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = read_jsonl(seed_jsonl)
    options = dict(build_options or {})
    page_cache = page_cache_root or DEFAULT_PAGE_CACHE_ROOT
    identity = seed_identity(rows)
    idem_payload = {
        "seed_jsonl_path": str(seed_jsonl),
        "seed_hashes": [stable_hash(row, length=16) for row in rows],
        "page_cache_root": str(page_cache),
        "build_options": options,
    }
    idem_key = "OSCACHE|" + stable_hash(idem_payload, length=24)
    job_code = "OSCACHE-" + stable_hash(idem_key, length=16)
    out_root = output_root or default_job_output_root(seed_jsonl, job_code, DEFAULT_OUTPUT_ROOT)
    return {
        "job_code": job_code,
        "idem_key": idem_key,
        "status": "ready",
        "priority": max(1, int(priority)),
        "emperor_name": identity["emperor_name"],
        "capture_profile": identity["capture_profile"],
        "seed_jsonl_path": str(seed_jsonl),
        "output_root": str(out_root),
        "page_cache_root": str(page_cache),
        "seed_count": len(rows),
        "job_payload": {
            "source": "enqueue-from-seed",
            "seed_jsonl_path": str(seed_jsonl),
            "seed_count": len(rows),
            "seed_hashes": idem_payload["seed_hashes"],
            "build_options": options,
        },
    }


def apply_schema(target_dsn: str, *, schema_name: str = DEFAULT_PG_SCHEMA) -> None:
    psycopg, dict_row = import_psycopg()
    sql = (ROOT / "db" / "migrations" / "20260708_retrieval_v2_object_source_cache_jobs.sql").read_text(encoding="utf-8")
    with psycopg.connect(target_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(render_sql(sql, schema_name=schema_name))
        conn.commit()


def upsert_job(cur: Any, job: Mapping[str, Any]) -> int:
    cur.execute(
        """
        insert into retrieval_v2.object_source_cache_jobs (
            job_code, idem_key, status, priority, emperor_name, capture_profile,
            seed_jsonl_path, output_root, page_cache_root, seed_count, job_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        on conflict (idem_key) do update set
            priority = least(retrieval_v2.object_source_cache_jobs.priority, excluded.priority),
            seed_jsonl_path = excluded.seed_jsonl_path,
            output_root = excluded.output_root,
            page_cache_root = excluded.page_cache_root,
            seed_count = excluded.seed_count,
            job_payload = retrieval_v2.object_source_cache_jobs.job_payload || excluded.job_payload,
            status = case
                when retrieval_v2.object_source_cache_jobs.status::text in ('succeeded', 'running', 'cancelled')
                    then retrieval_v2.object_source_cache_jobs.status
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
            job["capture_profile"],
            job["seed_jsonl_path"],
            job["output_root"],
            job["page_cache_root"],
            job["seed_count"],
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


def claim_ready_job(*, dsn: str, worker_id: str, lease_minutes: int = 240, schema_name: str = DEFAULT_PG_SCHEMA) -> dict[str, Any] | None:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                with picked as (
                    select id
                      from retrieval_v2.object_source_cache_jobs
                     where status in ('ready', 'retry_wait')
                       and attempt_count < max_attempts
                       and (lease_until is null or lease_until < now())
                     order by priority, created_at
                     limit 1
                     for update skip locked
                )
                update retrieval_v2.object_source_cache_jobs j
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
                  from retrieval_v2.object_source_cache_jobs
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
        insert into retrieval_v2.object_source_cache_job_runs (
            run_code, job_id, worker_id, status, input_fingerprint, output_root, run_payload
        )
        values (%s, %s, %s, 'running', %s, %s, %s::jsonb)
        returning id
        """,
        (
            run_code,
            int(job["id"]),
            worker_id,
            input_fingerprint,
            text(job.get("output_root")),
            stable_json({"job_code": job.get("job_code"), "seed_jsonl_path": job.get("seed_jsonl_path")}),
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
    counts: Mapping[str, int] | None = None,
    error_type: str = "",
    error_msg: str = "",
    run_payload: Mapping[str, Any] | None = None,
) -> None:
    safe_counts = dict(counts or {})
    cur.execute(
        """
        update retrieval_v2.object_source_cache_job_runs
           set status = %s,
               ended_at = now(),
               output_fingerprint = %s,
               person_count = %s,
               source_document_count = %s,
               mention_slice_count = %s,
               fetch_error_count = %s,
               review_queue_count = %s,
               run_payload = run_payload || %s::jsonb,
               error_type = %s,
               error_msg = %s
         where id = %s
        """,
        (
            status,
            output_fingerprint,
            int(safe_counts.get("person_count") or 0),
            int(safe_counts.get("source_document_count") or 0),
            int(safe_counts.get("mention_slice_count") or 0),
            int(safe_counts.get("fetch_error_count") or 0),
            int(safe_counts.get("review_queue_count") or 0),
            stable_json(run_payload or {}),
            error_type,
            error_msg,
            run_id,
        ),
    )
    if status == "succeeded":
        cur.execute(
            """
            update retrieval_v2.object_source_cache_jobs
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
            update retrieval_v2.object_source_cache_jobs
               set status = (
                       case when attempt_count >= max_attempts then 'failed' else 'retry_wait' end
                   )::retrieval_v2.rv2_object_source_cache_job_status,
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
    return {
        "job_code": job.get("job_code"),
        "seed_jsonl_path": str(resolve_path(text(job.get("seed_jsonl_path")))),
        "output_root": str(resolve_path(text(job.get("output_root")))),
        "page_cache_root": str(resolve_path(text(job.get("page_cache_root")))),
        "seed_count": int(job.get("seed_count") or 0),
        "execute_effect": "offline object source cache build-shards -> review-audit; no Codex, no consumption scoring",
    }


def build_shards_argv(job: Mapping[str, Any], options: Mapping[str, Any]) -> list[str]:
    argv = [
        "build-shards",
        "--seed-jsonl",
        str(resolve_path(text(job.get("seed_jsonl_path")))),
        "--output-root",
        str(resolve_path(text(job.get("output_root")))),
        "--cache-dir",
        str(resolve_path(text(job.get("page_cache_root")))),
        "--shard-size",
        str(int(options.get("shard_size") or 20)),
        "--shard-timeout",
        str(float(options.get("shard_timeout") or 120.0)),
        "--pages-per-query",
        str(int(options.get("pages_per_query") or 1)),
        "--source-hint-limit",
        str(int(options.get("source_hint_limit") or 1)),
        "--max-search-names",
        str(int(options.get("max_search_names") or 1)),
        "--search-timeout",
        str(int(options.get("search_timeout") or 5)),
        "--fetch-timeout",
        str(int(options.get("fetch_timeout") or 6)),
        "--context-chars",
        str(int(options.get("context_chars") or 220)),
        "--max-slices-per-document",
        str(int(options.get("max_slices_per_document") or 8)),
        "--request-delay",
        str(float(options.get("request_delay") if options.get("request_delay") is not None else 0.05)),
        "--max-retries",
        str(int(options.get("max_retries") if options.get("max_retries") is not None else 1)),
        "--retry-backoff",
        str(float(options.get("retry_backoff") if options.get("retry_backoff") is not None else 0.2)),
        "--max-retry-wait",
        str(float(options.get("max_retry_wait") if options.get("max_retry_wait") is not None else 2.0)),
        "--cache-backend",
        text(options.get("cache_backend")) or "filesystem",
        "--user-agent",
        text(options.get("user_agent")) or object_cache.DEFAULT_USER_AGENT,
    ]
    max_shards = int(options.get("max_shards") or 0)
    if max_shards > 0:
        argv.extend(["--max-shards", str(max_shards)])
    if bool(options.get("rerun_completed")):
        argv.append("--rerun-completed")
    if bool(options.get("stop_on_fetch_errors")):
        argv.append("--stop-on-fetch-errors")
    if bool(options.get("exclude_emperor_annals")):
        argv.append("--exclude-emperor-annals")
    if bool(options.get("cache_refresh")):
        argv.append("--cache-refresh")
    return argv


def summary_counts(output_root: Path) -> dict[str, int]:
    summary_path = output_root / "shard_summary.json"
    summary = read_json(summary_path) if summary_path.exists() else {}
    totals = summary.get("totals") if isinstance(summary.get("totals"), Mapping) else {}
    return {
        "person_count": int(totals.get("persons") or count_jsonl(output_root / "person_coverage.jsonl")),
        "source_document_count": int(totals.get("source_documents") or count_jsonl(output_root / "source_documents.jsonl")),
        "mention_slice_count": int(totals.get("mention_slices") or count_jsonl(output_root / "mention_slices.jsonl")),
        "fetch_error_count": int(totals.get("fetch_errors") or count_jsonl(output_root / "fetch_errors.jsonl")),
        "review_queue_count": int(totals.get("coverage_needs_agent_review") or count_jsonl(output_root / "agent_review_queue.jsonl")),
    }


def execute_job(*, job: Mapping[str, Any], max_docs_per_person: int = 6) -> dict[str, Any]:
    payload = job.get("job_payload") if isinstance(job.get("job_payload"), Mapping) else {}
    options = payload.get("build_options") if isinstance(payload.get("build_options"), Mapping) else {}
    output_root = resolve_path(text(job.get("output_root")))
    build_argv = build_shards_argv(job, options)
    rc = object_cache.main(build_argv)
    if rc != 0:
        raise ObjectSourceCacheWorkerError(f"object source cache build-shards failed with exit code {rc}")
    review_json = output_root / "review_audit.json"
    review_md = output_root / "review_audit.md"
    review_rc = object_cache.main(
        [
            "review-audit",
            "--cache-root",
            str(output_root),
            "--output-json",
            str(review_json),
            "--output-md",
            str(review_md),
            "--max-docs-per-person",
            str(max_docs_per_person),
        ]
    )
    if review_rc != 0:
        raise ObjectSourceCacheWorkerError(f"object source cache review-audit failed with exit code {review_rc}")
    summary_path = output_root / "shard_summary.json"
    summary = read_json(summary_path) if summary_path.exists() else {}
    review = read_json(review_json) if review_json.exists() else {}
    counts = summary_counts(output_root)
    return {
        "output_root": str(output_root),
        "build_argv": build_argv,
        "summary": summary,
        "review_audit": review,
        "counts": counts,
        "artifacts": {
            "summary_json": str(summary_path),
            "review_audit_json": str(review_json),
            "review_audit_md": str(review_md),
        },
    }


def object_cache_document_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "document_code": text(row.get("document_cache_code") or row.get("document_code")),
        "title": text(row.get("source_title") or row.get("title") or row.get("wikisource_title")),
        "url": text(row.get("source_url") or row.get("url")),
        "source_kind": text(row.get("source_kind")) or "wikisource_page",
        "source_role": text(row.get("source_role")),
        "source_shape": text(row.get("source_shape")),
        "object_source_cache": {
            "person_name": text(row.get("person_name")),
            "person_cache_code": text(row.get("person_cache_code")),
            "source_shape": text(row.get("source_shape")),
            "source_role": text(row.get("source_role")),
        },
    }


def object_cache_slice_score(row: Mapping[str, Any], doc: Mapping[str, Any] | None) -> int:
    shape = text((doc or {}).get("source_shape"))
    role = text(row.get("source_role") or (doc or {}).get("source_role"))
    score = 30
    if shape in {"object_biography_candidate", "object_existing_source_candidate", "title_name_candidate"}:
        score += 20
    elif shape == "object_mention_candidate":
        score += 10
    if role == "object_biography":
        score += 8
    score += min(12, len(text(row.get("raw_text"))) // 120)
    return score


def claim_candidate_quality_flags(candidate: Mapping[str, Any]) -> list[str]:
    return claim_plan_quality.claim_candidate_quality_flags(candidate)


def is_claim_candidate_slice_eligible(candidate: Mapping[str, Any]) -> bool:
    return claim_plan_quality.is_claim_candidate_slice_eligible(candidate)


def object_cache_candidate_slice(row: Mapping[str, Any], doc: Mapping[str, Any] | None = None) -> dict[str, Any]:
    document_code = text(row.get("document_cache_code") or row.get("document_code"))
    object_name = text(row.get("person_name") or row.get("object_name"))
    candidate = {
        "slice_code": text(row.get("slice_cache_code")) or "OSS-" + stable_hash(row, length=18),
        "document_code": document_code,
        "object_name": object_name,
        "locator": text(row.get("locator")),
        "score": object_cache_slice_score(row, doc),
        "matched_aliases": [text(alias) for alias in row.get("matched_aliases") or [] if text(alias)],
        "matched_rule_terms": [],
        "matched_outcome_terms": [],
        "matched_role_families": ["object_source_cache"],
        "text": text(row.get("raw_text") or row.get("text") or row.get("quote")),
        "object_source_cache": {
            "person_name": object_name,
            "person_cache_code": text(row.get("person_cache_code")),
            "source_title": text(row.get("source_title") or (doc or {}).get("source_title") or (doc or {}).get("title")),
            "source_role": text(row.get("source_role") or (doc or {}).get("source_role")),
            "source_shape": text((doc or {}).get("source_shape")),
            "slice_cache_code": text(row.get("slice_cache_code")),
            "section_heading": text(row.get("section_heading")),
            "quality_flags": [],
        },
    }
    candidate["object_source_cache"]["quality_flags"] = claim_candidate_quality_flags(candidate)
    return candidate


def selected_object_cache_slices(
    rows: Sequence[Mapping[str, Any]],
    docs_by_code: Mapping[str, Mapping[str, Any]],
    *,
    max_slices_per_person: int,
    max_total_slices: int,
    excluded_object_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    by_person: dict[str, list[dict[str, Any]]] = {}
    excluded = excluded_object_names or set()
    for row in rows:
        document_code = text(row.get("document_cache_code") or row.get("document_code"))
        candidate = object_cache_candidate_slice(row, docs_by_code.get(document_code))
        if not candidate["object_name"] or not candidate["text"]:
            continue
        if candidate["object_name"] in excluded:
            continue
        if not is_claim_candidate_slice_eligible(candidate):
            continue
        by_person.setdefault(candidate["object_name"], []).append(candidate)
    selected: list[dict[str, Any]] = []
    per_person_limit = max(1, int(max_slices_per_person))
    for person_name in sorted(by_person):
        rows_for_person = sorted(
            by_person[person_name],
            key=lambda row: (-int(row.get("score") or 0), str(row.get("document_code")), str(row.get("locator"))),
        )
        selected.extend(rows_for_person[:per_person_limit])
    selected.sort(key=lambda row: (str(row.get("object_name")), -int(row.get("score") or 0), str(row.get("document_code"))))
    if max_total_slices > 0:
        selected = selected[:max_total_slices]
    return selected


def claim_candidate_quality_audit(
    rows: Sequence[Mapping[str, Any]],
    docs_by_code: Mapping[str, Mapping[str, Any]],
    *,
    excluded_object_names: set[str] | None = None,
) -> dict[str, Any]:
    candidates = [
        object_cache_candidate_slice(row, docs_by_code.get(text(row.get("document_cache_code") or row.get("document_code"))))
        for row in rows
    ]
    return claim_plan_quality.claim_candidate_quality_audit(
        candidates,
        excluded_object_names=excluded_object_names,
    )


def claim_plan_audit(
    *,
    source_documents: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    object_names: Sequence[str],
    excluded_object_names: Sequence[str],
    include_target_emperor_object: bool,
    max_slices_per_person: int,
    max_total_slices: int,
    pilot_profile_signals: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    docs_by_code = {
        text(row.get("document_cache_code") or row.get("document_code")): row
        for row in source_documents
        if text(row.get("document_cache_code") or row.get("document_code"))
    }
    by_object: dict[str, dict[str, Any]] = {}
    source_shape_counts: dict[str, int] = {}
    for row in candidates:
        object_name = text(row.get("object_name"))
        document_code = text(row.get("document_code"))
        doc = docs_by_code.get(document_code, {})
        shape = text((row.get("object_source_cache") or {}).get("source_shape") if isinstance(row.get("object_source_cache"), Mapping) else "")
        shape = shape or text(doc.get("source_shape")) or "unknown"
        source_shape_counts[shape] = source_shape_counts.get(shape, 0) + 1
        current = by_object.setdefault(
            object_name,
            {
                "slice_count": 0,
                "document_codes": set(),
                "source_shapes": set(),
                "has_biography_source": False,
                "max_score": 0,
                "profile_signal_score": 0,
                "profile_signal_reasons": [],
            },
        )
        current["slice_count"] += 1
        current["document_codes"].add(document_code)
        current["source_shapes"].add(shape)
        current["has_biography_source"] = bool(current["has_biography_source"]) or shape in {
            "object_biography_candidate",
            "object_existing_source_candidate",
            "title_name_candidate",
        }
        current["max_score"] = max(int(current["max_score"]), int(row.get("score") or 0))
    profile_signals = pilot_profile_signals or {}
    for object_name, current in by_object.items():
        profile_score, profile_reasons = profile_signal_score(profile_signals.get(object_name))
        current["profile_signal_score"] = profile_score
        current["profile_signal_reasons"] = profile_reasons
    normalized_by_object = {
        name: {
            "slice_count": int(payload["slice_count"]),
            "document_count": len(payload["document_codes"]),
            "source_shapes": sorted(payload["source_shapes"]),
            "has_biography_source": bool(payload["has_biography_source"]),
            "max_score": int(payload["max_score"]),
            "profile_signal_score": int(payload["profile_signal_score"]),
            "profile_signal_reasons": list(payload["profile_signal_reasons"]),
            "capped_by_max_slices_per_person": int(payload["slice_count"]) >= max(1, int(max_slices_per_person)),
        }
        for name, payload in sorted(by_object.items())
    }
    return {
        "include_target_emperor_object": include_target_emperor_object,
        "excluded_object_names": sorted(excluded_object_names),
        "object_count": len(object_names),
        "candidate_slice_count": len(candidates),
        "source_shape_counts": dict(sorted(source_shape_counts.items())),
        "by_object": normalized_by_object,
        "max_slices_per_person": max_slices_per_person,
        "max_total_slices": max_total_slices,
    }


def candidate_source_shapes(row: Mapping[str, Any]) -> list[str]:
    payload = row.get("object_source_cache") if isinstance(row.get("object_source_cache"), Mapping) else {}
    shape = text(payload.get("source_shape"))
    return [shape] if shape else ["unknown"]


def select_claim_plan_pilot(
    candidates: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any],
    *,
    pilot_object_limit: int,
    pilot_slices_per_object: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_object = audit.get("by_object") if isinstance(audit.get("by_object"), Mapping) else {}
    object_scores: list[tuple[tuple[int, int, int, int, int, str], str]] = []
    for name, payload in by_object.items():
        if not isinstance(payload, Mapping):
            continue
        profile_score = int(payload.get("profile_signal_score") or 0)
        has_bio = 1 if payload.get("has_biography_source") else 0
        capped = 1 if payload.get("capped_by_max_slices_per_person") else 0
        slice_count = int(payload.get("slice_count") or 0)
        max_score = int(payload.get("max_score") or 0)
        object_scores.append(((-profile_score, -has_bio, -capped, -slice_count, -max_score, str(name)), str(name)))
    selected_objects = [name for _score, name in sorted(object_scores)[: max(1, int(pilot_object_limit))]]
    selected_set = set(selected_objects)
    by_selected: dict[str, list[dict[str, Any]]] = {name: [] for name in selected_objects}
    for row in candidates:
        object_name = text(row.get("object_name"))
        if object_name in selected_set:
            by_selected.setdefault(object_name, []).append(dict(row))
    selected_rows: list[dict[str, Any]] = []
    per_object_limit = max(1, int(pilot_slices_per_object))
    for object_name in selected_objects:
        rows = sorted(
            by_selected.get(object_name, []),
            key=lambda row: (-int(row.get("score") or 0), str(row.get("document_code")), str(row.get("locator"))),
        )
        selected_rows.extend(rows[:per_object_limit])
    selected_rows.sort(key=lambda row: (str(row.get("object_name")), -int(row.get("score") or 0), str(row.get("document_code"))))
    dropped_objects = sorted(set(str(name) for name in by_object) - selected_set)
    return selected_rows, {
        "selection_profile": "pilot",
        "pilot_object_limit": max(1, int(pilot_object_limit)),
        "pilot_slices_per_object": per_object_limit,
        "selected_objects": selected_objects,
        "dropped_objects": dropped_objects,
        "pre_selection_slice_count": len(candidates),
        "selected_slice_count": len(selected_rows),
        "ranking_policy": "prefer profile/object-type signals, biography source, capped objects, larger slice inventory, higher max score",
        "selected_object_scores": {
            name: (by_object.get(name) or {}).get("profile_signal_score", 0)
            for name in selected_objects
        },
    }


def apply_claim_plan_selection(
    candidates: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any],
    *,
    selection_profile: str,
    pilot_object_limit: int,
    pilot_slices_per_object: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if selection_profile == "all":
        return [dict(row) for row in candidates], {
            "selection_profile": "all",
            "selected_objects": sorted({text(row.get("object_name")) for row in candidates if text(row.get("object_name"))}),
            "dropped_objects": [],
            "pre_selection_slice_count": len(candidates),
            "selected_slice_count": len(candidates),
        }
    if selection_profile == "pilot":
        return select_claim_plan_pilot(
            candidates,
            audit,
            pilot_object_limit=pilot_object_limit,
            pilot_slices_per_object=pilot_slices_per_object,
        )
    raise ObjectSourceCacheWorkerError(f"unsupported claim-plan selection profile: {selection_profile}")


def profile_signal_coverage_audit(
    profile_signals: Mapping[str, Mapping[str, Any]] | None,
    *,
    selected_object_names: Sequence[str],
    by_object: Mapping[str, Any],
) -> dict[str, Any]:
    signals = profile_signals or {}
    selected = {text(name) for name in selected_object_names if text(name)}
    inventory = {text(name) for name in by_object if text(name)}
    scored_objects: list[dict[str, Any]] = []
    for name, signal in sorted(signals.items()):
        score, reasons = profile_signal_score(signal)
        if score <= 0:
            continue
        clean = text(name)
        if not clean:
            continue
        scored_objects.append(
            {
                "object_name": clean,
                "profile_signal_score": score,
                "profile_signal_reasons": reasons,
                "has_candidate_slices": clean in inventory,
                "selected": clean in selected,
            }
        )
    without_candidates = [row["object_name"] for row in scored_objects if not row["has_candidate_slices"]]
    dropped_by_selection = [
        row["object_name"]
        for row in scored_objects
        if row["has_candidate_slices"] and not row["selected"]
    ]
    return {
        "profile_signal_object_count": len(scored_objects),
        "selected_profile_signal_objects": [row["object_name"] for row in scored_objects if row["selected"]],
        "profile_objects_without_candidate_slices": without_candidates,
        "profile_objects_dropped_by_selection": dropped_by_selection,
        "undercoverage_risk": bool(without_candidates or dropped_by_selection),
        "objects": scored_objects,
    }


def object_cache_to_claim_candidates(
    *,
    cache_root: Path,
    emperor_name: str = "",
    target_code: str = "",
    rule_code: str = "i5b_item_wide",
    capture_profile: str = "personnel_political_wide",
    max_slices_per_person: int = 12,
    max_total_slices: int = 0,
    include_target_emperor_object: bool = False,
    selection_profile: str = "all",
    pilot_object_limit: int = 4,
    pilot_slices_per_object: int = 8,
    pilot_profile_signals: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    source_documents = read_jsonl(cache_root / "source_documents.jsonl")
    mention_slices = read_jsonl(cache_root / "mention_slices.jsonl")
    coverage_rows = read_jsonl(cache_root / "person_coverage.jsonl") if (cache_root / "person_coverage.jsonl").exists() else []
    excluded_object_names = {emperor_name} if emperor_name and not include_target_emperor_object else set()
    docs_by_code = {
        text(row.get("document_cache_code") or row.get("document_code")): row
        for row in source_documents
        if text(row.get("document_cache_code") or row.get("document_code"))
    }
    candidates = selected_object_cache_slices(
        mention_slices,
        docs_by_code,
        max_slices_per_person=max_slices_per_person,
        max_total_slices=max_total_slices,
        excluded_object_names=excluded_object_names,
    )
    object_names = sorted(
        (
            {text(row.get("person_name")) for row in coverage_rows if text(row.get("person_name"))}
            or {str(row["object_name"]) for row in candidates}
        )
        - excluded_object_names
    )
    audit = claim_plan_audit(
        source_documents=source_documents,
        candidates=candidates,
        object_names=object_names,
        excluded_object_names=sorted(excluded_object_names),
        include_target_emperor_object=include_target_emperor_object,
        max_slices_per_person=max_slices_per_person,
        max_total_slices=max_total_slices,
        pilot_profile_signals=pilot_profile_signals,
    )
    audit["candidate_quality"] = claim_candidate_quality_audit(
        mention_slices,
        docs_by_code,
        excluded_object_names=excluded_object_names,
    )
    selected_candidates, selection = apply_claim_plan_selection(
        candidates,
        audit,
        selection_profile=selection_profile,
        pilot_object_limit=pilot_object_limit,
        pilot_slices_per_object=pilot_slices_per_object,
    )
    selected_object_names = sorted({text(row.get("object_name")) for row in selected_candidates if text(row.get("object_name"))})
    selected_document_codes = {text(row.get("document_code")) for row in selected_candidates if text(row.get("document_code"))}
    slim_docs = [
        object_cache_document_row(row)
        for row in source_documents
        if text(row.get("document_cache_code") or row.get("document_code")) in selected_document_codes
    ]
    audit["selection"] = selection
    audit["profile_signal_coverage"] = profile_signal_coverage_audit(
        pilot_profile_signals,
        selected_object_names=selected_object_names,
        by_object=audit.get("by_object") if isinstance(audit.get("by_object"), Mapping) else {},
    )
    opportunity_estimate = claim_quality.estimate_claim_opportunities(selected_candidates)
    return {
        "schema_version": 1,
        "generated_by": "scripts/dev/retrieval_v2_object_source_cache_worker.py claim-plan",
        "task_identity": {
            "emperor_name": emperor_name,
            "target_code": target_code,
            "rule_code": rule_code,
            "capture_profile": capture_profile,
            "judge_mode": "claim_extraction_only",
        },
        "target_profile": {"primary_name": emperor_name},
        "rule": {"rule_code": rule_code},
        "object_seeds": [{"name": name} for name in selected_object_names],
        "source_documents": slim_docs,
        "candidate_slices": selected_candidates,
        "coverage": {
            "object_slice_counts": {
                name: sum(1 for row in selected_candidates if row.get("object_name") == name)
                for name in selected_object_names
            },
            "objects_without_slices": [
                name for name in selected_object_names if not any(row.get("object_name") == name for row in selected_candidates)
            ],
        },
        "stats": {
            "source_documents": len(slim_docs),
            "mention_slices": len(mention_slices),
            "candidate_slices": len(selected_candidates),
            "pre_selection_candidate_slices": len(candidates),
            "max_slices_per_person": max_slices_per_person,
            "max_total_slices": max_total_slices,
            "excluded_object_count": len(excluded_object_names),
            "selection_profile": selection_profile,
        },
        "claim_bridge": {
            "cache_root": str(cache_root),
            "policy": "object source cache mention_slices converted to claim-only candidates; no judge execution",
        },
        "claim_plan_audit": audit,
        "claim_opportunity_estimate": opportunity_estimate,
    }


def plan_claim_extraction_from_cache(
    *,
    cache_root: Path,
    claim_cache_root: Path,
    output_candidates: Path,
    output_uncovered_candidates: Path,
    emperor_name: str = "",
    target_code: str = "",
    rule_code: str = "i5b_item_wide",
    capture_profile: str = "personnel_political_wide",
    max_slices_per_person: int = 12,
    max_total_slices: int = 0,
    include_target_emperor_object: bool = False,
    selection_profile: str = "all",
    pilot_object_limit: int = 4,
    pilot_slices_per_object: int = 8,
    pilot_profile_signals_path: Path | None = None,
    pilot_priority_objects: Sequence[str] = (),
    enqueue_claim_job: bool = False,
    dsn: str = "",
    claim_run_root: Path | None = None,
    priority: int = 100,
    required_extractor_version: str = "",
    schema_name: str = DEFAULT_PG_SCHEMA,
) -> dict[str, Any]:
    candidates = object_cache_to_claim_candidates(
        cache_root=cache_root,
        emperor_name=emperor_name,
        target_code=target_code,
        rule_code=rule_code,
        capture_profile=capture_profile,
        max_slices_per_person=max_slices_per_person,
        max_total_slices=max_total_slices,
        include_target_emperor_object=include_target_emperor_object,
        selection_profile=selection_profile,
        pilot_object_limit=pilot_object_limit,
        pilot_slices_per_object=pilot_slices_per_object,
        pilot_profile_signals=load_profile_signals(
            pilot_profile_signals_path,
            priority_objects=pilot_priority_objects,
            target_person=emperor_name,
        ),
    )
    write_json(output_candidates, candidates)
    cache_plan = claim_cache.plan_candidates(
        output_candidates,
        claim_cache_root,
        output_uncovered_candidates,
        required_extractor_version=required_extractor_version or claim_worker.candidate_prompt.CLAIM_EXTRACTOR_VERSION,
    )
    enqueue_result: dict[str, Any] | None = None
    claim_job: dict[str, Any] | None = None
    if enqueue_claim_job and int(cache_plan.get("uncovered_slice_count") or 0) > 0:
        if not dsn:
            raise ObjectSourceCacheWorkerError("--enqueue-claim-job requires a resolved DSN")
        claim_job = claim_worker.job_from_candidates(
            candidates_path=output_uncovered_candidates,
            cache_root=claim_cache_root,
            run_root=claim_run_root or claim_worker.DEFAULT_RUN_ROOT,
            priority=priority,
        )
        enqueue_result = claim_worker.enqueue_job(dsn=dsn, job=claim_job, schema_name=schema_name)
    return {
        "ok": True,
        "status": "planned",
        "cache_root": str(cache_root),
        "claim_cache_root": str(claim_cache_root),
        "output_candidates": str(output_candidates),
        "output_uncovered_candidates": str(output_uncovered_candidates),
        "candidate_slice_count": cache_plan.get("candidate_slice_count"),
        "cached_slice_count": cache_plan.get("cached_slice_count"),
        "uncovered_slice_count": cache_plan.get("uncovered_slice_count"),
        "by_object": cache_plan.get("by_object") or {},
        "claim_plan_audit": candidates.get("claim_plan_audit") or {},
        "claim_opportunity_estimate": candidates.get("claim_opportunity_estimate") or {},
        "enqueue_claim_job": bool(enqueue_claim_job),
        "claim_job": claim_job,
        "enqueue": enqueue_result,
        "execute_effect": "plan claim extraction candidates from object source cache; optional enqueue only, no judge execution",
    }


def once(
    *,
    dsn: str,
    worker_id: str,
    execute: bool,
    max_docs_per_person: int = 6,
    schema_name: str = DEFAULT_PG_SCHEMA,
) -> dict[str, Any]:
    job = claim_ready_job(dsn=dsn, worker_id=worker_id, schema_name=schema_name) if execute else fetch_next_ready_job(dsn=dsn, schema_name=schema_name)
    if job is None:
        return {"ok": True, "status": "idle", "job": None}
    plan = job_plan(job)
    run_code = "OSCRUN-" + stable_hash([job.get("job_code"), time.time()], length=16)
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
        result = execute_job(job=job, max_docs_per_person=max_docs_per_person)
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
                counts=result.get("counts") if isinstance(result.get("counts"), Mapping) else {},
                run_payload=result,
            )
        conn.commit()
    return {"ok": True, "status": "succeeded", "job": dict(job), "result": result}


def build_options_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "shard_size": args.shard_size,
        "shard_timeout": args.shard_timeout,
        "max_shards": args.max_shards,
        "rerun_completed": bool(args.rerun_completed),
        "pages_per_query": args.pages_per_query,
        "source_hint_limit": args.source_hint_limit,
        "max_search_names": args.max_search_names,
        "search_timeout": args.search_timeout,
        "fetch_timeout": args.fetch_timeout,
        "context_chars": args.context_chars,
        "max_slices_per_document": args.max_slices_per_document,
        "stop_on_fetch_errors": bool(args.stop_on_fetch_errors),
        "exclude_emperor_annals": bool(args.exclude_emperor_annals),
        "request_delay": args.request_delay,
        "max_retries": args.max_retries,
        "retry_backoff": args.retry_backoff,
        "max_retry_wait": args.max_retry_wait,
        "cache_backend": args.cache_backend,
        "cache_refresh": bool(args.cache_refresh),
        "user_agent": args.user_agent,
    }


def add_build_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--shard-size", type=int, default=20)
    parser.add_argument("--shard-timeout", type=float, default=120.0)
    parser.add_argument("--max-shards", type=int, default=0)
    parser.add_argument("--rerun-completed", action="store_true")
    parser.add_argument("--pages-per-query", type=int, default=1)
    parser.add_argument("--source-hint-limit", type=int, default=1)
    parser.add_argument("--max-search-names", type=int, default=1)
    parser.add_argument("--search-timeout", type=int, default=5)
    parser.add_argument("--fetch-timeout", type=int, default=6)
    parser.add_argument("--context-chars", type=int, default=220)
    parser.add_argument("--max-slices-per-document", type=int, default=8)
    parser.add_argument("--stop-on-fetch-errors", action="store_true")
    parser.add_argument("--exclude-emperor-annals", action="store_true")
    parser.add_argument("--request-delay", type=float, default=0.05)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--retry-backoff", type=float, default=0.2)
    parser.add_argument("--max-retry-wait", type=float, default=2.0)
    parser.add_argument("--cache-backend", choices=("filesystem", "postgres"), default="filesystem")
    parser.add_argument("--cache-refresh", action="store_true")
    parser.add_argument("--user-agent", default=object_cache.DEFAULT_USER_AGENT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PostgreSQL-backed worker for retrieval_v2 object source cache jobs.")
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("apply-schema", help="Apply object source cache queue schema.")
    schema.add_argument("--env-file", type=Path)
    schema.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    schema.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    schema.add_argument("--output-json", type=Path)

    enqueue = sub.add_parser("enqueue-from-seed", help="Create one object source cache job from seed JSONL.")
    enqueue.add_argument("--seed-jsonl", type=Path, required=True)
    enqueue.add_argument("--output-root", type=Path)
    enqueue.add_argument("--page-cache-root", type=Path, default=DEFAULT_PAGE_CACHE_ROOT)
    enqueue.add_argument("--priority", type=int, default=100)
    enqueue.add_argument("--env-file", type=Path)
    enqueue.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    enqueue.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    enqueue.add_argument("--output-json", type=Path)
    add_build_args(enqueue)

    profile_seed = sub.add_parser("profile-seed", help="Write object source cache seed JSONL from a layered query profile.")
    profile_seed.add_argument("--profile-jsonl", type=Path, required=True)
    profile_seed.add_argument("--emperor-name", required=True)
    profile_seed.add_argument("--output-seed-jsonl", type=Path, required=True)
    profile_seed.add_argument("--capture-profile", default="personnel_political_wide")
    profile_seed.add_argument("--include-layer", action="append", default=[])
    profile_seed.add_argument("--max-objects", type=int, default=0)
    profile_seed.add_argument("--output-json", type=Path)

    plan = sub.add_parser("plan", help="Show the next ready object source cache job without taking a lease.")
    plan.add_argument("--env-file", type=Path)
    plan.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    plan.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    plan.add_argument("--output-json", type=Path)

    once_cmd = sub.add_parser("once", help="Claim and optionally execute one ready object source cache job.")
    once_cmd.add_argument("--env-file", type=Path)
    once_cmd.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    once_cmd.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    once_cmd.add_argument("--worker-id", default="retrieval_v2_object_source_cache_worker")
    once_cmd.add_argument("--execute", action="store_true")
    once_cmd.add_argument("--max-docs-per-person", type=int, default=6)
    once_cmd.add_argument("--output-json", type=Path)

    claim_plan = sub.add_parser("claim-plan", help="Build claim-only candidates from an object source cache and run claim-cache uncovered planning.")
    claim_plan.add_argument("--cache-root", type=Path, required=True)
    claim_plan.add_argument("--claim-cache-root", type=Path, default=DEFAULT_CLAIM_CACHE_ROOT)
    claim_plan.add_argument("--output-candidates", type=Path, required=True)
    claim_plan.add_argument("--output-uncovered-candidates", type=Path, required=True)
    claim_plan.add_argument("--emperor-name", default="")
    claim_plan.add_argument("--target-code", default="")
    claim_plan.add_argument("--rule-code", default="i5b_item_wide")
    claim_plan.add_argument("--capture-profile", default="personnel_political_wide")
    claim_plan.add_argument("--max-slices-per-person", type=int, default=12)
    claim_plan.add_argument("--max-total-slices", type=int, default=0)
    claim_plan.add_argument("--include-target-emperor-object", action="store_true")
    claim_plan.add_argument("--selection-profile", choices=("all", "pilot"), default="all")
    claim_plan.add_argument("--pilot-object-limit", type=int, default=4)
    claim_plan.add_argument("--pilot-slices-per-object", type=int, default=8)
    claim_plan.add_argument("--pilot-profile-signals-jsonl", type=Path)
    claim_plan.add_argument("--pilot-priority-object", action="append", default=[])
    claim_plan.add_argument("--enqueue-claim-job", action="store_true")
    claim_plan.add_argument("--claim-run-root", type=Path, default=claim_worker.DEFAULT_RUN_ROOT)
    claim_plan.add_argument("--priority", type=int, default=100)
    claim_plan.add_argument("--required-extractor-version", default=claim_worker.candidate_prompt.CLAIM_EXTRACTOR_VERSION)
    claim_plan.add_argument("--env-file", type=Path)
    claim_plan.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    claim_plan.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    claim_plan.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "env_file", None) is not None:
        load_env_file(args.env_file)
    needs_dsn = args.command in {"apply-schema", "enqueue-from-seed", "plan", "once"} or bool(getattr(args, "enqueue_claim_job", False))
    dsn = resolve_dsn(args.dsn_env) if needs_dsn else ""
    if args.command == "apply-schema":
        apply_schema(dsn, schema_name=args.pg_schema)
        payload = {"ok": True, "action": "apply_schema", "schema_name": args.pg_schema}
    elif args.command == "enqueue-from-seed":
        job = job_from_seed(
            seed_jsonl=args.seed_jsonl,
            output_root=args.output_root,
            page_cache_root=args.page_cache_root,
            priority=args.priority,
            build_options=build_options_from_args(args),
        )
        payload = {"ok": True, "schema_name": args.pg_schema, "job": job, "enqueue": enqueue_job(dsn=dsn, job=job, schema_name=args.pg_schema)}
    elif args.command == "profile-seed":
        payload = build_profile_seed(
            profile_path=args.profile_jsonl,
            emperor_name=args.emperor_name,
            output_seed_jsonl=args.output_seed_jsonl,
            capture_profile=args.capture_profile,
            include_layers=args.include_layer,
            max_objects=args.max_objects,
        )
    elif args.command == "plan":
        job = fetch_next_ready_job(dsn=dsn, schema_name=args.pg_schema)
        payload = {"ok": True, "status": "idle", "job": None} if job is None else {"ok": True, "status": "planned", "job": dict(job), "plan": job_plan(job)}
    elif args.command == "once":
        payload = once(dsn=dsn, worker_id=args.worker_id, execute=bool(args.execute), max_docs_per_person=args.max_docs_per_person, schema_name=args.pg_schema)
    elif args.command == "claim-plan":
        payload = plan_claim_extraction_from_cache(
            cache_root=args.cache_root,
            claim_cache_root=args.claim_cache_root,
            output_candidates=args.output_candidates,
            output_uncovered_candidates=args.output_uncovered_candidates,
            emperor_name=args.emperor_name,
            target_code=args.target_code,
            rule_code=args.rule_code,
            capture_profile=args.capture_profile,
            max_slices_per_person=args.max_slices_per_person,
            max_total_slices=args.max_total_slices,
            include_target_emperor_object=bool(args.include_target_emperor_object),
            selection_profile=args.selection_profile,
            pilot_object_limit=args.pilot_object_limit,
            pilot_slices_per_object=args.pilot_slices_per_object,
            pilot_profile_signals_path=args.pilot_profile_signals_jsonl,
            pilot_priority_objects=args.pilot_priority_object,
            enqueue_claim_job=bool(args.enqueue_claim_job),
            dsn=dsn,
            claim_run_root=args.claim_run_root,
            priority=args.priority,
            required_extractor_version=args.required_extractor_version,
            schema_name=args.pg_schema,
        )
    else:  # pragma: no cover
        raise ObjectSourceCacheWorkerError(f"unsupported command: {args.command}")
    write_json(getattr(args, "output_json", None), payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
