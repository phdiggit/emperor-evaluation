from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.source_excerpt_pool_lib.source_pack import audit_source_pack  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_WORKFLOW_CODE,
    load_source_excerpt_pool_paths,
    normalize_workflow_code,
    workflow_slug,
)


SCHEMA_VERSION = 1
REQUIRED_FILES = (
    "manifest.json",
    "accepted_packs.jsonl",
    "unresolved_gaps.jsonl",
    "profile_patches.jsonl",
    "next_stage_queue.jsonl",
    "acceptance.md",
)
ACCEPTANCE_STATUSES = {"accepted", "accepted_with_known_gaps", "needs_more_profile_work", "blocked"}
READY_STATUSES = {"accepted", "accepted_with_known_gaps"}
PATCH_STATUSES = {"applied", "proposed", "not_needed", "rejected"}
GAP_DECISIONS = {"known_non_blocking", "out_of_source_scope", "defer", "needs_profile_patch", "needs_manual_source", "blocked"}
LEGACY_GAP_DECISION_ALIASES = {"not_i5b_main": "out_of_source_scope"}
BLOCKING_GAP_DECISIONS = {"needs_profile_patch", "needs_manual_source", "blocked"}
NEXT_STAGE_VALUES = {"source_pack_audit", "source_excerpt_pool", "object_payload"}


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    _atomic_write_text(path, "\n".join(lines).rstrip() + ("\n" if lines else ""))


def read_json(path: Path, issues: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    if not path.exists():
        issues.append({"severity": "block", "code": "missing_file", "path": str(path), "message": f"{label} is missing"})
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append({"severity": "block", "code": "invalid_json", "path": str(path), "message": str(exc)})
        return {}
    if not isinstance(payload, dict):
        issues.append({"severity": "block", "code": "invalid_json_type", "path": str(path), "message": f"{label} must be a JSON object"})
        return {}
    return payload


def read_jsonl(path: Path, issues: list[dict[str, Any]], *, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            issues.append({"severity": "block", "code": "missing_file", "path": str(path), "message": f"{path.name} is missing"})
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception as exc:
            issues.append({"severity": "block", "code": "invalid_jsonl", "path": str(path), "line": line_number, "message": str(exc)})
            continue
        if not isinstance(row, dict):
            issues.append({"severity": "block", "code": "invalid_jsonl_type", "path": str(path), "line": line_number, "message": "line must be a JSON object"})
            continue
        rows.append(row)
    return rows


def _contract_name(workflow_code: str) -> str:
    return f"{workflow_slug(workflow_code)}_source_pack_handoff_v1"


def _row_workflow_code(row: Mapping[str, Any]) -> str:
    value = str(row.get("workflow_code") or "").strip()
    return normalize_workflow_code(value) if value else ""


def _same_resolved_path(left: Path | None, right: Path | None) -> bool:
    if left is None or right is None:
        return left is right
    return left.resolve(strict=False) == right.resolve(strict=False)


def init_handoff(
    *,
    handoff_root: Path,
    batch_id: str,
    persons: Sequence[str],
    owner: str = "",
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> Path:
    workflow_code = normalize_workflow_code(workflow_code)
    cleaned_persons = [person.strip() for person in persons if person.strip()]
    if not batch_id.strip():
        raise SystemExit("--batch-id is required")
    if not cleaned_persons:
        raise SystemExit("--person is required at least once")
    handoff_dir = handoff_root / batch_id.strip()
    handoff_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        handoff_dir / "manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "batch_id": batch_id.strip(),
            "created_at": iso_now(),
            "owner": owner.strip(),
            "persons": cleaned_persons,
            "workflow_code": workflow_code,
            "contract": _contract_name(workflow_code),
        },
    )
    for file_name in ("accepted_packs.jsonl", "unresolved_gaps.jsonl", "profile_patches.jsonl", "next_stage_queue.jsonl"):
        target = handoff_dir / file_name
        if not target.exists():
            write_jsonl(target, [])
    acceptance_md = handoff_dir / "acceptance.md"
    if not acceptance_md.exists():
        _atomic_write_text(
            acceptance_md,
            f"# {workflow_code} source pack batch acceptance\n\n"
            f"- batch_id: `{batch_id.strip()}`\n"
            f"- workflow_code: `{workflow_code}`\n"
            f"- created_at: `{iso_now()}`\n"
            f"- owner: `{owner.strip()}`\n\n"
            "| person | acceptance_status | accepted_pack_path | review_note |\n"
            "| --- | --- | --- | --- |\n"
            + "\n".join(f"| {person} | pending |  |  |" for person in cleaned_persons)
            + "\n",
        )
    return handoff_dir


def _issue(issues: list[dict[str, Any]], severity: str, code: str, message: str, **extra: Any) -> None:
    issues.append({"severity": severity, "code": code, "message": message, **extra})


def resolve_pack_path(value: Any, *, handoff_dir: Path, source_pack_root: Path | None) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    looks_absolute = path.is_absolute() or raw.startswith(("/", "\\"))
    if looks_absolute:
        if path.exists():
            return path
        if source_pack_root is not None:
            candidates = [source_pack_root / path.name]
            parts = path.parts
            for marker in ("source-packs", "source_pack_root"):
                if marker in parts:
                    suffix = Path(*parts[parts.index(marker) + 1 :])
                    if str(suffix) != ".":
                        candidates.append(source_pack_root / suffix)
            for candidate in candidates:
                if candidate.exists():
                    return candidate
        return path
    if source_pack_root is not None and (source_pack_root / path).exists():
        return source_pack_root / path
    if (handoff_dir / path).exists():
        return handoff_dir / path
    return source_pack_root / path if source_pack_root is not None else handoff_dir / path


def validate_handoff_dir(handoff_dir: Path, *, source_pack_root: Path | None = None, audit_packs: bool = True) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for file_name in REQUIRED_FILES:
        if not (handoff_dir / file_name).exists():
            _issue(issues, "block", "missing_required_file", f"{file_name} is required", path=str(handoff_dir / file_name))

    manifest = read_json(handoff_dir / "manifest.json", issues, label="manifest")
    manifest_workflow_code = normalize_workflow_code(str(manifest.get("workflow_code") or DEFAULT_WORKFLOW_CODE))
    persons = [str(value).strip() for value in manifest.get("persons", []) if str(value).strip()] if isinstance(manifest.get("persons"), list) else []
    person_set = set(persons)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        _issue(issues, "block", "invalid_schema_version", "manifest.schema_version must be 1", path=str(handoff_dir / "manifest.json"))
    if not manifest.get("batch_id"):
        _issue(issues, "block", "missing_batch_id", "manifest.batch_id is required", path=str(handoff_dir / "manifest.json"))
    if not persons:
        _issue(issues, "block", "missing_persons", "manifest.persons must be a non-empty list", path=str(handoff_dir / "manifest.json"))

    accepted_rows = read_jsonl(handoff_dir / "accepted_packs.jsonl", issues)
    gap_rows = read_jsonl(handoff_dir / "unresolved_gaps.jsonl", issues)
    patch_rows = read_jsonl(handoff_dir / "profile_patches.jsonl", issues)
    queue_rows = read_jsonl(handoff_dir / "next_stage_queue.jsonl", issues)

    accepted_by_person: dict[str, list[dict[str, Any]]] = {}
    for row in accepted_rows:
        person = str(row.get("person") or "").strip()
        status = str(row.get("acceptance_status") or "").strip()
        usable = row.get("usable_for_object_pool")
        row_workflow_code = _row_workflow_code(row)
        if person not in person_set:
            _issue(issues, "block", "unknown_person", "accepted_packs.person must be listed in manifest.persons", person=person)
        if row_workflow_code and row_workflow_code != manifest_workflow_code:
            _issue(
                issues,
                "block",
                "accepted_pack_workflow_mismatch",
                "accepted_packs.workflow_code must match manifest.workflow_code",
                person=person,
                value=row_workflow_code,
                expected=manifest_workflow_code,
            )
        if status not in ACCEPTANCE_STATUSES:
            _issue(issues, "block", "invalid_acceptance_status", "invalid acceptance_status", person=person, value=status)
        if not isinstance(usable, bool):
            _issue(issues, "block", "invalid_usable_for_object_pool", "usable_for_object_pool must be boolean", person=person)
        accepted_by_person.setdefault(person, []).append(row)

    for person in persons:
        rows = accepted_by_person.get(person, [])
        if not rows:
            _issue(issues, "block", "missing_person_acceptance", "each manifest person needs one accepted_packs row", person=person)
        elif len(rows) > 1:
            _issue(issues, "block", "duplicate_person_acceptance", "each person may have only one accepted_packs row", person=person)

    gaps_by_person: dict[str, list[dict[str, Any]]] = {}
    for row in gap_rows:
        person = str(row.get("person") or "").strip()
        decision = str(row.get("decision") or "").strip()
        row_workflow_code = _row_workflow_code(row)
        if person not in person_set:
            _issue(issues, "block", "unknown_person", "unresolved_gaps.person must be listed in manifest.persons", person=person)
        if row_workflow_code and row_workflow_code != manifest_workflow_code:
            _issue(
                issues,
                "block",
                "gap_workflow_mismatch",
                "unresolved_gaps.workflow_code must match manifest.workflow_code",
                person=person,
                value=row_workflow_code,
                expected=manifest_workflow_code,
            )
        if decision in LEGACY_GAP_DECISION_ALIASES:
            _issue(
                issues,
                "warning",
                "legacy_gap_decision",
                "legacy gap decision should be replaced by workflow-neutral decision",
                person=person,
                value=decision,
                replacement=LEGACY_GAP_DECISION_ALIASES[decision],
            )
        elif decision not in GAP_DECISIONS:
            _issue(issues, "block", "invalid_gap_decision", "invalid gap decision", person=person, value=decision)
        gaps_by_person.setdefault(person, []).append(row)

    for row in patch_rows:
        person = str(row.get("person") or "").strip()
        status = str(row.get("patch_status") or "").strip()
        row_workflow_code = _row_workflow_code(row)
        if person not in person_set:
            _issue(issues, "block", "unknown_person", "profile_patches.person must be listed in manifest.persons", person=person)
        if row_workflow_code and row_workflow_code != manifest_workflow_code:
            _issue(
                issues,
                "block",
                "profile_patch_workflow_mismatch",
                "profile_patches.workflow_code must match manifest.workflow_code",
                person=person,
                value=row_workflow_code,
                expected=manifest_workflow_code,
            )
        if status and status not in PATCH_STATUSES:
            _issue(issues, "block", "invalid_patch_status", "invalid patch_status", person=person, value=status)

    queue_by_person: dict[str, list[dict[str, Any]]] = {}
    for row in queue_rows:
        person = str(row.get("person") or "").strip()
        stage = str(row.get("stage") or "").strip()
        ready = row.get("ready")
        row_workflow_code = _row_workflow_code(row)
        if person not in person_set:
            _issue(issues, "block", "unknown_person", "next_stage_queue.person must be listed in manifest.persons", person=person)
        if row_workflow_code and row_workflow_code != manifest_workflow_code:
            _issue(
                issues,
                "block",
                "next_stage_workflow_mismatch",
                "next_stage_queue.workflow_code must match manifest.workflow_code",
                person=person,
                value=row_workflow_code,
                expected=manifest_workflow_code,
            )
        if stage not in NEXT_STAGE_VALUES:
            _issue(issues, "block", "invalid_next_stage", "invalid next stage", person=person, value=stage)
        if ready is not True:
            _issue(issues, "block", "next_stage_not_ready", "next_stage_queue rows must have ready=true", person=person)
        queue_by_person.setdefault(person, []).append(row)

    for person, rows in queue_by_person.items():
        if len(rows) > 1:
            _issue(issues, "block", "duplicate_next_stage_queue", "each ready person may have only one next_stage_queue row", person=person)

    pack_audits: dict[str, dict[str, Any]] = {}
    ready_people: list[str] = []
    for person, rows in accepted_by_person.items():
        if not rows:
            continue
        row = rows[0]
        status = str(row.get("acceptance_status") or "").strip()
        usable = row.get("usable_for_object_pool")
        pack_path = resolve_pack_path(row.get("accepted_pack_path"), handoff_dir=handoff_dir, source_pack_root=source_pack_root)
        blocking_gaps = [gap for gap in gaps_by_person.get(person, []) if str(gap.get("decision") or "") in BLOCKING_GAP_DECISIONS]
        if status in READY_STATUSES:
            if usable is not True:
                _issue(issues, "block", "ready_status_not_usable", "accepted statuses must have usable_for_object_pool=true", person=person)
            if pack_path is None:
                _issue(issues, "block", "missing_accepted_pack_path", "accepted status needs accepted_pack_path", person=person)
            elif not pack_path.exists():
                _issue(issues, "block", "accepted_pack_missing", "accepted source pack path does not exist", person=person, path=str(pack_path))
            elif audit_packs:
                audit = audit_source_pack(pack_path)
                pack_audits[person] = {
                    "ok": audit.get("ok"),
                    "block_count": audit.get("block_count", 0),
                    "warning_count": audit.get("warning_count", 0),
                    "doc_count": audit.get("doc_count", 0),
                    "pack_path": str(pack_path),
                }
                if not audit.get("ok"):
                    _issue(issues, "block", "accepted_pack_audit_failed", "accepted source pack has blocking audit issues", person=person, path=str(pack_path))
            if status == "accepted_with_known_gaps" and not gaps_by_person.get(person):
                _issue(issues, "block", "known_gaps_missing", "accepted_with_known_gaps requires unresolved_gaps rows", person=person)
            if blocking_gaps:
                _issue(issues, "block", "ready_person_has_blocking_gaps", "ready person cannot have blocking gap decisions", person=person)
            if not queue_by_person.get(person):
                _issue(issues, "block", "missing_next_stage_queue", "ready person must be present in next_stage_queue", person=person)
            for queue_row in queue_by_person.get(person, []):
                queue_pack_path = resolve_pack_path(queue_row.get("accepted_pack_path"), handoff_dir=handoff_dir, source_pack_root=source_pack_root)
                if queue_pack_path is None:
                    _issue(issues, "block", "missing_next_stage_pack_path", "next_stage_queue needs accepted_pack_path", person=person)
                elif pack_path is not None and not _same_resolved_path(queue_pack_path, pack_path):
                    _issue(
                        issues,
                        "block",
                        "next_stage_pack_mismatch",
                        "next_stage_queue.accepted_pack_path must match accepted_packs.accepted_pack_path",
                        person=person,
                        path=str(queue_pack_path),
                        expected=str(pack_path),
                    )
            ready_people.append(person)
        else:
            if usable is not False:
                _issue(issues, "block", "not_ready_status_usable", "not-ready statuses must have usable_for_object_pool=false", person=person)
            if queue_by_person.get(person):
                _issue(issues, "block", "not_ready_person_in_next_stage", "not-ready person cannot be in next_stage_queue", person=person)

    for person in queue_by_person:
        accepted = accepted_by_person.get(person, [{}])[0]
        if str(accepted.get("acceptance_status") or "") not in READY_STATUSES:
            _issue(issues, "block", "queue_person_not_accepted", "next_stage_queue person is not accepted", person=person)

    block_count = sum(1 for issue in issues if issue["severity"] == "block")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    acceptance_counts = Counter(str(row.get("acceptance_status") or "") for row in accepted_rows)
    issues_by_person: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        person = str(issue.get("person") or "").strip()
        if person:
            issues_by_person.setdefault(person, []).append(issue)
    person_statuses: list[dict[str, Any]] = []
    for person in persons:
        accepted = accepted_by_person.get(person, [{}])[0]
        status = str(accepted.get("acceptance_status") or "").strip()
        pack_path = resolve_pack_path(accepted.get("accepted_pack_path"), handoff_dir=handoff_dir, source_pack_root=source_pack_root)
        queue_rows = queue_by_person.get(person, [])
        queue_row = queue_rows[0] if queue_rows else {}
        person_issues = issues_by_person.get(person, [])
        person_statuses.append(
            {
                "person": person,
                "workflow_code": manifest_workflow_code,
                "acceptance_status": status,
                "accepted_pack_path": str(accepted.get("accepted_pack_path") or ""),
                "resolved_pack_path": str(pack_path) if pack_path is not None else "",
                "usable_for_object_pool": accepted.get("usable_for_object_pool"),
                "stage": str(queue_row.get("stage") or ""),
                "ready": queue_row.get("ready") is True,
                "query_profile_id": str(queue_row.get("query_profile_id") or accepted.get("query_profile_id") or ""),
                "gap_count": len(gaps_by_person.get(person, [])),
                "blocking_gap_count": sum(1 for gap in gaps_by_person.get(person, []) if str(gap.get("decision") or "") in BLOCKING_GAP_DECISIONS),
                "profile_patch_count": len([row for row in patch_rows if str(row.get("person") or "").strip() == person]),
                "issue_count": len(person_issues),
                "block_count": sum(1 for issue in person_issues if issue["severity"] == "block"),
                "warning_count": sum(1 for issue in person_issues if issue["severity"] == "warning"),
                "ready_for_next_stage": status in READY_STATUSES and not any(issue["severity"] == "block" for issue in person_issues),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": manifest.get("batch_id") or handoff_dir.name,
        "workflow_code": manifest_workflow_code,
        "path": str(handoff_dir),
        "ok": block_count == 0,
        "block_count": block_count,
        "warning_count": warning_count,
        "person_count": len(persons),
        "ready_people": sorted(set(ready_people)),
        "next_stage_count": len(queue_rows),
        "acceptance_counts": dict(sorted(acceptance_counts.items())),
        "person_statuses": person_statuses,
        "pack_audits": pack_audits,
        "issues": issues,
    }


def discover_handoff_dirs(handoff_root: Path) -> list[Path]:
    if (handoff_root / "manifest.json").exists():
        return [handoff_root]
    if not handoff_root.exists():
        return []
    return sorted(path for path in handoff_root.iterdir() if path.is_dir() and (path / "manifest.json").exists())


def build_report(
    handoff_root: Path,
    *,
    source_pack_root: Path | None = None,
    audit_packs: bool = True,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> dict[str, Any]:
    workflow_code = normalize_workflow_code(workflow_code)
    discovered_reports = [validate_handoff_dir(path, source_pack_root=source_pack_root, audit_packs=audit_packs) for path in discover_handoff_dirs(handoff_root)]
    reports = [report for report in discovered_reports if normalize_workflow_code(report.get("workflow_code") or DEFAULT_WORKFLOW_CODE) == workflow_code]
    skipped_workflow_batches = [
        {"batch_id": report.get("batch_id"), "workflow_code": report.get("workflow_code"), "path": report.get("path")}
        for report in discovered_reports
        if normalize_workflow_code(report.get("workflow_code") or DEFAULT_WORKFLOW_CODE) != workflow_code
    ]
    ready_people = sorted({person for report in reports for person in report.get("ready_people", [])})
    ready_queue: list[dict[str, Any]] = []
    needs_more_profile_work: list[dict[str, Any]] = []
    blocked_people: list[dict[str, Any]] = []
    for report in reports:
        batch_id = str(report.get("batch_id") or "")
        batch_path = str(report.get("path") or "")
        pack_audits = report.get("pack_audits") if isinstance(report.get("pack_audits"), Mapping) else {}
        for person_status in report.get("person_statuses") or []:
            if not isinstance(person_status, Mapping):
                continue
            entry = {
                "person": person_status.get("person", ""),
                "workflow_code": workflow_code,
                "batch_id": batch_id,
                "batch_path": batch_path,
                "acceptance_status": person_status.get("acceptance_status", ""),
                "accepted_pack_path": person_status.get("accepted_pack_path", ""),
                "resolved_pack_path": person_status.get("resolved_pack_path", ""),
                "stage": person_status.get("stage", ""),
                "query_profile_id": person_status.get("query_profile_id", ""),
                "gap_count": person_status.get("gap_count", 0),
                "blocking_gap_count": person_status.get("blocking_gap_count", 0),
                "profile_patch_count": person_status.get("profile_patch_count", 0),
                "pack_audit": pack_audits.get(str(person_status.get("person") or ""), {}),
            }
            if person_status.get("ready_for_next_stage"):
                ready_queue.append(entry)
            if person_status.get("acceptance_status") == "needs_more_profile_work":
                needs_more_profile_work.append(entry)
            if person_status.get("acceptance_status") == "blocked" or int(person_status.get("block_count") or 0) > 0:
                blocked_people.append(entry)
    issues: list[dict[str, Any]] = []
    ready_counter = Counter(str(row.get("person") or "") for row in ready_queue)
    for person, count in sorted(ready_counter.items()):
        if person and count > 1:
            _issue(issues, "block", "duplicate_ready_person", "ready person appears in multiple handoff batches", person=person, count=count)
    total_blocks = sum(report["block_count"] for report in reports) + sum(1 for issue in issues if issue["severity"] == "block")
    total_warnings = sum(report["warning_count"] for report in reports) + sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "workflow_code": workflow_code,
        "handoff_root": str(handoff_root),
        "ok": total_blocks == 0,
        "batch_count": len(reports),
        "skipped_batch_count": len(skipped_workflow_batches),
        "ready_people": ready_people,
        "ready_people_count": len(ready_people),
        "ready_queue": ready_queue,
        "needs_more_profile_work": needs_more_profile_work,
        "blocked_people": blocked_people,
        "block_count": total_blocks,
        "warning_count": total_warnings,
        "issues": issues,
        "skipped_workflow_batches": skipped_workflow_batches,
        "batches": reports,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    workflow_code = normalize_workflow_code(str(report.get("workflow_code") or DEFAULT_WORKFLOW_CODE))
    lines = [
        f"# {workflow_code} source pack handoff validation",
        "",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- workflow_code: `{workflow_code}`",
        f"- handoff_root: `{report.get('handoff_root') or ''}`",
        f"- ok: `{str(report.get('ok')).lower()}`",
        f"- batches: `{report.get('batch_count', 0)}`",
        f"- skipped_batches: `{report.get('skipped_batch_count', 0)}`",
        f"- ready_people: `{report.get('ready_people_count', 0)}`",
        f"- needs_more_profile_work: `{len(report.get('needs_more_profile_work') or [])}`",
        f"- blocked_people: `{len(report.get('blocked_people') or [])}`",
        f"- blocks: `{report.get('block_count', 0)}`",
        f"- warnings: `{report.get('warning_count', 0)}`",
        "",
        "## Batches",
        "",
        "| batch | ok | persons | ready | next_stage | blocks | statuses |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for batch in report.get("batches") or []:
        statuses = "；".join(f"{key}={value}" for key, value in (batch.get("acceptance_counts") or {}).items())
        lines.append(
            "| {batch} | {ok} | {persons} | {ready} | {next_stage} | {blocks} | {statuses} |".format(
                batch=batch.get("batch_id", ""),
                ok=str(batch.get("ok")).lower(),
                persons=batch.get("person_count", 0),
                ready=len(batch.get("ready_people") or []),
                next_stage=batch.get("next_stage_count", 0),
                blocks=batch.get("block_count", 0),
                statuses=statuses,
            )
        )
    ready_queue = report.get("ready_queue") if isinstance(report.get("ready_queue"), list) else []
    if ready_queue:
        lines.extend(["", "## Ready Queue", "", "| person | batch | stage | pack | gaps |", "| --- | --- | --- | --- | ---: |"])
        for row in ready_queue:
            if not isinstance(row, Mapping):
                continue
            lines.append(
                "| {person} | {batch} | {stage} | {pack} | {gaps} |".format(
                    person=row.get("person", ""),
                    batch=row.get("batch_id", ""),
                    stage=row.get("stage", ""),
                    pack=row.get("resolved_pack_path") or row.get("accepted_pack_path", ""),
                    gaps=row.get("gap_count", 0),
                )
            )
    needs = report.get("needs_more_profile_work") if isinstance(report.get("needs_more_profile_work"), list) else []
    if needs:
        lines.extend(["", "## Needs More Profile Work", "", "| person | batch | patches | gaps |", "| --- | --- | ---: | ---: |"])
        for row in needs:
            if isinstance(row, Mapping):
                lines.append(f"| {row.get('person', '')} | {row.get('batch_id', '')} | {row.get('profile_patch_count', 0)} | {row.get('gap_count', 0)} |")
    issue_lines: list[str] = []
    for issue in report.get("issues") or []:
        issue_lines.append(f"- `global` {issue.get('severity')} {issue.get('code')}: {issue.get('message')} {issue.get('person', '')}".rstrip())
    for batch in report.get("batches") or []:
        for issue in batch.get("issues") or []:
            issue_lines.append(f"- `{batch.get('batch_id')}` {issue.get('severity')} {issue.get('code')}: {issue.get('message')} {issue.get('person', '')}".rstrip())
    if issue_lines:
        lines.extend(["", "## Issues", "", *issue_lines])
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize and validate source-pack batch handoffs.")
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE, help="Workflow/subitem code for handoff metadata.")
    parser.add_argument("--handoff-root", type=Path, default=None)
    parser.add_argument("--source-pack-root", type=Path, default=None)
    parser.add_argument("--init", action="store_true", help="Create a batch handoff skeleton.")
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--owner", default="")
    parser.add_argument("--person", action="append", default=[])
    parser.add_argument("--no-audit-packs", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-issue", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workflow_code = normalize_workflow_code(args.workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    handoff_root = args.handoff_root or source_paths.get("handoff_root") or ROOT / ".tmp" / "handoffs"
    source_pack_root = args.source_pack_root or source_paths.get("source_pack_root")
    if args.init:
        path = init_handoff(
            handoff_root=handoff_root,
            batch_id=args.batch_id,
            persons=args.person,
            owner=args.owner,
            workflow_code=workflow_code,
        )
        payload = {"created": str(path)}
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else f"created: `{path}`\n"
        if args.output:
            _atomic_write_text(args.output, text)
        else:
            print(text, end="")
        return 0

    report = build_report(
        handoff_root,
        source_pack_root=source_pack_root,
        audit_packs=not args.no_audit_packs,
        workflow_code=workflow_code,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(report)
    if args.output:
        _atomic_write_text(args.output, text)
    else:
        print(text, end="")
    return 1 if args.fail_on_issue and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
