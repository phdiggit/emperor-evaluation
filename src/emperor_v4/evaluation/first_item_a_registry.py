from __future__ import annotations

import json
import hashlib
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.evaluation.battle_registry_store import load_battle_registry


ELIGIBLE_STATUS = "ELIGIBLE_DYNASTY_FOUNDER"
EXCLUDED_STATUS = "NOT_APPLICABLE_NON_FOUNDER"
PENDING_STATUS = "PENDING_FOUNDER_EVIDENCE"
RATE_FIELDS = (
    "terminal_completion_rate",
    "control_retention_rate",
    "early_stability_rate",
)


def load_qin_qing_first_item_roster(
    workspace_root: Path,
    efficiency_inputs: Mapping[str, Any],
    *,
    include_current_pending_founders: bool = False,
) -> dict[str, Any]:
    base = json.loads(
        (
            workspace_root
            / "docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    base_by_name = {
        str(row["ruler_name"]): dict(row) for row in base.get("records") or ()
    }
    founder_metadata = {
        str(row["ruler_name"]): dict(row)
        for row in efficiency_inputs.get("founder_roster") or ()
    }
    names = yaml.safe_load(
        (workspace_root / "config/common/所有君主.yml").read_text(encoding="utf-8")
    )
    if not isinstance(names, list) or not names:
        raise ValueError("秦至清所有君主名册为空或格式无效")
    normalized = [str(name) for name in names]
    if len(normalized) != len(set(normalized)):
        raise ValueError("秦至清所有君主名册存在重复姓名")
    extra_founders = set(founder_metadata) - set(normalized)
    canonical_by_name: dict[str, dict[str, Any]] = {}
    if extra_founders:
        canonical_pool = json.loads(
            (workspace_root / "config/common/canonical-ruler-pool.json").read_text(
                encoding="utf-8"
            )
        )
        canonical_by_name = {
            str(row["ruler_name"]): dict(row)
            for row in canonical_pool.get("records") or ()
        }
        invalid_extras = {
            name
            for name in extra_founders
            if name not in canonical_by_name
            or canonical_by_name[name].get("pool_status") != "INCLUDED"
            or canonical_by_name[name].get("first_item_readiness")
            not in {
                "PENDING_FIRST_ITEM_FORMAL_SETTLEMENT",
                "FORMAL_RECORD_PRESENT",
                "FORMAL_RECORD_PRESENT_ALIAS_NORMALIZED",
            }
        }
        if invalid_extras:
            raise ValueError(
                "第一项扩展奠基人不在当前正式池待结算或已结算名单: "
                f"{sorted(invalid_extras)}"
            )
        if include_current_pending_founders:
            normalized.extend(sorted(extra_founders))

    records: list[dict[str, Any]] = []
    for name in normalized:
        row = dict(base_by_name.get(name) or canonical_by_name.get(name) or {})
        row.update(founder_metadata.get(name) or {})
        stable_suffix = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16].upper()
        records.append(
            {
                "ruler_id": row.get("ruler_id") or f"RULER-ROSTER-{stable_suffix}",
                "ruler_name": name,
                "polity": row.get("polity"),
                "reign_range": row.get("reign_range"),
            }
        )
    return {
        "schema_version": "first-item-qin-qing-ruler-roster-v1",
        "record_count": len(records),
        "records": records,
    }


def _a1_axis(row: Mapping[str, Any]) -> dict[str, Any]:
    personal_start_disadvantage = float(row["starting_resource_disadvantage"])
    contribution_start_field = row["contribution_start_field"]
    contribution_units = float(contribution_start_field["subject_units"])
    contribution_total = contribution_units + sum(
        float(value) for value in contribution_start_field["other_actors"].values()
    )
    if contribution_total <= 0:
        raise ValueError("第一项A可归责贡献起点资源总量必须大于0")
    project_start_share = contribution_units / contribution_total
    project_start_disadvantage = 1.0 - project_start_share
    opponent = float(row["opponent_pressure"])
    complexity = float(row["environment_complexity"])
    completion = float(row["terminal_completion_rate"])
    responsibility = float(row["a1_strategic_responsibility_factor"])
    start_difficulty = (
        0.30 * personal_start_disadvantage
        + 0.70 * project_start_disadvantage
    )
    pure_difficulty = 0.50 * opponent + 0.50 * start_difficulty
    difficulty = min(1.0, pure_difficulty / 0.85)
    attributed_completion = completion * responsibility
    result_rate = attributed_completion
    rate = result_rate * difficulty
    return {
        "axis": "A1",
        "name": "创业战略增益与难度兑现",
        "starting_resource_share": round(100 * float(row["starting_resource_share"]), 2),
        "starting_resource_disadvantage": round(100 * personal_start_disadvantage, 2),
        "project_start_resource_share": round(100 * project_start_share, 2),
        "project_start_resource_disadvantage": round(100 * project_start_disadvantage, 2),
        "contribution_start_field": contribution_start_field,
        "opponent_pressure": round(100 * opponent, 2),
        "opponent_system_pressure": (
            round(100 * float(row["opponent_system_pressure"]), 2)
            if row["opponent_system_pressure"] is not None else None
        ),
        "relative_resource_pressure": round(100 * float(row["relative_resource_pressure"]), 2),
        "major_opponent_count": len(row["major_opponent_systems"]),
        "major_opponent_systems": row["major_opponent_systems"],
        "unknown_opponent_campaign_refs": row["unknown_opponent_campaign_refs"],
        "opponent_threat_source_status": row["opponent_threat_source_status"],
        "opponent_threat_routing_basis": row["opponent_threat_routing_basis"],
        "competitive_fragmentation": round(100 * complexity, 2),
        "a1_strategic_responsibility_factor": round(100 * responsibility, 2),
        "a1_strategic_responsibility_basis": str(
            row["a1_strategic_responsibility_basis"]
        ),
        "start_difficulty_rate": round(100 * start_difficulty, 2),
        "pure_difficulty_rate": round(100 * pure_difficulty, 2),
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
    created_control = float(row["created_net_control_value"])
    recovered_control = float(row.get("recovered_net_control_value") or 0.0)
    gross_control = created_control + recovered_control
    effective_control = created_control + 0.50 * recovered_control
    raw_control_scale = min(1.0, effective_control / 1000.0) if effective_control > 0 else 0.0
    control_scale_score = math.sqrt(raw_control_scale)
    retention = float(row["control_retention_rate"])
    completion = float(row["terminal_completion_rate"])
    stability = float(row["early_stability_rate"])
    error_points = float(row["strategic_error_points"])
    positive_decision_points = float(row["strategic_positive_decision_points"])
    acquisition_efficiency = effective_control / weighted_years if weighted_years > 0 else 0.0
    acquisition_pace = min(1.0, (acquisition_efficiency / 100.0) ** 0.35) if acquisition_efficiency > 0 else 0.0
    expected_closure_years = 8.0 * math.sqrt(effective_control / 550.25) if effective_control > 0 else 0.0
    closure_pace = min(1.0, expected_closure_years / years) if years > 0 else 0.0
    time_rate = 0.60 * acquisition_pace + 0.40 * closure_pace
    durability = 0.60 * retention + 0.40 * stability
    objective_points = 36 * control_scale_score * (
        0.50 + 0.25 * time_rate + 0.25 * durability
    )
    points = max(
        0.0,
        min(40.0, objective_points + positive_decision_points - error_points),
    )
    return {
        "axis": "A2",
        "name": "创业路线效率与稳固",
        "created_net_control_value": round(created_control, 2),
        "recovered_net_control_value": round(recovered_control, 2),
        "gross_unification_control_value": round(gross_control, 2),
        "effective_unification_control_value": round(effective_control, 2),
        "recovered_control_scoring_rate": 50.0,
        "raw_control_scale_rate": round(100 * raw_control_scale, 2),
        "control_scale_score_rate": round(100 * control_scale_score, 2),
        "closure_years": round(years, 2),
        "value_weighted_acquisition_years": round(weighted_years, 2),
        "control_acquisition_efficiency": round(acquisition_efficiency, 2),
        "acquisition_pace_rate": round(100 * acquisition_pace, 2),
        "scale_expected_closure_years": round(expected_closure_years, 2),
        "closure_pace_rate": round(100 * closure_pace, 2),
        "time_rate": round(100 * time_rate, 2),
        "control_retention_rate": round(100 * retention, 2),
        "durability_rate": round(100 * durability, 2),
        "terminal_completion_rate": round(100 * completion, 2),
        "early_stability_rate": round(100 * stability, 2),
        "strategic_positive_decisions": list(row["strategic_positive_decisions"]),
        "objective_result_points": round(objective_points, 1),
        "strategic_positive_decision_points": round(positive_decision_points, 1),
        "strategic_error_points": round(error_points, 1),
        "strategic_error_events": list(row["strategic_error_events"]),
        "rate": round(100 * points / 40.0, 2),
        "weight": 40,
        "points": round(points, 1),
    }


def build_first_item_a_registry(
    *, efficiency_inputs: Mapping[str, Any], competitive_landscapes: Mapping[str, Any],
    battle_registry: Mapping[str, Any], territorial_inputs: Mapping[str, Any],
    acquisition_windows: Mapping[str, Any], roster: Mapping[str, Any]
) -> dict[str, Any]:
    if efficiency_inputs.get("schema_version") != "first-item-a-strategic-efficiency-inputs-v18":
        raise ValueError("第一项A量化输入schema_version不正确")
    if efficiency_inputs.get("status") != "CURRENT":
        raise ValueError("第一项A量化输入状态不正确")
    if competitive_landscapes.get("schema_version") != "first-item-a-competitive-landscapes-v9":
        raise ValueError("第一项A竞争格局输入schema_version不正确")
    if competitive_landscapes.get("status") != "CURRENT":
        raise ValueError("第一项A竞争格局输入状态不正确")

    a2_c_lineage = dict(efficiency_inputs.get("a2_c_lineage") or {})

    battle_records = list(battle_registry.get("records") or ())
    battle_by_ref = {str(row["war_event_id"]): row for row in battle_records}
    current_portfolios = list(
        battle_registry.get("unification_campaign_portfolios") or ()
    )
    if len(battle_by_ref) != len(battle_records):
        raise ValueError("公共战役登记存在重复标识")
    opponent_system_windows = dict(
        competitive_landscapes.get("opponent_system_windows") or {}
    )
    supplemental_systems = dict(
        competitive_landscapes.get("supplemental_opponent_systems") or {}
    )
    relative_only_justifications = dict(
        competitive_landscapes.get("relative_only_threat_justifications") or {}
    )
    canonical_systems: dict[str, dict[str, Any]] = {}
    for portfolio in current_portfolios:
        for raw_system in portfolio.get("opponent_systems") or ():
            system_id = str(raw_system.get("system_id") or "")
            system = dict(raw_system)
            system.pop("system_id", None)
            if not system_id or (
                system_id in canonical_systems and canonical_systems[system_id] != system
            ):
                raise ValueError(f"统一链对手体系标识无效或漂移: {system_id}")
            canonical_systems[system_id] = system
    overlap = set(canonical_systems) & set(supplemental_systems)
    if overlap:
        raise ValueError(f"第一项A补充O体系与公共统一链重复: {sorted(overlap)}")
    opponent_systems = {**canonical_systems, **supplemental_systems}
    grade_rates = {
        "O1": 0.15,
        "O2": 0.30,
        "O3": 0.50,
        "O4": 0.70,
        "O5": 0.85,
        "O6": 1.00,
    }
    position_weights = (0.55, 0.20, 0.10, 0.07, 0.04)

    def compile_opponent_system_pressure(
        ruler_name: str,
    ) -> tuple[float, list[dict[str, Any]], list[str], str, str] | None:
        window = dict(opponent_system_windows.get(ruler_name) or {})
        if not window:
            return None
        system_refs = [str(ref) for ref in window.get("system_refs") or ()]
        if not system_refs or len(system_refs) != len(set(system_refs)):
            raise ValueError(f"第一项A人物O体系引用为空或重复: {ruler_name}")
        details = []
        for system_ref in system_refs:
            system = opponent_systems.get(system_ref)
            if system is None:
                raise ValueError(f"第一项A人物O体系引用不存在: {ruler_name}/{system_ref}")
            grade = str(system.get("organization_grade") or "")
            label = str(system.get("opponent_label") or "")
            basis = str(system.get("basis") or "")
            source_refs = [str(ref) for ref in system.get("source_campaign_refs") or ()]
            if grade not in grade_rates or not label or not basis or not source_refs:
                raise ValueError(f"第一项A人物O体系字段无效: {ruler_name}/{system_ref}")
            if str(system.get("closure") or "") == "RECOVERY_SAME_SYSTEM":
                lineage_parent = str(system.get("lineage_parent") or "")
                if not lineage_parent or lineage_parent not in system_refs:
                    raise ValueError(
                        f"第一项A同体系恢复阶段缺少同窗口父体系: "
                        f"{ruler_name}/{system_ref}/{lineage_parent}"
                    )
                continue
            details.append({
                "opponent_system_ref": system_ref,
                "opponent_label": label,
                "organization_grade": grade,
                "organization_rate": round(100 * grade_rates[grade], 2),
                "source_campaign_refs": source_refs,
            })
        details.sort(
            key=lambda item: (
                -grade_rates[str(item["organization_grade"])],
                str(item["opponent_system_ref"]),
            )
        )
        pressure = sum(
            position_weights[index] * grade_rates[str(item["organization_grade"])]
            for index, item in enumerate(details[:5])
        )
        if len(details) > 5:
            pressure += 0.04 * sum(
                grade_rates[str(item["organization_grade"])] for item in details[5:]
            ) / len(details[5:])
        unknown_refs = [str(ref) for ref in window.get("unknown_campaign_refs") or ()]
        if len(unknown_refs) != len(set(unknown_refs)):
            raise ValueError(f"第一项A人物unknown战役引用重复: {ruler_name}")
        return (
            min(1.0, pressure),
            details,
            unknown_refs,
            "OPPONENT_SYSTEM_O_GRADE_WITH_RELATIVE_RESOURCES",
            str(window.get("basis") or "贡献窗口内独立战争机器去重"),
        )

    roster_rows = list(roster.get("records") or ())
    roster_by_name = {str(row["ruler_name"]): row for row in roster_rows}
    if len(roster_by_name) != len(roster_rows):
        raise ValueError("第一项A名册存在重复ruler_name")
    input_rows = list(efficiency_inputs.get("records") or ())
    input_by_name = {str(row["ruler_name"]): row for row in input_rows}
    founder_metadata = {
        str(row["ruler_name"]): row
        for row in efficiency_inputs.get("founder_roster") or ()
    }
    if len(input_by_name) != len(input_rows):
        raise ValueError("第一项A量化输入存在重复ruler_name")
    unknown = set(input_by_name) - set(roster_by_name)
    if unknown:
        raise ValueError(f"第一项A量化输入包含名册外对象: {sorted(unknown)}")
    control_values = dict(efficiency_inputs.get("created_net_control_values") or {})
    recovered_control_values = dict(
        efficiency_inputs.get("recovered_net_control_values") or {}
    )
    weighted_years = dict(efficiency_inputs.get("value_weighted_acquisition_years") or {})
    landscape_rows = list(competitive_landscapes.get("records") or ())
    landscape_by_name = {str(row["ruler_name"]): row for row in landscape_rows}
    if len(landscape_by_name) != len(landscape_rows):
        raise ValueError("第一项A竞争格局存在重复ruler_name")
    error_events = dict(efficiency_inputs.get("strategic_error_events") or {})
    error_reviews = dict(efficiency_inputs.get("strategic_error_reviews") or {})
    positive_decisions = dict(efficiency_inputs.get("strategic_positive_decisions") or {})
    class_values = dict(efficiency_inputs.get("class_values") or {})
    severity_points = dict(class_values.get("strategic_error_points") or {})
    positive_decision_points = dict(class_values.get("positive_decision_points") or {})
    positive_position_weights = [
        float(value)
        for value in class_values.get("positive_decision_position_weights") or ()
    ]
    initial_resource_rubric = {
        str(row["class"]): dict(row)
        for row in class_values.get("initial_resource_share_rubric") or ()
    }
    if not initial_resource_rubric:
        raise ValueError("第一项A个人原始起点资源档位合同为空")
    input_names = set(input_by_name)
    aligned_a2_names = {str(name) for name in a2_c_lineage.get("aligned_names") or ()}
    pending_a2_names = {str(name) for name in a2_c_lineage.get("pending_names") or ()}
    supplemental_a2_names = {
        str(name)
        for name in a2_c_lineage.get("supplemental_control_window_names") or ()
    }
    supplemental_a2_rows = {
        str(row["ruler_name"]): row
        for row in territorial_inputs.get("a2_control_window_adjudications") or ()
    }
    if (
        aligned_a2_names & pending_a2_names
        or aligned_a2_names | pending_a2_names != input_names
        or not str(a2_c_lineage.get("policy") or "").strip()
    ):
        raise ValueError("第一项A2与C控制底账的人物血缘集合不闭合")
    if set(supplemental_a2_rows) != supplemental_a2_names:
        raise ValueError("第一项A2补充控制窗口与C控制底账名单不一致")
    for ruler_name, adjudication in supplemental_a2_rows.items():
        if (
            adjudication.get("adjudication_status")
            != "CALIBRATED_C_CONTROL_WINDOW"
            or not adjudication.get("source_refs")
            or not str(adjudication.get("basis") or "").strip()
            or float(adjudication["created_net_control_value"])
            != float(control_values[ruler_name])
            or float(adjudication.get("recovered_net_control_value") or 0.0)
            != float(recovered_control_values.get(ruler_name) or 0.0)
            or float(adjudication["value_weighted_acquisition_years"])
            != float(weighted_years[ruler_name])
        ):
            raise ValueError(f"第一项A2补充控制窗口未与计分输入等值: {ruler_name}")
    if any(set(values) != input_names for values in (control_values, weighted_years, landscape_by_name)):
        raise ValueError("第一项A净控制量、时间或竞争格局未完整覆盖奠基者")
    if set(recovered_control_values) - input_names:
        raise ValueError("第一项A恢复控制量包含非结算对象")
    if set(error_events) != input_names or set(error_reviews) != input_names:
        raise ValueError("第一项A战略误判事件或复核状态未完整覆盖结算对象")
    if relative_only_justifications:
        raise ValueError("第一项A不再允许纯相对资源路由；所有适用对象必须建立O体系")
    if set(opponent_system_windows) != input_names:
        raise ValueError("第一项A人物O体系窗口未完整覆盖全部适用对象")
    if set(positive_decisions) != input_names:
        raise ValueError("第一项A正向战略决策未完整覆盖奠基者")
    if (
        severity_points != {
            "MINOR": 1.0,
            "MATERIAL": 2.0,
            "MAJOR": 5.0,
            "CRITICAL": 10.0,
        }
        or positive_decision_points != {
            "MATERIAL": 1.0,
            "MAJOR": 3.0,
            "DECISIVE": 5.0,
            "EXCEPTIONAL": 8.0,
        }
        or positive_position_weights != [1.0, 0.5]
    ):
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
            metadata = founder_metadata.get(ruler_name) or {}
            pending = str(metadata.get("eligibility_decision") or "") in {
                "PENDING",
                "UNKNOWN",
            }
            records.append({
                **common,
                "scope_status": PENDING_STATUS if pending else EXCLUDED_STATUS,
                "score_applicable": False,
                "founder_role": None,
                "A1": None,
                "A2": None,
                "A_score_points": None,
                "canonical_rank": None,
                "basis": str(
                    metadata.get("eligibility_basis")
                    or (
                        "存在统一链贡献可能，但人物归责或窗口证据尚未闭合"
                        if pending
                        else "普通继承、守成扩张或未在本名册所属政权中承担奠基责任"
                    )
                ),
            })
            continue

        required = (
            "founder_role", "start_boundary", "end_boundary", "starting_position",
            "difficulty_start_boundary", "initial_resource_position",
            "initial_resource_share_pct",
            "a1_strategic_responsibility_factor",
            "a1_strategic_responsibility_basis",
            "initial_resource_source_status",
            "initial_resource_class",
            "initial_resource_share_basis",
            "evidence_status_basis",
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
        responsibility = float(decision["a1_strategic_responsibility_factor"])
        if not 0 < responsibility <= 1:
            raise ValueError(f"第一项A战略责任强度越界: {ruler_name}")
        initial_source_refs = list(decision.get("initial_resource_source_refs") or ())
        initial_source_status = str(decision["initial_resource_source_status"])
        initial_resource_class = str(decision["initial_resource_class"])
        initial_resource_share_basis = str(decision["initial_resource_share_basis"])
        resource_band = initial_resource_rubric.get(initial_resource_class)
        if (
            not initial_source_refs
            or initial_source_status != "SOURCE_ANCHORED_RULE_MAPPED"
            or not initial_resource_share_basis.strip()
            or resource_band is None
            or not float(resource_band["min_pct"])
            <= float(decision["initial_resource_share_pct"])
            <= float(resource_band["max_pct"])
        ):
            raise ValueError(f"第一项A个人原始起点缺少可审计规则映射: {ruler_name}")
        if (
            ruler_name in pending_a2_names
            and decision.get("evidence_status") != "CALIBRATED_EVIDENCE_LOWER_BOUND"
        ):
            raise ValueError(f"第一项A2尚未与C闭合却未保留证据下限: {ruler_name}")

        terminal_completion = float(decision["terminal_completion_rate"])
        control_value = float(control_values[ruler_name])
        recovered_control_value = float(recovered_control_values.get(ruler_name) or 0.0)
        acquisition_years = float(weighted_years[ruler_name])
        landscape = landscape_by_name[ruler_name]
        contribution_start_field = dict(landscape.get("start_field") or {})
        subject_units = float(contribution_start_field.get("subject_units") or 0)
        other_actors = dict(contribution_start_field.get("other_actors") or {})
        actor_units = [subject_units, *(float(value) for value in other_actors.values())]
        if subject_units < 0 or not other_actors or any(value < 0 for value in actor_units):
            raise ValueError(f"第一项A起点竞争格局无效: {ruler_name}")
        start_total = sum(actor_units)
        if start_total <= 0:
            raise ValueError(f"第一项A起点竞争格局总量无效: {ruler_name}")
        start_share = float(decision["initial_resource_share_pct"]) / 100.0
        if not 0 <= start_share <= 1:
            raise ValueError(f"第一项A初始资源份额越界: {ruler_name}")
        start_disadvantage = 1 - start_share
        shares = [value / start_total for value in actor_units if value > 0]
        complexity = (
            -sum(share * math.log(share) for share in shares) / math.log(len(shares))
            if len(shares) > 1
            else 0.0
        )
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
        compiled_threat = compile_opponent_system_pressure(ruler_name)
        if compiled_threat is None:
            raise ValueError(f"第一项A人物缺少O体系窗口: {ruler_name}")
        (
            opponent_system_pressure,
            threat_details,
            unknown_opponent_campaign_refs,
            threat_source_status,
            threat_routing_basis,
        ) = compiled_threat
        opponent_pressure = (
            0.70 * opponent_system_pressure
            + 0.30 * fallback_opponent_pressure
        )
        if control_value < 0 or acquisition_years <= 0:
            raise ValueError(f"第一项A净控制量或加权时间越界: {ruler_name}")
        person_errors = list(error_events.get(ruler_name) or ())
        error_review = dict(error_reviews[ruler_name])
        error_review_status = str(error_review.get("review_status") or "")
        searched_error_refs = list(error_review.get("searched_evidence_refs") or ())
        expected_review_status = (
            "REVIEWED_ERRORS"
            if person_errors
            else "REVIEWED_NO_THRESHOLD_ERROR"
        )
        if (
            error_review_status != expected_review_status
            or not searched_error_refs
            or (
                not person_errors
                and not str(error_review.get("no_error_basis") or "")
            )
        ):
            raise ValueError(f"第一项A战略误判复核状态无效: {ruler_name}")
        error_point_total = 0.0
        seen_error_names: set[str] = set()
        for event in person_errors:
            event_name = str(event.get("event") or "")
            severity = str(event.get("severity") or "")
            basis = str(event.get("basis") or "")
            source_refs = list(event.get("source_refs") or ())
            c_nonduplication_basis = str(
                event.get("c_nonduplication_basis") or ""
            )
            if (
                not event_name
                or event_name in seen_error_names
                or severity not in severity_points
                or not basis
                or not source_refs
                or not c_nonduplication_basis
            ):
                raise ValueError(f"第一项A战略误判事件无效: {ruler_name}/{event_name}")
            seen_error_names.add(event_name)
            error_point_total += float(severity_points[severity])
        source_positive_decisions = list(positive_decisions[ruler_name])
        if len(source_positive_decisions) > len(positive_position_weights):
            raise ValueError(f"第一项A正向战略决策数量无效: {ruler_name}")
        parsed_positive_decisions = []
        seen_positive_events: set[str] = set()
        for positive_decision in source_positive_decisions:
            event_name = str(positive_decision.get("event") or "")
            impact = str(positive_decision.get("impact") or "")
            basis = str(positive_decision.get("basis") or "")
            source_refs = list(positive_decision.get("source_refs") or ())
            if (
                not event_name
                or event_name in seen_positive_events
                or impact not in positive_decision_points
                or not basis
                or not source_refs
            ):
                raise ValueError(f"第一项A正向战略决策无效: {ruler_name}/{event_name}")
            seen_positive_events.add(event_name)
            parsed_positive_decisions.append({
                **dict(positive_decision),
                "event": event_name,
                "impact": impact,
                "basis": basis,
                "source_refs": source_refs,
                "base_points": float(positive_decision_points[impact]),
            })
        parsed_positive_decisions.sort(
            key=lambda item: (-float(item["base_points"]), str(item["event"]))
        )
        positive_point_total = 0.0
        for position, (positive_decision, position_weight) in enumerate(
            zip(parsed_positive_decisions, positive_position_weights), start=1
        ):
            positive_decision["position"] = position
            positive_decision["position_weight"] = position_weight
            positive_decision["effective_points"] = round(
                float(positive_decision["base_points"]) * position_weight, 2
            )
            positive_point_total += float(positive_decision["effective_points"])
        calculation_input = {
            **decision,
            "terminal_completion_rate": terminal_completion,
            "strategic_error_points": error_point_total,
            "strategic_error_events": person_errors,
            "strategic_error_review": error_review,
            "strategic_positive_decision_points": positive_point_total,
            "strategic_positive_decisions": parsed_positive_decisions,
            "created_net_control_value": control_value,
            "recovered_net_control_value": recovered_control_value,
            "value_weighted_acquisition_years": acquisition_years,
            "starting_resource_share": start_share,
            "starting_resource_disadvantage": start_disadvantage,
            "contribution_start_field": {
                "subject_units": subject_units,
                "other_actors": other_actors,
            },
            "opponent_pressure": opponent_pressure,
            "opponent_system_pressure": opponent_system_pressure,
            "relative_resource_pressure": fallback_opponent_pressure,
            "major_opponent_systems": threat_details,
            "unknown_opponent_campaign_refs": unknown_opponent_campaign_refs,
            "opponent_threat_source_status": threat_source_status,
            "opponent_threat_routing_basis": threat_routing_basis,
            "environment_complexity": complexity,
        }
        a1 = _a1_axis(calculation_input)
        a2 = _a2_axis(calculation_input)
        evidence_status = str(
            decision.get("evidence_status") or "CALIBRATED_CURRENT"
        )
        evidence_status_basis = str(decision["evidence_status_basis"])
        limitations: list[str] = []
        if ruler_name in pending_a2_names:
            limitations.append("A2控制量尚待纳入第一项C标准控制窗口并完成等值裁决")
        if evidence_status != "CALIBRATED_CURRENT" and not limitations:
            limitations.append(evidence_status_basis)
        if unknown_opponent_campaign_refs:
            limitations.append(
                "仍有未完成O体系归并的贡献窗口战役："
                + "、".join(unknown_opponent_campaign_refs)
            )
        records.append({
            **common,
            "scope_status": ELIGIBLE_STATUS,
            "score_applicable": True,
            "founder_role": decision["founder_role"],
            "difficulty_start_boundary": decision["difficulty_start_boundary"],
            "initial_resource_position": decision["initial_resource_position"],
            "initial_resource_share_pct": float(decision["initial_resource_share_pct"]),
            "initial_resource_source_refs": list(
                decision.get("initial_resource_source_refs") or ()
            ),
            "initial_resource_source_status": initial_source_status,
            "initial_resource_class": initial_resource_class,
            "initial_resource_share_basis": initial_resource_share_basis,
            "start_boundary": decision["start_boundary"],
            "end_boundary": decision["end_boundary"],
            "starting_position": decision["starting_position"],
            "A1": a1,
            "A2": a2,
            "strategic_error_events": person_errors,
            "strategic_error_review": error_review,
            "A_score_points": round(a1["points"] + a2["points"], 1),
            "canonical_rank": None,
            "responsibility_basis": decision["responsibility_basis"],
            "evidence_status": evidence_status,
            "evidence_status_basis": evidence_status_basis,
            "evidence_lower_bound": bool(limitations),
            "limitations": limitations,
            "unknown_control_scope": decision.get("unknown_control_scope"),
            "source_refs": list(
                (founder_metadata.get(ruler_name) or {}).get("evidence_refs")
                or ()
            ),
        })

    eligible = sorted(
        (row for row in records if row["score_applicable"]),
        key=lambda row: (-float(row["A_score_points"]), -float(row["A1"]["rate"]), str(row["ruler_name"])),
    )
    for rank, row in enumerate(eligible, start=1):
        row["canonical_rank"] = rank
    non_scored = sorted(
        (row for row in records if not row["score_applicable"]),
        key=lambda row: str(row["ruler_name"]),
    )
    pending = [row for row in non_scored if row["scope_status"] == PENDING_STATUS]
    excluded = [row for row in non_scored if row["scope_status"] == EXCLUDED_STATUS]
    records = eligible + pending + excluded
    scope_counts = Counter(str(row["scope_status"]) for row in records)
    return {
        "schema_version": "first-item-a-registry-v8",
        "canonical_status": "CURRENT",
        "status": "CURRENT_NOT_FORMAL_DATABASE_WRITE",
        "item": "第一项A创业战略能力（已吸收原D创业难度）",
        "max_points": 100,
        "method": {
            "eligibility_gate": "第一项评价对本王朝建国或统一主链具有实际可归责贡献者；继承者不自动排除，纯年号、名义最高统治和他人独立成果不生成信用",
            "A1": "不读取净控制量；个人原始起点、项目起点和主要对手压力分别占综合难度15%、35%、50%，并用85%历史前沿锚归一化；A1=60×项目完成率×A1战略责任强度×归一化难度。责任强度不是零和份额，不要求同项目人物合计100%，且不得由C项个人战功倒推",
            "A2": "只读取人物窗口已分账的净控制量，不再重复乘A1责任强度；原始规模率=计分控制量/1000，规模计分率取平方根；取得速度与闭合速度按60%/40%合成，耐久按控制留存60%和早期稳固40%合成。客观结果最高36分，具名非战役正确决策按1/3/5/8分奖励，误判按1/2/5/10分扣除，最终A2限0至40分",
            "error_boundary": f"{len(eligible)}名适用对象均须完成同强度负向复核；只登记本人最高决定造成统一链实质倒退的具名误判，普通败仗留在C；空数组只表示REVIEWED_NO_THRESHOLD_ERROR，不能表示未检索；贡献闭合后5至10年内由同一路线造成的迅速崩解仍进入稳定审计；玄武门之变不进入第一项",
            "decision_boundary": "正向锚点只评价根据地、政治时机、合法性、总体夺权路径和重大纠偏；战役路线、战区统筹、主力歼灭和前线指挥只归C1/C2",
            "inheritance_boundary": "继承、辅政、摄政、政变或禅代时已经有效控制的国家机器是起点资源，不是本人新增战略成果",
            "D_merge": "原D的起点、对手和环境已进入A1，不再单列D；净控制量只进入A2",
            "formula_contract": efficiency_inputs["formula_contract"],
        },
        "source_refs": {
            "roster": "config/common/所有君主.yml + config/first-item/first-item-a-strategic-efficiency-inputs.json#founder_roster",
            "strategic_inputs": "config/first-item/first-item-a-strategic-efficiency-inputs.json",
            "competitive_landscapes": "config/first-item/first-item-a-competitive-landscapes.json",
            "battle_registry": "docs/公共成果/军事/01-战役登记.json",
            "acquisition_windows": "config/first-item/first-item-c-acquisition-windows.json",
            "region_context": "config/first-item/first-item-c-territorial-control-adjudications.json",
        },
        "a2_c_lineage": a2_c_lineage,
        "record_count": len(records),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "score_ready_count": len(eligible) + len(excluded),
        "unresolved_count": len(pending),
        "scope_status_counts": dict(sorted(scope_counts.items())),
        "opponent_threat_source_counts": dict(sorted(Counter(
            str(row["A1"]["opponent_threat_source_status"]) for row in eligible
        ).items())),
        "strategic_error_review_counts": dict(sorted(Counter(
            str(row["strategic_error_review"]["review_status"])
            for row in eligible
        ).items())),
        "strategic_error_event_count": sum(
            len(row["strategic_error_events"]) for row in eligible
        ),
        "strategic_positive_decision_event_count": sum(
            len(row["A2"]["strategic_positive_decisions"]) for row in eligible
        ),
        "a2_cap_count": sum(float(row["A2"]["points"]) == 40.0 for row in eligible),
        "evidence_lower_bound_count": sum(
            bool(row["evidence_lower_bound"]) for row in eligible
        ),
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
        "# 第一项A创业战略能力结算",
        "",
        "> 原D创业难度已经进入A1；净控制量只进入A2，既有国家机器一律算起点，不算新增成果。",
        "> A1战略责任强度不是零和份额，只约束本人对项目难度与完成度的兑现；A2直接读取人物窗口已分账的净控制结果，不重复乘责任强度。战役路线与军事统筹只归C1/C2。",
        "",
        f"共{payload['record_count']}人，其中{payload['eligible_count']}名奠基者进入结算，"
        f"{payload['excluded_count']}名非奠基者不适用。",
        "",
        "| A项序 | 对象 | 政权 | A1责任强度 | 个人原始起点 | 贡献项目起点 | 对手压力 | 控制量 | 原始规模 | 规模计分 | 综合速度 | 耐久 | 决策净值 | A1/60 | A2/40 | A/100 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    eligible = [row for row in payload["records"] if row["score_applicable"]]
    for row in eligible:
        a1, a2 = row["A1"], row["A2"]
        lines.append(
            f"| {row['canonical_rank']} | {row['ruler_name']} | {row.get('polity') or '—'} | "
            f"{a1['a1_strategic_responsibility_factor']:.0f}% | "
            f"{a1['starting_resource_share']:.1f}% | {a1['project_start_resource_share']:.1f}% | {a1['opponent_pressure']:.1f}% | "
            f"{a2['effective_unification_control_value']:.2f} | {a2['raw_control_scale_rate']:.1f}% | "
            f"{a2['control_scale_score_rate']:.1f}% | {a2['time_rate']:.1f}% | {a2['durability_rate']:.1f}% | "
            f"{a2['strategic_positive_decision_points'] - a2['strategic_error_points']:+.1f} | "
            f"{a1['points']:.1f} | {a2['points']:.1f} | {row['A_score_points']:.1f} |"
        )
    lines.extend(["", "## 逐人结算依据", ""])
    def render_threat(encounter: Mapping[str, Any]) -> str:
        if "opponent_system_ref" in encounter:
            return (
                f"{encounter['opponent_label']}"
                f"（{encounter['organization_grade']}）"
            )
        return (
            f"{encounter['opponent']}"
            f"（相对资源压力{encounter['pressure_rate']:.2f}%）"
        )
    for row in eligible:
        lines.extend([
            f"### {row['canonical_rank']}. {row['ruler_name']}", "",
            f"- 难度起点：{row['difficulty_start_boundary']}；初始资源：{row['initial_resource_position']}。",
            (
                "- 起点来源："
                + "；".join(row["initial_resource_source_refs"]) + "。"
                if row["initial_resource_source_refs"]
                else "- 起点来源：沿用人物统一贡献资格与起点复核材料。"
            ),
            f"- 个人起点裁决：{row['initial_resource_share_basis']}",
            f"- 贡献窗口：{row['start_boundary']} → {row['end_boundary']}；窗口位置：{row['starting_position']}。",
            f"- 双起点资源份额：个人原始{row['A1']['starting_resource_share']:.2f}%，可归责贡献项目{row['A1']['project_start_resource_share']:.2f}%；综合难度按个人原始起点15%、项目起点35%、对手压力50%合成。",
            f"- A1战略责任强度：{row['A1']['a1_strategic_responsibility_factor']:.2f}%；{row['A1']['a1_strategic_responsibility_basis']}。项目完成{row['A1']['terminal_completion_rate']:.2f}%，归责后完成{row['A1']['attributed_completion_rate']:.2f}%；个人战役路线与军事统筹只由C1/C2结算。",
            f"- A2统一控制兑现：新增{row['A2']['created_net_control_value']:.2f}，恢复{row['A2']['recovered_net_control_value']:.2f}，原始合计{row['A2']['gross_unification_control_value']:.2f}；恢复按50%折算后计分控制量{row['A2']['effective_unification_control_value']:.2f}。原始规模率{row['A2']['raw_control_scale_rate']:.2f}%，规模计分率{row['A2']['control_scale_score_rate']:.2f}%。",
            (
                "- 正向战略决策：" + "；".join(
                    f"{decision['event']}（{decision['impact']}，位次{decision['position']}，有效奖励{decision['effective_points']:.2f}分；证据：{'、'.join(decision['source_refs'])}）"
                    for decision in row["A2"]["strategic_positive_decisions"]
                ) + f"；合计{row['A2']['strategic_positive_decision_points']:.2f}分。"
                if row["A2"]["strategic_positive_decisions"]
                else "- 正向战略决策：无门槛奖励项，不设保底奖励。"
            ),
            "- 主要对手压力：" + "；".join(
                render_threat(encounter)
                for encounter in row["A1"]["major_opponent_systems"]
            ) + (
                f"；战争机器压力{row['A1']['opponent_system_pressure']:.2f}%、"
                f"相对资源压力{row['A1']['relative_resource_pressure']:.2f}%、"
                f"综合值{row['A1']['opponent_pressure']:.2f}%"
                if row["A1"]["opponent_system_pressure"] is not None
                else f"；缺少可裁决O体系，按相对资源压力{row['A1']['relative_resource_pressure']:.2f}%作为证据下限"
            ) + "。",
            f"- 归责：{row['responsibility_basis']}", "",
        ])
        if row["A1"]["unknown_opponent_campaign_refs"]:
            lines.insert(
                len(lines) - 1,
                "- 未决对手样本：" + "、".join(row["A1"]["unknown_opponent_campaign_refs"]) + "。",
            )
        if row.get("unknown_control_scope"):
            lines.insert(len(lines) - 1, f"- 未覆盖控制：{row['unknown_control_scope']}")
        if row["limitations"]:
            lines.insert(
                len(lines) - 1,
                "- 限制：" + "；".join(row["limitations"]) + "。",
            )
        if row["strategic_error_events"]:
            lines.insert(
                len(lines) - 1,
                "- 战略误判：" + "；".join(
                    f"{event['event']}（{event['severity']}；证据：{'、'.join(event['source_refs'])}）"
                    for event in row["strategic_error_events"]
                ) + "。",
            )
    pending = [
        row for row in payload["records"]
        if row["scope_status"] == PENDING_STATUS
    ]
    excluded = [
        row for row in payload["records"]
        if row["scope_status"] == EXCLUDED_STATUS
    ]
    if pending:
        lines.extend([
            "## 证据待补", "",
            "以下对象存在统一链实际贡献可能，但人物归责或窗口证据尚未闭合，不以0分冒充终值：", "",
            "、".join(str(row["ruler_name"]) for row in pending) + "。", "",
        ])
    lines.extend([
        "## 非奠基者不适用", "",
        "以下对象A1、A2和A总分均为空值：", "",
        "、".join(str(row["ruler_name"]) for row in excluded) + "。", "",
    ])
    return "\n".join(lines)


def write_first_item_a_registry(workspace_root: Path) -> dict[str, Path]:
    def load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    efficiency_inputs = load(
        workspace_root / "config/first-item/first-item-a-strategic-efficiency-inputs.json"
    )
    payload = build_first_item_a_registry(
        efficiency_inputs=efficiency_inputs,
        competitive_landscapes=load(workspace_root / "config/first-item/first-item-a-competitive-landscapes.json"),
        battle_registry=load_battle_registry(
            workspace_root / "docs/公共成果/军事/01-战役登记.json"
        ),
        territorial_inputs=load(workspace_root / "config/first-item/first-item-c-territorial-control-adjudications.json"),
        acquisition_windows=load(workspace_root / "config/first-item/first-item-c-acquisition-windows.json"),
        roster=load_qin_qing_first_item_roster(
            workspace_root,
            efficiency_inputs,
            include_current_pending_founders=True,
        ),
    )
    output_dir = workspace_root / "docs/评分结算/第一项创业与政权取得能力/战略决策能力"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "01-第一项A战略决策能力结算.json"
    markdown_path = output_dir / "01-第一项A战略决策能力结算.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_first_item_a_registry_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}
