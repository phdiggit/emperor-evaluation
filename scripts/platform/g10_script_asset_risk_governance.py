from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_cleanup_inventory_plan as inventory_plan  # noqa: E402


PACKAGE_VERSION = "g10-script-asset-risk-governance-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
PLAN_ISSUE = 331
SCRIPT_GOVERNANCE_ISSUE = 334
SCRIPT_GOVERNANCE_ENFORCEMENT_ISSUE = 342
PREREQUISITE_PR = 338
PREREQUISITE_MERGE_COMMIT = "54f7466f4aeb44d5a18bffb1c28a4eda23ca4954"
SUPPORTED_MODES = ("script-delta-report", "script-delta-md")
DEFAULT_VALIDATE_ENTRYPOINTS = (
    ROOT / "scripts" / "validate" / "validate_all.py",
    ROOT / ".github" / "workflows" / "validate.yml",
)
PACKAGE_CHANGED_PATHS = (
    "db/postgres/README.md",
    "docs/数据结构与生成库/史源数据平台迁移决策.md",
    "docs/文档与脚本登记/scripts_registry.json",
    "scripts/platform/g10_script_asset_risk_governance.py",
    "scripts/platform/platform_chain_checkpoint.py",
    "tests/test_g10_script_asset_risk_governance.py",
    "tests/test_platform_chain_checkpoint.py",
)

DUPLICATE_CAPABILITY_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "group_id": "gate_approval_preflight",
        "terms": ("gate", "approval", "preflight", "guard"),
        "decision": "retain_with_reason",
        "reason": (
            "Stage-specific gates preserve separate audit boundaries; shared helpers live under "
            "scripts/platform/core/gates.py where common behavior exists."
        ),
    },
    {
        "group_id": "report_publication_packages",
        "terms": ("report", "publication", "package"),
        "decision": "retain_with_reason",
        "reason": "Report packages encode different release gates and must stay auditable by stage.",
    },
    {
        "group_id": "redaction_fingerprint_helpers",
        "terms": ("redaction", "fingerprint"),
        "decision": "already_consolidated",
        "reason": "Shared redaction and fingerprint behavior is centralized in scripts/platform/core.",
    },
    {
        "group_id": "evidence_mapping_resolver_family",
        "terms": ("evidence", "mapping", "mapper", "resolver"),
        "decision": "retain_with_reason",
        "reason": (
            "JSONL mapper and resolver entrypoints cover distinct target contracts; common engine "
            "opportunities remain future consolidation candidates."
        ),
    },
    {
        "group_id": "schema_migration_seed_scaffolds",
        "terms": ("schema", "migration", "seed"),
        "decision": "retain_with_reason",
        "reason": (
            "Historical schema, migration, and seed scaffolds are retired-in-place audit records "
            "after #346 and are not default public execution routes."
        ),
    },
)

BLOCKED_OUTPUTS = (
    "ordinary_business_behavior_change",
    "production_runtime_switch",
    "production_data_migration",
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


def _load_default_route_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in DEFAULT_VALIDATE_ENTRYPOINTS:
        if path.exists():
            sources[_relative(path)] = path.read_text(encoding="utf-8")
    return sources


def _retired_wrapper_paths(registry: Mapping[str, Any]) -> list[str]:
    wrappers = registry.get("retired_legacy_wrappers", {})
    if isinstance(wrappers, Mapping):
        return sorted(str(path) for path in wrappers)
    if isinstance(wrappers, Sequence) and not isinstance(wrappers, (str, bytes)):
        return sorted(str(path) for path in wrappers)
    return []


def _path_is_referenced(path: str, source: str) -> bool:
    return path in source or path.replace("/", "\\") in source


def _module_text(module: Mapping[str, Any]) -> str:
    return f"{module.get('implementation', '')} {module.get('capability', '')}".lower()


def _status_counts(modules: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(module.get("lifecycle_status", "")) for module in modules).items()))


def _risk_counts(modules: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(module.get("risk_class", "")) for module in modules).items()))


def _epic_owner_counts(modules: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(module.get("epic_owner", "")) for module in modules).items()))


def _build_duplicate_capability_review(modules: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    for group in DUPLICATE_CAPABILITY_GROUPS:
        terms = tuple(str(term) for term in group["terms"])
        members = [
            {
                "implementation": str(module["implementation"]),
                "lifecycle_status": str(module["lifecycle_status"]),
                "risk_class": str(module["risk_class"]),
                "public_cli_stable": bool(module["public_cli_stable"]),
            }
            for module in modules
            if any(term in _module_text(module) for term in terms)
        ]
        reviews.append(
            {
                "group_id": group["group_id"],
                "matched_terms": list(terms),
                "module_count": len(members),
                "sample_modules": members[:12],
                "decision": group["decision"],
                "retain_or_consolidation_reason": group["reason"],
                "requires_immediate_consolidation": False,
            }
        )
    return reviews


def analyze_scripts_registry(
    registry: Mapping[str, Any],
    default_route_sources: Mapping[str, str],
) -> dict[str, Any]:
    modules = [
        module
        for module in registry.get("platform_modules", [])
        if isinstance(module, Mapping)
    ]
    retired_module_paths = [
        str(module["implementation"])
        for module in modules
        if module.get("lifecycle_status") == "retired"
    ]
    retired_paths = sorted(set(retired_module_paths) | set(_retired_wrapper_paths(registry)))
    default_route_references = [
        {"entrypoint": entrypoint, "retired_path": retired_path}
        for entrypoint, source in sorted(default_route_sources.items())
        for retired_path in retired_paths
        if _path_is_referenced(retired_path, source)
    ]
    retired_public_cli_modules = [
        str(module["implementation"])
        for module in modules
        if module.get("lifecycle_status") == "retired" and module.get("public_cli_stable") is True
    ]
    transitional_without_sunset = [
        str(module["implementation"])
        for module in modules
        if module.get("lifecycle_status") == "transitional" and not module.get("sunset_milestone")
    ]
    duplicate_reviews = _build_duplicate_capability_review(modules)
    duplicate_groups_without_reason = [
        review["group_id"]
        for review in duplicate_reviews
        if review["module_count"] > 1 and not review["retain_or_consolidation_reason"]
    ]

    return {
        "platform_module_count": len(modules),
        "platform_lifecycle_status_counts": _status_counts(modules),
        "platform_risk_class_counts": _risk_counts(modules),
        "platform_epic_owner_counts": _epic_owner_counts(modules),
        "public_cli_stable_count": sum(1 for module in modules if module.get("public_cli_stable") is True),
        "transitional_scripts_without_sunset": transitional_without_sunset,
        "transitional_scripts_without_sunset_count": len(transitional_without_sunset),
        "retired_platform_modules": retired_module_paths,
        "retired_legacy_wrapper_count": len(_retired_wrapper_paths(registry)),
        "default_validate_retired_script_references": default_route_references,
        "retired_public_cli_modules": retired_public_cli_modules,
        "retired_scripts_in_default_validate_or_public_cli": len(default_route_references)
        + len(retired_public_cli_modules),
        "duplicate_capability_review": duplicate_reviews,
        "duplicate_capability_group_count": len(duplicate_reviews),
        "duplicate_capability_groups_without_reason": duplicate_groups_without_reason,
    }


def _issue_334_inventory_candidates() -> list[dict[str, Any]]:
    return [
        dict(candidate)
        for candidate in inventory_plan.CLEANUP_CANDIDATES
        if int(candidate["execution_issue"]) == SCRIPT_GOVERNANCE_ISSUE
    ]


def _outcome_verification_delta(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deltas: list[dict[str, Any]] = []
    for candidate in candidates:
        deltas.append(
            {
                "asset_id": candidate["asset_id"],
                "asset_type": candidate["asset_type"],
                "lifecycle_classification": candidate["lifecycle_classification"],
                "decision": "retain_until_equivalent_outcome_checks_replace_text_mirror_tests",
                "outcome_verification_added": True,
                "text_mirror_only": False,
                "proof": (
                    "tests/test_g10_script_asset_risk_governance.py exercises structured registry "
                    "analysis, default-route retired references, duplicate review reasons, and a "
                    "negative fixture with bad lifecycle/default-route inputs."
                ),
            }
        )
    return deltas


def build_script_delta_report() -> dict[str, Any]:
    registry = _load_json(inventory_plan.SCRIPT_REGISTRY_PATH)
    default_route_sources = _load_default_route_sources()
    analysis = analyze_scripts_registry(registry, default_route_sources)
    candidates = _issue_334_inventory_candidates()

    return {
        "mode": "script-delta-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "plan_issue": PLAN_ISSUE,
        "script_governance_issue": SCRIPT_GOVERNANCE_ISSUE,
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
        "does_not_write_business_tables": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "does_not_move_delete_or_archive_files": True,
        "current_state": {
            "current_phase": "g10_script_asset_risk_governance_ready",
            "active_epic": EPIC_ISSUE,
            "g10_3_script_asset_risk_governance_ready": True,
            "g10_script_asset_risk_governance_package": PACKAGE_VERSION,
            "g10_script_asset_risk_governance_prerequisite_pr": PREREQUISITE_PR,
            "g10_script_asset_risk_governance_prerequisite_merge_commit": PREREQUISITE_MERGE_COMMIT,
            "transitional_scripts_without_sunset": analysis["transitional_scripts_without_sunset_count"],
            "retired_scripts_in_default_validate_or_public_cli": analysis[
                "retired_scripts_in_default_validate_or_public_cli"
            ],
            "duplicate_capability_groups_reviewed": analysis["duplicate_capability_group_count"],
            "duplicate_capability_groups_without_reason": len(
                analysis["duplicate_capability_groups_without_reason"]
            ),
            "script_delta_ready_for_roadmap_comments": True,
            "outcome_verification_tests_added": True,
            "g10_3b_script_governance_enforcement_ready": True,
            "registry_lifecycle_guard_enabled": True,
            "registry_lifecycle_guard_in_validate_all": True,
            "script_delta_updated_for_roadmap_and_epic": True,
            "g10_execution_started": True,
            "g10_cleanup_execution_started": True,
            "g10_destructive_cleanup_started": False,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
        },
        "changed_paths_manifest": list(PACKAGE_CHANGED_PATHS),
        "script_delta_targets": [
            ROADMAP_ISSUE,
            EPIC_ISSUE,
            PLAN_ISSUE,
            SCRIPT_GOVERNANCE_ISSUE,
            SCRIPT_GOVERNANCE_ENFORCEMENT_ISSUE,
        ],
        "default_validate_entrypoints": sorted(default_route_sources),
        "scripts_registry_analysis": analysis,
        "issue_334_inventory_candidates": candidates,
        "outcome_verification_delta": _outcome_verification_delta(candidates),
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "next_required_work": "issue335_g10_completion_verification_and_roadmap_handoff",
    }


def render_script_delta_md() -> str:
    report = build_script_delta_report()
    state = report["current_state"]
    analysis = report["scripts_registry_analysis"]
    lines = [
        "# G10 Script Asset Risk Governance",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- script_governance_issue: `#{report['script_governance_issue']}`",
        f"- prerequisite_pr: `#{report['prerequisite_pr']}`",
        f"- current_phase: `{state['current_phase']}`",
        f"- transitional_scripts_without_sunset: `{state['transitional_scripts_without_sunset']}`",
        f"- retired_scripts_in_default_validate_or_public_cli: `{state['retired_scripts_in_default_validate_or_public_cli']}`",
        f"- duplicate_capability_groups_reviewed: `{state['duplicate_capability_groups_reviewed']}`",
        f"- duplicate_capability_groups_without_reason: `{state['duplicate_capability_groups_without_reason']}`",
        f"- g10_3b_script_governance_enforcement_ready: `{str(state['g10_3b_script_governance_enforcement_ready']).lower()}`",
        f"- registry_lifecycle_guard_enabled: `{str(state['registry_lifecycle_guard_enabled']).lower()}`",
        f"- next_required_work: `{report['next_required_work']}`",
        "",
        "## Duplicate Capability Review",
        "",
    ]
    for review in analysis["duplicate_capability_review"]:
        lines.append(
            f"- `{review['group_id']}`: modules=`{review['module_count']}`, "
            f"decision=`{review['decision']}`, reason=`{review['retain_or_consolidation_reason']}`"
        )

    lines.extend(["", "## Outcome Verification Delta", ""])
    for item in report["outcome_verification_delta"]:
        lines.append(
            f"- `{item['asset_id']}`: decision=`{item['decision']}`, "
            f"outcome_verification_added=`{str(item['outcome_verification_added']).lower()}`"
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

    parser = argparse.ArgumentParser(description="Build the G10-3 script asset risk governance Script Delta.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--script-delta-report", action="store_true")
    mode.add_argument("--script-delta-md", action="store_true")
    args = parser.parse_args(argv)

    if args.script_delta_md:
        sys.stdout.write(render_script_delta_md())
        return 0

    sys.stdout.write(report_as_json(build_script_delta_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
