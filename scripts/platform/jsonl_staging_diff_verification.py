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
from scripts.platform.jsonl_postgres_mapping_approval_package import (  # noqa: E402
    G1_MANIFEST_SHA256,
    build_package_report,
)
from scripts.platform.jsonl_staging_mapper import build_contract_report as build_staging_report  # noqa: E402
from scripts.platform.jsonl_staging_resolver_contract import (  # noqa: E402
    build_contract_report as build_resolver_report,
)


VERIFICATION_VERSION = "jsonl-staging-diff-verification-v1"
G2_APPROVAL_REFERENCE = "https://github.com/phdiggit/emperor-evaluation/issues/292#issuecomment-4802128055"
BOUNDARIES = (
    "offline report only; no database connection",
    "does not read production credentials",
    "does not write formal target business tables",
    "does not mutate JSONL or archive data",
    "does not freeze JSONL writes",
    "does not switch PostgreSQL to the unique write source",
    "dry-run verification does not prove production success",
)


def build_verification_report(*, source_root: Path = ROOT) -> dict[str, Any]:
    manifest_report = build_candidate_report(source_root=source_root)
    mapping_package = build_package_report(source_root=source_root)
    staging_report = build_staging_report(source_root=source_root)
    resolver_report = build_resolver_report(source_root=source_root)

    manifest_files = {item["path"]: item for item in manifest_report["files"]}
    covered_files = list(manifest_report["data_survey"]["covered_files"])
    row_count_diffs = build_count_diffs(manifest_files, staging_report["rows_by_file"], count_key="row_count")
    id_count_diffs = build_id_count_diffs(manifest_files)

    report = {
        "mode": "staging-diff-verification",
        "verification_version": VERIFICATION_VERSION,
        "gate_status": "NO_NEW_GATE",
        "approval_required_from_user": False,
        "g1_manifest_approved": True,
        "g2_mapping_approved": True,
        "g2_approval_reference": G2_APPROVAL_REFERENCE,
        "next_user_gate": "G3_REQUIRED_BEFORE_PRODUCTION_BUSINESS_WRITE",
        "production_success_inferred": False,
        "g1_manifest_sha256": G1_MANIFEST_SHA256,
        "current_manifest_sha256": manifest_report["manifest_sha256"],
        "manifest_matches_g1": manifest_report["manifest_sha256"] == G1_MANIFEST_SHA256,
        "covered_files": covered_files,
        "covered_file_count": len(covered_files),
        "rows_total": manifest_report["data_survey"]["rows_total"],
        "row_count_diffs_by_file": row_count_diffs,
        "id_count_diffs_by_file": id_count_diffs,
        "file_hashes_by_file": build_file_hashes(manifest_files),
        "orphan_reference_report": {
            "reference_edges": manifest_report["reference_edges"],
            "orphan_references": manifest_report["blockers"]["orphan_references"],
            "total_orphan_references": len(manifest_report["blockers"]["orphan_references"]),
        },
        "staging_report_summary": {
            "rows_total": staging_report["rows_total"],
            "rows_mapped": staging_report["rows_mapped"],
            "rows_with_reference_risk": staging_report["rows_with_reference_risk"],
            "rows_with_unknown_fields": staging_report["rows_with_unknown_fields"],
            "rows_with_validation_errors": staging_report["rows_with_validation_errors"],
            "staging_only_files": staging_report["staging_only_files"],
            "target_table_candidates": staging_report["target_table_candidates"],
        },
        "reference_diff_report": {
            "resolver_inputs_by_file": resolver_report["resolver_inputs_by_file"],
            "unresolved_references_by_file": resolver_report["unresolved_references_by_file"],
            "manual_review_fields_by_file": resolver_report["manual_review_fields_by_file"],
            "blocked_relationship_writes": resolver_report["blocked_relationship_writes"],
            "staging_only_reference_domains": resolver_report["staging_only_reference_domains"],
        },
        "lossy_conversion_report": {
            "type_loss_risks": mapping_package["type_loss_risks"],
            "relationship_splits": mapping_package["relationship_splits"],
            "jsonb_retained_fields_by_file": mapping_package["jsonb_retained_fields_by_file"],
            "remaining_unknown_fields_by_file": mapping_package["remaining_unknown_fields_by_file"],
            "relaxed_vs_formal_schema_differences": mapping_package["relaxed_vs_formal_schema_differences"],
        },
        "diff_summary": build_diff_summary(
            manifest_report=manifest_report,
            row_count_diffs=row_count_diffs,
            id_count_diffs=id_count_diffs,
            mapping_package=mapping_package,
            staging_report=staging_report,
        ),
        "boundaries": list(BOUNDARIES),
    }
    return report


def build_count_diffs(
    manifest_files: Mapping[str, Mapping[str, Any]],
    staging_rows_by_file: Mapping[str, int],
    *,
    count_key: str,
) -> dict[str, dict[str, int]]:
    diffs: dict[str, dict[str, int]] = {}
    for path, manifest_entry in sorted(manifest_files.items()):
        manifest_count = int(manifest_entry[count_key])
        staging_count = int(staging_rows_by_file.get(path, 0))
        if manifest_count != staging_count:
            diffs[path] = {
                "manifest_count": manifest_count,
                "staging_count": staging_count,
                "delta": staging_count - manifest_count,
            }
    return diffs


def build_id_count_diffs(manifest_files: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    diffs: dict[str, dict[str, int]] = {}
    for path, manifest_entry in sorted(manifest_files.items()):
        row_count = int(manifest_entry["row_count"])
        id_count = int(manifest_entry["id_count"])
        if row_count != id_count:
            diffs[path] = {"row_count": row_count, "id_count": id_count, "delta": id_count - row_count}
    return diffs


def build_file_hashes(manifest_files: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        path: {
            "sha256": item["sha256"],
            "row_count": item["row_count"],
            "primary_key": item["primary_key"],
            "id_count": item["id_count"],
        }
        for path, item in sorted(manifest_files.items())
    }


def build_diff_summary(
    *,
    manifest_report: Mapping[str, Any],
    row_count_diffs: Mapping[str, Any],
    id_count_diffs: Mapping[str, Any],
    mapping_package: Mapping[str, Any],
    staging_report: Mapping[str, Any],
) -> list[str]:
    return [
        "manifest hash matches G1" if manifest_report["manifest_sha256"] == G1_MANIFEST_SHA256 else "manifest hash drift",
        "no row count diff" if not row_count_diffs else "row count diff",
        "no id count diff" if not id_count_diffs else "id count diff",
        "no orphan reference" if not manifest_report["blockers"]["orphan_references"] else "orphan reference",
        "no staging validation error"
        if staging_report["rows_with_validation_errors"] == 0
        else "staging validation error",
        "lossy conversion risks documented" if mapping_package["type_loss_risks"] else "no lossy conversion risk",
        "relationship splits documented" if mapping_package["relationship_splits"] else "no relationship split",
        "G3 still required before production business write",
    ]


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def report_as_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# JSONL Staging Dry-Run & Diff Verification",
        "",
        "```text",
        "NO_NEW_GATE",
        "verification_package: python scripts/platform/jsonl_staging_diff_verification.py --verification-report",
        f"next_user_gate: {report['next_user_gate']}",
        f"g1_manifest_sha256: {report['g1_manifest_sha256']}",
        f"manifest_matches_g1: {str(report['manifest_matches_g1']).lower()}",
        f"rows_total: {report['rows_total']}",
        "production_success_inferred: false",
        "approval_required_from_user: false",
        "```",
        "",
        "## Diff Summary",
        "",
    ]
    lines.extend(f"- {item}" for item in report["diff_summary"])
    lines.extend(["", "## File Hashes", ""])
    for path, item in report["file_hashes_by_file"].items():
        lines.append(
            f"- `{path}`: rows `{item['row_count']}`, id_count `{item['id_count']}`, "
            f"primary_key `{item['primary_key']}`, sha256 `{item['sha256']}`"
        )
    lines.extend(["", "## Staging Summary", ""])
    staging = report["staging_report_summary"]
    lines.extend(
        [
            f"- rows_mapped: `{staging['rows_mapped']}`",
            f"- rows_with_reference_risk: `{staging['rows_with_reference_risk']}`",
            f"- rows_with_unknown_fields: `{staging['rows_with_unknown_fields']}`",
            f"- rows_with_validation_errors: `{staging['rows_with_validation_errors']}`",
            "- staging_only_files:",
        ]
    )
    lines.extend(f"  - `{item}`" for item in staging["staging_only_files"])
    lines.extend(["", "## Remaining Manual Review", ""])
    remaining = report["lossy_conversion_report"]["remaining_unknown_fields_by_file"]
    if remaining:
        for path, fields in remaining.items():
            lines.append(f"- `{path}`: {', '.join(f'`{field}`' for field in fields)}")
    else:
        lines.append("- none")
    lines.extend(["", "## Boundary", ""])
    lines.extend(f"- {item}" for item in report["boundaries"])
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the Epic 1 1C staging dry-run diff verification report.")
    parser.add_argument("--verification-report", action="store_true", help="print the staging diff JSON report")
    parser.add_argument("--markdown-report", action="store_true", help="print the staging diff Markdown report")
    parser.add_argument("--source-root", type=Path, default=ROOT, help="repository root to scan")
    args = parser.parse_args(argv)

    report = build_verification_report(source_root=args.source_root)
    if args.markdown_report:
        sys.stdout.write(report_as_markdown(report))
    else:
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
