from copy import deepcopy

import pytest

from emperor_v4.evaluation.third_item_current_settlement import _within_band_structure_credit


def construction_axis(start, end):
    return {
        'start_grade': start, 'end_grade': end, 'objective_delta': end-start,
        'within_band_structure_improvement': {
            'axis_scope': 'A2', 'threat_scope': 'SYSTEMIC',
            'outcome': 'NETWORK_REBUILT', 'improvement_level': 'DECISIVE',
            'attribution_credit': 1,
            'entry_structure': 'A separate frontier had isolated supply posts.',
            'handover_structure': 'Those posts form a staffed supply and relief network.',
            'attribution_basis': 'The ruler designed and sustained this network.',
            'net_improvement_basis': 'This is additional to the inherited network.',
            'level_basis': 'A key defensive network was rebuilt.',
            'deduplication_basis': 'No other component consumes this construction.',
            'parent_cycle_refs': ['synthetic-independent-network'],
            'source_refs': ['synthetic-network-evidence'],
            'restoration_only': False, 'consumed_elsewhere': False,
        },
    }


@pytest.mark.parametrize('start,end', [(3, 4), (4, 3)])
def test_cross_grade_requires_explicit_independent_result_boundary(start, end):
    axis = construction_axis(start, end)
    with pytest.raises(ValueError, match='跨档已消费'):
        _within_band_structure_credit(axis)
    axis['within_band_structure_improvement']['independent_of_cross_grade_basis'] = (
        'The state change concerns the main frontier; this separate network was not consumed.'
    )
    assert _within_band_structure_credit(axis) == _within_band_structure_credit(construction_axis(end, end))
    reused = deepcopy(axis)
    reused['within_band_structure_improvement']['consumed_elsewhere'] = True
    with pytest.raises(ValueError, match='重复计分'):
        _within_band_structure_credit(reused)


def test_fifth_grade_uses_ceiling_path():
    with pytest.raises(ValueError, match='封顶路径'):
        _within_band_structure_credit(construction_axis(5, 5))
