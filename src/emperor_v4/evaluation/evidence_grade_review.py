"""Finite, sourced review candidates; never certify hypothetical endpoints."""
from copy import deepcopy


def review_baseline(governance: dict, third: dict, handoff: dict) -> dict:
    """Bind the finite review to adopted inputs, not to a Git commit."""
    return {
        'governance': {axis: {key:state[key] for key in ('s0_band','main_band','end_band')}
                      | {'loss_grade':state['loss_review']['grade']}
                      for axis,state in governance['axes'].items()},
        'recovery': {
            'baseline':{a:v['band'] for a,v in governance['recovery']['baseline'].items()},
            'terminal':{a:v['band'] for a,v in governance['recovery']['terminal'].items()},
            'attribution':{a:v['factor'] for a,v in governance['recovery']['attribution'].items()},
            'deterioration_attribution':deepcopy(governance['recovery']['deterioration_attribution_by_axis']),
        },
        'handoff': {key:handoff[key] for key in ('D1_level','D3_level')},
        'military': {key:third[key] for key in ('military_net_loss_grade','cost_debit_points')},
    }


def validate_baselines(expected: dict, actual: dict) -> None:
    if not expected or expected != actual:
        raise ValueError('档位复核本人或联动基准已变，必须重审范围')


def project_review(review: dict, third: dict | None = None) -> dict:
    required = ('kind', 'basis', 'dependency_basis', 'admissibility')
    if any(not review.get(key) for key in required):
        raise ValueError('档位复核缺少依据、性质或联动说明')
    if review['admissibility'] != 'CONDITIONAL_REVIEW_ONLY':
        raise ValueError('复核候选不得冒充已经成立的替代裁决')
    out = deepcopy(review)
    out['score_effects'] = []
    if review['kind'] == 'SOURCE_BOUNDED_REVIEW':
        if not review.get('display'):
            raise ValueError('档位复核缺少当前档及具体候选')
        return out
    if review['kind'] != 'MILITARY_NET_LOSS' or third is None:
        raise ValueError('不支持的档位复核对象')
    grades = review.get('candidate_grades', [])
    policy = {'ML0': 0, 'ML1': 20, 'ML2': 40, 'ML3': 60, 'ML4': 80}
    if not grades or len(grades) != len(set(grades)) or any(g not in policy for g in grades):
        raise ValueError('军事净毁损候选档非法或重复')
    current = third['military_net_loss_grade']
    cost = float(third['cost_debit_points'])
    if review['baseline_grade'] != current or review['baseline_cost_debit'] != cost:
        raise ValueError('军事档位复核基准已变，必须重审')
    if current not in grades or not review.get('excluded_basis'):
        raise ValueError('遗漏当前档或其他档位排除依据')
    span = max(int(g[2:]) for g in grades)-min(int(g[2:]) for g in grades)
    if span > 2 and not review.get('wide_span_basis'):
        raise ValueError('超过两档须单独给出宽幅依据，不能静默截断')
    debit = max(cost, policy[current])
    if debit != float(third['applied_military_debit_points']):
        raise ValueError('当前军事扣分未按成本与净毁损取高')
    out['score_effects'] = [
        {'grade': g, 'conditional_total_delta': round(debit-max(cost, policy[g]), 2)}
        for g in grades
    ]
    out['grade_span'] = span
    out['display'] = ('净毁损现'+current[2:]+'级；本命题复核候选'
                      +'、'.join(g[2:] for g in grades)+'级。')
    out['conditional_effect_text'] = '固定当前普通成本：'+'；'.join(
        x['grade'][2:]+'级'+('不改总分' if x['conditional_total_delta']==0 else
                          f"使总分变化{x['conditional_total_delta']:+.2f}分")
        for x in out['score_effects'])+'。这些是条件算式，未采信候选不列替代名次。'
    return out
