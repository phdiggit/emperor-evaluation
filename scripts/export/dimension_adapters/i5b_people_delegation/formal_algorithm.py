from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from export.dimension_adapters.i5b_people_delegation.dictionary_readthrough import values_by_symbol


FORMAL_ALGORITHM_VERSION = "i5b-formal-algorithm-v1"
FORMAL_RULE_VERSION = "i5b-g7-three-core-rule-v1"
FORMAL_PUBLICATION_GATE = "G9"
FORMAL_SUBITEM_MAX_SCORE = Decimal("45")
FORMAL_SCORE_QUANT = Decimal("0.01")
_GRADE_DICTIONARY_VALUES = values_by_symbol("i5b.grade_dictionary.v1")
_DIRECTION_GRADE_MAPPING_VALUES = values_by_symbol("i5b.direction_grade_mapping.v1")
FORMAL_GRADE_ENUM = tuple(_GRADE_DICTIONARY_VALUES["FORMAL_GRADE_ENUM"])
FORMAL_GRADE_SPECS: dict[str, dict[str, Any]] = {
    str(grade): {
        "min_pct": Decimal(str(spec["min_pct"])),
        "max_pct": Decimal(str(spec["max_pct"])),
        "max_exclusive": bool(spec["max_exclusive"]),
    }
    for grade, spec in _GRADE_DICTIONARY_VALUES["FORMAL_GRADE_SPECS"].items()
}
AUTO_DIRECTION_TO_FORMAL_GRADE = dict(_DIRECTION_GRADE_MAPPING_VALUES["AUTO_DIRECTION_TO_FORMAL_GRADE"])
FORMAL_GRADE_BAND_POSITION = dict(_DIRECTION_GRADE_MAPPING_VALUES["FORMAL_GRADE_BAND_POSITION"])
_FORMAL_ALGORITHM_DISPLAY = _DIRECTION_GRADE_MAPPING_VALUES["FORMAL_ALGORITHM_DISPLAY"]
_SCORE_RANGE_TEXT = _FORMAL_ALGORITHM_DISPLAY["score_range_text"]
_FORMAL_ALGORITHM_MAPPING_ROWS = tuple(dict(row) for row in _FORMAL_ALGORITHM_DISPLAY["mapping_rows"])


def _score_from_pct(percent: Decimal) -> Decimal:
    return (FORMAL_SUBITEM_MAX_SCORE * percent / Decimal("100")).quantize(FORMAL_SCORE_QUANT, rounding=ROUND_HALF_UP)


def score_range_for_grade(grade: str) -> dict[str, str]:
    spec = FORMAL_GRADE_SPECS[grade]
    min_score = _score_from_pct(spec["min_pct"])
    max_score = _score_from_pct(spec["max_pct"])
    comparator = "<" if spec["max_exclusive"] else "<="
    percent_suffix = str(_SCORE_RANGE_TEXT["max_exclusive_percent_suffix"]) if spec["max_exclusive"] else ""
    return {
        "min_score": f"{min_score:.2f}",
        "max_score": f"{max_score:.2f}",
        "range_label": _SCORE_RANGE_TEXT["exclusive_range_label"].format(
            min_score=f"{min_score:.2f}",
            comparator=comparator,
            max_score=f"{max_score:.2f}",
        )
        if spec["max_exclusive"]
        else _SCORE_RANGE_TEXT["inclusive_range_label"].format(
            min_score=f"{min_score:.2f}",
            max_score=f"{max_score:.2f}",
        ),
        "percent_range": _SCORE_RANGE_TEXT["percent_range_label"].format(
            min_pct=spec["min_pct"],
            max_pct=spec["max_pct"],
            suffix=percent_suffix,
        ),
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
    grade = AUTO_DIRECTION_TO_FORMAL_GRADE.get(auto_direction, _FORMAL_ALGORITHM_DISPLAY["default_formal_grade"])
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


def compute_formal_publication_result(report: dict[str, Any]) -> dict[str, Any]:
    result = compute_formal_algorithm_result(report)
    return {
        **result,
        "publication_gate": FORMAL_PUBLICATION_GATE,
        "formal_score_value_45": result["formal_score_candidate_45"],
        "formal_score_value_released": True,
        "formal_ranking_released": True,
        "formal_score_value_suppressed_until_g9": False,
        "formal_ranking_suppressed_until_g9": False,
        "formal_score_value_source": "G9-approved publication of the G8 formal algorithm candidate value.",
    }


def build_formal_publication_rows(person_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for report in person_reports:
        publication = compute_formal_publication_result(report)
        rows.append(
            {
                "person": str(report.get("person") or ""),
                "auto_band_direction": str(report.get("auto_band_direction") or ""),
                "confidence": str(report.get("confidence") or ""),
                "negative_boundary_tier": str(report.get("negative_boundary_tier") or ""),
                "formal_grade": publication["formal_grade"],
                "score_range_45": publication["score_range_45"],
                "formal_score_value_45": publication["formal_score_value_45"],
                "algorithm_version": publication["algorithm_version"],
                "rule_version": publication["rule_version"],
                "publication_gate": publication["publication_gate"],
                "person_specific_override_allowed": publication["person_specific_override_allowed"],
                "manual_final_grade_allowed": publication["manual_final_grade_allowed"],
                "manual_final_score_allowed": publication["manual_final_score_allowed"],
            }
        )

    rows.sort(
        key=lambda row: (
            -Decimal(str(row["formal_score_value_45"])),
            FORMAL_GRADE_ENUM.index(str(row["formal_grade"])),
            str(row["person"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["formal_rank"] = index
        row["ranking_basis"] = "formal_score_value_45_desc_then_grade_then_person"
    return rows


def formal_algorithm_mapping_rows(*, g9_publication: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for direction_row in _FORMAL_ALGORITHM_MAPPING_ROWS:
        auto_direction = str(direction_row["auto_direction"])
        grade = AUTO_DIRECTION_TO_FORMAL_GRADE[auto_direction]
        score_range = score_range_for_grade(grade)
        rows.append(
            {
                "band": grade,
                "entry_condition": direction_row["entry_condition"],
                "typical_evidence_structure": auto_direction,
                "negative_intercept_condition": _FORMAL_ALGORITHM_DISPLAY["negative_intercept_condition"],
                "cross_item_split": _FORMAL_ALGORITHM_DISPLAY["cross_item_split"],
                "direct_score_allowed": _FORMAL_ALGORITHM_DISPLAY["direct_score_allowed_g9"]
                if g9_publication
                else _FORMAL_ALGORITHM_DISPLAY["direct_score_allowed_pre_g9"],
                "rule_confirmation_needed": f"{FORMAL_ALGORITHM_VERSION} / {FORMAL_RULE_VERSION}",
                "relative_score_range_draft": score_range["range_label"],
            }
        )
    return rows
