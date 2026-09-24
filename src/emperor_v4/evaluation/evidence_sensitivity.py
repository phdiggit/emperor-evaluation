"""Read-only, discrete evidence interpretations; never estimates probabilities."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import yaml

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.governance_state_recovery import state_score

CONFIG_PATH = Path('config/common/evidence-interpretation-cases.json')
OUTPUT_JSON = Path('docs/评分结算/净收益/综合分析/02-证据裁决敏感性.json')
OUTPUT_MD = OUTPUT_JSON.with_suffix('.md')
STATUSES = {'SUPPORTED_INTERPRETATION', 'REJECTED_DIAGNOSTIC', 'UNRESOLVED_EVIDENCE_GAP'}


def public_assessment(row: dict, analysis: dict, registry: dict) -> dict:
    """Publish source-supported scenarios, never computational outer limits."""
    a = row['evidence_assessment']
    rid = row['ruler_id']
    scopes = registry['rank_envelope']['case_scopes']
    relevant = [c for c in analysis['cases'] if c['status'] != 'REJECTED_DIAGNOSTIC' and (
        c['ruler_id'] == rid or any(x['ruler_id'] == rid for x in c.get('changes', []))
        or any(x['ruler_id'] == rid for x in scopes.get(c['case_id'], {}).get('affected', [])))]
    alternatives = []
    for c in analysis['cases']:
        scenario = c.get('scenario')
        if c['status'] != 'SUPPORTED_INTERPRETATION' or scenario is None:
            continue
        if not (c in relevant or scenario['pool_ranks'][rid] != row['rank']):
            continue
        score = scenario['pool_scores'][rid]
        alternatives.append({'case_id': c['case_id'], 'question': c['question'],
            'total_score': score, 'delta': round(score - row['total_score'], 2),
            'rank': scenario['pool_ranks'][rid],
            'public_basis': c.get('public_basis', c['basis']),
            'public_limitations': c.get('public_limitations', c['limitations'])})
    reviews = a.get('grade_reviews', [])
    review_by_id = {r['case_id']:r for r in reviews}
    issues = [{'question':c['question'], 'basis':c.get('public_basis',c['basis']),
               'limitations':c.get('public_limitations',c['limitations']) + (
                   ' 档位复核：'+review_by_id[c['case_id']]['display']+' '
                   +review_by_id[c['case_id']]['basis']+' '
                   +review_by_id[c['case_id']].get('conditional_effect_text','')
                   if c['case_id'] in review_by_id else '')} for c in relevant
              if c['status'] == 'UNRESOLVED_EVIDENCE_GAP']
    cost_limits = a.get('component_limitations', [])
    for limit in cost_limits:
        label, status = limit.split('：', 1)
        issues.append({'question':label+'的证据限制',
            'basis':('现有材料已证明当前成本下界，更高档的准入仍须补证。' if status == 'LOWER_BOUND'
                     else '当前成本为暂定裁决，其窗口、对象或归责仍有待核对。'),
            'limitations':'未形成可量化的替代裁决，不据此推定综合分可在整个合同范围内浮动。'})
    closed = bool(a.get('closure_ids'))
    if closed and issues:
        raise ValueError('完整范围声明仍有直接或联动证据缺口')
    projection = {
        'score_status':a['score_status'] if closed else ('SPECIFIC_EVIDENCE_GAPS' if issues else 'ADOPTED_SCORE'),
        'score_label':a['score_label'] if closed else ('按当前裁决列分；有具体待核事项' if issues else '按当前裁决列分'),
        'rank_status':a['rank_status'] if closed or alternatives else 'ADOPTED_RANK',
        'rank_label':a['rank_label'] if closed or alternatives else '当前裁决名次',
        'verified_score_range':a.get('verified_score_range') if closed else None,
        'verified_rank_range':a.get('verified_rank_range') if closed else None,
        'supported_alternatives':alternatives, 'public_issues':issues,
        'grade_reviews':reviews,
        'public_basis':a['public_basis'] if closed else (
            '正式分数和名次采用当前裁决。仅列有史源支持且联动已核对的替代裁决及其分差；'
            + ('所列情景不代表全部可能裁决。' if alternatives else '当前未列出可量化的合法替代裁决。')
            + '未量化的具体缺口不转换成分数波动，也不表示名次已被证明不稳定。'),
    }
    return projection


def analyze(records: list[dict], governance: dict[str, dict], cases: list[dict]) -> dict:
    """Reprice explicit state rulings; linked endpoint changes fail closed.

    Admissibility is a sourced semantic ruling supplied in cases, not inferred by
    this program. Absence of an alternate is not a zero-width confidence range.
    """
    indexed = {r['ruler_id']: r for r in records}
    if len(indexed) != len(records) or len({c['case_id'] for c in cases}) != len(cases):
        raise ValueError('重复人物或解释ID')
    results = []
    for case in cases:
        rid = case['ruler_id']
        if rid not in indexed:
            raise ValueError('解释对象不在当前入榜池')
        if case['status'] not in STATUSES or not all(case.get(k) for k in ('question', 'basis', 'source_refs', 'limitations')):
            raise ValueError('解释缺少处置、依据或范围限制')
        if case['status'] == 'UNRESOLVED_EVIDENCE_GAP' and case.get('changes'):
            raise ValueError('未决证据缺口不能生成数值情景')
        totals = {key: float(r['total_score']) for key,r in indexed.items()}
        deltas: dict[str, float] = {}
        consumed = set()
        calculations = []
        for change in case.get('changes', []):
            target, axis = change['ruler_id'], change['axis']
            if change.get('kind') != 'GOVERNANCE_MAIN_AND_LOSS' or set(change) != {
                'kind', 'ruler_id', 'axis', 'baseline', 'alternative', 'dependency_basis', 'deduplication_basis'
            }:
                raise ValueError('未支持的计算对象或未闭合的联动字段')
            if target not in indexed or (target,axis) in consumed:
                raise ValueError('情景对象不在入榜池或同轴重复计入')
            if not change['dependency_basis'] or not change['deduplication_basis']:
                raise ValueError('缺少端点不变及主态低谷去重依据')
            consumed.add((target,axis))
            state = governance[target]['axes'][axis]
            expected = {k:state[k] for k in ('s0_band','main_band','end_band')}
            expected['loss_grade'] = state['loss_review']['grade']
            if change['baseline'] != expected:
                raise ValueError(f'解释基准已变，须复核：{case["case_id"]}/{target}/{axis}')
            alternative = change['alternative']
            if set(alternative) != {'main_band','loss_grade'}:
                raise ValueError('端点或归责变化须联合重裁，不允许局部换分')
            before = state_score(axis, expected['main_band'], expected['loss_grade'])
            after = state_score(axis, alternative['main_band'], alternative['loss_grade'])
            if before != state['state_score']:
                raise ValueError('当前治理源与计算不同值')
            delta = round(after-before,1)
            deltas[target] = round(deltas.get(target,0)+delta,1)
            calculations.append({**deepcopy(change),'baseline_axis_score':before,'alternative_axis_score':after,'delta':delta})
        for target,delta in deltas.items():
            row=indexed[target]
            first=float(row.get('first_item_raw_score') or 0)
            addon=0.20*637*(first/240)**1.25 if first>0 else 0
            totals[target]=round(float(row['second_item_score'])+delta+float(row['third_item_score'])+addon+float(row['fourth_item_adjustment']),2)
        numeric = bool(calculations)
        if numeric and rid not in deltas:
            raise ValueError('情景必须包含所评人物；其他人物影响见统一重排名')
        ranks = {key:1+sum(other>score for other in totals.values()) for key,score in totals.items()} if numeric else {}
        results.append({
            **deepcopy(case), 'ruler_name':indexed[rid]['ruler_name'],
            'baseline':{'total_score':indexed[rid]['total_score'],'rank':indexed[rid]['rank']},
            'calculations':calculations,
            'scenario':{'total_score':totals[rid],'rank':ranks[rid],
                        'pool_scores': totals, 'pool_ranks': ranks,
                        'rank_changes':[{'ruler_id':key,'baseline_rank':indexed[key]['rank'],'scenario_rank':ranks[key]}
                                        for key in sorted(ranks) if ranks[key]!=indexed[key]['rank']]} if numeric else None,
        })
    rows=[]
    for row in records:
        selected=[r for r in results if r['ruler_id']==row['ruler_id']]
        supported=[r for r in selected if r['status']=='SUPPORTED_INTERPRETATION' and r['scenario'] is not None]
        scores=[row['total_score']]+[r['scenario']['total_score'] for r in supported]
        ranks=[row['rank']]+[r['scenario']['rank'] for r in supported]
        rows.append({'ruler_id':row['ruler_id'],'ruler_name':row['ruler_name'],
                     'case_ids':[r['case_id'] for r in selected],
                     'local_supported_total_range':[min(scores),max(scores)] if supported else None,
                     'local_supported_rank_range':[min(ranks),max(ranks)] if supported else None,
                     'quantification':'LISTED_LOCAL_SCENARIOS_ONLY' if supported else 'NOT_QUANTIFIED'})
    return {'schema_version':'evidence-sensitivity-v1','non_scoring':True,'confidence_interval':False,
            'scope':'LISTED_SCENARIOS_OTHER_RULINGS_AND_WEIGHTS_FIXED',
            'pool_count':len(records),'records':rows,'cases':results}


def rank_assessments(records: list[dict], analysis: dict, closures: list[dict]) -> dict:
    """Assess enumerated admissible joint worlds, never independent score extrema.

    Exhaustiveness is an explicit sourced adjudication, not inferred from the
    number of cases. The complete baseline score vector prevents stale proofs.
    """
    indexed = {r['ruler_id']: r for r in records}
    cases = {c['case_id']: c for c in analysis['cases']}
    result = {}
    for rid, row in indexed.items():
        relevant = [c for c in cases.values() if c['ruler_id'] == rid or
                    any(x['ruler_id'] == rid for x in c.get('changes', []))]
        gaps = [c['case_id'] for c in relevant if c['status'] == 'UNRESOLVED_EVIDENCE_GAP']
        supported = [c for c in cases.values() if c['status'] == 'SUPPORTED_INTERPRETATION' and c['scenario']]
        ranks = [row['rank']] + [c['scenario']['pool_ranks'][rid] for c in supported]
        changed = min(ranks) != max(ranks)
        result[rid] = {
            'score_status': 'OPEN_EVIDENCE' if gaps else 'NO_COMPLETE_CLOSURE_DECLARED',
            'score_label': '存在未决证据' if gaps else '未声明完整分数边界',
            'rank_status': 'VARIES_IN_SUPPORTED_SCENARIOS' if changed else 'NOT_ESTABLISHED',
            'rank_label': '已证合法情景内名次有变' if changed else '名次稳健性未判定',
            'observed_rank_range': [min(ranks), max(ranks)] if supported else None,
            'verified_rank_range': None, 'verified_score_range': None,
            'gap_case_ids': gaps, 'case_ids': [c['case_id'] for c in relevant],
            'public_issues': [{'question':c['question'], 'basis':c.get('public_basis',c['basis']), 'limitations':c.get('public_limitations',c['limitations'])}
                              for c in relevant if c['status'] != 'REJECTED_DIAGNOSTIC'],
            'scope': 'LISTED_SCENARIOS_ONLY', 'closure_ids': [],
            'public_basis': '名次依据当前裁决快照；未量化或已列情景同名次，都不等于已证明稳定。',
        }
    seen = set()
    for closure in closures:
        cid = closure['closure_id']
        if cid in seen:
            raise ValueError('重复覆盖声明')
        seen.add(cid)
        scope = closure['scope']
        targets = closure['ruler_ids']
        if scope not in {'LOCAL', 'JOINT_POOL'} or not targets or len(set(targets)) != len(targets):
            raise ValueError('覆盖范围不合法')
        if not set(targets) <= indexed.keys() or (scope == 'LOCAL' and len(targets) != 1):
            raise ValueError('本人局部覆盖只能包含一人')
        if scope == 'JOINT_POOL' and set(targets) != set(indexed):
            raise ValueError('联合稳健性须覆盖全池竞争者；不得默认为其他人固定')
        if closure.get('enumeration_complete') is not True or not all(closure.get(k) for k in ('coverage_basis', 'dependency_basis', 'source_refs')):
            raise ValueError('缺少完整合法情景覆盖及依赖依据')
        if closure.get('baseline_totals') != {k:r['total_score'] for k,r in indexed.items()}:
            raise ValueError('覆盖声明的全池基准已变，须复核')
        selected_ids = closure['case_ids']
        if len(set(selected_ids)) != len(selected_ids) or any(k not in cases for k in selected_ids):
            raise ValueError('覆盖情景重复或不存在')
        selected = [cases[k] for k in selected_ids]
        if any(c['status'] != 'SUPPORTED_INTERPRETATION' or not c['scenario'] for c in selected):
            raise ValueError('未决或排除假设不能用于完整范围证明')
        if any(result[rid]['gap_case_ids'] for rid in targets):
            raise ValueError('仍有未量化缺口，不能声明完整范围')
        relevant_ids = {c['case_id'] for c in cases.values() if c['status'] == 'SUPPORTED_INTERPRETATION' and
                        (c['ruler_id'] in targets or any(x['ruler_id'] in targets for x in c.get('changes', [])))}
        if set(selected_ids) != relevant_ids:
            raise ValueError('覆盖声明遗漏合法解释')
        if scope == 'LOCAL' and any(x['ruler_id'] not in targets for c in selected for x in c['changes']):
            raise ValueError('联动情景不能冒称仅改变本人')
        for rid in targets:
            assessment = result[rid]
            if assessment['closure_ids']:
                raise ValueError('同一人物只保留一个当前覆盖声明')
            ranks = [indexed[rid]['rank']] + [c['scenario']['pool_ranks'][rid] for c in selected]
            scores = [indexed[rid]['total_score']] + [c['scenario']['pool_scores'][rid] for c in selected]
            stable = min(ranks) == max(ranks)
            assessment.update(
                score_status='BOUNDED_SUPPORTED_SPACE', score_label='已闭合合法情景分数范围',
                rank_status=(scope + '_STABLE') if stable else 'VARIES_IN_COMPLETE_SPACE',
                rank_label=('本人裁决变化不影响当前名次' if scope == 'LOCAL' else '全池合法联动范围内名次稳定') if stable else '完整合法情景内名次有变',
                verified_rank_range=[min(ranks), max(ranks)], verified_score_range=[min(scores), max(scores)],
                scope=scope, closure_ids=[cid],
                public_basis=closure['coverage_basis'] + '；' + closure['dependency_basis'],
            )
    return result


def annotate_ranking(root: Path, records: list[dict], pool: list[dict], details: dict) -> dict:
    """Attach non-scoring, upstream public conclusions without build recursion."""
    registry = load_json(root / CONFIG_PATH)
    if any(c['status'] != 'REJECTED_DIAGNOSTIC' and not all(c.get(k) for k in ('public_basis','public_limitations')) for c in registry['cases']):
        raise ValueError('对外证据说明必须在正式解释源显式保存')
    for entry in registry['cases'] + registry.get('coverage_closures', []):
        for ref in entry.get('source_refs', []):
            if not ref.startswith(('https://', 'http://')) and not (root / ref.split('#', 1)[0]).is_file():
                raise ValueError(f'证据或覆盖依据不存在：{ref}')
    gov = load_json(root / 'config/second-item/governance-state-recovery-adjudications.json')['records']
    by_id = {r['ruler_id']: r for r in gov}
    mapped = {r['ruler_id']: by_id[r['source_item_ids']['second_item']] for r in pool if r['ruler_id'] in {x['ruler_id'] for x in records}}
    analysis = analyze(records, mapped, registry['cases'])
    assessments = rank_assessments(records, analysis, registry.get('coverage_closures', []))
    pool_by_id = {r['ruler_id']:r for r in pool}
    from emperor_v4.evaluation.canonical_ruler_pool import canonical_item_name
    for row in records:
        person = pool_by_id[row['ruler_id']]
        first_name = canonical_item_name('first_item',(person.get('source_item_names') or {}).get('first_item') or person['ruler_name'])
        first = details['first_cost'].get(first_name) or {}
        third = details['third'][person['source_item_ids']['third_item']]['global_cost_credit_profile']
        limits = [f'{label}：{status}' for label,status in (
            ('第一项成本',first.get('evidence_status')), ('第三项成本',third.get('status')))
            if status in {'LOWER_BOUND','PROVISIONAL'}]
        assessment = assessments[row['ruler_id']]
        assessment['component_limitations'] = limits
        if limits:
            if assessment['closure_ids']:
                raise ValueError('现数值适配器不能覆盖仍未闭合的军事成本边界')
            assessment.update(score_status='OPEN_EVIDENCE',score_label='存在未闭合证据边界')
            assessment['public_basis'] += ' 当前军事成本仍有下界或暂定限制，完整取值范围尚未闭合；成本下界不等于综合分下界。'
        row['evidence_assessment'] = assessment
    from emperor_v4.evaluation.rank_envelope import apply
    apply(root, records, pool, details, registry)
    for row in records:
        a = row['evidence_assessment']
        from emperor_v4.evaluation.evidence_grade_review import project_review, review_baseline, validate_baselines
        rid = row['ruler_id']
        a['grade_reviews'] = []
        for case in analysis['cases']:
            review = case.get('grade_review')
            targets = registry['rank_envelope']['case_scopes'].get(case['case_id'],{}).get('affected',[])
            if not review or not (case['ruler_id']==rid or any(t['ruler_id']==rid for t in targets)):
                continue
            source_person = pool_by_id[case['ruler_id']]
            source_third = details['third'][source_person['source_item_ids']['third_item']]
            target_ids={case['ruler_id']}|{t['ruler_id'] for t in targets}
            actual_baselines={key:review_baseline(mapped[key],details['third'][pool_by_id[key]['source_item_ids']['third_item']],details['handoff'][pool_by_id[key]['source_item_ids']['second_item']]) for key in sorted(target_ids)}
            validate_baselines(review.get('baseline_by_ruler',{}),actual_baselines)
            public_review = project_review(review, source_third)
            public_review.pop('baseline_by_ruler',None)
            a['grade_reviews'].append({'case_id':case['case_id'], 'question':case['question'],
                'source_refs':case['source_refs'], **public_review})
        projection = public_assessment(row, analysis, registry)
        a['public_projection'] = projection
        # All published labels have one upstream authority, separate from diagnostics.
        a.update({k:projection[k] for k in ('score_label','rank_label','public_basis','public_issues')})
    return assessments


def build(root: Path) -> dict:
    from emperor_v4.evaluation.composite_ranking import verify_composite_ranking
    from emperor_v4.evaluation.composite_details import load_detail_sources, SOURCES
    from emperor_v4.evaluation.canonical_ruler_pool import canonical_item_name
    verify_composite_ranking(root)
    project=yaml.safe_load((root/'config/project.yml').read_text(encoding='utf-8'))
    records=load_json(root/project['scoring_contract']['composite_ranking_json'])['records']
    pool=load_json(root/project['canonical_ruler_pool']['json'])['records']
    gov=load_json(root/project['formal_settlements']['second_item']['adopted_next_result_mechanism']['adjudications'])['records']
    by_id={r['ruler_id']:r for r in gov}
    mapped={r['ruler_id']:by_id[r['source_item_ids']['second_item']] for r in pool if r['settlement_readiness']=='COMPOSITE_READY'}
    cases=load_json(root/CONFIG_PATH)['cases']
    for case in cases:
        for ref in case['source_refs']:
            if ref.startswith(('https://','http://')):
                continue  # Source verification is semantic; execution stays offline.
            source, _, fragment = ref.partition('#')
            if not (root/source).is_file():
                raise ValueError(f'证据引用不存在：{ref}')
            if fragment.startswith('ruler_id=') and source.endswith('.json'):
                payload=load_json(root/source)
                rows=payload.get('records',payload.get('scores',[]))
                if not any(r.get('ruler_id')==fragment.split('=',1)[1] for r in rows):
                    raise ValueError(f'证据人物锚不存在：{ref}')
    result=analyze(records,mapped,cases)
    assessments={r['ruler_id']:r['evidence_assessment'] for r in records}
    prudent_intervals={r['ruler_id']:r['prudent_score_interval'] for r in records}
    details=load_detail_sources(root)
    pool_by_id={r['ruler_id']:r for r in pool}
    for row in result['records']:
        row['evidence_assessment']=assessments[row['ruler_id']]
        row['prudent_score_interval']=prudent_intervals[row['ruler_id']]
        person=pool_by_id[row['ruler_id']]; ids=person['source_item_ids']
        first_name=canonical_item_name('first_item',(person.get('source_item_names') or {}).get('first_item') or person['ruler_name'])
        first=details['first_cost'].get(first_name)
        cost=details['third'][ids['third_item']]['global_cost_credit_profile']
        fourth=details['fourth'][ids['fourth_item']]
        row['existing_evidence_annotations']={
            'governance_main_grades':{axis:mapped[row['ruler_id']]['axes'][axis]['main_band'] for axis in ('C1','C2','C3')},
            'military_net_loss_grade':details['third'][ids['third_item']]['military_net_loss_grade'],
            'third_item_cost_grade':cost['cost_band']+'-'+cost['position'],
            'first_item_cost_evidence_status':first.get('evidence_status') if first else 'NOT_APPLICABLE',
            'first_item_cost_unresolved_gaps':first.get('unresolved_gaps',[]) if first else [],
            'governance_confidence_as_recorded':{axis:details[axis][ids['second_item']].get('confidence') for axis in ('C1','C2','C3')},
            'third_item_cost_status':cost['status'],
            'third_item_cost_basis':cost['basis'],
            'fourth_item_coverage_as_recorded':{
                a['axis']:list(dict.fromkeys(e['public_source_coverage'] for e in a.get('public_evidence_items',[]) if e.get('public_source_coverage')))
                for a in fourth['axis_results']},
            'source_refs':{axis:SOURCES[axis]+'#ruler_id='+ids['second_item'] for axis in ('C1','C2','C3')}
                | {'third':SOURCES['third']+'#ruler_id='+ids['third_item'],'fourth':SOURCES['fourth']+'#ruler_id='+ids['fourth_item']},
        }
    return result


def render(payload: dict) -> str:
    labels={'SUPPORTED_INTERPRETATION':'证据允许解释','REJECTED_DIAGNOSTIC':'已排除假设','UNRESOLVED_EVIDENCE_GAP':'尚未闭合的证据问题'}
    lines=['# 证据裁决敏感性','',
           '本页只展示已登记的证据解释。全池列示不表示全池历史不确定性已量化；未量化不显示为零跨度。局部情景固定其他裁决与权重，不是统计置信区间，不构造综合置信度折扣。', '',
           f'当前入榜池：{payload["pool_count"]}人；证据解释按下列具体命题呈现。', '']
    for case in payload['cases']:
        lines += [f'## {case["ruler_name"]}：{case["question"]}', '',f'性质：{labels[case["status"]]}。', '',case.get('public_basis',case['basis']),'',f'限制：{case.get("public_limitations",case["limitations"])}','']
        if case['status'] == 'SUPPORTED_INTERPRETATION' and case['scenario']:
            base,alt=case['baseline'],case['scenario']
            lines += [f'基准{base["total_score"]:.2f}分、第{base["rank"]}；本情景{alt["total_score"]:.2f}分、第{alt["rank"]}。','']
            for change in case['calculations']:
                lines += [f'- {change["ruler_id"]} {change["axis"]}：{change["baseline_axis_score"]:.1f}→{change["alternative_axis_score"]:.1f}；联动：{change["dependency_basis"]}；去重：{change["deduplication_basis"]}。']
            lines += ['']
        elif case['status'] == 'REJECTED_DIAGNOSTIC':
            lines += ['该假设已排除，不列作可接受的替代分数或名次。','']
        else:
            lines += ['正式分数维持当前裁决；具体候选见下表。候选尚未成为合法替代，不据此改名次。','']
        lines += ['依据：'+ '；'.join(f'[{ref}]({ref if ref.startswith("http") else "../../../../"+ref})' for ref in case['source_refs']), '']
    lines += ['## 逐人当前档与有限复核候选','',
              '当前档直接读取正式源。审慎区间按现有史料中逐人排除后的候选及共享联动计算，不是统计覆盖率，也不保证未来新史料不能重开。非单点端点可能无法同时实现；单点不证明历史真值唯一。', '',
              '| 人物 | 当前C1／C2／C3主态 | 当前军事成本／净毁损 | 具体复核档位 | 现有史料审慎总分区间 |',
              '|---|---|---|---|---:|']
    for row in payload['records']:
        annotation=row.get('existing_evidence_annotations',{})
        mains=annotation.get('governance_main_grades',{})
        reviews=row.get('evidence_assessment',{}).get('public_projection',{}).get('grade_reviews',[])
        labels='；'.join(r['display'] for r in reviews) or '本轮未提出有源异档；采用左列当前档，来源限制另列。'
        interval=row.get('prudent_score_interval')
        cost_review=interval.get('cost_review') if interval else None
        if cost_review:
            labels += f'；成本现{cost_review["current_grade"]}、审慎复核至{cost_review["candidate_max_grade"]}：{cost_review["review_gate"]}'
        if interval:
            labels += ''.join(
                f'；{x["axis"]}现{x["current_grade"]}/{x["current_loss_grade"]}、复核{x["candidate_grade"]}/{x["candidate_loss_grade"]}：{x["review_gate"]}'
                for x in interval.get('axis_reviews',[]) if x['current_grade']!=x['candidate_grade'] or x['current_loss_grade']!=x['candidate_loss_grade']
            )
        display_range=(f'{interval["lower"]:.2f}—{interval["upper"]:.2f}' if interval else '尚未逐人复核')
        lines.append(f'| {row["ruler_name"]} | {"／".join(str(mains.get(a,"—")) for a in ("C1","C2","C3"))} | {annotation.get("third_item_cost_grade","—")}／{annotation.get("military_net_loss_grade","—")} | {labels} | {display_range} |')
    lines += ['', '### 军事净毁损条件分差', '',
              '只改变列示净毁损档，保持普通成本与其他分项不变；未采信的候选不生成替代名次，也不与其他争议极值叠加。', '',
              '| 人物 | 复核候选 | 条件分差 | 高档排除与责任边界 |', '|---|---|---|---|']
    for row in payload['records']:
        for review in row.get('evidence_assessment',{}).get('public_projection',{}).get('grade_reviews',[]):
            if review['kind']=='MILITARY_NET_LOSS':
                lines.append(f'| {row["ruler_name"]} | {review["display"]} | {review["conditional_effect_text"]} | {review["basis"]} {review["excluded_basis"]} |')
    lines += ['', '## 分项史源标签','',
              '未量化表示尚未形成有史源支持的数值替代，不等于真实分数可在合同全域浮动。合同极限及名次外界只用于内部排除检验，不作为公开分数范围。','',
              '下表逐人读取现行正式入口的证据标签，不把这些标签转换成概率，也不把自动汇集当作逐项史源复审通过。不同组件标签的定义不同；CONFIRMED不是高置信度排名，LOWER_BOUND表示成本下界，NOT_APPLICABLE不是零成本。治理标签原样保留，不擅自合并状态与归责的置信度。', '',
              '| 人物 | 第一项成本证据 | 治理C1／C2／C3原标签 | 第三项成本证据 | 本人局部证据情景名次范围 |',
              '|---|---|---|---|---|']
    for row in payload['records']:
        bounds=row['local_supported_rank_range']
        annotation=row.get('existing_evidence_annotations',{})
        confidence=annotation.get('governance_confidence_as_recorded',{})
        lines.append(f'| {row["ruler_name"]} | {annotation.get("first_item_cost_evidence_status") or "未记录"} | {"／".join(str(confidence.get(a) or "未记录") for a in ("C1","C2","C3"))} | {annotation.get("third_item_cost_status") or "未记录"} | {str(bounds[0])+"—"+str(bounds[1]) if bounds else "采用当前名次；候选未作合法替代"} |')
    lines += ['', '## 当前裁决与证据说明', '',
              '未判定不等于不稳定；完整本人范围与完整全池联动范围分别声明，不将互斥情景的分项极值拼接。', '',
              '| 人物 | 分数边界 | 名次稳健性 |', '|---|---|---|']
    for row in payload['records']:
        assessment=(row.get('evidence_assessment') or {}).get('public_projection')
        if assessment:
            lines.append(f'| {row["ruler_name"]} | {assessment["score_label"]} | {assessment["rank_label"]} |')
    return '\n'.join(lines)+'\n'


def run(root: Path, *, write: bool=False) -> dict:
    payload=build(root)
    markdown=render(payload)
    if write:
        (root/OUTPUT_JSON).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
        (root/OUTPUT_MD).write_text(markdown,encoding='utf-8',newline='\n')
    elif load_json(root/OUTPUT_JSON)!=payload or (root/OUTPUT_MD).read_text(encoding='utf-8')!=markdown:
        raise ValueError('证据裁决敏感性未同步；运行evidence-sensitivity --write')
    return {'status':'PASS','non_scoring':True,'pool_count':payload['pool_count'],'case_count':len(payload['cases'])}
