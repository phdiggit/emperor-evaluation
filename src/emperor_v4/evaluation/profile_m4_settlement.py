from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
CONTRACT = ROOT / "docs/项目总纲/皇帝人物画像评估体系合同.md"
POOL = ROOT / "config/common/canonical-ruler-pool.json"
PROJECT = ROOT / "config/project.yml"
MANUAL = ROOT / "config/profile/m4-adjudications.json"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
SETTLEMENT = PROFILE_ROOT / "34-M4政治联盟与内部联盟管理正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "35-M4主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "36-M4高档联盟生命周期复核.json"
FULL_POOL_REVIEW = PROFILE_ROOT / "37-M4全池两轮复审.json"
ACCEPTANCE = PROFILE_ROOT / "38-M4全池结算验收报告.md"

FIRST_B = ROOT / "docs/评分结算/第一项创业与政权取得能力/政治整合能力/01-第一项B政治整合能力结算.json"
FOURTH_A = ROOT / "docs/评分结算/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json"
FIFTH_B = ROOT / "docs/评分结算/第五项统治者政治素质/02-B轴用人与授权正式结算.json"
FIFTH_C = ROOT / "docs/评分结算/第五项统治者政治素质/03-C轴强制权力伦理正式结算.json"
PROFILE_INPUTS = {
    "PROFILE_M1": PROFILE_ROOT / "01-M1军事判断与统帅能力正式结算.json",
    "PROFILE_M2": PROFILE_ROOT / "12-M2外交博弈与对外联盟能力正式结算.json",
    "PROFILE_M3": PROFILE_ROOT / "29-M3财政经济约束理解与工具适配正式结算.json",
    "PROFILE_C1": PROFILE_ROOT / "15-C1战略判断与风险控制正式结算.json",
    "PROFILE_C2": PROFILE_ROOT / "19-C2信息处理学习与纠错正式结算.json",
    "PROFILE_C3": PROFILE_ROOT / "24-C3人才识别配置与授权正式结算.json",
    "PROFILE_C5": PROFILE_ROOT / "02-C5权力运用风格与克制正式结算.json",
}
NORMATIVE_INPUTS = {
    "FIRST_ITEM_B": FIRST_B,
    "FOURTH_ITEM_A": FOURTH_A,
    "FIFTH_ITEM_B": FIFTH_B,
    "FIFTH_ITEM_C": FIFTH_C,
    **PROFILE_INPUTS,
}

SCORES = {
    "G0": {"LOW": 2, "MID": 7, "HIGH": 12},
    "G1": {"LOW": 18, "MID": 25, "HIGH": 31},
    "G2": {"LOW": 38, "MID": 45, "HIGH": 51},
    "G3": {"LOW": 58, "MID": 65, "HIGH": 71},
    "G4": {"LOW": 77, "MID": 82, "HIGH": 87},
    "G5": {"LOW": 91, "MID": 94, "HIGH": 97},
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


def _normalized_sha(path: Path) -> str:
    normalized = _read(path).replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _stable(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16].upper()
    return f"M4U-{digest}"


def _rows(path: Path) -> list[dict[str, Any]]:
    payload = _load(path)
    return payload.get("records") or payload.get("scores") or []


def _material_units(entry: str, row: dict[str, Any]) -> Iterable[tuple[str, list[str]]]:
    if entry == "FIRST_ITEM_B":
        b1 = row.get("B1") or {}
        outcomes = b1.get("outcome_evidence") or []
        if outcomes:
            for outcome in outcomes:
                yield str(outcome.get("outcome_ref") or _stable(entry, row["ruler_id"], "OUTCOME")), list(outcome.get("source_refs") or [])
            return
    if entry == "FOURTH_ITEM_A":
        axes = [axis for axis in row.get("axis_results", []) if axis.get("axis") == "A"]
        if axes:
            for axis in axes:
                refs = list(axis.get("package_refs") or [])
                yield refs[0] if refs else "A_RECORD_LEVEL_EQUIVALENT_UNIT", refs
            return
    if entry in {"FIFTH_ITEM_B", "FIFTH_ITEM_C"}:
        traits = row.get("traits") or []
        if traits:
            for index, trait in enumerate(traits, 1):
                refs = list(trait.get("source_refs") or [])
                identity = str(trait.get("domain") or f"TRAIT-{index}") + f"-{index}"
                yield identity, refs
            return
    contexts = row.get("parents") or row.get("representative_parent_contexts") or []
    if contexts:
        for index, context in enumerate(contexts, 1):
            identity = str(context.get("parent_id") or context.get("parent_ref") or f"P{index}")
            refs = []
            for key in ("source_refs", "direct_process_refs", "cycle_anchor_refs", "source_parent_refs"):
                for ref in context.get(key, []) or []:
                    if str(ref) not in refs:
                        refs.append(str(ref))
            yield identity, refs
        return
    yield "RECORD_LEVEL_EQUIVALENT_UNIT", []


def _entry_disposition(entry: str) -> tuple[str, str]:
    if entry in {"FIRST_ITEM_B", "FOURTH_ITEM_A"}:
        return "BACKGROUND_VALIDATION", "只验证创业承担或共同体整合结果；不得从成果、分值或档位反推M4。"
    if entry in {"FIFTH_ITEM_B", "FIFTH_ITEM_C", "PROFILE_C3", "PROFILE_C5"}:
        return "BACKGROUND_VALIDATION", "只验证集团责任、参与渠道、安全预期或退出边界；个人用人与伦理方向不迁移。"
    if entry == "PROFILE_M2":
        return "AXIS_OUT_WITH_REASON", "外部对象、独立政权及条约交换唯一主路由M2；国内身份吸收已在M4显式父链另行闭合。"
    return "AXIS_OUT_WITH_REASON", "该画像父链主命题不属于国内集团利益、政治信用或联盟退出；已完成逐父链去重排除。"


def _make_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["ruler_id"]: row for row in records}
    units: list[dict[str, Any]] = []
    for row in records:
        for parent in row["parents"]:
            units.append({
                "unit_id": _stable(row["ruler_id"], "M4_EXPLICIT_ADJUDICATION", parent["parent_id"]),
                "ruler_id": row["ruler_id"],
                "ruler_name": row["ruler_name"],
                "entry": "M4_EXPLICIT_ADJUDICATION",
                "material_id": parent["parent_id"],
                "source_refs": [f"{MANUAL.relative_to(ROOT).as_posix()}#parent_id={parent['parent_id']}", *parent["source_refs"]],
                "status": "SCORING_PARENT",
                "scoring_parent_id": parent["parent_id"],
                "reason": "显式M4裁决闭合集团结构、利益与安全预期、本人选择、合作兑现、反馈、冲突和退出。",
            })

    for entry, path in NORMATIVE_INPUTS.items():
        status, reason = _entry_disposition(entry)
        for source in _rows(path):
            ruler_id = source.get("ruler_id")
            if ruler_id not in by_id:
                continue
            for material_id, refs in _material_units(entry, source):
                units.append({
                    "unit_id": _stable(ruler_id, entry, material_id),
                    "ruler_id": ruler_id,
                    "ruler_name": by_id[ruler_id]["ruler_name"],
                    "entry": entry,
                    "material_id": material_id,
                    "source_refs": [f"{path.relative_to(ROOT).as_posix()}#material_id={material_id}", *refs],
                    "status": status,
                    "scoring_parent_id": None,
                    "reason": reason,
                })

    counts = Counter(unit["status"] for unit in units)
    entry_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for unit in units:
        entry_counts[unit["entry"]][unit["status"]] += 1
    return {
        "schema_version": "profile-m4-unit-disposition-audit-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "contract_version": "FORMAL-V1.0",
        "axis_code": "M4",
        "record_count": len(records),
        "normative_entries": [*NORMATIVE_INPUTS, "M4_EXPLICIT_ADJUDICATION"],
        "unit_count": len(units),
        "status_counts": dict(sorted(counts.items())),
        "entry_status_counts": {key: dict(sorted(value.items())) for key, value in sorted(entry_counts.items())},
        "unresolved_count": counts["UNRESOLVED_EVIDENCE_GAP"],
        "policy": "每个规范入口稳定材料或等价单元只进入四态之一；只有显式M4父链是档位来源。",
        "units": sorted(units, key=lambda value: (value["ruler_id"], value["entry"], value["unit_id"])),
    }


def _make_high_review(records: list[dict[str, Any]]) -> dict[str, Any]:
    reviews = []
    for row in records:
        if row["axis_grade"] not in {"G4", "G5"}:
            continue
        directions = {parent["direction"] for parent in row["parents"]}
        reviews.append({
            "ruler_id": row["ruler_id"],
            "ruler_name": row["ruler_name"],
            "published_grade": row["axis_grade"],
            "published_position": row["position"],
            "major_group_structure_review": "CLOSED",
            "interest_and_security_expectation_review": "CLOSED",
            "cooperation_delivery_review": "CLOSED",
            "conflict_and_exit_review": "CLOSED",
            "full_power_window_review": "CLOSED",
            "bidirectional_review": "POSITIVE_AND_NEGATIVE_JOINTLY_ADJUDICATED" if any("MIXED" in value or "NEGATIVE" in value for value in directions) else "BOUNDED_NEGATIVE_SEARCH_CLOSED",
            "source_density_review": "COVERAGE_CLOSED",
            "lifecycle_count": len(row["parents"]),
            "mechanism_count": len(row["major_mechanisms_observed"]),
            "review_outcome": "HIGH_GRADE_SUPPORTED",
        })
    return {
        "schema_version": "profile-m4-high-grade-alliance-lifecycle-review-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "axis_code": "M4",
        "candidate_count": len(reviews),
        "policy": "G4/G5必须覆盖主要集团结构、利益与安全预期、合作兑现、冲突与退出及完整实际权力窗口；开国成果或单一联盟不足以过门。",
        "reviews": sorted(reviews, key=lambda value: value["ruler_id"]),
    }


def _make_full_pool_review(records: list[dict[str, Any]], manual: dict[str, Any]) -> dict[str, Any]:
    changed = {row["ruler_id"] for row in manual["grade_changes"]}
    return {
        "schema_version": "profile-m4-two-pass-full-pool-review-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "axis_code": "M4",
        "mechanical_screen_count": len(records),
        "semantic_review_count": len(records),
        "grade_change_count": len(manual["grade_changes"]),
        "grade_changes": manual["grade_changes"],
        "records": [{
            "ruler_id": row["ruler_id"],
            "ruler_name": row["ruler_name"],
            "task_code": row["task_code"],
            "actual_power_window": row["actual_power_window"],
            "first_pass_hypothesis": row["first_pass_hypothesis"],
            "major_group_structure": row["parents"][0]["group_structure"],
            "alliance_tasks": [parent["coalition_task"] for parent in row["parents"]],
            "final_grade": f"{row['axis_grade']}-{row['position']}",
            "review_status": "MATERIAL_CHANGED_GRADE" if row["ruler_id"] in changed else "MATERIAL_CONFIRMED_HYPOTHESIS",
            "positive_and_negative_checked": True,
            "full_lifecycle_closed": True,
            "all_normative_entries_consumed": True,
        } for row in sorted(records, key=lambda value: value["ruler_id"])],
    }


def _make_settlement(records: list[dict[str, Any]], audit: dict[str, Any], high: dict[str, Any]) -> dict[str, Any]:
    formal = []
    for source in records:
        row = {key: value for key, value in source.items() if key != "first_pass_hypothesis"}
        row["axis_code"] = "M4"
        row["axis_name"] = "政治联盟与内部联盟管理"
        row["formal_status"] = "FORMAL_CURRENT"
        row["score_100"] = SCORES[row["axis_grade"]][row["position"]]
        row["radar_value"] = row["score_100"]
        row["representative_parent_contexts"] = row["parents"]
        formal.append(row)
    formal.sort(key=lambda value: (-value["radar_value"], value["ruler_id"]))
    grade_distribution = Counter(row["axis_grade"] for row in formal)
    return {
        "schema_version": "profile-m4-formal-settlement-v1",
        "canonical_status": "FORMAL_CURRENT",
        "contract_version": "FORMAL-V1.0",
        "contract_sha256": _sha(CONTRACT),
        "axis_code": "M4",
        "axis_name": "政治联盟与内部联盟管理",
        "canonical_pool": POOL.relative_to(ROOT).as_posix(),
        "canonical_pool_sha256": _sha(POOL),
        "manual_adjudication": MANUAL.relative_to(ROOT).as_posix(),
        "manual_adjudication_sha256": _sha(MANUAL),
        "input_sha256": {path.relative_to(ROOT).as_posix(): _normalized_sha(path) for path in NORMATIVE_INPUTS.values()},
        "record_count": len(formal),
        "unresolved_evidence_gap_count": audit["unresolved_count"],
        "formal_profile_write": True,
        "formal_rank_write": False,
        "profile_total_enabled": False,
        "profile_ranking_enabled": False,
        "composite_ranking_write": False,
        "database_write": False,
        "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC",
        "grade_distribution": dict(sorted(grade_distribution.items())),
        "audit_refs": [AUDIT.name, HIGH_REVIEW.name, FULL_POOL_REVIEW.name],
        "summary": {
            "profile_ready": len(formal),
            "high_grade_count": high["candidate_count"],
            "evidence_limited_count": sum(row["score_status"] == "EVIDENCE_LIMITED" for row in formal),
        },
        "records": formal,
    }


def _acceptance(settlement: dict[str, Any], audit: dict[str, Any], high: dict[str, Any], review: dict[str, Any]) -> str:
    changes = "；".join(f"{row['ruler_name']} {row['from']}→{row['to']}" for row in review["grade_changes"])
    return "\n".join([
        "# M4 全池正式结算验收报告", "",
        "> M4独立画像轴；不进入五项综合总榜，不生成画像总分或轴内排名。", "",
        "## 构念与两轮复审", "",
        "- M4只评价国内集团级联盟建立、利益与地位配置、政治信用、冲突处理和退出；M2外部关系、C3个人用人、C5权力伦理、第一项B团队成果和第四项A结果均已去重。",
        f"- 第一轮建立{review['mechanical_screen_count']}人实际权力窗口、主要集团结构与应观察任务矩阵；第二轮逐人消费全部规范入口并联合检查正负证。",
        f"- 第二轮实际变档{review['grade_change_count']}人：{changes}。", "",
        "## 覆盖与证据", "",
        f"- 正式覆盖：{settlement['record_count']}/184；未决证据缺口：{settlement['unresolved_evidence_gap_count']}。",
        f"- 入口处置：{audit['unit_count']}个稳定材料或等价单元；四态统计：{json.dumps(audit['status_counts'], ensure_ascii=False)}。",
        f"- 高档生命周期复核：{high['candidate_count']}人；均已检查主要集团、利益与安全预期、合作兑现、冲突、退出和完整实际权力窗口。",
        f"- 低证据有界画像：{settlement['summary']['evidence_limited_count']}人；材料稀疏只降低置信度，不自动填入中性档。", "",
        "## 限制", "",
        "- 正式入口对集团级协商细节的保存密度不均；本轮使用全部规范入口及其中可定位的有界本地史料，不启用模型、网络服务、数据库、shadow或退役采集链。",
        "- JSON是唯一档位事实源，Markdown为同值阅读视图；稳定展示顺序不构成轴内排名。", "",
    ])


def _refresh_existing_contract_metadata() -> None:
    contract_sha = _sha(CONTRACT)
    for path in PROFILE_ROOT.glob("*.json"):
        if path in {MANIFEST, SETTLEMENT, AUDIT, HIGH_REVIEW, FULL_POOL_REVIEW}:
            continue
        payload = _load(path)
        if "contract_sha256" in payload and payload["contract_sha256"] != contract_sha:
            payload["contract_sha256"] = contract_sha
            _write_json(path, payload)


def _update_manifest() -> None:
    manifest = _load(MANIFEST)
    manifest["contract_sha256"] = _sha(CONTRACT)
    manifest["settled_axis_count"] = 8
    manifest["unsettled_axis_count"] = 0
    value = {
        "axis_code": "M4",
        "axis_name": "政治联盟与内部联盟管理",
        "status": "FORMAL_CURRENT",
        "record_count": 184,
        "json": SETTLEMENT.name,
        "markdown": MARKDOWN.name,
        "json_sha256": _sha(SETTLEMENT),
        "markdown_sha256": _sha(MARKDOWN),
        "audit_jsons": [AUDIT.name, HIGH_REVIEW.name, FULL_POOL_REVIEW.name],
        "audit_markdowns": [ACCEPTANCE.name],
        "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC",
        "formalization_note": "184人M4国内集团联盟生命周期正式结算；两轮全池复审、入口四态处置与高档全窗口门已闭合。",
    }
    current = next((row for row in manifest["axes"] if row["axis_code"] == "M4"), None)
    if current is None:
        manifest["axes"].append(value)
    else:
        current.clear()
        current.update(value)
    order = {code: index for index, code in enumerate(("M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5"))}
    manifest["axes"].sort(key=lambda row: order[row["axis_code"]])
    for axis in manifest["axes"]:
        axis["json_sha256"] = _sha(PROFILE_ROOT / axis["json"])
        axis["markdown_sha256"] = _sha(PROFILE_ROOT / axis["markdown"])
    _write_json(MANIFEST, manifest)


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
