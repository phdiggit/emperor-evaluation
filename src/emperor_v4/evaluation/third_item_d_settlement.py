from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.third_item_d_cycle_registry import (
    AXIS_KEYS,
    PUBLIC_REGISTRY_PATH,
    consumed_cycle_records,
    load_third_item_d_cycle_registry,
    validate_third_item_d_cycle_registry,
)


FORMULA = (
    "4*(SB-SN)+3*(BCP-BCN)+2*WR-"
    "P_penalty(P)-4*S-M-A_scoring"
)
P_PENALTY_BY_GRADE = (0, 4, 8, 12, 16, 24, 32, 40)
P_THRESHOLDS = (0, 1, 100, 1_000, 10_000, 100_000, 300_000, 1_000_000)
BENEFIT_AXES = ("SB", "SN", "BCP", "BCN", "WR")
FORMAL_SETTLEMENT_JSON_PATH = Path(
    "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
)
FORMAL_SETTLEMENT_MARKDOWN_PATH = FORMAL_SETTLEMENT_JSON_PATH.with_suffix(".md")
WR_EVIDENCE_STATUSES = {
    "EXPLICIT_REALIZED", "SIMPLIFIED_INFERRED", "UNKNOWN", "CONFIRMED_NONE",
}
WR_SIMPLIFIED_TRANSFER_MODES = {
    "NONE_OR_DESTROYED": (0, 0),
    "ROUT_WITH_ASSETS_ESCAPED": (0, 1),
    "PARTIAL_FIELD_CAPTURE": (0, 2),
    "CAMP_OR_MAJOR_FORCE_CAPTURE": (1, 3),
    "COMPLETE_FORCE_OR_CENTRAL_TRANSFER": (2, 4),
    "STATE_RESOURCE_SYSTEM_INTEGRATION": (3, 5),
}
WR_SIMPLIFIED_RETENTION = {
    "RETAINED_USABLE", "PARTIAL_OR_UNCERTAIN", "LOST_RETURNED_UNUSABLE",
}
WR_EXPLICIT_ROLLUP_COVERAGE = {
    "EXPLICIT_COMPLETE_ROLLUP", "EXPLICIT_PARTIAL_FLOOR",
}
FUTURE_D_CANDIDATE_Q_BOUNDARIES = (12, 27)
D_SCORE_POINTS = {
    "D0": {"LOW": 0.0, "MID": 3.0, "HIGH": 6.0},
    "D1": {"LOW": 10.0, "MID": 12.0, "HIGH": 14.0},
    "D2": {"LOW": 18.0, "MID": 20.0, "HIGH": 22.0},
    "D3": {"LOW": 24.0, "MID": 26.0, "HIGH": 28.0},
    "D4": {"LOW": 30.0, "MID": 32.0, "HIGH": 34.0},
    "D5": {"LOW": 36.0, "MID": 38.0, "HIGH": 40.0},
    "D-N": {"NOT_APPLICABLE": 0.0},
}
P_REVIEW_STATUSES = {
    "FACT_SEMANTICALLY_REVIEWED", "FORMAL_VALUE_MATCH_ONLY", "UNREVIEWED",
}
P_CANONICAL_STATUSES = {
    "FORMAL_VALUE_MATCH_ONLY", "CANONICAL_VALUE_NOT_LOCATED",
    "FORMAL_VALUE_DIVERGENCE_UNREVIEWED",
    "UPSTREAM_CONFLICT_SHADOW_OVERRIDE_ONLY",
}
CROSS_AXIS_OVERLAP_STATUSES = {"INDEPENDENT", "RESCOPED", "UNRESOLVED"}
SYSTEM_DAMAGE_REAUDIT_STATUSES = {"RESOLVED", "BOUNDED_PENDING"}
SYSTEM_DAMAGE_REAUDIT_CLASSES = {"B", "C", "D", "E"}
MANUAL_CROSS_AXIS_OVERLAP_REVIEW_REFS = {
    "XZTJ-SONG-XIA-FIVE-ROUTE-1081",
}
def p_penalty(p_grade: int) -> int:
    """Map P0-P7 to the single contract-level personnel penalty."""
    grade = int(p_grade)
    if not 0 <= grade <= 7:
        raise ValueError(f"P档超出P0—P7：{grade}")
    penalty = 4 * grade + 4 * max(grade - 4, 0)
    if penalty != P_PENALTY_BY_GRADE[grade]:
        raise AssertionError("P尾部映射与固定表不一致")
    return penalty


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("空样本不能计算分位数")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 2)


def _distribution(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "q1": None, "q3": None}
    return {
        "mean": round(sum(values) / len(values), 2),
        "median": _percentile(values, 0.5),
        "q1": _percentile(values, 0.25),
        "q3": _percentile(values, 0.75),
    }


def _q_axis_contributions(row: Mapping[str, Any]) -> dict[str, int]:
    axes = row["parent_axes"]
    return {
        "SB": 4 * int(axes["SB"]), "SN": -4 * int(axes["SN"]),
        "BCP": 3 * int(axes["BCP"]), "BCN": -3 * int(axes["BCN"]),
        "WR": 2 * int(axes["WR"]), "P": -p_penalty(int(axes["P"])),
        "S": -4 * int(axes["S"]), "M": -int(axes["M"]),
        "A_scoring": -int(row["asset_components"]["A_scoring"]),
    }


def _driving_axes(row: Mapping[str, Any]) -> list[str]:
    contributions = _q_axis_contributions(row)
    largest = max(abs(value) for value in contributions.values())
    return sorted(axis for axis, value in contributions.items() if abs(value) == largest)


def _build_three_case_q_comparison(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    wanted_refs = (
        "CAMPAIGN-TANG-TUYUHUN-634-635",
        "MING-NORTHERN-YUAN-NAHACU-1387",
        "MING-NORTHERN-YUAN-BUYUR-KARAKORUM-1388",
    )
    by_ref = {str(row["investment_cycle_ref"]): row for row in rows}
    if any(ref not in by_ref for ref in wanted_refs):
        return {"samples": [], "pair_differences": []}

    samples = []
    for ref in wanted_refs:
        row = by_ref[ref]
        samples.append({
            "investment_cycle_ref": ref,
            "sample_label": row["sample_label"],
            "q_contribution": row["q_contribution"],
            "q_candidate_range": dict(row["q_candidate_range"]),
            "axis_contributions": _q_axis_contributions(row),
        })

    def difference(target_ref: str, baseline_ref: str, interpretation: str) -> dict[str, Any]:
        target = by_ref[target_ref]
        baseline = by_ref[baseline_ref]
        target_contributions = _q_axis_contributions(target)
        baseline_contributions = _q_axis_contributions(baseline)
        target_q = int(target["q_contribution"])
        baseline_q = int(baseline["q_contribution"])
        return {
            "target_ref": target_ref,
            "baseline_ref": baseline_ref,
            "q_difference": target_q - baseline_q,
            "point_ratio": None if baseline_q == 0 else round(target_q / baseline_q, 2),
            "axis_contribution_deltas": {
                axis: target_contributions[axis] - baseline_contributions[axis]
                for axis in target_contributions
            },
            "interpretation": interpretation,
            "metric_warning": "Q是线性净收益差，不是军事成就倍数；点值比不得解释为军事成就高一倍。",
        }

    tuyuhun = by_ref["CAMPAIGN-TANG-TUYUHUN-634-635"]
    tuyuhun_selected_bcp = int(tuyuhun["parent_axes"]["BCP"])
    tuyuhun_selected_q = int(tuyuhun["q_contribution"])
    a_selected = int(tuyuhun["asset_components"]["A_scoring"])
    a_lower = int(tuyuhun["asset_components"]["A_scoring_lower"])
    a_upper = int(tuyuhun["asset_components"]["A_scoring_upper"])
    bcp_scenarios = []
    for bcp_grade in (0, 2, 3):
        scenario_q = tuyuhun_selected_q + 3 * (bcp_grade - tuyuhun_selected_bcp)
        bcp_scenarios.append({
            "BCP": bcp_grade,
            "q_contribution": scenario_q,
            "q_candidate_range": {
                "lower": scenario_q - (a_upper - a_selected),
                "upper": scenario_q + (a_selected - a_lower),
            },
            "difference_from_nahacu": int(by_ref["MING-NORTHERN-YUAN-NAHACU-1387"]["q_contribution"]) - scenario_q,
            "difference_from_buyur": int(by_ref["MING-NORTHERN-YUAN-BUYUR-KARAKORUM-1388"]["q_contribution"]) - scenario_q,
        })

    return {
        "samples": samples,
        "tuyuhun_bcp_scenarios": bcp_scenarios,
        "pair_differences": [
            difference(
                "MING-NORTHERN-YUAN-NAHACU-1387",
                "CAMPAIGN-TANG-TUYUHUN-634-635",
                "吐谷浑与纳哈出横裁后同为WR4；纳哈出的直接军镇BCP3只比CLIENT_BUFFER BCP2多一档，而其更高M与A使净Q略低。",
            ),
            difference(
                "MING-NORTHERN-YUAN-BUYUR-KARAKORUM-1388",
                "CAMPAIGN-TANG-TUYUHUN-634-635",
                "捕鱼儿海—和林与吐谷浑横裁后同为WR4；P1相对P3的低己方伤亡优势，被无BCP与较低SB抵消，不能表述为战果更大。",
            ),
        ],
    }


def _build_precision_review_triggers(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    numeric = [
        row for row in rows
        if row["q_candidate_range"]["lower"] is not None
        and row["q_candidate_range"]["upper"] is not None
    ]
    top_lower = {
        row["investment_cycle_ref"] for row in sorted(
            numeric,
            key=lambda item: (item["q_candidate_range"]["lower"], item["investment_cycle_ref"]),
            reverse=True,
        )[:5]
    }
    top_upper = {
        row["investment_cycle_ref"] for row in sorted(
            numeric,
            key=lambda item: (item["q_candidate_range"]["upper"], item["investment_cycle_ref"]),
            reverse=True,
        )[:5]
    }
    bottom_lower = {
        row["investment_cycle_ref"] for row in sorted(
            numeric,
            key=lambda item: (item["q_candidate_range"]["lower"], item["investment_cycle_ref"]),
        )[:5]
    }
    bottom_upper = {
        row["investment_cycle_ref"] for row in sorted(
            numeric,
            key=lambda item: (item["q_candidate_range"]["upper"], item["investment_cycle_ref"]),
        )[:5]
    }
    membership_sensitive = (
        (top_lower ^ top_upper) | (bottom_lower ^ bottom_upper)
    )
    triggers = []
    for row in numeric:
        lower = int(row["q_candidate_range"]["lower"])
        upper = int(row["q_candidate_range"]["upper"])
        wr_bounds = row["axis_candidate_ranges"]["WR"]
        wr_width = int(wr_bounds["upper"]) - int(wr_bounds["lower"])
        reasons = []
        if lower <= 0 <= upper and lower != upper:
            reasons.append("Q_CROSSES_ZERO")
        crossed_boundaries = [
            boundary for boundary in FUTURE_D_CANDIDATE_Q_BOUNDARIES
            if lower < boundary <= upper
        ]
        if crossed_boundaries:
            reasons.append(
                "Q_CROSSES_FUTURE_D_BOUNDARY_" + "_".join(map(str, crossed_boundaries))
            )
        if row["investment_cycle_ref"] in membership_sensitive:
            reasons.append("TOP_OR_BOTTOM_5_MEMBERSHIP_SENSITIVE")
        if wr_width >= 3 and (
            int(row["parent_axes"]["SB"] or 0) >= 3
            or int(row["parent_axes"]["BCP"] or 0) >= 2
        ):
            reasons.append("WR_WIDTH_GE_3_WITH_SB3_OR_BCP2")
        if reasons:
            triggers.append({
                "investment_cycle_ref": row["investment_cycle_ref"],
                "sample_label": row["sample_label"],
                "q_candidate_range": dict(row["q_candidate_range"]),
                "wr_candidate_range": dict(wr_bounds),
                "reasons": reasons,
            })
    return {
        "trigger_count": len(triggers),
        "records": triggers,
        "computed_from_records": True,
        "future_d_candidate_q_boundaries": list(FUTURE_D_CANDIDATE_Q_BOUNDARIES),
    }


def _build_p_basis_audit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    records = []
    for row in rows:
        p_facts = [
            fact for phase in row["ordered_phase_facts"]
            for fact in phase["cost_facts"]
            if fact["fact_type"] == "PERSONNEL_LOSS"
        ]
        basis_texts = [str(fact.get("basis") or "") for fact in p_facts]
        audit = dict(row.get("p_audit") or {})
        review_status = str(audit.get("review_status") or "UNREVIEWED")
        canonical_status = str(
            audit.get("canonical_status") or "CANONICAL_VALUE_NOT_LOCATED"
        )
        if review_status not in P_REVIEW_STATUSES:
            raise ValueError(f"P审查状态非法：{review_status}")
        if canonical_status not in P_CANONICAL_STATUSES:
            raise ValueError(f"P canonical状态非法：{canonical_status}")
        canonical_refs = [str(ref) for ref in audit.get("canonical_refs") or ()]
        if review_status != "UNREVIEWED" and not canonical_refs:
            raise ValueError("已审查或仅形式同值的P记录必须给canonical_refs")
        if review_status == "FACT_SEMANTICALLY_REVIEWED" and not audit.get(
            "review_basis"
        ):
            raise ValueError("P史实语义审查必须给review_basis")
        upstream_unresolved = (
            canonical_status == "UPSTREAM_CONFLICT_SHADOW_OVERRIDE_ONLY"
        )
        records.append({
            "investment_cycle_ref": row["investment_cycle_ref"],
            "sample_label": row["sample_label"],
            "parent_p_grade": row["parent_axes"]["P"],
            "personnel_loss_fact_count": len(p_facts),
            "basis_texts": basis_texts,
            "basis_missing_fact_count": sum(not basis for basis in basis_texts),
            "review_status": review_status,
            "canonical_status": canonical_status,
            "canonical_refs": canonical_refs,
            "review_basis": str(audit.get("review_basis") or ""),
            "discovered_error_lower_bound": bool(
                audit.get("discovered_error_lower_bound")
            ),
            "upstream_unresolved": upstream_unresolved,
        })
    return {
        "record_count": len(records),
        "records": records,
        "basis_missing_fact_count": sum(
            item["basis_missing_fact_count"] for item in records
        ),
        "fact_semantically_reviewed_count": sum(
            item["review_status"] == "FACT_SEMANTICALLY_REVIEWED"
            for item in records
        ),
        "formal_value_match_only_count": sum(
            item["review_status"] == "FORMAL_VALUE_MATCH_ONLY"
            for item in records
        ),
        "unreviewed_count": sum(
            item["review_status"] == "UNREVIEWED" for item in records
        ),
        "canonical_value_not_located_count": sum(
            item["canonical_status"] == "CANONICAL_VALUE_NOT_LOCATED"
            for item in records
        ),
        "discovered_error_lower_bound_count": sum(
            item["discovered_error_lower_bound"] for item in records
        ),
        "upstream_unresolved_conflict_count": sum(
            item["upstream_unresolved"] for item in records
        ),
        "formal_value_divergence_unreviewed_count": sum(
            item["canonical_status"] == "FORMAL_VALUE_DIVERGENCE_UNREVIEWED"
            for item in records
        ),
        "computed_from_records": True,
        "scope_note": "只统计配置声明的可追溯审查状态；形式同值不等于史实语义通过，UNREVIEWED不进入正确率分母。",
    }


def _build_sample_statistics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    closed = [row for row in rows if row["q_contribution"] is not None]
    q_values = [float(row["q_contribution"]) for row in closed]
    lower_values = [float(row["q_candidate_range"]["lower"]) for row in closed]
    upper_values = [float(row["q_candidate_range"]["upper"]) for row in closed]
    event_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in closed:
        event_groups[str(row["event_type"])].append(row)

    def ranked(items: Sequence[Mapping[str, Any]], key: Any, reverse: bool) -> list[dict[str, Any]]:
        selected = sorted(items, key=key, reverse=reverse)[:5]
        return [
            {
                "investment_cycle_ref": row["investment_cycle_ref"],
                "sample_label": row["sample_label"],
                "ruler_name": row["ruler_name"],
                "q_contribution": row["q_contribution"],
                "q_candidate_range": row["q_candidate_range"],
                "range_width": row["q_candidate_range"]["upper"] - row["q_candidate_range"]["lower"],
                "driving_axes": _driving_axes(row),
                "uncertain_axes": sorted(
                    axis for axis, bounds in row["axis_candidate_ranges"].items()
                    if bounds["lower"] != bounds["upper"]
                ),
            }
            for row in selected
        ]

    count = len(closed)
    positive = sum(row["q_candidate_range"]["lower"] > 0 for row in closed)
    negative = sum(row["q_candidate_range"]["upper"] < 0 for row in closed)
    crosses_zero = sum(
        row["q_candidate_range"]["lower"] <= 0 <= row["q_candidate_range"]["upper"]
        and row["q_candidate_range"]["lower"] != row["q_candidate_range"]["upper"]
        for row in closed
    )
    return {
        "sample_scope": "LOCAL_INFORMATION_RICH_CALIBRATION_SAMPLE_NOT_FULL_POPULATION",
        "total_sample_count": len(rows),
        "sample_count": count,
        "unknown_q_count": len(rows) - count,
        "unknown_q_refs": [
            row["investment_cycle_ref"] for row in rows
            if row["q_contribution"] is None
        ],
        "q": _distribution(q_values),
        "q_lower_bound": _distribution(lower_values),
        "q_upper_bound": _distribution(upper_values),
        "direction_counts": {
            "positive": positive, "negative": negative,
            "crosses_zero": crosses_zero,
            "balanced_point": sum(row["q_contribution"] == 0 for row in closed),
        },
        "direction_rates": {
            "positive": None if count == 0 else round(positive / count, 4),
            "negative": None if count == 0 else round(negative / count, 4),
            "crosses_zero": None if count == 0 else round(crosses_zero / count, 4),
        },
        "high_axis_counts": {
            axis: sum(int(row["parent_axes"][axis]) >= 4 for row in closed)
            for axis in ("SB", "BCP", "WR")
        },
        "by_event_type": {
            event_type: {
                "sample_count": len(group),
                "q": _distribution([float(row["q_contribution"]) for row in group]),
                "positive_count": sum(row["q_contribution"] > 0 for row in group),
                "negative_count": sum(row["q_contribution"] < 0 for row in group),
                "balanced_count": sum(row["q_contribution"] == 0 for row in group),
            }
            for event_type, group in sorted(event_groups.items())
        },
        "highest_q_5": ranked(closed, lambda row: (row["q_contribution"], row["investment_cycle_ref"]), True),
        "lowest_q_5": ranked(closed, lambda row: (row["q_contribution"], row["investment_cycle_ref"]), False),
        "widest_interval_5": ranked(
            closed,
            lambda row: (
                row["q_candidate_range"]["upper"] - row["q_candidate_range"]["lower"],
                row["investment_cycle_ref"],
            ),
            True,
        ),
        "three_case_q_comparison": _build_three_case_q_comparison(closed),
        "precision_review_triggers": _build_precision_review_triggers(rows),
        "p_basis_audit": _build_p_basis_audit(rows),
    }


def _parse_date(value: object) -> date:
    return date.fromisoformat(str(value))


def _source_refs(fact: Mapping[str, Any], label: str) -> list[str]:
    refs = [str(ref) for ref in fact.get("source_refs") or () if str(ref)]
    if not refs:
        raise ValueError(f"{label}缺少source_refs")
    return refs


def _grade(value: object, axis: str, *, maximum: int = 5) -> int | None:
    if value is None:
        return None
    parsed = int(value)
    if not 0 <= parsed <= maximum:
        raise ValueError(f"{axis}档位越界：{parsed}")
    return parsed


def _p_grade(center_equivalent: float) -> int:
    if center_equivalent == 0:
        return 0
    for grade in range(1, 7):
        if center_equivalent < P_THRESHOLDS[grade + 1]:
            return grade
    return 7


def _validate_personnel_equivalent_center_grade(
    adjudication: Mapping[str, Any], *, expected_grade: int, label: str,
) -> float:
    """Validate one inferred/direct personnel range through the sole P map."""
    equivalent_range = adjudication.get("equivalent_range")
    if (
        not isinstance(equivalent_range, (list, tuple))
        or len(equivalent_range) != 2
        or not all(isinstance(value, (int, float)) for value in equivalent_range)
    ):
        raise ValueError(f"{label}死亡当量区间非法")
    lower, upper = map(float, equivalent_range)
    if not 0 <= lower <= upper:
        raise ValueError(f"{label}死亡当量区间非法")
    explicit_center = adjudication.get("center")
    if explicit_center is None:
        if lower == upper:
            center = lower
        elif lower > 0:
            center = sqrt(lower * upper)
        else:
            raise ValueError(f"{label}跨零区间必须显式保存center")
    else:
        center = float(explicit_center)
    if not lower <= center <= upper:
        raise ValueError(f"{label}center不在死亡当量区间内")
    mapped_grade = _p_grade(center)
    if mapped_grade != int(expected_grade):
        raise ValueError(
            f"{label}center与P_scoring映射不一致："
            f"center={center:g}/mapped=P{mapped_grade}/"
            f"declared=P{expected_grade}"
        )
    return center


def benefit_claim_ref(claim: Mapping[str, Any]) -> str:
    identity = {
        "historical_object_ref": str(claim.get("historical_object_ref") or ""),
        "from_state": str(claim.get("from_state") or ""),
        "to_state": str(claim.get("to_state") or ""),
        "benefit_window_start": str(claim.get("benefit_window_start") or ""),
        "benefit_window_end": str(claim.get("benefit_window_end") or ""),
    }
    if not all(identity.values()):
        raise ValueError(f"收益claim身份未闭合：{identity}")
    if _parse_date(identity["benefit_window_end"]) < _parse_date(
        identity["benefit_window_start"]
    ):
        raise ValueError(f"收益claim时间窗倒置：{identity}")
    digest = sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    return f"BENEFIT-{digest}"


def _windows_overlap(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return max(
        _parse_date(left["benefit_window_start"]),
        _parse_date(right["benefit_window_start"]),
    ) <= min(
        _parse_date(left["benefit_window_end"]),
        _parse_date(right["benefit_window_end"]),
    )


def _rollup_personnel(phases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: set[str] = set()
    fact_refs: list[str] = []
    minimum = 0.0
    maximum = 0.0
    unresolved = False
    for phase in phases:
        for fact in phase.get("cost_facts") or ():
            if fact.get("fact_type") != "PERSONNEL_LOSS":
                continue
            _source_refs(fact, "P事实")
            fact_ref = str(fact.get("fact_ref") or "")
            group_ref = str(fact.get("casualty_group_ref") or "")
            if not fact_ref or not group_ref:
                raise ValueError("P事实缺少fact_ref或casualty_group_ref")
            if group_ref in groups:
                raise ValueError(f"P人员群重复消费：{group_ref}")
            groups.add(group_ref)
            fact_refs.append(fact_ref)
            if fact.get("equivalent_min") is None or fact.get("equivalent_max") is None:
                unresolved = True
                continue
            low = float(fact["equivalent_min"])
            high = float(fact["equivalent_max"])
            if low < 0 or high < low:
                raise ValueError(f"P人数区间非法：{fact_ref}")
            minimum += low
            maximum += high
    center = 0.0 if maximum == 0 else sqrt(max(minimum, 1e-9) * maximum)
    return {
        "P": None if unresolved else _p_grade(center),
        "equivalent_min": round(minimum, 2),
        "equivalent_max": round(maximum, 2),
        "center_equivalent": round(center, 2),
        "fact_refs": fact_refs,
        "casualty_group_refs": sorted(groups),
        "rollup_method": "DEDUPED_EQUIVALENT_RANGE_GEOMETRIC_CENTER",
        "unknown_input_present": unresolved,
    }


def _parent_axis_adjudication(
    cycle: Mapping[str, Any], section: str, axis: str, fact_refs: set[str],
    *, maximum: int = 5,
) -> dict[str, Any]:
    adjudication = deepcopy(dict(((cycle.get(section) or {}).get(axis) or {})))
    _source_refs(adjudication, f"父级{axis}裁决")
    grade = _grade(adjudication.get("grade"), axis, maximum=maximum)
    if grade is None:
        raise ValueError(f"父级{axis}裁决不得UNKNOWN")
    supporting = {str(ref) for ref in adjudication.get("supporting_fact_refs") or ()}
    if not supporting or not supporting <= fact_refs:
        raise ValueError(f"父级{axis}裁决缺少可解析supporting_fact_refs")
    if not adjudication.get("basis") or not adjudication.get("gate_evidence"):
        raise ValueError(f"父级{axis}裁决缺少basis或gate_evidence")
    adjudication["grade"] = int(grade)
    lower = int(_grade(adjudication.get("lower_grade", grade), f"{axis} lower", maximum=maximum) or 0)
    upper = int(_grade(adjudication.get("upper_grade", grade), f"{axis} upper", maximum=maximum) or 0)
    if not lower <= int(grade) <= upper:
        raise ValueError(f"父级{axis}裁决不在候选边界内")
    adjudication["lower_grade"] = lower
    adjudication["upper_grade"] = upper
    adjudication["supporting_fact_refs"] = sorted(supporting)
    return adjudication


def _rollup_system_damage(
    phases: Sequence[Mapping[str, Any]], cycle: Mapping[str, Any]
) -> dict[str, Any]:
    trajectories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_fact_refs: set[str] = set()
    for phase in phases:
        for fact in phase.get("cost_facts") or ():
            if fact.get("fact_type") != "SYSTEM_DAMAGE":
                continue
            _source_refs(fact, "S事实")
            object_ref = str(fact.get("affected_system_ref") or "")
            if not object_ref:
                raise ValueError("S事实缺少affected_system_ref")
            fact_ref = str(fact.get("fact_ref") or "")
            grades = {
                field: _grade(fact.get(field), "S", maximum=7)
                for field in (
                    "gross_damage_grade",
                    "flow_disruption_grade",
                    "terminal_residual_grade",
                )
            }
            if any(value is None for value in grades.values()):
                raise ValueError(f"S事实三组件不得UNKNOWN：{fact_ref}")
            all_fact_refs.add(fact_ref)
            trajectories[object_ref].append({
                "phase_ref": str(phase["phase_ref"]),
                "start": str(phase["start"]),
                "end": str(phase["end"]),
                "fact_ref": fact_ref,
                **{key: int(value) for key, value in grades.items()},
            })
    if not all_fact_refs:
        zero = deepcopy(dict(cycle.get("system_zero_adjudication") or {}))
        if zero:
            if zero.get("status") != "NO_SYSTEM_DAMAGE_BRIDGE_FACT":
                raise ValueError("S0裁决状态非法")
            _source_refs(zero, "S0裁决")
            if not str(zero.get("basis") or "").strip():
                raise ValueError("S0裁决缺少桥梁事实审查basis")
        return {
            "S": 0, "gross_damage_grade": 0, "flow_disruption_grade": 0,
            "terminal_residual_grade": 0, "affected_system_refs": [],
            "fact_refs": [], "damage_trajectories": {},
            "zero_adjudication": zero or None,
            "rollup_method": "DAMAGE_SPACE_UNION_DURATION_REPEAT_ADJUDICATION",
        }
    adjudication = _parent_axis_adjudication(
        cycle, "cost_axis_adjudications", "S", all_fact_refs, maximum=7
    )
    components = {
        field: int(_grade(adjudication.get(field), "S", maximum=7) or 0)
        for field in (
            "gross_damage_grade", "flow_disruption_grade",
            "terminal_residual_grade",
        )
    }
    observed_gross = max(
        item["gross_damage_grade"] for track in trajectories.values() for item in track
    )
    observed_flow = max(
        item["flow_disruption_grade"] for track in trajectories.values() for item in track
    )
    terminal_observed = max(
        sorted(track, key=lambda item: item["end"])[-1]["terminal_residual_grade"]
        for track in trajectories.values()
    )
    if components["gross_damage_grade"] < observed_gross:
        raise ValueError("父级gross_damage_grade低于已证阶段损害")
    if components["flow_disruption_grade"] < observed_flow:
        raise ValueError("父级flow_disruption_grade低于已证阶段阻断")
    if components["terminal_residual_grade"] < terminal_observed:
        raise ValueError("父级terminal_residual_grade低于各对象终点残余")
    s_floor = max(
        components["gross_damage_grade"],
        components["flow_disruption_grade"],
    )
    if adjudication["grade"] < s_floor:
        raise ValueError(
            f"父级S低于既发损害保底：S{adjudication['grade']} < S{s_floor}"
        )
    return {
        "S": adjudication["grade"], **components,
        "S_floor_from_realized_damage": s_floor,
        "affected_system_refs": sorted(trajectories),
        "fact_refs": sorted(all_fact_refs),
        "damage_trajectories": dict(trajectories),
        "parent_adjudication": adjudication,
        "rollup_method": "DAMAGE_SPACE_UNION_DURATION_REPEAT_ADJUDICATION",
    }


def _rollup_mobilization(
    phases: Sequence[Mapping[str, Any]], cycle: Mapping[str, Any]
) -> dict[str, Any]:
    by_input: dict[str, tuple[int | None, str]] = {}
    for phase in phases:
        for fact in phase.get("cost_facts") or ():
            if fact.get("fact_type") != "MOBILIZATION":
                continue
            _source_refs(fact, "M事实")
            input_ref = str(fact.get("mobilization_input_ref") or "")
            if not input_ref or input_ref in by_input:
                raise ValueError(f"M投入重复或缺失：{input_ref}")
            by_input[input_ref] = (
                _grade(fact.get("grade"), "M"),
                str(fact.get("fact_ref") or ""),
            )
    fact_refs = {item[1] for item in by_input.values()}
    if not fact_refs:
        return {"M": 0, "mobilization_input_refs": [], "fact_refs": [],
                "rollup_method": "MOBILIZATION_SCOPE_DURATION_ADJUDICATION"}
    adjudication = _parent_axis_adjudication(
        cycle, "cost_axis_adjudications", "M", fact_refs
    )
    return {
        "M": adjudication["grade"],
        "mobilization_input_refs": sorted(by_input),
        "fact_refs": sorted(item[1] for item in by_input.values()),
        "parent_adjudication": adjudication,
        "rollup_method": "MOBILIZATION_SCOPE_DURATION_ADJUDICATION",
    }


def _rollup_assets(
    phases: Sequence[Mapping[str, Any]], cycle: Mapping[str, Any]
) -> dict[str, Any]:
    by_asset: dict[str, dict[str, Any]] = {}
    for phase in phases:
        for fact in phase.get("cost_facts") or ():
            if fact.get("fact_type") != "ASSET_BURDEN":
                continue
            _source_refs(fact, "A事实")
            object_ref = str(fact.get("asset_object_ref") or "")
            if not object_ref or object_ref in by_asset:
                raise ValueError(f"A资产对象重复或缺失：{object_ref}")
            by_asset[object_ref] = dict(fact)
    component_fields = {
        "gross_commitment_grade": "gross_grade",
        "reusable_input_grade": "reusable_grade",
        "consumed_asset_grade": "consumed_grade",
        "lost_or_destroyed_asset_grade": "lost_grade",
    }
    adjudication = deepcopy(dict(cycle.get("asset_scoring_adjudication") or {}))
    _source_refs(adjudication, "A_scoring裁决")
    parent_components = dict(adjudication.get("parent_components") or {})
    result: dict[str, Any] = {}
    for output_field, input_field in component_fields.items():
        result[output_field] = _grade(
            parent_components.get(output_field), output_field
        )
        child_values = [
            _grade(fact.get(input_field), input_field)
            for fact in by_asset.values()
        ]
        known_child_values = [int(value) for value in child_values if value is not None]
        if result[output_field] is None and known_child_values:
            raise ValueError(f"父级A组件{output_field}不得抹去已知对象事实")
        if result[output_field] is not None and any(
            value > result[output_field] for value in known_child_values
        ):
            raise ValueError(f"父级A组件{output_field}低于已证对象档")
    if len(by_asset) > 1:
        multi_gate = dict(adjudication.get("multi_object_component_gate") or {})
        gate_objects = {
            str(ref) for ref in multi_gate.get("asset_object_refs") or ()
        }
        if (
            gate_objects != set(by_asset)
            or not multi_gate.get("aggregation_basis")
            or not multi_gate.get("regrade_status")
        ):
            raise ValueError("多个独立资产对象必须显式重定档父级A组件")
    gross = result["gross_commitment_grade"]
    reusable = result["reusable_input_grade"]
    consumed = result["consumed_asset_grade"]
    lost = result["lost_or_destroyed_asset_grade"]
    scoring_raw = _grade(adjudication.get("selected_grade"), "A_scoring")
    lower_raw = _grade(adjudication.get("lower_grade"), "A lower")
    upper_raw = _grade(adjudication.get("upper_grade"), "A upper")
    if any(value is None for value in (scoring_raw, lower_raw, upper_raw)):
        raise ValueError("A_scoring裁决必须给出selected/lower/upper")
    scoring, lower, upper = int(scoring_raw), int(lower_raw), int(upper_raw)
    confidence = str(adjudication.get("confidence") or "")
    supporting = {str(ref) for ref in adjudication.get("supporting_fact_refs") or ()}
    asset_fact_refs = {str(fact.get("fact_ref")) for fact in by_asset.values()}
    if not (lower <= scoring <= upper) or not confidence or not adjudication.get("basis"):
        raise ValueError("A_scoring裁决缺少有效边界、置信度或basis")
    if supporting != asset_fact_refs:
        raise ValueError("A_scoring裁决未覆盖全部资产事实")
    known_components = [value for value in (reusable, consumed, lost) if value is not None]
    if gross is not None and any(value > gross for value in known_components):
        raise ValueError("A组件不得高于gross投入边界")
    if gross is not None and upper > gross:
        raise ValueError("A_scoring上界不得高于gross投入")
    if consumed is not None and lower < consumed:
        raise ValueError("A_scoring下界不得低于已证消耗")
    if lost is not None and lower < lost:
        raise ValueError("A_scoring下界不得低于已证永久毁失")
    gross_copy = bool(
        gross
        and lost == gross
        and (int(reusable or 0) > 0 or int(consumed or 0) > 0)
    )
    if gross_copy:
        raise ValueError("gross投入整档复制为永久毁失")
    result.update(
        {
            "A_scoring": scoring,
            "A_scoring_lower": lower,
            "A_scoring_upper": upper,
            "A_scoring_confidence": confidence,
            "A_scoring_basis": adjudication["basis"],
            "A_scoring_adjudication": adjudication,
            "asset_object_refs": sorted(by_asset),
            "fact_refs": sorted(
                str(fact.get("fact_ref") or "") for fact in by_asset.values()
            ),
            "component_split_status": (
                "UNRESOLVED_REUSE_LOSS_DESTRUCTION_SPLIT"
                if any(value is None for value in (gross, reusable, consumed, lost))
                else "STRUCTURED_COMPONENT_ROLLUP"
            ),
            "gross_copied_to_permanent_loss": gross_copy,
            "rollup_method": "EXPLICIT_BOUNDED_NET_ASSET_ADJUDICATION",
        }
    )
    return result


def _validate_boundary(
    cycle: Mapping[str, Any], prior_cycles: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    boundary = deepcopy(dict(cycle.get("boundary_decision") or {}))
    _source_refs(boundary, "父周期边界")
    mode = str(boundary.get("mode") or "")
    if mode == "FIRST_CYCLE_IN_CHAIN":
        return boundary
    if mode != "SPLIT_FROM_PREVIOUS_INVESTMENT":
        raise ValueError(f"父周期边界模式非法：{mode}")
    prior_ref = str(boundary.get("prior_investment_cycle_ref") or "")
    if prior_ref not in prior_cycles:
        raise ValueError(f"拆分边界找不到前轮：{prior_ref}")
    prior_separated = bool(boundary.get("prior_force_withdrawn_or_demobilized"))
    prior_closed_with_independent_inputs = bool(
        boundary.get("prior_result_closed")
        and boundary.get("independent_force_and_logistics")
    )
    if not (
        boundary.get("new_authorization")
        and boundary.get("new_mobilization")
        and (prior_separated or prior_closed_with_independent_inputs)
    ):
        raise ValueError(
            f"{cycle['investment_cycle_ref']}缺少前轮闭合/独立军队后勤/新授权/新动员拆分证据"
        )
    return boundary


def _validate_national_scope(
    cycle: Mapping[str, Any], evaluation_subject: str,
) -> dict[str, Any] | None:
    raw = cycle.get("national_scope_adjudication")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("national_scope_adjudication必须是对象")
    adjudication = deepcopy(dict(raw))
    if adjudication.get("status") != "NATIONAL_COST_RESULT_SYMMETRY":
        raise ValueError("国家成本收益共同体裁决状态非法")
    if (
        adjudication.get("cost_community") != evaluation_subject
        or adjudication.get("benefit_community") != evaluation_subject
    ):
        raise ValueError("国家成本承担共同体与收益接收共同体不对称")
    if not str(adjudication.get("basis") or "").strip():
        raise ValueError("国家成本收益共同体裁决缺少basis")
    _source_refs(adjudication, "国家成本收益共同体裁决")
    return adjudication


def _validate_system_damage_reaudit(
    cycle: Mapping[str, Any], current_s_grade: int,
) -> dict[str, Any] | None:
    raw = cycle.get("system_damage_reaudit")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("system_damage_reaudit必须是对象")
    if current_s_grade <= 0:
        raise ValueError("S轴桥梁重审只适用于S>0样本")
    adjudication = deepcopy(dict(raw))
    status = adjudication.get("status")
    classification = adjudication.get("classification")
    if status not in SYSTEM_DAMAGE_REAUDIT_STATUSES:
        raise ValueError("S轴重审状态非法")
    if classification not in SYSTEM_DAMAGE_REAUDIT_CLASSES:
        raise ValueError("S轴重审分类非法")
    if status == "BOUNDED_PENDING" and classification != "B":
        raise ValueError("只有B类有界推定可保留待闭合状态")
    if status == "RESOLVED" and classification == "B":
        raise ValueError("B类有界推定应标记为BOUNDED_PENDING")
    if adjudication.get("current_grade") != current_s_grade:
        raise ValueError("S轴重审记录的current_grade与当前S不一致")
    if not str(adjudication.get("basis") or "").strip():
        raise ValueError("S轴重审缺少basis")
    _source_refs(adjudication, "S轴重审")
    adjudication["recall_required"] = classification in {"C", "D", "E"}
    adjudication["unresolved_cde"] = (
        adjudication["recall_required"] and status != "RESOLVED"
    )
    adjudication["bounded_b_pending"] = (
        classification == "B" and status == "BOUNDED_PENDING"
    )
    return adjudication


def _rollup_benefits(
    phases: Sequence[Mapping[str, Any]],
    accepted_claims: dict[str, list[dict[str, Any]]],
    cycle: Mapping[str, Any],
) -> tuple[dict[str, int | None], list[dict[str, Any]], int, dict[str, dict[str, Any]]]:
    claims: list[dict[str, Any]] = []
    suppressed = 0
    for phase in phases:
        for raw_claim in phase.get("benefit_facts") or ():
            claim = deepcopy(dict(raw_claim))
            _source_refs(claim, "收益事实")
            claim["benefit_claim_ref"] = benefit_claim_ref(claim)
            raw_axis_grades = claim.get("axis_grades") or {}
            axis_grades = {
                axis: (
                    _grade(raw_axis_grades[axis], axis)
                    if axis in raw_axis_grades
                    else 0
                )
                for axis in BENEFIT_AXES
            }
            if axis_grades["WR"] is not None and axis_grades["WR"] > 0:
                wr_status = claim.get("wr_evidence_status")
                if wr_status is not None and wr_status not in WR_EVIDENCE_STATUSES:
                    raise ValueError(f"WR证据状态非法：{wr_status}")
                if wr_status in {"UNKNOWN", "CONFIRMED_NONE"}:
                    raise ValueError("WR非零不得使用UNKNOWN或CONFIRMED_NONE证据状态")
                if claim.get("resource_realization_status") not in {
                    "REALIZED_AND_USABLE", "REALIZED_QUANTITY_UNRECORDED",
                }:
                    raise ValueError("WR非零必须证明资源已实现且可支配")
                if claim.get("resource_kind") in {None, "LAND_OR_ADMIN_CONTROL"}:
                    raise ValueError("土地或设治只进BCP，不得进入WR")
                if wr_status is None:
                    claim["wr_evidence_status"] = "UNKNOWN"
                    claim["wr_reaudit_status"] = "LEGACY_POSITIVE_PENDING_CLASSIFICATION"
            claim["axis_grades"] = axis_grades
            object_ref = str(claim["historical_object_ref"])
            claim["overlapping_prior_claim_refs"] = [
                old["benefit_claim_ref"]
                for old in accepted_claims[object_ref]
                if _windows_overlap(old, claim)
            ]
            duplicate = any(
                old["from_state"] == claim["from_state"]
                and old["to_state"] == claim["to_state"]
                for old in accepted_claims[object_ref]
            )
            if not duplicate and accepted_claims[object_ref]:
                previous = max(
                    accepted_claims[object_ref],
                    key=lambda old: _parse_date(old["benefit_window_end"]),
                )
                if claim["from_state"] != previous["to_state"]:
                    raise ValueError(
                        "收益状态链不连续："
                        f"{object_ref} {previous['to_state']} -> {claim['from_state']}"
                    )
            claim["consumed"] = not duplicate
            claim["dedupe_status"] = (
                "SUPPRESSED_REPEATED_STATE_TRANSITION"
                if duplicate
                else "CONSUMED_CONTINUOUS_STATE_TRANSITION"
            )
            if duplicate:
                suppressed += 1
            else:
                accepted_claims[object_ref].append(claim)
            claims.append(claim)

    axes: dict[str, int | None] = {}
    resolved_gates: dict[str, dict[str, Any]] = {}
    for axis in BENEFIT_AXES:
        candidate_refs = {
            str(claim["fact_ref"])
            for claim in claims
            if claim["consumed"] and claim["axis_grades"][axis] not in (None, 0)
        }
        if not candidate_refs:
            axes[axis] = 0
            continue
        adjudication = _parent_axis_adjudication(
            cycle, "benefit_axis_gates", axis, candidate_refs
        )
        if set(adjudication["supporting_fact_refs"]) != candidate_refs:
            raise ValueError(f"父级{axis}裁决必须显式覆盖全部非零候选事实")
        axes[axis] = adjudication["grade"]
        resolved_gates[axis] = adjudication
    return axes, claims, suppressed, resolved_gates


def _simplified_wr_adjudication(
    cycle: Mapping[str, Any], positive_claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    raw = cycle.get("wr_simplified_adjudication")
    if raw is None:
        return None
    adjudication = deepcopy(dict(raw))
    required = {"asset_base_grade", "transfer_mode", "realization_retention"}
    residual_fields = {
        "residual_resource_object_ref", "excluded_explicit_resource_object_refs",
    }
    if not required <= set(adjudication) or set(adjudication) - required - residual_fields:
        raise ValueError("WR简化裁决字段非法")
    explicit_object_refs = {
        str(claim["historical_object_ref"]) for claim in positive_claims
    }
    if positive_claims:
        if not residual_fields <= set(adjudication):
            raise ValueError("部分显式下限与简化推定互补时必须声明残余资源对象及排除对象")
        excluded = {
            str(ref) for ref in adjudication["excluded_explicit_resource_object_refs"]
        }
        residual_ref = str(adjudication["residual_resource_object_ref"] or "")
        if excluded != explicit_object_refs:
            raise ValueError("简化推定必须排除全部显式资源对象")
        if not residual_ref or residual_ref in explicit_object_refs:
            raise ValueError("同一resource_object不得同时显式与推定消费")
    elif set(adjudication) & residual_fields:
        raise ValueError("无显式下限时不得伪造残余资源对象排除表")
    asset_raw = adjudication["asset_base_grade"]
    if isinstance(asset_raw, Mapping):
        asset_lower = int(asset_raw.get("lower"))
        asset_upper = int(asset_raw.get("upper"))
    else:
        asset_lower = asset_upper = int(asset_raw)
    if not 0 <= asset_lower <= asset_upper <= 5:
        raise ValueError("WR简化裁决asset_base_grade越界")
    transfer_mode = str(adjudication["transfer_mode"])
    retention = str(adjudication["realization_retention"])
    if transfer_mode not in WR_SIMPLIFIED_TRANSFER_MODES:
        raise ValueError("WR简化裁决transfer_mode非法")
    if retention not in WR_SIMPLIFIED_RETENTION:
        raise ValueError("WR简化裁决realization_retention非法")
    if str(cycle.get("event_type")) == "INTERNAL_RESTORATION" and transfer_mode not in {
        "NONE_OR_DESTROYED", "ROUT_WITH_ASSETS_ESCAPED",
    }:
        explicit_net_new = any(
            claim.get("resource_kind") not in {None, "LAND_OR_ADMIN_CONTROL"}
            and int(claim["axis_grades"]["WR"] or 0) > 0
            for claim in positive_claims
        )
        if not explicit_net_new:
            raise ValueError("内战平乱同一国家系统转手不得推定正WR")

    band_lower, band_upper = WR_SIMPLIFIED_TRANSFER_MODES[transfer_mode]
    if transfer_mode == "NONE_OR_DESTROYED" or retention == "LOST_RETURNED_UNUSABLE":
        lower = upper = 0
        status = "CONFIRMED_NONE"
    else:
        upper = min(band_upper, asset_upper)
        lower = min(max(band_lower, asset_lower - 2), upper)
        if retention == "PARTIAL_OR_UNCERTAIN":
            lower = max(0, lower - 1)
        status = "SIMPLIFIED_INFERRED"
    selected = (lower + upper) // 2
    return {
        "status": status,
        "selected_grade": selected,
        "lower_grade": lower,
        "upper_grade": upper,
        "selection_policy": "LOWER_MIDPOINT_FOR_SHADOW_ORDERING_ONLY",
        "asset_base_grade": {"lower": asset_lower, "upper": asset_upper},
        "transfer_mode": transfer_mode,
        "realization_retention": retention,
        "supporting_fact_refs": [str(claim["fact_ref"]) for claim in positive_claims],
        "residual_resource_object_ref": adjudication.get("residual_resource_object_ref"),
        "excluded_explicit_resource_object_refs": list(
            adjudication.get("excluded_explicit_resource_object_refs") or ()
        ),
        "pending_reaudit_fact_refs": [],
        "zero_from_source_silence_forbidden": True,
        "q_range_integration_status": "COARSE_INTERVAL_CLOSED",
        "formal_fact_freeze": False,
    }


def _wr_evidence_adjudication(
    cycle: Mapping[str, Any], claims: Sequence[Mapping[str, Any]], wr_grade: int,
) -> dict[str, Any]:
    positive_claims = [
        claim for claim in claims
        if claim["consumed"] and int(claim["axis_grades"]["WR"] or 0) > 0
    ]
    zero = deepcopy(dict(cycle.get("wr_zero_adjudication") or {}))
    zero_status = str(zero.get("status") or "UNKNOWN")
    if zero_status not in {"UNKNOWN", "CONFIRMED_NONE"}:
        raise ValueError("WR0裁决只能是UNKNOWN或CONFIRMED_NONE")
    if zero_status == "CONFIRMED_NONE" and (
        not zero.get("basis") or not zero.get("source_refs")
    ):
        raise ValueError("CONFIRMED_NONE必须有basis与source_refs")
    if positive_claims and zero_status == "CONFIRMED_NONE":
        raise ValueError("显式正WR事实与CONFIRMED_NONE不得并存")
    all_positive_explicit = bool(positive_claims) and all(
        claim.get("wr_evidence_status") == "EXPLICIT_REALIZED"
        for claim in positive_claims
    )
    wr_gate = dict((cycle.get("benefit_axis_gates") or {}).get("WR") or {})
    explicit_coverage = wr_gate.get("wr_rollup_coverage")
    if all_positive_explicit and explicit_coverage not in WR_EXPLICIT_ROLLUP_COVERAGE:
        raise ValueError("显式WR父门禁必须声明完整rollup或部分下限")
    if all_positive_explicit and explicit_coverage == "EXPLICIT_COMPLETE_ROLLUP":
        return {
            "status": "EXPLICIT_REALIZED",
            "selected_grade": wr_grade,
            "lower_grade": wr_grade,
            "upper_grade": wr_grade,
            "claim_statuses": ["EXPLICIT_REALIZED"],
            "supporting_fact_refs": [str(claim["fact_ref"]) for claim in positive_claims],
            "pending_reaudit_fact_refs": [],
            "zero_from_source_silence_forbidden": True,
            "q_range_integration_status": "CLOSED",
            "effective_source_priority": "EXPLICIT_REALIZED",
            "configured_simplified_input_present": "wr_simplified_adjudication" in cycle,
            "simplified_override_applied": False,
            "ignored_lower_priority_inputs": (
                ["wr_simplified_adjudication"]
                if "wr_simplified_adjudication" in cycle else []
            ),
            "dual_effective_adjudication": False,
            "explicit_rollup_coverage": explicit_coverage,
            "explicit_floor_grade": wr_grade,
            "simplified_complement_applied": False,
        }

    if not positive_claims and zero_status == "CONFIRMED_NONE":
        return {
            "status": "CONFIRMED_NONE",
            "selected_grade": 0,
            "lower_grade": 0,
            "upper_grade": 0,
            "claim_statuses": [],
            "supporting_fact_refs": [],
            "pending_reaudit_fact_refs": [],
            "zero_from_source_silence_forbidden": True,
            "basis": zero["basis"],
            "q_range_integration_status": "CLOSED",
            "effective_source_priority": "CONFIRMED_NONE",
            "configured_simplified_input_present": "wr_simplified_adjudication" in cycle,
            "simplified_override_applied": False,
            "ignored_lower_priority_inputs": (
                ["wr_simplified_adjudication"]
                if "wr_simplified_adjudication" in cycle else []
            ),
            "dual_effective_adjudication": False,
            "explicit_rollup_coverage": None,
            "explicit_floor_grade": None,
            "simplified_complement_applied": False,
        }

    simplified = _simplified_wr_adjudication(cycle, positive_claims)
    if simplified is not None:
        if all_positive_explicit and explicit_coverage == "EXPLICIT_PARTIAL_FLOOR":
            simplified["selected_grade"] = max(
                wr_grade, int(simplified["selected_grade"])
            )
            simplified["lower_grade"] = max(
                wr_grade, int(simplified["lower_grade"])
            )
            simplified["upper_grade"] = max(
                wr_grade, int(simplified["upper_grade"])
            )
        simplified_is_complement = (
            all_positive_explicit
            and explicit_coverage == "EXPLICIT_PARTIAL_FLOOR"
        )
        simplified.update({
            "effective_source_priority": "SIMPLIFIED_INFERRED",
            "configured_simplified_input_present": True,
            "simplified_override_applied": not simplified_is_complement,
            "ignored_lower_priority_inputs": [],
            "dual_effective_adjudication": False,
            "explicit_rollup_coverage": explicit_coverage,
            "explicit_floor_grade": wr_grade if all_positive_explicit else None,
            "simplified_complement_applied": simplified_is_complement,
        })
        return simplified

    if positive_claims:
        statuses = sorted({
            str(claim.get("wr_evidence_status") or "UNKNOWN")
            for claim in positive_claims
        })
        return {
            "status": "UNKNOWN", "selected_grade": wr_grade,
            "lower_grade": None, "upper_grade": None,
            "claim_statuses": statuses,
            "supporting_fact_refs": [str(claim["fact_ref"]) for claim in positive_claims],
            "pending_reaudit_fact_refs": [str(claim["fact_ref"]) for claim in positive_claims],
            "zero_from_source_silence_forbidden": True,
            "q_range_integration_status": "PENDING_BATCH_REAUDIT",
            "effective_source_priority": "UNKNOWN",
            "configured_simplified_input_present": False,
            "simplified_override_applied": False,
            "ignored_lower_priority_inputs": [],
            "dual_effective_adjudication": False,
            "explicit_rollup_coverage": explicit_coverage,
            "explicit_floor_grade": wr_grade if all_positive_explicit else None,
            "simplified_complement_applied": False,
        }

    return {
        "status": "UNKNOWN",
        "selected_grade": 0,
        "lower_grade": None,
        "upper_grade": None,
        "claim_statuses": [],
        "supporting_fact_refs": [],
        "pending_reaudit_fact_refs": [],
        "zero_from_source_silence_forbidden": True,
        "basis": "未见非零WR事实，但尚未证明无所得；不得由史书沉默确认WR0。",
        "q_range_integration_status": "PENDING_BATCH_REAUDIT_POINT_PRESERVED",
        "effective_source_priority": "UNKNOWN",
        "configured_simplified_input_present": False,
        "simplified_override_applied": False,
        "ignored_lower_priority_inputs": [],
        "dual_effective_adjudication": False,
        "explicit_rollup_coverage": None,
        "explicit_floor_grade": None,
        "simplified_complement_applied": False,
    }


def _q(axes: Mapping[str, int | None], a_scoring: int | None) -> int | None:
    required = ("P", "S", "M", *BENEFIT_AXES)
    if a_scoring is None or any(axes.get(axis) is None for axis in required):
        return None
    return (
        4 * (int(axes["SB"]) - int(axes["SN"]))
        + 3 * (int(axes["BCP"]) - int(axes["BCN"]))
        + 2 * int(axes["WR"])
        - p_penalty(int(axes["P"]))
        - 4 * int(axes["S"])
        - int(axes["M"])
        - a_scoring
    )


def _cross_axis_overlap_adjudication(
    cycle: Mapping[str, Any], axes: Mapping[str, int | None],
) -> dict[str, Any] | None:
    parent_ref = str(cycle.get("investment_cycle_ref") or "")
    trigger = (
        axes.get("S") is not None and int(axes["S"]) >= 3
        and (
            (axes.get("SN") is not None and int(axes["SN"]) >= 3)
            or (axes.get("BCN") is not None and int(axes["BCN"]) >= 3)
        )
    )
    raw = cycle.get("cross_axis_overlap_adjudication")
    if trigger and not isinstance(raw, Mapping):
        raise ValueError(f"负向跨轴重叠触发样本缺少父级裁决：{parent_ref}")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("cross_axis_overlap_adjudication必须是对象")

    status = str(raw.get("status") or "")
    if status not in CROSS_AXIS_OVERLAP_STATUSES:
        raise ValueError(f"负向跨轴重叠裁决状态非法：{status}")
    affected_axes = list(raw.get("affected_axes") or ())
    allowed_axes = {"P", "S", "M", "A_scoring", "SN", "BCN"}
    if (
        not affected_axes or len(affected_axes) != len(set(affected_axes))
        or any(axis not in allowed_axes for axis in affected_axes)
    ):
        raise ValueError("负向跨轴重叠裁决affected_axes缺失、重复或非法")
    basis = str(raw.get("basis") or "").strip()
    source_refs = _source_refs(raw, "负向跨轴重叠裁决")
    if not basis:
        raise ValueError("负向跨轴重叠裁决缺少basis")
    if trigger and not ({"S"} <= set(affected_axes)):
        raise ValueError("自动触发裁决必须覆盖S轴")
    if trigger and not ({"SN", "BCN"} & set(affected_axes)):
        raise ValueError("自动触发裁决必须覆盖SN或BCN")
    if status == "INDEPENDENT":
        if "独立事实增量" not in basis or any(
            axis not in basis for axis in affected_axes
        ):
            raise ValueError("INDEPENDENT必须逐轴说明超出其他轴的独立事实增量")
    match = re.search(r"修订前Q=(-?\d+)", basis)
    previous_q = int(match.group(1)) if match is not None else None
    if status == "RESCOPED":
        if "重裁" not in basis:
            raise ValueError("RESCOPED必须说明父轴或事实已经完成重裁")
        if match is None:
            raise ValueError("RESCOPED的basis必须保存修订前Q")

    manual = parent_ref in MANUAL_CROSS_AXIS_OVERLAP_REVIEW_REFS
    automatic = trigger or (
        status == "RESCOPED" and not manual
        and "S" in affected_axes and bool({"SN", "BCN"} & set(affected_axes))
    )
    return {
        "status": status,
        "affected_axes": affected_axes,
        "basis": basis,
        "source_refs": source_refs,
        "automatic_triggered": automatic,
        "manual_review": manual,
        "current_axis_triggered": trigger,
        "previous_q_contribution": previous_q,
    }


def build_cycle_settlements(cycles: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if any("parent_axes" in cycle for cycle in cycles):
        raise ValueError("parent_axes不得作为shadow输入；必须由阶段事实rollup")
    seen_phases: set[str] = set()
    seen_fact_refs: set[str] = set()
    prior_cycles: dict[str, Mapping[str, Any]] = {}
    accepted_claims: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    suppressed_claim_count = 0

    for raw_cycle in cycles:
        cycle = deepcopy(dict(raw_cycle))
        forbidden_contribution_fields = {
            "personal_contribution_factor", "personal_contribution_gate",
            "authorization_discount", "ruler_contribution_factor",
        }
        present_forbidden = forbidden_contribution_fields & set(cycle)
        if present_forbidden:
            raise ValueError(
                f"D国家口径禁止个人贡献折减字段：{sorted(present_forbidden)}"
            )
        evaluation_subject = str(cycle.get("evaluation_subject_ref") or "")
        if not evaluation_subject:
            raise ValueError("父周期缺少evaluation_subject_ref")
        national_scope = _validate_national_scope(cycle, evaluation_subject)
        parent_ref = str(cycle.get("investment_cycle_ref") or "")
        if not parent_ref or parent_ref in prior_cycles:
            raise ValueError(f"investment_cycle_ref重复或缺失：{parent_ref}")
        boundary = _validate_boundary(cycle, prior_cycles)
        phases = list(cycle.get("ordered_phases") or ())
        if not phases:
            raise ValueError(f"{parent_ref}缺少ordered phases")
        starts = [_parse_date(phase["start"]) for phase in phases]
        if starts != sorted(starts):
            raise ValueError(f"{parent_ref}阶段未按时间排序")
        for phase in phases:
            _source_refs(phase, "阶段")
            phase_ref = str(phase.get("phase_ref") or "")
            if not phase_ref or phase_ref in seen_phases:
                raise ValueError(f"阶段跨父周期重复消费：{phase_ref}")
            seen_phases.add(phase_ref)
            for fact in [
                *(phase.get("cost_facts") or ()),
                *(phase.get("benefit_facts") or ()),
            ]:
                fact_ref = str(fact.get("fact_ref") or "")
                if not fact_ref or fact_ref in seen_fact_refs:
                    raise ValueError(f"阶段事实重复或缺失：{fact_ref}")
                seen_fact_refs.add(fact_ref)
            for fact in phase.get("cost_facts") or ():
                bearer = str(
                    fact.get("burden_bearer")
                    or phase.get("cost_burden_bearer")
                    or cycle.get("default_cost_burden_bearer")
                    or ""
                )
                if bearer != evaluation_subject:
                    raise ValueError(
                        f"成本承担主体不属于评价主体：{fact['fact_ref']} {bearer}"
                    )
                fact["effective_burden_bearer"] = bearer
            for fact in phase.get("benefit_facts") or ():
                recipient = str(
                    fact.get("recipient")
                    or phase.get("benefit_recipient")
                    or cycle.get("default_benefit_recipient")
                    or ""
                )
                if recipient != evaluation_subject:
                    raise ValueError(
                        f"收益接收主体不属于评价主体：{fact['fact_ref']} {recipient}"
                    )
                fact["effective_recipient"] = recipient

        p_rollup = _rollup_personnel(phases)
        s_rollup = _rollup_system_damage(phases, cycle)
        m_rollup = _rollup_mobilization(phases, cycle)
        asset_rollup = _rollup_assets(phases, cycle)
        benefit_axes, benefit_claims, suppressed, benefit_gates = _rollup_benefits(
            phases, accepted_claims, cycle
        )
        suppressed_claim_count += suppressed
        axes: dict[str, int | None] = {
            "P": p_rollup["P"],
            "S": s_rollup["S"],
            "M": m_rollup["M"],
            **benefit_axes,
        }
        system_damage_reaudit = _validate_system_damage_reaudit(
            cycle, int(axes["S"] or 0)
        )
        wr_evidence = _wr_evidence_adjudication(
            cycle, benefit_claims, int(axes["WR"] or 0)
        )
        if wr_evidence["status"] == "UNKNOWN":
            axes["WR"] = None
        else:
            axes["WR"] = int(wr_evidence["selected_grade"])
        if axes["M"] is not None and axes["M"] < 1:
            raise ValueError(f"{parent_ref}已有国家军事投入时M必须至少为1")
        overlap_adjudication = _cross_axis_overlap_adjudication(cycle, axes)
        q_value = _q(axes, asset_rollup["A_scoring"])
        if (
            overlap_adjudication is not None
            and overlap_adjudication["status"] == "RESCOPED"
            and overlap_adjudication["previous_q_contribution"] == q_value
        ):
            raise ValueError("RESCOPED必须先完成会改变Q的父轴或事实重裁")
        if (
            overlap_adjudication is not None
            and overlap_adjudication["status"] == "UNRESOLVED"
        ):
            q_value = None
        axis_ranges = {
            axis: {
                "lower": (
                    None if axes[axis] is None else
                    int((benefit_gates.get(axis) or {}).get("lower_grade", axes[axis]))
                ),
                "upper": (
                    None if axes[axis] is None else
                    int((benefit_gates.get(axis) or {}).get("upper_grade", axes[axis]))
                ),
            }
            for axis in BENEFIT_AXES
        }
        axis_ranges["WR"] = {
            "lower": wr_evidence.get("lower_grade"),
            "upper": wr_evidence.get("upper_grade"),
        }
        s_adjudication = s_rollup.get("parent_adjudication") or {}
        axis_ranges["S"] = {
            "lower": int(s_adjudication.get("lower_grade", axes["S"])),
            "upper": int(s_adjudication.get("upper_grade", axes["S"])),
        }
        lower_axes = dict(axes)
        upper_axes = dict(axes)
        for axis in ("SB", "BCP", "WR"):
            lower_axes[axis] = axis_ranges[axis]["lower"]
            upper_axes[axis] = axis_ranges[axis]["upper"]
        for axis in ("SN", "BCN"):
            lower_axes[axis] = axis_ranges[axis]["upper"]
            upper_axes[axis] = axis_ranges[axis]["lower"]
        lower_axes["S"] = axis_ranges["S"]["upper"]
        upper_axes["S"] = axis_ranges["S"]["lower"]
        q_lower = _q(lower_axes, asset_rollup["A_scoring_upper"])
        q_upper = _q(upper_axes, asset_rollup["A_scoring_lower"])
        direction = (
            "UNKNOWN" if q_value is None else
            "POSITIVE" if q_value > 0 else
            "NEGATIVE" if q_value < 0 else "BALANCED"
        )
        candidate_direction = (
            "UNKNOWN" if q_lower is None or q_upper is None else
            "POSITIVE" if q_lower > 0 else
            "NEGATIVE" if q_upper < 0 else
            "BALANCED" if q_lower == q_upper == 0 else
            "CROSSES_ZERO"
        )
        row = {
            "sample_label": cycle.get("sample_label"),
            "ruler_name": cycle.get("ruler_name"),
            "event_type": str(cycle.get("event_type") or "UNCLASSIFIED"),
            "investment_cycle_ref": parent_ref,
            "strategic_result_chain_refs": list(
                cycle.get("strategic_result_chain_refs") or ()
            ),
            "boundary_decision": boundary,
            "national_scope_adjudication": national_scope,
            "ordered_phase_refs": [str(phase["phase_ref"]) for phase in phases],
            "ordered_phase_facts": phases,
            "rollup_mode": "PARENT_ORDERED_FACT_ROLLUP",
            "parent_axes": axes,
            "personnel_rollup": p_rollup,
            "system_damage_rollup": s_rollup,
            "system_damage_reaudit": system_damage_reaudit,
            "mobilization_rollup": m_rollup,
            "asset_components": asset_rollup,
            "benefit_claims": benefit_claims,
            "benefit_axis_gates": benefit_gates,
            "wr_evidence_adjudication": wr_evidence,
            "p_audit": deepcopy(cycle.get("p_audit") or {}),
            "axis_candidate_ranges": {
                **axis_ranges,
                "A_scoring": {
                    "lower": asset_rollup["A_scoring_lower"],
                    "upper": asset_rollup["A_scoring_upper"],
                },
            },
            "cross_axis_accumulation_mode": "WEIGHTED_AXIS_SUM_PER_PARENT",
            "cross_axis_overlap_adjudication": overlap_adjudication,
            "q_formula": FORMULA,
            "q_contribution": q_value,
            "q_candidate_range": {
                "lower": q_lower,
                "upper": q_upper,
                "boundary_driver": "EXPLICIT_AXIS_AND_A_ADJUDICATION_BOUNDS",
            },
            "net_direction": direction,
            "candidate_net_direction": candidate_direction,
            "calibration_status": "CALIBRATION_PENDING",
            "formal_score_write": False,
            "notes": list(cycle.get("notes") or ()),
        }
        rows.append(row)
        prior_cycles[parent_ref] = row

    serialized_rows = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    statistics = _build_sample_statistics(rows)
    wr_status_counts = {
        status: sum(row["wr_evidence_adjudication"]["status"] == status for row in rows)
        for status in sorted(WR_EVIDENCE_STATUSES)
    }
    wr_silent_zero_pending_refs = [
        row["investment_cycle_ref"] for row in rows
        if row["wr_evidence_adjudication"]["selected_grade"] == 0
        and row["wr_evidence_adjudication"]["status"] == "UNKNOWN"
    ]
    wr_legacy_positive_pending_refs = [
        row["investment_cycle_ref"] for row in rows
        if row["wr_evidence_adjudication"]["selected_grade"] > 0
        and row["wr_evidence_adjudication"]["status"] == "UNKNOWN"
    ]
    wr_numeric_interval_count = sum(
        row["axis_candidate_ranges"]["WR"]["lower"] is not None
        and row["axis_candidate_ranges"]["WR"]["upper"] is not None
        for row in rows
    )
    wr_source_priority_records = [
        {
            "investment_cycle_ref": row["investment_cycle_ref"],
            "effective_source_priority": row["wr_evidence_adjudication"][
                "effective_source_priority"
            ],
            "configured_simplified_input_present": row["wr_evidence_adjudication"][
                "configured_simplified_input_present"
            ],
            "simplified_override_applied": row["wr_evidence_adjudication"][
                "simplified_override_applied"
            ],
            "dual_effective_adjudication": row["wr_evidence_adjudication"][
                "dual_effective_adjudication"
            ],
            "explicit_rollup_coverage": row["wr_evidence_adjudication"][
                "explicit_rollup_coverage"
            ],
            "simplified_complement_applied": row["wr_evidence_adjudication"][
                "simplified_complement_applied"
            ],
        }
        for row in rows
    ]
    wr_source_priority_counts = {
        priority: sum(
            item["effective_source_priority"] == priority
            for item in wr_source_priority_records
        )
        for priority in (
            "EXPLICIT_REALIZED", "CONFIRMED_NONE",
            "SIMPLIFIED_INFERRED", "UNKNOWN",
        )
    }
    overlap_records = [
        {
            "investment_cycle_ref": row["investment_cycle_ref"],
            "sample_label": row["sample_label"],
            "automatic_triggered": adjudication["automatic_triggered"],
            "manual_review": adjudication["manual_review"],
            "current_axis_triggered": adjudication["current_axis_triggered"],
            "status": adjudication["status"],
            "affected_axes": adjudication["affected_axes"],
            "previous_q_contribution": adjudication["previous_q_contribution"],
            "q_contribution": row["q_contribution"],
            "q_candidate_range": row["q_candidate_range"],
            "basis": adjudication["basis"],
            "source_refs": adjudication["source_refs"],
        }
        for row in rows
        if (adjudication := row["cross_axis_overlap_adjudication"]) is not None
    ]
    overlap_status_counts = {
        status: sum(item["status"] == status for item in overlap_records)
        for status in sorted(CROSS_AXIS_OVERLAP_STATUSES)
    }
    system_damage_bridge_records = [
        {
            "investment_cycle_ref": row["investment_cycle_ref"],
            "sample_label": row["sample_label"],
            "classification": adjudication["classification"],
            "status": adjudication["status"],
            "current_grade": adjudication["current_grade"],
            "s_candidate_range": row["axis_candidate_ranges"]["S"],
            "q_contribution": row["q_contribution"],
            "q_candidate_range": row["q_candidate_range"],
            "recall_required": adjudication["recall_required"],
            "unresolved_cde": adjudication["unresolved_cde"],
            "bounded_b_pending": adjudication["bounded_b_pending"],
            "basis": adjudication["basis"],
            "source_refs": adjudication["source_refs"],
        }
        for row in rows
        if (adjudication := row["system_damage_reaudit"]) is not None
    ]
    return {
        "schema_version": "third-item-d-phase-fact-shadow-v2",
        "formal_score_write": False,
        "calibration_status": "CALIBRATION_PENDING",
        "formula": FORMULA,
        "records": rows,
        "sample_statistics": statistics,
        "shadow_contract_recommendation": {
            "axis": "BCP",
            "change": "增加control_mode及间接战略控制门禁，不新造Q轴。",
            "control_modes": {
                "DIRECT_TERRITORIAL": "直接设治、驻军接管或可持续控制空间与通道。",
                "CLIENT_BUFFER": "有实际立废或军事保证，并形成可验证的外交安全约束、通道可用性与持续窗口。",
                "NOMINAL_TRIBUTARY": "仅名义册封、一次归附或一次朝贡；BCP保持0。",
            },
            "minimum_gate_fields": [
                "control_mode", "control_object", "actual_intervention",
                "security_constraint", "corridor_usability", "persistence_window",
            ],
            "indirect_control_cap": "CLIENT_BUFFER在缺乏强持续证据时封顶BCP3；持续性有强反证时保留0—3候选。",
            "sb_bcp_separation": "SB只结算敌方威胁减少；BCP只结算本方对空间、通道或缓冲体系的支配能力增加。",
            "formal_contract_write": False,
            "WR": {
                "change": "shadow采用简化三因子粗区间；不得由史书沉默推出WR0，也不得把粗推定冻结为正式事实。",
                "evidence_statuses": {
                    "EXPLICIT_REALIZED": "明确记载本方取得、接收或可支配的资产种类、规模或使用结果。",
                    "SIMPLIFIED_INFERRED": "只读既有固定事实，以资产基盘、固定转移模式和保持状态给出粗区间。",
                    "UNKNOWN": "材料沉默或控制、去向、保持状态未闭合；不得确认为WR0。",
                    "CONFIRMED_NONE": "明确无所得，或资产未被本方控制、已毁、返还、逃散或旋即丧失，方可确认WR0。",
                },
                "explicit_rollup_coverage": {
                    "EXPLICIT_COMPLETE_ROLLUP": "显式事实覆盖父周期全部已识别主要资源对象，才可屏蔽简化推定。",
                    "EXPLICIT_PARTIAL_FLOOR": "只证明单一资源对象或最低档；保留为下限，并对不重叠的残余资源对象继续推定。",
                },
                "simplified_inference_factors": {
                    "asset_base_grade": "由敌方军队体量与持续供养、骑畜舟师军械、王庭府库、财政运输体系证明；不得只凭人口。",
                    "transfer_mode": "固定枚举区分无接收或毁失、击溃逃散、局部缴获、夺营或主力接收、完整军队或中枢转移、国家资源系统整合。",
                    "realization_retention": "本方实际接收且可支配，未旋即返还或丧失；正常供军消耗不撤销已实现WR。",
                },
                "grade_policy": "以固定转移模式的初始带宽结合asset_base缩窄；保留区间，不以点值冒充精确裁决。强资产基盘与完整转移可达WR3/4，国家资源系统持续整合才开放更高上界。",
                "destruction_boundary": "敌方资产被毁只支持SB，不进入WR；同一国家系统的土地、人口或府库转手通常仍为WR0。",
                "anti_automation": "既不以灭国自动等于高WR，也不以史料未列缴获自动等于WR0；粗推定只服务shadow校准。",
                "formal_contract_write": False,
            },
        },
        "D_business_audit": {
            "investment_cycle_count": len(rows),
            "ordered_phase_count": len(seen_phases),
            "consumed_phase_fact_count": len(seen_fact_refs),
            "duplicate_phase_consumption_count": 0,
            "duplicate_phase_fact_consumption_count": 0,
            "suppressed_repeated_state_transition_count": suppressed_claim_count,
            "consumed_cross_parent_duplicate_claim_count": 0,
            "state_chain_discontinuity_count": 0,
            "gross_copied_to_permanent_loss_count": 0,
            "unknown_q_count": sum(row["q_contribution"] is None for row in rows),
            "cross_axis_overlap_automatic_trigger_count": sum(
                item["automatic_triggered"] for item in overlap_records
            ),
            "cross_axis_overlap_remaining_trigger_count": sum(
                item["current_axis_triggered"] for item in overlap_records
            ),
            "cross_axis_overlap_manual_review_count": sum(
                item["manual_review"] for item in overlap_records
            ),
            "cross_axis_overlap_status_counts": overlap_status_counts,
            "cross_axis_overlap_records": overlap_records,
            "system_damage_bridge_recall_count": sum(
                item["recall_required"] for item in system_damage_bridge_records
            ),
            "system_damage_bridge_unresolved_cde_count": sum(
                item["unresolved_cde"] for item in system_damage_bridge_records
            ),
            "system_damage_bridge_bounded_b_pending_count": sum(
                item["bounded_b_pending"] for item in system_damage_bridge_records
            ),
            "system_damage_bridge_records": system_damage_bridge_records,
            "wr_evidence_status_counts": wr_status_counts,
            "wr_numeric_interval_count": wr_numeric_interval_count,
            "wr_unknown_count": wr_status_counts["UNKNOWN"],
            "wr_same_resource_object_priority": [
                "EXPLICIT_REALIZED", "CONFIRMED_NONE",
                "SIMPLIFIED_INFERRED", "UNKNOWN",
            ],
            "wr_cross_resource_complement_policy": (
                "EXPLICIT_PARTIAL_FLOOR可与不同resource_object的残余推定互补；"
                "同一resource_object禁止显式与推定重复结算。"
            ),
            "wr_source_priority_records": wr_source_priority_records,
            "wr_source_priority_counts": wr_source_priority_counts,
            "wr_conflicting_same_object_double_adjudication_count": sum(
                item["dual_effective_adjudication"]
                for item in wr_source_priority_records
            ),
            "wr_explicit_rollup_coverage_counts": {
                coverage: sum(
                    item["explicit_rollup_coverage"] == coverage
                    for item in wr_source_priority_records
                )
                for coverage in sorted(WR_EXPLICIT_ROLLUP_COVERAGE)
            },
            "wr_partial_floor_with_simplified_complement_count": sum(
                item["explicit_rollup_coverage"] == "EXPLICIT_PARTIAL_FLOOR"
                and item["simplified_complement_applied"]
                for item in wr_source_priority_records
            ),
            "wr_same_resource_object_double_consumption_count": 0,
            "wr_silent_zero_pending_scan_count": len(wr_silent_zero_pending_refs),
            "wr_silent_zero_pending_scan_refs": wr_silent_zero_pending_refs,
            "wr_legacy_positive_pending_classification_count": len(wr_legacy_positive_pending_refs),
            "wr_legacy_positive_pending_classification_refs": wr_legacy_positive_pending_refs,
        },
        "semantic_fingerprint": sha256(serialized_rows.encode("utf-8")).hexdigest(),
    }


def linear_q_from_formal_cycle(cycle: Mapping[str, Any]) -> int | None:
    axes = cycle.get("axes")
    if not isinstance(axes, Mapping):
        return None
    if set(axes) != set(AXIS_KEYS):
        return None
    adjudications = [axes.get(axis) for axis in AXIS_KEYS]
    if any(not isinstance(value, Mapping) for value in adjudications):
        return None
    values = [axes[axis].get("grade") for axis in AXIS_KEYS]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        return None
    return (
        4 * (int(axes["SB"]["grade"]) - int(axes["SN"]["grade"]))
        + 3 * (int(axes["BCP"]["grade"]) - int(axes["BCN"]["grade"]))
        + 2 * int(axes["WR"]["grade"])
        - p_penalty(int(axes["P"]["grade"]))
        - 4 * int(axes["S"]["grade"])
        - int(axes["M"]["grade"])
        - int(axes["A"]["grade"])
    )


def _window_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_public_cycle_linear_q_analysis(
    public_payload: Mapping[str, Any],
) -> dict[str, Any]:
    validated = validate_third_item_d_cycle_registry(public_payload)
    consumed = consumed_cycle_records(validated)
    excluded = [
        dict(record) for record in validated["records"]
        if record["semantic_status"] == "EXCLUDED"
    ]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    subject_names: dict[str, str] = {}
    subject_roster_windows: dict[str, list[Any]] = {}
    for subject in validated["subject_roster"]:
        subject_id = str(subject["subject_ruler_id"])
        subject_names[subject_id] = str(subject["ruler_name"])
        subject_roster_windows[subject_id] = deepcopy(subject.get("ruler_windows") or [])
        grouped[subject_id] = []
    for source in consumed:
        subject_id = str(source["subject_ruler_id"])
        ruler_name = str(source["ruler_name"])
        previous_name = subject_names[subject_id]
        if previous_name != ruler_name:
            raise ValueError(
                f"subject_ruler_id对应多个ruler_name：{subject_id}/"
                f"{previous_name}/{ruler_name}"
            )
        cycle = deepcopy(source)
        q_value = linear_q_from_formal_cycle(cycle)
        if q_value is None:
            raise ValueError(f"可消费周期九轴未闭合：{source['cycle_identity']}")
        cycle["q_formula"] = FORMULA
        cycle["q_contribution"] = q_value
        cycle["net_direction"] = (
            "POSITIVE" if q_value > 0 else
            "NEGATIVE" if q_value < 0 else "BALANCED"
        )
        grouped[subject_id].append(cycle)

    records: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for subject_id in sorted(grouped):
        cycles = sorted(grouped[subject_id], key=lambda row: str(row["cycle_identity"]))
        q_value = sum(int(cycle["q_contribution"]) for cycle in cycles)
        directions = Counter(str(cycle["net_direction"]) for cycle in cycles)
        windows_by_key = {
            _window_key(window): deepcopy(window)
            for window in subject_roster_windows[subject_id]
        }
        for cycle in cycles:
            windows_by_key[_window_key(cycle["ruler_window"])] = deepcopy(cycle["ruler_window"])
        windows = [windows_by_key[key] for key in sorted(windows_by_key)]
        q_mean = round(q_value / len(cycles), 4) if cycles else None
        summary = {
            "ruler_id": subject_id,
            "subject_ruler_id": subject_id,
            "ruler_name": subject_names[subject_id],
            "ruler_windows": windows,
            "Q": q_value,
            "Q_mean": q_mean,
            "T": len(cycles),
            "K": len(cycles),
            "closure_rate": 1.0,
            "positive": directions["POSITIVE"],
            "zero": directions["BALANCED"],
            "negative": directions["NEGATIVE"],
        }
        summaries.append(summary)
        records.append({
            "ruler_id": subject_id,
            "subject_ruler_id": subject_id,
            "ruler_name": subject_names[subject_id],
            "ruler_windows": windows,
            "D_portfolio_metrics": {
                "cycle_q_adjudications": cycles,
                "Q": q_value,
                "Q_mean": q_mean,
                "T": len(cycles),
                "K": len(cycles),
                "closure_rate": 1.0,
                "formula": FORMULA,
            },
        })

    return {
        "schema_version": "third-item-d-formal-linear-q-analysis-v2",
        "source_schema_version": validated["schema_version"],
        "source_path": PUBLIC_REGISTRY_PATH.as_posix(),
        "formula": FORMULA,
        "formal_score_write": True,
        "records": records,
        "ruler_summaries": summaries,
        "canonical_audit": {
            "source_record_count": len(validated["records"]),
            "consumed_cycle_count": len(consumed),
            "excluded_cycle_count": len(excluded),
            "excluded_cycle_identities": sorted(
                str(record["cycle_identity"]) for record in excluded
            ),
            "subject_count": len(records),
            "zero_cycle_subject_count": sum(1 for row in summaries if row["T"] == 0),
            "duplicate_cycle_identity_count": 0,
            "unknown_q_count": 0,
            "legacy_fallback_count": 0,
        },
    }


def build_formal_linear_q_analysis(
    public_payload: Mapping[str, Any],
) -> dict[str, Any]:
    return build_public_cycle_linear_q_analysis(public_payload)


def _render_formal_linear_q_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 军事行动成本和收益登记线性 Q 正式结算",
        "",
        f"- Formula: `{payload['formula']}`",
        f"- Source: `{payload['source_path']}`",
        f"- Consumed cycles: {payload['canonical_audit']['consumed_cycle_count']}",
        f"- Excluded cycles: {payload['canonical_audit']['excluded_cycle_count']}",
        "",
        "| Ruler | Subject ID | Q | Mean Q | Cycles | + / 0 / - |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["ruler_summaries"]:
        lines.append(
            f"| {row['ruler_name']} | `{row['subject_ruler_id']}` | {row['Q']} | "
            f"{row['Q_mean']} | {row['T']} | "
            f"{row['positive']} / {row['zero']} / {row['negative']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_third_item_d_formal_settlement(repo_root: Path) -> dict[str, Any]:
    json_path = repo_root / FORMAL_SETTLEMENT_JSON_PATH
    if not json_path.exists():
        raise FileNotFoundError(f"当前战略链D正式结算不存在：{json_path}")
    analysis = json.loads(json_path.read_text(encoding="utf-8"))
    if analysis.get("schema_id") != "emperor-v4-d-strategy-chain-formal-settlement-batch-v2":
        raise ValueError("拒绝以旧线性Q结算覆盖当前战略链D正式结算")
    for row in analysis.get("records") or ():
        grade = str(row.get("D_grade"))
        position = str(row.get("D_within_grade_position"))
        try:
            expected = D_SCORE_POINTS[grade][position]
        except KeyError as exc:
            raise ValueError(f"D点值映射未闭合：{row.get('ruler_name')} {grade}/{position}") from exc
        if row.get("D_score_points") != expected:
            raise ValueError(
                f"D正式点值与合同不一致：{row.get('ruler_name')} "
                f"{row.get('D_score_points')} != {expected}"
            )
        if row.get("D_score_status") != "DIRECT_D_SCORE_ASSIGNED":
            raise ValueError(f"D正式点值状态未闭合：{row.get('ruler_name')}")
    if not analysis.get("formal_score_write"):
        raise ValueError("D正式结算尚未开启点值写入")
    return analysis


def write_legacy_linear_q_analysis(repo_root: Path) -> dict[str, Any]:
    """显式写出旧线性Q分析；不得作为当前D正式结算入口调用。"""
    public_payload = load_third_item_d_cycle_registry(repo_root / PUBLIC_REGISTRY_PATH)
    analysis = build_public_cycle_linear_q_analysis(public_payload)
    json_path = repo_root / "eval/third_item_d_shadow/legacy-linear-q.json"
    markdown_path = json_path.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        _render_formal_linear_q_markdown(analysis), encoding="utf-8"
    )
    return analysis


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 第三项D逐阶段事实 Shadow",
        "",
        "> 仅用于父投资周期与线性Q校准；不写正式D档、40分映射、总榜或排名。",
        "",
        "| 样本 | 皇帝 | 父投资周期 | P/S/M/A_scoring | SB/SN/BCP/BCN/WR | Q候选 | 边界 |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in payload.get("records") or ():
        axes = row["parent_axes"]
        q_value = row["q_contribution"]
        q_range = row["q_candidate_range"]
        asset = row["asset_components"]
        a_text = str(asset["A_scoring"])
        if asset["A_scoring_lower"] != asset["A_scoring_upper"]:
            a_text += f"[{asset['A_scoring_lower']}—{asset['A_scoring_upper']}]"
        q_text = "UNKNOWN" if q_value is None else str(q_value)
        if q_range["lower"] != q_range["upper"]:
            q_text += f"[{q_range['lower']}—{q_range['upper']}]"
        lines.append(
            "| {sample} | {ruler} | `{ref}` | {p}/{s}/{m}/{a} | "
            "{sb}/{sn}/{bcp}/{bcn}/{wr} | {q} | {boundary} |".format(
                sample=row["sample_label"], ruler=row["ruler_name"],
                ref=row["investment_cycle_ref"], p=axes["P"], s=axes["S"],
                m=axes["M"], a=a_text,
                sb=axes["SB"], sn=axes["SN"], bcp=axes["BCP"],
                bcn=axes["BCN"], wr=(axes["WR"] if axes["WR"] is not None else "UNKNOWN"),
                q=q_text,
                boundary=row["boundary_decision"]["mode"],
            )
        )
    overlap_audit = payload["D_business_audit"]
    lines.extend([
        "", "## 负向跨轴重叠轻量门禁", "",
        f"- 自动触发并完成审查：{overlap_audit['cross_axis_overlap_automatic_trigger_count']}；"
        f"重裁后仍满足自动条件：{overlap_audit['cross_axis_overlap_remaining_trigger_count']}；"
        f"人工已知风险审查：{overlap_audit['cross_axis_overlap_manual_review_count']}。",
        "",
        "| 父周期 | 审查方式 | 状态 | 受影响轴 | 修订前Q | 当前Q/候选区间 | 裁决依据 |",
        "|---|---|---|---|---:|---:|---|",
    ])
    for item in overlap_audit["cross_axis_overlap_records"]:
        review_mode = "AUTO" if item["automatic_triggered"] else "MANUAL"
        previous = item["previous_q_contribution"]
        previous_text = "—" if previous is None else str(previous)
        current = item["q_contribution"]
        q_range = item["q_candidate_range"]
        current_text = "UNKNOWN" if current is None else str(current)
        if q_range["lower"] != q_range["upper"]:
            current_text += f"[{q_range['lower']}—{q_range['upper']}]"
        lines.append(
            f"| `{item['investment_cycle_ref']}` | {review_mode} | {item['status']} | "
            f"{','.join(item['affected_axes'])} | {previous_text} | {current_text} | "
            f"{item['basis']} |"
        )
    statistics = payload["sample_statistics"]
    lines.extend([
        "", "## 样本分布", "",
        "> 以下统计只描述当前有信息量的局部校准样本，不代表全体皇帝或全量父周期。",
        "",
        f"- 总样本数：{statistics['total_sample_count']}；数值Q闭合样本：{statistics['sample_count']}；"
        f"因必需轴UNKNOWN排除：{statistics['unknown_q_count']}。",
        f"- Q：均值{statistics['q']['mean']}，中位数{statistics['q']['median']}，Q1={statistics['q']['q1']}，Q3={statistics['q']['q3']}。",
        f"- Q下界：均值{statistics['q_lower_bound']['mean']}，中位数{statistics['q_lower_bound']['median']}，Q1={statistics['q_lower_bound']['q1']}，Q3={statistics['q_lower_bound']['q3']}。",
        f"- Q上界：均值{statistics['q_upper_bound']['mean']}，中位数{statistics['q_upper_bound']['median']}，Q1={statistics['q_upper_bound']['q1']}，Q3={statistics['q_upper_bound']['q3']}。",
        f"- 正区间/负区间/跨0：{statistics['direction_counts']['positive']}/{statistics['direction_counts']['negative']}/{statistics['direction_counts']['crosses_zero']}；占比={statistics['direction_rates']['positive']}/{statistics['direction_rates']['negative']}/{statistics['direction_rates']['crosses_zero']}。",
        f"- SB4+/BCP4+/WR4+：{statistics['high_axis_counts']['SB']}/{statistics['high_axis_counts']['BCP']}/{statistics['high_axis_counts']['WR']}。",
        "", "### 按事件类型", "",
        "| 事件类型 | 样本数 | Q均值 | Q中位数 | 正/负/零 |",
        "|---|---:|---:|---:|---:|",
    ])
    for event_type, group in statistics["by_event_type"].items():
        lines.append(
            f"| {event_type} | {group['sample_count']} | {group['q']['mean']} | "
            f"{group['q']['median']} | {group['positive_count']}/{group['negative_count']}/{group['balanced_count']} |"
        )
    for title, key in (
        ("Q最高5", "highest_q_5"),
        ("Q最低5", "lowest_q_5"),
        ("区间最宽5", "widest_interval_5"),
    ):
        lines.extend(["", f"### {title}（仅当前样本）", ""])
        for item in statistics[key]:
            q_range = item["q_candidate_range"]
            lines.append(
                f"- `{item['investment_cycle_ref']}` {item['sample_label']}（{item['ruler_name']}）："
                f"Q={item['q_contribution']}，区间={q_range['lower']}—{q_range['upper']}，"
                f"驱动轴={','.join(item['driving_axes'])}，不确定轴={','.join(item['uncertain_axes']) or '无'}。"
            )
    comparison = statistics["three_case_q_comparison"]
    lines.extend([
        "", "## 三案横向Q差异分解", "",
        "> 这里只比较当前局部样本的线性净收益差；Q点值及点值比均不得解释为军事成就倍数。",
        "",
        "| 样本 | Q候选 | SB | BCP | WR | P | S | M | A_scoring |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for sample in comparison["samples"]:
        contributions = sample["axis_contributions"]
        q_range = sample["q_candidate_range"]
        q_text = str(sample["q_contribution"])
        if q_range["lower"] != q_range["upper"]:
            q_text += f"[{q_range['lower']}—{q_range['upper']}]"
        lines.append(
            f"| {sample['sample_label']} | {q_text} | {contributions['SB']:+d} | "
            f"{contributions['BCP']:+d} | {contributions['WR']:+d} | {contributions['P']:+d} | "
            f"{contributions['S']:+d} | {contributions['M']:+d} | {contributions['A_scoring']:+d} |"
        )
    lines.append("")
    for pair in comparison["pair_differences"]:
        target = next(item for item in comparison["samples"] if item["investment_cycle_ref"] == pair["target_ref"])
        baseline = next(item for item in comparison["samples"] if item["investment_cycle_ref"] == pair["baseline_ref"])
        deltas = pair["axis_contribution_deltas"]
        nonzero = "、".join(f"{axis}{value:+d}" for axis, value in deltas.items() if value)
        lines.append(
            f"- {target['sample_label']}相对{baseline['sample_label']}：Q差={pair['q_difference']:+d}，"
            f"轴贡献差={nonzero}。{pair['interpretation']}{pair['metric_warning']}"
        )
    lines.extend([
        "", "### 吐谷浑BCP情景", "",
        "| 吐谷浑BCP | 吐谷浑Q候选 | 纳哈出Q减吐谷浑Q | 捕鱼儿海Q减吐谷浑Q |",
        "|---:|---:|---:|---:|",
    ])
    for scenario in comparison["tuyuhun_bcp_scenarios"]:
        q_range = scenario["q_candidate_range"]
        lines.append(
            f"| {scenario['BCP']} | {scenario['q_contribution']}[{q_range['lower']}—{q_range['upper']}] | "
            f"{scenario['difference_from_nahacu']:+d} | {scenario['difference_from_buyur']:+d} |"
        )
    three_case_rows = {
        row["investment_cycle_ref"]: row for row in payload.get("records") or ()
        if row["investment_cycle_ref"] in {
            "CAMPAIGN-TANG-TUYUHUN-634-635",
            "MING-NORTHERN-YUAN-NAHACU-1387",
            "MING-NORTHERN-YUAN-BUYUR-KARAKORUM-1388",
        }
    }
    if three_case_rows:
        lines.extend(["", "### 三案事实与父级重算锚点", ""])
    tuyuhun = three_case_rows.get("CAMPAIGN-TANG-TUYUHUN-634-635")
    if tuyuhun:
        lines.append(
            f"- 吐谷浑BCP候选：{'；'.join(tuyuhun['notes'])} "
            f"WR4证据状态={tuyuhun['wr_evidence_adjudication']['status']}："
            "二十余万多种牲畜明确缴获且用于补充军食；与捕鱼儿海—和林同量纲横裁，不依赖结构推定或旧示例冻结。"
        )
    nahacu = three_case_rows.get("MING-NORTHERN-YUAN-NAHACU-1387")
    if nahacu:
        p_fact = nahacu["ordered_phase_facts"][0]["cost_facts"][0]
        lines.append(
            f"- 纳哈出P3：{p_fact['basis']} BCP3：{nahacu['benefit_axis_gates']['BCP']['basis']} "
            f"WR4：{nahacu['benefit_axis_gates']['WR']['basis']} "
            f"证据状态={nahacu['wr_evidence_adjudication']['status']}。"
        )
    buyur = three_case_rows.get("MING-NORTHERN-YUAN-BUYUR-KARAKORUM-1388")
    if buyur:
        lines.append(
            f"- 捕鱼儿海—和林阶段：{' → '.join(buyur['ordered_phase_refs'])}。"
            f"父P按{buyur['personnel_rollup']['rollup_method']}去重，父M："
            f"{buyur['mobilization_rollup']['parent_adjudication']['basis']} "
            f"父A：{buyur['asset_components']['A_scoring_basis']} "
            f"WR4：{buyur['benefit_axis_gates']['WR']['basis']} "
            f"证据状态={buyur['wr_evidence_adjudication']['status']}。"
        )
    recommendation = payload["shadow_contract_recommendation"]
    lines.extend([
        "", "## BCP最小合同修订建议（仅shadow）", "",
        f"- SB/BCP分离：{recommendation['sb_bcp_separation']}",
        f"- 修订方式：{recommendation['change']}",
    ])
    for mode, description in recommendation["control_modes"].items():
        lines.append(f"- `{mode}`：{description}")
    lines.extend([
        f"- 最小门禁字段：{', '.join(recommendation['minimum_gate_fields'])}。",
        f"- 间接控制上限：{recommendation['indirect_control_cap']}",
        "- 本建议不修改正式D合同，不写正式D结算。",
    ])
    wr_recommendation = recommendation["WR"]
    audit = payload["D_business_audit"]
    lines.extend([
        "", "## WR最小合同修订建议（仅shadow）", "",
        f"- 修订方式：{wr_recommendation['change']}",
    ])
    for status, description in wr_recommendation["evidence_statuses"].items():
        lines.append(f"- `{status}`：{description}")
    for coverage, description in wr_recommendation["explicit_rollup_coverage"].items():
        lines.append(f"- `{coverage}`：{description}")
    lines.extend([
        f"- `asset_base_grade`：{wr_recommendation['simplified_inference_factors']['asset_base_grade']}",
        f"- `transfer_mode`：{wr_recommendation['simplified_inference_factors']['transfer_mode']}",
        f"- `realization_retention`：{wr_recommendation['simplified_inference_factors']['realization_retention']}",
        f"- 档位规则：{wr_recommendation['grade_policy']}",
        f"- 毁失边界：{wr_recommendation['destruction_boundary']}",
        f"- 双向防机械化：{wr_recommendation['anti_automation']}",
        f"- 当前状态计数：EXPLICIT={audit['wr_evidence_status_counts']['EXPLICIT_REALIZED']}；"
        f"SIMPLIFIED_INFERRED={audit['wr_evidence_status_counts']['SIMPLIFIED_INFERRED']}；"
        f"CONFIRMED_NONE={audit['wr_evidence_status_counts']['CONFIRMED_NONE']}；"
        f"UNKNOWN={audit['wr_evidence_status_counts']['UNKNOWN']}。",
        f"- 数值WR区间闭合：{audit['wr_numeric_interval_count']}/{audit['investment_cycle_count']}；"
        f"仍UNKNOWN={audit['wr_unknown_count']}。",
        "- 判优先级以`resource_object`为单位：同一对象采用`EXPLICIT_REALIZED > CONFIRMED_NONE > SIMPLIFIED_INFERRED > UNKNOWN`；不同对象允许部分显式下限与残余推定互补。",
        f"- 生效来源计数：{audit['wr_source_priority_counts']}。",
        f"- 冲突性同对象双算：{audit['wr_conflicting_same_object_double_adjudication_count']}；"
        f"合法互补共存：{audit['wr_partial_floor_with_simplified_complement_count']}。",
        f"- 显式覆盖：{audit['wr_explicit_rollup_coverage_counts']}；"
        f"部分下限与残余推定互补={audit['wr_partial_floor_with_simplified_complement_count']}；"
        f"同一资源对象重复消费={audit['wr_same_resource_object_double_consumption_count']}。",
        "- 粗推定不等于正式事实冻结；本轮不修改正式D合同、正式D结算或总榜。",
        "", "### 全部24例WR证据组合", "",
        "| 父周期 | 生效来源 | 显式覆盖 | simplified输入 | 互补推定 | asset_base | transfer_mode | retention | WR区间 |",
        "|---|---|---|---|---|---:|---|---|---:|",
    ])
    for row in payload.get("records") or ():
        wr = row["wr_evidence_adjudication"]
        asset_base = wr.get("asset_base_grade")
        if isinstance(asset_base, Mapping):
            asset_text = (
                str(asset_base["lower"])
                if asset_base["lower"] == asset_base["upper"]
                else f"{asset_base['lower']}—{asset_base['upper']}"
            )
        else:
            asset_text = "—"
        lower = wr.get("lower_grade")
        upper = wr.get("upper_grade")
        wr_text = "UNKNOWN" if lower is None or upper is None else f"{lower}—{upper}"
        lines.append(
            f"| `{row['investment_cycle_ref']}` | {wr['effective_source_priority']} | "
            f"{wr['explicit_rollup_coverage'] or '—'} | {wr['configured_simplified_input_present']} | "
            f"{wr['simplified_complement_applied']} | {asset_text} | "
            f"{wr.get('transfer_mode', '—')} | {wr.get('realization_retention', '—')} | {wr_text} |"
        )
    precision = statistics["precision_review_triggers"]
    lines.extend([
        "", "### 后续精审触发器（由records计算）", "",
        f"- 触发父周期：{precision['trigger_count']}；未来D候选边界仅用于shadow："
        + "、".join(map(str, precision["future_d_candidate_q_boundaries"])) + "。",
    ])
    for item in precision["records"]:
        lines.append(
            f"- `{item['investment_cycle_ref']}`：Q={item['q_candidate_range']['lower']}—"
            f"{item['q_candidate_range']['upper']}，WR={item['wr_candidate_range']['lower']}—"
            f"{item['wr_candidate_range']['upper']}；触发=" + "、".join(item["reasons"]) + "。"
        )
    p_audit = statistics["p_basis_audit"]
    lines.extend([
        "", f"## P轴{p_audit['record_count']}例只读根因扫描", "",
        f"- 已完成史实语义审查={p_audit['fact_semantically_reviewed_count']}；"
        f"仅形式同值={p_audit['formal_value_match_only_count']}；"
        f"UNREVIEWED={p_audit['unreviewed_count']}。形式同值不等于canonical史实正确。",
        f"- 缺专属P推定basis的阶段事实={p_audit['basis_missing_fact_count']}；"
        f"未定位同ref canonical={p_audit['canonical_value_not_located_count']}；"
        f"正式值与shadow不同但未语义复审={p_audit['formal_value_divergence_unreviewed_count']}。",
        f"- 当前已发现错误下限={p_audit['discovered_error_lower_bound_count']}/{p_audit['record_count']}；"
        "UNREVIEWED与仅形式同值样本不进入正确率分母，因此不计算错误率。",
        f"- 上游未修冲突={p_audit['upstream_unresolved_conflict_count']}；"
        "卷198当前仅由shadow覆盖，原卡错误仍保留，状态为`UPSTREAM_CONFLICT_SHADOW_OVERRIDE_ONLY`。",
        "- 触发模式：事件外模板词直接套入；仅因发生接战机械给P2；用敌方斩俘或敌军规模反推本方P；stage与terminal未说明地倒挂；只数具名死亡而抹掉失载总量推定。",
        "- 后续定向扫描：只扫描命中上述模式或stage/terminal倒挂的P_inference，不扩成全库重算；先核actual_process，再核本方损害后效与canonical父周期。",
        "", "| 父周期 | shadow P | 审查状态 | canonical状态 | P basis |",
        "|---|---:|---|---|---|",
    ])
    for item in p_audit["records"]:
        basis = "；".join(text for text in item["basis_texts"] if text) or "—"
        lines.append(
            f"| `{item['investment_cycle_ref']}` | P{item['parent_p_grade']} | "
            f"{item['review_status']} | {item['canonical_status']} | {basis} |"
        )
    s_bridge_records = audit["system_damage_bridge_records"]
    lines.extend([
        "", "## S轴桥梁召回轻量审计", "",
        f"- 需召回C/D/E：{audit['system_damage_bridge_recall_count']}；"
        f"未处置C/D/E：{audit['system_damage_bridge_unresolved_cde_count']}；"
        f"B类有界待闭合：{audit['system_damage_bridge_bounded_b_pending_count']}。",
        "- 审计只消费父级裁决状态与依据，不尝试由程序理解全部历史文本。",
        "", "| 父周期 | 分类/状态 | S点值/区间 | Q点值/区间 | 桥梁裁决 |",
        "|---|---|---:|---:|---|",
    ])
    for item in s_bridge_records:
        s_range = item["s_candidate_range"]
        q_range = item["q_candidate_range"]
        lines.append(
            f"| `{item['investment_cycle_ref']}` | "
            f"{item['classification']}/{item['status']} | "
            f"S{item['current_grade']} / {s_range['lower']}—{s_range['upper']} | "
            f"{item['q_contribution']} / {q_range['lower']}—{q_range['upper']} | "
            f"{item['basis']} |"
        )
    lines.extend(["", "## 重点候选门禁", ""])
    for wanted_ref in (
        "CAMPAIGN-TANG-XUEYANTUO-645-647",
        "MTJ-MING-NORTHERN-WAR-1372",
    ):
        row = next(
            (item for item in payload.get("records") or ()
             if item["investment_cycle_ref"] == wanted_ref),
            None,
        )
        if row is None:
            continue
        axes = row["parent_axes"]
        asset = row["asset_components"]
        wr_text = axes["WR"] if axes["WR"] is not None else "UNKNOWN"
        q_lower = row["q_candidate_range"]["lower"]
        q_upper = row["q_candidate_range"]["upper"]
        q_range_text = (
            "UNKNOWN" if q_lower is None or q_upper is None
            else f"{q_lower}—{q_upper}"
        )
        lines.append(
            f"- `{wanted_ref}`：P/S/M/A={axes['P']}/{axes['S']}/{axes['M']}/"
            f"{asset['A_scoring']}（A边界{asset['A_scoring_lower']}—{asset['A_scoring_upper']}，"
            f"{asset['A_scoring_confidence']}）；SB/SN/BCP/BCN/WR="
            f"{axes['SB']}/{axes['SN']}/{axes['BCP']}/{axes['BCN']}/{wr_text}；"
            f"Q候选={q_range_text}。"
        )
        for axis, gate in row["benefit_axis_gates"].items():
            if gate["grade"] >= 3:
                lines.append(
                    f"  - {axis}{gate['grade']}门禁：{gate['basis']}"
                )
    lines.extend(["", "## 父周期边界证据", ""])
    for row in payload.get("records") or ():
        boundary = row["boundary_decision"]
        lines.append(
            f"- `{row['investment_cycle_ref']}`：{boundary.get('reason')} "
            f"来源：{'；'.join(boundary.get('source_refs') or ())}"
        )
    lines.extend([
        "", "## 门禁摘要", "",
        f"- 父投资周期：{audit['investment_cycle_count']}；有序阶段：{audit['ordered_phase_count']}；阶段事实：{audit['consumed_phase_fact_count']}。",
        f"- 跨父周期已消费重复claim：{audit['consumed_cross_parent_duplicate_claim_count']}；gross整档复制为永久毁失：{audit['gross_copied_to_permanent_loss_count']}。",
        f"- Q UNKNOWN：{audit['unknown_q_count']}；D1—D5仍为`CALIBRATION_PENDING`。",
        f"- WR证据状态：{audit['wr_evidence_status_counts']}；数值区间={audit['wr_numeric_interval_count']}；"
        f"仍UNKNOWN={audit['wr_unknown_count']}。",
        f"- WR同对象冲突性双算={audit['wr_conflicting_same_object_double_adjudication_count']}；"
        f"不同对象合法互补={audit['wr_partial_floor_with_simplified_complement_count']}。",
        f"- WR生效来源：{audit['wr_source_priority_counts']}。",
        f"- WR显式覆盖：{audit['wr_explicit_rollup_coverage_counts']}；部分显式与残余推定互补="
        f"{audit['wr_partial_floor_with_simplified_complement_count']}；同对象重复="
        f"{audit['wr_same_resource_object_double_consumption_count']}。",
        "",
    ])
    return "\n".join(lines)


def write_sample_shadow(repo_root: Path) -> dict[str, Any]:
    source = repo_root / "config" / "third-item-d-shadow-samples.json"
    output_root = repo_root / "eval" / "third_item_d_shadow"
    cycles = json.loads(source.read_text(encoding="utf-8"))["cycles"]
    payload = build_cycle_settlements(cycles)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "current.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_root / "current.md").write_text(render_markdown(payload), encoding="utf-8")
    return payload
