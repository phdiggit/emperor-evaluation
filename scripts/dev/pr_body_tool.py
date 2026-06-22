from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWED_FENCE_LANGUAGES = {"", "bash", "json", "python", "text"}
DAMAGED_FENCE_PATTERNS = (
    re.compile(r"^`\\[A-Za-z]", re.MULTILINE),
    re.compile(r"^`[A-Za-z][A-Za-z0-9_-]*\s*$", re.MULTILINE),
)


class PrBodyError(ValueError):
    pass


def _repo_root() -> Path:
    return ROOT.resolve()


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = _repo_root() / candidate
    return candidate.resolve(strict=False)


def read_body_text(path: str | Path) -> str:
    try:
        text = _resolve_path(path).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PrBodyError(f"body file is not valid UTF-8: {path}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_body_text(path: str | Path, text: str) -> None:
    target = _resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.replace("\r\n", "\n").replace("\r", "\n"), encoding="utf-8", newline="\n")


def _format_char(char: str) -> str:
    return f"U+{ord(char):04X}"


def _find_control_chars(text: str) -> list[str]:
    return sorted(
        {
            _format_char(char)
            for char in text
            if (ord(char) < 32 and char not in {"\n", "\t"}) or ord(char) == 127
        }
    )


def _validate_code_fences(text: str) -> list[str]:
    errors: list[str] = []
    fence_lines = [(index, line.strip()) for index, line in enumerate(text.splitlines(), start=1) if line.strip().startswith("```")]

    if len(fence_lines) % 2 != 0:
        errors.append("triple-backtick code fences must be paired")

    for pair_index, (line_number, line) in enumerate(fence_lines):
        if pair_index % 2 == 1:
            if line != "```":
                errors.append(f"line {line_number}: closing code fence must be plain ```")
            continue
        language = line[3:].strip()
        if language not in ALLOWED_FENCE_LANGUAGES:
            errors.append(f"line {line_number}: unsupported code fence language: {language or '<empty>'}")

    return errors


def _validate_final_changed_files(text: str) -> list[str]:
    errors: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "Final Changed Files" not in line:
            continue
        for following in lines[index + 1 :]:
            stripped = following.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                break
            if stripped.startswith("`") and not stripped.startswith("```"):
                errors.append("Final Changed Files code block must use standard triple-backtick fences")
            break
    return errors


def validate_text(text: str) -> list[str]:
    errors: list[str] = []
    controls = _find_control_chars(text)
    if controls:
        errors.append(f"control characters are not allowed: {', '.join(controls)}")
    if "\ufffd" in text:
        errors.append("Unicode replacement character U+FFFD is not allowed")
    if "???" in text:
        errors.append("obvious encoding anomaly ??? is not allowed")
    for pattern in DAMAGED_FENCE_PATTERNS:
        if pattern.search(text):
            errors.append("damaged Markdown code fence is not allowed")
            break
    errors.extend(_validate_code_fences(text))
    errors.extend(_validate_final_changed_files(text))
    return errors


def validate_file(path: str | Path) -> None:
    errors = validate_text(read_body_text(path))
    if errors:
        raise PrBodyError("; ".join(errors))


def normalize_file(input_path: str | Path, output_path: str | Path) -> None:
    text = read_body_text(input_path)
    errors = validate_text(text)
    if errors:
        raise PrBodyError("; ".join(errors))
    write_body_text(output_path, text)
    read_body_text(output_path)


def apply_pr_body(pr_number: str, body_file: str | Path) -> None:
    validate_file(body_file)
    if shutil.which("gh") is None:
        raise PrBodyError("gh CLI is not available; PR body file was preserved")
    subprocess.run(
        ["gh", "pr", "edit", str(pr_number), "--body-file", str(_resolve_path(body_file))],
        cwd=_repo_root(),
        check=True,
    )


def _emit_stdout(message: str) -> None:
    sys.stdout.buffer.write((message + "\n").encode("utf-8"))


def _emit_stderr(message: str) -> None:
    sys.stderr.buffer.write((message + "\n").encode("utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize, validate, and safely apply GitHub PR bodies.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize_parser = subparsers.add_parser("normalize", help="Normalize a Markdown PR body to UTF-8 no BOM and LF.")
    normalize_parser.add_argument("--input", required=True)
    normalize_parser.add_argument("--output", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a Markdown PR body file.")
    validate_parser.add_argument("body_file")

    apply_parser = subparsers.add_parser("apply", help="Validate then apply a PR body with gh pr edit --body-file.")
    apply_parser.add_argument("--pr", required=True)
    apply_parser.add_argument("--body-file", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "normalize":
            normalize_file(args.input, args.output)
            _emit_stdout(f"normalized PR body: {args.output}")
        elif args.command == "validate":
            validate_file(args.body_file)
            _emit_stdout(f"valid PR body: {args.body_file}")
        elif args.command == "apply":
            apply_pr_body(args.pr, args.body_file)
            _emit_stdout(f"updated PR body for #{args.pr}: {args.body_file}")
        else:  # pragma: no cover - argparse enforces commands
            raise AssertionError(f"unknown command: {args.command}")
    except (PrBodyError, subprocess.CalledProcessError) as exc:
        _emit_stderr(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
