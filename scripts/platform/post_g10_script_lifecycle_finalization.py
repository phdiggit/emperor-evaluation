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
from scripts.platform import g10_script_asset_risk_governance as governance  # noqa: E402
from scripts.validate import validate_script_lifecycle_registry as lifecycle_guard  # noqa: E402


PACKAGE_VERSION = "post-g10-script-lifecycle-finalization-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
POST_G10_S1_ISSUE = 346
PREREQUISITE_PR = 345
PREREQUISITE_MERGE_COMMIT = "16e8d84f281a1d4b9fef4896ae1f96517d75ba6f"
SUPPORTED_MODES = ("finalization-report", "finalization-md")
SUNSET_MILESTONE = "Post-G10-S1 script lifecycle finalization (#346)"
LAST_REQUIRED_BY = "Retired in place by Issue #346 Post-G10-S1 script lifecycle finalization"
DEFAULT_REPLACEMENT = "scripts/platform/platform_chain_checkpoint.py"

PREVIOUSLY_RETIRED_IN_PLACE_IDS = (
    "platform_anchors_schema_proposal",
    "platform_formal_ddl_live_rehearsal",
    "platform_formal_ddl_rehearsal",
    "platform_formal_schema_draft",
    "platform_schema_changing_formal_schema_update",
    "platform_schema_diff_draft_renderer",
)
FINALIZE_RETIRE_IN_PLACE_IDS = (
    "platform_formal_migration_proposal",
    "platform_guarded_executable_migration_pr",
    "platform_isolated_seed_dry_apply",
    "platform_isolated_seed_rollback_restore",
    "platform_migration_bundle_review_pack",
    "platform_migration_sql_draft_renderer",
    "platform_production_migration_admission",
    "platform_production_migration_dry_run_package",
    "platform_production_migration_freeze_checklist",
    "platform_production_migration_pr_scaffold",
    "platform_production_readiness_plan",
    "platform_production_schema_live_apply_entrypoint_guard",
    "platform_production_schema_live_apply_execution",
    "platform_production_schema_live_apply_execution_pr_scaffold",
    "platform_production_schema_live_apply_execution_preflight",
    "platform_production_seed_data_apply_execution",
    "platform_schema_change_approval_gate_package",
    "platform_schema_change_candidate_review_bundle",
    "platform_schema_change_explicit_approval_request_handoff",
    "platform_schema_change_pr_prep_pack",
    "platform_seed_artifact_db_preflight",
    "platform_seed_artifact_plan",
    "platform_seed_artifact_renderer",
    "platform_seed_artifact_validation_matrix",
)
SEED_REPLACEMENTS = {
    "platform_production_seed_data_apply_execution": (
        "scripts/platform/jsonl_postgres_mapping_approval_package.py"
    ),
    "platform_seed_artifact_db_preflight": "scripts/platform/canonical_manifest_gate.py",
    "platform_seed_artifact_plan": "scripts/platform/canonical_manifest_gate.py",
    "platform_seed_artifact_renderer": "scripts/platform/canonical_manifest_gate.py",
    "platform_seed_artifact_validation_matrix": "scripts/platform/canonical_manifest_gate.py",
}
FINALIZED_SCRIPT_IDS = PREVIOUSLY_RETIRED_IN_PLACE_IDS + FINALIZE_RETIRE_IN_PLACE_IDS
PACKAGE_CHANGED_PATHS = (
    "db/postgres/README.md",
    "docs/数据结构与生成库/史源数据平台迁移决策.md",
    "docs/文档与脚本登记/scripts_registry.json",
    "scripts/platform/g10_script_asset_risk_governance.py",
    "scripts/platform/platform_chain_checkpoint.py",
    "scripts/platform/post_g10_script_lifecycle_finalization.py",
    "tests/test_g10_script_asset_risk_governance.py",
    "tests/test_platform_chain_checkpoint.py",
    "tests/test_post_g10_script_lifecycle_finalization.py",
)
BLOCKED_OUTPUTS = (
    "new_score_publication",
    "new_ranking_publication",
    "stage_total_table",
    "final_total_table",
    "cross_subitem_leaderboard",
    "production_runtime_switch",
    "production_data_migration",
    "data_archive_export_path_mutation",
    "epic2_entry",
    "epic3_entry",
)


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


def _expected_replacement(item_id: str) -> str:
    return SEED_REPLACEMENTS.get(item_id, DEFAULT_REPLACEMENT)


def _expected_final_fields(item_id: str) -> dict[str, Any]:
    if item_id in PREVIOUSLY_RETIRED_IN_PLACE_IDS:
        return {
            "lifecycle_status": "retired",
            "replacement": DEFAULT_REPLACEMENT,
            "sunset_milestone": "G10-2b low-risk script lifecycle execution (#341)",
            "last_required_by": "Retired by Issue #341 G10-2b low-risk script lifecycle execution",
            "public_cli_stable": False,
        }
    return {
        "lifecycle_status": "retired",
        "replacement": _expected_replacement(item_id),
        "sunset_milestone": SUNSET_MILESTONE,
        "last_required_by": LAST_REQUIRED_BY,
        "public_cli_stable": False,
    }


def _replacement_exists(path: str) -> bool:
    return (ROOT / path).exists()


def _restore_instructions(module: Mapping[str, Any], item_id: str) -> list[str]:
    implementation = str(module["implementation"])
    registry_path = inventory_plan.SCRIPT_REGISTRY_PATH.relative_to(ROOT).as_posix()
    if item_id in PREVIOUSLY_RETIRED_IN_PLACE_IDS:
        return [
            (
                f"Keep `{item_id}` in the #341 retired-in-place state unless reopening Issue #341; "
                f"to inspect the prior row, run: git show {PREREQUISITE_MERGE_COMMIT}:{registry_path}"
            ),
            (
                "No script file was moved, deleted, or archived in #346; if a future change mutates "
                f"`{implementation}`, restore it with: git checkout {PREREQUISITE_MERGE_COMMIT} -- {implementation}"
            ),
        ]
    return [
        (
            f"Restore the registry row for `{item_id}` from the pre-#346 registry snapshot with: "
            f"git show {PREREQUISITE_MERGE_COMMIT}:{registry_path}"
        ),
        (
            "No script file was moved, deleted, or archived in #346; if a future change mutates "
            f"`{implementation}`, restore it with: git checkout {PREREQUISITE_MERGE_COMMIT} -- {implementation}"
        ),
    ]


def _decision_item(module: Mapping[str, Any], item_id: str) -> dict[str, Any]:
    current_fields = _field_subset(module)
    expected_fields = _expected_final_fields(item_id)
    return {
        "id": item_id,
        "implementation": str(module["implementation"]),
        "final_lifecycle_decision": "retire_in_place",
        "previous_state_source": f"git show {PREREQUISITE_MERGE_COMMIT}:docs/文档与脚本登记/scripts_registry.json",
        "current_field_values": current_fields,
        "expected_final_field_values": expected_fields,
        "final_fields_match_expected": current_fields == expected_fields,
        "actual_registry_lifecycle_finalization": item_id in FINALIZE_RETIRE_IN_PLACE_IDS,
        "file_path_action": "retained_in_place",
        "actual_moved_deleted_archived_paths": [],
        "replacement_exists": _replacement_exists(str(current_fields["replacement"])),
        "restore_instructions": _restore_instructions(module, item_id),
    }


def _report_only_test_consolidation() -> list[dict[str, Any]]:
    return [
        {
            "test_path": "tests/test_g10_script_asset_risk_governance.py",
            "previous_role": "G10-3 lifecycle count assertions before finalization",
            "issue_346_action": (
                "replaced transitional-count expectations with outcome assertions that all "
                "post-G10 non-active platform script assets are retired in place"
            ),
            "superseded_by": "tests/test_post_g10_script_lifecycle_finalization.py",
        },
        {
            "test_path": "tests/test_post_g10_script_lifecycle_finalization.py",
            "previous_role": "none",
            "issue_346_action": (
                "adds outcome-level checks for final registry fields, restore instructions, "
                "default/public route safety, duplicate governance, and no path mutation"
            ),
            "superseded_by": None,
        },
    ]


def build_finalization_report(
    registry: Mapping[str, Any] | None = None,
    default_route_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    registry = registry or _load_json(inventory_plan.SCRIPT_REGISTRY_PATH)
    default_route_sources = default_route_sources or governance._load_default_route_sources()
    modules_by_id = _platform_modules_by_id(registry)
    missing_ids = [item_id for item_id in FINALIZED_SCRIPT_IDS if item_id not in modules_by_id]
    manifest = [
        _decision_item(modules_by_id[item_id], item_id)
        for item_id in FINALIZED_SCRIPT_IDS
        if item_id in modules_by_id
    ]
    analysis = governance.analyze_scripts_registry(registry, default_route_sources)
    guard_report = lifecycle_guard.build_guard_report(registry, default_route_sources)
    path_actions = [path for item in manifest for path in item["actual_moved_deleted_archived_paths"]]
    unexpected_final_fields = [
        {
            "id": item["id"],
            "current_field_values": item["current_field_values"],
            "expected_final_field_values": item["expected_final_field_values"],
        }
        for item in manifest
        if not item["final_fields_match_expected"]
    ]
    ready = (
        not missing_ids
        and len(manifest) == len(FINALIZED_SCRIPT_IDS)
        and not unexpected_final_fields
        and len(path_actions) == 0
        and all(item["replacement_exists"] for item in manifest)
        and all(item["restore_instructions"] for item in manifest)
        and guard_report["current_state"]["registry_lifecycle_guard_ready"]
        and analysis["transitional_scripts_without_sunset_count"] == 0
        and analysis["retired_scripts_in_default_validate_or_public_cli"] == 0
        and not analysis["duplicate_capability_groups_without_reason"]
    )
    return {
        "mode": "finalization-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "post_g10_s1_issue": POST_G10_S1_ISSUE,
        "prerequisite_pr": PREREQUISITE_PR,
        "prerequisite_merge_commit": PREREQUISITE_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
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
        "does_not_publish_leaderboards": True,
        "does_not_enter_epic2_or_epic3": True,
        "does_not_move_delete_or_archive_files": True,
        "current_state": {
            "current_phase": "post_g10_s1_script_lifecycle_finalization_ready",
            "active_epic": EPIC_ISSUE,
            "post_g10_s1_script_lifecycle_finalization_ready": ready,
            "post_g10_script_lifecycle_finalization_package": PACKAGE_VERSION,
            "script_lifecycle_finalization_non_active_item_count": len(manifest),
            "script_lifecycle_finalization_updated_registry_entries": len(FINALIZE_RETIRE_IN_PLACE_IDS),
            "script_lifecycle_finalization_retired_in_place_count": len(manifest),
            "script_lifecycle_finalization_missing_ids": len(missing_ids),
            "script_lifecycle_finalization_unexpected_final_fields": len(unexpected_final_fields),
            "script_lifecycle_finalization_restore_instructions_complete": all(
                item["restore_instructions"] for item in manifest
            ),
            "script_lifecycle_finalization_actual_moved_deleted_archived_path_count": len(path_actions),
            "script_lifecycle_finalization_replacement_paths_exist": all(
                item["replacement_exists"] for item in manifest
            ),
            "transitional_scripts_without_sunset": analysis["transitional_scripts_without_sunset_count"],
            "retired_scripts_in_default_validate_or_public_cli": analysis[
                "retired_scripts_in_default_validate_or_public_cli"
            ],
            "duplicate_capability_groups_reviewed": analysis["duplicate_capability_group_count"],
            "duplicate_capability_groups_without_reason": len(
                analysis["duplicate_capability_groups_without_reason"]
            ),
            "registry_lifecycle_guard_ready": guard_report["current_state"][
                "registry_lifecycle_guard_ready"
            ],
            "report_only_tests_replaced": True,
            "remaining_script_governance_debt": [],
            "script_lifecycle_finalization_remaining_debt_count": 0,
            "script_governance_report_only_fallback_allowed": False,
            "g10_destructive_cleanup_started": False,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "changed_paths_manifest": list(PACKAGE_CHANGED_PATHS),
        "missing_script_ids": missing_ids,
        "unexpected_final_fields": unexpected_final_fields,
        "script_lifecycle_finalization_manifest": manifest,
        "script_lifecycle_finalization_manifest_count": len(manifest),
        "actual_moved_deleted_archived_paths": path_actions,
        "scripts_registry_analysis": {
            "platform_lifecycle_status_counts": analysis["platform_lifecycle_status_counts"],
            "transitional_scripts_without_sunset": analysis["transitional_scripts_without_sunset"],
            "retired_public_cli_modules": analysis["retired_public_cli_modules"],
            "default_validate_retired_script_references": analysis[
                "default_validate_retired_script_references"
            ],
            "retired_scripts_in_default_validate_or_public_cli": analysis[
                "retired_scripts_in_default_validate_or_public_cli"
            ],
            "duplicate_capability_review": analysis["duplicate_capability_review"],
            "duplicate_capability_groups_without_reason": analysis[
                "duplicate_capability_groups_without_reason"
            ],
        },
        "report_only_test_consolidation": _report_only_test_consolidation(),
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "next_required_work": "select_one_non_script_followup_gate_or_close_issue_346_after_merge",
    }


def render_finalization_md() -> str:
    report = build_finalization_report()
    state = report["current_state"]
    lines = [
        "# Post-G10 Script Lifecycle Finalization",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- post_g10_s1_issue: `#{report['post_g10_s1_issue']}`",
        f"- prerequisite_pr: `#{report['prerequisite_pr']}`",
        f"- current_phase: `{state['current_phase']}`",
        f"- post_g10_s1_script_lifecycle_finalization_ready: `{str(state['post_g10_s1_script_lifecycle_finalization_ready']).lower()}`",
        f"- non_active_item_count: `{state['script_lifecycle_finalization_non_active_item_count']}`",
        f"- updated_registry_entries: `{state['script_lifecycle_finalization_updated_registry_entries']}`",
        f"- transitional_scripts_without_sunset: `{state['transitional_scripts_without_sunset']}`",
        f"- retired_scripts_in_default_validate_or_public_cli: `{state['retired_scripts_in_default_validate_or_public_cli']}`",
        f"- duplicate_capability_groups_without_reason: `{state['duplicate_capability_groups_without_reason']}`",
        f"- remaining_script_governance_debt_count: `{state['script_lifecycle_finalization_remaining_debt_count']}`",
        f"- script_governance_report_only_fallback_allowed: `{str(state['script_governance_report_only_fallback_allowed']).lower()}`",
        "",
        "## Lifecycle Finalization Manifest",
        "",
    ]
    for item in report["script_lifecycle_finalization_manifest"]:
        lines.append(
            f"- `{item['id']}`: decision=`{item['final_lifecycle_decision']}`, "
            f"path_action=`{item['file_path_action']}`, replacement=`{item['current_field_values']['replacement']}`"
        )

    lines.extend(["", "## Report-Only Test Consolidation", ""])
    for item in report["report_only_test_consolidation"]:
        lines.append(f"- `{item['test_path']}`: `{item['issue_346_action']}`")

    lines.extend(["", "## Blocked Outputs", ""])
    for item in report["blocked_outputs"]:
        lines.append(f"- `{item}`")

    lines.extend(["", "## Changed Paths Manifest", ""])
    for path in report["changed_paths_manifest"]:
        lines.append(f"- `{path}`")

    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the post-G10 script lifecycle finalization report.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--finalization-report", action="store_true")
    mode.add_argument("--finalization-md", action="store_true")
    args = parser.parse_args(argv)

    if args.finalization_md:
        sys.stdout.write(render_finalization_md())
        return 0

    sys.stdout.write(report_as_json(build_finalization_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
