"""Check current strategic-chain score fields without the retired calculator."""
from copy import deepcopy

import pytest

from emperor_v4.evaluation.third_item_c_strategy_chain import GRADE_RANGES, _verify_score_fields


def scored_row(counts, outcome, *, position=None, final=2, axes=(2, 2, 2)):
    position = outcome if position is None else position
    lower, upper = GRADE_RANGES[final]
    rate = lower + (upper - lower) * position
    return dict(
        ruler_name='合成体系', combat_delivery_grade=f'C1-{axes[0]}',
        operational_sustainability_cap=f'C2-{axes[1]}', system_reliability_cap=f'C3-{axes[2]}',
        final_grade=f'C-{final}', strategy_chain_outcome_profile={'return_class_counts': counts},
        C_score_outcome_position=outcome, C_score_band_position=position,
        C_score_rate=round(rate, 2), C_score_points=round(rate / 2, 1),
        C_score_band={'lower_rate': lower, 'upper_rate': upper},
    )


@pytest.mark.parametrize('counts,outcome', [
    ({'PROPORTIONATE_RETURN': 1, 'UNKNOWN': 7}, .5125),
    ({'PROPORTIONATE_RETURN': 4}, .55),
    ({'HIGH_RETURN': 1, 'NEGATIVE_RETURN': 3}, .25),
    ({'UNKNOWN': 2}, .5),
])
def test_current_quality_uses_known_chain_results_and_rejects_stale_values(counts, outcome):
    row = scored_row(counts, outcome)
    row['task_outcome_profile'] = {'return_class_counts': {'NEGATIVE_RETURN': 8},
                                  'major_system_success_count': 8}
    row['capability_only_parent_refs'] = ['synthetic-capability']
    before = deepcopy(row)
    _verify_score_fields(row)
    assert row == before
    row['C_score_outcome_position'] = outcome + .1
    with pytest.raises(ValueError, match='结果质量位置'):
        _verify_score_fields(row)


def test_axis_surplus_is_retained_after_gate_without_rewriting_axes():
    row = scored_row({'HIGH_RETURN': 1}, .625, position=.75, final=3, axes=(4, 4, 4))
    before = deepcopy(row)
    _verify_score_fields(row)
    assert row == before
    row['C_score_band_position'] = .625
    with pytest.raises(ValueError, match='战略链档内位置'):
        _verify_score_fields(row)


def test_explicit_position_does_not_replace_required_outcome_quality():
    row = scored_row({'UNKNOWN': 2}, .5, position=.75)
    row['C_score_within_band_adjudication'] = {'position': 'HIGH'}
    _verify_score_fields(row, {'formal_score_rate_snapshot': 0})
    row['C_score_outcome_position'] = 0
    with pytest.raises(ValueError, match='结果质量位置'):
        _verify_score_fields(row, {'formal_score_rate_snapshot': row['C_score_rate']})


def test_removing_wrong_window_chain_invalidates_unchanged_score_fields():
    row = scored_row({'NEGATIVE_RETURN': 2}, .25)
    _verify_score_fields(row)
    row['strategy_chain_outcome_profile']['return_class_counts'] = {'NEGATIVE_RETURN': 1}
    before = deepcopy(row)
    with pytest.raises(ValueError, match='结果质量位置'):
        _verify_score_fields(row)
    assert row == before
