"""Current C1-led joint judgment and deterministic score projection."""
from decimal import Decimal, ROUND_HALF_UP
import re

SCHEMA = 'third-item-c-joint-assessment-v1'
BANDS = ((0,29),(30,44),(45,59),(60,74),(75,89),(90,100))
POSITIONS = {'LOW': Decimal('.25'), 'MID': Decimal('.50'), 'HIGH': Decimal('.75')}
RETIRED_FIELDS = {
    'operational_sustainability_cap','system_reliability_cap','axis_floor_grade','gate_cap',
    'c5_axis_gate','c5_axis_revalidation','major_victory_gate','major_victory_gate_chain_view',
    'C_score_support_surplus','C_score_axis_surplus_position','C_score_outcome_position',
    'raw_grade','C_overall_grade',
    'c5_scarcity_gate','major_victory_gate_adjudication',
}

def grade(value):
    if value == 'UNKNOWN': return None
    match = re.fullmatch(r'C(?:1)?-([0-5])', str(value))
    if not match: raise ValueError(f'C档位无效：{value}')
    return int(match[1])

def score_fields(g, position):
    if g is None:
        if position is not None: raise ValueError('待定不得设置计分位置')
        return dict(C_score_band=None,C_score_band_position=None,C_score_rate=None,C_score_points=None,
                    C_score_position_method='EVIDENCE_PENDING',C_score_within_band_adjudication=None)
    if type(g) is not int or not 0 <= g <= 5 or position not in POSITIONS:
        raise ValueError('C档或显式位置无效')
    low,high = BANDS[g]
    rate = Decimal(low)+Decimal(high-low)*POSITIONS[position]
    return dict(C_score_band={'lower_rate':low,'upper_rate':high},
        C_score_band_position=float(POSITIONS[position]),C_score_rate=float(rate),
        C_score_points=float((rate/2).quantize(Decimal('.1'),rounding=ROUND_HALF_UP)),
        C_score_position_method='AUTHORED_JOINT_POSITION',
        C_score_within_band_adjudication={'position':position})

def verify_joint(row):
    stale=RETIRED_FIELDS & row.keys()
    if stale: raise ValueError(f'C联合结算不得保留旧短板或资格字段：{sorted(stale)}')
    a=row.get('joint_assessment') or {}
    if a.get('schema_version') != SCHEMA: raise ValueError('缺少C联合裁决')
    g=grade(row.get('final_grade'))
    if grade(row.get('combat_delivery_grade')) != g: raise ValueError('C1主评与正式总档不同值')
    for key in ('positive_evidence','adverse_evidence','reason','scope_boundary'):
        if not isinstance(a.get(key),str) or not a[key].strip(): raise ValueError(f'C联合裁决缺少{key}')
    expected=score_fields(g,a.get('position'))
    for key,value in expected.items():
        actual=row.get(key)
        if key=='C_score_within_band_adjudication' and actual is not None:
            actual={'position':actual.get('position')}
        if actual != value: raise ValueError(f'C联合计分不一致：{key}')
    if bool(row.get('score_ready')) != (g is not None): raise ValueError('C就绪状态与缺证不一致')
    chains={c['chain_id']:c for c in list(row.get('strategy_chains') or [])+
            list(row.get('capability_only_strategy_chains') or [])}
    refs=a.get('adopted_chain_refs') or []
    if len(refs)!=len(set(refs)) or not set(refs)<=set(chains): raise ValueError('C采用链不属于本人现行范围')
    if set(refs)&set(a.get('excluded_observations',{})):raise ValueError('已排除观察不得恢复采用')
    phase_ids={(x['ruler_id'],x['ref']) for x in a.get('key_phase_reviews',[])}
    if len(phase_ids)!=len(a.get('key_phase_reviews',[])):raise ValueError('关键阶段重复')
    if any(rid!=row.get('ruler_id') for rid,_ in phase_ids): raise ValueError('关键阶段借入他人窗口')
    for phase in a.get('key_phase_reviews',[]):
        if phase.get('status') not in {'ACCEPT','LIMITED','OTHER_SIDE'}:raise ValueError('未知关键阶段裁决状态')
        observations={e.get('observation_ref') for e in (row.get('public_reading') or {}).get('evidence_items',[])}
        if phase['ref'] not in set(chains)|observations:raise ValueError('关键阶段不属于本人采用材料')
        accepted=phase.get('status')=='ACCEPT'
        if accepted != (phase.get('adopted_difficulty') in {'D3','D4'}): raise ValueError('关键阶段资格与采用D不一致')
        if not phase.get('joint_phase_reason') or not phase.get('source_passages'):
            raise ValueError('关键阶段缺实际过程或来源')
    if row.get('system_observation_status')=='INHERITED_UNTESTED':
        e=row.get('inherited_system_assessment') or {}
        if g is not None and g>3: raise ValueError('继承保有能力不得超过三档')
        for key in ('ruler_window','baseline_window','baseline_ruler_id','baseline_source_refs','counterevidence_review'):
            if not e.get(key): raise ValueError(f'继承评价缺少{key}')
        if e.get('window_review')!='NO_ACTUAL_SYSTEM_STRESS' or e.get('continuity_status')!='SUPPORTED_WITH_LIMITS':
            raise ValueError('继承评价须有无实战与正面延续核查')
        if chains or refs: raise ValueError('继承评价不得借用前任战争')
    if g is not None and g>=4:
        # One retained long chain may contain independently launched tasks.
        # Container counts cannot replace the authored independence decision.
        if not a.get('independent_revalidation_basis') or not refs:
            raise ValueError('高档须有实际独立复验依据')
    return g
