"""Validate authored D1/D3 public records; project prose without rewriting it."""
from __future__ import annotations

import copy
import json
import os
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
    for key in ('path', 'source_title', 'source_locator', 'source_kind', 'excerpt', 'public_excerpt'):
        if not isinstance(ref.get(key), str) or not ref[key].strip():
            raise ValueError(f'D1/D3史源缺少{key}')
    if ref['public_excerpt'] != _plain_source_excerpt(ref['excerpt']):
        raise ValueError('D1/D3引文展示与原始转录文字不同值')
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
    title = '行政连续性' if axis == 'D1' else '交接稳定'
    lines = [f'# {title}正式阅读视图', '', '> 正文、逐条史源与限制逐字读取正式JSON；档内指数不单独加分。', '']
    for row in payload['records']:
        grade = int(row['handoff_level'][-1] if axis == 'D1' else row['D3_grade'][-1])
        lines += [f'## {row["ruler_name"]}（{row["polity"]}）', '',
                  f'- 公开档位：{"EDCBAS"[grade]}；内部指数：{row["direction_index"]}。', '',
                  row['public_story'], '', '**为什么这样评**', '', row['public_adjudication_summary'], '',
                  f'观察范围：{row["public_window"]}', '', f'本人责任：{row["public_responsibility"]}', '',
                  f'评价限制：{row["public_boundary"]}', '']
        for item in row['public_evidence_items']:
            lines += [f'### {item["public_label"]}（{MODES[item["evidence_mode"]]}）', '', item['public_basis'], '', item['public_boundary'], '']
            for ref in item['source_refs']:
                target = os.path.relpath(ref['path'], D1_PATH.parent).replace('\\', '/')
                lines += [f'- {ref["source_kind"]} · {ref["source_title"]} · {ref["source_locator"]}', '',
                          '\n'.join('> ' + line.rstrip() if line.rstrip() else '>' for line in ref['public_excerpt'].split('\n')), '',
                          f'[查看所引记录]({target})' + (f' · [查看史源]({ref["source_url"]})' if ref.get('source_url', '').startswith('https://') else ''), '']
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
