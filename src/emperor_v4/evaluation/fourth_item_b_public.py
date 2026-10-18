"""Authored education and talent-mobility reading; never adjudicates or changes scores."""
from copy import deepcopy
import re
from urllib.parse import urlsplit

from .fourth_item_a import components, net_result, POINTS, BANDS

SCHEMA = 'fourth-item-b-authored-public-v1'
CURVE_SOURCE = 'docs/评分结算/净收益/第四项文明与国家整合收益/03-第四项共享曲线交班锚与去重审计.json'
SCOPE_SOURCE = 'config/common/canonical-ruler-pool.json'
TITLE = '教育可及与人才流动'
BOUNDARY = '只评价实际教学、学习机会和人才流动的独立变化，不重复计算选官制度、当期官僚质量及知识文化成果。'
METHOD = ('先把符合条件的正向结果与负向损害分别判断为0至4级；同方向取最强结果，第二项独立结果最多补强0.5，方向强度不超过4。正负强度之差决定净方向，非零差的绝对值向下取整、最低1级、最高4级。'
          '一侧达到4级、反向最高1级时，按合同保留4级；重大负向损害另有最低负档、最高正档及高位限制。无关正向成果不能解除重大负向限制，同一损害的真实修复才可降低限制。'
          '最终幅度1至4级的低、中、高位分别对应3/4.5/6、7.5/9.5/11.5、13.5/16/18、19/21/22.5分，再按方向取正负；0级为0分。覆盖、持续性、交班、跨场景结果与反证决定档内位置，材料条数不决定分数。')
SCALE = ['局部、短期或低强度变化', '清晰可验证的有限扩张、修复、收缩或破坏', '主要领域形成稳定的重大改变', '跨场景新范式或系统性破坏']
INTERNAL = re.compile(r'结果方向未单列|责任范围按现有材料区分|过期表述|本轮|本批|旧包|本包|撤资格|闭合|回填|回灌|横校|[A-Z]{2,}_[A-Z_]+|(?:R|P|N|CIV)[0-4](?:\b|(?=[\u4e00-\u9fff]))')


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or INTERNAL.search(value):
        raise ValueError(f'第四项B公开正文无效：{field}={value!r}')
    return value


def source_label(ref):
    if ref.startswith(('https://', 'http://')):
        return urlsplit(ref).hostname or '来源页面'
    return ref


def _sources(sources, expected):
    if not isinstance(sources, list) or [s.get('original') for s in sources] != list(expected):
        raise ValueError('第四项B逐条史源与正式来源不同值')
    for source in sources:
        _text(source.get('label'), 'source.label')
        _text(source.get('kind'), 'source.kind')
        original = source['original']
        target = source.get('target', '')
        if target and (target != original or not target.startswith(('https://', 'http://', 'docs/', 'config/'))):
            raise ValueError('第四项B来源链接不合法或与原引用不一致')


def package_reading(package):
    data = deepcopy(package.get('public_reading'))
    if not isinstance(data, dict) or data.get('schema') != SCHEMA:
        raise ValueError(f"缺少第四项B影响材料正文：{package['package_code']}")
    for field in ('title', 'story', 'baseline', 'responsibility', 'level_basis', 'coverage', 'duration', 'boundary', 'source_note'):
        _text(data.get(field), field)
    _sources(data.get('sources'), package.get('source_refs', []))
    p, n = components(package)
    revoked = package.get('scoring_eligibility') == 'REVOKED'
    data['status'] = ('不单独计分，保留相关事实' if revoked else
                      '正负结果并存' if p and n else '正向结果' if p else '负向损害' if n else '未形成可计入结果')
    data['components'] = f'正向结果强度{p}级；负向损害强度{n}级。' + ('相关事实不参与本轴合成。' if revoked else '')
    data['major_negative'] = '重大负向限制已触发，须与正向成果分开保留。' if package.get('hard_negative_gate') == 'ACTIVE' and not revoked else '该材料未触发独立的重大负向限制。'
    return data


def axis_reading(row, axis, packages):
    data = deepcopy(axis.get('public_reading'))
    if not isinstance(data, dict) or data.get('schema') != SCHEMA:
        raise ValueError(f"缺少第四项B人物正文：{row['ruler_name']}")
    for field in ('question', 'window', 'story', 'decision', 'responsibility', 'boundary', 'source_note'):
        _text(data.get(field), field)
    refs = data.get('assessment_sources')
    if not refs:
        raise ValueError('第四项B缺少裁决及窗口来源入口')
    _sources(refs, [s['original'] for s in refs])
    selected = [packages[ref] for ref in axis['package_refs']]
    data['evidence_items'] = [dict(package_ref=p['package_code'], **package_reading(p)) for p in selected]
    context = data.get('context_items', [])
    if not isinstance(context, list):
        raise ValueError('第四项B相关背景须为列表')
    for entry in context:
        if entry.get('assessment_source'):
            # Quoted project prose stays verbatim and is labelled as such.
            if not isinstance(entry.get('story'), str) or not entry['story'].strip():
                raise ValueError('第四项B相关项目正文为空')
        else:
            _text(entry.get('story'), 'context.story')
        _text(entry.get('boundary'), 'context.boundary')
        refs = entry.get('source_refs')
        if entry.get('package_ref'):
            background = packages[entry['package_ref']]
            if background['ruler_id'] != row['ruler_id'] or background['axis'] == 'B' or refs != background.get('source_refs', []):
                raise ValueError('第四项B背景材料跨人、跨界或丢失引用')
        _sources(entry.get('sources'), refs or [])
    result = net_result(selected)
    eligible = [p for p in selected if p.get('scoring_eligibility') != 'REVOKED']
    if eligible and (axis['magnitude_grade'] != result['grade'] or axis['direction'] != result['direction']):
        raise ValueError('第四项B公开计算与正式档位不一致')
    points = axis['signed_adjustment']
    grade = int(result['grade'][3:])
    if not eligible:
        if points != 0:
            raise ValueError('无合格结果却有非零分')
        status = '复核后未确认独立净变化' if selected else '没有确认独立变化'
        calc = '当前没有满足本轴条件的独立结果参与合成，调整为0分；这不等于历史上没有相关行动或没有材料。'
    else:
        expected = POINTS[grade][BANDS.index(axis['band'])] * (1 if result['P'] > result['N'] else -1) if grade else 0
        if expected != points:
            raise ValueError('第四项B公开计算与正式分数不同值')
        if result['high_forbidden'] and axis.get('band') == 'HIGH':
            raise ValueError('第四项B公开档内位置违反重大负向或4级保留约束')
        status = '正负相抵，净调整为0' if not grade else ('正向' if points > 0 else '负向') + ' · ' + SCALE[grade-1] + ' · ' + {'LOW':'低位','MID':'中位','HIGH':'高位'}[axis['band']]
        calc = f'正向合成强度{result["P"]:g}，负向合成强度{result["N"]:g}；相减为{result["P"]-result["N"]:g}。'
        if result['H']:
            calc += f'另保留{result["H"]}级重大负向限制。'
        calc += f'按普通净算、4级保留及重大负向限制规则，最终幅度为{grade}级。'
        calc += f'取{ {"LOW":"低位","MID":"中位","HIGH":"高位"}.get(axis.get("band"), "零值")}，正式调整为{points:+g}分。' if points else '正负相抵，正式调整为0分；负向事实不会因此消失。'
    data.update(status=status, points=points, calculation=calc, method=METHOD, scale=SCALE)
    return data


def verify_readings(payload, root=None):
    packages = {p['package_code']:p for p in payload['accepted_packages']}
    for row in payload['records']:
        axis = next(a for a in row['axis_results'] if a['axis']=='B')
        axis_reading(row, axis, packages)
    if root is not None:
        from .formal_json_store import load_json
        cached = {}
        curve = load_json(root / CURVE_SOURCE)
        windows = {r['ruler_id']:r['actual_power_window'] for s in curve['dynasty_curve_segments'] for r in s['ruler_order']}
        for row in payload['records']:
            axis = next(a for a in row['axis_results'] if a['axis']=='B')
            expected_window = windows[row['ruler_id']]
            if isinstance(expected_window, list):
                expected_window = '；'.join(f'{w[0]}—{w[1]}年' for w in expected_window)
            if axis['public_reading']['window'] != expected_window:
                raise ValueError('第四项B阅读时期与当前正式窗口不一致')
            for entry in axis['public_reading'].get('context_items', []):
                path = entry.get('assessment_source')
                if not path:
                    continue
                if not path.startswith(('docs/', 'config/')) or '..' in path.split('/'):
                    raise ValueError('第四项B相关裁决来源路径非法')
                if path not in cached:
                    cached[path] = {r['ruler_id']:r for r in load_json(root / path)['records']}
                origin = cached[path].get(entry.get('assessment_ruler_id'))
                if origin is None or origin.get('ruler_name') != row['ruler_name']:
                    raise ValueError('第四项B相关裁决人物引用错误')
                if entry['assessment_field'] == 'public_story' and entry['story'] != origin['public_story']:
                    raise ValueError('第四项B引用的相关裁决正文已变化，须复核上游说明')
    return len(payload['records'])


def markdown_reading(data):
    def sources(refs):
        return '\n'.join('- ' + s['kind'] + '：' + (f'[{s["label"]}]({s["target"]})' if s['target'] else s['label']) for s in refs)
    lines = [f'**{data["question"]}**', '', f'评价时期：{data["window"]}。', '', data['story'], '', '**为什么这样评**', '', data['decision'], '', '**本人责任**', '', data['responsibility']]
    for entry in data['evidence_items']:
        lines += ['', f'#### {entry["title"]}', '', entry['status'], '', entry['story'], '', entry['baseline'], '', entry['responsibility'], '', entry['level_basis'], '', entry['coverage'], '', entry['duration'], '', entry['components'], '', entry['major_negative'], '', entry['boundary'], '', entry['source_note'], '', sources(entry['sources'])]
    for entry in data['context_items']:
        lines += ['', '**相关背景（不代替本轴结果证据）**', '', entry['story'], '', entry['boundary'], '', sources(entry['sources'])]
    lines += ['', '**计算与范围**', '', data['calculation'], '', data['method'], '', data['boundary'], '', data['source_note']]
    lines += ['', sources(data.get('assessment_sources', []))]
    return '\n'.join(lines)
