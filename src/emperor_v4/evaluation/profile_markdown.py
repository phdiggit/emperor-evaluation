from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_registry import (
    PROFILE_ROOT,
    ROOT,
    profile_axis_entry,
    profile_axis_files,
)
from emperor_v4.evaluation.profile_parent_schema import (
    parent_chains,
    representative_parent_chains,
)

AXIS_FILES = profile_axis_files()
C1_DISPLAY_REF_LIMIT = 4
C2_DISPLAY_REF_LIMIT = 4


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _grade(record: dict[str, Any]) -> str:
    return f"{record['axis_grade']}-{record['position']}"


def _limitation_values(record: dict[str, Any]) -> list[str]:
    values = record.get("limitations") or []
    if isinstance(values, str):
        values = [values]
    normalized = [str(value) for value in values if value]
    if len(normalized) > 1 and all(len(value) == 1 for value in normalized):
        return ["".join(normalized)]
    return normalized


def _shared_limitations(records: list[dict[str, Any]]) -> tuple[dict[str, str], list[tuple[str, str]]]:
    counts = Counter(value for row in records for value in _limitation_values(row))
    shared = [(text, count) for text, count in counts.items() if count >= 5]
    shared.sort(key=lambda item: (-item[1], item[0]))
    labels = {text: f"L{index}" for index, (text, _) in enumerate(shared, 1)}
    return labels, [(labels[text], f"{text}（适用于{count}人）") for text, count in shared]


def _limitations(record: dict[str, Any], labels: dict[str, str]) -> str:
    values = [labels.get(value, value) for value in _limitation_values(record)]
    return "；".join(values) or "无"


def _parent_basis(parent: dict[str, Any]) -> str:
    for key in ("lifecycle_narrative", "cycle_basis", "constraint_and_task", "coalition_task", "basis", "lifecycle_review"):
        if parent.get(key):
            return str(parent[key])
    return "该父链的结构化字段见正式JSON。"


def _parent_chains(row: dict[str, Any]) -> list[dict[str, Any]]:
    return parent_chains(row)


def _representative_parent_chains(row: dict[str, Any]) -> list[dict[str, Any]]:
    return representative_parent_chains(row)


def _c1_negative_grade(record: dict[str, Any]) -> str:
    """Return the strongest score-bearing C1 negative diagnostic for the table."""

    roles: list[str] = []
    for parent in _parent_chains(record):
        if parent.get("consumption_status") != "SCORING_PARENT":
            continue
        direction = str(parent.get("direction") or "")
        role = str(parent.get("diagnostic_role") or "")
        if direction == "MIXED_POSITIVE":
            role = str(parent.get("counter_diagnostic_role") or role)
        if direction in {"NEGATIVE", "MIXED_NEGATIVE", "MIXED_POSITIVE"} and role.startswith("DW"):
            roles.append(role)
    return max(roles, key=lambda value: int(value[2:])) if roles else "DW0"


def _c1_type_summary(record: dict[str, Any]) -> str:
    """Compact person-type label for the C1 full-pool scan table."""

    scoring = [
        parent
        for parent in _parent_chains(record)
        if parent.get("consumption_status") == "SCORING_PARENT"
    ]
    positive_count = sum(parent.get("direction") in {"POSITIVE", "MIXED_POSITIVE"} for parent in scoring)
    negative_grade = _c1_negative_grade(record)
    has_negative = negative_grade != "DW0"
    grade = str(record.get("axis_grade") or "")
    if grade == "G5":
        return "历史级长板—深下沿复合型" if has_negative else "历史级战略重构型"
    if grade == "G4":
        if positive_count >= 2 and has_negative:
            return "跨域强战略—风险下沿型"
        if positive_count >= 2:
            return "跨域战略重构型"
        return "高难战略适应型" if not has_negative else "强长板—风险失配型"
    if grade == "G3":
        if positive_count and has_negative:
            return "中上战略—风险波动型"
        if positive_count:
            return "有限战略适应型"
        return "战略风险失配型" if has_negative else "战略覆盖有限型"
    if grade == "G2":
        return "局部能力—高风险失配型" if has_negative else "局部战略适应型"
    if grade == "G1":
        return "低位战略失控型" if has_negative else "低覆盖战略型"
    return "多机制战略失能型" if has_negative else "战略证据不足型"


def _parent_refs(
    parent: dict[str, Any],
    *,
    compact_sources: bool = False,
    include_cycle_anchors: bool = False,
) -> list[str]:
    if compact_sources:
        keys = (
            ("direct_process_refs", "cycle_anchor_refs", "source_refs")
            if include_cycle_anchors
            else ("direct_process_refs", "source_refs")
        )
        for key in keys:
            refs = parent.get(key) or []
            if refs:
                return list(dict.fromkeys(str(ref) for ref in refs))
        return []

    refs: list[str] = []
    for key in ("source_refs", "direct_process_refs", "cycle_anchor_refs", "source_parent_refs"):
        for ref in parent.get(key, []) or []:
            value = str(ref)
            if value not in refs:
                refs.append(value)
    return refs


def _parent_lines(
    parent: dict[str, Any],
    *,
    compact_sources: bool = False,
    include_cycle_anchors: bool = False,
    source_limit: int = C1_DISPLAY_REF_LIMIT,
) -> Iterable[str]:
    direction = parent.get("direction", "—")
    strength = parent.get("intensity") or parent.get("material_strength") or parent.get("material_intensity") or "—"
    mode = str(parent.get("capability_mode") or parent.get("result_responsibility") or "")
    if "operational_design" in mode:
        direction_label = {"POSITIVE": "统筹+", "NEGATIVE": "统筹−", "MIXED": "统筹±"}.get(str(direction), "统筹")
        yield f"- `{parent.get('parent_id', 'NO-ID')}`（{direction_label} / {strength}）：{_parent_basis(parent)}"
    else:
        yield f"- `{parent.get('parent_id', 'NO-ID')}`（{direction} / {strength}）：{_parent_basis(parent)}"
    refs = _parent_refs(
        parent,
        compact_sources=compact_sources,
        include_cycle_anchors=include_cycle_anchors,
    )
    if refs:
        if compact_sources and len(refs) > source_limit:
            display_refs = refs[:source_limit]
            suffix = f"；其余{len(refs) - source_limit}条直接定位见正式JSON"
            yield "  - 直接定位（节选）：" + "；".join(display_refs) + suffix
        elif compact_sources:
            yield "  - 直接定位：" + "；".join(refs)
        else:
            yield "  - 来源：" + "；".join(refs)


def _m3_source_lines(record: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in record.get("source_evidence") or []:
        title = str(item.get("source_title") or "").strip()
        quote = " ".join(str(item.get("quote") or "").split())
        if title and quote:
            lines.append(f"  - {title}：{quote}")
    return lines


def _m3_reader_text(value: Any) -> str:
    text = str(value or "")
    replacements = (
        (
            "现有正式结果材料没有闭合到独立的本人过程父链，行为归责仅使用C4已审定部分，不能外推为完整政策能力画像。",
            "现有材料不足以还原独立、完整的个人决策过程，不能外推为完整政策能力画像。",
        ),
        ("按固定审计闭合；未找到不转零", "按现有证据范围判断；没有找到材料不等于负证"),
        ("专项补审", "专项核对"),
        ("最新C1已明确", "C1材料表明"),
        ("最新C2已明确", "C2材料表明"),
        ("按最新边界", "依本轴边界"),
        ("旧DA3撤销为DA0", "因此裁为DA0"),
        ("旧DA", "此前DA"),
        ("NOT_APPLICABLE", "不在该项计入"),
        ("成本登记", "成本材料"),
        ("父链", "行为链"),
        ("审计", "核对"),
        ("机器", ""),
        ("全国同步脱困", "全国同时脱困"),
        ("去重规则", "归属边界"),
        ("内部去重", "项目归属"),
        ("去重", "避免重复计入"),
        ("消费", "计入"),
        ("机械", "直接"),
        ("合同", "规则"),
        ("FULL_OR_MAJOR_REGIONAL", "完整或主要区域"),
        ("LIMITED_REGIONAL", "有限区域"),
        ("UNRESOLVED_NOT_HIGH_GRADE_GATE", "仅适用于非高档"),
        ("MATERIAL", "部分归责"),
        ("FULL", "主要归责"),
        ("NONE", "不另归责"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = re.sub(r"M\d+(?:-[A-Z0-9]+)+", "材料", text)
    text = re.sub(r"\b(?:raw|formal|terminal_quality|source_ref|material_id)\b", "", text, flags=re.I)
    text = re.sub(r"\b[A-Z][A-Z _-]{5,}\b", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ；")
    return text


def _m3_vector(values: list[int]) -> str:
    return "/".join(f"{value}档" for value in values)


def _m3_starting_context(record: dict[str, Any]) -> str:
    trajectory = record["ability_evidence"]["trajectory"]
    return (
        f"接手时民生、经济财政、社会安全分别为{_m3_vector(trajectory['start_vector'])}；"
        f"任内主态为{_m3_vector(trajectory['main_vector'])}，交班为{_m3_vector(trajectory['end_vector'])}。"
    )


def _m3_construction(record: dict[str, Any]) -> str:
    trajectory = record["ability_evidence"]["trajectory"]
    return (
        f"三轴最高实现为{_m3_vector(trajectory['peak_vector'])}，"
        f"建设恢复{float(trajectory['recovery_score_27']):.1f}/27，"
        f"稳定兑现与压力吸收{float(trajectory['stability_score_18']):.1f}/18；"
        f"交班较主态回落{_m3_vector(trajectory['rollback_vector'])}。"
    )


def _m3_handoff(record: dict[str, Any]) -> str:
    trajectory = record["ability_evidence"]["trajectory"]
    return f"交班时民生、经济财政、社会安全分别为{_m3_vector(trajectory['end_vector'])}。"


def _m3_limitations(record: dict[str, Any]) -> str:
    values = []
    for value in _limitation_values(record):
        text = _m3_reader_text(value)
        if (
            text
            and text not in {"None", "主要归责", "部分归责", "不另归责"}
            and not re.fullmatch(r"(?:[A-Z][A-Z _-]+；?)+", text)
        ):
            values.append(text)
    return "；".join(dict.fromkeys(values)) or "无"


def _overview_table(axis: str, records: list[dict[str, Any]], labels: dict[str, str]) -> list[str]:
    if axis == "C1":
        lines = [
            "| 雷达值 | 档位 | 位置 | 人物 | 政权 | 证据 | 置信度 | 人物类型 | 负证档位 |",
            "|---:|---|---|---|---|---|---|---|---|",
        ]
        for row in records:
            cells = [
                row["radar_value"],
                row["axis_grade"],
                row["position"],
                row["ruler_name"],
                row["polity"],
                row["axis_evidence_level"],
                row["confidence"],
                _c1_type_summary(row),
                _c1_negative_grade(row),
            ]
            lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
        return lines
    if axis == "C2":
        def public_review_status(row: dict[str, Any]) -> str:
            status = str(row.get("review_status", ""))
            return "证据下限" if status.startswith("EVIDENCE_FLOOR") else "有界结论"

        lines = [
            "| 雷达值 | 档位 | 位置 | 人物 | 政权 | 证据 | 置信度 | 证据边界 | 典型模式 | 限制 |",
            "|---:|---|---|---|---|---|---|---|---|---|",
        ]
        for row in records:
            cells = [row["radar_value"], row["axis_grade"], row["position"], row["ruler_name"], row["polity"], row["axis_evidence_level"], row["confidence"], public_review_status(row), row["typical_pattern"], _limitations(row, labels)]
            lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
        return lines
    if axis == "M4":
        lines = [
            "| 序 | 人物 | 政权 | 实际权力窗口 | 档位 | 位置 | 雷达值 | 证据 | 输出 | 状态 | 父链 | 典型模式 |",
            "|---:|---|---|---|---|---|---:|---|---|---|---:|---|",
        ]
        for row in records:
            cells = [row["sequence"], row["ruler_name"], row["polity"], row["actual_power_window"], row["axis_grade"], row["position"], row["radar_value"], row["axis_evidence_level"], row["output_mode"], row["score_status"], len(_parent_chains(row)), row["typical_pattern"]]
            lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
        return lines
    if axis == "M3":
        lines = [
            "| 人物 | 政权 | 民生局面 | 经济财政局面 | 社会安全局面 | 任内动态 | 档位 | 雷达值 | 证据 |",
            "|---|---|---|---|---|---|---|---:|---|",
        ]
        for row in records:
            components = row["components"]
            cells = [
                row["ruler_name"], row["polity"],
                row["absolute_state_meanings"]["C1"], row["absolute_state_meanings"]["C2"],
                row["absolute_state_meanings"]["C3"], row["dynamic_label"],
                f"{row['axis_grade']}-{row['position']}",
                row["radar_value"], row["axis_evidence_level"],
            ]
            lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
        return lines
    if axis == "C3":
        lines = [
            "| 序 | 人物 | 政权 | 实际权力窗口 | 档位 | 位置 | 雷达值 | 证据 | 输出 | 状态 | 父链 | 典型模式 | 限制 |",
            "|---:|---|---|---|---|---|---:|---|---|---|---:|---|---|",
        ]
        for row in records:
            cells = [row["sequence"], row["ruler_name"], row["polity"], row["actual_power_window"], row["axis_grade"], row["position"], row["radar_value"], row["axis_evidence_level"], row["output_mode"], row["score_status"], len(_parent_chains(row)), row["typical_pattern"], _limitations(row, labels)]
            lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
        return lines
    lines = [
        "| 展示序 | 池序 | 人物 | 档位 | 潜在高档假设 | 雷达值 | 证据 | 置信度 | 输出模式 | 典型模式 |",
        "|---:|---:|---|---|---|---:|---|---|---|---|",
    ]
    for display, row in enumerate(records, 1):
        latent = row.get("latent_high_grade_hypothesis") or "—"
        if isinstance(latent, dict):
            latent = latent.get("grade") or latent.get("axis_grade") or "有"
        cells = [display, row["sequence"], row["ruler_name"], _grade(row), latent, row["radar_value"], row["axis_evidence_level"], row["confidence"], row["output_mode"], row["typical_pattern"]]
        lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
    return lines


def render_profile_markdown(settlement: dict[str, Any]) -> str:
    axis = settlement["axis_code"]
    if axis not in AXIS_FILES:
        raise ValueError(f"unsupported profile axis: {axis}")
    records = settlement["records"]
    labels, shared = ({}, []) if axis in {"M3", "M4"} else _shared_limitations(records)
    profile_note = (
        "> 独立人物画像轴；不进入五项综合总榜，不生成画像总分或轴内排名。本文逐人展示正式裁决。"
        if axis == "M3"
        else "> 独立人物画像轴；不进入五项综合总榜，不生成画像总分或轴内排名。JSON是唯一机器入口；本文是同值阅读视图。"
    )
    if axis == "M3":
        reading_source_note = "- 逐人条目分别说明局面、行为、后果与裁档理由；来源按书名与原文逐行列出。"
    elif axis == "C1":
        reading_source_note = f"- 全池表的‘典型模式’为人物类型摘要，‘限制’只显示最强计分负证档位；逐人条目展开完整主模式、裁档理由、限制和代表父链，每条父链最多列{C1_DISPLAY_REF_LIMIT}条直接过程定位，完整来源集合保留在正式JSON。"
    elif axis == "C2":
        reading_source_note = f"- 逐人条目只展开核心依据、档内定位、限制和代表父链；每条父链最多列{C2_DISPLAY_REF_LIMIT}条直接过程定位，完整来源集合与关联父链保留在正式JSON。"
    else:
        reading_source_note = "- 逐人条目只展开主模式、裁档理由、限制和代表父链；来源紧随父链，避免重复整段口径。"
    lines = [
        f"# {axis} {settlement['axis_name']}正式结算",
        "",
        profile_note,
        "",
        "## 阅读说明",
        "",
        "- 全池表用于横向扫读；顺序仅是稳定展示顺序，不是画像排名。",
        "- `G0—G5`与档内位置共同映射雷达值；`E1—E3`表示证据完成度，不能替代能力裁决。",
        reading_source_note,
        "",
    ]
    if shared:
        lines.extend(["### 共用限制说明", ""])
        lines.extend(f"- `{label}`：{text}" for label, text in shared)
        lines.append("")
    if axis == "M1":
        lines.extend([
            "## 军事画像口径",
            "",
            "- 裁档结果由正式 JSON 中的 `axis_grade` 与 `position` 给出，裁档理由须与之同值。",
            "- M1 裁档理由与档内依据不得使用第三项的汇总数值；第三项只可作为具体父周期结果的追溯入口。",
            "- `operational_design` 在阅读层统一标作“统筹+／统筹−／统筹±”，不再伪装为前线指挥。",
            "- 自然语言中的情境数量不作为机器裁档输入；复核以结构化父链为准。",
            "",
        ])
    if axis == "C5":
        lines.extend([
            "## 权力运用画像口径",
            "",
            "- 逐人正式值、关键事实和材料依据以当前 JSON 及同值阅读视图为准。",
            "- 每人均单列关键事实、裁档理由与史料定位；链接只作阅读入口，不能替代具名史源与卷次。",
            "- 个案烈度与MI覆盖分离；一般政治斗争、轴外成败和他人独立行为不得倒灌C5。",
            "- 逐人依据先展示当前裁决事实，再展示与主要入口绑定的结构化代表父链；两者共同限定结论，不按材料条数加减档位。",
            "",
        ])
    if axis == "C2":
        lines.extend([
            "## 信息处理画像口径",
            "",
            "- 逐人正式值、关键事实和材料依据以当前 JSON 及同值阅读视图为准。",
            "- “证据下限”只概括当前已观察模式，不得解释为全生涯能力实质低下。",
            "- 不按目标分布放宽G档门槛，不用跨轴组合链、结果倒推或无父链默认落点代替裁决。",
            "",
        ])
    lines.extend(["## 全池结算表", ""])
    lines.extend(_overview_table(axis, records, labels))
    lines.extend(["", "## 逐人裁决依据", ""])
    for display, row in enumerate(records, 1):
        if axis == "M3":
            lines.extend([
                f"### {display}. {row['ruler_name']}",
                "",
                f"- **结算**：`{_grade(row)}` / 雷达值 `{row['radar_value']}` / 证据 `{row['axis_evidence_level']}`。",
                f"- **接手局面**：{_m3_starting_context(row)}",
                f"- **建设与维持**：{_m3_construction(row)}",
                f"- **成本与后果**：{_m3_reader_text(row['costs_and_consequences'])}",
                f"- **关键行为链**：{_m3_reader_text(row['behavior_chain'])}",
                f"- **交班局面**：{_m3_handoff(row)}",
                f"- **落档理由**：{_m3_reader_text(row['grade_basis'])}",
                f"- **档内位置**：{_m3_reader_text(row['position_basis'])}",
                f"- **限制**：{_m3_limitations(row)}",
                "- **来源**：",
                *_m3_source_lines(row),
                "",
            ])
            continue
        lines.extend([
            f"### {display}. {row['ruler_name']}（{row['ruler_id']}）",
            "",
            f"- **结算**：`{_grade(row)}` / 雷达值 `{row['radar_value']}` / `{row['axis_evidence_level']}` / `{'证据有限' if axis == 'C2' and row['score_status'] == 'EVIDENCE_LIMITED' else row['score_status']}`。",
            f"- **{'核心依据' if axis == 'C2' else '主模式'}**：{row.get('grade_basis') if axis == 'C2' else row['typical_pattern']}",
            *([] if axis == "C2" else [f"- **裁档理由**：{row.get('grade_basis') or '见结构化父链与正式裁决源。'}"]),
            f"- **{'档内定位' if axis == 'C2' else '档内位置'}**：{row.get('position_basis') or '由同档材料强度与反例共同确定。'}",
            f"- **限制**：{_limitations(row, labels)}",
        ])
        if axis == "C5" and row.get("public_evidence_points"):
            lines.append("- **关键事实与边界**：")
            for point in row["public_evidence_points"]:
                lines.append(f"  - **{point['title']}**")
                lines.extend(f"    - {detail}" for detail in point.get("details", []))
        if axis == "M1":
            projection = row.get("military_talent_registry_projection") or {}
            paired = projection.get("paired_result_difficulty_campaign_roles_display")
            lines.append("- 武将登记逐项（成果等级/难度｜战役群名称/武将角色）：")
            lines.append(f"  {paired or '—'}")
        parents = _parent_chains(row)
        if axis in {"C1", "C2"}:
            parents = _representative_parent_chains(row)
        if parents:
            lines.append("- **代表父链**：")
            for parent in parents:
                if axis == "C2":
                    lines.extend(
                        _parent_lines(
                            parent,
                            compact_sources=True,
                            include_cycle_anchors=True,
                            source_limit=C2_DISPLAY_REF_LIMIT,
                        )
                    )
                else:
                    lines.extend(_parent_lines(parent, compact_sources=axis == "C1"))
        else:
            lines.append("- **代表父链**：当前无闭合父链；不得把缺材料当作负证。")
        if axis == "C5" and row.get("source_refs"):
            lines.append("- **史料与定位**：")
            lines.extend(f"  - {ref}" for ref in row["source_refs"])
        lines.append("")
    if axis == "C3":
        lines.extend([
            "## C3 专项边界",
            "",
            "档位来自显式逐人裁决源；不读取第五项B或其他画像轴的档位、方向、MI或分值。最终治绩、名臣数量、官职数量、处罚伦理与集团成果均不得换算为C3。",
            "",
        ])
    if axis == "M3":
        lines.extend([
            "## M3 专项边界", "",
            "M3以第二项C1、C2、C3、C4的正式裁决为事实底座，但不相加、不线性折算，也不把任一子项档位一对一转换为M3。先判断民生、经济财政与社会安全的绝对局面组合，再判断任内建设、承压、恶化及其归责，最后用行为链、阶段反转和交班下沿复核语义档位；雷达值只由最终档位与档内位置固定投影。旧M3过程材料继续用于补正行为、反馈、成本和归责，不按政策数量计功扣责。", "",
        ])
    if axis == "M4":
        lines.extend([
            "## M4 专项边界", "",
            "档位来自显式逐人国内集团联盟生命周期裁决；M2外部联盟、C3个人用人、C5权力伦理、第一项B开国团队成果、第四项A社会整合结果、第二项治理结果、集团数量和材料数量均不转换为M4。", "",
        ])
    return "\n".join(lines)


def write_axes(axis_codes: Iterable[str]) -> list[Path]:
    written = []
    axes = list(axis_codes)
    for axis in axes:
        entry = profile_axis_entry(axis)
        json_path = ROOT / entry["json"]
        payload = load_json(json_path)
        markdown_path = ROOT / entry["markdown"]
        markdown_path.write_text(render_profile_markdown(payload), encoding="utf-8", newline="\n")
        written.append(markdown_path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="生成已结算C类画像轴的同值Markdown阅读视图")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--axis", action="append", choices=sorted(AXIS_FILES))
    args = parser.parse_args()
    axes = args.axis or list(AXIS_FILES)
    if not args.write:
        parser.error("必须显式传入 --write")
    for path in write_axes(axes):
        print(path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
