from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.evaluation.governance_achievement_candidate import (
    audit_governance_achievement_candidates,
    prepare_governance_achievement_candidates,
)
from emperor_v4.evaluation.governance_achievement_registry import (
    project_civil_talent_impact,
    validate_governance_achievement_registry,
)
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


def test_governance_registry_projects_top_floor_without_writing_profile() -> None:
    registry = {
        "schema_version": "governance-achievement-registry-v1",
        "registry_version": "shadow-v1",
        "status": "shadow",
        "achievements": [
            {
                "achievement_ref": "GOVACH-LAW-001",
                "independent_governance_key": "national-law-system",
                "canonical_label": "全国律令体系",
                "domain": "law_and_adjudication",
                "period": {"start": "贞观元年", "end": "贞观十一年"},
                "implementation_status": "operated",
                "observable_result": "律令全国颁行并持续施用",
                "result_direction": "positive",
                "positive_result_preserved": True,
                "scale": {
                    "level": "national",
                    "consequence_basis": "national_core_subsystem",
                    "reason": "重构并运行全国刑律子系统",
                },
                "foundational": False,
                "durable_cross_stage": True,
                "stable_delivery": True,
                "important_method_or_legacy": True,
                "participants": [
                    {
                        "person_ref": "PER-001",
                        "canonical_name": "测试人物",
                        "responsibility_role": "lead",
                        "contribution_scope": "共同主导设计和颁行",
                    }
                ],
                "ruler_links": [
                    {
                        "ruler_ref": "RULER-001",
                        "ruler_name": "测试皇帝",
                        "authorization_status": "explicit",
                        "reign_window": "测试元年至十一年",
                    }
                ],
                "neutral_fact_refs": ["DNMAT-001"],
                "source_refs": ["SRC-001"],
                "reuse_targets": ["talent_grade_civil_governance", "i5b_appointment"],
                "limitations": ["集体成果，不得独占归功"],
            }
        ],
    }
    schema_path = ROOT / "config/governance-achievement-registry.schema.json"

    validation = validate_governance_achievement_registry(
        registry, schema_path=schema_path
    )
    impact = project_civil_talent_impact(
        registry,
        [
            {
                "person_ref": "PER-001",
                "canonical_name": "测试人物",
                "talent_grade": "important",
            }
        ],
    )

    assert validation["achievement_count"] == 1
    assert validation["scale_counts"] == {"national": 1}
    assert impact["grade_change_candidate_count"] == 1
    assert impact["impacts"][0]["effective_shadow_grade"] == "top"
    assert impact["impacts"][0]["historic_fact_path_status"] == "not_established"
    assert impact["person_profile_writes"] == impact["score_writes"] == 0


def test_governance_candidate_pipeline_reads_each_component_once_and_bounds_output(
    tmp_path: Path,
) -> None:
    def chain(key: str, actor: str, quote_ref: str) -> dict[str, object]:
        return {
            "chain_key": key,
            "task_code": "DYNGOV-TANG-01-TEST",
            "title": "律令修订",
            "domain": "law_and_adjudication",
            "period": "贞观年间",
            "action": "修订律令",
            "implementation": "颁行天下",
            "operation_status": "operated",
            "observable_result": "形成全国施用的律令体系",
            "cost_or_burden": "原文未载",
            "actors": [
                {
                    "name": actor,
                    "responsibility_role": "lead",
                    "contribution_phases": ["designed", "implemented"],
                    "role_basis": "主持修订和颁行",
                    "quote_refs": [quote_ref],
                }
            ],
            "evidence": [
                {
                    "page_title": "通典/卷一",
                    "revision_ref": "1",
                    "quote_ref": quote_ref,
                    "exact_quote": "房玄齡等刪定律令，頒行天下。",
                }
            ],
            "uncertainty": "",
        }

    baseline_chain = chain("tang-law-baseline", "房玄齡", "q1")
    candidate_chain = chain("tang-law-candidate", "房玄齡", "q2")
    preparation = prepare_governance_achievement_candidates(
        {
            "status": "accepted_shadow",
            "chains": [baseline_chain],
        },
        {
            "status": "accepted_shadow",
            "materials": [
                {
                    "material_ref": "DNMAT-TEST",
                    "candidate_chain_keys": ["tang-law-candidate"],
                    "fact_variants": [
                        {"source_kind": "baseline", "chain_key": "tang-law-baseline", "chain": baseline_chain},
                        {"source_kind": "candidate", "chain_key": "tang-law-candidate", "chain": candidate_chain},
                    ],
                }
            ],
            "review_queue": [],
        },
        {"status": "accepted_shadow", "atoms": []},
        [
            {
                "person_ref": "PER-001",
                "canonical_name": "房玄龄",
                "aliases": ["房玄齡"],
            }
        ],
        dynasty_token="TANG",
        output_root=tmp_path,
        output_schema_path=ROOT / "config/governance-achievement-candidate-output.schema.json",
    )

    assert preparation["component_universe_count"] == 1
    assert preparation["eligible_component_count"] == 1
    assert preparation["policy_version"] == "governance-achievement-judgment-v2"
    task_code = preparation["bindings"][0]["task_code"]
    payload = {
        "schema_version": "governance-achievement-candidate-output-v1",
        "task_code": task_code,
        "component_decisions": [
            {"component_ref": "DNMAT-TEST", "disposition": "register", "reason": "已颁行并形成结果"}
        ],
        "achievements": [
            {
                "local_key": "achievement-1",
                "independent_governance_key": "tang-national-law-system",
                "canonical_label": "唐代全国律令体系",
                "domain": "law_and_adjudication",
                "component_refs": ["DNMAT-TEST"],
                "period_start": "贞观初",
                "period_end": "贞观末",
                "implementation_status": "operated",
                "observable_result": "律令颁行天下并实际施用",
                "result_direction": "positive",
                "positive_result_preserved": True,
                "scale_level": "national",
                "scale_basis": "national_core_subsystem",
                "scale_reason": "形成全国刑律核心子系统",
                "foundational": False,
                "durable_cross_stage": True,
                "stable_delivery": True,
                "important_method_or_legacy": True,
                "participants": [
                    {
                        "person_ref": "PER-001",
                        "responsibility_role": "lead",
                        "contribution_scope": "主持修订和颁行",
                    }
                ],
                "limitations": [],
            }
        ],
        "limitations": [],
    }
    audit = audit_governance_achievement_candidates(
        preparation,
        [payload],
        output_schema_path=ROOT / "config/governance-achievement-candidate-output.schema.json",
        registry_schema_path=ROOT / "config/governance-achievement-registry.schema.json",
    )

    assert audit["status"] == "accepted_shadow"
    assert audit["component_count"] == audit["disposition_counts"]["register"] == 1
    assert audit["registry_validation"]["status"] == "passed"
    assert audit["registry"]["achievements"][0]["participants"][0]["canonical_name"] == "房玄龄"
    assert audit["registry_writes"] == audit["person_profile_writes"] == audit["score_writes"] == 0

    invalid = json.loads(json.dumps(payload, ensure_ascii=False))
    invalid["achievements"][0]["participants"][0]["person_ref"] = "PER-OUTSIDE"
    with pytest.raises(ValueError, match="participant 越界"):
        audit_governance_achievement_candidates(
            preparation,
            [invalid],
            output_schema_path=ROOT / "config/governance-achievement-candidate-output.schema.json",
            registry_schema_path=ROOT / "config/governance-achievement-registry.schema.json",
        )

    provisional = prepare_governance_achievement_candidates(
        {
            "status": "accepted_shadow",
            "chains": [
                chain("tang-provisional-person", "姚元之", "q3"),
                chain("tang-collective-office", "刑部", "q4"),
            ],
        },
        {"status": "accepted_shadow", "materials": [], "review_queue": []},
        {"status": "accepted_shadow", "atoms": []},
        [],
        dynasty_token="TANG",
        output_root=tmp_path / "provisional",
        output_schema_path=ROOT / "config/governance-achievement-candidate-output.schema.json",
    )

    assert provisional["component_universe_count"] == 2
    assert provisional["eligible_component_count"] == 1
    assert provisional["ineligible_component_count"] == 1
    assert "刑部" in provisional["unresolved_actor_names"]
    provisional_people = [
        row
        for row in provisional["people"].values()
        if row.get("identity_status") == "provisional_actor_name"
    ]
    assert [row["canonical_name"] for row in provisional_people] == ["姚元之"]
