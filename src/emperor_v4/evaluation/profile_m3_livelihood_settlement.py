from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
POOL = ROOT / "config/common/canonical-ruler-pool.json"
OLD_M3 = ROOT / "config/profile/m3-adjudications.json"
OLD_SEMANTIC = ROOT / "config/profile/m3-semantic-review-decisions.json"
MISSING = ROOT / "config/profile/m3-c1-c4-missing-ruler-adjudications.json"
SUPPLEMENT = ROOT / "config/profile/m3-c1-c4-supplement-adjudications.json"
C4_ATTRIBUTION = ROOT / "config/second-item/c4-attribution-readjudications.json"
FINANCE_ROOT = ROOT / "docs/评分结算/第二项治国净收益/财政民生"
C_PATHS = {
    "C1": FINANCE_ROOT / "01-C1正式结算.json",
    "C2": FINANCE_ROOT / "02-C2正式结算.json",
    "C3": FINANCE_ROOT / "03-C3正式结算.json",
    "C4": FINANCE_ROOT / "04-C4正式结算.json",
}
RESULT = FINANCE_ROOT / "05-治理结果220分正式结算.json"
SECOND_ITEM_TOTAL = ROOT / "docs/评分结算/第二项治国净收益/01-第二项治国净收益405分正式结算.json"
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
CONTRACT = ROOT / "docs/项目总纲/皇帝人物画像评估体系合同.md"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
M3_SETTLEMENT = PROFILE_ROOT / "M3/29-M3民生财政建设正式结算.json"
M3_MARKDOWN = M3_SETTLEMENT.with_suffix(".md")
M3_REVIEW = PROFILE_ROOT / "M3/30-M3对第二项C1-C4逐人补正审计.json"
M3_ACCEPTANCE = PROFILE_ROOT / "M3/31-M3民生财政建设全池收口.md"

FINANCE_MECHANISMS = {
    "BUDGET_TREASURY",
    "MARKET_TRADE",
    "MONETARY_CREDIT",
    "PUBLIC_WORKS",
    "RELIEF_STORAGE",
    "TAX_LABOR",
    "WAR_FINANCE",
}
C1_MECHANISMS = {"PUBLIC_WORKS", "RELIEF_STORAGE", "TAX_LABOR", "WAR_FINANCE"}

GRADE_THRESHOLDS = (
    (90.0, "G5"),
    (75.0, "G4"),
    (55.0, "G3"),
    (35.0, "G2"),
    (15.0, "G1"),
    (0.0, "G0"),
)
GRADE_RANGES = {
    "G0": (0.0, 15.0),
    "G1": (15.0, 35.0),
    "G2": (35.0, 55.0),
    "G3": (55.0, 75.0),
    "G4": (75.0, 90.0),
    "G5": (90.0, 100.000001),
}


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM forbidden: {path}")
    return json.loads(raw.decode("utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _records_hash(records: list[dict[str, Any]]) -> str:
    serialized = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rerank(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records.sort(key=lambda row: (-float(row["score"]), str(row["ruler_id"])))
    previous: float | None = None
    previous_rank = 0
    for index, row in enumerate(records, start=1):
        score = float(row["score"])
        if previous is None or score != previous:
            previous_rank = index
            previous = score
        row["rank"] = previous_rank
    return records


def _c4_band(score: float) -> str:
    if score < 0:
        if score > -8:
            return "C4N-1"
        if score >= -16:
            return "C4N-2"
        if score >= -25:
            return "C4N-3"
        if score >= -35:
            return "C4N-4"
        if score >= -41:
            return "C4N-5"
        return "C4N-6"
    if score < 8:
        return "C4-1"
    if score < 16:
        return "C4-2"
    if score < 25:
        return "C4-3"
    if score < 35:
        return "C4-4"
    if score < 41:
        return "C4-5"
    return "C4-6"


GENERIC_UNBOUND_PREFIXES = (
    "已按所列食货志原页",
    "食货上原文按",
    "田赋与蠲免制度段",
    "漕运、仓储与赈济制度段",
    "钱币、交钞与流通段",
    "钱钞制度段",
    "盐法与商税段",
    "户口、二税户",
    "户口、黄册",
    "户口、田制",
    "榷场、和籴",
    "金银、盐酒",
)

PARENT_EXCEPTIONS = {
    "M3P-SEM-B8A188804592": ("EXCLUDED_WRONG_RULER_WINDOW", "卷030事实属于李乾顺窗口，不得补入李安全。"),
    "M3P-SEM-B11DAF73C32E": ("EXCLUDED_UNBOUND_DYNASTIC_TREATISE", "《清史稿》卷121泛朝代制度段未绑定载湉1889—1898实际权力窗口。"),
    "M3P-SEM-2CFB1D6AF8CF": ("EXCLUDED_DUPLICATE_PARENT", "与M3P-SEM-08C7529128F9重复同一三长制原文；仅保留本人实施链。"),
    "M3P-SEM-79B68183AF83": ("EXCLUDED_DUPLICATE_UNBOUND_PARENT", "与M3P-SEM-81DABEC0936C共享同一泛制度段，且均未闭合本人具体选择。"),
    "M3P-SEM-82DB285775FE": ("EXCLUDED_DUPLICATE_UNBOUND_PARENT", "与M3P-SEM-8F7020EE5BD3共享同一泛制度段，不重复挂接。"),
    "M3P-SEM-71E6BE5ACD70": ("EXCLUDED_DUPLICATE_UNBOUND_PARENT", "与M3P-SEM-1488F42D114E共享同一泛制度段，不重复挂接。"),
    "M3P-SEM-BC343A900939": ("EXCLUDED_DUPLICATE_UNBOUND_PARENT", "与M3P-SEM-EB9646C47A0C内容完全相同，且均未闭合本人具体选择。"),
    "M3P-SEM-4227251A59DF": ("EXCLUDED_DUPLICATE_UNBOUND_PARENT", "与M3P-SEM-2F00C9DE9F00内容完全相同，且均未闭合本人具体选择。"),
    "M3P-SEM-FD4244A2E2D3": ("CONTEXT_ONLY_AXIS_OUT", "材料主体是战争攻守、筑戍与军事后勤建议，未闭合C1—C4独立民生财政结果。"),
    "M3P-SEM-A0912563B699": ("ACCEPTED_DIRECTION_CORRECTED", "原负向标记错误；归州县、均田租属于行政与赋役接口调整，只作中性补证。"),
    "M3P-SEM-3163DE74DFCF": ("ACCEPTED_DIRECTION_CORRECTED", "原负向标记错误；用途说明与复核构成宫廷财政约束正证。"),
    "M3P-SEM-7F03B0DF0BA6": ("CONTEXT_ONLY_SUCCESSOR_REVERSAL", "停止至大银钞发生于继任朝，只能证明海山方案退出，不得记为海山本人正向选择。"),
    "M3P-SEM-0E2450BC2208": ("CONTEXT_ONLY_UNBOUND_SUMMARY", "泛食货志段未给出可复核的本人选择与结果命题。"),
}

SOCIAL_SAFETY_TERMS = ("死亡", "杀", "饿", "饥民", "流亡", "破家", "鬻子", "人身", "财产", "治安", "安之", "安定", "侵暴", "劳弊")


def _parent_review(parent: dict[str, Any], candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    parent_id = str(parent["parent_id"])
    candidate_ids = [str(value) for value in parent.get("candidate_ids") or []]
    candidate_rows = [candidates[value] for value in candidate_ids if value in candidates]
    text = str(parent.get("constraint_and_task") or "")
    mechanisms = set(parent.get("diagnostic_mechanisms") or [])
    exception = PARENT_EXCEPTIONS.get(parent_id)
    if exception:
        disposition, reason = exception
    elif candidate_rows and all(row.get("disposition") == "AXIS_OUT_WITH_REASON" for row in candidate_rows):
        disposition = "EXCLUDED_AXIS_OUT"
        reason = "该父链全部候选已在旧M3语义复核中判为轴外。"
    elif any(text.startswith(prefix) for prefix in GENERIC_UNBOUND_PREFIXES):
        disposition = "CONTEXT_ONLY_UNBOUND_SUMMARY"
        reason = "制度志概括未闭合到本人、阶段、选择与实现结果，不作为人物行为链。"
    elif parent.get("closure_level") == "ATTRIBUTED_CHOICE_ONLY" or parent.get("delivery_status") == "CHOICE_OBSERVED_DELIVERY_OPEN":
        disposition = "CONTEXT_ONLY_DELIVERY_OPEN"
        reason = "只闭合本人选择或命令，未闭合交付/结果；保留检索上下文，不进入四项分值。"
    else:
        disposition = "ACCEPTED_UNIQUE_PARENT_CHAIN"
        reason = "本人选择、机制与反馈/结果形成父链级闭合；候选入口只作追踪，不重复计链。"
    accepted = disposition.startswith("ACCEPTED")
    result_only = bool(candidate_rows) and all(row.get("disposition") == "RESULT_VALIDATION_ONLY" for row in candidate_rows)
    axis_routes = {
        "C1": "APPLIED_PARENT_CHAIN_SUPPLEMENT" if accepted and mechanisms & C1_MECHANISMS else "CONTEXT_ONLY",
        "C2": "APPLIED_PARENT_CHAIN_SUPPLEMENT" if accepted and mechanisms & FINANCE_MECHANISMS else "CONTEXT_ONLY",
        "C3": "APPLIED_PARENT_CHAIN_SUPPLEMENT" if accepted and any(term in text for term in SOCIAL_SAFETY_TERMS) else "CONTEXT_ONLY_NO_DIRECT_SOCIAL_SAFETY_RESULT",
        "C4": "APPLIED_ATTRIBUTION_CHAIN_SUPPLEMENT" if accepted and not result_only else "CONTEXT_ONLY_NO_ATTRIBUTION_CHAIN",
    }
    if disposition.startswith("EXCLUDED"):
        axis_routes = {axis: disposition for axis in C_PATHS}
    elif disposition.startswith("CONTEXT_ONLY"):
        axis_routes = {axis: disposition for axis in C_PATHS}
    direction = str(parent.get("direction") or "UNRESOLVED_DIRECTION")
    if parent_id == "M3P-SEM-A0912563B699":
        direction = "NEUTRAL_ADMINISTRATIVE_ADJUSTMENT"
    elif parent_id == "M3P-SEM-3163DE74DFCF":
        direction = "POSITIVE"
    return {
        "parent_id": parent_id,
        "candidate_ids": candidate_ids,
        "candidate_count": len(candidate_ids),
        "disposition": disposition,
        "direction": direction,
        "closure_level": parent.get("closure_level"),
        "delivery_status": parent.get("delivery_status"),
        "material_intensity": parent.get("material_intensity"),
        "mechanisms": sorted(mechanisms),
        "choice_types": parent.get("choice_types") or [],
        "chain_summary": text,
        "source_refs": parent.get("source_refs") or [],
        "axis_routes": axis_routes,
        "review_reason": reason,
        "old_parent_ref": f"config/profile/m3-adjudications.json#parent_id={parent_id}",
    }


def _orphan_candidate_review(row: dict[str, Any]) -> dict[str, Any]:
    disposition = str(row.get("disposition") or "")
    mechanisms = set(row.get("mechanisms") or [])
    if disposition == "AXIS_OUT_WITH_REASON":
        routes = {axis: "EXCLUDED_AXIS_OUT_ORPHAN_CANDIDATE" for axis in C_PATHS}
        reason = "旧语义复核已判轴外，且未进入任何父行为链。"
    elif disposition == "RESULT_VALIDATION_ONLY":
        routes = {
            "C1": "APPLIED_RESULT_EVIDENCE_FRAGMENT" if mechanisms & C1_MECHANISMS else "CONTEXT_ONLY",
            "C2": "APPLIED_RESULT_EVIDENCE_FRAGMENT" if mechanisms & FINANCE_MECHANISMS else "CONTEXT_ONLY",
            "C3": "CONTEXT_ONLY_NO_DIRECT_SOCIAL_SAFETY_RESULT",
            "C4": "CONTEXT_ONLY_RESULT_NOT_ATTRIBUTION",
        }
        reason = "结果校验材料可补C1/C2结果边界，但不是独立行为链，也不生成C4归责。"
    else:
        routes = {
            "C1": "APPLIED_PROCESS_EVIDENCE_FRAGMENT" if mechanisms & C1_MECHANISMS else "CONTEXT_ONLY",
            "C2": "APPLIED_PROCESS_EVIDENCE_FRAGMENT" if mechanisms & FINANCE_MECHANISMS else "CONTEXT_ONLY",
            "C3": "CONTEXT_ONLY_NO_DIRECT_SOCIAL_SAFETY_RESULT",
            "C4": "CONTEXT_ONLY_NO_PARENT_CHAIN_CLOSURE",
        }
        reason = "单条过程材料保留为补证片段；未闭合为父行为链，不按链计数或直接改分。"
    return {
        "candidate_id": row["candidate_id"],
        "old_m3_disposition": disposition,
        "direction": row.get("direction"),
        "mechanisms": sorted(mechanisms),
        "source_refs": row.get("source_refs") or [],
        "axis_routes": routes,
        "review_reason": reason,
        "semantic_source_ref": f"config/profile/m3-semantic-review-decisions.json#candidate_id={row['candidate_id']}",
    }
def build_supplement() -> dict[str, Any]:
    pool = [row for row in _load(POOL)["records"] if row["pool_status"] == "INCLUDED"]
    old_records = {row["ruler_id"]: row for row in _load(OLD_M3)["records"]}
    semantic_rows = _load(OLD_SEMANTIC)["records"]
    semantic_by_id = {row["candidate_id"]: row for row in semantic_rows}
    semantic_by_ruler: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in semantic_rows:
        semantic_by_ruler[row["ruler_id"]].append(row)
    finance = {
        axis: {row["ruler_id"]: row for row in _load(path)["scores"]}
        for axis, path in C_PATHS.items()
    }
    missing = {row["ruler_id"]: row for row in _load(MISSING)["records"]}
    attribution_reviews = {row["ruler_id"]: row for row in _load(C4_ATTRIBUTION)["records"]}
    records: list[dict[str, Any]] = []
    disposition_counts: dict[str, dict[str, int]] = {
        axis: defaultdict(int) for axis in C_PATHS
    }
    for sequence, ruler in enumerate(sorted(pool, key=lambda row: row["ruler_id"]), start=1):
        ruler_id = ruler["ruler_id"]
        old = old_records[ruler_id]
        parent_reviews = [_parent_review(parent, semantic_by_id) for parent in old.get("parents") or []]
        linked_candidate_ids = {candidate_id for parent in parent_reviews for candidate_id in parent["candidate_ids"]}
        orphan_reviews = [
            _orphan_candidate_review(row)
            for row in semantic_by_ruler.get(ruler_id, [])
            if row["candidate_id"] not in linked_candidate_ids
        ]
        axis_resolutions: dict[str, Any] = {}
        for axis in C_PATHS:
            before = finance[axis].get(ruler_id)
            override = missing.get(ruler_id, {}).get(axis)
            applicable = [route["parent_id"] for route in parent_reviews if route["axis_routes"][axis].startswith("APPLIED")]
            excluded = [route["parent_id"] for route in parent_reviews if route["axis_routes"][axis].startswith("EXCLUDED")]
            applied_orphans = [row["candidate_id"] for row in orphan_reviews if row["axis_routes"][axis].startswith("APPLIED")]
            excluded_orphans = [row["candidate_id"] for row in orphan_reviews if row["axis_routes"][axis].startswith("EXCLUDED")]
            attribution_review = attribution_reviews.get(ruler_id) if axis == "C4" else None
            if override and axis != "C4":
                disposition = "APPLIED_SCORE_CHANGE_NEW_FORMAL_RECORD"
                after_band = override["main_band"]
                after_score = override["score"]
                reason = override["reason"]
            elif attribution_review:
                final_grade = attribution_review["decision"]["final_grade"]
                final_penalty = float(attribution_review["decision"]["final_penalty"])
                after_score = round(
                    max(-45.0, min(45.0, float(before["positive_score_retained"]) - float(before["deterioration_penalty"]) - final_penalty)),
                    1,
                )
                after_band = _c4_band(after_score)
                if final_grade == before["destructive_amplification_grade"]:
                    disposition = "REVIEWED_C4_ATTRIBUTION_RETAINED"
                else:
                    disposition = "APPLIED_C4_ATTRIBUTION_READJUDICATION"
                reason = attribution_review["decision"]["reason"]
            elif applicable or applied_orphans:
                disposition = "APPLIED_EVIDENCE_SUPPLEMENT_NO_SCORE_CHANGE"
                after_band = before["main_band"]
                after_score = before["score"]
                reason = "旧M3材料已进入该子项补证/归责边界；不足以推翻现有主态或动态分。"
            elif parent_reviews or orphan_reviews:
                disposition = "REVIEWED_NO_APPLICABLE_SCORE_OR_EVIDENCE_CHANGE"
                after_band = before["main_band"]
                after_score = before["score"]
                reason = "旧M3候选已逐条复核，但对本子项仅属背景、已覆盖或轴外。"
            else:
                disposition = "SEARCHED_NO_OLD_M3_CANDIDATE"
                after_band = before["main_band"]
                after_score = before["score"]
                reason = "旧M3全池检索无可路由候选；保留现有第二项正式裁决，不把无命中当负证。"
            disposition_counts[axis][disposition] += 1
            axis_resolutions[axis] = {
                "disposition": disposition,
                "before_band": before["main_band"] if before else None,
                "before_score": before["score"] if before else None,
                "after_band": after_band,
                "after_score": after_score,
                "applied_parent_ids": applicable,
                "excluded_parent_ids": excluded,
                "applied_orphan_candidate_ids": applied_orphans,
                "excluded_orphan_candidate_ids": excluded_orphans,
                "reason": reason,
                "c4_attribution_review_ref": (
                    f"config/second-item/c4-attribution-readjudications.json#task_code={attribution_review['task_code']}"
                    if attribution_review else None
                ),
            }
        records.append(
            {
                "sequence": sequence,
                "task_code": f"PROFILE-M3-C1C4-{ruler_id}",
                "ruler_id": ruler_id,
                "ruler_name": ruler["ruler_name"],
                "polity": ruler["polity"],
                "actual_power_window": ruler["actual_power_window"],
                "old_m3_parent_ids": [parent["parent_id"] for parent in old.get("parents") or []],
                "old_m3_parent_count": len(parent_reviews),
                "old_m3_candidate_count": len(semantic_by_ruler.get(ruler_id, [])),
                "parent_chain_reviews": parent_reviews,
                "orphan_candidate_reviews": orphan_reviews,
                "axis_resolutions": axis_resolutions,
                "missing_formal_record_adjudication_ref": (
                    f"config/profile/m3-c1-c4-missing-ruler-adjudications.json#ruler_id={ruler_id}"
                    if ruler_id in missing else None
                ),
                "review_status": "FULLY_ROUTED_TO_C1_C2_C3_C4",
            }
        )
    payload = {
        "schema_version": "profile-m3-c1-c4-supplement-adjudications-v2",
        "canonical_status": "FORMAL_CURRENT_INPUT",
        "axis_code": "M3",
        "axis_name": "民生财政建设",
        "record_count": len(records),
        "parent_chain_count": sum(row["old_m3_parent_count"] for row in records),
        "candidate_trace_count": sum(row["old_m3_candidate_count"] for row in records),
        "review_scope": "ALL_184_PROFILE_RULERS_AND_ALL_204_OLD_M3_PARENT_CHAINS",
        "policy": {
            "second_item_authority": "C1_C2_C3_C4_ARE_THE_COMPLETE_M3_SETTLEMENT_SOURCE",
            "old_m3_material_role": "SUPPLEMENT_OR_CORRECTION_INPUT_ONLY",
            "no_action_rule": "NO_OLD_M3_HIT_IS_NOT_NEGATIVE_EVIDENCE",
            "no_process_to_result_conversion": True,
            "wrong_window_rule": "AXIS_OUT_WRONG_WINDOW",
            "deduplication_unit": "PARENT_CHAIN",
            "candidate_role": "TRACE_ONLY_NOT_AN_INDEPENDENT_BEHAVIOR_CHAIN",
        },
        "axis_disposition_counts": {
            axis: dict(sorted(counts.items())) for axis, counts in disposition_counts.items()
        },
        "records": records,
    }
    _write_json(SUPPLEMENT, payload)
    return payload


def _new_absolute_record(axis: str, source: dict[str, Any]) -> dict[str, Any]:
    adjudication = source[axis]
    common = {
        "adjudication_reason": adjudication["reason"],
        "confidence": adjudication["confidence"],
        "evidence": source["evidence"],
        "evidence_mode": "DIRECT_LOCAL_WINDOW_READJUDICATION",
        "main_band": adjudication["main_band"],
        "polity": source["polity"],
        "reign_range": source["reign_range"],
        "ruler_id": source["ruler_id"],
        "ruler_name": source["ruler_name"],
        "score": adjudication["score"],
        "state_anchors": adjudication["state_anchors"],
        "m3_supplement_origin": "NEW_FORMAL_RECORD_FROM_M3_C1_C4_READJUDICATION",
    }
    if axis in {"C1", "C2"}:
        common.update(
            {
                "high_band_gate": {
                    "status": "NOT_APPLICABLE_BELOW_HIGH_BAND" if adjudication["main_band"].endswith(("1", "2", "3")) else "PASS",
                    "basis": "按本人窗口本地直接结果材料裁决。",
                },
                "material_limitations": [source["window_note"]],
                "peak_band": None,
                "stability_class_diagnostic_only": None,
            }
        )
    else:
        common.update(
            {
                "authority_attribution": source["window_note"],
                "evidence_refs": [
                    ref
                    for evidence in source["evidence"]
                    for ref in evidence["source_refs"]
                ],
                "stability_class_diagnostic_only": "K2",
            }
        )
    return common


def _new_c4_record(source: dict[str, Any]) -> dict[str, Any]:
    adjudication = source["C4"]
    score = float(adjudication["score"])
    positive = max(score, 0.0)
    penalty = max(-score, 0.0)
    return {
        "adjudication_reason": adjudication["reason"],
        "attribution_factor": adjudication["attribution_factor"],
        "closed_recovery_axes": ["C1", "C2", "C3"] if score > 0 else [],
        "destructive_amplification_grade": "DA0",
        "destructive_amplification_penalty": 0.0,
        "deterioration_attribution": adjudication["deterioration_attribution"],
        "deterioration_curve_summary": adjudication["reason"],
        "deterioration_penalty": penalty,
        "main_band": adjudication["main_band"],
        "negative_tail_adjudication_reason": adjudication["reason"] if score < 0 else None,
        "original_adjudication_reason": adjudication["reason"],
        "period": "post_tang" if source["polity"] in {"清", "西夏"} else "qin_through_tang",
        "polity": source["polity"],
        "positive_score_retained": positive,
        "pre_negative_tail_band": "C4-1" if score < 0 else adjudication["main_band"],
        "pre_negative_tail_raw_score": positive,
        "pre_negative_tail_score": positive,
        "raw_score": score,
        "recovery_score": positive,
        "reign_range": source["reign_range"],
        "ruler_id": source["ruler_id"],
        "ruler_name": source["ruler_name"],
        "score": score,
        "stability_score": 0.0,
        "terminal_band": "C4T-1" if score < 0 else "C4T-3",
        "terminal_cap": 45.0,
        "terminal_cap_applied": False,
        "terminal_reason": adjudication["reason"],
        "weighted_attributable_deterioration": round(penalty / 9.0, 1),
        "weighted_net_recovery_delta": round(positive / 9.0, 1),
        "evidence": source["evidence"],
        "m3_supplement_origin": "NEW_FORMAL_RECORD_FROM_M3_C1_C4_READJUDICATION",
    }


def _apply_c4_attribution_review(row: dict[str, Any], review: dict[str, Any]) -> None:
    decision = review["decision"]
    positive = float(row["positive_score_retained"])
    deterioration = float(row["deterioration_penalty"])
    amplification = float(decision["final_penalty"])
    pre_da_score = round(max(-45.0, min(45.0, positive - deterioration)), 1)
    score = round(max(-45.0, min(45.0, pre_da_score - amplification)), 1)
    original_reason = str(row.get("original_adjudication_reason") or row.get("adjudication_reason") or "")

    row["destructive_amplification_grade"] = decision["final_grade"]
    row["destructive_amplification_penalty"] = amplification
    row["pre_negative_tail_raw_score"] = pre_da_score
    row["pre_negative_tail_score"] = pre_da_score
    row["pre_negative_tail_band"] = _c4_band(pre_da_score)
    row["raw_score"] = score
    row["score"] = score
    row["main_band"] = _c4_band(score)
    row["negative_tail_adjudication_reason"] = decision["reason"] if score < 0 else None
    row["original_adjudication_reason"] = original_reason
    row["attribution_readjudication_reason"] = decision["reason"]
    row["adjudication_reason"] = f"{original_reason} 归责扣减全池复核：{decision['reason']}"
    row["c4_attribution_readjudication"] = {
        "review_status": review["review_status"],
        "previous_grade": decision["previous_grade"],
        "final_grade": decision["final_grade"],
        "final_penalty": amplification,
        "change_type": decision["change_type"],
        "duplicate_control": review["duplicate_control"],
        "review_ref": f"config/second-item/c4-attribution-readjudications.json#task_code={review['task_code']}",
    }
    row.pop("pre_m3_correction", None)
    row.pop("m3_correction_ref", None)


def apply_finance_supplements(supplement: dict[str, Any]) -> dict[str, dict[str, Any]]:
    missing = {row["ruler_id"]: row for row in _load(MISSING)["records"]}
    reviews = {row["ruler_id"]: row for row in supplement["records"]}
    payloads: dict[str, dict[str, Any]] = {}
    for axis, path in C_PATHS.items():
        payload = _load(path)
        indexed = {row["ruler_id"]: row for row in payload["scores"]}
        for ruler_id, source in missing.items():
            indexed[ruler_id] = (
                _new_c4_record(source) if axis == "C4" else _new_absolute_record(axis, source)
            )
        for ruler_id, review in reviews.items():
            row = indexed[ruler_id]
            resolution = review["axis_resolutions"][axis]
            parent_by_id = {
                parent["parent_id"]: parent
                for parent in review["parent_chain_reviews"]
            }
            applied_supplements = [
                {
                    "parent_id": parent_id,
                    "candidate_ids_trace_only": parent_by_id[parent_id]["candidate_ids"],
                    "route": parent_by_id[parent_id]["axis_routes"][axis],
                    "direction": parent_by_id[parent_id]["direction"],
                    "mechanisms": parent_by_id[parent_id]["mechanisms"],
                    "chain_summary": parent_by_id[parent_id]["chain_summary"],
                    "source_refs": parent_by_id[parent_id]["source_refs"],
                    "old_parent_ref": parent_by_id[parent_id]["old_parent_ref"],
                }
                for parent_id in resolution["applied_parent_ids"]
            ]
            orphan_by_id = {
                candidate["candidate_id"]: candidate
                for candidate in review["orphan_candidate_reviews"]
            }
            applied_orphan_supplements = [
                {
                    "candidate_id": candidate_id,
                    "route": orphan_by_id[candidate_id]["axis_routes"][axis],
                    "direction": orphan_by_id[candidate_id]["direction"],
                    "mechanisms": orphan_by_id[candidate_id]["mechanisms"],
                    "source_refs": orphan_by_id[candidate_id]["source_refs"],
                    "semantic_source_ref": orphan_by_id[candidate_id]["semantic_source_ref"],
                }
                for candidate_id in resolution["applied_orphan_candidate_ids"]
            ]
            source_review = {
                "disposition": resolution["disposition"],
                "applied_parent_ids": resolution["applied_parent_ids"],
                "excluded_parent_ids": resolution["excluded_parent_ids"],
                "applied_parent_chain_supplements": applied_supplements,
                "applied_orphan_candidate_ids": resolution["applied_orphan_candidate_ids"],
                "excluded_orphan_candidate_ids": resolution["excluded_orphan_candidate_ids"],
                "applied_orphan_candidate_supplements": applied_orphan_supplements,
                "review_ref": f"config/profile/m3-c1-c4-supplement-adjudications.json#task_code={review['task_code']}",
            }
            if resolution["c4_attribution_review_ref"]:
                source_review["c4_attribution_review_ref"] = resolution["c4_attribution_review_ref"]
            row["m3_supplement_review"] = source_review
        if axis == "C4":
            for review in _load(C4_ATTRIBUTION)["records"]:
                _apply_c4_attribution_review(indexed[review["ruler_id"]], review)
        payload["scores"] = _rerank(list(indexed.values()))
        payload["record_count"] = len(payload["scores"])
        payload["scope"] = "秦至清195人；含画像正式池184人"
        payload["m3_supplement_review"] = {
            "status": "FULL_184_ROUTED",
            "source": "config/profile/m3-c1-c4-supplement-adjudications.json",
            "new_formal_record_count": len(missing),
        }
        if axis == "C4":
            attribution_payload = _load(C4_ATTRIBUTION)
            payload["attribution_readjudication"] = {
                "status": "FULL_184_ADJUDICATED",
                "source": "config/second-item/c4-attribution-readjudications.json",
                "record_count": attribution_payload["record_count"],
                "grade_counts": attribution_payload["grade_counts"],
                "records_sha256": attribution_payload["records_sha256"],
            }
            payload["payload_sha256_basis"] = "canonical_records_json_v1"
            payload["payload_sha256"] = _records_hash(payload["scores"])
        _write_json(path, payload)
        payloads[axis] = payload
    return payloads


def build_result(finance: dict[str, dict[str, Any]]) -> dict[str, Any]:
    indexed = {
        axis: {row["ruler_id"]: row for row in payload["scores"]}
        for axis, payload in finance.items()
    }
    ids = set(indexed["C1"])
    if any(set(rows) != ids for rows in indexed.values()):
        raise ValueError("C1-C4 ID sets differ after M3 supplements")
    records = []
    for ruler_id in ids:
        rows = {axis: indexed[axis][ruler_id] for axis in C_PATHS}
        first = rows["C1"]
        records.append(
            {
                "C1_band": rows["C1"]["main_band"],
                "C1_score": rows["C1"]["score"],
                "C2_band": rows["C2"]["main_band"],
                "C2_score": rows["C2"]["score"],
                "C3_band": rows["C3"]["main_band"],
                "C3_score": rows["C3"]["score"],
                "C4_band": rows["C4"]["main_band"],
                "C4_score": rows["C4"]["score"],
                "polity": first["polity"],
                "reign_range": first["reign_range"],
                "ruler_id": ruler_id,
                "ruler_name": first["ruler_name"],
                "score": round(sum(float(rows[axis]["score"]) for axis in C_PATHS), 1),
            }
        )
    records = _rerank(records)
    payload = _load(RESULT)
    payload["scores"] = records
    payload["record_count"] = len(records)
    payload["scope"] = "秦至清195人；含画像正式池184人"
    payload["payload_sha256_basis"] = "canonical_records_json_v1"
    payload["payload_sha256"] = _records_hash(records)
    payload["m3_sync"] = {
        "axis_name": "民生财政建设",
        "formula": "normalized_100 = clamp(round((C1 + C2 + C3 + C4) / 220 * 100), 0, 100)",
        "supplement_source": "config/profile/m3-c1-c4-supplement-adjudications.json",
    }
    _write_json(RESULT, payload)
    return payload


def sync_second_item_total(result: dict[str, Any]) -> dict[str, Any]:
    payload = _load(SECOND_ITEM_TOTAL)
    result_by_id = {row["ruler_id"]: row for row in result["scores"]}
    records = []
    for row in payload["records"]:
        source = result_by_id[row["ruler_id"]]
        for axis in C_PATHS:
            row[f"{axis}_band"] = source[f"{axis}_band"]
            row[f"{axis}_score"] = source[f"{axis}_score"]
        row["governance_result_score"] = source["score"]
        row["second_item_score"] = round(
            float(row["governance_method_score"])
            + float(row["governance_result_score"])
            + float(row["handoff_score"]),
            1,
        )
        records.append(row)
    records.sort(key=lambda row: (-float(row["second_item_score"]), str(row["ruler_id"])))
    previous_score: float | None = None
    previous_rank = 0
    for index, row in enumerate(records, start=1):
        score = float(row["second_item_score"])
        if previous_score is None or score != previous_score:
            previous_rank = index
            previous_score = score
        row["rank"] = previous_rank
    payload["records"] = records
    payload["record_count"] = len(records)
    payload["payload_sha256"] = _records_hash(records)
    _write_json(SECOND_ITEM_TOTAL, payload)
    table = [
        "| 排名 | 人物 | 政权 | 治理手段/165 | C1/80 | C2/35 | C3/60 | C4/-45—45 | 交接/20 | 总分/405 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in records:
        table.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {float(row['governance_method_score']):.1f} | "
            f"{float(row['C1_score']):.1f} | {float(row['C2_score']):.1f} | {float(row['C3_score']):.1f} | "
            f"{float(row['C4_score']):.1f} | {float(row['handoff_score']):.1f} | **{float(row['second_item_score']):.1f}** |"
        )
    markdown = SECOND_ITEM_TOTAL.with_suffix(".md")
    markdown.write_text(
        _replace_first_table(markdown.read_text(encoding="utf-8"), table),
        encoding="utf-8",
        newline="\n",
    )
    return payload


def _grade(value: float) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if value >= threshold:
            return grade
    raise AssertionError(value)


def _position(value: float, grade: str) -> str:
    low, high = GRADE_RANGES[grade]
    width = high - low
    relative = (value - low) / width if width else 0.5
    if relative < 1 / 3:
        return "LOW"
    if relative < 2 / 3:
        return "MID"
    return "HIGH"


def build_m3(result: dict[str, Any], supplement: dict[str, Any]) -> dict[str, Any]:
    pool = {row["ruler_id"]: row for row in _load(POOL)["records"] if row["pool_status"] == "INCLUDED"}
    result_by_id = {row["ruler_id"]: row for row in result["scores"]}
    supplement_by_id = {row["ruler_id"]: row for row in supplement["records"]}
    records = []
    for ruler_id, ruler in pool.items():
        row = result_by_id[ruler_id]
        raw_220 = float(row["score"])
        value = round(max(0.0, min(100.0, raw_220 / 220.0 * 100.0)))
        grade = _grade(value)
        position = _position(value, grade)
        review = supplement_by_id[ruler_id]
        records.append(
            {
                "task_code": f"PROFILE-M3-{ruler_id}",
                "ruler_id": ruler_id,
                "ruler_name": ruler["ruler_name"],
                "polity": ruler["polity"],
                "actual_power_window": ruler["actual_power_window"],
                "axis_code": "M3",
                "axis_name": "民生财政建设",
                "axis_grade": grade,
                "position": position,
                "score_100": value,
                "radar_value": value,
                "component_total_220": raw_220,
                "components": {
                    axis: {"band": row[f"{axis}_band"], "score": row[f"{axis}_score"]}
                    for axis in C_PATHS
                },
                "value_mode": "SECOND_ITEM_C1_C2_C3_C4_SYNCHRONIZED",
                "axis_evidence_level": "E3",
                "confidence": "HIGH",
                "output_mode": "FORMAL_RESULT_SYNCHRONIZATION",
                "score_status": "FINAL",
                "formal_status": "FORMAL_CURRENT",
                "typical_pattern": (
                    f"{ruler['ruler_name']}的民生财政建设由第二项C1 {row['C1_band']}、"
                    f"C2 {row['C2_band']}、C3 {row['C3_band']}、C4 {row['C4_band']}统合；"
                    f"治理结果{raw_220:.1f}/220，折算画像值{value:.1f}/100。"
                ),
                "counterpattern": "M3不再另行寻找‘本人动作’作为准入门；旧M3材料只用于补正C1—C4证据、窗口和归责。",
                "grade_basis": "C1+C2+C3+C4的正式治理结果按220分满量程线性折算到100分，不另加能力分、政策数或姓名覆盖。",
                "position_basis": "档内位置由连续折算值在本档等宽三分区中的位置确定。",
                "adjudication_ref": f"config/profile/m3-c1-c4-supplement-adjudications.json#task_code={review['task_code']}",
                "axis_relevance_check": {
                    "status": "SECOND_ITEM_C1_C4_RESULT_SYNCHRONIZED",
                    "component_codes": list(C_PATHS),
                    "process_material_conversion_forbidden": True,
                },
                "limitations": [
                    "M3只同步第二项C1—C4正式结果；旧过程材料须先在对应子项完成窗口、归责与方向复核，不能直接换算M3。"
                ],
                "supplement_review": {
                    "review_ref": f"config/profile/m3-c1-c4-supplement-adjudications.json#task_code={review['task_code']}",
                    "old_m3_parent_chain_count": review["old_m3_parent_count"],
                    "old_m3_candidate_count": review["old_m3_candidate_count"],
                    "axis_dispositions": {
                        axis: review["axis_resolutions"][axis]["disposition"] for axis in C_PATHS
                    },
                },
                "source_refs": [
                    f"docs/评分结算/第二项治国净收益/财政民生/{filename}#ruler_id={ruler_id}"
                    for filename in (
                        "01-C1正式结算.json",
                        "02-C2正式结算.json",
                        "03-C3正式结算.json",
                        "04-C4正式结算.json",
                    )
                ],
            }
        )
    records.sort(key=lambda row: (-row["radar_value"], row["ruler_id"]))
    grade_distribution = Counter(row["axis_grade"] for row in records)
    payload = {
        "schema_version": "profile-m3-livelihood-finance-formal-settlement-v1",
        "canonical_status": "FORMAL_CURRENT",
        "contract_version": "FORMAL-V2.0",
        "axis_code": "M3",
        "axis_name": "民生财政建设",
        "formula": "score_100 = clamp(round((C1_80 + C2_35 + C3_60 + C4_signed_-45_to_45) / 220 * 100), 0, 100)",
        "record_count": len(records),
        "formal_profile_write": True,
        "formal_rank_write": False,
        "profile_total_enabled": False,
        "profile_ranking_enabled": False,
        "composite_ranking_write": False,
        "database_write": False,
        "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC",
        "supplement_adjudication_source": "config/profile/m3-c1-c4-supplement-adjudications.json",
        "second_item_result_source": "docs/评分结算/第二项治国净收益/财政民生/05-治理结果220分正式结算.json",
        "grade_thresholds": {"G0": "0—<15", "G1": "15—<35", "G2": "35—<55", "G3": "55—<75", "G4": "75—<90", "G5": "90—100"},
        "summary": {
            "grade_distribution": {
                grade: grade_distribution.get(grade, 0)
                for grade in ("G0", "G1", "G2", "G3", "G4", "G5")
            },
            "minimum_score_100": min(row["score_100"] for row in records),
            "maximum_score_100": max(row["score_100"] for row in records),
            "supplemented_old_parent_chain_count": supplement["parent_chain_count"],
            "candidate_trace_count": supplement["candidate_trace_count"],
        },
        "records": records,
    }
    _write_json(M3_SETTLEMENT, payload)
    return payload


def _replace_first_table(text: str, table_lines: list[str]) -> str:
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("| "))
    end = start
    while end < len(lines) and lines[end].startswith("|") and lines[end].endswith("|"):
        end += 1
    return "\n".join([*lines[:start], *table_lines, *lines[end:]]) + "\n"


def _detail_block(axis: str, row: dict[str, Any]) -> str:
    evidence = row.get("evidence") or []
    refs = [str(ref) for unit in evidence for ref in unit.get("source_refs") or []]
    return "\n".join(
        [
            f"### {row['ruler_name']}（{row['polity']}，分项第{row['rank']}名）",
            "",
            f"- 正式裁决：`{row['main_band']}`，{row['score']}分。",
            f"- 裁决理由：{row['adjudication_reason']}",
            f"- M3补正：`{row['m3_supplement_review']['disposition']}`；旧材料逐条处置见补正审计。",
            f"- 史源定位：{'；'.join(refs) if refs else '沿用原正式裁决证据。'}",
            "",
        ]
    )


def render_finance_markdowns(finance: dict[str, dict[str, Any]], result: dict[str, Any]) -> None:
    headers = {
        "C1": [
            "| 排名 | 人物 | 政权 | 全任曲线 S0→S_main→S_end | 主档 | 分数/80 |",
            "|---:|---|---|---|---|---:|",
        ],
        "C2": [
            "| 排名 | 人物 | 政权 | 全任曲线 S0→S_main→S_end | 主档 | 分数/35 |",
            "|---:|---|---|---|---|---:|",
        ],
        "C3": [
            "| 排名 | 人物 | 政权 | 全任曲线 S0→S_main→S_end | K稳定性（诊断） | 主档 | 分数/60 |",
            "|---:|---|---|---|---|---|---:|",
        ],
        "C4": [
            "| 排名 | 人物 | 政权 | 动态构成：净恢复 + K稳定承压 - 恶化 - DA | 注解 | C4档 | C4分 |",
            "|---:|---|---|---|---|---|---:|",
        ],
    }
    missing_ids = {row["ruler_id"] for row in _load(MISSING)["records"]}
    for axis, payload in finance.items():
        table = list(headers[axis])
        for row in payload["scores"]:
            if axis in {"C1", "C2"}:
                anchors = row["state_anchors"]
                middle = anchors.get("S_avg") or anchors.get("S_main")
                curve = f"{anchors['S0']}→{middle}→{anchors['S_end']}"
                if row.get("peak_band"):
                    curve += f"（峰值：{row['peak_band']}）"
                table.append(
                    f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {curve} | "
                    f"{row['main_band']} | **{float(row['score']):.1f}** |"
                )
            elif axis == "C3":
                anchors = row["state_anchors"]
                middle = anchors.get("S_main") or anchors.get("S_avg")
                curve = f"{anchors['S0']}→{middle}→{anchors['S_end']}"
                table.append(
                    f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {curve} | "
                    f"{row.get('stability_class_diagnostic_only') or '—'} | {row['main_band']} | **{float(row['score']):.1f}** |"
                )
            else:
                recovery = float(row.get("recovery_score") or 0.0)
                stability = float(row.get("stability_score") or 0.0)
                deterioration = float(row.get("deterioration_penalty") or 0.0)
                da = float(row.get("destructive_amplification_penalty") or 0.0)
                dynamic = f"{recovery:.1f} + K {stability:.1f} - {deterioration:.1f} - {da:.1f} = {float(row['raw_score']):.1f}"
                notes = []
                if row.get("closed_recovery_axes"):
                    notes.append("恢复轴=" + "/".join(row["closed_recovery_axes"]))
                if row.get("deterioration_attribution") not in {None, "NONE"}:
                    notes.append("恶化归责=" + str(row["deterioration_attribution"]))
                if row.get("destructive_amplification_grade") not in {None, "DA0"}:
                    notes.append(str(row["destructive_amplification_grade"]) + "放大")
                if row.get("terminal_cap_applied"):
                    notes.append("终局封顶=" + str(row["terminal_cap"]))
                table.append(
                    f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {dynamic} | "
                    f"{'；'.join(notes) or '—'} | {row['main_band']} | **{float(row['score']):.1f}** |"
                )
        path = C_PATHS[axis].with_suffix(".md")
        text = _replace_first_table(path.read_text(encoding="utf-8"), table)
        text = text.replace("185人", "195人")
        for row in payload["scores"]:
            if row["ruler_id"] in missing_ids and f"### {row['ruler_name']}（" not in text:
                text += "\n" + _detail_block(axis, row)
        path.write_text(text, encoding="utf-8", newline="\n")

    result_table = [
        "| 排名 | 人物 | 政权 | C1档/80 | C2档/35 | C3档/60 | C4档/-45—45 | 合计/220 |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in result["scores"]:
        result_table.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | "
            f"{row['C1_band']}/{float(row['C1_score']):.1f} | {row['C2_band']}/{float(row['C2_score']):.1f} | "
            f"{row['C3_band']}/{float(row['C3_score']):.1f} | {row['C4_band']}/{float(row['C4_score']):.1f} | "
            f"**{float(row['score']):.1f}** |"
        )
    result_text = _replace_first_table(RESULT.with_suffix(".md").read_text(encoding="utf-8"), result_table)
    RESULT.with_suffix(".md").write_text(result_text.replace("185人", "195人"), encoding="utf-8", newline="\n")
    readme = FINANCE_ROOT / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("185人", "195人").replace("覆盖185人", "覆盖195人"),
        encoding="utf-8",
        newline="\n",
    )


def _render_m3(payload: dict[str, Any]) -> str:
    lines = [
        "# M3 民生财政建设正式结算",
        "",
        "M3与第二项财政民生完全同步：C1、C2、C3、C4先在第二项完成逐人正式裁决，再把治理结果220分线性折算为画像轴100分。旧M3检索材料仅用于补正四子项，不再要求每人必须找到独立‘动作链’。",
        "",
        "| 人物 | 政权 | C1 | C2 | C3 | C4 | 治理结果/220 | M3/100 | 档位 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["records"]:
        c = row["components"]
        lines.append(
            f"| {row['ruler_name']} | {row['polity']} | {c['C1']['score']} | {c['C2']['score']} | "
            f"{c['C3']['score']} | {c['C4']['score']} | {row['component_total_220']} | "
            f"{row['score_100']} | {row['axis_grade']}-{row['position']} |"
        )
    lines.extend(
        [
            "",
            "## 旧M3材料处置",
            "",
        "184人均在 `config/profile/m3-c1-c4-supplement-adjudications.json` 有逐人记录。旧材料按父行为链去重后逐条路由为补证、归责补充、背景、已覆盖或轴外；候选入口仅作追踪。李安全的错窗材料和载湉的泛朝代制度段已明确排除。",
            "",
        ]
    )
    return "\n".join(lines)


def build_review(supplement: dict[str, Any], m3: dict[str, Any]) -> None:
    attribution = _load(C4_ATTRIBUTION)
    review_payload = {
        "schema_version": "profile-m3-c1-c4-full-pool-review-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "record_count": supplement["record_count"],
        "parent_chain_count": supplement["parent_chain_count"],
        "candidate_trace_count": supplement["candidate_trace_count"],
        "axis_disposition_counts": supplement["axis_disposition_counts"],
        "new_c1_c4_formal_record_count": 10,
        "c4_attribution_readjudication": {
            "source": "config/second-item/c4-attribution-readjudications.json",
            "record_count": attribution["record_count"],
            "grade_counts": attribution["grade_counts"],
            "records_sha256": attribution["records_sha256"],
            "policy": attribution["policy"],
        },
        "wrong_window_corrections": [
            {"ruler_id": "RULER-XIXIA-LIANQUAN", "candidate_id": "M3H-69D7C4E148F00DAC", "reason": "volume-030属于李乾顺窗口。"},
            {"ruler_id": "RULER-PUBLIC-79839092B61C3D74", "candidate_id": "M3-FT-A348B2D36AF7F0C9", "reason": "卷121泛制度段未绑定1889—1898本人窗口。"},
        ],
        "records": [
            {
                "task_code": row["task_code"],
                "ruler_id": row["ruler_id"],
                "ruler_name": row["ruler_name"],
                "old_m3_parent_count": row["old_m3_parent_count"],
                "old_m3_candidate_count": row["old_m3_candidate_count"],
                "parent_chain_reviews": row["parent_chain_reviews"],
                "orphan_candidate_reviews": row["orphan_candidate_reviews"],
                "axis_resolutions": row["axis_resolutions"],
                "axis_dispositions": {
                    axis: row["axis_resolutions"][axis]["disposition"] for axis in C_PATHS
                },
            }
            for row in supplement["records"]
        ],
    }
    _write_json(M3_REVIEW, review_payload)
    from emperor_v4.evaluation.profile_markdown import render_profile_markdown

    M3_MARKDOWN.write_text(render_profile_markdown(m3), encoding="utf-8", newline="\n")
    M3_ACCEPTANCE.write_text(
        "# M3 民生财政建设全池收口\n\n"
        "- 画像正式池：184人，M3非空184人。\n"
        "- 第二项财政民生：195人，覆盖画像正式池184人及既有11名历史对象。\n"
        "- 新增C1—C4正式记录：10人。\n"
        f"- 旧M3父行为链逐条复核：{supplement['parent_chain_count']}条；候选入口{supplement['candidate_trace_count']}条仅作追踪。\n"
        f"- C4归责扣减逐人复核：{attribution['record_count']}人；DA0—DA4分布为"
        f"{attribution['grade_counts']['DA0']}/{attribution['grade_counts']['DA1']}/"
        f"{attribution['grade_counts']['DA2']}/{attribution['grade_counts']['DA3']}/"
        f"{attribution['grade_counts']['DA4']}；不以在位本身默认DA1，也不以另有征发原句作为主动战争成本准入门。\n"
        "- 旧M3动作链不再直接裁M3；只作为C1—C4补证、归责、背景或轴外审计。\n"
        "- M3公式：`clamp(round((C1+C2+C3+C4)/220*100), 0, 100)`。\n",
        encoding="utf-8",
        newline="\n",
    )


def update_manifest() -> None:
    manifest = _load(MANIFEST)
    manifest["contract_version"] = "FORMAL-V2.0"
    manifest["contract_sha256"] = _sha(CONTRACT)
    manifest["canonical_pool_sha256"] = _sha(POOL)
    value = {
        "axis_code": "M3",
        "axis_name": "民生财政建设",
        "status": "FORMAL_CURRENT",
        "record_count": 184,
        "json": M3_SETTLEMENT.relative_to(PROFILE_ROOT).as_posix(),
        "markdown": M3_MARKDOWN.relative_to(PROFILE_ROOT).as_posix(),
        "json_sha256": _sha(M3_SETTLEMENT),
        "markdown_sha256": _sha(M3_MARKDOWN),
        "audit_jsons": [M3_REVIEW.relative_to(PROFILE_ROOT).as_posix()],
        "audit_markdowns": [M3_ACCEPTANCE.relative_to(PROFILE_ROOT).as_posix()],
        "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC",
        "formalization_note": "M3改为第二项C1—C4同步的民生财政建设轴；184人全覆盖，旧316条候选逐条路由，原财政民生快照缺失的10人已补齐四子项；C4归责扣减已按C1/C2/C3吸收边界逐人重裁。",
    }
    current = next(row for row in manifest["axes"] if row["axis_code"] == "M3")
    current.clear()
    current.update(value)
    _write_json(MANIFEST, manifest)


def run() -> dict[str, Any]:
    supplement = build_supplement()
    finance = apply_finance_supplements(supplement)
    result = build_result(finance)
    sync_second_item_total(result)
    render_finance_markdowns(finance, result)
    m3 = build_m3(result, supplement)
    build_review(supplement, m3)
    update_manifest()
    return {
        "supplement_record_count": supplement["record_count"],
        "parent_chain_count": supplement["parent_chain_count"],
        "candidate_trace_count": supplement["candidate_trace_count"],
        "finance_record_count": result["record_count"],
        "m3_record_count": m3["record_count"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
