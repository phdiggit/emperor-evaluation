from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.epic5_formal_grade_result_contract import (  # noqa: E402
    TEMPLATE_PERSON_ID,
    build_formal_grade_result_template,
)
from scripts.platform.epic5_pilot_subitem_evidence_profile_contract import build_evidence_profile_template  # noqa: E402
from scripts.platform.epic5_pilot_subitem_profile_contract import (  # noqa: E402
    PILOT_PROFILE_DEFINITIONS,
    build_subitem_profile,
)
from scripts.shared.scoring_engine_contracts import ScorePublicationResult, validate_interface_bundle  # noqa: E402


PACKAGE_VERSION = "epic5-score-publication-result-contract-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
FORMAL_GRADE_CONTRACT_PR = 317
FORMAL_GRADE_CONTRACT_MERGE_COMMIT = "2f7e8b0b0954eb322600019791a9255718ff6649"
SUPPORTED_MODES = ("contract-report", "publication-md")
TEMPLATE_PUBLICATION_SCOPE = "__pilot_score_publication_contract_template__"
TEMPLATE_PUBLICATION_GATE = "G9"
TEMPLATE_SUBITEM_RANK = 1
PUBLICATION_BOUNDARY_POLICY = "contract_template_requires_future_per_subitem_g9_before_real_publication"


def _definition_by_id(subitem_id: str) -> Mapping[str, Any]:
    for definition in PILOT_PROFILE_DEFINITIONS:
        if definition["subitem_id"] == subitem_id:
            return definition
    raise KeyError(f"unknown pilot subitem_id: {subitem_id}")


def build_score_publication_result_template(subitem_id: str) -> ScorePublicationResult:
    _definition_by_id(subitem_id)
    formal_grade = build_formal_grade_result_template(subitem_id)
    return ScorePublicationResult(
        person_id=TEMPLATE_PERSON_ID,
        subitem_id=subitem_id,
        formal_score_value=formal_grade.candidate_value,
        subitem_rank=TEMPLATE_SUBITEM_RANK,
        publication_gate=TEMPLATE_PUBLICATION_GATE,
        publication_scope=TEMPLATE_PUBLICATION_SCOPE,
        stage_or_final_total_table_released=False,
        cross_subitem_leaderboard_released=False,
    )


def build_score_publication_result_contracts() -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for definition in PILOT_PROFILE_DEFINITIONS:
        subitem_id = str(definition["subitem_id"])
        subitem = build_subitem_profile(definition)
        evidence = build_evidence_profile_template(subitem_id)
        formal_grade = build_formal_grade_result_template(subitem_id)
        publication = build_score_publication_result_template(subitem_id)
        bundle = validate_interface_bundle(
            subitem=subitem,
            evidence=evidence,
            formal_grade=formal_grade,
            publication=publication,
        )
        publication_template = dict(bundle["publication_result"])
        publication_template.update(
            {
                "formal_score_value_is_placeholder": True,
                "subitem_rank_is_placeholder": True,
                "publication_boundary_policy": PUBLICATION_BOUNDARY_POLICY,
                "template_not_for_publication": True,
                "template_not_for_person_scoring": True,
            }
        )
        contracts.append(
            {
                "subitem_id": subitem_id,
                "person_id": TEMPLATE_PERSON_ID,
                "subitem_profile": bundle["subitem_profile"],
                "evidence_profile_template": bundle["evidence_profile"],
                "formal_grade_result_template": bundle["formal_grade_result"],
                "score_publication_result_template": publication_template,
                "profile_status": "pilot_score_publication_result_contract_only",
                "template_not_for_scoring": True,
                "template_not_for_publication": True,
                "person_specific_evidence_included": False,
                "person_specific_formal_grade_result_included": False,
                "person_specific_score_publication_result_included": False,
                "source_lookup_performed": False,
                "g8_release_performed": False,
                "g9_publication_performed": False,
                "stage_or_final_total_table_released": False,
                "cross_subitem_leaderboard_released": False,
            }
        )
    return contracts


def build_contract_report() -> dict[str, Any]:
    contracts = build_score_publication_result_contracts()
    subitem_ids = [contract["subitem_id"] for contract in contracts]
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "formal_grade_contract_pr": FORMAL_GRADE_CONTRACT_PR,
        "formal_grade_contract_merge_commit": FORMAL_GRADE_CONTRACT_MERGE_COMMIT,
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
            "current_phase": "epic5_score_publication_result_contract_package_ready",
            "active_epic": EPIC_ISSUE,
            "epic5_formal_grade_result_contract_pr": FORMAL_GRADE_CONTRACT_PR,
            "epic5_formal_grade_result_contract_merge_commit": FORMAL_GRADE_CONTRACT_MERGE_COMMIT,
            "epic5_score_publication_result_contract_ready": True,
            "positive_benefit_total": 1500,
            "score_publication_result_contract_count": len(contracts),
            "pilot_subitem_score_publication_templates_selected": subitem_ids,
            "person_specific_evidence_profiles_built": False,
            "person_specific_formal_grade_results_built": False,
            "person_specific_score_publication_results_built": False,
            "formal_grade_results_released_for_new_subitems": False,
            "score_publication_result_templates_built": True,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "score_publication_result_contracts": contracts,
        "score_publication_contract_invariants": [
            "publication_person_id_matches_formal_grade_template",
            "publication_subitem_id_matches_formal_grade_and_subitem_profile",
            "publication_gate_is_g9_contract_requirement",
            "formal_score_value_equals_deterministic_candidate_placeholder",
            "subitem_rank_is_positive_placeholder",
            "stage_or_final_total_table_release_locked_false",
            "cross_subitem_leaderboard_release_locked_false",
            "person_specific_publication_result_not_included",
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
        "next_required_work": "epic5_deterministic_rerun_and_report_contract_package",
    }


def render_publication_md() -> str:
    report = build_contract_report()
    lines = [
        "# Epic5 Score Publication Result Contract",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- formal_grade_contract_pr: `#{report['formal_grade_contract_pr']}`",
        f"- formal_grade_contract_merge_commit: `{report['formal_grade_contract_merge_commit']}`",
        "- This package defines score publication result templates only; it does not publish scores.",
        "",
        "## Score Publication Result Templates",
        "",
    ]
    for contract in report["score_publication_result_contracts"]:
        template = contract["score_publication_result_template"]
        lines.append(
            f"- `{contract['subitem_id']}`: publication_gate=`{template['publication_gate']}`; "
            f"formal_score_value_is_placeholder=`true`; subitem_rank_is_placeholder=`true`; "
            "stage_or_final_total_table_released=`false`; cross_subitem_leaderboard_released=`false`"
        )

    lines.extend(["", "## Score Publication Contract Invariants", ""])
    for item in report["score_publication_contract_invariants"]:
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

    parser = argparse.ArgumentParser(description="Build the Epic5 score publication result contract package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--publication-md", action="store_true")
    args = parser.parse_args(argv)

    if args.publication_md:
        sys.stdout.write(render_publication_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
