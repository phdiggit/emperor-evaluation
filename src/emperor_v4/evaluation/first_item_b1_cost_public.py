"""Consume declared B1 and military-cost public prose without rewriting it."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.first_item_public_outcomes import (
    _parse_source_sections, SOURCE_MARKDOWN_PATH as A_SOURCE,
)
from emperor_v4.evaluation.first_item_b1_inputs import load_b1_inputs, load_opponent_systems, b1_components, calculation_text, INPUTS
import json

BASE = Path('docs/评分结算/净收益/第一项政权奠基与统一贡献及能力')
B1_SOURCE = BASE / '02-第一项B1创业难度与战略效率正式结算.md'
COST_SOURCE = BASE / '06-军事成本正式裁决.json'
SCHEMA = 'first-item-b1-cost-public-v1'
B1_FIELDS = {'公开起点说明':'public_start_basis', '公开对手说明':'public_opponent_basis', '公开效率说明':'public_efficiency_basis', '公开阅读问题':'public_question', '公开阅读正文':'public_story'}
POSITIONS = {'LOW':'低位','MID':'中位','HIGH':'高位','HIGHEST':'极端上沿'}
STATUSES = {'CONFIRMED':'关键结构已证实', 'LOWER_BOUND':'已证实下界，覆盖或上限仍有缺口', 'PROVISIONAL':'关键条件仍待确认'}


def public_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'第一项公开来源缺少{field}，禁止阅读层从内部文字补写')
    if re.search(r'[A-Za-z]|\{\{', value):
        raise ValueError(f'第一项公开说明含未转述术语：{field}')
    return value.strip()


def project_b1(fields: dict[str, str]) -> dict[str, Any]:
    result = {target: public_text(fields.get(source), source) for source,target in B1_FIELDS.items()}
    # This is the declared arithmetic, displayed only in the calculation panel.
    result['public_calculation'] = fields['B1结算']
    return result


def project_cost(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: public_text(row.get(key),key) for key in ('public_basis','public_responsibility_window')}
    gaps = row.get('public_unresolved_gaps')
    if not isinstance(gaps,list) or len(gaps) != len(row.get('unresolved_gaps',[])):
        raise ValueError('成本公开证据缺口须逐条保留')
    result['public_unresolved_gaps'] = [public_text(gap,'public_unresolved_gaps') for gap in gaps]
    links = row.get('public_source_links')
    if not isinstance(links,list):
        raise ValueError('成本公开补充来源须明确登记')
    result['public_source_links'] = []
    for link in links:
        if not isinstance(link,dict) or set(link) != {'label','url'}:
            raise ValueError('成本公开来源格式无效')
        parsed = urlparse(link['url'])
        if parsed.scheme not in {'http','https'} or not parsed.netloc:
            raise ValueError('成本公开来源协议无效')
        result['public_source_links'].append({'label':public_text(link['label'],'source label'),'url':link['url']})
    band = str(row.get('cost_band',''))
    if not re.fullmatch(r'C[0-7]',band) or row.get('cost_position') not in POSITIONS or row.get('evidence_status') not in STATUSES:
        raise ValueError('成本公开等级或证据状态无效')
    result['public_level_label'] = f"第{band[1]}级 · {POSITIONS[row['cost_position']]}"
    result['public_status_label'] = STATUSES[row['evidence_status']]
    return result


def load_first_item_b1_cost_public(root: Path) -> tuple[dict, dict]:
    expected = _parse_source_sections(root / A_SOURCE)
    b1 = _parse_source_sections(root / B1_SOURCE)
    costs = load_json(root / COST_SOURCE)['records']
    cost_by_name = {row['ruler_name']:row for row in costs}
    if not expected or set(b1) != set(expected) or set(cost_by_name) != set(expected) or len(cost_by_name) != len(costs):
        raise ValueError('B1/成本公开记录须完整覆盖当前第一项正式对象且不得重复')
    inputs = load_b1_inputs(root)
    systems = load_opponent_systems(root)
    method = json.loads((root / INPUTS).read_text(encoding='utf-8'))['public_method']
    projected = {}
    for name, fields in b1.items():
        record = project_b1(fields)
        record.update(b1_components(inputs[name], systems))
        record['public_calculation'] = calculation_text(inputs[name], systems)
        record['public_method'] = method
        record['public_sources'] = list(dict.fromkeys([
            B1_SOURCE.as_posix(), INPUTS.as_posix(), 'config/military/opponent-system-contract.json',
            'docs/公共成果/军事/01-战役登记.json',
            *[ref for ref in inputs[name]['source_refs'] if ref.startswith(('http://', 'https://', 'docs/', 'config/'))],
        ]))
        projected[name] = record
    for field in ('public_question', 'public_story'):
        if len({r[field] for r in projected.values()}) != len(projected):
            raise ValueError(f'B1人物阅读入口重复：{field}')
    return (projected,
            {name:project_cost(row) for name,row in cost_by_name.items()})


def verify_first_item_b1_cost_public(root: Path) -> dict[str, Any]:
    b1,cost = load_first_item_b1_cost_public(root)
    return {'status':'PASS','schema_version':SCHEMA,'b1_record_count':len(b1),'cost_record_count':len(cost)}
