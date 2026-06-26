from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.epic5_deterministic_rerun_report_contract import (  # noqa: E402
    build_rerun_report_contracts,
)
from scripts.platform.epic5_formal_grade_result_contract import (  # noqa: E402
    FORMAL_GRADE_ALLOWED_VALUES,
    SCORE_RANGE_POLICY,
)


PACKAGE_VERSION = "epic5-per-subitem-g8-algorithm-release-gate-contract-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
DICTIONARY_GOVERNANCE_PR = 329
DICTIONARY_GOVERNANCE_MERGE_COMMIT = "7ea07c863679b11210f1f02086bdb28cd331a382"
SUPPORTED_MODES = ("contract-report", "g8-gate-md")

G8_RELEASE_REQUIRED_CHECKS = (
    "subitem_profile_reviewed",
    "evidence_profile_to_grade_mapping_reviewed",
    "score_range_and_candidate_value_deterministic",
    "deterministic_rerun_key_present",
    "impact_report_template_available_without_person_values",
    "publication_report_template_blocks_g9_outputs",
    "no_person_specific_override_enforced",
    "stage_or_final_total_table_release_locked_false",
    "cross_subitem_leaderboard_release_locked_false",
)

G8_GATE_ALLOWED_OUTPUTS = (
    "algorithm_version_for_subitem",
    "grade_ladder_and_score_range_contract",
    "deterministic_candidate_value_rule_contract",
    "impact_report_without_formal_person_values",
    "validator_contract",
)

G8_GATE_BLOCKED_OUTPUTS = (
    "person_specific_evidence_profile",
    "person_specific_formal_grade_result",
    "person_specific_score_publication_result",
    "new_subitem_formal_scores",
    "new_subitem_formal_rankings",
    "stage_total_table",
    "final_total_table",
    "cross_subitem_leaderboard",
    "source_lookup_or_sourcepack_claim",
    "source_document_passage_business_table_write",
    "evidence_cluster_anchor_relationship_business_table_write",
    "rule_display_dictionary_canonical_write",
    "g10_destructive_cleanup",
    "epic_2_or_epic_3_entry",
)


def build_g8_gate_contracts() -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for rerun_contract in build_rerun_report_contracts():
        publication_contract = rerun_contract["source_publication_contract"]
        subitem_profile = publication_contract["subitem_profile"]
        formal_grade_template = publication_contract["formal_grade_result_template"]
        contracts.append(
            {
                "subitem_id": rerun_contract["subitem_id"],
                "person_id": rerun_contract["person_id"],
                "subitem_profile": subitem_profile,
                "algorithm_version": subitem_profile["algorithm_version"],
                "g8_gate_status": "contract_template_only_not_approved",
                "g8_gate_template_ready": True,
                "g8_release_performed": False,
                "g9_publication_performed": False,
                "required_checks": list(G8_RELEASE_REQUIRED_CHECKS),
                "allowed_outputs": list(G8_GATE_ALLOWED_OUTPUTS),
                "blocked_outputs": list(G8_GATE_BLOCKED_OUTPUTS),
                "deterministic_rerun_key": formal_grade_template["deterministic_rerun_key"],
                "formal_grade_allowed_values": list(FORMAL_GRADE_ALLOWED_VALUES),
                "score_range_policy": SCORE_RANGE_POLICY,
                "no_override_policy": formal_grade_template["no_override_policy"],
                "impact_report_template": rerun_contract["impact_report_template"],
                "validator_contract": rerun_contract["validator_contract"],
                "publication_report_template": rerun_contract["publication_report_template"],
                "template_not_for_scoring": True,
                "template_not_for_publication": True,
                "person_specific_evidence_included": False,
                "person_specific_formal_grade_result_included": False,
                "person_specific_score_publication_result_included": False,
                "source_lookup_performed": False,
            }
        )
    return contracts


def build_contract_report() -> dict[str, Any]:
    contracts = build_g8_gate_contracts()
    subitem_ids = [contract["subitem_id"] for contract in contracts]
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "dictionary_governance_pr": DICTIONARY_GOVERNANCE_PR,
        "dictionary_governance_merge_commit": DICTIONARY_GOVERNANCE_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_write_business_tables": True,
        "does_not_lookup_sources": True,
        "does_not_build_person_specific_evidence": True,
        "does_not_release_person_specific_formal_grade_results": True,
        "does_not_release_person_specific_score_publication_results": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "current_state": {
            "current_phase": "epic5_per_subitem_g8_algorithm_release_gate_contract_ready",
            "active_epic": EPIC_ISSUE,
            "epic5_per_subitem_g8_algorithm_release_gate_contract_ready": True,
            "positive_benefit_total": 1500,
            "per_subitem_g8_gate_contract_count": len(contracts),
            "pilot_subitem_g8_gate_templates_selected": subitem_ids,
            "per_subitem_g8_algorithm_release_performed": False,
            "person_specific_evidence_profiles_built": False,
            "person_specific_formal_grade_results_built": False,
            "person_specific_score_publication_results_built": False,
            "formal_grade_results_released_for_new_subitems": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "g8_gate_contracts": contracts,
        "g8_gate_contract_invariants": [
            "subitem_profile_algorithm_version_is_gate_subject",
            "required_checks_reuse_epic5_scope_g8_policy",
            "deterministic_rerun_key_present_before_release_review",
            "impact_report_template_excludes_formal_person_values",
            "publication_report_template_blocks_g9_outputs",
            "no_override_policy_locked_false",
            "stage_or_final_total_table_release_locked_false",
            "cross_subitem_leaderboard_release_locked_false",
        ],
        "allowed_outputs": list(G8_GATE_ALLOWED_OUTPUTS),
        "blocked_outputs": list(G8_GATE_BLOCKED_OUTPUTS),
        "next_required_work": "epic5_per_subitem_g8_algorithm_release_review_or_execution_gate",
    }


def render_g8_gate_md() -> str:
    report = build_contract_report()
    lines = [
        "# Epic5 Per-Subitem G8 Algorithm Release Gate Contract",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- dictionary_governance_pr: `#{report['dictionary_governance_pr']}`",
        f"- dictionary_governance_merge_commit: `{report['dictionary_governance_merge_commit']}`",
        "- This package defines G8 gate templates only; it does not release new subitem algorithms.",
        "",
        "## G8 Gate Templates",
        "",
    ]
    for contract in report["g8_gate_contracts"]:
        lines.append(
            f"- `{contract['subitem_id']}`: algorithm_version=`{contract['algorithm_version']}`; "
            f"g8_gate_status=`{contract['g8_gate_status']}`; "
            "g8_release_performed=`false`; g9_publication_performed=`false`"
        )

    lines.extend(["", "## Required Checks", ""])
    for check in G8_RELEASE_REQUIRED_CHECKS:
        lines.append(f"- `{check}`")

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

    parser = argparse.ArgumentParser(description="Build the Epic5 per-subitem G8 algorithm release gate contract.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--g8-gate-md", action="store_true")
    args = parser.parse_args(argv)

    if args.g8_gate_md:
        sys.stdout.write(render_g8_gate_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
