from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.epic5_score_publication_result_contract import (  # noqa: E402
    TEMPLATE_PERSON_ID,
    build_score_publication_result_contracts,
)


PACKAGE_VERSION = "epic5-deterministic-rerun-report-contract-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
SCORE_PUBLICATION_CONTRACT_PR = 318
SCORE_PUBLICATION_CONTRACT_MERGE_COMMIT = "c800570aead93c146e6598d7246f892bf74aab5f"
SUPPORTED_MODES = ("contract-report", "rerun-report-md")

RERUN_REQUIRED_INPUTS = (
    "subitem_profile.subitem_id",
    "subitem_profile.score_cap",
    "subitem_profile.algorithm_version",
    "evidence_profile_template.positive_signal_profile",
    "evidence_profile_template.negative_signal_profile",
    "evidence_profile_template.cross_item_split_signals",
    "formal_grade_result_template.formal_grade",
    "formal_grade_result_template.score_range",
    "formal_grade_result_template.candidate_value",
)
VALIDATOR_REQUIRED_CHECKS = (
    "subitem_id_matches_across_profile_evidence_grade_publication",
    "template_person_id_is_not_real_person",
    "deterministic_rerun_key_is_present_and_stable",
    "candidate_value_is_inside_score_range",
    "publication_value_equals_candidate_placeholder",
    "g9_publication_gate_is_required_for_real_publication",
    "no_override_policy_locked_false",
    "stage_or_final_total_table_released_false",
    "cross_subitem_leaderboard_released_false",
)
IMPACT_REPORT_SECTIONS = (
    "subitem_profile_summary",
    "evidence_profile_signal_summary",
    "formal_grade_result_template",
    "deterministic_rerun_key_contract",
    "blocked_publication_outputs",
)
PUBLICATION_REPORT_SECTIONS = (
    "score_publication_result_template",
    "g9_gate_requirement",
    "placeholder_score_value_and_rank",
    "no_stage_or_final_total_release",
    "no_cross_subitem_leaderboard_release",
)


def build_rerun_report_contracts() -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for publication_contract in build_score_publication_result_contracts():
        formal_grade = publication_contract["formal_grade_result_template"]
        publication = publication_contract["score_publication_result_template"]
        subitem_id = str(publication_contract["subitem_id"])
        deterministic_key = str(formal_grade["deterministic_rerun_key"])
        contracts.append(
            {
                "subitem_id": subitem_id,
                "person_id": TEMPLATE_PERSON_ID,
                "deterministic_rerun_key_contract": {
                    "deterministic_rerun_key": deterministic_key,
                    "required_inputs": list(RERUN_REQUIRED_INPUTS),
                    "stable_sort_keys": ["subitem_id", "person_id", "deterministic_rerun_key"],
                    "runtime_state_inputs_allowed": False,
                    "source_lookup_inputs_allowed": False,
                    "publication_inputs_allowed": False,
                },
                "validator_contract": {
                    "required_checks": list(VALIDATOR_REQUIRED_CHECKS),
                    "validator_scope": "contract_template_only_no_business_publication",
                    "fails_if_stage_or_final_total_released": True,
                    "fails_if_cross_subitem_leaderboard_released": True,
                    "fails_if_person_specific_publication_claimed": True,
                },
                "impact_report_template": {
                    "sections": list(IMPACT_REPORT_SECTIONS),
                    "subitem_id": subitem_id,
                    "deterministic_rerun_key": deterministic_key,
                    "formal_grade": formal_grade["formal_grade"],
                    "candidate_value_is_placeholder": True,
                    "template_not_for_publication": True,
                },
                "publication_report_template": {
                    "sections": list(PUBLICATION_REPORT_SECTIONS),
                    "subitem_id": subitem_id,
                    "publication_gate": publication["publication_gate"],
                    "formal_score_value_is_placeholder": True,
                    "subitem_rank_is_placeholder": True,
                    "stage_or_final_total_table_released": False,
                    "cross_subitem_leaderboard_released": False,
                    "template_not_for_publication": True,
                },
                "source_publication_contract": publication_contract,
                "profile_status": "pilot_deterministic_rerun_report_contract_only",
                "template_not_for_scoring": True,
                "template_not_for_publication": True,
                "person_specific_evidence_included": False,
                "person_specific_formal_grade_result_included": False,
                "person_specific_score_publication_result_included": False,
                "source_lookup_performed": False,
                "g8_release_performed": False,
                "g9_publication_performed": False,
            }
        )
    return contracts


def build_contract_report() -> dict[str, Any]:
    contracts = build_rerun_report_contracts()
    subitem_ids = [contract["subitem_id"] for contract in contracts]
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "score_publication_contract_pr": SCORE_PUBLICATION_CONTRACT_PR,
        "score_publication_contract_merge_commit": SCORE_PUBLICATION_CONTRACT_MERGE_COMMIT,
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
            "current_phase": "epic5_deterministic_rerun_report_contract_package_ready",
            "active_epic": EPIC_ISSUE,
            "epic5_score_publication_result_contract_pr": SCORE_PUBLICATION_CONTRACT_PR,
            "epic5_score_publication_result_contract_merge_commit": SCORE_PUBLICATION_CONTRACT_MERGE_COMMIT,
            "epic5_deterministic_rerun_report_contract_ready": True,
            "positive_benefit_total": 1500,
            "deterministic_rerun_report_contract_count": len(contracts),
            "pilot_subitem_rerun_report_templates_selected": subitem_ids,
            "validator_contracts_built": True,
            "impact_report_templates_built": True,
            "publication_report_templates_built": True,
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
        "rerun_report_contracts": contracts,
        "rerun_report_contract_invariants": [
            "deterministic_key_reuses_formal_grade_template_key",
            "rerun_inputs_exclude_runtime_state_and_source_lookup",
            "validator_contract_blocks_person_specific_publication_claims",
            "impact_report_template_contains_formal_grade_boundary",
            "publication_report_template_contains_g9_requirement_without_publication_release",
            "stage_or_final_total_table_release_locked_false",
            "cross_subitem_leaderboard_release_locked_false",
        ],
        "blocked_outputs": [
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
        ],
        "next_required_work": "issue_311_rule_display_dictionary_externalization_or_non_destructive_governance",
    }


def render_rerun_report_md() -> str:
    report = build_contract_report()
    lines = [
        "# Epic5 Deterministic Rerun And Report Contract",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- score_publication_contract_pr: `#{report['score_publication_contract_pr']}`",
        f"- score_publication_contract_merge_commit: `{report['score_publication_contract_merge_commit']}`",
        "- This package defines rerun, validator, impact report, and publication report contracts only.",
        "",
        "## Rerun Report Templates",
        "",
    ]
    for contract in report["rerun_report_contracts"]:
        rerun = contract["deterministic_rerun_key_contract"]
        lines.append(
            f"- `{contract['subitem_id']}`: deterministic_rerun_key=`{rerun['deterministic_rerun_key']}`; "
            "validator_contract=`present`; impact_report_template=`present`; publication_report_template=`present`"
        )

    lines.extend(["", "## Rerun Report Contract Invariants", ""])
    for item in report["rerun_report_contract_invariants"]:
        lines.append(f"- `{item}`")

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

    parser = argparse.ArgumentParser(description="Build the Epic5 deterministic rerun and report contract package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--rerun-report-md", action="store_true")
    args = parser.parse_args(argv)

    if args.rerun_report_md:
        sys.stdout.write(render_rerun_report_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
