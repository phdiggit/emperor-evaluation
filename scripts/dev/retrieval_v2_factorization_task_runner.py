from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_factorization_tasks import patch_path_for_task  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import repo_relative, text  # noqa: E402


RUNNER_SOURCE = "scripts/dev/retrieval_v2_factorization_worklists.py"


class FactorizationTaskRunnerError(ValueError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(dict(json.loads(line)))
    return rows


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_codex_tasks(
    *,
    tasks_path: Path,
    execute: bool,
    background: bool,
    limit: int,
    output: Path | None,
    agent_output_root: Path | None = None,
    codex_win_bin: str = "codex-win",
    max_workers: int = 4,
    timeout_seconds: int = 1800,
    sandbox_profile: str = "local-write",
    permission_profile: str | None = None,
    deny_policy: str | None = None,
    write_roots: Sequence[Path] = (),
    git_snapshot: str | None = None,
    respect_task_argv: bool = False,
    search: bool = False,
) -> dict[str, Any]:
    agent_root = agent_output_root or (tasks_path.parent / "agent_run")
    agent_root.mkdir(parents=True, exist_ok=True)
    tasks_for_agent = tasks_path
    if limit > 0:
        tasks_for_agent = agent_root / "limited_tasks.jsonl"
        write_jsonl(tasks_for_agent, read_jsonl(tasks_path)[:limit])
    argv = [
        codex_win_bin, "agent", "run-plan", "--tasks-jsonl", str(tasks_for_agent),
        "--output-root", str(agent_root), "--cwd", str(ROOT), "--max-workers", str(max(1, max_workers)),
        "--timeout-seconds", str(max(1, timeout_seconds)), "--sandbox-profile", sandbox_profile,
    ]
    if permission_profile:
        argv.extend(["--permission-profile", permission_profile])
    if deny_policy:
        argv.extend(["--deny-policy", deny_policy])
    for write_root in write_roots:
        argv.extend(["--write-root", str(write_root)])
    if git_snapshot:
        argv.extend(["--git-snapshot", git_snapshot])
    if background:
        argv.append("--background")
    if not execute:
        argv.append("--dry-run")
    if respect_task_argv:
        argv.append("--respect-task-argv")
    if search:
        argv.append("--search")
    completed = subprocess.run(
        argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    try:
        agent_payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise FactorizationTaskRunnerError(
            f"codex-win agent run-plan returned non-JSON stdout rc={completed.returncode}: {completed.stdout[:400]}"
        ) from exc
    payload = {
        "generated_by": RUNNER_SOURCE,
        "runner": "codex-win agent run-plan",
        "execute": execute,
        "background": background,
        "returncode": completed.returncode,
        "agent_output_root": repo_relative(agent_root),
        "tasks_jsonl": repo_relative(tasks_for_agent),
        "command": argv,
        "results": agent_payload.get("tasks", []),
        "totals": agent_payload.get("totals", {}),
        "agent": agent_payload,
    }
    if completed.stderr:
        payload["stderr"] = completed.stderr
    if output:
        write_json(output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", end="")
    return payload


def resolve_repo_path(value: Any) -> Path:
    path = Path(text(value))
    return path if path.is_absolute() else ROOT / path


def iter_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [text_value for item in value.values() for text_value in iter_text_values(item)]
    if isinstance(value, list):
        return [text_value for item in value for text_value in iter_text_values(item)]
    return []


def extract_patch_rows_from_text(raw_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in raw_text.splitlines():
        candidate = line.strip()
        if not (candidate.startswith("{") and "binding_code" in candidate):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        binding_code = text(payload.get("binding_code")) if isinstance(payload, Mapping) else ""
        if binding_code and binding_code not in seen:
            seen.add(binding_code)
            rows.append(dict(payload))
    return rows


def recover_rows_for_task(task: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    sources: list[str] = []

    def add_rows(candidates: Sequence[Mapping[str, Any]], source: Path) -> None:
        added = 0
        for payload in candidates:
            binding_code = text(payload.get("binding_code"))
            if binding_code and binding_code not in seen:
                seen.add(binding_code)
                rows.append(dict(payload))
                added += 1
        if added:
            sources.append(repo_relative(source))

    last_message_path = resolve_repo_path(task.get("last_message_path"))
    if last_message_path.exists():
        add_rows(extract_patch_rows_from_text(last_message_path.read_text(encoding="utf-8")), last_message_path)
    log_path = resolve_repo_path(task.get("log_path"))
    if log_path.exists() and int(task.get("material_count") or 0) != len(rows):
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            for value in iter_text_values(event):
                if "binding_code" in value:
                    add_rows(extract_patch_rows_from_text(value), log_path)
    return rows, sources


def patch_status(rows: Sequence[Mapping[str, Any]], *, expected: int) -> str:
    return "missing" if not rows else "complete" if expected > 0 and len(rows) == expected else "partial"


def render_recovery_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 factorization patch recovery", "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- tasks_jsonl: `{payload.get('tasks_jsonl', '')}`", "",
        "| task | batch | status | recovered | patch |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for task in payload.get("tasks") or []:
        lines.append(
            f"| `{task.get('task_code')}` | `{task.get('batch_id')}` | `{task.get('status')}` | "
            f"{task.get('recovered')}/{task.get('expected')} | `{task.get('patch_path')}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def recover_task_patches(*, tasks_path: Path, output_json: Path | None, output_md: Path | None) -> dict[str, Any]:
    recovered: list[dict[str, Any]] = []
    for task in read_jsonl(tasks_path):
        rows, sources = recover_rows_for_task(task)
        patch_path = patch_path_for_task(task)
        expected = int(task.get("material_count") or 0)
        existing_rows = read_jsonl(patch_path) if patch_path.exists() else []
        existing_status = patch_status(existing_rows, expected=expected)
        recovered_status = patch_status(rows, expected=expected)
        written = False
        if existing_status == "complete":
            status, final_count, source_mode = "complete", len(existing_rows), "existing_preserved"
        elif recovered_status == "complete":
            write_jsonl(patch_path, rows)
            status, final_count, source_mode, written = "complete", len(rows), "recovered_complete", True
        elif existing_rows and len(existing_rows) >= len(rows):
            status, final_count, source_mode = existing_status, len(existing_rows), "existing_partial_preserved"
        elif rows:
            write_jsonl(patch_path, rows)
            status, final_count, source_mode, written = "partial", len(rows), "recovered_partial", True
        else:
            status, final_count, source_mode = "missing", 0, "missing"
        recovered.append({
            "task_code": text(task.get("task_code")), "batch_id": text(task.get("batch_id")),
            "expected": expected, "recovered": final_count, "recovered_from_logs": len(rows),
            "existing": len(existing_rows), "status": status, "source_mode": source_mode,
            "written": written, "patch_path": repo_relative(patch_path), "sources": sources,
        })
    totals = Counter(row["status"] for row in recovered)
    payload = {
        "generated_by": RUNNER_SOURCE,
        "command": "recover-patches",
        "ok": all(row["status"] == "complete" for row in recovered),
        "tasks_jsonl": repo_relative(tasks_path),
        "totals": dict(sorted(totals.items())),
        "tasks": recovered,
    }
    if output_json:
        write_json(output_json, payload)
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_recovery_markdown(payload), encoding="utf-8")
    return payload
