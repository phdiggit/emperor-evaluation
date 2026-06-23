from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import constants as c


def _repo_root() -> Path:
    return c.ROOT.resolve()


def normalize_repo_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").strip()


def _repo_relative(path: Path) -> str:
    return normalize_repo_path(path.resolve(strict=False).relative_to(_repo_root()))


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = _repo_root() / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(_repo_root())
    except ValueError as exc:
        raise ValueError(f"path escapes repo root: {path}") from exc
    return resolved


def _ensure_tmp_output(output: str | None) -> Path | None:
    if not output:
        return None
    target = _resolve_repo_path(output)
    if not _repo_relative(target).startswith(".tmp/"):
        raise ValueError(f"output must be under .tmp/: {output}")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _ensure_report_output(output: str | None) -> Path | None:
    if not output:
        return None
    target = _resolve_repo_path(output)
    if _repo_relative(target) != c.DEFAULT_REPORT_OUTPUT:
        raise ValueError(f"report output must be {c.DEFAULT_REPORT_OUTPUT}: {output}")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _emit_stdout(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8"))


def _emit_stderr(text: str) -> None:
    sys.stderr.buffer.write((text + "\n").encode("utf-8"))


def git_output_bytes(*args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=_repo_root(),
        capture_output=True,
        text=False,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout


def git_output_text(*args: str, check: bool = True) -> str:
    return git_output_bytes(*args, check=check).decode("utf-8")


def git_lines(*args: str) -> list[str]:
    return [normalize_repo_path(line) for line in git_output_text(*args).splitlines() if line.strip()]


def _git_blob(ref: str, path: str) -> bytes:
    return git_output_bytes("show", f"{ref}:{path}")


def _is_text_path(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    if Path(path).name == ".gitignore":
        return True
    return suffix in c.TEXT_SUFFIXES


def _decode_text(data: bytes) -> str | None:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _normalized_text(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip() + "\n"


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(payload: Any, output: str | None) -> None:
    text = _json_text(payload)
    target = _ensure_tmp_output(output)
    if target:
        target.write_text(text, encoding="utf-8", newline="\n")
    else:
        _emit_stdout(text)


def _load_json_file(path: str | Path) -> dict[str, Any]:
    resolved = _resolve_repo_path(path)
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{normalize_repo_path(path)}: invalid JSON: {exc}") from exc


def _path_exists(path: str) -> bool:
    return _resolve_repo_path(path).exists()


def _uses_forward_slashes(path: str) -> bool:
    return "\\" not in path


def _valid_repo_target_path(path: str) -> bool:
    if not path or not _uses_forward_slashes(path):
        return False
    if path in c.PLACEMENT_TARGET_EXACT_PATHS:
        return True
    if path.startswith(("/", "./", "../")):
        return False
    if re.match(r"^[A-Za-z]:", path):
        return False
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if any(char in path for char in "*?"):
        return False
    return path.startswith(c.PLACEMENT_TARGET_ROOTS)


def _tracked_current_docs() -> list[str]:
    return sorted(path for path in git_lines("ls-files", "docs") if path.startswith("docs/"))


def _tracked_archive_docs() -> list[str]:
    return sorted(path for path in git_lines("ls-files", c.ARCHIVE_DOCS_ROOT) if path.startswith(c.ARCHIVE_DOCS_ROOT))


def _status_path_entries(line: str) -> tuple[str, str | None]:
    status = line[:2]
    raw_path = normalize_repo_path(line[3:])
    if " -> " in raw_path:
        old_path, new_path = raw_path.split(" -> ", 1)
        return normalize_repo_path(new_path), normalize_repo_path(old_path)
    return raw_path, None


def _worktree_files(*roots: str) -> list[str]:
    paths = set(git_lines("ls-files", *roots))
    status_lines = git_output_text("status", "--porcelain=v1", "--untracked-files=all", "--", *roots).splitlines()
    for line in status_lines:
        if not line or len(line) < 4:
            continue
        status = line[:2]
        path, old_path = _status_path_entries(line)
        if old_path:
            paths.discard(old_path)
        if "D" in status and "R" not in status:
            paths.discard(path)
            continue
        paths.add(path)
    return sorted(path for path in paths if path and not path.startswith(".tmp/"))


def _worktree_current_docs() -> list[str]:
    return sorted(path for path in _worktree_files("docs") if path.startswith("docs/"))


def _worktree_archive_docs() -> list[str]:
    return sorted(path for path in _worktree_files(c.ARCHIVE_DOCS_ROOT) if path.startswith(c.ARCHIVE_DOCS_ROOT))
