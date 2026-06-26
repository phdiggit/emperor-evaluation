from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import i5b_dictionary_snapshot_loader_validator as snapshot_loader  # noqa: E402
from scripts.platform import i5b_python_constant_cleanup_after_readthrough as cleanup  # noqa: E402
from scripts.platform import i5b_rule_display_dictionary_contract as contract  # noqa: E402


PACKAGE_VERSION = "i5b-rule-display-dictionary-governance-gate-v1"
ROADMAP_ISSUE = contract.ROADMAP_ISSUE
EPIC_ISSUE = contract.EPIC_ISSUE
TECH_DEBT_ISSUE = contract.TECH_DEBT_ISSUE
CLEANUP_PR = 328
CLEANUP_MERGE_COMMIT = "622590a1b7b6970c4c97d0a209b1eed3efa2eb5c"
SUPPORTED_MODES = ("governance-report", "governance-md")

GOVERNANCE_DECISIONS = (
    {
        "decision": "repo_immutable_snapshot_is_current_offline_release_artifact",
        "status": "accepted_for_pre_g10_runtime",
        "rationale": "ordinary exports and CI must keep deterministic offline rerun without a live DSN",
    },
    {
        "decision": "postgres_dictionary_tables_require_separate_schema_gate",
        "status": "deferred",
        "rationale": "dictionary table creation is non-destructive but still schema-changing and must remain separately reviewable",
    },
    {
        "decision": "canonical_dictionary_write_requires_separate_write_gate",
        "status": "deferred",
        "rationale": "canonical dictionary writes must be auditable, reversible, and scoped to an explicit PR",
    },
    {
        "decision": "runtime_python_modules_keep_compatible_symbols_only",
        "status": "accepted",
        "rationale": "public constants remain compatibility surfaces; values are initialized from the validated snapshot",
    },
)

CHANGE_CONTROL_REQUIREMENTS = (
    "bump_or_add_versioned_rule_id_for_semantic_dictionary_changes",
    "keep_locale_status_effective_from_gate_source_and_digest_on_every_item",
    "run_snapshot_validator_and_readthrough_parity_tests",
    "state whether output parity is expected or intentionally changed in PR body",
    "keep ordinary exports independent from live DSN unless a separate gate approves otherwise",
)

FUTURE_SCHEMA_GATE_REQUIREMENTS = (
    "separate PR for PostgreSQL dictionary table DDL",
    "separate PR for canonical dictionary write or backfill",
    "rollback or audit plan for any dictionary data write",
    "operator-visible evidence that ordinary exports still support offline snapshot mode",
)

BLOCKED_OUTPUTS = (
    "postgres_dictionary_table_creation",
    "canonical_dictionary_write",
    "ordinary_export_runtime_dsn_dependency",
    "new_subitem_formal_scores",
    "new_subitem_formal_rankings",
    "stage_total_table",
    "final_total_table",
    "cross_subitem_leaderboard",
    "g10_destructive_cleanup",
)


def build_governance_report() -> dict[str, Any]:
    snapshot_report = snapshot_loader.build_snapshot_report()
    cleanup_report = cleanup.build_cleanup_report()
    blockers = []
    if snapshot_report["validation_errors"]:
        blockers.append("snapshot_validation_failed")
    if cleanup_report["cleanup_blockers"]:
        blockers.append("python_constant_cleanup_not_ready")

    ready = not blockers
    return {
        "mode": "governance-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "tech_debt_issue": TECH_DEBT_ISSUE,
        "cleanup_pr": CLEANUP_PR,
        "cleanup_merge_commit": CLEANUP_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_import_runtime_adapter": True,
        "does_not_render_exports": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_write_business_tables": True,
        "does_not_write_postgres_dictionary_tables": True,
        "does_not_write_canonical_dictionary": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "current_state": {
            "current_phase": "issue311_rule_display_dictionary_governance_gate_ready",
            "active_epic": EPIC_ISSUE,
            "active_tech_debt": TECH_DEBT_ISSUE,
            "issue311_rule_display_dictionary_governance_gate_ready": ready,
            "dictionary_governance_policy_recorded": ready,
            "immutable_snapshot_runtime_mode_retained": True,
            "future_postgres_dictionary_schema_gate_required": True,
            "future_canonical_dictionary_write_gate_required": True,
            "snapshot_validation_passed": snapshot_report["validated"],
            "python_constant_cleanup_passed": not cleanup_report["cleanup_blockers"],
            "postgres_dictionary_tables_created": False,
            "canonical_dictionary_write_performed": False,
            "ordinary_exports_require_live_dsn": False,
            "g10_destructive_cleanup_entered": False,
        },
        "governance_blockers": blockers,
        "governance_decisions": list(GOVERNANCE_DECISIONS),
        "change_control_requirements": list(CHANGE_CONTROL_REQUIREMENTS),
        "future_schema_gate_requirements": list(FUTURE_SCHEMA_GATE_REQUIREMENTS),
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "snapshot_package_version": snapshot_report["package_version"],
        "cleanup_package_version": cleanup_report["package_version"],
        "next_required_work": "epic5_pre_g10_contract_schema_report_test_plumbing",
    }


def render_governance_md() -> str:
    report = build_governance_report()
    lines = [
        "# I5B Rule And Display Dictionary Governance Gate",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- tech_debt_issue: `#{report['tech_debt_issue']}`",
        f"- governance_blockers: `{len(report['governance_blockers'])}`",
        f"- next_required_work: `{report['next_required_work']}`",
        "",
        "## Governance Decisions",
        "",
    ]
    for decision in report["governance_decisions"]:
        lines.append(
            f"- `{decision['decision']}`: status=`{decision['status']}`; rationale={decision['rationale']}"
        )

    lines.extend(["", "## Change Control Requirements", ""])
    for requirement in report["change_control_requirements"]:
        lines.append(f"- `{requirement}`")

    lines.extend(["", "## Blocked Outputs", ""])
    for output in report["blocked_outputs"]:
        lines.append(f"- `{output}`")

    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build I5B rule/display dictionary governance gate reports.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--governance-report", action="store_true")
    mode.add_argument("--governance-md", action="store_true")
    args = parser.parse_args(argv)

    if args.governance_md:
        sys.stdout.write(render_governance_md())
        return 0

    sys.stdout.write(report_as_json(build_governance_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
