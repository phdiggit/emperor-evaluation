"""Authored control-result narratives and checked, read-only B calculations."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
import re
from pathlib import Path
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.third_item_b_sources import AXES, expand_readings

RATE_TABLE = ((0, 15, 29), (30, 37, 44), (45, 52, 59), (60, 67, 74), (75, 82, 89), (90, 95, 100))
RATE_TABLE_LINES = tuple(f"{i}档：低位{lo}%、中位{mid}%、高位{hi}%。" for i, (lo, mid, hi) in enumerate(RATE_TABLE))
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
    '三轴合成满分80分。控制规模与战略价值按55%和45%合成，再乘交班成熟度修正系数。百分数在公式中先除以100。'
    '控制规模按本人窗口净变化的60%与交班规模的40%计档。当量按统一的历史分区及实际覆盖率比较各朝控制空间。现代面积与人口各用独立统计口径。'
    '表中“未单列”的时点缺少单列数值，各区域当量按各自采用范围列示，合计见计档算式。'
    '控制规模0档仍分低、中、高位。档内位置取决于具体控制证据。'
    '合成使用各轴采用的得分率。权重与成熟度系数各按规则确定。因跨项排除或上限调整时，保留原始率与采用理由。'
)
EQUAL_RATE_ADOPTION_BASIS = '原始得分率与正式采用率一致；该率只参与控制成果合成，不是百分制总评，也不是合成权重。'
SHARED_BOUNDARY = (
    '战略价值和成熟度采用本人窗口内的合格控制成果，区分新建收复、压力下保全与常规维护。纯继承归入接班存量。'
    '成熟度覆盖全部主要成果，采用本人任内运行和交班时的状态。同一成果已计入政权奠基与统一的部分从本项排除，原始率与实际采用率分别列示。'
)
SHARED_SOURCE_NOTE = (
    '依据正文来自现行区域和归责裁决。来源按正式裁决、军事记录、材料汇集与原裁决书目列示，材料汇集提供进一步查找的线索。'
)
DERIVED_READING_FIELDS = {
    'raw_rate', 'adopted_rate', 'level_label', 'rate_note', 'scale', 'method', 'combination',
    'recorded_diagnostic_rate', 'diagnostic_note', 'rate_table', 'contribution_label',
    'contribution_cap', 'contribution_note', 'snapshot', 'regions', 'calculation', 'review_status', 'review_note',
}
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
        f"控制成果合成 = 80 × {fmt(mix)} × {fmt(maturity)}；结果保留两位小数，为{result:.2f}分。"
    )


def reading_projection(axis_name, row, credit):
    axis = row['axes'][axis_name]
    authored = axis.get('public_reading')
    if not isinstance(authored, dict):
        raise ValueError(f"{row['ruler_name']} {axis_name}缺少直接维护的公开正文")
    result = expand_readings(row)[axis_name]
    result.setdefault('boundary', SHARED_BOUNDARY)
    result.setdefault('source_note', SHARED_SOURCE_NOTE)
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
        f'合成记录还保留{fmt(diagnostic)}%的诊断率，用于核对。诊断率不参与当前合成，排除的成果见采用说明。'
        if dec(diagnostic) != dec(raw) else ''
    )
    result['rate_table'] = list(RATE_TABLE_LINES)
    contribution, cap = CONTRIBUTIONS[row['control_contribution_type']]
    result['contribution_label'] = contribution
    result['contribution_cap'] = cap
    result['contribution_note'] = f'本人贡献类型为“{contribution}”，该类型的战略价值和交班成熟度上限为{cap}档。合成采用跨项排除后的正式得分率。'
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
            f'接班控制空间{fmt(start)}当量，交班{fmt(end)}当量。本人各主政窗口的净变化合计{fmt(net)}当量。\n\n'
            f'加权控制值 = 0.6 × {fmt(net)} + 0.4 × {fmt(end)} = {fmt(before_exclusion)}当量。\n\n'
            f'{adjustment}，本项计档控制值为{fmt(weighted)}当量。'
        )
    else:
        result['calculation'] = result['rate_note'] + ' ' + result['adoption_basis']
    if axis_name == 'B4':
        review = axis.get('maturity_review') or {}
        if result.get('review_source_basis') != review.get('basis'):
            raise ValueError('B4复核来源已变化，须核对并同步公开判词，不能只刷新状态')
        status = review.get('status', 'NOT_REVIEWED')
        notes = {
            'CONFIRMED': '已复核，采用本人任内的实际运行和交班状态。',
            'EVIDENCE_GAP': '待补证。判断交班稳定性的材料尚未齐备，暂用现有评价。',
            'NOT_REVIEWED': '交班成熟度尚未复核，暂用现有评价。',
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
    from .second_item_c_source_display import bibliographic_source

    checked = set(); contents = {}
    def non_public(value):
        if isinstance(value, dict):
            return {key: non_public(item) for key, item in value.items() if not key.startswith('public_')}
        if isinstance(value, list): return [non_public(item) for item in value]
        return value
    for row in payload['records']:
        readings = expand_readings(row)
        for key in AXES:
            reading = readings[key]
            refs = list(reading['sources']) + [ref for item in reading['evidence_items'] for ref in item['sources']]
            for ref in refs:
                if 'public_citation' in ref:
                    citation = ref['public_citation']
                    fields = {'title', 'url', 'context', 'quote'}
                    if (not isinstance(citation, dict) or set(citation) != fields
                            or any(not isinstance(value, str) or not value.strip() for value in citation.values())
                            or bibliographic_source({'source_title': citation['title'], 'source_locator': '',
                                                     'source_url': citation['url']})['source_urls'] != [citation['url']]):
                        raise ValueError('第三项B公开原典引用缺少书目、链接、上下文或原文')
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
