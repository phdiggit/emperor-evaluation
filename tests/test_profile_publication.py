from copy import deepcopy

import pytest

from emperor_v4.evaluation.profile_publication import CLOSED_NO_GRADE, validate_closed_no_grade
from emperor_v4.evaluation.profile_publication import validate_bounded_diplomatic_grade
from emperor_v4.evaluation.profile_publication import validate_final_capability_review


def final_review_record():
    return dict(axis_grade='G0', position='MID', score_100=7, radar_value=7,
                axis_evidence_level='E1', confidence='LOW', output_mode='EPISODE_TAG',
                score_status='EVIDENCE_LIMITED', adjudication_state='FORMAL_CURRENT',
                display_point_only=False, assessment_basis='NO_DEMONSTRATED_CAPABILITY',
                typical_pattern='未显示外交能力', limitations=['Bounded search scope'],
                parent_chains=[{'consumption_status': 'BACKGROUND_VALIDATION'}],
                final_capability_review=dict(actual_window='window', direct_review='direct sources',
                    indirect_review='delegated actions', exclusion_basis='internal actions excluded',
                    source_refs=['synthetic source'], conclusion='NO_DEMONSTRATED_CAPABILITY',
                    evidence_admission_scope='FULL_LIFETIME_ATTRIBUTABLE_EVENTS',
                    claim_scope='REVIEWED_EVIDENCE_ONLY'))


def test_final_capability_review_is_explicit_and_evidence_limited():
    validate_final_capability_review(final_review_record())


@pytest.mark.parametrize('change', ['confidence', 'indirect_review', 'scoring_parent', 'claim_scope', 'evidence_admission_scope'])
def test_final_capability_review_rejects_unjustified_classification(change):
    row = final_review_record()
    if change == 'confidence':
        row['confidence'] = 'HIGH'
    elif change == 'scoring_parent':
        row['parent_chains'][0]['consumption_status'] = 'SCORING_PARENT'
    else:
        row['final_capability_review'][change] = ''
    with pytest.raises(ValueError):
        validate_final_capability_review(row)


def test_empty_evidence_cannot_silently_keep_a_default_grade():
    with pytest.raises(ValueError, match='explicit final capability review'):
        validate_final_capability_review({'axis_grade': 'G3', 'parent_chains': []})


def test_bounded_diplomacy_requires_positive_evidence_of_an_external_choice():
    row = {
        'axis_evidence_level': 'E1', 'confidence': 'LOW', 'output_mode': 'EPISODE_TAG',
        'score_status': 'EVIDENCE_LIMITED', 'adjudication_state': 'FORMAL_CURRENT',
        'limitations': ['Only one observed condition'], 'position_basis': 'Limited outcome',
        'axis_relevance_check': {'scoring_parent_refs': ['synthetic']},
        'parent_chains': [{'bounded_adjudication': True, 'parent_id': 'synthetic',
                          'consumption_status': 'SCORING_PARENT',
                          'membership_relative_to_evaluated_ruler': 'EXTERNAL_TO_EVALUATED_RULER',
                          'counterparty_condition_authenticity': 'VERIFIED_EXTERNAL',
                          'source_refs': ['synthetic-source'], 'cycle_basis': 'Offer rejected',
                          'attribution_basis': 'Personal refusal', 'actual_window': 'Defined window'}],
    }
    validate_bounded_diplomatic_grade(row)
    row['parent_chains'][0]['source_refs'] = []
    with pytest.raises(ValueError, match='external decision'):
        validate_bounded_diplomatic_grade(row)


def test_bounded_diplomacy_does_not_publish_uncertainty_as_full_evidence():
    with pytest.raises(ValueError, match='evidence limits'):
        validate_bounded_diplomatic_grade({'parent_chains': [{'bounded_adjudication': True}],
                                          'axis_evidence_level': 'E1', 'confidence': 'HIGH'})
from emperor_v4.evaluation.profile_markdown import _m2_display_grade, _m2_display_radar


def closed_record():
    return dict(adjudication_state=CLOSED_NO_GRADE, axis_grade=None, position=None,
                score_100=None, radar_value=None, output_mode="NO_GRADE",
                score_status="EVIDENCE_INSUFFICIENT", display_point_only=False,
                formal_status="FORMAL_CURRENT", grade_basis="Only background is established.",
                position_basis="No position without a grade.",
                no_grade_closure=dict(review_scope="One bounded dossier.",
                                      evidence_gap="Personal authorization is not established.",
                                      reopen_condition="Locate an attributable instruction."),
                parent_chains=[dict(source_refs=["synthetic-source.md"])])


def test_closed_evidence_gap_is_not_a_zero_or_historical_grade():
    row = closed_record()
    validate_closed_no_grade(row, "M2")
    assert _m2_display_grade(row) == "无档"
    assert _m2_display_radar(row) == "—"


@pytest.mark.parametrize("field,value", [("radar_value", 0), ("score_100", 0),
    ("axis_grade", "G0"), ("position", "LOW"), ("display_point_only", True),
    ("parent_chains", []), ("no_grade_closure", {}), ("formal_status", "DRAFT")])
def test_invalid_terminal_closure_is_rejected(field, value):
    row = deepcopy(closed_record())
    row[field] = value
    with pytest.raises(ValueError):
        validate_closed_no_grade(row, "M2")


def test_other_axes_do_not_inherit_the_exception():
    with pytest.raises(ValueError):
        validate_closed_no_grade(closed_record(), "M1")
