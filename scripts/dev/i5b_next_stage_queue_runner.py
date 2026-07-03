from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_payload_skeleton import build_payload_skeleton  # noqa: E402
from scripts.dev.i5b_source_pack_handoff import (  # noqa: E402
    build_report as build_handoff_report,
    discover_handoff_dirs,
    read_json,
    read_jsonl,
    resolve_pack_path,
)
from scripts.dev.source_excerpt_pool_lib.builder import build_excerpt_pool  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_PROFILE,
    DEFAULT_WORKFLOW_CODE,
    ExcerptPoolError,
    load_source_excerpt_pool_paths,
    normalize_workflow_code,
    workflow_slug,
)
from scripts.dev.source_excerpt_pool_lib.profile import load_profile  # noqa: E402


DEFAULT_OUTPUT_ROOT = ROOT / ".tmp" / "i5b-next-stage"


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def person_slug(person: str) -> str:
    digest = hashlib.sha1(person.encode("utf-8")).hexdigest()[:10]
    return f"person-{digest}"


def count_todo_markers(value: Any) -> int:
    if isinstance(value, dict):
        return sum(count_todo_markers(item) for item in value.values())
    if isinstance(value, list):
        return sum(count_todo_markers(item) for item in value)
    if isinstance(value, str):
        return value.count("TODO")
    return 0


def _read_handoff_jsonl(path: Path, *, required: bool = True) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    rows = read_jsonl(path, issues, required=required)
    return rows, issues


def _read_manifest(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    return read_json(path, issues, label="manifest"), issues


def collect_ready_queue(
    *,
    handoff_root: Path,
    source_pack_root: Path | None,
    workflow_code: str,
    people: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    workflow_code = normalize_workflow_code(workflow_code)
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen_people: set[str] = set()
    for handoff_dir in discover_handoff_dirs(handoff_root):
        manifest, manifest_issues = _read_manifest(handoff_dir / "manifest.json")
        issues.extend(manifest_issues)
        manifest_workflow = normalize_workflow_code(str(manifest.get("workflow_code") or DEFAULT_WORKFLOW_CODE))
        if manifest_workflow != workflow_code:
            continue
        batch_id = str(manifest.get("batch_id") or handoff_dir.name)
        accepted_rows, accepted_issues = _read_handoff_jsonl(handoff_dir / "accepted_packs.jsonl")
        queue_rows, queue_issues = _read_handoff_jsonl(handoff_dir / "next_stage_queue.jsonl")
        issues.extend(accepted_issues)
        issues.extend(queue_issues)
        accepted_by_person = {
            str(row.get("person") or "").strip(): row
            for row in accepted_rows
            if str(row.get("person") or "").strip()
        }
        for queue_row in queue_rows:
            person = str(queue_row.get("person") or "").strip()
            if not person or queue_row.get("ready") is not True:
                continue
            if people is not None and person not in people:
                continue
            if person in seen_people:
                issues.append(
                    {
                        "severity": "block",
                        "code": "duplicate_ready_person",
                        "message": "person appears in multiple ready queue rows",
                        "person": person,
                        "batch_id": batch_id,
                    }
                )
                continue
            seen_people.add(person)
            accepted_row = accepted_by_person.get(person, {})
            accepted_pack_path = queue_row.get("accepted_pack_path") or accepted_row.get("accepted_pack_path")
            pack_path = resolve_pack_path(accepted_pack_path, handoff_dir=handoff_dir, source_pack_root=source_pack_root)
            rows.append(
                {
                    "batch_id": batch_id,
                    "handoff_dir": str(handoff_dir),
                    "person": person,
                    "stage": str(queue_row.get("stage") or ""),
                    "accepted_pack_path": str(pack_path) if pack_path is not None else "",
                }
            )
    return rows, issues


def process_ready_item(
    item: Mapping[str, Any],
    *,
    profile_path: Path,
    output_root: Path,
    workflow_code: str,
    include_adjacent: bool,
    context_chars: int,
    max_passages_per_page: int,
    dry_run: bool,
) -> dict[str, Any]:
    person = str(item.get("person") or "").strip()
    pack_path = Path(str(item.get("accepted_pack_path") or ""))
    item_dir = output_root / workflow_slug(workflow_code) / person_slug(person)
    excerpt_output = item_dir / "source_excerpt_pool.json"
    payload_output = item_dir / "object_payload_skeleton.json"
    result: dict[str, Any] = {
        "person": person,
        "batch_id": item.get("batch_id") or "",
        "stage": item.get("stage") or "",
        "accepted_pack_path": str(pack_path),
        "excerpt_output": str(excerpt_output),
        "payload_output": str(payload_output),
        "status": "planned" if dry_run else "ok",
        "issues": [],
    }
    if dry_run:
        return result
    try:
        profile = load_profile(profile_path, person, workflow_code=workflow_code)
        excerpt_report = build_excerpt_pool(
            profile,
            include_adjacent=include_adjacent,
            offline=True,
            source_pack=pack_path,
            context_chars=context_chars,
            max_passages_per_page=max_passages_per_page,
        )
        payload = build_payload_skeleton(profile, excerpt_report=excerpt_report, include_adjacent=include_adjacent)
        write_json(excerpt_output, excerpt_report)
        write_json(payload_output, payload)
        result.update(
            {
                "excerpt_status": excerpt_report.get("status"),
                "excerpt_count": len(excerpt_report.get("excerpts") or []),
                "object_count": len(payload.get("objects") or []),
                "source_count": len(payload.get("sources") or []),
                "todo_markers": count_todo_markers(payload),
            }
        )
    except Exception as exc:
        result["status"] = "blocked"
        result["issues"].append({"severity": "block", "code": "next_stage_generation_failed", "message": repr(exc)})
    return result


def run_queue(
    *,
    workflow_code: str,
    handoff_root: Path,
    source_pack_root: Path | None,
    profile_path: Path,
    output_root: Path,
    people: set[str] | None = None,
    limit: int | None = None,
    include_adjacent: bool = False,
    context_chars: int = 420,
    max_passages_per_page: int = 4,
    audit_packs: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    workflow_code = normalize_workflow_code(workflow_code)
    handoff_report = build_handoff_report(
        handoff_root,
        source_pack_root=source_pack_root,
        audit_packs=audit_packs,
        workflow_code=workflow_code,
    )
    queue, queue_issues = collect_ready_queue(
        handoff_root=handoff_root,
        source_pack_root=source_pack_root,
        workflow_code=workflow_code,
        people=people,
    )
    if limit is not None:
        queue = queue[:limit]
    items: list[dict[str, Any]] = []
    if handoff_report["ok"] and not any(issue.get("severity") == "block" for issue in queue_issues):
        for item in queue:
            items.append(
                process_ready_item(
                    item,
                    profile_path=profile_path,
                    output_root=output_root,
                    workflow_code=workflow_code,
                    include_adjacent=include_adjacent,
                    context_chars=context_chars,
                    max_passages_per_page=max_passages_per_page,
                    dry_run=dry_run,
                )
            )
    status_counts = Counter(str(item.get("status") or "") for item in items)
    item_blocks = sum(1 for item in items if item.get("status") == "blocked")
    queue_blocks = sum(1 for issue in queue_issues if issue.get("severity") == "block")
    blocked = not handoff_report["ok"] or queue_blocks > 0 or item_blocks > 0
    return {
        "schema_version": 1,
        "generated_at": iso_now(),
        "workflow_code": workflow_code,
        "dry_run": dry_run,
        "ok": not blocked,
        "handoff": {
            "root": str(handoff_root),
            "ok": handoff_report["ok"],
            "batches": handoff_report["batch_count"],
            "ready_people": handoff_report["ready_people"],
            "blocks": handoff_report["block_count"],
            "warnings": handoff_report["warning_count"],
        },
        "paths": {
            "profile": str(profile_path),
            "source_pack_root": str(source_pack_root) if source_pack_root is not None else "",
            "output_root": str(output_root),
        },
        "queue_count": len(queue),
        "status_counts": dict(sorted(status_counts.items())),
        "queue_issues": queue_issues,
        "items": items,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        f"# {report.get('workflow_code')} next-stage queue run",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- dry_run: `{str(report.get('dry_run')).lower()}`",
        f"- ok: `{str(report.get('ok')).lower()}`",
        f"- handoff_ready_people: `{len((report.get('handoff') or {}).get('ready_people') or [])}`",
        f"- queue_count: `{report.get('queue_count', 0)}`",
        f"- status_counts: `{json.dumps(report.get('status_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        "",
        "| person | status | excerpts | objects | sources | TODO | payload |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.get("items") or []:
        lines.append(
            "| {person} | {status} | {excerpts} | {objects} | {sources} | {todo} | `{payload}` |".format(
                person=item.get("person", ""),
                status=item.get("status", ""),
                excerpts=item.get("excerpt_count", ""),
                objects=item.get("object_count", ""),
                sources=item.get("source_count", ""),
                todo=item.get("todo_markers", ""),
                payload=item.get("payload_output", ""),
            )
        )
    issue_lines = [
        f"- queue {issue.get('severity')} {issue.get('code')}: {issue.get('message')} {issue.get('person', '')}".rstrip()
        for issue in report.get("queue_issues") or []
    ]
    for item in report.get("items") or []:
        for issue in item.get("issues") or []:
            issue_lines.append(f"- {item.get('person')} {issue.get('severity')} {issue.get('code')}: {issue.get('message')}")
    if issue_lines:
        lines.extend(["", "## Issues", "", *issue_lines])
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consume source-pack handoff ready queue into excerpt reports and I5B object payload skeletons.")
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE)
    parser.add_argument("--handoff-root", type=Path, default=None)
    parser.add_argument("--source-pack-root", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--person", action="append", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--include-adjacent", action="store_true")
    parser.add_argument("--context-chars", type=int, default=420)
    parser.add_argument("--max-passages-per-page", type=int, default=4)
    parser.add_argument("--no-audit-packs", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-issue", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workflow_code = normalize_workflow_code(args.workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    handoff_root = args.handoff_root or source_paths.get("handoff_root") or ROOT / ".tmp" / "handoffs"
    source_pack_root = args.source_pack_root or source_paths.get("source_pack_root")
    profile_path = args.profile or source_paths.get("query_profile") or DEFAULT_PROFILE
    report_path = args.report or args.output_root / workflow_slug(workflow_code) / "next_stage_queue_report.json"
    people = {person.strip() for person in args.person if person.strip()} or None
    report = run_queue(
        workflow_code=workflow_code,
        handoff_root=handoff_root,
        source_pack_root=source_pack_root,
        profile_path=profile_path,
        output_root=args.output_root,
        people=people,
        limit=args.limit,
        include_adjacent=args.include_adjacent,
        context_chars=args.context_chars,
        max_passages_per_page=args.max_passages_per_page,
        audit_packs=not args.no_audit_packs,
        dry_run=args.dry_run,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    print(json.dumps({"report": str(report_path), "ok": report["ok"], "queue_count": report["queue_count"]}, ensure_ascii=False, sort_keys=True))
    return 1 if args.fail_on_issue and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
