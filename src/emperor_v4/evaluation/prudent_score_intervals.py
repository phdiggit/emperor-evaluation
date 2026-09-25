"""Current-source, non-probabilistic score enclosures for the ranked pool.

The input registries adjudicate terminal endpoints and linked scenarios. This
module prices them with the live settlement formulas; it never edits grades.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from math import ceil, floor
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation import governance_state_recovery as gov_math

COST_REVIEW = Path('config/common/prudent-military-cost-grade-reviews.json')
GOV_REVIEW = Path('config/common/prudent-governance-grade-scenarios.json')
AXIS_REVIEW = Path('config/second-item/c1-c2-c3-low-confidence-terminal-adjudications.json')
CASES = Path('config/common/evidence-interpretation-cases.json')
THIRD = Path('docs/评分结算/净收益/第三项军事与边疆净收益/02-第三项正式结算.json')
D_STAGE = Path('docs/评分结算/净收益/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json')
STAGE_REVIEW = Path('config/common/prudent-strategic-stage-grade-reviews.json')
C4 = gov_math.FORMAL_PATHS['C4']
HANDOFF = Path('docs/评分结算/净收益/第二项治国净收益/政权交接稳定/03-交接质量20分正式结算.json')
FACTORS = Path('config/third-item/third-item-cost-credit-factors.json')
ENDPOINT_RULES = {
    'paired_endpoints_only': '只消费列出的配对端点，不拆分主档与低谷',
    'score_extrema_across_explicit_endpoints_only': '只消费列出的显式端点',
    'lower_and_upper_endpoints': '只比较列出的上下端点',
    'score_extrema_across_all_allowed_grade_loss_combinations': '仅本轴已允许的主档与低谷可组合',
}


def _needs_main_grade_review(label: object) -> bool:
    normalized = str(label).strip().upper()
    if normalized == 'HIGH' or normalized.startswith('HIGH_'):
        return False
    if normalized.startswith(('MEDIUM', 'LOW')) or normalized in {'中', '中低', '中高'}:
        return True
    raise ValueError(f'未知治理证据置信标签：{label}')


def _own_interval_rank_projection(
    records: list[dict[str, Any]], ruler_id: str, lower: float, upper: float
) -> dict[str, Any]:
    """Project one person's prudent score interval onto others' formal scores."""
    if lower > upper:
        raise ValueError('审慎分位置投影区间倒置')
    others = [
        float(row['total_score']) for row in records if row['ruler_id'] != ruler_id
    ]
    return {
        'best': 1 + sum(score > upper for score in others),
        'worst': 1 + sum(score > lower for score in others),
        'method': 'OWN_PRUDENT_INTERVAL_VS_OTHER_FORMAL_SCORES',
        'other_scores_fixed': True,
        'is_joint_rank_interval': False,
        'basis': '仅将本人现有史料审慎分数区间投影到当前正式榜，其他人物固定为正式综合分；不是联合名次置信区间。',
    }


def _declared_terminal_endpoints(final: dict[str, Any]) -> list[str]:
    """Expand only a ruling that explicitly permits grade/loss combinations."""
    primary = final['primary_endpoint']
    if final['status'] == 'FINAL_SINGLE_POINT':
        return [primary]
    raw = final['range']
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split('↔')]
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError('治理终裁审慎区间缺端点')
    mode = final['leaderboard_consumption']
    if mode in {'paired_endpoints_only','score_extrema_across_explicit_endpoints_only',
                'lower_and_upper_endpoints'}:
        return raw
    if mode != 'score_extrema_across_all_allowed_grade_loss_combinations':
        raise ValueError(f'未知治理终裁端点消费方式：{mode}')
    parsed = []
    for value in raw:
        match = re.fullmatch(r'(C[123])-([1-6])/L([0-3])(?:~L([0-3]))?', value)
        if not match:
            raise ValueError(f'治理终裁组合端点非法：{value}')
        parsed.append(match)
    axis = parsed[0][1]
    if any(match[1]!=axis for match in parsed):
        raise ValueError('治理终裁组合端点跨轴')
    bands = [int(match[2]) for match in parsed]
    losses = [int(value) for match in parsed for value in (match[3],match[4]) if value is not None]
    return [f'{axis}-{grade}/L{loss}'
            for grade in range(min(bands),max(bands)+1)
            for loss in range(min(losses),max(losses)+1)]


def _check_ref(root: Path, ref: str) -> None:
    if ref.startswith(('https://','http://')):
        return
    if not (root / ref.split('#',1)[0]).is_file():
        raise ValueError(f'审慎区间证据引用不存在：{ref}')


def _check_lineage_ref(root: Path, ref: str) -> None:
    if ref.startswith(('https://', 'http://')):
        return
    path = ref.split('#', 1)[0]
    location = path.rsplit(':', 1)
    if len(location) == 2 and location[1].isdigit():
        path = location[0]
    if not (root / path).is_file():
        raise ValueError(f'审慎区间原史源引用不存在：{ref}')


def _governance_score(rid: str, ruling: dict, c4: dict) -> float:
    axis_sum = sum(
        gov_math.state_score(a, ruling['axes'][a]['main_band'], ruling['axes'][a]['loss_review']['grade'])
        for a in gov_math.AXES
    )
    rec = ruling['recovery']
    calc = gov_math.retained_recovery(
        {a: rec['baseline'][a]['band'] for a in gov_math.AXES},
        {a: rec['terminal'][a]['band'] for a in gov_math.AXES},
        {a: rec['attribution'][a]['factor'] for a in gov_math.AXES},
    )
    deterioration = gov_math._deterioration(ruling)
    da = c4[rid]['destructive_amplification_penalty']
    c4score = gov_math._round(max(
        Decimal(str(gov_math.C4_SCORE_MIN)),
        min(Decimal(str(gov_math.C4_SCORE_MAX)),
            Decimal(str(calc['positive_retained']))-Decimal(str(deterioration))-Decimal(str(da))),
    ))
    return round(axis_sum + c4score, 1)


def _mutate(ruling: dict, axes: dict, attribution: dict) -> None:
    for axis, changes in axes.items():
        if axis not in gov_math.AXES:
            raise ValueError(f'未知治理轴：{axis}')
        state = ruling['axes'][axis]
        for key, value in changes.items():
            if key == 'loss':
                state['loss_review']['grade'] = value
            elif key in ('s0','main','end'):
                state[key+'_band'] = value
                if key == 's0': ruling['recovery']['baseline'][axis]['band'] = value
                if key == 'end': ruling['recovery']['terminal'][axis]['band'] = value
            else:
                raise ValueError(f'未知治理变更字段：{key}')
    for axis, factor in attribution.items():
        ruling['recovery']['attribution'][axis]['factor'] = factor


def _cost_delta(current_debit: float, ml: float, grade: str, position: str, factors: dict) -> float:
    candidate_debit=max(ml,80*(1-float(factors[grade][position])))
    if candidate_debit+1e-8 < current_debit:
        raise ValueError('成本上档候选使扣分变少')
    return round(current_debit-candidate_debit,2)


def _validate_stage_reviews(root: Path, ranked_ids: set[str]) -> tuple[int, int, dict[str, int]]:
    source = load_json(root / STAGE_REVIEW)
    if source.get('schema_version') != 'prudent-strategic-stage-grade-reviews-v1':
        raise ValueError('军事阶段低置信复核版本不符')
    expected = {}
    for ruler in load_json(root / D_STAGE)['records']:
        if ruler['ruler_id'] not in ranked_ids:
            continue
        for chain in ruler.get('strategic_internal_chains', []):
            for stage in chain.get('stage_result_evidence', []):
                low = {axis: value for axis, value in stage.get('axes', {}).items()
                       if value.get('confidence') is not None and _needs_main_grade_review(value['confidence'])}
                if low:
                    expected[(ruler['ruler_id'], stage['stage_ref'])] = (ruler, chain, low)
    reviews = {(r['ruler_id'], r['stage_ref']): r for r in source['records']}
    if len(reviews) != len(source['records']) or set(reviews) != set(expected):
        raise ValueError('军事阶段低置信复核未覆盖入榜对象')
    axis_count = 0
    methods: dict[str, int] = defaultdict(int)
    for key, review in reviews.items():
        ruler, chain, low = expected[key]
        if (review['parent_chain_id'], review['baseline_D_grade'], review['baseline_D_score_points']) != (
                chain['chain_id'], ruler['D_grade'], ruler['D_score_points']):
            raise ValueError(f'军事阶段审慎基准漂移：{key}')
        actual = {axis: {'grade': value['grade'], 'confidence': value['confidence']}
                  for axis, value in low.items()}
        if (review['low_confidence_axes'] != actual or not review.get('review_gate')
                or not review.get('source_refs')
                or review.get('review_method') not in {'FORMAL_STAGE_BASIS_REUSED', 'DIRECT_SOURCE_RECHECKED'}):
            raise ValueError(f'军事阶段低置信复核缺依据：{key}')
        for ref in review['source_refs']:
            _check_ref(root, ref)
        axis_count += len(low)
        methods[review['review_method']] += 1
    return len(reviews), axis_count, dict(methods)


def attach(root: Path, records: list[dict[str,Any]]) -> dict[str,int]:
    """Attach one sourced prudent interval to each ranked record."""
    root = root.resolve()
    by_id = {r['ruler_id']: r for r in records}
    if len(by_id) != len(records):
        raise ValueError('审慎区间榜单人物重复')
    if any(any('第一项成本' in note for note in r.get('evidence_assessment',{}).get('component_limitations',[])) for r in records):
        raise ValueError('第一项出现未纳入审慎区间的成本缺口')
    cost_source = load_json(root / COST_REVIEW)
    scenario_source = load_json(root / GOV_REVIEW)
    axis_source = load_json(root / AXIS_REVIEW)
    case_source = load_json(root / CASES)
    if cost_source.get('schema_version') != 'prudent-military-cost-grade-reviews-v1':
        raise ValueError('军事成本审慎范围版本不符')
    if scenario_source.get('schema_version') != 'prudent-governance-grade-scenarios-v1':
        raise ValueError('治理联动审慎范围版本不符')
    if axis_source.get('schema_version') != 'c1-c2-c3-low-confidence-terminal-adjudications-v1':
        raise ValueError('治理低置信终裁版本不符')

    third = {r['ruler_id']:r for r in load_json(root / THIRD)['records']}
    stage_review_count, stage_axis_count, stage_review_methods = _validate_stage_reviews(root, set(by_id))
    gov = {r['ruler_id']:r for r in load_json(root / gov_math.REVIEW_PATH)['records']}
    c4 = {r['ruler_id']:r for r in load_json(root / C4)['scores']}
    handoff = {r['ruler_id']:r for r in load_json(root / HANDOFF)['records']}
    factors = load_json(root / FACTORS)['factor_by_global_cost_band_and_position']
    active_cases = {c['case_id']:c for c in case_source['cases'] if c['status']=='UNRESOLVED_EVIDENCE_GAP'}

    expected_cost = {rid for rid in by_id if third[rid]['global_cost_credit_profile']['status'] in ('LOWER_BOUND','PROVISIONAL')}
    reviews = {r['ruler_id']:r for r in cost_source['records']}
    if len(reviews)!=len(cost_source['records']) or set(reviews)!=expected_cost:
        raise ValueError('军事成本审慎复核没有逐人覆盖现行下界与暂定对象')
    scenario_cases={s['case_id'] for s in scenario_source['scenarios']}
    for cid, case in active_cases.items():
        if cid in scenario_cases:
            continue
        scope=case_source['rank_envelope']['case_scopes'][cid]['affected']
        if case['ruler_id'] not in reviews or len(scope)!=1 or scope[0]['components']!=['THIRD_COST']:
            raise ValueError(f'现行未决命题未进入审慎区间：{cid}')
    cost_deltas = {rid:0.0 for rid in by_id}
    for rid, review in reviews.items():
        t = third[rid]; cost = t['global_cost_credit_profile']
        if (review['baseline_band'],review['baseline_position'],review['baseline_status']) != (
                cost['cost_band'],cost['position'],cost['status']):
            raise ValueError(f'军事成本审慎基准漂移：{rid}')
        _check_ref(root,review['source_ref'])
        if not review.get('review_gate'):
            raise ValueError(f'军事成本审慎上档缺边界：{rid}')
        grade = review['candidate_max_band']; position = review['candidate_max_position']
        if grade not in factors or position not in factors[grade]:
            raise ValueError(f'军事成本审慎候选非法：{rid}')
        current_debit=float(t['applied_military_debit_points'])
        ml=abs(float(t['military_net_loss_penalty']))
        cost_deltas[rid]=_cost_delta(current_debit,ml,grade,position,factors)

    governance_case_deltas: dict[str,dict[str,list[float]]] = defaultdict(lambda:defaultdict(list))
    scenario_count = 0
    for scenario in scenario_source['scenarios']:
        cid = scenario['case_id']
        if cid not in active_cases or scenario.get('kind') != 'PRUDENT_CONDITIONAL_REVIEW_ONLY':
            raise ValueError(f'治理审慎情景未绑定当前未决命题：{cid}')
        if not scenario.get('dependency_basis') or not scenario.get('source_refs') or not scenario.get('affected'):
            raise ValueError(f'治理审慎情景缺依据或联动：{cid}')
        for ref in scenario['source_refs']:_check_ref(root,ref)
        for mutation in scenario['affected']:
            rid=mutation['ruler_id']
            if rid not in by_id:
                raise ValueError(f'治理联动对象未入榜：{rid}')
            if 'handoff_D3_level' in mutation:
                h=handoff[rid]
                d1, d3=h['D1_level'], mutation['handoff_D3_level']
                if not isinstance(d3,int) or not 0<=d3<=5:
                    raise ValueError('D3审慎候选非法')
                cap=[4,8,12,16,20,20][min(d1,d3)]
                candidate=min(2*(d1+d3),cap)
                delta=round(candidate-float(h['score']),2)
            else:
                original=gov[rid]
                actual=sum(original['axes'][a]['state_score'] for a in gov_math.AXES)+c4[rid]['score']
                if _governance_score(rid,original,c4)!=round(actual,1):
                    raise ValueError(f'治理审慎现行数值基准漂移：{rid}')
                alternate=deepcopy(original)
                _mutate(alternate,mutation.get('axes',{}),mutation.get('recovery_attribution',{}))
                delta=round(_governance_score(rid,alternate,c4)-_governance_score(rid,original,c4),2)
            governance_case_deltas[rid][cid].append(delta)
        scenario_count+=1

    pool=load_json(root/'config/common/canonical-ruler-pool.json')['records']
    second_ids={r['ruler_id']:r['source_item_ids']['second_item'] for r in pool if r['ruler_id'] in by_id}
    formal_axes={a:{r['ruler_id']:r for r in load_json(root/path)['scores']}
                 for a,path in gov_math.FORMAL_PATHS.items() if a in gov_math.AXES}
    expected_all={(row['ruler_id'],a) for a, rows in formal_axes.items() for row in rows.values()
                  if _needs_main_grade_review(row.get('confidence',''))}
    axis_reviews={(r['ruler_id'],r['axis']):r for r in axis_source['records']}
    if (len(axis_reviews)!=len(axis_source['records']) or set(axis_reviews)!=expected_all
            or axis_source.get('record_count')!=len(axis_reviews)):
        raise ValueError('治理低置信终裁未完整覆盖正式分片')
    axis_deltas: dict[str,list[dict]] = defaultdict(list)
    method_counts: dict[str,int] = defaultdict(int)
    for (rid,axis),review in axis_reviews.items():
        final=review.get('final_adjudication',{})
        status=review.get('decision_final')
        if status not in {'FINAL_SINGLE_POINT','FINAL_PRUDENT_RANGE'} or final.get('status')!=status:
            raise ValueError(f'治理终裁状态非法：{rid}/{axis}')
        method_counts[status] += 1
        formal_row=formal_axes[axis][rid]
        if formal_row.get('low_confidence_terminal_adjudication',{}).get('final_adjudication')!=final:
            raise ValueError(f'治理终裁正式分片漂移：{rid}/{axis}')
        primary=final['primary_endpoint']
        if primary!=f"{formal_row['main_band']}/{formal_row['loss_grade']}":
            raise ValueError(f'治理终裁采用点漂移：{rid}/{axis}')
        allowed=final.get('allowed_endpoints',[])
        if (not allowed or len(allowed)!=len(set(allowed)) or primary not in allowed
                or (status=='FINAL_SINGLE_POINT' and allowed!=[primary])
                or (status=='FINAL_PRUDENT_RANGE' and len(allowed)<2)
                or allowed!=_declared_terminal_endpoints(final)):
            raise ValueError(f'治理终裁端点非法：{rid}/{axis}')
        scores={}
        for endpoint in allowed:
            grade, loss=endpoint.split('/')
            if grade not in {f'{axis}-{n}' for n in range(1,7)} or loss not in gov_math.LOSS_RATES:
                raise ValueError(f'治理终裁端点档位非法：{rid}/{axis}: {endpoint}')
            scores[endpoint]=gov_math.state_score(axis,int(grade[-1]),loss)
        if status=='FINAL_SINGLE_POINT':
            continue
        if rid not in second_ids.values():
            continue
        original=gov[rid]['axes'][axis]
        current=gov_math.state_score(axis,original['main_band'],original['loss_review']['grade'])
        if current!=scores[primary]:
            raise ValueError(f'治理终裁分值基准漂移：{rid}/{axis}')
        source_ref=f'{AXIS_REVIEW.as_posix()}#ruler_id={rid}&axis={axis}'
        axis_deltas[rid].append({
            'axis':axis,'current_grade':f'{axis}-{original["main_band"]}',
            'current_loss_grade':original['loss_review']['grade'],
            'allowed_endpoints':allowed,'endpoint_scores':scores,
            'leaderboard_consumption':final['leaderboard_consumption'],
            'endpoint_rule':ENDPOINT_RULES[final['leaderboard_consumption']],
            'conditional_delta_range':[round(min(scores.values())-current,2),round(max(scores.values())-current,2)],
            'review_gate':review['reason'],'source_ref':source_ref,
        })

    intervals=0
    for rid,row in by_id.items():
        case_deltas=governance_case_deltas[rid]
        source_id=second_ids[rid]
        gov_min=sum(min([0.0]+d) for d in case_deltas.values())+sum(x['conditional_delta_range'][0] for x in axis_deltas[source_id])
        gov_max=sum(max([0.0]+d) for d in case_deltas.values())+sum(x['conditional_delta_range'][1] for x in axis_deltas[source_id])
        base=float(row['total_score'])
        # Widen at the final precision so floating arithmetic cannot omit an endpoint.
        low=floor((base+cost_deltas[rid]+gov_min+1e-8)*100)/100
        high=ceil((base+gov_max-1e-8)*100)/100
        if not low-1e-8<=base<=high+1e-8:
            raise ValueError(f'正式分数不在审慎区间：{rid}')
        if low<high:intervals+=1
        review=reviews.get(rid)
        per_axis_methods = {axis: axis_reviews[(source_id,axis)]['decision_final']
                            for axis in gov_math.AXES if (source_id,axis) in axis_reviews}
        basis = '依低置信逐轴终裁的合法端点计算现有史料审慎区间；不是统计置信区间或未来史料的绝对界。'
        row['prudent_score_interval']={
            'lower':low,'upper':high,
            'basis':basis,
            'confidence_scope':'CURRENT_CORPUS_EVIDENCE_REVIEW_NOT_PROBABILITY',
            'governance_main_review_methods':per_axis_methods,
            'cost_review':None if review is None else {
                'current_grade':review['baseline_band']+'-'+review['baseline_position'],
                'current_evidence_status':review['baseline_status'],
                'current_cost_basis':third[rid]['global_cost_credit_profile']['basis'],
                'candidate_max_grade':review['candidate_max_band']+'-'+review['candidate_max_position'],
                'conditional_total_delta':cost_deltas[rid],
                'review_gate':review['review_gate'],'source_ref':review['source_ref'],
            },
            'linked_case_ids':sorted(case_deltas),
            'axis_reviews':axis_deltas[source_id],
            'linked_reviews':[
                {'case_id':cid,'question':active_cases[cid]['question'],
                 'basis':active_cases[cid].get('public_basis',active_cases[cid]['basis']),
                 'conditional_delta_range':[round(min([0.0]+d),2),round(max([0.0]+d),2)],
                 'source_refs':active_cases[cid]['source_refs']}
                for cid,d in sorted(case_deltas.items())
            ],
            'governance_conditional_delta_range':[round(gov_min,2),round(gov_max,2)],
            'endpoint_attainability':(
                'OUTER_ENCLOSURE_NOT_ALL_JOINT_EXTREMES_PROVEN' if low<high
                else 'SINGLE_CURRENT_CORPUS_DISPOSITION_NOT_FUTURE_SOURCE_PROOF'
            ),
        }
        row['prudent_rank_projection'] = _own_interval_rank_projection(
            records, rid, low, high
        )
        assessment=row.get('evidence_assessment',{})
        projection=assessment.get('public_projection',{})
        if projection:
            if low<high:
                label='现有史料审慎区间已列；正式分仍按当前裁决'
            elif projection.get('public_issues'):
                label='现有史料审慎单点；来源限制已说明'
            else:
                label='现有史料审慎单点'
            basis=('正式分数和名次采用当前裁决。现有史料审慎区间按逐人条件档位与联动另列；'
                   '候选端点并非已采信的替代分数，亦不生成候选名次。新增史料可以重开。')
            projection.update(score_label=label,public_basis=basis)
            assessment.update(score_label=label,public_basis=basis)
    return {'pool_count':len(records),'nonpoint_count':intervals,'cost_review_count':len(reviews),
            'low_evidence_axis_review_count':len(axis_reviews),
            'governance_axis_review_methods':dict(method_counts),
            'strategic_stage_review_count':stage_review_count,
            'strategic_stage_axis_review_count':stage_axis_count,
            'strategic_stage_review_methods':stage_review_methods,
            'governance_scenario_count':scenario_count,
            'active_case_count':len(active_cases)}
