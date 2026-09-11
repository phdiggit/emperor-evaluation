from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import pytest
from emperor_v4.evaluation.governance_state_recovery import AXES, FIXED_POINTS, LOSS_RATES, state_score, retained_recovery

@pytest.mark.parametrize('axis', AXES)
@pytest.mark.parametrize('main', range(1, 7))
def test_bounded_loss_formula_floor_and_monotonicity(axis, main):
    points = FIXED_POINTS[axis]
    values = [state_score(axis, main, grade) for grade in LOSS_RATES]
    assert values == sorted(values, reverse=True)
    assert all(points[0] <= v <= points[main - 1] for v in values)
    for grade, rate in LOSS_RATES.items():
        expected = max(Decimal(str(points[0])), Decimal(str(points[main - 1])) * (1 - rate))
        assert state_score(axis, main, grade) == float(expected.quantize(Decimal('.1'), rounding=ROUND_HALF_UP))

def test_round_final_score_not_the_loss_and_reject_legacy_inputs():
    # 35 * 0.93 = 32.55; rounding the 2.45 loss first would give 32.5.
    assert state_score('C2', 6, 'L2') == 32.6
    for args in [('C1', True, 'L1'), ('C1', 0, 'L1'), ('C1', 7, 'L1'), ('X', 3, 'L1'), ('C1', 3, 'K0')]:
        with pytest.raises(ValueError):
            state_score(*args)

def test_only_terminal_increment_survives_and_attribution_precedes_cap():
    start = dict.fromkeys(AXES, 1); end = dict.fromkeys(AXES, 3)
    full = dict.fromkeys(AXES, 1)
    assert retained_recovery(start, end, full)['positive_retained'] == 14
    assert retained_recovery(end, end, full)['positive_retained'] == 0
    end = dict.fromkeys(AXES, 6)
    assert retained_recovery(start, end, full)['positive_retained'] == 27
    assert retained_recovery(start, end, dict.fromkeys(AXES, .5))['positive_retained'] == 26.5
    assert retained_recovery(start, end, dict.fromkeys(AXES, 0))['positive_retained'] == 0


@pytest.mark.parametrize('dimensions', [[], ['scope', 'duration'], ['severity'], ['severity', 'severity'], ['severity', 'unknown'], [None]])
def test_l3_requires_severity_and_a_supported_extent(dimensions):
    from emperor_v4.evaluation.governance_state_recovery import _validate_loss_dimensions
    with pytest.raises(ValueError):
        _validate_loss_dimensions({'grade': 'L3', 'strong_dimensions': dimensions})


@pytest.mark.parametrize('dimensions', [['severity', 'scope'], ['severity', 'duration'], ['severity', 'scope', 'duration']])
def test_l3_accepts_both_contract_extent_routes(dimensions):
    from emperor_v4.evaluation.governance_state_recovery import _validate_loss_dimensions
    _validate_loss_dimensions({'grade': 'L3', 'strong_dimensions': dimensions})


@pytest.mark.parametrize('axis', AXES)
@pytest.mark.parametrize('grade,rate', LOSS_RATES.items())
def test_main_state_monotonicity_and_proportional_bound(axis, grade, rate):
    scores = [state_score(axis, b, grade) for b in range(1, 7)]
    assert scores == sorted(scores)
    for base, score in zip(FIXED_POINTS[axis], scores):
        assert Decimal(str(base)) - Decimal(str(score)) <= Decimal(str(base)) * rate + Decimal('.05')

def test_axis_specific_baseline_and_terminal_bottleneck():
    result = retained_recovery({'C1':4,'C2':3,'C3':2}, {'C1':6,'C2':2,'C3':6}, {'C1':1,'C2':1,'C3':.5})
    assert result['terminal_band'] == 3
    assert result['positive_retained'] <= 24.9


def test_deterioration_preserves_axis_specific_responsibility():
    from emperor_v4.evaluation.governance_state_recovery import _deterioration
    row = {'axes': {axis: {'s0_band': 3, 'end_band': 2} for axis in AXES},
           'recovery': {'deterioration_attribution_by_axis': {'C1': 0, 'C2': 0, 'C3': 1}}}
    assert _deterioration(row) == 2.0
    row['recovery']['deterioration_attribution_by_axis'] = {'C1': .25, 'C2': 0, 'C3': 0}
    assert _deterioration(row) == .8
    row['recovery']['deterioration_attribution_by_axis']['C1'] = True
    with pytest.raises(ValueError):
        _deterioration(row)


def test_current_rulings_and_formal_consumers_match():
    from emperor_v4.evaluation.governance_state_recovery import verify_governance_state_recovery_review
    assert verify_governance_state_recovery_review(Path('.'))['status'] == 'PASS'


def test_retired_k_inputs_are_not_active_governance_inputs():
    from emperor_v4.evaluation.formal_json_store import load_json

    review = load_json(Path('config/second-item/governance-state-recovery-adjudications.json'))
    assert all('diagnostic_legacy_K' not in axis for row in review['records'] for axis in row['axes'].values())
    assert 'legacy_K' not in review['review_policy']

    c4 = load_json(Path('config/second-item/c4-attribution-readjudications.json'))
    assert all(
        'K' not in c4_row and 'K_role' not in c4_row
        for row in c4['records']
        for c4_row in row['entry_matrix'].values()
    )
