"""Current independent-result settlement and deterministic public readings.

Grades and unit boundaries are adjudicated in the formal JSON, never inferred
from an axis total. All functions are offline; projection never changes scores.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib
import re

from .formal_json_store import load_json

SCHEMA = 'fourth-item-independent-results-v2'
BASE = Path('docs/评分结算/净收益/第四项文明与国家整合收益')
JSON_PATH = BASE / '01-第四项文明与国家整合收益正式结算.json'
TOTAL_PATH = BASE / '02-第四项文明与国家整合收益正式总榜.md'
POOL = Path('config/common/canonical-ruler-pool.json')
CONTRACT = 'docs/分项规则/第四项文明与国家整合收益/00-规则与计分合同.md'
AXIS_NAMES = {'A': '国家共同体与社会整合', 'B': '教育可及与人才流动', 'C': '文化知识生产传播与生态'}
AXIS_PATHS = {a: BASE / name / f'01-皇帝{a}项正式结算.md' for a, name in AXIS_NAMES.items()}
POINTS = {1: (1, 1.5, 2), 2: (3, 4, 5), 3: (8, 10, 12), 4: (16, 20, 24)}
BANDS = ('LOW', 'MID', 'HIGH')
SCALE = ['局部、短期或低强度变化', '清晰可验证的有限变化', '主要领域形成稳定的重大变化', '跨场景新范式或系统性破坏']
METHOD = '每条独立结果按层级与位置计价，正负采用同一价格表：1级为1/1.5/2分，2级为3/4/5分，3级为8/10/12分，4级为16/20/24分。逐条线性相加，三轴等权、总倍率1，不截断或饱和。合计不另定等级；数值相抵不表示损害已被修复。'


def price(result):
    if result.get('eligibility') != 'ADMITTED':
        raise ValueError('只有已准入结果可以计价')
    level, band, direction = result.get('level'), result.get('band'), result.get('direction')
    if type(level) is not int or level not in POINTS or band not in BANDS or direction not in ('POSITIVE', 'NEGATIVE'):
        raise ValueError('独立结果层级、带位或方向无效')
    return POINTS[level][BANDS.index(band)] * (1 if direction == 'POSITIVE' else -1)


def totals(results):
    values = [price(r) for r in results]
    positive = sum(max(v, 0) for v in values)
    negative = sum(max(-v, 0) for v in values)
    return {'positive_gross': positive, 'negative_gross': negative, 'signed_adjustment': positive-negative}


def disposition(results):
    if not results:
        return 'NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW'
    return 'SIGNED_CIVILIZATION_ADJUSTMENT_READY' if totals(results)['signed_adjustment'] else 'OBSERVED_OFFSETTING_OR_BALANCED_EFFECTS'


def public_text(value):
    """Translate notation only; historical claims remain those of the decision."""
    text = str(value or '')
    text = re.sub(r'R([1-4])(?:[-/](LOW|MID|HIGH))?', lambda m: m[1]+'级'+({'LOW':'低位','MID':'中位','HIGH':'高位'}.get(m[2], '')), text)
    text = text.replace('LOW', '低位').replace('MID', '中位').replace('HIGH', '高位')
    text = text.replace('本轮', '当前').replace('本次', '当前').replace('候选', '结果').replace('旧包', '原证据包').replace('闭合', '落实').replace('回填', '归入')
    return text


def _sources(refs):
    return [dict(original=s, target=s if s.startswith(('http://', 'https://', 'docs/', 'config/')) else '', label=s, kind='裁决所引材料') for s in dict.fromkeys(refs)]


def join_reading_text(*parts, separator=' '):
    """Keep the first occurrence of each complete sentence across adjacent fields."""
    seen = set()
    paragraphs = []
    for part in parts:
        unique = []
        for sentence in re.split(r'(?<=[。！？\n])', part):
            key = sentence.strip()
            if key not in seen or not key:
                seen.add(key)
                unique.append(sentence)
        remaining = ''.join(unique).strip()
        if remaining:
            paragraphs.append(remaining)
    return separator.join(paragraphs)


def axis_reading(row, axis, packages=None):
    if axis.get('calculation_version') != SCHEMA:
        raise ValueError('第四项阅读不接受旧净档接口')
    results = axis['results']
    total = totals(results)
    if any(axis.get(k) != v for k, v in total.items()):
        raise ValueError('第四项阅读与独立结果合计不同值')
    a = axis['axis']
    status = ('无准入结果' if not results else '正负相抵' if not total['signed_adjustment'] else '正向净额' if total['signed_adjustment'] > 0 else '负向净额')
    evidence = []
    for r in results:
        value = price(r)
        if value != r['contribution']:
            raise ValueError('第四项逐结果价格不同值')
        basis = public_text(r['basis'])
        refs = list(r['source_refs'])
        for e in r.get('evidence', []):
            for key in ('url', 'source_url', 'source_path', 'path', 'source'):
                if isinstance(e.get(key), str) and e[key].startswith(('http://', 'https://', 'docs/')):
                    refs.append(e[key])
        sources = _sources(refs)
        components = f'{r["level"]}级{dict(LOW="低位", MID="中位", HIGH="高位")[r["band"]]}，独立计入{value:+g}分。'
        boundary = public_text(r['cross_item_handoff']['basis'])
        entry = dict(result_id=r['result_id'], package_ref=r['result_id'], title=public_text(r['title']),
                     story=public_text(r['title']), result=public_text(r['title']), status='正向结果' if value > 0 else '负向损害',
                     baseline=public_text(axis['baseline_basis']), responsibility=public_text(axis['responsibility']),
                     level_basis=basis, coverage=basis, duration=public_text(axis['handoff_basis']),
                     components=components, major_negative='损害独立保留，数值相抵不代表修复。' if value < 0 else '',
                     hard_negative='损害独立保留，数值相抵不代表修复。' if value < 0 else '',
                     boundary=boundary, scope=join_reading_text(basis, boundary), source_note='下列材料用于本条结果；等级与责任判断属于项目裁决。',
                     sources=sources, exclusion_reason='')
        evidence.append(entry)
    calculation = '；'.join(f'{public_text(r["title"])} {r["contribution"]:+g}' for r in results)
    calculation += f'。正毛额{total["positive_gross"]:g}分，负毛额{total["negative_gross"]:g}分，净额{total["signed_adjustment"]:+g}分。'
    if not results:
        calculation = '当前复核未接纳独立结果，计0分；不等于没有相关历史活动。'
    reason = public_text(axis['decision_basis'])
    window = row['actual_power_window']
    if isinstance(window, list):
        window = '；'.join(f'{w[0]}—{w[1]}年' for w in window)
    return dict(question=f'{row["ruler_name"]}的{AXIS_NAMES[a]}发生了哪些独立变化？', window=str(window),
                story='；'.join(e['story'] for e in evidence) if evidence else reason,
                decision=reason, decision_basis=reason, zero_reason=reason if not total['signed_adjustment'] else '',
                responsibility=public_text(axis['responsibility']), boundary=public_text(axis['cross_item_handoff']['owned_outcome']),
                review_basis=reason, source_note='以当前有限证据评价本人窗口内的独立结果；未把其他项目缺少记录视为0分。',
                evidence_items=evidence, context_items=[], assessment_sources=_sources([JSON_PATH.as_posix(), CONTRACT]),
                status=status, points=total['signed_adjustment'], calculation=calculation, method=METHOD, scale=SCALE)


def project(payload):
    for row in payload['records']:
        for axis in row['axis_results']:
            reading = axis_reading(row, axis)
            axis['public_reading'] = reading
            axis['public_adjudication_summary'] = join_reading_text(reading['story'], reading['decision'], separator='\n')
            axis['public_boundary'] = reading['boundary']
            axis['public_level_label'] = reading['status']
            axis['public_component_label'] = AXIS_NAMES[axis['axis']]
            axis['public_evidence_items'] = [dict(id=e['result_id'], public_label=e['title'], public_role=e['status'],
                                                   public_basis=e['level_basis'], public_boundary=e['boundary']) for e in reading['evidence_items']]
            if not axis['public_evidence_items']:
                axis['public_evidence_items'] = [dict(id=row['ruler_id']+'-'+axis['axis']+'-none', public_label='无准入结果', public_role='证据复核', public_basis=reading['decision'], public_boundary=reading['boundary'])]
        row['public_boundary'] = '三轴独立结果等权相加；相抵不表示损害修复，合计不另定等级。'
        row['public_level_label'] = '独立结果净额'
        row['public_component_label'] = '第四项文明与国家整合'
    payload['public_projection_schema_version'] = SCHEMA
    payload['public_projection_status'] = 'FORMAL_UPSTREAM_SOURCE'
    payload['public_projection_record_count'] = len(payload['records'])
    return payload


def verify_projection(payload):
    if payload.get('schema_version') != SCHEMA or project(deepcopy(payload)) != payload:
        raise ValueError('第四项公开文案与当前来源转述不一致（独立结果接口）')
    return dict(status='PASS', schema_version=SCHEMA, record_count=len(payload['records']),
                package_count=len(payload['accepted_packages']))


def verify_readings(payload, root=None, axis_code=None):
    for row in payload['records']:
        for axis in row['axis_results']:
            if axis_code is None or axis['axis'] == axis_code:
                if axis.get('public_reading') != axis_reading(row, axis):
                    raise ValueError('第四项阅读不是独立结果的确定性投影')
    return len(payload['records'])


def verify_payload(payload, root):
    if payload.get('schema_version') != SCHEMA:
        raise ValueError('第四项必须采用独立结果正式接口')
    contract = payload.get('contract', {})
    if (contract.get('result_price_table') != {str(k):list(v) for k,v in POINTS.items()}
            or contract.get('axis_weights') != dict(A=1, B=1, C=1)
            or contract.get('multiplier') != 1
            or contract.get('range') is not None or contract.get('axis_range') is not None):
        raise ValueError('第四项价格、权重或无上限合同不一致')
    if payload.get('adoption_review', {}).get('status') != 'CURRENT_FINITE_EVIDENCE_ADJUDICATION_CLOSED':
        raise ValueError('第四项逐结果裁决尚未完成')
    documents = {}
    for source in payload.get('source_documents', []):
        path = root / source['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('第四项史源内容变化，须复核引用: '+str(path))
        documents[source['path']] = path.read_text(encoding='utf-8')
    def check_refs(value):
        if isinstance(value, dict):
            source = next((value[k] for k in ('source_path','path','source') if isinstance(value.get(k), str) and value[k] in documents), None)
            if source and value.get('anchor') and ''.join(value['anchor'].split()) not in ''.join(documents[source].split()):
                raise ValueError('第四项史源锚与原文不一致: '+source)
            for v in value.values():
                check_refs(v)
        elif isinstance(value, list):
            for v in value:
                check_refs(v)
        elif isinstance(value, str):
            if '.tmp/' in value or '.tmp\\' in value:
                raise ValueError('正式第四项不得依赖临时目录')
    check_refs(payload['records'])
    pool = load_json(root / POOL)['records']
    pool_by_source = {r['source_item_ids']['fourth_item']: r for r in pool}
    included = {r['source_item_ids']['fourth_item'] for r in pool if r['pool_status'] == 'INCLUDED'}
    excluded = {r['source_item_ids']['fourth_item'] for r in pool if r['pool_status'] == 'EXCLUDED'}
    ids = [r['ruler_id'] for r in payload['records']]
    if len(ids) != len(set(ids)) or set(ids) != included:
        raise ValueError('第四项正式记录与规范池入池对象不一致')
    if {r['ruler_id'] for r in payload['excluded_records']} != excluded:
        raise ValueError('第四项排除对象范围不一致')
    if any(r.get('fourth_item_signed_adjustment') is not None for r in payload['excluded_records']):
        raise ValueError('池外记录不可伪装成新制计分')
    seen = set()
    bindings = {}
    for row in payload['records']:
        if not row.get('actual_power_window') or Counter(a['axis'] for a in row['axis_results']) != Counter('ABC'):
            raise ValueError('本人窗口或三轴覆盖错误')
        def normalize_window(value):
            return str(value).replace('—', '-').replace('年', '').replace('；', ';').replace(' ', '')
        if normalize_window(row['actual_power_window']) != normalize_window(pool_by_source[row['ruler_id']]['actual_power_window']):
            raise ValueError('第四项本人窗口与规范池不一致')
        for axis in row['axis_results']:
            if axis.get('calculation_version') != SCHEMA or any(axis.get(k) is not None for k in ('magnitude_grade', 'band')):
                raise ValueError('禁止以旧轴净档或带位计算')
            if not axis.get('decision_basis') or not axis.get('zero_scan_checked') or not axis.get('baseline_basis') or not axis.get('handoff_basis'):
                raise ValueError('缺少裁决、反漏检、基线或交班依据')
            if axis.get('source_coverage') not in ('ADEQUATE', 'PARTIAL_BUT_SUFFICIENT'):
                raise ValueError('证据不足不得宣称本轴正式就绪')
            handoff = axis['cross_item_handoff']
            if not handoff.get('owned_outcome') or not handoff.get('neighbor_bindings'):
                raise ValueError('缺少跨项拥有者')
            for b in handoff['neighbor_bindings']:
                if not b.get('reserved_outcome'):
                    raise ValueError('缺少邻项消费边界')
                if b['status'] == 'CURRENT_RECORD_BOUND':
                    path, rid = b['source'].split('#ruler_id=')
                    if path not in bindings:
                        source = load_json(root / path)
                        bindings[path] = {r['ruler_id'] for r in source.get('records', source.get('scores', []))}
                    if rid not in bindings[path]:
                        raise ValueError('邻项正式引用不存在: '+b['source'])
                elif b['status'] != 'NO_CURRENT_RECORD_RESERVATION_FOR_FUTURE_SETTLEMENT':
                    raise ValueError('邻项缺口状态无效')
            for result in axis['results']:
                rid = result['result_id']
                if rid in seen:
                    raise ValueError('独立结果ID重复: '+rid)
                seen.add(rid)
                if result['contribution'] != price(result):
                    raise ValueError('独立结果价格不同值: '+rid)
                if not result.get('basis') or not result.get('unit_relation') or not (result.get('source_refs') or result.get('evidence')):
                    raise ValueError('缺少结果理由、单位关系或史源: '+rid)
                if result['cross_item_handoff'].get('owner') != 'I4.'+axis['axis']:
                    raise ValueError('跨项消费拥有者错误: '+rid)
                if result.get('parent_result_id') in {r['result_id'] for r in axis['results']}:
                    raise ValueError('父子结果不得重复计价')
            expected = totals(axis['results'])
            if any(axis.get(k) != v for k, v in expected.items()) or axis['disposition'] != disposition(axis['results']):
                raise ValueError('第四项轴毛净额或零值处置错误')
        p = sum(a['positive_gross'] for a in row['axis_results'])
        n = sum(a['negative_gross'] for a in row['axis_results'])
        if (row['positive_gross'], row['negative_gross'], row['fourth_item_signed_adjustment']) != (p, n, p-n):
            raise ValueError('第四项全项毛净额错误')
        expected_rank = 1+sum(r['fourth_item_signed_adjustment'] > p-n for r in payload['records'])
        if row['rank'] != expected_rank:
            raise ValueError('第四项竞争排名错误')
    verify_projection(payload)
    return dict(status='PASS', scope=SCHEMA, ruler_count=len(ids), result_count=len(seen), semantic_review_complete=True)


def markdown_reading(data):
    lines = [f'**{data["question"]}**', '', f'评价时期：{data["window"]}', '', data['decision'], '']
    for e in data['evidence_items']:
        explanation = join_reading_text(e['level_basis'], e['responsibility'], e['boundary'], separator='\n\n')
        lines += ['#### '+e['title'], '', e['components'], '', explanation, '']
        lines += ['- '+(f'[{s["label"]}]({s["target"]})' if s['target'] else s['label']) for s in e['sources']]
        lines += ['']
    lines += [data['calculation'], '', data['method'], '', data['source_note']]
    return '\n'.join(lines)


def render(payload):
    rows = payload['records']
    total = ['# 第四项文明与国家整合收益正式总榜', '', METHOD, '', '只列规范池入池对象；综合就绪另按规范池判断，排除对象保留在正式JSON的excluded_records。', '',
             '| 排名 | 人物 | A净额 | B净额 | C净额 | 正毛额 | 负毛额 | 净额 |', '|---:|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        v = {a['axis']:a['signed_adjustment'] for a in r['axis_results']}
        total.append(f'| {r["rank"]} | {r["ruler_name"]} | {v["A"]:g} | {v["B"]:g} | {v["C"]:g} | {r["positive_gross"]:g} | {r["negative_gross"]:g} | {r["fourth_item_signed_adjustment"]:g} |')
    views = {TOTAL_PATH:'\n'.join(total)+'\n'}
    for a in 'ABC':
        lines = ['# 第四项'+a+'轴'+AXIS_NAMES[a]+'正式结算', '', METHOD, '']
        for row in rows:
            axis = next(x for x in row['axis_results'] if x['axis'] == a)
            lines += ['## '+row['ruler_name'], '', markdown_reading(axis_reading(row, axis)), '']
        views[AXIS_PATHS[a]] = '\n'.join(lines).rstrip()+'\n'
    return views


def verify(root, *, check_views=True):
    payload = load_json(root / JSON_PATH)
    report = verify_payload(payload, root)
    if check_views:
        for path, content in render(payload).items():
            if not (root/path).is_file() or (root/path).read_text(encoding='utf-8') != content:
                raise ValueError('第四项阅读视图不同值: '+str(path))
    return report


def write_views(root):
    verify(root, check_views=False)
    for path, content in render(load_json(root/JSON_PATH)).items():
        (root/path).parent.mkdir(parents=True, exist_ok=True)
        if not (root/path).is_file() or (root/path).read_text(encoding='utf-8') != content:
            (root/path).write_text(content, encoding='utf-8', newline='\n')
    return verify(root)
