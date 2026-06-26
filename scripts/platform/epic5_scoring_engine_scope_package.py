from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PACKAGE_VERSION = "epic5-scoring-engine-boundary-scope-package-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
PREVIOUS_EPIC_ISSUE = 211
PREVIOUS_COMPLETED_PR = 310
PREVIOUS_COMPLETED_MERGE_COMMIT = "831aae51845763ddd2e8944b95e5397320aeff1b"
SUPPORTED_MODES = ("contract-report", "scope-md")


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "previous_epic_issue": PREVIOUS_EPIC_ISSUE,
        "previous_completed_pr": PREVIOUS_COMPLETED_PR,
        "previous_completed_merge_commit": PREVIOUS_COMPLETED_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_write_business_tables": True,
        "does_not_modify_score_standard": True,
        "does_not_modify_subitem_rule_sources": True,
        "current_state": {
            "current_phase": "epic5_boundary_scope_package_ready",
            "active_epic": EPIC_ISSUE,
            "active_epic_title": "Scoring_Engine_Cross_Subitem_Generalization",
            "positive_benefit_total": 1500,
            "former_active_cap_1440": "obsolete",
            "formal_evidence_released": True,
            "fifth_item_b_algorithm_released": True,
            "fifth_item_b_score_values_released": True,
            "fifth_item_b_ranking_released": True,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "epic5_boundary_scope_package_ready": True,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "i5b_capabilities_to_generalize": [
            "net_evidence_profile_to_formal_grade",
            "formal_grade_to_subitem_score_range",
            "deterministic_in_band_candidate_value",
            "g8_algorithm_release_gate_separated_from_g9_publication_gate",
            "no_person_specific_override",
            "impact_report_and_publication_report_contracts",
            "subitem_internal_ranking_without_stage_or_final_leaderboard",
            "versioned_rule_algorithm_display_and_publication_state",
        ],
        "must_remain_subitem_specific": [
            "evidence_trigger_terms",
            "positive_core_taxonomy",
            "negative_boundary_taxonomy",
            "adjacent_item_split_rules",
            "subitem_cap_and_weight",
            "historical_anchor_examples",
        ],
        "generic_schema_draft": [
            {
                "name": "subitem_profile",
                "purpose": "Describe a subitem's scoring cap, grade ladder, gates, and boundary policy.",
                "required_fields": [
                    "subitem_id",
                    "subitem_name",
                    "score_cap",
                    "grade_scale_version",
                    "algorithm_version",
                    "g8_gate_status",
                    "g9_publication_status",
                    "stage_or_final_total_release_allowed",
                ],
            },
            {
                "name": "evidence_profile",
                "purpose": "Normalize person/subitem evidence into positive, negative, confidence, and split signals.",
                "required_fields": [
                    "person_id",
                    "subitem_id",
                    "positive_signal_profile",
                    "negative_signal_profile",
                    "confidence",
                    "cross_item_split_signals",
                    "source_traceability_status",
                ],
            },
            {
                "name": "formal_grade_result",
                "purpose": "Map the evidence profile to a formal grade, range, and deterministic candidate value.",
                "required_fields": [
                    "person_id",
                    "subitem_id",
                    "formal_grade",
                    "score_range",
                    "candidate_value",
                    "algorithm_version",
                    "deterministic_rerun_key",
                    "manual_override_allowed",
                ],
            },
            {
                "name": "score_publication_result",
                "purpose": "Publish only gate-approved subitem values and subitem-internal ranking.",
                "required_fields": [
                    "person_id",
                    "subitem_id",
                    "formal_score_value",
                    "subitem_rank",
                    "publication_gate",
                    "publication_scope",
                    "stage_or_final_total_table_released",
                    "cross_subitem_leaderboard_released",
                ],
            },
        ],
        "pilot_subitem_candidates": [
            {
                "subitem": "第二项治国净收益",
                "purpose": "Test net-benefit evidence profile fields outside Fifth Item B.",
                "publication_allowed_in_this_package": False,
            },
            {
                "subitem": "第三项军事与边疆净收益",
                "purpose": "Test adjacent-item split and negative-boundary portability.",
                "publication_allowed_in_this_package": False,
            },
            {
                "subitem": "第六项关键历史决策能力",
                "purpose": "Test subitem cap/decomposition modeling after the 1500 total-plate decision.",
                "publication_allowed_in_this_package": False,
            },
        ],
        "g8_g9_reuse_rules": {
            "g8_per_subitem_algorithm_release_requires": [
                "subitem_profile_reviewed",
                "evidence_profile_to_grade_mapping_reviewed",
                "score_range_and_candidate_value_deterministic",
                "impact_report_without_formal_person_values",
                "no_person_specific_override_enforced",
            ],
            "g9_per_subitem_publication_allows": [
                "formal_person_values_for_that_subitem",
                "subitem_internal_ranking_for_that_subitem",
            ],
            "g9_per_subitem_publication_does_not_allow": [
                "stage_total_table",
                "final_total_table",
                "cross_subitem_leaderboard",
                "other_subitem_values_without_their_own_gate",
            ],
        },
        "generic_no_override_constraints": {
            "person_specific_override_allowed": False,
            "manual_final_grade_allowed": False,
            "manual_final_score_allowed": False,
            "override_policy": "algorithm_and_gate_outputs_only",
        },
        "allowed_scope": [
            "inventory_i5b_chain_for_reusable_interfaces",
            "define_cross_subitem_minimum_schema",
            "define_report_templates_without_new_scores",
            "select_pilot_subitem_candidates_without_publication",
            "define_g8_g9_reuse_and_leaderboard_boundaries",
            "define_integration_points_with_issue_311_dictionary_governance",
            "add_boundary_regression_tests",
        ],
        "prohibited_scope": [
            "new_subitem_formal_score_publication",
            "stage_or_final_total_table_publication",
            "cross_subitem_leaderboard_publication",
            "g10_destructive_cleanup",
            "source_document_passage_business_table_write",
            "evidence_cluster_anchor_relationship_business_table_write",
            "rule_display_dictionary_canonical_write",
            "epic_2_or_epic_3_entry",
        ],
        "followup_gate_boundaries": {
            "per_subitem_formal_algorithm_release": "requires_g8_style_gate_for_each_new_subitem",
            "per_subitem_score_publication": "requires_g9_style_gate_for_each_new_subitem",
            "stage_or_final_total_table": "requires_separate_total_table_publication_gate",
            "cross_subitem_leaderboard": "requires_separate_leaderboard_publication_gate",
            "rule_display_dictionary_canonical_write": "requires_separate_dictionary_write_gate_or_issue_311_pr",
            "destructive_cleanup": "blocked_until_g10",
            "source_documents_passages": "blocked_by_followup_gate",
            "evidence_clusters_anchors_relationships": "blocked_by_followup_gate",
            "epic_2_entry": "blocked_until_separate_ready_review",
            "epic_3_entry": "blocked_until_separate_ready_review",
        },
        "next_required_work": "epic5_minimum_interface_contract_after_boundary_review",
    }


def render_scope_md() -> str:
    report = build_contract_report()
    lines = [
        "# Epic5 Scoring Engine Boundary Scope Package",
        "",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- package_version: `{report['package_version']}`",
        f"- previous_completed_pr: `#{report['previous_completed_pr']}`",
        f"- previous_completed_merge_commit: `{report['previous_completed_merge_commit']}`",
        "- This package is offline and does not publish new scores or rankings.",
        "",
        "## Current State",
        "",
    ]
    for key, value in report["current_state"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")

    lines.extend(["", "## Capabilities To Generalize", ""])
    for item in report["i5b_capabilities_to_generalize"]:
        lines.append(f"- `{item}`")

    lines.extend(["", "## Generic Schema Draft", ""])
    for schema in report["generic_schema_draft"]:
        fields = ", ".join(f"`{field}`" for field in schema["required_fields"])
        lines.append(f"- `{schema['name']}`: {schema['purpose']} Required fields: {fields}.")

    lines.extend(["", "## Pilot Subitem Candidates", ""])
    for candidate in report["pilot_subitem_candidates"]:
        lines.append(
            f"- {candidate['subitem']}: {candidate['purpose']} "
            f"publication_allowed_in_this_package=`{str(candidate['publication_allowed_in_this_package']).lower()}`"
        )

    lines.extend(["", "## G8/G9 Reuse Rules", ""])
    for key, values in report["g8_g9_reuse_rules"].items():
        lines.append(f"- `{key}`:")
        for value in values:
            lines.append(f"  - `{value}`")

    lines.extend(["", "## Prohibited Scope", ""])
    for item in report["prohibited_scope"]:
        lines.append(f"- `{item}`")

    lines.extend(["", "## Follow-Up Gate Boundaries", ""])
    for key, value in report["followup_gate_boundaries"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the Epic5 scoring engine boundary scope package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--scope-md", action="store_true")
    args = parser.parse_args(argv)

    if args.scope_md:
        sys.stdout.write(render_scope_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
