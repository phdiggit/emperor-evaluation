"""Conservative rank certificates over a superset of registered disputes.

Envelope endpoints are contract limits, NOT admissible historical rulings.
Allowing impossible joint combinations only widens this set: disjoint rank
proofs remain sound; overlap is inconclusive and never a witness of instability.
"""
from pathlib import Path
from math import floor, ceil

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.canonical_ruler_pool import canonical_item_name
from emperor_v4.evaluation.governance_state_recovery import FIXED_POINTS, C4_SCORE_MIN, C4_SCORE_MAX


def handoff_enclosure(current: dict, review: dict) -> tuple[float, float]:
    """Exclude sourced D3 outcomes while preserving the reviewed D1 ruling."""
    if review.get('baseline') != {k: current[k] for k in ('D1_level', 'D3_level')}:
        raise ValueError('交接排除依据的基准已变，须复核')
    if not all(review.get(k) for k in ('source_refs', 'dependency_basis', 'public_basis')):
        raise ValueError('交接档位排除缺少史源及依赖依据')
    excluded = review.get('excluded_d3_levels', {})
    if not excluded or not set(excluded) <= {str(i) for i in range(6)} or not all(excluded.values()):
        raise ValueError('交接排除档位不合法或缺少逐档依据')
    if str(current['D3_level']) in excluded:
        raise ValueError('已排除当前裁决，须先修正正式评分')
    d1 = current['D1_level']
    caps = [4, 8, 12, 16, 20, 20]
    values = [min(2 * (d1 + d3), caps[min(d1, d3)])
              for d3 in range(6) if str(d3) not in excluded]
    return float(min(values)), float(max(values))


def certify(bounds: dict[str, tuple[float, float]]) -> dict:
    for lo, hi in bounds.values():
        if lo > hi:
            raise ValueError('Invalid score enclosure')
    return {
        rid: {
            'best_possible_rank_bound': 1 + sum(a > hi for key,(a,b) in bounds.items() if key != rid),
            'worst_possible_rank_bound': 1 + sum(b > lo for key,(a,b) in bounds.items() if key != rid),
        }
        for rid,(lo,hi) in bounds.items()
    }


def apply(root: Path, records: list[dict], pool: list[dict], details: dict, registry: dict) -> None:
    """Hold unchallenged adopted rulings fixed; widen all declared consumers."""
    from emperor_v4.evaluation.composite_ranking import FIRST_ITEM_ADD_ON_COEFFICIENT
    indexed = {r['ruler_id']:r for r in records}
    pool_index = {r['ruler_id']:r for r in pool}
    scopes = registry['rank_envelope']['case_scopes']
    active = {c['case_id']:c for c in registry['cases'] if c['status']=='UNRESOLVED_EVIDENCE_GAP'}
    if set(scopes) != set(active):
        raise ValueError('未决问题必须精确登记保守检验范围及全部联动对象')
    affected = {rid:{} for rid in indexed}
    for cid, scope in scopes.items():
        if not scope.get('dependency_basis') or not scope.get('affected'):
            raise ValueError('缺少未决问题的消费及联动依据')
        if active[cid]['ruler_id'] not in {x['ruler_id'] for x in scope['affected']}:
            raise ValueError('争议范围遗漏本人')
        for target in scope['affected']:
            rid = target['ruler_id']
            if rid not in indexed:
                raise ValueError('争议影响对象不在当前排名池')
            if not target['components']:
                raise ValueError('争议影响组件不能为空')
            for component in target['components']:
                affected[rid].setdefault(component, []).append(cid)
    first_mapping = load_json(root/'config/first-item/military-cost-debits.json')
    third_mapping = load_json(root/'config/third-item/third-item-cost-credit-factors.json')
    first_max = float(first_mapping['max_debit_points'])
    third_max = float(third_mapping['cost_debit_base_points'])
    bounds = {}
    for rid, row in indexed.items():
        person=pool_index[rid]; ids=person['source_item_ids']; sid=ids['second_item']
        name=canonical_item_name('first_item',(person.get('source_item_names') or {}).get('first_item') or person['ruler_name'])
        first=details['first_cost'].get(name) or {}
        third=details['third'][ids['third_item']]
        cost=third['global_cost_credit_profile']
        for component, status in [('FIRST_COST',first.get('evidence_status')),('THIRD_COST',cost.get('status'))]:
            if status in {'LOWER_BOUND','PROVISIONAL'}:
                affected[rid].setdefault(component, []).append('FORMAL_'+component+'_'+status)
        base=(float(row['second_item_score'])+float(row['third_item_score'])+float(row['fourth_item_adjustment'])
              +FIRST_ITEM_ADD_ON_COEFFICIENT*637*(float(row['first_item_raw_score'] or 0)/240)**1.25)
        lower=upper=base; terms=[]
        for component, causes in affected[rid].items():
            if component in FIXED_POINTS:
                current=float(details[component][sid]['score'])
                lo,hi=FIXED_POINTS[component][0],FIXED_POINTS[component][-1]
            elif component=='C4':
                current=float(details['C4'][sid]['score']); lo,hi=C4_SCORE_MIN,C4_SCORE_MAX
            elif component=='HANDOFF':
                current=float(details['handoff'][sid]['score']); lo,hi=0.0,20.0
                reviews = [target['handoff_exclusions'] for cid in causes
                           for target in scopes[cid]['affected']
                           if target['ruler_id'] == rid and target.get('handoff_exclusions')]
                if reviews:
                    if len(causes) != 1 or len(reviews) != 1:
                        raise ValueError('多重交接争议须联合复核，不能独立套用档位排除')
                    lo,hi=handoff_enclosure(details['handoff'][sid],reviews[0])
            elif component=='FIRST_COST':
                if row['first_item_status']!='APPLICABLE':
                    raise ValueError('不适用人物不能调整第一项成本')
                raw=details['first'][name]
                gross=float(raw['gross']); debit=float(raw['cost_debit'])
                minimum=debit if first.get('evidence_status')=='LOWER_BOUND' else 0.0
                def addon(x): return FIRST_ITEM_ADD_ON_COEFFICIENT*637*(max(0,x)/240)**1.25
                current=addon(gross-debit);lo=addon(gross-first_max);hi=addon(gross-minimum)
            elif component=='THIRD_COST':
                current=-float(third['applied_military_debit_points'])
                minimum=float(third['cost_debit_points']) if cost['status']=='LOWER_BOUND' else 0.0
                # ML and ordinary debit share a maximum; never add them twice.
                minimum=max(minimum,abs(float(third['military_net_loss_penalty'])))
                lo,hi=-third_max,-minimum
            else:
                raise ValueError('未知保守检验组件：'+component)
            if not lo-0.01 <= current <= hi+0.01:
                raise ValueError('当前分数不在合同边界内：'+rid+'/'+component)
            lower+=lo-current;upper+=hi-current
            terms.append({'component':component,'baseline':current,'contract_outer_bounds':[lo,hi],'causes':causes})
            if component=='HANDOFF' and reviews:
                terms[-1]['evidence_exclusions']=reviews[0]
        # Bounds enclose the rounded score as well, including nonlinear F.
        lo=floor((lower+1e-8)*100)/100 if terms else float(row['total_score'])
        hi=ceil((upper-1e-8)*100)/100 if terms else float(row['total_score'])
        bounds[rid]=(lo,hi)
        assessment=row['evidence_assessment']
        assessment['contract_envelope']={
            'score_outer_bounds':[lo,hi], 'terms':terms,
            'is_admissible_score_interval':False,
            'scope':'REGISTERED_DISPUTES_AND_COST_INTENSITY_OTHER_ADOPTED_RULINGS_FIXED',
        }
    ranks=certify(bounds)
    for rid,row in indexed.items():
        a=row['evidence_assessment'];envelope=a['contract_envelope'];proof=ranks[rid]
        envelope.update(proof)
        stable=proof['best_possible_rank_bound']==proof['worst_possible_rank_bound']==row['rank']
        own_fixed=not envelope['terms']
        lo,hi=bounds[rid]
        local_best=1+sum(float(other['total_score'])>hi for other in records if other['ruler_id']!=rid)
        local_worst=1+sum(float(other['total_score'])>lo for other in records if other['ruler_id']!=rid)
        envelope['local_rank_outer_bounds']=[local_best,local_worst]
        envelope['potential_competitor_ids']=[other_id for other_id,(other_lo,other_hi) in bounds.items()
            if other_id!=rid and not (other_lo>hi or other_hi<lo)
            and (lo!=hi or other_lo!=other_hi)]
        envelope['purpose']='INTERNAL_EXCLUSION_CHECK_ONLY'
        envelope['public_display']=False
        envelope['rank_proven_within_registered_enclosure']=stable
        envelope['own_rulings_fixed']=own_fixed
