from copy import deepcopy

import pytest

from emperor_v4.evaluation.third_item_c_strategy_chain import (
    AXIS_FIELDS, GRADE_RANGES, _verify_grade_projection,
    _verify_inherited_system, _verify_score_fields,
)


def inherited_row(grades):
    # Independent synthetic systems exercise the contract, not ruler snapshots.
    final = min(min(grades), 3)
    surplus = sum(g - final for g in grades)
    axis_position = surplus / (2 * (5 - final))
    position = max(axis_position, 0.5)
    lower, upper = GRADE_RANGES[final]
    rate = lower + (upper - lower) * position
    return {
        **{field: f"{axis}-{grade}" for (axis, field), grade in zip(AXIS_FIELDS.items(), grades)},
        "ruler_name": "synthetic successor", "system_observation_status": "INHERITED_UNTESTED",
        "inherited_system_assessment": {
            "status": "EVIDENCE_SUPPORTED", "window_review": "NO_ACTUAL_SYSTEM_STRESS",
            "ruler_window": "later window", "baseline_window": "earlier window",
            "baseline_ruler_id": "synthetic predecessor", "baseline_source_refs": ["baseline evidence"],
            "counterevidence_review": ["reviewed limitations"], "continuity_status": "SUPPORTED_WITH_LIMITS",
            "axis_continuity": {axis: {field: "synthetic evidence" for field in
                ("baseline_basis", "continuity_basis", "source_refs", "grade_basis")} for axis in AXIS_FIELDS},
        },
        "axis_floor_grade": f"C-{min(grades)}", "raw_grade": f"C-{min(grades)}",
        "gate_cap": 3, "final_grade": f"C-{final}", "C_overall_grade": f"C-{final}",
        "C_score_rate": round(rate, 2), "C_score_points": rate / 2,
        "C_score_band_position": position, "C_score_outcome_position": 0.5,
        "C_score_band": {"lower_rate": lower, "upper_rate": upper},
    }


@pytest.mark.parametrize("grades", [(1, 1, 1), (2, 4, 3), (4, 4, 4)])
def test_inherited_system_uses_evidence_grades_and_observation_cap(grades):
    row = inherited_row(grades)
    before = deepcopy(row)
    _verify_inherited_system(row)
    _verify_grade_projection(row)
    _verify_score_fields(row)
    assert row == before  # The gate must not rewrite fact axes.


@pytest.mark.parametrize("missing", ["baseline_source_refs", "counterevidence_review", "ruler_window"])
def test_inherited_system_requires_evidence(missing):
    row = inherited_row((2, 4, 3))
    del row["inherited_system_assessment"][missing]
    with pytest.raises(ValueError):
        _verify_inherited_system(row)


def test_inherited_system_rejects_broken_continuity_and_copied_victory():
    row = inherited_row((2, 4, 3))
    row["inherited_system_assessment"]["continuity_status"] = "BROKEN"
    with pytest.raises(ValueError):
        _verify_inherited_system(row)
    row = inherited_row((2, 4, 3))
    row["major_system_success_chain_refs"] = ["predecessor war"]
    with pytest.raises(ValueError):
        _verify_inherited_system(row)


def test_missing_observation_does_not_become_zero_or_fabricated_outcome():
    with pytest.raises(ValueError):
        _verify_inherited_system({"final_grade": "C-N", "C_score_points": 0})
    row = inherited_row((2, 4, 3))
    row["C_score_outcome_position"] = 1
    with pytest.raises(ValueError):
        _verify_score_fields(row)
    row = inherited_row((2, 4, 3))
    row["C_score_within_band_adjudication"] = {"position": "HIGH"}
    with pytest.raises(ValueError):
        _verify_inherited_system(row)
