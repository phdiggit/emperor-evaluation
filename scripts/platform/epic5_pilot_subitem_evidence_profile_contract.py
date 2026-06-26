from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.epic5_pilot_subitem_profile_contract import (  # noqa: E402
    PILOT_PROFILE_DEFINITIONS,
    build_subitem_profile,
)
from scripts.shared.scoring_engine_contracts import EvidenceProfile  # noqa: E402


PACKAGE_VERSION = "epic5-pilot-subitem-evidence-profile-contract-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
PROFILE_CONTRACT_PR = 315
PROFILE_CONTRACT_MERGE_COMMIT = "af12b0a5792539220244449c6ac013b311791695"
SUPPORTED_MODES = ("contract-report", "evidence-md")
TEMPLATE_PERSON_ID = "__pilot_contract_template__"
TEMPLATE_CONFIDENCE = "contract_template_no_person_confidence"
TEMPLATE_SOURCE_TRACEABILITY_STATUS = "contract_template_no_source_lookup"


EVIDENCE_CONTRACT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "second_governance_net_benefit": {
        "positive_signal_groups": [
            {
                "group_id": "institutional_benefit",
                "component_ids": ["A"],
                "required_fields": ["institutional_change_type", "operation_quality", "duration_scope"],
            },
            {
                "group_id": "administrative_benefit",
                "component_ids": ["B"],
                "required_fields": ["bureaucratic_quality", "correction_signal", "execution_signal"],
            },
            {
                "group_id": "livelihood_economic_benefit",
                "component_ids": ["C"],
                "required_fields": ["livelihood_signal", "fiscal_signal", "economic_signal"],
            },
            {
                "group_id": "succession_sustainability_benefit",
                "component_ids": ["D"],
                "required_fields": ["institutional_resilience", "social_resilience", "handoff_stability"],
            },
        ],
        "negative_signal_groups": [
            "institutional_damage",
            "administrative_failure",
            "livelihood_or_fiscal_pressure",
            "succession_fragility",
        ],
        "cross_item_split_signals": [
            "power_acquisition_process_routes_to_first_item",
            "military_security_result_routes_to_third_item",
            "key_decision_capacity_routes_to_sixth_item",
            "long_term_structural_disaster_routes_to_seventh_item",
        ],
    },
    "third_military_border_net_benefit": {
        "positive_signal_groups": [
            {
                "group_id": "strategic_security_benefit",
                "component_ids": ["A"],
                "required_fields": ["threat_reduction", "security_boundary", "strategic_depth"],
            },
            {
                "group_id": "frontier_control_benefit",
                "component_ids": ["B"],
                "required_fields": ["control_durability", "frontier_governance", "borderland_stability"],
            },
            {
                "group_id": "military_system_effectiveness",
                "component_ids": ["C"],
                "required_fields": ["command_system", "force_generation", "operational_learning"],
            },
            {
                "group_id": "military_cost_benefit",
                "component_ids": ["D"],
                "required_fields": ["cost_level", "benefit_durability", "civilian_burden_split"],
            },
        ],
        "negative_signal_groups": [
            "strategic_overextension",
            "frontier_control_failure",
            "military_system_damage",
            "disproportionate_military_cost",
        ],
        "cross_item_split_signals": [
            "founding_war_routes_to_first_item",
            "livelihood_result_routes_to_second_item_c",
            "civilizational_integration_routes_to_fourth_item_a",
            "long_term_structural_disaster_routes_to_seventh_item",
        ],
    },
    "sixth_key_decision_capacity": {
        "positive_signal_groups": [
            {
                "group_id": "major_node_judgment",
                "component_ids": ["A"],
                "required_fields": ["timing_judgment", "direction_judgment", "priority_judgment"],
            },
            {
                "group_id": "risk_control_and_stop_loss",
                "component_ids": ["B"],
                "required_fields": ["risk_detection", "loss_containment", "course_correction"],
            },
            {
                "group_id": "long_term_strategic_vision",
                "component_ids": ["C"],
                "required_fields": ["multi_generation_effect", "strategic_tradeoff", "path_dependency_awareness"],
            },
        ],
        "negative_signal_groups": [
            "major_node_misjudgment",
            "risk_amplification",
            "missed_stop_loss_window",
            "strategic_short_sightedness",
        ],
        "cross_item_split_signals": [
            "specific_institutional_outcome_routes_to_second_item_a",
            "specific_military_outcome_routes_to_third_item",
            "general_cognitive_trait_routes_to_fifth_item_e",
            "long_term_structural_disaster_routes_to_seventh_item",
        ],
    },
}


REQUIRED_SIGNAL_FIELDS = [
    "signal_group_id",
    "component_ids",
    "claim_summary",
    "source_traceability_status",
    "cross_item_split_signal",
    "confidence",
]


def _definition_by_id(subitem_id: str) -> Mapping[str, Any]:
    for definition in PILOT_PROFILE_DEFINITIONS:
        if definition["subitem_id"] == subitem_id:
            return definition
    raise KeyError(f"unknown pilot subitem_id: {subitem_id}")


def build_evidence_profile_template(subitem_id: str) -> EvidenceProfile:
    definition = _definition_by_id(subitem_id)
    contract = EVIDENCE_CONTRACT_DEFINITIONS[subitem_id]
    positive_signal_profile = {
        "schema_version": PACKAGE_VERSION,
        "schema_only": True,
        "template_not_for_scoring": True,
        "subitem_score_cap": definition["score_cap"],
        "required_signal_fields": list(REQUIRED_SIGNAL_FIELDS),
        "positive_signal_groups": list(contract["positive_signal_groups"]),
    }
    negative_signal_profile = {
        "schema_version": PACKAGE_VERSION,
        "schema_only": True,
        "template_not_for_scoring": True,
        "subitem_score_cap": definition["score_cap"],
        "negative_signal_groups": list(contract["negative_signal_groups"]),
        "negative_boundary_policy": "negative signals remain profile inputs only until a later formal-grade contract",
    }
    return EvidenceProfile(
        person_id=TEMPLATE_PERSON_ID,
        subitem_id=subitem_id,
        positive_signal_profile=positive_signal_profile,
        negative_signal_profile=negative_signal_profile,
        confidence=TEMPLATE_CONFIDENCE,
        cross_item_split_signals=tuple(contract["cross_item_split_signals"]),
        source_traceability_status=TEMPLATE_SOURCE_TRACEABILITY_STATUS,
    )


def build_evidence_profile_contracts() -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for definition in PILOT_PROFILE_DEFINITIONS:
        subitem = build_subitem_profile(definition)
        evidence = build_evidence_profile_template(str(definition["subitem_id"]))
        if evidence.subitem_id != subitem.subitem_id:
            raise ValueError(f"evidence template subitem_id mismatch: {definition['subitem_id']}")
        template = evidence.to_dict()
        template.update(
            {
                "subitem_profile": subitem.to_dict(),
                "profile_status": "pilot_evidence_profile_contract_only",
                "template_not_for_scoring": True,
                "person_specific_evidence_included": False,
                "source_lookup_performed": False,
                "formal_grade_result_included": False,
                "score_publication_result_included": False,
            }
        )
        contracts.append(template)
    return contracts


def build_contract_report() -> dict[str, Any]:
    contracts = build_evidence_profile_contracts()
    subitem_ids = [contract["subitem_id"] for contract in contracts]
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "profile_contract_pr": PROFILE_CONTRACT_PR,
        "profile_contract_merge_commit": PROFILE_CONTRACT_MERGE_COMMIT,
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
        "does_not_release_formal_grade_results": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "current_state": {
            "current_phase": "epic5_pilot_subitem_evidence_profile_contract_package_ready",
            "active_epic": EPIC_ISSUE,
            "epic5_pilot_subitem_profile_contract_pr": PROFILE_CONTRACT_PR,
            "epic5_pilot_subitem_profile_contract_merge_commit": PROFILE_CONTRACT_MERGE_COMMIT,
            "epic5_pilot_subitem_evidence_profile_contract_ready": True,
            "positive_benefit_total": 1500,
            "evidence_profile_contract_count": len(contracts),
            "pilot_subitem_evidence_profiles_selected": subitem_ids,
            "person_specific_evidence_profiles_built": False,
            "formal_grade_results_released_for_new_subitems": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "evidence_profile_contracts": contracts,
        "evidence_contract_invariants": [
            "evidence_profile_subitem_id_matches_pilot_subitem_profile",
            "template_person_id_is_not_a_real_person",
            "positive_signal_profile_is_schema_only",
            "negative_signal_profile_is_schema_only",
            "cross_item_split_signals_are_required_before_formal_grade_mapping",
            "source_traceability_status_is_contract_template_only",
            "no_formal_grade_or_score_publication_result_included",
        ],
        "blocked_outputs": [
            "person_specific_evidence_profiles",
            "source_lookup_or_sourcepack_claim",
            "formal_grade_result",
            "score_publication_result",
            "new_subitem_formal_scores",
            "new_subitem_formal_rankings",
            "stage_total_table",
            "final_total_table",
            "cross_subitem_leaderboard",
            "source_document_passage_business_table_write",
            "evidence_cluster_anchor_relationship_business_table_write",
            "rule_display_dictionary_canonical_write",
            "g10_destructive_cleanup",
            "epic_2_or_epic_3_entry",
        ],
        "next_required_work": "epic5_formal_grade_result_contract_package",
    }


def render_evidence_md() -> str:
    report = build_contract_report()
    lines = [
        "# Epic5 Pilot Subitem Evidence Profile Contract",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- profile_contract_pr: `#{report['profile_contract_pr']}`",
        f"- profile_contract_merge_commit: `{report['profile_contract_merge_commit']}`",
        "- This package defines evidence profile contracts only; it does not build person evidence or publish scores.",
        "",
        "## Evidence Profile Contracts",
        "",
    ]
    for contract in report["evidence_profile_contracts"]:
        positive_groups = ", ".join(
            group["group_id"] for group in contract["positive_signal_profile"]["positive_signal_groups"]
        )
        negative_groups = ", ".join(contract["negative_signal_profile"]["negative_signal_groups"])
        lines.append(
            f"- `{contract['subitem_id']}`: positive_groups=`{positive_groups}`; "
            f"negative_groups=`{negative_groups}`; template_not_for_scoring=`true`"
        )

    lines.extend(["", "## Evidence Contract Invariants", ""])
    for item in report["evidence_contract_invariants"]:
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

    parser = argparse.ArgumentParser(description="Build the Epic5 pilot subitem evidence profile contract package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--evidence-md", action="store_true")
    args = parser.parse_args(argv)

    if args.evidence_md:
        sys.stdout.write(render_evidence_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
