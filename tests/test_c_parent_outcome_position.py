from copy import deepcopy

import pytest

from emperor_v4.evaluation.five_dynasties_third_item import _apply_c_within_band_position
from emperor_v4.evaluation.third_item_c_strategy_chain import _verify_score_fields


def row_with_outcomes(counts):
    return {
        'combat_delivery_grade': 'C1-2',
        'operational_sustainability_cap': 'C2-2',
        'system_reliability_cap': 'C3-2',
        'current_item_task_count': sum(counts.values()),
        'task_outcome_profile': {'return_class_counts': counts},
    }


def test_parent_outcome_quality_converges_with_known_evidence():
    row = row_with_outcomes({'PROPORTIONATE_RETURN': 1, 'UNKNOWN': 7})
    _apply_c_within_band_position(row)
    assert row['C_score_outcome_position'] == pytest.approx(0.5125)
    row['task_outcome_profile']['return_class_counts'] = {'PROPORTIONATE_RETURN': 4}
    _apply_c_within_band_position(row)
    assert row['C_score_outcome_position'] == pytest.approx(0.55)


def test_major_result_gate_counts_do_not_add_another_position_credit():
    row = row_with_outcomes({'HIGH_RETURN': 1, 'NEGATIVE_RETURN': 3})
    other = deepcopy(row)
    other['task_outcome_profile'].update(major_system_success_count=8, major_system_failure_count=1)
    _apply_c_within_band_position(row)
    _apply_c_within_band_position(other)
    assert row['C_score_outcome_position'] == other['C_score_outcome_position'] == 0.25


@pytest.mark.parametrize('scope', ['current', 'capability', 'inherited'])
def test_no_known_result_starts_at_neutral_position(scope):
    row = row_with_outcomes({'UNKNOWN': 2})
    if scope == 'capability':
        row.update(current_item_task_count=0, capability_only_parent_refs=['synthetic capability'])
    elif scope == 'inherited':
        row['system_observation_status'] = 'INHERITED_UNTESTED'
    _apply_c_within_band_position(row)
    assert row['C_score_outcome_position'] == 0.5
    assert row['C_score_band_position'] == 0.5


def test_strategy_results_override_parent_counts_and_gate_preserves_axes():
    row = row_with_outcomes({'NEGATIVE_RETURN': 8})
    row.update(combat_delivery_grade='C1-4', operational_sustainability_cap='C2-4',
               system_reliability_cap='C3-4', final_grade='C-3',
               strategy_chain_outcome_profile={'return_class_counts': {'HIGH_RETURN': 1}})
    _apply_c_within_band_position(row)
    assert row['C_score_outcome_position'] == 0.625
    assert row['C_score_axis_surplus_position'] == 0.75
    assert row['C_score_band_position'] == 0.75
    assert row['C_score_rate'] == 70.5
    assert row['combat_delivery_grade'] == 'C1-4'


def test_explicit_position_replaces_q_but_capability_never_supplies_results():
    row = row_with_outcomes({})
    row.update(current_item_task_count=0, capability_only_parent_refs=['synthetic capability'],
               C_score_within_band_adjudication={'position': 'HIGH'})
    _apply_c_within_band_position(row)
    assert row['C_score_outcome_position'] == 0.5
    assert row['C_score_band_position'] == 0.75


def test_explicit_position_and_old_rate_metadata_cannot_hide_wrong_q():
    row = row_with_outcomes({'UNKNOWN': 2})
    row.update(ruler_name='synthetic system', final_grade='C-2',
               strategy_chain_outcome_profile={'return_class_counts': {'UNKNOWN': 2}},
               C_score_within_band_adjudication={'position': 'HIGH'})
    _apply_c_within_band_position(row)
    _verify_score_fields(row, {'formal_score_rate_snapshot': 0})
    row['C_score_outcome_position'] = 0
    with pytest.raises(ValueError, match='结果质量位置'):
        _verify_score_fields(row, {'formal_score_rate_snapshot': row['C_score_rate']})
