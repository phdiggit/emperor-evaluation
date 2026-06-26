from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


FORMAL_ALGORITHM_VERSION = "i5b-formal-algorithm-v1"
FORMAL_RULE_VERSION = "i5b-g7-three-core-rule-v1"
FORMAL_SUBITEM_MAX_SCORE = Decimal("45")
FORMAL_SCORE_QUANT = Decimal("0.01")
FORMAL_GRADE_ENUM = (
    "历史极限",
    "历史顶级",
    "优秀",
    "良好",
    "合格",
    "一般",
    "较差",
    "很差",
    "极差",
)


FORMAL_GRADE_SPECS: dict[str, dict[str, Any]] = {
    "历史极限": {"min_pct": Decimal("96"), "max_pct": Decimal("98"), "max_exclusive": False},
    "历史顶级": {"min_pct": Decimal("90"), "max_pct": Decimal("95"), "max_exclusive": False},
    "优秀": {"min_pct": Decimal("80"), "max_pct": Decimal("89"), "max_exclusive": False},
    "良好": {"min_pct": Decimal("70"), "max_pct": Decimal("79"), "max_exclusive": False},
    "合格": {"min_pct": Decimal("60"), "max_pct": Decimal("69"), "max_exclusive": False},
    "一般": {"min_pct": Decimal("50"), "max_pct": Decimal("59"), "max_exclusive": False},
    "较差": {"min_pct": Decimal("40"), "max_pct": Decimal("49"), "max_exclusive": False},
    "很差": {"min_pct": Decimal("30"), "max_pct": Decimal("39"), "max_exclusive": False},
    "极差": {"min_pct": Decimal("0"), "max_pct": Decimal("30"), "max_exclusive": True},
}


AUTO_DIRECTION_TO_FORMAL_GRADE = {
    "高位强正，上探极正候选": "历史极限",
    "强正": "优秀",
    "强正受压制，不上探极正": "良好",
    "强正封顶，不上探极正": "良好",
    "中正": "合格",
    "中正受中负压制": "一般",
    "中正受强负压制": "较差",
    "中负": "很差",
    "强负": "极差",
}


FORMAL_GRADE_BAND_POSITION = {
    "高位强正，上探极正候选": "high",
    "强正": "mid",
    "强正受压制，不上探极正": "low",
    "强正封顶，不上探极正": "mid",
    "中正": "mid",
    "中正受中负压制": "low",
    "中正受强负压制": "low",
    "中负": "mid",
    "强负": "low",
}


def _score_from_pct(percent: Decimal) -> Decimal:
    return (FORMAL_SUBITEM_MAX_SCORE * percent / Decimal("100")).quantize(FORMAL_SCORE_QUANT, rounding=ROUND_HALF_UP)


def score_range_for_grade(grade: str) -> dict[str, str]:
    spec = FORMAL_GRADE_SPECS[grade]
    min_score = _score_from_pct(spec["min_pct"])
    max_score = _score_from_pct(spec["max_pct"])
    comparator = "<" if spec["max_exclusive"] else "<="
    return {
        "min_score": f"{min_score:.2f}",
        "max_score": f"{max_score:.2f}",
        "range_label": f"{min_score:.2f} <= 分值 {comparator} {max_score:.2f}"
        if spec["max_exclusive"]
        else f"{min_score:.2f}—{max_score:.2f}",
        "percent_range": f"{spec['min_pct']}%—{spec['max_pct']}%" + ("以下" if spec["max_exclusive"] else ""),
    }


def _band_position_ratio(position: str) -> Decimal:
    return {
        "high": Decimal("0.82"),
        "mid": Decimal("0.50"),
        "low": Decimal("0.22"),
    }.get(position, Decimal("0.50"))


def _adjustment_units(report: dict[str, Any]) -> Decimal:
    adjustment = Decimal("0")
    if str(report.get("confidence") or "") in {"high", "high_mid"}:
        adjustment += Decimal("0.05")
    if int(report.get("coverage_dimension_count") or 0) >= 3:
        adjustment += Decimal("0.04")
    if bool(report.get("positive_three_core_coverage")):
        adjustment += Decimal("0.04")
    if bool(report.get("negative_boundary_blocking")):
        adjustment -= Decimal("0.10")
    if str(report.get("negative_boundary_tier") or "") in {"weak_to_medium", "adjacent_item_medium_residual"}:
        adjustment -= Decimal("0.04")
    if bool(report.get("has_extreme_negative_core")):
        adjustment -= Decimal("0.08")
    return max(Decimal("-0.18"), min(Decimal("0.18"), adjustment))


def compute_formal_score_candidate(report: dict[str, Any], grade: str, band_position: str) -> str:
    spec = FORMAL_GRADE_SPECS[grade]
    min_score = _score_from_pct(spec["min_pct"])
    max_score = _score_from_pct(spec["max_pct"])
    ratio = max(Decimal("0.05"), min(Decimal("0.95"), _band_position_ratio(band_position) + _adjustment_units(report)))
    value = min_score + ((max_score - min_score) * ratio)
    return f"{value.quantize(FORMAL_SCORE_QUANT, rounding=ROUND_HALF_UP):.2f}"


def compute_formal_algorithm_result(report: dict[str, Any]) -> dict[str, Any]:
    auto_direction = str(report.get("auto_band_direction") or "")
    grade = AUTO_DIRECTION_TO_FORMAL_GRADE.get(auto_direction, "一般")
    band_position = FORMAL_GRADE_BAND_POSITION.get(auto_direction, "mid")
    score_range = score_range_for_grade(grade)
    return {
        "algorithm_version": FORMAL_ALGORITHM_VERSION,
        "rule_version": FORMAL_RULE_VERSION,
        "formal_grade": grade,
        "formal_grade_enum": list(FORMAL_GRADE_ENUM),
        "score_range_45": score_range["range_label"],
        "percent_range": score_range["percent_range"],
        "band_position": band_position,
        "formal_score_candidate_45": compute_formal_score_candidate(report, grade, band_position),
        "formal_score_value_suppressed_until_g9": True,
        "formal_ranking_suppressed_until_g9": True,
        "person_specific_override_allowed": False,
        "manual_final_grade_allowed": False,
        "manual_final_score_allowed": False,
    }


def formal_algorithm_mapping_rows() -> list[dict[str, Any]]:
    direction_rows = [
        ("高位强正，上探极正候选", "三核心覆盖且没有强负阻断，进入第五项B历史天花板候选。"),
        ("强正", "强正证据稳定但未达到历史极限门槛。"),
        ("强正受压制，不上探极正", "强正底盘存在，但直接强负核心阻断上探。"),
        ("强正封顶，不上探极正", "强正成立但被单维、上限或覆盖不足封顶。"),
        ("中正", "中等正向结构成立，未触发高位或强负压制。"),
        ("中正受中负压制", "中正基础被中负边界压制。"),
        ("中正受强负压制", "中正基础被强负核心显著压低。"),
        ("中负", "剥离相邻项后仍残留中等负压。"),
        ("强负", "直接命中表达安全、人才安全或授权可信度破坏。"),
    ]
    rows: list[dict[str, Any]] = []
    for auto_direction, entry_condition in direction_rows:
        grade = AUTO_DIRECTION_TO_FORMAL_GRADE[auto_direction]
        score_range = score_range_for_grade(grade)
        rows.append(
            {
                "band": grade,
                "entry_condition": entry_condition,
                "typical_evidence_structure": auto_direction,
                "negative_intercept_condition": "强负核心或中负升强负边界必须阻断高位上探。",
                "cross_item_split": "战功、政绩、边疆收益、统一贡献、治世光环全部外剥。",
                "direct_score_allowed": "否，G9 前不发布人物正式分值。",
                "rule_confirmation_needed": f"{FORMAL_ALGORITHM_VERSION} / {FORMAL_RULE_VERSION}",
                "relative_score_range_draft": score_range["range_label"],
            }
        )
    return rows
