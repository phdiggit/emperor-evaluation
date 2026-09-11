from copy import deepcopy

import pytest

from emperor_v4.evaluation.profile_c4 import validate_decision, verify


def decision():
    return {'applicability': {'status': 'APPLICABLE'}, 'axis_grade': 'G3',
            'position': 'MID', 'score_100': 65, 'radar_value': 65, 'axis_evidence_level': 'E2'}


def test_c4_projection_rejects_independent_score_change():
    row = decision()
    validate_decision(row)
    row['score_100'] = 66
    with pytest.raises(ValueError, match='不同值'):
        validate_decision(row)


def test_not_applicable_is_null_not_zero():
    row = decision()
    row.update(applicability={'status': 'NOT_APPLICABLE', 'basis': '无真实结构选择权'},
               axis_grade=None, position=None, score_100=None, radar_value=None)
    validate_decision(row)
    invalid = deepcopy(row)
    invalid['radar_value'] = 0
    with pytest.raises(ValueError, match='不适用'):
        validate_decision(invalid)


def test_g5_requires_documented_magnitude_review():
    row = decision()
    row.update(axis_grade='G5', position='LOW', score_100=91, radar_value=91)
    with pytest.raises(ValueError, match='架构量级'):
        validate_decision(row)


def test_current_c4_identity_lineage_and_reader_consistency():
    assert verify()['status'] == 'PASS'
