"""Build and verify public adjudication projections for Items 3 and 4.

The formal settlement records remain the scoring authority.  This module only
adds deterministic ``public_*`` fields derived from those records and refuses
to write when the scoring payload changes.
"""
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


THIRD_AB_PATH = Path(
    "docs/评分结算/净收益/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json"
)
THIRD_C_PATH = Path(
    "docs/评分结算/净收益/第三项军事与边疆净收益/军事体系有效性/01-皇帝C项正式结算.json"
)
THIRD_D_PATH = Path(
    "docs/评分结算/净收益/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
)
THIRD_CREDIT_PATH = Path("config/third-item/third-item-result-credit-adjudications.json")
THIRD_ML_PATH = Path("config/third-item/third-item-military-net-loss-penalties.json")
THIRD_TOTAL_PATH = Path("docs/评分结算/净收益/第三项军事与边疆净收益/02-第三项正式结算.json")
FOURTH_PATH = Path(
    "docs/评分结算/净收益/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json"
)

PUBLIC_PROJECTION_SCHEMA = "third-fourth-item-public-projection-v1"
PUBLIC_EVIDENCE_FIELDS = (
    "id",
    "public_label",
    "public_role",
    "public_basis",
    "public_boundary",
)
PUBLIC_PROJECTION_FIELDS = {
    "public_adjudication_summary",
    "public_evidence_items",
    "public_boundary",
    "public_level_label",
    "public_component_label",
    "public_axis_projections",
    "public_military_cost",
    "public_military_net_loss",
}

THIRD_ROUTED_PATHS = {
    "AB": THIRD_AB_PATH,
    "C": THIRD_C_PATH,
    "D": THIRD_D_PATH,
}

THIRD_AXIS_LABELS = {
    "A1": "主要安全威胁与战略主动",
    "A2": "防线协同与战略纵深",
    "B1": "实际控制范围",
    "B2": "战略成果价值",
    "B4": "控制成果稳定性",
    "C1": "实战任务交付",
    "C2": "持续作战与任务承载",
    "C3": "军事体系可靠性",
    "ML": "重大军事净毁损",
}

THIRD_AXIS_ROLES = {
    "A1": "安全威胁变化",
    "A2": "防线与纵深",
    "B1": "控制范围变化",
    "B2": "战略价值",
    "B4": "稳定交付",
    "C1": "实战结果",
    "C2": "持续承载",
    "C3": "体系可靠性",
    "ML": "重大损失判断",
}

THIRD_BOUNDARIES = {
    "A1": "这里只看本人统治窗口内的安全威胁变化和战略主动，不把统一创业存量、继任者阶段或将领独立行动重复计入。",
    "A2": "这里只看本人窗口新增或保全的边防协同与战略纵深，不把继承存量重复计作本人建设。",
    "B1": "这里只看本人窗口可确认的实际控制范围变化，不按继承存量、名称或一次性占领自动计作新增成果。",
    "B2": "这里只看控制成果的战略价值，不把面积、战役数量或同一成果重复计入。",
    "B4": "这里只看控制成果在本人离场前后的稳定交付，不把后继者独立表现倒归本人。",
    "C1": "这里只看本人责任窗口内军事体系把资源转化为真实任务结果的表现，具体统帅执行按事实分别承担责任。",
    "C2": "这里只看跨阶段动员、补充和完成任务的实际承载，不把单次胜负或后继者独立作战重复计入。",
    "C3": "这里只看不同战区和压力下体系是否可靠，不把单名将的独立能力或同一战果重复计为体系表现。",
    "ML": "只有重大结果、较高本方代价和本人责任同时成立时才追加重大净毁损扣减；普通军事代价已覆盖的同一损失不再重复扣减。",
}

CIVILIZATION_AXIS_LABELS = {
    "A": "国家共同体与社会整合",
    "B": "教育可及与人才流动",
    "C": "知识生产、传播与文化生态",
}

CIVILIZATION_BOUNDARIES = {
    "A": "这里只报告本人实际掌权窗口内、能够与既有共同体状态区分的变化；前代存量、后世独立发展和其他轴已经承担的结果不重复计算。",
    "B": "这里只报告本人实际掌权窗口内教育、人才和身份通道的可确认变化；既有传统、后世扩展和没有实际使用结果的设置不替代本人窗口证据。",
    "C": "这里只报告本人窗口内知识生产、传播或文化生态的可确认变化；后世名望、单纯作品存世和其他轴的制度结果不重复计算。",
}

LEVEL_LABELS = {index: f"第{index}级" for index in range(0, 7)}
BAND_LABELS = {
    "HIGH": "高位",
    "MID": "中位",
    "LOW": "低位",
    "upper": "上位",
    "middle-upper": "中上位",
    "middle": "中位",
    "middle-lower": "中下位",
    "lower": "下位",
}
ML_LABELS = {
    "ML0": "未达到重大军事净毁损追加条件",
    "ML1": "有限重大军事净毁损",
    "ML2": "明显重大军事净毁损",
    "ML3": "严重重大军事净毁损",
    "ML4": "极严重重大军事净毁损",
}
CIV_MAGNITUDE_LABELS = {
    "CIV1": "第一级影响幅度",
    "CIV2": "第二级影响幅度",
    "CIV3": "第三级影响幅度",
    "CIV4": "第四级影响幅度",
}
RELATIVE_CHANGE_LABELS = {
    "R1": "有限变化",
    "R2": "明显变化",
    "R3": "持续变化",
}
DIRECTION_LABELS = {
    "POSITIVE": "正向变化",
    "NEGATIVE": "负向变化",
    "BALANCED": "正负相抵",
}
ATTRIBUTION_LABELS = {
    "PRIMARY_RULER": "本人承担主要决策责任",
    "SHARED_MATERIAL": "本人和其他责任中心共同承担",
    "NO_CHANGE": "没有确认本人造成的状态变化",
    "FULL": "本人承担主要责任",
    "SHARED": "本人和其他责任中心共同承担",
    "NONE": "没有确认足够的本人责任",
    "RULER_DIRECT_DECISION": "本人直接决定",
    "RULER_DIRECT_COMMISSION_AND_STATE_PRINT": "本人直接委托并由国家组织实施",
    "RULER_FOUNDED_STATE_INSTITUTION": "本人设立并组织运行",
    "ACTUAL_CONTROLLER_DIRECT_EDICT": "实际掌权者直接下令",
    "SEMANTIC_NODE_RULER_WINDOW": "本人窗口内的责任按事实区分",
    "RULER_COMMISSIONED_AND_SUPPORTED": "本人直接委托并提供支持",
}

# Public text is intentionally stricter than the formal records.  A source may
# keep codes, URLs and audit vocabulary; a public projection may not.
PUBLIC_FORBIDDEN_RE = re.compile(
    r"(?:https?://|"
    r"ML[0-4]|CIV[0-4]|DA[0-9]+|"
    r"\b(?:POSITIVE|NEGATIVE|BALANCED|HYBRID|HIGH|MID|LOW|NONE|FULL|SHARED|"
    r"core|support|reader|formal|source|position|grade|direction|schema)\b|"
    r"门槛|闭合|消费|净账|父链|归责|独立门槛|版本史|审计|本轮|重审|重裁|回源|"
    r"字段|枚举|过程史|主档|档内位置|"
    r"[A-Za-z])",
    flags=re.IGNORECASE,
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
    """Keep factual Chinese prose while removing machine and audit notation."""

    if isinstance(value, (list, tuple)):
        return "；".join(_unique([_clean_public_text(item) for item in value]))
    if isinstance(value, dict):
        return _clean_public_text(
            value.get("summary")
            or value.get("basis")
            or value.get("reason")
            or value.get("details")
            or ""
        )
    if value is None:
        return ""
    text = str(value).replace("`", "").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\bHIGH降MID\b", "由高位降至中位", text)
    text = re.sub(r"\bR3只取LOW\b", "仅取有限水平", text)
    text = re.sub(r"保R3", "已保留当前水平", text)
    text = re.sub(r"\bHIGH\b", "高位", text)
    text = re.sub(r"\bMID\b", "中位", text)
    text = re.sub(r"\bLOW\b", "低位", text)
    text = re.sub(r"\bHIGHEST\b", "最高水平", text)
    text = re.sub(r"\b[A-Z]{1,5}[0-9]+(?:-[A-Z0-9_]+)*\b", "", text)
    text = re.sub(r"[A-Za-z][A-Za-z0-9_:+./-]*", "", text)
    replacements = (
        ("未闭合", "未形成完整证据"),
        ("闭合", "形成完整证据"),
        ("门禁", "条件"),
        ("消费", "计入"),
        ("归责", "本人责任"),
        ("父链", "上层证据"),
        ("门槛", "条件"),
        ("净账", "净效果"),
        ("主档", "主要等级"),
        ("档内位置", "本级位置"),
        ("版本史", "过程记录"),
        ("审计", "核对"),
        ("本轮", "当前评定"),
        ("重审", "复核"),
        ("重裁", "复核"),
        ("回源", "来源核对"),
        ("字段", "内容"),
        ("过程史", "过程记录"),
        ("正式记录", "现有材料"),
        ("逐人裁决", "本人责任判断"),
        ("依据链", "依据"),
        ("总档", "整体水平"),
        ("统一锚", "同一口径"),
        ("交班锚", "接班参照点"),
        ("限档", "降低等级"),
        ("主要包", "主要成果"),
        ("档内规则", "同一尺度"),
        ("档内", "同级"),
        ("裁为", "判断为"),
        ("合同", "规定"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = re.sub(r"[（(]\s*[）)]", "", text)
    text = re.sub(r"依据\s*[:：]\s*；?[^。；]*[。；]?", "", text)
    text = re.sub(r"([0-6])档", r"第\1级", text)
    text = re.sub(r"三轴[0-9/]+、整体水平", "三个方面的整体水平", text)
    text = re.sub(r"（([^（）]*)[，,；、]\s*）", r"（\1）", text)
    text = text.replace("不足或", "证据不足，")
    text = text.replace("保；", "已保留；")
    text = text.replace("由降", "由较高水平降至中位")
    text = re.sub(r"[；，、,]\s*[；，、,。]+", "；", text)
    text = re.sub(r"；\s*。", "。", text)
    text = re.sub(r"。\s*。+", "。", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" ；，、,。:：")
    if not re.search(r"[\u4e00-\u9fff0-9]", text):
        return ""
    return text


def _first_text(*values: object) -> str:
    for value in values:
        text = _clean_public_text(value)
        if text:
            return text
    return ""


def _strip_internal_tail(value: object) -> str:
    text = _clean_public_text(value)
    text = re.sub(r"(?:三轴|三个方面)的整体水平.*$", "", text)
    return text.strip(" ；，、,。:：")


def _number(value: object) -> float:
    if isinstance(value, bool) or value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _level_number(value: object) -> int | None:
    text = str(value or "")
    for pattern in (r"S([0-6])", r"[-/]([0-6])", r"([0-6])$"):
        matches = re.findall(pattern, text)
        if matches:
            return int(matches[-1])
    matches = re.findall(r"([0-6])", text)
    return int(matches[-1]) if matches else None


def _level_label(value: object, fallback: str = "未单列等级") -> str:
    number = _level_number(value)
    return LEVEL_LABELS.get(number, fallback)


def _band_label(value: object) -> str:
    return BAND_LABELS.get(str(value or ""), "")


def _stable_id(prefix: str, ruler_id: object, key: object) -> str:
    raw = f"{prefix}|{ruler_id or ''}|{key}".encode("utf-8")
    return f"{prefix}-PUBLIC-" + hashlib.sha256(raw).hexdigest()[:16].upper()


def _item(
    prefix: str,
    ruler_id: object,
    key: object,
    label: str,
    role: str,
    basis: object,
    boundary: str,
) -> dict[str, str]:
    return {
        "id": _stable_id(prefix, ruler_id, key),
        "public_label": _clean_public_text(label) or "公开依据",
        "public_role": _clean_public_text(role) or "依据",
        "public_basis": _clean_public_text(basis) or "正式记录没有保留可直述的独立事实。",
        "public_boundary": _clean_public_text(boundary) or "公开层只展示当前正式记录能够支持的范围。",
    }


def _projection(
    *,
    summary: object,
    items: list[dict[str, str]],
    boundary: str,
    level_label: str,
    component_label: str,
    axis_projections: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cleaned_summary = _clean_public_text(summary) or "正式记录没有保留可直述的独立裁决说明。"
    result: dict[str, Any] = {
        "public_adjudication_summary": cleaned_summary,
        "public_evidence_items": items,
        "public_boundary": _clean_public_text(boundary),
        "public_level_label": _clean_public_text(level_label),
        "public_component_label": _clean_public_text(component_label),
    }
    if axis_projections is not None:
        result["public_axis_projections"] = axis_projections
    return result


def _apply_projection(target: dict[str, Any], projection: dict[str, Any]) -> None:
    for key in list(target):
        if key.startswith("public_"):
            target.pop(key, None)
    target.update(copy.deepcopy(projection))


def _records(payload: dict[str, Any], key: str = "records") -> list[dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"正式公开投影记录集合无效：{key}")
    return rows


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {str(row.get("ruler_id")): row for row in rows if row.get("ruler_id")}
    if len(result) != len(rows):
        raise ValueError("正式公开投影人物ID缺失或重复")
    return result


def _package_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {str(row.get("package_code")): row for row in rows if row.get("package_code")}
    if len(result) != len(rows):
        raise ValueError("正式公开投影证据包代码缺失或重复")
    return result


def _without_public(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_public(child)
            for key, child in value.items()
            if not key.startswith("public_")
        }
    if isinstance(value, list):
        return [_without_public(child) for child in value]
    return value


def _signature(value: Any) -> str:
    return json.dumps(
        _without_public(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_public_strings(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.startswith("public_projection"):
                continue
            if key.startswith("public_") and key not in PUBLIC_PROJECTION_FIELDS:
                # Some historical formal records already contain machine-side
                # ``public_*`` bookkeeping.  Only this module's projection
                # fields are subject to the public-language contract.
                continue
            child_path = f"{path}.{key}" if path else str(key)
            if key.startswith("public_") and isinstance(child, str):
                if not child.strip() or PUBLIC_FORBIDDEN_RE.search(child):
                    raise ValueError(f"公开字段含空值或内部术语：{child_path}={child!r}")
            _validate_public_strings(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_public_strings(child, f"{path}[{index}]")


def _validate_evidence(items: object, *, prefix: str, ruler_id: str) -> None:
    if not isinstance(items, list) or not items:
        raise ValueError(f"公开依据为空：{prefix}/{ruler_id}")
    ids = [str(item.get("id") or "") for item in items if isinstance(item, dict)]
    if len(ids) != len(items) or len(ids) != len(set(ids)):
        raise ValueError(f"公开依据ID缺失或重复：{prefix}/{ruler_id}")
    for item in items:
        if not isinstance(item, dict) or set(item) != set(PUBLIC_EVIDENCE_FIELDS):
            raise ValueError(f"公开依据字段不完整：{prefix}/{ruler_id}")
        if "-PUBLIC-" not in str(item["id"]):
            raise ValueError(f"公开依据ID不稳定：{prefix}/{ruler_id}")
        for field in PUBLIC_EVIDENCE_FIELDS[1:]:
            value = item[field]
            if not isinstance(value, str) or not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
                raise ValueError(f"公开依据含内部术语：{prefix}/{ruler_id}/{field}")


def _verify_projection_fields(row: dict[str, Any], *, prefix: str, ruler_id: str) -> None:
    summary = row.get("public_adjudication_summary")
    boundary = row.get("public_boundary")
    level = row.get("public_level_label")
    component = row.get("public_component_label")
    for name, value in (
        ("public_adjudication_summary", summary),
        ("public_boundary", boundary),
        ("public_level_label", level),
        ("public_component_label", component),
    ):
        if not isinstance(value, str) or not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
            raise ValueError(f"公开字段缺失或含内部术语：{prefix}/{ruler_id}/{name}")
    _validate_evidence(row.get("public_evidence_items"), prefix=prefix, ruler_id=ruler_id)


def _ab_axis_projection(axis: str, row: dict[str, Any], ruler_id: str) -> dict[str, Any]:
    raw = _first_text(row.get("reason"), row.get("rationale"), row.get("attribution_basis"))
    if axis in {"A1", "A2"}:
        start = _level_label(row.get("start"))
        end = _level_label(row.get("end"))
        prefix = f"接手时为{start}，结束时为{end}。"
    else:
        level = _level_label(row.get("grade"))
        band = _band_label(row.get("band_position"))
        prefix = f"当前结果为{level}{f'、{band}' if band else ''}。"
    basis = f"{prefix}{raw}" if raw else f"{prefix}正式记录保留了本轴的当前结果。"
    item = _item(
        "THIRD-" + axis,
        ruler_id,
        "result",
        THIRD_AXIS_LABELS[axis],
        THIRD_AXIS_ROLES[axis],
        basis,
        THIRD_BOUNDARIES[axis],
    )
    return _projection(
        summary=f"{THIRD_AXIS_LABELS[axis]}为{item['public_basis']}",
        items=[item],
        boundary=THIRD_BOUNDARIES[axis],
        level_label=prefix.rstrip("。"),
        component_label=THIRD_AXIS_LABELS[axis],
    )


def _ab_projection(row: dict[str, Any]) -> dict[str, Any]:
    ruler_id = str(row.get("ruler_id") or "")
    axes = row.get("axes") if isinstance(row.get("axes"), dict) else {}
    axis_projections: dict[str, dict[str, Any]] = {}
    items: list[dict[str, str]] = []
    for axis in ("A1", "A2", "B1", "B2", "B4"):
        if not isinstance(axes.get(axis), dict):
            continue
        projection = _ab_axis_projection(axis, axes[axis], ruler_id)
        _apply_projection(axes[axis], projection)
        axis_projections[axis] = projection
        items.append(
            _item(
                "THIRD-AB",
                ruler_id,
                axis,
                projection["public_component_label"],
                projection["public_evidence_items"][0]["public_role"],
                projection["public_evidence_items"][0]["public_basis"],
                projection["public_boundary"],
            )
        )
    summary = "；".join(item["public_basis"] for item in items)
    summary = summary or "战略安全与边疆控制结果由威胁变化、防线协同、实际控制和稳定交付共同形成。"
    summary += " 本人战略选择、国家资源配置与具体将领执行按各自事实区分。"
    return _projection(
        summary=summary,
        items=items or [
            _item(
                "THIRD-AB",
                ruler_id,
                "overall",
                "战略安全总体结果",
                "总体结果",
                summary,
                "这里只展示当前正式记录能够支持的安全与控制事实，不把其他项目的成果重复计入。",
            )
        ],
        boundary="战略安全、边疆控制与具体将领执行分别说明；统一创业存量、继任者阶段和同一成果不重复计入。",
        level_label="战略安全与边疆控制结果",
        component_label="战略安全与边疆控制",
        axis_projections=axis_projections,
    )


def _credit_axis_projection(axis: str, row: dict[str, Any], ruler_id: str) -> dict[str, Any]:
    start = _level_label(row.get("start_grade"))
    end = _level_label(row.get("end_grade"))
    attribution = ATTRIBUTION_LABELS.get(str(row.get("attribution_category") or ""), "本人责任按正式记录区分")
    basis = _first_text(row.get("attribution_basis"), row.get("settlement_type_basis"))
    text = f"接手时为{start}，结束时为{end}。{basis or '正式记录保留了起点、终点和责任范围。'} {attribution}。"
    item = _item(
        "THIRD-" + axis,
        ruler_id,
        "result",
        THIRD_AXIS_LABELS[axis],
        "本人责任结果",
        text,
        THIRD_BOUNDARIES[axis],
    )
    return _projection(
        summary=text,
        items=[item],
        boundary=THIRD_BOUNDARIES[axis],
        level_label=f"结束时{end}安全水平",
        component_label=THIRD_AXIS_LABELS[axis],
    )


def _credit_projection(row: dict[str, Any]) -> dict[str, Any]:
    ruler_id = str(row.get("ruler_id") or "")
    axes = row.get("axes") if isinstance(row.get("axes"), dict) else {}
    axis_projections: dict[str, dict[str, Any]] = {}
    items: list[dict[str, str]] = []
    for axis in ("A1", "A2"):
        if not isinstance(axes.get(axis), dict):
            continue
        projection = _credit_axis_projection(axis, axes[axis], ruler_id)
        _apply_projection(axes[axis], projection)
        axis_projections[axis] = projection
        items.append(
            _item(
                "THIRD-CREDIT",
                ruler_id,
                axis,
                projection["public_component_label"],
                "本人责任结果",
                projection["public_adjudication_summary"],
                projection["public_boundary"],
            )
        )
    b80 = row.get("B80_adjudication")
    if isinstance(b80, dict):
        b_items = []
        for axis, label in (("B1", "实际控制范围"), ("B2", "战略成果价值"), ("B4", "控制成果稳定性")):
            rate = b80.get(f"adjudicated_{axis}_rate")
            b_items.append(
                _item(
                    "THIRD-CREDIT-B80",
                    ruler_id,
                    axis,
                    label,
                    "合成采用比例",
                    f"正式合成采用比例为{_number(rate):g}%，用于表达该方面在控制成果合成中的实际权重。",
                    THIRD_BOUNDARIES[axis],
                )
            )
        b_projection = _projection(
            summary="；".join(item["public_basis"] for item in b_items),
            items=b_items,
            boundary="三类控制成果按正式比例合成；同一控制对象、继承存量和其他项目结果不重复计入。",
            level_label="控制成果合成比例",
            component_label="控制成果合成",
        )
        _apply_projection(b80, b_projection)
        items.extend(b_items)
    summary = "；".join(item["public_basis"] for item in items) or "正式记录没有保留可直述的战略安全变化。"
    return _projection(
        summary=summary,
        items=items or [
            _item(
                "THIRD-CREDIT",
                ruler_id,
                "overall",
                "战略结果归属",
                "总体边界",
                "正式记录没有保留可直述的战略安全变化。",
                "这里只展示当前正式记录能够支持的结果。",
            )
        ],
        boundary="起点、终点、本人责任和合成比例分别保留；不把同一安全结果在不同轴重复计算。",
        level_label="战略结果归属与合成",
        component_label="战略结果归属",
        axis_projections=axis_projections,
    )


def _c_axis_projection(axis: str, row: dict[str, Any], ruler_id: str) -> dict[str, Any]:
    grade_key = {
        "C1": "combat_delivery_grade",
        "C2": "operational_sustainability_cap",
        "C3": "system_reliability_cap",
    }[axis]
    level = _level_label(row.get(grade_key))
    profile = row.get("task_outcome_profile") if isinstance(row.get("task_outcome_profile"), dict) else {}
    count_text = ""
    if profile:
        selected = int(_number(profile.get("selected_task_count")))
        high = int(_number((profile.get("return_class_counts") or {}).get("HIGH_RETURN")))
        low = int(_number((profile.get("return_class_counts") or {}).get("LOW_RETURN")))
        negative = int(_number((profile.get("return_class_counts") or {}).get("NEGATIVE_RETURN")))
        count_text = f"已核对{selected}项独立任务，其中较好结果{high}项、低回报{low}项、负向结果{negative}项。"
    raw = _strip_internal_tail(
        _first_text(
        row.get("strategy_chain_review_basis"),
        row.get("current_task_basis_reason"),
        row.get("cap_reasons"),
        )
    )
    if not raw:
        raw = "正式记录保留了该方面的军事体系结果。"
    attribution = "本人承担国家战略选择和军政资源配置责任；具体统帅执行按各自事实区分。"
    basis = f"该方面为{level}水平。{count_text}{raw} {attribution}"
    item = _item(
        "THIRD-" + axis,
        ruler_id,
        "result",
        THIRD_AXIS_LABELS[axis],
        THIRD_AXIS_ROLES[axis],
        basis,
        THIRD_BOUNDARIES[axis],
    )
    return _projection(
        summary=basis,
        items=[item],
        boundary=THIRD_BOUNDARIES[axis],
        level_label=f"{THIRD_AXIS_LABELS[axis]}为{level}",
        component_label=THIRD_AXIS_LABELS[axis],
    )


def _c_projection(row: dict[str, Any]) -> dict[str, Any]:
    ruler_id = str(row.get("ruler_id") or "")
    projections: dict[str, dict[str, Any]] = {}
    items: list[dict[str, str]] = []
    for axis in ("C1", "C2", "C3"):
        projection = _c_axis_projection(axis, row, ruler_id)
        projections[axis] = projection
        items.append(
            _item(
                "THIRD-C",
                ruler_id,
                axis,
                projection["public_component_label"],
                projection["public_evidence_items"][0]["public_role"],
                projection["public_evidence_items"][0]["public_basis"],
                projection["public_boundary"],
            )
        )
    overall = _level_label(row.get("C_overall_grade"))
    basis = _strip_internal_tail(_first_text(row.get("strategy_chain_review_basis"), row.get("current_task_basis_reason")))
    summary = f"军事体系整体为{overall}水平。{basis or '实战交付、持续承载和体系可靠性共同形成当前结果。'} 本人战略责任与具体统帅执行按事实区分。"
    return _projection(
        summary=summary,
        items=items,
        boundary="军事体系只看本人责任窗口内的实战交付、持续承载与可靠性；创业能力、单名将执行和同一战略链不重复计入。",
        level_label=f"军事体系整体为{overall}水平",
        component_label="军事体系整体结果",
        axis_projections=projections,
    )


def _cost_projection(profile: dict[str, Any], ruler_id: str, *, prefix: str = "THIRD-COST") -> dict[str, Any]:
    band = _level_label(profile.get("cost_band"))
    position = _band_label(profile.get("position"))
    basis = _first_text(profile.get("basis")) or "正式记录没有保留可直述的普通军事代价事实。"
    summary = f"普通军事代价为{band}{f'、{position}' if position else ''}。{basis}"
    boundary = (
        "普通军事代价只记录本人统治窗口内本方军队、军事资产、后勤与持续动员的实际承载；"
        "重大净毁损追加判断使用同一损失时不再重复扣减，外部行动和非军事成本不并入。"
    )
    item = _item(prefix, ruler_id, "cost", "普通军事代价", "本方军事承载", summary, boundary)
    return _projection(
        summary=summary,
        items=[item],
        boundary=boundary,
        level_label=f"普通军事代价为{band}{f'、{position}' if position else ''}",
        component_label="普通军事代价",
    )


def _ml_projection(row: dict[str, Any], ruler_id: str, *, prefix: str = "THIRD-ML") -> dict[str, Any]:
    grade = str(row.get("grade") or row.get("military_net_loss_grade") or "ML0")
    label = ML_LABELS.get(grade, "重大军事净毁损按正式记录保留")
    attribution = ATTRIBUTION_LABELS.get(
        str(row.get("military_net_loss_attribution") or ""),
        "正式记录区分外部压力、共同原因和本人责任",
    )
    basis = _first_text(row.get("basis"), row.get("military_net_loss_basis"))
    if grade == "ML0":
        summary = f"{label}。现有材料没有同时确认重大安全结果、较高本方军事代价和足够本人责任，因此不追加重大军事净毁损扣减。"
    else:
        summary = f"{label}。{basis or '现有材料确认达到重大结果、较高本方代价和本人责任条件。'} {attribution}。"
    boundary = THIRD_BOUNDARIES["ML"]
    item = _item(prefix, ruler_id, "loss", "重大军事净毁损", "重大损失判断", summary, boundary)
    return _projection(
        summary=summary,
        items=[item],
        boundary=boundary,
        level_label=label,
        component_label="重大军事净毁损",
    )


def _d_projection(row: dict[str, Any]) -> dict[str, Any]:
    ruler_id = str(row.get("ruler_id") or "")
    profile = row.get("attributable_cost_profile")
    profile = profile if isinstance(profile, dict) else {}
    cost = _cost_projection(profile, ruler_id, prefix="THIRD-D-COST")
    _apply_projection(profile, cost)
    row["attributable_cost_profile"] = profile
    external_count = len(row.get("external_strategic_chains") or [])
    internal_count = len(row.get("strategic_internal_chains") or [])
    result_basis = _first_text(row.get("adjudication_basis")) or "正式记录保留了战略结果组合。"
    items = [
        _item(
            "THIRD-D",
            ruler_id,
            "result",
            "战略结果组合",
            "战略结果",
            f"正式记录列出{external_count}条外部战略结果链和{internal_count}条内部军事链。{result_basis}",
            "不同战略目标、阶段结果和内部代价分别说明；同一终局、区域恢复和重复动员不重复计算。",
        ),
        cost["public_evidence_items"][0],
        _item(
            "THIRD-D",
            ruler_id,
            "responsibility",
            "责任与重复计算边界",
            "责任边界",
            "国家战略结果、具体统帅执行和本方军事代价分别保留，不能用单一终局名称替代责任判断。",
            "D项结果不把普通军事代价和重大净毁损重复写成两次损失。",
        ),
    ]
    summary = f"战略结果由{external_count}条外部结果链和{internal_count}条内部军事链共同构成。{result_basis}"
    return _projection(
        summary=summary,
        items=items,
        boundary="战略结果、具体执行、普通军事代价和重大净毁损按各自对象说明，不把同一阶段结果重复计算。",
        level_label=f"战略结果为{_level_label(row.get('D_grade'))}",
        component_label="战略结果与军事代价",
    )


def _third_projection(row: dict[str, Any], ab: dict[str, Any], credit: dict[str, Any], c: dict[str, Any], d: dict[str, Any], ml: dict[str, Any] | None) -> dict[str, Any]:
    ruler_id = str(row.get("ruler_id") or "")
    cost_profile = row.get("global_cost_credit_profile")
    cost_profile = cost_profile if isinstance(cost_profile, dict) else {}
    cost = _cost_projection(cost_profile, ruler_id)
    _apply_projection(cost_profile, cost)
    row["global_cost_credit_profile"] = cost_profile
    ml_source = ml or {}
    ml_data = {
        "ruler_id": ruler_id,
        "ruler_name": row.get("ruler_name"),
        "grade": row.get("military_net_loss_grade"),
        "military_net_loss_grade": row.get("military_net_loss_grade"),
        "military_net_loss_attribution": row.get("military_net_loss_attribution"),
        "military_net_loss_basis": row.get("military_net_loss_basis"),
        "basis": ml_source.get("basis") or row.get("military_net_loss_basis"),
    }
    loss = _ml_projection(ml_data, ruler_id, prefix="THIRD-ML")
    ab_summary = _first_text(ab.get("public_adjudication_summary"), credit.get("public_adjudication_summary"))
    c_summary = _first_text(c.get("public_adjudication_summary"))
    items = [
        _item(
            "THIRD-TOTAL",
            ruler_id,
            "strategic",
            "战略安全结果",
            "实际安全结果与本人责任",
            ab_summary or "正式记录保留了战略安全与边疆控制结果。",
            "战略安全结果只来自本人窗口内的正式战略记录，不把统一创业存量和继任者阶段重复计入。",
        ),
        _item(
            "THIRD-TOTAL",
            ruler_id,
            "system",
            "军事体系实际交付与可靠性",
            "体系表现",
            c_summary or "正式记录保留了实战交付、持续承载和体系可靠性结果。",
            "体系表现与具体统帅执行、战略安全成果分开说明，不把同一战略链重复计入。",
        ),
        cost["public_evidence_items"][0],
        loss["public_evidence_items"][0],
        _item(
            "THIRD-TOTAL",
            ruler_id,
            "boundary",
            "本项重复计算边界",
            "重复计算边界",
            "战略成果、军事体系表现和军事代价分别记录；普通军事代价与重大军事净毁损只取需要扣减的较高者。",
            "本项不把同一损失、后继者独立行动、非军事成本或其他评价体系结果重复扣减。",
        ),
    ]
    summary = "；".join(item["public_basis"] for item in items[:4])
    projection = _projection(
        summary=summary,
        items=items,
        boundary="战略安全结果、军事体系表现、普通军事代价和重大军事净毁损各有对象；普通代价与重大净毁损不重复扣减。",
        level_label="第三项军事与边疆净收益正式结果",
        component_label="第三项军事与边疆净收益",
    )
    projection["public_military_cost"] = copy.deepcopy(cost)
    projection["public_military_net_loss"] = copy.deepcopy(loss)
    return projection


def _refresh_third(payloads: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    ab_rows = _index(_records(payloads["AB"]))
    c_rows = _index(_records(payloads["C"]))
    d_rows = _index(_records(payloads["D"]))
    credit_rows = _index(_records(payloads["credit"]))
    ml_rows = _index(_records(payloads["ML"]))
    total_rows = _index(_records(payloads["total"]))
    ids = set(total_rows)
    if not ids or any(set(rows) != ids for rows in (ab_rows, c_rows, d_rows, credit_rows)):
        raise ValueError("第三项公开投影组件人物集合不一致")
    for row in ab_rows.values():
        _apply_projection(row, _ab_projection(row))
    for row in credit_rows.values():
        _apply_projection(row, _credit_projection(row))
    for row in c_rows.values():
        _apply_projection(row, _c_projection(row))
    for row in d_rows.values():
        _apply_projection(row, _d_projection(row))
    for row in ml_rows.values():
        _apply_projection(row, _ml_projection(row, str(row.get("ruler_id") or "")))
    for ruler_id, row in total_rows.items():
        _apply_projection(
            row,
            _third_projection(row, ab_rows[ruler_id], credit_rows[ruler_id], c_rows[ruler_id], d_rows[ruler_id], ml_rows.get(ruler_id)),
        )
    for key, payload in payloads.items():
        payload["public_projection_schema_version"] = PUBLIC_PROJECTION_SCHEMA
        payload["public_projection_status"] = "FORMAL_UPSTREAM_SOURCE"
        payload["public_projection_source"] = {
            "formal_contract": "docs/分项规则/第三项军事与边疆净收益/00-规则与计分合同.md"
            if key != "fourth"
            else "docs/分项规则/第四项文明与国家整合收益/00-规则与计分合同.md",
            "reader_policy": "reader只显示public_adjudication_summary、public_evidence_items和public_boundary",
        }
    payloads["AB"]["public_projection_record_count"] = len(ab_rows)
    payloads["C"]["public_projection_record_count"] = len(c_rows)
    payloads["D"]["public_projection_record_count"] = len(d_rows)
    payloads["credit"]["public_projection_record_count"] = len(credit_rows)
    payloads["ML"]["public_projection_record_count"] = len(ml_rows)
    payloads["total"]["public_projection_record_count"] = len(total_rows)
    return payloads


def _package_projection(package: dict[str, Any]) -> dict[str, Any]:
    ruler_id = str(package.get("ruler_id") or "")
    axis = str(package.get("axis") or "")
    direction = DIRECTION_LABELS.get(str(package.get("direction") or ""), "结果方向未单列")
    attribution = ATTRIBUTION_LABELS.get(str(package.get("attribution_strength") or ""), "责任范围按正式记录区分")
    change = _first_text(package.get("attributable_change")) or "正式记录没有保留可直述的本人窗口变化。"
    baseline = _first_text(package.get("inherited_baseline"))
    counter = package.get("counterevidence")
    counter_text = _first_text(counter.get("summary") if isinstance(counter, dict) else counter)
    basis = f"{direction}：{change}。{f'相对既有状态：{baseline}。' if baseline else ''}{attribution}。"
    if counter_text:
        basis += f"补充限制：{counter_text}。"
    boundary = CIVILIZATION_BOUNDARIES.get(axis, "这里只展示本人窗口内能够确认的文明与国家整合变化，不把后世独立发展重复归入本人。")
    level = RELATIVE_CHANGE_LABELS.get(str(package.get("relative_change_level") or ""), "正式记录保留的变化水平")
    item = _item(
        "FOURTH-PACKAGE",
        ruler_id,
        str(package.get("package_code") or axis),
        CIVILIZATION_AXIS_LABELS.get(axis, "文明与国家整合变化"),
        direction,
        basis,
        boundary,
    )
    return _projection(
        summary=basis,
        items=[item],
        boundary=boundary,
        level_label=f"{level}，{direction}",
        component_label=CIVILIZATION_AXIS_LABELS.get(axis, "文明与国家整合变化"),
    )


def _fourth_axis_projection(row: dict[str, Any], axis: str, packages: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ruler_id = str(row.get("ruler_id") or "")
    refs = [str(ref) for ref in row.get("package_refs") or () if ref]
    package_projections = []
    for ref in refs:
        package = packages.get(ref)
        if package is None:
            continue
        package_projections.append(_package_projection(package))
    if package_projections:
        items = [projection["public_evidence_items"][0] for projection in package_projections]
        direction = DIRECTION_LABELS.get(str(row.get("direction") or ""), "结果方向未单列")
        summary = f"{CIVILIZATION_AXIS_LABELS[axis]}为{direction}。" + "；".join(
            projection["public_adjudication_summary"] for projection in package_projections
        )
        level = CIV_MAGNITUDE_LABELS.get(str(row.get("magnitude_grade") or ""), "正式记录保留的影响幅度")
    else:
        items = [
            _item(
                "FOURTH-AXIS",
                ruler_id,
                f"{axis}-no-independent-change",
                CIVILIZATION_AXIS_LABELS[axis],
                "没有确认独立变化",
                "正式材料没有确认本人窗口形成可以与既有状态区分的独立变化，因此本轴不形成单独调整。",
                CIVILIZATION_BOUNDARIES[axis],
            )
        ]
        summary = f"{CIVILIZATION_AXIS_LABELS[axis]}：正式材料没有确认本人窗口形成可以与既有状态区分的独立变化，因此本轴不形成单独调整。"
        level = "没有确认独立变化"
    return _projection(
        summary=summary,
        items=items,
        boundary=CIVILIZATION_BOUNDARIES[axis],
        level_label=level,
        component_label=CIVILIZATION_AXIS_LABELS[axis],
    )


def _fourth_projection(row: dict[str, Any], packages: dict[str, dict[str, Any]]) -> dict[str, Any]:
    axes = {str(axis.get("axis")): axis for axis in row.get("axis_results") or () if isinstance(axis, dict)}
    axis_projections: dict[str, dict[str, Any]] = {}
    items: list[dict[str, str]] = []
    for axis in "ABC":
        if not isinstance(axes.get(axis), dict):
            continue
        projection = _fourth_axis_projection(axes[axis], axis, packages)
        _apply_projection(axes[axis], projection)
        axis_projections[axis] = projection
        items.extend(projection["public_evidence_items"])
    summary = "；".join(
        projection["public_adjudication_summary"] for projection in axis_projections.values()
    ) or "正式记录没有保留可直述的文明与国家整合结果。"
    return _projection(
        summary=summary,
        items=items or [
            _item(
                "FOURTH-RECORD",
                row.get("ruler_id"),
                "overall",
                "文明与国家整合总体结果",
                "总体结果",
                summary,
                "三轴分别判断；不把同一变化在多个轴重复计算。",
            )
        ],
        boundary="国家共同体、教育与人才、知识与文化生态分别判断；继承存量、后世独立发展和同一成果不重复计入。",
        level_label="第四项文明与国家整合正式结果",
        component_label="第四项文明与国家整合",
        axis_projections=axis_projections,
    )


def _refresh_fourth(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _records(payload)
    package_rows = _records(payload, "accepted_packages")
    packages = _package_index(package_rows) if package_rows else {}
    for package in package_rows:
        _apply_projection(package, _package_projection(package))
    for row in rows:
        _apply_projection(row, _fourth_projection(row, packages))
    payload["public_projection_schema_version"] = PUBLIC_PROJECTION_SCHEMA
    payload["public_projection_status"] = "FORMAL_UPSTREAM_SOURCE"
    payload["public_projection_record_count"] = len(rows)
    payload["public_projection_package_count"] = len(package_rows)
    payload["public_projection_source"] = {
        "formal_contract": "docs/分项规则/第四项文明与国家整合收益/00-规则与计分合同.md",
        "reader_policy": "reader只显示public_adjudication_summary、public_evidence_items和public_boundary",
    }
    return payload


def _load_payloads(root: Path) -> dict[str, dict[str, Any]]:
    return {
        "AB": load_json(root / THIRD_AB_PATH),
        "C": load_json(root / THIRD_C_PATH),
        "D": load_json(root / THIRD_D_PATH),
        "credit": load_json(root / THIRD_CREDIT_PATH),
        "ML": load_json(root / THIRD_ML_PATH),
        "total": load_json(root / THIRD_TOTAL_PATH),
        "fourth": load_json(root / FOURTH_PATH),
    }


def _verify_third(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    before = {key: _signature(value) for key, value in payloads.items() if key != "fourth"}
    expected = _refresh_third(copy.deepcopy({key: value for key, value in payloads.items() if key != "fourth"}))
    for key, payload in payloads.items():
        if key == "fourth":
            continue
        if _signature(payload) != before[key]:
            raise ValueError(f"第三项公开字段改变了正式评分字段：{key}")
        if _signature(payload) != _signature(expected[key]):
            raise ValueError(f"第三项公开字段不是当前正式记录的确定性投影：{key}")
        _validate_public_strings(payload)
    total_rows = _index(_records(payloads["total"]))
    for key in ("AB", "C", "D", "credit"):
        rows = _index(_records(payloads[key]))
        if set(rows) != set(total_rows):
            raise ValueError(f"第三项公开投影人物集合不一致：{key}")
        for ruler_id, row in rows.items():
            _verify_projection_fields(row, prefix="THIRD", ruler_id=ruler_id)
    for ruler_id, row in total_rows.items():
        _verify_projection_fields(row, prefix="THIRD-TOTAL", ruler_id=ruler_id)
        _verify_projection_fields(row["global_cost_credit_profile"], prefix="THIRD-COST", ruler_id=ruler_id)
        _verify_projection_fields(row["public_military_net_loss"], prefix="THIRD-ML", ruler_id=ruler_id)
    ml_rows = _index(_records(payloads["ML"]))
    for ruler_id, row in ml_rows.items():
        _verify_projection_fields(row, prefix="THIRD-ML", ruler_id=ruler_id)
    return {
        "status": "PASS",
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
        "record_count": len(total_rows),
        "source_record_counts": {key: len(_records(payloads[key])) for key in ("AB", "C", "D", "credit", "ML", "total")},
    }


def _verify_fourth(payload: dict[str, Any]) -> dict[str, Any]:
    before = _signature(payload)
    expected = _refresh_fourth(copy.deepcopy(payload))
    if before != _signature(payload):
        raise ValueError("第四项公开校验内部签名异常")
    if _signature(payload) != _signature(expected):
        raise ValueError("第四项公开字段不是当前正式记录的确定性投影")
    _validate_public_strings(payload)
    rows = _records(payload)
    packages = _records(payload, "accepted_packages")
    for row in rows:
        ruler_id = str(row.get("ruler_id") or "")
        _verify_projection_fields(row, prefix="FOURTH-RECORD", ruler_id=ruler_id)
        axes = {str(axis.get("axis")): axis for axis in row.get("axis_results") or () if isinstance(axis, dict)}
        for axis in "ABC":
            if axis in axes:
                _verify_projection_fields(axes[axis], prefix="FOURTH-AXIS", ruler_id=f"{ruler_id}/{axis}")
    for package in packages:
        _verify_projection_fields(package, prefix="FOURTH-PACKAGE", ruler_id=str(package.get("ruler_id") or ""))
    return {
        "status": "PASS",
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
        "record_count": len(rows),
        "package_count": len(packages),
    }


def verify_public_projection(workspace_root: Path) -> dict[str, Any]:
    root = workspace_root.resolve()
    payloads = _load_payloads(root)
    third = _verify_third(payloads)
    fourth = _verify_fourth(payloads["fourth"])
    if third["record_count"] != fourth["record_count"]:
        raise ValueError("第三项与第四项公开投影人物数量不一致")
    return {
        "status": "PASS",
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
        "third_item": third,
        "fourth_item": fourth,
    }


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    root = workspace_root.resolve()
    current = _load_payloads(root)
    third_current = {key: value for key, value in current.items() if key != "fourth"}
    projected_third = _refresh_third(copy.deepcopy(third_current))
    projected_fourth = _refresh_fourth(copy.deepcopy(current["fourth"]))
    if write:
        polities = load_ruler_polities(root)
        for key, path in THIRD_ROUTED_PATHS.items():
            write_json(root / path, projected_third[key], ruler_polities=polities)
        for key in ("credit", "ML", "total"):
            path = {
                "credit": THIRD_CREDIT_PATH,
                "ML": THIRD_ML_PATH,
                "total": THIRD_TOTAL_PATH,
            }[key]
            write_json(root / path, projected_third[key])
        write_json(root / FOURTH_PATH, projected_fourth, ruler_polities=polities)
        report = verify_public_projection(root)
        report["status"] = "WRITTEN"
        return report
    if projected_third != third_current or projected_fourth != current["fourth"]:
        raise ValueError("第三/第四项正式公开投影未同步；请运行third-fourth-item-public --write")
    return verify_public_projection(root)
