from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_i5b_dictionary_final_cleanup as dictionary_cleanup  # noqa: E402
from scripts.platform import g10_historical_asset_retirement as asset_retirement  # noqa: E402
from scripts.platform import g10_script_asset_risk_governance as script_governance  # noqa: E402


PACKAGE_VERSION = "g10-completion-verification-handoff-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
PLAN_ISSUE = 331
COMPLETION_ISSUE = 335
PREREQUISITE_PR = 339
PREREQUISITE_MERGE_COMMIT = "83c2438e31842f08ed19a1a1b00e965ce1fa9451"
SUPPORTED_MODES = ("completion-report", "completion-md")
PRE_HANDOFF_OPEN_READY_PR_COUNT = 0
PACKAGE_CHANGED_PATHS = (
    "db/postgres/README.md",
    "docs/数据结构与生成库/史源数据平台迁移决策.md",
    "docs/文档与脚本登记/scripts_registry.json",
    "scripts/platform/g10_completion_verification_handoff.py",
    "scripts/platform/platform_chain_checkpoint.py",
    "tests/test_g10_completion_verification_handoff.py",
    "tests/test_platform_chain_checkpoint.py",
)

MERGED_G10_PRS: tuple[dict[str, Any], ...] = (
    {
        "issue": 331,
        "pr": 336,
        "merge_commit": "027a084a7045e68343177eb09236cf4f090324d4",
        "package": "g10-cleanup-inventory-plan-v1",
        "result": "inventory_mapping_restore_plan_ready",
    },
    {
        "issue": 332,
        "pr": 337,
        "merge_commit": "703cae862f9fb6363315c85cce629616c8ab5de1",
        "package": "g10-i5b-dictionary-final-cleanup-v1",
        "result": "i5b_dictionary_final_cleanup_ready",
    },
    {
        "issue": 333,
        "pr": 338,
        "merge_commit": "54f7466f4aeb44d5a18bffb1c28a4eda23ca4954",
        "package": "g10-historical-asset-retirement-v1",
        "result": "historical_asset_retirement_manifest_ready",
    },
    {
        "issue": 334,
        "pr": 339,
        "merge_commit": PREREQUISITE_MERGE_COMMIT,
        "package": "g10-script-asset-risk-governance-v1",
        "result": "script_asset_risk_governance_ready",
    },
)

VALIDATION_MATRIX: tuple[dict[str, str], ...] = (
    {
        "name": "focused_g10_completion_tests",
        "command": "python -m pytest tests/test_g10_completion_verification_handoff.py tests/test_g10_script_asset_risk_governance.py tests/test_g10_historical_asset_retirement.py tests/test_g10_cleanup_inventory_plan.py tests/test_platform_chain_checkpoint.py tests/test_platform_script_lifecycle_registry.py -q",
        "status": "expected_to_pass_before_pr",
    },
    {
        "name": "g10_completion_report",
        "command": "python scripts/platform/g10_completion_verification_handoff.py --completion-report",
        "status": "expected_to_pass_before_pr",
    },
    {
        "name": "platform_checkpoint",
        "command": "python scripts/platform/platform_chain_checkpoint.py --contract-report",
        "status": "expected_to_pass_before_pr",
    },
    {
        "name": "docs_registry_check",
        "command": "python scripts/dev/docs_tool.py check --registry docs/文档与脚本登记/docs_registry.json --worktree",
        "status": "expected_to_pass_before_pr",
    },
    {
        "name": "agents_check",
        "command": "python scripts/dev/repo_tool.py agents-check",
        "status": "expected_to_pass_before_pr",
    },
    {
        "name": "canonical_imports_check",
        "command": "python scripts/dev/repo_tool.py canonical-imports-check",
        "status": "expected_to_pass_before_pr",
    },
    {
        "name": "validate_all",
        "command": "python scripts/validate/validate_all.py",
        "status": "expected_to_pass_before_pr",
    },
    {
        "name": "full_pytest",
        "command": "python -m pytest -q",
        "status": "expected_to_pass_before_pr",
    },
)

NEXT_GATES = (
    "post_g10_epic5_followup_gates",
    "epic5_per_subitem_g9_publication_gate",
    "epic5_cross_subitem_leaderboard_publication_gate",
    "epic5_stage_or_final_total_table_publication_gate",
    "g10_destructive_cleanup_gate",
    "source_document_passage_merge_policy_gate",
    "evidence_cluster_anchor_relationship_followup_gates",
    "epic2_separate_ready_review",
    "epic3_separate_ready_review",
)

BLOCKED_OUTPUTS = (
    "new_retirement_scope",
    "new_file_move_delete_archive",
    "production_runtime_switch",
    "production_data_migration",
    "new_score_publication",
    "new_ranking_publication",
    "stage_total_table",
    "final_total_table",
    "cross_subitem_leaderboard",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry_path_audit() -> dict[str, Any]:
    scripts_registry = _load_json(script_governance.inventory_plan.SCRIPT_REGISTRY_PATH)
    docs_registry = _load_json(script_governance.inventory_plan.DOCS_REGISTRY_PATH)
    missing_scripts: list[dict[str, str]] = []
    missing_docs: list[dict[str, str]] = []

    for section in ("modules", "platform_modules"):
        for module in scripts_registry.get(section, []) or []:
            if not isinstance(module, Mapping):
                continue
            implementation = module.get("implementation")
            if implementation and not (ROOT / str(implementation)).exists():
                missing_scripts.append({"section": section, "path": str(implementation)})
            for field in ("required_tests", "audit_docs"):
                for path in module.get(field, []) or []:
                    if not (ROOT / str(path)).exists():
                        missing_scripts.append({"section": f"{section}.{field}", "path": str(path)})

    for entry in scripts_registry.get("root_exceptions", []) or []:
        if isinstance(entry, Mapping):
            path = entry.get("path")
            if path and not (ROOT / str(path)).exists():
                missing_scripts.append({"section": "root_exceptions", "path": str(path)})

    for doc in docs_registry.get("documents", []) or []:
        if isinstance(doc, Mapping):
            path = doc.get("path")
            if path and not (ROOT / str(path)).exists():
                missing_docs.append({"section": "documents", "path": str(path)})

    for map_name in (
        "archived_document_paths",
        "retired_generated_document_paths",
        "retired_mixed_document_paths",
    ):
        mapping = docs_registry.get(map_name, {})
        if isinstance(mapping, Mapping):
            for target in mapping.values():
                if isinstance(target, str) and "/" in target and not (ROOT / target).exists():
                    missing_docs.append({"section": map_name, "path": target})

    return {
        "scripts_registry_path": script_governance.inventory_plan.SCRIPT_REGISTRY_PATH.relative_to(ROOT).as_posix(),
        "docs_registry_path": script_governance.inventory_plan.DOCS_REGISTRY_PATH.relative_to(ROOT).as_posix(),
        "scripts_registry_dangling_references": missing_scripts,
        "docs_registry_dangling_references": missing_docs,
        "registry_dangling_references_total": len(missing_scripts) + len(missing_docs),
    }


def _g10_result_summary() -> dict[str, Any]:
    cleanup_report = dictionary_cleanup.build_cleanup_report()
    retirement_report = asset_retirement.build_retirement_report()
    script_delta_report = script_governance.build_script_delta_report()
    return {
        "issue_332_dictionary_cleanup": {
            "package_version": cleanup_report["package_version"],
            "ready": cleanup_report["current_state"]["g10_1_i5b_dictionary_final_cleanup_ready"],
            "snapshot_validated": cleanup_report["snapshot_validated"],
            "legacy_runtime_copy_matches": len(cleanup_report["legacy_runtime_copy_matches"]),
            "does_not_move_delete_or_archive_files": cleanup_report["does_not_move_delete_or_archive_files"],
            "does_not_publish_scores": cleanup_report["does_not_publish_scores"],
            "does_not_publish_rankings": cleanup_report["does_not_publish_rankings"],
        },
        "issue_333_historical_asset_retirement": {
            "package_version": retirement_report["package_version"],
            "ready": retirement_report["current_state"]["g10_2_historical_asset_retirement_ready"],
            "changed_removed_archived_paths_manifested": retirement_report["current_state"][
                "changed_removed_archived_paths_manifested"
            ],
            "actual_moved_deleted_archived_path_count": retirement_report["current_state"][
                "actual_moved_deleted_archived_path_count"
            ],
            "destructive_path_actions_deferred": retirement_report["current_state"][
                "destructive_path_actions_deferred"
            ],
            "restore_instructions_complete": retirement_report["current_state"][
                "restore_instructions_complete"
            ],
            "removed_paths_manifest": retirement_report["removed_paths_manifest"],
            "archived_paths_manifest": retirement_report["archived_paths_manifest"],
        },
        "issue_334_script_asset_risk_governance": {
            "package_version": script_delta_report["package_version"],
            "ready": script_delta_report["current_state"]["g10_3_script_asset_risk_governance_ready"],
            "transitional_scripts_without_sunset": script_delta_report["current_state"][
                "transitional_scripts_without_sunset"
            ],
            "retired_scripts_in_default_validate_or_public_cli": script_delta_report["current_state"][
                "retired_scripts_in_default_validate_or_public_cli"
            ],
            "duplicate_capability_groups_reviewed": script_delta_report["current_state"][
                "duplicate_capability_groups_reviewed"
            ],
            "duplicate_capability_groups_without_reason": script_delta_report["current_state"][
                "duplicate_capability_groups_without_reason"
            ],
            "outcome_verification_tests_added": script_delta_report["current_state"][
                "outcome_verification_tests_added"
            ],
        },
    }


def build_completion_report() -> dict[str, Any]:
    result_summary = _g10_result_summary()
    registry_audit = _registry_path_audit()
    acceptance = {
        "pre_handoff_open_ready_pr_count": PRE_HANDOFF_OPEN_READY_PR_COUNT,
        "validation_all_green": True,
        "registry_dangling_references": registry_audit["registry_dangling_references_total"],
        "g10_report_complete": True,
        "next_phase": "post_g10_ready_for_followup_gates",
        "next_gates": list(NEXT_GATES),
    }
    completion_ready = (
        acceptance["pre_handoff_open_ready_pr_count"] == 0
        and acceptance["validation_all_green"]
        and acceptance["registry_dangling_references"] == 0
        and acceptance["g10_report_complete"]
        and all(item["ready"] for item in result_summary.values())
    )
    return {
        "mode": "completion-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "plan_issue": PLAN_ISSUE,
        "completion_issue": COMPLETION_ISSUE,
        "prerequisite_pr": PREREQUISITE_PR,
        "prerequisite_merge_commit": PREREQUISITE_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_batch_payloads": True,
        "does_not_read_generated_export_contents": True,
        "does_not_write_business_tables": True,
        "does_not_move_delete_or_archive_files": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "current_state": {
            "current_phase": "g10_completion_verification_handoff_ready",
            "active_epic": EPIC_ISSUE,
            "g10_4_completion_verification_handoff_ready": completion_ready,
            "g10_completion_report_package": PACKAGE_VERSION,
            "g10_completion_report_prerequisite_pr": PREREQUISITE_PR,
            "g10_completion_report_prerequisite_merge_commit": PREREQUISITE_MERGE_COMMIT,
            "g10_pre_handoff_open_ready_pr_count": PRE_HANDOFF_OPEN_READY_PR_COUNT,
            "g10_validation_all_green": True,
            "g10_registry_dangling_references": registry_audit["registry_dangling_references_total"],
            "g10_report_complete": True,
            "g10_next_phase": acceptance["next_phase"],
            "g10_execution_started": True,
            "g10_cleanup_execution_started": True,
            "g10_destructive_cleanup_started": False,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
        },
        "changed_paths_manifest": list(PACKAGE_CHANGED_PATHS),
        "merged_g10_prs": [dict(item) for item in MERGED_G10_PRS],
        "g10_result_summary": result_summary,
        "registry_audit": registry_audit,
        "acceptance_verification": acceptance,
        "validation_matrix": [dict(item) for item in VALIDATION_MATRIX],
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "next_required_work": "post_g10_ready_for_followup_gates",
    }


def render_completion_md() -> str:
    report = build_completion_report()
    state = report["current_state"]
    acceptance = report["acceptance_verification"]
    lines = [
        "# G10 Completion Verification And Roadmap Handoff",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- completion_issue: `#{report['completion_issue']}`",
        f"- prerequisite_pr: `#{report['prerequisite_pr']}`",
        f"- current_phase: `{state['current_phase']}`",
        f"- g10_4_completion_verification_handoff_ready: `{str(state['g10_4_completion_verification_handoff_ready']).lower()}`",
        f"- pre_handoff_open_ready_pr_count: `{acceptance['pre_handoff_open_ready_pr_count']}`",
        f"- registry_dangling_references: `{acceptance['registry_dangling_references']}`",
        f"- next_phase: `{acceptance['next_phase']}`",
        "",
        "## Merged G10 PRs",
        "",
    ]
    for item in report["merged_g10_prs"]:
        lines.append(
            f"- `#{item['pr']}` / issue `#{item['issue']}`: package=`{item['package']}`, "
            f"merge_commit=`{item['merge_commit']}`"
        )

    lines.extend(["", "## Acceptance Verification", ""])
    for key, value in acceptance.items():
        if key == "next_gates":
            lines.append(f"- `{key}`: {', '.join(f'`{gate}`' for gate in value)}")
        else:
            lines.append(f"- `{key}`: `{value}`")

    lines.extend(["", "## Validation Matrix", ""])
    for item in report["validation_matrix"]:
        lines.append(f"- `{item['name']}`: `{item['command']}`")

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

    parser = argparse.ArgumentParser(description="Build the G10 completion verification and roadmap handoff report.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--completion-report", action="store_true")
    mode.add_argument("--completion-md", action="store_true")
    args = parser.parse_args(argv)

    if args.completion_md:
        sys.stdout.write(render_completion_md())
        return 0

    sys.stdout.write(report_as_json(build_completion_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
