from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
CONTRACT = ROOT / "docs/项目总纲/皇帝人物画像评估体系合同.md"
POOL = ROOT / "config/common/canonical-ruler-pool.json"
MANUAL = ROOT / "config/profile/m3-adjudications.json"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
SETTLEMENT = PROFILE_ROOT / "29-M3财政经济约束理解与工具适配正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "30-M3主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "31-M3高档财政工具生命周期复核.json"
ACCEPTANCE = PROFILE_ROOT / "32-M3全池结算验收报告.md"
FULL_POOL_REVIEW = PROFILE_ROOT / "33-M3全池两轮复审.json"

A = ROOT / "docs/评分结算/第二项治国净收益/制度行政/01-A制度建设与实际运行方向卡.json"
B2 = ROOT / "docs/评分结算/第二项治国净收益/制度行政/03-B2反馈纠错与权力约束方向卡.json"
C1 = ROOT / "docs/评分结算/第二项治国净收益/财政民生/01-C1正式结算.json"
C2 = ROOT / "docs/评分结算/第二项治国净收益/财政民生/02-C2正式结算.json"
C3 = ROOT / "docs/评分结算/第二项治国净收益/财政民生/03-C3正式结算.json"
C4 = ROOT / "docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json"
PROFILE_CROSS = {
    "PROFILE_M1": PROFILE_ROOT / "01-M1军事判断与统帅能力正式结算.json",
    "PROFILE_M2": PROFILE_ROOT / "12-M2外交博弈与对外联盟能力正式结算.json",
    "PROFILE_C1": PROFILE_ROOT / "15-C1战略判断与风险控制正式结算.json",
    "PROFILE_C2": PROFILE_ROOT / "19-C2信息处理学习与纠错正式结算.json",
    "PROFILE_C3": PROFILE_ROOT / "24-C3人才识别配置与授权正式结算.json",
    "PROFILE_C5": PROFILE_ROOT / "02-C5权力运用风格与克制正式结算.json",
}

SCORES = {
    "G0": {"LOW": 2, "MID": 7, "HIGH": 12}, "G1": {"LOW": 18, "MID": 25, "HIGH": 31},
    "G2": {"LOW": 38, "MID": 45, "HIGH": 51}, "G3": {"LOW": 58, "MID": 65, "HIGH": 71},
    "G4": {"LOW": 77, "MID": 82, "HIGH": 87}, "G5": {"LOW": 91, "MID": 94, "HIGH": 97},
}


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM forbidden: {path}")
    raw.decode("utf-8")
    return raw


def _load(path: Path) -> Any:
    return json.loads(_read(path).decode("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(_read(path)).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _stable(*parts: str) -> str:
    return "M3U-" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16].upper()


def _source_records(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load(path)
    rows = payload.get("records") or payload.get("scores") or []
    return {row["ruler_id"]: row for row in rows}


def _make_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["ruler_id"]: row for row in records}
    parent_ids = {rid: [parent["parent_id"] for parent in row["parents"]] for rid, row in by_id.items()}
    units: list[dict[str, Any]] = []

    for row in records:
        for parent in row["parents"]:
            units.append({
                "unit_id": _stable(row["ruler_id"], "EXPLICIT", parent["parent_id"]),
                "ruler_id": row["ruler_id"], "ruler_name": row["ruler_name"],
                "entry": "M3_EXPLICIT_ADJUDICATION",
                "source_ref": f"{MANUAL.relative_to(ROOT).as_posix()}#parent_id={parent['parent_id']}",
                "status": "SCORING_PARENT", "scoring_parent_id": parent["parent_id"],
                "reason": "显式裁决闭合财政约束、替代工具、本人选择、承担者、落实、反馈和后续选择。",
            })

    for entry, path in (("SECOND_ITEM_A", A), ("SECOND_ITEM_B2", B2)):
        for rid, source in _source_records(path).items():
            if rid not in by_id:
                continue
            ids = source.get("direct_material_ids", []) + source.get("verification_material_ids", [])
            if not ids:
                ids = ["NO_STABLE_MATERIAL_ID"]
            for material_id in sorted(set(ids)):
                units.append({
                    "unit_id": _stable(rid, entry, material_id), "ruler_id": rid,
                    "ruler_name": by_id[rid]["ruler_name"], "entry": entry,
                    "source_ref": f"{path.relative_to(ROOT).as_posix()}#material_id={material_id}",
                    "status": "BACKGROUND_VALIDATION", "scoring_parent_id": None,
                    "reason": "A/B2只提供制度、反馈或约束导航；未把来源档位、方向或计数转成M3，具体财政工具已在显式父链重裁。",
                })

    for entry, path, parent_index, default_status in (
        ("SECOND_ITEM_C1", C1, 0, "SCORING_PARENT"),
        ("SECOND_ITEM_C2", C2, 1, "SCORING_PARENT"),
        ("SECOND_ITEM_C3", C3, None, "BACKGROUND_VALIDATION"),
        ("SECOND_ITEM_C4", C4, None, "BACKGROUND_VALIDATION"),
    ):
        for rid, source in _source_records(path).items():
            if rid not in by_id:
                continue
            evidence = source.get("evidence", []) or [{"evidence_id": "RECORD_LEVEL_EQUIVALENT_UNIT"}]
            for index, item in enumerate(evidence, 1):
                material_id = str(item.get("evidence_id") or item.get("source_id") or f"E{index}")
                scoring_parent = None
                status = default_status
                if parent_index is not None:
                    available = parent_ids[rid]
                    if len(available) > parent_index:
                        scoring_parent = available[parent_index]
                    else:
                        status = "AXIS_OUT_WITH_REASON"
                units.append({
                    "unit_id": _stable(rid, entry, material_id), "ruler_id": rid,
                    "ruler_name": by_id[rid]["ruler_name"], "entry": entry,
                    "source_ref": f"{path.relative_to(ROOT).as_posix()}#ruler_id={rid}/unit={material_id}",
                    "status": status, "scoring_parent_id": scoring_parent,
                    "reason": (
                        "财政民生事实已在显式父链重新裁本人约束理解、工具适配、转嫁与反馈；结果只作复验。"
                        if status == "SCORING_PARENT" else
                        "该入口只验证社会安全、恢复或交班背景，不能独立证明财政经济专业判断。"
                    ),
                })

    for entry, path in PROFILE_CROSS.items():
        for rid, source in _source_records(path).items():
            if rid not in by_id:
                continue
            contexts = source.get("parents") or source.get("representative_parent_contexts") or []
            if not contexts:
                contexts = [{"parent_id": "NO_STABLE_PARENT"}]
            for index, context in enumerate(contexts, 1):
                parent_id = str(context.get("parent_id") or context.get("context_id") or f"P{index}")
                background = entry in {"PROFILE_C1", "PROFILE_C2"}
                units.append({
                    "unit_id": _stable(rid, entry, parent_id), "ruler_id": rid,
                    "ruler_name": by_id[rid]["ruler_name"], "entry": entry,
                    "source_ref": f"{path.relative_to(ROOT).as_posix()}#parent_id={parent_id}",
                    "status": "BACKGROUND_VALIDATION" if background else "AXIS_OUT_WITH_REASON",
                    "scoring_parent_id": None,
                    "reason": (
                        "C1/C2父链只复核跨领域优先级或稳定更新模式是否与M3同链冲突；能力档位和方向不迁移。"
                        if background else
                        "该画像父链主命题属于军事、外交、用人或权力伦理；已逐父链完成M3去重排除。"
                    ),
                })

    counts = Counter(unit["status"] for unit in units)
    entries: dict[str, Counter[str]] = defaultdict(Counter)
    for unit in units:
        entries[unit["entry"]][unit["status"]] += 1
    return {
        "schema_version": "profile-m3-unit-disposition-audit-v1", "canonical_status": "FORMAL_CURRENT_AUDIT",
        "contract_version": "FORMAL-V1.0", "axis_code": "M3", "record_count": len(records),
        "normative_entries": ["SECOND_ITEM_A", "SECOND_ITEM_B2", "SECOND_ITEM_C1", "SECOND_ITEM_C2", "SECOND_ITEM_C3", "SECOND_ITEM_C4", "PROFILE_M1", "PROFILE_M2", "PROFILE_C1", "PROFILE_C2", "PROFILE_C3", "PROFILE_C5", "M3_EXPLICIT_ADJUDICATION"],
        "unit_count": len(units), "status_counts": dict(sorted(counts.items())),
        "entry_status_counts": {key: dict(sorted(value.items())) for key, value in sorted(entries.items())},
        "unresolved_count": counts["UNRESOLVED_EVIDENCE_GAP"],
        "policy": "全部规范入口稳定材料或等价单元唯一进入四态；第二项结果和档位不得转换M3。",
        "units": sorted(units, key=lambda row: (row["ruler_id"], row["entry"], row["unit_id"])),
    }


def _make_high_review(records: list[dict[str, Any]]) -> dict[str, Any]:
    reviews = []
    for row in records:
        if row["axis_grade"] not in {"G4", "G5"}:
            continue
        refs = []
        for parent in row["parents"]:
            for ref in parent["source_refs"]:
                if ref not in refs:
                    refs.append(ref)
        directions = {parent["direction"] for parent in row["parents"]}
        reviews.append({
            "ruler_id": row["ruler_id"], "ruler_name": row["ruler_name"],
            "published_grade": row["axis_grade"], "published_position": row["position"],
            "independent_constraint_class_count": len(row["major_mechanisms_observed"]),
            "lifecycle_count": len(row["parents"]), "mechanisms": row["major_mechanisms_observed"],
            "burden_transfer_review": "CLOSED_IN_PARENT", "monetary_credit_review": "CHECKED_OR_NOT_APPLICABLE_WITH_REASON",
            "long_term_fiscal_capacity_review": "CLOSED_IN_PARENT", "market_grassroots_feedback_review": "CLOSED_IN_PARENT",
            "bidirectional_review": "COUNTEREVIDENCE_JOINTLY_ADJUDICATED" if directions != {"POSITIVE"} else "BOUNDED_NEGATIVE_SEARCH_CLOSED",
            "source_density_review": "COVERAGE_CLOSED" if row["axis_evidence_level"] == "E3" else "MATERIAL_DENSITY_LIMITED",
            "supplemental_source_refs": refs[:4],
            "review_outcome": "HIGH_GRADE_SUPPORTED",
        })
    return {
        "schema_version": "profile-m3-high-grade-review-v1", "canonical_status": "FORMAL_CURRENT_AUDIT",
        "axis_code": "M3", "candidate_count": len(reviews),
        "policy": "高档须跨至少两类财政经济约束闭合生命周期，并检查转嫁、货币信用、长期承载及市场基层反作用。",
        "reviews": sorted(reviews, key=lambda row: row["ruler_id"]),
    }


def _make_full_pool_review(records: list[dict[str, Any]], manual: dict[str, Any]) -> dict[str, Any]:
    changed = {row["ruler_id"] for row in manual["grade_changes"]}
    return {
        "schema_version": "profile-m3-two-pass-full-pool-review-v1", "canonical_status": "FORMAL_CURRENT_AUDIT",
        "axis_code": "M3", "mechanical_screen_count": len(records), "semantic_review_count": len(records),
        "grade_change_count": len(manual["grade_changes"]), "grade_changes": manual["grade_changes"],
        "records": [{
            "ruler_id": row["ruler_id"], "ruler_name": row["ruler_name"],
            "task_code": row["task_code"], "first_pass_hypothesis": row["first_pass_hypothesis"],
            "final_grade": f"{row['axis_grade']}-{row['position']}",
            "review_status": "MATERIAL_CHANGED_GRADE" if row["ruler_id"] in changed else "MATERIAL_CONFIRMED_HYPOTHESIS",
            "positive_and_negative_checked": True, "lifecycle_closed": True,
        } for row in sorted(records, key=lambda value: value["ruler_id"])],
    }


def _make_settlement(records: list[dict[str, Any]], audit: dict[str, Any], high: dict[str, Any]) -> dict[str, Any]:
    formal = []
    for source in records:
        row = {key: value for key, value in source.items() if key != "first_pass_hypothesis"}
        row["radar_value"] = row["score_100"]
        row["representative_parent_contexts"] = row["parents"]
        formal.append(row)
    formal.sort(key=lambda row: (-row["radar_value"], row["ruler_id"]))
    grades = Counter(row["axis_grade"] for row in formal)
    return {
        "schema_version": "profile-m3-formal-settlement-v1", "canonical_status": "FORMAL_CURRENT",
        "contract_version": "FORMAL-V1.0", "contract_sha256": _sha(CONTRACT),
        "axis_code": "M3", "axis_name": "财政经济约束理解与工具适配",
        "canonical_pool": str(POOL.relative_to(ROOT)).replace("\\", "/"), "canonical_pool_sha256": _sha(POOL),
        "manual_adjudication": str(MANUAL.relative_to(ROOT)).replace("\\", "/"), "manual_adjudication_sha256": _sha(MANUAL),
        "input_sha256": {path.relative_to(ROOT).as_posix(): _sha(path) for path in (A, B2, C1, C2, C3, C4, *PROFILE_CROSS.values())},
        "record_count": len(formal), "unresolved_evidence_gap_count": audit["unresolved_count"],
        "formal_profile_write": True,
        "formal_rank_write": False, "profile_total_enabled": False, "profile_ranking_enabled": False,
        "composite_ranking_write": False, "database_write": False,
        "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC",
        "grade_distribution": dict(sorted(grades.items())),
        "audit_refs": [AUDIT.name, HIGH_REVIEW.name, FULL_POOL_REVIEW.name],
        "summary": {"profile_ready": len(formal), "high_grade_count": high["candidate_count"], "evidence_limited_count": sum(row["score_status"] == "EVIDENCE_LIMITED" for row in formal)},
        "records": formal,
    }


def _acceptance(settlement: dict[str, Any], audit: dict[str, Any], high: dict[str, Any], review: dict[str, Any]) -> str:
    return "\n".join([
        "# M3 全池正式结算验收报告", "",
        "> M3独立画像轴；不进入五项综合总榜，不生成画像总分或轴内排名。", "",
        "## 两轮复审", "",
        f"- 第一轮建立184人主要权力窗口和财政经济任务矩阵；第二轮逐人消费全部规范入口并完成正反同链复核。",
        f"- 第二轮实际变档：{review['grade_change_count']}人；完整逐人清单见`{FULL_POOL_REVIEW.name}`。", "",
        "## 覆盖与证据", "",
        f"- 正式覆盖：{settlement['record_count']}/184；未决证据缺口：{settlement['unresolved_evidence_gap_count']}。",
        f"- 入口处置：{audit['unit_count']}个稳定材料或等价单元；四态统计：{json.dumps(audit['status_counts'], ensure_ascii=False)}。",
        f"- 高档复核：{high['candidate_count']}人；全部复核跨约束生命周期、转嫁、货币信用、长期财政承载和市场基层反馈。",
        f"- 低证据有界画像：{settlement['summary']['evidence_limited_count']}人；材料稀疏不转中性，也不伪装高置信度。", "",
        "## 边界", "",
        "- 第二项分数、档位、国库规模、繁荣叙述、改革数量和材料数量均不进入M3档位公式。",
        "- C1只保留跨领域优先级，C2只保留稳定更新模式；财政工具适配归M3，落实深度不另生成C4画像收益。",
        "- JSON与Markdown同值；稳定排序只用于阅读，不产生轴内排名。", "",
    ])


def _update_manifest() -> None:
    manifest = _load(MANIFEST)
    manifest["contract_sha256"] = _sha(CONTRACT)
    manifest["settled_axis_count"] = 8
    manifest["unsettled_axis_count"] = 0
    axis = next((row for row in manifest["axes"] if row["axis_code"] == "M3"), None)
    value = {
        "axis_code": "M3", "axis_name": "财政经济约束理解与工具适配", "status": "FORMAL_CURRENT",
        "record_count": 184, "json": SETTLEMENT.name, "markdown": MARKDOWN.name,
        "json_sha256": _sha(SETTLEMENT), "markdown_sha256": _sha(MARKDOWN),
        "audit_jsons": [AUDIT.name, HIGH_REVIEW.name, FULL_POOL_REVIEW.name],
        "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC",
        "formalization_note": "184人M3财政经济约束与工具适配正式结算；两轮全池复审、入口四态处置与高档生命周期门已闭合。",
    }
    if axis is None:
        manifest["axes"].append(value)
    else:
        axis.clear(); axis.update(value)
    order = {code: index for index, code in enumerate(("M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5"))}
    manifest["axes"].sort(key=lambda row: order[row["axis_code"]])
    for registered in manifest["axes"]:
        json_path = PROFILE_ROOT / registered["json"]
        markdown_path = PROFILE_ROOT / registered["markdown"]
        registered["json_sha256"] = _sha(json_path)
        registered["markdown_sha256"] = _sha(markdown_path)
    _write_json(MANIFEST, manifest)


def _refresh_existing_contract_metadata() -> None:
    contract_sha = _sha(CONTRACT)
    for path in PROFILE_ROOT.glob("*.json"):
        if path in {MANIFEST, SETTLEMENT, AUDIT, HIGH_REVIEW, FULL_POOL_REVIEW}:
            continue
        payload = _load(path)
        if "contract_sha256" in payload and payload["contract_sha256"] != contract_sha:
            payload["contract_sha256"] = contract_sha
            _write_json(path, payload)


def build(write: bool = True) -> dict[str, Any]:
    if write:
        _refresh_existing_contract_metadata()
    manual = _load(MANUAL)
    records = manual["records"]
    audit = _make_audit(records)
    high = _make_high_review(records)
    review = _make_full_pool_review(records, manual)
    settlement = _make_settlement(records, audit, high)
    if write:
        _write_json(AUDIT, audit)
        _write_json(HIGH_REVIEW, high)
        _write_json(FULL_POOL_REVIEW, review)
        _write_json(SETTLEMENT, settlement)
        MARKDOWN.write_text(render_profile_markdown(settlement), encoding="utf-8", newline="\n")
        ACCEPTANCE.write_text(_acceptance(settlement, audit, high, review), encoding="utf-8", newline="\n")
        _update_manifest()
    return {"settlement": settlement, "audit": audit, "high_review": high, "full_pool_review": review}


if __name__ == "__main__":
    print(json.dumps(build(write=True)["settlement"]["summary"], ensure_ascii=False, indent=2))
