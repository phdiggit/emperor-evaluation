from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Any, Mapping, Sequence
from uuid import uuid4

from emperor_v4.evaluation.i5b_current_value_runner import (
    build_i5b_current_value,
    render_scoring_detail_markdown,
)
from emperor_v4.runtime.emperor_rebuild import RebuildLimits, rebuild_emperor


SCHEMA_VERSION = "emperor-rebuild-background-request-v1"
RESULT_SCHEMA_VERSION = "emperor-rebuild-background-result-v1"
RETRYABLE_EXIT_CODE = 75


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _safe_token(value: object, *, field: str) -> str:
    token = str(value or "")
    if not token or any(part in token for part in ("/", "\\", "..")):
        raise ValueError(f"{field} 含非法路径字符")
    return token


def _make_tree_owner_writable(root: Path) -> None:
    if not root.exists():
        return
    for path in (root, *root.rglob("*")):
        path.chmod(path.stat().st_mode | stat.S_IWUSR)


def _prepare_workspace(
    *, release_root: Path, workspace_root: Path, ruler: str
) -> None:
    workspace_root.mkdir(parents=True, exist_ok=True)
    _make_tree_owner_writable(workspace_root)
    shutil.copytree(
        release_root / "config",
        workspace_root / "config",
        dirs_exist_ok=True,
    )
    _make_tree_owner_writable(workspace_root / "config")
    source = release_root / "eval/i5b_current_value" / ruler / "source-pack.json"
    if not source.is_file():
        raise ValueError(f"release 不含皇帝 source-pack: {ruler}")
    target = workspace_root / "eval/i5b_current_value" / ruler / "source-pack.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def run_background_request(
    *,
    request_path: Path,
    release_root: Path,
    state_root: Path,
    source_index_root: Path,
    dynasty_governance_root: Path,
) -> dict[str, object]:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if request.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("后台皇帝任务请求 schema 不支持")
    task_code = _safe_token(request.get("task_code"), field="task_code")
    ruler = _safe_token(request.get("ruler"), field="ruler")
    if request_path.stem != task_code:
        raise ValueError("后台皇帝任务文件名必须等于 task_code")
    max_attempts = int(request.get("max_attempts", 4))
    if not 1 <= max_attempts <= 8:
        raise ValueError("max_attempts 必须介于 1 到 8")
    limits_payload = dict(request.get("limits") or {})
    limits = RebuildLimits(**limits_payload)
    release_root = release_root.resolve()
    job_root = (state_root / "jobs" / task_code).resolve()
    if state_root.resolve() not in job_root.parents:
        raise ValueError("后台皇帝任务状态目录越界")
    result_path = job_root / "result.json"
    input_fingerprint = _digest(
        {
            "request": request,
            "release": release_root.name,
            "source_pack_sha256": sha256(
                (release_root / "eval/i5b_current_value" / ruler / "source-pack.json").read_bytes()
            ).hexdigest(),
        }
    )
    if result_path.is_file():
        current = json.loads(result_path.read_text(encoding="utf-8"))
        if (
            current.get("input_fingerprint") == input_fingerprint
            and current.get("status") == "succeeded"
        ):
            return {**current, "reused": True}
    else:
        current = {}
    attempt_count = (
        int(current.get("attempt_count", 0)) + 1
        if current.get("input_fingerprint") == input_fingerprint
        else 1
    )
    marker = job_root / "input.json"
    if marker.is_file():
        previous = json.loads(marker.read_text(encoding="utf-8"))
        if previous.get("input_fingerprint") != input_fingerprint:
            exports = job_root / "exports"
            if exports.exists():
                _make_tree_owner_writable(exports)
                shutil.rmtree(exports)
    workspace_root = job_root / "workspace"
    _prepare_workspace(
        release_root=release_root,
        workspace_root=workspace_root,
        ruler=ruler,
    )
    _atomic_json(
        marker,
        {
            "schema_version": SCHEMA_VERSION,
            "task_code": task_code,
            "ruler": ruler,
            "input_fingerprint": input_fingerprint,
        },
    )
    try:
        rebuild = rebuild_emperor(
            workspace_root=workspace_root,
            ruler=ruler,
            source_index_path=None,
            source_index_root=source_index_root,
            dynasty_governance_root=dynasty_governance_root,
            runtime_root=job_root / "runtime",
            limits=limits,
        )
        source_pack_path = workspace_root / "eval/i5b_current_value" / ruler / "source-pack.json"
        report = build_i5b_current_value(source_pack_path, workspace_root=workspace_root)
        exports = job_root / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        (exports / "scoring-detail.md").write_text(
            render_scoring_detail_markdown(report), encoding="utf-8", newline="\n"
        )
        person_root = exports / "persons"
        person_root.mkdir(parents=True, exist_ok=True)
        for member in json.loads(source_pack_path.read_text(encoding="utf-8")).get("members") or ():
            person = str(member["person"])
            (person_root / f"{person}.md").write_text(
                render_scoring_detail_markdown(report, person=person),
                encoding="utf-8",
                newline="\n",
            )
        result = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "succeeded",
            "task_code": task_code,
            "ruler": ruler,
            "input_fingerprint": input_fingerprint,
            "reused": False,
            "rebuild": rebuild,
            "exports": str(exports),
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "attempt_count": attempt_count,
            "max_attempts": max_attempts,
            "retryable": False,
            "terminal": True,
        }
    except Exception as exc:
        retryable = isinstance(exc, TimeoutError) and attempt_count < max_attempts
        result = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "failed",
            "task_code": task_code,
            "ruler": ruler,
            "input_fingerprint": input_fingerprint,
            "reused": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "attempt_count": attempt_count,
            "max_attempts": max_attempts,
            "retryable": retryable,
            "terminal": not retryable,
            "database_write_count": 0,
            "formal_score_write_count": 0,
        }
    _atomic_json(result_path, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="单皇帝全链路后台任务")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--source-index-root", type=Path, required=True)
    parser.add_argument("--dynasty-governance-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_background_request(
        request_path=args.request,
        release_root=args.release_root,
        state_root=args.state_root,
        source_index_root=args.source_index_root,
        dynasty_governance_root=args.dynasty_governance_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["status"] == "succeeded":
        return 0
    return RETRYABLE_EXIT_CODE if result.get("retryable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
