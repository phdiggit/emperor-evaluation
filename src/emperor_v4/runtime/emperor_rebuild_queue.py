from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Sequence

from emperor_v4.runtime.emperor_rebuild_worker import run_background_request


QUEUE_SCHEMA_VERSION = "emperor-rebuild-background-queue-tick-v1"


def _claim_lock(lock_path: Path, *, stale_seconds: int = 2_100) -> int | None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            if time.time() - lock_path.stat().st_mtime <= stale_seconds:
                return None
            lock_path.unlink()
            return os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except (FileNotFoundError, FileExistsError):
            return None


def run_queue_tick(
    *,
    release_root: Path,
    state_root: Path,
    source_index_root: Path,
    dynasty_governance_root: Path,
) -> dict[str, object]:
    lock_path = state_root / "queue.lock"
    lock_fd = _claim_lock(lock_path)
    if lock_fd is None:
        return {"schema_version": QUEUE_SCHEMA_VERSION, "status": "busy"}
    try:
        os.write(lock_fd, str(os.getpid()).encode("ascii"))
        requests = sorted((state_root / "requests").glob("*.json"))
        selected: Path | None = None
        for request_path in requests:
            result_path = state_root / "jobs" / request_path.stem / "result.json"
            if result_path.is_file():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if result.get("status") == "succeeded" or result.get("terminal") is True:
                    continue
            selected = request_path
            break
        if selected is None:
            return {
                "schema_version": QUEUE_SCHEMA_VERSION,
                "status": "idle",
                "request_count": len(requests),
            }
        try:
            result = run_background_request(
                request_path=selected,
                release_root=release_root,
                state_root=state_root,
                source_index_root=source_index_root,
                dynasty_governance_root=dynasty_governance_root,
            )
        except Exception as exc:
            result = {
                "status": "queue_rejected",
                "task_code": selected.stem,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "terminal": True,
            }
            rejected_path = state_root / "jobs" / selected.stem / "result.json"
            rejected_path.parent.mkdir(parents=True, exist_ok=True)
            rejected_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        return {
            "schema_version": QUEUE_SCHEMA_VERSION,
            "status": "processed",
            "task_code": selected.stem,
            "job_status": result["status"],
            "retryable": bool(result.get("retryable")),
        }
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="无人值守皇帝重建请求队列")
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--source-index-root", type=Path, required=True)
    parser.add_argument("--dynasty-governance-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_queue_tick(
        release_root=args.release_root,
        state_root=args.state_root,
        source_index_root=args.source_index_root,
        dynasty_governance_root=args.dynasty_governance_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
