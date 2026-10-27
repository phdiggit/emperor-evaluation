from copy import deepcopy

import pytest

from emperor_v4.evaluation.profile_c2_c5_verifier import validate_active_case_links


def synthetic_row():
    return {
        'parent_chains': [{'parent_id': 'current', 'direction': 'NEGATIVE', 'intensity': 'MI2_LIFECYCLE'}],
        'counterpattern': {'positive_parent_refs': [], 'negative_parent_refs': ['current'], 'mixed_parent_refs': []},
        'representative_parent_ids': ['current'],
        'axis_evidence_level': 'E2',
        'political_conflict_scope_status': 'CONFLICTS_REVIEWED',
        'unit_groups': [{'status': 'SCORING_PARENT', 'parent_id': 'current'}],
        'non_scoring_observations': [{'parent_id': 'retired', 'basis': '仅保留旧来源定位。'}],
    }


def test_current_case_links_do_not_require_retired_contexts_to_score():
    row = synthetic_row()
    before = deepcopy(row)
    validate_active_case_links(row)
    assert row == before


@pytest.mark.parametrize('problem', ['wrong_direction', 'retired_active_reference', 'incomplete_index'])
def test_current_case_index_rejects_inconsistent_links(problem):
    row = synthetic_row()
    if problem == 'wrong_direction':
        row['parent_chains'][0]['direction'] = 'POSITIVE'
    elif problem == 'retired_active_reference':
        row['unit_groups'][0]['parent_id'] = 'retired'
    else:
        row['counterpattern']['negative_parent_refs'] = []
    with pytest.raises(AssertionError):
        validate_active_case_links(row)


def test_e3_needs_independent_sustained_or_cross_phase_material():
    row = synthetic_row()
    row['axis_evidence_level'] = 'E3'
    with pytest.raises(AssertionError, match='C5 E3'):
        validate_active_case_links(row)
    row['parent_chains'][0]['intensity'] = 'MI3_SUSTAINED_SYSTEMIC'
    with pytest.raises(AssertionError, match='C5 E3'):
        validate_active_case_links(row)
    row['parent_chains'].append({'parent_id': 'independent', 'direction': 'POSITIVE', 'intensity': 'MI2_LIFECYCLE'})
    row['counterpattern']['positive_parent_refs'] = ['independent']
    validate_active_case_links(row)
