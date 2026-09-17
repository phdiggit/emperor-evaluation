from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json


B1_PATH = Path("docs/评分结算/净收益/第二项治国净收益/制度行政/02-B1官僚治理与行政执行方向卡.json")
REGISTRY_ROOT = Path("docs/公共成果/制度行政/01-制度行政计分材料登记")
PROFILE_KEYS = ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
STYLE = "B1-PROFILE-ADJUDICATION-V1"

DIRECTION_TAGS = {
    "positive": "正向",
    "positive_correction": "正向",
    "negative": "负向",
    "mixed_positive": "正向主导",
    "mixed_negative": "负向主导",
    "mixed": "正负并存",
    "balanced": "正负并存",
    "neutral": "正负并存",
    "context": "边界材料",
}
ROLE_TAGS = {
    "core": "核心行政链",
    "central": "中枢行政链",
    "distributed": "多责任官行政链",
    "support": "支撑行政链",
    "context": "边界材料",
}
CLOSURE_TAGS = {
    "sustained_or_systemic": "持续或系统运行",
    "observed_or_repeated": "已有实际运行",
    "observed": "已有实际运行",
    "not_restored": "未恢复",
    "reversed": "后续逆转",
    "not_closed": "运行证据尚未完整",
}
STATUS_TAGS = {
    "COUNTED_INDEPENDENT": "独立计入",
    "ABSORBED_SAME_LIFECYCLE": "并入同一运行链",
    "BOUNDARY_CONTEXT": "不单独计入",
    "ZERO_NET": "不增加净值",
}
MACHINE_TERM_RE = re.compile(
    r"(?:B[12](?:[-_/][A-Za-z_]+)?|M[0-3]|N3-(?:domain|cross|terminal)|"
    r"\b(?:core|support|central|distributed|context|mixed_positive|mixed_negative|position|terminal|cross)\b|G[0-5])",
    flags=re.I,
)


def _text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _public_text(value: object) -> str:
    text = _text(value).replace("`", "")
    if not text:
        return ""
    text = re.sub(r"(?:尚)?未闭合到", "现有证据尚不足以形成", text)
    text = re.sub(r"(?:尚)?未闭合", "现有证据尚不足以证明", text)
    replacements = (
        (r"N3-terminal", "广域整体失效"),
        (r"N3-cross", "跨功能失灵"),
        (r"N3-domain", "单功能系统失灵"),
        (r"B1[-_/]?(?:core|central|support|distributed|personnel)", "官僚治理"),
        (r"B1", "官僚治理"),
        (r"B2", "反馈与约束"),
        (r"mixed_positive", "正向主导"),
        (r"mixed_negative", "负向主导"),
        (r"mixed", "正负并存"),
        (r"distributed", "多责任官行政链"),
        (r"central", "中枢行政链"),
        (r"support", "支撑行政链"),
        (r"core", "核心行政链"),
        (r"context", "边界材料"),
        (r"terminal", "广域整体失效"),
        (r"cross", "跨功能失灵"),
        (r"major-stage", "主要阶段"),
        (r"M[0-3]", ""),
        (r"G[0-5]", "当前等级"),
        (r"position", "档内位置"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    text = text.replace("归A", "归制度建设")
    text = text.replace("A项", "制度建设")
    text = re.sub(r"(?<![A-Za-z])A计(?:权|分)?", "制度建设计分", text)
    text = text.replace("闭合", "已有充分证据支持")
    text = text.replace("消费", "计入")
    text = text.replace("不重复计数", "不重复计算")
    text = text.replace("重复消费", "重复计算")
    text = text.replace("门槛占用", "等级要求")
    text = text.replace("净余量", "剩余有效依据")
    text = re.sub(r"当前等级(?:当前等级)+", "当前等级", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[；，]\s*[；，]+", "；", text)
    return text.strip(" ；，。")


def _iter_profiles(row: dict[str, Any]):
    for key in PROFILE_KEYS:
        for profile in row.get(key) or []:
            if isinstance(profile, dict):
                yield profile


def _status(profile: dict[str, Any]) -> str:
    mode = str(profile.get("position_count_mode") or "")
    if mode == "absorbed_same_lifecycle" or (
        profile.get("position_weight_override") == 0 and profile.get("absorbed_into_lifecycle_key")
    ):
        return "ABSORBED_SAME_LIFECYCLE"
    if mode in {"context_only", "context_only_no_effective_mechanism"} or profile.get("direction") == "context":
        return "BOUNDARY_CONTEXT"
    if mode == "balanced_mixed_lifecycle" or float(profile.get("signed_weight") or 0.0) == 0.0:
        return "ZERO_NET"
    return "COUNTED_INDEPENDENT"


def _tags(profile: dict[str, Any], status: str) -> list[str]:
    if status == "ABSORBED_SAME_LIFECYCLE":
        role = "补充材料"
    elif status == "BOUNDARY_CONTEXT":
        role = "边界材料"
    else:
        role = ROLE_TAGS.get(str(profile.get("b1_role") or ""), "行政运行链")
    values = [
        DIRECTION_TAGS.get(str(profile.get("direction") or ""), "正负并存"),
        role,
        STATUS_TAGS[status],
    ]
    closure = CLOSURE_TAGS.get(str(profile.get("result_closure") or "").lower())
    if closure:
        values.append(closure)
    return list(dict.fromkeys(value for value in values if value))


def _material_index(workspace_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted((workspace_root / REGISTRY_ROOT).glob("*.json")):
        payload = load_json(path)
        for material in payload.get("records") or []:
            material_id = _text(material.get("material_id"))
            if material_id and material_id not in result:
                result[material_id] = material
    return result


def _prose_source(value: object) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        if not isinstance(item, str):
            continue
        text = _text(item)
        if not text or text.startswith(("docs/", "config/", "archive/", "http://", "https://")):
            continue
        result.append(text)
    return result


def _unique(values: list[str], limit: int = 4) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _public_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _bigrams(value: object) -> set[str]:
    chars = "".join(re.findall(r"[\u3400-\u9fff]", _public_text(value)))
    return {chars[index : index + 2] for index in range(max(0, len(chars) - 1))}


def _best_relevant_clause(sources: list[object], tokens: set[str]) -> str:
    scored: dict[str, int] = {}
    for source in sources:
        raw = _text(source)
        if not raw:
            continue
        for clause in re.split(r"(?<=[。；])", raw):
            clause = clause.strip()
            if not clause:
                continue
            score = sum(1 for token in tokens if token in clause)
            if score:
                scored[clause] = max(score, scored.get(clause, 0))
    if not scored:
        return ""
    return max(scored, key=lambda clause: (scored[clause], len(clause)))


def _relevant_record_basis(row: dict[str, Any], profile: dict[str, Any]) -> str:
    tokens = _bigrams(profile.get("mechanism") or profile.get("material_id"))
    if not tokens:
        return ""
    current = _best_relevant_clause([row.get("grade_basis"), row.get("grade_gate_basis")], tokens)
    if current:
        return current
    historical = [
        item.get("basis")
        for item in row.get("review_material_basis") or []
        if isinstance(item, dict)
    ]
    return _best_relevant_clause(historical, tokens)


def _basis_and_boundary(
    row: dict[str, Any], profile: dict[str, Any], material: dict[str, Any] | None, status: str
) -> tuple[str, str, list[str]]:
    basis_values: list[str] = []
    boundary_values: list[str] = []
    sources: list[str] = []

    if status in {"ABSORBED_SAME_LIFECYCLE", "BOUNDARY_CONTEXT"}:
        exclusion = _text(profile.get("position_exclusion_reason"))
        if exclusion:
            basis_values.append(exclusion)
            sources.append("position_exclusion_reason")

    severity = _text(profile.get("severity_basis"))
    if severity:
        basis_values.append(severity)
        sources.append("severity_basis")

    source_basis = _prose_source(profile.get("source_basis"))
    if source_basis:
        basis_values.extend(source_basis)
        sources.append("source_basis")

    if material:
        for field in ("measure", "operation", "result"):
            value = _text(material.get(field))
            if value:
                basis_values.append(value)
        if any(_text(material.get(field)) for field in ("measure", "operation", "result")):
            sources.append("material_registry")
        boundary = _text(material.get("cost_or_capture"))
        if boundary:
            boundary_values.append(boundary)
            sources.append("material_boundary")

    if not basis_values or material is None:
        record_basis = _relevant_record_basis(row, profile)
        if record_basis:
            basis_values.append(record_basis)
            sources.append("record_adjudication")

    exclusion = _text(profile.get("position_exclusion_reason"))
    if exclusion:
        boundary_values.append(exclusion)

    basis = _unique(basis_values)
    boundary = _unique(boundary_values, limit=2)
    if not basis:
        fallback = _public_text(profile.get("mechanism") or profile.get("material_id"))
        if fallback:
            basis = [f"{fallback}。正式记录未另拆独立逐材料说明，按当前材料角色与既定权重处理"]
            sources.append("profile_fallback")

    return "；".join(basis), "；".join(boundary), list(dict.fromkeys(sources))


def _score_signature(payload: dict[str, Any]) -> str:
    snapshot = []
    for row in payload.get("records") or []:
        profiles = []
        for profile in _iter_profiles(row):
            profiles.append({
                key: profile.get(key)
                for key in (
                    "profile_id", "material_id", "evidence_slice", "M", "direction", "direction_factor",
                    "signed_weight", "lifecycle_key", "lifecycle_group_key", "grade_independence_lifecycle_key",
                    "position_count_mode", "position_weight_override", "absorbed_into_lifecycle_key", "b1_role",
                    "severity", "severity_scope",
                )
            })
        snapshot.append({
            "ruler_id": row.get("ruler_id"),
            "grade": row.get("grade"),
            "position": row.get("position"),
            "direction_index": row.get("direction_index"),
            "rank": row.get("rank"),
            "profiles": profiles,
        })
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_public_profile(row: dict[str, Any], profile: dict[str, Any]) -> None:
    for field in ("adjudication_basis", "adjudication_boundary"):
        value = _text(profile.get(field))
        if value and MACHINE_TERM_RE.search(value):
            raise ValueError(
                f"B1逐材料公开裁决仍含机器术语：{row.get('ruler_name')} / {profile.get('material_id')} / {field}"
            )


def normalize_payload(payload: dict[str, Any], workspace_root: Path) -> dict[str, Any]:
    before = _score_signature(payload)
    materials = _material_index(workspace_root)
    status_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    profile_count = 0

    for row in payload.get("records") or []:
        row_status: Counter[str] = Counter()
        for profile in _iter_profiles(row):
            profile_count += 1
            status = _status(profile)
            row_status[status] += 1
            status_counts[status] += 1
            material = materials.get(_text(profile.get("material_id")))
            basis, boundary, sources = _basis_and_boundary(row, profile, material, status)
            profile["adjudication_status"] = status
            profile["adjudication_tags"] = _tags(profile, status)
            profile["adjudication_basis"] = basis
            if boundary:
                profile["adjudication_boundary"] = boundary
            else:
                profile.pop("adjudication_boundary", None)
            profile["adjudication_basis_source"] = sources
            _validate_public_profile(row, profile)
            for source in sources:
                source_counts[source] += 1

        independent = [
            profile for profile in _iter_profiles(row)
            if profile.get("adjudication_status") == "COUNTED_INDEPENDENT"
        ]
        positive = sum(1 for profile in independent if profile.get("direction") in {"positive", "positive_correction"})
        negative = sum(1 for profile in independent if profile.get("direction") == "negative")
        mixed = sum(1 for profile in independent if profile.get("direction") not in {"positive", "positive_correction", "negative"})
        mixed += row_status["ZERO_NET"]
        absorbed = row_status["ABSORBED_SAME_LIFECYCLE"]
        context = row_status["BOUNDARY_CONTEXT"]
        parts = [f"正式结算按独立行政运行链判断：正向 {positive} 条、负向 {negative} 条、正负并存 {mixed} 条"]
        if absorbed:
            parts.append(f"{absorbed} 条补充材料并入同一运行链")
        if context:
            parts.append(f"{context} 条边界材料不单独计入")
        parts.append("各条权重并不相同，不能按条数直接相减")
        row["public_adjudication_summary"] = "；".join(parts) + "。"
        row["profile_adjudication_style"] = STYLE

    if _score_signature(payload) != before:
        raise ValueError("B1逐材料裁决标准化意外改变了正式评分字段")

    payload["profile_adjudication_style"] = STYLE
    payload["profile_adjudication_record_count"] = len(payload.get("records") or [])
    payload["profile_adjudication_profile_count"] = profile_count
    payload["profile_adjudication_status_counts"] = dict(sorted(status_counts.items()))
    payload["profile_adjudication_basis_source_counts"] = dict(sorted(source_counts.items()))
    return payload


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    path = workspace_root / B1_PATH
    payload = normalize_payload(load_json(path), workspace_root)
    if write:
        write_json(path, payload, ruler_polities=load_ruler_polities(workspace_root))
    return {
        "style": payload["profile_adjudication_style"],
        "record_count": payload["profile_adjudication_record_count"],
        "profile_count": payload["profile_adjudication_profile_count"],
        "status_counts": payload["profile_adjudication_status_counts"],
        "basis_source_counts": payload["profile_adjudication_basis_source_counts"],
        "write": write,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="标准化第二项B1逐材料裁决字段，不改变评分")
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = run(args.workspace_root.resolve(), write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
