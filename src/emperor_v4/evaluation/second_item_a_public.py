from __future__ import annotations

"""Validate authored A prose and copy it verbatim to evidence / Markdown views.

Historical prose is edited in the formal records. This module never creates,
translates, truncates or repairs that prose from scoring fields or material counts.
"""

import copy
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json

A_PATH = Path("docs/评分结算/净收益/第二项治国净收益/制度行政/01-A制度建设与实际运行方向卡.json")
MARKDOWN_PATH = A_PATH.with_suffix(".md")
PUBLIC_PROJECTION_SCHEMA = "second-item-a-public-projection-v2"
PUBLIC_MARKER = "<!-- A_AUTHORED_PUBLIC_READING -->"
PROFILE_KEYS = ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
PUBLIC_DIRECTIONS = {"positive":"正向", "positive_correction":"正向", "negative":"负向", "mixed_positive":"正向主导", "mixed_negative":"负向主导", "mixed":"正负并存", "balanced":"正负并存", "neutral":"事实参考"}
PUBLIC_NODE_FIELDS = ("institution_node_id", "public_label", "public_direction", "public_tags", "signed_weight", "public_adjudication_basis", "public_boundary", "public_reception", "public_sources", "public_material_ids")
PUBLIC_FORBIDDEN_RE = re.compile(r"(?<![A-Za-z])(?:M[0-3]|R[0-4]|G[0-5])(?![A-Za-z0-9])|S(?:\+\+|\+|−|-)\s*\d*|NON_S|position|canonical|生命周期|主档消费|门禁|该节点被判断为|已有材料支持|证明链条成立|净方向不在.*裁决|不在本节点中判断正负方向|正向影响权重为|制度净值为")

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


def _signed_weight(node: dict[str, Any]) -> float:
    value = node.get("signed_weight")
    if value is not None:
        return _number(value)
    direction = str(node.get("direction") or node.get("normative_direction") or "")
    if direction in {"negative", "mixed_negative"}:
        return -abs(_number(node.get("S_minus_weight")))
    return abs(_number(node.get("S_depth_weight")))


def _require_prose(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
        raise ValueError(f"第二项A缺少人工正文或仍含过程话术：{context}")
    return value


def _public_nodes(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Check identity, direction and weight; preserve authored words exactly."""
    nodes = row.get("public_institution_nodes")
    groups = _node_groups(row)
    if not isinstance(nodes, list):
        raise ValueError(f"第二项A缺少人工节点正文：{row.get('ruler_name')}")
    ids = [n.get("institution_node_id") for n in nodes]
    if len(ids) != len(set(ids)) or set(ids) != set(groups):
        raise ValueError(f"第二项A公开节点与正式身份不一致：{row.get('ruler_name')}")
    for node in nodes:
        context = f"{row.get('ruler_name')} / {node.get('institution_node_id')}"
        if set(node) != set(PUBLIC_NODE_FIELDS):
            raise ValueError(f"第二项A公开节点字段不完整：{context}")
        formal = _merge_group(groups[node["institution_node_id"]])
        if node["public_direction"] != _public_direction(formal) or node["signed_weight"] != _signed_weight(formal):
            raise ValueError(f"第二项A公开节点改变了正式方向或权重：{context}")
        for field in ("public_label", "public_adjudication_basis", "public_reception"):
            _require_prose(node[field], f"{context} / {field}")
        if node["public_boundary"] is not None:
            _require_prose(node["public_boundary"], f"{context} / public_boundary")
        if not isinstance(node["public_tags"], list) or not node["public_tags"]:
            raise ValueError(f"第二项A缺少节点标签：{context}")
        for tag in node["public_tags"]:
            _require_prose(tag, context)
        if not isinstance(node["public_sources"], list) or not node["public_sources"]:
            raise ValueError(f"第二项A缺少逐卡来源：{context}")
        if not isinstance(node["public_material_ids"], list):
            raise ValueError(f"第二项A材料引用类型错误：{context}")
        material_ids = []
        for key in ("construction_operation_material_ids", "material_ids", "durability_material_ids", "material_id"):
            raw = formal.get(key) or []
            material_ids.extend(raw if isinstance(raw, list) else [raw])
        if node["public_material_ids"] != list(dict.fromkeys(material_ids)):
            raise ValueError(f"第二项A公开材料编号与正式节点不一致：{context}")
    return nodes


def _public_evidence_items(row: dict[str, Any], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "institution_node_id": n["institution_node_id"],
        "public_label": n["public_label"], "public_direction": n["public_direction"],
        "public_tags": copy.deepcopy(n["public_tags"]),
        "public_basis": n["public_adjudication_basis"],
        "public_boundary": n["public_boundary"], "public_reception": n["public_reception"],
        "public_sources": copy.deepcopy(n["public_sources"]),
        "public_material_ids": copy.deepcopy(n["public_material_ids"]),
    } for n in nodes]


def _scoring_signature(payload: dict[str, Any]) -> str:
    # Protect all non-public record fields, including totals, IDs and rankings.
    rows = [{k: v for k, v in row.items() if not k.startswith("public_")} for row in payload.get("records", [])]
    return json.dumps(sorted(rows, key=lambda r: r["ruler_id"]), ensure_ascii=False, sort_keys=True)


def _verify_ref(root: Path, ref: object) -> None:
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError("第二项A逐卡来源为空")
    parsed = urlsplit(ref)
    if parsed.scheme:
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError(f"第二项A来源协议非法：{ref}")
        return  # Verification is offline; no claim about live remote availability.
    target = (root / unquote(parsed.path)).resolve()
    if parsed.path.startswith((".tmp/", "tmp/", ".cache/", "logs/")) or not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError(f"第二项A本地来源不存在或越界：{ref}")
    if target.suffix == ".json" and parsed.fragment:
        reference = unquote(parsed.fragment)
        parameter, _, pointer = reference.partition("/")
        key, equal, value = parameter.partition("=")
        if equal:
            matches = []
            def walk(item):
                if isinstance(item, dict):
                    if str(item.get(key, "")) == value:
                        matches.append(item)
                        return
                    for child in item.values(): walk(child)
                elif isinstance(item, list):
                    for child in item: walk(child)
            walk(load_json(target))
            if not matches:
                raise ValueError(f"第二项A来源编号无匹配：{ref}")
            if pointer:
                for item in matches:
                    try:
                        for part in pointer.split("/"):
                            item = item[int(part)] if isinstance(item, list) else item[part]
                    except (KeyError, ValueError, IndexError, TypeError) as exc:
                        raise ValueError(f"第二项A来源路径无匹配：{ref}") from exc


def _refresh_payload(payload: dict[str, Any], workspace_root: Path) -> dict[str, Any]:
    before = _scoring_signature(payload)
    if payload.get("public_projection_schema_version") != PUBLIC_PROJECTION_SCHEMA:
        raise ValueError("第二项A必须先维护正式人工正文，不再从旧字段自动生成事实")
    for row in payload.get("records", []):
        _require_prose(row.get("public_story"), str(row.get("ruler_name")))
        _require_prose(row.get("public_adjudication_summary"), str(row.get("ruler_name")))
        _require_prose(row.get("public_boundary"), str(row.get("ruler_name")))
        nodes = _public_nodes(row)
        row["public_evidence_items"] = _public_evidence_items(row, nodes)
    if _scoring_signature(payload) != before:
        raise ValueError("第二项A阅读投影改变了评分字段")
    return payload


def refresh_public_projection(workspace_root: Path) -> dict[str, Any]:
    return _refresh_payload(load_json(workspace_root / A_PATH), workspace_root)


def public_markdown(payload: dict[str, Any]) -> str:
    lines = [PUBLIC_MARKER, "## 三、制度建设逐人阅读", "", "正文与定档理由直接读取正式JSON；计算表见上文。没有制度节点的记录只显示证据边界，不计作材料卡。", ""]
    for row in payload["records"]:
        lines += [f"### {row['ruler_name']}", "", row["public_story"], "", "**定档理由：**" + row["public_adjudication_summary"], ""]
        for n in row["public_institution_nodes"]:
            lines += [f"#### {n['public_label']}（{n['public_direction']}）", "", n["public_adjudication_basis"], "", n["public_reception"], ""]
            if n["public_boundary"]:
                lines += ["范围与边界：" + n["public_boundary"], ""]
            lines += ["来源：" + "；".join(f"[{v['label']}]({v['ref']})" for v in n["public_sources"]), ""]
        lines += ["评价范围：" + row["public_boundary"], ""]
    return "\n".join(lines).rstrip() + "\n"


def _markdown_view(workspace_root: Path, payload: dict[str, Any]) -> str:
    original = (workspace_root / MARKDOWN_PATH).read_text(encoding="utf-8")
    prefix = original.split(PUBLIC_MARKER, 1)[0].rstrip()
    return prefix + "\n\n" + public_markdown(payload)


def verify_public_projection(workspace_root: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if payload is None:
        payload = load_json(workspace_root / A_PATH)
    projected = _refresh_payload(copy.deepcopy(payload), workspace_root)
    if projected != payload:
        raise ValueError("第二项A公开证据未与人工正文同步；运行second-item-a-public --write")
    rows = payload.get("records", [])
    if payload.get("public_projection_record_count") != len(rows):
        raise ValueError("第二项A公开人物计数不一致")
    count = 0
    for row in rows:
        nodes = row["public_institution_nodes"]
        count += len(nodes)
        pos = sum(n["signed_weight"] for n in nodes if n["signed_weight"] > 0)
        neg = sum(-n["signed_weight"] for n in nodes if n["signed_weight"] < 0)
        if pos != row["P_gross"] or neg != row["N_gross"] or pos-neg != row["A_net_units"]:
            raise ValueError(f"第二项A公开权重与正式总账不一致：{row['ruler_name']}")
        for n in nodes:
            for source in n["public_sources"]:
                if set(source) != {"label", "ref"} or not source["label"]:
                    raise ValueError(f"第二项A来源结构错误：{row['ruler_name']}")
                _verify_ref(workspace_root, source["ref"])
    if payload.get("public_projection_node_count") != count:
        raise ValueError("第二项A公开节点计数不一致")
    path = workspace_root / MARKDOWN_PATH
    if path.read_text(encoding="utf-8") != _markdown_view(workspace_root, payload):
        raise ValueError("第二项A Markdown阅读正文未与正式JSON同值")
    return {"status":"PASS", "record_count":len(rows), "public_node_count":count,
            "empty_node_record_count":sum(not r["public_institution_nodes"] for r in rows),
            "schema_version":PUBLIC_PROJECTION_SCHEMA}


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    current = load_json(workspace_root / A_PATH)
    projected = _refresh_payload(copy.deepcopy(current), workspace_root)
    if write:
        for source in projected.get("source_documents", []):
            if source.get("path") == "docs/分项规则/第二项治国净收益/制度行政/00-规则与计分合同.md":
                source["byte_sha256"] = hashlib.sha256((workspace_root / source["path"]).read_bytes()).hexdigest()
        write_json(workspace_root / A_PATH, projected, ruler_polities=load_ruler_polities(workspace_root))
        (workspace_root / MARKDOWN_PATH).write_text(_markdown_view(workspace_root, projected), encoding="utf-8", newline="\n")
    report = verify_public_projection(workspace_root, projected if write else current)
    if write: report["status"] = "WRITTEN"
    return report
