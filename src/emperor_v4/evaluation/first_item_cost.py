from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.first_item_markdown_settlement import load_first_item_markdown_settlement


COST_PATH = 'docs/评分结算/第一项政权奠基与统一贡献及能力/06-军事成本正式裁决.json'
MAPPING_PATH = 'config/first-item/military-cost-debits.json'


def render_cost_adjudications(source: dict[str, Any]) -> str:
    lines = ['# 第一项军事成本裁决', '',
             '本表记录逐人成本裁决。全部适用对象及跨项去重闭合后，按已确认映射从五轴合计扣除军事成本，净分进入第一项正式结算及综合榜；待裁决不等于零成本。', '',
             '| 人物 | 成本档 | 位置 | 状态 | 责任窗口 |', '|---|---|---|---|---|']
    for row in source['records']:
        lines.append('| ' + ' | '.join(str(row.get(key) or '待裁决') for key in
                     ('ruler_name', 'cost_band', 'cost_position', 'evidence_status', 'responsibility_window')) + ' |')
    for row in source['records']:
        lines.extend(['', f"## {row['ruler_name']}", '', row['basis'] or '尚未形成成本裁决。'])
        lines.extend(f'- 缺口：{gap}' for gap in row['unresolved_gaps'])
        lines.extend(f'- 证据入口：`{ref}`' for ref in row['source_refs'])
    return '\n'.join(lines) + '\n'


def calculate_cost_debit(gross: float, band: str, position: str, mapping: dict[str, Any]) -> dict[str, float]:
    """Convert an adjudicated band; never infer a band from battle results."""
    value = Decimal(str(gross))
    if not value.is_finite() or not 0 <= value <= 240:
        raise ValueError('第一项五轴合计须在0—240内')
    try:
        debit = Decimal(str(mapping['debit_by_band_and_position'][band][position]))
    except KeyError as error:
        raise ValueError('成本档位或位置没有扣分映射') from error
    limit = Decimal(str(mapping['max_debit_points']))
    if not debit.is_finite() or not 0 <= debit <= limit:
        raise ValueError('成本扣分越界')
    net = max(Decimal(0), value - debit).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    return {'gross_points': float(value), 'cost_debit_points': float(debit), 'net_points': float(net)}


def build_first_item_cost_report(root: Path, *, formal_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Read-only review. Unclosed evidence has no deterministic net score."""
    source = json.loads((root / COST_PATH).read_text(encoding='utf-8'))
    mapping = json.loads((root / MAPPING_PATH).read_text(encoding='utf-8'))
    if mapping['status'] not in {'CONFIRMED', 'PENDING_CONFIRMATION'}:
        raise ValueError('第一项成本扣分映射状态非法')
    expected_bands = {f'C{i}' for i in range(8)}
    if set(mapping['debit_by_band_and_position']) != expected_bands:
        raise ValueError('第一项成本扣分映射必须完整覆盖C0—C7')
    ordered = []
    for band in sorted(expected_bands):
        positions = ['LOW', 'MID', 'HIGH'] + (['HIGHEST'] if band == 'C7' else [])
        if set(mapping['debit_by_band_and_position'][band]) != set(positions):
            raise ValueError('第一项成本扣分映射位置不完整')
        for position in positions:
            ordered.append(calculate_cost_debit(240, band, position, mapping)['cost_debit_points'])
    if ordered != sorted(ordered) or ordered[0] != 0 or ordered[-1] != mapping['max_debit_points']:
        raise ValueError('第一项成本扣分映射不单调或上下限不一致')
    if (root / COST_PATH).with_suffix('.md').read_text(encoding='utf-8') != render_cost_adjudications(source):
        raise ValueError('第一项成本JSON与阅读视图不一致')
    if formal_rows is None:
        formal_rows = load_first_item_markdown_settlement(root, validate_cost=False)
    formal = {row['name']: row for row in formal_rows}
    records = source['records']
    names = [row['ruler_name'] for row in records]
    ids = [row['ruler_id'] for row in records]
    if set(names) != set(formal) or len(names) != len(set(names)) or len(ids) != len(set(ids)):
        raise ValueError('第一项成本对象与当前五轴适用对象不一致或ID重复')
    mapping_ready = mapping['status'] == 'CONFIRMED'
    consumed: set[str] = set()
    output = []
    for row in records:
        name = row['ruler_name']
        status = row['evidence_status']
        if status not in {'CONFIRMED', 'LOWER_BOUND', 'PROVISIONAL'}:
            raise ValueError(f'{name}成本状态非法；适用对象不能用其他项NOT_APPLICABLE代替')
        for ref in row['source_refs']:
            if not (root / ref.split('#', 1)[0]).is_file():
                raise ValueError(f'{name}成本证据路径不存在：{ref}')
        if status != 'PROVISIONAL':
            calculate_cost_debit(240, row['cost_band'], row['cost_position'], mapping)
            if not row['source_refs'] or not row['basis'] or not row['responsibility_window']:
                raise ValueError(f'{name}成本裁决缺少证据、依据或责任窗口')
            if not row['consumed_phase_refs']:
                raise ValueError(f'{name}成本裁决缺少已核对的责任阶段')
            for phase in row['consumed_phase_refs']:
                if phase in consumed:
                    raise ValueError(f'同一成本阶段被多人重复消费：{phase}')
                consumed.add(phase)
        elif not row['unresolved_gaps']:
            raise ValueError(f'{name}待裁决成本必须说明缺口')
        item = {'ruler_id': row['ruler_id'], 'ruler_name': name, 'evidence_status': status,
                'cost_band': row['cost_band'], 'cost_position': row['cost_position'],
                'gross_points': sum(formal[name][k] for k in ('a', 'b1', 'b2', 'c1', 'c2')),
                'cost_debit_points': None, 'net_points': None,
                'unresolved_gaps': row['unresolved_gaps']}
        if status == 'CONFIRMED' and row['unresolved_gaps']:
            raise ValueError(f'{name}仍有成本缺口，不能标为CONFIRMED')
        if status == 'CONFIRMED' and mapping_ready:
            item.update(calculate_cost_debit(item['gross_points'], row['cost_band'], row['cost_position'], mapping))
        output.append(item)
    ready = mapping_ready and all(row['net_points'] is not None for row in output)
    if ready:
        for row in output:
            settled = formal[row['ruler_name']]
            if settled['cost_debit'] != row['cost_debit_points'] or settled['total'] != row['net_points']:
                raise ValueError(f"第一项正式净分与逐人成本裁决不一致：{row['ruler_name']}")
    return {'status': 'READY' if ready else 'PENDING_ADJUDICATION', 'record_count': len(output),
            'confirmed_count': sum(row['evidence_status'] == 'CONFIRMED' for row in output),
            'mapping_status': mapping['status'], 'formal_score_write': False,
            'records': output}
