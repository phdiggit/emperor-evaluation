from copy import deepcopy

import pytest

from emperor_v4.evaluation.evidence_sensitivity import analyze, render, rank_assessments


def test_public_projection_only_quantifies_supported_scenarios():
    from emperor_v4.evaluation.evidence_sensitivity import public_assessment
    rows,gov,case=inputs()
    rejected=deepcopy(case); rejected.update(case_id='rejected',status='REJECTED_DIAGNOSTIC')
    analysis=analyze(rows,gov,[case,rejected])
    assessments=rank_assessments(rows,analysis,[])
    rows[0]['evidence_assessment']=assessments['a']
    rows[0]['evidence_assessment']['contract_envelope']={'score_outer_bounds':[-999,999]}
    p=public_assessment(rows[0],analysis,{'rank_envelope':{'case_scopes':{}}})
    assert [x['case_id'] for x in p['supported_alternatives']]==['synthetic']
    assert p['supported_alternatives'][0]['delta']==-22.9
    assert 'contract_envelope' not in p
    assert p['verified_score_range'] is None


def test_unquantified_dependency_is_visible_without_a_numeric_range():
    from emperor_v4.evaluation.evidence_sensitivity import public_assessment
    rows,gov,case=inputs()
    case.update(status='UNRESOLVED_EVIDENCE_GAP',changes=[])
    analysis=analyze(rows,gov,[case])
    rows[1]['evidence_assessment']=rank_assessments(rows,analysis,[])['b']
    registry={'rank_envelope':{'case_scopes':{'synthetic':{'affected':[{'ruler_id':'b'}]}}}}
    p=public_assessment(rows[1],analysis,registry)
    assert p['public_issues'][0]['question']==case['question']
    assert p['supported_alternatives']==[]
    assert p['score_status']=='SPECIFIC_EVIDENCE_GAPS'
    assert p['rank_status']=='ADOPTED_RANK'
    assert p['verified_score_range'] is None


def closure(rows, case, scope='LOCAL'):
    return dict(closure_id='synthetic-complete', scope=scope,
                ruler_ids=[r['ruler_id'] for r in rows] if scope=='JOINT_POOL' else ['a'],
                case_ids=[case['case_id']], enumeration_complete=True,
                coverage_basis='合成证据只允许这两个完整解释。',
                dependency_basis='各情景内部联动已闭合，互斥解释不叠加。',
                source_refs=['synthetic-source'],
                baseline_totals={r['ruler_id']:r['total_score'] for r in rows})


def test_score_can_vary_while_local_rank_is_proven_stable():
    rows,gov,case=inputs()
    rows[0].update(total_score=200, second_item_score=150)
    rows[1]['rank']=2
    analysis=analyze(rows,gov,[case])
    open_result=rank_assessments(rows,analysis,[])['a']
    assert open_result['rank_status']=='NOT_ESTABLISHED'
    result=rank_assessments(rows,analysis,[closure(rows,case)])['a']
    assert result['rank_status']=='LOCAL_STABLE'
    assert result['verified_rank_range']==[1,1]
    assert result['verified_score_range']==[177.1,200]


def test_joint_worlds_detect_competitor_changes_and_ties():
    rows,gov,case=inputs()
    analysis=analyze(rows,gov,[case])
    result=rank_assessments(rows,analysis,[closure(rows,case,'JOINT_POOL')])
    assert result['b']['rank_status']=='JOINT_POOL_STABLE'
    assert result['c']['verified_rank_range']==[2,3]
    assert result['a']['rank_status']=='VARIES_IN_COMPLETE_SPACE'


def test_unresolved_rejected_partial_and_stale_proofs_fail_closed():
    rows,gov,case=inputs()
    gap=deepcopy(case);gap.update(case_id='gap',status='UNRESOLVED_EVIDENCE_GAP',changes=[])
    with pytest.raises(ValueError,match='缺口'):
        rank_assessments(rows,analyze(rows,gov,[case,gap]),[closure(rows,case)])
    bad=closure(rows,case);bad['baseline_totals']['b']=99
    with pytest.raises(ValueError,match='基准'):
        rank_assessments(rows,analyze(rows,gov,[case]),[bad])
    bad=closure(rows,case,'JOINT_POOL');bad['ruler_ids']=['a','b']
    with pytest.raises(ValueError,match='全池'):
        rank_assessments(rows,analyze(rows,gov,[case]),[bad])
    case['status']='REJECTED_DIAGNOSTIC'
    with pytest.raises(ValueError,match='排除'):
        rank_assessments(rows,analyze(rows,gov,[case]),[closure(rows,case)])


def test_each_joint_case_is_a_complete_world_not_independent_extrema():
    rows,gov,case=inputs()
    second=deepcopy(case);second['case_id']='mutually-exclusive';second['ruler_id']='b'
    second['changes'][0]['ruler_id']='b'
    proof=closure(rows,case,'JOINT_POOL');proof['case_ids'].append(second['case_id'])
    result=rank_assessments(rows,analyze(rows,gov,[case,second]),[proof])
    # c rises only to 2; combining mutually exclusive changes would invent rank 1.
    assert result['c']['verified_rank_range']==[2,3]


def inputs():
    rows=[dict(ruler_id=rid,ruler_name=rid,total_score=total,rank=rank,
               first_item_raw_score=None,second_item_score=total-50,
               third_item_score=40,fourth_item_adjustment=10)
          for rid,total,rank in [('a',100,1),('b',100,1),('c',90,3)]]
    state=dict(s0_band=3,main_band=4,end_band=4,loss_review={'grade':'L0'},state_score=54.9)
    gov={r['ruler_id']:{'axes':{'C1':deepcopy(state)}} for r in rows}
    change=dict(kind='GOVERNANCE_MAIN_AND_LOSS',ruler_id='a',axis='C1',
                baseline=dict(s0_band=3,main_band=4,end_band=4,loss_grade='L0'),
                alternative=dict(main_band=3,loss_grade='L0'),
                dependency_basis='独立端点材料未变；只改变主要阶段的解释。',
                deduplication_basis='合成用例无独立低谷，不重复扣。')
    case=dict(case_id='synthetic',ruler_id='a',status='SUPPORTED_INTERPRETATION',
              question='合成主态解释',basis='独立构造的材料允许两种解释。',
              limitations='只覆盖本情景。',source_refs=['synthetic-source'],changes=[change])
    return rows,gov,case


def test_reprices_formula_and_reranks_competition_ties_without_writes():
    rows,gov,case=inputs()
    original=deepcopy((rows,gov,case))
    result=analyze(rows,gov,[case])
    scenario=result['cases'][0]['scenario']
    assert scenario['total_score']==77.1
    assert scenario['rank']==3
    assert {r['ruler_id']:r['scenario_rank'] for r in scenario['rank_changes']}=={'a':3,'c':2}
    assert result['records'][0]['local_supported_rank_range']==[1,3]
    assert (rows,gov,case)==original


def test_rejected_hypothesis_never_enters_supported_bounds():
    rows,gov,case=inputs()
    case['status']='REJECTED_DIAGNOSTIC'
    result=analyze(rows,gov,[case])
    assert result['cases'][0]['scenario']['rank']==3
    assert result['records'][0]['local_supported_rank_range'] is None
    assert '本情景77.10' not in render(result)
    assert '该假设已排除' in render(result)


def test_unquantified_is_not_zero_width_or_high_confidence():
    rows,gov,case=inputs()
    case.update(status='UNRESOLVED_EVIDENCE_GAP',changes=[])
    result=analyze(rows,gov,[case])
    assert all(r['local_supported_rank_range'] is None for r in result['records'])
    assert result['cases'][0]['scenario'] is None
    assert '未量化' in render(result)
    case['changes']=inputs()[2]['changes']
    with pytest.raises(ValueError,match='不能生成'):
        analyze(rows,gov,[case])


def test_baseline_drift_and_unclosed_endpoint_changes_fail_closed():
    rows,gov,case=inputs()
    case['changes'][0]['baseline']['end_band']=3
    with pytest.raises(ValueError,match='基准已变'):
        analyze(rows,gov,[case])
    rows,gov,case=inputs()
    case['changes'][0]['alternative']['end_band']=3
    with pytest.raises(ValueError,match='联合重裁'):
        analyze(rows,gov,[case])


def test_joint_case_reprices_all_targets_before_ranking():
    rows,gov,case=inputs()
    other=deepcopy(case['changes'][0]); other['ruler_id']='b'
    case['changes'].append(other)
    result=analyze(rows,gov,[case])
    assert result['cases'][0]['scenario']['rank']==2
    changes={r['ruler_id']:r['scenario_rank'] for r in result['cases'][0]['scenario']['rank_changes']}
    assert changes=={'a':2,'b':2,'c':1}


def test_duplicate_axis_and_missing_dependency_proof_are_rejected():
    rows,gov,case=inputs()
    case['changes'].append(deepcopy(case['changes'][0]))
    with pytest.raises(ValueError,match='重复'):
        analyze(rows,gov,[case])
    rows,gov,case=inputs()
    case['changes'][0]['dependency_basis']=''
    with pytest.raises(ValueError,match='联动|端点'):
        analyze(rows,gov,[case])
