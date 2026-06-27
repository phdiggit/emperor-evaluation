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


PACKAGE_VERSION = "g10-historical-asset-retirement-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
PLAN_ISSUE = 331
DICTIONARY_CLEANUP_ISSUE = 332
RETIREMENT_ISSUE = 333
PREREQUISITE_PR = 337
PREREQUISITE_MERGE_COMMIT = "703cae862f9fb6363315c85cce629616c8ab5de1"
SUPPORTED_MODES = ("retirement-report", "retirement-md")
PACKAGE_CHANGED_PATHS = (
    "db/postgres/README.md",
    "docs/数据结构与生成库/史源数据平台迁移决策.md",
    "docs/文档与脚本登记/scripts_registry.json",
    "scripts/platform/g10_historical_asset_retirement.py",
    "scripts/platform/platform_chain_checkpoint.py",
    "tests/test_g10_historical_asset_retirement.py",
    "tests/test_platform_chain_checkpoint.py",
)
PROTECTED_DESTRUCTIVE_ROOTS = (
    "data/batches/",
    "data/*_batches/",
    "archive/data/",
    "exports/",
)
BLOCKED_OUTPUTS = (
    "data_batch_payload_archive_without_manifest",
    "archive_data_mutation_without_restore_gate",
    "generated_export_delete_while_registry_or_tests_reference_targets",
    "active_runtime_entrypoint_removal",
    "source_of_truth_removal",
    "new_score_publication",
    "new_ranking_publication",
    "stage_total_table",
    "final_total_table",
    "cross_subitem_leaderboard",
)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _existing_files_for_patterns(patterns: Sequence[str]) -> list[str]:
    paths: set[str] = set()
    for pattern in patterns:
        normalized = pattern.rstrip("/")
        if "*" in normalized:
            roots = [path for path in ROOT.glob(normalized) if path.exists()]
        else:
            roots = [ROOT / normalized]
        for root in roots:
            if root.is_file():
                paths.add(_relative(root))
            elif root.is_dir():
                for child in root.rglob("*"):
                    if child.is_file():
                        paths.add(_relative(child))
    return sorted(paths)


def _issue_333_candidates() -> list[dict[str, Any]]:
    return [
        dict(candidate)
        for candidate in inventory_plan.CLEANUP_CANDIDATES
        if int(candidate["execution_issue"]) == RETIREMENT_ISSUE
    ]


def _docs_registry() -> dict[str, Any]:
    return _load_json(inventory_plan.DOCS_REGISTRY_PATH)


def _scripts_registry() -> dict[str, Any]:
    return _load_json(inventory_plan.SCRIPT_REGISTRY_PATH)


def _referenced_export_targets(docs_registry: Mapping[str, Any]) -> list[str]:
    targets: set[str] = set()
    for doc in docs_registry.get("documents", []):
        if isinstance(doc, Mapping):
            for target in doc.get("placement_targets", []) or []:
                if str(target).startswith("exports/"):
                    targets.add(str(target))
    for map_name in ("retired_generated_document_paths", "retired_mixed_document_paths"):
        mapping = docs_registry.get(map_name, {})
        if isinstance(mapping, Mapping):
            for target in mapping.values():
                if str(target).startswith("exports/"):
                    targets.add(str(target))
    return sorted(targets)


def _candidate_action(candidate: Mapping[str, Any], docs_registry: Mapping[str, Any]) -> dict[str, Any]:
    asset_id = str(candidate["asset_id"])
    patterns = [str(path) for path in candidate["paths"] if ":" not in str(path)]
    existing_files = _existing_files_for_patterns(patterns)
    classification = str(candidate["lifecycle_classification"])

    if classification in {"audit_only", "keep_active"}:
        action = "retain_without_path_change"
        execution_status = f"{classification}_confirmed"
        destructive_action_deferred = False
        reason = "Candidate remains an audit or registry spine asset; no file move/delete/archive is allowed in G10-2."
    elif asset_id == "archive_data_jsonl_batch_history":
        action = "defer_archive_until_payload_manifest_gate"
        execution_status = "archive_deferred"
        destructive_action_deferred = True
        reason = "Batch and archive/data payloads can contain unique review context; this PR manifests paths only and does not read or move payload content."
    elif asset_id == "generated_markdown_and_governance_exports":
        referenced_targets = set(_referenced_export_targets(docs_registry))
        action = "defer_delete_until_generated_export_reference_gate"
        execution_status = "delete_deferred"
        destructive_action_deferred = True
        reason = (
            "Generated exports still have docs registry or test-visible references; deletion requires a separate gate that first updates those references."
            if referenced_targets
            else "Generated exports are delete candidates, but deletion remains deferred to keep this package non-destructive."
        )
    else:
        action = "manifest_only_no_path_change"
        execution_status = "manifested"
        destructive_action_deferred = classification in inventory_plan.DESTRUCTIVE_CLASSIFICATIONS
        reason = "No concrete safe path mutation was selected from the G10-0 inventory."

    return {
        "asset_id": asset_id,
        "asset_type": candidate["asset_type"],
        "lifecycle_classification": classification,
        "risk_class": candidate["risk_class"],
        "requested_paths": list(candidate["paths"]),
        "existing_file_count": len(existing_files),
        "sample_existing_files": existing_files[:20],
        "action": action,
        "execution_status": execution_status,
        "destructive_action_deferred": destructive_action_deferred,
        "actual_moved_deleted_archived_paths": [],
        "replacement_mapping": candidate["replacement_mapping"],
        "restore_instructions": [
            f"Restore any changed tracked path with: git checkout GPT -- {path}"
            for path in existing_files[:20]
        ]
        or ["No tracked file mutation was performed for this candidate."],
        "reason": reason,
    }


def build_retirement_report() -> dict[str, Any]:
    docs_registry = _docs_registry()
    scripts_registry = _scripts_registry()
    candidates = _issue_333_candidates()
    manifest = [_candidate_action(candidate, docs_registry) for candidate in candidates]
    referenced_export_targets = _referenced_export_targets(docs_registry)
    generated_export_files = _existing_files_for_patterns(("exports/",))
    batch_archive_files = _existing_files_for_patterns(("archive/data/jsonl_batches/", "data/batches/", "data/*_batches/"))
    actual_path_actions = [
        path
        for item in manifest
        for path in item["actual_moved_deleted_archived_paths"]
    ]
    destructive_deferred = [item["asset_id"] for item in manifest if item["destructive_action_deferred"]]
    restore_complete = all(item["restore_instructions"] for item in manifest)

    return {
        "mode": "retirement-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "plan_issue": PLAN_ISSUE,
        "dictionary_cleanup_issue": DICTIONARY_CLEANUP_ISSUE,
        "retirement_issue": RETIREMENT_ISSUE,
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
        "does_not_read_generated_export_contents": True,
        "does_not_write_business_tables": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "does_not_move_delete_or_archive_files": True,
        "current_state": {
            "current_phase": "g10_historical_asset_retirement_ready",
            "active_epic": EPIC_ISSUE,
            "g10_2_historical_asset_retirement_ready": True,
            "g10_execution_started": True,
            "g10_cleanup_execution_started": True,
            "g10_destructive_cleanup_started": False,
            "changed_removed_archived_paths_manifested": True,
            "actual_moved_deleted_archived_path_count": len(actual_path_actions),
            "destructive_path_actions_deferred": bool(destructive_deferred),
            "registry_dangling_active_entries": 0,
            "default_validate_retired_script_invocations": 0,
            "replacement_mapping_auditable": True,
            "restore_instructions_complete": restore_complete,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
        },
        "changed_paths_manifest": list(PACKAGE_CHANGED_PATHS),
        "removed_paths_manifest": [],
        "archived_paths_manifest": [],
        "retirement_manifest": manifest,
        "retirement_manifest_count": len(manifest),
        "destructive_action_deferred_asset_ids": destructive_deferred,
        "protected_destructive_roots": list(PROTECTED_DESTRUCTIVE_ROOTS),
        "generated_export_existing_file_count": len(generated_export_files),
        "generated_export_registry_reference_count": len(referenced_export_targets),
        "sample_generated_export_registry_references": referenced_export_targets[:20],
        "batch_archive_existing_file_count": len(batch_archive_files),
        "scripts_registry_snapshot": {
            "platform_module_count": len(scripts_registry.get("platform_modules", [])),
            "scripts_module_count": len(scripts_registry.get("modules", [])),
            "retired_legacy_wrapper_count": len(scripts_registry.get("retired_legacy_wrappers", {})),
        },
        "docs_registry_snapshot": {
            "document_count": len(docs_registry.get("documents", [])),
            "archived_document_path_count": len(docs_registry.get("archived_document_paths", {})),
            "retired_generated_document_path_count": len(docs_registry.get("retired_generated_document_paths", {})),
            "retired_mixed_document_path_count": len(docs_registry.get("retired_mixed_document_paths", {})),
        },
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "next_required_work": "issue334_script_asset_risk_governance",
    }


def render_retirement_md() -> str:
    report = build_retirement_report()
    lines = [
        "# G10 Historical Asset Retirement",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- retirement_issue: `#{report['retirement_issue']}`",
        f"- prerequisite_pr: `#{report['prerequisite_pr']}`",
        f"- actual_moved_deleted_archived_path_count: `{report['current_state']['actual_moved_deleted_archived_path_count']}`",
        f"- destructive_path_actions_deferred: `{str(report['current_state']['destructive_path_actions_deferred']).lower()}`",
        f"- next_required_work: `{report['next_required_work']}`",
        "",
        "## Retirement Manifest",
        "",
    ]
    for item in report["retirement_manifest"]:
        lines.append(
            f"- `{item['asset_id']}`: action=`{item['action']}`, "
            f"status=`{item['execution_status']}`, files=`{item['existing_file_count']}`"
        )

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

    parser = argparse.ArgumentParser(description="Build the G10-2 historical asset retirement manifest.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--retirement-report", action="store_true")
    mode.add_argument("--retirement-md", action="store_true")
    args = parser.parse_args(argv)

    if args.retirement_md:
        sys.stdout.write(render_retirement_md())
        return 0

    sys.stdout.write(report_as_json(build_retirement_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
