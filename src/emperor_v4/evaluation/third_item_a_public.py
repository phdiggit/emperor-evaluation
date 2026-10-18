"""Authored A-axis reading and deterministic explanations, without adjudication."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json
import re
from emperor_v4.evaluation.formal_json_store import load_json


STATE_MEANINGS = {
    'A1': (
        '国家军事存续受到现实威胁，整体安全接近崩解',
        '主要威胁能够制造国家级危机，国家被迫长期高强度防御',
        '主要方向明显被动，入侵、割据或颠覆威胁反复发生',
        '主要威胁与国家相互制衡，双方均未取得稳定主动',
        '主要威胁总体受控，国家掌握战略主动，但仍有明显未决强敌或方向',
        '主要威胁被结构性压低，国家主导整体安全秩序',
    ),
    'A2': (
        '缺乏有效战略边界，首都或核心区长期直接暴露',
        '主要防线或缓冲体系破裂，只剩核心附近的应急防御',
        '能够守住部分节点，但尚未形成主要方向的防御协同',
        '决定性主要方向的防线、纵深、交通、补给或缓冲能够协同，整体仍有显著缺口',
        '主要边界体系总体有效，关键门户与纵深能够协同，仍有明显未决或次要缺口',
        '战略边界体系成形，核心有稳定纵深，整体防御无显著结构缺口',
    ),
}
METHOD = (
    '每轴满分60分，两轴合计120分。先按交班状态确定基础值，再分别计算本人造成的改善、恶化、独立建设或压力下的保全；'
    '交班基础值表达留下的安全状态，不等于本人创造了全部成果。同档交班仍有基础分，但不会自动获得改善或保全加分。'
    '状态档位从0到5，数值越高越安全；0是明确的危机状态，不是缺失数据。'
    '两轴分别评价威胁与战略主动、防线与纵深，不能把同一改善重复加分。'
)
READING_TEXT_FIELDS = ('story', 'decision', 'responsibility', 'window', 'boundary')
INTERNAL_PROSE = re.compile(r'父卡|闭合|倒灌|本轮|重裁|撤回|回滚|可本人责任于本人|本人本人责任|[A-Za-z_]{2,}')


def _number(value):
    return Decimal(str(value or 0))


def calculation(axis, contract):
    """Explain stored terms and reject a stale or inconsistent result."""
    end = int(axis['end_grade'])
    # Axis-specific state value is already checked by the settlement verifier.
    base = _number(axis['end_state_value'])
    positive = _number(axis['positive_value_delta'])
    negative = _number(axis['negative_value_delta'])
    improvement_weight = _number(contract['change_weights']['improvement'])
    deterioration_weight = _number(contract['change_weights']['deterioration'])
    structure = axis.get('within_band_structure_improvement') or {}
    construction = _number(contract['construction_base_points'].get(structure.get('improvement_level'), 0)) * _number(structure.get('attribution_credit'))
    ceiling = _number(axis.get('ceiling_progress_bonus'))
    maintenance = _number(axis.get('maintenance_bonus'))
    special = max(ceiling, construction, maintenance)
    reversal = _number(axis.get('reversal_penalty'))
    deterioration = _number(axis.get('within_band_deterioration_penalty'))
    penalty = max(reversal, deterioration)
    raw = base + improvement_weight * positive + deterioration_weight * negative + special - penalty
    bounded = min(Decimal(100), max(Decimal(0), raw))
    points = (bounded * Decimal('.6')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    if points != _number(axis['axis_points']) or abs(raw - _number(axis['unclamped_trajectory_value'])) > Decimal('.000001'):
        raise ValueError('第三项A公开计算与正式记录不一致，须先核对裁决，禁止修改分数迎合展示')
    n = lambda v: format(v.normalize(), 'f')
    lines = [
        f'交班{end}档的状态基础值为{n(base)}。',
        f'本人改善价值{n(positive)} × {n(improvement_weight)} = {n(positive * improvement_weight)}；本人恶化价值{n(negative)} × {n(deterioration_weight)} = {n(negative * deterioration_weight)}。',
        f'专项取高：封顶建设{n(ceiling)}、独立建设{n(construction)}、压力保全{n(maintenance)}，只计其中最高的{n(special)}。',
        f'负向调整取高：重大逆转{n(reversal)}、档内恶化{n(deterioration)}，只扣其中最高的{n(penalty)}。',
        f'轨迹值 = {n(base)} + {n(positive * improvement_weight)} + ({n(negative * deterioration_weight)}) + {n(special)} − {n(penalty)} = {n(raw)}。',
        f'轨迹值限制在0—100内得到{n(bounded)}，再乘0.6，四舍五入保留两位小数，最终为{points:.2f}分。',
    ]
    if axis.get('improvement_step_credits'):
        lines.insert(1, '逐档本人责任：' + '；'.join(
            f"{step['from_grade']}→{step['to_grade']}档取{step['credit']}"
            for step in axis['improvement_step_credits']) + '。')
    return '\n\n'.join(lines)


def reading_projection(axis_name, axis, contract):
    authored = axis.get('public_reading')
    if not isinstance(authored, dict):
        raise ValueError(f'第三项{axis_name}缺少直接维护的公开正文')
    result = deepcopy(authored)
    for field in READING_TEXT_FIELDS:
        if not isinstance(result.get(field), str) or not result[field].strip():
            raise ValueError(f'第三项{axis_name}公开正文缺少{field}')
        if INTERNAL_PROSE.search(result[field]):
            raise ValueError(f'第三项{axis_name}公开正文含内部术语或残句：{field}')
    if not result.get('sources'):
        raise ValueError(f'第三项{axis_name}缺少裁决来源')
    if result.get('unresolved_refs'):
        raise ValueError(f'第三项{axis_name}存在未定位的公开引用，须补齐现行材料链接')
    for ref in result['sources']:
        if any(not isinstance(ref.get(field), str) or not ref[field].strip() for field in ('path', 'label', 'kind')):
            raise ValueError(f'第三项{axis_name}公开来源缺少路径、名称或材料类型')
    values = contract['state_values'][axis_name]
    if _number(axis['end_state_value']) != _number(values[int(axis['end_grade'])]):
        raise ValueError(f'第三项{axis_name}交班状态价值与合同不一致')
    result['method'] = METHOD + '本轴0—5档对应的状态价值依次为' + '、'.join(str(v) for v in values) + '。本人改善价值为逐档状态价值差乘各档本人责任比例后相加；恶化价值按已裁责任窗口的状态价值下降及责任比例计算，为非正数。多次主政的改善与恶化分别保留，不先相抵。下列基础值、变化价值、专项和扣减均为轨迹点，最后统一乘0.6换为分数。'
    result['scale'] = [f'{i}档：{text}。' for i, text in enumerate(STATE_MEANINGS[axis_name])]
    result['calculation'] = calculation(axis, contract)
    return result


def verify_reading_sources(root: Path, payload):
    """Paths and declared bindings must resolve; a collection is not a quote."""
    checked = set()
    contents = {}
    for row in payload['records']:
        for axis_name in ('A1', 'A2'):
            reading = row['axes'][axis_name]['public_reading']
            for ref in reading['sources']:
                key = (ref['path'], ref.get('binding'))
                if key in checked:
                    continue
                path = root / ref['path'].split('#', 1)[0]
                if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError(f'第三项A公开来源不存在或超出工作区：{key}')
                if path not in contents:
                    contents[path] = json.dumps(load_json(path), ensure_ascii=False) if path.suffix == '.json' else path.read_text(encoding='utf-8')
                if ref.get('binding') and ref['binding'] not in contents[path]:
                    raise ValueError(f'第三项A公开来源定位不匹配：{key}')
                checked.add(key)
    return len(checked)
