from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.i5b_factor_semantics import EXPECTED_VERSIONS


SCHEMA_VERSION = "i5b-scoring-policy-v1"
REPORT_SCHEMA_VERSION = "i5b-scoring-policy-report-v1"
RULE_ORDER = (
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
)
RULE_WEIGHTS = {
    "talent_discovery": Decimal("0.19"),
    "appointment_delegation": Decimal("0.36"),
    "team_building": Decimal("0.21"),
    "tolerate_talent": Decimal("0.18"),
    "anti_nepotism": Decimal("0.06"),
}


@dataclass(frozen=True)
class RuleSignals:
    positive_signal: Decimal
    negative_signal: Decimal
    signal_ref: str | None = None


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _decimal(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - Decimal has small subclasses
        raise ValueError(f"{label} 必须是十进制数") from exc


def _quant(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _text(value: Decimal) -> str:
    return str(_quant(value))


def _require_exact(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} 未保持冻结的 V3 计分骨架")


def _option_decimal(
    table: Mapping[str, Any], option_code: str, label: str
) -> Decimal:
    if option_code not in table:
        raise ValueError(f"{label} option_code 非法: {option_code}")
    return _decimal(table[option_code], label)


def _clamp(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    return max(minimum, min(maximum, value))


def calculate_material_projection(
    policy: Mapping[str, Any],
    *,
    rule_code: str,
    choices: Mapping[str, str],
    side: str | None = None,
) -> dict[str, Any]:
    """Apply the frozen V3 numeric formula after a V4 adapter chose option codes."""
    if rule_code == "team_building":
        raise ValueError("team_building 必须使用人物池，不能计算单材料分")
    rules = policy.get("rules") or {}
    if rule_code not in rules:
        raise ValueError(f"未知第五项 B rule: {rule_code}")

    evidence_policy = policy.get("evidence_factor") or {}
    evidence_choices = {
        name: str(choices.get(name) or "")
        for name in ("attribution_factor", "source_factor", "context_factor")
    }
    evidence_values = {
        name: _option_decimal(
            evidence_policy.get(name) or {}, option_code, f"{rule_code}.{name}"
        )
        for name, option_code in evidence_choices.items()
    }
    evidence_factor = _clamp(
        evidence_values["attribution_factor"]
        * evidence_values["source_factor"]
        * evidence_values["context_factor"],
        _decimal(evidence_policy.get("minimum"), "evidence minimum"),
        _decimal(evidence_policy.get("maximum"), "evidence maximum"),
    )
    rule = rules[rule_code]

    if rule_code == "appointment_delegation":
        dimension_names = (
            "appointment_importance",
            "appointment_effect",
            "continuity_factor",
        )
        dimension_values = {
            name: _option_decimal(
                rule.get(name) or {}, str(choices.get(name) or ""), f"{rule_code}.{name}"
            )
            for name in dimension_names
        }
        raw = (
            dimension_values["appointment_importance"]
            * dimension_values["appointment_effect"]
            * dimension_values["continuity_factor"]
            * evidence_factor
        )
    elif rule_code == "talent_discovery":
        dimension_names = (
            "direction_sign",
            "discovery_level",
            "talent_quality_factor",
        )
        dimension_values = {
            name: _option_decimal(
                rule.get(name) or {}, str(choices.get(name) or ""), f"{rule_code}.{name}"
            )
            for name in dimension_names
        }
        raw = (
            dimension_values["direction_sign"]
            * dimension_values["discovery_level"]
            * dimension_values["talent_quality_factor"]
            * evidence_factor
        )
    elif rule_code == "tolerate_talent":
        if side == "positive":
            dimension_names = (
                "feedback_entry",
                "expression_safety",
                "protection_repair",
            )
            sign = Decimal("1")
        elif side == "negative":
            dimension_names = ("handling_severity", "target_fault_factor")
            sign = Decimal("-1")
        else:
            raise ValueError("tolerate_talent 必须显式声明 positive 或 negative lane")
        dimension_values = {
            name: _option_decimal(
                rule.get(name) or {}, str(choices.get(name) or ""), f"{rule_code}.{name}"
            )
            for name in dimension_names
        }
        raw = sign * evidence_factor
        for value in dimension_values.values():
            raw *= value
    else:
        if side == "positive":
            dimension_names = (
                "selection_openness",
                "institutionalization",
                "office_weight",
            )
            sign = Decimal("1")
        elif side == "negative":
            dimension_names = (
                "favoritism_intensity",
                "office_weight",
                "displacement_harm",
            )
            sign = Decimal("-1")
        else:
            raise ValueError("anti_nepotism 必须显式声明 positive 或 negative lane")
        dimension_values = {
            name: _option_decimal(
                rule.get(name) or {}, str(choices.get(name) or ""), f"{rule_code}.{name}"
            )
            for name in dimension_names
        }
        raw = sign * evidence_factor
        for value in dimension_values.values():
            raw *= value

    material = policy.get("material_layer") or {}
    material_score = _clamp(
        raw,
        _decimal(material.get("material_score_min"), "material score minimum"),
        _decimal(material.get("material_score_max"), "material score maximum"),
    )
    resolved_side = "negative" if material_score < 0 else "positive"
    if side is not None and resolved_side != side:
        raise ValueError(f"{rule_code} lane 与确定性材料分符号冲突")
    return {
        "schema_version": "i5b-material-numeric-projection-v1",
        "rule_code": rule_code,
        "side": resolved_side,
        "factor_option_codes": {
            **{name: choices[name] for name in dimension_names},
            **evidence_choices,
        },
        "deterministic_dimension_values": {
            **{name: float(value) for name, value in dimension_values.items()},
            **{name: float(value) for name, value in evidence_values.items()},
        },
        "evidence_factor": float(evidence_factor),
        "raw_material_score": float(_quant(raw)),
        "material_score": float(_quant(material_score)),
        "numeric_values_supplied_by_model": False,
        "formal_score": False,
    }


def evaluate_i5b_scoring_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("第五项 B 计分政策版本非法")
    if policy.get("status") != "v3_scoring_skeleton_with_v4_settlement_budget_shadow":
        raise ValueError("第五项 B 计分骨架尚未冻结")

    inheritance = policy.get("inheritance") or {}
    _require_exact(inheritance.get("source_tag"), "v3-freeze-20260712", "V3 tag")
    _require_exact(
        inheritance.get("source_commit"),
        "2d7f696643115d6f5f73df3c9ec44885349422f4",
        "V3 commit",
    )

    runtime = policy.get("runtime_policy") or {}
    required_runtime = {
        "mode": "offline_report_only_shadow",
        "model_calls_allowed": False,
        "database_writes_allowed": False,
        "formal_scoring_allowed": False,
        "ranking_allowed": False,
        "old_gold_or_opened_sealed_may_calibrate_numeric_mapping": False,
    }
    for key, value in required_runtime.items():
        _require_exact(runtime.get(key), value, f"runtime_policy.{key}")

    factor_contract = policy.get("factor_semantics_contract") or {}
    _require_exact(
        factor_contract.get("contract_versions"),
        {rule: EXPECTED_VERSIONS[rule] for rule in RULE_ORDER},
        "V4 factor contract versions",
    )
    _require_exact(
        factor_contract.get("numeric_values_must_not_be_supplied_to_factor_agent"),
        True,
        "数值与因子智能体隔离",
    )

    material = policy.get("material_layer") or {}
    _require_exact(material.get("material_score_min"), -4.0, "材料分下限")
    _require_exact(material.get("material_score_max"), 4.0, "材料分上限")
    _require_exact(
        material.get("top_k_allowed_after_eligibility_gate"),
        True,
        "Gate 后 strongest-N 结算",
    )
    _require_exact(
        material.get("settlement_budget_required"), True, "结算预算要求"
    )
    _require_exact(
        material.get("every_accepted_material_must_contribute"),
        False,
        "已接受材料贡献规则",
    )
    _require_exact(
        material.get("supporting_only_material_allowed"), True, "非计分支持材料"
    )

    budget = policy.get("settlement_budget") or {}
    _require_exact(
        budget.get("selection_mode"),
        "eligibility_gate_then_strongest_n",
        "预算结算顺序",
    )
    _require_exact(
        budget.get("numeric_top_k_selection_allowed_after_gate"),
        True,
        "Gate 后 strongest-N 许可",
    )
    _require_exact(
        budget.get("domain_representation_quota_allowed"),
        False,
        "领域代表配额禁令",
    )
    _require_exact(
        budget.get("unfilled_budget_reduces_score"), False, "未用满预算不得扣分"
    )
    _require_exact(
        budget.get("context_labels_are_scoring_slots"), False, "场景标签不得成为槽位"
    )
    _require_exact(
        budget.get("positive_and_negative_independent"), True, "正负预算独立"
    )
    event_budgets = budget.get("event_rules") or {}
    _require_exact(set(event_budgets), set(RULE_ORDER) - {"team_building"}, "事件 rule 预算")
    for rule_code, rule_budget in event_budgets.items():
        _require_exact(rule_budget.get("positive"), 3, f"{rule_code} 正向预算")
        _require_exact(rule_budget.get("negative"), 3, f"{rule_code} 负向预算")
    team_budget = budget.get("team_building") or {}
    _require_exact(team_budget.get("positive_member_budget"), 8, "团队正池预算")
    _require_exact(team_budget.get("negative_member_budget"), 3, "团队负池预算")

    evidence = policy.get("evidence_factor") or {}
    _require_exact(evidence.get("minimum"), 0.45, "evidence factor 下限")
    _require_exact(evidence.get("maximum"), 1.25, "evidence factor 上限")
    _require_exact(
        evidence.get("attribution_factor"),
        {"indirect": 0.8, "direct": 1.0, "direct_under_pressure": 1.1},
        "attribution factor",
    )
    _require_exact(
        evidence.get("source_factor"),
        {"weak_or_compressed": 0.75, "standard": 1.0, "complete_direct_chain": 1.1},
        "source factor",
    )
    _require_exact(
        evidence.get("context_factor"),
        {"weak_but_applicable": 0.7, "clear": 1.0, "core_mechanism_direct": 1.1},
        "context factor",
    )

    rules = policy.get("rules") or {}
    _require_exact(set(rules), set(RULE_ORDER), "五条 rule")
    talent = rules["talent_discovery"]
    if "channel_factor" in talent or "channel_factor" in str(talent.get("formula") or ""):
        raise ValueError("talent_discovery 不得重复乘渠道因子")
    appointment = rules["appointment_delegation"]
    _require_exact(
        appointment.get("projection_mode"),
        "exact_v4_option_mapping",
        "appointment projection",
    )
    _require_exact(
        appointment.get("appointment_importance"),
        {
            "nominal_or_light": 0.6,
            "real_bounded": 1.0,
            "major_affairs": 1.25,
            "critical_national_or_long_term": 1.4,
        },
        "appointment importance",
    )
    _require_exact(
        appointment.get("appointment_effect"),
        {
            "weak_feedback": 0.4,
            "normal_success": 1.0,
            "major_success": 1.5,
            "exceptional_success": 1.8,
            "bounded_control_failure": -0.3,
            "limited_direct_damage": -0.8,
            "major_direct_damage": -1.8,
            "structural_continuing_damage": -2.6,
        },
        "appointment effect",
    )

    team = rules["team_building"]
    _require_exact(
        team.get("negative_profile_mapping_version"),
        "negative-profile-team-v1",
        "team negative profile mapping",
    )
    _require_exact(
        team.get("factor_roles", {}).get("confidant_dependency"),
        "diagnostic_only_not_a_multiplier",
        "team confidant dependency",
    )
    team_policy = (policy.get("aggregation_policies") or {}).get(
        "bounded-team-pool-no-rank-decay-v1"
    ) or {}
    _require_exact(
        team_policy.get("positive_and_negative_axes_independent"),
        True,
        "team 正交双轴",
    )
    _require_exact(
        team_policy.get("rank_decay"),
        False,
        "team 成员排名衰减",
    )

    for rule_code in ("talent_discovery", "tolerate_talent", "anti_nepotism"):
        rule = rules[rule_code]
        if rule.get("fail_closed_when_missing") != "insufficient_projection":
            raise ValueError(f"{rule_code} 缺少投影输入时必须失败关闭")
        if not tuple(rule.get("required_additional_inputs") or ()):
            raise ValueError(f"{rule_code} 未声明 V3 公式所需额外结构输入")

    item = policy.get("item_raw_signal") or {}
    _require_exact(tuple(item.get("rule_order") or ()), RULE_ORDER, "rule order")
    weights = {
        rule: _decimal(value, f"rule_weights.{rule}")
        for rule, value in (item.get("rule_weights") or {}).items()
    }
    _require_exact(weights, RULE_WEIGHTS, "V3 五 rule 权重")
    _require_exact(sum(weights.values()), Decimal("1.00"), "rule 权重和")
    _require_exact(item.get("missing_rule_policy"), "explicit_zero_without_fake_cluster", "缺失 rule")

    mapping = policy.get("batch_dynamic_mapping") or {}
    _require_exact(mapping.get("required"), True, "动态映射要求")
    _require_exact(
        mapping.get("inherited_v3_algorithm_available"),
        False,
        "V3 动态映射实现状态",
    )
    _require_exact(
        mapping.get("single_ruler_immediate_mapping_allowed"),
        False,
        "单皇帝即时映射禁令",
    )
    _require_exact(
        mapping.get("before_snapshot_approval"),
        {"score_rate": None, "score": None, "tier": None, "tier_band": None},
        "动态映射前输出",
    )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "v3_scoring_skeleton_with_v4_settlement_budget_shadow",
        "policy_sha256": _stable_hash(policy),
        "summary": {
            "rule_count": 5,
            "rule_weight_sum": 1.0,
            "exact_option_projection_rule_count": 1,
            "joint_projection_rule_count": 3,
            "person_pool_projection_rule_count": 1,
            "material_numeric_projection_implemented": True,
            "weighted_raw_signal_implemented": True,
            "dynamic_mapping_contract_frozen": True,
            "dynamic_mapping_algorithm_inherited": False,
            "formal_scoring_allowed": False,
            "ranking_allowed": False,
            "model_call_count": 0,
            "database_write_count": 0,
            "settlement_budget_enabled": True,
            "event_selection_mode": "eligibility_gate_then_strongest_n",
            "domain_representation_quota_allowed": False,
            "event_rule_side_budget": 3,
            "team_positive_member_budget": 8,
            "team_negative_member_budget": 3,
        },
        "inheritance": {
            "source_tag": inheritance["source_tag"],
            "source_commit": inheritance["source_commit"],
            "preserved_rule_weights": {
                rule: float(weight) for rule, weight in RULE_WEIGHTS.items()
            },
        },
    }


def calculate_weighted_raw_signal(
    signals: Mapping[str, RuleSignals],
) -> dict[str, Any]:
    unknown = set(signals) - set(RULE_ORDER)
    if unknown:
        raise ValueError(f"未知第五项 B rule: {sorted(unknown)}")

    rows: dict[str, dict[str, Any]] = {}
    weighted_raw_signal = Decimal("0")
    for rule_code in RULE_ORDER:
        signal = signals.get(
            rule_code,
            RuleSignals(positive_signal=Decimal("0"), negative_signal=Decimal("0")),
        )
        positive = _decimal(signal.positive_signal, f"{rule_code}.positive_signal")
        negative = _decimal(signal.negative_signal, f"{rule_code}.negative_signal")
        if positive < 0 or negative < 0:
            raise ValueError(f"{rule_code} 正负侧信号必须分别为非负数")
        raw_net = positive - negative
        weighted = RULE_WEIGHTS[rule_code] * raw_net
        weighted_raw_signal += weighted
        rows[rule_code] = {
            "signal_ref": signal.signal_ref,
            "no_material": signal.signal_ref is None and positive == 0 and negative == 0,
            "positive_signal": _text(positive),
            "negative_signal": _text(negative),
            "rule_raw_net": _text(raw_net),
            "rule_weight": _text(RULE_WEIGHTS[rule_code]),
            "weighted_raw_signal": _text(weighted),
        }

    return {
        "schema_version": "weighted-raw-envelope-v1",
        "formula_stage": "raw_signal_only",
        "formula_version": "i5b-weighted-raw-signal-v1",
        "dynamic_mapping_required": True,
        "max_score": "45.000",
        "rules": rows,
        "weighted_raw_signal": _text(weighted_raw_signal),
        "score_rate": None,
        "score": None,
        "tier": None,
        "tier_band": None,
        "formal_score": False,
    }


def build_batch_mapping_input(
    ruler_envelopes: Sequence[Mapping[str, Any]],
    *,
    calibration_version: str,
) -> dict[str, Any]:
    if not calibration_version.strip():
        raise ValueError("calibration_version 不能为空")
    rulers: list[str] = []
    normalized: list[dict[str, Any]] = []
    for row in ruler_envelopes:
        ruler = str(row.get("ruler") or "").strip()
        envelope = row.get("raw_signal_envelope") or {}
        if not ruler or ruler in rulers:
            raise ValueError("动态映射批次中的皇帝身份必须非空且唯一")
        if (
            envelope.get("schema_version") != "weighted-raw-envelope-v1"
            or envelope.get("dynamic_mapping_required") is not True
            or envelope.get("formal_score") is not False
            or any(envelope.get(key) is not None for key in ("score_rate", "score", "tier", "tier_band"))
        ):
            raise ValueError(f"{ruler} raw signal envelope 非法")
        rulers.append(ruler)
        normalized.append(
            {
                "ruler": ruler,
                "weighted_raw_signal": envelope["weighted_raw_signal"],
                "raw_signal_fingerprint": _stable_hash(envelope),
            }
        )
    if len(normalized) < 2:
        raise ValueError("动态映射必须是多皇帝批次，不能单人即时定标")
    normalized.sort(key=lambda row: row["ruler"])
    cohort_fingerprint = _stable_hash(
        {"calibration_version": calibration_version, "rulers": normalized}
    )
    return {
        "schema_version": "i5b-batch-mapping-input-v1",
        "status": "awaiting_dynamic_mapping_definition_and_human_approval",
        "calibration_version": calibration_version,
        "cohort_identity": [row["ruler"] for row in normalized],
        "cohort_fingerprint": cohort_fingerprint,
        "raw_signals": normalized,
        "score_rate": None,
        "score": None,
        "tier": None,
        "tier_band": None,
        "formal_scoring_allowed": False,
    }
