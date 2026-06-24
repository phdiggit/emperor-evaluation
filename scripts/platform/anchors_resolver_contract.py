from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
RESOLVER_VERSION = "anchors-resolver-contract-v1"
SCHEMA_PROPOSAL_VERSION = "anchors-schema-proposal-v1"
ANCHOR_SOURCE_FILES = (
    "data/thematic_anchors.jsonl",
    "data/thematic_anchor_objects.jsonl",
    "data/thematic_anchor_events.jsonl",
    "data/thematic_anchor_mechanisms.jsonl",
)
REFERENCE_SOURCE_FILES = (
    "data/query_profiles.jsonl",
    "data/evidence_cards.jsonl",
    "data/evidence_clusters.jsonl",
)
SOURCE_FILES = (*ANCHOR_SOURCE_FILES, *REFERENCE_SOURCE_FILES)
REFERENCE_FIELDS = ("object_anchor", "object_anchors", "thematic_anchor_targets")
INDIRECT_RELATIONSHIP_FIELDS = ("linked_evidence_ids", "linked_cluster_ids")
RESOLVER_STATUS_VALUES = (
    "unresolved_candidate",
    "manual_review_required",
    "blocked_pending_schema",
)
STABLE_ID_FIELDS = ("anchor_id", "anchor_code", "code", "stable_key", "stable_id", "key", "id")
DISPLAY_LABEL_FIELDS = (
    "display_label",
    "label",
    "anchor_label",
    "anchor_name",
    "name",
    "object_name",
    "title",
    "theme",
    "summary",
)
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")
BLOCKED_RELATIONSHIP_WRITES = (
    "anchor_links_write",
    "evidence_relationship_write",
    "cluster_relationship_write",
    "person_subitem_relationship_write",
    "downstream_release_write",
    "adjudication_write",
)


@dataclass(frozen=True)
class JsonlRow:
    source_file: str
    line_no: int
    payload: dict[str, Any]


def build_contract_report(
    *,
    source_root: Path = ROOT,
    relative_files: Sequence[str] = SOURCE_FILES,
) -> dict[str, Any]:
    rows = load_jsonl_rows(source_root=source_root, relative_files=relative_files)
    anchor_rows = [row for row in rows if row.source_file in ANCHOR_SOURCE_FILES]
    reference_rows = [row for row in rows if row.source_file in REFERENCE_SOURCE_FILES]
    anchor_candidates = build_anchor_candidates(anchor_rows)
    reference_inputs = build_anchor_reference_inputs(reference_rows)
    link_candidates = build_anchor_link_candidates(reference_inputs)
    indirect_blocks = build_indirect_relationship_blocks(reference_rows)

    report = {
        "mode": "contract-report",
        "resolver_version": RESOLVER_VERSION,
        "schema_proposal_version": SCHEMA_PROPOSAL_VERSION,
        "source_files": sorted({row.source_file for row in rows}),
        "anchor_source_files": list(ANCHOR_SOURCE_FILES),
        "reference_source_files": list(REFERENCE_SOURCE_FILES),
        "anchor_candidates_by_file": group_by_source_file(anchor_candidates),
        "anchor_reference_inputs_by_file": group_by_source_file(reference_inputs),
        "anchor_link_candidate_plan": build_anchor_link_candidate_plan(link_candidates),
        "resolver_status_values": list(RESOLVER_STATUS_VALUES),
        "blocked_relationship_writes": build_blocked_relationship_writes(link_candidates, indirect_blocks),
        "manual_review_fields_by_file": build_manual_review_fields_by_file(reference_inputs, indirect_blocks),
        "unresolved_references_by_file": build_unresolved_references_by_file(reference_inputs),
        "limitations": [
            "offline_contract_report_only",
            "does_not_read_env_files_or_dsn",
            "does_not_connect_to_postgresql",
            "does_not_access_network",
            "does_not_read_batch_or_archive_data",
            "display_label_is_never_promoted_to_stable_anchor_identity",
            "anchors_do_not_prove_evidence_cluster_person_or_subitem_relationships",
        ],
    }
    assert_report_has_no_blocked_terms(report)
    return report


def load_jsonl_rows(*, source_root: Path, relative_files: Sequence[str]) -> list[JsonlRow]:
    rows: list[JsonlRow] = []
    for relative in relative_files:
        display_path = relative.replace("\\", "/")
        path = source_root / relative
        if not path.exists():
            continue
        for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                payload = {"raw_line": raw_line, "json_error": exc.msg}
            if not isinstance(payload, dict):
                payload = {"value": payload, "json_error": "JSON payload must be an object"}
            rows.append(JsonlRow(source_file=display_path, line_no=line_no, payload=payload))
    return rows


def build_anchor_candidates(rows: Sequence[JsonlRow]) -> list[dict[str, Any]]:
    return [build_anchor_candidate(row) for row in rows]


def build_anchor_candidate(row: JsonlRow) -> dict[str, Any]:
    identity = first_text_value(row.payload, STABLE_ID_FIELDS)
    label = first_text_value(row.payload, DISPLAY_LABEL_FIELDS)
    status = "unresolved_candidate" if identity else "manual_review_required"
    return {
        "source_file": row.source_file,
        "line_no": row.line_no,
        "anchor_code_candidate": identity,
        "identity_source_field": first_present_field(row.payload, STABLE_ID_FIELDS),
        "diagnostic_key": diagnostic_key(row),
        "display_label": label,
        "anchor_type": infer_anchor_type(row.source_file, row.payload),
        "resolver_status": status,
        "display_label_is_stable_id": False,
        "payload_fields": sorted(sanitize_report_field(field) for field in row.payload),
    }


def build_anchor_reference_inputs(rows: Sequence[JsonlRow]) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for row in rows:
        target_domain, target_code = infer_reference_target(row)
        for field in REFERENCE_FIELDS:
            if field not in row.payload:
                continue
            for value in normalize_reference_values(row.payload[field]):
                inputs.append(
                    {
                        "source_file": row.source_file,
                        "line_no": row.line_no,
                        "field": field,
                        "anchor_code_candidate": value["anchor_code_candidate"],
                        "display_label": value["display_label"],
                        "diagnostic_key": diagnostic_key(row, field),
                        "target_domain": target_domain,
                        "target_code": target_code,
                        "resolver_status": value["resolver_status"],
                        "kept_as": "anchor_reference_input",
                        "relationship_proven": False,
                    }
                )
    return inputs


def normalize_reference_values(value: Any) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    raw_values = value if isinstance(value, list) else [value]
    normalized: list[dict[str, Any]] = []
    for item in raw_values:
        if item in (None, ""):
            continue
        if isinstance(item, dict):
            identity = first_text_value(item, STABLE_ID_FIELDS)
            label = first_text_value(item, DISPLAY_LABEL_FIELDS) or stable_text(item)
            normalized.append(
                {
                    "anchor_code_candidate": identity or label,
                    "display_label": label,
                    "resolver_status": "unresolved_candidate" if identity else "manual_review_required",
                }
            )
        else:
            text = str(item).strip()
            if text:
                normalized.append(
                    {
                        "anchor_code_candidate": text,
                        "display_label": text,
                        "resolver_status": "unresolved_candidate",
                    }
                )
    return normalized


def build_anchor_link_candidates(reference_inputs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in reference_inputs:
        candidates.append(
            {
                "anchor_code": item["anchor_code_candidate"] or item["diagnostic_key"],
                "target_domain": item["target_domain"],
                "target_code": item["target_code"],
                "link_role": item["field"],
                "resolver_status": item["resolver_status"],
                "blocked_action": "anchor_links_write",
                "relationship_proven": False,
                "source_file": item["source_file"],
                "line_no": item["line_no"],
            }
        )
    return candidates


def build_anchor_link_candidate_plan(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "target_table": "anchor_link_candidates",
        "formal_relationship_table": False,
        "candidate_rows": len(candidates),
        "columns": [
            "anchor_code",
            "target_domain",
            "target_code",
            "link_role",
            "resolver_status",
            "blocked_action",
            "relationship_proven",
            "source_file",
            "line_no",
            "payload",
        ],
        "resolver_status_allowed": list(RESOLVER_STATUS_VALUES),
        "blocked_action": "anchor_links_write",
        "relationship_proven": False,
        "writes_anchor_links": False,
        "rows_by_source_file": count_by_source_file(candidates),
    }


def build_indirect_relationship_blocks(rows: Sequence[JsonlRow]) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for row in rows:
        for field in INDIRECT_RELATIONSHIP_FIELDS:
            if field not in row.payload:
                continue
            blocked.append(
                {
                    "source_file": row.source_file,
                    "line_no": row.line_no,
                    "field": field,
                    "blocked_action": "evidence_relationship_write"
                    if field == "linked_evidence_ids"
                    else "cluster_relationship_write",
                    "allowed_action": "keep_as_non_anchor_resolver_input",
                    "relationship_proven": False,
                }
            )
    return blocked


def build_blocked_relationship_writes(
    link_candidates: Sequence[Mapping[str, Any]],
    indirect_blocks: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    link_lines = group_line_numbers(link_candidates)
    for source_file, line_numbers in link_lines.items():
        blocked.append(
            {
                "source_file": source_file,
                "target_table": "anchor_links",
                "blocked_action": "anchor_links_write",
                "allowed_action": "unresolved_candidate_report_only",
                "line_numbers": line_numbers,
                "relationship_proven": False,
            }
        )
    for item in indirect_blocks:
        blocked.append(
            {
                "source_file": item["source_file"],
                "field": item["field"],
                "target_table": "non_anchor_relationships",
                "blocked_action": item["blocked_action"],
                "allowed_action": item["allowed_action"],
                "line_numbers": [item["line_no"]],
                "relationship_proven": False,
            }
        )
    return blocked


def build_manual_review_fields_by_file(
    reference_inputs: Sequence[Mapping[str, Any]],
    indirect_blocks: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    manual: dict[str, list[dict[str, Any]]] = {}
    for item in reference_inputs:
        if item["resolver_status"] != "manual_review_required":
            continue
        manual.setdefault(str(item["source_file"]), []).append(
            {
                "field": item["field"],
                "line_numbers": [item["line_no"]],
                "reason": "reference value lacks stable anchor identity",
            }
        )
    for item in indirect_blocks:
        manual.setdefault(str(item["source_file"]), []).append(
            {
                "field": item["field"],
                "line_numbers": [item["line_no"]],
                "reason": "linked evidence or cluster field is not resolved through anchors",
            }
        )
    return manual


def build_unresolved_references_by_file(reference_inputs: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    unresolved: dict[str, dict[str, dict[str, Any]]] = {}
    for item in reference_inputs:
        by_file = unresolved.setdefault(str(item["source_file"]), {})
        field_item = by_file.setdefault(
            str(item["field"]),
            {
                "field": item["field"],
                "line_numbers": [],
                "candidate_count": 0,
                "kept_as": "anchor_reference_input",
                "blocked_action": "anchor_links_write",
                "relationship_proven": False,
            },
        )
        field_item["line_numbers"].append(item["line_no"])
        field_item["candidate_count"] += 1
    return {
        source_file: [
            {**item, "line_numbers": sorted(set(item["line_numbers"]))}
            for item in fields.values()
        ]
        for source_file, fields in unresolved.items()
    }


def group_by_source_file(items: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(str(item["source_file"]), []).append(dict(item))
    return grouped


def count_by_source_file(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        source_file = str(item["source_file"])
        counts[source_file] = counts.get(source_file, 0) + 1
    return counts


def group_line_numbers(items: Sequence[Mapping[str, Any]]) -> dict[str, list[int]]:
    grouped: dict[str, set[int]] = {}
    for item in items:
        grouped.setdefault(str(item["source_file"]), set()).add(int(item["line_no"]))
    return {source_file: sorted(line_numbers) for source_file, line_numbers in grouped.items()}


def infer_anchor_type(source_file: str, payload: Mapping[str, Any]) -> str:
    explicit = first_text_value(payload, ("anchor_type", "anchor_kind", "object_type"))
    if explicit:
        return explicit
    if source_file.endswith("thematic_anchor_objects.jsonl"):
        return "object"
    if source_file.endswith("thematic_anchor_events.jsonl"):
        return "event"
    if source_file.endswith("thematic_anchor_mechanisms.jsonl"):
        return "mechanism"
    return "theme"


def infer_reference_target(row: JsonlRow) -> tuple[str, str | None]:
    if row.source_file.endswith("query_profiles.jsonl"):
        return "query_profile", stable_text(row.payload.get("query_profile_id"))
    if row.source_file.endswith("evidence_cards.jsonl"):
        return "evidence_card", stable_text(row.payload.get("evidence_id"))
    if row.source_file.endswith("evidence_clusters.jsonl"):
        return "evidence_cluster", stable_text(row.payload.get("cluster_id"))
    return "unknown", None


def diagnostic_key(row: JsonlRow, *parts: str) -> str:
    suffix = ":".join(parts)
    if suffix:
        return f"{row.source_file}:{row.line_no}:{suffix}"
    return f"{row.source_file}:{row.line_no}"


def first_present_field(payload: Mapping[str, Any], fields: Sequence[str]) -> str | None:
    for field in fields:
        if stable_text(payload.get(field)):
            return field
    return None


def first_text_value(payload: Mapping[str, Any], fields: Sequence[str]) -> str | None:
    for field in fields:
        value = stable_text(payload.get(field))
        if value:
            return value
    return None


def stable_text(value: Any) -> str | None:
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return text or None
    return None


def sanitize_report_field(field: str) -> str:
    lowered = field.lower()
    if any(term in lowered for term in BLOCKED_REPORT_TERMS):
        return "[blocked-report-field]"
    return field


def assert_report_has_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False, sort_keys=True).lower()
    for term in BLOCKED_REPORT_TERMS:
        if term in text:
            raise AssertionError(f"report unexpectedly contains {term!r}")


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Report the offline anchors resolver contract.")
    parser.add_argument("--contract-report", action="store_true", help="print the offline anchors resolver report")
    parser.add_argument("--source-root", type=Path, default=ROOT, help="repository root or fixture root")
    args = parser.parse_args(argv)

    report = build_contract_report(source_root=args.source_root)
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
