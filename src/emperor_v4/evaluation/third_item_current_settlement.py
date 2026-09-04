from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json

from emperor_v4.evaluation.third_item_d_settlement import (
    FORMAL_SETTLEMENT_JSON_PATH as FORMAL_D_PATH,
)


AB_PATH = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
C_PATH = Path("docs/评分结算/第三项军事与边疆净收益/军事体系有效性/01-皇帝C项正式结算.json")
FORMAL_PATH = Path("docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json")
RESULT_CREDIT_ADJUDICATIONS_PATH = Path("config/third-item/third-item-result-credit-adjudications.json")
COST_CREDIT_FACTORS_PATH = Path("config/third-item/third-item-cost-credit-factors.json")
MILITARY_NET_LOSS_PENALTIES_PATH = Path("config/third-item/third-item-military-net-loss-penalties.json")
C_OUTCOME_ADJUDICATIONS_PATH = Path("config/third-item/third-item-c-outcome-adjudications.json")
AB_HANDOFF_ADJUDICATIONS_PATH = Path("config/third-item/third-item-ab-handoff-adjudications.json")
A_AXIS_NARRATIVE_ADJUDICATIONS_PATH = Path(
    "config/third-item/third-item-a-axis-narrative-adjudications.json"
)

A_AXIS_SCOPES = {
    "A1": "STRATEGIC_THREAT_CONTROL_STATE",
    "A2": "STRATEGIC_BOUNDARY_SECURITY_SYSTEM",
}


def _reign_range_label(value: object) -> str:
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and all(isinstance(item, int) for item in value):
            return f"{value[0]}-{value[1]}"
        return "；".join(str(item) for item in value)
    return str(value)


def _load(path: Path) -> dict[str, Any]:
    return load_json(path)


def _index(records: Sequence[Mapping[str, Any]], component: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in records:
        name = str(row["ruler_name"])
        if name in indexed:
            raise ValueError(f"{component}存在重复评价主体：{name}")
        indexed[name] = row
    return indexed


def _component_identity(
    name: str,
    rows: Sequence[Mapping[str, Any] | None],
) -> str:
    ids = {str(row["ruler_id"]) for row in rows if row is not None}
    if len(ids) != 1:
        raise ValueError(f"{name}跨组件人物ID不一致：{sorted(ids)}")
    return ids.pop()


def _rank(records: Sequence[dict[str, Any]]) -> None:
    ready = sorted(
        (row for row in records if row["third_item_score_points"] is not None),
        key=lambda row: (-float(row["third_item_score_points"]), str(row["ruler_id"])),
    )
    previous: float | None = None
    rank = 0
    for index, row in enumerate(ready, 1):
        score = float(row["third_item_score_points"])
        if score != previous:
            rank = index
            previous = score
        row["rank"] = rank
        row["rank_status"] = "GLOBAL_CURRENT_READY_POOL"
    for row in records:
        if row["third_item_score_points"] is None:
            row["rank"] = None
            row["rank_status"] = "PENDING_COMPONENT_SCORE"


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def _within_band_structure_credit(axis: Mapping[str, Any]) -> float:
    evidence = axis.get("within_band_structure_improvement")
    if evidence is None:
        return 0.0
    if not isinstance(evidence, Mapping):
        raise ValueError("A1档内结构改善必须为证据对象")
    credit = evidence.get("attribution_credit")
    if not isinstance(credit, (int, float)) or isinstance(credit, bool) or credit not in {0.25, 0.5, 0.75, 1.0}:
        raise ValueError("A1档内结构改善归责信用不合法")
    if not (int(axis["start_grade"]) == int(axis["end_grade"]) in {1, 2, 3, 4}):
        raise ValueError("A1档内结构改善只适用于1至4档同档交班")
    if axis.get("active_window_segments") or float(axis["objective_delta"]) != 0:
        raise ValueError("A1档内结构改善不得重复跨窗口或跨档信用")
    for key in ("entry_structure", "handover_structure", "attribution_basis", "net_improvement_basis", "deduplication_basis"):
        if not isinstance(evidence.get(key), str) or not evidence[key].strip():
            raise ValueError(f"A1档内结构改善缺少{key}")
    for key in ("parent_cycle_refs", "source_refs"):
        refs = evidence.get(key)
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs) or len(refs) != len(set(refs)):
            raise ValueError(f"A1档内结构改善{key}不合法")
    if evidence.get("threat_scope") != "SYSTEMIC" or evidence.get("outcome") not in {"STRUCTURAL_DOWNGRADE", "SYSTEM_TERMINATED"}:
        raise ValueError("A1档内改善未闭合系统级威胁结构变化")
    if evidence.get("restoration_only") is not False or evidence.get("consumed_elsewhere") is not False:
        raise ValueError("A1档内结构改善不得只恢复原状或重复计分")
    return 10.0 * float(credit)


def _decompose_a120_axis(axis: Mapping[str, Any]) -> tuple[float, float]:
    end_grade = int(axis["end_grade"])
    attributable_delta = float(axis["attributable_delta"])
    positive_raw = 10 * max(0.0, attributable_delta) + max(
        float(axis.get("ceiling_progress_bonus") or 0),
        float(axis.get("maintenance_bonus") or 0),
        _within_band_structure_credit(axis),
    )
    anchor_raw = (
        12 * end_grade
        + 10 * min(0.0, attributable_delta)
        - float(axis.get("negative_adjustment") or 0)
    )
    anchor = _clamp(0.0, 100.0, anchor_raw)
    with_positive = _clamp(0.0, 100.0, anchor_raw + positive_raw)
    return round(anchor * 0.6, 2), round((with_positive - anchor) * 0.6, 2)


def _validate_result_credit_contract(
    payload: Mapping[str, Any],
    formal_ab_payload: Mapping[str, Any] | None = None,
    *,
    require_synchronized: bool = False,
) -> None:
    if payload.get("schema_id") != "emperor-v4-third-item-result-credit-adjudications-v2":
        raise ValueError("A120结果信用合同schema不合法")
    contract = payload.get("contract") or {}
    if contract.get("improvement_attribution_scale") != {
        "NONE": 0,
        "LIMITED": 0.25,
        "JOINT": 0.5,
        "PRIMARY": 0.75,
        "LEADING": 1.0,
    }:
        raise ValueError("A120逐档改善归责映射不合法")
    if contract.get("improvement_attribution_formula") != (
        "positive attributable_delta = sum(improvement_step_credits.credit)"
    ):
        raise ValueError("A120逐档改善归责公式不合法")
    maintenance_bonus = contract.get("maintenance_bonus") or {}
    if maintenance_bonus != {"NONE": 0, "TESTED": 10, "SEVERE": 25, "HISTORIC": 40}:
        raise ValueError("A120守成加点映射不合法")

    records = list(payload.get("records") or ())
    if payload.get("record_count") != len(records) or len(records) != 201:
        raise ValueError("A120结果信用覆盖不闭合")
    if len({str(row.get("ruler_id")) for row in records}) != len(records):
        raise ValueError("A120结果信用存在重复人物ID")

    formal_by_id: dict[str, Mapping[str, Any]] = {}
    if formal_ab_payload is not None:
        formal_by_id = {
            str(row["ruler_id"]): row
            for row in formal_ab_payload.get("records") or ()
        }

    allowed_credits = {0.0, 0.25, 0.5, 0.75, 1.0}
    allowed_maintenance = {
        "NOT_APPLICABLE": 0,
        "NONE": 0,
        "TESTED": 10,
        "SEVERE": 25,
        "HISTORIC": 40,
    }
    for row in records:
        ruler_id = str(row["ruler_id"])
        formal = formal_by_id.get(ruler_id)
        if formal_ab_payload is not None and formal is None:
            raise ValueError(f"{row['ruler_name']}缺少AB正式人物记录")
        axis_points = 0.0
        historic_ref_sets: list[set[str]] = []
        for axis_name in ("A1", "A2"):
            axis = row["axes"][axis_name]
            structure_credit = _within_band_structure_credit(axis)
            if structure_credit:
                if axis_name != "A1":
                    raise ValueError("档内军事威胁结构改善只能进入A1")
                if formal is not None:
                    refs = set(axis["within_band_structure_improvement"]["parent_cycle_refs"])
                    allowed = set(formal.get("parent_cycle_refs") or ())
                    excluded = set(formal.get("excluded_founding_unification_refs") or ())
                    if not refs.issubset(allowed) or refs & excluded:
                        raise ValueError(f"{row['ruler_name']}档内结构改善父链越界或重复统一成果")
            start = int(axis["start_grade"])
            end = int(axis["end_grade"])
            objective_delta = int(axis["objective_delta"])
            attributable_delta = float(axis["attributable_delta"])
            active_segments = list(axis.get("active_window_segments") or ())
            expected_objective_delta = (
                sum(int(segment["delta"]) for segment in active_segments)
                if active_segments
                else end - start
            )
            if (
                not 0 <= start <= 5
                or not 0 <= end <= 5
                or objective_delta != expected_objective_delta
            ):
                raise ValueError(f"{row['ruler_name']} {axis_name}客观起终档不闭合")

            steps = list(axis.get("improvement_step_credits") or ())
            expected_step_count = max(0, objective_delta)
            if len(steps) != expected_step_count:
                raise ValueError(f"{row['ruler_name']} {axis_name}逐档改善归责数量不一致")
            for index, step in enumerate(steps):
                if (
                    int(step.get("from_grade", -1)) != start + index
                    or int(step.get("to_grade", -1)) != start + index + 1
                    or float(step.get("credit", -1)) not in allowed_credits
                    or not str(step.get("basis") or "").strip()
                ):
                    raise ValueError(f"{row['ruler_name']} {axis_name}逐档改善归责不合法")
            if objective_delta > 0 and abs(sum(float(step["credit"]) for step in steps) - attributable_delta) > 0.001:
                raise ValueError(f"{row['ruler_name']} {axis_name}逐档改善归责汇总不一致")
            if objective_delta <= 0 and attributable_delta > 0:
                raise ValueError(f"{row['ruler_name']} {axis_name}无改善却记正向归责")

            difficulty = str(axis["maintenance_difficulty"])
            bonus = float(axis["maintenance_bonus"])
            if difficulty not in allowed_maintenance or bonus != allowed_maintenance[difficulty]:
                raise ValueError(f"{row['ruler_name']} {axis_name}守成档与加点不一致")
            if difficulty in {"TESTED", "SEVERE", "HISTORIC"} and not (
                start == end and start in {4, 5}
            ):
                raise ValueError(f"{row['ruler_name']} {axis_name}不满足高位守成入口")
            if difficulty == "HISTORIC":
                if any(
                    int(row["axes"][other_axis]["objective_delta"]) < 0
                    for other_axis in ("A1", "A2")
                ):
                    raise ValueError(f"{row['ruler_name']}存在A轴终点下降，不得记历史级守成")
                gate = axis.get("historic_maintenance_gate") or {}
                pressure_refs = list(gate.get("pressure_refs") or ())
                continuity_refs = list(gate.get("continued_effectiveness_refs") or ())
                if gate.get("pressure_level") not in {"O5_O6_REALIZED", "REPEATED_O4_EQUIVALENT"}:
                    raise ValueError(f"{row['ruler_name']} {axis_name}历史级守成压力不合法")
                if float(gate.get("maintenance_attribution_credit") or 0) not in {0.75, 1.0}:
                    raise ValueError(f"{row['ruler_name']} {axis_name}历史级守成本人归责不足")
                if gate.get("pressure_origin") != "EXTERNAL_NOT_SELF_INDUCED":
                    raise ValueError(f"{row['ruler_name']} {axis_name}历史级守成危机来源不合法")
                if gate.get("terminal_grade_held") is not True or not pressure_refs or not continuity_refs:
                    raise ValueError(f"{row['ruler_name']} {axis_name}历史级守成持续有效性未闭合")
                if gate.get("cross_axis_consumption_check") != "PASS":
                    raise ValueError(f"{row['ruler_name']} {axis_name}历史级守成跨轴去重未闭合")
                if float(axis.get("negative_adjustment") or 0) != 0:
                    raise ValueError(f"{row['ruler_name']} {axis_name}历史级守成存在未消化负向调整")
                if formal is not None:
                    allowed_refs = {
                        str(ref) for ref in formal.get("parent_cycle_refs") or ()
                    } | {
                        str(ref) for ref in formal.get("evidence_event_refs") or ()
                    }
                    if not set(map(str, pressure_refs + continuity_refs)).issubset(allowed_refs):
                        raise ValueError(f"{row['ruler_name']} {axis_name}历史级守成引用越界")
                historic_ref_sets.append(set(map(str, pressure_refs + continuity_refs)))
            elif axis.get("historic_maintenance_gate") is not None:
                raise ValueError(f"{row['ruler_name']} {axis_name}非历史级守成不得保留历史门")

            expected_trajectory = _clamp(
                0.0,
                100.0,
                12 * end
                + 10 * attributable_delta
                + max(float(axis.get("ceiling_progress_bonus") or 0), bonus, structure_credit)
                - float(axis.get("negative_adjustment") or 0),
            )
            if abs(float(axis["trajectory_value"]) - expected_trajectory) > 0.001:
                raise ValueError(f"{row['ruler_name']} {axis_name}轨迹值不一致")
            expected_axis_points = round(expected_trajectory * 0.6, 2)
            if abs(float(axis["axis_points"]) - expected_axis_points) > 0.001:
                raise ValueError(f"{row['ruler_name']} {axis_name}轴分不一致")
            axis_points += expected_axis_points

        if len(historic_ref_sets) > 1 and historic_ref_sets[0] & historic_ref_sets[1]:
            raise ValueError(f"{row['ruler_name']}同一防守链不得在A1、A2重复记历史级守成")

        if abs(float(row["A120_points"]) - round(axis_points, 2)) > 0.001:
            raise ValueError(f"{row['ruler_name']} A120汇总不一致")
        if require_synchronized and formal is not None and (
            float(formal.get("A120_score_points")) != float(row["A120_points"])
            or formal.get("A120_axis_adjudications") != row["axes"]
            or formal.get("B80_adjudication") != row["B80_adjudication"]
        ):
            raise ValueError(f"{row['ruler_name']} A120/B80正式视图未同步")


def _validate_ab_axis_narratives(payload: Mapping[str, Any]) -> None:
    records = list(payload.get("records") or ())
    if len(records) != 201:
        raise ValueError("A轴逐人依据覆盖不闭合")
    for row in records:
        axes = row.get("axes") or {}
        bases: dict[str, str] = {}
        for axis_name, expected_scope in A_AXIS_SCOPES.items():
            axis = axes.get(axis_name) or {}
            if axis.get("assessment_scope") != expected_scope:
                raise ValueError(
                    f"{row['ruler_name']} {axis_name}叙事作用域不合法"
                )
            basis = str(axis.get("reason") or axis.get("rationale") or "").strip()
            if not basis:
                raise ValueError(f"{row['ruler_name']} {axis_name}缺少轴专属依据")
            bases[axis_name] = basis
        if bases["A1"] == bases["A2"]:
            raise ValueError(f"{row['ruler_name']} A1、A2不得使用完全相同的轴专属依据")


def _load_a_axis_narrative_adjudications(
    workspace_root: Path,
) -> dict[str, Mapping[str, Any]]:
    payload = _load(workspace_root / A_AXIS_NARRATIVE_ADJUDICATIONS_PATH)
    if payload.get("schema_id") != (
        "emperor-v4-third-item-a-axis-narrative-adjudications-v1"
    ):
        raise ValueError("A轴叙事裁决schema不合法")
    records = list(payload.get("adjudications") or ())
    indexed = {str(row.get("ruler_id")): row for row in records}
    if len(indexed) != len(records) or any(not ruler_id for ruler_id in indexed):
        raise ValueError("A轴叙事裁决人物ID缺失或重复")
    for row in records:
        if any(
            not str(row.get(field) or "").strip()
            for field in ("ruler_name", "shared_context", "A1_basis", "A2_basis")
        ):
            raise ValueError(f"A轴叙事裁决字段不完整：{row.get('ruler_name')}")
        if str(row["A1_basis"]).strip() == str(row["A2_basis"]).strip():
            raise ValueError(f"A轴叙事裁决未拆轴：{row['ruler_name']}")
    return indexed


def _validate_cost_factor_contract(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_id") != "emperor-v4-third-item-cost-debits-v2":
        raise ValueError("军事成本固定扣分合同schema不合法")
    if float(payload.get("cost_debit_base_points") or 0) != 80.0:
        raise ValueError("军事成本固定扣分基数必须为80")
    if payload.get("ml_combination_rule") != "TAKE_HIGHER_ABSOLUTE_DEBIT_NOT_ADDITIVE":
        raise ValueError("军事成本与ML必须取高且不叠加")
    factors = payload["factor_by_global_cost_band_and_position"]
    ordered = [
        ("C1", "LOW"), ("C1", "MID"), ("C1", "HIGH"),
        ("C2", "LOW"), ("C2", "MID"), ("C2", "HIGH"),
        ("C3", "LOW"), ("C3", "MID"), ("C3", "HIGH"),
        ("C4", "LOW"), ("C4", "MID"), ("C4", "HIGH"),
        ("C5", "LOW"), ("C5", "MID"), ("C5", "HIGH"),
        ("C6", "LOW"), ("C6", "MID"), ("C6", "HIGH"),
        ("C7", "LOW"), ("C7", "MID"), ("C7", "HIGH"), ("C7", "HIGHEST"),
    ]
    values = [float(factors[band][position]) for band, position in ordered]
    if any(left <= right for left, right in zip(values, values[1:])):
        raise ValueError("成本系数必须按成本严重度严格递减")
    if float(factors["C0"]["LOW"]) != 1.0:
        raise ValueError("C0-LOW必须保持1.0")


def _render_current_weighted_markdown(records: Sequence[Mapping[str, Any]]) -> str:
    human_status = {
        "NOT_APPLICABLE": "不适用",
        "NONE": "无",
        "HIGH": "高位",
        "MID": "中位",
        "LOW": "低位",
    }

    def human_label(value: object) -> str:
        return human_status.get(str(value), str(value))

    def human_basis(value: object) -> str:
        return (
            str(value)
            .replace(
                "NOT_APPLICABLE does not mean low cost. The whole founding/unification campaign, including reversals and costs, is excluded under the corrected hard gate.",
                "不适用不等于低成本；创业统一整链及其反转与成本已按跨项去重规则排除。",
            )
            .replace("LOWER_BOUND", "证据下限")
            .replace("PROVISIONAL", "暂定")
            .replace("CONFIRMED", "已确认")
            .replace(
                "C5 rests only on the merged Song chain M5 burden. No F3 is inferred and no separate chain is combined; therefore not C6.",
                "C5仅由合并后的攻宋链M5负担准入；不推定F3，也不拼接其他独立链，因此不进C6。",
            )
        )

    eligible = sorted(
        (row for row in records if row.get("third_item_score_points") is not None),
        key=lambda row: (int(row["rank"]), str(row["ruler_id"])),
    )
    lines = [
        "# 秦至清第三项军事与边疆正式结算",
        "",
        "本表按A120战略安全结果、B80边疆控制结果、C50军事体系能力合并。普通成本按既有档位固定扣分；军事净毁损（ML）与普通成本取高，不叠加。",
        "",
        "公式：第三项 = A120 + B80 + C50 - max（固定成本扣分，|ML|）。",
        "",
        "| 排名 | 皇帝 | 政权 | 在位 | A120 | B80 | C50 | 全局成本 | 固定成本 | ML | 实际扣分 | 总分 |",
        "|---:|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in eligible:
        profile = row["global_cost_credit_profile"]
        lines.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
            f"{float(row['A120_score_points']):.2f} | {float(row['B80_score_points']):.2f} | "
            f"{float(row['C50_score_points']):.2f} | {human_label(profile['cost_band'])}-{human_label(profile['position'])} | "
            f"{float(row['cost_debit_points']):.2f} | "
            f"{abs(float(row['military_net_loss_penalty'])):.2f} | {float(row['applied_military_debit_points']):.2f} | "
            f"{float(row['third_item_score_points']):.2f} |"
        )
    lines += ["", "## 逐人结算依据", ""]
    for row in eligible:
        profile = row["global_cost_credit_profile"]
        debit_source = {
            "NONE": "无扣分",
            "COST": "普通成本",
            "ML": "军事净毁损",
            "COST_AND_ML_EQUAL": "普通成本与军事净毁损同额",
        }[str(row["applied_military_debit_source"])]
        lines += [
            f"### {row['rank']}. {row['ruler_name']}（{float(row['third_item_score_points']):.2f}）",
            "",
            f"- 成本：{human_label(profile['cost_band'])}-{human_label(profile['position'])}，固定扣{float(row['cost_debit_points']):.2f}分。{human_basis(profile['basis'])}",
        ]
        lines += [
            f"- ML：{row['military_net_loss_grade']}（{abs(float(row['military_net_loss_penalty'])):.2f}分）。与普通成本取高，实际扣{float(row['applied_military_debit_points']):.2f}分（{debit_source}）。{human_basis(row['military_net_loss_basis'])}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def _validate_cross_item_parent_routing(
    credit_payload: Mapping[str, Any],
    ab_payload: Mapping[str, Any],
    c_payload: Mapping[str, Any],
    d_payload: Mapping[str, Any],
) -> None:
    """Enforce the same adjudicated parent routing across all four axes."""
    components = [
        {str(row["ruler_id"]): row for row in payload["records"]}
        for payload in (ab_payload, c_payload, d_payload)
    ]
    for credit in credit_payload["records"]:
        route = credit.get("cross_item_parent_routing")
        if not route:
            continue
        ruler_id = str(credit["ruler_id"])
        ab, c, d = (component[ruler_id] for component in components)
        name = credit["ruler_name"]
        if not str(route.get("reason") or "").strip():
            raise ValueError(f"{name}跨项父链路由缺少裁决依据")
        excluded = set(route.get("D_excluded_chain_ids") or ())
        recorded = {chain["chain_id"] for chain in d.get("cross_item_excluded_chains") or ()}
        active = {
            ref
            for chain in list(d.get("external_strategic_chains") or ())
            + list(d.get("strategic_internal_chains") or ())
            for ref in [chain["chain_id"], *(chain.get("member_cycle_refs") or ())]
        }
        if not excluded.issubset(recorded) or excluded & active:
            raise ValueError(f"{name}第一项消费父链回流D或排除登记缺失")
        capability = set(route.get("C_capability_only_parent_refs") or ())
        if not capability.issubset(set(c.get("capability_only_parent_refs") or ())):
            raise ValueError(f"{name}C能力专用桥接未同步")
        if capability & set(c.get("current_item_task_refs") or ()):
            raise ValueError(f"{name}C能力专用父链同时进入当前结果任务")
        if route.get("C_phase_routing") is not None:
            if route["C_phase_routing"] != c.get("current_item_phase_routing"):
                raise ValueError(f"{name}C父链阶段切分未同步")
        if route.get("A_consumption") == "OBJECTIVE_STATE_ONLY_NO_ATTRIBUTABLE_CHANGE":
            for axis in credit["axes"].values():
                if any(float(axis.get(key) or 0) != 0 for key in (
                    "attributable_delta", "negative_adjustment", "maintenance_bonus",
                    "ceiling_progress_bonus",
                )):
                    raise ValueError(f"{name}第一项整链消费后仍保留A归责加减")
        if route.get("B_consumption") == "EXCLUDED_FIRST_ITEM_ACQUISITION":
            if any(float(ab["axes"][axis]["score_rate"]) != 0 for axis in ("B1", "B2", "B4")):
                raise ValueError(f"{name}第一项取得链仍保留B控制得分")
        excluded_control = set(route.get("B_excluded_control_package_refs") or ())
        if excluded_control & set(ab.get("primary_control_package_refs") or ()):
            raise ValueError(f"{name}第一项控制成果包回流第三项B")


def build_current_third_item_settlement(workspace_root: Path) -> dict[str, Any]:
    paths = {
        "AB": workspace_root / AB_PATH,
        "C": workspace_root / C_PATH,
        "D": workspace_root / FORMAL_D_PATH,
        "result_credit": workspace_root / RESULT_CREDIT_ADJUDICATIONS_PATH,
        "cost_credit": workspace_root / COST_CREDIT_FACTORS_PATH,
        "military_net_loss": workspace_root / MILITARY_NET_LOSS_PENALTIES_PATH,
    }
    payloads = {key: _load(path) for key, path in paths.items()}
    _validate_cross_item_parent_routing(
        payloads["result_credit"], payloads["AB"], payloads["C"], payloads["D"]
    )
    _validate_cost_factor_contract(payloads["cost_credit"])
    _validate_result_credit_contract(
        payloads["result_credit"], payloads["AB"], require_synchronized=True
    )
    indexed = {
        key: _index(payloads[key]["records"], key)
        for key in ("AB", "C", "D", "result_credit")
    }
    cost_overrides = _index(
        payloads["cost_credit"]["global_cost_overrides"], "global_cost_overrides"
    )
    military_net_loss_policy = payloads["military_net_loss"]["policy"]
    expected_penalties = {"ML0": 0, "ML1": -10, "ML2": -20, "ML3": -30, "ML4": -40}
    if military_net_loss_policy != expected_penalties:
        raise ValueError("军事净毁损档位映射与合同不一致")
    military_net_loss_by_name = _index(
        payloads["military_net_loss"]["records"], "military_net_loss"
    )
    attribution_policy = payloads["military_net_loss"]["attribution_policy"]
    if attribution_policy.get("default") != "FULL":
        raise ValueError("军事净毁损默认归责必须为FULL")
    material_attribution_ids = {str(value) for value in attribution_policy.get("material_ruler_ids") or ()}
    configured_net_loss_ids = {str(item["ruler_id"]) for item in military_net_loss_by_name.values()}
    if not material_attribution_ids.issubset(configured_net_loss_ids):
        raise ValueError("军事净毁损MATERIAL归责名单包含未裁决人物")
    for name, item in military_net_loss_by_name.items():
        if item["grade"] not in expected_penalties:
            raise ValueError(f"{name}军事净毁损档位非法")
        d_row = indexed["D"].get(name)
        if d_row is None or str(d_row["ruler_id"]) != str(item["ruler_id"]):
            raise ValueError(f"{name}军事净毁损裁决与D人物不一致")
        cost_override = cost_overrides.get(name)
        cost_band_label = (
            cost_override["global_cost_band"]
            if cost_override is not None
            else d_row["attributable_cost_profile"]["cost_band"]
        )
        cost_band = int(str(cost_band_label)[1:])
        if cost_band < 5:
            raise ValueError(f"{name}军事净毁损未通过C5成本门")
        chains = list(d_row.get("external_strategic_chains") or ()) + list(d_row.get("strategic_internal_chains") or ())
        if not any(
            str(chain.get("security_result_grade") or chain.get("achievement_grade") or "").startswith(("EN2", "EN3"))
            for chain in chains
        ):
            raise ValueError(f"{name}军事净毁损未通过EN2/EN3门")
    c_consumed_by_name = {
        name: {
            str(chain["chain_id"])
            for chain in row.get("cross_item_excluded_chains", [])
            if "THIRD_ITEM_C" in str(chain.get("result_type") or "")
        }
        for name, row in indexed["D"].items()
    }
    c_consumed_by_name = {
        name: chain_ids for name, chain_ids in c_consumed_by_name.items() if chain_ids
    }
    if set(c_consumed_by_name) != set(cost_overrides):
        raise ValueError(
            "第三项C消费者退出人物与全局成本恢复人物不一致："
            f"excluded={sorted(c_consumed_by_name)} overrides={sorted(cost_overrides)}"
        )
    for name, chain_ids in c_consumed_by_name.items():
        restored = set(cost_overrides[name]["restored_third_item_c_chain_ids"])
        if chain_ids != restored:
            raise ValueError(f"{name}第三项C消费者退出链未完整恢复：{chain_ids} != {restored}")
    ordered_names = list(indexed["AB"])
    ordered_names.extend(name for name in indexed["C"] if name not in indexed["AB"])
    ordered_names.extend(
        name
        for name in indexed["D"]
        if name not in indexed["AB"] and name not in indexed["C"]
    )
    ordered_names.extend(
        name
        for name in indexed["result_credit"]
        if name not in indexed["AB"] and name not in indexed["C"] and name not in indexed["D"]
    )

    records: list[dict[str, Any]] = []
    for name in ordered_names:
        ab_row = indexed["AB"].get(name)
        c_row = indexed["C"].get(name)
        d_row = indexed["D"].get(name)
        credit_row = indexed["result_credit"].get(name)
        ruler_id = _component_identity(name, (ab_row, c_row, d_row, credit_row))
        base: dict[str, Any] = {}

        c50_points = (
            float(c_row["C_score_points"])
            if c_row is not None and c_row.get("C_score_points") is not None
            else None
        )
        a120_points: float | None = None
        a120_anchor: float | None = None
        a120_positive: float | None = None
        b80_points: float | None = None
        local_cost_profile: dict[str, Any] | None = None
        global_cost_profile: dict[str, Any] | None = None
        cost_factor: float | None = None
        cost_debit: float | None = None
        if credit_row is not None:
            axis_parts = [_decompose_a120_axis(credit_row["axes"][axis]) for axis in ("A1", "A2")]
            a120_anchor = round(sum(part[0] for part in axis_parts), 2)
            a120_positive = round(sum(part[1] for part in axis_parts), 2)
            a120_points = round(float(credit_row["A120_points"]), 2)
            if round(a120_anchor + a120_positive, 2) != a120_points:
                raise ValueError(f"{name} A120正向信用拆分不闭合")
            b80_points = round(float(credit_row["B80_adjudication"]["B80_points"]), 2)
        if d_row is not None:
            profile = d_row["attributable_cost_profile"]
            local_cost_profile = {
                "cost_band": profile["cost_band"],
                "position": profile["position"],
                "status": profile["status"],
                "basis": profile.get("basis") or profile.get("admission_fact") or "正式D局部成本画像未另列依据。",
            }
            override = cost_overrides.get(name)
            if override is None:
                global_cost_profile = dict(local_cost_profile)
                global_cost_profile["source"] = "D_LOCAL_COST_VIEW"
                global_cost_profile["restored_third_item_c_chain_ids"] = []
            else:
                if str(override["ruler_id"]) != ruler_id:
                    raise ValueError(f"{name}全局成本覆盖人物ID不一致")
                global_cost_profile = {
                    "cost_band": override["global_cost_band"],
                    "position": override["global_cost_position"],
                    "status": "CONFIRMED_GLOBAL_COST_VIEW",
                    "basis": override["basis"],
                    "source": "D_LOCAL_PLUS_RESTORED_THIRD_ITEM_C_CHAINS",
                    "restored_third_item_c_chain_ids": list(override["restored_third_item_c_chain_ids"]),
                }
            factor_table = payloads["cost_credit"]["factor_by_global_cost_band_and_position"]
            cost_factor = float(
                factor_table[global_cost_profile["cost_band"]][global_cost_profile["position"]]
            )
            cost_debit = round(
                float(payloads["cost_credit"]["cost_debit_base_points"]) * (1.0 - cost_factor),
                2,
            )
        net_loss = military_net_loss_by_name.get(name)
        net_loss_grade = str(net_loss["grade"]) if net_loss else "ML0"
        net_loss_penalty = float(expected_penalties[net_loss_grade])
        net_loss_basis = str(net_loss["basis"]) if net_loss else "未同时通过EN2/EN3、C5以上本方成本和本人责任门，不生成负向尾部。"
        net_loss_attribution = (
            "NONE"
            if net_loss is None
            else "MATERIAL"
            if ruler_id in material_attribution_ids
            else "FULL"
        )
        total = None
        applied_debit: float | None = None
        applied_debit_source: str | None = None
        if None not in (a120_points, b80_points, c50_points, cost_debit):
            ml_debit = abs(net_loss_penalty)
            applied_debit = max(float(cost_debit), ml_debit)
            applied_debit_source = (
                "NONE" if applied_debit == 0
                else "COST" if float(cost_debit) > ml_debit
                else "ML" if ml_debit > float(cost_debit)
                else "COST_AND_ML_EQUAL"
            )
            total = round(float(a120_points) + float(b80_points) + float(c50_points) - applied_debit, 2)
        missing = []
        if ab_row is None:
            missing.append("AB_SOURCE")
        if credit_row is None or a120_points is None or b80_points is None:
            missing.append("A120/B80_ADJUDICATION")
        if c50_points is None:
            missing.append("C")
        if d_row is None or global_cost_profile is None or cost_factor is None:
            missing.append("GLOBAL_COST_VIEW")

        polity_source = ab_row or c_row or d_row or {}
        reign_source = ab_row or c_row or d_row or {}
        base.update({
            "ruler_id": ruler_id,
            "ruler_name": name,
            "polity": polity_source.get("polity") or "—",
            "reign_range": reign_source.get("reign_range"),
            "A120_score_points": a120_points,
            "B80_score_points": b80_points,
            "C50_score_points": c50_points,
            "D_local_cost_profile": local_cost_profile,
            "global_cost_credit_profile": global_cost_profile,
            "cost_credit_factor": cost_factor,
            "cost_debit_points": cost_debit,
            "score_formula": "A120 + B80 + C50 - max(cost_debit, abs(military_net_loss_penalty))",
            "military_net_loss_grade": net_loss_grade,
            "military_net_loss_attribution": net_loss_attribution,
            "military_net_loss_penalty": net_loss_penalty,
            "military_net_loss_basis": net_loss_basis,
            "applied_military_debit_points": applied_debit,
            "applied_military_debit_source": applied_debit_source,
            "third_item_score_points": total,
            "third_item_score_rate": None if total is None else round(total / 250 * 100, 2),
            "coverage_status": {
                "AB": ab_row.get("coverage_status") if ab_row else "NO_AB_RECORD",
                "C": c_row.get("coverage_status") if c_row else "NO_C_RECORD",
                "D": d_row.get("coverage_status") if d_row else "NO_D_RECORD",
                "result_credit": "FORMAL_CURRENT" if credit_row else "NO_RESULT_CREDIT_ADJUDICATION",
            },
            "component_join_status": "READY" if not missing else "PENDING_" + "_".join(missing),
            "formal_score_write": total is not None,
            "pending_reason": None if not missing else f"缺少{'、'.join(missing)}闭合结果，第三项不赋中性总分。",
        })
        records.append(base)

    _rank(records)
    records.sort(
        key=lambda row: (
            row["third_item_score_points"] is None,
            -float(row["third_item_score_points"] or 0),
            str(row["ruler_id"]),
        )
    )
    scores = [float(row["third_item_score_points"]) for row in records if row["third_item_score_points"] is not None]
    result = {
        "schema_id": "emperor-v4-third-item-formal-settlement-v7-fixed-cost-debit",
        "canonical_status": "FORMAL_CURRENT",
        "item_name": "第三项 军事与边疆净收益",
        "item_max_points": 250,
        "record_count": len(records),
        "score_ready_count": len(scores),
        "C_unassessed_count": sum(row["C50_score_points"] is None for row in records),
        "formal_score_write": len(scores) == len(records),
        "database_write": False,
        "rank_tie_policy": "COMPETITION_RANK",
        "source_contracts": [
            "docs/分项规则/第三项军事与边疆净收益/国防安全/00-规则与结算合同.md",
            "docs/分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md",
            "docs/分项规则/第三项军事与边疆净收益/军事成本收益比/00-规则与结算合同.md",
        ],
        "source_results": [
            "国防安全/01-皇帝AB项正式结算.json",
            "军事体系有效性/01-皇帝C项正式结算.json",
            "军事成本收益比/01-皇帝D项正式结算.json",
        ],
        "scope": "当前AB/C/D组件与A120/B80裁决并集；A120、B80、C50相加后，扣除普通成本与军事净毁损绝对值中的较高者",
        "score_contract": {
            "maximum_points": 250,
            "minimum_points": -40,
            "A120_maximum": 120,
            "B80_maximum": 80,
            "C50_maximum": 50,
            "D_cost_role": "GLOBAL_FIXED_COST_DEBIT_SOURCE",
            "cost_debit_base_points": 80,
            "cost_debit_range": [0, 40],
            "military_net_loss_penalty_range": [-40, 0],
            "cost_and_ml_combination": "MAX_NOT_ADDITIVE",
            "formula": "A120 + B80 + C50 - max(cost_debit, abs(military_net_loss_penalty))",
            "rounding": "ROUND_FINAL_SCORE_TO_2_DECIMALS",
        },
        "score_recalculation_policy": "A120_PLUS_B80_PLUS_C50_MINUS_MAX_FIXED_COST_OR_ML",
        "score_range": {"minimum": min(scores), "maximum": max(scores)},
        "component_coverage_counts": {
            "AB": len(indexed["AB"]),
            "C": len(indexed["C"]),
            "D": len(indexed["D"]),
            "result_credit": len(indexed["result_credit"]),
            "union": len(records),
            "ready": len(scores),
            "pending": len(records) - len(scores),
        },
        "records": records,
    }
    return result


def _write_text_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.current-third-item-write-tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def verify_current_third_item_settlement(workspace_root: Path) -> dict[str, Any]:
    """Validate the formal combined snapshot without rebuilding its components."""
    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown

    payload = _load(workspace_root / FORMAL_PATH)
    credit_payload = _load(workspace_root / RESULT_CREDIT_ADJUDICATIONS_PATH)
    ab_payload = _load(workspace_root / AB_PATH)
    _validate_cross_item_parent_routing(
        credit_payload, ab_payload, _load(workspace_root / C_PATH),
        _load(workspace_root / FORMAL_D_PATH),
    )
    _validate_result_credit_contract(
        credit_payload,
        ab_payload,
        require_synchronized=True,
    )
    _validate_ab_axis_narratives(ab_payload)
    expected_ab_markdown = _render_formal_markdown("AB", ab_payload["records"])
    actual_ab_markdown = (workspace_root / AB_PATH).with_suffix(".md").read_text(encoding="utf-8")
    if actual_ab_markdown != expected_ab_markdown:
        raise ValueError("第三项AB Markdown与正式JSON渲染结果不一致")
    records = list(payload.get("records") or ())
    if payload.get("schema_id") != "emperor-v4-third-item-formal-settlement-v7-fixed-cost-debit":
        raise ValueError("第三项正式结算schema不合法")
    if payload.get("record_count") != len(records) or len(records) != 201:
        raise ValueError("第三项正式结算覆盖不闭合")
    if len({row.get("ruler_id") for row in records}) != len(records):
        raise ValueError("第三项正式结算存在重复人物ID")

    ready = []
    for row in records:
        score = row.get("third_item_score_points")
        if score is None:
            if row.get("formal_score_write") or not row.get("pending_reason"):
                raise ValueError(f"第三项待结算状态不完整：{row.get('ruler_name')}")
            continue
        components = (
            row.get("A120_score_points"),
            row.get("B80_score_points"),
            row.get("C50_score_points"),
            row.get("cost_credit_factor"),
            row.get("cost_debit_points"),
            row.get("military_net_loss_penalty"),
            row.get("applied_military_debit_points"),
            row.get("applied_military_debit_source"),
        )
        if any(value is None for value in components):
            raise ValueError(f"第三项机械计分字段不完整：{row.get('ruler_name')}")
        a120, b80, c50, factor, cost_debit, penalty, applied_debit = map(float, components[:-1])
        expected_cost_debit = round(80 * (1 - factor), 2)
        if cost_debit != expected_cost_debit:
            raise ValueError(f"第三项固定成本扣分与factor不一致：{row.get('ruler_name')}")
        expected_applied = max(cost_debit, abs(penalty))
        if applied_debit != expected_applied:
            raise ValueError(f"第三项成本与ML取高不一致：{row.get('ruler_name')}")
        expected_source = (
            "NONE" if expected_applied == 0
            else "COST" if cost_debit > abs(penalty)
            else "ML" if abs(penalty) > cost_debit
            else "COST_AND_ML_EQUAL"
        )
        if row.get("applied_military_debit_source") != expected_source:
            raise ValueError(f"第三项实际扣分来源不一致：{row.get('ruler_name')}")
        expected = round(a120 + b80 + c50 - applied_debit, 2)
        if float(score) != expected:
            raise ValueError(f"第三项正式分数与给定裁决不一致：{row.get('ruler_name')}")
        if not row.get("formal_score_write") or row.get("component_join_status") != "READY":
            raise ValueError(f"第三项正式写入状态不闭合：{row.get('ruler_name')}")
        ready.append(row)

    expected_order = sorted(ready, key=lambda row: (-float(row["third_item_score_points"]), str(row["ruler_id"])))
    prior_score: float | None = None
    expected_rank = 0
    for index, row in enumerate(expected_order, 1):
        score = float(row["third_item_score_points"])
        if score != prior_score:
            expected_rank = index
            prior_score = score
        if row.get("rank") != expected_rank:
            raise ValueError(f"第三项正式排名不一致：{row.get('ruler_name')}")
    if records != sorted(
        records,
        key=lambda row: (
            row.get("third_item_score_points") is None,
            -float(row.get("third_item_score_points") or 0),
            str(row["ruler_id"]),
        ),
    ):
        raise ValueError("第三项正式记录顺序不稳定")

    scores = [float(row["third_item_score_points"]) for row in ready]
    coverage = payload.get("component_coverage_counts") or {}
    if coverage.get("union") != len(records) or coverage.get("ready") != len(ready):
        raise ValueError("第三项组件覆盖摘要与正式记录不一致")
    if payload.get("score_ready_count") != len(ready):
        raise ValueError("第三项就绪计数不一致")
    if payload.get("score_range") != {"minimum": min(scores), "maximum": max(scores)}:
        raise ValueError("第三项分数范围不一致")
    expected_markdown = _render_current_weighted_markdown(records)
    actual_markdown = (workspace_root / FORMAL_PATH).with_suffix(".md").read_text(
        encoding="utf-8"
    )
    if actual_markdown != expected_markdown:
        raise ValueError("第三项Markdown与正式JSON渲染结果不一致")
    return {
        "status": "PASS", "record_count": len(records),
        "score_ready_count": len(ready), "pending_count": len(records) - len(ready),
        "score_range": payload["score_range"],
    }


def _synchronize_current_ab_view(workspace_root: Path) -> None:
    """Put the current A120/B80 values beside the atomic AB adjudications."""
    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown

    ab_path = workspace_root / AB_PATH
    credit_path = workspace_root / RESULT_CREDIT_ADJUDICATIONS_PATH
    ab_payload = _load(ab_path)
    credit_payload = _load(credit_path)
    handoff_payload = _load(workspace_root / AB_HANDOFF_ADJUDICATIONS_PATH)
    narrative_adjudications = _load_a_axis_narrative_adjudications(workspace_root)
    _validate_result_credit_contract(credit_payload)
    credits = _index(credit_payload["records"], "result_credit")
    threat_supplements = {
        str(item["ruler_id"]): item
        for item in handoff_payload.get("primary_threat_supplements") or ()
    }
    for row in ab_payload["records"]:
        name = str(row["ruler_name"])
        credit = credits.get(name)
        if credit is None or str(credit["ruler_id"]) != str(row["ruler_id"]):
            raise ValueError(f"{name}缺少同主体A120/B80当前裁决")
        parts = [_decompose_a120_axis(credit["axes"][axis]) for axis in ("A1", "A2")]
        anchor = round(sum(part[0] for part in parts), 2)
        positive = round(sum(part[1] for part in parts), 2)
        a120 = round(float(credit["A120_points"]), 2)
        b80 = round(float(credit["B80_adjudication"]["B80_points"]), 2)
        if round(anchor + positive, 2) != a120:
            raise ValueError(f"{name} A120当前拆分不闭合")
        row.update(
            {
                "A120_non_cost_anchor_points": anchor,
                "A120_positive_result_credit_points": positive,
                "A120_score_points": a120,
                "B80_score_points": b80,
                "AB200_score_points": round(a120 + b80, 2),
                "A120_axis_adjudications": credit["axes"],
                "B80_adjudication": credit["B80_adjudication"],
            }
        )
        for axis_name, scope in A_AXIS_SCOPES.items():
            axis = row["axes"][axis_name]
            axis["assessment_scope"] = scope
            if not str(axis.get("reason") or "").strip():
                axis["reason"] = str(axis.get("rationale") or "").strip()
        narrative = narrative_adjudications.get(str(row["ruler_id"]))
        if narrative:
            if str(narrative["ruler_name"]) != name:
                raise ValueError(f"{name}的A轴叙事裁决人物名不一致")
            row["A_axis_common_context"] = str(narrative["shared_context"])
            row["axes"]["A1"]["reason"] = str(narrative["A1_basis"])
            row["axes"]["A2"]["reason"] = str(narrative["A2_basis"])
        threat_supplement = threat_supplements.get(str(row["ruler_id"]))
        if threat_supplement:
            refs = list(dict.fromkeys(
                str(ref)
                for ref in threat_supplement.get("primary_threat_refs") or ()
            ))
            allowed_refs = {
                str(ref) for ref in row.get("parent_cycle_refs") or ()
            } | {
                str(ref) for ref in row.get("evidence_event_refs") or ()
            }
            if not refs or not set(refs).issubset(allowed_refs):
                raise ValueError(f"{name}的AB主压力补充引用越界")
            if not str(threat_supplement.get("reason") or "").strip():
                raise ValueError(f"{name}的AB主压力补充缺少理由")
            row["primary_threat_refs"] = refs
            row["primary_threat_basis"] = str(threat_supplement["reason"])
    unknown_narrative_ids = set(narrative_adjudications) - {
        str(row["ruler_id"]) for row in ab_payload["records"]
    }
    if unknown_narrative_ids:
        raise ValueError(f"A轴叙事裁决存在池外人物：{sorted(unknown_narrative_ids)}")
    _validate_ab_axis_narratives(ab_payload)
    _validate_result_credit_contract(credit_payload, ab_payload)
    ab_payload.update(
        {
            "schema_id": "emperor-v4-third-item-ab-formal-settlement-v3-attribution-maintenance",
            "score_contract": {
                "maximum_points": 200,
                "A120_maximum": 120,
                "B80_maximum": 80,
                "AB200_formula": "A120 + B80",
                "A120_formula": "sum(0.6*clamp(0,100,12*end+10*attributable_delta+max(ceiling_bonus,maintenance_bonus,within_band_structure_credit)-max(reversal_penalty,within_band_deterioration_penalty)))",
                "B80_formula": "80*(0.55*B1_rate+0.45*B2_rate)*(0.70+0.30*B4_rate)",
                "legacy_AB_score_points": "ATOMIC_AXIS_DIAGNOSTIC_ONLY_NOT_CURRENT_AB_TOTAL",
            },
        }
    )
    write_json(ab_path, ab_payload, ruler_polities=load_ruler_polities(workspace_root))
    _write_text_atomic(ab_path.with_suffix(".md"), _render_formal_markdown("AB", ab_payload["records"]))


def _synchronize_current_c_outcome_view(workspace_root: Path) -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown

    """Keep every current C task visible without inventing missing outcomes."""
    c_path = workspace_root / C_PATH
    payload = _load(c_path)
    adjudication_payload = _load(workspace_root / C_OUTCOME_ADJUDICATIONS_PATH)
    adjudications = {
        str(item["ruler_id"]): item
        for item in adjudication_payload.get("adjudications") or ()
    }
    shared_binding_adjudications = {
        str(item["parent_cycle_ref"]): item
        for item in adjudication_payload.get(
            "shared_parent_ruler_binding_adjudications", ()
        )
    }
    if len(shared_binding_adjudications) != len(
        adjudication_payload.get("shared_parent_ruler_binding_adjudications", ())
    ):
        raise ValueError("C共享父任务人物绑定裁决存在重复父任务")
    for row in payload["records"]:
        adjudication = adjudications.get(str(row["ruler_id"])) or {}
        excluded_out_of_window = {
            str(ref)
            for ref in adjudication.get("excluded_out_of_window_parent_refs") or ()
        }
        capability_only = {
            str(ref) for ref in row.get("capability_only_parent_refs") or ()
        }
        current_refs = [
            str(ref)
            for ref in row.get("current_item_task_refs") or ()
            if str(ref) not in excluded_out_of_window and str(ref) not in capability_only
        ]
        if not current_refs:
            current_refs = [
                str(ref)
                for ref in row.get("independent_task_groups") or ()
                if (
                    isinstance(ref, str)
                    and str(ref) not in capability_only
                    and str(ref) not in excluded_out_of_window
                )
            ]
        current_refs = list(dict.fromkeys(current_refs))
        independent_cross_item_refs = list(dict.fromkeys(
            str(ref)
            for ref in adjudication.get(
                "cross_item_independent_information_refs", ()
            )
        ))
        if independent_cross_item_refs:
            current_or_capability = set(current_refs) | capability_only
            if not set(independent_cross_item_refs).issubset(current_or_capability):
                raise ValueError(
                    f"{row['ruler_name']}的C跨项独立信息引用越界"
                )
            row["cross_item_independent_information_refs"] = (
                independent_cross_item_refs
            )
        else:
            row.pop("cross_item_independent_information_refs", None)
        if excluded_out_of_window:
            existing_refs = {
                str(ref)
                for ref in row.get("independent_task_groups") or ()
            } | {
                str(ref)
                for ref in row.get("major_system_success_refs") or ()
            } | {
                str(ref)
                for ref in row.get("major_system_failure_refs") or ()
            } | {
                str(ref)
                for ref in row.get("excluded_out_of_window_parent_refs") or ()
            }
            if not excluded_out_of_window.issubset(existing_refs):
                unknown = sorted(excluded_out_of_window - existing_refs)
                raise ValueError(
                    f"{row['ruler_name']}的C越窗排除引用不属于当前任务: {unknown}"
                )
            row["independent_task_groups"] = [
                ref for ref in row.get("independent_task_groups") or ()
                if str(ref) not in excluded_out_of_window
            ]
            row["independent_task_count"] = len(row["independent_task_groups"])
            row["major_system_success_refs"] = [
                ref for ref in row.get("major_system_success_refs") or ()
                if str(ref) not in excluded_out_of_window
            ]
            row["major_system_failure_refs"] = [
                ref for ref in row.get("major_system_failure_refs") or ()
                if str(ref) not in excluded_out_of_window
            ]
            row["excluded_out_of_window_parent_refs"] = sorted(
                excluded_out_of_window
            )
            row["cap_reasons"] = [str(adjudication["reason"])]
        else:
            row.pop("excluded_out_of_window_parent_refs", None)
        previous = dict(row.get("task_outcome_profile") or {})
        class_by_ref = {
            str(ref): str(outcome)
            for outcome, outcome_refs in dict(
                previous.get("return_class_refs") or {}
            ).items()
            for ref in outcome_refs or ()
        }
        resolved = [
            (ref, class_by_ref.get(ref, "UNKNOWN")) for ref in current_refs
        ]
        counts: dict[str, int] = {}
        outcome_refs: dict[str, list[str]] = {}
        for ref, outcome in resolved:
            counts[outcome] = counts.get(outcome, 0) + 1
            outcome_refs.setdefault(outcome, []).append(ref)
        counts = dict(sorted(counts.items()))
        outcome_refs = dict(sorted(outcome_refs.items()))
        known = sum(count for outcome, count in counts.items() if outcome != "UNKNOWN")
        profile_source = str(previous.get("source") or "CURRENT_C_TASKS")
        if (
            any(outcome == "UNKNOWN" for _, outcome in resolved)
            and not profile_source.endswith("_WITH_EXPLICIT_UNKNOWN_CLOSURE")
        ):
            profile_source += "_WITH_EXPLICIT_UNKNOWN_CLOSURE"
        row["current_item_task_count"] = len(current_refs)
        row["current_item_task_refs"] = current_refs
        row["task_outcome_profile"] = {
            **previous,
            "source": profile_source,
            "selected_task_count": len(current_refs),
            "known_outcome_count": known,
            "return_class_counts": counts,
            "return_class_refs": outcome_refs,
            "status": "QUANTIFIED" if known else (
                "UNQUANTIFIED" if current_refs else "NOT_APPLICABLE"
            ),
        }
        row["current_task_basis_reason"] = (
            f"当前第三项独立体系压力父周期{len(current_refs)}项，已知结果{known}项，"
            f"回报剖面={counts}；重大体系胜绩"
            f"{len(row.get('major_system_success_refs') or ())}项、重大体系失败"
            f"{len(row.get('major_system_failure_refs') or ())}项。"
        )
    shared_owners: dict[str, list[tuple[str, str]]] = {}
    for row in payload["records"]:
        capability_only = {
            str(ref) for ref in row.get("capability_only_parent_refs") or ()
        }
        for ref in row.get("independent_task_groups") or ():
            ref = str(ref)
            shared_owners.setdefault(ref, []).append((
                str(row["ruler_id"]),
                (
                    "AUTHORIZED_CAPABILITY_ONLY_VIEW"
                    if ref in capability_only
                    else "CURRENT_RULER_WINDOW_VIEW"
                ),
            ))
    duplicated = {
        ref: sorted(bindings)
        for ref, bindings in shared_owners.items()
        if len(bindings) > 1
    }
    if set(duplicated) != set(shared_binding_adjudications):
        raise ValueError("C共享父任务人物绑定裁决没有精确覆盖当前重复父任务集合")
    for ref, expected in duplicated.items():
        decision = shared_binding_adjudications[ref]
        actual = sorted(
            (
                str(binding["ruler_id"]),
                str(binding["consumption_scope"]),
            )
            for binding in decision.get("ruler_bindings") or ()
        )
        if actual != expected:
            raise ValueError(f"C共享父任务人物绑定与当前消费范围不一致: {ref}")
        if (
            decision.get("binding_status")
            != "EXPLICIT_LEGACY_PARENT_RULER_SCOPE_CLOSED"
            or not str(decision.get("reason") or "").strip()
        ):
            raise ValueError(f"C共享父任务人物绑定裁决未闭合: {ref}")
    payload["shared_parent_ruler_binding_contract"] = {
        "status": "CLOSED",
        "shared_parent_count": len(duplicated),
        "binding_count": sum(len(bindings) for bindings in duplicated.values()),
        "source": str(C_OUTCOME_ADJUDICATIONS_PATH).replace("\\", "/"),
        "rule": "同一父任务按显式ruler_id与CURRENT/CAPABILITY_ONLY范围分别消费，不复制另一人物行动、结果或成本。",
    }
    write_json(c_path, payload, ruler_polities=load_ruler_polities(workspace_root))
    _write_text_atomic(
        c_path.with_suffix(".md"),
        _render_formal_markdown("C", payload["records"]),
    )


def write_current_third_item_settlement(workspace_root: Path) -> dict[str, Any]:
    _synchronize_current_ab_view(workspace_root)
    _synchronize_current_c_outcome_view(workspace_root)
    payload = build_current_third_item_settlement(workspace_root)
    json_path = workspace_root / FORMAL_PATH
    markdown_path = json_path.with_suffix(".md")
    _write_text_atomic(
        json_path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    _write_text_atomic(markdown_path, _render_current_weighted_markdown(payload["records"]))
    return payload
