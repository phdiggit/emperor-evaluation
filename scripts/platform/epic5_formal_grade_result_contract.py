from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.epic5_pilot_subitem_evidence_profile_contract import (  # noqa: E402
    TEMPLATE_PERSON_ID,
    build_evidence_profile_template,
)
from scripts.platform.epic5_pilot_subitem_profile_contract import (  # noqa: E402
    PILOT_PROFILE_DEFINITIONS,
    build_subitem_profile,
)
from scripts.shared.scoring_engine_contracts import (  # noqa: E402
    FormalGradeResult,
    ScoreRange,
    validate_interface_bundle,
)


PACKAGE_VERSION = "epic5-formal-grade-result-contract-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
EVIDENCE_PROFILE_CONTRACT_PR = 316
EVIDENCE_PROFILE_CONTRACT_MERGE_COMMIT = "b72bc06fdd30c6c59b3a5508f7553058deb7c102"
SUPPORTED_MODES = ("contract-report", "formal-grade-md")
TEMPLATE_FORMAL_GRADE = "__pilot_formal_grade_contract_template__"
TEMPLATE_DETERMINISTIC_RERUN_KEY_PREFIX = "epic5-formal-grade-contract-template"
SCORE_RANGE_POLICY = "contract_template_full_subitem_cap_range_no_publication_value"

FORMAL_GRADE_ALLOWED_VALUES = (
    "extreme_positive",
    "strong_positive",
    "moderate_positive",
    "weak_positive",
    "neutral_or_mixed",
    "weak_negative",
    "moderate_negative",
    "strong_negative",
    "extreme_negative",
)


def _definition_by_id(subitem_id: str) -> Mapping[str, Any]:
    for definition in PILOT_PROFILE_DEFINITIONS:
        if definition["subitem_id"] == subitem_id:
            return definition
    raise KeyError(f"unknown pilot subitem_id: {subitem_id}")


def build_formal_grade_result_template(subitem_id: str) -> FormalGradeResult:
    definition = _definition_by_id(subitem_id)
    subitem = build_subitem_profile(definition)
    return FormalGradeResult(
        person_id=TEMPLATE_PERSON_ID,
        subitem_id=subitem_id,
        formal_grade=TEMPLATE_FORMAL_GRADE,
        score_range=ScoreRange("0", subitem.score_cap),
        candidate_value="0",
        algorithm_version=subitem.algorithm_version,
        deterministic_rerun_key=f"{TEMPLATE_DETERMINISTIC_RERUN_KEY_PREFIX}:{subitem_id}:v1",
    )


def build_formal_grade_result_contracts() -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for definition in PILOT_PROFILE_DEFINITIONS:
        subitem_id = str(definition["subitem_id"])
        subitem = build_subitem_profile(definition)
        evidence = build_evidence_profile_template(subitem_id)
        formal_grade = build_formal_grade_result_template(subitem_id)
        bundle = validate_interface_bundle(subitem=subitem, evidence=evidence, formal_grade=formal_grade)
        formal_grade_template = dict(bundle["formal_grade_result"])
        formal_grade_template.update(
            {
                "formal_grade_allowed_values": list(FORMAL_GRADE_ALLOWED_VALUES),
                "score_range_policy": SCORE_RANGE_POLICY,
                "candidate_value_is_placeholder": True,
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
                "formal_grade_result_template": formal_grade_template,
                "publication_result": None,
                "profile_status": "pilot_formal_grade_result_contract_only",
                "template_not_for_scoring": True,
                "template_not_for_publication": True,
                "person_specific_evidence_included": False,
                "person_specific_formal_grade_result_included": False,
                "score_publication_result_included": False,
                "source_lookup_performed": False,
                "g8_release_performed": False,
                "g9_publication_performed": False,
            }
        )
    return contracts


def build_contract_report() -> dict[str, Any]:
    contracts = build_formal_grade_result_contracts()
    subitem_ids = [contract["subitem_id"] for contract in contracts]
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "evidence_profile_contract_pr": EVIDENCE_PROFILE_CONTRACT_PR,
        "evidence_profile_contract_merge_commit": EVIDENCE_PROFILE_CONTRACT_MERGE_COMMIT,
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
        "does_not_release_formal_grade_results_for_new_subitems": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "current_state": {
            "current_phase": "epic5_formal_grade_result_contract_package_ready",
            "active_epic": EPIC_ISSUE,
            "epic5_pilot_subitem_evidence_profile_contract_pr": EVIDENCE_PROFILE_CONTRACT_PR,
            "epic5_pilot_subitem_evidence_profile_contract_merge_commit": EVIDENCE_PROFILE_CONTRACT_MERGE_COMMIT,
            "epic5_formal_grade_result_contract_ready": True,
            "positive_benefit_total": 1500,
            "formal_grade_result_contract_count": len(contracts),
            "pilot_subitem_formal_grade_templates_selected": subitem_ids,
            "person_specific_evidence_profiles_built": False,
            "person_specific_formal_grade_results_built": False,
            "formal_grade_results_released_for_new_subitems": False,
            "score_publication_results_built": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "formal_grade_result_contracts": contracts,
        "formal_grade_contract_invariants": [
            "formal_grade_subitem_id_matches_pilot_subitem_profile",
            "formal_grade_person_id_matches_template_evidence_person_id",
            "formal_grade_algorithm_version_matches_subitem_profile",
            "score_range_stays_within_subitem_cap",
            "candidate_value_is_contract_placeholder_inside_score_range",
            "no_override_policy_locked_false",
            "score_publication_result_not_included",
            "stage_or_final_total_table_release_locked_false",
            "cross_subitem_leaderboard_release_locked_false",
        ],
        "blocked_outputs": [
            "person_specific_formal_grade_result",
            "score_publication_result",
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
        "next_required_work": "epic5_score_publication_result_contract_package",
    }


def render_formal_grade_md() -> str:
    report = build_contract_report()
    lines = [
        "# Epic5 Formal Grade Result Contract",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- evidence_profile_contract_pr: `#{report['evidence_profile_contract_pr']}`",
        f"- evidence_profile_contract_merge_commit: `{report['evidence_profile_contract_merge_commit']}`",
        "- This package defines formal grade result templates only; it does not publish scores.",
        "",
        "## Formal Grade Result Templates",
        "",
    ]
    for contract in report["formal_grade_result_contracts"]:
        template = contract["formal_grade_result_template"]
        score_range = template["score_range"]
        lines.append(
            f"- `{contract['subitem_id']}`: formal_grade=`{template['formal_grade']}`; "
            f"range=`{score_range['lower']}..{score_range['upper']}`; "
            f"candidate_value_is_placeholder=`true`; score_publication_result_included=`false`"
        )

    lines.extend(["", "## Formal Grade Contract Invariants", ""])
    for item in report["formal_grade_contract_invariants"]:
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

    parser = argparse.ArgumentParser(description="Build the Epic5 formal grade result contract package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--formal-grade-md", action="store_true")
    args = parser.parse_args(argv)

    if args.formal_grade_md:
        sys.stdout.write(render_formal_grade_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
