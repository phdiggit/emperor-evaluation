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

SCHEMA = 'third-item-c-contract-inputs-v1'
BUILT_SCHEMA = 'third-item-c-contract-reading-v3'
# The expanded, build-time reading shape stays stable for all reader surfaces.
READING_SCHEMA = 'third-item-c-contract-reading-v1'
RULE = 'docs/分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md'
O_RULE = 'docs/证据规则/军事对手战争机器O档合同.md'
O_SOURCE = 'config/military/opponent-system-contract.json'
C_SOURCE = 'config/third-item/third-item-c-strategy-chain-adjudications.json'
PARENT_SOURCE = 'config/third-item/third-item-c-parent-cycle-adjudications.json'
RETURNS = {'HIGH_RETURN': '高收益', 'PROPORTIONATE_RETURN': '相称收益',
           'COMMENSURATE_RETURN': '相称收益', 'LOW_RETURN': '低收益',
           'NEGATIVE_RETURN': '负收益', 'UNKNOWN': '未明确分类',
           'NOT_APPLICABLE_CAPABILITY_ONLY': '能力观察，不参与当前回报类别'}
AXES = {'C1': 'combat_delivery_grade', 'C2': 'operational_sustainability_cap',
        'C3': 'system_reliability_cap'}
QUESTIONS = {
 'C1': '应结合对手强度、完整交战过程、战果、战损与续战能力判断。攻城未克或目标未全成不直接等于全役战败，局部胜利也不等于主要目标已经完成；五档不得有完整战略链上的重大体系失败。',
 'C2': '应比较已执行的动员、粮运、补充和恢复，不能用出兵数、里程或敌方断粮代替自身保障。',
 'C3': '应比较不同主将、战场的实际执行与纠错，不能用名将名单、君主名望或一次亲征代替稳定复制。',
}
BOUNDARIES = {
 'C1': ('核心任务整体失去能力与仍能临时作战', '普通任务反复失败与仍能有限兑现',
        '总体偏弱与普通中等任务总体可成', '普通中等任务可成与主要高难任务多数可成',
        '主要高难任务多数可成、仅有少数重大失败，与多个强敌体系下长期顶级兑现且无完整战略链重大失败'),
 'C2': ('保障体系崩溃与仍能极短期行动', '极短期行动与有限持续作战',
        '保障经常限制主要行动与通常可支撑普通战争', '普通战争可维持与多路大规模长期战争稳定维持',
        '仍有显著缺口与多个强敌、独立方向长期顶级保障且无整组保障崩溃'),
 'C3': ('全国组织全面崩溃且未恢复与中央长期严重失灵', '中央长期严重失灵与仍有有限组合可执行',
        '反复重大组织失误或依赖单一集团与通常有效', '通常有效与多将多方向稳定运行',
        '多将多方向运行与顶级跨将跨战场复制及具名显著成果'),
}


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


def build_review(row, context, *, task_aliases=(), axis_findings=None):
    """Build an evidence review; no numeric result is inferred or written here."""
    from .third_item_c_public import SCALES
    authored = expand_passages(row['public_reading'])
    items = {e['id']: e for e in authored['evidence_items']}
    chains = row.get('strategy_chains', []) + row.get('capability_only_strategy_chains', [])
    # Some settled records admit capability parents without a converted chain.
    # An authored grouping exposes that evidence for reading only. It never
    # changes the official chain ledger, outcome quality, counts or gates.
    chains += _additional_capability_chains(row)
    current_ids = set(row.get('strategy_chain_refs', []))
    chain_ids = {c['chain_id'] for c in chains}
    titles = authored.get('chain_titles', {})
    if any(cid not in chain_ids or not isinstance(title, str) or not title.strip()
           or not re.search('[\u3400-\u9fff]', title) for cid,title in titles.items()):
        raise ValueError('公开任务标题须明确绑定本人现有任务并使用具体中文名称')
    aliases = {}
    for alias in task_aliases:
        if alias['chain_id'] not in chain_ids or not alias.get('basis'):
            raise ValueError('C公开任务别名须有本人战争链和人工说明')
        aliases.setdefault(alias['chain_id'], []).append(alias['task_ref'])
    gate = row.get('c5_axis_gate') or {}
    person_systems = {s['opponent_system_ref']: s for s in gate.get('C1_O4_plus_opponent_systems', [])}
    chain_reviews = []
    for i, chain in enumerate(chains, 1):
        cid = chain['chain_id']; parents, parent_status = _parent_refs(row, chain)
        sourced = authored.get('source_reviews', {}).get(cid)
        parent_evidence = []
        for ref in parents:
            entry = context.get('parent_cycles', {}).get((row['ruler_id'], ref))
            state = entry.get('evidence_status') if entry else 'NOT_BOUND'
            parent_evidence.append(dict(ref=ref, evidence_status=state,
                status_text=('已登记边界与来源，仍须结合本人窗口' if state=='CLOSED' else '来源仍待复核，登记存在不等于史实边界已证' if state=='PENDING' else '尚未按本人身份定位到父周期登记'),
                source_refs=deepcopy(entry.get('source_refs', [])) if entry else []))
        linked = [e for e in items.values() if cid in e.get('c_chain_refs', [])]
        axis_links = {axis: [dict(evidence_ref=a['evidence_ref'], reason=a['reason'])
                            for a in authored['axes'][axis].get('arguments', [])
                            if a['evidence_ref'] in {e['id'] for e in linked}]
                      for axis in AXES}
        used = {a['evidence_ref'] for values in axis_links.values() for a in values}
        facts = [e for e in linked if e['id'] in used]
        # Explicit source bindings locate reviewed facts without silently adopting
        # them as new axis arguments. Boundary material never fills a war-fact gap.
        source_refs = (sourced or {}).get('source_material_refs', [])
        boundary_refs = (sourced or {}).get('boundary_material_refs', [])
        linked_ids = {e['id'] for e in linked}
        if not set(source_refs + boundary_refs) <= linked_ids or set(source_refs) & set(boundary_refs):
            raise ValueError('回源材料须显式关联本链，事实材料与范围材料不得混用')
        if any(items[ref]['kind'] == '现行评价判断' for ref in source_refs):
            raise ValueError('总体评价不得充作回源战争事实')
        if any(not items[ref].get('source_passages') for ref in source_refs + boundary_refs):
            raise ValueError('回源材料须保留可逐字核对的来源摘录')
        source_facts = [e for e in linked if e['id'] in used or e['id'] in source_refs]
        boundary_materials = [items[ref] for ref in boundary_refs]
        title = titles.get(cid) or _public_title(chain.get('label'), facts[0]['label'] if facts else f'战争范围第{i}条（公开名称尚待整理）')
        refs = set(parents + chain.get('source_event_refs', []) + chain.get('source_parent_refs', [])
                   + aliases.get(cid, []) + [cid])
        # These are authored material-to-chain bindings, not a guessed conversion
        # of CAMPAIGN/WAR names. Matching a task still does not prove its side or window.
        for fact in linked:
            if fact.get('war_event_id'):refs.add(fact['war_event_id'])
            for source in fact.get('sources', []) + fact.get('source_passages', []):
                anchor = source.get('path', '').partition('#')[2]
                if anchor.startswith('WAR-'):refs.add(anchor)
                elif anchor.startswith('war_event_id='):refs.add(anchor.removeprefix('war_event_id='))
        opponents = []
        for ref, system in context['systems'].items():
            phase_entries=[(key,entry) for key,entry in system.get('window_assessments',{}).items()
                           if entry['subject_ruler_id']==row['ruler_id'] and cid in entry['source_chain_refs']]
            if phase_entries:
                for key,entry in phase_entries:
                    value=_system_entry(ref,entry,'SOURCE_WINDOW_REVIEWED',{cid})
                    value['assessment_ref']=key
                    value['mother_grade']=system['organization_grade']
                    value['scope_note']='对象原总体登记'+system['organization_grade']+'；本条按已核实的主体、窗口和实际投入取'+entry['organization_grade']+'。总体登记不替代窗口，两个层次不重复算两个对手。'
                    opponents.append(value)
                continue
            if system.get('subject_ruler_id') and system['subject_ruler_id'] != row['ruler_id']:continue
            person = person_systems.get(ref) or {}
            match = refs & set(system['source_campaign_refs'])
            person_match = refs & set(person.get('task_refs', []))
            sourced_match = system.get('subject_ruler_id') == row['ruler_id'] and cid in system.get('source_chain_refs', [])
            if match or person_match or sourced_match:
                status = 'SOURCE_WINDOW_REVIEWED' if sourced_match else 'PERSON_GATE_AND_TASK' if person_match else 'PUBLIC_TASK_CANDIDATE'
                opponents.append(_system_entry(ref, system, status, match | person_match | ({cid} if sourced_match else set())))
        if sourced:
            selected=set(sourced.get('opponent_refs', []))
            opponents=[o for o in opponents if o['ref'] in selected]
            for entry in sourced.get('unresolved_opponents',[]):
                opponents.append(_unresolved_opponent(entry, cid, parents, sourced))
            if sourced.get('admissibility_conflict'):
                for opponent in opponents:
                    opponent['binding_status']='SOURCE_OBJECT_ONLY'
                    opponent['scope_note']='已核对原战事对象；本人的实战归属或任务准入存在下述冲突，不参加本人高难任务证明。'
                    if sourced.get('admissibility_conflict_basis'):
                        opponent['scope_note']+=' '+sourced['admissibility_conflict_basis']
        old_grade = str(chain.get('opponent_grade') or '')
        normalized_old = old_grade.removeprefix('INTERNAL_')
        old_text = (normalized_old + ('（旧内部任务等级，未替代公共登记）' if old_grade.startswith('INTERNAL_') else '')
                    if normalized_old in ('O1','O2','O3','O4','O5','O6') else '没有可核准的公共O档（旧记录缺项或仅有继承占位）')
        grades = {s['grade'] for s in opponents}
        conflict = _opponent_grade_conflict(normalized_old, opponents, sourced)
        gaps = []
        if not opponents:
            gaps.append('没有按已登记任务定位到公共对手O档；旧链内称谓或占位不能替代具名、实际交手窗口的登记。')
        elif conflict:
            gaps.append(f'链内旧称为{old_grade}，同任务公共登记候选为' + '、'.join(sorted(grades)) + '；尚须核对交手双方及窗口，潜在口径冲突未解决，不能择高用于证明档位。')
        elif not any(s['binding_status'] in ('PERSON_GATE_AND_TASK','SOURCE_WINDOW_REVIEWED') for s in opponents):
            gaps.append('公共登记能对应任务，但尚缺将其实际投入绑定到本人交手窗口的明确裁决；候选不等于已经核准。')
        if parent_status != 'EXPLICIT_MEMBERS':
            gaps.append('现有记录只给出父任务或阶段来源，未逐一明确其在本链中的成员身份；不把来源数量当独立任务数。')
        if not parents:
            gaps.append('本链缺少可下钻的父周期定位。')
        pending_parents = [e for e in parent_evidence if e['evidence_status'] != 'CLOSED']
        if pending_parents:gaps.append(f'{len(pending_parents)}项父周期或阶段定位的来源边界仍待核实，不能把登记数量当已证任务数。')
        if not facts:
            gaps.append('尚无本页逐轴论证实际采用的具体史实材料与本链相连；不以旧总体评价充作史实。')
        result = chain.get('terminal_result_class') or 'UNKNOWN'
        phase = [dict(ref=p.get('ref'), result=p.get('return_class', 'UNKNOWN'), result_label=RETURNS.get(p.get('return_class','UNKNOWN'),'未明确分类'))
                 for p in chain.get('known_phase_results', [])]
        if result == 'UNKNOWN':gaps.append('完整战略链回报尚未明确分类，不当作失败或中性结果。')
        result_basis = ('完整链回报为现有正式裁决；下列事实可以用于核查，但目前没有独立说明投入、目标、所得与维持结果如何共同推导该类别。'
                        if result != 'UNKNOWN' else '尚无完整链回报裁决。')
        terminal_note = chain.get('terminal_result') if isinstance(chain.get('terminal_result'), str) else ''
        if terminal_note:
            result_basis = '现有终局说明：' + terminal_note + ' 这段说明供核查回报类别，不把终局成败自动换成三轴档位。'
        if sourced:
            result_basis = sourced['return_explanation']
            gaps = list(sourced.get('specific_gaps', []))
            for parent in parent_evidence:
                if parent['ref'] not in sourced.get('reviewed_parent_refs', []):continue
                parent['legacy_evidence_status']=parent['evidence_status']
                parent['evidence_status']='SOURCE_RECHECKED'
                parent['status_text']='已回到具体来源复核；本人的窗口、归属与任务准入限制见本链说明，旧登记状态保留在追溯数据中'
                parent['source_refs']=[s['path'] for s in sourced['source_passages']]
        # A successful battle or negative episode is not itself the return derivation.
        chain_reviews.append(dict(chain_id=cid, title=title,
            consumption='CURRENT' if cid in current_ids else 'CAPABILITY_ONLY',
            consumption_text=('本项当前战争：参与结果质量' if cid in current_ids else
                              '已准入能力父任务的公开补证组：未改写正式战略链台账、数量或门禁，不进入当前回报质量'
                              if chain.get('chain_type')=='PUBLIC_CAPABILITY_EVIDENCE_GROUP' else
                              '仅作能力观察：不进入当前回报质量，不重复领取成果或成本'),
            person_window=authored['window'], recorded_period=chain.get('period', ''),
            window_note='只采用本人的实际权力阶段；战争总跨度不等于全部归本人。',
            parent_refs=parents, parent_binding_status=parent_status, parent_evidence=parent_evidence,
            opponents=opponents, legacy_opponent_grade=old_grade,
            legacy_opponent_text=old_text,
            opponent_conflict=conflict, terminal_result_class=result,
            high_difficulty_exclusion=sourced.get('high_difficulty_exclusion','') if sourced else '',
            result_label=RETURNS.get(result, '未识别的回报类别'), result_basis=result_basis,
            phase_results=phase, major_success=bool(chain.get('major_system_success')),
            major_failure=bool(chain.get('major_system_failure')),
            evidence_refs=[e['id'] for e in source_facts], axis_links=axis_links, gaps=gaps,
            **({'boundary_evidence_refs': list(boundary_refs)} if boundary_refs else {}),
            evidence_sources=[dict(label=e['label'], path=s['path']) for e in source_facts + boundary_materials for s in e['sources']],
            source_review_ref=cid if sourced is not None else None))
    axes = {}
    inheritance = row.get('inherited_system_assessment') if row.get('system_observation_status') == 'INHERITED_UNTESTED' else None
    for idx, (axis, field) in enumerate(AXES.items()):
        g = _number(row[field]); a = authored['axes'][axis]
        args = [x for x in a.get('arguments', []) if x.get('evidence_ref') in items]
        relevant = [c for c in chain_reviews if c['axis_links'][axis]]
        limits = []
        if not args:limits.append('缺少逐条史实论证，现有数值不能仅凭原总体评价得到证明。')
        uncovered = [c['chain_id'] for c in chain_reviews if not c['axis_links'][axis]]
        if uncovered:limits.append(f'本轴尚未逐条审查全部战争：{len(uncovered)}条链未绑定本轴具体论证，不能用选例推出全任期比例或稳定性。')
        if g is not None and g >= 4 and axis in ('C1', 'C3') and len(chains) < 2:
            limits.append('现有可观察战略链不足两条，与四档所需的样本上限条件有冲突；须按合同重裁，不以现有档位反证资格。')
        if g is not None and g >= 4 and any(c['gaps'] for c in chain_reviews):
            limits.append('对手、窗口、父周期或材料绑定仍有逐链缺口，尚不能据这些记录完整证明高难任务、多方向或稳定复制。')
        if g == 5:
            high = [c for c in chain_reviews if not c['high_difficulty_exclusion'] and (not c['opponent_conflict'] or c['legacy_opponent_grade'].removeprefix('INTERNAL_') in ('O4','O5','O6') or authored.get('source_reviews', {}).get(c['chain_id'])) and any(s['binding_status'] in ('PERSON_GATE_AND_TASK','SOURCE_WINDOW_REVIEWED') and s['grade'] in ('O4','O5','O6') for s in c['opponents'])]
            if len(high) < 3:limits.append('尚未明确串起至少三条跨期高难战略链；人数、事件条数与资格通过标签不能补足。')
            limits.append('五档还须逐项证明长期顶级表现；必要资格通过不等于足以排除四档。')
            if axis == 'C2':limits.append('必须审查所有主要方向是否发生整组保障崩溃，不能把有饥疫就自动算崩溃，也不能因最终胜利就免审。')
            if axis == 'C3':limits.append('须把具名顶级将领各自在本人窗口的显著成果落到具体战争，名将名单本身不算完成验证。')
        lower = (f'与{g-1}档的分界是：{BOUNDARIES[axis][g-1]}。现有事实支持哪些能力见下列逐条作用；尚缺按全部相关任务进行同尺度比较，不能仅由原档位排除低一档。'
                 if g else '本轴已是最低档；仍须证明崩溃的范围、持续时间与任内未恢复，不能由一次败战或材料空白推出零档。')
        upper = (f'与{g+1}档的分界是：{BOUNDARIES[axis][g]}。目前没有达到更高档的完整证明；这是证据边界，不等于已经证明实际能力必然达不到。'
                 if g is not None and g < 5 else '本轴已是最高档；重点是能否充分排除四档，而不是继续增加胜仗数量。')
        if g is None:
            lower = '必要事实不足，不能以零档或原分代替尚未成立的裁决。'
            upper = '须补足下列具名缺口后重新定档，不默认赋予中档。'
        examples = '；'.join(items[x['evidence_ref']]['label'] + '：' + x['reason'] for x in args[:2])
        if examples:
            lower += ' 本人可核查的支持是：' + examples
        if g == 3 and axis in ('C1','C3') and len(chains) < 2 and not inheritance:
            upper = f'四档至少需两条可观察战略链，现有记录仅{len(chains)}条，不满足提高到四档的样本必要条件。这限制证据上限，不反推历史能力一定弱，也不单凭样本少证明三档。'
        if g == 4:
            upper += ' 本人五档资格中的强敌登记为' + '、'.join(s['opponent_label'] + s['organization_grade'] for s in person_systems.values()) if person_systems else ' 本人五档资格没有具名强敌登记，不能借原四档反推已经达到或接近五档。'
        status = 'ADJACENT_BOUNDARY_UNRESOLVED'
        support = a['basis']
        if inheritance:
            cont = inheritance['axis_continuity'][axis]
            support = cont['grade_basis']
            lower = cont['baseline_basis'] + ' ' + cont['continuity_basis']
            upper = cont['grade_basis'] + ' 没有任内实战新验证，不以先帝战果增加本人档位。'
            status = 'INHERITED_LIMITED_ASSESSMENT'
            limits = [inheritance['inference_limit']]
        elif not args:
            status = 'MATERIAL_EVIDENCE_MISSING'
        axes[axis] = dict(grade=g, grade_label='待定' if g is None else f'{g}档', criterion='必要证据不足，暂不定档' if g is None else SCALES[idx][g], support=support,
            evidence_refs=[x['evidence_ref'] for x in args], chain_refs=[c['chain_id'] for c in relevant],
            against_lower=lower, against_upper=upper, counterevidence_review=QUESTIONS[axis],
            status=status, status_text=('按继承证据作有限判断，未作任内实战证明' if inheritance else
                '具体材料缺失，当前档位尚待证据重裁' if not args else '有具体事实支持能力观察，但相邻档分界尚未充分证明'),
            limitations=limits, uncovered_chain_refs=uncovered)
    for axis, finding in (axis_findings or {}).items():
        if axis not in AXES or not finding.get('evidence_refs') or not set(finding['evidence_refs']) <= set(authored['axes'][axis]['evidence_refs']):
            raise ValueError('人工相邻档说明须绑定本轴已采用的事实')
        for key in ('against_lower', 'against_upper'):
            if not finding.get(key):raise ValueError('人工相邻档说明不得只讲一侧')
            axes[axis][key] = finding[key]
        axes[axis]['status_text'] = '已逐项说明两侧分界及具体疑点；未解释的部分仍不视为定档已证'
        axes[axis]['authored_finding_evidence_refs'] = list(finding['evidence_refs'])
        if finding.get('assessment_status'):
            states={'SOURCE_SUPPORTED':'已回源支持本档与相邻档分界','SOURCE_CONFLICT':'已回源发现当前裁决与事实冲突，须重裁','SPECIFIC_SOURCE_GAP':'已回源，缺少具名的关键事实，无法确认档位分界','CONTRACT_BOUNDARY_AMBIGUOUS':'史实已核，全任期分界仍须按合同裁定'}
            if finding['assessment_status'] not in states:raise ValueError('未知回源裁决说明状态')
            if set(finding.get('reviewed_chain_refs',[])) != chain_ids or not chain_ids <= set(authored.get('source_reviews',{})):
                raise ValueError('不得以局部选例宣称完成逐人回源')
            axes[axis]['status']=finding['assessment_status']
            axes[axis]['status_text']=states[finding['assessment_status']]
            axes[axis]['support']=finding['support']
            axes[axis]['limitations']=finding.get('limitations',[])
    success = sum(c['major_success'] for c in chain_reviews)
    failure = sum(c['major_failure'] for c in chain_reviews)
    missing_o = sum(not any(o['grade'] in ('O1','O2','O3','O4','O5','O6') and o['binding_status'] in ('SOURCE_WINDOW_REVIEWED','PERSON_GATE_AND_TASK') for o in c['opponents']) for c in chain_reviews)
    summary = (f'本人的战争按{len(row.get("strategy_chains", []))}条当前战略链、{len(row.get("capability_only_strategy_chains", []))}条能力专用链展开，其中{missing_o}条未采用确定的本人对手窗口档（包括审慎范围、未证独立体系或归属限制，不等于没有战役材料）。父周期只作证据下钻，同一连续战争不按战斗或材料条数重复计功。'
               if not inheritance else '本人按无任内实战的继承体系评价。前任战争只作基线，不能编成本人新战略链、胜绩或回报；须逐轴看任内延续和反证。')
    return dict(schema_version=BUILT_SCHEMA, sources=[RULE, O_RULE, C_SOURCE, PARENT_SOURCE, O_SOURCE],
        summary=summary,
        method='对手O档先说明实际窗口的战争机器强度，再检验完整战略任务的难度、兑现、保障和跨将领运行。O档不是胜绩分数；高O、胜仗多、回报高都不能单独推出本轴高档。',
        o_scales=[dict(grade=k, label=v['label'], definition=v['definition']) for k,v in context['o_grades'].items()],
        chains=chain_reviews, excluded_chain_reviews=deepcopy(authored.get('excluded_chain_reviews', [])), axes=axes, task_aliases=deepcopy(list(task_aliases)), axis_findings=deepcopy(axis_findings or {}),
        person_opponent_gate_records=deepcopy(list(person_systems.values())),
        person_gate_note='这里只展示本人既有的具名资格登记。未逐链对应的记录不自动算已证明；登记之外没有O档不等于对手较弱。',
        gate_explanation=(f'按现有战略链标记，重大体系胜绩{success}条、重大体系失败{failure}条（当前与能力专用均列入资格观察，未按阶段重复）。'
            '四档需至少一项重大体系胜绩，且成功数不低于重大失败数；五档需至少三项、重大失败为零，并有对外战争重大胜绩复验及三轴各自的强敌、方向、将领成果条件。C1五档本身也不得有完整战略链上的重大体系失败。未登记不等于已证明不存在。'),
        gate_directions=deepcopy(gate.get('C2_O4_plus_strategic_directions', [])),
        gate_commander_names=deepcopy(gate.get('C3_top_commander_names', [])),
        return_note='当前战略链回报只参与档内结果质量，不直接决定三轴档位；能力专用链不参与该质量位置。D项的安全或投入产出档位不能替换这里的回报类别。高收益不等于重大体系胜绩，负收益也不自动等于重大体系失败。',
        inheritance=deepcopy(inheritance),
        conclusion='评分以当前正式裁决为准。具体战事、任务组织、门槛与证据缺口分别列明；已查明的归属错误和反证须用于重裁，必要证据不足时暂不定档，不把已有数值或结构通过标记当成历史论证。')


def review_inputs(*, task_aliases=(), axis_findings=None):
    """Create stored inputs without copying any generated review fields."""
    return dict(schema_version=SCHEMA, task_aliases=deepcopy(list(task_aliases)),
                axis_findings=deepcopy(axis_findings if axis_findings is not None else {}))


def validate_review(row, context):
    inputs = row['public_reading'].get('contract_review')
    if not isinstance(inputs, dict) or inputs.get('schema_version') != SCHEMA:
        raise ValueError('C公开正文缺少现行合同论证人工输入')
    if set(inputs) != {'schema_version', 'task_aliases', 'axis_findings'}:
        raise ValueError('C合同论证只保存人工输入，不得内嵌生成副本')
    if (not isinstance(inputs['task_aliases'], list)
            or any(not isinstance(a, dict) or not all(isinstance(a.get(k), str) and a[k].strip()
                       for k in ('chain_id', 'task_ref', 'basis')) for a in inputs['task_aliases'])
            or not isinstance(inputs['axis_findings'], dict)
            or any(not isinstance(finding, dict) for finding in inputs['axis_findings'].values())):
        raise ValueError('C合同论证人工输入结构无效')
    if not isinstance(context, dict) or not {'systems', 'o_grades'} <= context.keys():
        raise ValueError('C合同论证需要显式的现行对手与父周期上下文')
    validate_passages(row['public_reading'])
    review = build_review(row, context, task_aliases=inputs['task_aliases'], axis_findings=inputs['axis_findings'])
    ids = [c['chain_id'] for c in review['chains']]
    if ids != row.get('strategy_chain_refs', []) + row.get('capability_only_strategy_chain_refs', []) + [c['chain_id'] for c in _additional_capability_chains(row)]:
        raise ValueError('C公开合同论证未完整覆盖本人战略链')
    sources = row['public_reading'].get('source_reviews', {})
    if not isinstance(sources, dict):
        raise ValueError('C回源复核须按本人战略链ID登记')
    for chain in review['chains']:
        expected_ref = chain['chain_id'] if sources.get(chain['chain_id']) is not None else None
        if ('source_review' in chain or 'source_review_ref' not in chain
                or chain['source_review_ref'] != expected_ref):
            raise ValueError('C回源复核引用须对应本链唯一来源，不得内嵌副本')
    for axis, field in AXES.items():
        if review['axes'][axis]['grade'] != _number(row[field]):
            raise ValueError('C相邻档解释不得回写或替换当前档位')
    return review


def reading_review(row, *, context):
    """Expand validated chain references for output without changing stored data."""
    review = validate_review(row, context)
    sources = row['public_reading'].get('source_reviews', {})
    for chain in review['chains']:
        ref = chain.pop('source_review_ref')
        chain['source_review'] = expand_entry(row['public_reading'], sources[ref]) if ref is not None else None
    review['schema_version'] = READING_SCHEMA
    return review


def markdown_review(review):
    lines = ['#### 完整任务、对手与相邻档分界', '', review['summary'], '', review['method'], '',
             '本人的对手等级、父周期和回报类别如下；未绑定的公共登记只是候选。', '']
    lines += ['规则与正式依据：' + '；'.join(review['sources']), '']
    if review.get('excluded_chain_reviews'):
        lines += ['已排除的错归任务（不进入本人能力、重大胜负或结果质量）：', '']
        for entry in review['excluded_chain_reviews']:lines += [entry['label'] + '：' + entry['basis'], '']
    for s in review['o_scales']:lines += [s['grade'] + ' ' + s['label'] + '：' + s['definition'], '']
    lines += [review['person_gate_note'], '', review['gate_explanation'], '', '具名将领资格记录：' + '、'.join(review['gate_commander_names']), '']
    for s in review['person_opponent_gate_records']:lines += [s['opponent_label'] + ' · ' + s['organization_grade'], '']
    for s in review['task_aliases']:lines += [s['basis'], '']
    for c in review['chains']:
        lines += [f'##### {c["title"]}', '', c['consumption_text'], '',
                  '本人评价窗口：' + c['person_window'], '', c['window_note'], '',
                  '战略链标识：' + c['chain_id'], '', '父周期或阶段定位：' + '、'.join(c['parent_refs']), '',
                  '对手链内旧称：' + c['legacy_opponent_text'], '']
        for s in c['opponents']:
            grade_text=s['grade']+('；现有史料审慎范围'+'—'.join(s['grade_range']) if s.get('grade_range') else '')
            lines += [f'公共对手：{s["label"]}（{grade_text}；{s["binding_status"]}）', '', s['basis'], '']
        lines += ['完整链回报：' + c['result_label'], '', c['result_basis'], '',
                  '重大体系胜绩：' + ('有' if c['major_success'] else '未登记') + '；重大体系失败：' + ('有' if c['major_failure'] else '未登记'), '']
        for phase in c['phase_results']:lines += ['阶段参考：' + str(phase['ref']) + ' · ' + phase['result_label'] + '（不另出票、不平均成完整链结果）', '']
        for parent in c['parent_evidence']:lines += ['父周期来源状态：' + parent['ref'] + ' · ' + parent['status_text'], '', '来源：' + '；'.join(parent['source_refs']), '']
        for axis, links in c['axis_links'].items():
            for link in links:lines += [axis + '材料 ' + link['evidence_ref'] + '：' + link['reason'], '']
        for gap in c['gaps']:lines += ['未解释：' + gap, '']
        lines += ['来源：' + '；'.join(s['path'] for s in c['evidence_sources']), '']
    for axis, a in review['axes'].items():
        lines += [f'##### {axis}为何定为本档、能否区分相邻档', '', a['status_text'], '',
                  '本档要求：' + a['criterion'], '', a['support'], '', a['against_lower'], '', a['against_upper'], '', a['counterevidence_review'], '']
        for limit in a['limitations']:lines += ['限制：' + limit, '']
    if review['inheritance']:
        e=review['inheritance']
        lines += ['继承基线：' + e['baseline_window'], '', '；'.join(e['baseline_source_refs']), '']
        for a in e['counterevidence_review']:lines += ['继承反证：' + a['basis'], '']
    return '\n'.join(lines + [review['return_note'], '', review['conclusion'], ''])


def html_review(review, source_link=None, *, evidence_link=None):
    """Static collection markup; it only displays the saved upstream review."""
    from .third_item_c_public import AUDIT_TERMS, AUDIT_LINK_NOTE, LABELS
    axis_labels = dict(zip(AXES, LABELS))
    def p(value, cls='prose'):
        return f'<p class="{cls}">{escape(str(value))}</p>'
    def listed(values):
        return '<ul>' + ''.join('<li>' + escape(str(v)) + '</li>' for v in values) + '</ul>'
    def material(ref):
        return evidence_link(ref) if evidence_link else '<code>' + escape(ref) + '</code>'
    def materials(refs):
        if not refs:
            return p('此处尚无正式关联的材料，不能按名称猜配；具体缺口仍按原说明核查。', 'notice')
        return '<ul class="third-c-judgment-materials">' + ''.join('<li>' + material(ref) + '</li>' for ref in dict.fromkeys(refs)) + '</ul>'
    glossary = '<details class="third-c-audit-terms"><summary>核查术语是什么意思？</summary><dl>' + ''.join(
        '<dt>' + escape(term) + '</dt><dd>' + escape(meaning) + '</dd>' for term, meaning in AUDIT_TERMS) + '</dl></details>'
    chains = []
    for c in review['chains']:
        labels={'SOURCE_WINDOW_REVIEWED':'本人实际交手窗口已经回源核实','SOURCE_OBJECT_ONLY':'原战事对象已核对，本人归属或任务准入存在冲突','SOURCE_EVIDENCE_UNDETERMINED':'来源已核对，组织分级仍缺具名关键事实','PERSON_GATE_AND_TASK':'本人资格记录与任务对应'}
        opponents = ''.join('<li><strong>' + escape(s['label']) + ' · ' + escape(s['grade']+('；现有史料审慎范围'+'—'.join(s['grade_range']) if s.get('grade_range') else '')) + '</strong>'
             + p(labels.get(s['binding_status'],'公共任务候选，尚待核对本人实际交手窗口'), 'notice')
             + p('交手评定窗口：'+s['window']) + p(s['basis']) + (p(s['scope_note']) if s.get('scope_note') else '') + (source_link(s['source'], '对手登记依据 ↗') if source_link else '') + '</li>' for s in c['opponents'])
        phases = listed([str(s['ref']) + ' · ' + s['result_label'] + '（阶段参考，不另出票、不平均）' for s in c['phase_results']])
        parents = ''.join('<li><code>' + escape(e['ref']) + '</code>' + p(e['status_text']) + (' '.join(source_link(s, '父周期来源 ↗') for s in e['source_refs']) if source_link else '') + '</li>' for e in c['parent_evidence'])
        refs = '<details><summary>战争过程与原始分组（父周期）</summary>' + p(c['window_note']) + '<ul>' + parents + '</ul>' + phases + p('战略链：' + c['chain_id'], 'meta') + '</details>'
        links = ''.join('<li><strong>' + escape(axis_labels[axis]) + '</strong>：' + escape(link['reason']) + '（对应材料：' + material(link['evidence_ref']) + '）</li>' for axis, values in c['axis_links'].items() for link in values)
        sources = ' '.join(source_link(s['path'], s['label'] + ' ↗') for s in c['evidence_sources']) if source_link else ''
        chains.append('<details class="third-c-contract-chain" data-contract-chain="' + escape(c['chain_id']) + '"><summary>' + escape(c['title']) + ' · ' + escape(c['result_label']) + '</summary>'
             + p(c['consumption_text'], 'meta') + p('本人评价窗口：' + c['person_window'])
             + '<h5>面对什么对手？</h5>' + p('链内旧称：' + c['legacy_opponent_text'])
             + ('<ul>' + opponents + '</ul>' if opponents else p('尚无可对应的公共对手O档。', 'notice'))
             + refs + '<h5>完整任务得到什么？</h5>' + p(c['result_label']) + p(c['result_basis'])
             + '<h5>本次战争已关联的材料</h5>' + materials(c['evidence_refs'])
             + ('<h5>范围核对材料（不作本人战事采用）</h5>' + materials(c['boundary_evidence_refs']) if c.get('boundary_evidence_refs') else '')
             + p('重大体系胜绩：' + ('有' if c['major_success'] else '未登记') + '；重大体系失败：' + ('有' if c['major_failure'] else '未登记'))
             + '<h5>与三方面判断怎样相连？</h5><ul>' + links + '</ul>'
             + (listed(c['gaps']) if c['gaps'] else '') + sources + '</details>')
    gates = ''.join('<li>' + escape(s['opponent_label']) + ' · ' + escape(s['organization_grade']) + '</li>' for s in review['person_opponent_gate_records'])
    comparisons = ''.join('<section class="third-c-adjacent-boundary" data-contract-axis="' + axis + '"><h4>' + escape(axis_labels[axis]) + ' · ' + a['grade_label'] + '的分界审查</h4>'
              + p(a['status_text'], 'notice') + p('本档要求：' + a['criterion']) + p(a['support'])
              + p(a['against_lower']) + p(a['against_upper']) + p(a['counterevidence_review']) + listed(a['limitations'])
              + '<h5>本轴正式关联的材料（含相邻档说明）</h5>' + materials(a['evidence_refs'] + a.get('authored_finding_evidence_refs', [])) + '</section>' for axis,a in review['axes'].items())
    scales = ''.join('<li><strong>' + escape(s['grade']) + ' ' + escape(s['label']) + '</strong>：' + escape(s['definition']) + '</li>' for s in review['o_scales'])
    inheritance = ''
    if review['inheritance']:
        e = review['inheritance']
        inheritance = '<details><summary>继承体系的基线、延续与反证</summary>' + p(e['baseline_window']) + listed([x['basis'] for x in e['counterevidence_review']]) + (''.join(source_link(s, '基线来源 ↗') for s in e['baseline_source_refs']) if source_link else '') + '</details>'
    qualification = p(review['gate_explanation']) + p('具名将领资格记录：' + ('、'.join(review['gate_commander_names']) or '未登记')) + p('方向资格记录：' + ('、'.join(s['direction'] for s in review['gate_directions']) or '未登记')) + listed([s['basis'] for s in review['task_aliases']])
    if review.get('excluded_chain_reviews'):
        inheritance += '<details class="third-c-excluded-tasks"><summary>已排除的错归任务（不计分）</summary>' + listed([e['label'] + '：' + e['basis'] for e in review['excluded_chain_reviews']]) + '</details>'
    return '<section class="third-c-contract-review" data-contract-reading><h3>对手、完整任务与相邻档分界</h3>' + glossary + p(AUDIT_LINK_NOTE) + p(review['summary']) + p(review['method']) + '<details><summary>对手O档怎么看？</summary><ol>' + scales + '</ol></details>' + '<details><summary>已登记的本人对手与资格依据</summary>' + p(review['person_gate_note']) + ('<ul>' + gates + '</ul>' if gates else p('没有具名登记，不能用空白认定对手低档。', 'notice')) + qualification + '</details>' + inheritance + '<details><summary>逐条完整战争及证据分组（战略链、父周期；' + str(len(review['chains'])) + '条）</summary>' + ''.join(chains) + '</details>' + comparisons + p(review['return_note']) + p(review['conclusion'], 'notice') + '</section>'
