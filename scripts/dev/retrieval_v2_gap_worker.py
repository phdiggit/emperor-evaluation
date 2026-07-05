from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_gap_handoff as handoff


DEFAULT_RUN_ROOT = Path("tmp/retrieval_v2_clean_runs/gap_worker")
EXECUTABLE_KINDS = {"codex_source_pack_refine"}
REVIEW_ONLY_KINDS = {"codex_material_review"}
SOURCE_REFINE_TYPES = {
    "source_missing",
    "predicate_missing",
    "civil_undercoverage",
    "negative_undercoverage",
    "weak_alias_noise",
    "core_no_material",
    "core_zero_signal",
}


class GapWorkerError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sanitize_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return token or "gap"


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GapWorkerError(f"{path}: expected JSON object")
    return payload


def write_json(path: Path | None, payload: Mapping[str, Any]) -> None:
    text_payload = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"
    if path is None:
        print(text_payload, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text_payload, encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise GapWorkerError(f"{path}:{lineno}: expected JSON object")
        rows.append(payload)
    return rows


def resolve_artifact(path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if path.exists() or path.is_absolute():
        return str(path)
    candidate = ROOT / path
    return str(candidate if candidate.exists() else path)


def event_from_job(job: Mapping[str, Any]) -> dict[str, Any]:
    payload = job.get("payload") if isinstance(job.get("payload"), Mapping) else {}
    event = payload.get("gap_event") if isinstance(payload.get("gap_event"), Mapping) else {}
    return dict(event)


def job_action(job: Mapping[str, Any]) -> str:
    payload = job.get("payload") if isinstance(job.get("payload"), Mapping) else {}
    return text(payload.get("action"))


def job_code(job: Mapping[str, Any]) -> str:
    return text(job.get("job_code") or event_from_job(job).get("event_code") or job.get("idem_key"))


def group_key(job: Mapping[str, Any]) -> tuple[str, str]:
    event = event_from_job(job)
    artifacts = event.get("artifact_paths") if isinstance(event.get("artifact_paths"), Mapping) else {}
    task_path = text(artifacts.get("task"))
    target_code = text(event.get("target_code"))
    rule_code = text(event.get("rule_code"))
    return (resolve_artifact(task_path), f"{target_code}|{rule_code}")


def unique_texts(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = text(value)
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def clean_runner_argv(
    *,
    jobs: Sequence[Mapping[str, Any]],
    mode: str,
    worker_run_root: Path,
    env_file: Path | None,
    clean_runner: Path,
    python_bin: str,
    candidate_source_refine_max_objects: int,
    candidate_source_refine_pages_per_object: int,
    candidate_source_refine_source_hint_limit: int,
    judge_shard_size: int,
    judge_shard_workers: int,
) -> list[str] | None:
    first_event = event_from_job(jobs[0])
    artifacts = first_event.get("artifact_paths") if isinstance(first_event.get("artifact_paths"), Mapping) else {}
    task_path = resolve_artifact(text(artifacts.get("task")))
    if not task_path:
        return None

    job_codes = [job_code(job) for job in jobs]
    gap_types = unique_texts(event_from_job(job).get("gap_type") for job in jobs)
    objects = unique_texts(event_from_job(job).get("object_name") for job in jobs)
    target_code = text(first_event.get("target_code")) or "target"
    rule_code = text(first_event.get("rule_code")) or "rule"
    group_id = handoff.stable_fingerprint([job_codes, task_path])[:10].upper()
    run_root = worker_run_root / sanitize_token(f"{target_code}_{rule_code}_{group_id}")
    has_alias = "alias_missing" in gap_types or any(job_action(job) == "alias_refine" for job in jobs)
    source_refine_rounds = 1 if any(gap_type in SOURCE_REFINE_TYPES for gap_type in gap_types) else 0
    max_objects = max(1, min(candidate_source_refine_max_objects, len(objects) or candidate_source_refine_max_objects))

    argv = [
        python_bin,
        str(clean_runner),
        "--task",
        task_path,
        "--run-root",
        str(run_root),
        "--max-workers",
        "1",
        "--max-alias-refine-rounds",
        "1" if has_alias else "0",
        "--candidate-source-refine-rounds",
        str(source_refine_rounds),
        "--candidate-source-refine-max-objects",
        str(max_objects),
        "--candidate-source-refine-pages-per-object",
        str(candidate_source_refine_pages_per_object),
        "--candidate-source-refine-source-hint-limit",
        str(candidate_source_refine_source_hint_limit),
        "--judge-shard-size",
        str(judge_shard_size),
        "--judge-shard-workers",
        str(judge_shard_workers),
        "--skip-fetch-errors",
        "--progress",
    ]
    for object_name in objects:
        argv.extend(["--candidate-source-refine-object", object_name])
    if env_file is not None:
        argv[2:2] = ["--env-file", str(env_file)]
    if mode == "candidate-only":
        argv.append("--skip-judge")
    return argv


def plan_from_jobs(
    jobs: Sequence[Mapping[str, Any]],
    *,
    mode: str = "candidate-only",
    worker_run_root: Path = DEFAULT_RUN_ROOT,
    env_file: Path | None = None,
    clean_runner: Path = Path("scripts/dev/retrieval_v2_clean_runner.py"),
    python_bin: str = "python",
    candidate_source_refine_max_objects: int = 8,
    candidate_source_refine_pages_per_object: int = 4,
    candidate_source_refine_source_hint_limit: int = 4,
    judge_shard_size: int = 4,
    judge_shard_workers: int = 4,
) -> dict[str, Any]:
    executable_groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    review_jobs: list[Mapping[str, Any]] = []
    unsupported_jobs: list[Mapping[str, Any]] = []
    for job in jobs:
        kind = text(job.get("kind"))
        if kind in EXECUTABLE_KINDS:
            executable_groups.setdefault(group_key(job), []).append(job)
        elif kind in REVIEW_ONLY_KINDS:
            review_jobs.append(job)
        else:
            unsupported_jobs.append(job)

    entries: list[dict[str, Any]] = []
    for _, group_jobs in sorted(executable_groups.items(), key=lambda item: item[0]):
        first_event = event_from_job(group_jobs[0])
        argv = clean_runner_argv(
            jobs=group_jobs,
            mode=mode,
            worker_run_root=worker_run_root,
            env_file=env_file,
            clean_runner=clean_runner,
            python_bin=python_bin,
            candidate_source_refine_max_objects=candidate_source_refine_max_objects,
            candidate_source_refine_pages_per_object=candidate_source_refine_pages_per_object,
            candidate_source_refine_source_hint_limit=candidate_source_refine_source_hint_limit,
            judge_shard_size=judge_shard_size,
            judge_shard_workers=judge_shard_workers,
        )
        gap_types = unique_texts(event_from_job(job).get("gap_type") for job in group_jobs)
        objects = unique_texts(event_from_job(job).get("object_name") for job in group_jobs)
        entries.append(
            {
                "entry_type": "clean_runner",
                "executable": argv is not None,
                "reason": "" if argv is not None else "missing task artifact path",
                "mode": mode,
                "job_codes": [job_code(job) for job in group_jobs],
                "target_code": text(first_event.get("target_code")),
                "emperor_name": text(first_event.get("emperor_name")),
                "rule_code": text(first_event.get("rule_code")),
                "source_pack_code": text(first_event.get("source_pack_code")),
                "gap_types": gap_types,
                "objects": objects,
                "argv": argv or [],
            }
        )

    for job in review_jobs:
        event = event_from_job(job)
        entries.append(
            {
                "entry_type": "codex_material_review",
                "executable": False,
                "reason": "material review jobs require a dedicated reviewer; clean runner is not invoked",
                "job_codes": [job_code(job)],
                "target_code": text(event.get("target_code")),
                "emperor_name": text(event.get("emperor_name")),
                "rule_code": text(event.get("rule_code")),
                "source_pack_code": text(event.get("source_pack_code")),
                "gap_types": [text(event.get("gap_type"))],
                "objects": [text(event.get("object_name"))] if text(event.get("object_name")) else [],
                "argv": [],
            }
        )
    for job in unsupported_jobs:
        entries.append(
            {
                "entry_type": "unsupported_job",
                "executable": False,
                "reason": f"unsupported job kind: {job.get('kind')}",
                "job_codes": [job_code(job)],
                "argv": [],
            }
        )

    return {
        "generated_by": "scripts/dev/retrieval_v2_gap_worker.py",
        "mode": mode,
        "entries": entries,
        "totals": {
            "jobs": len(jobs),
            "entries": len(entries),
            "executable_entries": sum(1 for entry in entries if entry.get("executable")),
            "review_entries": sum(1 for entry in entries if entry.get("entry_type") == "codex_material_review"),
        },
    }


def fetch_ready_jobs(*, dsn: str, kinds: Sequence[str], limit: int) -> list[dict[str, Any]]:
    psycopg, dict_row = handoff.import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select job_code, idem_key, kind, status, priority, payload
                  from retrieval_v2.jobs
                 where status = 'ready'
                   and kind = any(%s)
                 order by priority, created_at
                 limit %s
                """,
                (list(kinds), limit),
            )
            return [dict(row) for row in cur.fetchall()]


def update_job_statuses(
    *,
    dsn: str,
    job_codes: Sequence[str],
    status: str,
    worker_id: str,
    error: str = "",
) -> int:
    if status not in {"running", "succeeded", "failed"}:
        raise GapWorkerError(f"unsupported DB job status update: {status}")
    codes = unique_texts(job_codes)
    if not codes:
        return 0
    psycopg, _ = handoff.import_psycopg()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            if status == "running":
                cur.execute(
                    """
                    update retrieval_v2.jobs
                       set status = 'running',
                           attempt_count = attempt_count + 1,
                           locked_by = %s,
                           locked_at = now(),
                           lease_until = now() + interval '2 hours',
                           last_error = null,
                           updated_at = now()
                     where job_code = any(%s)
                       and status in ('queued', 'ready', 'retry_wait')
                    returning job_code
                    """,
                    (worker_id, codes),
                )
            else:
                cur.execute(
                    """
                    update retrieval_v2.jobs
                       set status = %s,
                           locked_by = null,
                           locked_at = null,
                           lease_until = null,
                           last_error = nullif(%s, ''),
                           updated_at = now()
                     where job_code = any(%s)
                       and status in ('queued', 'ready', 'running', 'retry_wait')
                    returning job_code
                    """,
                    (status, error, codes),
                )
            rows = cur.fetchall()
        conn.commit()
    return len(rows)


def update_gap_events_for_jobs(
    *,
    dsn: str,
    job_codes: Sequence[str],
    status: str,
) -> int:
    if status not in {"running", "resolved", "retry_wait"}:
        raise GapWorkerError(f"unsupported DB gap event status update: {status}")
    codes = unique_texts(job_codes)
    if not codes:
        return 0
    psycopg, _ = handoff.import_psycopg()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with event_codes as (
                    select payload #>> '{gap_event,event_code}' as event_code
                      from retrieval_v2.jobs
                     where job_code = any(%s)
                )
                update retrieval_v2.coverage_gap_events e
                   set status = %s,
                       updated_at = now()
                 where e.event_code in (
                       select event_code from event_codes where coalesce(event_code, '') <> ''
                 )
                   and e.status in ('queued', 'ready', 'running', 'retry_wait')
                returning e.event_code
                """,
                (codes, status),
            )
            rows = cur.fetchall()
        conn.commit()
    return len(rows)


def load_jobs_from_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for path in args.events_jsonl or []:
        for event in load_jsonl(path):
            job = handoff.job_from_event(event)
            if job is not None:
                jobs.append(job)
    for path in args.jobs_jsonl or []:
        jobs.extend(load_jsonl(path))
    if args.from_db:
        handoff.load_env_file(args.env_file)
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            raise GapWorkerError(f"missing PostgreSQL DSN env var: {args.dsn_env}")
        jobs.extend(fetch_ready_jobs(dsn=dsn, kinds=args.kind, limit=max(1, args.limit)))
    return jobs


def run_plan(
    plan: Mapping[str, Any],
    *,
    execute: bool = False,
    limit: int = 0,
    db_dsn: str = "",
    worker_id: str = "retrieval_v2_gap_worker",
) -> dict[str, Any]:
    entries = [entry for entry in plan.get("entries") or [] if isinstance(entry, Mapping)]
    if limit > 0:
        entries = entries[:limit]
    results: list[dict[str, Any]] = []
    for entry in entries:
        argv = [str(part) for part in entry.get("argv") or []]
        if not entry.get("executable") or not argv:
            results.append({"job_codes": entry.get("job_codes") or [], "status": "skipped", "reason": entry.get("reason")})
            continue
        if not execute:
            results.append({"job_codes": entry.get("job_codes") or [], "status": "planned", "argv": argv})
            continue
        db_running_count = 0
        if db_dsn:
            db_running_count = update_job_statuses(
                dsn=db_dsn,
                job_codes=entry.get("job_codes") or [],
                status="running",
                worker_id=worker_id,
            )
            db_event_running_count = update_gap_events_for_jobs(
                dsn=db_dsn,
                job_codes=entry.get("job_codes") or [],
                status="running",
            )
        else:
            db_event_running_count = 0
        completed = subprocess.run(argv, cwd=ROOT)
        result_status = "succeeded" if completed.returncode == 0 else "failed"
        event_result_status = "resolved" if completed.returncode == 0 else "retry_wait"
        db_done_count = 0
        db_event_done_count = 0
        if db_dsn:
            db_done_count = update_job_statuses(
                dsn=db_dsn,
                job_codes=entry.get("job_codes") or [],
                status=result_status,
                worker_id=worker_id,
                error="" if completed.returncode == 0 else f"clean runner exited {completed.returncode}",
            )
            db_event_done_count = update_gap_events_for_jobs(
                dsn=db_dsn,
                job_codes=entry.get("job_codes") or [],
                status=event_result_status,
            )
        results.append(
            {
                "job_codes": entry.get("job_codes") or [],
                "status": result_status,
                "returncode": completed.returncode,
                "argv": argv,
                "db_running_count": db_running_count,
                "db_done_count": db_done_count,
                "db_event_running_count": db_event_running_count,
                "db_event_done_count": db_event_done_count,
            }
        )
    return {
        "generated_by": "scripts/dev/retrieval_v2_gap_worker.py",
        "execute": execute,
        "results": results,
        "totals": {
            "entries": len(results),
            "succeeded": sum(1 for row in results if row.get("status") == "succeeded"),
            "failed": sum(1 for row in results if row.get("status") == "failed"),
            "skipped": sum(1 for row in results if row.get("status") == "skipped"),
            "planned": sum(1 for row in results if row.get("status") == "planned"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan and optionally run retrieval_v2 gap refinement jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Build a clean-runner execution plan from retrieval_v2.jobs payloads.")
    plan.add_argument("--events-jsonl", type=Path, action="append", default=[])
    plan.add_argument("--jobs-jsonl", type=Path, action="append", default=[])
    plan.add_argument("--from-db", action="store_true")
    plan.add_argument("--env-file", type=Path)
    plan.add_argument("--dsn-env", default=handoff.DEFAULT_DSN_ENV)
    plan.add_argument("--kind", action="append", default=["codex_source_pack_refine", "codex_material_review"])
    plan.add_argument("--limit", type=int, default=50)
    plan.add_argument("--mode", choices=("candidate-only", "judge"), default="candidate-only")
    plan.add_argument("--worker-run-root", type=Path, default=DEFAULT_RUN_ROOT)
    plan.add_argument("--output", type=Path)
    plan.add_argument("--clean-runner", type=Path, default=Path("scripts/dev/retrieval_v2_clean_runner.py"))
    plan.add_argument("--python-bin", default="python")
    plan.add_argument("--candidate-source-refine-max-objects", type=int, default=8)
    plan.add_argument("--candidate-source-refine-pages-per-object", type=int, default=4)
    plan.add_argument("--candidate-source-refine-source-hint-limit", type=int, default=4)
    plan.add_argument("--judge-shard-size", type=int, default=4)
    plan.add_argument("--judge-shard-workers", type=int, default=4)

    run = subparsers.add_parser("run-plan", help="Run or print a plan produced by the plan subcommand.")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--limit", type=int, default=0)
    run.add_argument("--output", type=Path)
    run.add_argument("--env-file", type=Path)
    run.add_argument("--dsn-env", default="")
    run.add_argument("--update-db", action="store_true", help="Update retrieval_v2.jobs lifecycle while executing.")
    run.add_argument("--no-update-db", action="store_true", help="Do not update retrieval_v2.jobs even for DB-sourced plans.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "plan":
        jobs = load_jobs_from_args(args)
        payload = plan_from_jobs(
            jobs,
            mode=args.mode,
            worker_run_root=args.worker_run_root,
            env_file=args.env_file,
            clean_runner=args.clean_runner,
            python_bin=args.python_bin,
            candidate_source_refine_max_objects=args.candidate_source_refine_max_objects,
            candidate_source_refine_pages_per_object=args.candidate_source_refine_pages_per_object,
            candidate_source_refine_source_hint_limit=args.candidate_source_refine_source_hint_limit,
            judge_shard_size=args.judge_shard_size,
            judge_shard_workers=args.judge_shard_workers,
        )
        if args.from_db:
            payload["job_source"] = {
                "from_db": True,
                "dsn_env": args.dsn_env,
                "env_file": str(args.env_file) if args.env_file is not None else "",
            }
        write_json(args.output, payload)
        return 0
    if args.command == "run-plan":
        plan = load_json(args.plan)
        job_source = plan.get("job_source") if isinstance(plan.get("job_source"), Mapping) else {}
        update_db = args.execute and not args.no_update_db and (args.update_db or bool(job_source.get("from_db")))
        db_dsn = ""
        if update_db:
            env_file = args.env_file
            if env_file is None and text(job_source.get("env_file")):
                env_file = Path(text(job_source.get("env_file")))
            handoff.load_env_file(env_file)
            dsn_env = text(args.dsn_env) or text(job_source.get("dsn_env")) or handoff.DEFAULT_DSN_ENV
            db_dsn = os.environ.get(dsn_env, "")
            if not db_dsn:
                raise GapWorkerError(f"missing PostgreSQL DSN env var: {dsn_env}")
        payload = run_plan(plan, execute=args.execute, limit=max(0, args.limit), db_dsn=db_dsn)
        write_json(args.output, payload)
        return 0 if payload["totals"]["failed"] == 0 else 1
    raise GapWorkerError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
