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

from scripts.dev import retrieval_v2_object_source_cache as object_cache  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402


DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
DEFAULT_OUTPUT_ROOT = ROOT / "tmp" / "retrieval_v2_object_source_cache_runs"
DEFAULT_PAGE_CACHE_ROOT = ROOT / "tmp" / "retrieval_v2_source_pages"


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


def apply_schema(target_dsn: str) -> None:
    psycopg, dict_row = import_psycopg()
    sql = (ROOT / "db" / "migrations" / "20260708_retrieval_v2_object_source_cache_jobs.sql").read_text(encoding="utf-8")
    with psycopg.connect(target_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
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


def enqueue_job(*, dsn: str, job: Mapping[str, Any]) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            job_id = upsert_job(cur, job)
        conn.commit()
    return {"job_id": job_id, "job_code": job["job_code"], "idem_key": job["idem_key"]}


def claim_ready_job(*, dsn: str, worker_id: str, lease_minutes: int = 240) -> dict[str, Any] | None:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
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


def fetch_next_ready_job(*, dsn: str) -> dict[str, Any] | None:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
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


def once(
    *,
    dsn: str,
    worker_id: str,
    execute: bool,
    max_docs_per_person: int = 6,
) -> dict[str, Any]:
    job = claim_ready_job(dsn=dsn, worker_id=worker_id) if execute else fetch_next_ready_job(dsn=dsn)
    if job is None:
        return {"ok": True, "status": "idle", "job": None}
    plan = job_plan(job)
    run_code = "OSCRUN-" + stable_hash([job.get("job_code"), time.time()], length=16)
    input_fingerprint = stable_hash(job)
    if not execute:
        return {"ok": True, "status": "planned", "job": dict(job), "plan": plan}
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            run_id = create_job_run(cur, job=job, worker_id=worker_id, run_code=run_code, input_fingerprint=input_fingerprint)
        conn.commit()
    try:
        result = execute_job(job=job, max_docs_per_person=max_docs_per_person)
    except Exception as exc:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
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
        with conn.cursor() as cur:
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
    schema.add_argument("--output-json", type=Path)

    enqueue = sub.add_parser("enqueue-from-seed", help="Create one object source cache job from seed JSONL.")
    enqueue.add_argument("--seed-jsonl", type=Path, required=True)
    enqueue.add_argument("--output-root", type=Path)
    enqueue.add_argument("--page-cache-root", type=Path, default=DEFAULT_PAGE_CACHE_ROOT)
    enqueue.add_argument("--priority", type=int, default=100)
    enqueue.add_argument("--env-file", type=Path)
    enqueue.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    enqueue.add_argument("--output-json", type=Path)
    add_build_args(enqueue)

    plan = sub.add_parser("plan", help="Show the next ready object source cache job without taking a lease.")
    plan.add_argument("--env-file", type=Path)
    plan.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    plan.add_argument("--output-json", type=Path)

    once_cmd = sub.add_parser("once", help="Claim and optionally execute one ready object source cache job.")
    once_cmd.add_argument("--env-file", type=Path)
    once_cmd.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    once_cmd.add_argument("--worker-id", default="retrieval_v2_object_source_cache_worker")
    once_cmd.add_argument("--execute", action="store_true")
    once_cmd.add_argument("--max-docs-per-person", type=int, default=6)
    once_cmd.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "env_file", None) is not None:
        load_env_file(args.env_file)
    dsn = resolve_dsn(args.dsn_env)
    if args.command == "apply-schema":
        apply_schema(dsn)
        payload = {"ok": True, "action": "apply_schema"}
    elif args.command == "enqueue-from-seed":
        job = job_from_seed(
            seed_jsonl=args.seed_jsonl,
            output_root=args.output_root,
            page_cache_root=args.page_cache_root,
            priority=args.priority,
            build_options=build_options_from_args(args),
        )
        payload = {"ok": True, "job": job, "enqueue": enqueue_job(dsn=dsn, job=job)}
    elif args.command == "plan":
        job = fetch_next_ready_job(dsn=dsn)
        payload = {"ok": True, "status": "idle", "job": None} if job is None else {"ok": True, "status": "planned", "job": dict(job), "plan": job_plan(job)}
    elif args.command == "once":
        payload = once(dsn=dsn, worker_id=args.worker_id, execute=bool(args.execute), max_docs_per_person=args.max_docs_per_person)
    else:  # pragma: no cover
        raise ObjectSourceCacheWorkerError(f"unsupported command: {args.command}")
    write_json(getattr(args, "output_json", None), payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
