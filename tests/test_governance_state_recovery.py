import pytest

from emperor_v4.evaluation.governance_state_recovery import (
    AXES,
    clean_retired_low_valley_references,
    _terminal_endpoint_display,
    retained_recovery,
    state_score,
)


def test_retired_diagnostic_cleanup_preserves_author_names():
    assert clean_retired_low_valley_references('甲与Kung的研究') == '甲与Kung的研究'
    assert clean_retired_low_valley_references('与K合用') == '与低谷修正合用'


def test_terminal_endpoint_display_keeps_paired_losses_together():
    row = {
        'ruler_id': 'synthetic', 'main_band': 'C3-2', 'loss_grade': 'L0',
        'low_confidence_terminal_adjudication': {
            'decision_final': 'FINAL_PRUDENT_RANGE',
            'final_adjudication': {
                'status': 'FINAL_PRUDENT_RANGE', 'primary_endpoint': 'C3-2/L0',
                'allowed_endpoints': ['C3-2/L0', 'C3-3/L2'],
                'leaderboard_consumption': 'paired_endpoints_only',
            },
        },
    }
    assert _terminal_endpoint_display(row) == '仅配对：C3-2/L0、C3-3/L2'


def test_terminal_endpoint_display_compacts_only_a_complete_combination_set():
    row = {
        'ruler_id': 'synthetic', 'main_band': 'C2-2', 'loss_grade': 'L0',
        'low_confidence_terminal_adjudication': {
            'decision_final': 'FINAL_PRUDENT_RANGE',
            'final_adjudication': {
                'status': 'FINAL_PRUDENT_RANGE', 'primary_endpoint': 'C2-2/L0',
                'allowed_endpoints': [f'C2-{band}/L{loss}' for band in (2, 3) for loss in (0, 1)],
                'leaderboard_consumption': 'score_extrema_across_all_allowed_grade_loss_combinations',
            },
        },
    }
    assert _terminal_endpoint_display(row) == 'C2-2～3 × L0～L1'
    row['low_confidence_terminal_adjudication']['final_adjudication']['allowed_endpoints'].pop()
    with pytest.raises(ValueError, match='集合不完整'):
        _terminal_endpoint_display(row)


@pytest.mark.parametrize("axis,main,loss,expected", [
    ("C1", 1, "L3", 5.7),   # floor beats the proportional deduction
    ("C1", 4, "L1", 53.3),  # a non-terminal band uses its own axis table
    ("C2", 6, "L2", 32.6),  # round the final value, not the deduction
    ("C3", 6, "L0", 60.0),  # zero loss preserves the full base
])
def test_loss_formula_floor_axis_mapping_and_final_rounding(axis, main, loss, expected):
    assert state_score(axis, main, loss) == expected


def test_reject_invalid_or_retired_state_inputs():
    for args in [
        ("C1", True, "L1"),
        ("C1", 0, "L1"),
        ("C1", 7, "L1"),
        ("X", 3, "L1"),
        ("C1", 3, "K0"),
    ]:
        with pytest.raises(ValueError):
            state_score(*args)


def test_only_terminal_increment_survives_and_attribution_precedes_cap():
    start = dict.fromkeys(AXES, 1)
    end = dict.fromkeys(AXES, 3)
    full = dict.fromkeys(AXES, 1)
    assert retained_recovery(start, end, full)["positive_retained"] == 14
    assert retained_recovery(end, end, full)["positive_retained"] == 0
    end = dict.fromkeys(AXES, 6)
    assert retained_recovery(start, end, full)["positive_retained"] == 27
    assert retained_recovery(start, end, dict.fromkeys(AXES, 0.5))["positive_retained"] == 26.5
    assert retained_recovery(start, end, dict.fromkeys(AXES, 0))["positive_retained"] == 0


@pytest.mark.parametrize(
    "dimensions",
    [[], ["scope", "duration"], ["severity"], ["severity", "severity"], ["severity", "unknown"], [None]],
)
def test_l3_requires_severity_and_a_supported_extent(dimensions):
    from emperor_v4.evaluation.governance_state_recovery import _validate_loss_dimensions

    with pytest.raises(ValueError):
        _validate_loss_dimensions({"grade": "L3", "strong_dimensions": dimensions})


@pytest.mark.parametrize(
    "dimensions",
    [["severity", "scope"], ["severity", "duration"], ["severity", "scope", "duration"]],
)
def test_l3_accepts_both_contract_extent_routes(dimensions):
    from emperor_v4.evaluation.governance_state_recovery import _validate_loss_dimensions

    _validate_loss_dimensions({"grade": "L3", "strong_dimensions": dimensions})


def test_axis_specific_baseline_and_terminal_bottleneck():
    result = retained_recovery(
        {"C1": 4, "C2": 3, "C3": 2},
        {"C1": 6, "C2": 2, "C3": 6},
        {"C1": 1, "C2": 1, "C3": 0.5},
    )
    assert result["terminal_band"] == 3
    assert result["positive_retained"] <= 24.9


def test_deterioration_preserves_axis_specific_responsibility():
    from emperor_v4.evaluation.governance_state_recovery import _deterioration

    row = {
        "axes": {axis: {"s0_band": 3, "end_band": 2} for axis in AXES},
        "recovery": {"deterioration_attribution_by_axis": {"C1": 0, "C2": 0, "C3": 1}},
    }
    assert _deterioration(row) == 2.0
    row["recovery"]["deterioration_attribution_by_axis"] = {"C1": 0.25, "C2": 0, "C3": 0}
    assert _deterioration(row) == 0.8
    row["recovery"]["deterioration_attribution_by_axis"]["C1"] = True
    with pytest.raises(ValueError):
        _deterioration(row)
