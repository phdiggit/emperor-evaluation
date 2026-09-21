from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)


A_PATH = Path(
    "docs/评分结算/净收益/第二项治国净收益/制度行政/"
    "01-A制度建设与实际运行方向卡.json"
)
CONTRACT_PATH = Path("docs/分项规则/第二项治国净收益/制度行政/00-规则与计分合同.md")
MATERIAL_ROOT = Path("docs/公共成果/制度行政/01-制度行政计分材料登记")
NODE_REGISTRY_PATH = Path("docs/公共成果/制度行政/03-重要制度发展节点链.json")

PUBLIC_PROJECTION_SCHEMA = "second-item-a-public-projection-v1"
PUBLIC_NODE_FIELDS = (
    "institution_node_id",
    "public_label",
    "public_direction",
    "public_tags",
    "signed_weight",
    "public_adjudication_basis",
    "public_scope",
    "public_boundary",
    "public_reception",
)
A_PUBLIC_BOUNDARY = (
    "制度建设公开层只展示当前正式结构中已经闭合为独立制度节点的材料；"
    "没有可单列节点时，只表示当前正式记录未形成可单独展示的制度节点，"
    "不据此推断其他制度行为的存在与否或效果。"
)
PROFILE_KEYS = ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
MATERIAL_KEYS = (
    "construction_operation_material_ids",
    "material_ids",
    "durability_material_ids",
    "material_id",
)

PUBLIC_DIRECTIONS = {
    "positive": "正向",
    "positive_correction": "正向",
    "negative": "负向",
    "mixed_positive": "正向主导",
    "mixed_negative": "负向主导",
    "mixed": "正负并存",
    "balanced": "正负并存",
    "neutral": "正负并存",
}
PUBLIC_GRADE = {"G0": "E", "G1": "D", "G2": "C", "G3": "B", "G4": "A", "G5": "S"}
PUBLIC_POSITION_LABEL = {
    "lower": "下位",
    "lower-middle": "中下位",
    "middle": "中位",
    "middle-upper": "中上位",
    "upper": "上位",
}

ROLE_LABELS = {
    "FOUNDATIONAL_CREATION": "创设",
    "MAJOR_RESTRUCTURE": "重构",
    "MAJOR_RECONSTRUCTION": "重建",
    "CANONICALIZATION": "定型",
    "MAJOR_CODIFICATION": "定型",
    "MAJOR_CIVILIZATIONAL_CORRECTION": "重大纠偏",
    "MAJOR_NEGATIVE_RESTRUCTURE": "负向重构",
    "MAJOR_NEGATIVE_CREATION": "负向创设",
    "SEVERE_CIVILIZATIONAL_REVERSAL": "严重倒退",
    "STRUCTURAL_NON_DURABLE": "核心结构",
    "DURABILITY_EVIDENCE_PENDING": "核心结构",
    "LOCAL_OR_SECONDARY_CONSTRUCTION": "局部建设",
    "PAPER_OR_INCOMPLETE_CONSTRUCTION": "未完成尝试",
    "TRANSITIONAL_RESTORATION": "过渡恢复",
    "MAINTENANCE_REVISION": "维护调整",
}
MAJOR_ROLES = {
    "FOUNDATIONAL_CREATION",
    "MAJOR_RESTRUCTURE",
    "MAJOR_RECONSTRUCTION",
    "CANONICALIZATION",
    "MAJOR_CODIFICATION",
    "MAJOR_CIVILIZATIONAL_CORRECTION",
    "MAJOR_NEGATIVE_RESTRUCTURE",
    "MAJOR_NEGATIVE_CREATION",
    "SEVERE_CIVILIZATIONAL_REVERSAL",
    "STRUCTURAL_NON_DURABLE",
    "DURABILITY_EVIDENCE_PENDING",
}
GENERIC_LABELS = {
    "A",
    "其他制度行政机制",
    "法律与司法",
    "选官与官僚人事",
    "地方行政与政策交付",
    "国家教育与官学",
    "中央组织",
}

PUBLIC_FORBIDDEN_RE = re.compile(
    r"(?:"
    r"(?<![A-Za-z])M[0-3](?![A-Za-z0-9])|"
    r"(?<![A-Za-z])R[0-4](?![A-Za-z0-9])|"
    r"S(?:\+\+|\+|−|-)\s*\d*|NON_S|"
    r"\bcanonical\b|\blifecycle\b|\bposition\b|"
    r"生命周期|门禁|主档|消费|净余|计权|"
    r"按正式显式复核|按跨朝同领域谱系横向复裁|按A审查清单|"
    r"本轮|重审|恢复原|"
    r"MAJOR_[A-Z_]+|"
    r"(?<![A-Za-z])(?:positive|negative|mixed|balanced|neutral|"
    r"mixed_positive|mixed_negative|observed_or_repeated|"
    r"sustained_or_systemic|reception_only|institution_lifecycle_adjudicated)"
    r"(?![A-Za-z])"
    r")",
    flags=re.IGNORECASE,
)


def _number(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool) or value is None or value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _json_number(value: float) -> int | float:
    rounded = round(float(value), 6)
    return int(rounded) if rounded.is_integer() else rounded


def _format_number(value: object, *, signed: bool = False) -> str:
    number = _number(value)
    if number.is_integer():
        text = f"{number:.0f}"
    else:
        text = f"{number:.1f}".rstrip("0").rstrip(".")
    if signed and number > 0:
        return f"+{text}"
    return text


def _clean_public_text(value: object) -> str:
    """Turn formal shorthand into final reader prose before it reaches the source."""

    text = str(value or "").replace("`", "").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\{\{.*?\}\}", "", text)
    text = re.sub(r"\s*原文定位[：:].*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = (
        (r"按正式显式复核", "根据现有材料"),
        (r"按跨朝同领域谱系横向复裁", "根据制度沿革材料"),
        (r"按A审查清单", "根据制度材料"),
        (r"只作A的(?:S\+\+|S\+|S−|S-)?耐久长期接收条件[^；。]*", "只作长期接收条件说明，不增加本节点权重"),
        (r"经A结算审查(?:确认|解冻)?", "经正式材料确认"),
        (r"A结算审查", "正式材料审查"),
        (r"不进行A负向/正向裁决", "不在本节点中判断正负方向"),
        (r"只支持G[0-5](?:与\s*=?\s*[+-]?\d+(?:\.\d+)?)?", "仅支持有限建设"),
        (r"D1/D3", "交接评价"),
        (r"D1", "交接评价"),
        (r"不重复计本人建设M或财政民生结果", "不重复计算本人建设或财政民生结果"),
        (r"不重复消费|只消费一次|消费一次", "只计算一次"),
        (r"消费", "计算"),
        (r"跨分项[^。；]*", "其他项目的相关事实只作交叉核对，不重复计算"),
        (r"移出A计权|不折入A|移出A", "不计入制度建设"),
        (r"进入A", "计入制度建设"),
        (r"A计权", "制度建设计分"),
        (r"A档内", "制度等级中"),
        (r"A负链", "负向制度链"),
        (r"A只计", "本节点只计"),
        (r"不进入D1", "不归入交接评价"),
        (r"B1/B2复验|B1、B2复验", "其他治理评价作交叉核对"),
        (r"B1/B2", "其他治理评价"),
        (r"B1|B2", "其他治理评价"),
        (r"按现合同抵扣", "按同一机制合并判断"),
        (r"A项", "本项"),
        (r"净余量", "净值"),
        (r"主档", "主要等级结论"),
        (r"门禁", "长期接收条件"),
        (r"计权", "计入"),
        (r"追加S", "增加长期接收权重"),
        (r"抬或S", "提高等级或长期接收权重"),
        (r"S净值", "长期接收净值"),
        (r"S级", "最高级"),
        (r"加S", "增加长期接收权重"),
        (r"计S", "计入长期接收权重"),
        (r"只作A的S耐久长期接收条件[^；。]*", "只作长期接收条件说明，不增加本节点权重"),
        (r"不进入人物直接M", "不进入人物直接贡献"),
        (r"不计正向S", "不增加正向长期接收权重"),
        (r"正向S", "正向长期接收权重"),
        (r"S耐久", "长期接收"),
        (r"合计([+-])?(\d+(?:\.\d+)?)", r"净值为\1\2"),
        (r"改判|改裁", "最终判断"),
        (r"前态", "此前状态"),
        (r"倒算", "归入"),
        (r"接收材料", "后世沿用证据"),
        (r"正功", "正向贡献"),
        (r"负功", "负向贡献"),
        (r"净判", "判断"),
        (r"生命周期", "设立、运行与后续变化"),
        (r"谱系", "制度沿革"),
        (r"归责", "责任归属"),
        (r"闭合", "证明链条成立"),
        (r"本轮", ""),
        (r"重审", "重新判断"),
        (r"恢复原", "恢复既有"),
        (r"canonical", "定型"),
        (r"MAJOR_NEGATIVE_RESTRUCTURE", "负向重构"),
        (r"MAJOR_NEGATIVE_CREATION", "负向创设"),
        (r"MAJOR_RECONSTRUCTION", "重建"),
        (r"MAJOR_RESTRUCTURE", "重构"),
        (r"FOUNDATIONAL_CREATION", "创设"),
        (r"CANONICALIZATION|MAJOR_CODIFICATION", "定型"),
        (r"MAJOR_CIVILIZATIONAL_CORRECTION", "重大纠偏"),
        (r"STRUCTURAL_NON_DURABLE|DURABILITY_EVIDENCE_PENDING", "核心结构"),
        (r"S\+\+", "跨朝代长期沿用"),
        (r"S\+", "多个后继统治阶段持续采用"),
        (r"S[−-]\s*\d*", "长期负向影响"),
        (r"非S|不计S|S节点", "未计入长期接收加权"),
        (r"R4", "跨朝代长期沿用"),
        (r"R3", "多个后继统治阶段持续采用"),
        (r"R[12]", "后世接收范围有限"),
        (r"R0", "本人任内已有实际运行"),
        (r"NON_S", "未计入长期接收加权"),
        (r"mixed_positive", "正向主导"),
        (r"mixed_negative", "负向主导"),
        (r"positive", "正向"),
        (r"negative", "负向"),
        (r"balanced|mixed|neutral", "正负并存"),
        (r"observed_or_repeated|observed", "已有实际运行"),
        (r"sustained_or_systemic", "持续或系统运行"),
        (r"reception_only", "仅作后世接收说明"),
        (r"institution_lifecycle_adjudicated", "设立、运行与后续变化已有材料支持"),
        (r"(?<![A-Za-z])M[0-3](?![A-Za-z0-9])", ""),
        (r"(?<![A-Za-z])S(?![A-Za-z])", "长期接收权重"),
        (r"(?<![A-Za-z])M(?![A-Za-z])", "该项权重"),
        (r"(?<![A-Za-z])position(?![A-Za-z])", "档内位置"),
        (r"(?<![A-Za-z])C_A(?![A-Za-z])", ""),
        (r"\|", "；"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"[；，]\s*[；，]+", "；", text)
    text = text.replace("。；", "；")
    text = text.replace(
        "只作A的跨朝代长期沿用长期接收条件",
        "只作长期接收条件说明，不增加本节点权重",
    )
    text = text.replace(
        "只作A的多个后继统治阶段持续采用长期接收条件",
        "只作长期接收条件说明，不增加本节点权重",
    )
    text = text.replace(
        "正负向与混合设立、运行与后续变化按同一机制合并判断",
        "正负作用在同一机制中合并判断",
    )
    text = text.replace("后继多个后继", "多个后继")
    text = text.replace("保留未计入长期接收加权", "保留")
    text = re.sub(r"。\s*。+", "。", text)
    text = re.sub(r"；\s*。", "。", text)
    text = re.sub(r"^[\s；，:：\-]+|[\s；，。]+$", "", text)
    return text.strip()


def _compact(value: object, limit: int = 420) -> str:
    text = _clean_public_text(value)
    if len(text) <= limit:
        return text
    pieces = [piece.strip() for piece in re.split(r"(?<=[。！？；])", text) if piece.strip()]
    selected = ""
    for piece in pieces:
        candidate = f"{selected}{piece}"
        if len(candidate) > limit:
            break
        selected = candidate
    if not selected:
        selected = text[: max(1, limit - 1)]
    return selected.rstrip("，；、") + "…"


def _unique_texts(values: list[object], *, limit: int = 3, item_limit: int = 420) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _compact(value, item_limit)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _linked_material_ids(node: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in MATERIAL_KEYS:
        raw = node.get(key)
        if isinstance(raw, list):
            candidates = raw
        elif raw:
            candidates = [raw]
        else:
            candidates = []
        for value in candidates:
            text = str(value).strip()
            if text and text not in values:
                values.append(text)
    return values


def _load_materials(workspace_root: Path) -> dict[str, dict[str, Any]]:
    materials: dict[str, dict[str, Any]] = {}
    for path in sorted((workspace_root / MATERIAL_ROOT).glob("*.json")):
        payload = load_json(path)
        for material in payload.get("records") or []:
            material_id = str(material.get("material_id") or "").strip()
            if not material_id:
                continue
            if material_id in materials:
                raise ValueError(f"第二项A公共材料ID重复：{material_id}")
            materials[material_id] = material
    return materials


def _generated_node_id(row: dict[str, Any], source: str, index: int, node: dict[str, Any]) -> str:
    labels = str(node.get("label_zh") or node.get("mechanism") or "").strip()
    material_ids = ",".join(sorted(_linked_material_ids(node)))
    raw = "|".join(
        (
            str(row.get("ruler_id") or ""),
            source,
            material_ids,
            str(node.get("direction") or node.get("normative_direction") or ""),
            labels,
            str(index),
        )
    )
    return "A-PUBLIC-NODE-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def _ensure_profile_ids(row: dict[str, Any]) -> int:
    created = 0
    for key in PROFILE_KEYS:
        for index, profile in enumerate(row.get(key) or []):
            if not isinstance(profile, dict):
                continue
            if str(profile.get("institution_node_id") or "").strip():
                continue
            profile["institution_node_id"] = _generated_node_id(row, key, index, profile)
            created += 1
    return created


def _node_groups(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    def add(source: str, index: int, node: dict[str, Any]) -> None:
        node_id = str(node.get("institution_node_id") or "").strip()
        if not node_id:
            raise ValueError(f"第二项A公开节点缺少稳定ID：{row.get('ruler_name')} / {source}[{index}]")
        group = groups.setdefault(node_id, {"important": [], "profiles": []})
        target = "important" if source == "important_institutions" else "profiles"
        group[target].append(node)

    for key in PROFILE_KEYS:
        for index, node in enumerate(row.get(key) or []):
            if isinstance(node, dict):
                add(key, index, node)
    for index, node in enumerate(row.get("important_institutions") or []):
        if isinstance(node, dict):
            add("important_institutions", index, node)
    return groups


def _merge_group(group: dict[str, Any]) -> dict[str, Any]:
    important = group["important"][0] if group["important"] else None
    profile = group["profiles"][0] if group["profiles"] else None
    merged = dict(important or profile or {})
    if profile and important:
        # The profile is the formal contribution authority for direction and weight;
        # the important-node record remains authoritative for public identity and role.
        for key, value in profile.items():
            if value is not None and (key not in important or not important.get(key)):
                merged[key] = value
        for key in (
            "M",
            "direction",
            "direction_factor",
            "signed_weight",
            "base_signed",
            "durability_bonus",
            "S_effect",
            "counts_toward_S",
            "result_closure",
        ):
            if profile.get(key) is not None:
                merged[key] = profile[key]
    elif profile:
        merged.update(profile)

    for key in (
        "material_ids",
        "construction_operation_material_ids",
        "durability_material_ids",
    ):
        combined: list[str] = []
        for node in (important, profile):
            if not node:
                continue
            raw = node.get(key) or []
            values = raw if isinstance(raw, list) else [raw]
            for value in values:
                text = str(value).strip()
                if text and text not in combined:
                    combined.append(text)
        if combined:
            merged[key] = combined
    if important and important.get("material_id") and not merged.get("material_id"):
        merged["material_id"] = important["material_id"]
    merged["__important"] = important
    merged["__profile"] = profile
    merged["__raw_nodes"] = [node for node in (important, profile) if node]
    return merged


def _scope_material_ids(node: dict[str, Any], materials: dict[str, dict[str, Any]]) -> list[str]:
    explicit = node.get("construction_operation_material_ids") or []
    if not isinstance(explicit, list):
        explicit = [explicit]
    ids = [str(value).strip() for value in explicit if str(value).strip()]
    if ids:
        return list(dict.fromkeys(ids))
    result: list[str] = []
    for material_id in _linked_material_ids(node):
        material = materials.get(material_id)
        if material and str(material.get("result_closure") or "").lower() == "reception_only":
            continue
        result.append(material_id)
    return result


def _material_values(
    node: dict[str, Any],
    materials: dict[str, dict[str, Any]],
    fields: tuple[str, ...],
    *,
    material_ids: list[str] | None = None,
) -> list[str]:
    values: list[str] = []
    for material_id in material_ids or _linked_material_ids(node):
        material = materials.get(material_id)
        if not material:
            continue
        for field in fields:
            text = _compact(material.get(field))
            if text and text not in values:
                values.append(text)
    return values


def _specific_reason(row: dict[str, Any], node: dict[str, Any]) -> str:
    raw_nodes = [node.get("__important"), node.get("__profile")]
    candidates: list[str] = []
    row_level = {
        str(row.get("grade_basis") or "").strip(),
        str(row.get("position_basis") or "").strip(),
    }
    all_reasons: Counter[str] = Counter()
    for key in PROFILE_KEYS + ("important_institutions",):
        for item in row.get(key) or []:
            if not isinstance(item, dict):
                continue
            for field in ("reason", "direction_reason"):
                value = str(item.get(field) or "").strip()
                if value:
                    all_reasons[value] += 1
    for raw in raw_nodes:
        if not raw:
            continue
        for field in ("reason", "direction_reason"):
            value = str(raw.get(field) or "").strip()
            if not value or value in row_level or all_reasons[value] > 1:
                continue
            if any(
                marker in value
                for marker in (
                    "只保留改变核心规则",
                    "按跨朝同领域",
                    "按正式显式复核",
                    "按A审查清单",
                    "正向0",
                    "正向1",
                    "正向2",
                    "正向3",
                    "负向0",
                    "负向1",
                    "负向2",
                    "负向3",
                    "制度净值",
                    "结算G",
                    "根据制度材料完成单一制度接口裁决",
                )
            ):
                continue
            candidates.append(value)
    return _compact(candidates[0] if candidates else "", 360)


def _public_label(node: dict[str, Any], materials: dict[str, dict[str, Any]]) -> str:
    candidate = _compact(node.get("label_zh") or node.get("mechanism"), 120)
    scope_ids = _scope_material_ids(node, materials)
    material_candidates = _material_values(node, materials, ("measure", "title", "operation"), material_ids=scope_ids)
    if (
        not candidate
        or candidate in GENERIC_LABELS
        or "证据闭合" in candidate
        or (len(candidate) > 48 and any(marker in candidate for marker in ("缺少", "不能", "未", "不")))
    ):
        candidate = material_candidates[0] if material_candidates else candidate
    if not candidate:
        domain = _compact(node.get("institution_domain"), 60)
        candidate = f"{domain or '制度'}调整"
    candidate = candidate.split("；", 1)[0].split("。", 1)[0].strip()
    return _compact(candidate, 80) or "制度调整"


def _public_scope(node: dict[str, Any], materials: dict[str, dict[str, Any]], label: str) -> str:
    scope_ids = _scope_material_ids(node, materials)
    values = _material_values(node, materials, ("measure", "operation"), material_ids=scope_ids)
    if not values:
        values = _material_values(node, materials, ("title", "result"), material_ids=scope_ids)
    if not values:
        values = [label]
    return _compact("；".join(values), 620)


def _public_result(node: dict[str, Any], materials: dict[str, dict[str, Any]], scope: str) -> str:
    values = _material_values(
        node,
        materials,
        ("result", "continuity"),
        material_ids=_scope_material_ids(node, materials),
    )
    for value in values:
        if value and value != scope and value not in scope:
            return _compact(value, 260)
    return ""


def _public_status(node: dict[str, Any]) -> str:
    closure = str(node.get("result_closure") or "").lower()
    if "revers" in closure:
        return "后续发生逆转"
    if "sustain" in closure or "system" in closure:
        return "形成持续或系统运行"
    if "observ" in closure:
        return "已观察到实际运行"
    if "limited" in closure:
        return "目前只有有限观察"
    if closure:
        return "设立、运行与后续变化已有材料支持"
    return "已被正式记录"


def _public_boundary(
    row: dict[str, Any],
    node: dict[str, Any],
    materials: dict[str, dict[str, Any]],
) -> str:
    values = _material_values(node, materials, ("cost_or_capture",))
    reason = _specific_reason(row, node)
    if reason:
        clauses = [
            clause.strip()
            for clause in re.split(r"(?<=[。！？；])", reason)
            if clause.strip()
            and any(marker in clause for marker in ("不能", "不足", "未", "不", "仅", "只", "另", "不再"))
        ]
        values.extend(clause for clause in clauses[:2] if clause not in values)
    default = "未列入上述范围的其他制度行为、运行结果和后继成果不归入本节点。"
    if default not in values:
        values.append(default)
    return _compact("；".join(values), 620)


def _reception(node: dict[str, Any], materials: dict[str, dict[str, Any]]) -> tuple[str, str]:
    effect = str(node.get("S_effect") or "").upper().replace("−", "-")
    gate = str(node.get("durability_gate") or "").upper()
    scopes = {
        str(materials[mid].get("reception_scope") or "").upper()
        for mid in _linked_material_ids(node)
        if mid in materials
    }
    counts = node.get("counts_toward_S") is True
    if effect == "S++" or "PLUSPLUS" in gate or "R4" in gate or "R4" in scopes:
        if counts:
            return "cross", "跨朝代长期沿用。"
        return "cross", "跨朝代长期沿用，但本节点未计入长期接收加权。"
    if effect == "S+" or "PASS_COUNTS_TOWARD_S" in gate or "PASS_R3" in gate or "R3" in scopes:
        if counts:
            return "multi", "多个后继统治阶段持续采用。"
        return "multi", "多个后继统治阶段持续采用，但本节点未计入长期接收加权。"
    if effect.startswith("S-") or "NEGATIVE_R3" in gate or "NEGATIVE_R4" in gate:
        return "negative", "负向机制长期延续，形成耐久扣减。"
    if "PENDING" in gate or "FAIL_R" in gate:
        return "pending", "现有证据不足以证明长期持续沿用，因此未计入长期接收加权。"
    if node.get("__important") and not counts:
        return "not_counted", "未计入长期接收加权。"
    if "R2" in scopes or "R1" in scopes:
        return "limited", "已有阶段性后世接收证据，但未计入长期接收加权。"
    if "R0" in scopes:
        return "actual", "已有任内实际运行证据，未计入长期接收加权。"
    closure = str(node.get("result_closure") or "").lower()
    if "reverse" in closure or "reversed" in closure:
        return "limited", "后续发生逆转，未形成长期持续沿用。"
    if "limited" in closure:
        return "limited", "现有证据仅支持有限观察，未证明长期持续沿用。"
    if closure:
        return "actual", "已有实际运行证据，未计入长期接收加权。"
    return "not_counted", "现有记录未形成长期接收加权。"


def _public_direction(node: dict[str, Any]) -> str:
    raw = str(node.get("direction") or node.get("normative_direction") or "").strip()
    if raw in PUBLIC_DIRECTIONS:
        return PUBLIC_DIRECTIONS[raw]
    weight = _number(node.get("signed_weight"))
    if weight > 0:
        return "正向"
    if weight < 0:
        return "负向"
    return "正负并存"


def _is_major(node: dict[str, Any]) -> bool:
    role = str(node.get("major_node_role") or "")
    return role in MAJOR_ROLES or (
        node.get("decision") == "MAJOR_NODE" and role not in {"PAPER_OR_INCOMPLETE_CONSTRUCTION", "MAINTENANCE_REVISION"}
    )


def _public_tags(node: dict[str, Any], public_direction: str) -> list[str]:
    tags: list[str] = []
    if _is_major(node):
        tags.append("重大制度")
    role = ROLE_LABELS.get(str(node.get("major_node_role") or ""))
    if role:
        tags.append(role)
    if not role:
        tags.append(
            {
                "正向": "正向建设",
                "正向主导": "正向主导",
                "负向": "负向制度作用",
                "负向主导": "负向主导",
                "正负并存": "正负并存",
            }.get(public_direction, "制度作用")
        )
    closure = str(node.get("result_closure") or "").lower()
    closure_tag = None
    if "revers" in closure:
        closure_tag = "后续逆转"
    elif "sustain" in closure or "system" in closure:
        closure_tag = "持续运行"
    elif "observ" in closure:
        closure_tag = "已有实际运行"
    elif "limited" in closure:
        closure_tag = "有限观察"
    if closure_tag:
        tags.append(closure_tag)
    return list(dict.fromkeys(tags or ["制度作用"]))


def _signed_weight(node: dict[str, Any]) -> float:
    value = node.get("signed_weight")
    if value is not None:
        return _number(value)
    direction = str(node.get("direction") or node.get("normative_direction") or "")
    if direction in {"negative", "mixed_negative"}:
        return -abs(_number(node.get("S_minus_weight")))
    return abs(_number(node.get("S_depth_weight")))


def _public_nodes(row: dict[str, Any], materials: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter[str]]:
    nodes: list[dict[str, Any]] = []
    reception_counts: Counter[str] = Counter()
    for node_id, group in _node_groups(row).items():
        merged = _merge_group(group)
        label = _public_label(merged, materials)
        direction = _public_direction(merged)
        scope = _public_scope(merged, materials, label)
        result = _public_result(merged, materials, scope)
        reason = _specific_reason(row, merged)
        if not reason:
            role = ROLE_LABELS.get(str(merged.get("major_node_role") or ""))
            reason = f"该节点被判断为{role or direction + '制度作用'}，{_public_status(merged)}。"
        basis_parts = [
            reason,
            f"具体范围是{scope}",
        ]
        if result:
            basis_parts.append(f"运行结果是{result}")
        reception_bucket, reception_text = _reception(merged, materials)
        reception_counts[reception_bucket] += 1
        nodes.append(
            {
                "institution_node_id": node_id,
                "public_label": label,
                "public_direction": direction,
                "public_tags": _public_tags(merged, direction),
                "signed_weight": _json_number(_signed_weight(merged)),
                "public_adjudication_basis": _compact(
                    "；".join(value for value in basis_parts if value), 720
                ),
                "public_scope": scope,
                "public_boundary": _public_boundary(row, merged, materials),
                "public_reception": reception_text,
            }
        )
    return nodes, reception_counts


def _public_reception_overview(counts: Counter[str], node_count: int) -> str:
    if not node_count:
        return "当前正式记录没有可单列的制度节点，未形成后世接收加权"
    parts: list[str] = []
    labels = (
        ("cross", "跨朝代长期沿用"),
        ("multi", "多个后继统治阶段持续采用"),
        ("negative", "负向机制长期延续形成耐久扣减"),
        ("pending", "现有证据不足以证明长期持续沿用"),
        ("limited", "有阶段性接收或有限延续"),
        ("actual", "已有任内或阶段性实际运行"),
        ("not_counted", "未计入长期接收加权"),
    )
    for key, label in labels:
        count = counts.get(key, 0)
        if count:
            parts.append(f"{label}{count}项")
    return "；".join(parts) or "现有记录未形成长期接收加权。"


def _public_grade(row: dict[str, Any]) -> str:
    base = PUBLIC_GRADE.get(str(row.get("grade") or ""), "")
    position = PUBLIC_POSITION_LABEL.get(str(row.get("position") or ""), "")
    return f"{base}级（{position}）" if base and position else base


def _profile_weights(row: dict[str, Any]) -> list[float]:
    return [
        _number(profile.get("signed_weight"))
        for key in PROFILE_KEYS
        for profile in row.get(key) or []
        if isinstance(profile, dict)
    ]


def _totals(row: dict[str, Any], public_nodes: list[dict[str, Any]]) -> tuple[float, float, float, bool]:
    present = all(row.get(key) is not None for key in ("P_gross", "N_gross", "A_net_units"))
    if present:
        positive = _number(row["P_gross"])
        negative = _number(row["N_gross"])
        net = _number(row["A_net_units"])
        return positive, negative, net, True
    weights = [_number(node.get("signed_weight")) for node in public_nodes]
    if not weights:
        weights = _profile_weights(row)
    positive = sum(value for value in weights if value > 0)
    negative = sum(-value for value in weights if value < 0)
    return positive, negative, positive - negative, False


def _summary(
    row: dict[str, Any],
    positive: float,
    negative: float,
    net: float,
    reception_counts: Counter[str],
    node_count: int,
) -> str:
    grade = _public_grade(row) or "未定"
    overview = _public_reception_overview(reception_counts, node_count)
    return (
        f"正式制度建设公开结论：正向影响权重为{_format_number(positive)}，"
        f"负向影响权重为{_format_number(negative)}，制度净值为{_format_number(net, signed=True)}；"
        f"后世接收概况：{overview}；公开等级为{grade}。"
    )


def _public_evidence_basis(node: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("public_adjudication_basis", "public_scope", "public_reception"):
        value = str(node.get(key) or "").strip()
        if not value:
            continue
        existing = "\n\n".join(parts)
        if existing and value in existing:
            continue
        parts.append(value)
    return "\n\n".join(parts)


def _public_evidence_items(row: dict[str, Any], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not nodes:
        return [{
            "public_label": "当前没有可单列制度节点",
            "public_tags": ["未形成独立制度节点"],
            "public_basis": "当前正式记录没有可单列的制度节点，因此本项没有逐节点材料卡。",
            "public_boundary": A_PUBLIC_BOUNDARY,
        }]
    return [
        {
            "public_label": str(node["public_label"]),
            "public_direction": str(node["public_direction"]),
            "public_tags": list(node["public_tags"]),
            "public_basis": _public_evidence_basis(node),
            "public_boundary": str(node["public_boundary"]),
        }
        for node in nodes
    ]


def _scoring_signature(payload: dict[str, Any]) -> str:
    snapshot = copy.deepcopy(payload.get("records") or [])
    for row in snapshot:
        for key in (
            "public_institution_nodes",
            "public_adjudication_summary",
            "public_boundary",
            "public_evidence_items",
            "P_gross",
            "N_gross",
            "A_net_units",
            "polarization_ratio",
        ):
            row.pop(key, None)
        for key in PROFILE_KEYS:
            for profile in row.get(key) or []:
                if isinstance(profile, dict):
                    profile.pop("institution_node_id", None)
    return json.dumps(
        sorted(snapshot, key=lambda item: str(item.get("ruler_id"))),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _refresh_payload(payload: dict[str, Any], workspace_root: Path) -> dict[str, Any]:
    before_signature = _scoring_signature(payload)
    previous_derived_total_count = payload.get("public_projection_derived_total_count")
    previous_generated_node_id_count = payload.get("public_projection_generated_node_id_count")
    legacy_derived_total_count = sum(
        1 for row in payload.get("records") or [] if row.get("v2_explicit_patch") is not True
    )
    existing_totals = {
        str(row.get("ruler_id")): tuple(row.get(key) for key in ("P_gross", "N_gross", "A_net_units"))
        for row in payload.get("records") or []
    }
    materials = _load_materials(workspace_root)
    generated_ids = 0
    derived_totals = 0
    public_node_count = 0
    for row in payload.get("records") or []:
        generated_ids += _ensure_profile_ids(row)
        nodes, reception_counts = _public_nodes(row, materials)
        positive, negative, net, had_totals = _totals(row, nodes)
        if had_totals:
            if abs(net - (positive - negative)) > 1e-9:
                raise ValueError(f"第二项A正式正负总量与净值不一致：{row.get('ruler_name')}")
        else:
            row["P_gross"] = _json_number(positive)
            row["N_gross"] = _json_number(negative)
            row["A_net_units"] = _json_number(net)
            derived_totals += 1
        row["public_institution_nodes"] = nodes
        row["public_adjudication_summary"] = _summary(
            row,
            positive,
            negative,
            net,
            reception_counts,
            len(nodes),
        )
        row["public_boundary"] = A_PUBLIC_BOUNDARY
        row["public_evidence_items"] = _public_evidence_items(row, nodes)
        public_node_count += len(nodes)

    for row in payload.get("records") or []:
        ruler_id = str(row.get("ruler_id"))
        before = existing_totals[ruler_id]
        after = tuple(row.get(key) for key in ("P_gross", "N_gross", "A_net_units"))
        if all(value is not None for value in before) and before != after:
            raise ValueError(f"第二项A公开字段迁移改变了既有正负总量：{row.get('ruler_name')}")
    if _scoring_signature(payload) != before_signature:
        raise ValueError("第二项A公开字段迁移意外改变了正式评分字段")

    payload["public_projection_schema_version"] = PUBLIC_PROJECTION_SCHEMA
    payload["public_projection_status"] = "FORMAL_UPSTREAM_SOURCE"
    payload["public_projection_record_count"] = len(payload.get("records") or [])
    payload["public_projection_node_count"] = public_node_count
    persisted_generated_node_id_count = sum(
        1
        for row in payload.get("records") or []
        for key in PROFILE_KEYS
        for profile in row.get(key) or []
        if str(profile.get("institution_node_id") or "").startswith("A-PUBLIC-NODE-")
    )
    payload["public_projection_generated_node_id_count"] = max(
        value
        for value in (
            previous_generated_node_id_count
            if isinstance(previous_generated_node_id_count, int)
            else 0,
            generated_ids,
            persisted_generated_node_id_count,
        )
    )
    payload["public_projection_derived_total_count"] = (
        max(
            value
            for value in (
                previous_derived_total_count if isinstance(previous_derived_total_count, int) else 0,
                derived_totals,
                legacy_derived_total_count,
            )
        )
    )
    payload["public_projection_source"] = {
        "formal_contract": CONTRACT_PATH.as_posix(),
        "material_registry": MATERIAL_ROOT.as_posix(),
        "institution_registry": NODE_REGISTRY_PATH.as_posix(),
        "node_identity": "现有institution_node_id；缺失profile按人物、材料、方向和位置生成后固化",
    }
    contract_path = workspace_root / CONTRACT_PATH
    if contract_path.is_file():
        contract_hash = hashlib.sha256(contract_path.read_bytes()).hexdigest()
        for source in payload.get("source_documents") or []:
            if source.get("path") == CONTRACT_PATH.as_posix():
                source["byte_sha256"] = contract_hash
    return payload


def refresh_public_projection(workspace_root: Path) -> dict[str, Any]:
    payload = load_json(workspace_root / A_PATH)
    return _refresh_payload(payload, workspace_root)


def verify_public_projection(
    workspace_root: Path,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if payload is None:
        payload = load_json(workspace_root / A_PATH)
    if payload.get("public_projection_schema_version") != PUBLIC_PROJECTION_SCHEMA:
        raise ValueError("第二项A缺少正式公开投影schema标记")
    if payload.get("public_projection_status") != "FORMAL_UPSTREAM_SOURCE":
        raise ValueError("第二项A公开投影不是正式上游真源")
    records = payload.get("records") or []
    if payload.get("public_projection_record_count") != len(records):
        raise ValueError("第二项A公开投影人物计数不一致")
    if not isinstance(payload.get("public_projection_derived_total_count"), int):
        raise ValueError("第二项A公开投影总账补齐计数缺失")
    if not isinstance(payload.get("public_projection_generated_node_id_count"), int):
        raise ValueError("第二项A公开投影稳定ID计数缺失")
    materials = _load_materials(workspace_root)
    expected_node_count = 0
    generated_node_id_count = 0
    for row in records:
        name = str(row.get("ruler_name"))
        for key in PROFILE_KEYS + ("important_institutions",):
            for profile in row.get(key) or []:
                if not isinstance(profile, dict) or not str(profile.get("institution_node_id") or "").strip():
                    raise ValueError(f"第二项A原始公开节点缺少稳定ID：{name}")
                if str(profile.get("institution_node_id") or "").startswith("A-PUBLIC-NODE-"):
                    generated_node_id_count += 1
        actual_nodes = row.get("public_institution_nodes")
        if not isinstance(actual_nodes, list):
            raise ValueError(f"第二项A缺少逐人公开节点列表：{name}")
        ids = [str(node.get("institution_node_id") or "") for node in actual_nodes if isinstance(node, dict)]
        if len(ids) != len(actual_nodes) or len(ids) != len(set(ids)) or any(not value for value in ids):
            raise ValueError(f"第二项A逐人公开节点ID不唯一或缺失：{name}")
        for node in actual_nodes:
            if set(node) != set(PUBLIC_NODE_FIELDS):
                raise ValueError(f"第二项A公开节点字段不完整：{name} / {node.get('institution_node_id')}")
            if node.get("public_direction") not in {"正向", "负向", "正负并存", "正向主导", "负向主导"}:
                raise ValueError(f"第二项A公开方向非法：{name} / {node.get('institution_node_id')}")
            if not str(node.get("public_label") or "").strip() or not str(node.get("public_adjudication_basis") or "").strip():
                raise ValueError(f"第二项A公开标题或裁决缺失：{name} / {node.get('institution_node_id')}")
            if not isinstance(node.get("public_tags"), list) or not node["public_tags"]:
                raise ValueError(f"第二项A公开标签缺失：{name} / {node.get('institution_node_id')}")
            for field in (
                "public_label",
                "public_adjudication_basis",
                "public_scope",
                "public_boundary",
                "public_reception",
            ):
                value = str(node.get(field) or "")
                if not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
                    raise ValueError(f"第二项A公开字段含空值或内部术语：{name} / {node.get('institution_node_id')} / {field}")
        expected_nodes, reception_counts = _public_nodes(row, materials)
        if actual_nodes != expected_nodes:
            raise ValueError(f"第二项A公开节点不是当前正式结构的确定性投影：{name}")
        public_positive = sum(_number(node["signed_weight"]) for node in actual_nodes if _number(node["signed_weight"]) > 0)
        public_negative = sum(-_number(node["signed_weight"]) for node in actual_nodes if _number(node["signed_weight"]) < 0)
        positive = _number(row.get("P_gross"))
        negative = _number(row.get("N_gross"))
        net = _number(row.get("A_net_units"))
        if (
            abs(public_positive - positive) > 1e-9
            or abs(public_negative - negative) > 1e-9
            or abs(net - (positive - negative)) > 1e-9
        ):
            raise ValueError(f"第二项A公开节点正负权重与正式总账不一致：{name}")
        summary = row.get("public_adjudication_summary")
        if not isinstance(summary, str) or not summary.strip() or PUBLIC_FORBIDDEN_RE.search(summary):
            raise ValueError(f"第二项A人物级公开总结缺失或含内部术语：{name}")
        expected_summary = _summary(row, positive, negative, net, reception_counts, len(actual_nodes))
        if summary != expected_summary:
            raise ValueError(f"第二项A人物级公开总结不是正式总账的确定性投影：{name}")
        if row.get("public_boundary") != A_PUBLIC_BOUNDARY:
            raise ValueError(f"第二项A人物级公开边界不是当前公开合同投影：{name}")
        evidence = row.get("public_evidence_items")
        expected_evidence = _public_evidence_items(row, actual_nodes)
        if evidence != expected_evidence:
            raise ValueError(f"第二项A人物级公开证据不是当前制度节点的确定性投影：{name}")
        for index, item in enumerate(evidence):
            for field in ("public_label", "public_basis", "public_boundary"):
                value = str(item.get(field) or "")
                if not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
                    raise ValueError(f"第二项A公开证据字段缺失或含内部术语：{name} / {index} / {field}")
        expected_node_count += len(actual_nodes)
    if payload.get("public_projection_node_count") != expected_node_count:
        raise ValueError("第二项A公开投影节点计数不一致")
    if payload.get("public_projection_generated_node_id_count") != generated_node_id_count:
        raise ValueError("第二项A公开投影稳定ID计数不一致")
    if not 0 <= payload["public_projection_derived_total_count"] <= len(records):
        raise ValueError("第二项A公开投影总账补齐计数非法")
    return {
        "status": "PASS",
        "record_count": len(records),
        "public_node_count": expected_node_count,
        "generated_node_id_count": generated_node_id_count,
        "derived_total_count": payload["public_projection_derived_total_count"],
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
    }


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    path = workspace_root / A_PATH
    current = load_json(path)
    projected = _refresh_payload(copy.deepcopy(current), workspace_root)
    if write:
        write_json(path, projected, ruler_polities=load_ruler_polities(workspace_root))
        report = verify_public_projection(workspace_root)
        report["status"] = "WRITTEN"
        return report
    if projected != current:
        raise ValueError("第二项A正式公开投影未同步；请运行second-item-a-public --write")
    return verify_public_projection(workspace_root)
