"""Shared A/B authored reading; axis selection never changes formal decisions."""
from copy import deepcopy
import re
from urllib.parse import urlsplit
from .fourth_item_a import components
from .fourth_item_results import METHOD, SCALE

CURVE_SOURCE = 'docs/评分结算/净收益/第四项文明与国家整合收益/03-第四项共享曲线交班锚与去重审计.json'
SCOPE_SOURCE = 'config/common/canonical-ruler-pool.json'
INTERNAL = re.compile(r'结果方向未单列|责任范围按现有材料区分|过期表述|本轮|本批|旧包|本包|撤资格|闭合|回填|回灌|横校|[A-Z]{2,}_[A-Z_]+|(?:R|P|N|CIV)[0-4](?:\b|(?=[\u4e00-\u9fff]))')


class AxisReading:
    """Bind the shared public projection and validation to one formal axis."""

    def __init__(self, axis_code):
        self.axis_code = axis_code
        self.schema = f'fourth-item-{axis_code.lower()}-authored-public-v1'

    def _text(self, value, field):
        if not isinstance(value, str) or not value.strip() or INTERNAL.search(value):
            raise ValueError(f'第四项{self.axis_code}公开正文无效：{field}={value!r}')
        return value

    def _sources(self, sources, expected):
        if not isinstance(sources, list) or [s.get('original') for s in sources] != list(expected):
            raise ValueError(f'第四项{self.axis_code}逐条史源与正式来源不同值')
        for source in sources:
            self._text(source.get('label'), 'source.label')
            self._text(source.get('kind'), 'source.kind')
            original = source['original']
            target = source.get('target', '')
            if target and (target != original or not target.startswith(('https://', 'http://', 'docs/', 'config/'))):
                raise ValueError(f'第四项{self.axis_code}来源链接不合法或与原引用不一致')

    def package_reading(self, package):
        data = deepcopy(package.get('public_reading'))
        if not isinstance(data, dict) or data.get('schema') != self.schema:
            raise ValueError(f"缺少第四项{self.axis_code}影响材料正文：{package['package_code']}")
        for field in ('title', 'story', 'baseline', 'responsibility', 'level_basis', 'coverage', 'duration', 'boundary', 'source_note'):
            self._text(data.get(field), field)
        self._sources(data.get('sources'), package.get('source_refs', []))
        p, n = components(package)
        revoked = package.get('scoring_eligibility') == 'REVOKED'
        data['status'] = ('不单独计分，保留相关事实' if revoked else
                          '正负结果并存' if p and n else '正向结果' if p else '负向损害' if n else '未形成可计入结果')
        data['components'] = f'正向结果强度{p}级；负向损害强度{n}级。' + ('相关事实不参与本轴合成。' if revoked else '')
        data['major_negative'] = '重大负向限制已触发，须与正向成果分开保留。' if package.get('hard_negative_gate') == 'ACTIVE' and not revoked else '该材料未触发独立的重大负向限制。'
        return data

    def axis_reading(self, row, axis, packages):
        from .fourth_item_results import axis_reading
        return axis_reading(row, axis, packages)

    def verify_readings(self, payload, root=None):
        from .fourth_item_results import verify_readings
        return verify_readings(payload, root, self.axis_code)


def source_label(ref):
    if ref.startswith(('https://', 'http://')):
        return urlsplit(ref).hostname or '来源页面'
    return ref


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
