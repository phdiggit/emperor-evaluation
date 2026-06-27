from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_cleanup_inventory_plan as inventory_plan  # noqa: E402
from scripts.platform import g10_historical_asset_retirement as retirement  # noqa: E402
from scripts.platform import g10_script_asset_risk_governance as governance  # noqa: E402


PACKAGE_VERSION = "g10-low-risk-script-lifecycle-execution-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
PLAN_ISSUE = 331
SCRIPT_GOVERNANCE_ISSUE = 334
LIFECYCLE_EXECUTION_ISSUE = 341
NEXT_GUARD_ISSUE = 342
FINAL_HANDOFF_ISSUE = 335
PREREQUISITE_PR = 339
PREREQUISITE_MERGE_COMMIT = "83c2438e31842f08ed19a1a1b00e965ce1fa9451"
SUPPORTED_MODES = ("lifecycle-report", "lifecycle-md")
REPLACEMENT = "scripts/platform/platform_chain_checkpoint.py"
SUNSET_MILESTONE = "G10-2b low-risk script lifecycle execution (#341)"
LAST_REQUIRED_BY = "Retired by Issue #341 G10-2b low-risk script lifecycle execution"
LOW_RISK_LIFECYCLE_EXECUTION_IDS = (
    "platform_anchors_schema_proposal",
    "platform_formal_ddl_live_rehearsal",
    "platform_formal_ddl_rehearsal",
    "platform_formal_schema_draft",
    "platform_schema_changing_formal_schema_update",
    "platform_schema_diff_draft_renderer",
)
PACKAGE_CHANGED_PATHS = (
    "db/postgres/README.md",
    "docs/数据结构与生成库/史源数据平台迁移决策.md",
    "docs/文档与脚本登记/scripts_registry.json",
    "scripts/platform/g10_low_risk_script_lifecycle_execution.py",
    "scripts/platform/g10_script_asset_risk_governance.py",
    "scripts/platform/platform_chain_checkpoint.py",
    "tests/test_g10_low_risk_script_lifecycle_execution.py",
    "tests/test_g10_script_asset_risk_governance.py",
    "tests/test_platform_chain_checkpoint.py",
)
PROTECTED_HIGH_RISK_ROOTS = (
    "data/",
    "archive/data/",
    "exports/",
)
BLOCKED_OUTPUTS = (
    "data_archive_export_path_mutation",
    "source_of_truth_removal",
    "production_runtime_switch",
    "production_data_migration",
    "new_score_publication",
    "new_ranking_publication",
    "stage_total_table",
    "final_total_table",
    "cross_subitem_leaderboard",
)
EXPECTED_PREVIOUS_FIELDS = {
    item_id: {
        "lifecycle_status": "audit_only",
        "replacement": REPLACEMENT,
        "sunset_milestone": None,
        "last_required_by": "Historical ADR audit only",
        "public_cli_stable": False,
    }
    for item_id in LOW_RISK_LIFECYCLE_EXECUTION_IDS
}
EXPECTED_CURRENT_FIELDS = {
    item_id: {
        "lifecycle_status": "retired",
        "replacement": REPLACEMENT,
        "sunset_milestone": SUNSET_MILESTONE,
        "last_required_by": LAST_REQUIRED_BY,
        "public_cli_stable": False,
    }
    for item_id in LOW_RISK_LIFECYCLE_EXECUTION_IDS
}


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _platform_modules_by_id(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(module["id"]): module
        for module in registry.get("platform_modules", [])
        if isinstance(module, Mapping) and "id" in module
    }


def _field_subset(module: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "lifecycle_status": module.get("lifecycle_status"),
        "replacement": module.get("replacement"),
        "sunset_milestone": module.get("sunset_milestone"),
        "last_required_by": module.get("last_required_by"),
        "public_cli_stable": module.get("public_cli_stable"),
    }


def _path_exists(path: str | None) -> bool:
    if not path or any(token in path for token in (" plus ", "*", ":")):
        return True
    return (ROOT / path).exists()


def _restore_instructions(module: Mapping[str, Any]) -> list[str]:
    implementation = str(module["implementation"])
    return [
        (
            "Restore the registry row in docs/文档与脚本登记/scripts_registry.json "
            f"for id `{module['id']}` to the previous_field_values recorded in this manifest."
        ),
        (
            "No script file was moved, deleted, or archived in #341; if a future change mutates "
            f"`{implementation}`, restore the file from the pre-#341 base with: "
            f"git checkout {PREREQUISITE_MERGE_COMMIT} -- {implementation}"
        ),
    ]


def _execution_item(module: Mapping[str, Any], default_route_violations: Sequence[str]) -> dict[str, Any]:
    item_id = str(module["id"])
    current_values = _field_subset(module)
    previous_values = dict(EXPECTED_PREVIOUS_FIELDS[item_id])
    expected_current = dict(EXPECTED_CURRENT_FIELDS[item_id])
    implementation = str(module["implementation"])
    return {
        "id": item_id,
        "implementation": implementation,
        "risk_class": module["risk_class"],
        "previous_field_values": previous_values,
        "current_field_values": current_values,
        "expected_current_field_values": expected_current,
        "actual_lifecycle_update": previous_values["lifecycle_status"] != current_values["lifecycle_status"],
        "actual_registry_field_update_count": sum(
            1 for field, value in current_values.items() if previous_values.get(field) != value
        ),
        "file_path_action": "retained_in_place",
        "actual_moved_deleted_archived_paths": [],
        "default_or_public_route_violation": implementation in default_route_violations
        or module.get("public_cli_stable") is True,
        "restore_instructions": _restore_instructions(module),
    }


def _dangling_registry_refs(items: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    dangling: list[dict[str, str]] = []
    for item in items:
        implementation = str(item["implementation"])
        replacement = item.get("replacement")
        if not _path_exists(implementation):
            dangling.append({"id": str(item["id"]), "field": "implementation", "path": implementation})
        if not _path_exists(str(replacement) if replacement is not None else None):
            dangling.append({"id": str(item["id"]), "field": "replacement", "path": str(replacement)})
    return dangling


def _test_consolidation_manifest() -> list[dict[str, Any]]:
    return [
        {
            "test_path": "tests/test_g10_script_asset_risk_governance.py",
            "previous_role": "report-only Script Delta assertions for Issue #334",
            "issue_341_action": (
                "downgraded the zero-retired-platform-module expectation to an outcome assertion "
                "that retired scripts remain outside default validate and public CLI routes"
            ),
            "superseded_by": "tests/test_g10_low_risk_script_lifecycle_execution.py",
        },
        {
            "test_path": "tests/test_g10_low_risk_script_lifecycle_execution.py",
            "previous_role": "none",
            "issue_341_action": (
                "adds outcome-level checks for registry field updates, restore instructions, "
                "route safety, and high-risk root boundaries"
            ),
            "superseded_by": None,
        },
    ]


def build_lifecycle_report(
    registry: Mapping[str, Any] | None = None,
    default_route_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    registry = registry or _load_json(inventory_plan.SCRIPT_REGISTRY_PATH)
    default_route_sources = default_route_sources or governance._load_default_route_sources()
    analysis = governance.analyze_scripts_registry(registry, default_route_sources)
    modules_by_id = _platform_modules_by_id(registry)
    missing_ids = [item_id for item_id in LOW_RISK_LIFECYCLE_EXECUTION_IDS if item_id not in modules_by_id]
    selected = [modules_by_id[item_id] for item_id in LOW_RISK_LIFECYCLE_EXECUTION_IDS if item_id in modules_by_id]
    default_route_violation_paths = {
        str(item["retired_path"])
        for item in analysis["default_validate_retired_script_references"]
    }
    manifest = [
        _execution_item(module, sorted(default_route_violation_paths))
        for module in selected
    ]
    unexpected_current_field_values = [
        {
            "id": item["id"],
            "current_field_values": item["current_field_values"],
            "expected_current_field_values": item["expected_current_field_values"],
        }
        for item in manifest
        if item["current_field_values"] != item["expected_current_field_values"]
    ]
    dangling_refs = _dangling_registry_refs(selected)
    path_actions = [path for item in manifest for path in item["actual_moved_deleted_archived_paths"]]
    ready = (
        not missing_ids
        and not unexpected_current_field_values
        and not dangling_refs
        and len(manifest) >= 1
        and len(path_actions) == 0
        and analysis["transitional_scripts_without_sunset_count"] == 0
        and analysis["retired_scripts_in_default_validate_or_public_cli"] == 0
    )

    return {
        "mode": "lifecycle-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "plan_issue": PLAN_ISSUE,
        "script_governance_issue": SCRIPT_GOVERNANCE_ISSUE,
        "lifecycle_execution_issue": LIFECYCLE_EXECUTION_ISSUE,
        "next_guard_issue": NEXT_GUARD_ISSUE,
        "final_handoff_issue": FINAL_HANDOFF_ISSUE,
        "prerequisite_pr": PREREQUISITE_PR,
        "prerequisite_merge_commit": PREREQUISITE_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "source_inputs": {
            "issue_331_inventory_package": inventory_plan.PACKAGE_VERSION,
            "issue_331_inventory_candidate_count": len(inventory_plan.CLEANUP_CANDIDATES),
            "issue_333_retirement_manifest_package": retirement.PACKAGE_VERSION,
            "issue_333_retirement_manifest_note": (
                "Used as prerequisite state only; #341 does not scan or mutate data/archive/export roots."
            ),
            "issue_334_script_risk_report_package": governance.PACKAGE_VERSION,
            "issue_334_duplicate_capability_groups_reviewed": analysis["duplicate_capability_group_count"],
        },
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_read_batch_payloads": True,
        "does_not_read_generated_exports": True,
        "does_not_touch_data_archive_export_roots": True,
        "does_not_write_business_tables": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "does_not_move_delete_or_archive_files": True,
        "current_state": {
            "current_phase": "g10_low_risk_script_lifecycle_execution_ready",
            "active_epic": EPIC_ISSUE,
            "g10_2b_low_risk_script_lifecycle_execution_ready": ready,
            "g10_low_risk_script_lifecycle_execution_package": PACKAGE_VERSION,
            "g10_low_risk_lifecycle_update_count": len(
                [item for item in manifest if item["actual_lifecycle_update"]]
            ),
            "g10_low_risk_updated_registry_entries": len(manifest),
            "actual_moved_deleted_archived_path_count": len(path_actions),
            "transitional_scripts_without_sunset": analysis["transitional_scripts_without_sunset_count"],
            "retired_scripts_in_default_validate_or_public_cli": analysis[
                "retired_scripts_in_default_validate_or_public_cli"
            ],
            "registry_dangling_reference_count": len(dangling_refs),
            "restore_instructions_complete": all(item["restore_instructions"] for item in manifest),
            "test_consolidation_recorded": True,
            "g10_destructive_cleanup_started": False,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
        },
        "changed_paths_manifest": list(PACKAGE_CHANGED_PATHS),
        "missing_lifecycle_execution_ids": missing_ids,
        "unexpected_current_field_values": unexpected_current_field_values,
        "registry_dangling_references": dangling_refs,
        "lifecycle_execution_manifest": manifest,
        "lifecycle_execution_manifest_count": len(manifest),
        "actual_moved_deleted_archived_paths": path_actions,
        "protected_high_risk_roots": list(PROTECTED_HIGH_RISK_ROOTS),
        "test_consolidation_manifest": _test_consolidation_manifest(),
        "scripts_registry_analysis": {
            "platform_lifecycle_status_counts": analysis["platform_lifecycle_status_counts"],
            "transitional_scripts_without_sunset": analysis["transitional_scripts_without_sunset"],
            "retired_platform_modules": analysis["retired_platform_modules"],
            "retired_scripts_in_default_validate_or_public_cli": analysis[
                "retired_scripts_in_default_validate_or_public_cli"
            ],
            "duplicate_capability_groups_without_reason": analysis[
                "duplicate_capability_groups_without_reason"
            ],
        },
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "next_required_work": "issue342_registry_lifecycle_guard_then_issue335_completion_handoff",
    }


def render_lifecycle_md() -> str:
    report = build_lifecycle_report()
    state = report["current_state"]
    lines = [
        "# G10 Low-risk Script Lifecycle Execution",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- lifecycle_execution_issue: `#{report['lifecycle_execution_issue']}`",
        f"- next_guard_issue: `#{report['next_guard_issue']}`",
        f"- final_handoff_issue: `#{report['final_handoff_issue']}`",
        f"- prerequisite_pr: `#{report['prerequisite_pr']}`",
        f"- current_phase: `{state['current_phase']}`",
        f"- g10_low_risk_lifecycle_update_count: `{state['g10_low_risk_lifecycle_update_count']}`",
        f"- actual_moved_deleted_archived_path_count: `{state['actual_moved_deleted_archived_path_count']}`",
        f"- retired_scripts_in_default_validate_or_public_cli: `{state['retired_scripts_in_default_validate_or_public_cli']}`",
        f"- registry_dangling_reference_count: `{state['registry_dangling_reference_count']}`",
        f"- next_required_work: `{report['next_required_work']}`",
        "",
        "## Lifecycle Execution Manifest",
        "",
    ]
    for item in report["lifecycle_execution_manifest"]:
        lines.append(
            f"- `{item['implementation']}`: `{item['previous_field_values']['lifecycle_status']}` -> "
            f"`{item['current_field_values']['lifecycle_status']}`, "
            f"replacement=`{item['current_field_values']['replacement']}`"
        )

    lines.extend(["", "## Restore Instructions", ""])
    for item in report["lifecycle_execution_manifest"]:
        lines.append(f"- `{item['id']}`:")
        for instruction in item["restore_instructions"]:
            lines.append(f"  - {instruction}")

    lines.extend(["", "## Test Consolidation", ""])
    for item in report["test_consolidation_manifest"]:
        lines.append(f"- `{item['test_path']}`: {item['issue_341_action']}")

    lines.extend(["", "## Changed Paths Manifest", ""])
    for path in report["changed_paths_manifest"]:
        lines.append(f"- `{path}`")

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

    parser = argparse.ArgumentParser(description="Build the G10-2b low-risk lifecycle execution manifest.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--lifecycle-report", action="store_true")
    mode.add_argument("--lifecycle-md", action="store_true")
    args = parser.parse_args(argv)

    if args.lifecycle_md:
        sys.stdout.write(render_lifecycle_md())
        return 0

    sys.stdout.write(report_as_json(build_lifecycle_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
