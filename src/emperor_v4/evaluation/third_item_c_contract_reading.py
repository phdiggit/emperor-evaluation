"""Trace current C evidence without assigning or changing historical grades.

Only authored review inputs live in public_reading. This module assembles the
full review from current evidence and an explicitly supplied context. A gate
or a count never proves a semantic grade.
"""
from copy import deepcopy
from html import escape
from pathlib import Path
import json
import re

from .first_item_b1_inputs import load_opponent_systems
from .opponent_system_contract import load_opponent_system_contract
from .third_item_c_passages import expand_entry, expand_passages, validate_passages

SCHEMA = 'third-item-c-joint-contract-inputs-v1'
BUILT_SCHEMA = 'third-item-c-contract-reading-v3'
# The expanded, build-time reading shape stays stable for all reader surfaces.
READING_SCHEMA = 'third-item-c-joint-contract-reading-v1'
RULE = 'docs/分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md'
O_RULE = 'docs/证据规则/军事对手战争机器O档合同.md'
O_SOURCE = 'config/military/opponent-system-contract.json'
C_SOURCE = 'config/third-item/third-item-c-strategy-chain-adjudications.json'
PARENT_SOURCE = 'config/third-item/third-item-c-parent-cycle-adjudications.json'
RETURNS = {'HIGH_RETURN': '高收益', 'PROPORTIONATE_RETURN': '相称收益',
           'COMMENSURATE_RETURN': '相称收益', 'LOW_RETURN': '低收益',
           'NEGATIVE_RETURN': '负收益', 'UNKNOWN': '未明确分类',
           'NOT_APPLICABLE_CAPABILITY_ONLY': '能力观察，不参与当前回报类别'}
AXES = {'C1': 'combat_delivery_grade'}
def load_context(root):
    contract = load_opponent_system_contract(root)
    systems=load_opponent_systems(root)
    for ref,entries in contract.get('window_assessment_extensions',{}).items():
        if ref not in systems:raise ValueError('窗口补证不得另造未登记的机器身份')
        systems[ref].setdefault('window_assessments',{}).update(entries)
    for system in systems.values():
        for entry in system.get('window_assessments',{}).values():
            if entry.get('organization_grade') not in contract['grades'] or not all(entry.get(k) for k in ('subject_ruler_id','actual_competition_window','source_chain_refs','basis','source_passages')):
                raise ValueError('对手窗口评定缺少主体、投入范围、具体依据或逐字出处')
    parent_payload = json.loads((root / PARENT_SOURCE).read_text(encoding='utf-8'))
    parents = {(r['ruler_id'], c['cycle_ref']): c for r in parent_payload['people'] for c in r['parent_cycles']}
    return {'systems': systems, 'o_grades': contract['grades'], 'parent_cycles': parents}


def _unique(values):
    return list(dict.fromkeys(str(v) for v in values if v))


def _number(value):
    if value == 'UNKNOWN':
        return None
    return int(str(value).rsplit('-', 1)[-1])


def _outcome_review_label(chain, outcome):
    status = chain.get(f'major_{outcome}_review_status')
    if status == 'PENDING':
        return '待裁（不作已审零项）'
    if status == 'REVIEWED_NOT_ESTABLISHED':
        return '已审不成立'
    if status == 'REVIEWED_CONFIRMED':
        return '已审成立'
    return '有（现行登记）' if chain.get(f'major_system_{outcome}') else '未登记'


def _public_title(value, fallback):
    return value if value and re.search('[\u3400-\u9fff]', value) and not value.startswith('正式父周期：') else fallback


def _parent_refs(row, chain):
    explicit = chain.get('member_parent_refs') or chain.get('source_parent_refs')
    if explicit:
        return _unique(explicit), 'EXPLICIT_MEMBERS'
    linked = [p['parent_ref'] for p in row.get('strategy_chain_parent_cycle_evidence', [])
              if isinstance(p, dict) and p.get('strategy_chain_ref') == chain['chain_id']]
    if linked:
        return _unique(linked), 'EXPLICIT_MEMBERS'
    return _unique(chain.get('source_event_refs', [])), 'SOURCE_REFERENCES_ONLY'


def _system_entry(ref, system, status, task_refs):
    return dict(ref=ref, label=system['opponent_label'], grade=system['organization_grade'],
                window=system.get('actual_competition_window','尚未显式登记本人的交手窗口'),
                basis=system['basis'], source_campaign_refs=deepcopy(system['source_campaign_refs']),
                binding_status=status, matched_task_refs=sorted(task_refs),
                source=O_SOURCE if not system.get('system_id') else 'docs/公共成果/军事/01-战役登记.json')


def _opponent_grade_conflict(old_grade, opponents, sourced):
    grades = {s['grade'] for s in opponents}
    different = old_grade in ('O1','O2','O3','O4','O5','O6') and bool(grades) and old_grade not in grades
    if not different:
        return False
    notes = (sourced or {}).get('opponent_adjudication_notes', {})
    # A documented window correction resolves the old label difference. Keep
    # the old grade visible, without continuing to call it an unreviewed conflict.
    return not all(s.get('binding_status') == 'SOURCE_WINDOW_REVIEWED'
                   and notes.get(s['ref'], {}).get('basis')
                   and s.get('assessment_ref')
                   and notes[s['ref']].get('window_ref') == s['assessment_ref']
                   for s in opponents)


def _unresolved_opponent(entry, cid, parents, sourced):
    classification = entry.get('classification', 'BOUNDED_UNCERTAINTY')
    labels = {'BOUNDED_UNCERTAINTY': '未定',
              'NON_SYSTEM': '未证独立体系',
              'NO_ENCOUNTER': '未证本方交战',
              'SOURCE_GAP': '缺具体过程',
              'WINDOW_CONFLICT': '窗口错配',
              'SIDE_CONFLICT': '归属混录'}
    if classification not in labels:
        raise ValueError('未知的对手材料审查类别')
    passages = sourced.get('source_passages', [])
    return dict(ref='UNDETERMINED:'+cid, label=entry['label'],
                grade=labels[classification], classification=classification,
                window=entry.get('actual_window', sourced['actual_window']),
                basis=entry['basis'], grade_range=entry.get('grade_range', []),
                source_campaign_refs=parents,
                binding_status='SOURCE_EVIDENCE_UNDETERMINED',
                matched_task_refs=[cid], source=passages[0]['path'] if passages else C_SOURCE)


def _additional_capability_chains(row):
    admitted=set(row.get('capability_only_parent_refs', []))
    grouped=set()
    existing=set(row.get('strategy_chain_refs',[])+row.get('capability_only_strategy_chain_refs',[]))
    covered={ref for chain in row.get('capability_only_strategy_chains',[]) for ref in _parent_refs(row,chain)[0]}
    result=[]
    for observation in row['public_reading'].get('additional_capability_chains', []):
        refs=observation.get('source_parent_refs', [])
        cid=observation.get('chain_id')
        if not cid or cid in existing or not refs or not set(refs)<=admitted or grouped.intersection(refs) or covered.intersection(refs):
            raise ValueError('补证能力组须逐项来自本人已准入父任务且不得重复分组')
        if not observation.get('basis') or not observation.get('label'):
            raise ValueError('补证能力组须有实际任务名称与分组依据')
        existing.add(cid);grouped.update(refs)
        result.append(dict(observation,chain_type='PUBLIC_CAPABILITY_EVIDENCE_GROUP',terminal_result_class='NOT_APPLICABLE_CAPABILITY_ONLY'))
    return result


def build_review(row,context,*,task_aliases=(),axis_findings=None):
    from .third_item_c_joint import verify_joint
    verify_joint(row)
    a=row['joint_assessment'];chains=[]
    by_id={c['chain_id']:c for c in row.get('strategy_chains',[])+row.get('capability_only_strategy_chains',[])}
    for binding in a.get('opponent_windows',[]):
        if binding.get('status') not in {'REGISTERED_ACTUAL_WINDOW','O_UNKNOWN','NON_COMBAT'}:
            raise ValueError('未知实际对手窗口状态')
        for entry in binding.get('opponents',[]):
            system=context.get('systems',{}).get(entry.get('opponent_system_ref'))
            if system is None:raise ValueError('实际对手引用未在公共登记')
            pointer=entry.get('registry_pointer') or ''
            key=pointer.rsplit('/',1)[-1]
            if '/window_assessment_extensions/' in pointer or '/window_assessments/' in pointer:
                w=system.get('window_assessments',{}).get(key)
                if not w or w.get('subject_ruler_id')!=row['ruler_id']:
                    raise ValueError('实际对手窗口借入他人材料')
                if w.get('organization_grade')!=entry['organization_grade']:
                    raise ValueError('实际对手窗口档位与公共登记不同值')
                c=by_id.get(binding['ref'])
                if c and binding['ref'] not in w.get('source_chain_refs',[]):
                    parents=set(_parent_refs(row,c)[0])
                    if not parents & set(w.get('source_campaign_refs',[])):
                        raise ValueError('实际对手窗口未绑定本人任务')
            elif system.get('organization_grade')!=entry['organization_grade']:
                raise ValueError('实际对手档位与公共登记不同值')
    for c in list(row.get('strategy_chains') or [])+list(row.get('capability_only_strategy_chains') or []):
        cid=c['chain_id']
        windows=deepcopy([w for w in a.get('opponent_windows',[]) if w.get('ref')==cid])
        for w in windows:
            if w['opponents']:w['label']='；'.join(e['label']+'（'+e['organization_grade']+'）' for e in w['opponents'])
            w['status']={'REGISTERED_ACTUAL_WINDOW':'已登记本人实际窗口','O_UNKNOWN':'实际投入层级未知','NON_COMBAT':'不另立交战对手'}.get(w['status'],w['status'])
        chains.append(dict(chain_id=cid,title=row['public_reading']['task_titles'][cid],
            scope='能力专用' if c in row.get('capability_only_strategy_chains',[]) else '当前任务',
            basis=c.get('basis',''),opponent_windows=windows,
            result=RETURNS.get(c.get('terminal_result_class'),'未明确分类'),
            adopted=cid in a['adopted_chain_refs']))
    excluded=[dict(chain_id=ref,label=row['public_reading']['task_titles'].get(ref,'未采用的观察材料'),basis=basis.replace('不改正式结果','退出本人采用'))
        for ref,basis in a.get('excluded_observations',{}).items()]
    return dict(schema_version=READING_SCHEMA,summary=row['public_reading']['story'],method='逐项核对实际任务、对手及关键阶段。是否采用和未明之处分别保留，不按胜负条数计算能力。',
        sources=[RULE,O_RULE,C_SOURCE],chains=chains,phase_reviews=deepcopy(a.get('key_phase_reviews',[])),
        excluded_chain_reviews=excluded,
        limitations=deepcopy(a.get('limitations',[])),inheritance=deepcopy(row.get('inherited_system_assessment')),
        conclusion='采用范围与未明之处见各任务说明；来源未穷尽，不将缺载视作不存在。')

def review_inputs(*,task_aliases=(),axis_findings=None):
    return dict(schema_version=SCHEMA,task_aliases=list(task_aliases),axis_findings=axis_findings or {})

def validate_review(row,context):return build_review(row,context)
def reading_review(row,*,context):return validate_review(row,context)

def markdown_review(review):
    lines=['#### 完整任务与关键阶段','',review['method'],'']
    for c in review['chains']:
        lines+=['##### '+c['title'],'',c['scope']+'；'+('纳入本次整体判断' if c['adopted'] else '保留事实与未采用边界')+'；'+c['result'],'',c['basis'],'']
        for w in c['opponent_windows']:
            lines+=['实际对手窗口：'+w.get('label','')+'；'+w.get('status',''),'']
    for p in review['phase_reviews']:
        lines+=['关键阶段：'+p['label']+'；'+str(p.get('adopted_difficulty') or '未采用高D'),' ',p['joint_phase_reason'],'']
    for e in review['excluded_chain_reviews']:lines+=['不计分：'+e['label']+'；'+e['basis'],'']
    lines+=review['limitations']+[review['conclusion']]
    return '\n'.join(line.rstrip() for line in lines)

def html_review(review,source_link=None,*,evidence_link=None):
    def p(x):return '<p class="prose">'+escape(str(x))+'</p>'
    out=p(review['method'])
    for c in review['chains']:
        out+='<details><summary>'+escape(c['title'])+'</summary>'+p(('纳入整体判断；' if c['adopted'] else '保留记录，未纳入采用；')+c['scope']+'；'+c['result'])
        for w in c['opponent_windows']:out+=p(w.get('label','')+'；'+w.get('status',''))
        out+='<details><summary>详细裁决依据</summary>'+p(c['basis'])+'</details></details>'
    for phase in review['phase_reviews']:out+='<details><summary>'+escape(phase['label'])+'</summary>'+p(phase['joint_phase_reason'])+'</details>'
    for e in review['excluded_chain_reviews']:out+='<details><summary>未采用：'+escape(e['label'])+'</summary>'+p(e['basis'])+'</details>'
    return out+''.join(p(x) for x in review['limitations'])
