from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_staging_mapper import StagingRow, build_staging_rows, load_source_rows
from scripts.platform.jsonl_target_mapping import (
    CANONICAL_JSONL_FILES,
    MAPPING_VERSION,
    assert_report_has_no_blocked_terms,
    build_mappings,
    is_reference_risk_field,
    sanitize_report_field,
)
from scripts.platform.jsonl_unknown_field_triage import TRIAGE_VERSION, build_decision_registry


RESOLVER_VERSION = "jsonl-staging-resolver-contract-v1"
ANCHOR_FILES = {
    "data/thematic_anchors.jsonl",
    "data/thematic_anchor_objects.jsonl",
    "data/thematic_anchor_events.jsonl",
    "data/thematic_anchor_mechanisms.jsonl",
}
LIMITATIONS = (
    "本报告只定义 staging/ref-risk resolver 契约，不写正式业务表。",
    "source_id 只能先进入 source document resolver；source_id != passage_id。",
    "passage span 需要后续人工 passage review，当前不得写 evd_src_links。",
    "person 中文名、item/subitem、linked_*、*_ids 与 cross_item* 只作为 resolver input 或 range/filter。",
    "thematic anchor 文件保持 staging-only；当前 schema 缺少正式 anchors 与 anchor_links target。",
    "本报告不是证据卡、裁判结论或业务汇总。",
)


@dataclass(frozen=True)
class ResolverSpec:
    domain: str
    input_shape: str
    candidate_source: str
    resolution_target: str
    required_preconditions: tuple[str, ...]
    allowed_action: str
    blocked_action: str
    reason: str
    manual_review_required: bool


DOMAIN_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "person": {
        "required_preconditions": [
            "person identity resolver exists",
            "Chinese names and aliases are disambiguated before person_id use",
        ],
        "allowed_action": "resolver_input_only",
        "blocked_action": "direct_person_id_write",
    },
    "subitem": {
        "required_preconditions": ["item/subitem catalog resolver exists"],
        "allowed_action": "range_filter_or_resolver_input_only",
        "blocked_action": "evidence_relationship_write",
    },
    "query_profile": {
        "required_preconditions": ["query profile code exists in canonical query_profiles rows"],
        "allowed_action": "resolve_code_then_mapper_input",
        "blocked_action": "direct_relationship_write_without_resolver",
    },
    "source_document": {
        "required_preconditions": ["source document code resolver exists"],
        "allowed_action": "resolve_to_source_document_or_code_only",
        "blocked_action": "passage_id_write_or_evd_src_links_write",
    },
    "source_passage": {
        "required_preconditions": ["reviewed passage span exists after source document resolution"],
        "allowed_action": "manual_passage_review_input_only",
        "blocked_action": "automatic_passage_link_write",
    },
    "evidence_card": {
        "required_preconditions": ["evidence card code exists in canonical evidence_cards rows"],
        "allowed_action": "resolve_code_then_mapper_input",
        "blocked_action": "direct_fk_write_without_resolver",
    },
    "evidence_cluster": {
        "required_preconditions": ["cluster code exists in canonical evidence_clusters rows"],
        "allowed_action": "resolve_code_then_mapper_input",
        "blocked_action": "cluster_relationship_write_without_resolver",
    },
    "anchor": {
        "required_preconditions": ["formal anchor target schema and resolver are defined in a later PR"],
        "allowed_action": "staging_placeholder_or_blocked_reference_report",
        "blocked_action": "anchors_or_anchor_links_write",
    },
}


FIELD_SPECS: dict[str, ResolverSpec] = {
    "person": ResolverSpec(
        domain="person",
        input_shape="name_or_code_scalar",
        candidate_source="stg_jsonl_rows.range_filter_fields",
        resolution_target="person resolver output",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["person"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["person"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["person"]["blocked_action"],
        reason="Person labels are not durable identifiers.",
        manual_review_required=True,
    ),
    "persons": ResolverSpec(
        domain="person",
        input_shape="name_or_code_list",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="person resolver output",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["person"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["person"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["person"]["blocked_action"],
        reason="Person lists require identity disambiguation.",
        manual_review_required=True,
    ),
    "linked_persons": ResolverSpec(
        domain="person",
        input_shape="name_or_code_list",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="person resolver output",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["person"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["person"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["person"]["blocked_action"],
        reason="Linked person references require a later anchor/person resolver.",
        manual_review_required=True,
    ),
    "item": ResolverSpec(
        domain="subitem",
        input_shape="range_filter_scalar",
        candidate_source="stg_jsonl_rows.range_filter_fields",
        resolution_target="subitem resolver input",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["subitem"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["subitem"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["subitem"]["blocked_action"],
        reason="Item narrows review scope but does not prove an evidence relation.",
        manual_review_required=True,
    ),
    "subitem": ResolverSpec(
        domain="subitem",
        input_shape="range_filter_scalar",
        candidate_source="stg_jsonl_rows.range_filter_fields",
        resolution_target="subitem resolver input",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["subitem"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["subitem"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["subitem"]["blocked_action"],
        reason="Subitem narrows review scope but does not prove an evidence relation.",
        manual_review_required=True,
    ),
    "query_profile_id": ResolverSpec(
        domain="query_profile",
        input_shape="code_scalar",
        candidate_source="mapping.code_field_or_reference_risk_fields",
        resolution_target="query_profiles.code",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["query_profile"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["query_profile"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["query_profile"]["blocked_action"],
        reason="Query profile codes must resolve to canonical profile rows before relationships.",
        manual_review_required=False,
    ),
    "inherits_from": ResolverSpec(
        domain="query_profile",
        input_shape="code_scalar_or_list",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="query_profiles.code",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["query_profile"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["query_profile"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["query_profile"]["blocked_action"],
        reason="Profile inheritance requires a profile resolver and cycle review.",
        manual_review_required=True,
    ),
    "source_id": ResolverSpec(
        domain="source_document",
        input_shape="code_scalar",
        candidate_source="mapping.code_field_or_reference_risk_fields",
        resolution_target="src_docs.code or source document resolver output",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["source_document"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["source_document"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["source_document"]["blocked_action"],
        reason="source_id is a document/source-code reference, not a passage identifier.",
        manual_review_required=True,
    ),
    "linked_source_ids": ResolverSpec(
        domain="source_document",
        input_shape="code_list",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="src_docs.code or source document resolver output",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["source_document"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["source_document"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["source_document"]["blocked_action"],
        reason="Linked source codes require document resolution and later passage review.",
        manual_review_required=True,
    ),
    "evidence_id": ResolverSpec(
        domain="evidence_card",
        input_shape="code_scalar",
        candidate_source="mapping.code_field",
        resolution_target="evd_cards.code",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["evidence_card"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["evidence_card"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["evidence_card"]["blocked_action"],
        reason="Evidence card codes can identify card candidates only after mapper validation.",
        manual_review_required=False,
    ),
    "linked_evidence_ids": ResolverSpec(
        domain="evidence_card",
        input_shape="code_list",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="evd_cards.code",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["evidence_card"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["evidence_card"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["evidence_card"]["blocked_action"],
        reason="Linked evidence codes require resolver proof before relationship writes.",
        manual_review_required=True,
    ),
    "cluster_id": ResolverSpec(
        domain="evidence_cluster",
        input_shape="code_scalar",
        candidate_source="mapping.code_field",
        resolution_target="clusters.code",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["evidence_cluster"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["evidence_cluster"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["evidence_cluster"]["blocked_action"],
        reason="Cluster codes can identify cluster candidates only after mapper validation.",
        manual_review_required=False,
    ),
    "linked_cluster_ids": ResolverSpec(
        domain="evidence_cluster",
        input_shape="code_list",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="clusters.code",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["evidence_cluster"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["evidence_cluster"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["evidence_cluster"]["blocked_action"],
        reason="Linked cluster codes require resolver proof before relationship writes.",
        manual_review_required=True,
    ),
    "cluster_candidate_id": ResolverSpec(
        domain="evidence_cluster",
        input_shape="code_scalar",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="clusters.code",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["evidence_cluster"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["evidence_cluster"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["evidence_cluster"]["blocked_action"],
        reason="Candidate cluster codes need cluster resolver review.",
        manual_review_required=True,
    ),
    "anchor_id": ResolverSpec(
        domain="anchor",
        input_shape="code_scalar",
        candidate_source="mapping.code_field",
        resolution_target="staging-only anchor placeholder",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["anchor"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["anchor"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["anchor"]["blocked_action"],
        reason="Anchor rows have no formal target schema in this stage.",
        manual_review_required=True,
    ),
    "object_anchor": ResolverSpec(
        domain="anchor",
        input_shape="anchor_name_scalar",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="staging-only anchor placeholder",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["anchor"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["anchor"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["anchor"]["blocked_action"],
        reason="Anchor names require later anchor identity rules.",
        manual_review_required=True,
    ),
    "object_anchors": ResolverSpec(
        domain="anchor",
        input_shape="anchor_object_list",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="staging-only anchor placeholder",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["anchor"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["anchor"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["anchor"]["blocked_action"],
        reason="Embedded anchor objects require later anchor resolver review.",
        manual_review_required=True,
    ),
    "thematic_anchor_targets": ResolverSpec(
        domain="anchor",
        input_shape="anchor_name_list",
        candidate_source="stg_jsonl_rows.reference_risk_fields",
        resolution_target="staging-only anchor placeholder",
        required_preconditions=tuple(DOMAIN_REQUIREMENTS["anchor"]["required_preconditions"]),
        allowed_action=DOMAIN_REQUIREMENTS["anchor"]["allowed_action"],
        blocked_action=DOMAIN_REQUIREMENTS["anchor"]["blocked_action"],
        reason="Thematic anchor targets have no formal link target yet.",
        manual_review_required=True,
    ),
}


def build_contract_report(
    *,
    source_root: Path = ROOT,
    relative_files: Sequence[str] = CANONICAL_JSONL_FILES,
) -> dict[str, Any]:
    mappings = build_mappings()
    source_rows = load_source_rows(source_root=source_root, relative_files=relative_files)
    staging_rows = build_staging_rows(source_rows)
    triage_registry = build_decision_registry()
    source_files = sorted({row.source_file for row in source_rows})
    rows_by_file = count_rows_by_file(staging_rows)
    line_index = build_field_line_index(staging_rows)
    manual_review_fields = collect_manual_review_fields(staging_rows, triage_registry)
    resolver_rules = build_resolver_rules(source_files, line_index, manual_review_fields)
    blocked_writes = build_blocked_relationship_writes(staging_rows, resolver_rules)

    report = {
        "mode": "contract-report",
        "resolver_version": RESOLVER_VERSION,
        "mapping_version": MAPPING_VERSION,
        "triage_version": TRIAGE_VERSION,
        "source_files": source_files,
        "rows_by_file": rows_by_file,
        "resolver_inputs_by_file": build_resolver_inputs_by_file(line_index),
        "resolver_rules": resolver_rules,
        "resolver_requirements_by_domain": DOMAIN_REQUIREMENTS,
        "unresolved_references_by_file": build_unresolved_references_by_file(line_index),
        "manual_review_fields_by_file": manual_review_fields,
        "staging_only_reference_domains": build_staging_only_reference_domains(source_files, mappings),
        "blocked_relationship_writes": blocked_writes,
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def count_rows_by_file(rows: Sequence[StagingRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.source_file] = counts.get(row.source_file, 0) + 1
    return counts


def build_field_line_index(rows: Sequence[StagingRow]) -> dict[str, dict[str, dict[str, Any]]]:
    index: dict[str, dict[str, dict[str, Any]]] = {}
    mappings = build_mappings()
    for row in rows:
        mapping = mappings.get(row.source_file)
        for field in sorted(set(row.reference_risk_fields) | set(row.range_filter_fields)):
            add_field_occurrence(index, row.source_file, field, row.line_no, "staging_bucket")
        if mapping and mapping.code_field and row.jsonl_code:
            add_field_occurrence(index, row.source_file, mapping.code_field, row.line_no, "mapping_code_field")
        if row.source_file in ANCHOR_FILES:
            add_field_occurrence(index, row.source_file, "anchor_id", row.line_no, "staging_only_code_field")
    return index


def add_field_occurrence(
    index: dict[str, dict[str, dict[str, Any]]],
    source_file: str,
    field: str,
    line_no: int,
    source: str,
) -> None:
    display_field = sanitize_report_field(field)
    entry = index.setdefault(source_file, {}).setdefault(
        display_field,
        {"field": display_field, "line_numbers": [], "candidate_sources": []},
    )
    if line_no not in entry["line_numbers"]:
        entry["line_numbers"].append(line_no)
    if source not in entry["candidate_sources"]:
        entry["candidate_sources"].append(source)


def collect_manual_review_fields(
    rows: Sequence[StagingRow],
    triage_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_file: dict[str, dict[str, set[int]]] = {}
    for row in rows:
        source_registry = triage_registry.get(row.source_file, {})
        for field in row.unknown_fields:
            by_file.setdefault(row.source_file, {}).setdefault(sanitize_report_field(field), set()).add(row.line_no)
        for field in row.payload_fields:
            decision = source_registry.get(field)
            if decision and decision.category == "manual_review":
                by_file.setdefault(row.source_file, {}).setdefault(sanitize_report_field(field), set()).add(row.line_no)

    return {
        source_file: [
            {
                "field": field,
                "line_numbers": sorted(lines),
                "reason": "manual review required before resolver output can be trusted",
            }
            for field, lines in sorted(fields.items())
        ]
        for source_file, fields in sorted(by_file.items())
    }


def build_resolver_rules(
    source_files: Sequence[str],
    line_index: Mapping[str, Mapping[str, Mapping[str, Any]]],
    manual_review_fields: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for source_file in source_files:
        fields = set(line_index.get(source_file, {}))
        fields.update(item["field"] for item in manual_review_fields.get(source_file, ()))
        for field in sorted(fields):
            spec = spec_for_field(source_file, field)
            occurrence = line_index.get(source_file, {}).get(field, {})
            rules.append(
                {
                    "source_file": source_file,
                    "field": field,
                    "resolver_domain": spec.domain,
                    "input_shape": spec.input_shape,
                    "candidate_source": spec.candidate_source,
                    "resolution_target": spec.resolution_target,
                    "required_preconditions": list(spec.required_preconditions),
                    "allowed_action": spec.allowed_action,
                    "blocked_action": spec.blocked_action,
                    "reason": spec.reason,
                    "manual_review_required": spec.manual_review_required or is_manual_field(source_file, field, manual_review_fields),
                    "line_numbers": sorted(occurrence.get("line_numbers", [])),
                }
            )

    rules.append(
        {
            "source_file": "data/evidence_cards.jsonl",
            "field": "source_id",
            "resolver_domain": "source_passage",
            "input_shape": "reviewed_text_span_after_source_document_resolution",
            "candidate_source": "future passage review",
            "resolution_target": "reviewed passage span",
            "required_preconditions": DOMAIN_REQUIREMENTS["source_passage"]["required_preconditions"],
            "allowed_action": DOMAIN_REQUIREMENTS["source_passage"]["allowed_action"],
            "blocked_action": DOMAIN_REQUIREMENTS["source_passage"]["blocked_action"],
            "reason": "source document resolution is not passage resolution.",
            "manual_review_required": True,
            "line_numbers": sorted(line_index.get("data/evidence_cards.jsonl", {}).get("source_id", {}).get("line_numbers", [])),
        }
    )
    return sorted(rules, key=lambda item: (item["source_file"], item["field"], item["resolver_domain"]))


def spec_for_field(source_file: str, field: str) -> ResolverSpec:
    if source_file in ANCHOR_FILES and field not in {"person", "persons", "linked_persons"}:
        return FIELD_SPECS.get(field) or FIELD_SPECS["anchor_id"]
    if field in FIELD_SPECS:
        return FIELD_SPECS[field]
    if is_reference_risk_field(field):
        if "source" in field:
            return FIELD_SPECS["linked_source_ids"]
        if "evidence" in field:
            return FIELD_SPECS["linked_evidence_ids"]
        if "cluster" in field:
            return FIELD_SPECS["linked_cluster_ids"]
        return ResolverSpec(
            domain="anchor" if source_file in ANCHOR_FILES else "source_document",
            input_shape="reference_risk_value",
            candidate_source="stg_jsonl_rows.reference_risk_fields",
            resolution_target="resolver output",
            required_preconditions=("explicit resolver rule is registered",),
            allowed_action="manual_review_input_only",
            blocked_action="direct_fk_or_relationship_write",
            reason="Dynamic reference-risk field requires explicit resolver review.",
            manual_review_required=True,
        )
    return ResolverSpec(
        domain="anchor" if source_file in ANCHOR_FILES else "query_profile",
        input_shape="manual_review_value",
        candidate_source="unknown_field_triage.manual_review",
        resolution_target="manual review decision",
        required_preconditions=("explicit triage decision is registered",),
        allowed_action="manual_review_only",
        blocked_action="automatic_resolution",
        reason="No automatic resolver rule is registered for this field.",
        manual_review_required=True,
    )


def is_manual_field(
    source_file: str,
    field: str,
    manual_review_fields: Mapping[str, Sequence[Mapping[str, Any]]],
) -> bool:
    return any(item["field"] == field for item in manual_review_fields.get(source_file, ()))


def build_resolver_inputs_by_file(
    line_index: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for source_file, fields in sorted(line_index.items()):
        entries = []
        for field, item in sorted(fields.items()):
            spec = spec_for_field(source_file, field)
            entries.append(
                {
                    "field": field,
                    "resolver_domain": spec.domain,
                    "input_shape": spec.input_shape,
                    "candidate_sources": sorted(item["candidate_sources"]),
                    "line_numbers": sorted(item["line_numbers"]),
                }
            )
        result[source_file] = entries
    return result


def build_unresolved_references_by_file(
    line_index: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    unresolved: dict[str, list[dict[str, Any]]] = {}
    for source_file, fields in sorted(line_index.items()):
        entries = []
        for field, item in sorted(fields.items()):
            spec = spec_for_field(source_file, field)
            if spec.allowed_action in {"resolver_input_only", "range_filter_or_resolver_input_only"} or "write" in spec.blocked_action:
                entries.append(
                    {
                        "field": field,
                        "resolver_domain": spec.domain,
                        "line_numbers": sorted(item["line_numbers"]),
                        "blocked_action": spec.blocked_action,
                        "reason": spec.reason,
                    }
                )
        if entries:
            unresolved[source_file] = entries
    return unresolved


def build_staging_only_reference_domains(
    source_files: Sequence[str],
    mappings: Mapping[str, Any],
) -> list[dict[str, Any]]:
    domains = []
    for source_file in sorted(set(source_files) & ANCHOR_FILES):
        mapping = mappings[source_file]
        domains.append(
            {
                "source_file": source_file,
                "resolver_domain": "anchor",
                "staging_only": True,
                "blocked_reason": mapping.blocked_reason,
                "blocked_action": DOMAIN_REQUIREMENTS["anchor"]["blocked_action"],
            }
        )
    return domains


def build_blocked_relationship_writes(
    rows: Sequence[StagingRow],
    rules: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rule_lookup = {(rule["source_file"], rule["field"], rule["resolver_domain"]): rule for rule in rules}
    blocked: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        fields = set(row.reference_risk_fields) | set(row.range_filter_fields)
        if row.source_file in ANCHOR_FILES:
            fields.add("anchor_id")
        for field in fields:
            display_field = sanitize_report_field(field)
            spec = spec_for_field(row.source_file, display_field)
            key = (row.source_file, display_field, spec.domain)
            rule = rule_lookup.get(key)
            entry = blocked.setdefault(
                key,
                {
                    "source_file": row.source_file,
                    "field": display_field,
                    "resolver_domain": spec.domain,
                    "blocked_action": spec.blocked_action,
                    "allowed_action": spec.allowed_action,
                    "line_numbers": [],
                    "reason": rule["reason"] if rule else spec.reason,
                },
            )
            if row.line_no not in entry["line_numbers"]:
                entry["line_numbers"].append(row.line_no)
    return sorted(
        ({**entry, "line_numbers": sorted(entry["line_numbers"])} for entry in blocked.values()),
        key=lambda item: (item["source_file"], item["field"], item["resolver_domain"]),
    )


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Report offline staging resolver contract rules.")
    parser.add_argument("--contract-report", action="store_true", help="print the offline resolver contract report")
    parser.add_argument("--source-root", type=Path, default=ROOT, help="repository root or fixture root")
    args = parser.parse_args(argv)

    report = build_contract_report(source_root=args.source_root)
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
