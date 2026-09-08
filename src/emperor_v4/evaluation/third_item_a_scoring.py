"""A1/A2 state value and attributable change, without historical adjudication."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping


A_STATE_VALUES = {
    "A1": [0, 8, 18, 30, 40, 50],
    "A2": [0, 8, 16, 30, 40, 50],
}
A_CHANGE_WEIGHTS = {"improvement": 1.4, "deterioration": 0.5}
A_FORMULA = (
    "0.6 * clamp(0,100,state_value(end)+1.4*positive_value_delta+0.5*negative_value_delta"
    "+max(ceiling_bonus,maintenance_bonus,within_band_structure_credit)"
    "-max(reversal_penalty,within_band_deterioration_penalty))"
)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _grade(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5:
        raise ValueError("A状态档位须为0至5整数")
    return value


def _change_value(values: list[int], axis: Mapping[str, Any]) -> Decimal:
    start, end = _grade(axis["start_grade"]), _grade(axis["end_grade"])
    delta = end - start
    attributable = _decimal(axis["attributable_delta"])
    if delta > 0:
        steps = axis.get("improvement_step_credits") or []
        if len(steps) != delta:
            raise ValueError("A非线性改善须逐档闭合归责")
        result = Decimal(0)
        credits = Decimal(0)
        for index, step in enumerate(steps):
            if step.get("from_grade") != start + index or step.get("to_grade") != start + index + 1:
                raise ValueError("A改善逐档路径与窗口不一致")
            credit = _decimal(step["credit"])
            if credit not in map(Decimal, ("0", ".25", ".5", ".75", "1")):
                raise ValueError("A逐档改善信用不合法")
            credits += credit
            result += (values[start + index + 1] - values[start + index]) * credit
        if credits != attributable:
            raise ValueError("A逐档改善与归责档差不闭合")
        return result
    if axis.get("improvement_step_credits"):
        raise ValueError("A非改善窗口不得列正向跨档信用")
    if not Decimal(delta) <= attributable <= 0:
        raise ValueError("A下降责任越出窗口；跨项排除后的独立损失须显式声明责任路径")
    if delta == 0:
        return Decimal(0)
    return Decimal(values[end] - values[start]) * attributable / Decimal(delta)


def attributable_value_delta(axis_name: str, axis: Mapping[str, Any]) -> Decimal:
    values = A_STATE_VALUES[axis_name]
    start, end = _grade(axis["start_grade"]), _grade(axis["end_grade"])
    segments = axis.get("active_window_segments") or []
    liability = axis.get("post_exclusion_liability")
    if segments and liability:
        raise ValueError("A多窗口与跨项排除责任路径不得重叠使用")
    if liability:
        if not axis.get("excluded_cross_item_refs") or not liability.get("basis"):
            raise ValueError("A独立损失须有跨项排除及责任依据")
        refs = liability.get("source_refs") or []
        if not refs or not set(refs).issubset(axis.get("attribution_source_refs") or []):
            raise ValueError("A独立损失引用须属于本人归责来源")
        if set(refs) & set(axis["excluded_cross_item_refs"]):
            raise ValueError("A独立损失不得使用已排除的成果来源")
        if (liability["end_grade"] != end
                or liability["start_grade"] <= start
                or axis["objective_delta"] != end - start
                or liability["attributable_delta"] != axis["attributable_delta"]
                or liability["end_grade"] >= liability["start_grade"]):
            raise ValueError("A跨项排除责任路径未与既有损失和终点闭合")
        return _change_value(values, liability)
    if segments:
        if segments[0]["start_grade"] != start or segments[-1]["end_grade"] != end:
            raise ValueError("A多窗口外侧端点不一致")
        if len({s.get("window_ref") for s in segments}) != len(segments) or any(not s.get("window_ref") for s in segments):
            raise ValueError("A多窗口须有唯一窗口引用")
        if sum(s["end_grade"] - s["start_grade"] for s in segments) != axis["objective_delta"]:
            raise ValueError("A多窗口客观变化汇总不一致")
        if sum(_decimal(s["attributable_delta"]) for s in segments) != _decimal(axis["attributable_delta"]):
            raise ValueError("A多窗口本人归责汇总不一致")
        expected_steps = [dict(step, window_ref=s["window_ref"]) for s in segments for step in s.get("improvement_step_credits") or []]
        if (axis.get("improvement_step_credits") or []) != expected_steps:
            raise ValueError("A多窗口逐档信用未按窗口汇总")
        for s in segments:
            if s.get("delta") != s["end_grade"] - s["start_grade"]:
                raise ValueError("A窗口客观档差不一致")
        return sum((_change_value(values, s) for s in segments), Decimal(0))
    if axis["objective_delta"] != end - start:
        raise ValueError("A客观档差与起终不一致")
    return _change_value(values, axis)


def calculate_a_axis(
    axis_name: str, axis: Mapping[str, Any], *, structure_credit: float = 0,
) -> dict[str, float]:
    """Return deterministic fields; special-credit evidence is validated by the caller."""
    end_value = Decimal(A_STATE_VALUES[axis_name][_grade(axis["end_grade"])])
    value_delta = attributable_value_delta(axis_name, axis)
    # Validate the whole path first, then weight each window's signed change.
    # Weighting the net value would incorrectly cancel separately attributable gains/losses.
    segments = axis.get("active_window_segments") or []
    changes = ([_change_value(A_STATE_VALUES[axis_name], s) for s in segments]
               if segments else [value_delta])
    positive = sum((max(Decimal(0), value) for value in changes), Decimal(0))
    negative = sum((min(Decimal(0), value) for value in changes), Decimal(0))
    positive_credit = _decimal(A_CHANGE_WEIGHTS["improvement"]) * positive
    negative_credit = _decimal(A_CHANGE_WEIGHTS["deterioration"]) * negative
    change = positive_credit + negative_credit
    special = max(_decimal(axis.get("ceiling_progress_bonus") or 0),
                  _decimal(axis.get("maintenance_bonus") or 0), _decimal(structure_credit))
    anchor_raw = end_value + negative_credit - _decimal(axis.get("negative_adjustment") or 0)
    raw = anchor_raw + positive_credit + special
    clipped = max(Decimal(0), min(Decimal(100), raw))
    anchor = max(Decimal(0), min(Decimal(100), anchor_raw))
    points = (clipped * Decimal(".6")).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    anchor_points = (anchor * Decimal(".6")).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    return {
        "end_state_value": float(end_value),
        "attributable_value_delta": float(value_delta),
        "positive_value_delta": float(positive),
        "negative_value_delta": float(negative),
        "weighted_change_value": float(change),
        "unclamped_trajectory_value": float(raw),
        "trajectory_value": float(clipped),
        "axis_points": float(points),
        "non_cost_anchor_points": float(anchor_points),
        "positive_result_credit_points": float(points - anchor_points),
    }
