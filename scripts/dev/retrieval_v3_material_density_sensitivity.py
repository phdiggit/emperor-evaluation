from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping, Sequence


SCENARIOS: tuple[dict[str, Any], ...] = (
    {"scenario": "all_equal_sum", "material_decay": "0", "event_decay": "0", "object_decay": "0"},
    {"scenario": "gentle_decay", "material_decay": "0.5", "event_decay": "0.5", "object_decay": "0.25"},
    {"scenario": "balanced_decay", "material_decay": "1", "event_decay": "1", "object_decay": "0.5"},
    {"scenario": "strong_density_control", "material_decay": "1.25", "event_decay": "1.25", "object_decay": "0.75"},
)


def text(value: Any) -> str:
    return str(value or "").strip()


def decimal_value(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def quant(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def rank_weight(rank: int, decay: Decimal) -> Decimal:
    if rank < 1:
        raise ValueError("rank must be positive")
    return Decimal(str(rank ** -float(decay)))


def weighted_rank_sum(values: Sequence[Decimal], decay: Decimal) -> tuple[Decimal, list[dict[str, Any]]]:
    ordered = sorted((decimal_value(value) for value in values), reverse=True)
    components: list[dict[str, Any]] = []
    total = Decimal("0")
    for rank, value in enumerate(ordered, start=1):
        weight = rank_weight(rank, decay)
        contribution = value * weight
        total += contribution
        components.append({
            "rank": rank,
            "input_value": str(quant(value)),
            "weight": str(quant(weight)),
            "weighted_value": str(quant(contribution)),
        })
    return total, components


def material_event_key(material: Mapping[str, Any]) -> str:
    event_keys = sorted({text(key) for key in material.get("event_group_keys") or [] if text(key)})
    if event_keys:
        return "|".join(event_keys)
    return "claim:" + text(material.get("claim_key") or material.get("claim_id"))


def weighted_material_sum(
    materials: Sequence[Mapping[str, Any]], decay: Decimal
) -> tuple[Decimal, list[dict[str, Any]]]:
    ordered = sorted(
        materials,
        key=lambda row: (
            -decimal_value(row.get("abs_score")),
            text(row.get("claim_key")),
            text(row.get("binding_code")),
        ),
    )
    total = Decimal("0")
    components: list[dict[str, Any]] = []
    for rank, material in enumerate(ordered, start=1):
        value = decimal_value(material.get("abs_score"))
        weight = rank_weight(rank, decay)
        contribution = value * weight
        total += contribution
        components.append({
            "rank": rank,
            "claim_key": text(material.get("claim_key")),
            "binding_code": text(material.get("binding_code")),
            "factor_judgment_id": material.get("factor_judgment_id"),
            "input_value": str(quant(value)),
            "weight": str(quant(weight)),
            "weighted_value": str(quant(contribution)),
        })
    return total, components


def aggregate_side(
    materials: Sequence[Mapping[str, Any]], *, material_decay: Decimal, event_decay: Decimal, object_decay: Decimal
) -> dict[str, Any]:
    event_materials: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for material in materials:
        object_key = text(material.get("object_id")) or "binding:" + text(material.get("binding_code"))
        event_materials[(object_key, material_event_key(material))].append(material)
    object_events: dict[str, list[Decimal]] = defaultdict(list)
    event_rows: list[dict[str, Any]] = []
    for (object_key, event_key), values in sorted(event_materials.items()):
        event_value, components = weighted_material_sum(values, material_decay)
        object_events[object_key].append(event_value)
        event_rows.append({
            "object_key": object_key,
            "event_key": event_key,
            "material_count": len(values),
            "event_value": str(quant(event_value)),
            "material_components": components,
        })
    object_rows: list[dict[str, Any]] = []
    object_values: list[Decimal] = []
    for object_key, values in sorted(object_events.items()):
        object_value, components = weighted_rank_sum(values, event_decay)
        object_values.append(object_value)
        object_rows.append({
            "object_key": object_key,
            "event_count": len(values),
            "object_value": str(quant(object_value)),
            "event_components": components,
        })
    signal, object_components = weighted_rank_sum(object_values, object_decay)
    positive_weights = [
        decimal_value(component["weight"])
        for event in event_rows for component in event["material_components"]
    ]
    return {
        "signal": str(quant(signal)),
        "material_count": len(materials),
        "event_count": len(event_rows),
        "object_count": len(object_rows),
        "all_materials_accounted": sum(row["material_count"] for row in event_rows) == len(materials),
        "minimum_material_stage_weight": str(quant(min(positive_weights))) if positive_weights else None,
        "event_rows": event_rows,
        "object_rows": object_rows,
        "object_components": object_components,
    }


def _details_by_emperor(details: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        text(row.get("emperor_name")): row
        for row in details.values()
        if isinstance(row, Mapping) and text(row.get("emperor_name"))
    }


def build_sensitivity_report(
    *, score_details: Mapping[str, Any], emperors: Sequence[str], scenarios: Sequence[Mapping[str, Any]] = SCENARIOS
) -> dict[str, Any]:
    details = _details_by_emperor(score_details)
    scenario_rows: list[dict[str, Any]] = []
    for raw_scenario in scenarios:
        scenario = dict(raw_scenario)
        material_decay = decimal_value(scenario.get("material_decay"))
        event_decay = decimal_value(scenario.get("event_decay"))
        object_decay = decimal_value(scenario.get("object_decay"))
        results: list[dict[str, Any]] = []
        for emperor in emperors:
            detail = details.get(text(emperor), {})
            calc = detail.get("calc_detail") or {}
            materials = [row for row in calc.get("materials") or [] if isinstance(row, Mapping)]
            positive = aggregate_side(
                [row for row in materials if text(row.get("side")) == "positive"],
                material_decay=material_decay, event_decay=event_decay, object_decay=object_decay)
            negative = aggregate_side(
                [row for row in materials if text(row.get("side")) == "negative"],
                material_decay=material_decay, event_decay=event_decay, object_decay=object_decay)
            results.append({
                "emperor_name": text(emperor),
                "current_positive_signal": text(detail.get("positive_signal")),
                "current_negative_signal": text(detail.get("negative_signal")),
                "unscaled_positive_signal": positive["signal"],
                "unscaled_negative_signal": negative["signal"],
                "unscaled_net_signal": str(quant(decimal_value(positive["signal"]) - decimal_value(negative["signal"]))),
                "all_materials_accounted": positive["all_materials_accounted"] and negative["all_materials_accounted"],
                "positive": positive,
                "negative": negative,
            })
        positive_current = sum((decimal_value(row["current_positive_signal"]) for row in results), Decimal("0"))
        negative_current = sum((decimal_value(row["current_negative_signal"]) for row in results), Decimal("0"))
        positive_unscaled = sum((decimal_value(row["unscaled_positive_signal"]) for row in results), Decimal("0"))
        negative_unscaled = sum((decimal_value(row["unscaled_negative_signal"]) for row in results), Decimal("0"))
        positive_scale = positive_current / positive_unscaled if positive_unscaled else Decimal("1")
        negative_scale = negative_current / negative_unscaled if negative_unscaled else Decimal("1")
        for row in results:
            scaled_positive = decimal_value(row["unscaled_positive_signal"]) * positive_scale
            scaled_negative = decimal_value(row["unscaled_negative_signal"]) * negative_scale
            row["scaled_positive_signal"] = str(quant(scaled_positive))
            row["scaled_negative_signal"] = str(quant(scaled_negative))
            row["scaled_net_signal"] = str(quant(scaled_positive - scaled_negative))
        scenario_rows.append({
            **scenario,
            "strictly_positive_rank_weights": True,
            "drops_scored_materials": False,
            "hard_cap_applied": False,
            "three_emperor_positive_scale": str(quant(positive_scale)),
            "three_emperor_negative_scale": str(quant(negative_scale)),
            "results": results,
        })
    return {
        "ok": True,
        "mode": "report_only_density_sensitivity",
        "scale_scope": "three_emperor_lane_totals_preserved_for_sensitivity_only",
        "write_db": False,
        "formal_score_changed": False,
        "all_scored_materials_must_contribute": True,
        "hard_caps_allowed": False,
        "scenarios": scenario_rows,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 入分材料密度敏感性分析", "",
        "> 每条入分材料均参与计算且权重大于零；不删材料、不取 Top-K、不设硬上限。本报告不改正式分。", "",
    ]
    scenarios = report.get("scenarios") or []
    if scenarios:
        lines.extend([
            "## 当前公式基线", "", "| 皇帝 | current + | current - | current net |",
            "| --- | ---: | ---: | ---: |",
        ])
        for row in scenarios[0].get("results") or []:
            current_positive = decimal_value(row.get("current_positive_signal"))
            current_negative = decimal_value(row.get("current_negative_signal"))
            lines.append(
                f"| {row.get('emperor_name')} | {quant(current_positive)} | {quant(current_negative)} | "
                f"{quant(current_positive - current_negative)} |"
            )
        lines.extend([
            "", "> 各场景只在三人范围内分别保持正向、负向总量，用于比较分配变化；该缩放不是正式全局参数。", "",
        ])
    for scenario in scenarios:
        lines.extend([
            f"## {scenario.get('scenario')}", "",
            f"- decay material/event/object: `{scenario.get('material_decay')}/{scenario.get('event_decay')}/{scenario.get('object_decay')}`",
            "", "| 皇帝 | scaled + | scaled - | scaled net | materials accounted |",
            "| --- | ---: | ---: | ---: | --- |",
        ])
        for row in scenario.get("results") or []:
            material_count = int((row.get("positive") or {}).get("material_count") or 0) + int((row.get("negative") or {}).get("material_count") or 0)
            lines.append(
                f"| {row.get('emperor_name')} | {row.get('scaled_positive_signal')} | "
                f"{row.get('scaled_negative_signal')} | {row.get('scaled_net_signal')} | "
                f"{material_count}/{str(row.get('all_materials_accounted')).lower()} |"
            )
        lines.append("")
    return "\n".join(lines)
