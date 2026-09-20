"""Build and verify the formal public projection for Second Item D1/D3."""
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


D1_PATH = Path(
    "docs/评分结算/净收益/第二项治国净收益/政权交接稳定/"
    "01-D1继任行政连续性方向卡.json"
)
D3_PATH = Path(
    "docs/评分结算/净收益/第二项治国净收益/政权交接稳定/"
    "02-D3政权交接稳定方向卡.json"
)
PUBLIC_PROJECTION_SCHEMA = "second-item-d1-d3-public-projection-v1"
PUBLIC_EVIDENCE_FIELDS = (
    "id",
    "public_label",
    "public_role",
    "public_basis",
    "public_boundary",
)

D1_LEVEL_LABELS = {
    0: "行政连续性中断",
    1: "残余性行政承接",
    2: "部分行政承接，关键领域需要接管或重组",
    3: "既有行政链继续运行",
    4: "多领域或广域行政链继续交付",
    5: "高强度多领域行政连续",
}
D3_LEVEL_LABELS = {
    0: "交接断裂",
    1: "分裂争位",
    2: "暴力接管",
    3: "脆弱完成",
    4: "安全交接",
    5: "高质量交接",
}
D1_CODE_LABELS = {
    "DIRECT_D1_CONTINUITY": "既有行政链连续运行",
    "DIRECT_D1_DISRUPTION": "行政链断裂或结构重组",
}
CLOSURE_LABELS = {
    "observed_or_repeated": "窗口内已有实际结果",
    "repeated_or_stage": "多个阶段出现实际结果",
    "sustained_or_systemic": "形成持续的实际结果",
    "institution_lifecycle_adjudicated": "机构的设立、运行与后续变化均有实际材料支持",
}

# Public fields are deliberately checked separately from the machine-facing
# formal record. Machine IDs, grade codes, URLs, and process/audit vocabulary
# may remain in the formal record but must not leak into the reader projection.
PUBLIC_FORBIDDEN_RE = re.compile(
    r"(?:"
    r"https?://|"
    r"(?<![A-Za-z0-9])(?:D1|D3|H[0-5]|G[0-5]|E[0-3]|M[0-3])(?:-[A-Z0-9_]+)?(?![A-Za-z0-9])|"
    r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9_:-]*(?![A-Za-z0-9])|"
    r"责任窗口|门禁|消费|闭合|主档|本轮|重审|重裁|回源|恢复原|版本|审计|"
    r"字段|枚举|schema|reader|position|grade|lifecycle|score|direction|formal|source"
    r")",
    flags=re.IGNORECASE,
)
ASCII_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9_:-]*(?![A-Za-z0-9])"
)


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
    """Remove internal notation while retaining the formal factual wording."""

    if isinstance(value, list):
        return "；".join(_unique([_clean_public_text(item) for item in value]))
    if value is None:
        return ""
    text = str(value).replace("`", "").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\{\{.*?\}\}", "", text)

    # These clauses describe the adjudication process or a different axis,
    # rather than the public fact being projected.
    text = re.sub(
        r"[^。；]*?(?:按(?:D1|D3)?(?:主档|语义)?(?:门禁|生命周期|闭合)|"
        r"本轮|重审|重裁|回源|恢复原|审计)[^。；]*[。；]?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"[^。；]*?(?:D1|D3)[^。；]*[。；]?", "", text, flags=re.IGNORECASE)

    replacements = (
        ("消费", "计入"),
        ("闭合", "形成完整链条"),
        ("主档", "等级判断"),
        ("生命周期", "连续链"),
        ("门禁", "条件"),
        ("position", "档内位置"),
        ("formal", ""),
        ("source", ""),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = text.replace("完整终局窗", "完整交接记录")
    # Remove remaining machine identifiers and enum words, including IDs next
    # to Chinese text where a normal word boundary is not present.
    text = ASCII_TOKEN_RE.sub("", text)
    text = re.sub(r"[；，、]\s*[；，、]+", "；", text)
    text = re.sub(r"。\s*。+", "。", text)
    text = re.sub(r"；\s*。", "。", text)
    text = re.sub(r"(?:判|定)(?=。|；|$)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ；，、。:：")


def _number(value: object) -> float:
    if isinstance(value, bool) or value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _d1_level(row: dict[str, Any]) -> int:
    value = str(row.get("handoff_level") or row.get("grade") or "")
    match = re.search(r"([0-5])$", value)
    if not match:
        raise ValueError(f"D1缺少可识别的正式档位：{row.get('ruler_name')}")
    return int(match.group(1))


def _d3_level(row: dict[str, Any]) -> int:
    value = str(row.get("D3_grade") or "")
    match = re.search(r"([0-5])$", value)
    if not match:
        raise ValueError(f"D3缺少可识别的正式档位：{row.get('ruler_name')}")
    return int(match.group(1))


def _profile_rows(row: dict[str, Any]):
    for profile_key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
        for index, profile in enumerate(row.get(profile_key) or []):
            if isinstance(profile, dict):
                yield profile_key, index, profile


def _profile_label(profile: dict[str, Any]) -> str:
    mechanism = str(profile.get("mechanism") or "").strip()
    if mechanism in D1_CODE_LABELS:
        return D1_CODE_LABELS[mechanism]
    label = _clean_public_text(profile.get("label_zh") or mechanism)
    return label or "行政承接与运行"


def _profile_role(profile: dict[str, Any]) -> str:
    direction = str(profile.get("direction") or "")
    weight = _number(profile.get("signed_weight"))
    if direction.startswith("mixed_"):
        return "承接与风险并存"
    if weight > 0:
        return "前任行政资产承接"
    if weight < 0:
        return "行政断裂或结构替换"
    return "背景边界"


def _d1_basis(row: dict[str, Any], profile: dict[str, Any]) -> str:
    label = _profile_label(profile)
    mechanism = str(profile.get("mechanism") or "").strip()
    generic = {
        "继任行政连续性",
        "制度交班与行政连续性",
        "其他制度行政机制",
        "DIRECT_D1_CONTINUITY",
        "DIRECT_D1_DISRUPTION",
    }
    basis = _clean_public_text(profile.get("label_zh") or profile.get("mechanism"))
    if not basis or mechanism in generic:
        basis = _clean_public_text(row.get("grade_basis"))
    closure = CLOSURE_LABELS.get(str(profile.get("result_closure") or ""))
    if closure and closure not in basis:
        basis = f"{basis}；{closure}" if basis else closure
    return basis or "正式记录显示该承接或断裂在退出后的观察范围内具有实际结果。"


def _d1_boundary(profile: dict[str, Any]) -> str:
    role = _profile_role(profile)
    if role == "行政断裂或结构替换":
        return (
            "观察范围为前任实际权力终止后的通常三年；这里只记录行政断裂、换血、重组或执行失序，"
            "宫廷争位本身属于交接安全，继任者独立新政和更晚长期成败不归入。"
        )
    if role == "背景边界":
        return (
            "这条材料只作背景核对；行政连续性仍须以退出后既有官署、人员、命令或执行链的实际运行判断，"
            "不把继任者独立新政和更晚长期成败归给前任。"
        )
    if role == "承接与风险并存":
        return (
            "观察范围为前任实际权力终止后的通常三年；这里只保留前任行政资产继续运行与其风险边界，"
            "宫廷争位和继任者独立新政分别按各自问题处理。"
        )
    return (
        "观察范围为前任实际权力终止后的通常三年；这里只把前任留下并被继任继续使用的官署、人员、"
        "命令或执行链归入承接，继任者独立新政和更晚长期成败不归入。"
    )


def _stable_id(axis: str, row: dict[str, Any], suffix: str) -> str:
    raw = f"{axis}|{row.get('ruler_id', '')}|{suffix}".encode("utf-8")
    return f"{axis}-PUBLIC-" + hashlib.sha256(raw).hexdigest()[:16].upper()


def _d1_evidence_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for profile_key, index, profile in _profile_rows(row):
        items.append(
            {
                "id": _stable_id("D1", row, f"{profile_key}|{index}"),
                "public_label": _profile_label(profile),
                "public_role": _profile_role(profile),
                "public_basis": _d1_basis(row, profile),
                "public_boundary": _d1_boundary(profile),
            }
        )
    if not items:
        items.append(
            {
                "id": _stable_id("D1", row, "overall"),
                "public_label": "总体行政承接判断",
                "public_role": "总体结果",
                "public_basis": _clean_public_text(row.get("grade_basis"))
                or "正式记录显示退出后的行政承接没有形成可直述的单独材料条目。",
                "public_boundary": _d1_boundary({}),
            }
        )
    return items


def _d1_summary(row: dict[str, Any]) -> str:
    level = _d1_level(row)
    basis = _clean_public_text(row.get("grade_basis"))
    summary = D1_LEVEL_LABELS[level]
    if basis:
        summary += f"。{basis}"
    return (
        f"{summary}。判断窗口是前任实际权力终止后的通常三年；只计入前任留下并被继任继续使用的"
        "官署、人员、命令或执行链，继任者独立新政和更晚长期成败不归入。"
    )


def _d3_successor(row: dict[str, Any]) -> str:
    value = _clean_public_text(row.get("actual_successor"))
    return value or "未形成有效的本政权中央继承"


def _d3_facts(row: dict[str, Any]) -> str:
    facts = _clean_public_text(row.get("immediate_result_facts"))
    reason = _clean_public_text(row.get("reason"))
    if reason and reason not in facts:
        facts = f"{facts}；{reason}" if facts else reason
    return facts or "正式记录未提供可直述的即时交接事实。"


def _d3_boundary(role: str) -> str:
    if role == "事前安排":
        return (
            "安排只说明前任留下的承接准备，不等于交接已经安全完成；实际结果仍以中央是否形成单一承接、"
            "以及交接窗口内是否出现争位或强制改立为准。"
        )
    if role == "终局事实":
        return (
            "这里只确认实际权力终止至中央承接后的交接事实；继任者后来的行政表现、长期治理和后世政权寿命不归入。"
        )
    return (
        "评价范围是实际权力终止至中央承接后约一年的交接窗口；这里只看承接是否完成、是否出现争位、"
        "暴力接管或中央分裂，不把继任者长期治理倒归前任。"
    )


def _d3_evidence_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    successor = _d3_successor(row)
    arrangement = _clean_public_text(row.get("prearrangement_evidence"))
    facts = _d3_facts(row)
    terminal = _clean_public_text(row.get("terminal_evidence"))
    if not arrangement:
        arrangement = "正式记录未见前任留下的明确承接安排。"
    elif "终局窗口" in arrangement and ("固定" in arrangement or "复核" in arrangement):
        arrangement = "现有材料未提供可直述的事前安排。"
    if not terminal:
        terminal = facts
    return [
        {
            "id": _stable_id("D3", row, "arrangement"),
            "public_label": "事前安排",
            "public_role": "事前安排",
            "public_basis": arrangement,
            "public_boundary": _d3_boundary("事前安排"),
        },
        {
            "id": _stable_id("D3", row, "immediate"),
            "public_label": "即时承接结果",
            "public_role": "交接结果",
            "public_basis": f"实际承接者：{successor}；{facts}",
            "public_boundary": _d3_boundary("交接结果"),
        },
        {
            "id": _stable_id("D3", row, "terminal"),
            "public_label": "终局事实",
            "public_role": "终局事实",
            "public_basis": terminal,
            "public_boundary": _d3_boundary("终局事实"),
        },
    ]


def _d3_summary(row: dict[str, Any]) -> str:
    level = _d3_level(row)
    basis = _clean_public_text(row.get("reason")) or _d3_facts(row)
    return (
        f"{D3_LEVEL_LABELS[level]}。实际承接者：{_d3_successor(row)}。{basis}。"
        "评价范围是实际权力终止至中央承接后约一年的交接窗口；继任者后来的行政表现、长期治理和"
        "后世政权寿命不归入。"
    )


def _scoring_signature(payload: dict[str, Any]) -> str:
    snapshot = copy.deepcopy(payload.get("records") or [])
    for row in snapshot:
        for key in (
            "public_adjudication_summary",
            "public_evidence_items",
        ):
            row.pop(key, None)
    return json.dumps(
        sorted(snapshot, key=lambda item: str(item.get("ruler_id"))),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _refresh_payload(payload: dict[str, Any], axis: str) -> dict[str, Any]:
    before_signature = _scoring_signature(payload)
    item_count = 0
    for row in payload.get("records") or []:
        if axis == "D1":
            row["public_adjudication_summary"] = _d1_summary(row)
            row["public_evidence_items"] = _d1_evidence_items(row)
        elif axis == "D3":
            row["public_adjudication_summary"] = _d3_summary(row)
            row["public_evidence_items"] = _d3_evidence_items(row)
        else:
            raise ValueError(f"未知D1/D3公开投影轴：{axis}")
        item_count += len(row["public_evidence_items"])
    if _scoring_signature(payload) != before_signature:
        raise ValueError(f"第二项{axis}公开字段迁移意外改变了正式评分字段")
    payload["public_projection_schema_version"] = PUBLIC_PROJECTION_SCHEMA
    payload["public_projection_axis"] = axis
    payload["public_projection_status"] = "FORMAL_UPSTREAM_SOURCE"
    payload["public_projection_record_count"] = len(payload.get("records") or [])
    payload["public_projection_evidence_item_count"] = item_count
    payload["public_projection_source"] = {
        "formal_contract": "docs/分项规则/第二项治国净收益/政权交接稳定/00-规则与结算合同.md",
        "reader_policy": "reader只消费public_adjudication_summary和public_evidence_items",
        "boundary": (
            "D1只公开行政承接；D3只公开中央权力交接；继任者独立新政和长期治理不倒灌。"
        ),
    }
    return payload


def _verify_text(value: object, *, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"第二项D1/D3公开字段为空：{name}")
    if PUBLIC_FORBIDDEN_RE.search(value):
        raise ValueError(f"第二项D1/D3公开字段含内部术语或机器标记：{name}")


def _verify_payload(payload: dict[str, Any], axis: str) -> dict[str, Any]:
    if payload.get("public_projection_schema_version") != PUBLIC_PROJECTION_SCHEMA:
        raise ValueError(f"第二项{axis}缺少正式公开投影schema标记")
    if payload.get("public_projection_axis") != axis:
        raise ValueError(f"第二项{axis}公开投影轴标记不一致")
    if payload.get("public_projection_status") != "FORMAL_UPSTREAM_SOURCE":
        raise ValueError(f"第二项{axis}公开投影不是正式上游真源")
    records = payload.get("records") or []
    if payload.get("public_projection_record_count") != len(records):
        raise ValueError(f"第二项{axis}公开投影人物计数不一致")
    all_ids: set[str] = set()
    expected_count = 0
    for row in records:
        name = str(row.get("ruler_name") or "")
        if axis == "D1":
            expected_summary = _d1_summary(row)
            expected_items = _d1_evidence_items(row)
        else:
            expected_summary = _d3_summary(row)
            expected_items = _d3_evidence_items(row)
        summary = row.get("public_adjudication_summary")
        _verify_text(summary, name=name)
        if summary != expected_summary:
            raise ValueError(f"第二项{axis}人物级公开总结不是确定性投影：{name}")
        actual_items = row.get("public_evidence_items")
        if not isinstance(actual_items, list) or not actual_items:
            raise ValueError(f"第二项{axis}缺少逐人公开材料列表：{name}")
        expected_count += len(expected_items)
        if actual_items != expected_items:
            raise ValueError(f"第二项{axis}公开材料不是当前正式结构的确定性投影：{name}")
        ids = []
        for item in actual_items:
            if set(item) != set(PUBLIC_EVIDENCE_FIELDS):
                raise ValueError(f"第二项{axis}公开材料字段不完整：{name}")
            item_id = str(item.get("id") or "")
            if not item_id.startswith(f"{axis}-PUBLIC-") or item_id in all_ids:
                raise ValueError(f"第二项{axis}公开材料ID不稳定或重复：{name}")
            ids.append(item_id)
            for field in ("public_label", "public_role", "public_basis", "public_boundary"):
                _verify_text(item.get(field), name=f"{name}/{item_id}/{field}")
        all_ids.update(ids)
    if payload.get("public_projection_evidence_item_count") != expected_count:
        raise ValueError(f"第二项{axis}公开材料计数不一致")
    return {
        "status": "PASS",
        "axis": axis,
        "record_count": len(records),
        "public_evidence_item_count": expected_count,
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
    }


def verify_public_projection(
    workspace_root: Path,
    *,
    payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if payloads is None:
        payloads = {
            "D1": load_json(workspace_root / D1_PATH),
            "D3": load_json(workspace_root / D3_PATH),
        }
    d1 = _verify_payload(payloads["D1"], "D1")
    d3 = _verify_payload(payloads["D3"], "D3")
    d1_ids = {row.get("ruler_id") for row in payloads["D1"].get("records") or []}
    d3_ids = {row.get("ruler_id") for row in payloads["D3"].get("records") or []}
    if d1_ids != d3_ids:
        raise ValueError("第二项D1/D3公开投影覆盖对象不一致")
    return {
        "status": "PASS",
        "record_count": len(d1_ids),
        "D1": d1,
        "D3": d3,
    }


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    paths = {"D1": workspace_root / D1_PATH, "D3": workspace_root / D3_PATH}
    current = {axis: load_json(path) for axis, path in paths.items()}
    projected = {
        axis: _refresh_payload(copy.deepcopy(payload), axis)
        for axis, payload in current.items()
    }
    if write:
        ruler_polities = load_ruler_polities(workspace_root)
        for axis, path in paths.items():
            write_json(path, projected[axis], ruler_polities=ruler_polities)
        report = verify_public_projection(workspace_root)
        report["status"] = "WRITTEN"
        return report
    if projected != current:
        raise ValueError("第二项D1/D3正式公开投影未同步；请运行second-item-d1-d3-public --write")
    return verify_public_projection(workspace_root)
