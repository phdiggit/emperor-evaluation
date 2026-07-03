from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import i5b_source_pack_handoff as handoff_tool  # noqa: E402
from scripts.dev import i5b_source_pack_status as status_tool  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_PROFILE,
    DEFAULT_WORKFLOW_CODE,
    load_source_excerpt_pool_paths,
    normalize_workflow_code,
)


SCHEMA_VERSION = 1
FOLLOWUP_STATUSES = {"needs_more_profile_work"}
BLOCKED_STATUSES = {"blocked"}


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line:
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _unique_people(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    people: list[str] = []
    seen: set[str] = set()
    for row in rows:
        person = str(row.get("person") or "").strip()
        if person and person not in seen:
            people.append(person)
            seen.add(person)
    return people


def _chunks(items: Sequence[Mapping[str, Any]], desired_count: int) -> list[list[Mapping[str, Any]]]:
    if desired_count <= 0 or not items:
        return []
    count = min(desired_count, len(items))
    size = math.ceil(len(items) / count)
    return [list(items[index : index + size]) for index in range(0, len(items), size)]


def _person_chunks(people: Sequence[str], desired_count: int) -> list[list[str]]:
    rows = [{"person": person} for person in people]
    return [[str(row["person"]) for row in chunk] for chunk in _chunks(rows, desired_count)]


def _followup_chunks_by_batch(rows: Sequence[Mapping[str, Any]], desired_count: int) -> list[list[Mapping[str, Any]]]:
    if desired_count <= 0 or not rows:
        return []
    groups_by_batch: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        batch_id = str(row.get("batch_id") or "")
        groups_by_batch.setdefault(batch_id, []).append(row)
    groups = list(groups_by_batch.values())
    if len(groups) <= desired_count:
        return groups
    buckets: list[list[Mapping[str, Any]]] = [[] for _ in range(desired_count)]
    for group in groups:
        target = min(range(desired_count), key=lambda index: len(buckets[index]))
        buckets[target].extend(group)
    return [bucket for bucket in buckets if bucket]


def collect_handoff_queues(handoff_root: Path, handoff_report: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    batch_ok = {str(batch.get("batch_id") or ""): bool(batch.get("ok")) for batch in handoff_report.get("batches") or []}
    ready_people = set(str(person) for person in handoff_report.get("ready_people") or [])
    ready_queue: list[dict[str, Any]] = []
    followup_queue: list[dict[str, Any]] = []
    blocked_queue: list[dict[str, Any]] = []

    for handoff_dir in handoff_tool.discover_handoff_dirs(handoff_root):
        manifest = _read_json(handoff_dir / "manifest.json") if (handoff_dir / "manifest.json").exists() else {}
        batch_id = str(manifest.get("batch_id") or handoff_dir.name)
        accepted_rows = _read_jsonl(handoff_dir / "accepted_packs.jsonl")
        queue_rows = _read_jsonl(handoff_dir / "next_stage_queue.jsonl")
        queue_by_person = {str(row.get("person") or "").strip(): row for row in queue_rows}
        for row in accepted_rows:
            person = str(row.get("person") or "").strip()
            status = str(row.get("acceptance_status") or "").strip()
            base = {
                "person": person,
                "batch_id": batch_id,
                "batch_ok": batch_ok.get(batch_id, False),
                "acceptance_status": status,
                "accepted_pack_path": str(row.get("accepted_pack_path") or "").strip(),
                "gap_summary": str(row.get("gap_summary") or "").strip(),
                "review_note": str(row.get("review_note") or "").strip(),
            }
            if person in ready_people:
                queue_row = queue_by_person.get(person, {})
                ready_queue.append(
                    {
                        **base,
                        "stage": str(queue_row.get("stage") or "").strip(),
                        "ready": queue_row.get("ready") is True,
                    }
                )
            elif status in FOLLOWUP_STATUSES:
                followup_queue.append(base)
            elif status in BLOCKED_STATUSES:
                blocked_queue.append(base)

    return {
        "ready_queue": ready_queue,
        "source_pack_followup_queue": followup_queue,
        "blocked_queue": blocked_queue,
    }


def build_status_snapshot(
    *,
    workflow_code: str,
    all_list: Path,
    profile_path: Path,
    source_pack_root: Path,
    jobs_dir: Path,
    logs_dir: Path,
) -> dict[str, Any]:
    return status_tool.build_status_report(
        persons=status_tool.load_persons(all_list) if all_list.exists() else [],
        profiles=status_tool.load_profiles(profile_path, workflow_code=workflow_code) if profile_path.exists() else {},
        jobs=status_tool.load_jobs(jobs_dir, logs_dir),
        packs=status_tool.load_packs(source_pack_root),
        workflow_code=workflow_code,
    )


def build_agent_plan(
    *,
    ready_queue: Sequence[Mapping[str, Any]],
    followup_queue: Sequence[Mapping[str, Any]],
    blocked_queue: Sequence[Mapping[str, Any]],
    handoff_ok: bool,
    source_pack_agents: int,
    next_stage_agents: int,
) -> dict[str, Any]:
    source_pack_assignments = []
    for index, chunk in enumerate(_followup_chunks_by_batch(followup_queue, source_pack_agents), start=1):
        people = _unique_people(chunk)
        source_pack_assignments.append(
            {
                "agent_id": f"source-pack-followup-{index:02d}",
                "mission": "continue profile/source-pack refinement until each assigned person reaches ready or blocked",
                "people": people,
                "handoff_batches": sorted({str(row.get("batch_id") or "") for row in chunk if row.get("batch_id")}),
                "acceptance_target": "write/update accepted_packs, unresolved_gaps, profile_patches, next_stage_queue, then pass handoff validation",
            }
        )

    releasable_ready = list(ready_queue) if handoff_ok else []
    next_stage_assignments = []
    for index, people in enumerate(_person_chunks(_unique_people(releasable_ready), next_stage_agents), start=1):
        next_stage_assignments.append(
            {
                "agent_id": f"next-stage-{index:02d}",
                "mission": "consume ready source packs into source excerpt pool/object payload preparation",
                "people": people,
                "acceptance_target": "produce next-stage handoff artifacts without changing scores or final adjudication",
            }
        )

    return {
        "recommended_concurrency": len(source_pack_assignments) + len(next_stage_assignments),
        "handoff_ready_release": bool(handoff_ok and releasable_ready),
        "controller_review_required": bool(blocked_queue or not handoff_ok),
        "source_pack_followup_agents": source_pack_assignments,
        "next_stage_agents": next_stage_assignments,
        "blocked_people": _unique_people(blocked_queue),
        "controller_gates": [
            "handoff validation has zero blocks before releasing ready_queue",
            "source-pack agents own refinement and handoff updates for their assigned people",
            "next-stage agents may prepare excerpt/object payloads but must not decide final scores",
            "main controller only reviews blocked people, warnings, and next-stage acceptance summaries",
        ],
    }


def build_control_board(
    *,
    handoff_root: Path,
    source_pack_root: Path | None = None,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
    audit_packs: bool = True,
    include_status: bool = True,
    all_list: Path | None = None,
    profile_path: Path | None = None,
    jobs_dir: Path | None = None,
    logs_dir: Path | None = None,
    source_pack_agents: int = 4,
    next_stage_agents: int = 1,
) -> dict[str, Any]:
    workflow_code = normalize_workflow_code(workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    resolved_source_pack_root = source_pack_root or source_paths.get("source_pack_root")
    handoff_report = handoff_tool.build_report(
        handoff_root,
        source_pack_root=resolved_source_pack_root,
        audit_packs=audit_packs,
        workflow_code=workflow_code,
    )
    queues = collect_handoff_queues(handoff_root, handoff_report)
    status_snapshot: dict[str, Any] | None = None
    if include_status:
        resolved_profile = profile_path or source_paths.get("query_profile") or DEFAULT_PROFILE
        resolved_pack_root = resolved_source_pack_root or ROOT / ".tmp" / "source-packs"
        resolved_jobs_dir = jobs_dir or source_paths.get("jobs_dir") or resolved_pack_root.parent / "jobs"
        resolved_logs_dir = logs_dir or source_paths.get("logs_dir") or resolved_pack_root.parent / "logs"
        status_snapshot = build_status_snapshot(
            workflow_code=workflow_code,
            all_list=all_list or status_tool.DEFAULT_ALL_LIST,
            profile_path=resolved_profile,
            source_pack_root=resolved_pack_root,
            jobs_dir=resolved_jobs_dir,
            logs_dir=resolved_logs_dir,
        )

    agent_plan = build_agent_plan(
        ready_queue=queues["ready_queue"],
        followup_queue=queues["source_pack_followup_queue"],
        blocked_queue=queues["blocked_queue"],
        handoff_ok=bool(handoff_report.get("ok")),
        source_pack_agents=source_pack_agents,
        next_stage_agents=next_stage_agents,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "workflow_code": workflow_code,
        "handoff_root": str(handoff_root),
        "source_pack_root": str(resolved_source_pack_root or ""),
        "handoff_summary": {
            "ok": bool(handoff_report.get("ok")),
            "batches": int(handoff_report.get("batch_count") or 0),
            "ready_people": int(handoff_report.get("ready_people_count") or 0),
            "blocks": int(handoff_report.get("block_count") or 0),
            "warnings": int(handoff_report.get("warning_count") or 0),
        },
        "ready_queue": queues["ready_queue"],
        "source_pack_followup_queue": queues["source_pack_followup_queue"],
        "blocked_queue": queues["blocked_queue"],
        "agent_plan": agent_plan,
        "status_totals": status_snapshot.get("totals") if isinstance(status_snapshot, Mapping) else None,
    }


def render_markdown(board: Mapping[str, Any]) -> str:
    summary = board.get("handoff_summary") if isinstance(board.get("handoff_summary"), Mapping) else {}
    plan = board.get("agent_plan") if isinstance(board.get("agent_plan"), Mapping) else {}
    lines = [
        f"# {board.get('workflow_code') or DEFAULT_WORKFLOW_CODE} source pack control board",
        "",
        f"- generated_at: `{board.get('generated_at') or ''}`",
        f"- handoff_root: `{board.get('handoff_root') or ''}`",
        f"- source_pack_root: `{board.get('source_pack_root') or ''}`",
        f"- handoff_ok: `{str(summary.get('ok')).lower()}`",
        f"- batches: `{summary.get('batches', 0)}`",
        f"- ready_people: `{summary.get('ready_people', 0)}`",
        f"- blocks: `{summary.get('blocks', 0)}`",
        f"- warnings: `{summary.get('warnings', 0)}`",
        f"- recommended_concurrency: `{plan.get('recommended_concurrency', 0)}`",
        f"- handoff_ready_release: `{str(plan.get('handoff_ready_release')).lower()}`",
        "",
        "## Ready Queue",
        "",
        "| person | batch | stage | pack |",
        "| --- | --- | --- | --- |",
    ]
    for row in board.get("ready_queue") or []:
        lines.append(
            f"| {row.get('person', '')} | {row.get('batch_id', '')} | {row.get('stage', '')} | {row.get('accepted_pack_path', '')} |"
        )
    lines.extend(["", "## Source Pack Follow-Up Agents", ""])
    for assignment in plan.get("source_pack_followup_agents") or []:
        lines.append(f"- `{assignment.get('agent_id')}`: {'、'.join(assignment.get('people') or [])}")
    lines.extend(["", "## Next Stage Agents", ""])
    for assignment in plan.get("next_stage_agents") or []:
        lines.append(f"- `{assignment.get('agent_id')}`: {'、'.join(assignment.get('people') or [])}")
    blocked_people = plan.get("blocked_people") or []
    if blocked_people:
        lines.extend(["", "## Controller Review", "", "- blocked_people: " + "、".join(blocked_people)])
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a controller-light source-pack handoff board and sub-agent work plan.")
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE)
    parser.add_argument("--handoff-root", type=Path, default=None)
    parser.add_argument("--source-pack-root", type=Path, default=None)
    parser.add_argument("--all-list", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--jobs-dir", type=Path, default=None)
    parser.add_argument("--logs-dir", type=Path, default=None)
    parser.add_argument("--source-pack-agents", type=int, default=4)
    parser.add_argument("--next-stage-agents", type=int, default=1)
    parser.add_argument("--no-audit-packs", action="store_true")
    parser.add_argument("--no-status", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-block", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workflow_code = normalize_workflow_code(args.workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    handoff_root = args.handoff_root or source_paths.get("handoff_root") or ROOT / ".tmp" / "handoffs"
    board = build_control_board(
        handoff_root=handoff_root,
        source_pack_root=args.source_pack_root,
        workflow_code=workflow_code,
        audit_packs=not args.no_audit_packs,
        include_status=not args.no_status,
        all_list=args.all_list,
        profile_path=args.profile,
        jobs_dir=args.jobs_dir,
        logs_dir=args.logs_dir,
        source_pack_agents=args.source_pack_agents,
        next_stage_agents=args.next_stage_agents,
    )
    text = json.dumps(board, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(board)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    blocked = int(board.get("handoff_summary", {}).get("blocks") or 0)
    return 1 if args.fail_on_block and blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
