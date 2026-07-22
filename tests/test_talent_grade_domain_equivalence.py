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
    project_i5b_team_building_impact,
    validate_governance_achievement_registry,
)
from emperor_v4.evaluation.governance_achievement_lineage import (
    audit_governance_achievement_lineage,
    prepare_governance_achievement_lineage,
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
        "not_in_command_chain": "不在军事指挥链",
    }
    assert policy["responsibility_roles"]["civil_governance"] == {
        "exclusive": "独占",
        "lead": "主导",
        "participant": "参与",
    }
    assert (
        policy["historic_paths"]["military"]["normal_repeated_delivery"]
        ["minimum_independent_s_or_higher_campaigns"]
        == 2
    )
    assert (
        policy["historic_paths"]["military"]["s_plus_anchor_path"]
        ["minimum_additional_independent_a_or_higher_campaigns"]
        == 1
    )
    assert policy["top_fallback"]["military_single_s_plus_establishes_top"] is True
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


def test_military_two_s_plus_one_a_passes_without_legacy() -> None:
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
    assert result["matched_path"] == "military_two_s_plus_one_a"


def test_military_one_s_two_s_minus_is_historic() -> None:
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
    assert result["matched_path"] == "military_one_s_two_s_minus"


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
    assert result["matched_path"] == "military_one_s_plus_one_a"
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

    assert result["matched_path"] == "military_exceptional_two_s_command"


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
            },
            _achievement("C", "regional", campaign_tier="A", responsibility_role="principal_commander"),
        ],
    )

    assert result["matched_path"] == "military_two_s_plus_one_a"


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
    assert impact["impacts"][0]["talent_grade"] == "top"
    assert impact["impacts"][0]["historic_fact_path_status"] == "not_established"

    i5b_impact = project_i5b_team_building_impact(
        registry,
        team_report={
            "ruler": "测试皇帝",
            "members": [
                {
                    "person": "测试人物",
                    "person_ref": "PER-V4-001",
                    "effective_talent_grade": "important",
                },
                {
                    "person": "已选人物",
                    "person_ref": "PER-V4-002",
                    "effective_talent_grade": "important",
                },
            ],
        },
        material_budget_report={
            "rules": [
                {
                    "rule_code": "team_building",
                    "positive_members": [
                        {"person": "已选人物", "talent_value": "0.9"}
                    ],
                    "functional_complementarity_factor": "1.2",
                    "long_term_stability_factor": "1.2",
                }
            ]
        },
        scoring_policy={
            "rules": {
                "team_building": {
                    "talent_quality_factor": {
                        "ordinary": 0.35,
                        "usable": 0.55,
                        "important": 0.9,
                        "top": 1.2,
                        "historic": 1.6,
                    }
                }
            }
        },
    )

    assert i5b_impact["reselection_required"] is True
    assert i5b_impact["affected_members"][0]["person_ref"] == "PER-V4-001"
    assert i5b_impact["affected_members"][0]["registry_person_refs"] == ["PER-001"]
    assert i5b_impact["affected_members"][0]["i5b_disposition"] == (
        "positive_pool_reselection_required"
    )
    assert i5b_impact["affected_members"][0]["counterfactual_rule_raw_net_delta"] == "0.432"
    assert i5b_impact["automatic_roster_mutation_allowed"] is False


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

    ruler_preparation = json.loads(json.dumps(preparation, ensure_ascii=False))
    ruler_preparation["people"]["PER-001"]["canonical_name"] = "唐太宗"
    component = ruler_preparation["components"]["DNMAT-TEST"]
    component["allowed_participants"][0]["canonical_name"] = "唐太宗"
    for fact in component["facts"]:
        for actor in fact["actors"]:
            actor["canonical_name"] = "唐太宗"
            actor["name"] = "唐太宗"
            actor["contribution_phases"] = ["authorized"]
    ruler_audit = audit_governance_achievement_candidates(
        ruler_preparation,
        [payload],
        output_schema_path=ROOT / "config/governance-achievement-candidate-output.schema.json",
        registry_schema_path=ROOT / "config/governance-achievement-registry.schema.json",
        ruler_aliases=yaml.safe_load(
            (ROOT / "config/historical-entity-identities.yml").read_text(
                encoding="utf-8"
            )
        ),
        dynasty_name="唐",
    )
    ruler_achievement = ruler_audit["registry"]["achievements"][0]
    assert ruler_achievement["participants"] == []
    assert ruler_achievement["ruler_links"][0]["ruler_name"] == "李世民"
    assert ruler_achievement["ruler_links"][0]["authorization_status"] == "explicit"

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


def test_governance_lineage_drops_explicitly_unsupported_component(
    tmp_path: Path,
) -> None:
    registry = {
        "schema_version": "governance-achievement-registry-v1",
        "status": "shadow",
        "achievements": [
            {
                "achievement_ref": "GOVACH-001",
                "independent_governance_key": "law-result",
                "canonical_label": "依法改判",
                "domain": "law_and_adjudication",
                "period": {"start": "贞观元年", "end": "贞观元年"},
                "implementation_status": "completed",
                "observable_result": "一案依法改判",
                "result_direction": "positive",
                "positive_result_preserved": True,
                "scale": {
                    "level": "local",
                    "consequence_basis": "local_public_result",
                    "reason": "单案结果",
                },
                "foundational": False,
                "durable_cross_stage": False,
                "stable_delivery": False,
                "important_method_or_legacy": False,
                "participants": [
                    {
                        "person_ref": "PER-001",
                        "canonical_name": "测试人物",
                        "responsibility_role": "lead",
                        "contribution_scope": "执奏改判",
                    }
                ],
                "ruler_links": [],
                "neutral_fact_refs": ["COMP-1", "COMP-2"],
                "source_refs": ["SRC-1", "SRC-2"],
                "reuse_targets": ["talent_grade_civil_governance"],
                "limitations": [
                    "存在多事实上游组件；当前保留组件级完整史源，正式接受前需细化本成果的逐事实引用子集。"
                ],
            }
        ],
    }

    def fact(ref: str, source: str, result: str) -> dict[str, object]:
        return {
            "fact_ref": ref,
            "title": result,
            "period": "贞观元年",
            "action": result,
            "implementation": result,
            "observable_result": result,
            "actors": [
                {
                    "canonical_name": "测试人物",
                    "responsibility_role": "lead",
                    "role_basis": "直接记载",
                }
            ],
            "source_refs": [source],
        }

    candidate_preparation = {
        "schema_version": "governance-achievement-candidate-preparation-v1",
        "components": {
            "COMP-1": {"facts": [fact("FACT-1", "SRC-1", "依法改判")]},
            "COMP-2": {"facts": [fact("FACT-2", "SRC-2", "无关制度")]},
        },
    }
    achievement_audit = {
        "status": "accepted_shadow",
        "registry": registry,
        "lineage_refinement_queue": [
            {
                "independent_governance_key": "law-result",
                "component_refs": ["COMP-1", "COMP-2"],
            }
        ],
    }
    preparation = prepare_governance_achievement_lineage(
        achievement_audit,
        candidate_preparation,
        output_root=tmp_path,
        output_schema_path=ROOT / "config/governance-achievement-lineage-output.schema.json",
    )
    result = audit_governance_achievement_lineage(
        achievement_audit,
        candidate_preparation,
        preparation,
        {
            "schema_version": "governance-achievement-lineage-output-v1",
            "task_code": preparation["task_code"],
            "selections": [
                {
                    "achievement_ref": "GOVACH-001",
                    "fact_refs": ["FACT-1"],
                    "unsupported_component_refs": ["COMP-2"],
                    "reason": "COMP-2不支持本案",
                }
            ],
            "limitations": [],
        },
        output_schema_path=ROOT / "config/governance-achievement-lineage-output.schema.json",
        registry_schema_path=ROOT / "config/governance-achievement-registry.schema.json",
    )

    refined = result["registry"]["achievements"][0]
    assert refined["neutral_fact_refs"] == ["FACT-1"]
    assert refined["source_refs"] == ["SRC-1"]
    assert refined["limitations"] == []
    assert result["unsupported_component_count"] == 1
