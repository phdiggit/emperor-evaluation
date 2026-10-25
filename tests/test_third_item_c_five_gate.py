"""C5 keeps actual high-O and own external delivery, without retired axis quotas."""
from copy import deepcopy
import pytest
from c_joint_cases import row
from emperor_v4.evaluation.third_item_c_five_gate import verify_five_gate

def inputs():
    r=row(5,'MID');r['strategy_chains']=[dict(chain_id='EXTERNAL',source_event_refs=['P3'],major_system_success=True)]
    r['strategy_chain_refs']=['EXTERNAL'];r['capability_only_strategy_chains']=[dict(chain_id='EARLY',source_event_refs=['P1'],major_system_success=True),dict(chain_id='LATE',source_event_refs=['P2'],major_system_success=True)]
    r['joint_assessment']['observation_scopes']={'EXTERNAL':'EXTERNAL'}
    r['joint_assessment']['high_grade_evidence']=dict(opponent_systems=[dict(opponent_system_ref='ONE',task_refs=['EARLY','EXTERNAL']),dict(opponent_system_ref='TWO',task_refs=['LATE'])],
        current_external_chain_refs=['EXTERNAL'],current_external_revalidation_basis='本人外战主军交付',failure_scope_review='明确反证范围与恢复限制')
    systems={key:dict(organization_grade='O4',source_campaign_refs=['P1','P2','P3']) for key in ['ONE','TWO']}
    return r,systems

def test_high_evidence_is_checked_without_talent_quota_or_assigning_grade():
    r,s=inputs();before=deepcopy(r);assert verify_five_gate(r,s,{})['status']=='PASS';assert r==before

@pytest.mark.parametrize('fault',['missing_system','mother_grade','wrong_chain','one_system','duplicate_task','no_external','internal_war','ordinary_result','no_failure_review'])
def test_necessary_high_grade_evidence_fails_closed(fault):
    r,s=inputs();g=r['joint_assessment']['high_grade_evidence']
    if fault=='missing_system':s.pop('ONE')
    elif fault=='mother_grade':s['ONE']['organization_grade']='O3'
    elif fault=='wrong_chain':g['opponent_systems'][0]['task_refs']=['FOREIGN']
    elif fault=='one_system':g['opponent_systems']=g['opponent_systems'][:1]
    elif fault=='duplicate_task':g['opponent_systems'][0]['task_refs']=['EARLY','EARLY']
    elif fault=='no_external':g['current_external_chain_refs']=[]
    elif fault=='internal_war':r['joint_assessment']['observation_scopes']['EXTERNAL']='INTERNAL'
    elif fault=='ordinary_result':r['strategy_chains'][0]['major_system_success']=False
    else:g['failure_scope_review']=''
    with pytest.raises(ValueError):verify_five_gate(r,s)

def test_actual_weak_window_cannot_inherit_mother_high_grade():
    r,s=inputs();s['ONE']['organization_grade']='O6';s['ONE']['window_assessments']={'W':dict(subject_ruler_id=r['ruler_id'],source_chain_refs=['EXTERNAL'],organization_grade='O3')}
    with pytest.raises(ValueError):verify_five_gate(r,s)

def test_failure_is_retained_for_authored_overall_review_not_a_zero_failure_quota():
    r,s=inputs();r['strategy_chains'][0]['major_system_failure']=True
    assert verify_five_gate(r,s)['status']=='PASS'
