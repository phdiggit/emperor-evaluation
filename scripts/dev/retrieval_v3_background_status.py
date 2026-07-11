from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def write_text(path: Path | None, payload: str) -> None:
    if path is None:
        print(payload, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")


def write_json(path: Path | None, payload: Mapping[str, Any]) -> None:
    write_text(path, pretty_json(payload))


def rows(cur: Any, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    cur.execute(sql, tuple(params))
    return [dict(row) for row in cur.fetchall()]


def latest_run_code_by_job(cur: Any, *, job_codes: Sequence[str]) -> dict[str, str]:
    clean_codes = [str(code).strip() for code in job_codes if str(code).strip()]
    if not clean_codes:
        return {}
    result = rows(
        cur,
        """
        select distinct on (j.job_code)
               j.job_code, r.run_code
          from retrieval_v3.claim_extraction_jobs j
          join retrieval_v3.claim_extraction_job_runs r on r.job_id = j.id
         where j.job_code = any(%s)
         order by j.job_code, r.started_at desc, r.id desc
        """,
        (clean_codes,),
    )
    return {str(row["job_code"]): str(row["run_code"]) for row in result}


def build_status_report(
    *,
    dsn: str,
    schema_name: str,
    emperors: Sequence[str],
    objects: Sequence[str],
    recent_limit: int = 12,
) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    target_emperors = [str(name).strip() for name in emperors if str(name).strip()]
    target_objects = [str(name).strip() for name in objects if str(name).strip()]
    recent = max(1, int(recent_limit))
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            object_source_status = rows(
                cur,
                """
                select status::text as status, count(*)::int as count
                  from retrieval_v3.object_source_cache_jobs
                 group by status
                 order by status
                """,
            )
            claim_status = rows(
                cur,
                """
                select status::text as status, count(*)::int as count
                  from retrieval_v3.claim_extraction_jobs
                 group by status
                 order by status
                """,
            )
            recent_object_jobs = rows(
                cur,
                """
                select j.job_code, j.status::text as status, j.priority, j.emperor_name, j.seed_count,
                       j.attempt_count, j.locked_by, j.lease_until, j.last_error,
                       j.seed_jsonl_path, j.output_root, j.updated_at,
                       r.run_code as latest_run_code,
                       r.status::text as latest_run_status,
                       r.person_count, r.source_document_count, r.mention_slice_count,
                       r.review_queue_count, r.error_type as latest_error_type, r.error_msg as latest_error_msg,
                       r.run_payload->'claim_bridge_result'->>'status' as claim_bridge_status,
                       r.run_payload->'claim_bridge_result'->>'uncovered_slice_count' as claim_bridge_uncovered_slices,
                       r.run_payload->'claim_bridge_result'->'claim_job'->>'job_code' as claim_job_code
                  from retrieval_v3.object_source_cache_jobs j
                  left join lateral (
                        select *
                          from retrieval_v3.object_source_cache_job_runs
                         where job_id = j.id
                         order by started_at desc, id desc
                         limit 1
                  ) r on true
                 order by j.updated_at desc
                 limit %s
                """,
                (recent,),
            )
            recent_claim_jobs = rows(
                cur,
                """
                select j.job_code, j.status::text as status, j.priority, j.emperor_name, j.target_code,
                       j.rule_code, j.capture_profile, j.uncovered_slice_count, j.attempt_count,
                       j.locked_by, j.lease_until, j.last_error, j.candidate_payload_path,
                       j.run_root, j.cache_root, j.updated_at,
                       r.run_code as latest_run_code,
                       r.status::text as latest_run_status,
                       r.claim_count as latest_claim_count,
                       r.usage_payload as latest_usage_payload,
                       r.error_type as latest_error_type,
                       r.error_msg as latest_error_msg
                  from retrieval_v3.claim_extraction_jobs j
                  left join lateral (
                        select *
                          from retrieval_v3.claim_extraction_job_runs
                         where job_id = j.id
                         order by started_at desc, id desc
                         limit 1
                  ) r on true
                 order by j.updated_at desc
                 limit %s
                """,
                (recent,),
            )
            by_emperor = []
            by_object = []
            if target_emperors:
                by_emperor = rows(
                    cur,
                    """
                    select emperor_name, status::text as status, count(*)::int as claim_count,
                           max(updated_at) as latest_updated_at
                      from retrieval_v3.claim_cache
                     where emperor_name = any(%s)
                     group by emperor_name, status
                     order by emperor_name, status
                    """,
                    (target_emperors,),
                )
            if target_emperors or target_objects:
                by_object = rows(
                    cur,
                    """
                    select emperor_name, object_name, status::text as status, count(*)::int as claim_count,
                           max(updated_at) as latest_updated_at
                      from retrieval_v3.claim_cache
                     where (%s::text[] = '{}'::text[] or emperor_name = any(%s))
                        or (%s::text[] = '{}'::text[] or object_name = any(%s))
                     group by emperor_name, object_name, status
                     order by emperor_name, object_name, status
                    """,
                    (target_emperors, target_emperors, target_objects, target_objects),
                )
            running_claim_jobs = [row for row in recent_claim_jobs if row.get("status") == "running"]
            ready_claim_jobs = [row for row in recent_claim_jobs if row.get("status") == "ready"]
            failed_claim_jobs = [row for row in recent_claim_jobs if row.get("status") in {"failed", "retry_wait"}]
            claim_job_codes = [str(row.get("job_code") or "") for row in recent_claim_jobs]
            run_codes = latest_run_code_by_job(cur, job_codes=claim_job_codes)
    return {
        "ok": True,
        "schema_name": schema_name,
        "targets": {"emperors": target_emperors, "objects": target_objects},
        "queue_summary": {
            "object_source": object_source_status,
            "claim_extraction": claim_status,
        },
        "recent_object_source_jobs": recent_object_jobs,
        "recent_claim_jobs": recent_claim_jobs,
        "latest_claim_run_codes_by_job": run_codes,
        "claim_cache_by_emperor": by_emperor,
        "claim_cache_by_object": by_object,
        "alerts": {
            "running_claim_job_count": len(running_claim_jobs),
            "ready_claim_job_count": len(ready_claim_jobs),
            "failed_or_retry_claim_job_count": len(failed_claim_jobs),
            "zero_claim_target_objects": [
                name
                for name in target_objects
                if not any(row.get("object_name") == name and int(row.get("claim_count") or 0) > 0 for row in by_object)
            ],
        },
        "execute_effect": "read-only PostgreSQL status report; no queue mutation, no worker execution, no claim import",
    }


def count_by_status(rows_payload: Sequence[Mapping[str, Any]]) -> str:
    if not rows_payload:
        return "none"
    return ", ".join(f"{row.get('status')}={row.get('count')}" for row in rows_payload)


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 background status",
        "",
        f"- schema: `{report.get('schema_name')}`",
        f"- object-source queue: {count_by_status(report.get('queue_summary', {}).get('object_source', []))}",
        f"- claim-extraction queue: {count_by_status(report.get('queue_summary', {}).get('claim_extraction', []))}",
        "",
        "## recent object-source jobs",
        "",
        "| job | status | emperor | docs | slices | bridge | claim_job |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in report.get("recent_object_source_jobs", []):
        lines.append(
            "| {job} | {status} | {emperor} | {docs} | {slices} | {bridge} | {claim_job} |".format(
                job=row.get("job_code") or "",
                status=row.get("status") or "",
                emperor=row.get("emperor_name") or "",
                docs=row.get("source_document_count") or 0,
                slices=row.get("mention_slice_count") or 0,
                bridge=row.get("claim_bridge_status") or "",
                claim_job=row.get("claim_job_code") or "",
            )
        )
    lines.extend(
        [
            "",
            "## recent claim jobs",
            "",
            "| job | status | emperor | uncovered | latest_claims | run_code |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in report.get("recent_claim_jobs", []):
        lines.append(
            "| {job} | {status} | {emperor} | {uncovered} | {claims} | {run_code} |".format(
                job=row.get("job_code") or "",
                status=row.get("status") or "",
                emperor=row.get("emperor_name") or "",
                uncovered=row.get("uncovered_slice_count") or 0,
                claims=row.get("latest_claim_count") or 0,
                run_code=row.get("latest_run_code") or "",
            )
        )
    lines.extend(["", "## target claim counts", ""])
    for row in report.get("claim_cache_by_emperor", []):
        lines.append(f"- {row.get('emperor_name')} `{row.get('status')}`: {row.get('claim_count')}")
    zero_objects = report.get("alerts", {}).get("zero_claim_target_objects") or []
    if zero_objects:
        lines.extend(["", "## alerts", ""])
        lines.append("- zero-claim target objects: " + ", ".join(str(name) for name in zero_objects))
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only retrieval_v3 background worker and claim-cache status report.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--emperor", action="append", default=[])
    parser.add_argument("--object", action="append", default=[])
    parser.add_argument("--recent-limit", type=int, default=12)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    report = build_status_report(
        dsn=resolve_dsn(args.dsn_env),
        schema_name=args.pg_schema,
        emperors=args.emperor,
        objects=args.object,
        recent_limit=args.recent_limit,
    )
    if args.output_json is not None:
        write_json(args.output_json, report)
    elif args.output_md is None:
        write_json(None, report)
    if args.output_md is not None:
        write_text(args.output_md, render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
