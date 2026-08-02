from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ELIGIBLE_STATUS = "ELIGIBLE_DYNASTY_FOUNDER"
EXCLUDED_STATUS = "NOT_APPLICABLE_NON_FOUNDER"
RATE_FIELDS = (
    "terminal_completion_rate",
    "control_retention_rate",
    "loss_recovery_rate",
    "early_stability_rate",
)


def _a1_axis(row: Mapping[str, Any]) -> dict[str, Any]:
    start_disadvantage = float(row["starting_resource_disadvantage"])
    opponent = float(row["opponent_pressure"])
    complexity = float(row["environment_complexity"])
    completion = float(row["terminal_completion_rate"])
    created_control = float(row["created_net_control_value"])
    difficulty = 0.45 * start_disadvantage + 0.35 * opponent + 0.20 * complexity
    control_scale = min(1.0, (created_control / 700.0) ** 0.35) if created_control > 0 else 0.0
    attributed_completion = completion
    result_rate = 0.75 * control_scale + 0.25 * attributed_completion
    rate = result_rate * (0.75 + 0.25 * difficulty)
    return {
        "axis": "A1",
        "name": "创业战略增益与难度兑现",
        "starting_resource_share": round(100 * float(row["starting_resource_share"]), 2),
        "starting_resource_disadvantage": round(100 * start_disadvantage, 2),
        "start_field": row["start_field"],
        "created_net_control_value": round(created_control, 2),
        "control_scale_rate": round(100 * control_scale, 2),
        "opponent_pressure": round(100 * opponent, 2),
        "battlefield_pressure": (
            round(100 * float(row["battlefield_pressure"]), 2)
            if row["battlefield_pressure"] is not None else None
        ),
        "relative_resource_pressure": round(100 * float(row["relative_resource_pressure"]), 2),
        "major_opponent_count": len(row["major_opponent_encounters"]),
        "major_opponent_encounters": row["major_opponent_encounters"],
        "opponent_threat_source_status": row["opponent_threat_source_status"],
        "competitive_fragmentation": round(100 * complexity, 2),
        "difficulty_rate": round(100 * difficulty, 2),
        "terminal_completion_rate": round(100 * completion, 2),
        "attributed_completion_rate": round(100 * attributed_completion, 2),
        "result_rate": round(100 * result_rate, 2),
        "rate": round(100 * rate, 2),
        "weight": 60,
        "points": round(60 * rate, 1),
    }


def _a2_axis(row: Mapping[str, Any]) -> dict[str, Any]:
    years = float(row["effective_years"])
    weighted_years = float(row["value_weighted_acquisition_years"])
    effective_control = float(row["created_net_control_value"])
    retention = float(row["control_retention_rate"])
    recovery = float(row["loss_recovery_rate"])
    completion = float(row["terminal_completion_rate"])
    stability = float(row["early_stability_rate"])
    error_burden = float(row["strategic_error_burden_rate"])
    positive_anchor_rate = float(row["strategic_positive_anchor_rate"])
    acquisition_efficiency = effective_control / weighted_years if weighted_years > 0 else 0.0
    acquisition_pace = min(1.0, (acquisition_efficiency / 100.0) ** 0.35) if acquisition_efficiency > 0 else 0.0
    expected_closure_years = 8.0 * math.sqrt(effective_control / 550.25) if effective_control > 0 else 0.0
    closure_pace = min(1.0, expected_closure_years / years) if years > 0 else 0.0
    time_rate = 0.60 * acquisition_pace + 0.40 * closure_pace
    resilience = 0.60 * retention + 0.40 * recovery
    decision_quality = positive_anchor_rate * (1 - error_burden)
    uncapped = (
        0.60 * decision_quality
        + 0.15 * time_rate
        + 0.15 * resilience
        + 0.10 * stability
    )
    rate = uncapped
    return {
        "axis": "A2",
        "name": "创业路线效率与稳固",
        "closure_years": round(years, 2),
        "value_weighted_acquisition_years": round(weighted_years, 2),
        "control_acquisition_efficiency": round(acquisition_efficiency, 2),
        "acquisition_pace_rate": round(100 * acquisition_pace, 2),
        "scale_expected_closure_years": round(expected_closure_years, 2),
        "closure_pace_rate": round(100 * closure_pace, 2),
        "time_rate": round(100 * time_rate, 2),
        "control_retention_rate": round(100 * retention, 2),
        "loss_recovery_rate": round(100 * recovery, 2),
        "resilience_rate": round(100 * resilience, 2),
        "terminal_completion_rate": round(100 * completion, 2),
        "early_stability_rate": round(100 * stability, 2),
        "strategic_positive_anchor_rate": round(100 * positive_anchor_rate, 2),
        "strategic_positive_anchor": dict(row["strategic_positive_anchor"]),
        "strategic_error_burden_rate": round(100 * error_burden, 2),
        "strategic_decision_quality_rate": round(100 * decision_quality, 2),
        "strategic_error_events": list(row["strategic_error_events"]),
        "rate": round(100 * rate, 2),
        "weight": 40,
        "points": round(40 * rate, 1),
    }


def build_first_item_a_registry(
    *, efficiency_inputs: Mapping[str, Any], competitive_landscapes: Mapping[str, Any],
    battle_registry: Mapping[str, Any], territorial_inputs: Mapping[str, Any],
    acquisition_windows: Mapping[str, Any], roster: Mapping[str, Any]
) -> dict[str, Any]:
    if efficiency_inputs.get("schema_version") != "first-item-a-strategic-efficiency-inputs-v7":
        raise ValueError("第一项A量化输入schema_version不正确")
    if efficiency_inputs.get("status") != "CURRENT":
        raise ValueError("第一项A量化输入状态不正确")
    if competitive_landscapes.get("schema_version") != "first-item-a-competitive-landscapes-v4":
        raise ValueError("第一项A竞争格局输入schema_version不正确")
    if competitive_landscapes.get("status") != "CURRENT":
        raise ValueError("第一项A竞争格局输入状态不正确")

    battle_records = list(battle_registry.get("records") or ())
    battle_by_ref = {str(row["war_event_id"]): row for row in battle_records}
    portfolios = list(battle_registry.get("unification_portfolios") or ())
    portfolio_by_ref = {str(row["portfolio_ref"]): row for row in portfolios}
    if len(battle_by_ref) != len(battle_records) or len(portfolio_by_ref) != len(portfolios):
        raise ValueError("公共战役登记存在重复标识")
    campaign_sources = dict(competitive_landscapes.get("campaign_threat_sources") or {})
    manual_windows = {
        str(row["ruler_name"]): row for row in acquisition_windows.get("manual_windows") or ()
    }

    recovery_refs: set[str] = set()
    def collect_recovery_refs(value: Any) -> None:
        if isinstance(value, Mapping):
            group_ref = value.get("campaign_group_id")
            effects = value.get("control_effects")
            if group_ref and isinstance(effects, list) and any(
                effect.get("control_change") == "recovery_within_window"
                for effect in effects if isinstance(effect, Mapping)
            ):
                recovery_refs.add(str(group_ref))
            for child in value.values():
                collect_recovery_refs(child)
        elif isinstance(value, list):
            for child in value:
                collect_recovery_refs(child)
    collect_recovery_refs(territorial_inputs)

    tier_stakes = {"S+": 1.0, "S": 0.85, "S-": 0.70, "A": 0.55, "B": 0.40, "C": 0.25, "D": 0.10}
    difficulty_rates = {None: 0.0, "D0": 0.0, "D1": 0.25, "D2": 0.50, "D3": 0.75, "D4": 1.0}
    condition_rates = {None: 0.0, "collapsed": 0.0, "residual": 0.20, "weakened": 0.40, "viable": 0.60, "strong": 0.80, "dominant": 1.0}
    opponent_caliber_rates = {
        "minor": 0.30,
        "regional_major": 0.50,
        "first_tier_pole": 0.75,
        "dominant_pole": 1.0,
        "external_hegemony": 1.0,
    }

    def compile_campaign_threat(ruler_name: str) -> tuple[float, list[dict[str, Any]], str] | None:
        source = dict(campaign_sources.get(ruler_name) or {})
        campaign_rows: list[tuple[str, Mapping[str, Any]]] = []
        if source:
            include_refs = set(str(ref) for ref in source.get("include_campaign_refs") or ())
            for portfolio_ref in source.get("portfolio_refs") or ():
                portfolio = portfolio_by_ref.get(str(portfolio_ref))
                if portfolio is None:
                    raise ValueError(f"第一项A对手压力组合不存在: {ruler_name}/{portfolio_ref}")
                for group in portfolio.get("campaign_groups") or ():
                    group_ref = str(group["campaign_group_id"])
                    if not include_refs or group_ref in include_refs:
                        campaign_rows.append((group_ref, dict(group.get("payload") or {})))
            for campaign_ref in source.get("campaign_refs") or ():
                row = battle_by_ref.get(str(campaign_ref))
                if row is None:
                    raise ValueError(f"第一项A对手压力战役不存在: {ruler_name}/{campaign_ref}")
                campaign_rows.append((str(campaign_ref), row))
            source_status = "PUBLIC_BATTLE_PORTFOLIO"
        elif ruler_name in manual_windows:
            for campaign_ref in manual_windows[ruler_name].get("campaign_refs") or ():
                row = battle_by_ref.get(str(campaign_ref))
                if row is None:
                    raise ValueError(f"第一项A手工窗口战役不存在: {ruler_name}/{campaign_ref}")
                campaign_rows.append((str(campaign_ref), row))
            source_status = "PUBLIC_BATTLE_MANUAL_WINDOW"
        else:
            return None

        details: list[dict[str, Any]] = []
        weighted_threat = 0.0
        total_stake = 0.0
        peak_threat = 0.0
        for campaign_ref, row in campaign_rows:
            tier = row.get("campaign_tier")
            difficulty = row.get("combat_difficulty")
            condition = row.get("opponent_condition")
            caliber = row.get("opponent_strategic_weight")
            if tier is None:
                continue
            if (
                tier not in tier_stakes or difficulty not in difficulty_rates
                or condition not in condition_rates or caliber not in opponent_caliber_rates
            ):
                raise ValueError(f"第一项A公共战役威胁字段无效: {ruler_name}/{campaign_ref}")
            regeneration = 1.0 if campaign_ref in recovery_refs else 0.0
            threat_parts = [
                difficulty_rates[difficulty],
                condition_rates[condition],
                opponent_caliber_rates[str(caliber)],
            ]
            if regeneration:
                threat_parts.append(regeneration)
            field_threat = sum(threat_parts) / len(threat_parts)
            load = tier_stakes[str(tier)] * field_threat
            weighted_threat += load
            total_stake += tier_stakes[str(tier)]
            peak_threat = max(peak_threat, field_threat)
            details.append({
                "campaign_ref": campaign_ref,
                "campaign_tier": tier,
                "combat_difficulty": difficulty,
                "opponent_condition": condition,
                "opponent_strategic_weight": caliber,
                "regeneration_rate": round(100 * regeneration, 2),
                "field_threat_rate": round(100 * field_threat, 2),
                "strategic_load_units": round(load + 1e-12, 4),
            })
        if not details:
            return None
        weighted_mean = weighted_threat / total_stake
        return 0.5 * (weighted_mean + peak_threat), details, source_status

    roster_rows = list(roster.get("records") or ())
    roster_by_name = {str(row["ruler_name"]): row for row in roster_rows}
    if len(roster_by_name) != len(roster_rows):
        raise ValueError("第一项A名册存在重复ruler_name")
    input_rows = list(efficiency_inputs.get("records") or ())
    input_by_name = {str(row["ruler_name"]): row for row in input_rows}
    if len(input_by_name) != len(input_rows):
        raise ValueError("第一项A量化输入存在重复ruler_name")
    unknown = set(input_by_name) - set(roster_by_name)
    if unknown:
        raise ValueError(f"第一项A量化输入包含名册外对象: {sorted(unknown)}")
    control_values = dict(efficiency_inputs.get("created_net_control_values") or {})
    weighted_years = dict(efficiency_inputs.get("value_weighted_acquisition_years") or {})
    landscape_rows = list(competitive_landscapes.get("records") or ())
    landscape_by_name = {str(row["ruler_name"]): row for row in landscape_rows}
    if len(landscape_by_name) != len(landscape_rows):
        raise ValueError("第一项A竞争格局存在重复ruler_name")
    error_events = dict(efficiency_inputs.get("strategic_error_events") or {})
    positive_anchors = dict(efficiency_inputs.get("strategic_positive_anchors") or {})
    class_values = dict(efficiency_inputs.get("class_values") or {})
    severity_penalties = dict(class_values.get("error_severity_penalty") or {})
    positive_anchor_rates = dict(class_values.get("positive_anchor_rate") or {})
    input_names = set(input_by_name)
    if any(set(values) != input_names for values in (control_values, weighted_years, landscape_by_name)):
        raise ValueError("第一项A净控制量、时间或竞争格局未完整覆盖奠基者")
    if set(error_events) - input_names:
        raise ValueError("第一项A战略误判包含名册外奠基者")
    if set(positive_anchors) != input_names:
        raise ValueError("第一项A正向战略锚点未完整覆盖奠基者")
    if not severity_penalties or not positive_anchor_rates:
        raise ValueError("第一项A战略事件档位映射缺失")

    records: list[dict[str, Any]] = []
    for ruler_name, roster_row in roster_by_name.items():
        common = {
            "ruler_id": roster_row.get("ruler_id"),
            "ruler_name": ruler_name,
            "polity": roster_row.get("polity"),
            "reign_range": roster_row.get("reign_range"),
        }
        decision = input_by_name.get(ruler_name)
        if decision is None:
            records.append({
                **common,
                "scope_status": EXCLUDED_STATUS,
                "score_applicable": False,
                "founder_role": None,
                "A1": None,
                "A2": None,
                "A_score_points": None,
                "canonical_rank": None,
                "basis": "普通继承、守成扩张或未在本名册所属政权中承担奠基责任",
            })
            continue

        required = (
            "founder_role", "start_boundary", "end_boundary", "starting_position",
            "responsibility_basis", "effective_years", *RATE_FIELDS,
        )
        if any(decision.get(field) in (None, "") for field in required):
            raise ValueError(f"第一项A量化裁决字段不完整: {ruler_name}")
        for field in RATE_FIELDS:
            value = float(decision[field])
            if not 0 <= value <= 1:
                raise ValueError(f"第一项A比例越界: {ruler_name}/{field}")
        if float(decision["effective_years"]) <= 0:
            raise ValueError(f"第一项A时间值越界: {ruler_name}")

        terminal_completion = float(decision["terminal_completion_rate"])
        control_value = float(control_values[ruler_name])
        acquisition_years = float(weighted_years[ruler_name])
        landscape = landscape_by_name[ruler_name]
        start_field = dict(landscape.get("start_field") or {})
        subject_units = float(start_field.get("subject_units") or 0)
        other_actors = dict(start_field.get("other_actors") or {})
        actor_units = [subject_units, *(float(value) for value in other_actors.values())]
        if subject_units <= 0 or not other_actors or any(value <= 0 for value in actor_units):
            raise ValueError(f"第一项A起点竞争格局无效: {ruler_name}")
        start_total = sum(actor_units)
        start_share = subject_units / start_total
        start_disadvantage = 1 - start_share
        shares = [value / start_total for value in actor_units]
        complexity = -sum(share * math.log(share) for share in shares) / math.log(len(shares))
        encounters = list(landscape.get("major_opponent_encounters") or ())
        if not encounters:
            raise ValueError(f"第一项A主要对手为空: {ruler_name}")
        encounter_details = []
        total_stake = 0.0
        weighted_pressure = 0.0
        seen_opponents: set[str] = set()
        for encounter in encounters:
            if not isinstance(encounter, list) or len(encounter) != 4:
                raise ValueError(f"第一项A主要对手格式无效: {ruler_name}")
            opponent_name, own_units_raw, opponent_units_raw, stake_raw = encounter
            opponent_name = str(opponent_name)
            own_units = float(own_units_raw)
            opponent_units = float(opponent_units_raw)
            stake = float(stake_raw)
            if not opponent_name or opponent_name in seen_opponents or min(own_units, opponent_units, stake) <= 0:
                raise ValueError(f"第一项A主要对手数据无效: {ruler_name}/{opponent_name}")
            seen_opponents.add(opponent_name)
            pressure = opponent_units / (own_units + opponent_units)
            total_stake += stake
            weighted_pressure += stake * pressure
            encounter_details.append({
                "opponent": opponent_name,
                "subject_resource_units": own_units,
                "opponent_resource_units": opponent_units,
                "stake_units": stake,
                "pressure_rate": round(100 * pressure, 2),
            })
        fallback_opponent_pressure = weighted_pressure / total_stake
        compiled_threat = compile_campaign_threat(ruler_name)
        if compiled_threat is None:
            opponent_pressure = fallback_opponent_pressure
            battlefield_pressure = None
            threat_details = encounter_details
            threat_source_status = "COMPLETE_DEFAULT_RELATIVE_ENCOUNTERS"
        else:
            battlefield_pressure, threat_details, threat_source_status = compiled_threat
            opponent_pressure = 0.5 * (
                battlefield_pressure + fallback_opponent_pressure
            )
            threat_source_status += "_WITH_RELATIVE_RESOURCES"
        if control_value < 0 or acquisition_years <= 0:
            raise ValueError(f"第一项A净控制量或加权时间越界: {ruler_name}")
        person_errors = list(error_events.get(ruler_name) or ())
        remaining_quality = 1.0
        seen_error_names: set[str] = set()
        for event in person_errors:
            event_name = str(event.get("event") or "")
            severity = str(event.get("severity") or "")
            basis = str(event.get("basis") or "")
            if not event_name or event_name in seen_error_names or severity not in severity_penalties or not basis:
                raise ValueError(f"第一项A战略误判事件无效: {ruler_name}/{event_name}")
            seen_error_names.add(event_name)
            remaining_quality *= 1 - float(severity_penalties[severity])
        error_burden = 1 - remaining_quality
        positive_anchor = dict(positive_anchors[ruler_name])
        anchor_event = str(positive_anchor.get("event") or "")
        anchor_impact = str(positive_anchor.get("impact") or "")
        anchor_basis = str(positive_anchor.get("basis") or "")
        if (
            not anchor_event or anchor_impact not in positive_anchor_rates
            or not anchor_basis
        ):
            raise ValueError(f"第一项A正向战略锚点无效: {ruler_name}")
        positive_anchor_rate = float(positive_anchor_rates[anchor_impact])
        if not 0 <= positive_anchor_rate <= 1:
            raise ValueError(f"第一项A正向战略锚点档位越界: {ruler_name}")
        calculation_input = {
            **decision,
            "terminal_completion_rate": terminal_completion,
            "strategic_error_burden_rate": error_burden,
            "strategic_error_events": person_errors,
            "strategic_positive_anchor_rate": positive_anchor_rate,
            "strategic_positive_anchor": positive_anchor,
            "created_net_control_value": control_value,
            "value_weighted_acquisition_years": acquisition_years,
            "starting_resource_share": start_share,
            "starting_resource_disadvantage": start_disadvantage,
            "start_field": {"subject_units": subject_units, "other_actors": other_actors},
            "opponent_pressure": opponent_pressure,
            "battlefield_pressure": battlefield_pressure,
            "relative_resource_pressure": fallback_opponent_pressure,
            "major_opponent_encounters": threat_details,
            "opponent_threat_source_status": threat_source_status,
            "environment_complexity": complexity,
        }
        a1 = _a1_axis(calculation_input)
        a2 = _a2_axis(calculation_input)
        records.append({
            **common,
            "scope_status": ELIGIBLE_STATUS,
            "score_applicable": True,
            "founder_role": decision["founder_role"],
            "start_boundary": decision["start_boundary"],
            "end_boundary": decision["end_boundary"],
            "starting_position": decision["starting_position"],
            "A1": a1,
            "A2": a2,
            "strategic_error_events": person_errors,
            "A_score_points": round(a1["points"] + a2["points"], 1),
            "canonical_rank": None,
            "responsibility_basis": decision["responsibility_basis"],
        })

    eligible = sorted(
        (row for row in records if row["score_applicable"]),
        key=lambda row: (-float(row["A_score_points"]), -float(row["A1"]["rate"]), str(row["ruler_name"])),
    )
    for rank, row in enumerate(eligible, start=1):
        row["canonical_rank"] = rank
    excluded = sorted(
        (row for row in records if not row["score_applicable"]),
        key=lambda row: str(row["ruler_name"]),
    )
    records = eligible + excluded
    scope_counts = Counter(str(row["scope_status"]) for row in records)
    return {
        "schema_version": "first-item-a-registry-v1",
        "canonical_status": "CURRENT",
        "status": "CURRENT_NOT_FORMAL_DATABASE_WRITE",
        "item": "第一项A创业战略能力（已吸收原D创业难度）",
        "max_points": 100,
        "method": {
            "eligibility_gate": "第一项只评价王朝奠基人；非奠基者为空分不适用",
            "A1": "读取奠基项目扣除起点继承后的王朝级新增净控制和终点完成；不再按个人战役路线切分，个人军事统筹与战区贡献只归C1/C2；起点按同期开局各主要势力资源份额计算；对手压力由公共战役战场压力与同期相对资源压力各占50%，兼顾战斗力和敌我体量；环境复杂度取开局资源分布的信息熵",
            "A2": "具名非战役正向战略锚点经具名误判折损后占60%，时间效率与控制韧性各占15%，早期稳定占10%；无奠基覆盖率封顶",
            "error_boundary": "只登记具名误判事件并按统一严重度合成；无事件即零负担；玄武门之变不进入第一项",
            "decision_boundary": "正向锚点只评价根据地、政治时机、合法性、总体夺权路径和重大纠偏；战役路线、战区统筹、主力歼灭和前线指挥只归C1/C2",
            "inheritance_boundary": "继承、辅政、摄政、政变或禅代时已经有效控制的国家机器是起点资源，不是本人新增战略成果",
            "D_merge": "原D的起点、对手、环境和超额完成度已进入A1，不再单列D",
            "formula_contract": efficiency_inputs["formula_contract"],
        },
        "source_refs": {
            "roster": "docs/评分结算/第三项军事与边疆净收益/02-秦至唐第三项正式结算.json",
            "strategic_inputs": "config/first-item-a-strategic-efficiency-inputs.json",
            "competitive_landscapes": "config/first-item-a-competitive-landscapes.json",
            "battle_registry": "docs/公共成果/军事/01-秦至唐战役登记.json",
            "acquisition_windows": "config/first-item-c-acquisition-windows.json",
            "region_context": "config/first-item-c-territorial-control-adjudications.json",
        },
        "record_count": len(records),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "score_ready_count": len(records),
        "unresolved_count": 0,
        "scope_status_counts": dict(sorted(scope_counts.items())),
        "opponent_threat_source_counts": dict(sorted(Counter(
            str(row["A1"]["opponent_threat_source_status"]) for row in eligible
        ).items())),
        "formal_score_write": False,
        "database_write": False,
        "ranking_write": False,
        "score_range": {
            "minimum": min(float(row["A_score_points"]) for row in eligible),
            "maximum": max(float(row["A_score_points"]) for row in eligible),
        },
        "records": records,
    }


def render_first_item_a_registry_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 秦至唐第一项A创业战略能力结算",
        "",
        "> 当前值只用于公式和归责校准，不写正式评分数据库。原D创业难度已经进入A1；既有国家机器一律算起点，不算新增成果。",
        "> 共同奠基者共享项目级客观基线，人物差异由具名非战役战略锚点和具名误判结算；战役路线与军事统筹只归C1/C2。",
        "",
        f"- 名册对象：{payload['record_count']} 人",
        f"- 奠基者完整结算：{payload['eligible_count']} 人",
        "- canonical状态：CURRENT；本文件是A项当前唯一有效结果",
        f"- 非奠基者不适用：{payload['excluded_count']} 人",
        f"- 未决：{payload['unresolved_count']} 人",
        "",
        "| A项序 | 对象 | 政权 | 起点份额 | 主要对手数 | 对手压力 | 王朝级净控制 | 加权取得年 | 全部闭合年 | 项目完成 | 正向锚点 | 误判负担 | A1/60 | A2/40 | A/100 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    eligible = [row for row in payload["records"] if row["score_applicable"]]
    for row in eligible:
        a1, a2 = row["A1"], row["A2"]
        lines.append(
            f"| {row['canonical_rank']} | {row['ruler_name']} | {row.get('polity') or '—'} | "
            f"{a1['starting_resource_share']:.1f}% | {a1['major_opponent_count']} | {a1['opponent_pressure']:.1f}% | {a1['created_net_control_value']:.2f} | "
            f"{a2['value_weighted_acquisition_years']:.1f} | {a2['closure_years']:.1f} | "
            f"{a1['terminal_completion_rate']:.0f}% | "
            f"{a2['strategic_positive_anchor']['impact']} | "
            f"{a2['strategic_error_burden_rate']:.0f}% | "
            f"{a1['points']:.1f} | {a2['points']:.1f} | {row['A_score_points']:.1f} |"
        )
    lines.extend(["", "## 逐人边界", ""])
    def render_threat(encounter: Mapping[str, Any]) -> str:
        if "campaign_ref" in encounter:
            return (
                f"{encounter['campaign_ref']} {encounter['field_threat_rate']:.2f}%"
                f"（负荷{encounter['strategic_load_units']:.4f}）"
            )
        return (
            f"{encounter['opponent']} {encounter['pressure_rate']:.2f}%"
            f"（成果权重{encounter['stake_units']:g}）"
        )
    for row in eligible:
        lines.extend([
            f"### {row['canonical_rank']}. {row['ruler_name']}", "",
            f"- 窗口：{row['start_boundary']} → {row['end_boundary']}。",
            f"- 起点：{row['starting_position']}。",
            f"- 起点资源份额：{row['A1']['starting_resource_share']:.2f}%；竞争格局分散度：{row['A1']['competitive_fragmentation']:.2f}%。",
            f"- 奠基项目完成：{row['A1']['terminal_completion_rate']:.2f}%；个人战役路线与军事统筹不在A重复归责，统一由C1/C2结算。",
            f"- 正向战略锚点：{row['A2']['strategic_positive_anchor']['event']}（{row['A2']['strategic_positive_anchor']['impact']}，锚点率{row['A2']['strategic_positive_anchor_rate']:.2f}%）。",
            "- 主要对手压力：" + "；".join(
                render_threat(encounter)
                for encounter in row["A1"]["major_opponent_encounters"]
            ) + (
                f"；战场压力{row['A1']['battlefield_pressure']:.2f}%、"
                f"相对资源压力{row['A1']['relative_resource_pressure']:.2f}%、"
                f"综合值{row['A1']['opponent_pressure']:.2f}%"
                if row["A1"]["battlefield_pressure"] is not None
                else f"；相对资源压力{row['A1']['relative_resource_pressure']:.2f}%"
            ) + f"（{row['A1']['opponent_threat_source_status']}）。",
            f"- 归责：{row['responsibility_basis']}", "",
        ])
        if row["strategic_error_events"]:
            lines.insert(
                len(lines) - 1,
                "- 战略误判：" + "；".join(
                    f"{event['event']}（{event['severity']}）" for event in row["strategic_error_events"]
                ) + "。",
            )
    excluded = [row for row in payload["records"] if not row["score_applicable"]]
    lines.extend([
        "## 非奠基者不适用", "",
        "以下对象A1、A2和A总分均为空值：", "",
        "、".join(str(row["ruler_name"]) for row in excluded) + "。", "",
        "## 机器读取", "",
        "同目录JSON是唯一机器读取源；本文件仅为同值阅读视图。", "",
    ])
    return "\n".join(lines)


def write_first_item_a_registry(workspace_root: Path) -> dict[str, Path]:
    def load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    payload = build_first_item_a_registry(
        efficiency_inputs=load(workspace_root / "config/first-item-a-strategic-efficiency-inputs.json"),
        competitive_landscapes=load(workspace_root / "config/first-item-a-competitive-landscapes.json"),
        battle_registry=load(workspace_root / "docs/公共成果/军事/01-秦至唐战役登记.json"),
        territorial_inputs=load(workspace_root / "config/first-item-c-territorial-control-adjudications.json"),
        acquisition_windows=load(workspace_root / "config/first-item-c-acquisition-windows.json"),
        roster=load(workspace_root / "docs/评分结算/第三项军事与边疆净收益/02-秦至唐第三项正式结算.json"),
    )
    output_dir = workspace_root / "docs/评分结算/第一项创业与政权取得能力/战略决策能力"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "01-秦至唐第一项A战略决策能力结算.json"
    markdown_path = output_dir / "01-秦至唐第一项A战略决策能力结算.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_first_item_a_registry_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}
