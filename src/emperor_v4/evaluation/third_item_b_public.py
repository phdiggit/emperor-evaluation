"""Authored control-result narratives and checked, read-only B calculations."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
import re
from pathlib import Path
from emperor_v4.evaluation.formal_json_store import load_json

AXES = ('B1', 'B2', 'B4')
RATE_TABLE = ((0, 15, 29), (30, 37, 44), (45, 52, 59), (60, 67, 74), (75, 82, 89), (90, 95, 100))
BANDS = {'LOW': '低位', 'MID': '中位', 'HIGH': '高位'}
REGION_LABELS = {'MESOPOTAMIA_CAUCASUS_NETWORK': '两河—阿塞拜疆—南高加索主要军政网络',
                 'QING_TAIWAN_PENGHU': '台湾—澎湖控制空间'}
CONTRIBUTIONS = {
    'NEW_RECOVERED_REBUILT': ('新建、收复或实控结构重建', 5),
    'SAVED_UNDER_MAJOR_PRESSURE': ('重大失控压力下的保全或恢复', 4),
    'ROUTINE_MAINTENANCE': ('有实际行动的常规维护', 2),
    'INHERITED_ONLY': ('仅继承存量，未确认合格本人控制贡献', 0),
}
SCALES = {
    'B1': ('加权控制值不大于0，净退控抵消交班规模修正', '加权控制值大于0且不足0.75', '加权控制值达到0.75但不足1.5', '加权控制值达到1.5但不足3', '加权控制值达到3但不足6', '加权控制值达到6以上'),
    'B2': ('没有可计的本人控制成果或可识别战略价值', '只改善易替代的单点态势', '对局部交通、防御、资源或贸易有明确作用', '对主要区域的门户、走廊、缓冲、补给或强敌压制有重要作用', '关键影响一个主要战略方向，显著改变攻防条件', '对国家存续、核心安全或整体战略格局有决定性价值'),
    'B4': ('没有合格本人控制成果可供评价，或成果已丧失、始终只有名义控制', '主要成果仍处战时占领、围困或随时可能失控状态', '控制结构未完备，仍依赖临时重兵、个人威望或异常资源投入', '已有常态运行成果，但主要成果仍有关键功能缺口，或本人造成的另一主要方向退控尚未恢复', '全部主要成果具备常态运行和正常移交的必要安排，但任内运行验证尚不足以确认完全摆脱应急或个人临时维持', '必要安排及任内实际运行均已证明，关键功能由常态机制持续承接，能正常移交'),
}
METHOD = (
    '三轴合成满分80分，不把三个得分率直接相加。控制规模与战略价值按55%／45%合成，'
    '再乘交班成熟度修正系数。百分数在公式中先除以100。'
    '控制规模认可60%的窗口净变化和40%的交班规模；这不是现代面积、人口占比或成功概率。'
    '战略价值与交班成熟度只评价本人合格成果，先区分新建收复、压力下保全、常规维护与纯继承。'
    '同一成果已经计入“政权奠基与统一贡献”的部分不再计入“军事与边疆”，原始判断、实际采用率分别保留。'
)
INTERNAL = re.compile(r'[A-Za-z_]{2,}|父卡|闭合|倒灌|本轮|重裁|回滚|数值不变|旧ID|规范化|全量重审|可本人责任于本人|本人本人责任')


def dec(value):
    return Decimal(str(value))


def fmt(value):
    return format(dec(value).normalize(), 'f')


def grade(axis):
    match = re.fullmatch(r'B[124]-([0-5])', str(axis['grade']))
    if not match or axis['band_position'] not in BANDS:
        raise ValueError('第三项B原始档位或档内位置无效')
    level = int(match[1])
    expected = RATE_TABLE[level][('LOW', 'MID', 'HIGH').index(axis['band_position'])]
    if dec(axis['score_rate']) != dec(expected):
        raise ValueError('第三项B原始档位与得分率不一致，须核对正式裁决')
    return level, f"{level}档·{BANDS[axis['band_position']]}"


def region_values(region):
    values = region.get('control_equivalent')
    values = values if isinstance(values, dict) else {}
    start = values.get('start', region.get('start_equivalent'))
    end = values.get('end', region.get('end_equivalent'))
    # A single stored equivalent applies only to its explicitly declared anchor.
    single = region.get('control_equivalent')
    if isinstance(single, (float, int)):
        if 'start' in region.get('anchors', []): start = single
        if 'end' in region.get('anchors', []): end = single
    label = region.get('object_name') or region.get('region_name')
    return dict(label=REGION_LABELS.get(label, label),
                start=start, end=end, spatial_weight=region.get('spatial_weight'),
                start_coverage=region.get('start_coverage'), end_coverage=region.get('end_coverage'),
                excluded=region.get('scoring_disposition') == 'EXCLUDED_FIRST_ITEM_OR_NO_INDEPENDENT_CONTROL' or region.get('counted') is False,
                window_snapshots=deepcopy(region.get('window_snapshots') or {}))


def combination(row, credit):
    b = credit['B80_adjudication']
    rates = {key: dec(b[f'adjudicated_{key}_rate']) for key in AXES}
    if any(not 0 <= value <= 100 for value in rates.values()):
        raise ValueError('第三项B实际采用率超出0—100')
    mix = Decimal('.55') * rates['B1'] / 100 + Decimal('.45') * rates['B2'] / 100
    maturity = Decimal('.70') + Decimal('.30') * rates['B4'] / 100
    # Reuse the current settlement's operation order and rounding. A decimal
    # half-up reimplementation would silently change existing boundary results.
    actual = {key: float(value) for key, value in rates.items()}
    result = dec(round(80 * (0.55 * actual['B1'] / 100 + 0.45 * actual['B2'] / 100)
                       * (0.70 + 0.30 * actual['B4'] / 100), 2))
    if abs(result - dec(b['B80_points'])) > Decimal('.001') or abs(result - dec(row['B80_score_points'])) > Decimal('.001'):
        raise ValueError('第三项B展示计算与正式合成结果不一致，禁止为展示改分')
    return (
        f"实际采用率：控制规模{fmt(rates['B1'])}%，战略价值{fmt(rates['B2'])}%，交班成熟度{fmt(rates['B4'])}%。\n\n"
        f"规模与价值合成率 = 0.55 × {fmt(rates['B1']/100)} + 0.45 × {fmt(rates['B2']/100)} = {fmt(mix)}。\n\n"
        f"成熟度修正系数 = 0.70 + 0.30 × {fmt(rates['B4']/100)} = {fmt(maturity)}。\n\n"
        f"控制成果合成 = 80 × {fmt(mix)} × {fmt(maturity)}；沿用当前确定性结算保留两位小数的结果，为{result:.2f}分。"
    )


def reading_projection(axis_name, row, credit):
    axis = row['axes'][axis_name]
    authored = axis.get('public_reading')
    if not isinstance(authored, dict):
        raise ValueError(f"{row['ruler_name']} {axis_name}缺少直接维护的公开正文")
    result = deepcopy(authored)
    for field in ('story', 'decision', 'responsibility', 'window', 'boundary', 'adoption_basis'):
        value = result.get(field)
        if not isinstance(value, str) or not value.strip() or INTERNAL.search(value):
            raise ValueError(f"{row['ruler_name']} {axis_name}公开正文为空或含内部术语：{field}")
    for item in result.get('evidence_items', []):
        if not item.get('label') or INTERNAL.search(item['label']) or not item.get('sources') or not item.get('basis') or INTERNAL.search(item['basis']):
            raise ValueError(f"{row['ruler_name']} {axis_name}逐条依据缺少正文或来源")
    if not result.get('sources'):
        raise ValueError(f"{row['ruler_name']} {axis_name}公开来源缺失")
    level, level_label = grade(axis)
    raw = axis['score_rate']
    b = credit['B80_adjudication']
    diagnostic = b[f'formal_{axis_name}_rate']
    applied = b[f'adjudicated_{axis_name}_rate']
    result.update(raw_rate=raw, adopted_rate=applied, level_label=level_label,
                  rate_note=f'原始评定{level_label}，对应{fmt(raw)}%；正式合成采用{fmt(applied)}%。',
                  scale=[f'{i}档：{text}。' for i, text in enumerate(SCALES[axis_name])],
                  method=METHOD, combination=combination(row, credit))
    result['recorded_diagnostic_rate'] = diagnostic
    result['diagnostic_note'] = (
        f'合成记录另存诊断率{fmt(diagnostic)}%，与现行轴记录的{fmt(raw)}%不同；它不替代现行原始评定，也不参与当前合成。按已裁排除理由分别保留这些数值，不为展示覆盖旧字段。'
        if dec(diagnostic) != dec(raw) else ''
    )
    result['rate_table'] = [f"{i}档：低位{values[0]}%、中位{values[1]}%、高位{values[2]}%。" for i, values in enumerate(RATE_TABLE)]
    contribution, cap = CONTRIBUTIONS[row['control_contribution_type']]
    result['contribution_label'] = contribution
    result['contribution_cap'] = cap
    result['contribution_note'] = f'原记录贡献类型为“{contribution}”，战略价值和成熟度最高可评{cap}档；这是上限，不保证达到该档。另有跨项排除时，以实际采用率为准。'
    if axis_name == 'B1':
        snapshot = row['b1_control_equivalents']
        start, end, net, weighted = (dec(snapshot[k]) for k in ('start', 'end', 'net_change', 'weighted_value'))
        excluded = dec(row.get('b1_cross_item_excluded_weighted_value') or 0)
        before_exclusion = Decimal('.6') * net + Decimal('.4') * end
        if abs(before_exclusion - excluded - weighted) > Decimal('.000001'):
            raise ValueError(f"{row['ruler_name']}空间快照与当前计档值不一致")
        result['snapshot'] = deepcopy(snapshot)
        result['regions'] = [region_values(r) for r in row.get('b1_region_adjudications', [])]
        adjustment = (f'按现行跨项与空间口径裁决补回{fmt(-excluded)}当量后' if excluded < 0
                      else f'按现行跨项裁决排除{fmt(excluded)}当量后')
        result['calculation'] = (
            f'接班控制空间{fmt(start)}当量，交班{fmt(end)}当量；正式责任窗口净变化为{fmt(net)}当量。多次主政只计本人各窗口变化，不把间隔他人的变化归本人。\n\n'
            f'加权控制值 = 0.6 × {fmt(net)} + 0.4 × {fmt(end)} = {fmt(before_exclusion)}当量。\n\n'
            f'{adjustment}，本项计档控制值为{fmt(weighted)}当量；正式原始评定为{level_label}，得分率{fmt(raw)}%，实际采用{fmt(applied)}%。'
        )
        result['calculation'] += '\n\n0档仍区分低、中、高位，对应0%、15%、29%；0档不等于每种情形都必然采用0%。具体档内位置沿用当前正式裁决，不在阅读层按空间值插值或补判。'
    else:
        result['calculation'] = result['rate_note'] + ' ' + result['adoption_basis']
    if axis_name == 'B4':
        review = axis.get('maturity_review') or {}
        if result.get('review_source_basis') != review.get('basis'):
            raise ValueError('B4复核来源已变化，须核对并同步公开判词，不能只刷新状态')
        status = review.get('status', 'NOT_REVIEWED')
        notes = {
            'CONFIRMED': '已完成现行成熟度边界复核；具体判定仍以本人交班状态和任内运行证据为准。',
            'EVIDENCE_GAP': '成熟度复核仍缺必要证据：现值暂留，尚未通过新边界复核；不因此自动升档或降档。',
            'NOT_REVIEWED': '当前为保留的正式值，尚未登记完成现行成熟度边界复核；不得把现值或此处展示当作已通过复核的证明。',
        }
        if status not in notes:
            raise ValueError('未知B4复核状态，须明确公开解释')
        result.update(review_status=status, review_note=notes[status])
        if status != 'NOT_REVIEWED' and not result.get('review_explanation'):
            raise ValueError('B4复核结论缺少明确的公开依据')
        if result.get('review_explanation') and INTERNAL.search(result['review_explanation']):
            raise ValueError('B4公开复核依据含内部术语')
    return result


def verify_sources(root: Path, payload):
    checked = set(); contents = {}
    def non_public(value):
        if isinstance(value, dict):
            return {key: non_public(item) for key, item in value.items() if not key.startswith('public_')}
        if isinstance(value, list): return [non_public(item) for item in value]
        return value
    for row in payload['records']:
        for key in AXES:
            reading = row['axes'][key]['public_reading']
            refs = list(reading['sources']) + [ref for item in reading['evidence_items'] for ref in item['sources']]
            for ref in refs:
                target = ref.get('path', '')
                identity = (target, ref.get('binding'))
                if identity in checked: continue
                path = root / target.split('#', 1)[0]
                if not target or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError(f'第三项B公开来源失效：{target}')
                if not ref.get('label') or not ref.get('kind'):
                    raise ValueError(f'第三项B来源缺少名称或类型：{target}')
                if path not in contents:
                    contents[path] = json.dumps(non_public(load_json(path)), ensure_ascii=False) if path.suffix == '.json' else path.read_text(encoding='utf-8')
                if ref.get('binding') and ref['binding'] not in contents[path]:
                    raise ValueError(f'第三项B来源定位不匹配：{target}')
                checked.add(identity)
    return len(checked)
