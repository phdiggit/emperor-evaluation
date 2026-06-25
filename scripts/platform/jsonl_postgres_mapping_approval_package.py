from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.canonical_manifest_gate import build_candidate_report  # noqa: E402
from scripts.platform.jsonl_staging_mapper import build_contract_report as build_staging_report  # noqa: E402
from scripts.platform.jsonl_target_mapping import (  # noqa: E402
    CANONICAL_JSONL_FILES,
    MAPPING_VERSION,
    build_contract_report as build_mapping_report,
    build_mappings,
)
from scripts.platform.jsonl_unknown_field_triage import build_contract_report as build_triage_report  # noqa: E402


PACKAGE_VERSION = "jsonl-postgres-mapping-approval-package-v1"
G1_MANIFEST_SHA256 = "1d395d0bc5c859e02add21de4ccde62f8172332123facd668cecb9c10bd8431f"
LIMITATIONS = (
    "G1 manifest is approved; G2 mapping is not approved by this package.",
    "The package is offline and does not read production DSN.",
    "The package does not connect PostgreSQL and does not write target business tables.",
    "The package does not freeze JSONL or switch PostgreSQL to unique write source.",
)


def build_package_report(*, source_root: Path = ROOT) -> dict[str, Any]:
    manifest_report = build_candidate_report(source_root=source_root)
    mapping_report = build_mapping_report(source_root=source_root)
    staging_report = build_staging_report(source_root=source_root)
    triage_report = build_triage_report(source_root=source_root)
    mappings = build_mappings()

    coverage_files = list(CANONICAL_JSONL_FILES)
    missing_mapping_files = sorted(set(manifest_report["data_survey"]["covered_files"]) - set(mapping_report["files"]))
    unknown_fields = mapping_report["unknown_fields_by_file"]
    remaining_unknown_fields = triage_report["remaining_unknown_fields_by_file"]
    staging_only_files = mapping_report["staging_only_files"]

    report = {
        "mode": "mapping-approval-package",
        "package_version": PACKAGE_VERSION,
        "gate_status": "G2_REQUIRED",
        "approval_required_from_user": True,
        "g1_manifest_approved": True,
        "g1_manifest_sha256": G1_MANIFEST_SHA256,
        "current_manifest_sha256": manifest_report["manifest_sha256"],
        "manifest_matches_g1": manifest_report["manifest_sha256"] == G1_MANIFEST_SHA256,
        "mapping_version": MAPPING_VERSION,
        "covered_files": coverage_files,
        "covered_file_count": len(coverage_files),
        "missing_mapping_files": missing_mapping_files,
        "staging_only_files": staging_only_files,
        "mapping_unknown_fields_by_file": unknown_fields,
        "remaining_unknown_fields_by_file": remaining_unknown_fields,
        "missing_required_fields_by_file": mapping_report["missing_required_fields_by_file"],
        "duplicate_codes_by_file": mapping_report["duplicate_codes_by_file"],
        "invalid_json_by_file": mapping_report["invalid_json_by_file"],
        "jsonb_retained_fields_by_file": build_jsonb_retention_report(mappings),
        "relationship_splits": build_relationship_splits(),
        "type_loss_risks": build_type_loss_risks(),
        "relaxed_vs_formal_schema_differences": build_relaxed_schema_differences(staging_only_files),
        "staging_report_summary": {
            "rows_total": staging_report["rows_total"],
            "rows_mapped": staging_report["rows_mapped"],
            "rows_with_reference_risk": staging_report["rows_with_reference_risk"],
            "rows_with_unknown_fields": staging_report["rows_with_unknown_fields"],
            "rows_with_validation_errors": staging_report["rows_with_validation_errors"],
            "target_table_candidates": staging_report["target_table_candidates"],
        },
        "triage_decision_counts": triage_report["decision_counts"],
        "risk_summary": build_risk_summary(
            missing_mapping_files=missing_mapping_files,
            unknown_fields=unknown_fields,
            remaining_unknown_fields=remaining_unknown_fields,
            mapping_report=mapping_report,
        ),
        "boundaries": list(LIMITATIONS),
    }
    return report


def build_jsonb_retention_report(mappings: Mapping[str, Any]) -> dict[str, dict[str, list[str]]]:
    report: dict[str, dict[str, list[str]]] = {}
    for source_file, mapping in mappings.items():
        report[source_file] = {
            "payload_fields": sorted(mapping.payload_fields),
            "reference_risk_fields": sorted(mapping.reference_risk_fields),
            "range_filter_fields": sorted(mapping.range_filter_fields),
            "candidate_fields": sorted(mapping.candidate_fields),
        }
    return report


def build_relationship_splits() -> list[dict[str, str]]:
    return [
        {
            "source": "data/evidence_cards.jsonl.source_id",
            "target": "evd_src_links",
            "status": "deferred_until_source_passage_resolution",
            "reason": "source_id is not passage_id; source/passages resolver must run before relationship write",
        },
        {
            "source": "data/evidence_clusters.jsonl.linked_evidence_ids",
            "target": "cluster_evd",
            "status": "deferred_until_evidence_code_resolution",
            "reason": "array values must split into relationship rows only after evidence card code resolution",
        },
        {
            "source": "data/thematic_anchors*.jsonl linked_* fields",
            "target": "anchor_links",
            "status": "deferred_until_formal_link_table_and_resolver",
            "reason": "anchors table exists, but formal anchor_links target and semantics are not approved",
        },
        {
            "source": "data/search_logs.jsonl result/link fields",
            "target": "search_hits and candidate matches",
            "status": "deferred_until_hit_payload_and_passage_resolution",
            "reason": "search log is not evidence; result payload must split through later ingestion/review flow",
        },
    ]


def build_type_loss_risks() -> list[dict[str, str]]:
    return [
        {
            "field_family": "list/object JSONL fields",
            "risk": "retained_as_jsonb_not_scalar_columns",
            "examples": "query_terms, trigger_terms, five_axis_assessment, linked_*",
        },
        {
            "field_family": "Chinese names and item/subitem labels",
            "risk": "resolver_required_before_foreign_keys",
            "examples": "person, persons, linked_persons, item, subitem",
        },
        {
            "field_family": "status/polarity/tier strings",
            "risk": "formal_check_constraints_require_normalization",
            "examples": "verification_status, adjudication_status, polarity, tier",
        },
        {
            "field_family": "legacy semicolon/comma reference strings",
            "risk": "must_split_before_relationship_rows",
            "examples": "linked_evidence_id and linked_evidence_ids",
        },
    ]


def build_relaxed_schema_differences(staging_only_files: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {
            "area": "staging envelope",
            "relaxed_contract": "stg_jsonl_rows keeps direct/candidate/payload/range/reference/unknown buckets as JSONB",
            "formal_contract": "formal target tables require typed columns and foreign keys",
            "approval_need": "G2 must approve which fields leave JSONB buckets",
        },
        {
            "area": "resolver foreign keys",
            "relaxed_contract": "person, item, subitem and source references remain text/range/reference-risk data",
            "formal_contract": "persons, subitems, passages and target rows use numeric foreign keys",
            "approval_need": "resolver outputs must be approved before target importer writes relationships",
        },
        {
            "area": "relationship tables",
            "relaxed_contract": "evd_src_links, cluster_evd and anchor_links candidates are reported, not written",
            "formal_contract": "relationship tables require resolved target ids and review semantics",
            "approval_need": "G2 mapping must approve relationship split rules; G3 still gates writes",
        },
        {
            "area": "staging-only files",
            "relaxed_contract": sorted(staging_only_files),
            "formal_contract": "events and trigger_terms have no formal target table; anchor_links remains deferred",
            "approval_need": "approve staging-only handling or request schema expansion before importer work",
        },
    ]


def build_risk_summary(
    *,
    missing_mapping_files: Sequence[str],
    unknown_fields: Mapping[str, Any],
    remaining_unknown_fields: Mapping[str, Any],
    mapping_report: Mapping[str, Any],
) -> list[str]:
    risks = [
        "missing mapping" if missing_mapping_files else "no missing mapping",
        "unknown field" if unknown_fields else "no unknown field",
        "remaining manual-review unknown field" if remaining_unknown_fields else "no remaining manual-review unknown field",
        "missing required field" if mapping_report["missing_required_fields_by_file"] else "no missing required field",
        "duplicate code" if mapping_report["duplicate_codes_by_file"] else "no duplicate code",
        "invalid JSON" if mapping_report["invalid_json_by_file"] else "no invalid JSON",
        "relationship/type-loss approval required",
    ]
    return risks


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def report_as_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# JSONL 到 PostgreSQL Mapping Approval Package",
        "",
        "```text",
        "G2_REQUIRED",
        f"mapping_package: python scripts/platform/jsonl_postgres_mapping_approval_package.py --package-report",
        f"g1_manifest_sha256: {report['g1_manifest_sha256']}",
        f"manifest_matches_g1: {str(report['manifest_matches_g1']).lower()}",
        "covered_files:",
    ]
    lines.extend(f"  - {item}" for item in report["covered_files"])
    lines.extend(
        [
            "risk_summary:",
            *[f"  - {item}" for item in report["risk_summary"]],
            "approval_required_from_user: true",
            "```",
            "",
            f"- package_version: `{report['package_version']}`",
            f"- mapping_version: `{report['mapping_version']}`",
            f"- covered_file_count: `{report['covered_file_count']}`",
            f"- staging_rows: `{report['staging_report_summary']['rows_total']}`",
            "",
            "## Staging-Only Files",
            "",
        ]
    )
    lines.extend(f"- `{item}`" for item in report["staging_only_files"])
    lines.extend(["", "## Relationship Splits", ""])
    lines.extend(f"- `{item['source']}` -> `{item['target']}`: {item['status']}" for item in report["relationship_splits"])
    lines.extend(["", "## Boundary", ""])
    lines.extend(f"- {item}" for item in report["boundaries"])
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the Epic 1 G2 JSONL to PostgreSQL mapping approval package.")
    parser.add_argument("--package-report", action="store_true", help="print the mapping approval JSON report")
    parser.add_argument("--markdown-report", action="store_true", help="print the mapping approval Markdown report")
    parser.add_argument("--source-root", type=Path, default=ROOT, help="repository root to scan")
    args = parser.parse_args(argv)

    report = build_package_report(source_root=args.source_root)
    if args.markdown_report:
        sys.stdout.write(report_as_markdown(report))
    else:
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
