from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PACKAGE_VERSION = "i5b-rule-display-dictionary-contract-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
TECH_DEBT_ISSUE = 311
RERUN_REPORT_CONTRACT_PR = 319
RERUN_REPORT_CONTRACT_MERGE_COMMIT = "427e1be38d1ad612435e043d501a9850c11bd7a2"
SUPPORTED_MODES = ("contract-report", "dictionary-md")

SOURCE_MODULES = (
    "scripts/export/dimension_adapters/i5b_people_delegation/rules.py",
    "scripts/export/dimension_adapters/i5b_people_delegation/formal_algorithm.py",
    "scripts/export/dimension_adapters/i5b_people_delegation/adapter.py",
)
SNAPSHOT_SCHEMA_REQUIRED_FIELDS = (
    "snapshot_version",
    "scope",
    "rule_id",
    "dictionary_type",
    "locale",
    "status",
    "effective_from",
    "gate_source",
    "digest_sha256",
    "payload",
)
LOADER_CONTRACT_REQUIRED_CHECKS = (
    "load_immutable_snapshot_from_repo_path",
    "validate_snapshot_version",
    "validate_digest_before_use",
    "reject_runtime_dsn_dependency",
    "reject_unversioned_dictionary_item",
    "preserve_offline_deterministic_rerun",
)
VALIDATOR_CONTRACT_REQUIRED_CHECKS = (
    "rule_id_unique_within_scope",
    "locale_required_for_display_text",
    "gate_source_required_for_algorithm_mapping",
    "digest_matches_payload",
    "status_in_active_deprecated_draft",
    "effective_from_is_explicit",
)


HARD_CODED_INVENTORY: list[dict[str, Any]] = [
    {
        "source_path": SOURCE_MODULES[0],
        "symbol": "TRIAL_SCORE_MAP",
        "dictionary_type": "grade_dictionary",
        "target_snapshot": "i5b_grade_dictionary",
        "migration_action": "externalize_v3_2_trial_score_labels_and_ranges",
    },
    {
        "source_path": SOURCE_MODULES[0],
        "symbol": "HIGH_VALUE_ANCHOR_KEYWORDS",
        "dictionary_type": "rule_keyword_dictionary",
        "target_snapshot": "i5b_rule_keyword_dictionary",
        "migration_action": "externalize_high_value_anchor_keywords",
    },
    {
        "source_path": SOURCE_MODULES[0],
        "symbol": "STARTUP_ANCHOR_KEYWORDS",
        "dictionary_type": "rule_keyword_dictionary",
        "target_snapshot": "i5b_rule_keyword_dictionary",
        "migration_action": "externalize_startup_anchor_keywords",
    },
    {
        "source_path": SOURCE_MODULES[0],
        "symbol": "BOUNDARY_ANCHOR_KEYWORDS",
        "dictionary_type": "rule_keyword_dictionary",
        "target_snapshot": "i5b_rule_keyword_dictionary",
        "migration_action": "externalize_boundary_anchor_keywords",
    },
    {
        "source_path": SOURCE_MODULES[0],
        "symbol": "DIRECT_SAFETY_KEYWORDS",
        "dictionary_type": "rule_keyword_dictionary",
        "target_snapshot": "i5b_rule_keyword_dictionary",
        "migration_action": "externalize_direct_safety_keywords",
    },
    {
        "source_path": SOURCE_MODULES[0],
        "symbol": "POSITIVE_CORE_KEYWORDS",
        "dictionary_type": "rule_keyword_dictionary",
        "target_snapshot": "i5b_positive_core_dictionary",
        "migration_action": "externalize_three_core_positive_rule_keywords",
    },
    {
        "source_path": SOURCE_MODULES[0],
        "symbol": "RULE_SENSITIVE_POINTS",
        "dictionary_type": "rule_dictionary",
        "target_snapshot": "i5b_rule_dictionary",
        "migration_action": "externalize_rule_question_default_and_why_text",
    },
    {
        "source_path": SOURCE_MODULES[0],
        "symbol": "DIMENSION_RULES",
        "dictionary_type": "direction_grade_mapping",
        "target_snapshot": "i5b_dimension_inference_dictionary",
        "migration_action": "externalize_dimension_inference_keyword_mapping",
    },
    {
        "source_path": SOURCE_MODULES[1],
        "symbol": "FORMAL_GRADE_ENUM",
        "dictionary_type": "grade_dictionary",
        "target_snapshot": "i5b_grade_dictionary",
        "migration_action": "externalize_v3_2_grade_enum",
    },
    {
        "source_path": SOURCE_MODULES[1],
        "symbol": "FORMAL_GRADE_SPECS",
        "dictionary_type": "grade_dictionary",
        "target_snapshot": "i5b_grade_dictionary",
        "migration_action": "externalize_percent_and_score_band_specs",
    },
    {
        "source_path": SOURCE_MODULES[1],
        "symbol": "AUTO_DIRECTION_TO_FORMAL_GRADE",
        "dictionary_type": "direction_grade_mapping",
        "target_snapshot": "i5b_direction_grade_mapping",
        "migration_action": "externalize_auto_direction_to_formal_grade_mapping",
    },
    {
        "source_path": SOURCE_MODULES[1],
        "symbol": "FORMAL_GRADE_BAND_POSITION",
        "dictionary_type": "direction_grade_mapping",
        "target_snapshot": "i5b_direction_grade_mapping",
        "migration_action": "externalize_band_position_mapping",
    },
    {
        "source_path": SOURCE_MODULES[2],
        "symbol": "render_score_mapping_draft",
        "dictionary_type": "display_dictionary",
        "target_snapshot": "i5b_display_dictionary",
        "migration_action": "externalize_g8_g9_publication_explanatory_markdown",
    },
    {
        "source_path": SOURCE_MODULES[2],
        "symbol": "render_formal_person_section",
        "dictionary_type": "display_dictionary",
        "target_snapshot": "i5b_display_dictionary",
        "migration_action": "externalize_person_formal_score_display_labels",
    },
]


def _inventory_by_type() -> dict[str, list[str]]:
    by_type: dict[str, list[str]] = {}
    for item in HARD_CODED_INVENTORY:
        by_type.setdefault(str(item["dictionary_type"]), []).append(str(item["symbol"]))
    return by_type


def build_contract_report() -> dict[str, Any]:
    by_type = _inventory_by_type()
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "tech_debt_issue": TECH_DEBT_ISSUE,
        "rerun_report_contract_pr": RERUN_REPORT_CONTRACT_PR,
        "rerun_report_contract_merge_commit": RERUN_REPORT_CONTRACT_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_write_business_tables": True,
        "does_not_write_postgres_dictionary_tables": True,
        "does_not_modify_runtime_adapter": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "current_state": {
            "current_phase": "issue311_i5b_dictionary_externalization_contract_ready",
            "active_epic": EPIC_ISSUE,
            "active_tech_debt": TECH_DEBT_ISSUE,
            "issue311_dictionary_contract_ready": True,
            "hardcoded_inventory_count": len(HARD_CODED_INVENTORY),
            "dictionary_types_selected": sorted(by_type),
            "snapshot_schema_defined": True,
            "loader_contract_defined": True,
            "validator_contract_defined": True,
            "runtime_adapter_migrated": False,
            "postgres_dictionary_tables_created": False,
            "canonical_dictionary_write_performed": False,
            "ordinary_exports_require_live_dsn": False,
            "g10_destructive_cleanup_entered": False,
        },
        "hardcoded_inventory": list(HARD_CODED_INVENTORY),
        "inventory_by_type": by_type,
        "snapshot_schema": {
            "schema_name": "i5b_rule_display_dictionary_snapshot",
            "required_fields": list(SNAPSHOT_SCHEMA_REQUIRED_FIELDS),
            "dictionary_types": sorted(by_type),
            "locale_policy": "locale_required_for_display_dictionary_and_rule_text",
            "digest_policy": "sha256_over_stable_json_payload",
            "canonical_target": "postgres_or_versioned_snapshot_followup",
        },
        "loader_contract": {
            "required_checks": list(LOADER_CONTRACT_REQUIRED_CHECKS),
            "default_source": "immutable_repo_snapshot",
            "runtime_dsn_required": False,
            "offline_deterministic_rerun_required": True,
        },
        "validator_contract": {
            "required_checks": list(VALIDATOR_CONTRACT_REQUIRED_CHECKS),
            "fails_if_missing_digest": True,
            "fails_if_unversioned": True,
            "fails_if_locale_missing_for_display": True,
        },
        "blocked_outputs": [
            "postgres_dictionary_table_creation",
            "canonical_dictionary_write",
            "runtime_adapter_migration",
            "ordinary_export_runtime_dsn_dependency",
            "new_subitem_formal_scores",
            "new_subitem_formal_rankings",
            "stage_total_table",
            "final_total_table",
            "cross_subitem_leaderboard",
            "g10_destructive_cleanup",
        ],
        "next_required_work": "issue311_dictionary_snapshot_loader_validator_package",
    }


def render_dictionary_md() -> str:
    report = build_contract_report()
    lines = [
        "# I5B Rule And Display Dictionary Contract",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- tech_debt_issue: `#{report['tech_debt_issue']}`",
        f"- rerun_report_contract_pr: `#{report['rerun_report_contract_pr']}`",
        "- This package inventories hardcoded rule/display constants and defines snapshot, loader, and validator contracts only.",
        "",
        "## Inventory By Type",
        "",
    ]
    for dictionary_type, symbols in sorted(report["inventory_by_type"].items()):
        lines.append(f"- `{dictionary_type}`: {', '.join(f'`{symbol}`' for symbol in symbols)}")

    lines.extend(["", "## Snapshot Schema", ""])
    for field in report["snapshot_schema"]["required_fields"]:
        lines.append(f"- `{field}`")

    lines.extend(["", "## Blocked Outputs", ""])
    for item in report["blocked_outputs"]:
        lines.append(f"- `{item}`")

    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the I5B rule/display dictionary externalization contract.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--dictionary-md", action="store_true")
    args = parser.parse_args(argv)

    if args.dictionary_md:
        sys.stdout.write(render_dictionary_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
