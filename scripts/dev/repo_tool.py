from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
BLOCKED_BINARY_SUFFIXES = {
    ".db",
    ".docx",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pptx",
    ".sqlite",
    ".webp",
    ".xlsx",
    ".zip",
}


def _repo_root() -> Path:
    return ROOT.resolve()


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve(strict=False)
    root = _repo_root()
    try:
        resolved.relative_to(root)
    except ValueError as exc:  # pragma: no cover - exercised via tests
        raise ValueError(f"path escapes repo root: {path}") from exc
    return resolved


def _ensure_allowed_text_path(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in BLOCKED_BINARY_SUFFIXES:
        raise ValueError(f"binary files are not supported: {path}")
    if suffix not in TEXT_SUFFIXES:
        raise ValueError(f"unsupported text file extension: {path}")


def _read_utf8_text(path: Path) -> str:
    _ensure_allowed_text_path(path)
    return path.read_text(encoding="utf-8-sig")


def read_text_file(path: str | Path) -> str:
    resolved = _resolve_repo_path(path)
    return _read_utf8_text(resolved)


def write_text_file(path: str | Path, source: str | Path) -> None:
    target = _resolve_repo_path(path)
    _ensure_allowed_text_path(target)
    text = Path(source).read_text(encoding="utf-8-sig")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def replace_text_file(path: str | Path, old: str, new: str) -> int:
    target = _resolve_repo_path(path)
    text = _read_utf8_text(target)
    count = text.count(old)
    if count == 0:
        raise ValueError(f"old text not found: {old}")
    target.write_text(text.replace(old, new), encoding="utf-8")
    return count


def git_output_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=_repo_root(),
        capture_output=True,
        text=False,
        check=True,
    )
    return result.stdout.decode("utf-8").splitlines()


def normalize_repo_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def git_changed_files(*args: str, ignore_prefixes: tuple[str, ...] = (".tmp/",)) -> list[str]:
    paths = {
        normalize_repo_path(line)
        for line in git_output_lines(*args)
        if line.strip()
    }
    return sorted(
        path for path in paths if not any(path.startswith(prefix) for prefix in ignore_prefixes)
    )


def changed_files(base: str = "origin/GPT...HEAD") -> list[str]:
    return git_changed_files("diff", "--name-only", base)


def status_files() -> list[str]:
    paths: set[str] = set()
    for line in git_output_lines("status", "--short", "--untracked-files=normal"):
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        normalized = normalize_repo_path(path)
        if normalized.startswith(".tmp/"):
            continue
        paths.add(normalized)
    return sorted(paths)


def _emit_stdout(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8"))


def _emit_stdout_lines(lines: list[str]) -> None:
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    _emit_stdout(payload)


def _emit_stderr(message: str) -> None:
    sys.stderr.buffer.write((message + "\n").encode("utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UTF-8 safe repo helper for Codex work.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read", help="Read a UTF-8 text file inside the repo.")
    read_parser.add_argument("path")

    write_parser = subparsers.add_parser("write", help="Write a UTF-8 text file from --from.")
    write_parser.add_argument("path")
    write_parser.add_argument("--from", dest="source", required=True)

    replace_parser = subparsers.add_parser(
        "replace", help="Replace all occurrences of --old with --new in a UTF-8 text file."
    )
    replace_parser.add_argument("path")
    replace_parser.add_argument("--old", required=True)
    replace_parser.add_argument("--new", required=True)

    changed_parser = subparsers.add_parser(
        "changed-files", help="Print repo-relative paths from git diff --name-only."
    )
    changed_parser.add_argument("--base", default="origin/GPT...HEAD")

    subparsers.add_parser("status-files", help="Print repo-relative paths from git status.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "read":
            _emit_stdout(read_text_file(args.path))
        elif args.command == "write":
            write_text_file(args.path, args.source)
        elif args.command == "replace":
            _emit_stdout(str(replace_text_file(args.path, args.old, args.new)))
        elif args.command == "changed-files":
            _emit_stdout_lines(changed_files(args.base))
        elif args.command == "status-files":
            _emit_stdout_lines(status_files())
        else:  # pragma: no cover - argparse enforces commands
            raise AssertionError(f"unknown command: {args.command}")
    except Exception as exc:  # pragma: no cover - exercised in CLI tests
        _emit_stderr(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
