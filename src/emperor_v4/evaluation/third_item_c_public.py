"""Authored Item 3 C prose; deterministic, read-only explanation of its settlement."""
from copy import deepcopy
import re
import posixpath

AXES = ('C1', 'C2', 'C3')
FIELDS = ('combat_delivery_grade', 'operational_sustainability_cap', 'system_reliability_cap')
LABELS = ('实战表现', '持续作战保障', '跨将领稳定发挥')
AUDIT_TERMS = (
    ('战略链', '把同一主要压力对象、连续国家授权与共同终局的战争过程合为一条观察。年度、战斗或材料记载多，不因此多计一次结果。'),
    ('父周期', '供回看战争过程与阶段事实的既有证据分组。分组边界仍须核实，不因已有登记就成为独立战争，也不另计一次胜负或分数。'),
    ('能力专用链', '只在准入范围内观察军队能力的战争材料，不进入当前链的结果质量，不重复计战争成果、控制或成本；能否用于资格核查，以本条正式采用范围为准。'),
    ('对手O档', '对手在实际交手时期的战争机器组织强度。它说明当时的任务难度，不是获胜分数，也不是某个国家永久不变的等级。'),
    ('资格门禁与资格上限', '进入某档所需的证据条件及其限制。通过条件不等于能力已经达到该档；总档资格上限只限制最终总档，不改写三轴原档。'),
    ('具名资格记录', '按具体对手、将领或方向登记的资格材料。仍须核对本人时期和对应战争，不能仅凭名单或数量证明能力。'),
    ('回报类别与结果质量', '按完整战争分为高、相称、低、负向或未知，用于档内位置，不直接替代三轴定档。高回报不等于重大体系胜绩，负回报也不自动等于重大体系失败。'),
    ('相邻档分界', '说明现有事实为何支持本档，以及能否区别于低一档或高一档。未能区分时，原有档位本身不能作为证明。'),
    ('闭合、绑定与回源', '核对人物、时期、战争对象、事实和出处能否对应。绑定是记录中已有的明确关联；有编号或链接不等于史实已被充分证明。'),
    ('出票与消费范围', '“出票”指把结果单独计作一次胜负或结果；“消费范围”指材料已经在哪个项目采用。同一战争的阶段材料不重复计功，已用于其他项目的成果不再重复结算。'),
)
AUDIT_LINK_NOTE = '材料链接按正式记录已有的关联定位，不按战事名称猜配。各条材料的采用范围与缺口仍以原文为准；关联不表示每条材料都能单独证明全部判断。'
COMBAT_GUIDE = (
    '看军队面对实际对手和战争压力时的全役作战表现。目标完成程度是重要证据，还须结合对手强度、完整交战过程、可证战果、己方战损及战后续战能力判断。'
    '\n\n目标未完成时，保留未克城池、未达政治或领土目标等限制，再分别核对取得了什么战果、主力损失到什么程度、是否保存，以及能否继续作战。'
    '攻城未克不自动等于全役战败；有野战胜利或主力撤回也不自动支持高档。主力保存与可继续作战须分别有证据，失载的部分保留未知，不机械按斩获比例定档。'
    '\n\n重大体系失败须有主力毁灭、整组行动因保障或军令崩溃，或主要方向因组织失灵连续失效的证据。'
    '不能只凭目标未成认定，也不能用另一方向的胜利注销已经证实的主力毁灭或整组崩溃。'
    '同一实际作战表现不因改写出兵目标而换档；战争成果、控制和代价仍按各自规则结算。'
)
REVIEW_LABELS = {
    'SOURCE_SUPPORTED': '已回源支持',
    'ADJACENT_BOUNDARY_UNRESOLVED': '相邻档分界尚未充分证明',
    'INHERITED_LIMITED_ASSESSMENT': '继承体系的有限判断',
    'CONTRACT_BOUNDARY_AMBIGUOUS': '史实已核，分界仍待裁定',
    'MATERIAL_EVIDENCE_MISSING': '缺具体材料，待重裁',
    'SOURCE_CONFLICT': '史实冲突，须重裁',
    'SPECIFIC_SOURCE_GAP': '关键事实缺证',
}
REVIEW_NOTE = '档位与分数为现行结算值；各方面的分界论证状态列在档位旁，具体疑点见“深入核对”。'
INTERNAL = re.compile(r'第[一二三四]项|本批|本轮|横校|回灌|倒灌|闭合|父卡|\d+票|旧ID|重绑|campaign_group|UNKNOWN|RETRO\d')
ASSESSMENT_SCOPE = '军事体系主要参考对外战争，有限参考统一战争与内部平乱；五档须有对外战争重大胜绩，且完整战略链上无重大体系失败。'
METHOD = (
    '军队能力满分50分，三个方面不相加，也不取平均。先看面对实际对手的全役作战表现；持续保障与组织可靠性只能验证或压低这个判断，不能抬高它。'
    '先取三轴最低档作为原始总档，再与资格上限取低，得到最终结算档；资格封顶不改写三轴。'
    '4档须有重大体系胜绩，并满足成功数不低于重大失败数；C1五档须无完整战略链上的重大体系失败，五档还须有对外战争重大胜绩及多个强敌体系、跨方向、跨将领的检验。'
    '攻城未克或目标未全成不直接等于全役战败；须结合对手强度、全役战果、战损及续战能力判断，同一作战表现不因改写出兵目标而换档。'
    '无任内实战而按继承体系评价的，总档最高3档。'
    '总档0至5对应得分率区间0%—29%、30%—44%、45%—59%、60%—74%、75%—89%、90%—100%。'
    '档内位置取三方面相对最终档的能力余量与完整战争过程的结果质量位置的较高者；有明确同档位置裁决时，以该位置替代结果质量位置，再与能力余量取高。'
    '结果质量区分高、相称、低、负向和未知；未知不当作失败，任务数量本身不加分。最终按50×得分率÷100换算，沿用正式结算的舍入。'
)
SCALES = (
    ('核心任务整体失去作战能力', '普通任务也反复失败', '胜负混杂且总体偏弱', '普通和中等任务总体可兑现', '主要或高难任务多数兑现，仅有少数重大失败', '多个强敌体系下长期保持顶级兑现，且完整战略链上无重大体系失败'),
    ('动员、补充或后勤体系崩溃', '只能维持极短期临时行动', '能有限作战，保障经常限制主要行动', '通常能支撑普通战争，大规模长期行动有缺口', '稳定支撑多路、大规模或较长期战争，仍有保障缺口', '多个强敌、独立方向下长期顶级保障，无战役群级保障崩溃'),
    ('国家级军令和组织全面崩溃且未恢复', '中央级组织长期严重失灵且未恢复', '反复组织失误，明显依赖少数将领或临时拼凑', '通常有效，跨将领和方向复制有限', '多名将领、多方向稳定运行，仍有组织缺口', '顶级跨将领和战场复制，至少两名顶级统帅各有显著成果'),
)


def grade(value):
    if value == 'UNKNOWN':
        return None
    match = re.fullmatch(r'C(?:[123])?-([0-5])', str(value))
    if not match:
        raise ValueError(f'第三项C档位无效：{value}')
    return int(match[1])


def fmt(value):
    return f'{float(value):.4f}'.rstrip('0').rstrip('.')


def calculation(row):
    from .third_item_c_strategy_chain import _reject_grade_aliases
    _reject_grade_aliases(row)
    axes = [grade(row[k]) for k in FIELDS]
    raw, final = grade(row['axis_floor_grade']), grade(row['final_grade'])
    cap = row['gate_cap']
    if any(value is None for value in axes):
        if any(row.get(key) != 'UNKNOWN' for key in ('axis_floor_grade', 'final_grade')) or any(row.get(key) is not None for key in ('C_score_points', 'C_score_rate', 'C_score_band_position')):
            raise ValueError('必要轴缺证时总档和分数必须保持未知，不得按零分合成')
        return dict(axis_grades=axes, raw_grade=None, gate_cap=cap, final_grade=None,
                    points=None, rate=None, total_label='证据不足 · 暂不计分',
                    grade_path='至少一项必要能力尚不能据现有材料定档，军事体系总档暂缺。',
                    cap_reason='资格门不能代替必要轴的事实裁决。', position='档内位置暂不计算。',
                    method=METHOD, outcome_text='已知战争结果仍保留，但不能替代缺证的必要能力。',
                    formula='军事体系及第三项合计暂不计分，不以零分填补，也不进入综合排名。',
                    outcome_profile=deepcopy(row.get('strategy_chain_outcome_profile') or {}))
    if min(axes) != raw or min(raw, cap) != final:
        raise ValueError('第三项C三轴、原始总档、封顶与最终档不一致，禁止为展示改分')
    band = row['C_score_band']
    rate, points = float(row['C_score_rate']), float(row['C_score_points'])
    p = float(row['C_score_band_position'])
    if not band['lower_rate'] <= rate <= band['upper_rate'] or abs(points - 50 * rate / 100) > .051:
        raise ValueError('第三项C正式得分与得分率区间不一致')
    view = row.get('major_victory_gate_chain_view') or {}
    success = int(view.get('current_major_successes', 0)) + int(view.get('capability_only_major_successes', 0))
    failure = int(view.get('current_major_failures', 0)) + int(view.get('capability_only_major_failures', 0))
    if row.get('system_observation_status') == 'INHERITED_UNTESTED':
        cap_reason = '本任未经过实战检验，继承体系评价的总档最高3档；这个上限不是默认给3档。'
    elif cap < raw:
        cap_reason = f'现行登记的原始总档为{raw}档，资格上限为{cap}档，因此最终按{cap}档结算，三轴原档不变。原资格台账列重大成功{success}项、重大失败{failure}项；登记不足不等于历史上不存在合格胜绩，回源支持与冲突见各链及三轴说明。已准入的能力观察可用于能力与资格论证，但公开补证不擅自改写原门禁、成果、成本或分数。'
    else:
        cap_reason = f'资格上限为{cap}档，本人原始总档为{raw}档，资格条件没有进一步压低本人的总档。高上限不表示实际达到该档。'
    surplus = float(row.get('C_score_axis_surplus_position', 0))
    q = float(row.get('C_score_outcome_position', .5))
    profile = row.get('strategy_chain_outcome_profile') or {}
    counts = profile.get('return_class_counts') or {}
    outcome_text = '按完整战争过程合并后的结果：' + '、'.join(
        f'{label}{int(counts.get(key, 0))}项' for key, label in (
            ('HIGH_RETURN', '高回报'), ('PROPORTIONATE_RETURN', '相称回报'),
            ('LOW_RETURN', '低回报'), ('NEGATIVE_RETURN', '负向结果'), ('UNKNOWN', '结果未量化'))) + '。同一场连续战争只计一次，不按战役记载条数加分。'
    explicit = row.get('C_score_within_band_adjudication') or {}
    position = f'能力余量位置a={fmt(surplus)}，战争结果质量位置q={fmt(q)}；正式采用档内位置p={fmt(p)}。'
    if explicit:
        positions = {'LOW': ('低位', .25), 'MID': ('中位', .5), 'HIGH': ('高位', .75)}
        if explicit.get('position') not in positions or not isinstance(explicit.get('reason'), str) or not explicit['reason'].strip():
            raise ValueError('显式档内裁决须有有效位置与原裁决理由')
        label, value = positions[explicit['position']]
        position += (f'本记录明确裁定为档内{label}（{fmt(value)}）。原裁决理由：{explicit["reason"]}'
                     f'\n\n计算时以{fmt(value)}替代结果质量位置q，再与能力余量a取高，'
                     f'p=max({fmt(surplus)}, {fmt(value)})={fmt(p)}。')
    if final == 5:
        position = '三轴均为5档，且5档全部资格通过，按合同直接取满分50分。'
    else:
        s = sum(a - final for a in axes)
        position = f'能力余量s=({axes[0]}−{final})+({axes[1]}−{final})+({axes[2]}−{final})={s}；a=s÷[2×(5−{final})]={fmt(surplus)}。' + position
        position += '高、相称、低、负向结果分别取1、0.55、0.2、0；以已量化结果求平均，q从0.5按min(1，已知数÷4)向该均值收敛。没有已量化结果时q=0.5，能力专用链不进入结果质量；继承体系无本人战果时同样取q=0.5。'
        position += f'本档得分率={band["lower_rate"]}+({band["upper_rate"]}−{band["lower_rate"]})×{fmt(p)}，按正式结算得到{fmt(rate)}%。'
        expected = band['lower_rate'] + (band['upper_rate'] - band['lower_rate']) * p
        if abs(rate - expected) > .02:
            raise ValueError('第三项C档内位置与正式得分率不一致')
    return dict(axis_grades=axes, raw_grade=raw, gate_cap=cap, final_grade=final,
                points=row['C_score_points'], rate=row['C_score_rate'],
                total_label=f'最终{final}档 · {fmt(points)} / 50分',
                grade_path=f'三轴分别为{axes[0]}、{axes[1]}、{axes[2]}档；最低档为{raw}档，即原始总档。与资格上限{cap}档取低，最终为{final}档。三轴保持原值。',
                cap_reason=cap_reason, position=position, method=METHOD,
                outcome_text=outcome_text,
                formula=(f'最终{final}档对应{band["lower_rate"]}%—{band["upper_rate"]}%。'
                         f'正式得分率为{fmt(rate)}%；50 × {fmt(rate)} ÷ 100，按现行结算舍入后为{fmt(points)}分。'),
                outcome_profile=deepcopy(row.get('strategy_chain_outcome_profile') or {}))


def reading_projection(row, *, context):
    authored = row.get('public_reading')
    if not isinstance(authored, dict):
        raise ValueError(f'{row["ruler_name"]}缺少第三项C上游正文')
    from .third_item_c_contract_reading import reading_review
    from .third_item_c_passages import expand_passages
    result = expand_passages(authored)
    for key in ('story', 'window', 'responsibility', 'boundary', 'source_note'):
        value = result.get(key)
        if not isinstance(value, str) or not value.strip() or INTERNAL.search(value):
            raise ValueError(f'{row["ruler_name"]} C公开正文无效：{key}')
    if re.search(r'[{}\[\]]|window_ref|JIN-', result['window']):
        raise ValueError('第三项C评价时期须为直接维护的人类可读窗口')
    if set(result.get('axes', {})) != set(AXES):
        raise ValueError('第三项C必须分别维护三轴依据')
    evidence_ids = {e['id'] for e in result.get('evidence_items', [])}
    if not evidence_ids or len(evidence_ids) != len(result['evidence_items']):
        raise ValueError('第三项C逐条材料为空或标识重复')
    evidence_by_id = {e['id']: e for e in result['evidence_items']}
    # Validate authored bindings before deriving the review that consumes them.
    for axis in AXES:
        a = result['axes'][axis]
        if not a.get('basis') or INTERNAL.search(a['basis']) or not a.get('evidence_refs') or not set(a['evidence_refs']) <= evidence_ids:
            raise ValueError(f'{row["ruler_name"]} {axis}依据或显式材料绑定无效')
        if any(not x.get('reason') or INTERNAL.search(x['reason']) or x.get('evidence_ref') not in a['evidence_refs'] for x in a.get('arguments', [])):
            raise ValueError('逐轴论证必须说明所引材料的作用，并绑定本轴已声明的材料')
    result['contract_review'] = reading_review(row, context=context)
    for i, axis in enumerate(AXES):
        a = result['axes'][axis]
        if not a.get('basis') or INTERNAL.search(a['basis']) or not a.get('evidence_refs') or not set(a['evidence_refs']) <= evidence_ids:
            raise ValueError(f'{row["ruler_name"]} {axis}依据或显式材料绑定无效')
        g = grade(row[FIELDS[i]])
        a.update(label=LABELS[i], grade=g, grade_label='待定' if g is None else f'{g}档', scale=list(SCALES[i]))
        a['assessment_guide'] = COMBAT_GUIDE if axis == 'C1' else ''
        review = result['contract_review']['axes'][axis]
        status = review.get('status')
        if status not in REVIEW_LABELS:
            raise ValueError(f'第三项C未知分界论证状态：{status}')
        a.update(review_status=status, review_label=REVIEW_LABELS[status], review_text=review['status_text'])
        arguments = a.get('arguments', [])
        if any(not x.get('reason') or INTERNAL.search(x['reason']) or x.get('evidence_ref') not in a['evidence_refs'] for x in arguments):
            raise ValueError('逐轴论证必须说明所引材料的作用，并绑定本轴已声明的材料')
        if len({x['evidence_ref'] for x in arguments}) != len(arguments):
            raise ValueError('同一材料不得在同一轴重复充当多条论证')
        reason_by_id = {x['evidence_ref']: x['reason'] for x in arguments}
        refs = list(reason_by_id) if arguments else a['evidence_refs']
        a['materials'] = [dict(deepcopy(evidence_by_id[ref]), reason=reason_by_id.get(ref, ''))
                          for ref in refs if ref != 'C-DECISION' and not evidence_by_id[ref]['text'].startswith('未知')]
        a['evidence_note'] = ('' if a['materials'] else '目前只有总体评价，尚未关联可逐条核对的具体战争材料；这里的证据展示仍不完整。')
    if len({a['basis'] for a in result['axes'].values()}) != 3:
        raise ValueError('第三项C三轴不得复用同一总评')
    for e in result['evidence_items']:
        if not all(e.get(k) for k in ('label', 'text', 'kind', 'scope', 'sources')):
            raise ValueError('第三项C材料须区分原文、既有摘要及评价，并保留范围与来源')
        if e['kind'] not in ('现行评价判断', '既有史实摘要', '史料原文'):
            raise ValueError('第三项C未知材料类别')
    result['calculation'] = calculation(row)
    from .third_item_c_commander_reading import commander_projection
    result['axes']['C3']['commander_profiles'] = commander_projection(row)
    result['assessment_scope_note'] = ASSESSMENT_SCOPE
    result['review_note'] = REVIEW_NOTE
    result['audit_terms'] = list(AUDIT_TERMS)
    result['audit_link_note'] = AUDIT_LINK_NOTE
    result['ruler_id'] = row['ruler_id']
    return result


def verify_sources(root, payload, *, context=None):
    from .third_item_c_contract_reading import load_context
    context = load_context(root) if context is None else context
    from emperor_v4.evaluation.battle_registry_store import load_battle_registry
    registry = load_battle_registry(root / 'docs/公共成果/军事/01-战役登记.json')
    battles = {r['war_event_id']: r for r in registry['records']}
    for row in payload['records']:
        data = reading_projection(row, context=context)
        chain_ids = {c['chain_id'] for c in data['contract_review']['chains']}
        for e in data['evidence_items']:
            if not set(e.get('c_chain_refs', [])) <= chain_ids:
                raise ValueError('C公开材料引用了本人现行记录之外的战争链')
            for ref in e['sources']:
                if not (root / ref['path'].split('#', 1)[0]).is_file():
                    raise ValueError(f'C公开来源文件不存在：{ref["path"]}')
            event_id = e.get('war_event_id') or e.get('background_war_event_id')
            if event_id:
                battle = battles[event_id]
                if e.get('background_war_event_id') and e.get('c_chain_refs'):
                    raise ValueError('背景战事不得再绑定本人实战链')
                if e.get('war_event_id') and event_id not in row.get('settled_event_refs', []) and event_id not in row.get('current_item_task_refs', []) and event_id not in row.get('capability_only_parent_refs', []):
                    raise ValueError('C公开战役未在本人正式引用中显式登记')
                if e['text'] != battle.get('observable_result') or e.get('historical_source_refs') != battle.get('source_refs', []):
                    raise ValueError('C公共史实摘要已变化，须核对上游正文，禁止页面改写')
            for passage in e.get('source_passages', []):
                path, _, anchor = passage['path'].partition('#')
                text = (root / path).read_text(encoding='utf-8')
                if anchor:
                    marker = '### ' + anchor + ' '
                    if marker not in text:
                        raise ValueError('C材料的史源段落锚点不存在')
                    text = text.split(marker, 1)[1].split('\n### ', 1)[0]
                if not passage.get('quote') or passage['quote'] not in text:
                    raise ValueError('C材料摘录与所引原记录不一致，须核对上游材料')
    return len(payload['records'])


def markdown(row, *, context):
    data = reading_projection(row, context=context)
    c = data['calculation']
    lines = [f'评价时期：{data["window"]}', '', data['assessment_scope_note'], '', data['review_note'], '', data['story'], '', data['responsibility'], '']
    for axis in AXES:
        a = data['axes'][axis]
        lines += [f'#### {axis} {a["label"]}（{a["grade_label"]}，不单独加分）', '', a['assessment_guide'], '', '分界论证：' + a['review_label'], '', a['review_text'], '', a['basis'], '',
                  '材料：' + '、'.join(a['evidence_refs']), '']
        if axis == 'C3':
            commanders = a['commander_profiles']
            lines += ['##### 将领档位与本任成果', '', commanders['note'], '']
            for entry in commanders['entries']:
                lines += ['- [' + entry['name'] + ' · ' + entry['grade_label'] + '](../../../../../reader/'
                          + entry['archive_href'] + ')：' + entry['qualification_text']]
        if a['evidence_note']:
            lines += [a['evidence_note'], '']
        for e in a['materials']:
            lines += [f'##### {e["label"]}', '', e['text'], '']
            if e['reason']:
                lines += ['定档作用：' + e['reason'], '']
            lines += ['来源：' + '；'.join(s['path'] for s in e['sources']), '']
    from .third_item_c_contract_reading import markdown_review
    lines += [markdown_review(data['contract_review']), '', '#### 总档、封顶与分数', '', c['grade_path'], '', c['cap_reason'], '', c['outcome_text'], '', c['position'], '', c['formula'], '', c['method'], '',
              '#### 逐条材料与来源', '', data['source_note'], '']
    for e in data['evidence_items']:
        lines += [f'- {e["label"]}（{e["kind"]}；{e["id"]}）：{e["text"]}', f'  范围：{e["scope"]}',
                  '  来源：' + '；'.join(f'[{s["label"]}]({posixpath.relpath(s["path"], "docs/评分结算/净收益/第三项军事与边疆净收益/军事体系有效性")})' for s in e['sources'])]
        if e.get('historical_source_refs'):
            lines += ['  原登记史源：' + '；'.join(map(str, e['historical_source_refs']))]
    return '\n'.join([*lines, '', '评价边界：' + data['boundary'], ''])
