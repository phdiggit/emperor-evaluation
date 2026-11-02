"""Read-only C sources, current score synthesis, and authored zero explanations."""
from copy import deepcopy
from pathlib import Path

from .fourth_item_a import components
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


def axis_reading(row, axis, packages):
    from .fourth_item_results import axis_reading as current_reading
    return current_reading(row, axis, packages)


def verify_readings(payload, root=None):
    from .fourth_item_results import verify_readings as current_verify
    return current_verify(payload, root, 'C')


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
