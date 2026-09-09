from copy import deepcopy

import pytest

from emperor_v4.evaluation.five_dynasties_third_item import _apply_c_within_band_position


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
