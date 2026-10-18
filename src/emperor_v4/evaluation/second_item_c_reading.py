"""Deterministic calculation notes for authored C reading records.

Historical prose and source bindings are never inferred by this module.
"""
from __future__ import annotations

from typing import Any

from emperor_v4.evaluation.governance_state_recovery import FIXED_POINTS, LOSS_RATES

NAMES = {"C1": "民生", "C2": "经济财政", "C3": "社会安全"}
GRADES = {1: "E", 2: "D", 3: "C", 4: "B", 5: "A", 6: "S"}


def calculation(axis: str, row: dict[str, Any]) -> str:
    """Explain declared inputs, including floors, caps and legacy boundaries."""
    if axis in NAMES:
        band = int(str(row["main_band"]).split("-")[-1])
        base = FIXED_POINTS[axis][band - 1]
        loss = row.get("loss_grade")
        if loss not in LOSS_RATES:
            return (
                f"主要状态为{GRADES[band]}档，现行状态基础分表对应{base:g}分。"
                f"本记录属于池外保留结果，未采用当前统一低谷修正；正式保留分为{row['score']:g}分，"
                "不将其冒充按当前低谷公式新算的结果，也不进入当前综合榜。"
            )
        rate = float(LOSS_RATES[loss]) * 100
        floor = FIXED_POINTS[axis][0]
        return (
            f"主要状态{GRADES[band]}档的基础分为{base:g}；本条已裁低谷的修正率为{rate:g}%。"
            f"最终分 = max（本轴最低分{floor:g}，{base:g} ×（1 − {rate:g}%）），"
            f"只在最后按四舍五入保留一位小数，得到{row['score']:.1f}分。"
            "低谷只计主要状态尚未包含的独立损害，不按事件条数重复相加。"
        )
    current = row.get("recovery_formula_version") == "GOVERNANCE-STATE-RECOVERY-V4"
    lines = []
    if not current:
        lines.append("本条属于池外保留结果，以下展示原记录采用的恢复路径与保留数值，不按现行机制重裁，也不进入当前综合榜。")
    paths = row.get("recovery_path_basis") or {}
    for key, name in NAMES.items():
        detail = paths[key]
        start = int(str(detail["start_band"]).split("-")[-1])
        end = int(str(detail["highest_achieved_band"]).split("-")[-1])
        credit = detail.get("boundary_difficulty_credit", 0)
        weight = detail.get("axis_weight", {"C1": .5, "C2": .2, "C3": .3}[key])
        factor = detail.get("attribution_factor", (row.get("recovery_attribution") or {}).get("factor", 0))
        weighted = detail.get("weighted_difficulty_credit", 0)
        lines.append(
            f"{name}恢复路径：{GRADES[start]}档→{GRADES[end]}档，跨档难度合计{credit:g}；"
            f"轴权重{weight * 100:g}%，本人责任系数{factor:g}，"
            f"记录中的加权恢复贡献为{weighted:g}（乘10计入恢复分）。"
        )
    if current:
        lines.append("向上跨档难度依次为：E→D 0.6、D→C 0.8、C→B 1.0、B→A 1.3、A→S 1.6；只累计可比恢复基线至任期结束仍保留的档界。本人责任系数取1、0.5或0。")
    recovery = row.get("recovery_score", 0)
    retained = row.get("positive_score_retained", 0)
    cap = row.get("terminal_cap", 27)
    lines.append(
        f"三轴恢复合成后，正式恢复分为{recovery:g}；恢复分最高27分。"
        f"本条终点质量上限为{cap:g}分，最终保留恢复{retained:g}分。"
    )
    drops = row.get("deterioration_path_basis") or {}
    for key, name in NAMES.items():
        d = drops.get(key, {})
        if not d:
            continue
        start = str(d.get("reference_band", "")).split("-")[-1]
        end = str(d.get("end_band", "")).split("-")[-1]
        if not start.isdigit() or not end.isdigit():
            continue
        lines.append(
            f"{name}恶化路径：{GRADES[int(start)]}档→{GRADES[int(end)]}档；"
            f"下降{d.get('raw_drop', 0):g}档 × 本人责任系数{d.get('attribution_factor', 0):g}"
            f" × 轴权重{d.get('axis_weight', 0) * 100:g}%。"
        )
    deterioration = row.get("deterioration_penalty", 0)
    weighted_drop = row.get("weighted_attributable_deterioration", 0)
    if current:
        lines.append(f"本人造成的加权下降为{weighted_drop:g}；恶化扣分 = min（1，{weighted_drop:g} ÷ 2）× 13，正式扣{deterioration:g}分。")
    else:
        lines.append(f"原记录保留的恶化扣分为{deterioration:g}分。")
    grade = row.get("destructive_amplification_grade", "DA0")
    from emperor_v4.evaluation.second_item_c_public import DA_LABELS
    cost = row.get("destructive_amplification_penalty", 0)
    lines.append(f"额外民力成本采用“{DA_LABELS[grade]}”，按成本档表扣{cost:g}分；只计未被状态、低谷、恶化或军事成本包含的独立负担。")
    raw = retained - deterioration - cost
    lines.append(
        f"净调整 = 保留恢复{retained:g} − 恶化扣分{deterioration:g} − 额外成本{cost:g} = {raw:g}；"
        f"限制在−40至27分并按正式规则保留一位小数，最终{row['score']:+.1f}分。"
    )
    return "\n\n".join(lines)
