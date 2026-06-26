from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PACKAGE_VERSION = "g10-cleanup-inventory-plan-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
PLAN_ISSUE = 331
LAST_MERGED_PR = 330
LAST_MERGED_PR_MERGE_COMMIT = "cd0fbbc2a28da4194801d906eff742f204faca62"
SUPPORTED_MODES = ("inventory-report", "inventory-md")
SCRIPT_REGISTRY_PATH = ROOT / "docs" / "文档与脚本登记" / "scripts_registry.json"
DOCS_REGISTRY_PATH = ROOT / "docs" / "文档与脚本登记" / "docs_registry.json"

LIFECYCLE_CLASSIFICATIONS = (
    "keep_active",
    "audit_only",
    "superseded",
    "deprecated",
    "retire_candidate",
    "archive_candidate",
    "delete_candidate",
)
DESTRUCTIVE_CLASSIFICATIONS = {"retire_candidate", "archive_candidate", "delete_candidate"}
REQUIRED_ASSET_TYPES = (
    "scripts",
    "docs",
    "archives",
    "generated_exports",
    "registry_entries",
    "tests",
)

CLEANUP_CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "asset_id": "i5b_rule_display_dictionary_runtime_snapshot",
        "asset_type": "scripts",
        "paths": [
            "scripts/platform/i5b_dictionary_snapshots/i5b_rule_display_dictionary_snapshot_v1.json",
            "scripts/export/dimension_adapters/i5b_people_delegation/dictionary_readthrough.py",
            "scripts/export/dimension_adapters/i5b_people_delegation/rules.py",
            "scripts/export/dimension_adapters/i5b_people_delegation/formal_algorithm.py",
            "scripts/export/dimension_adapters/i5b_people_delegation/adapter.py",
        ],
        "lifecycle_classification": "keep_active",
        "risk_class": "high",
        "replacement_mapping": {
            "replacement_path": "scripts/platform/i5b_dictionary_snapshots/i5b_rule_display_dictionary_snapshot_v1.json",
            "archive_path": None,
            "git_history_only": False,
            "registry_record": "platform_i5b_rule_display_dictionary_governance_gate",
        },
        "restore_plan": [
            "Restore the immutable snapshot and readthrough modules from git.",
            "Run the snapshot validator and I5B readthrough parity tests.",
        ],
        "execution_issue": 332,
        "notes": "Keep the immutable snapshot and runtime readthrough path active while G10-1 removes remaining duplicate source text.",
    },
    {
        "asset_id": "issue311_transition_audit_packages",
        "asset_type": "scripts",
        "paths": [
            "scripts/platform/i5b_rule_display_dictionary_contract.py",
            "scripts/platform/i5b_dictionary_snapshot_loader_validator.py",
            "scripts/platform/i5b_runtime_adapter_dictionary_readiness.py",
            "scripts/platform/i5b_python_constant_cleanup_after_readthrough.py",
            "scripts/platform/i5b_rule_display_dictionary_governance_gate.py",
        ],
        "lifecycle_classification": "retire_candidate",
        "risk_class": "high",
        "replacement_mapping": {
            "replacement_path": "scripts/platform/i5b_dictionary_snapshots/i5b_rule_display_dictionary_snapshot_v1.json",
            "archive_path": "archive/docs/audits/",
            "git_history_only": False,
            "registry_record": "docs/文档与脚本登记/scripts_registry.json",
        },
        "restore_plan": [
            "Keep source files until G10-1 proves readthrough parity from the immutable snapshot.",
            "If retired later, restore from git by path and re-enable only through the scripts registry.",
        ],
        "execution_issue": 332,
        "notes": "Candidate only; G10-0 does not change lifecycle or remove files.",
    },
    {
        "asset_id": "epic5_pre_g10_contract_packages",
        "asset_type": "scripts",
        "paths": [
            "scripts/platform/epic5_scoring_engine_scope_package.py",
            "scripts/platform/epic5_scoring_engine_interface_contract.py",
            "scripts/platform/epic5_pilot_subitem_profile_contract.py",
            "scripts/platform/epic5_pilot_subitem_evidence_profile_contract.py",
            "scripts/platform/epic5_formal_grade_result_contract.py",
            "scripts/platform/epic5_score_publication_result_contract.py",
            "scripts/platform/epic5_deterministic_rerun_report_contract.py",
            "scripts/platform/epic5_per_subitem_g8_algorithm_release_gate.py",
        ],
        "lifecycle_classification": "audit_only",
        "risk_class": "medium",
        "replacement_mapping": {
            "replacement_path": "scripts/platform/platform_chain_checkpoint.py",
            "archive_path": None,
            "git_history_only": False,
            "registry_record": "docs/文档与脚本登记/scripts_registry.json",
        },
        "restore_plan": [
            "Use the checkpoint and git history to reconstruct the completed Epic5 contract chain.",
            "Retain CLI entrypoints until G10-4 proves no default validation route depends on them.",
        ],
        "execution_issue": 333,
        "notes": "Audit-only classification prevents accidental deletion before #333 validates registry and test dependencies.",
    },
    {
        "asset_id": "current_platform_and_scoring_docs",
        "asset_type": "docs",
        "paths": [
            "docs/皇帝综合评价体系评分标准.md",
            "docs/数据结构与生成库/史源数据平台迁移决策.md",
            "db/postgres/README.md",
            "docs/文档与脚本登记/docs_registry.json",
            "docs/文档与脚本登记/scripts_registry.json",
        ],
        "lifecycle_classification": "keep_active",
        "risk_class": "high",
        "replacement_mapping": {
            "replacement_path": "docs/数据结构与生成库/史源数据平台迁移决策.md",
            "archive_path": None,
            "git_history_only": False,
            "registry_record": "docs/文档与脚本登记/docs_registry.json",
        },
        "restore_plan": [
            "Restore current docs from git and re-run docs registry checks.",
            "Do not archive or delete the scoring standard in G10 cleanup.",
        ],
        "execution_issue": 335,
        "notes": "These are current fact sources, not cleanup targets.",
    },
    {
        "asset_id": "docs_registry_archived_and_retired_mappings",
        "asset_type": "registry_entries",
        "paths": [
            "docs/文档与脚本登记/docs_registry.json:archived_document_paths",
            "docs/文档与脚本登记/docs_registry.json:retired_generated_document_paths",
            "docs/文档与脚本登记/docs_registry.json:retired_mixed_document_paths",
        ],
        "lifecycle_classification": "keep_active",
        "risk_class": "medium",
        "replacement_mapping": {
            "replacement_path": "docs/文档与脚本登记/docs_registry.json",
            "archive_path": None,
            "git_history_only": False,
            "registry_record": "docs_registry_lifecycle_maps",
        },
        "restore_plan": [
            "Restore registry maps from git and run docs_tool check.",
            "Use registry paths as the restore index for archived and generated docs.",
        ],
        "execution_issue": 333,
        "notes": "Registry maps are the audit spine for later retirement PRs.",
    },
    {
        "asset_id": "scripts_registry_lifecycle_entries",
        "asset_type": "registry_entries",
        "paths": [
            "docs/文档与脚本登记/scripts_registry.json:platform_modules",
            "docs/文档与脚本登记/scripts_registry.json:retired_legacy_wrappers",
            "docs/文档与脚本登记/scripts_registry.json:root_exceptions",
        ],
        "lifecycle_classification": "keep_active",
        "risk_class": "high",
        "replacement_mapping": {
            "replacement_path": "docs/文档与脚本登记/scripts_registry.json",
            "archive_path": None,
            "git_history_only": False,
            "registry_record": "scripts_registry_lifecycle_maps",
        },
        "restore_plan": [
            "Restore scripts registry from git and run agents-check plus canonical-imports-check.",
            "Use registry lifecycle fields to decide any later retire/archive/delete action.",
        ],
        "execution_issue": 334,
        "notes": "G10-3 must update this registry before changing default validation routes.",
    },
    {
        "asset_id": "archive_docs_historical_decision_records",
        "asset_type": "archives",
        "paths": [
            "archive/docs/adr/",
            "archive/docs/audits/",
            "archive/docs/design_snapshots/",
            "archive/docs/docs_governance/",
        ],
        "lifecycle_classification": "audit_only",
        "risk_class": "medium",
        "replacement_mapping": {
            "replacement_path": "docs/数据结构与生成库/史源数据平台迁移决策.md",
            "archive_path": "archive/docs/",
            "git_history_only": False,
            "registry_record": "docs/文档与脚本登记/docs_registry.json",
        },
        "restore_plan": [
            "Use docs_registry archived_document_paths to identify the current archive target.",
            "Restore individual history records from git if an audit trail is needed.",
        ],
        "execution_issue": 333,
        "notes": "Historical records stay audit-only unless #333 proves a narrower archive/delete action is safe.",
    },
    {
        "asset_id": "archive_data_jsonl_batch_history",
        "asset_type": "archives",
        "paths": [
            "archive/data/jsonl_batches/",
            "data/batches/",
            "data/*_batches/",
        ],
        "lifecycle_classification": "archive_candidate",
        "risk_class": "high",
        "replacement_mapping": {
            "replacement_path": "docs/数据结构与生成库/史源数据平台迁移决策.md",
            "archive_path": "archive/data/jsonl_batches/",
            "git_history_only": False,
            "registry_record": "source_batch_history_or_restore_manifest",
        },
        "restore_plan": [
            "Do not read or move batch payloads in G10-0.",
            "Before any later archive/delete action, create a manifest with git object restore instructions.",
        ],
        "execution_issue": 333,
        "notes": "High-risk candidate because batch history can carry unique source-review context.",
    },
    {
        "asset_id": "generated_markdown_and_governance_exports",
        "asset_type": "generated_exports",
        "paths": [
            "exports/",
            "exports/governance/",
            "exports/markdown_views/",
            "exports/matrix/",
        ],
        "lifecycle_classification": "delete_candidate",
        "risk_class": "medium",
        "replacement_mapping": {
            "replacement_path": "scripts/export/",
            "archive_path": None,
            "git_history_only": False,
            "registry_record": "docs/文档与脚本登记/docs_registry.json:retired_generated_document_paths",
        },
        "restore_plan": [
            "Regenerate from the owning exporter or docs_tool report command.",
            "If a generated view was tracked historically, restore it from git before rerunning the generator.",
        ],
        "execution_issue": 333,
        "notes": "Candidate only; G10-0 never deletes generated views.",
    },
    {
        "asset_id": "mirror_and_report_text_tests",
        "asset_type": "tests",
        "paths": [
            "tests/test_i5b_*audit*.py",
            "tests/test_file_governance_report.py",
            "tests/test_redundant_file_candidates_report.py",
            "tests/test_scripts_*directory_layout.py",
        ],
        "lifecycle_classification": "deprecated",
        "risk_class": "medium",
        "replacement_mapping": {
            "replacement_path": "tests/test_g10_cleanup_inventory_plan.py",
            "archive_path": None,
            "git_history_only": False,
            "registry_record": "docs/文档与脚本登记/scripts_registry.json:required_tests",
        },
        "restore_plan": [
            "Keep tests until #334 proves equivalent outcome-level checks.",
            "If a mirror test is retired later, restore it from git and re-add it to required_tests if validation regresses.",
        ],
        "execution_issue": 334,
        "notes": "Candidate for outcome-test strengthening, not immediate removal.",
    },
)

EXECUTION_SPLIT: tuple[dict[str, Any], ...] = (
    {
        "issue": 331,
        "name": "G10-0 cleanup inventory, replacement mapping, and restore plan",
        "allowed_actions": ["inventory", "mapping", "restore_plan", "execution_split"],
        "forbidden_actions": ["move_files", "delete_files", "archive_files", "publish_scores"],
        "must_land_before": [332, 333, 334, 335],
    },
    {
        "issue": 332,
        "name": "G10-1 I5B rule/display dictionary final cleanup",
        "allowed_actions": ["snapshot_readthrough_cleanup", "parity_tests", "no_hardcoded_copy_regression"],
        "depends_on": [331],
    },
    {
        "issue": 333,
        "name": "G10-2 historical scripts/docs/archive retirement",
        "allowed_actions": ["retire_archive_delete_after_manifest", "registry_lifecycle_sync", "restore_instructions"],
        "depends_on": [331],
    },
    {
        "issue": 334,
        "name": "G10-3 script asset risk governance",
        "allowed_actions": ["scripts_lifecycle_audit", "duplicate_capability_review", "outcome_test_strengthening"],
        "depends_on": [331],
    },
    {
        "issue": 335,
        "name": "G10-4 completion verification and roadmap handoff",
        "allowed_actions": ["completion_report", "validation_matrix", "roadmap_status_sync"],
        "depends_on": [332, 333, 334],
    },
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_registry_snapshot() -> dict[str, Any]:
    scripts_registry = _load_json(SCRIPT_REGISTRY_PATH)
    docs_registry = _load_json(DOCS_REGISTRY_PATH)
    return {
        "scripts_registry_path": SCRIPT_REGISTRY_PATH.relative_to(ROOT).as_posix(),
        "docs_registry_path": DOCS_REGISTRY_PATH.relative_to(ROOT).as_posix(),
        "platform_module_count": len(scripts_registry.get("platform_modules", [])),
        "scripts_module_count": len(scripts_registry.get("modules", [])),
        "retired_legacy_wrapper_count": len(scripts_registry.get("retired_legacy_wrappers", {})),
        "docs_document_count": len(docs_registry.get("documents", [])),
        "archived_document_path_count": len(docs_registry.get("archived_document_paths", {})),
        "retired_generated_document_path_count": len(docs_registry.get("retired_generated_document_paths", {})),
        "retired_mixed_document_path_count": len(docs_registry.get("retired_mixed_document_paths", {})),
    }


def _candidate_summary(candidates: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {classification: 0 for classification in LIFECYCLE_CLASSIFICATIONS}
    for candidate in candidates:
        counts[str(candidate["lifecycle_classification"])] += 1
    return counts


def build_inventory_report() -> dict[str, Any]:
    candidates = [dict(candidate) for candidate in CLEANUP_CANDIDATES]
    return {
        "mode": "inventory-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "plan_issue": PLAN_ISSUE,
        "last_merged_pr": LAST_MERGED_PR,
        "last_merged_pr_merge_commit": LAST_MERGED_PR_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_read_batch_payloads": True,
        "does_not_read_generated_exports": True,
        "does_not_move_delete_or_archive_files": True,
        "does_not_write_business_tables": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "current_state": {
            "current_phase": "g10_cleanup_inventory_plan_ready",
            "active_epic": EPIC_ISSUE,
            "g10_cleanup_inventory_plan_ready": True,
            "g10_execution_started": False,
            "g10_destructive_cleanup_started": False,
            "cleanup_candidate_count": len(candidates),
            "candidate_asset_types": sorted({candidate["asset_type"] for candidate in candidates}),
            "lifecycle_classification_counts": _candidate_summary(candidates),
            "next_required_work": "g10_1_i5b_rule_display_dictionary_final_cleanup_after_issue_331_lands",
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "registry_snapshot": build_registry_snapshot(),
        "cleanup_candidates": candidates,
        "execution_split": [dict(item) for item in EXECUTION_SPLIT],
        "inventory_invariants": [
            "all_candidate_asset_types_are_represented",
            "all_retire_archive_delete_candidates_have_replacement_mapping",
            "all_retire_archive_delete_candidates_have_restore_plan",
            "g10_0_is_inventory_only_no_file_moves",
            "g10_1_to_g10_4_execution_order_is_explicit",
            "stage_or_final_total_table_release_locked_false",
            "cross_subitem_leaderboard_release_locked_false",
        ],
        "blocked_outputs": [
            "file_move",
            "file_delete",
            "file_archive",
            "production_data_mutation",
            "new_score_publication",
            "new_ranking_publication",
            "stage_total_table",
            "final_total_table",
            "cross_subitem_leaderboard",
            "epic_2_or_epic_3_entry",
        ],
    }


def render_inventory_md() -> str:
    report = build_inventory_report()
    lines = [
        "# G10 Cleanup Inventory, Mapping, And Restore Plan",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- plan_issue: `#{report['plan_issue']}`",
        f"- last_merged_pr: `#{report['last_merged_pr']}`",
        f"- last_merged_pr_merge_commit: `{report['last_merged_pr_merge_commit']}`",
        "- This package is inventory-only. It does not move, delete, or archive files.",
        "",
        "## Cleanup Candidates",
        "",
    ]
    for candidate in report["cleanup_candidates"]:
        mapping = candidate["replacement_mapping"]
        lines.append(
            f"- `{candidate['asset_id']}`: asset_type=`{candidate['asset_type']}`; "
            f"classification=`{candidate['lifecycle_classification']}`; "
            f"replacement=`{mapping['replacement_path']}`; issue=`#{candidate['execution_issue']}`"
        )

    lines.extend(["", "## Execution Split", ""])
    for item in report["execution_split"]:
        lines.append(f"- `#{item['issue']}`: {item['name']}")

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

    parser = argparse.ArgumentParser(description="Build the G10 cleanup inventory and restore-plan package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inventory-report", action="store_true")
    mode.add_argument("--inventory-md", action="store_true")
    args = parser.parse_args(argv)

    if args.inventory_md:
        sys.stdout.write(render_inventory_md())
        return 0

    sys.stdout.write(report_as_json(build_inventory_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
