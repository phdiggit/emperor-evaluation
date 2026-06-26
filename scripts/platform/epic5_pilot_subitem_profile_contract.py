from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.shared.scoring_engine_contracts import SubitemProfile  # noqa: E402


PACKAGE_VERSION = "epic5-pilot-subitem-profile-contract-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
INTERFACE_PR = 314
INTERFACE_MERGE_COMMIT = "e64f9f9089739555823cb9268d283e5632abc893"
SUPPORTED_MODES = ("contract-report", "profiles-md")
GRADE_SCALE_VERSION = "score-standard-v3.2-positive-total-1500"
ALGORITHM_VERSION = "epic5-pilot-profile-contract-only-v1"
G8_GATE_STATUS = "not_requested_profile_contract_only"
G9_PUBLICATION_STATUS = "blocked_profile_contract_only"


PILOT_PROFILE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "subitem_id": "second_governance_net_benefit",
        "subitem_name": "第二项治国净收益",
        "score_cap": 460,
        "source_rule_anchor": "docs/皇帝综合评价体系评分标准.md#4-第二项治国净收益460",
        "profile_contract_focus": "Net-benefit governance profile outside Fifth Item B.",
        "component_cap_profile": [
            {"component_id": "A", "component_name": "制度建设", "score_cap": 140},
            {"component_id": "B", "component_name": "行政治理", "score_cap": 160},
            {"component_id": "C", "component_name": "民生经济", "score_cap": 110},
            {"component_id": "D", "component_name": "可持续性", "score_cap": 50},
        ],
        "cross_item_boundary_notes": [
            "夺权过程归第一项。",
            "对外军事安全收益归第三项。",
            "关键节点判断能力本身归第六项。",
        ],
    },
    {
        "subitem_id": "third_military_border_net_benefit",
        "subitem_name": "第三项军事与边疆净收益",
        "score_cap": 250,
        "source_rule_anchor": "docs/皇帝综合评价体系评分标准.md#5-第三项军事与边疆净收益250",
        "profile_contract_focus": "Military and frontier net-benefit profile with adjacent-item split checks.",
        "component_cap_profile": [
            {"component_id": "A", "component_name": "战略安全收益", "score_cap": 80},
            {"component_id": "B", "component_name": "边疆控制净收益", "score_cap": 80},
            {"component_id": "C", "component_name": "军事体系有效性", "score_cap": 50},
            {"component_id": "D", "component_name": "军事成本收益比", "score_cap": 40},
        ],
        "cross_item_boundary_notes": [
            "创业战争归第一项。",
            "民生承受的最终生活结果归第二项C。",
            "边疆地区文明认同和文化吸纳归第四项A。",
        ],
    },
    {
        "subitem_id": "sixth_key_decision_capacity",
        "subitem_name": "第六项关键历史决策能力",
        "score_cap": 180,
        "source_rule_anchor": "docs/皇帝综合评价体系评分标准.md#8-第六项关键历史决策能力180",
        "profile_contract_focus": "Decision-capacity profile carrying the Epic4 1500 total-plate supplement.",
        "component_cap_profile": [
            {"component_id": "A", "component_name": "重大节点判断", "score_cap": 60},
            {"component_id": "B", "component_name": "风险控制与止损", "score_cap": 50},
            {"component_id": "C", "component_name": "长期战略眼光", "score_cap": 70},
        ],
        "cross_item_boundary_notes": [
            "具体制度建设成果归第二项A。",
            "具体军事收益归第三项。",
            "个人认知素质的一般表现归第五项E。",
        ],
    },
]


def _component_cap_sum(definition: Mapping[str, Any]) -> int:
    return sum(int(component["score_cap"]) for component in definition["component_cap_profile"])


def build_subitem_profile(definition: Mapping[str, Any]) -> SubitemProfile:
    return SubitemProfile(
        subitem_id=str(definition["subitem_id"]),
        subitem_name=str(definition["subitem_name"]),
        score_cap=definition["score_cap"],
        grade_scale_version=GRADE_SCALE_VERSION,
        algorithm_version=ALGORITHM_VERSION,
        g8_gate_status=G8_GATE_STATUS,
        g9_publication_status=G9_PUBLICATION_STATUS,
        stage_or_final_total_release_allowed=False,
        cross_subitem_leaderboard_release_allowed=False,
    )


def build_pilot_subitem_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for definition in PILOT_PROFILE_DEFINITIONS:
        if _component_cap_sum(definition) != int(definition["score_cap"]):
            raise ValueError(f"component caps do not sum to score_cap: {definition['subitem_id']}")

        profile = build_subitem_profile(definition).to_dict()
        profile.update(
            {
                "profile_status": "pilot_profile_contract_only",
                "publication_allowed_in_this_package": False,
                "evidence_profile_contract_included": False,
                "formal_grade_result_included": False,
                "score_publication_result_included": False,
                "component_cap_profile": list(definition["component_cap_profile"]),
                "component_cap_sum": str(_component_cap_sum(definition)),
                "source_rule_anchor": definition["source_rule_anchor"],
                "profile_contract_focus": definition["profile_contract_focus"],
                "cross_item_boundary_notes": list(definition["cross_item_boundary_notes"]),
            }
        )
        profiles.append(profile)
    return profiles


def build_contract_report() -> dict[str, Any]:
    profiles = build_pilot_subitem_profiles()
    profile_ids = [profile["subitem_id"] for profile in profiles]
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "interface_pr": INTERFACE_PR,
        "interface_merge_commit": INTERFACE_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_write_business_tables": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "does_not_release_formal_grade_results": True,
        "does_not_build_evidence_profiles": True,
        "current_state": {
            "current_phase": "epic5_pilot_subitem_profile_contract_package_ready",
            "active_epic": EPIC_ISSUE,
            "epic5_interface_contract_pr": INTERFACE_PR,
            "epic5_interface_contract_merge_commit": INTERFACE_MERGE_COMMIT,
            "epic5_pilot_subitem_profile_contract_ready": True,
            "positive_benefit_total": 1500,
            "pilot_profile_count": len(profiles),
            "pilot_subitem_profiles_selected": profile_ids,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "pilot_subitem_profiles": profiles,
        "profile_contract_invariants": [
            "score_cap_matches_active_1500_scoring_standard",
            "component_caps_sum_to_subitem_score_cap",
            "subitem_profile_stage_or_final_total_release_locked_false",
            "subitem_profile_cross_subitem_leaderboard_release_locked_false",
            "g8_gate_not_requested_for_profile_contract_only",
            "g9_publication_blocked_for_profile_contract_only",
            "no_evidence_profile_formal_grade_or_publication_result_included",
        ],
        "blocked_outputs": [
            "new_subitem_formal_scores",
            "new_subitem_formal_rankings",
            "stage_total_table",
            "final_total_table",
            "cross_subitem_leaderboard",
            "evidence_profile_contract_package_claim",
            "per_subitem_g8_algorithm_release",
            "per_subitem_g9_publication",
            "rule_display_dictionary_canonical_write",
            "source_document_passage_business_table_write",
            "evidence_cluster_anchor_relationship_business_table_write",
            "g10_destructive_cleanup",
            "epic_2_or_epic_3_entry",
        ],
        "next_required_work": "epic5_pilot_subitem_evidence_profile_contract_package",
    }


def render_profiles_md() -> str:
    report = build_contract_report()
    lines = [
        "# Epic5 Pilot Subitem Profile Contract",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- interface_pr: `#{report['interface_pr']}`",
        f"- interface_merge_commit: `{report['interface_merge_commit']}`",
        "- This package defines pilot subitem profiles only; it does not publish scores.",
        "",
        "## Pilot Profiles",
        "",
    ]
    for profile in report["pilot_subitem_profiles"]:
        components = ", ".join(
            f"{component['component_id']}{component['score_cap']}"
            for component in profile["component_cap_profile"]
        )
        lines.append(
            f"- `{profile['subitem_id']}` {profile['subitem_name']}: "
            f"score_cap=`{profile['score_cap']}`, components=`{components}`, "
            "publication_allowed_in_this_package=`false`"
        )

    lines.extend(["", "## Profile Contract Invariants", ""])
    for item in report["profile_contract_invariants"]:
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

    parser = argparse.ArgumentParser(description="Build the Epic5 pilot subitem profile contract package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--profiles-md", action="store_true")
    args = parser.parse_args(argv)

    if args.profiles_md:
        sys.stdout.write(render_profiles_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
