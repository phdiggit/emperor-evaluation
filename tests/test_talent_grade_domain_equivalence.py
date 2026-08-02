from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.evaluation.talent_grade_domain_equivalence import (
    assess_domain_historic_path,
    assess_military_talent_grade_shadow,
    validate_campaign_registry,
)


ROOT = Path(__file__).resolve().parents[1]


def _achievement(
    key: str,
    scale: str,
    *,
    responsibility_role: str = "exclusive",
    consequence_basis: str = "regional_theater_control",
    **extra: object,
) -> dict[str, object]:
    return {
        "achievement_ref": f"ACH-{key}",
        "independent_key": key,
        "scale": scale,
        "responsibility_role": responsibility_role,
        "result": "implemented_positive",
        "consequence_basis": consequence_basis,
        "progress_level": "significant",
        "contribution_types": ["implementation_lead"],
        **(
            {
                "combat_difficulty": "D3",
                "settlement_scope": (
                    "person_campaign_subresult"
                    if responsibility_role == "principal_commander"
                    else "ruler_campaign_parent"
                ),
            }
            if responsibility_role in {"commander_in_chief", "principal_commander"}
            else {}
        ),
        **extra,
    }


def test_v11_policy_makes_domain_paths_equivalent_without_common_legacy_gate() -> None:
    policy = yaml.safe_load(
        (ROOT / "config/talent-grade-v11-domain-equivalent-historic.yml").read_text(
            encoding="utf-8"
        )
    )

    assert policy["status"] == "current_shadow_policy"
    assert policy["principles"]["cross_stage_legacy_is_not_a_common_requirement"] is True
    assert policy["principles"]["domain_paths_operationalize_historic_height"] is True
    assert policy["principles"]["separate_unstructured_height_gate"] is False
    assert policy["responsibility_roles"]["military"] == {
        "commander_in_chief": "主帅",
        "principal_commander": "主将",
        "participant": "从攻",
        "not_in_command_chain": "不在军事指挥链",
    }
    assert policy["responsibility_roles"]["civil_governance"] == {
        "exclusive": "独占",
        "lead": "主导",
        "participant": "参与",
    }
    assert policy["historic_paths"]["military"]["strategic_weights"] == {
        "A": 1,
        "S-": 2,
        "S": 3,
        "S+": 4,
    }
    assert policy["top_fallback"]["military_paths"] == [
        "stable_s_plus_at_d2_or_higher",
        "s_minus_or_s_at_d3_or_higher_with_stability_second_a_d2_or_method",
        "two_s_minus_or_higher_at_d2_or_higher_with_one_stable",
    ]
    assert (
        policy["historic_paths"]["civil_governance"]["repeated_structural_path"]
        ["minimum_independent_significant_or_higher_results"]
        == 3
    )
    assert policy["historic_paths"]["civil_governance"]["counted_value_directions"] == [
        "positive"
    ]
    assert policy["principles"]["governance_scale_is_reach_not_progress_or_grade"] is True
    assert (
        policy["historic_paths"]["culture_and_scholarship"]
        ["civilization_foundational_single_work_path"]
        ["requires_personally_authored_or_finalized"]
        is True
    )


def test_military_sustained_portfolio_accepts_two_s_plus_one_a() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement("A", "national", campaign_tier="S", responsibility_role="commander_in_chief", consequence_basis="state_conquest"),
            _achievement(
                "B",
                "national",
                campaign_tier="S",
                responsibility_role="principal_commander",
                consequence_basis="national_war_outcome",
            ),
            _achievement("C", "regional", campaign_tier="A", responsibility_role="principal_commander"),
        ],
    )

    assert result["historic_fact_path_status"] == "eligible"
    assert result["matched_path"] == "military_sustained_strategic_portfolio"
    assert result["counts"]["strategic_weight"] == 7


def test_military_sustained_portfolio_accepts_one_s_two_s_minus() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement(
                "decisive",
                "national",
                campaign_tier="S",
                responsibility_role="commander_in_chief",
                decisive=True,
            ),
            _achievement(
                "north",
                "national",
                campaign_tier="S-",
                responsibility_role="commander_in_chief",
            ),
            _achievement(
                "east",
                "national",
                campaign_tier="S-",
                responsibility_role="commander_in_chief",
            ),
        ],
    )

    assert result["historic_fact_path_status"] == "eligible"
    assert result["matched_path"] == "military_sustained_strategic_portfolio"
    assert result["counts"]["strategic_weight"] == 7


def test_one_decisive_s_plus_and_one_a_establish_historic_path() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement(
                "SPLUS",
                "era_shaping",
                campaign_tier="S+",
                responsibility_role="commander_in_chief",
                consequence_basis="unification",
                decisive=True,
            ),
            _achievement(
                "A",
                "regional",
                campaign_tier="A",
                responsibility_role="principal_commander",
            ),
        ],
    )

    assert result["historic_fact_path_status"] == "eligible"
    assert result["matched_path"] == "military_peak_pair"
    assert result["matched_independent_keys"] == ["SPLUS", "A"]


def test_s_plus_without_decisiveness_or_second_a_is_not_historic() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement(
                "SPLUS",
                "era_shaping",
                campaign_tier="S+",
                responsibility_role="commander_in_chief",
                consequence_basis="unification",
            )
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"
    assert result["counts"]["s_plus"] == 1


def test_two_exceptional_main_command_s_campaigns_can_pass_alone() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement(
                "A", "national", campaign_tier="S", responsibility_role="commander_in_chief", consequence_basis="state_conquest", decisive=True
            ),
            _achievement(
                "B", "era_shaping", campaign_tier="S+", responsibility_role="principal_commander", consequence_basis="unification", decisive=True
            ),
        ],
    )

    assert result["matched_path"] == "military_peak_pair"


def test_clear_military_success_survives_separately_recorded_coordination_cost() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement("A", "national", campaign_tier="S", responsibility_role="commander_in_chief", consequence_basis="national_war_outcome"),
            {
                **_achievement(
                    "B", "national", campaign_tier="S", responsibility_role="principal_commander", consequence_basis="state_conquest", decisive=True
                ),
                "result": "implemented_mixed",
                "positive_result_preserved": True,
                "value_judgment": {
                    "comparison_basis": "inferred_prior_state",
                    "baseline_fact_refs": [],
                    "overall_direction": "positive",
                    "overall_magnitude": "structural",
                    "axes": {
                        "productivity_livelihood": {
                            "direction": "not_established",
                            "magnitude": "not_established",
                            "basis_fact_refs": [],
                            "basis": "",
                        },
                        "civilization_institutions": {
                            "direction": "positive",
                            "magnitude": "structural",
                            "basis_fact_refs": ["DNMAT-TEST"],
                            "basis": "全国律令投入运行。",
                        },
                        "state_people_security": {
                            "direction": "positive",
                            "magnitude": "significant",
                            "basis_fact_refs": ["DNMAT-TEST"],
                            "basis": "司法秩序获得制度支持。",
                        },
                        "culture_education_thought": {
                            "direction": "not_established",
                            "magnitude": "not_established",
                            "basis_fact_refs": [],
                            "basis": "",
                        },
                    },
                    "effect_horizon": "cross_stage",
                    "basis": "基线：旧有律令体系尚未形成该运行结果；变化：新律令颁行天下；结果：律令已经实际施用。",
                },
            },
            _achievement("C", "regional", campaign_tier="A", responsibility_role="principal_commander"),
        ],
    )

    assert result["matched_path"] == "military_sustained_strategic_portfolio"


def test_mixed_result_without_preserved_professional_success_does_not_count() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement("A", "national", campaign_tier="S", responsibility_role="commander_in_chief", consequence_basis="national_war_outcome"),
            {
                **_achievement("B", "national", campaign_tier="S", responsibility_role="principal_commander", consequence_basis="state_conquest"),
                "result": "implemented_mixed",
                "positive_result_preserved": False,
            },
            _achievement("C", "regional", campaign_tier="A", responsibility_role="principal_commander"),
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"


def test_two_s_campaigns_need_explicit_decisiveness_for_exception() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement("A", "national", campaign_tier="S", responsibility_role="commander_in_chief", consequence_basis="state_conquest"),
            _achievement("B", "national", campaign_tier="S", responsibility_role="principal_commander", consequence_basis="unification"),
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"


def test_two_ordinary_s_campaigns_do_not_pass_exception_path() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement(
                "A",
                "national",
                campaign_tier="S",
                responsibility_role="principal_commander",
                consequence_basis="national_war_outcome",
            ),
            _achievement(
                "B",
                "national",
                campaign_tier="S",
                responsibility_role="principal_commander",
                consequence_basis="state_conquest",
            ),
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"


def test_shadow_military_grade_does_not_let_principal_inherit_parent_campaign() -> None:
    result = assess_military_talent_grade_shadow(
        [
            _achievement(
                "PARENT",
                "national",
                campaign_tier="S+",
                combat_difficulty="D4",
                responsibility_role="principal_commander",
                settlement_scope="ruler_campaign_parent",
                decisive=True,
                stable_delivery=True,
            )
        ],
        coverage_complete=True,
    )

    assert result["grade"] == "ordinary"


def test_shadow_military_top_requires_result_and_difficulty_review() -> None:
    top = assess_military_talent_grade_shadow(
        [
            _achievement(
                "ANCHOR",
                "national",
                campaign_tier="S-",
                combat_difficulty="D3",
                responsibility_role="commander_in_chief",
                stable_delivery=True,
            )
        ],
        coverage_complete=True,
    )
    low_difficulty = assess_military_talent_grade_shadow(
        [
            _achievement(
                "ANCHOR",
                "national",
                campaign_tier="S-",
                combat_difficulty="D1",
                responsibility_role="commander_in_chief",
                stable_delivery=True,
            )
        ],
        coverage_complete=True,
    )

    assert top["grade"] == "top"
    assert low_difficulty["grade"] == "important"


def test_shadow_military_safe_projection_stops_at_important() -> None:
    result = assess_military_talent_grade_shadow(
        [
            _achievement(
                "SAFE-A",
                "national",
                campaign_tier="A",
                combat_difficulty="D2",
                responsibility_role="principal_commander",
                evidence_detail_status="safe_projection",
                stable_delivery=True,
            ),
            _achievement(
                "SAFE-B",
                "national",
                campaign_tier="A",
                combat_difficulty="D2",
                responsibility_role="principal_commander",
                evidence_detail_status="safe_projection",
                stable_delivery=True,
            ),
        ],
        coverage_complete=False,
    )

    assert result["grade"] == "important"
    assert result["rule_path"] == "one_a_or_two_b"


def test_shadow_military_ruler_operational_direction_needs_person_result() -> None:
    parent = _achievement(
        "RULER-DIRECTION",
        "national",
        campaign_tier="S",
        combat_difficulty="D4",
        responsibility_role="commander_in_chief",
        settlement_scope="ruler_campaign_parent",
        ruler_campaign_relation="operational_direction",
        stable_delivery=True,
    )
    child = {
        **parent,
        "settlement_scope": "person_campaign_subresult",
    }
    frontline = {
        **parent,
        "ruler_campaign_relation": "frontline_command",
        "control_extent": "sustained",
    }

    parent_result = assess_military_talent_grade_shadow(
        [parent], coverage_complete=False
    )
    child_result = assess_military_talent_grade_shadow(
        [child], coverage_complete=False
    )
    frontline_result = assess_military_talent_grade_shadow(
        [frontline], coverage_complete=False
    )

    assert parent_result["grade"] is None
    assert child_result["grade"] == "top"
    assert frontline_result["grade"] == "top"


def test_shadow_military_historic_peak_pair_requires_difficulty_pair() -> None:
    base = [
        _achievement(
            "SPLUS",
            "era_shaping",
            campaign_tier="S+",
            combat_difficulty="D4",
            responsibility_role="commander_in_chief",
            decisive=True,
            stable_delivery=True,
        ),
        _achievement(
            "SUPPORT",
            "regional",
            campaign_tier="A",
            combat_difficulty="D2",
            responsibility_role="principal_commander",
        ),
    ]
    passed = assess_military_talent_grade_shadow(base, coverage_complete=True)
    failed = assess_military_talent_grade_shadow(
        [{**row, "combat_difficulty": "D1"} for row in base],
        coverage_complete=True,
    )

    assert passed["grade"] == "historic"
    assert failed["grade"] == "important"


def test_shadow_military_incomplete_empty_coverage_does_not_guess_ordinary() -> None:
    result = assess_military_talent_grade_shadow([], coverage_complete=False)

    assert result["grade"] is None
    assert result["rule_path"] == "coverage_incomplete_no_grade"


def test_sui_chen_campaign_uses_contribution_not_formal_role_for_credit() -> None:
    payload = json.loads(
        (ROOT / "config/unification-campaign-tier-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    portfolio = next(
        row
        for row in payload["adjudications"]
        if row["portfolio_ref"] == "UCP-SUI-YANGJIAN-587-591"
    )
    campaign = next(
        row
        for row in portfolio["campaign_groups"]
        if row["campaign_group_id"] == "WAR-PARENT-SUI-UNIFICATION-589"
    )
    members = {row["actor_name"]: row for row in campaign["members"]}

    assert members["高颎"]["role_code"] == "principal_commander"
    assert members["高颎"]["talent_credit"] == "independent"
    assert members["高颎"]["person_command_index"]["consumption_mode"] == (
        "operational_result"
    )
    assert members["杨广"]["role_code"] == "commander_in_chief"
    assert members["杨广"]["talent_credit"] == "not_applicable"
    assert members["杨广"]["person_command_index"]["consumption_mode"] == "none"
    assert members["杨素"]["talent_credit"] == "covered_by_child"
    assert members["贺若弼"]["talent_credit"] == "covered_by_child"
    assert members["韩擒虎"]["talent_credit"] == "covered_by_child"


def test_civil_scale_alone_does_not_establish_historic_progress() -> None:
    result = assess_domain_historic_path(
        "civil_governance",
        [
            _achievement("A", "national", responsibility_role="exclusive"),
            _achievement(
                "B", "national", responsibility_role="lead"
            ),
            _achievement("C", "regional"),
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"


def test_civil_participation_is_registered_but_does_not_raise_grade() -> None:
    result = assess_domain_historic_path(
        "civil_governance",
        [
            _achievement("A", "national", responsibility_role="participant"),
            _achievement("B", "national", responsibility_role="participant"),
            _achievement("C", "regional", responsibility_role="participant"),
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"
    assert result["counts"]["eligible_independent"] == 0


def test_mixed_governance_result_remains_evidence_but_does_not_raise_grade() -> None:
    result = assess_domain_historic_path(
        "civil_governance",
        [
            {
                **_achievement("A", "national", responsibility_role="exclusive"),
                "result": "implemented_mixed",
                "positive_result_preserved": True,
            },
            {
                **_achievement("B", "national", responsibility_role="lead"),
                "result": "implemented_mixed",
                "positive_result_preserved": True,
            },
            {
                **_achievement("C", "regional"),
                "result": "implemented_mixed",
                "positive_result_preserved": True,
            },
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"
    assert result["counts"]["eligible_independent"] == 0


def test_single_cultural_work_requires_foundational_authorship_and_durability() -> None:
    passed = assess_domain_historic_path(
        "culture_and_scholarship",
        [
            _achievement(
                "WORK",
                "era_shaping",
                consequence_basis="national_war_outcome",
                foundational=True,
                durable_cross_stage=True,
                personally_authored_or_finalized=True,
                contribution_types=["scholarly_authorship"],
                progress_level="era_shaping",
            )
        ],
    )
    failed = assess_domain_historic_path(
        "culture_and_scholarship",
        [
            _achievement(
                "WORK",
                "era_shaping",
                consequence_basis="national_war_outcome",
                foundational=True,
                durable_cross_stage=True,
                personally_authored_or_finalized=False,
                contribution_types=["scholarly_authorship"],
                progress_level="era_shaping",
            )
        ],
    )

    assert passed["historic_fact_path_status"] == "eligible"
    assert failed["historic_fact_path_status"] == "not_established"


def test_same_independent_chain_cannot_be_counted_twice() -> None:
    with pytest.raises(ValueError, match="independent_key"):
        assess_domain_historic_path(
            "military",
            [
                _achievement(
                    "SAME",
                    "national",
                    responsibility_role="commander_in_chief",
                    consequence_basis="state_conquest",
                ),
                _achievement("SAME", "regional", responsibility_role="principal_commander"),
            ],
        )


def test_campaign_registry_enforces_neutral_identity_and_scale_basis() -> None:
    json.loads((ROOT / "config/campaign-registry.schema.json").read_text(encoding="utf-8"))
    registry = {
        "schema_version": "campaign-registry-v1",
        "status": "shadow",
        "campaigns": [
            {
                "campaign_ref": "CAM-TEST-001",
                "independent_campaign_key": "test-war-objective",
                "canonical_label": "测试战役群",
                "episode_refs": ["EP-001"],
                "period": {"start": "测试元年", "end": "测试二年"},
                "theater": "测试战区",
                "strategic_objective": "结束整场战争",
                "campaign_tier": "S",
                "campaign_tier_basis": "核心方向、全国主要对手和整场战争结果共同支持。",
                "land_strategic_value": "core_heartland",
                "strategic_result_class": "single_pole_or_state_terminal",
                "combat_difficulty": "D2",
                "combat_difficulty_basis": "对手主力仍具战力。",
                "outcome": {
                    "battle_result": "victory",
                    "objective_completion": "complete",
                    "observable_consequence": "整场战争结束"
                },
                "scale": {
                    "level": "national",
                    "consequence_basis": "national_war_outcome",
                    "decisiveness": "decisive",
                    "opponent_condition": "viable",
                    "opponent_strategic_weight": "first_tier_pole",
                    "reason": "直接决定战争结局"
                },
                "participants": [
                    {
                        "person_ref": "PER-001",
                        "command_role": "principal_commander",
                        "command_scope": "主战区",
                    }
                ],
                "source_refs": ["SRC-001"],
                "reuse_targets": [
                    "talent_grade_military",
                    "item1_c1_campaign_contribution"
                ]
            }
        ]
    }

    assert validate_campaign_registry(registry) == {
        "schema_version": "campaign-registry-validation-v1",
        "status": "passed",
        "campaign_count": 1,
        "participant_count": 1,
        "formal_score_write_allowed": False,
    }

    registry["campaigns"][0]["scale"]["consequence_basis"] = "important_objective"
    with pytest.raises(ValueError, match="S级以上战役"):
        validate_campaign_registry(registry)


def test_residual_state_conquest_is_not_national_by_title_alone() -> None:
    registry = {
        "schema_version": "campaign-registry-v1",
        "registry_version": "shadow-v1",
        "status": "shadow",
        "campaigns": [
            {
                "campaign_ref": "CAM-TEST-RESIDUAL",
                "independent_campaign_key": "residual-state-conquest",
                "canonical_label": "残余政权征服测试",
                "episode_refs": ["EP-002"],
                "period": {"start": "测试元年", "end": "测试元年"},
                "theater": "测试战区",
                "strategic_objective": "消灭残余政权",
                "campaign_tier": "S",
                "campaign_tier_basis": "仅凭灭国名义尝试定为S级。",
                "land_strategic_value": "important_region",
                "strategic_result_class": "single_pole_or_state_terminal",
                "combat_difficulty": "D0",
                "combat_difficulty_basis": "仅为残余力量。",
                "outcome": {
                    "battle_result": "victory",
                    "objective_completion": "complete",
                    "observable_consequence": "残余政权灭亡",
                },
                "scale": {
                    "level": "national",
                    "consequence_basis": "state_conquest",
                    "decisiveness": "major",
                    "opponent_condition": "residual",
                    "opponent_strategic_weight": "minor",
                    "reason": "仅有灭国名义",
                },
                "participants": [
                    {
                        "person_ref": "PER-002",
                        "command_role": "principal_commander",
                        "command_scope": "主战区",
                    }
                ],
                "source_refs": ["SRC-002"],
                "reuse_targets": ["talent_grade_military"],
            }
        ],
    }

    with pytest.raises(ValueError, match="残余政权"):
        validate_campaign_registry(registry)
