from copy import deepcopy

from emperor_v4.evaluation.prudent_score_intervals import _check_lineage_ref, _cost_delta, _declared_terminal_endpoints, _governance_score, _mutate, _needs_main_grade_review


def test_paired_terminal_endpoints_do_not_cross_grade_and_loss():
    ruling = {
        'status': 'FINAL_PRUDENT_RANGE',
        'primary_endpoint': 'C3-2/L0',
        'range': ['C3-2/L0', 'C3-3/L2'],
        'leaderboard_consumption': 'paired_endpoints_only',
    }
    assert _declared_terminal_endpoints(ruling) == ['C3-2/L0', 'C3-3/L2']


def test_terminal_combination_range_expands_only_when_declared():
    ruling = {
        'status': 'FINAL_PRUDENT_RANGE',
        'primary_endpoint': 'C2-3/L2',
        'range': ['C2-2/L0~L1', 'C2-3/L2'],
        'leaderboard_consumption': 'score_extrema_across_all_allowed_grade_loss_combinations',
    }
    assert _declared_terminal_endpoints(ruling) == [
        f'C2-{grade}/L{loss}' for grade in (2,3) for loss in (0,1,2)
    ]


def test_all_supported_below_high_labels_require_review():
    for label in ('LOW', 'low', 'MEDIUM_LOW', 'MEDIUM', 'medium', 'MEDIUM_HIGH',
                  'MEDIUM_HIGH_WINDOW_READJUDICATED', 'MEDIUM_RULE_HIGH_EVIDENCE_LIMITED',
                  '中低', '中', '中高'):
        assert _needs_main_grade_review(label)
    assert not _needs_main_grade_review('HIGH')
    assert not _needs_main_grade_review('HIGH_WINDOW_READJUDICATED')


def test_lineage_ref_accepts_a_file_with_line_or_record_fragment(tmp_path):
    (tmp_path / 'source.md').write_text('sample', encoding='utf-8')
    _check_lineage_ref(tmp_path, 'source.md:12')
    _check_lineage_ref(tmp_path, 'source.md#section')


def _synthetic_governance():
    axes = {
        axis: {'s0_band': 2, 'main_band': 2, 'end_band': 2, 'loss_review': {'grade': 'L0'}}
        for axis in ('C1', 'C2', 'C3')
    }
    axes['C2']['main_band'] = 3
    return {
        'axes': axes,
        'recovery': {
            'baseline': {axis: {'band': 2} for axis in axes},
            'terminal': {axis: {'band': 2} for axis in axes},
            'attribution': {axis: {'factor': 0} for axis in axes},
            'deterioration_attribution_by_axis': {axis: 0 for axis in axes},
        },
    }


def test_joint_terminal_change_reprices_recovery_without_changing_main_state():
    current = _synthetic_governance()
    alternate = deepcopy(current)
    _mutate(alternate, {'C2': {'end': 3}}, {'C2': 1.0})
    c4 = {'synthetic': {'destructive_amplification_penalty': 0}}
    assert alternate['axes']['C2']['main_band'] == 3
    assert alternate['recovery']['terminal']['C2']['band'] == 3
    assert round(_governance_score('synthetic', alternate, c4)
                 - _governance_score('synthetic', current, c4), 1) == 1.6


def test_cost_candidate_and_net_loss_take_one_larger_debit():
    factors = {'C5': {'HIGH': 0.7}, 'C6': {'LOW': 0.625, 'HIGH': 0.45}}
    assert _cost_delta(40, 40, 'C6', 'LOW', factors) == 0
    assert _cost_delta(40, 40, 'C6', 'HIGH', factors) == -4
