"""Read-only C sources, current score synthesis, and authored zero explanations."""
from copy import deepcopy
from math import floor
from pathlib import Path

from .fourth_item_a import components, net_result, POINTS, BANDS
from .fourth_item_b_public import METHOD, SCALE

SCHEMA = 'fourth-item-c-sources-and-score-v1'
FORMAL = 'docs/评分结算/净收益/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json'
CURVE = 'docs/评分结算/净收益/第四项文明与国家整合收益/03-第四项共享曲线交班锚与去重审计.json'
POOL = 'config/common/canonical-ruler-pool.json'
POSITIONS = {'LOW': '低位', 'MID': '中位', 'HIGH': '高位'}


def text(value, label):
    from .third_fourth_item_public import PUBLIC_FORBIDDEN_RE
    if not isinstance(value, str) or not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
        raise ValueError(f'第四项C公开说明无效：{label}')
    return value


def sources(items, expected):
    if not isinstance(items, list) or [s.get('original') for s in items] != list(expected):
        raise ValueError('第四项C逐条来源与原有引用不同值')
    for source in items:
        if not isinstance(source.get('label'), str) or not source['label'].strip():
            raise ValueError('第四项C来源标题为空')
        text(source.get('kind'), 'source.kind')
        target = source.get('target')
        original = source['original']
        linked = original.startswith(('https://', 'http://', 'docs/', 'config/'))
        if target != (original if linked else ''):
            raise ValueError('第四项C来源链接丢失、被替换或不是原有引用')
    return deepcopy(items)


def package_reading(package):
    data = package['public_c_result_reading']
    for key in ('result', 'responsibility', 'scope'):
        text(data.get(key), key)
    refs = sources(data.get('sources'), package['source_refs'])
    if data['source_refs'] != package['source_refs']:
        raise ValueError('第四项C结果来源未同步')
    p, n = components(package)
    revoked = package.get('scoring_eligibility') == 'REVOKED'
    status = ('不单独计分，保留相关事实' if revoked else '正负结果并存' if p and n
              else '正向结果' if p else '负向损害' if n else '未形成可计入结果')
    exclusion = package.get('public_exclusion_reading', {})
    return dict(package_ref=package['package_code'], result=data['result'], responsibility=data['responsibility'],
                scope=data['scope'], status=status, sources=refs,
                exclusion_reason=text(exclusion.get('reason'), 'exclusion.reason') if revoked else '',
                components=f'本材料参与合成的正向强度为{p}级，负向强度为{n}级。' + ('不提供任何合成强度。' if revoked else ''),
                hard_negative='重大负向限制：不参与。' if revoked else
                '重大负向限制：已触发。' if package.get('hard_negative_gate') == 'ACTIVE' else '重大负向限制：未触发。')


def calculation(axis, selected):
    eligible = [p for p in selected if p.get('scoring_eligibility') != 'REVOKED']
    result = net_result(selected)
    grade = int(result['grade'][3:])
    points = axis['signed_adjustment']
    if not eligible:
        expected_state = 'NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW' if selected else 'NO_ELIGIBLE_CIVILIZATION_INCREMENT'
        if points != 0 or axis['disposition'] != expected_state:
            raise ValueError('第四项C无合格材料的处置或分数不一致')
        return ('没有合格材料提供正向或负向强度，正式调整为0分。未确认独立结果与材料复核后不计分分别说明；'
                '这不是将未知的历史作用估计为零，也不是正负相抵。'), '没有确认独立变化' if not selected else '复核后未确认独立净变化'
    if axis['magnitude_grade'] != result['grade'] or axis['direction'] != result['direction']:
        raise ValueError('第四项C公开合成与现行方向、幅度不一致')
    if grade:
        if axis.get('band') not in BANDS:
            raise ValueError('第四项C缺少合法档内位置')
        expected = POINTS[grade][BANDS.index(axis['band'])] * (1 if result['P'] > result['N'] else -1)
        if result['high_forbidden'] and axis['band'] == 'HIGH':
            raise ValueError('第四项C档内位置违反限制')
    else:
        expected = 0
        if axis['disposition'] != 'OBSERVED_OFFSETTING_OR_BALANCED_EFFECTS':
            raise ValueError('第四项C相抵零值处置未同步')
    if expected != points:
        raise ValueError('第四项C换分与正式分数不同值')
    lines = []
    all_components = [components(p) for p in eligible]
    for index, label, total in ((0, '正向', result['P']), (1, '负向', result['N'])):
        values = [pair[index] for pair in all_components if pair[index]]
        if not values:
            lines.append(f'{label}：没有合格组件，强度为0。')
        else:
            strongest = max(values)
            bonus = 0.5 if len(values) > 1 else 0
            lines.append(f'{label}：取最强材料{strongest}级，第二项独立材料补强{bonus:g}，上限4级，合成强度为{total:g}。')
    delta = result['P'] - result['N']
    ordinary = min(4, max(1, floor(abs(delta)))) if delta else 0
    lines.append(f'正向{result["P"]:g} − 负向{result["N"]:g} = {delta:g}。普通净算幅度为{ordinary}级：非零差额取绝对值后向下取整，最低1级、最高4级。')
    pmax = max((pair[0] for pair in all_components), default=0)
    nmax = max((pair[1] for pair in all_components), default=0)
    protected = (pmax == 4 and nmax <= 1) or (nmax == 4 and pmax <= 1)
    if protected:
        lines.append('一侧有4级结果、反向最高1级，适用4级保留；存在反向结果时不能取高位。')
    if result['H']:
        h = result['H']
        if delta < 0:
            lines.append(f'保留{h}级重大负向限制，最终负向幅度至少{max(1,h-1)}级；无关正向成果不能解除该限制。')
        elif delta > 0:
            lines.append(f'保留{h}级重大负向限制，最终正向幅度最多{5-h}级，且不能取高位。')
        else:
            lines.append(f'正负相抵仍保留{h}级重大负向记录；0分不表示损害未发生或已经修复。')
    else:
        lines.append('没有触发重大负向限制。')
    lines.append(f'按上述规则，最终净幅度为{grade}级。')
    if grade:
        low, mid, high = POINTS[grade]
        band = POSITIONS[axis['band']]
        lines.append(f'本幅度低、中、高位依次为{low:g}、{mid:g}、{high:g}分；现行采用{band}，按净方向取符号，正式调整为{points:+g}分。')
        status = ('正向' if points > 0 else '负向') + f' · {SCALE[grade-1]} · {band}'
    else:
        lines.append('正负相抵，幅度为0，不再选低、中、高位，正式调整为0分；各条正负事实仍分别保留。')
        status = '正负相抵，净调整为0'
    return '\n\n'.join(lines), status


def axis_reading(row, axis, packages):
    authored = axis.get('public_reading')
    if not isinstance(authored, dict) or authored.get('schema') != SCHEMA:
        raise ValueError(f'缺少第四项C分数与零值说明：{row.get("ruler_name")}')
    for key in ('question', 'window', 'decision_basis', 'review_basis', 'source_note'):
        text(authored.get(key), key)
    if authored.get('basis_material_refs') != axis['package_refs']:
        raise ValueError('第四项C说明绑定的材料已变化')
    selected = [packages[code] for code in axis['package_refs']]
    for p in selected:
        if p['ruler_id'] != row['ruler_id'] or p['axis'] != 'C':
            raise ValueError('第四项C跨人或跨轴引用')
    calc, status = calculation(axis, selected)
    zero_reason = authored.get('zero_reason', '')
    if axis['signed_adjustment'] == 0:
        text(zero_reason, 'zero_reason')
    elif zero_reason:
        raise ValueError('第四项C非零记录不能带零值解释')
    assessment = sources(authored.get('assessment_sources'), [FORMAL, CURVE, POOL])
    evidence = [package_reading(p) for p in selected]
    return dict(question=authored['question'], window=authored['window'], points=axis['signed_adjustment'], status=status,
                decision_basis=authored['decision_basis'], zero_reason=zero_reason, review_basis=authored['review_basis'],
                source_note=authored['source_note'], evidence_items=evidence, assessment_sources=assessment,
                calculation=calc, method=METHOD, scale=SCALE)


def verify_readings(payload, root=None):
    packages = {p['package_code']:p for p in payload['accepted_packages']}
    for row in payload['records']:
        axis_reading(row, next(a for a in row['axis_results'] if a['axis']=='C'), packages)
    if root is not None:
        from .formal_json_store import load_json
        audit = load_json(Path(root)/CURVE)
        windows = {r['ruler_id']:r['actual_power_window'] for s in audit['dynasty_curve_segments'] for r in s['ruler_order']}
        reviews = {r['ruler_id']:next(a['basis'] for a in r['axis_reviews'] if a['axis']=='C') for r in audit['a_axis_review']['rulers']}
        for row in payload['records']:
            data = next(a for a in row['axis_results'] if a['axis']=='C')['public_reading']
            window = windows[row['ruler_id']]
            if isinstance(window, list):
                window = '；'.join(f'{part[0]}—{part[1]}年' for part in window)
            if data['window'] != window or data.get('review_basis_original') != reviews[row['ruler_id']]:
                raise ValueError('第四项C主政时期或复核依据已变化，须同步说明')
    return len(payload['records'])


def markdown_reading(data):
    def refs(items):
        return '\n'.join('- '+s['kind']+'：'+(f'[{s["label"]}]({s["target"]})' if s['target'] else s['label'])+'\n\n  原引用（含项目采用说明）：'+s['original'] for s in items)
    lines = [f'**{data["question"]}**', '', '评价时期：'+data['window'], '', data['status'], '', data['decision_basis']]
    if data['zero_reason']:
        lines += ['', '**为什么是0分**', '', data['zero_reason']]
    for index, item in enumerate(data['evidence_items'], 1):
        lines += ['', f'#### 材料{index}：{item["status"]}', '', item['result'], '', '**本人责任**', '', item['responsibility'], '', item['scope'], '', item['components'], '', item['hard_negative']]
        if item['exclusion_reason']:
            lines += ['', '不计分原因：'+item['exclusion_reason']]
        lines += ['', '**这条材料的来源**', '', refs(item['sources'])]
    lines += ['', '**分数怎样合成**', '', data['calculation'], '', data['method'], '', '**现行复核边界**', '', data['review_basis'], '', data['source_note'], '', refs(data['assessment_sources'])]
    return '\n'.join(lines)
