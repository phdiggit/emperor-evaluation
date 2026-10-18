"""Current B1 evidence inputs and deterministic arithmetic, never historical inference."""
from pathlib import Path
import json
import re
from math import sqrt, isfinite

from .first_item_weights import B1_START_POINTS, B1_OPPONENT_POINTS, b1_efficiency_points, round_points
from .first_item_public_outcomes import _parse_source_sections, SOURCE_MARKDOWN_PATH as A_SOURCE

INPUTS = Path('docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/02-第一项B1计时与对手正式依据.json')
B1_SOURCE = INPUTS.with_name('02-第一项B1创业难度与战略效率正式结算.md')


def load_opponent_systems(root: Path) -> dict:
    contract = json.loads((root / 'config/military/opponent-system-contract.json').read_text(encoding='utf-8'))
    systems = dict(contract['supplemental_opponent_systems'])
    registry = json.loads((root / 'docs/公共成果/军事/01-战役登记.json').read_text(encoding='utf-8'))
    metadata = registry.get('payload_metadata', registry)
    for portfolio in metadata.get('unification_campaign_portfolios', []):
        for system in portfolio.get('opponent_systems', []):
            ref = system['system_id']
            if ref in systems and systems[ref]['organization_grade'] != system['organization_grade']:
                raise ValueError(f'对手等级登记冲突：{ref}')
            systems[ref] = system
    return systems


def b1_components(row: dict, systems: dict) -> dict:
    start = B1_START_POINTS[row['start_resource_grade']]
    refs = row['opponent_refs']
    if len(refs) > 2 or len(refs) != len(set(refs)):
        raise ValueError('B1只准入两个不同的实际战争机器')
    values = sorted((B1_OPPONENT_POINTS[systems[ref]['organization_grade']] for ref in refs), reverse=True)
    opponent = sum(value * (1 if i == 0 else .5) for i, value in enumerate(values))
    stages = row['efficiency_stages']
    efficiency = 0.0
    if stages:
        total_weight = 0.0
        for stage in stages:
            numbers = [stage[key] for key in ('control_credit', 'years', 'weight')]
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) for value in numbers):
                raise ValueError('B1阶段参数必须为有限数值')
            if stage['weight'] <= 0 or not stage.get('basis'):
                raise ValueError('B1阶段必须有正权重与计时依据')
            efficiency += b1_efficiency_points(stage['control_credit'], stage['years']) * stage['weight']
            total_weight += stage['weight']
        efficiency = round_points(efficiency / total_weight)
    return {'start_points': float(start), 'opponent_points': float(opponent), 'efficiency_points': efficiency,
            'total_points': round_points(start + opponent + efficiency)}


def load_b1_inputs(root: Path, *, verify_markdown: bool = True) -> dict:
    payload = json.loads((root / INPUTS).read_text(encoding='utf-8'))
    if payload.get('schema_version') != 'first-item-b1-current-inputs-v1':
        raise ValueError('B1当前依据格式错误')
    rows = payload.get('records', [])
    by_name = {row['ruler_name']: row for row in rows}
    if len(by_name) != len(rows) or set(by_name) != set(_parse_source_sections(root / A_SOURCE)):
        raise ValueError('B1当前依据未逐人覆盖正式A对象或存在重复')
    systems = load_opponent_systems(root)
    formal = _parse_source_sections(root / B1_SOURCE) if verify_markdown else {}
    a_sections = _parse_source_sections(root / A_SOURCE)
    shared = {}
    for name, row in by_name.items():
        if not row.get('timing_basis') or not row.get('source_refs'):
            raise ValueError(f'B1缺少计时或史源依据：{name}')
        for ref in row['opponent_refs']:
            if ref not in systems or not systems[ref].get('basis') or not systems[ref].get('source_campaign_refs'):
                raise ValueError(f'B1实际对手无有效公共来源：{name}/{ref}')
        result = b1_components(row, systems)
        if not row['efficiency_stages'] and not re.search(r'有效控制信用为\s*0(?:\D|$)', a_sections[name].get('取得/恢复成果', '')):
            raise ValueError(f'B1没有效率阶段但A仍有保留成果：{name}')
        for stage in row['efficiency_stages']:
            if stage.get('shared_stage_ref'):
                shared.setdefault(stage['shared_stage_ref'], []).append((stage['control_credit'], stage['years']))
        if verify_markdown:
            match = re.match(r'([\d.]+)/50\s*=\s*起点([\d.]+)\s*\+\s*对手([\d.]+)\s*\+\s*效率([\d.]+)', formal[name]['B1结算'])
            expected = (result['total_points'], result['start_points'], result['opponent_points'], result['efficiency_points'])
            if not match or tuple(map(float, match.groups())) != expected:
                raise ValueError(f'B1正式Markdown与当前计时、对手及公式不同值：{name}')
            expected_efficiency = ' '.join(calculation_text(row, systems).splitlines()[2:])
            if formal[name]['效率'] != expected_efficiency:
                raise ValueError(f'B1正式效率代入与当前阶段参数不同值：{name}')
    for ref, stages in shared.items():
        if len(stages) < 2 or len(set(stages)) != 1:
            raise ValueError(f'B1同代共同阶段规模或工期不一致：{ref}')
    if verify_markdown:
        table = {}
        for line in (root / B1_SOURCE).read_text(encoding='utf-8').splitlines():
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if len(cells) == 9 and cells[0].isdigit():
                if cells[1] in table:
                    raise ValueError('B1摘要表人物重复')
                table[cells[1]] = cells
        if set(table) != set(by_name):
            raise ValueError('B1摘要表与正式逐人输入覆盖不同')
        for name, row in by_name.items():
            points = b1_components(row, systems)
            cells = table[name]
            if cells[2] != row['start_resource_grade'] or tuple(float(cells[i].strip('*')) for i in (3, 6, 7, 8)) != tuple(points[k] for k in ('start_points','opponent_points','efficiency_points','total_points')):
                raise ValueError(f'B1摘要表与正式裁决不同值：{name}')
    return by_name


def calculation_text(row: dict, systems: dict) -> str:
    points = b1_components(row, systems)
    labels = '；'.join(f"{systems[ref]['opponent_label']} {systems[ref]['organization_grade']}" for ref in row['opponent_refs']) or '没有准入的独立战争机器'
    lines = [f"起点：{row['start_resource_grade']}，{points['start_points']:g}/15。", f"实际对手：{labels}；最强全值、第二强半值，{points['opponent_points']:g}/15。"]
    for stage in row['efficiency_stages']:
        expected = 4 + 8 * sqrt(stage['control_credit'] / 1000)
        value = b1_efficiency_points(stage['control_credit'], stage['years'])
        lines.append(f"{stage['label']}：规模{stage['control_credit']:g}；实际{stage['years']:g}年/期望{expected:.2f}年，速度比{stage['years']/expected:.3f}，阶段效率{value:g}，加权值{stage['weight']:g}。{stage['basis']}")
    if not row['efficiency_stages']:
        lines.append('没有最终保留的新增或恢复成果，效率为0；这不等于做事缓慢。')
    lines.append(f"完成效率{points['efficiency_points']:g}/20；合计{points['start_points']:g}+{points['opponent_points']:g}+{points['efficiency_points']:g}={points['total_points']:g}/50。")
    return '\n'.join(lines)
