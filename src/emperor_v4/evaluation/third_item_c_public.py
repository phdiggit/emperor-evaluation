"""Read-only projection of the current C1-led joint settlement."""
from copy import deepcopy
from pathlib import Path
import json
from .third_item_c_joint import grade, verify_joint

AXES=('C1',)
FIELDS=('combat_delivery_grade',)
LABELS=('实战兑现与体系表现',)
SCALES=((
 '核心任务整体失去作战能力','主要任务反复不能兑现','能执行重要或区域任务，主要任务总体偏弱',
 '通常任务有可靠执行，高难复验或压力覆盖有边界','高难主要任务充分交付并有独立复验，整体可靠',
 '多个高阶体系、跨期主要任务持续顶级兑现，并有本项外战复验'),)
METHOD='先确定整体档位，再按低、中、高位分别取该档得分率区间的25%、50%、75%处。以50分乘得分率，四舍五入至一位；五档也不自动满分。'
COMBAT_GUIDE='同时考察对手、作战过程、实际战果、失败程度，以及军队能否在同一压力下恢复。对手强大或条件困难只是高难任务的前提，不直接决定档位；同一任务不按阶段重复算作多次成功。'
ASSESSMENT_SCOPE='任内战争与仅用于观察能力的其他阶段分开。最高档还须经多个强大军事体系、跨期主要任务及本人任内对外战争的实战检验。'
REVIEW_NOTE='档位与位置来自正式联合裁决；保障、组织事实不独立计分。未审材料与未知不当作零失败。'
REVIEW_LABELS={'SOURCE_SUPPORTED':'有明确采用依据','SPECIFIC_SOURCE_GAP':'必要证据不足'}
AUDIT_TERMS=(('高难阶段','实际约束与重大军事交付必须同时成立。'),('独立复验','按实际任务和压力变化判断，同役阶段不重复计算。'))
AUDIT_LINK_NOTE='来源链接只按正式记录已有绑定展示；有链接不等于史料已穷尽。'

def fmt(value):return f'{float(value):.4f}'.rstrip('0').rstrip('.')

def calculation(row):
    g=verify_joint(row)
    a=row['joint_assessment']
    if g is None:
        return dict(final_grade=None,points=None,rate=None,total_label='证据不足 · 暂不计分',
            grade_path='必要证据不足，整体档与分数暂缺。',cap_reason=a['scope_boundary'],
            outcome_text='已知正反证保留，不以未知填零。',position='暂不计算档内位置。',
            formula='暂不计分，不以零分填补或进入综合排名。',method=METHOD)
    position={'LOW':'低位','MID':'中位','HIGH':'高位'}[a['position']]
    rate,points=row['C_score_rate'],row['C_score_points']
    return dict(final_grade=g,points=points,rate=rate,total_label=f'{g}档{position} · {fmt(points)} / 50分',
        grade_path=f'整体{g}档，得分率区间{row["C_score_band"]["lower_rate"]}%—{row["C_score_band"]["upper_rate"]}%。',
        cap_reason='',outcome_text='',
        position=row['public_reading']['position_explanation'],
        formula=f'50 × {fmt(rate)} ÷ 100，四舍五入至一位＝{fmt(points)}分。',method=METHOD)

def reading_projection(row, *, context):
    from .third_item_c_contract_reading import reading_review
    from .third_item_c_commander_reading import commander_projection
    p=deepcopy(row.get('public_reading'))
    if not isinstance(p,dict) or p.get('schema_version')!='third-item-c-joint-public-v1':
        raise ValueError('C缺少当前联合裁决公开正文')
    if set(p)!={'schema_version','story','window','responsibility','boundary','source_note','evidence_items','position_explanation','task_titles'}:
        raise ValueError('C公开正文不得储存生成副本或第二套档位')
    for key in ('story','window','responsibility','boundary','source_note','position_explanation'):
        if not isinstance(p.get(key),str) or not p[key].strip():raise ValueError('C公开正文缺少'+key)
    chains=list(row.get('strategy_chains') or [])+list(row.get('capability_only_strategy_chains') or [])
    if not isinstance(p['task_titles'],dict) or set(p['task_titles'])!={c['chain_id'] for c in chains}:
        raise ValueError('C任务名称须覆盖本人现行任务')
    if any(not isinstance(v,str) or not v.strip() for v in p['task_titles'].values()):
        raise ValueError('C任务名称不得为空')
    items=p.get('evidence_items',[])
    if len(items)!=len({e['id'] for e in items}):raise ValueError('C材料编号重复')
    for e in items:
        if not all(e.get(k) for k in ('id','label','text','kind','scope','sources')):raise ValueError('C材料缺类型、范围或出处')
        if e['kind'] not in ('现行评价判断','既有史实摘要','史料原文'):raise ValueError('未知C材料类别')
        if not set(e.get('c_chain_refs',[]))<=set(row.get('strategy_chain_refs',[])+row.get('capability_only_strategy_chain_refs',[])):
            raise ValueError('C材料引用本人范围外任务')
    g=grade(row['final_grade']);a=row['joint_assessment']
    p['axes']={'C1':dict(label=LABELS[0],grade=g,grade_label='待定' if g is None else str(g)+'档',
        basis=p['story'],assessment_guide=COMBAT_GUIDE,scale=SCALES[0],materials=items,
        evidence_note='' if items else '未见足以定档的本人战争材料。',
        review_status='SPECIFIC_SOURCE_GAP' if g is None else 'SOURCE_SUPPORTED',
        review_label=REVIEW_LABELS['SPECIFIC_SOURCE_GAP' if g is None else 'SOURCE_SUPPORTED'],
        review_text=a['scope_boundary'])}
    p.update(calculation=calculation(row),contract_review=reading_review(row,context=context),
        assessment_scope_note=ASSESSMENT_SCOPE,review_note=REVIEW_NOTE,audit_terms=list(AUDIT_TERMS),
        audit_link_note=AUDIT_LINK_NOTE,ruler_id=row['ruler_id'])
    p['commander_profiles']=commander_projection(row)
    return p

def _json_passage_matches(document, anchor, quote):
    from urllib.parse import parse_qsl
    def records(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from records(child)
        elif isinstance(value, list):
            for child in value:
                yield from records(child)

    pairs=dict(parse_qsl(anchor,keep_blank_values=True)) if '=' in anchor else {}
    field=pairs.pop('field',None)
    matches = [node for node in records(document)
               if (all(str(node.get(k,''))==v for k,v in pairs.items()) if pairs
                   else not anchor or anchor in node.values())]
    if not matches:
        raise ValueError('C材料的JSON记录锚点不存在')
    if field:
        selected=[]
        for node in matches:
            for key in field.split('.'):
                node=node.get(key) if isinstance(node,dict) else None
            if node is not None:selected.append(node)
        matches=selected
    # A saved excerpt may consist of separate lines from one source card.
    # Every line must occur in that same anchored card, never across cards.
    parts=[p.strip() for p in str(quote or '').splitlines() if p.strip()]
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for child in value.values():yield from strings(child)
        elif isinstance(value,list):
            for child in value:yield from strings(child)
    return bool(parts) and any(all(any(p in value for value in strings(node)) for p in parts) for node in matches)



def verify_sources(root,payload,*,context=None):
    from .third_item_c_contract_reading import load_context
    context=load_context(root) if context is None else context
    cache={};documents={};checked=set()
    for row in payload['records']:
        data=reading_projection(row,context=context)
        refs=set(row.get('strategy_chain_refs',[])+row.get('capability_only_strategy_chain_refs',[]))
        for e in data['evidence_items']:
            if not set(e.get('c_chain_refs',[]))<=refs:raise ValueError('C材料借入本人范围外任务')
            for s in e['sources']:
                if not (root/s['path'].partition('#')[0]).is_file():raise ValueError('C来源不存在：'+s['path'])
            for passage in e.get('source_passages',[]):
                path,_,anchor=passage['path'].partition('#')
                key=(path,anchor,passage.get('quote',''))
                if key in checked:continue
                if path not in cache:cache[path]=(root/path).read_text(encoding='utf8')
                text=cache[path];quote=passage.get('quote','')
                if not quote:raise ValueError('C摘录为空')
                if Path(path).suffix=='.json':
                    if path not in documents:documents[path]=json.loads(text)
                    if not _json_passage_matches(documents[path],anchor,quote):raise ValueError('C摘录与JSON记录不符：'+passage['path'])
                else:
                    if anchor:
                        import re
                        heading=re.search(r'^(#{1,6})[ \t]+'+re.escape(anchor)+r'(?:[ \t][^\n]*)?$',text,re.M)
                        if not heading:raise ValueError('C来源段落锚点不存在：'+passage['path'])
                        scoped=text[heading.start():]
                        scoped=re.split(r'\n#{1,'+str(len(heading[1]))+r'}[ \t]',scoped,maxsplit=1)[0]
                    else:scoped=text
                    if quote not in scoped:raise ValueError('C摘录与来源不符：'+passage['path'])
                checked.add(key)
    return len(payload['records'])

def markdown(row,*,context):
    from .third_item_c_contract_reading import markdown_review
    p=reading_projection(row,context=context);a=row['joint_assessment']
    lines=[p['calculation']['total_label'],'',p['window'],'',p['story'],'',
        '档内位置：'+p['position_explanation'],'',
        p['responsibility'],'',p['boundary'],'',p['source_note'],'']
    for e in p['evidence_items']:
        lines+=['#### '+e['label'],'',e['kind']+'：'+e['text'],'',e['scope'],'',
            '来源：'+'；'.join(s['path'] for s in e['sources']),'']
        for s in e.get('source_passages',[]):lines+=['> '+s['quote'].replace('\n','\n> '),'']
    if p['commander_profiles']['entries']:
        lines+=['#### 将领与本任事实','',p['commander_profiles']['note'],'']
        for commander in p['commander_profiles']['entries']:
            lines+=['- '+commander['name']+' · '+commander['grade_label']+'：'+commander['qualification_text']]
            for result in commander['own_window_results']:lines+=['  - '+result['label']]
        lines+=['']
    lines+=[markdown_review(p['contract_review']),'',p['calculation']['formula'],'']
    return '\n'.join(lines)
