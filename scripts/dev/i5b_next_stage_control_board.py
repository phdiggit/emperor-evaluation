from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import i5b_next_stage_queue_runner as queue_runner  # noqa: E402
from scripts.dev import i5b_object_payload_audit as payload_audit  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_PROFILE,
    DEFAULT_WORKFLOW_CODE,
    load_source_excerpt_pool_paths,
    normalize_workflow_code,
    workflow_slug,
)


SCHEMA_VERSION = 1
DEFAULT_NEXT_STAGE_ROOT = ROOT / ".tmp" / "i5b-next-stage"
DEFAULT_CANDIDATE_ROOT = ROOT / ".tmp" / "i5b-object-payload-work"


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def default_assignment_run_id() -> str:
    return datetime.now().astimezone().strftime("run-%Y%m%d-%H%M%S")


def person_slug(person: str) -> str:
    digest = hashlib.sha1(person.encode("utf-8")).hexdigest()[:10]
    return f"person-{digest}"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload_rows(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict) and isinstance(raw.get("payloads"), list):
        return [row for row in raw["payloads"] if isinstance(row, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def _payload_people(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    try:
        rows = _payload_rows(_read_json(path))
    except Exception as exc:
        return [], [{"severity": "block", "code": "candidate_json_error", "message": repr(exc), "path": str(path)}]
    people: list[str] = []
    for index, row in enumerate(rows):
        emperor = row.get("emperor") if isinstance(row.get("emperor"), Mapping) else {}
        person = str(emperor.get("name") or row.get("person") or "").strip()
        if person:
            people.append(person)
        else:
            issues.append(
                {
                    "severity": "block",
                    "code": "candidate_missing_person",
                    "message": "candidate payload must identify emperor.name",
                    "payload_index": index,
                    "path": str(path),
                }
            )
    return people, issues


def _todo_totals(audit: Mapping[str, Any]) -> dict[str, int]:
    totals = {marker: 0 for marker in payload_audit.TODO_MARKERS}
    for payload in audit.get("payloads") or []:
        for marker, count in (payload.get("todo_counts") or {}).items():
            totals[marker] = totals.get(marker, 0) + int(count)
    return totals


def discover_candidate_paths(candidate_root: Path, explicit_candidates: Sequence[Path] | None = None) -> list[Path]:
    paths = [path for path in (explicit_candidates or []) if path.exists()]
    if candidate_root.exists():
        paths.extend(candidate_root.rglob("object_payload_candidate.json"))
    unique: list[Path] = []
    seen: set[str] = set()
    for path in sorted(paths, key=lambda item: str(item)):
        key = str(path.resolve())
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def _candidate_record(path: Path) -> dict[str, Any]:
    review_report = path.parent / "review_report.md"
    audit = payload_audit.audit_payload_file(path)
    people, person_issues = _payload_people(path)
    issues = list(audit.get("issues") or []) + person_issues
    if not review_report.exists():
        issues.append(
            {
                "severity": "block",
                "code": "missing_review_report",
                "message": "candidate handoff must include sibling review_report.md",
                "path": str(review_report),
            }
        )
    block_count = int(audit.get("block_count") or 0) + sum(1 for issue in person_issues if issue.get("severity") == "block")
    if not review_report.exists():
        block_count += 1
    warning_count = int(audit.get("warning_count") or 0) + sum(1 for issue in issues if issue.get("severity") == "warning")
    return {
        "path": str(path),
        "review_report": str(review_report),
        "review_report_exists": review_report.exists(),
        "people": people,
        "audit_ok": bool(audit.get("ok")) and not person_issues and review_report.exists(),
        "block_count": block_count,
        "warning_count": warning_count,
        "payload_count": int(audit.get("payload_count") or 0),
        "todo_counts": _todo_totals(audit),
        "issues": issues,
    }


def collect_candidates(
    candidate_root: Path,
    *,
    explicit_candidates: Sequence[Path] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    by_person: dict[str, list[dict[str, Any]]] = {}
    for path in discover_candidate_paths(candidate_root, explicit_candidates):
        record = _candidate_record(path)
        records.append(record)
        issues.extend(record["issues"])
        for person in record["people"]:
            by_person.setdefault(person, []).append(record)
    return by_person, records, issues


def _load_next_stage_report(path: Path) -> dict[str, Any]:
    report = _read_json(path)
    if not isinstance(report, dict) or not isinstance(report.get("items"), list):
        raise ValueError(f"invalid next-stage report: {path}")
    return report


def load_or_run_next_stage(
    *,
    workflow_code: str,
    next_stage_report: Path | None,
    handoff_root: Path,
    source_pack_root: Path | None,
    profile_path: Path,
    output_root: Path,
    people: set[str] | None,
    limit: int | None,
    include_adjacent: bool,
    context_chars: int,
    max_passages_per_page: int,
    audit_packs: bool,
    dry_run: bool,
) -> dict[str, Any]:
    if next_stage_report is not None:
        return _load_next_stage_report(next_stage_report)
    return queue_runner.run_queue(
        workflow_code=workflow_code,
        handoff_root=handoff_root,
        source_pack_root=source_pack_root,
        profile_path=profile_path,
        output_root=output_root,
        people=people,
        limit=limit,
        include_adjacent=include_adjacent,
        context_chars=context_chars,
        max_passages_per_page=max_passages_per_page,
        audit_packs=audit_packs,
        dry_run=dry_run,
    )


def filter_next_stage_report(
    report: Mapping[str, Any],
    *,
    people: set[str] | None,
    exclude_people: set[str] | None,
    limit: int | None,
) -> dict[str, Any]:
    filtered = dict(report)
    items = list(report.get("items") or [])
    if people is not None:
        items = [item for item in items if str(item.get("person") or "").strip() in people]
    if exclude_people:
        items = [item for item in items if str(item.get("person") or "").strip() not in exclude_people]
    if limit is not None:
        items = items[:limit]
    filtered["items"] = items
    filtered["queue_count"] = len(items)
    return filtered


def _chunks(items: Sequence[Mapping[str, Any]], desired_count: int) -> list[list[Mapping[str, Any]]]:
    if desired_count <= 0 or not items:
        return []
    count = min(desired_count, len(items))
    size = math.ceil(len(items) / count)
    return [list(items[index : index + size]) for index in range(0, len(items), size)]


def _audit_command(inputs: Sequence[str], output: Path) -> str:
    input_args = " ".join(f'--input "{path}"' for path in inputs)
    return f'python scripts/dev/i5b_object_payload_audit.py {input_args} --format markdown --output "{output}" --fail-on-block'


def _assignment_prompt(agent_id: str, people: Sequence[Mapping[str, Any]], target_dir: Path, audit_command: str) -> str:
    names = "、".join(str(row.get("person") or "") for row in people)
    lines = [
        f"You are {agent_id}. Prepare I5B object payload candidates for: {names}.",
        f"Write only under: {target_dir}",
        "For each person, read object_payload_skeleton.json and source_excerpt_pool.json, then produce:",
        "- object_payload_candidate.json",
        "- review_report.md",
        "Before filling attrs, inspect object_payload_skeleton.existing_db_facts and per-object existing_db_facts; preserve table facts and do not downgrade them.",
        "Do not write the database, formal data, scores, ranks, or final adjudication.",
        "Remove unsupported TODO candidates or mark them in review_report instead of leaving TODO markers in JSON.",
        "Acceptance command:",
        audit_command,
        "Assigned inputs:",
    ]
    for row in people:
        lines.append(
            "- {person}: skeleton={skeleton}; excerpts={excerpts}; candidate={candidate}; review={review}".format(
                person=row.get("person") or "",
                skeleton=row.get("payload_skeleton") or "",
                excerpts=row.get("source_excerpt_pool") or "",
                candidate=row.get("target_candidate") or "",
                review=row.get("target_review_report") or "",
            )
        )
    return "\n".join(lines)


def build_agent_plan(
    missing_people: Sequence[Mapping[str, Any]],
    *,
    candidate_root: Path,
    worker_count: int,
    assignment_run_id: str,
) -> dict[str, Any]:
    assignments: list[dict[str, Any]] = []
    for index, chunk in enumerate(_chunks(missing_people, worker_count), start=1):
        agent_id = f"object-payload-{index:02d}"
        target_dir = candidate_root / "assignments" / assignment_run_id / agent_id
        people: list[dict[str, Any]] = []
        candidate_paths: list[str] = []
        for row in chunk:
            person = str(row.get("person") or "")
            person_dir = target_dir / person_slug(person)
            candidate = person_dir / "object_payload_candidate.json"
            review = person_dir / "review_report.md"
            candidate_paths.append(str(candidate))
            people.append(
                {
                    "person": person,
                    "batch_id": row.get("batch_id") or "",
                    "payload_skeleton": row.get("payload_output") or "",
                    "source_excerpt_pool": row.get("excerpt_output") or "",
                    "accepted_pack_path": row.get("accepted_pack_path") or "",
                    "target_candidate": str(candidate),
                    "target_review_report": str(review),
                }
            )
        audit_output = target_dir / "audit.md"
        audit_command = _audit_command(candidate_paths, audit_output)
        assignments.append(
            {
                "agent_id": agent_id,
                "people": people,
                "target_dir": str(target_dir),
                "candidate_paths": candidate_paths,
                "audit_output": str(audit_output),
                "audit_command": audit_command,
                "acceptance_target": "deliver candidate payloads, sibling review reports, and a passing object payload audit",
                "prompt": _assignment_prompt(agent_id, people, target_dir, audit_command),
            }
        )
    return {
        "recommended_concurrency": len(assignments),
        "assignments": assignments,
        "controller_gates": [
            "run this board after next-stage queue materialization",
            "spawn one object-payload worker per assignment when missing_people is non-empty",
            "do not inspect every candidate manually; review only blocked_payload_audit and duplicate_candidate rows",
            "payloads with status ready_for_import_dry_run may proceed to importer dry-run, not database writes",
        ],
    }


def _person_item(
    item: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    status = str(item.get("status") or "")
    base = {
        "person": str(item.get("person") or ""),
        "batch_id": item.get("batch_id") or "",
        "next_stage_status": status,
        "payload_output": item.get("payload_output") or "",
        "excerpt_output": item.get("excerpt_output") or "",
        "accepted_pack_path": item.get("accepted_pack_path") or "",
        "candidate_count": len(candidates),
        "candidates": list(candidates),
        "status": "",
        "issues": [],
    }
    if status not in {"ok", "planned"}:
        base["status"] = "blocked_next_stage"
        base["issues"] = list(item.get("issues") or [])
        return base
    if not candidates:
        base["status"] = "needs_object_payload_worker"
        return base
    if len(candidates) > 1:
        base["status"] = "blocked_duplicate_candidate"
        base["issues"] = [
            {
                "severity": "block",
                "code": "duplicate_candidate_payload",
                "message": "multiple object_payload_candidate.json files identify the same person",
                "paths": [candidate.get("path") for candidate in candidates],
            }
        ]
        return base
    candidate = candidates[0]
    base["status"] = "ready_for_import_dry_run" if candidate.get("audit_ok") else "blocked_payload_audit"
    base["issues"] = list(candidate.get("issues") or [])
    return base


def build_control_board(
    *,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
    next_stage_report: Path | None = None,
    handoff_root: Path,
    source_pack_root: Path | None,
    profile_path: Path,
    next_stage_output_root: Path,
    candidate_root: Path = DEFAULT_CANDIDATE_ROOT,
    explicit_candidates: Sequence[Path] | None = None,
    people: set[str] | None = None,
    exclude_people: set[str] | None = None,
    limit: int | None = None,
    include_adjacent: bool = False,
    context_chars: int = 420,
    max_passages_per_page: int = 4,
    audit_packs: bool = True,
    dry_run_next_stage: bool = False,
    worker_count: int = 4,
    assignment_run_id: str | None = None,
) -> dict[str, Any]:
    workflow_code = normalize_workflow_code(workflow_code)
    next_stage = load_or_run_next_stage(
        workflow_code=workflow_code,
        next_stage_report=next_stage_report,
        handoff_root=handoff_root,
        source_pack_root=source_pack_root,
        profile_path=profile_path,
        output_root=next_stage_output_root,
        people=people,
        limit=limit,
        include_adjacent=include_adjacent,
        context_chars=context_chars,
        max_passages_per_page=max_passages_per_page,
        audit_packs=audit_packs,
        dry_run=dry_run_next_stage,
    )
    next_stage = filter_next_stage_report(next_stage, people=people, exclude_people=exclude_people, limit=limit)
    by_person, candidate_records, candidate_issues = collect_candidates(candidate_root, explicit_candidates=explicit_candidates)
    rows: list[dict[str, Any]] = []
    seen_people: set[str] = set()
    for item in next_stage.get("items") or []:
        person = str(item.get("person") or "").strip()
        if not person:
            continue
        seen_people.add(person)
        rows.append(_person_item(item, by_person.get(person, [])))
    untracked_candidates = sorted(person for person in by_person if person not in seen_people)
    if untracked_candidates:
        candidate_issues.append(
            {
                "severity": "warning",
                "code": "candidate_not_in_ready_queue",
                "message": "candidate exists for a person not present in the next-stage report",
                "people": untracked_candidates,
            }
        )
    status_counts = Counter(str(row.get("status") or "") for row in rows)
    missing = [row for row in rows if row.get("status") == "needs_object_payload_worker"]
    ready = [row for row in rows if row.get("status") == "ready_for_import_dry_run"]
    blocked = [row for row in rows if str(row.get("status") or "").startswith("blocked_")]
    issue_count = sum(len(row.get("issues") or []) for row in rows) + len(candidate_issues)
    block_count = sum(1 for row in rows if str(row.get("status") or "").startswith("blocked_"))
    block_count += sum(1 for issue in candidate_issues if issue.get("severity") == "block")
    warning_count = sum(1 for issue in candidate_issues if issue.get("severity") == "warning")
    next_stage_ok = bool(next_stage.get("ok"))
    if not next_stage_ok:
        block_count += 1
    run_id = assignment_run_id or default_assignment_run_id()
    agent_plan = build_agent_plan(
        missing,
        candidate_root=candidate_root,
        worker_count=worker_count,
        assignment_run_id=run_id,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "workflow_code": workflow_code,
        "assignment_run_id": run_id,
        "paths": {
            "handoff_root": str(handoff_root),
            "source_pack_root": str(source_pack_root) if source_pack_root is not None else "",
            "profile": str(profile_path),
            "next_stage_output_root": str(next_stage_output_root),
            "candidate_root": str(candidate_root),
            "next_stage_report": str(next_stage_report) if next_stage_report is not None else "",
        },
        "summary": {
            "ok": block_count == 0,
            "complete": next_stage_ok and not missing and block_count == 0,
            "next_stage_ok": next_stage_ok,
            "queue_count": len(rows),
            "candidate_files": len(candidate_records),
            "ready_for_import_dry_run": len(ready),
            "needs_object_payload_worker": len(missing),
            "blocked": len(blocked),
            "warnings": warning_count,
            "issue_count": issue_count,
            "status_counts": dict(sorted(status_counts.items())),
            "controller_review_required": block_count > 0,
        },
        "people": rows,
        "ready_for_import_payloads": [
            candidate["path"]
            for row in ready
            for candidate in row.get("candidates") or []
            if candidate.get("audit_ok")
        ],
        "missing_people": missing,
        "blocked_people": blocked,
        "candidate_issues": candidate_issues,
        "untracked_candidate_people": untracked_candidates,
        "agent_plan": agent_plan,
    }


def render_markdown(board: Mapping[str, Any]) -> str:
    summary = board.get("summary") if isinstance(board.get("summary"), Mapping) else {}
    plan = board.get("agent_plan") if isinstance(board.get("agent_plan"), Mapping) else {}
    lines = [
        f"# {board.get('workflow_code') or DEFAULT_WORKFLOW_CODE} next-stage control board",
        "",
        f"- generated_at: `{board.get('generated_at') or ''}`",
        f"- ok: `{str(summary.get('ok')).lower()}`",
        f"- complete: `{str(summary.get('complete')).lower()}`",
        f"- queue_count: `{summary.get('queue_count', 0)}`",
        f"- ready_for_import_dry_run: `{summary.get('ready_for_import_dry_run', 0)}`",
        f"- needs_object_payload_worker: `{summary.get('needs_object_payload_worker', 0)}`",
        f"- blocked: `{summary.get('blocked', 0)}`",
        f"- recommended_concurrency: `{plan.get('recommended_concurrency', 0)}`",
        "",
        "## People",
        "",
        "| person | status | candidate_count | payload | candidate |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in board.get("people") or []:
        candidate_paths = [str(candidate.get("path") or "") for candidate in row.get("candidates") or []]
        lines.append(
            "| {person} | {status} | {count} | `{payload}` | `{candidate}` |".format(
                person=row.get("person", ""),
                status=row.get("status", ""),
                count=row.get("candidate_count", 0),
                payload=row.get("payload_output", ""),
                candidate="; ".join(candidate_paths),
            )
        )
    ready_payloads = board.get("ready_for_import_payloads") or []
    if ready_payloads:
        lines.extend(["", "## Ready For Import Dry-Run", ""])
        for path in ready_payloads:
            lines.append(f"- `{path}`")
    assignments = plan.get("assignments") or []
    if assignments:
        lines.extend(["", "## Object Payload Worker Assignments", ""])
        for assignment in assignments:
            people = "、".join(str(row.get("person") or "") for row in assignment.get("people") or [])
            lines.append(f"- `{assignment.get('agent_id')}`: {people}")
            lines.append(f"  - target_dir: `{assignment.get('target_dir')}`")
            lines.append(f"  - audit_command: `{assignment.get('audit_command')}`")
    issue_lines: list[str] = []
    for row in board.get("people") or []:
        for issue in row.get("issues") or []:
            issue_lines.append(f"- `{row.get('person')}` {issue.get('severity')} {issue.get('code')}: {issue.get('message')}")
    for issue in board.get("candidate_issues") or []:
        issue_lines.append(f"- candidate {issue.get('severity')} {issue.get('code')}: {issue.get('message')}")
    if issue_lines:
        lines.extend(["", "## Issues", "", *issue_lines])
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a controller-light I5B next-stage handoff board for object payload workers.")
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE)
    parser.add_argument("--next-stage-report", type=Path, default=None)
    parser.add_argument("--handoff-root", type=Path, default=None)
    parser.add_argument("--source-pack-root", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--next-stage-output-root", type=Path, default=DEFAULT_NEXT_STAGE_ROOT)
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--candidate", type=Path, action="append", default=[])
    parser.add_argument("--person", action="append", default=[])
    parser.add_argument("--exclude-person", action="append", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--include-adjacent", action="store_true")
    parser.add_argument("--context-chars", type=int, default=420)
    parser.add_argument("--max-passages-per-page", type=int, default=4)
    parser.add_argument("--no-audit-packs", action="store_true")
    parser.add_argument("--dry-run-next-stage", action="store_true")
    parser.add_argument("--worker-count", type=int, default=4)
    parser.add_argument("--assignment-run-id", default=None)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fail-on-block", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workflow_code = normalize_workflow_code(args.workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    handoff_root = args.handoff_root or source_paths.get("handoff_root") or ROOT / ".tmp" / "handoffs"
    source_pack_root = args.source_pack_root or source_paths.get("source_pack_root")
    profile_path = args.profile or source_paths.get("query_profile") or DEFAULT_PROFILE
    people = {person.strip() for person in args.person if person.strip()} or None
    exclude_people = {person.strip() for person in args.exclude_person if person.strip()} or None
    board = build_control_board(
        workflow_code=workflow_code,
        next_stage_report=args.next_stage_report,
        handoff_root=handoff_root,
        source_pack_root=source_pack_root,
        profile_path=profile_path,
        next_stage_output_root=args.next_stage_output_root,
        candidate_root=args.candidate_root,
        explicit_candidates=args.candidate,
        people=people,
        exclude_people=exclude_people,
        limit=args.limit,
        include_adjacent=args.include_adjacent,
        context_chars=args.context_chars,
        max_passages_per_page=args.max_passages_per_page,
        audit_packs=not args.no_audit_packs,
        dry_run_next_stage=args.dry_run_next_stage,
        worker_count=args.worker_count,
        assignment_run_id=args.assignment_run_id,
    )
    text = json.dumps(board, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(board)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 1 if args.fail_on_block and not board["summary"]["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
