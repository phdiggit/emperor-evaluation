from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import object_pool_importer as importer  # noqa: E402

DEFAULT_RECEIPT_LOG = Path("tmp/i5b-object-payload-work/import_receipts/i5b_object_payload_import_receipts.jsonl")


@dataclass(frozen=True)
class PendingPayload:
    display_path: str
    path: Path
    payload_sha256: str
    payload: importer.ImportPayload

    @property
    def person(self) -> str:
        return self.payload.emperor.name


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected JSON object")
    return raw


def ready_payload_paths(board: dict[str, Any]) -> list[str]:
    ready = board.get("ready_for_import_payloads")
    if not isinstance(ready, list):
        raise ValueError("control board missing ready_for_import_payloads list")
    paths: list[str] = []
    for index, row in enumerate(ready):
        if isinstance(row, str):
            paths.append(row)
            continue
        if isinstance(row, dict) and isinstance(row.get("path"), str):
            paths.append(str(row["path"]))
            continue
        raise ValueError(f"ready_for_import_payloads[{index}]: expected path string")
    return paths


def assert_board_importable(board: dict[str, Any], *, allow_board_blocks: bool = False) -> None:
    summary = board.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("control board missing summary object")
    blocked = int(summary.get("blocked") or 0)
    if allow_board_blocks:
        return
    if summary.get("ok") is not True:
        raise ValueError("control board is not ok; refuse to import")
    if blocked > 0:
        raise ValueError("control board has blocked payloads; refuse to import")


def payload_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_success_receipts(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    keys: set[tuple[str, str]] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            continue
        if row.get("dry_run") is True:
            continue
        person = row.get("person")
        digest = row.get("payload_sha256")
        if isinstance(person, str) and isinstance(digest, str):
            keys.add((person, digest))
    return keys


def build_pending_payloads(paths: list[str], receipt_log: Path) -> tuple[list[PendingPayload], list[dict[str, Any]]]:
    imported_keys = load_success_receipts(receipt_log)
    pending: list[PendingPayload] = []
    skipped: list[dict[str, Any]] = []
    seen_ready_keys: set[tuple[str, str]] = set()

    for display_path in paths:
        path = Path(display_path)
        digest = payload_sha256(path)
        payloads = importer.load_payloads(path)
        if len(payloads) != 1:
            raise ValueError(f"{display_path}: expected exactly one payload candidate")
        payload = payloads[0]
        key = (payload.emperor.name, digest)
        row = {
            "person": payload.emperor.name,
            "payload_path": display_path,
            "payload_sha256": digest,
        }
        if key in imported_keys:
            skipped.append({**row, "reason": "already_imported"})
            continue
        if key in seen_ready_keys:
            skipped.append({**row, "reason": "duplicate_ready_payload"})
            continue
        seen_ready_keys.add(key)
        pending.append(PendingPayload(display_path=display_path, path=path, payload_sha256=digest, payload=payload))
    return pending, skipped


def append_receipts(
    receipt_log: Path,
    *,
    control_board: Path,
    pending: list[PendingPayload],
    import_reports: list[dict[str, Any]],
) -> None:
    receipt_log.parent.mkdir(parents=True, exist_ok=True)
    stamp = utc_now()
    with receipt_log.open("a", encoding="utf-8", newline="\n") as handle:
        for payload, report in zip(pending, import_reports, strict=True):
            row = {
                "schema_version": 1,
                "generated_at": stamp,
                "control_board": str(control_board),
                "payload_path": payload.display_path,
                "payload_sha256": payload.payload_sha256,
                "person": payload.person,
                "dry_run": False,
                "import_report": report,
            }
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def import_ready_payloads(
    *,
    control_board: Path,
    receipt_log: Path,
    dsn_env: str,
    dry_run: bool,
    allow_board_blocks: bool = False,
) -> dict[str, Any]:
    board = load_json(control_board)
    assert_board_importable(board, allow_board_blocks=allow_board_blocks)
    summary = board.get("summary") if isinstance(board.get("summary"), dict) else {}
    ready_paths = ready_payload_paths(board)
    pending, skipped = build_pending_payloads(ready_paths, receipt_log)

    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "ok": True,
        "dry_run": dry_run,
        "control_board": str(control_board),
        "receipt_log": str(receipt_log),
        "board_ok": summary.get("ok"),
        "board_blocked": int(summary.get("blocked") or 0),
        "allow_board_blocks": allow_board_blocks,
        "ready_count": len(ready_paths),
        "pending_count": len(pending),
        "skipped_count": len(skipped),
        "imported_count": 0,
        "skipped": skipped,
        "imported": [],
        "unsourced": [],
    }
    if not pending:
        return report

    import_report = importer.import_payloads(
        tuple(row.payload for row in pending),
        importer.resolve_dsn(dsn_env),
        dry_run=dry_run,
    )
    payload_reports = import_report["payloads"]
    report["imported_count"] = len(payload_reports)
    report["unsourced"] = import_report["unsourced"]
    report["imported"] = [
        {
            "person": pending_row.person,
            "payload_path": pending_row.display_path,
            "payload_sha256": pending_row.payload_sha256,
            "counts": payload_report.get("counts", {}),
        }
        for pending_row, payload_report in zip(pending, payload_reports, strict=True)
    ]
    if not dry_run:
        append_receipts(
            receipt_log,
            control_board=control_board,
            pending=pending,
            import_reports=payload_reports,
        )
    return report


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# I5B object payload import batch",
        "",
        f"- ok: {str(report['ok']).lower()}",
        f"- dry_run: {str(report['dry_run']).lower()}",
        f"- ready_count: {report['ready_count']}",
        f"- pending_count: {report['pending_count']}",
        f"- imported_count: {report['imported_count']}",
        f"- skipped_count: {report['skipped_count']}",
        f"- unsourced: {len(report['unsourced'])}",
    ]
    if report["imported"]:
        lines.extend(["", "## Imported"])
        for row in report["imported"]:
            counts = row.get("counts", {})
            lines.append(
                f"- {row['person']}: objects={counts.get('objects', 0)}, "
                f"obj_srcs={counts.get('obj_srcs', 0)}, sources={counts.get('sources', 0)}"
            )
    if report["skipped"]:
        lines.extend(["", "## Skipped"])
        for row in report["skipped"]:
            lines.append(f"- {row['person']}: {row['reason']}")
    return "\n".join(lines) + "\n"


def write_output(path: Path | None, text: str) -> None:
    if path is None:
        print(text, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import ready I5B object payloads from a next-stage control board.")
    parser.add_argument("--control-board", type=Path, required=True, help="JSON output from i5b_next_stage_control_board.py.")
    parser.add_argument("--receipt-log", type=Path, default=DEFAULT_RECEIPT_LOG, help="JSONL import receipt log.")
    parser.add_argument("--dsn-env", default=importer.DEFAULT_DSN_ENV, help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--dry-run", action="store_true", help="Run import in a rolled-back transaction and skip receipts.")
    parser.add_argument(
        "--allow-board-blocks",
        action="store_true",
        help="Import ready_for_import_payloads even when other control-board rows are blocked.",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="Write report here instead of stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = import_ready_payloads(
            control_board=args.control_board,
            receipt_log=args.receipt_log,
            dsn_env=args.dsn_env,
            dry_run=args.dry_run,
            allow_board_blocks=args.allow_board_blocks,
        )
    except Exception as exc:
        error_report = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "ok": False,
            "error": str(exc),
        }
        text = (
            json.dumps(error_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else f"# I5B object payload import batch\n\n- ok: false\n- error: {exc}\n"
        )
        write_output(args.output, text)
        return 1

    text = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else format_markdown(report)
    )
    write_output(args.output, text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
