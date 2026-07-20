from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.evaluation.talent_grade_domain_equivalence import (
    assess_domain_historic_path,
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
        "deputy_commander": "副将",
        "participant": "从攻",
    }
    assert policy["responsibility_roles"]["civil_governance"] == {
        "exclusive": "独占",
        "lead": "主导",
        "participant": "参与",
    }
    assert (
        policy["historic_paths"]["military"]["normal_repeated_delivery"]
        ["minimum_independent_national_campaigns"]
        == 2
    )
    assert (
        policy["historic_paths"]["civil_governance"]["normal_repeated_delivery"]
        ["minimum_independent_regional_or_higher_results"]
        == 3
    )
    assert (
        policy["historic_paths"]["culture_and_scholarship"]
        ["civilization_foundational_single_work_path"]
        ["requires_personally_authored_or_finalized"]
        is True
    )


def test_military_two_national_plus_one_regional_passes_without_legacy() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement("A", "national", responsibility_role="commander_in_chief", consequence_basis="state_conquest"),
            _achievement(
                "B",
                "national",
                responsibility_role="principal_commander",
                consequence_basis="national_war_outcome",
            ),
            _achievement("C", "regional", responsibility_role="principal_commander"),
        ],
    )

    assert result["historic_fact_path_status"] == "eligible"
    assert result["matched_path"] == "military_two_national_plus_one_regional"


def test_two_exceptional_main_command_national_campaigns_can_pass_alone() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement(
                "A", "national", responsibility_role="commander_in_chief", consequence_basis="state_conquest", decisive=True
            ),
            _achievement(
                "B", "era_shaping", responsibility_role="principal_commander", consequence_basis="unification", decisive=True
            ),
        ],
    )

    assert result["matched_path"] == "military_exceptional_two_national_command"


def test_clear_military_success_survives_separately_recorded_coordination_cost() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement("A", "national", responsibility_role="commander_in_chief", consequence_basis="national_war_outcome"),
            {
                **_achievement(
                    "B", "national", responsibility_role="principal_commander", consequence_basis="state_conquest", decisive=True
                ),
                "result": "implemented_mixed",
                "positive_result_preserved": True,
            },
            _achievement("C", "regional", responsibility_role="principal_commander"),
        ],
    )

    assert result["matched_path"] == "military_two_national_plus_one_regional"


def test_mixed_result_without_preserved_professional_success_does_not_count() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement("A", "national", responsibility_role="commander_in_chief", consequence_basis="national_war_outcome"),
            {
                **_achievement("B", "national", responsibility_role="principal_commander", consequence_basis="state_conquest"),
                "result": "implemented_mixed",
                "positive_result_preserved": False,
            },
            _achievement("C", "regional", responsibility_role="principal_commander"),
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"


def test_two_national_campaigns_need_explicit_decisiveness_for_exception() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement("A", "national", responsibility_role="commander_in_chief", consequence_basis="state_conquest"),
            _achievement("B", "national", responsibility_role="principal_commander", consequence_basis="unification"),
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"


def test_two_ordinary_national_campaigns_do_not_pass_exception_path() -> None:
    result = assess_domain_historic_path(
        "military",
        [
            _achievement(
                "A",
                "national",
                responsibility_role="principal_commander",
                consequence_basis="national_war_outcome",
            ),
            _achievement(
                "B",
                "national",
                responsibility_role="principal_commander",
                consequence_basis="state_conquest",
            ),
        ],
    )

    assert result["historic_fact_path_status"] == "not_established"


def test_civil_repeated_national_delivery_does_not_require_cross_stage_legacy() -> None:
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

    assert result["matched_path"] == "civil_two_national_plus_one_regional"


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
        "registry_version": "shadow-v1",
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
                    "opponent_strategic_weight": "national_peer",
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
    with pytest.raises(ValueError, match="国家级战役"):
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
