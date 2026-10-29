"""Synthetic quality constraints; neither chain counts nor weights choose grades."""
from copy import deepcopy
import pytest
from emperor_v4.evaluation.governance_quality import ASSESSMENT_METHOD, direction_index, validate_quality_assessment
from emperor_v4.evaluation.second_item_b1_settlement import active_groups


def case(grade='G4'):
    row=dict(ruler_id='SYNTHETIC',ruler_name='合成对象',grade=grade,position='middle',
        assessment_method=ASSESSMENT_METHOD,confidence='MEDIUM',grade_origin='EVIDENCE_ADJUDICATION',
        grade_basis='有代表性的组织运行',position_basis='覆盖稳定但有明确范围限制',
        M_positive_profile=[dict(profile_id='ONE',material_id='SOURCE',lifecycle_key='SYSTEM',
            M='M2',direction='positive',evidence_use='direct',material_review_basis='来源明确实际办理，范围有限')],
        M_mixed_profile=[],M_negative_profile=[])
    row['semantic_assessment']=dict(main_state_basis=row['grade_basis'],position_basis=row['position_basis'],
        scope_and_attribution='本人负责的实际职责和阶段',counterevidence_and_recovery='同尺度反证及恢复已合看',
        material_review_basis='只按实际闭合范围采用',reliability_basis='主要责任持续可靠的事实说明',
        rare_quality_basis='相对通常可靠性更高的质量说明')
    return row


@pytest.mark.parametrize('grade',['G3','G4','G5'])
def test_quality_validation_does_not_impose_mechanism_count_or_extra_retest(grade):
    row=case(grade);before=deepcopy(row)
    validate_quality_assessment(row,'B1')
    assert row==before


@pytest.mark.parametrize('field',['scope_and_attribution','counterevidence_and_recovery','position_basis','material_review_basis'])
def test_quality_judgment_requires_explicit_evidence_boundaries(field):
    row=case();row['semantic_assessment'].pop(field)
    with pytest.raises(ValueError,match='缺少范围'):
        validate_quality_assessment(row,'B1')


def test_different_delivery_labels_do_not_allow_duplicate_direct_lifecycles():
    row=case();p=deepcopy(row['M_positive_profile'][0]);p['profile_id']='TWO'
    row['M_positive_profile'].append(p)
    with pytest.raises(ValueError,match='重复直接材料'):
        active_groups(row)


def test_missing_evidence_default_cannot_invent_positive_or_negative_achievement():
    row=case('G2');row.update(position='lower',confidence='LOW',grade_origin='MISSING_EVIDENCE_DEFAULT',
        evidence_status='INSUFFICIENT_EVIDENCE_DEFAULT')
    with pytest.raises(ValueError,match='不能虚构'):
        validate_quality_assessment(row,'B2')
    row['M_positive_profile']=[]
    validate_quality_assessment(row,'B2')
    row['position']='middle'
    with pytest.raises(ValueError,match='默认值'):
        validate_quality_assessment(row,'B2')


def test_unclosed_order_cannot_be_direct_operation():
    row=case();row['M_positive_profile'][0]['M']='M0'
    with pytest.raises(ValueError,match='未闭合材料'):
        validate_quality_assessment(row,'B1')


def test_retired_numeric_weights_cannot_sneak_back_into_quality_assessment():
    row=case();row['M_positive_profile'][0]['signed_weight']=2
    with pytest.raises(ValueError,match='仍以权重'):
        validate_quality_assessment(row,'B1')


@pytest.mark.parametrize('grade,field',[('G4','reliability_basis'),('G5','rare_quality_basis')])
def test_high_quality_claim_requires_the_relevant_explanation(grade,field):
    row=case(grade);row['semantic_assessment'].pop(field)
    with pytest.raises(ValueError,match='缺少'):
        validate_quality_assessment(row,'B1')


def test_direction_index_rounds_once_in_its_own_contract_interval():
    assert direction_index('G1','middle') == 30.0
    assert direction_index('G1','middle',scale=80) == 24.0
    assert direction_index('G2','middle') == 47.5
    assert direction_index('G2','middle',scale=80) == 38.0
