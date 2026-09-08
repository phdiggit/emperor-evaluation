"""Reader layout for current AB decisions; never changes adjudication values."""

import re
from typing import Any, Mapping
from urllib.parse import quote

from emperor_v4.evaluation.third_item_current_settlement import CONSTRUCTION_BASE_POINTS


def prose(*values: object, ruler: str = "") -> str:
    """Remove display wrappers and exact duplicate clauses, without truncating facts."""
    clauses: list[str] = []
    for value in values:
        text = str(value or "").strip()
        text = re.sub(r"(?:依据链|依据父链)[:：][^。]*(?:。|$)", "", text)
        text = re.sub(
            rf"{re.escape(ruler)}\s*A[12](?:（[^）]*）)?(?:逐人裁决|逐人复核|复核)[:：]",
            "", text,
        )
        text = re.sub(r"^(?:整体边疆形势|规模与控制强度|战略价值|交班成熟度)[:：]", "", text)
        text = re.sub(
            rf"{re.escape(ruler)}是本窗口国家战略、兵力与边防资源配置的最终责任主体；本轴变化由其任内连续军令体系形成，现有父链未显示摄政或外部主体替代其作出终局选择，故客观变动[^。]+。",
            "改善由本人主导的战略决策与持续军令形成，按主导归责计入。", text,
        )
        text = re.sub(r"(?<![A-Za-z0-9_])(A[12])S([0-5])(?![A-Za-z0-9_])", r"\1-\2档", text)
        text = re.sub(r"(?<![A-Za-z0-9_])S([0-5])(?![A-Za-z0-9_])", r"\1档", text)
        for token, label in {'NOT_APPLICABLE': '不适用', 'HISTORIC': '历史级保全', 'SEVERE': '严重保全', 'TESTED': '经受压力检验', 'NONE': '未计', 'EVIDENCE_LIMITED': '证据不足'}.items():
            text = re.sub(rf'\b{token}\b', label, text)
        for clause in re.split(r"[。；]\s*", text):
            clause = clause.strip()
            if not clause or clause in {
                "客观起终档未变化，不生成变化分", "不生成变化分",
                "本轴只保留客观状态", "原有分数不变",
            }:
                continue
            if clause not in clauses:
                clauses.append(clause)
    return "。".join(clauses) + ("。" if clauses else "")


def a_calculation(axis: Mapping[str, Any]) -> str:
    """Show actual final-point contributions, including signed losses and clipping."""
    parts = [f"交班基础{float(axis['end_state_value']) * .6:g}"]
    for label, value in (
        ("跨档改善", float(axis['positive_value_delta']) * 1.4 * .6),
        ("归责回吐", float(axis['negative_value_delta']) * .5 * .6),
    ):
        if value:
            parts.append(f"{'＋' if value > 0 else '－'}{label}{abs(value):g}")
    structure = axis.get('within_band_structure_improvement') or {}
    construction = CONSTRUCTION_BASE_POINTS.get(structure.get('improvement_level'), 0) * float(structure.get('attribution_credit') or 0)
    specials = [
        ('封顶建设', float(axis.get('ceiling_progress_bonus') or 0)),
        ('独立建设', construction),
        ('压力保全', float(axis.get('maintenance_bonus') or 0)),
    ]
    label, special = max(specials, key=lambda item: item[1])
    if special:
        parts.append(f"＋{label}{special * .6:g}")
    penalty = float(axis.get('negative_adjustment') or 0)
    if penalty:
        parts.append(f"－负向调整{penalty * .6:g}")
    raw = float(axis['unclamped_trajectory_value']) * .6
    if not 0 <= raw <= 60:
        parts.append(f"＝{raw:g}，按0—60分范围限制后")
    return ''.join(parts) + f"＝**{float(axis['axis_points']):.2f}分**。"


def a_reason(row: Mapping[str, Any], name: str) -> str:
    axis = row['A120_axis_adjudications'][name]
    structure = axis.get('within_band_structure_improvement')
    if structure:
        level = {'SIGNIFICANT': '显著', 'DECISIVE': '重大'}[structure['improvement_level']]
        pieces = [structure['entry_structure'], structure['handover_structure'],
                  f"认定为{level}独立建设", structure['attribution_basis'].split('。', 1)[0]]
    else:
        ownership = prose(axis.get('attribution_basis'), ruler=str(row['ruler_name']))
        ownership = '。'.join(
            clause for clause in ownership.split('。')
            if re.search('归责|主导|授权|决策|自主|外生|摄政|贡献|全部归|责任|中枢|具体执行|方案', clause)
        )
        pieces = [row['axes'][name].get('reason'), ownership]
        if float(axis.get('maintenance_bonus') or 0):
            pieces.append(axis.get('maintenance_basis'))
    if float(axis.get('negative_adjustment') or 0):
        for field in ('reversal_basis', 'within_band_deterioration_basis'):
            if float(axis.get('reversal_penalty' if field == 'reversal_basis' else 'within_band_deterioration_penalty') or 0):
                pieces.append(axis.get(field))
    return prose(*pieces, ruler=str(row['ruler_name']))


def source_links(row: Mapping[str, Any]) -> str:
    """Keep a small source index and a direct link to the complete formal record."""
    paths: list[str] = []
    refs = list(row.get('source_refs') or [])
    for axis in row['A120_axis_adjudications'].values():
        refs.extend((axis.get('within_band_structure_improvement') or {}).get('source_refs', []))
    for ref in refs:
        path = str(ref).split('#', 1)[0]
        if path.startswith(('docs/史料通读产物/', 'docs/公共成果/')) and not path.endswith('/') and path not in paths:
            paths.append(path)
    links = []
    for path in paths[:3]:
        label = path.rsplit('/', 1)[-1].removesuffix('.json').removesuffix('.md')
        volume = re.match(r'volume-(\d+)\.(source-summary|battle-adjudications)', label)
        if volume:
            book = path.split('/')[-2]
            label = f"《{book}》卷{volume[1]}·" + ('通读总结' if volume[2] == 'source-summary' else '战役记录')
        elif '/03-军事行动成本和收益登记/' in path:
            label = '军事行动登记'
        links.append(f"[{label}](../../../{quote(path[5:], safe='/')})")
    links.append('[完整裁决与引用](01-皇帝AB项正式结算.json)')
    return '；'.join(links)


def render_person(row: Mapping[str, Any], *, b_basis, b_grade, b_regions, depth_lines) -> list[str]:
    axes = row['A120_axis_adjudications']
    b = row['B80_adjudication']
    titles = {'A1': '战略威胁', 'A2': '战略边界', 'B1': '控制规模', 'B2': '战略价值', 'B4': '交班成熟度'}
    lines = [
        f"**A {float(row['A120_score_points']):.2f}／120 · B {float(row['B80_score_points']):.2f}／80**",
        '', '| 评价轴 | 裁决结果 | 得分／得分率 |', '|---|---|---:|',
    ]
    for name in ('A1', 'A2'):
        axis = axes[name]
        lines.append(f"| {name} {titles[name]} | {axis['start_grade']}→{axis['end_grade']}档 · {axis['settlement_type_label']} | {float(axis['axis_points']):.2f}／60 |")
    for name in ('B1', 'B2', 'B4'):
        rate = float(b[f'adjudicated_{name}_rate'])
        grade = 0 if rate < 30 else 1 if rate < 45 else 2 if rate < 60 else 3 if rate < 75 else 4 if rate < 90 else 5
        lines.append(f"| {name} {titles[name]} | {grade}档 | {rate:g}% |")
    lines += ['', *([prose(row['A_axis_common_context']), ''] if row.get('A_axis_common_context') else [])]
    for name in ('A1', 'A2'):
        lines += [f"**{name} {titles[name]}**", '', a_reason(row, name), '', '计分：' + a_calculation(axes[name]), '']
    control = row.get('b1_control_equivalents') or {}
    b1 = row['axes']['B1']
    net = control.get('net_change', b1.get('raw_net_change'))
    end = control.get('end')
    weighted = control.get('weighted_value', b1.get('weighted_control_value'))
    excluded = float(row.get('b1_cross_item_excluded_weighted_value') or 0)
    amounts = []
    if net is not None:
        amounts.append(f"本项计入净增{float(net)-excluded:+g}当量")
    if end is not None:
        amounts.append(f"交班规模{float(end):g}当量")
    lines += ['**B1 控制规模**', '', prose(b_regions(row), '，'.join(amounts)), '']
    for name in ('B2', 'B4'):
        adjusted = float(row['axes'][name].get('score_rate') or 0) != float(b[f'adjudicated_{name}_rate'])
        basis = b.get('consistency_basis') if adjusted else b_basis(row, name)
        lines += [f"**{name} {titles[name]}**", '', prose(basis, ruler=str(row['ruler_name'])), '']
    contribution = {
        'NEW_RECOVERED_REBUILT': '新增、收复或重建控制',
        'SAVED_UNDER_MAJOR_PRESSURE': '重大失控压力下的保全或恢复',
        'ROUTINE_MAINTENANCE': '常规维护', 'INHERITED_ONLY': '仅继承存量，不计本人控制贡献',
    }.get(str(row.get('control_contribution_type')), '见正式控制成果裁决')
    lines += [f"B项本人贡献：{contribution}。", '', '<details>', '<summary>计分明细与来源</summary>', '']
    for name in ('A1', 'A2'):
        axis = axes[name]
        steps = axis.get('improvement_step_credits') or []
        if steps:
            lines.append(f"- {name}逐档归责：" + '；'.join(f"{s['from_grade']}→{s['to_grade']}档取{float(s['credit']):g}" + (f"（{s['window_ref']}）" if s.get('window_ref') else '') for s in steps) + '。')
        structure = axis.get('within_band_structure_improvement') or {}
        if structure:
            base = CONSTRUCTION_BASE_POINTS[structure['improvement_level']]
            lines.append(f"- {name}独立建设：基础{base:g}×归责{float(structure['attribution_credit']):g}×0.6；与保全、封顶建设取高。")
            lines.append(f"- {name}建设边界：{prose(structure['level_basis'], structure['attribution_basis'], structure.get('deduplication_basis'), ruler=str(row['ruler_name']))}")
        else:
            review = axis.get('positive_credit_review') or {}
            basis = review.get('basis') or (axis.get('ceiling_progress_basis') if int(axis['end_grade']) == 5 else '')
            if basis:
                lines.append(f"- {name}专项边界：{prose(basis, ruler=str(row['ruler_name']))}")
        if float(axis.get('reversal_penalty') or 0) or float(axis.get('within_band_deterioration_penalty') or 0):
            lines.append(f"- {name}负向调整：重大逆转{float(axis.get('reversal_penalty') or 0):g}与档内恶化{float(axis.get('within_band_deterioration_penalty') or 0):g}轨迹点取高，再乘0.6。")
    if weighted is not None:
        lines.append(f"- B1计档控制值：{float(weighted):g}当量。")
    if excluded:
        lines.append(f"- B1跨项{'扣除' if excluded > 0 else '补回'}：{abs(excluded):g}当量；客观净变化{float(net):+g}当量。")
    for name in ('B2','B4'):
        if float(row['axes'][name].get('score_rate') or 0) != float(b[f'adjudicated_{name}_rate']):
            lines.append(f"- {b_grade(row,name)}。")
            lines.append(f"- {name}{b_basis(row,name)}")
    lines += [f"- B合成：80×（0.55×{float(b['adjudicated_B1_rate'])/100:g}＋0.45×{float(b['adjudicated_B2_rate'])/100:g}）×（0.70＋0.30×{float(b['adjudicated_B4_rate'])/100:g}）＝{float(row['B80_score_points']):.2f}分。", *depth_lines(row), f"- 来源：{source_links(row)}", '', '</details>', '']
    return lines
