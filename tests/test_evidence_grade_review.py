from copy import deepcopy

import pytest

from emperor_v4.evaluation.evidence_grade_review import project_review


def inputs():
    third = dict(military_net_loss_grade='ML0', cost_debit_points=24.6,
                 applied_military_debit_points=24.6)
    review = dict(kind='MILITARY_NET_LOSS', baseline_grade='ML0',
                  baseline_cost_debit=24.6, candidate_grades=['ML0','ML1','ML2'],
                  basis='合成连续失败命题，候选仍须分别证明。',
                  excluded_basis='合成事实未支持更高成本或全国自毁。',
                  dependency_basis='成本不变且取高。',
                  admissibility='CONDITIONAL_REVIEW_ONLY')
    return review, third


def test_maximum_not_additive_and_no_rank_or_supported_scenario():
    review, third = inputs()
    original = deepcopy((review, third))
    result = project_review(review, third)
    assert [x['conditional_total_delta'] for x in result['score_effects']] == [0,0,-15.4]
    assert result['admissibility'] == 'CONDITIONAL_REVIEW_ONLY'
    assert not {'rank','scenario','supported_alternatives'} & result.keys()
    assert (review, third) == original


def test_stale_cost_or_grade_fails_instead_of_reusing_old_bounds():
    review, third = inputs()
    third['cost_debit_points'] = 20.4
    with pytest.raises(ValueError,match='基准'):
        project_review(review, third)


def test_wide_span_requires_evidence_and_is_never_silently_clipped():
    review, third = inputs()
    review['candidate_grades'].append('ML3')
    with pytest.raises(ValueError,match='超过两档'):
        project_review(review, third)
    review['wide_span_basis'] = '合成例中的另一路径已独立列明。'
    result = project_review(review, third)
    assert result['grade_span'] == 3
    assert result['candidate_grades'][-1] == 'ML3'


def test_missing_current_grade_or_exclusion_and_fake_admissibility_fail():
    review, third = inputs()
    review['candidate_grades']=['ML1']
    with pytest.raises(ValueError,match='遗漏当前档'):
        project_review(review, third)
    review, third=inputs()
    review['admissibility']='SUPPORTED_INTERPRETATION'
    with pytest.raises(ValueError,match='冒充'):
        project_review(review, third)


def test_linked_baseline_changes_are_not_silently_fixed():
    from emperor_v4.evaluation.evidence_grade_review import validate_baselines
    expected={'a':{'end':4},'b':{'start':4}}
    actual=deepcopy(expected);actual['b']['start']=3
    with pytest.raises(ValueError,match='联动基准'):
        validate_baselines(expected,actual)
