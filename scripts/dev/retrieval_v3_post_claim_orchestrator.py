from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]


class PostClaimOrchestratorError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def safe_job_code(value: Any) -> str:
    raw = text(value) or "unknown-job"
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in raw)


def build_post_claim_plan(payload: Mapping[str, Any], *, output_root: Path) -> dict[str, Any]:
    if text(payload.get("status")) != "succeeded":
        return {"status": "skipped", "reason": "claim_job_not_succeeded", "commands": []}
    job = payload.get("job") if isinstance(payload.get("job"), Mapping) else {}
    result = payload.get("result") if isinstance(payload.get("result"), Mapping) else {}
    emperor = text(job.get("emperor_name")) or text(result.get("emperor_name"))
    if not emperor:
        raise PostClaimOrchestratorError("succeeded claim job is missing emperor_name")

    job_code = safe_job_code(job.get("job_code"))
    run_root = output_root / job_code
    event_output = run_root / "event_groups.json"
    discovery_json = run_root / "related_object_discovery.json"
    discovery_md = run_root / "related_object_discovery.md"
    discovery_worklist = run_root / "related_object_identity_worklist.jsonl"
    return {
        "status": "ready",
        "job_code": text(job.get("job_code")),
        "emperor_name": emperor,
        "claim_count": int(result.get("claim_count") or 0),
        "output_root": str(run_root),
        "commands": [
            {
                "stage": "semantic_identity",
                "argv": [
                    sys.executable,
                    str(ROOT / "scripts/dev/retrieval_v3_claim_semantic_identity_backfill.py"),
                    "--execute",
                    "--output-json",
                    str(run_root / "semantic_identity.json"),
                ],
            },
            {
                "stage": "event_group_target",
                "argv": [
                    sys.executable,
                    str(ROOT / "scripts/dev/retrieval_v3_claim_event_groups.py"),
                    "--emperor-name",
                    emperor,
                    "--execute",
                    "--replace-existing",
                    "--output-json",
                    str(event_output),
                ],
            },
            {
                "stage": "related_object_discovery",
                "argv": [
                    sys.executable,
                    str(ROOT / "scripts/dev/retrieval_v3_unseeded_actor_discovery.py"),
                    "--emperor",
                    emperor,
                    "--output-json",
                    str(discovery_json),
                    "--output-md",
                    str(discovery_md),
                    "--output-worklist",
                    str(discovery_worklist),
                ],
            },
        ],
        "identity_gate": {
            "required": True,
            "worklist": str(discovery_worklist),
            "automatic_canonical_person_creation": False,
        },
    }


def execute_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if text(plan.get("status")) != "ready":
        return dict(plan)
    Path(text(plan.get("output_root"))).mkdir(parents=True, exist_ok=True)
    executions: list[dict[str, Any]] = []
    for command in plan.get("commands") or []:
        argv = [text(value) for value in command.get("argv") or []]
        completed = subprocess.run(argv, check=False, capture_output=True, text=True, encoding="utf-8")
        execution = {
            "stage": command.get("stage"),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        executions.append(execution)
        if completed.returncode != 0:
            return {**dict(plan), "status": "failed", "executions": executions}
    return {**dict(plan), "status": "succeeded", "executions": executions}


def write_json(path: Path | None, payload: Mapping[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild event groups and discover related actors after one claim job.")
    parser.add_argument("--claim-worker-output", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = json.loads(args.claim_worker_output.read_text(encoding="utf-8"))
    plan = build_post_claim_plan(payload, output_root=args.output_root)
    result = execute_plan(plan) if args.execute else plan
    write_json(args.output_json, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
