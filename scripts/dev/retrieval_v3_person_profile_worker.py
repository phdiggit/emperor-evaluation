from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v3_judgment_worklists as judgments  # noqa: E402
from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import write_json  # noqa: E402


def claim_job(cur: Any, *, worker_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        update retrieval_v3.person_profile_jobs j
           set status='running',stage='judgment',attempt_count=j.attempt_count+1,
               worker_id=%s,lease_expires_at=now()+interval '40 minutes',updated_at=now()
         where j.id=(
             select id from retrieval_v3.person_profile_jobs
              where attempt_count < max_attempts
                and available_at <= now()
                and (status='pending' or (status='running' and lease_expires_at < now()))
              order by available_at,id for update skip locked limit 1
         )
        returning j.*
        """,
        (worker_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def extract_fallback(last_message: Path, patch_path: Path) -> bool:
    if not last_message.exists():
        return False
    content = last_message.read_text(encoding="utf-8")
    begin = content.find(judgments.PATCH_JSONL_BEGIN)
    end = content.find(judgments.PATCH_JSONL_END, begin + len(judgments.PATCH_JSONL_BEGIN))
    if begin < 0 or end < 0:
        return False
    payload = content[begin + len(judgments.PATCH_JSONL_BEGIN):end].strip()
    if not payload:
        return False
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(payload + "\n", encoding="utf-8")
    return True


def execute_task(task: Mapping[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
    prompt_path = ROOT / str(task["prompt_path"])
    patch_path = ROOT / str(task["patch_path"])
    last_message = ROOT / str(task["last_message_path"])
    argv = [str(value) for value in task["argv"]]
    exec_index = argv.index("exec")
    argv.insert(exec_index, "--search")
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        input=prompt_path.read_text(encoding="utf-8"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        env=os.environ.copy(),
        check=False,
    )
    if not patch_path.exists():
        extract_fallback(last_message, patch_path)
    return {
        "task_code": task["task_code"],
        "returncode": completed.returncode,
        "patch_exists": patch_path.exists(),
        "stderr": completed.stderr[-2000:],
    }


def update_job(cur: Any, *, job_id: int, status: str, stage: str, error: str = "", result: Mapping[str, Any] | None = None) -> None:
    cur.execute(
        """
        update retrieval_v3.person_profile_jobs
           set status=%s,stage=%s,last_error=%s,result_payload=%s::jsonb,
               lease_expires_at=null,available_at=case when %s in ('failed','pending') then now()+interval '2 minutes' else available_at end,
               updated_at=now()
         where id=%s
        """,
        (status, stage, error[:4000], json.dumps(dict(result or {}), ensure_ascii=False), status, job_id),
    )


def run_once(*, dsn: str, worker_id: str, output_root: Path, timeout_seconds: int) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            job = claim_job(cur, worker_id=worker_id)
        conn.commit()
    if not job:
        return {"status": "idle"}

    job_id = int(job["id"])
    object_id = int(job["object_id"])
    run_root = output_root / str(job["job_code"]) / f"attempt-{job['attempt_count']}"
    try:
        workitems = judgments.build_workitems(
            dsn=dsn,
            item_code="I5B",
            kinds=[judgments.PERSON_TALENT_KIND, judgments.PERSON_NEGATIVE_TALENT_KIND],
            object_ids=[object_id],
        )
        if not workitems:
            raise judgments.JudgmentWorklistError(f"no profile workitems for object_id={object_id}")
        expected_kinds = {str(row.get("task_kind")) for row in workitems}
        judgments.write_worklist_outputs(output_root=run_root, workitems=workitems, batch_size=1)
        tasks = judgments.load_tasks(run_root / "codex_tasks.jsonl")
        executions = [execute_task(task, timeout_seconds=timeout_seconds) for task in tasks]
        if any(row["returncode"] != 0 or not row["patch_exists"] for row in executions):
            raise judgments.JudgmentWorklistError(f"profile judgment task failed: {executions}")
        patch_rows = [row for task in tasks for row in judgments.read_jsonl(ROOT / str(task["patch_path"]))]
        kinds = {str(row.get("task_kind")) for row in patch_rows}
        if kinds != expected_kinds:
            raise judgments.JudgmentWorklistError(f"profile patch kinds {sorted(kinds)} != {sorted(expected_kinds)}")
        apply_result = judgments.apply_patch_rows(dsn=dsn, rows=patch_rows, execute=True)
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("select retrieval_v3.refresh_person_profile_readiness(%s)", (object_id,))
                cur.execute("select readiness_status::text from retrieval_v3.person_profiles where object_id=%s", (object_id,))
                readiness = str(cur.fetchone()["readiness_status"])
                if readiness != "profile_complete":
                    raise judgments.JudgmentWorklistError(f"profile readiness is {readiness}, expected profile_complete")
                result = {"object_id": object_id, "readiness_status": readiness, "executions": executions, "apply": apply_result}
                update_job(cur, job_id=job_id, status="succeeded", stage="profile_complete", result=result)
            conn.commit()
        return {"status": "succeeded", **result}
    except Exception as exc:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                final_status = "failed" if int(job["attempt_count"]) >= int(job["max_attempts"]) else "pending"
                update_job(cur, job_id=job_id, status=final_status, stage="retry_wait", error=str(exc))
            conn.commit()
        return {"status": "failed", "object_id": object_id, "error": str(exc)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Complete talent and negative-risk profiles for claim-ready people.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    parser.add_argument("--worker-id", default="retrieval_v3_person_profile_worker")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    payload = run_once(
        dsn=resolve_dsn(args.dsn_env),worker_id=args.worker_id,output_root=args.output_root,
        timeout_seconds=max(1,args.timeout_seconds),
    )
    payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    if args.output_json is not None:
        write_json(args.output_json,payload)
    print(json.dumps(payload,ensure_ascii=False,sort_keys=True))
    return 0 if payload["status"] in {"idle","succeeded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
