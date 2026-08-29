from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
AXIS_FILES = {
    "M1": "M1/01-M1军事判断与统帅能力正式结算.json",
    "C1": "C1/15-C1战略判断与风险控制正式结算.json",
    "C2": "C2/19-C2信息处理学习与纠错正式结算.json",
    "C3": "C3/24-C3人才识别配置与授权正式结算.json",
    "C5": "C5/02-C5权力运用风格与克制正式结算.json",
    "M3": "M3/29-M3民生财政建设正式结算.json",
    "M4": "M4/34-M4政治联盟与内部联盟管理正式结算.json",
}


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


def _parent_refs(parent: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("source_refs", "direct_process_refs", "cycle_anchor_refs", "source_parent_refs"):
        for ref in parent.get(key, []) or []:
            value = str(ref)
            if value not in refs:
                refs.append(value)
    return refs


def _parent_lines(parent: dict[str, Any]) -> Iterable[str]:
    direction = parent.get("direction", "—")
    strength = parent.get("intensity") or parent.get("material_strength") or parent.get("material_intensity") or "—"
    mode = str(parent.get("capability_mode") or parent.get("result_responsibility") or "")
    if "operational_design" in mode:
        direction_label = {"POSITIVE": "统筹+", "NEGATIVE": "统筹−", "MIXED": "统筹±"}.get(str(direction), "统筹")
        yield f"- `{parent.get('parent_id', 'NO-ID')}`（{direction_label} / {strength}）：{_parent_basis(parent)}"
    else:
        yield f"- `{parent.get('parent_id', 'NO-ID')}`（{direction} / {strength}）：{_parent_basis(parent)}"
    refs = _parent_refs(parent)
    if refs:
        yield "  - 来源：" + "；".join(refs)


def _overview_table(axis: str, records: list[dict[str, Any]], labels: dict[str, str]) -> list[str]:
    if axis == "C1":
        lines = [
            "| 雷达值 | 档位 | 位置 | 人物 | 政权 | 证据 | 置信度 | 典型模式 | 限制 |",
            "|---:|---|---|---|---|---|---|---|---|",
        ]
        for row in records:
            cells = [row["radar_value"], row["axis_grade"], row["position"], row["ruler_name"], row["polity"], row["axis_evidence_level"], row["confidence"], row["typical_pattern"], _limitations(row, labels)]
            lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
        return lines
    if axis == "C2":
        lines = [
            "| 雷达值 | 档位 | 位置 | 人物 | 政权 | 证据 | 置信度 | 典型模式 | 限制 |",
            "|---:|---|---|---|---|---|---|---|---|",
        ]
        for row in records:
            cells = [row["radar_value"], row["axis_grade"], row["position"], row["ruler_name"], row["polity"], row["axis_evidence_level"], row["confidence"], row["typical_pattern"], _limitations(row, labels)]
            lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
        return lines
    if axis == "M4":
        lines = [
            "| 序 | 人物 | 政权 | 实际权力窗口 | 档位 | 位置 | 雷达值 | 证据 | 输出 | 状态 | 父链 | 典型模式 |",
            "|---:|---|---|---|---|---|---:|---|---|---|---:|---|",
        ]
        for row in records:
            cells = [row["sequence"], row["ruler_name"], row["polity"], row["actual_power_window"], row["axis_grade"], row["position"], row["radar_value"], row["axis_evidence_level"], row["output_mode"], row["score_status"], len(row["parents"]), row["typical_pattern"]]
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
            cells = [row["sequence"], row["ruler_name"], row["polity"], row["actual_power_window"], row["axis_grade"], row["position"], row["radar_value"], row["axis_evidence_level"], row["output_mode"], row["score_status"], len(row["parents"]), row["typical_pattern"], _limitations(row, labels)]
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
    labels, shared = ({}, []) if axis == "M4" else _shared_limitations(records)
    lines = [
        f"# {axis} {settlement['axis_name']}正式结算",
        "",
        "> 独立人物画像轴；不进入五项综合总榜，不生成画像总分或轴内排名。JSON是唯一机器入口；本文是同值阅读视图。",
        "",
        "## 阅读说明",
        "",
        "- 全池表用于横向扫读；顺序仅是稳定展示顺序，不是画像排名。",
        "- `G0—G5`与档内位置共同映射雷达值；`E1—E3`表示证据完成度，不能替代能力裁决。",
        "- 逐人条目只展开主模式、裁档理由、限制和代表父链；来源紧随父链，避免重复整段口径。",
        "",
    ]
    if shared:
        lines.extend(["### 共用限制说明", ""])
        lines.extend(f"- `{label}`：{text}" for label, text in shared)
        lines.append("")
    if axis == "M1":
        lines.extend([
            "## 结算账本整改（2026-08）",
            "",
            "- 发布真值只由 JSON 中的 `axis_grade` 与 `position` 决定；阅读层中与该真值冲突的旧“取Gx／定Gx／支持Gx”表述已清除。",
            "- M1 裁档理由与档内依据不得使用第三项的汇总数值；第三项只可作为具体父周期结果的追溯入口。",
            "- `operational_design` 在阅读层统一标作“统筹+／统筹−／统筹±”，不再伪装为前线指挥。",
            "- 自然语言中的情境数量不作为机器裁档输入；复核以结构化父链为准。整改范围、命中对象和异常重裁候选见同目录 `12-M1结算账本整改与异常重裁复核.json`。",
            "",
        ])
    lines.extend(["## 全池结算表", ""])
    lines.extend(_overview_table(axis, records, labels))
    lines.extend(["", "## 逐人裁决依据", ""])
    for display, row in enumerate(records, 1):
        if axis == "M3":
            lines.extend([
                f"### {display}. {row['ruler_name']}（{row['ruler_id']}）",
                "",
                f"- **结算**：`{_grade(row)}` / 雷达值 `{row['radar_value']}` / `{row['axis_evidence_level']}` / `{row['score_status']}`。",
                f"- **接手局面**：{row['starting_context']}",
                f"- **建设与维持**：{row['construction_and_maintenance']}",
                f"- **成本与后果**：{row['costs_and_consequences']}",
                f"- **关键行为链**：{row['behavior_chain']}",
                f"- **交班局面**：{row['handoff_state']}",
                f"- **落档理由**：{row['grade_basis']}",
                f"- **档内位置**：{row['position_basis']}",
                f"- **限制**：{_limitations(row, labels)}",
                f"- **来源**：{'；'.join(row.get('source_refs') or [])}",
                "",
            ])
            continue
        lines.extend([
            f"### {display}. {row['ruler_name']}（{row['ruler_id']}）",
            "",
            f"- **结算**：`{_grade(row)}` / 雷达值 `{row['radar_value']}` / `{row['axis_evidence_level']}` / `{row['score_status']}`。",
            f"- **主模式**：{row['typical_pattern']}",
            f"- **裁档理由**：{row.get('grade_basis') or '见结构化父链与正式裁决源。'}",
            f"- **档内位置**：{row.get('position_basis') or '由同档材料强度与反例共同确定。'}",
            f"- **限制**：{_limitations(row, labels)}",
        ])
        if axis == "M1":
            projection = row.get("military_talent_registry_projection") or {}
            paired = projection.get("paired_result_difficulty_campaign_roles_display")
            lines.append("- 武将登记逐项（成果等级/难度｜战役群名称/武将角色）：")
            lines.append(f"  {paired or '—'}")
        parents = row.get("parents", [])
        if parents:
            lines.append("- **代表父链**：")
            for parent in parents:
                lines.extend(_parent_lines(parent))
        else:
            lines.append("- **代表父链**：当前无闭合父链；不得把缺材料当作负证。")
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
        json_path = PROFILE_ROOT / AXIS_FILES[axis]
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown_path = json_path.with_suffix(".md")
        markdown_path.write_text(render_profile_markdown(payload), encoding="utf-8", newline="\n")
        written.append(markdown_path)
    manifest_path = PROFILE_ROOT / "00-已结算轴正式入口.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_code = {row["axis_code"]: row for row in manifest["axes"]}
    for axis, path in zip(axes, written, strict=True):
        by_code[axis]["markdown_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
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
