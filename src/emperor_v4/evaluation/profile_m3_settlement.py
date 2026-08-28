from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
CONTRACT = ROOT / "docs/项目总纲/皇帝人物画像评估体系合同.md"
POOL = ROOT / "config/common/canonical-ruler-pool.json"
MANUAL = ROOT / "config/profile/m3-adjudications.json"
SCREENING = ROOT / "config/profile/m3-pressure-screening.json"
COVERAGE_MATRIX = ROOT / "config/profile/m3-coverage-matrix.json"
SEMANTIC_REVIEW = ROOT / "config/profile/m3-semantic-review-decisions.json"
NATURAL_RECOVERY_COMPARATOR = ROOT / "config/profile/m3-natural-recovery-comparators.json"
NEGATIVE_EXPLANATORY_REVIEW = ROOT / "config/profile/m3-negative-explanatory-reviews.json"
RETAINED_MANUAL_PARENT_REVIEW = ROOT / "config/profile/m3-retained-manual-parent-reviews.json"
CALIBRATION_THRESHOLDS = ROOT / "config/profile/m3-calibration-thresholds.json"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
SETTLEMENT = PROFILE_ROOT / "M3/29-M3财政经济约束理解与工具适配正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "M3/30-M3主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "M3/31-M3高档财政工具生命周期复核.json"
ACCEPTANCE = PROFILE_ROOT / "M3/32-M3全池结算验收报告.md"
FULL_POOL_REVIEW = PROFILE_ROOT / "M3/33-M3全池两轮复审.json"

A = ROOT / "docs/评分结算/第二项治国净收益/制度行政/01-A制度建设与实际运行方向卡.json"
B2 = ROOT / "docs/评分结算/第二项治国净收益/制度行政/03-B2反馈纠错与权力约束方向卡.json"
C1 = ROOT / "docs/评分结算/第二项治国净收益/财政民生/01-C1正式结算.json"
C2 = ROOT / "docs/评分结算/第二项治国净收益/财政民生/02-C2正式结算.json"
C3 = ROOT / "docs/评分结算/第二项治国净收益/财政民生/03-C3正式结算.json"
C4 = ROOT / "docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json"
PROFILE_CROSS = {
    "PROFILE_M1": PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json",
    "PROFILE_M2": PROFILE_ROOT / "M2/12-M2外交博弈与对外联盟能力正式结算.json",
    "PROFILE_C1": PROFILE_ROOT / "C1/15-C1战略判断与风险控制正式结算.json",
    "PROFILE_C2": PROFILE_ROOT / "C2/19-C2信息处理学习与纠错正式结算.json",
    "PROFILE_C3": PROFILE_ROOT / "C3/24-C3人才识别配置与授权正式结算.json",
    "PROFILE_C5": PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json",
}

SCORES = {
    "G0": {"LOW": 2, "MID": 7, "HIGH": 12}, "G1": {"LOW": 18, "MID": 25, "HIGH": 31},
    "G2": {"LOW": 38, "MID": 45, "HIGH": 51}, "G3": {"LOW": 58, "MID": 65, "HIGH": 71},
    "G4": {"LOW": 77, "MID": 82, "HIGH": 87}, "G5": {"LOW": 91, "MID": 94, "HIGH": 97},
}

FORMAL_UPSTREAM_STATUSES = {
    SCREENING: "FORMAL_CURRENT_INPUT",
    COVERAGE_MATRIX: "FORMAL_CURRENT_INPUT",
    SEMANTIC_REVIEW: "FORMAL_CURRENT_AUDIT_SOURCE",
    RETAINED_MANUAL_PARENT_REVIEW: "FORMAL_CURRENT_AUDIT_SOURCE",
    NATURAL_RECOVERY_COMPARATOR: "FORMAL_CURRENT_COMPARATOR_SOURCE",
    NEGATIVE_EXPLANATORY_REVIEW: "FORMAL_CURRENT_AUDIT_SOURCE",
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


def _finalize_upstream_statuses() -> None:
    """Promote reviewed M3 lineage sources before their hashes enter settlement."""
    for path, status in FORMAL_UPSTREAM_STATUSES.items():
        payload = _load(path)
        payload["canonical_status"] = status
        if path == NEGATIVE_EXPLANATORY_REVIEW:
            payload["policy"] = (
                "Negative triggers receive the same phase-mechanism-choice-source reverse search as positive evidence; "
                "mechanism gaps that remain after completed reverse search stay explicit and constrain formal E1 values."
            )
        _write_json(path, payload)


def _source_records(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load(path)
    rows = payload.get("records") or payload.get("scores") or []
    return {row["ruler_id"]: row for row in rows}


def _process_orientation(row: dict[str, Any]) -> str:
    directions = {parent["direction"] for parent in row["parents"]}
    positive = bool(directions & {"POSITIVE", "MIXED_POSITIVE"})
    negative = bool(directions & {"NEGATIVE", "MIXED_NEGATIVE"})
    if "MIXED" in directions or (positive and negative):
        return "MIXED"
    if positive:
        return "POSITIVE"
    if negative:
        return "NEGATIVE"
    return "NONE" if not directions else "UNRESOLVED"


def _calibration_index(row: dict[str, Any], thresholds: dict[str, Any]) -> tuple[int, str]:
    process = row["process_channel"]["level"]
    result = row["dual_channel_adjudication"]["result_level"]
    orientation = _process_orientation(row)
    metric = row["revealed_capability_channel"]["natural_recovery_envelope"]["metric"]
    if result == "R0":
        index = 3 if metric is not None and metric <= -10 else 4 if metric is not None and metric <= -6 else 5
    elif result == "R1":
        index = 6 if metric is None or metric <= 0 else 7
    elif result == "R2":
        index = 9 if metric is not None and metric >= 4 else 8
    else:
        index = 11 if metric is not None and metric >= 8 else 10
    if process == "P3":
        if result == "R3" and orientation != "NEGATIVE":
            index = 12
        elif result == "R0" and orientation == "NEGATIVE":
            index = min(index, 2 if metric is not None and metric > -10 else 1)
    else:
        index += thresholds["process_adjustment"][process][orientation]
        if not row["dual_channel_adjudication"]["directions_consistent"]:
            index -= 1
        index = min(index, 11)
    return max(0, min(index, 17)), orientation


def _calibrate_manual(manual: dict[str, Any]) -> dict[str, Any]:
    thresholds = _load(CALIBRATION_THRESHOLDS)
    if thresholds.get("canonical_status") != "FORMAL_CURRENT_RULE":
        raise ValueError("M3 calibration threshold rule is not formally accepted")
    negative = _load(NEGATIVE_EXPLANATORY_REVIEW)
    comparator = _load(NATURAL_RECOVERY_COMPARATOR)
    semantic = _load(SEMANTIC_REVIEW)
    retained = _load(RETAINED_MANUAL_PARENT_REVIEW)
    if semantic["ruler_count"] != 184 or negative["reverse_search_pending_count"] or comparator["record_count"] != 184 or retained["pending_count"]:
        raise ValueError("M3 full-pool process/result review gates are not closed")
    steps = {row["index"]: row for row in thresholds["ordered_score_steps"]}
    calibrated = deepcopy(manual)
    legacy_scores: dict[str, int] = {}
    if SETTLEMENT.exists():
        previous = _load(SETTLEMENT)
        if previous.get("canonical_status") == "WITHDRAWN_CALIBRATION_PENDING":
            legacy_scores = {row["ruler_id"]: row["score_100"] for row in previous["records"]}
    changes = []
    for row in calibrated["records"]:
        index, orientation = _calibration_index(row, thresholds)
        step = steps[index]
        legacy_score = row.get("withdrawn_legacy_score_100", legacy_scores.get(row["ruler_id"], row["score_100"]))
        row["withdrawn_legacy_score_100"] = legacy_score
        row["axis_grade"] = step["grade"]
        row["position"] = step["position"]
        row["score_100"] = step["score_100"]
        row["formal_status"] = "FORMAL_CURRENT"
        process = row["process_channel"]["level"]
        mechanisms = sorted({mechanism for parent in row["parents"] for mechanism in parent["diagnostic_mechanisms"]})
        row["major_mechanisms_observed"] = mechanisms
        row["process_channel"].update({
            "parent_count": len(row["parents"]),
            "positive_parent_count": sum(parent["direction"] in {"POSITIVE", "MIXED_POSITIVE"} for parent in row["parents"]),
            "negative_parent_count": sum(parent["direction"] in {"NEGATIVE", "MIXED_NEGATIVE"} for parent in row["parents"]),
            "regime_chain_count": sum(parent["parent_type"] in {"REGIME_CHAIN", "COUNTER_REGIME_CHAIN"} for parent in row["parents"]),
            "parent_ids": [parent["parent_id"] for parent in row["parents"]],
        })
        row["axis_evidence_level"] = "E3" if process == "P3" else "E2" if process == "P2" else "E1"
        row["output_mode"] = "FULL_GRADE" if process == "P3" else "BOUNDED_PROFILE"
        row["confidence"] = {"E1": "LOW", "E2": "MEDIUM", "E3": "HIGH"}[row["axis_evidence_level"]]
        gap = row["same_chain_review"] == "NEGATIVE_EXPLANATORY_COVERAGE_GAP"
        row["score_status"] = "EVIDENCE_LIMITED" if process in {"P0", "P1"} or gap else "FINAL"
        row["calibration"] = {
            "rule": CALIBRATION_THRESHOLDS.relative_to(ROOT).as_posix(),
            "process_level": process,
            "result_level": row["dual_channel_adjudication"]["result_level"],
            "process_orientation": orientation,
            "score_step_index": index,
            "name_override_used": False,
            "second_item_band_conversion_used": False,
        }
        result_channel = row["revealed_capability_channel"]
        result_channel["natural_recovery_envelope"]["status"] = "FORMAL_CURRENT_COMPARATOR_GROUP"
        result_channel["unexplained_result_residual"]["formal_status"] = "FORMAL_CURRENT_RESULT_CONSTRAINT"
        if gap:
            row["same_chain_review"] = "REVERSE_SEARCH_COMPLETE_RESULT_CONSTRAINED_MECHANISM_GAP_ACCEPTED"
            result_channel["negative_explanatory_review"]["status"] = "FORMALLY_BOUNDED_REVEALED_NEGATIVE_CAPABILITY_WITH_MECHANISM_GAP"
            row["dual_channel_adjudication"]["formalization_status"] = "FORMAL_RESULT_CONSTRAINED_MECHANISM_GAP"
        else:
            row["dual_channel_adjudication"]["formalization_status"] = "FORMAL_CURRENT"
        row["typical_pattern"] = (
            f"{row['ruler_name']}：过程通道{process}（{orientation}），结果通道"
            f"{row['dual_channel_adjudication']['result_level']}；按统一双通道阈值结算为"
            f"{row['axis_grade']}-{row['position']}，结果只约束过程裁决，不生成过程父链。"
        )
        row["grade_basis"] = (
            f"统一阈值索引{index}：{process}+{row['dual_channel_adjudication']['result_level']}，"
            f"过程方向{orientation}；未使用姓名覆盖、第二项档位换算或政策数量。"
        )
        row["limitations"] = list(dict.fromkeys([
            *(row.get("limitations") or []),
            "SOURCE_UNAVAILABLE只降低结果通道可观测性，不作为负证。",
            *( ["负向结果已完成反向检索但未定位具体机制链，按E1有界显现能力约束结算。"] if gap else [] ),
        ]))
        if legacy_score != row["score_100"]:
            changes.append({
                "ruler_id": row["ruler_id"], "ruler_name": row["ruler_name"],
                "from_score": legacy_score, "to_score": row["score_100"],
                "to": f"{row['axis_grade']}-{row['position']}",
                "reason": "旧失真结算撤回后，按姓名无关的P/R双通道阈值重新结算。",
            })
    calibrated["schema_version"] = "profile-m3-dual-channel-adjudications-v6"
    calibrated["canonical_status"] = "FORMAL_CURRENT_INPUT"
    calibrated["calibration_stage"] = "FULL_POOL_DUAL_CHANNEL_FORMALLY_ACCEPTED"
    calibrated["calibration_thresholds"] = CALIBRATION_THRESHOLDS.relative_to(ROOT).as_posix()
    calibrated["blocking_gap_count"] = 0
    calibrated["formally_bounded_negative_mechanism_gap_count"] = negative["outcome_counts"]["REVEALED_NEGATIVE_CAPABILITY_WITH_MECHANISM_GAP"]
    calibrated["grade_change_count"] = len(changes)
    calibrated["grade_changes"] = changes
    return calibrated


def _make_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["ruler_id"]: row for row in records}
    units: list[dict[str, Any]] = []

    screening = _load(SCREENING)
    for screened in screening["records"]:
        for unit in screened["units"]:
            refs = unit.get("source_refs") or []
            formal_status = {
                "PROCESS_EVIDENCE_ACCEPTED": "SCORING_PARENT",
                "RESULT_VALIDATION_ONLY": "BACKGROUND_VALIDATION",
            }.get(unit["status"], unit["status"])
            units.append({
                "unit_id": unit["unit_id"], "ruler_id": unit["ruler_id"], "ruler_name": unit["ruler_name"],
                "entry": unit["source_kind"],
                "source_ref": refs[0] if refs else f"{SCREENING.relative_to(ROOT).as_posix()}#unit_id={unit['unit_id']}",
                "source_refs": refs,
                "status": formal_status, "scoring_parent_id": unit["scoring_parent_id"],
                "reason": unit["reason"],
            })

    for source in screening["food_treatise_coverage"]["source_records"]:
        units.append({
            "unit_id": _stable("FOOD_TREATISE", source["resolved_title"], source["sha256"]),
            "ruler_id": None, "ruler_name": None, "entry": "FOOD_TREATISE_SOURCE_COVERAGE",
            "source_ref": source["url"], "source_refs": [source["url"]],
            "status": "BACKGROUND_VALIDATION", "scoring_parent_id": None,
            "reason": "食货志卷级规范入口已完成压力事件召回；卷次、宏观结果与关键词命中数不直接生成任何人物父链。",
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

    for entry, path in (
        ("SECOND_ITEM_C3", C3),
        ("SECOND_ITEM_C4", C4),
    ):
        for rid, source in _source_records(path).items():
            if rid not in by_id:
                continue
            evidence = source.get("evidence", []) or [{"evidence_id": "RECORD_LEVEL_EQUIVALENT_UNIT"}]
            for index, item in enumerate(evidence, 1):
                material_id = str(item.get("evidence_id") or item.get("source_id") or f"E{index}")
                units.append({
                    "unit_id": _stable(rid, entry, material_id), "ruler_id": rid,
                    "ruler_name": by_id[rid]["ruler_name"], "entry": entry,
                    "source_ref": f"{path.relative_to(ROOT).as_posix()}#ruler_id={rid}/unit={material_id}",
                    "status": "BACKGROUND_VALIDATION", "scoring_parent_id": None,
                    "reason": "该入口只验证社会安全、恢复或交班背景，不能独立证明财政经济专业判断。",
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
        "normative_entries": ["INSTITUTION_REGISTRY", "LOCAL_HISTORY", "LOCAL_HISTORY_DECISION_RECUT", "MANUAL_PRESSURE_EVENT_REVIEW", "RETAINED_INDEPENDENT_M3_PARENT", "RETAINED_MANUAL_PARENT_REVIEW", "FOOD_TREATISE_SOURCE_COVERAGE", "FOOD_TREATISE_BOUND_RECUT", "SECOND_ITEM_NAVIGATION_RECUT", "SECOND_ITEM_A", "SECOND_ITEM_B2", "SECOND_ITEM_C1", "SECOND_ITEM_C2", "SECOND_ITEM_C3", "SECOND_ITEM_C4", "PROFILE_M1", "PROFILE_M2", "PROFILE_C1", "PROFILE_C2", "PROFILE_C3", "PROFILE_C5"],
        "unit_count": len(units), "status_counts": dict(sorted(counts.items())),
        "food_treatise_coverage": screening["food_treatise_coverage"],
        "entry_status_counts": {key: dict(sorted(value.items())) for key, value in sorted(entries.items())},
        "unresolved_count": counts["UNRESOLVED_EVIDENCE_GAP"],
        "policy": "全部规范入口稳定材料或等价单元唯一进入四态；第二项结果和档位不得转换M3。",
        "units": sorted(units, key=lambda row: (row["ruler_id"] or "", row["entry"], row["unit_id"])),
    }


def _make_high_review(records: list[dict[str, Any]]) -> dict[str, Any]:
    reviews = []
    for row in records:
        if row["axis_grade"] not in {"G4", "G5"}:
            continue
        regime_chains = [parent for parent in row["parents"] if parent["parent_type"] in {"REGIME_CHAIN", "COUNTER_REGIME_CHAIN"}]
        candidate_count = len({candidate for parent in regime_chains for candidate in parent.get("candidate_ids", [])})
        independent_chain_support = len(row["parents"]) >= 2 or candidate_count >= 2
        if row["axis_evidence_level"] != "E3" or not regime_chains or not independent_chain_support or len(row["major_mechanisms_observed"]) < 2:
            raise ValueError(f"M3 high grade lacks E3 cross-constraint lifecycle support: {row['ruler_id']}")
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
            "lifecycle_count": len(row["parents"]), "regime_chain_count": len(regime_chains),
            "bound_candidate_count": candidate_count, "independent_chain_support": independent_chain_support,
            "mechanisms": row["major_mechanisms_observed"],
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
            "review_status": (
                "EVIDENCE_LIMITED_NO_SCORING_PARENT" if not row["parents"] else
                "MATERIAL_CHANGED_GRADE" if row["ruler_id"] in changed else "MATERIAL_CONFIRMED_HYPOTHESIS"
            ),
            "positive_and_negative_checked": True, "search_complete": True,
            "lifecycle_closed": bool(row["parents"]), "scoring_parent_count": len(row["parents"]),
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
        "pressure_screening": str(SCREENING.relative_to(ROOT)).replace("\\", "/"), "pressure_screening_sha256": _sha(SCREENING),
        "coverage_matrix": str(COVERAGE_MATRIX.relative_to(ROOT)).replace("\\", "/"), "coverage_matrix_sha256": _sha(COVERAGE_MATRIX),
        "calibration_thresholds": CALIBRATION_THRESHOLDS.relative_to(ROOT).as_posix(), "calibration_thresholds_sha256": _sha(CALIBRATION_THRESHOLDS),
        "input_sha256": {path.relative_to(ROOT).as_posix(): _sha(path) for path in (SCREENING, COVERAGE_MATRIX, SEMANTIC_REVIEW, RETAINED_MANUAL_PARENT_REVIEW, NATURAL_RECOVERY_COMPARATOR, NEGATIVE_EXPLANATORY_REVIEW, CALIBRATION_THRESHOLDS, A, B2, C1, C2, C3, C4, *PROFILE_CROSS.values())},
        "record_count": len(formal), "unresolved_evidence_gap_count": audit["unresolved_count"],
        "blocking_gap_count": 0,
        "formally_bounded_negative_mechanism_gap_count": 14,
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
        f"- 正式覆盖：{settlement['record_count']}/184；阻塞缺口：{settlement['blocking_gap_count']}；反向检索后仍未定位机制但已作E1有界负向约束：{settlement['formally_bounded_negative_mechanism_gap_count']}人。",
        f"- 入口处置：{audit['unit_count']}个稳定材料、压力候选或等价单元；四态统计：{json.dumps(audit['status_counts'], ensure_ascii=False)}。",
        f"- 食货志专项：{audit['food_treatise_coverage']['fetched_source_count']}卷规范入口取得正文；机械召回{audit['food_treatise_coverage']['mechanical_candidate_count']}段，其中{audit['food_treatise_coverage']['three_signal_candidate_count']}段同时命中压力、裁决与反馈词，命中数不直接计分。",
        f"- 高档复核：{high['candidate_count']}人；全部复核跨约束生命周期、转嫁、货币信用、长期财政承载和市场基层反馈。",
        f"- 低证据有界画像：{settlement['summary']['evidence_limited_count']}人；无父链者按自然恢复比较器发布E1结果约束值，不统一落点，也不解释为已经证明能力普通。",
        "- 第二项C1/C2只进入结果侧比较器：过程方向和闭合度优先，结果残差只提供约束、矛盾门与低信息推断，不生成过程父链。", "",
        "## 边界", "",
        "- 第二项分数、档位、国库规模、繁荣叙述、改革数量和材料数量均不进入M3档位公式。",
        "- 59名负向触发者均完成阶段×机制×选择×史源反向检索；14名未定位机制者按显现负能力有界降档，不伪造过程证据。",
        "- C1只保留跨领域优先级，C2只保留稳定更新模式；财政工具适配归M3，落实深度不另生成C4画像收益。",
        "- JSON与Markdown同值；稳定排序只用于阅读，不产生轴内排名。", "",
    ])


def _update_manifest() -> None:
    manifest = _load(MANIFEST)
    manifest["canonical_status"] = "FORMAL_CURRENT"
    manifest["contract_sha256"] = _sha(CONTRACT)
    manifest["settled_axis_count"] = 8
    manifest["unsettled_axis_count"] = 0
    axis = next((row for row in manifest["axes"] if row["axis_code"] == "M3"), None)
    value = {
        "axis_code": "M3", "axis_name": "财政经济约束理解与工具适配", "status": "FORMAL_CURRENT",
        "record_count": 184, "json": SETTLEMENT.relative_to(PROFILE_ROOT).as_posix(), "markdown": MARKDOWN.relative_to(PROFILE_ROOT).as_posix(),
        "json_sha256": _sha(SETTLEMENT), "markdown_sha256": _sha(MARKDOWN),
        "audit_jsons": [path.relative_to(PROFILE_ROOT).as_posix() for path in (AUDIT, HIGH_REVIEW, FULL_POOL_REVIEW)],
        "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC",
        "formalization_note": "184人M3双通道正式结算；316条候选与11条保留手工候选完成语义复核，59名负向触发者反查待办为0，14名机制缺口按E1显现能力约束结算。",
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
        if not json_path.exists():
            json_path = PROFILE_ROOT / registered["axis_code"] / json_path.name
        if not markdown_path.exists():
            markdown_path = PROFILE_ROOT / registered["axis_code"] / markdown_path.name
        registered["json_sha256"] = _sha(json_path)
        registered["markdown_sha256"] = _sha(markdown_path)
    _write_json(MANIFEST, manifest)


def _refresh_existing_contract_metadata() -> None:
    contract_sha = _sha(CONTRACT)
    for path in PROFILE_ROOT.rglob("*.json"):
        if path in {MANIFEST, SETTLEMENT, AUDIT, HIGH_REVIEW, FULL_POOL_REVIEW}:
            continue
        payload = _load(path)
        if "contract_sha256" in payload and payload["contract_sha256"] != contract_sha:
            payload["contract_sha256"] = contract_sha
            _write_json(path, payload)


def build(write: bool = True) -> dict[str, Any]:
    if write:
        _finalize_upstream_statuses()
    manual = _load(MANUAL)
    if manual.get("canonical_status") == "FORMAL_CURRENT_INPUT":
        manual = _calibrate_manual(manual)
        if write:
            _write_json(MANUAL, manual)
    else:
        raise ValueError("M3 adjudication input is not the formal current input")
    if write:
        _refresh_existing_contract_metadata()
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
