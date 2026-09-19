"""Build and verify the formal public projection for Second Item B2."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)


B2_PATH = Path(
    "docs/评分结算/净收益/第二项治国净收益/制度行政/"
    "03-B2反馈纠错与权力约束方向卡.json"
)
CONTRACT_PATH = Path("docs/分项规则/第二项治国净收益/制度行政/00-规则与计分合同.md")
PUBLIC_PROJECTION_SCHEMA = "second-item-b2-public-projection-v1"
PROFILE_KEYS = ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
PUBLIC_EVIDENCE_FIELDS = (
    "id",
    "public_label",
    "public_direction",
    "public_tags",
    "public_basis",
    "public_boundary",
)

PUBLIC_DIRECTIONS = {"正向", "负向", "正向主导", "负向主导", "正负并存"}
GRADE_LABELS = {
    "G0": "最低档",
    "G1": "较低档",
    "G2": "中档",
    "G3": "较高档",
    "G4": "高档",
    "G5": "最高档",
}
POSITION_LABELS = {
    "lower": "下位",
    "lower-middle": "中下位",
    "middle": "中位",
    "middle-upper": "中上位",
    "upper": "上位",
}
ROLE_LABELS = {
    "external_constraint": "外部约束",
    "information_ingress": "信息进入",
    "sovereign_self_correction": "本人纠偏",
    "ignored_high_stakes_feedback": "重要意见未被采纳",
}
CLOSURE_LABELS = {
    "observed": "已观察到实际结果",
    "observed_or_repeated": "已观察到实际结果",
    "repeated_or_stage": "在多个阶段出现实际结果",
    "sustained_or_systemic": "形成持续或系统性结果",
    "institution_lifecycle_adjudicated": "设立、运行与后续变化均有材料支持",
    "limited_observation": "目前只有有限的实际观察",
    "context_only": "仅作背景核对",
}

PUBLIC_FORBIDDEN_RE = re.compile(
    r"(?:"
    r"(?<![A-Za-z0-9])(?:B1|B2|C[1-4]|D[13]|M[0-3]|M|G[0-5]|R[0-4])(?![A-Za-z0-9])|"
    r"S(?:\+\+|\+|−|-)\s*\d*|"
    r"\b(?:position|lifecycle|canonical|observed_or_repeated|"
    r"repeated_or_stage|sustained_or_systemic|institution_lifecycle_adjudicated|"
    r"context_only|external_constraint|information_ingress|"
    r"sovereign_self_correction|ignored_high_stakes_feedback)\b|"
    r"[A-Za-z]+(?:_[A-Za-z0-9]+)+|"
    r"生命周期|门禁|主档|消费|净余量|计权|闭合|本轮|重审|重裁|恢复原|版本史"
    r")",
    flags=re.IGNORECASE,
)


def _number(value: object) -> float:
    if isinstance(value, bool) or value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _clean_public_text(value: object) -> str:
    """Translate formal B2 shorthand before it reaches the public source."""

    text = str(value or "").replace("`", "").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\{\{.*?\}\}", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Remove process-history clauses from the person-level summary. The
    # underlying formal settlement remains available in the machine fields.
    text = re.sub(
        r"[^。；]*?(?:专项扩搜|扩搜|重审|重裁|再审|改判|按修订后的)[^。；]*[。；]",
        "",
        text,
    )
    replacements = (
        (r"(?<![A-Za-z0-9])B1(?![A-Za-z0-9])", "官僚治理"),
        (r"(?<![A-Za-z0-9])B2(?![A-Za-z0-9])", "本项"),
        (r"(?<![A-Za-z0-9])C[1-4](?![A-Za-z0-9])", "其他治理结果"),
        (r"(?<![A-Za-z0-9])D(?:1|3)(?![A-Za-z0-9])", "交接评价"),
        (r"mixed[-_]negative\s*M3", "负向主导的较强机制"),
        (r"mixed[-_]positive\s*M3", "正向主导的较强机制"),
        (r"mixed[-_]negative\s*M2", "负向主导的有限机制"),
        (r"mixed[-_]positive\s*M2", "正向主导的有限机制"),
        (r"正向主导\s*mixed\s*M3", "正向主导的较强机制"),
        (r"负向主导\s*mixed\s*M3", "负向主导的较强机制"),
        (r"mixed\s*M3", "正负并存的较强机制"),
        (r"mixed\s*M2", "正负并存的有限机制"),
        (r"有限(?:的)?\s*正向?M2", "有限的正向机制"),
        (r"有限(?:的)?\s*负向?M2", "有限的负向机制"),
        (r"正向M3", "较强的正向机制"),
        (r"负向M3", "较强的负向机制"),
        (r"正向M2", "有限的正向机制"),
        (r"负向M2", "有限的负向机制"),
        (r"正M3", "较强的正向机制"),
        (r"负M3", "较强的负向机制"),
        (r"正M2", "有限的正向机制"),
        (r"负M2", "有限的负向机制"),
        (r"多M2路径", "多条有限机制路径"),
        (r"多M2门", "多条有限机制条件"),
        (r"M数量", "机制数量"),
        (r"计M", "计入机制判断"),
        (r"(?<![A-Za-z0-9])M3(?![A-Za-z0-9])", "持续或系统性的机制"),
        (r"(?<![A-Za-z0-9])M2(?![A-Za-z0-9])", "有限但有实际结果的机制"),
        (r"(?<![A-Za-z0-9])M1(?![A-Za-z0-9])", "阶段性机制"),
        (r"(?<![A-Za-z0-9])M0(?![A-Za-z0-9])", "背景或未形成实际结果的材料"),
        (r"(?<![A-Za-z0-9])G5(?![A-Za-z0-9])", "最高档"),
        (r"(?<![A-Za-z0-9])G4(?![A-Za-z0-9])", "高档"),
        (r"(?<![A-Za-z0-9])G3(?![A-Za-z0-9])", "较高档"),
        (r"(?<![A-Za-z0-9])G2(?![A-Za-z0-9])", "中档"),
        (r"(?<![A-Za-z0-9])G1(?![A-Za-z0-9])", "较低档"),
        (r"(?<![A-Za-z0-9])G0(?![A-Za-z0-9])", "最低档"),
        (r"(?<![A-Za-z0-9])R4(?![A-Za-z0-9])", "跨朝代长期沿用"),
        (r"(?<![A-Za-z0-9])R3(?![A-Za-z0-9])", "多个后继阶段持续采用"),
        (r"(?<![A-Za-z0-9])R[12](?![A-Za-z0-9])", "有限的后世接收"),
        (r"(?<![A-Za-z0-9])R0(?![A-Za-z0-9])", "本人任内实际运行"),
        (r"(?<![A-Za-z0-9])external_constraint(?![A-Za-z0-9])", "外部约束"),
        (r"(?<![A-Za-z0-9])information_ingress(?![A-Za-z0-9])", "信息进入"),
        (r"(?<![A-Za-z0-9])sovereign_self_correction(?![A-Za-z0-9])", "本人纠偏"),
        (r"(?<![A-Za-z0-9])ignored_high_stakes_feedback(?![A-Za-z0-9])", "重要意见未被采纳"),
        (r"(?<![A-Za-z0-9])observed_or_repeated(?![A-Za-z0-9])", "已观察到实际结果"),
        (r"(?<![A-Za-z0-9])repeated_or_stage(?![A-Za-z0-9])", "在多个阶段出现实际结果"),
        (r"(?<![A-Za-z0-9])sustained_or_systemic(?![A-Za-z0-9])", "形成持续或系统性结果"),
        (r"(?<![A-Za-z0-9])institution_lifecycle_adjudicated(?![A-Za-z0-9])", "设立、运行与后续变化均有材料支持"),
        (r"(?<![A-Za-z0-9])context_only(?![A-Za-z0-9])", "仅作背景核对"),
        (r"(?<![A-Za-z0-9])event_scale(?![A-Za-z0-9])", "事件范围"),
        (r"(?<![A-Za-z0-9])sanction_intensity(?![A-Za-z0-9])", "惩罚强度"),
        (r"(?<![A-Za-z0-9])irreversibility(?![A-Za-z0-9])", "后果不可逆程度"),
        (r"(?<![A-Za-z0-9])highest_power_directness(?![A-Za-z0-9])", "最高权力直接性"),
        (r"(?<![A-Za-z0-9])position(?![A-Za-z0-9])", "档内位置"),
        (r"(?<![A-Za-z0-9])lifecycle(?![A-Za-z0-9])", "反馈链"),
        (r"生命周期", "反馈链"),
        (r"跨层级信息进入", "跨层级的信息进入"),
        (r"跨渠道门", "跨渠道条件"),
        (r"主档", "整体判断"),
        (r"门禁", "等级条件"),
        (r"净余量", "综合余量"),
        (r"计权", "计入计算"),
        (r"消费", "计算"),
        (r"闭合", "形成完整链条"),
        (r"去重", "避免重复计算"),
        (r"混合偏正", "正向主导"),
        (r"混合偏负", "负向主导"),
        (r"mixed_positive", "正向主导"),
        (r"mixed_negative", "负向主导"),
        (r"positive", "正向"),
        (r"negative", "负向"),
        (r"balanced|mixed|neutral", "正负并存"),
        (r"本轮", ""),
        (r"恢复原", "恢复既有"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(
        r"档内位置按[^。；]+(?:。|；)?",
        "档内位置由现有机制的代表性确定。",
        text,
    )
    text = re.sub(r"定(最低档|较低档|中档|较高档|高档|最高档)", r"对应\1", text)
    text = re.sub(r"维持(最低档|较低档|中档|较高档|高档|最高档)", r"整体判断为\1", text)
    text = text.replace("有限有限的", "有限的")
    text = text.replace("有限有限但有实际结果的机制", "有限但有实际结果的机制")
    text = text.replace("正负并存-负向", "负向主导")
    text = text.replace("正负并存-正向", "正向主导")
    text = text.replace("多有限但有实际结果的机制", "多条有限机制")
    text = text.replace("抬持续或系统性的机制", "抬成持续或系统性的机制")
    text = text.replace("外部约束 持续或系统性的机制", "持续运行的外部约束")
    text = text.replace("反复运行的持续运行的外部约束", "持续运行的外部约束")
    text = text.replace("整体判断整体判断为", "整体判断为")
    text = text.replace("整体判断较高档保留", "整体判断为较高档")
    text = text.replace("硬门", "条件")
    text = text.replace("最低门", "最低条件")
    text = text.replace("档门", "档位条件")
    text = text.replace("负链", "负向机制")
    text = text.replace("middle", "中位")
    text = re.sub(r"[；，、]\s*[；，、]+", "；", text)
    text = re.sub(r"。\s*。+", "。", text)
    text = re.sub(r"；\s*。", "。", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ；，、")


def _profile_rows(row: dict[str, Any]):
    for profile_key in PROFILE_KEYS:
        for index, profile in enumerate(row.get(profile_key) or []):
            if isinstance(profile, dict):
                yield profile_key, index, profile


def _group_key(profile: dict[str, Any], index: int) -> str:
    for key in ("absorbed_into_lifecycle_key", "lifecycle_key", "material_id"):
        value = str(profile.get(key) or "").strip()
        if value:
            return value
    material_ids = profile.get("material_ids") or []
    if isinstance(material_ids, list):
        for value in material_ids:
            if str(value).strip():
                return str(value).strip()
    return f"profile-{index}"


def _group_profiles(row: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for _, index, profile in _profile_rows(row):
        groups.setdefault(_group_key(profile, index), []).append(profile)
    return groups


def _stable_id(row: dict[str, Any], group_key: str) -> str:
    raw = f"{row.get('ruler_id', '')}|{group_key}".encode("utf-8")
    return "B2-PUBLIC-" + hashlib.sha256(raw).hexdigest()[:16].upper()


def _public_direction(profiles: list[dict[str, Any]]) -> str:
    weights = [_number(profile.get("signed_weight")) for profile in profiles]
    positive = any(value > 0 for value in weights)
    negative = any(value < 0 for value in weights)
    if positive and negative:
        total = sum(weights)
        if total > 0:
            return "正向主导"
        if total < 0:
            return "负向主导"
        return "正负并存"
    if positive:
        return "正向主导" if any(str(p.get("direction")) == "mixed_positive" for p in profiles) else "正向"
    if negative:
        return "负向主导" if any(str(p.get("direction")) == "mixed_negative" for p in profiles) else "负向"
    directions = {str(profile.get("direction") or "") for profile in profiles}
    if "positive" in directions and "negative" in directions:
        return "正负并存"
    if "positive" in directions:
        return "正向"
    if "negative" in directions:
        return "负向"
    if directions & {"mixed_negative"}:
        return "负向主导"
    if directions & {"mixed_positive"}:
        return "正向主导"
    return "正负并存"


def _public_label(profiles: list[dict[str, Any]]) -> str:
    for profile in profiles:
        candidate = _clean_public_text(profile.get("label_zh") or profile.get("mechanism"))
        if candidate:
            candidate = re.split(r"[；。]", candidate, maxsplit=1)[0].strip()
            if len(candidate) > 80:
                candidate = candidate[:77].rstrip("，、； ") + "…"
            return candidate
    return "反馈与约束机制"


def _public_basis(profiles: list[dict[str, Any]]) -> str:
    values: list[str] = []
    for profile in profiles:
        mechanism = _clean_public_text(profile.get("mechanism"))
        closure = CLOSURE_LABELS.get(str(profile.get("result_closure") or ""), "")
        if mechanism and closure and closure not in mechanism:
            mechanism = f"{mechanism}；{closure}"
        if mechanism:
            values.append(mechanism)
    return "；".join(_unique(values)) or "现有正式记录未提供可直述的机制依据。"


def _public_tags(profiles: list[dict[str, Any]]) -> list[str]:
    tags = ["反馈与纠错"]
    for profile in profiles:
        role = ROLE_LABELS.get(str(profile.get("mechanism_role") or ""))
        if role:
            tags.append(role)
        closure = CLOSURE_LABELS.get(str(profile.get("result_closure") or ""))
        if closure:
            tags.append(closure)
        if _number(profile.get("signed_weight")) == 0 or str(profile.get("position_count_mode") or "") in {
            "context_only",
            "context_only_no_effective_mechanism",
        }:
            tags.append("背景材料")
    if len(profiles) > 1 or any(profile.get("absorbed_into_lifecycle_key") for profile in profiles):
        tags.append("同一机制的合并阶段")
    return _unique(tags)


def _public_boundary(profiles: list[dict[str, Any]]) -> str:
    values: list[str] = []
    for profile in profiles:
        reason = _clean_public_text(profile.get("position_exclusion_reason"))
        if reason:
            values.append(reason)
    if any(_number(profile.get("signed_weight")) == 0 for profile in profiles):
        values.append("这条材料仅作背景核对，不单独计算")
    if len(profiles) > 1 or any(profile.get("absorbed_into_lifecycle_key") for profile in profiles):
        values.append("同一反馈机制的多个阶段合并展示，不重复计算")
    else:
        values.append("同一机制只作一次判断，不重复计算")
    values.append("其他治理结果不在这里重复计算")
    return "；".join(_unique(values)) + "。"


def _public_evidence_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for group_key, profiles in _group_profiles(row).items():
        items.append(
            {
                "id": _stable_id(row, group_key),
                "public_label": _public_label(profiles),
                "public_direction": _public_direction(profiles),
                "public_tags": _public_tags(profiles),
                "public_basis": _public_basis(profiles),
                "public_boundary": _public_boundary(profiles),
            }
        )
    return items


def _public_summary(row: dict[str, Any]) -> str:
    basis = row.get("grade_basis") or next(iter(row.get("settlement_basis") or []), "")
    text = _clean_public_text(basis)
    grade = GRADE_LABELS.get(str(row.get("grade") or ""), "当前等级")
    position = POSITION_LABELS.get(str(row.get("position") or ""), "当前档内位置")
    if text and text[-1] not in "。！？":
        text += "。"
    tail = f"整体判断为{grade}（{position}）。"
    if tail not in text:
        text += tail
    return text or tail


def _scoring_signature(payload: dict[str, Any]) -> str:
    snapshot = copy.deepcopy(payload.get("records") or [])
    for row in snapshot:
        for key in ("public_adjudication_summary", "public_evidence_items"):
            row.pop(key, None)
    return json.dumps(
        sorted(snapshot, key=lambda item: str(item.get("ruler_id"))),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _refresh_payload(payload: dict[str, Any]) -> dict[str, Any]:
    before_signature = _scoring_signature(payload)
    profile_count = 0
    evidence_count = 0
    merged_count = 0
    zero_weight_count = 0
    for row in payload.get("records") or []:
        profiles = list(_profile_rows(row))
        profile_count += len(profiles)
        groups = _group_profiles(row)
        items = _public_evidence_items(row)
        row["public_adjudication_summary"] = _public_summary(row)
        row["public_evidence_items"] = items
        evidence_count += len(items)
        merged_count += sum(1 for group in groups.values() if len(group) > 1)
        zero_weight_count += sum(
            1 for _, _, profile in profiles if _number(profile.get("signed_weight")) == 0
        )
    if _scoring_signature(payload) != before_signature:
        raise ValueError("第二项B2公开字段迁移意外改变了正式评分字段")
    payload["public_projection_schema_version"] = PUBLIC_PROJECTION_SCHEMA
    payload["public_projection_status"] = "FORMAL_UPSTREAM_SOURCE"
    payload["public_projection_record_count"] = len(payload.get("records") or [])
    payload["public_projection_profile_count"] = profile_count
    payload["public_projection_evidence_item_count"] = evidence_count
    payload["public_projection_merged_group_count"] = merged_count
    payload["public_projection_zero_weight_profile_count"] = zero_weight_count
    payload["public_projection_source"] = {
        "formal_contract": CONTRACT_PATH.as_posix(),
        "identity": "人物ID加lifecycle_key、absorbed_into_lifecycle_key或材料ID生成稳定公开条目ID",
        "reader_policy": "reader只消费public_adjudication_summary和public_evidence_items",
    }
    return payload


def refresh_public_projection(workspace_root: Path) -> dict[str, Any]:
    return _refresh_payload(load_json(workspace_root / B2_PATH))


def verify_public_projection(
    workspace_root: Path,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if payload is None:
        payload = load_json(workspace_root / B2_PATH)
    if payload.get("public_projection_schema_version") != PUBLIC_PROJECTION_SCHEMA:
        raise ValueError("第二项B2缺少正式公开投影schema标记")
    if payload.get("public_projection_status") != "FORMAL_UPSTREAM_SOURCE":
        raise ValueError("第二项B2公开投影不是正式上游真源")
    records = payload.get("records") or []
    if payload.get("public_projection_record_count") != len(records):
        raise ValueError("第二项B2公开投影人物计数不一致")

    expected_profile_count = 0
    expected_evidence_count = 0
    expected_merged_count = 0
    expected_zero_weight_count = 0
    all_ids: set[str] = set()
    for row in records:
        name = str(row.get("ruler_name"))
        profiles = list(_profile_rows(row))
        groups = _group_profiles(row)
        expected_profile_count += len(profiles)
        expected_evidence_count += len(groups)
        expected_merged_count += sum(1 for group in groups.values() if len(group) > 1)
        expected_zero_weight_count += sum(
            1 for _, _, profile in profiles if _number(profile.get("signed_weight")) == 0
        )
        actual_items = row.get("public_evidence_items")
        if not isinstance(actual_items, list) or not actual_items:
            raise ValueError(f"第二项B2缺少逐人公开材料列表：{name}")
        ids = [str(item.get("id") or "") for item in actual_items if isinstance(item, dict)]
        if len(ids) != len(actual_items) or len(ids) != len(set(ids)) or any(not value for value in ids):
            raise ValueError(f"第二项B2公开材料ID不唯一或缺失：{name}")
        if all_ids & set(ids):
            raise ValueError(f"第二项B2公开材料ID跨人物重复：{name}")
        all_ids.update(ids)
        for item in actual_items:
            if set(item) != set(PUBLIC_EVIDENCE_FIELDS):
                raise ValueError(f"第二项B2公开材料字段不完整：{name} / {item.get('id')}")
            if not str(item.get("id") or "").startswith("B2-PUBLIC-"):
                raise ValueError(f"第二项B2公开材料ID不稳定：{name} / {item.get('id')}")
            if item.get("public_direction") not in PUBLIC_DIRECTIONS:
                raise ValueError(f"第二项B2公开方向非法：{name} / {item.get('id')}")
            if not isinstance(item.get("public_tags"), list) or not item["public_tags"]:
                raise ValueError(f"第二项B2公开标签缺失：{name} / {item.get('id')}")
            for tag in item["public_tags"]:
                if not isinstance(tag, str) or not tag.strip() or PUBLIC_FORBIDDEN_RE.search(tag):
                    raise ValueError(f"第二项B2公开标签含空值或内部术语：{name} / {item.get('id')}")
            for field in ("public_label", "public_basis", "public_boundary"):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
                    raise ValueError(f"第二项B2公开字段含空值或内部术语：{name} / {item.get('id')} / {field}")
        expected_items = _public_evidence_items(row)
        if actual_items != expected_items:
            raise ValueError(f"第二项B2公开材料不是当前正式结构的确定性投影：{name}")
        summary = row.get("public_adjudication_summary")
        if not isinstance(summary, str) or not summary.strip() or PUBLIC_FORBIDDEN_RE.search(summary):
            raise ValueError(f"第二项B2人物级公开总结缺失或含内部术语：{name}")
        if summary != _public_summary(row):
            raise ValueError(f"第二项B2人物级公开总结不是当前正式裁决的确定性投影：{name}")

    if payload.get("public_projection_profile_count") != expected_profile_count:
        raise ValueError("第二项B2公开投影profile计数不一致")
    if payload.get("public_projection_evidence_item_count") != expected_evidence_count:
        raise ValueError("第二项B2公开材料计数不一致")
    if payload.get("public_projection_merged_group_count") != expected_merged_count:
        raise ValueError("第二项B2公开合并组计数不一致")
    if payload.get("public_projection_zero_weight_profile_count") != expected_zero_weight_count:
        raise ValueError("第二项B2背景profile计数不一致")
    return {
        "status": "PASS",
        "record_count": len(records),
        "profile_count": expected_profile_count,
        "public_evidence_item_count": expected_evidence_count,
        "merged_group_count": expected_merged_count,
        "zero_weight_profile_count": expected_zero_weight_count,
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
    }


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    path = workspace_root / B2_PATH
    current = load_json(path)
    projected = _refresh_payload(copy.deepcopy(current))
    if write:
        write_json(path, projected, ruler_polities=load_ruler_polities(workspace_root))
        report = verify_public_projection(workspace_root)
        report["status"] = "WRITTEN"
        return report
    if projected != current:
        raise ValueError("第二项B2正式公开投影未同步；请运行second-item-b2-public --write")
    return verify_public_projection(workspace_root)
