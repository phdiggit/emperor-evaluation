"""Build and verify the formal public projection for Second Item C1-C4."""
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


FORMAL_PATHS = {
    "C1": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/01-C1正式结算.json"),
    "C2": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/02-C2正式结算.json"),
    "C3": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/03-C3正式结算.json"),
    "C4": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/04-C4正式结算.json"),
}
CONTRACT_PATH = Path("docs/分项规则/第二项治国净收益/财政民生/00-规则与结算合同.md")
PUBLIC_PROJECTION_SCHEMA = "second-item-c-public-projection-v1"
AXES = ("C1", "C2", "C3", "C4")
STATE_AXES = ("C1", "C2", "C3")

PUBLIC_EVIDENCE_FIELDS = (
    "id",
    "public_label",
    "public_role",
    "public_basis",
    "public_boundary",
)
PUBLIC_ROLES = {
    "主要状态",
    "低谷",
    "边界",
    "恢复",
    "责任范围",
    "状态恶化",
    "额外代价",
}

AXIS_NAMES = {
    "C1": "民生",
    "C2": "经济财政",
    "C3": "社会安全",
}
STATE_LABELS = {
    "C1": {
        1: "崩溃",
        2: "广泛困顿",
        3: "基本维持",
        4: "普遍温饱",
        5: "富庶",
        6: "极盛",
    },
    "C2": {
        1: "失灵崩解",
        2: "汲取脆弱",
        3: "基本运行",
        4: "健康稳定",
        5: "富实强健",
        6: "结构顶峰",
    },
    "C3": {
        1: "广域失序",
        2: "持续脆弱",
        3: "可运行秩序",
        4: "总体稳定",
        5: "长期高位",
        6: "结构顶峰",
    },
}
LOSS_LABELS = {
    "L0": "未另证独立有效低谷",
    "L1": "有界局部或短时损害",
    "L2": "重要地区或群体出现明显损害",
    "L3": "严重且广泛或长期反复的本轴损害",
}
DA_LABELS = {
    "DA0": "未确认独立的额外民力成本",
    "DA1": "有限的额外民力成本",
    "DA2": "显著的额外民力成本",
    "DA3": "严重的额外民力成本",
    "DA4": "极重的额外民力成本",
    "DA5": "接近系统性汲取的额外民力成本",
    "DA6": "灾难级的额外民力成本",
}

AXIS_BOUNDARIES = {
    "C1": "这里只展示普通家庭的衣食、家庭负担与家庭形成结果；战争胜负、纯军事损失、制度设计和后续继任结果不在本轴重复计算。",
    "C2": "这里只展示生产、市场货币、常规税基与储备结果；家庭生活结果、治安司法、战争成本、恢复过程和制度设计不在本轴重复计算。",
    "C3": "这里只展示居民人身财产安全、基层秩序与司法救济结果；外部军事安全、粮价储备、制度设计和政权存续不在本轴重复计算。",
}
C4_BOUNDARY = "这里只展示本人责任期内的保留恢复、状态变化和独立额外民力成本；三个绝对状态轴、纯军事投入及同一已计后果不在本轴重复计算。"
RECOVERY_BOUNDARY = "只有任期结束时仍保留的改善进入恢复结果；短暂峰值、单纯止损和绝对状态本身不重复计算。"
RESPONSIBILITY_BOUNDARY = "恢复责任按实际权力分工判断，不从名义身份、结果好坏或继任结果反推。"
DETERIORATION_BOUNDARY = "只比较接手到任期结束的可比状态；灾害、失权后的新损害和他人责任不直接归入本人。"
COST_BOUNDARY = "只保留已证的独立民力、生产机会或民间财产负担；纯军事投入和同一已计后果不重复计算。"

PUBLIC_FORBIDDEN_RE = re.compile(
    r"(?:"
    r"(?<![A-Za-z0-9])(?:C[1-4](?:-[1-6])?|C4T-[1-6]|L[0-3]|DA[0-6]|"
    r"S_(?:0|main|end|avg)|FULL|SHARED|NONE|RAW|M3)(?![A-Za-z0-9])|"
    r"(?<![A-Za-z0-9])[A-Za-z]+_[A-Za-z0-9_]+(?![A-Za-z0-9])|"
    r"C1\s*[—/-]\s*C3|C1\s*[、/]\s*C2|"
    r"主档|主态|低谷修正|门槛|闭合|消费|净账|父链|版本史|归责|"
    r"审计|正式结算|重审|重裁|本轮|恢复原|净分|终局层级|"
    r"(?<![A-Za-z0-9])V[0-9]+(?![A-Za-z0-9])|"
    r"governance|review|basis|source|status"
    r")",
    flags=re.IGNORECASE,
)


def _clean(value: object) -> str:
    """Turn formal shorthand into ordinary Chinese before it reaches readers."""

    text = str(value or "").replace("`", "").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\{\{.*?\}\}", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    text = re.sub(r"C4T-[1-6]", "任期末综合状态", text, flags=re.IGNORECASE)

    def state_code(match: re.Match[str]) -> str:
        axis, band = f"C{match.group(1).upper()}", int(match.group(2))
        return f"{AXIS_NAMES[axis]}{STATE_LABELS[axis].get(band, '当前状态')}"

    text = re.sub(r"(?<![A-Za-z0-9])C([123])[-/]([1-6])(?![A-Za-z0-9])", state_code, text)
    text = re.sub(r"(?<![A-Za-z0-9])C1\s*[/、]\s*C2\s*[/、]\s*C3(?![A-Za-z0-9])", "民生、经济财政与社会安全", text)
    text = re.sub(r"(?<![A-Za-z0-9])C1\s*[/、]\s*C2(?![A-Za-z0-9])", "民生与经济财政", text)
    text = re.sub(r"(?<![A-Za-z0-9])C([1234])(?![A-Za-z0-9])", lambda m: {
        "1": "民生",
        "2": "经济财政",
        "3": "社会安全",
        "4": "恢复与成本结果",
    }[m.group(1)], text)

    for code, label in LOSS_LABELS.items():
        text = re.sub(rf"(?<![A-Za-z0-9]){code}(?![A-Za-z0-9])", label, text)
    for code, label in DA_LABELS.items():
        text = re.sub(rf"(?<![A-Za-z0-9]){code}(?![A-Za-z0-9])", label, text)

    replacements = (
        (r"S_(?:0|s0)", "接手状态"),
        (r"S_(?:main|avg)", "主要阶段状态"),
        (r"S_end", "任期结束状态"),
        (r"FULL", "本人独立或主导"),
        (r"SHARED", "本人和其他掌权者共同承担"),
        (r"NONE", "本人责任不足"),
        (r"主档", "主要状态"),
        (r"主态", "主要状态"),
        (r"低谷修正", "低谷损害"),
        (r"去重", "避免重复计算"),
        (r"消费", "已计入"),
        (r"净恢复", "保留的恢复"),
        (r"净账|净分", "结果"),
        (r"闭合", "证明"),
        (r"门槛", "条件"),
        (r"归责", "本人责任"),
        (r"父链", "相关依据"),
        (r"(?<![A-Za-z0-9])raw(?![A-Za-z0-9])", "已有"),
        (r"旧已有", "旧判断"),
        (r"(?<![A-Za-z0-9])V[0-9]+(?:消费|已计入)?核对：?[^。；]*[。；]?", ""),
        (r"(?<![A-Za-z0-9])V[0-9]+(?![A-Za-z0-9])", ""),
        (r"本轮", "当前判断"),
        (r"恢复原", "恢复既有"),
        (r"raw锚点", "接手状态"),
        (r"C4净分", "恢复与成本结果"),
        (r"正向保留\s*[-+]?\d+(?:\.\d+)?分", "保留恢复"),
        (r"可归责恶化另扣\s*[-+]?\d+(?:\.\d+)?分", "本人责任期状态下降另行评估"),
        (r"最终(?:DA[0-6]|额外民力成本)[^。；]*", "额外成本判断"),
        (r"恢复原值\s*[-+]?\d+(?:\.\d+)?", "保留恢复"),
        (r"交班", "任期结束"),
        (r"本人窗口", "本人责任期"),
        (r"本人实际窗口", "本人责任期"),
        (r"C1—C3", "三个绝对状态轴"),
        (r"C1/C2/C3", "三个绝对状态轴"),
        (r"C1/C2", "民生与经济财政"),
        (r"P/R", "生产与储备"),
        (r"P面", "生产方面"),
        (r"M侧", "市场与货币方面"),
        (r"F/R面", "财政与储备方面"),
        (r"(?:GOVERNANCE|CIVILIAN|RECOVERY|FORMAL)[-_A-Z0-9]*", ""),
        (r"\b(?:REVIEWED|FORMAL_SYNCED|STRUCTURED|DIRECT|INFERRED|ACTIVE|CURRENT|UNKNOWN)\b", ""),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Process-history clauses are not public evidence. Keep the surrounding
    # historical result instead of exposing an implementation review narrative.
    text = re.sub(r"[^。；]*?(?:版本史|字段|审计|重审|重裁)[^。；]*[。；]", "", text)
    text = re.sub(r"[；，、]\s*[；，、]+", "；", text)
    text = re.sub(r"。\s*。+", "。", text)
    text = re.sub(r"；\s*。", "。", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ；，、：")


def _first_text(*values: object) -> str:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return ""


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _number(value: object) -> float:
    if isinstance(value, bool) or value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("scores") or payload.get("records") or []
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("C1-C4正式公开投影的记录集合无效")
    return rows


def _state_phrase(axis: str, value: object) -> str:
    match = re.fullmatch(r"C([123])[-/]([1-6])", str(value or "").strip())
    if not match or match.group(1) != axis[1:]:
        return f"{AXIS_NAMES[axis]}的当前状态"
    band = int(match.group(2))
    return f"{AXIS_NAMES[axis]}的{STATE_LABELS[axis][band]}状态"


def _stable_id(axis: str, row: dict[str, Any], key: str) -> str:
    raw = f"{axis}|{row.get('ruler_id', '')}|{key}".encode("utf-8")
    return f"{axis}-PUBLIC-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def _item(axis: str, row: dict[str, Any], key: str, label: str, role: str, basis: str, boundary: str) -> dict[str, str]:
    return {
        "id": _stable_id(axis, row, key),
        "public_label": label,
        "public_role": role,
        "public_basis": _clean(basis),
        "public_boundary": _clean(boundary),
    }


def _state_review(row: dict[str, Any]) -> dict[str, Any]:
    state = row.get("state_adjudication")
    return state if isinstance(state, dict) else {}


def _state_items(axis: str, row: dict[str, Any]) -> list[dict[str, str]]:
    state = _state_review(row)
    loss = state.get("loss_review") if isinstance(state.get("loss_review"), dict) else {}
    main = _first_text(
        loss.get("main_representativeness"),
        row.get("adjudication_reason"),
        row.get("stability_basis"),
    )
    if not main:
        main = "正式记录没有提供可进一步拆分的主要状态说明；公开层不补造历史判断。"

    grade = str(row.get("loss_grade") or loss.get("grade") or "").strip()
    if grade in LOSS_LABELS:
        low_basis = _first_text(loss.get("basis"), loss.get("deduplication"))
        if grade == "L0":
            low_basis = "未另证独立有效低谷；这不等于全任没有局部压力。"
        elif not low_basis:
            low_basis = "正式记录给出了低谷等级，但没有保留可直述的独立低谷说明；公开层不补造具体损害。"
        low = f"{LOSS_LABELS[grade]}：{low_basis}"
    else:
        low = "当前正式记录没有独立低谷裁决子块；公开层不对池外记录另行推断。"

    limitations = row.get("material_limitations") or []
    if not isinstance(limitations, list):
        limitations = [limitations]
    limitation_text = "；".join(_unique([_clean(value) for value in limitations]))
    boundary_basis = (
        f"当前人物的材料边界：{limitation_text}"
        if limitation_text
        else "当前人物没有另列材料边界；公开层仍遵守本轴对象范围。"
    )
    state_label = _state_phrase(axis, row.get("main_band"))
    return [
        _item(axis, row, "state", "主要状态", "主要状态", f"当前主要状态为{state_label}。{main}", AXIS_BOUNDARIES[axis]),
        _item(axis, row, "low", "低谷与损失", "低谷", low, AXIS_BOUNDARIES[axis]),
        _item(axis, row, "boundary", "评价边界", "边界", boundary_basis, AXIS_BOUNDARIES[axis]),
    ]


def _recovery_basis(row: dict[str, Any]) -> tuple[str, set[str]]:
    path = row.get("recovery_path_basis") or {}
    parts: list[str] = []
    recovered: set[str] = set()
    if isinstance(path, dict):
        for axis in STATE_AXES:
            detail = path.get(axis)
            if not isinstance(detail, dict):
                continue
            retained = bool(detail.get("retained_increment")) or _number(detail.get("linear_delta")) > 0
            if not retained:
                continue
            recovered.add(axis)
            start = _state_phrase(axis, detail.get("start_band"))
            end = _state_phrase(axis, detail.get("highest_achieved_band"))
            parts.append(f"{start}恢复至{end}")
    if not parts:
        return "未形成明确的本人责任期恢复；短暂峰值或单纯止损不作为恢复结果。", recovered
    return "；".join(parts) + "；只有任期结束时仍保留的改善进入恢复结果。", recovered


def _responsibility_basis(row: dict[str, Any], recovered: set[str]) -> str:
    chains = row.get("recovery_chain_attributions")
    parts: list[str] = []
    if isinstance(chains, dict):
        for axis in STATE_AXES:
            if axis not in recovered or not isinstance(chains.get(axis), dict):
                continue
            detail = chains[axis]
            grade = str(detail.get("grade") or "")
            labels = {"FULL": "本人独立或主导", "SHARED": "本人和其他掌权者共同承担", "NONE": "本人责任不足"}
            label = labels.get(grade, "责任范围按正式记录保留")
            basis = _clean(detail.get("basis"))
            parts.append(f"{AXIS_NAMES[axis]}恢复属于{label}{f'：{basis}' if basis else ''}")
    if parts:
        return "；".join(parts) + "。"
    attribution = row.get("recovery_attribution")
    if isinstance(attribution, dict) and recovered:
        grade = str(attribution.get("grade") or "")
        labels = {"FULL": "本人独立或主导", "SHARED": "本人和其他掌权者共同承担", "NONE": "本人责任不足"}
        label = labels.get(grade, "责任范围按正式记录保留")
        basis = _clean(attribution.get("basis"))
        return f"保留恢复的责任范围为{label}{f'：{basis}' if basis else ''}。"
    return "没有可归入本人责任期的恢复，因此不另行扩大恢复责任。"


def _deterioration_basis(row: dict[str, Any]) -> str:
    path = row.get("deterioration_path_basis") or {}
    parts: list[str] = []
    if isinstance(path, dict):
        for axis in STATE_AXES:
            detail = path.get(axis)
            if not isinstance(detail, dict):
                continue
            if _number(detail.get("attributable_drop")) > 0 and _number(detail.get("attribution_factor")) > 0:
                parts.append(f"{AXIS_NAMES[axis]}在本人责任范围内从接手状态下降到任期结束状态")
    if parts:
        return "；".join(parts) + "。"
    if _number(row.get("deterioration_penalty")) > 0:
        fallback = _first_text(row.get("deterioration_curve_summary"), row.get("negative_tail_adjudication_reason"))
        if fallback:
            return fallback
    return "从接手到任期结束的可比状态中，没有认定本人造成明确下降。"


def _cost_basis(row: dict[str, Any]) -> str:
    review = row.get("active_civilian_cost_review")
    review = review if isinstance(review, dict) else {}
    basis = _first_text(
        review.get("choice_and_civilian_basis"),
        (row.get("c4_attribution_readjudication") or {}).get("behavior_chain_basis")
        if isinstance(row.get("c4_attribution_readjudication"), dict)
        else "",
        row.get("military_cost_public_basis"),
    )
    grade = str(row.get("destructive_amplification_grade") or "DA0")
    label = DA_LABELS.get(grade, "额外民力成本按正式记录保留")
    if grade == "DA0":
        return f"{label}。{basis}" if basis else f"{label}。"
    return f"{label}：{basis or '正式记录没有保留可直述的成本事实。'}"


def _c4_items(row: dict[str, Any]) -> list[dict[str, str]]:
    recovery, recovered = _recovery_basis(row)
    responsibility = _responsibility_basis(row, recovered)
    deterioration = _deterioration_basis(row)
    cost = _cost_basis(row)
    review = row.get("active_civilian_cost_review")
    review = review if isinstance(review, dict) else {}
    absorbed = _first_text(
        review.get("absorbed_and_excluded_basis"),
        row.get("behavior_and_attribution"),
    )
    boundary = f"{absorbed}；{C4_BOUNDARY}" if absorbed else C4_BOUNDARY
    return [
        _item("C4", row, "recovery", "恢复对象与程度", "恢复", recovery, RECOVERY_BOUNDARY),
        _item("C4", row, "responsibility", "恢复责任范围", "责任范围", responsibility, RESPONSIBILITY_BOUNDARY),
        _item("C4", row, "deterioration", "状态恶化", "状态恶化", deterioration, DETERIORATION_BOUNDARY),
        _item("C4", row, "cost", "额外代价", "额外代价", cost, COST_BOUNDARY),
        _item("C4", row, "boundary", "重复计算边界", "边界", boundary, C4_BOUNDARY),
    ]


def _public_items(axis: str, row: dict[str, Any]) -> list[dict[str, str]]:
    return _state_items(axis, row) if axis in STATE_AXES else _c4_items(row)


def _public_summary(axis: str, row: dict[str, Any], items: list[dict[str, str]] | None = None) -> str:
    items = items or _public_items(axis, row)
    if axis in STATE_AXES:
        return "".join(
            [
                items[0]["public_basis"],
                " ",
                items[1]["public_basis"],
                " 评价范围：",
                AXIS_BOUNDARIES[axis],
            ]
        ).strip()
    return "；".join(
        f"{item['public_label']}：{item['public_basis']}"
        for item in items[:4]
    ) + " 结果边界：" + C4_BOUNDARY


def _projection_keys() -> set[str]:
    return {
        "public_projection_schema_version",
        "public_projection_status",
        "public_projection_axis",
        "public_projection_record_count",
        "public_projection_evidence_item_count",
        "public_projection_source",
    }


def _scoring_signature(payload: dict[str, Any]) -> str:
    snapshot = copy.deepcopy(payload)
    rows = snapshot.get("scores") or snapshot.get("records") or []
    for row in rows:
        if isinstance(row, dict):
            for key in ("public_adjudication_summary", "public_evidence_items"):
                row.pop(key, None)
    for key in _projection_keys():
        snapshot.pop(key, None)
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _refresh_payload(axis: str, payload: dict[str, Any]) -> dict[str, Any]:
    before_signature = _scoring_signature(payload)
    rows = _records(payload)
    evidence_count = 0
    for row in rows:
        items = _public_items(axis, row)
        row["public_adjudication_summary"] = _public_summary(axis, row, items)
        row["public_evidence_items"] = items
        evidence_count += len(items)
    if _scoring_signature(payload) != before_signature:
        raise ValueError(f"第二项{axis}公开字段迁移意外改变了正式评分字段")
    payload["public_projection_schema_version"] = PUBLIC_PROJECTION_SCHEMA
    payload["public_projection_status"] = "FORMAL_UPSTREAM_SOURCE"
    payload["public_projection_axis"] = axis
    payload["public_projection_record_count"] = len(rows)
    payload["public_projection_evidence_item_count"] = evidence_count
    payload["public_projection_source"] = {
        "formal_contract": CONTRACT_PATH.as_posix(),
        "identity": "人物ID与公开条目角色生成稳定公开条目ID；公开文字只由当前正式C1-C4字段确定性投影",
        "reader_policy": "reader只消费public_adjudication_summary和public_evidence_items",
    }
    return payload


def _verify_payload(axis: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("public_projection_schema_version") != PUBLIC_PROJECTION_SCHEMA:
        raise ValueError(f"第二项{axis}缺少正式公开投影schema标记")
    if payload.get("public_projection_status") != "FORMAL_UPSTREAM_SOURCE":
        raise ValueError(f"第二项{axis}公开投影不是正式上游真源")
    if payload.get("public_projection_axis") != axis:
        raise ValueError(f"第二项{axis}公开投影轴标记不一致")
    rows = _records(payload)
    if payload.get("public_projection_record_count") != len(rows):
        raise ValueError(f"第二项{axis}公开投影人物计数不一致")
    all_ids: set[str] = set()
    evidence_count = 0
    for row in rows:
        name = str(row.get("ruler_name") or row.get("ruler_id"))
        actual = row.get("public_evidence_items")
        if not isinstance(actual, list) or len(actual) != (3 if axis in STATE_AXES else 5):
            raise ValueError(f"第二项{axis}公开条目数量不完整：{name}")
        ids = [str(item.get("id") or "") for item in actual if isinstance(item, dict)]
        if len(ids) != len(actual) or len(ids) != len(set(ids)) or any(not value for value in ids):
            raise ValueError(f"第二项{axis}公开条目ID不唯一或缺失：{name}")
        if all_ids & set(ids):
            raise ValueError(f"第二项{axis}公开条目ID跨人物重复：{name}")
        all_ids.update(ids)
        for item in actual:
            if not isinstance(item, dict) or set(item) != set(PUBLIC_EVIDENCE_FIELDS):
                raise ValueError(f"第二项{axis}公开条目字段不完整：{name}")
            if not str(item["id"]).startswith(f"{axis}-PUBLIC-"):
                raise ValueError(f"第二项{axis}公开条目ID不稳定：{name}")
            if item["public_role"] not in PUBLIC_ROLES:
                raise ValueError(f"第二项{axis}公开角色非法：{name}")
            for field in PUBLIC_EVIDENCE_FIELDS[1:]:
                value = item[field]
                if not isinstance(value, str) or not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
                    raise ValueError(f"第二项{axis}公开字段含空值或内部术语：{name}/{field}")
        expected = _public_items(axis, row)
        if actual != expected:
            raise ValueError(f"第二项{axis}公开条目不是当前正式裁决的确定性投影：{name}")
        summary = row.get("public_adjudication_summary")
        if not isinstance(summary, str) or not summary.strip() or PUBLIC_FORBIDDEN_RE.search(summary):
            raise ValueError(f"第二项{axis}人物级公开总结缺失或含内部术语：{name}")
        if summary != _public_summary(axis, row, actual):
            raise ValueError(f"第二项{axis}人物级公开总结不是当前正式裁决的确定性投影：{name}")
        evidence_count += len(actual)
    if payload.get("public_projection_evidence_item_count") != evidence_count:
        raise ValueError(f"第二项{axis}公开条目计数不一致")
    if _scoring_signature(payload) != _scoring_signature(_refresh_payload(axis, copy.deepcopy(payload))):
        raise ValueError(f"第二项{axis}公开投影改变了正式评分字段")
    return {
        "status": "PASS",
        "axis": axis,
        "record_count": len(rows),
        "public_evidence_item_count": evidence_count,
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
    }


def verify_public_projection(workspace_root: Path) -> dict[str, Any]:
    root = workspace_root.resolve()
    reports = {
        axis: _verify_payload(axis, load_json(root / path))
        for axis, path in FORMAL_PATHS.items()
    }
    id_sets = {
        axis: {str(row.get("ruler_id")) for row in _records(load_json(root / path))}
        for axis, path in FORMAL_PATHS.items()
    }
    if any(ids != id_sets["C1"] for ids in id_sets.values()):
        raise ValueError("第二项C1-C4公开投影人物集合不一致")
    return {
        "status": "PASS",
        "axis_reports": reports,
        "record_count": len(id_sets["C1"]),
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
    }


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    root = workspace_root.resolve()
    current = {axis: load_json(root / path) for axis, path in FORMAL_PATHS.items()}
    projected = {
        axis: _refresh_payload(axis, copy.deepcopy(payload))
        for axis, payload in current.items()
    }
    if write:
        polities = load_ruler_polities(root)
        for axis, path in FORMAL_PATHS.items():
            write_json(root / path, projected[axis], ruler_polities=polities)
        report = verify_public_projection(root)
        report["status"] = "WRITTEN"
        return report
    if projected != current:
        raise ValueError("第二项C1-C4正式公开投影未同步；请运行second-item-c-public --write")
    return verify_public_projection(root)
