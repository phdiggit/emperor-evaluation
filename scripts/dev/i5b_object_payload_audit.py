from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import object_pool_importer as importer  # noqa: E402


TODO_MARKERS = ("TODO", "TODO_RULE_CODE", "TODO_TALENT_QUALITY", "TODO-SRC")
EMPEROR_META_PLACEHOLDERS = {"not asserted in this candidate payload"}


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload_rows(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict) and isinstance(raw.get("payloads"), list):
        return [row for row in raw["payloads"] if isinstance(row, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _todo_counts(value: Any) -> dict[str, int]:
    counts = {marker: 0 for marker in TODO_MARKERS}
    for text in _walk_strings(value):
        for marker in TODO_MARKERS:
            counts[marker] += text.count(marker)
    return counts


def _issue(issues: list[dict[str, Any]], severity: str, code: str, message: str, **extra: Any) -> None:
    issues.append({"severity": severity, "code": code, "message": message, **extra})


def _audit_emperor_meta(issues: list[dict[str, Any]], emperor: Mapping[str, Any], *, payload_index: int) -> None:
    if "is_founder" in emperor and not isinstance(emperor.get("is_founder"), bool):
        _issue(
            issues,
            "block",
            "emperor_is_founder_required",
            "emperor.is_founder must be true or false when present",
            payload_index=payload_index,
            emperor=emperor.get("name") or "",
        )
    for key in ("succession_mode", "power_origin"):
        value = emperor.get(key)
        if isinstance(value, str) and value.strip().lower() in EMPEROR_META_PLACEHOLDERS:
            _issue(
                issues,
                "block",
                "emperor_meta_placeholder",
                f"emperor.{key} still contains a placeholder",
                payload_index=payload_index,
                emperor=emperor.get("name") or "",
                field=key,
            )


def audit_payload_file(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        raw = _load_json(path)
    except Exception as exc:
        return {
            "path": str(path),
            "ok": False,
            "block_count": 1,
            "warning_count": 0,
            "payload_count": 0,
            "issues": [{"severity": "block", "code": "invalid_json", "message": repr(exc)}],
        }
    rows = _payload_rows(raw)
    if not rows:
        _issue(issues, "block", "empty_payload", "input must be a payload object, payload list, or {payloads: [...]}")
    try:
        payloads = importer.load_payloads(path)
    except Exception as exc:
        payloads = ()
        _issue(issues, "block", "payload_schema_error", "object_pool_importer rejected payload", detail=repr(exc))

    per_payload: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        todo_counts = _todo_counts(row)
        todo_total = todo_counts["TODO"]
        if todo_total:
            _issue(
                issues,
                "block",
                "todo_marker_present",
                "payload still contains TODO markers",
                payload_index=index,
                todo_counts=todo_counts,
            )
        sources = row.get("sources") if isinstance(row.get("sources"), list) else []
        objects = row.get("objects") if isinstance(row.get("objects"), list) else []
        emperor = row.get("emperor") if isinstance(row.get("emperor"), Mapping) else {}
        _audit_emperor_meta(issues, emperor, payload_index=index)
        per_payload.append(
            {
                "payload_index": index,
                "emperor": str(emperor.get("name") or ""),
                "sources": len(sources),
                "objects": len(objects),
                "todo_counts": todo_counts,
            }
        )

    block_count = sum(1 for issue in issues if issue["severity"] == "block")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "path": str(path),
        "ok": block_count == 0,
        "block_count": block_count,
        "warning_count": warning_count,
        "payload_count": len(payloads) if payloads else len(rows),
        "payloads": per_payload,
        "issues": issues,
    }


def build_report(paths: list[Path]) -> dict[str, Any]:
    files = [audit_payload_file(path) for path in paths]
    total_blocks = sum(file["block_count"] for file in files)
    total_warnings = sum(file["warning_count"] for file in files)
    return {
        "generated_at": iso_now(),
        "ok": total_blocks == 0,
        "file_count": len(files),
        "block_count": total_blocks,
        "warning_count": total_warnings,
        "files": files,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# I5B object payload audit",
        "",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- ok: `{str(report.get('ok')).lower()}`",
        f"- files: `{report.get('file_count', 0)}`",
        f"- blocks: `{report.get('block_count', 0)}`",
        f"- warnings: `{report.get('warning_count', 0)}`",
        "",
        "| file | ok | payloads | blocks | TODO | TODO_RULE_CODE | TODO_TALENT_QUALITY | TODO-SRC |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for file in report.get("files") or []:
        totals = {marker: 0 for marker in TODO_MARKERS}
        for payload in file.get("payloads") or []:
            for marker, count in (payload.get("todo_counts") or {}).items():
                totals[marker] = totals.get(marker, 0) + int(count)
        lines.append(
            "| {path} | {ok} | {payloads} | {blocks} | {todo} | {rule} | {talent} | {src} |".format(
                path=file.get("path", ""),
                ok=str(file.get("ok")).lower(),
                payloads=file.get("payload_count", 0),
                blocks=file.get("block_count", 0),
                todo=totals.get("TODO", 0),
                rule=totals.get("TODO_RULE_CODE", 0),
                talent=totals.get("TODO_TALENT_QUALITY", 0),
                src=totals.get("TODO-SRC", 0),
            )
        )
    issue_lines = []
    for file in report.get("files") or []:
        for issue in file.get("issues") or []:
            issue_lines.append(f"- `{file.get('path')}` {issue.get('severity')} {issue.get('code')}: {issue.get('message')}")
    if issue_lines:
        lines.extend(["", "## Issues", "", *issue_lines])
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit I5B object payload candidates before importer dry-run or database writes.")
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-block", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_report(args.input)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 1 if args.fail_on_block and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
