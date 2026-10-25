"""Necessary C5 evidence checks; authored joint judgment assigns the grade."""
from .third_item_c_joint import grade

SCHEMA='third-item-c-joint-high-evidence-v1'
HIGH_OPPONENT_GRADES={'O4','O5','O6'}

def verify_five_gate(row,systems,profiles=None):
    if grade(row.get('final_grade'))!=5:return {'status':'NOT_REQUESTED'}
    a=row.get('joint_assessment') or {};gate=a.get('high_grade_evidence') or {}
    chains={c['chain_id']:c for c in row.get('strategy_chains',[])+row.get('capability_only_strategy_chains',[])}
    admitted={}
    for entry in gate.get('opponent_systems',[]):
        ref=entry['opponent_system_ref'];system=systems.get(ref)
        if system is None:raise ValueError('五档对手未在公共O库登记')
        for cid in entry.get('task_refs',[]):
            if cid not in chains:raise ValueError('五档材料不属于本人战争范围')
            windows=[w for w in system.get('window_assessments',{}).values()
                if w.get('subject_ruler_id')==row.get('ruler_id') and cid in w.get('source_chain_refs',[])]
            c=chains[cid]
            parents=set(c.get('source_event_refs',[])+c.get('member_parent_refs',[])+c.get('source_parent_refs',[]))
            parents.update(c[k] for k in ('canonical_strategy_ref','canonical_parent_ref') if c.get(k))
            valid=(any(w.get('organization_grade') in HIGH_OPPONENT_GRADES for w in windows) if windows else
                system.get('organization_grade') in HIGH_OPPONENT_GRADES and bool(parents & set(system.get('source_campaign_refs',[]))))
            if not valid:raise ValueError('五档不得借母体、他任或D路径替代实际O窗口')
            if c.get('major_system_success'):
                admitted.setdefault(ref,set()).add(cid)
    tasks=set().union(*admitted.values()) if admitted else set()
    if len(admitted)<2 or len(tasks)<3:raise ValueError('五档缺多个体系或跨期任务复验')
    current=set(row.get('strategy_chain_refs',[]))
    external=set(gate.get('current_external_chain_refs',[]))
    if not external or not external<=current or not external<=tasks:
        raise ValueError('五档缺本项实际外战复验')
    if any(a.get('observation_scopes',{}).get(cid)!='EXTERNAL' or not chains[cid].get('major_system_success') for cid in external):
        raise ValueError('五档本项复验须为明确外战重大交付')
    for key in ('current_external_revalidation_basis','failure_scope_review'):
        if not gate.get(key):raise ValueError('五档缺外战或重大失败范围说明')
    if not a.get('adverse_evidence') or not a.get('reason'):raise ValueError('五档不得省略整体反证裁决')
    return {'status':'PASS','opponent_system_count':len(admitted),'high_task_count':len(tasks)}
