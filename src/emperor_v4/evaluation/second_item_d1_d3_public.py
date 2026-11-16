"""Validate authored D1/D3 records and project shared reading guidance."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json

D1_PATH = Path('docs/评分结算/净收益/第二项治国净收益/政权交接稳定/01-D1继任行政连续性方向卡.json')
D3_PATH = D1_PATH.with_name('02-D3政权交接稳定方向卡.json')
PUBLIC_PROJECTION_SCHEMA = 'second-item-d1-d3-authored-public-v2'
PUBLIC_RECORD_FIELDS = ('public_story', 'public_adjudication_summary', 'public_window',
                        'public_responsibility', 'public_boundary', 'public_evidence_items')
PUBLIC_EVIDENCE_FIELDS = ('id', 'public_label', 'public_role', 'public_basis',
                         'public_boundary', 'evidence_mode', 'source_refs')
PUBLIC_FORBIDDEN_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:D[13]|H[0-5]|G[0-5]|M[0-3])(?:-[A-Z0-9_]+)?(?![A-Za-z0-9])|'
    r'[A-Za-z][A-Za-z_:-]{1,}|本轮|重裁|门禁|闭合|主档|倒灌|position|跨窗|消费')
BROKEN_TEXT_RE = re.compile(r'(?:止于|达到|裁为|取|判为)[。；]|。；|、。|未提供可直述|形成持续的实际结果')
MODES = dict(DIRECT='史料直接记载', INFERRED='受约束推断', ASSESSMENT='正式评价判断', BACKGROUND='背景核对')

SCOPE_GUIDE = {
    'D1': (
        '从本人实际最高治理权终止起，通常观察三年内人员、官署和命令是否继续运行。'
        '最上档还可参考本人明确留下并获持续接用的行政资产，旁证看接用关系和实际价值。继任者的新政以及人员自己的能力和军功分别归责。',
        '争位影响本项的条件是实际中断行政。政策成效、廉洁、战争伤亡和继承安全各有评价范围。'
        '逐条材料区分原文与史料摘要，采用可定位的行政运行或断裂事实。',
    ),
    'D3': (
        '从最后有效继承安排观察至实际权力承接，再观察约一年。摄政按实际失权开窗。'
        '本人承担其安排延续下来的争位和控制权风险。一年内开始的同一冲突可追至结束，继任者独立引发的新冲突另行归责。',
        '档位看最高权力是否有效承接，是否发生争位、暴力接管或中央分裂。'
        '和平投降、名义继承和幼主身份均须结合实际承接结果。行政表现与后世治乱各有评价范围。',
    ),
}

_D1_BOUNDARY = (
    '行政连续不等于政策正确、官员廉洁或继承过程和平。'
    '交接争位只有造成官署、人员或命令的实际断裂时才影响本项；不重复计入战争伤亡和日常行政的政策收益。'
)
_D3_BOUNDARY = (
    '本项看最高权力是否形成有效接续，以及是否出现争位、暴力接管或中央分裂；'
    '不以行政机器后来好坏替代交接安全，也不将后世王朝寿命归给前任。'
)
_SHARED_SCOPE = {
    'D1': {
        'public_window': (
            '从本人实际最高治理权终止后起，通常观察三年内旧人员、官署及命令的实际运行。'
            '最上档还可采用有明确任用与连续使用关系的长期资产旁证；'
            '旁证不按经过年数加分，也不将继任者独立决策或全部成果归给前任。',
        ),
        'public_responsibility': (
            '只评价本人留下的行政资产是否被实际接用；'
            '继任者的独立新政及工作人员本人的能力、军功分别保留，不全部归给前任。',
        ),
        'public_boundary': (
            '所引原文与既有摘要分列；本条仅采用其中可定位的行政运行或断裂事实。' + _D1_BOUNDARY,
            _D1_BOUNDARY,
        ),
    },
    'D3': {
        'public_window': (
            '从最后有效继承安排观察至实际权力承接，再观察约一年；只追踪前任安排直接延续的争位或控制权风险。'
            '已在一年内开始的同一冲突可追至结束；继任者新造的冲突及更晚治乱不计入。',
        ),
        'public_responsibility': (
            '只评价本人退出时留下的继承安排及其即时权力结果；摄政者按实际权力终止点观察。'
            '和平投降、名义继承或幼主身份均不单独决定档位。',
        ),
        'public_boundary': (_D3_BOUNDARY,),
    },
}


def display_scope(value, axis, field):
    """Keep case details when the shared passage already appears in the guide."""
    for shared in _SHARED_SCOPE[axis][field]:
        if value == shared:
            return ''
        if value.endswith('。' + shared):
            return value.removesuffix(shared)
        if value.startswith(shared + ' '):
            return value.removeprefix(shared).lstrip()
    return value


def _plain_source_excerpt(value):
    """Check transcription formatting only; retain source words and editorial notes."""
    value = re.sub(r'\{\{header2\b.*?\}\}', '', value, flags=re.S)
    value = re.sub(r'\{\{YL\|([^{}]+)\}\}', r'\1', value)
    value = re.sub(r'<br\s*/?>', '\n', value, flags=re.I)
    value = re.sub(r'<ref\b[^>]*>(.*?)</ref>', r'〔校注：\1〕', value, flags=re.S | re.I)
    value = re.sub(r'</?(?:span|div|p)\b[^>]*>', '', value, flags=re.I)
    value = re.sub(r'\[\[(?:[^\]\n|]+\|)?([^\]\n]+)\]\]', r'\1', value)
    return value.replace("'''", '').strip()


def _scoring_signature(payload):
    rows = [{k: v for k, v in row.items() if not k.startswith('public_')} for row in payload.get('records', [])]
    return json.dumps(sorted(rows, key=lambda r: r['ruler_id']), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def public_record(row):
    """Format retained quotations for reading without modifying adopted evidence."""
    result = copy.deepcopy(row)
    for item in result['public_evidence_items']:
        for ref in item['source_refs']:
            excerpt = ref.get('excerpt')
            if not isinstance(excerpt, str) or not excerpt.strip():
                raise ValueError('D1/D3史源缺少excerpt')
            formatted = _plain_source_excerpt(excerpt)
            if not formatted:
                raise ValueError('D1/D3展示引文为空')
            if 'public_excerpt' in ref and ref['public_excerpt'] != formatted:
                raise ValueError('D1/D3引文展示与原始转录文字不同值')
            ref['public_excerpt'] = formatted
    return result


def display_source(ref):
    from .second_item_c_source_display import bibliographic_source, display_project_summary

    kind = {
        '史料原文引句（登记转录）': '史料原文引句',
        '既有史料摘要（含转录引句）': '项目史料摘要（含引句）',
    }.get(ref['source_kind'], ref['source_kind'])
    excerpt = ref['public_excerpt']
    if kind.startswith('项目史料摘要'):
        excerpt = display_project_summary(excerpt)
    return {**bibliographic_source(ref), 'source_kind': ref.get('public_source_kind', kind),
            'public_excerpt': ref.get('public_source_excerpt', excerpt),
            'source_context': ref.get('public_source_context', ''), 'support_role': ref.get('support_role', '')}


def display_reason(record):
    summary = record['public_adjudication_summary']
    story = record['public_story']
    prefix = summary.removesuffix(story).rstrip()
    return prefix if summary.endswith(story) and prefix.endswith('。') else summary


def _verify_text(value, *, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'D1/D3公开正文为空：{name}')
    if PUBLIC_FORBIDDEN_RE.search(value) or BROKEN_TEXT_RE.search(value):
        raise ValueError(f'D1/D3公开正文含内部术语或残句：{name}')


def _refresh_payload(payload, axis):
    if axis not in ('D1', 'D3'):
        raise ValueError(f'未知交接轴：{axis}')
    for row in payload.get('records', []):
        for key in PUBLIC_RECORD_FIELDS:
            if key not in row:
                raise ValueError(f'{axis}缺少直接维护的公开字段：{row.get("ruler_name")}/{key}')
        public_record(row)
        for item in row['public_evidence_items']:
            for ref in item['source_refs']:
                ref.pop('public_excerpt', None)
    payload.update(public_projection_schema_version=PUBLIC_PROJECTION_SCHEMA,
                   public_projection_axis=axis, public_projection_status='FORMAL_UPSTREAM_SOURCE',
                   public_projection_record_count=len(payload.get('records', [])),
                   public_projection_evidence_item_count=sum(len(r['public_evidence_items']) for r in payload.get('records', [])),
                   public_projection_source={
                       'formal_contract': 'docs/分项规则/第二项治国净收益/政权交接稳定/00-规则与结算合同.md',
                       'reader_policy': '公开正文、边界和逐条史源直接维护在正式记录；投影只同步元数据和阅读视图。',
                   })
    return payload


def _verify_source(root, ref, cache):
    for key in ('path', 'source_title', 'source_locator', 'source_kind', 'excerpt'):
        if not isinstance(ref.get(key), str) or not ref[key].strip():
            raise ValueError(f'D1/D3史源缺少{key}')
    if 'public_excerpt' in ref:
        raise ValueError('D1/D3只保存原始引文，不得内嵌展示引文副本')
    for key in ('public_source_title', 'public_source_kind', 'public_source_excerpt',
                'public_source_context', 'public_source_locator', 'public_source_url'):
        if key in ref and (not isinstance(ref[key], str) or not ref[key].strip()):
            raise ValueError(f'D1/D3公开史源说明为空：{key}')
    if not _plain_source_excerpt(ref['excerpt']):
        raise ValueError('D1/D3展示引文为空')
    relative = Path(ref['path'])
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to((root / 'docs').resolve()) or not path.is_file():
        raise ValueError(f'D1/D3史源路径无效：{relative}')
    if path not in cache:
        cache[path] = load_json(path) if path.suffix == '.json' else path.read_text(encoding='utf-8')
    source = cache[path]
    if ref.get('material_id'):
        material = next((m for m in source.get('records', []) if m.get('material_id') == ref['material_id']), None)
        if material is None:
            raise ValueError(f'D1/D3史源材料不存在：{ref["material_id"]}')
        candidates = [e for e in material.get('evidence', []) if isinstance(e, dict)]
        if not any(e.get('evidence_id') == ref.get('evidence_id') and e.get('exact_quote') == ref['excerpt']
                   and (e.get('source_url') or '') == ref.get('source_url', '') for e in candidates):
            raise ValueError(f'D1/D3引文与材料登记不一致：{ref["material_id"]}')
    elif isinstance(source, str):
        if ref['excerpt'] not in source:
            raise ValueError(f'D1/D3引文不在所引文件中：{relative}')
        line = source[:source.index(ref['excerpt'])].count('\n') + 1
        if ref.get('line') != line:
            raise ValueError(f'D1/D3引文行号不一致：{relative}')
    else:
        def matches(value):
            if isinstance(value, dict):
                if value.get('evidence_id') == ref.get('evidence_id') and value.get('exact_quote') == ref['excerpt']:
                    return True
                return any(matches(v) for v in value.values())
            return isinstance(value, list) and any(matches(v) for v in value)
        if not ref.get('evidence_id') or not matches(source):
            raise ValueError(f'D1/D3独立史源引文不一致：{relative}')
    url = ref.get('source_url', '')
    # Older material registers also retain book labels and retired cache locators.
    # These remain provenance text; the reader links only HTTPS and current docs.
    if url and re.match(r'[A-Za-z][A-Za-z0-9+.-]*:', url) and not url.startswith('https://'):
        raise ValueError('D1/D3史源链接协议无效')


def _verify_payload(root, payload, axis, cache):
    if payload != _refresh_payload(copy.deepcopy(payload), axis):
        raise ValueError(f'{axis}公开元数据未同步')
    ids, names, evidence_ids = set(), set(), set()
    for row in payload['records']:
        if row['ruler_id'] in ids or row['ruler_name'] in names:
            raise ValueError(f'{axis}人物身份重复')
        ids.add(row['ruler_id']); names.add(row['ruler_name'])
        for key in PUBLIC_RECORD_FIELDS:
            if key != 'public_evidence_items':
                _verify_text(row[key], name=f'{row["ruler_name"]}/{key}')
        items = row['public_evidence_items']
        if not isinstance(items, list) or not items:
            raise ValueError(f'{axis}缺少逐条材料：{row["ruler_name"]}')
        for item in items:
            if set(item) != set(PUBLIC_EVIDENCE_FIELDS) or item['id'] in evidence_ids:
                raise ValueError(f'{axis}材料字段或身份无效：{row["ruler_name"]}')
            evidence_ids.add(item['id'])
            for key in ('public_label', 'public_role', 'public_basis', 'public_boundary'):
                _verify_text(item[key], name=f'{row["ruler_name"]}/{key}')
            if item['evidence_mode'] not in MODES:
                raise ValueError(f'{axis}材料须声明直接记载、推断、裁决或背景')
            if not isinstance(item['source_refs'], list) or not item['source_refs']:
                raise ValueError(f'{axis}逐条材料缺少史源：{row["ruler_name"]}')
            for ref in item['source_refs']:
                _verify_source(root, ref, cache)
        if axis == 'D1':
            adopted = set(row.get('direct_material_ids', []))
            permitted = adopted | set(row.get('verification_material_ids', []))
            referenced = {ref['material_id'] for item in items for ref in item['source_refs'] if ref.get('material_id')}
            if not adopted <= referenced or not referenced <= permitted:
                raise ValueError(f'D1公开史源与当前采用材料不一致：{row["ruler_name"]}')
    return dict(status='PASS', axis=axis, record_count=len(ids), public_evidence_item_count=len(evidence_ids), schema_version=PUBLIC_PROJECTION_SCHEMA)


def render_public_markdown(payload, axis):
    from .reading_layout import evidence_repeated_in_story

    title = '行政连续性' if axis == 'D1' else '交接稳定'
    lines = [f'# {title}正式阅读视图', '', '> 档内指数不单独加分。', '',
             '<a id="handoff-scope"></a>', '', '## 共同评价范围', '']
    for paragraph in SCOPE_GUIDE[axis]:
        lines += [paragraph, '']
    for row in payload['records']:
        row = public_record(row)
        grade = int(row['handoff_level'][-1] if axis == 'D1' else row['D3_grade'][-1])
        lines += [f'## {row["ruler_name"]}（{row["polity"]}）', '',
                  f'- 公开档位：{"EDCBAS"[grade]}；内部指数：{row["direction_index"]}。', '',
                  row['public_story'], '', '**为什么这样评**', '', display_reason(row), '']
        for field, label in (('public_window', '观察范围'), ('public_responsibility', '本人责任'), ('public_boundary', '评价限制')):
            if detail := display_scope(row[field], axis, field):
                lines += [detail if detail.startswith('实际退出点：') else f'{label}：{detail}', '']
        lines += ['[查看共同评价范围](#handoff-scope)', '']
        repeated = set(evidence_repeated_in_story(row))
        for item in row['public_evidence_items']:
            basis = '' if item['id'] in repeated else item['public_basis']
            lines += [f'### {item["public_label"]}（{MODES[item["evidence_mode"]]}）', '']
            if basis:
                lines += [basis, '']
            if boundary := display_scope(item['public_boundary'], axis, 'public_boundary'):
                lines += [boundary, '']
            for raw in item['source_refs']:
                ref = display_source(raw)
                citation = ' · '.join(ref[key] for key in ('source_kind', 'source_title', 'source_locator') if ref[key])
                lines += [f'- {citation}', '']
                if ref['source_context']:
                    lines += [ref['source_context'], '']
                if ref['public_excerpt'] != basis:
                    lines += ['\n'.join('> ' + line.rstrip() if line.rstrip() else '>' for line in ref['public_excerpt'].split('\n')), '']
                if ref.get('support_role'):
                    lines += [ref['support_role'], '']
                if ref['source_urls']:
                    lines += [' · '.join(f'[查看所引史源]({url})' for url in ref['source_urls']), '']
    return '\n'.join(lines).rstrip() + '\n'


def verify_public_projection(workspace_root, *, payloads=None):
    payloads = payloads if payloads is not None else {'D1': load_json(workspace_root / D1_PATH), 'D3': load_json(workspace_root / D3_PATH)}
    cache = {}
    reports = {axis: _verify_payload(workspace_root, payloads[axis], axis, cache) for axis in ('D1', 'D3')}
    if {r['ruler_id'] for r in payloads['D1']['records']} != {r['ruler_id'] for r in payloads['D3']['records']}:
        raise ValueError('D1/D3公开对象不一致')
    return dict(status='PASS', record_count=reports['D1']['record_count'], **reports)


def run(workspace_root, *, write=False):
    paths = {'D1': workspace_root / D1_PATH, 'D3': workspace_root / D3_PATH}
    current = {axis: load_json(path) for axis, path in paths.items()}
    projected = {axis: _refresh_payload(copy.deepcopy(payload), axis) for axis, payload in current.items()}
    report = verify_public_projection(workspace_root, payloads=projected)
    for axis, path in paths.items():
        text = render_public_markdown(projected[axis], axis)
        if write:
            write_json(path, projected[axis], ruler_polities=load_ruler_polities(workspace_root))
            path.with_suffix('.md').write_text(text, encoding='utf-8', newline='\n')
        elif current[axis] != projected[axis] or path.with_suffix('.md').read_text(encoding='utf-8') != text:
            raise ValueError(f'{axis}公开元数据或Markdown未同步；运行second-item-d1-d3-public --write')
    return report
