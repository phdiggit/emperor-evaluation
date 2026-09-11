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
C3_DISPLAY_REF_LIMIT = 3


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _grade(record: dict[str, Any]) -> str:
    return f"{record['axis_grade']}-{record['position']}"


def _m2_adjudication_label(record: dict[str, Any]) -> str:
    state = str(record.get("adjudication_state") or "FORMAL_CURRENT")
    if state == "UNRESOLVED_EVIDENCE_GAP":
        return "待补证（旧值仅显示）"
    if state == "REASSESSMENT_REQUIRED":
        return "待重算（有界显示点）"
    return "当前正式"


def _m2_display_grade(record: dict[str, Any]) -> str:
    grade = _grade(record)
    return f"显示点·{grade}" if record.get("display_point_only") else grade


def _m2_display_radar(record: dict[str, Any]) -> str | int:
    return "—" if record.get("display_point_only") else record["radar_value"]


def _m2_source_display_ref(value: str) -> str:
    """Keep semantic anchors, but omit verbose line/paragraph locators in M2 Markdown."""

    value = re.sub(r"#L\d+(?:[-—–]L?\d+)*$", "", value)
    value = re.sub(r"#P\d+(?:[-—–]P?\d+)*$", "", value)
    return value


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


def _c5_person_type(record: dict[str, Any]) -> str:
    value = str(record.get("person_type") or "").strip()
    return value or "综合权力边界型"


def _c3_short_text(value: Any, limit: int = 96) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"^.*?（[^）]*）[：:]\s*", "", text)
    text = text.strip("；。 ")
    if len(text) > limit:
        return text[: limit - 1].rstrip("；，、 ") + "…"
    return text


def _c3_clauses(value: Any) -> list[str]:
    clauses: list[str] = []
    for part in re.split(r"[；。]", str(value or "")):
        part = re.sub(r"^#+\s*", "", part).strip("；。 ")
        if part and part not in clauses:
            clauses.append(part)
    return clauses


def _c3_person_type(record: dict[str, Any]) -> str:
    """Return a compact C3 type label for the full-pool scan table."""

    grade = str(record.get("axis_grade") or "")
    position = str(record.get("position") or "")
    domains = {str(value) for value in record.get("major_task_domains_observed") or ()}
    text = " ".join(
        str(record.get(key) or "")
        for key in ("typical_pattern", "counterpattern", "grade_basis", "position_basis")
    )
    has_feedback = bool(re.search(r"反馈|纠偏|重配|替换|收权|复用|复发", text))
    has_risk = bool(re.search(r"失灵|错配|误用|偏置|反转|风险|反证|下沿|不足|不稳|清洗|受损", text))
    cross_domain = len(domains & {
        "MILITARY", "ADMINISTRATION", "JUDICIAL_OVERSIGHT",
        "DIPLOMATIC_COALITION", "SUCCESSION_AND_POWER_RELATIONS",
    }) >= 2
    if grade == "G5":
        return "历史级跨域授权—深下沿型" if has_risk else "历史级跨域授权型"
    if grade == "G4":
        if position == "HIGH":
            return "跨域强授权—高位接近型"
        if has_feedback:
            return "跨域强授权—反馈复验型"
        return "跨域强授权—稳定性受限型"
    if grade == "G3":
        if has_risk:
            return "强链—稳定性受限型"
        return "跨域中上配置型" if cross_domain else "中上责任中心型"
    if grade == "G2":
        return "局部强链—反馈受限型" if has_risk or has_feedback else "局部责任链型"
    if grade == "G1":
        return "有限识别—反馈受限型" if has_risk else "责任链薄弱型"
    return "高权任用失控型" if has_risk else "人才保护失灵型"


def _c3_grade_reason(record: dict[str, Any]) -> str:
    grade = str(record.get("axis_grade") or "")
    raw = str(record.get("grade_basis") or "")
    match = re.search(r"为什么是G\d[：:](.*?)(?=；为什么是(?:LOW|MID|HIGH)|$)", raw)
    if match:
        reason = match.group(1)
    else:
        reason = re.sub(r"^G\d-(?:LOW|MID|HIGH)[：:]\s*", "", raw)
        reason = re.split(r"(?:因此定位为|因此定为|故定为)G\d", reason, maxsplit=1)[0]
    clauses = _c3_clauses(reason)
    reason = "；".join(clauses[:2]) if clauses else "见结构化父链与正式裁决。"
    return f"{grade}：{_c3_short_text(reason, 150)}"


def _c3_position_reason(record: dict[str, Any]) -> str:
    grade = str(record.get("axis_grade") or "")
    position = str(record.get("position") or "")
    text = " ".join(
        str(record.get(key) or "")
        for key in ("typical_pattern", "counterpattern", "grade_basis", "position_basis")
    )
    has_feedback = bool(re.search(r"反馈|纠偏|重配|替换|收权|复用|复发", text))
    has_risk = bool(re.search(r"失灵|错配|误用|偏置|反转|风险|反证|下沿|不足|不稳|清洗|受损", text))
    templates = {
        "G5": {
            "HIGH": "正向宽度接近极限，但仍缺少压过反证的更强上沿。",
            "MID": "历史级跨域闭环成立，但错配或人才保护反证压住上沿。",
            "LOW": "历史级能力成立，但成熟期稳定性与人才保护反证较重。",
        },
        "G4": {
            "HIGH": "跨任务复验与反馈闭环最强，但全域迁移仍不及G5。",
            "MID": "跨任务强链成立，但稳定性仍有明确下沿。",
            "LOW": "达到G4门槛，但长期窗口或第二稳定器不足。",
        },
        "G3": {
            "HIGH": "至少一条强链成立，但跨任务稳定性不足以进G4。",
            "MID": "多类责任中心可见，但强度或观察窗口仍居中。",
            "LOW": "局部强链存在，但主要任务或反馈覆盖有限。",
        },
        "G2": {
            "HIGH": "局部强链较突出，但跨域复验不足。",
            "MID": "责任链已有闭合，但长期反馈与迁移性不足。",
            "LOW": "仅见局部配置，持续授权与纠偏证据有限。",
        },
        "G1": {
            "HIGH": "已见明确责任中心，但闭环不稳或材料窗口偏窄。",
            "MID": "局部识别可见，岗位与反馈闭环偏弱。",
            "LOW": "责任中心与后续响应均较薄。",
        },
        "G0": {
            "HIGH": "负向机制跨对象或阶段闭合，已超过单一失误。",
            "MID": "负向责任链占主导，但仍保留局部正证。",
            "LOW": "高权任用与反馈接口出现基础性失灵。",
        },
    }
    reason = templates.get(grade, {}).get(position, "由同档材料强度与反例共同确定。")
    if grade == "G4" and position == "MID" and has_feedback:
        reason = "跨任务强链成立，且有反馈纠偏；稳定性仍有明确下沿。"
    if grade == "G3" and position == "HIGH" and not has_risk:
        reason = "至少一条强链成立，跨任务稳定性尚不足以进G4。"
    if grade == "G2" and position == "HIGH" and has_risk:
        reason = "局部强链较突出，但风险反馈仍未形成稳定闭环。"
    return f"{position}：{_c3_short_text(reason, 120)}"


def _c3_limitation(record: dict[str, Any]) -> str:
    if record.get("score_status") == "EVIDENCE_LIMITED":
        return "证据受限：结论限于已核实的主要任务与阶段。"
    raw_values = [
        str(record.get("position_basis") or ""),
        str(record.get("grade_basis") or ""),
        *_limitation_values(record),
        str(record.get("counterpattern") or ""),
    ]
    candidates: list[str] = []
    for value in raw_values:
        for clause in _c3_clauses(value):
            clause = re.sub(r"^#+\s*", "", clause)
            clause = re.sub(r"^(?:总体画像|G4门槛复核|G4门槛裁定|为什么是[^：]+|(?:LOW|MID|HIGH))[：:]\s*", "", clause)
            if re.match(r"^(?:第)?[一二三四五六七八九十]+、", clause):
                continue
            if (
                re.search(r"限制|不足|缺少|缺乏|不能|不宜|不及|不够|尚未|未达|窗口有限|厚度有限|任期短|短板|短缺|风险|反证|下沿|阻断|不稳|未形成|失灵|偏置|受损|薄", clause)
                and not re.search(r"明确拒绝|要求|检查|能够|形成闭环|持续|继续|直接责问|不能因亲族而授予|只许先任", clause)
            ):
                if clause not in candidates:
                    candidates.append(clause)
    if candidates:
        return _c3_short_text(candidates[0], 72) + ("。" if not candidates[0].endswith(("。", "…")) else "")
    fallback = {
        "G5": "个别错配或成熟期反证限制上沿。",
        "G4": "跨任务稳定性或晚期反证限制上沿。",
        "G3": "强链成立，但稳定性不足以进入G4。",
        "G2": "局部责任链可见，跨域复验不足。",
        "G1": "责任中心与反馈闭环较薄。",
        "G0": "人才保护与高权反馈接口持续失灵。",
    }
    return fallback.get(str(record.get("axis_grade") or ""), "限制见正式JSON。")


def _c3_parent_field(parent: dict[str, Any], key: str) -> str:
    return _c3_short_text(parent.get(key), 92) or "—"


def _c3_parent_lines(parent: dict[str, Any]) -> list[str]:
    direction = parent.get("direction", "—")
    title = str(parent.get("evidence_title") or parent.get("source_domain") or "责任中心")
    details = [str(value) for value in parent.get("evidence_detail") or [] if value]
    lines = [f"- `{parent.get('parent_id', 'NO-ID')}`（{direction}）：{title}"]
    if details:
        lines.append("  - 清单要点：")
        lines.extend(f"    - {detail}" for detail in details)
        lines.append(f"  - 后续响应：{_c3_parent_field(parent, 'authorization_response')}")
    else:
        lines.append(
            f"  - 任务与人选：{_c3_parent_field(parent, 'task_requirement')}；{_c3_parent_field(parent, 'candidate_identification')}"
        )
        lines.append(
            f"  - 岗位与权限：{_c3_parent_field(parent, 'position_configuration')}；{_c3_parent_field(parent, 'actual_authority')}"
        )
        lines.append(
            f"  - 交付与反馈：{_c3_parent_field(parent, 'delivery')}；{_c3_parent_field(parent, 'feedback')}"
        )
        lines.append(f"  - 后续响应：{_c3_parent_field(parent, 'authorization_response')}")
    refs = _parent_refs(parent)
    if refs:
        display_refs = refs[:C3_DISPLAY_REF_LIMIT]
        suffix = f"；其余{len(refs) - len(display_refs)}条见正式JSON" if len(refs) > len(display_refs) else ""
        lines.append("  - 来源（节选）：" + "；".join(display_refs) + suffix)
    return lines


def _c5_political_review_lines(record: dict[str, Any]) -> list[str]:
    review = record.get("political_conflict_review") or {}
    if not review:
        return []
    scope_status = {
        "CONFLICTS_REVIEWED": "已识别冲突已逐案复核",
        "NO_MAJOR_CONFLICT": "未命中需重开的重大冲突触发",
    }.get(
        str(record.get("political_conflict_scope_status") or ""),
        str(record.get("political_conflict_scope_status") or "—"),
    )
    radius = str(review.get("expansion_radius_code") or "—")
    adjudication = str(review.get("semantic_adjudication") or "").strip()
    lines = [f"- **政治斗争复核**：{scope_status}；{radius}。{adjudication}"]
    if review.get("dedup_instruction"):
        lines.append(f"- **政治斗争去重**：{review['dedup_instruction']}")
    return lines


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
    show_routing: bool = False,
    strip_source_locators: bool = False,
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
    if strip_source_locators:
        refs = list(dict.fromkeys(_m2_source_display_ref(ref) for ref in refs))
    if refs:
        if compact_sources and len(refs) > source_limit:
            display_refs = refs[:source_limit]
            suffix = f"；其余{len(refs) - source_limit}条直接定位见正式JSON"
            yield "  - 直接定位（节选）：" + "；".join(display_refs) + suffix
        elif compact_sources:
            yield "  - 直接定位：" + "；".join(refs)
        else:
            yield "  - 来源：" + "；".join(refs)
    projection_reason = str(parent.get("secondary_projection_reason") or "").strip()
    if projection_reason:
        yield "  - 跨轴投影边界：" + projection_reason
    handoff = parent.get("route_handoff")
    if show_routing and handoff:
        if isinstance(handoff, dict):
            target_axis = handoff.get("target_axis") or "—"
            target_parent_ref = handoff.get("target_parent_ref") or "—"
            target = f"{target_axis} / {target_parent_ref}"
            status = str(handoff.get("status") or "—")
            reason = str(handoff.get("reason") or "").strip()
            suffix = f"；{reason}" if reason else ""
            yield f"  - 路由处置：{status} → {target}{suffix}"
        else:
            yield f"  - 路由处置：{_escape(handoff)}"
    if show_routing and parent.get("consumption_status") not in {None, "SCORING_PARENT"}:
        yield f"  - 轴内状态：{parent.get('consumption_status')}"


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
            cells = [row["sequence"], row["ruler_name"], row["polity"], row["actual_power_window"], row["axis_grade"], row["position"], row["radar_value"], row["axis_evidence_level"], row["output_mode"], row["score_status"], len(_parent_chains(row)), _c3_person_type(row), _c3_limitation(row)]
            lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
        return lines
    if axis == "C5":
        lines = [
            "| 展示序 | 池序 | 人物 | 档位 | 雷达值 | 证据 | 置信度 | 输出模式 | 人物类型 |",
            "|---:|---:|---|---|---:|---|---|---|---|",
        ]
        for display, row in enumerate(records, 1):
            cells = [
                display,
                row["sequence"],
                row["ruler_name"],
                _grade(row),
                row["radar_value"],
                row["axis_evidence_level"],
                row["confidence"],
                row["output_mode"],
                _c5_person_type(row),
            ]
            lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
        return lines
    if axis == "M2":
        lines = [
            "| 展示序 | 池序 | 人物 | 档位/显示点 | 潜在高档假设 | 当前雷达值 | 证据 | 置信度 | 输出模式 | 当前状态 | 典型模式 |",
            "|---:|---:|---|---|---|---:|---|---|---|---|---|",
        ]
        for display, row in enumerate(records, 1):
            latent = row.get("latent_high_grade_hypothesis") or "—"
            if isinstance(latent, dict):
                latent = latent.get("grade") or latent.get("axis_grade") or "有"
            cells = [
                display,
                row["sequence"],
                row["ruler_name"],
                _m2_display_grade(row),
                latent,
                _m2_display_radar(row),
                row["axis_evidence_level"],
                row["confidence"],
                row["output_mode"],
                _m2_adjudication_label(row),
                row["typical_pattern"],
            ]
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
    if axis == "C4":
        from emperor_v4.evaluation.profile_c4 import render
        return render(settlement)
    if axis not in AXIS_FILES:
        raise ValueError(f"unsupported profile axis: {axis}")
    records = settlement["records"]
    labels, shared = ({}, []) if axis in {"M3", "M4", "C3"} else _shared_limitations(records)
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
    elif axis == "C5":
        reading_source_note = "- 全池表用人物类型浓缩主模式，不展示潜在高档假设；逐人条目展开主模式、裁档理由、政治斗争复核、限制和代表父链，完整证据与去重结论保留在正式JSON。"
    elif axis == "C3":
        reading_source_note = "- 全池表的‘典型模式’浓缩为人物类型；逐人条目分开显示裁档理由、档内位置和一句限制。代表父链按任务—人选、岗位—权限、交付—反馈、后续响应分组，完整字段与来源集合保留在正式JSON。"
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
    if axis == "M2":
        lines.extend([
            "- M2中标为‘待补证’或‘待重算’的人物只保留整改前历史显示点；阅读视图不把旧值当作当前实裁或当前雷达值。",
            "- 轴外父链仍保留完整来源与去向，`AXIS_OUT_WITH_REASON`/`BACKGROUND_VALIDATION`不参与M2档位。",
            "",
        ])
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
    cross_axis_note = [
        "## 跨轴计分边界",
        "",
        "- 同一史料或事件出现在多个轴，不等于同一能力被重复计分；正式计分以各轴独立构念、父链命题和归责边界为准。",
        "- 同源材料须分别说明各轴的独立命题与归责边界；当前正式父链保留依据，不依赖历史过程审计。",
    ]
    axis_boundary_note = {
        "M1": "- M1只消费战役、战区、统帅与作战操作；战略目标、风险选择和退出留在C1，外交条件交换留在M2。",
        "M2": "- M2只消费外部对象的条件、承诺、反馈和执行；战略目标与风险取舍留在C1，内部集团整合留在M4。",
        "C1": "- C1只消费战略目标、优先级、风险、资源与退出；具体战役解题留在M1，外部条件交换留在M2。",
        "C2": "- C2只消费信息取得、反证理解与认知更新；战略选择、外交条件和权力程序不因共享史料转入C2。",
        "C3": "- C3只消费人才识别、配置、授权与交付反馈；集团生命周期和外交对象关系分别留在M4/M2。",
        "C5": "- C5只消费权力边界、异议安全、惩罚程序与比例；军事、外交和人才成果不因共享史料转入C5。",
        "M3": "- M3只消费财政民生与治理结果及其过程；上游轴事实只作已声明输入，不把上游档位重复换算。",
        "M4": "- M4只消费内部政治集团、藩镇、继承与权力整合；外部外交、军事操作和个人用人不因共享史料重复计入。",
    }.get(axis)
    if axis_boundary_note:
        cross_axis_note.insert(2, axis_boundary_note)
    lines.extend(cross_axis_note)
    lines.extend(["", "## 全池结算表", ""])
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
        settlement_line = (
            f"- **结算**：`{_m2_display_grade(row)}` / 当前雷达值 `{_m2_display_radar(row)}` / "
            f"{row['axis_evidence_level']} / {row['score_status']} / {_m2_adjudication_label(row)}。"
            if axis == "M2"
            else f"- **结算**：`{_grade(row)}` / 雷达值 `{row['radar_value']}` / `{row['axis_evidence_level']}` / "
            f"`{'证据有限' if axis == 'C2' and row['score_status'] == 'EVIDENCE_LIMITED' else row['score_status']}`。"
        )
        lines.extend([
            f"### {display}. {row['ruler_name']}（{row['ruler_id']}）",
            "",
            settlement_line,
            f"- **{'核心依据' if axis == 'C2' else '主模式'}**：{row.get('grade_basis') if axis == 'C2' else row['typical_pattern']}",
            *([] if axis == "C2" else [f"- **裁档理由**：{_c3_grade_reason(row) if axis == 'C3' else (row.get('grade_basis') or '见结构化父链与正式裁决源。')}" ]),
            f"- **{'档内定位' if axis == 'C2' else '档内位置'}**：{_c3_position_reason(row) if axis == 'C3' else (row.get('position_basis') or '由同档材料强度与反例共同确定。')}",
            f"- **限制**：{_c3_limitation(row) if axis == 'C3' else _limitations(row, labels)}",
        ])
        if axis == "C5":
            lines.extend(_c5_political_review_lines(row))
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
            projection_reasons = list(
                dict.fromkeys(
                    str(context.get("secondary_projection_reason") or "").strip()
                    for context in row.get("representative_parent_contexts") or []
                    if str(context.get("secondary_projection_reason") or "").strip()
                )
            )
            if projection_reasons:
                lines.append("- **跨轴投影边界**：")
                lines.extend(f"  - {reason}" for reason in projection_reasons)
        parents = _parent_chains(row)
        if axis in {"C1", "C2"}:
            parents = _representative_parent_chains(row)
        if parents:
            lines.append("- **代表父链**：")
            for parent in parents:
                if axis == "C3":
                    lines.extend(_c3_parent_lines(parent))
                elif axis == "C2":
                    lines.extend(
                        _parent_lines(
                            parent,
                            compact_sources=True,
                            include_cycle_anchors=True,
                            source_limit=C2_DISPLAY_REF_LIMIT,
                        )
                    )
                else:
                    lines.extend(
                        _parent_lines(
                            parent,
                            compact_sources=axis == "C1",
                            show_routing=axis == "M2",
                            strip_source_locators=axis == "M2",
                        )
                    )
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
