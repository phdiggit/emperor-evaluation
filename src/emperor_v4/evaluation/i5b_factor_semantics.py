from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "i5b-factor-semantics-v1"
REPORT_SCHEMA_VERSION = "i5b-factor-semantics-report-v1"

EXPECTED_VERSIONS = {
    "appointment_delegation": "appointment-delegation-factor-observation-v8",
    "talent_discovery": "talent-discovery-factor-agent-v2",
    "tolerate_talent": "tolerate-talent-factor-agent-v3",
    "anti_nepotism": "anti-nepotism-factor-agent-v2",
    "team_building": "team-building-factor-agent-v3",
}

EXPECTED_FACTORS = {
    "appointment_delegation": {
        "appointment_importance",
        "appointment_effect",
        "attribution_factor",
        "context_factor",
        "continuity_factor",
        "source_factor",
    },
    "talent_discovery": {
        "recognition_novelty",
        "recognition_basis",
        "barrier_crossing",
        "conversion_to_use",
    },
    "tolerate_talent": {
        "feedback_reception",
        "talent_safety",
        "professional_autonomy",
        "conflict_repair_continuity",
    },
    "anti_nepotism": {
        "capability_basis",
        "process_integrity",
        "public_power_exposure",
        "network_effect",
    },
    "team_building": {
        "talent_depth",
        "core_role_coverage",
        "functional_complementarity",
        "continuity_structure",
        "confidant_dependency",
        "negative_profile_exposure",
    },
}

REQUIRED_OBSERVATIONS = {
    "appointment_delegation": {
        "jurisdiction_scope",
        "cross_domain",
        "institution_forming",
        "duration",
        "one_off_basis",
        "explicit_ruler_action",
        "scoped_responsibility",
        "linked_feedback",
        "distinct_authorization_count",
        "distinct_observation_count",
        "predecision_pressure_refs",
    },
    "talent_discovery": {
        "visibility_basis_at",
        "verification_at",
        "first_substantive_use_at",
    },
    "tolerate_talent": {
        "subject_ownership_chain",
        "positive_safety_followup",
        "independent_repair_followup",
        "independent_continuity_followup",
        "repair_assessment",
    },
    "team_building": {
        "historic_count",
        "top_count",
        "historic_or_top_count",
        "qualified_member_count",
        "qualified_role_anchors",
        "independent_role_matching",
        "normalized_window",
        "stage_snapshots",
        "role_transitions",
        "core_role_gap_intervals",
        "profile_version_distribution",
        "negative_profile_members",
        "negative_profile_mapping_version",
        "profile_identity_conflicts",
    },
}

EXPECTED_STRUCTURED_GATES = {
    "appointment_delegation": {
        "continuity_stable_min_distinct_observations": 2,
        "continuity_multi_stage_min_distinct_authorizations": 2,
        "attribution_under_pressure_requires_predecision_pressure_ref": True,
        "effect_requires_linked_feedback": True,
        "continuity_short_requires_one_off_basis": [
            "explicit_one_off",
            "bounded_absence",
        ],
    },
    "talent_discovery": {
        "verified_basis_requires_verification_before_first_use": True,
        "trial_then_scaled_use_min_distinct_stages": 2,
    },
    "tolerate_talent": {
        "subject_chain_order_fields_required": True,
        "positive_safety_followup_after_ruler_response": True,
        "positive_safety_followup_observation_must_differ": True,
        "repair_followup_after_ruler_response": True,
        "repair_followup_observation_must_differ": True,
        "continuity_followup_after_ruler_response": True,
        "continuity_followup_observation_must_differ": True,
        "repair_assessment_timing_values": ["timely", "delayed", "not_established"],
        "repair_assessment_scope_values": [
            "substantive_full",
            "substantive_partial",
            "formal_only",
            "none",
        ],
        "timely_repair_requires": {
            "timing": "timely",
            "scope": "substantive_full",
            "trust_restored": True,
        },
        "delayed_partial_repair_requires_substantive_scope": [
            "substantive_full",
            "substantive_partial",
        ],
        "delayed_partial_repair_requires_any": [
            "timing_delayed",
            "scope_substantive_partial",
        ],
        "delayed_timing_requires_delay_basis_refs": True,
        "formal_reversal_requires": {
            "scope": "formal_only",
            "trust_restored": False,
        },
        "formal_reversal_requires_later_independent_continuity": True,
        "formal_reversal_requires_bounded_nonrestoration_refs": True,
    },
    "anti_nepotism": {
        "cross_person_single_channel": {"min_people": 2, "exact_channels": 1},
        "cross_channel_capture": {
            "min_people": 2,
            "min_channels": 2,
            "control_refs_required": True,
        },
        "durable_capture": {
            "cross_channel_capture_required": True,
            "cross_period_or_repeated_refs_required": True,
        },
    },
    "team_building": {
        "talent_multi_historic": {"min_historic_count": 2},
        "talent_multi_top": {
            "max_historic_count": 1,
            "min_historic_or_top_count": 2,
        },
        "balanced_four": {
            "covered_core_roles": 4,
            "independent_role_matching_size": 4,
        },
        "strong_three": {"independent_role_matching_size": 3},
        "core_role_coverage": {
            "role_catalog": [
                "strategic_decision",
                "public_governance",
                "specialist_execution",
                "correction_feedback",
            ],
            "critical_long_vacancy_priority": True,
        },
        "durable_multi_stage": {
            "min_stage_count": 2,
            "min_roles_each_stage": 3,
            "max_role_gap_years": 1,
            "real_stage_boundary_required": True,
        },
        "managed_turnover": {
            "durable_multi_stage_must_fail": True,
            "min_transition_count": 1,
            "max_transition_gap_years": 1,
            "distinct_predecessor_successor_required": True,
        },
        "confidant_dependency": {
            "single_point_min_sole_core_roles": 3,
            "elevated_min_sole_core_roles": 2,
            "distributed_min_independent_roles": 3,
        },
        "negative_profile_axis": {
            "orthogonal_to_talent_grade": True,
            "raw_class_severity_version_required": True,
            "none_observed_requires_complete_coverage": True,
            "core_role_concentration_min_sole_roles": 2,
            "systemic_min_risk_members": 2,
            "systemic_min_joint_sole_roles": 3,
        },
    },
}


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _factor_map(rule_code: str, rule: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    factors = dict(rule.get("factors") or {})
    if rule_code == "appointment_delegation":
        factors.update(rule.get("model_owned_factors") or {})
        factors.update(rule.get("deterministic_factors") or {})
    return factors


def _require_exact_subset(
    actual: Mapping[str, Any], expected: Mapping[str, Any], label: str
) -> None:
    for key, value in expected.items():
        if actual.get(key) != value:
            raise ValueError(f"{label}.{key} 未按冻结语义收口")


def evaluate_i5b_factor_semantics(contract: Mapping[str, Any]) -> dict[str, Any]:
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("第五项 B 因子语义合同版本非法")
    if contract.get("status") != "current_active":
        raise ValueError("第五项 B 当前因子语义未启用")
    common = contract.get("common_contract") or {}
    required_common = {
        "categorical_only": True,
        "numeric_score_or_rank_allowed": False,
        "context_kind_owns_factor_denominator": True,
        "evidence_lineage_required": True,
        "absence_inference_requires_bounded_coverage": True,
    }
    _require_exact_subset(common, required_common, "common_contract")
    generic_terminal = contract.get("generic_owned_factor_terminal_protocol") or {}
    if generic_terminal != {
        "applies_to": [
            "talent_discovery",
            "tolerate_talent",
            "anti_nepotism",
            "team_building",
        ],
        "terminal_states": ["not_applicable", "insufficient_evidence"],
        "terminal_state_must_propagate_to_all_owned_factors": True,
    }:
        raise ValueError("第五项 B generic 终止协议非法")
    appointment_resolution = contract.get("appointment_resolution_protocol") or {}
    if appointment_resolution != {
        "applies_to": ["appointment_delegation"],
        "decision_statuses": ["resolved", "insufficient_coverage"],
        "insufficient_coverage_requires_null_option_code": True,
    }:
        raise ValueError("任用授权 resolution 协议非法")

    rules = contract.get("rules") or {}
    if set(rules) != set(EXPECTED_VERSIONS):
        raise ValueError("第五项 B 必须精确覆盖五条 rule")

    report_rows = []
    for rule_code in EXPECTED_VERSIONS:
        rule = rules[rule_code]
        if rule.get("contract_version") != EXPECTED_VERSIONS[rule_code]:
            raise ValueError(f"{rule_code} 合同版本未冻结")
        context_kinds = tuple(rule.get("context_kinds") or ())
        if not context_kinds or len(context_kinds) != len(set(context_kinds)):
            raise ValueError(f"{rule_code} context_kinds 非法")
        factors = _factor_map(rule_code, rule)
        if set(factors) != EXPECTED_FACTORS[rule_code]:
            raise ValueError(f"{rule_code} 因子集合未精确收口")
        option_count = 0
        for factor_name, factor in factors.items():
            options = tuple(factor.get("option_codes") or ())
            if not options or len(options) != len(set(options)):
                raise ValueError(f"{rule_code}/{factor_name} 档位为空或重复")
            option_count += len(options)
            if rule_code != "appointment_delegation" and not {
                "not_applicable",
                "insufficient_evidence",
            } <= set(options):
                raise ValueError(f"{rule_code}/{factor_name} 缺少安全退出档")

        observation_key = (
            "required_mechanical_observations"
            if rule_code == "appointment_delegation"
            else "required_structural_observations"
            if rule_code == "team_building"
            else "required_semantic_observations"
        )
        expected_observations = REQUIRED_OBSERVATIONS.get(rule_code)
        if expected_observations is not None and set(
            rule.get(observation_key) or ()
        ) != expected_observations:
            raise ValueError(f"{rule_code} 必需观察字段未精确收口")
        _require_exact_subset(
            rule.get("structured_gates") or {},
            EXPECTED_STRUCTURED_GATES[rule_code],
            f"{rule_code}.structured_gates",
        )
        report_rows.append(
            {
                "rule_code": rule_code,
                "contract_version": EXPECTED_VERSIONS[rule_code],
                "context_kinds": list(context_kinds),
                "factor_count": len(factors),
                "option_count": option_count,
                "semantic_gate_status": "inventory_and_selected_gates_validated",
            }
        )

    anti = rules["anti_nepotism"]
    if anti.get("factor_ownership") != {
        "episode": [
            "capability_basis",
            "process_integrity",
            "public_power_exposure",
        ],
        "aggregate_context": ["network_effect"],
    }:
        raise ValueError("anti_nepotism 因子所有权非法")
    public_options = set(
        anti["factors"]["public_power_exposure"]["option_codes"]
    )
    if (
        "appointment_channel_control" in public_options
        or "system_wide_public_power" not in public_options
    ):
        raise ValueError("anti_nepotism 公共权力档仍与程序控制重叠")
    team = rules["team_building"]
    expected_profile_contract = {
        "source": "current_historical_outcome_and_window_risk_projection",
        "talent_grade_policy": "config/talent-grade-v11-domain-equivalent-historic.yml",
        "political_risk_policy": "config/political-risk.yml",
        "rebuild_from_current_inputs": True,
        "accepted_value_state": "current_coverage_complete",
        "profile_ref_and_snapshot_version_content_unique": True,
        "direct_external_score_or_primary_key_reuse_forbidden": True,
    }
    if team.get("profile_snapshot_contract") != expected_profile_contract:
        raise ValueError("team_building 当前人物画像投影合同未收口")
    if "capability_risk_dominated" in set(
        team["factors"]["talent_depth"]["option_codes"]
    ):
        raise ValueError("team_building talent_depth 不得混入负面政治风险")

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "current_active",
        "contract_sha256": _stable_hash(contract),
        "summary": {
            "rule_count": len(report_rows),
            "factor_count": sum(row["factor_count"] for row in report_rows),
            "option_count": sum(row["option_count"] for row in report_rows),
            "contract_inventory_and_selected_structured_gates_machine_validated": True,
            "formal_scoring_allowed": False,
            "database_write_count": 0,
        },
        "rules": report_rows,
    }
