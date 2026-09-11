from copy import deepcopy
from decimal import Decimal

import pytest

from emperor_v4.evaluation.third_item_a_scoring import (
    A_STATE_VALUES, attributable_value_delta, calculate_a_axis,
)


def axis(start, end, responsibility=1):
    return {
        "start_grade": start, "end_grade": end, "objective_delta": end-start,
        "attributable_delta": (end-start)*responsibility,
        "improvement_step_credits": [
            {"from_grade": g, "to_grade": g+1, "credit": responsibility}
            for g in range(start, end)
        ],
    }


@pytest.mark.parametrize("name", A_STATE_VALUES)
def test_state_value_order_responsibility_and_high_position_retention(name):
    values = A_STATE_VALUES[name]
    assert all(a < b for a, b in zip(values, values[1:]))
    assert values[0] == 0 and values[5] == 50
    assert values[3:5] == [30, 40]
    for start in range(6):
        for end in range(6):
            result = calculate_a_axis(name, axis(start, end))
            assert 0 <= result["axis_points"] <= 60
            assert result["axis_points"] == pytest.approx(
                result["non_cost_anchor_points"] + result["positive_result_credit_points"]
            )
            neutral = calculate_a_axis(name, axis(start, end, 0))
            if end > start:
                assert result["axis_points"] >= neutral["axis_points"]
            else:
                assert result["axis_points"] <= neutral["axis_points"]
    high_loss = calculate_a_axis(name, axis(5, 5))["axis_points"]-calculate_a_axis(name, axis(5, 4))["axis_points"]
    threshold_loss = calculate_a_axis(name, axis(3, 3))["axis_points"]-calculate_a_axis(name, axis(3, 2))["axis_points"]
    assert threshold_loss > high_loss
    assert calculate_a_axis(name, axis(2, 1))["axis_points"] > 0


def test_each_crossing_uses_its_own_credit_and_value():
    a = axis(1, 3)
    a["improvement_step_credits"][0]["credit"] = .25
    a["attributable_delta"] = 1.25
    assert attributable_value_delta("A2", a) == Decimal(16)
    with pytest.raises(ValueError, match="路径"):
        a["improvement_step_credits"][0]["from_grade"] = 0
        calculate_a_axis("A2", a)


def test_multi_window_excludes_intervening_changes_and_keeps_each_threshold():
    first, last = axis(1, 2), axis(4, 3, .5)
    first.update(window_ref="first", delta=1)
    last.update(window_ref="last", delta=-1)
    combined = axis(1, 3)
    combined.update(
        active_window_segments=[first, last], objective_delta=0,
        attributable_delta=.5,
        improvement_step_credits=[dict(s, window_ref="first") for s in first["improvement_step_credits"]],
    )
    assert attributable_value_delta("A1", combined) == Decimal(5)
    result = calculate_a_axis("A1", combined)
    assert result["positive_value_delta"] == 10
    assert result["negative_value_delta"] == -5
    assert result["weighted_change_value"] == 11.5
    assert result["non_cost_anchor_points"] == 16.5
    assert result["positive_result_credit_points"] == 8.4
    bad = deepcopy(combined)
    bad["active_window_segments"][1]["attributable_delta"] = -1
    with pytest.raises(ValueError, match="归责汇总"):
        calculate_a_axis("A1", bad)


def test_post_exclusion_liability_requires_explicit_disjoint_sources():
    a = axis(2, 1)
    a["attributable_delta"] = -2
    with pytest.raises(ValueError, match="责任越出"):
        calculate_a_axis("A1", a)
    a.update(
        excluded_cross_item_refs=["excluded-gain"], attribution_source_refs=["later-loss"],
        post_exclusion_liability={
            "start_grade": 3, "end_grade": 1, "attributable_delta": -2,
            "basis": "Separately adjudicated later loss", "source_refs": ["later-loss"],
        },
    )
    assert attributable_value_delta("A1", a) == Decimal(-22)
    a["post_exclusion_liability"]["source_refs"] = ["excluded-gain"]
    with pytest.raises(ValueError, match="引用"):
        calculate_a_axis("A1", a)


def test_special_credit_uses_max_and_clipping_preserves_raw_value():
    a = axis(4, 4)
    a.update(maintenance_bonus=12, ceiling_progress_bonus=0)
    result = calculate_a_axis("A1", a, structure_credit=14)
    assert result["unclamped_trajectory_value"] == 54
    low = axis(5, 0)
    result = calculate_a_axis("A1", low)
    assert result["unclamped_trajectory_value"] < 0
    assert result["axis_points"] == 0
    high = axis(0, 5)
    high["maintenance_bonus"] = 12
    assert calculate_a_axis("A1", high)["axis_points"] == 60


def test_axis_rounding_is_half_up():
    result = calculate_a_axis("A1", axis(0, 0), structure_credit=.075)
    assert result["axis_points"] == .05


@pytest.mark.parametrize("name", A_STATE_VALUES)
def test_improvement_retains_full_path_credit_and_loss_uses_its_own_weight(name):
    gain = calculate_a_axis(name, axis(0, 5))
    loss = calculate_a_axis(name, axis(5, 0))
    assert gain["weighted_change_value"] == 70
    assert loss["weighted_change_value"] == -25
    for grade in (3, 4, 5):
        assert calculate_a_axis(name, axis(grade, grade))["axis_points"] == grade*6
