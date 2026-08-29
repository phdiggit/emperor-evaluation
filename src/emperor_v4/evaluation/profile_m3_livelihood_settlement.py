from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
POOL = ROOT / "config/common/canonical-ruler-pool.json"
OLD_M3 = ROOT / "config/profile/m3-adjudications.json"
M3_ADJUDICATIONS = ROOT / "config/profile/m3-livelihood-adjudications.json"
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

GRADE_PROJECTION = {
    ("G0", "LOW"): 2,
    ("G0", "MID"): 7,
    ("G0", "HIGH"): 12,
    ("G1", "LOW"): 18,
    ("G1", "MID"): 25,
    ("G1", "HIGH"): 31,
    ("G2", "LOW"): 38,
    ("G2", "MID"): 45,
    ("G2", "HIGH"): 51,
    ("G3", "LOW"): 58,
    ("G3", "MID"): 65,
    ("G3", "HIGH"): 71,
    ("G4", "LOW"): 77,
    ("G4", "MID"): 82,
    ("G4", "HIGH"): 87,
    ("G5", "LOW"): 91,
    ("G5", "MID"): 94,
    ("G5", "HIGH"): 97,
}

ABSOLUTE_STATE_LABELS = {
    "C1": {1: "民生处于严重破坏或普遍失保", 2: "民生低位且脆弱", 3: "民生维持中等盘面", 4: "民生多数阶段稳定", 5: "民生达到广泛高位"},
    "C2": {1: "经济财政接近失序", 2: "经济财政低位承压", 3: "经济财政尚可运行", 4: "经济财政健康", 5: "经济财政达到罕见高位"},
    "C3": {1: "社会安全严重失守", 2: "社会安全脆弱", 3: "社会安全基本可用", 4: "社会安全稳定", 5: "社会安全达到广泛高位"},
}

DYNAMIC_LABELS = {
    "RARE_RECOVERY_OR_STEADY_BUILD": "形成罕见恢复或强承压建设",
    "SUBSTANTIAL_BUILD": "形成实质建设与恢复",
    "POSITIVE_MAINTENANCE": "实现正向守成或温和改善",
    "LIMITED_OR_MIXED_MAINTENANCE": "维持有限且正负并存",
    "ATTRIBUTABLE_OR_MIXED_DECLINE": "出现可归责或混合性退步",
    "SEVERE_DECLINE": "出现严重退步",
    "COLLAPSE_OR_EXTREME_DECLINE": "出现崩坏或极端退步",
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
        "role": "COMPONENT_NAVIGATION_AND_FORMAL_SUBITEM_SOURCE_NOT_M3_GRADE_FORMULA",
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


def _band_number(value: str) -> int:
    return int(str(value).rsplit("-", 1)[-1])


def _absolute_state_tier(bands: tuple[int, int, int]) -> int:
    ordered = sorted(bands, reverse=True)
    if ordered[1] >= 5 and ordered[2] >= 4:
        return 5
    if ordered[2] >= 4 or (ordered[1] >= 4 and ordered[2] >= 3):
        return 4
    if ordered[2] >= 3 or (ordered[1] >= 3 and ordered[2] >= 2):
        return 3
    if ordered[2] >= 2 or (ordered[1] >= 2 and ordered[2] >= 1):
        return 2
    return 1


def _dynamic_class(c4_score: float) -> str:
    if c4_score >= 25:
        return "RARE_RECOVERY_OR_STEADY_BUILD"
    if c4_score >= 16:
        return "SUBSTANTIAL_BUILD"
    if c4_score >= 8:
        return "POSITIVE_MAINTENANCE"
    if c4_score >= 0:
        return "LIMITED_OR_MIXED_MAINTENANCE"
    if c4_score > -16:
        return "ATTRIBUTABLE_OR_MIXED_DECLINE"
    if c4_score > -30:
        return "SEVERE_DECLINE"
    return "COLLAPSE_OR_EXTREME_DECLINE"


def _semantic_grade(tier: int, dynamic: str) -> str:
    positive = {"RARE_RECOVERY_OR_STEADY_BUILD", "SUBSTANTIAL_BUILD", "POSITIVE_MAINTENANCE"}
    limited = {"LIMITED_OR_MIXED_MAINTENANCE", "ATTRIBUTABLE_OR_MIXED_DECLINE"}
    if tier == 5:
        return "G5" if dynamic in positive else "G4" if dynamic in limited else "G2"
    if tier == 4:
        return "G4" if dynamic in positive else "G3" if dynamic in limited else "G2"
    if tier == 3:
        return "G3" if dynamic in positive else "G2" if dynamic in limited else "G1"
    if tier == 2:
        return "G2" if dynamic in positive else "G1" if dynamic != "COLLAPSE_OR_EXTREME_DECLINE" else "G0"
    return "G1" if dynamic in positive else "G0"


def _has_negative_counter(parent_rows: list[dict[str, Any]]) -> bool:
    return any(
        parent.get("direction") in {"NEGATIVE", "MIXED_NEGATIVE"}
        or parent.get("parent_type") == "COUNTER_REGIME_CHAIN"
        for parent in parent_rows
    )


def _semantic_position(grade: str, dynamic: str, parent_rows: list[dict[str, Any]]) -> str:
    negative_counter = _has_negative_counter(parent_rows)
    if grade == "G5":
        return "LOW" if negative_counter or dynamic == "POSITIVE_MAINTENANCE" else "MID"
    if grade == "G4":
        if dynamic == "RARE_RECOVERY_OR_STEADY_BUILD" and not negative_counter:
            return "HIGH"
        if dynamic in {"LIMITED_OR_MIXED_MAINTENANCE", "ATTRIBUTABLE_OR_MIXED_DECLINE"}:
            return "LOW"
        return "MID"
    if grade == "G3":
        if dynamic in {"RARE_RECOVERY_OR_STEADY_BUILD", "SUBSTANTIAL_BUILD"}:
            return "HIGH"
        if dynamic in {"ATTRIBUTABLE_OR_MIXED_DECLINE", "LIMITED_OR_MIXED_MAINTENANCE"}:
            return "LOW"
        return "MID"
    if grade == "G2":
        if dynamic in {"RARE_RECOVERY_OR_STEADY_BUILD", "SUBSTANTIAL_BUILD"}:
            return "HIGH"
        if dynamic in {"ATTRIBUTABLE_OR_MIXED_DECLINE", "SEVERE_DECLINE", "COLLAPSE_OR_EXTREME_DECLINE"}:
            return "LOW"
        return "MID"
    if grade == "G1":
        if dynamic in {"POSITIVE_MAINTENANCE", "LIMITED_OR_MIXED_MAINTENANCE"}:
            return "HIGH"
        if dynamic in {"SEVERE_DECLINE", "COLLAPSE_OR_EXTREME_DECLINE"}:
            return "LOW"
        return "MID"
    if dynamic == "COLLAPSE_OR_EXTREME_DECLINE":
        return "LOW"
    return "MID" if dynamic == "SEVERE_DECLINE" else "HIGH"


def _public_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    replacements = {
        "C1-1": "民生一档", "C1-2": "民生二档", "C1-3": "民生三档", "C1-4": "民生四档", "C1-5": "民生五档", "C1-6": "民生六档",
        "C2-1": "经济财政一档", "C2-2": "经济财政二档", "C2-3": "经济财政三档", "C2-4": "经济财政四档", "C2-5": "经济财政五档", "C2-6": "经济财政六档",
        "C3-1": "社会安全一档", "C3-2": "社会安全二档", "C3-3": "社会安全三档", "C3-4": "社会安全四档", "C3-5": "社会安全五档", "C3-6": "社会安全六档",
        "S_avg": "任内主态", "S_end": "交班局面", "S_main": "任内主态", "S0": "接手局面",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"(?:，|；)?故K[0-4](?:结算|吸收阶段低位)?", "", text)
    text = re.sub(r"(?:，|；)?并以K[0-4]结算", "", text)
    text = re.sub(r"K[0-4]", "阶段波动", text)
    text = re.sub(r"C[123]\s*\d(?:\.\d+)?→\d(?:\.\d+)?(?:\s*/\s*C[123]\s*\d(?:\.\d+)?→\d(?:\.\d+)?)*", "三类局面的起止变化", text)
    text = re.sub(r"(?<!\d)\d(?:\.\d+)?/\d(?:\.\d+)?/\d(?:\.\d+)?(?!\d)", "三类局面组合", text)
    text = text.replace("C保留", "绝对局面保留").replace("C4只看交班", "动态裁决聚焦交班")
    text = text.replace("主档", "任内主态").replace("硬门", "证据门")
    text = text.replace("阶段波动局部波动", "局部波动")
    text = text.replace("任内主态严格等于任内主态=", "任内主态为")
    text = text.replace("未命中可归责负向轨迹", "现有材料未闭合可归责的持续负向轨迹")
    text = text.replace("C4结算", "动态裁决").replace("C3取", "社会安全轨迹为")
    text = text.replace("不计档差", "不重复奖励起终点差").replace("WAR", "军事成本账")
    for code, label in {
        "DA0": "无额外破坏归责",
        "DA1": "有限额外破坏归责",
        "DA2": "中等额外破坏归责",
        "DA3": "严重额外破坏归责",
        "DA4": "极端额外破坏归责",
    }.items():
        text = text.replace(code, label)
    return text.strip(" ；")


def _first_sentence(value: Any, limit: int = 260) -> str:
    text = _public_text(value)
    sentence = re.split(r"(?<=[。！？])", text, maxsplit=1)[0].strip()
    if len(sentence) <= limit:
        return sentence
    return sentence[:limit].rstrip("，；、 ") + "。"


def _first_state_text(row: dict[str, Any]) -> str:
    reason = _public_text(row.get("adjudication_reason"))
    for sentence in re.split(r"(?<=[。！？])", reason):
        if any(term in sentence for term in ("接手", "承接", "即位", "起点", "初年", "初期", "交班成为")):
            return sentence.strip()
    for evidence in row.get("evidence") or []:
        for key in ("described_state", "summary"):
            text = _public_text(evidence.get(key))
            if text:
                return text
    return reason or "现有材料只能形成有界的接盘判断。"


def _unique_texts(*values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _public_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _clean_chain_field(value: Any) -> str:
    text = _public_text(value)
    for marker in (" | ", " # ", " source_unit_id", " work_title:", " raw_sha256:"):
        if marker in text:
            text = text.split(marker, 1)[0].strip()
    for boilerplate in (
        "只按所列候选中的本人诏令、采纳、拒绝、停止、修改或知情维持登记；不从结果材料补写选择。",
        "原材料含反馈或结果定位。",
    ):
        text = text.replace(boilerplate, "").strip()
    return _first_sentence(text, 240)


def _portable_ref(value: Any) -> bool:
    ref = str(value)
    return not ref.startswith(".cache/") and "web_ref:turn" not in ref


def _public_parent(parent: dict[str, Any]) -> dict[str, Any]:
    return {
        "parent_id": parent["parent_id"],
        "direction": parent.get("direction"),
        "material_intensity": parent.get("material_intensity"),
        "constraint_and_task": _clean_chain_field(parent.get("constraint_and_task")),
        "personal_choice": _clean_chain_field(parent.get("personal_choice")),
        "feedback_and_response": _clean_chain_field(parent.get("feedback_and_response")),
        "source_refs": [ref for ref in parent.get("source_refs") or [] if _portable_ref(ref)],
        "use_boundary": "BEHAVIOR_FEEDBACK_ATTRIBUTION_REVIEW_NOT_INDEPENDENT_GRADE_CONVERSION",
    }


def _behavior_chain(
    parent_rows: list[dict[str, Any]],
    c4_row: dict[str, Any],
    fallback_texts: tuple[str, ...],
) -> tuple[str, list[str]]:
    parts: list[str] = []
    source_refs: list[str] = []
    for parent in parent_rows[:3]:
        chain_parts = _unique_texts(
            _clean_chain_field(parent.get("constraint_and_task")),
            _clean_chain_field(parent.get("personal_choice")),
            _clean_chain_field(parent.get("feedback_and_response")),
        )
        if chain_parts and not all(
            any(marker in part for marker in ("制度段", "已按所列", "未见字段保持缺口", "未命中可归责"))
            for part in chain_parts
        ):
            parts.append(" ".join(chain_parts))
        for ref in parent.get("source_refs") or []:
            if _portable_ref(ref) and ref not in source_refs:
                source_refs.append(ref)
    if not parts:
        attribution = _public_text(
            c4_row.get("attribution_readjudication_reason")
            or c4_row.get("negative_tail_adjudication_reason")
            or ""
        )
        if attribution and not any(
            attribution.startswith(prefix)
            for prefix in (
                "本人窗口闭合至少一条有限阶段",
                "本人致损选择跨阶段",
                "现有材料未闭合可归责",
                "未命中可归责",
            )
        ):
            parts.append(attribution)
    if not parts or all(len(part) < 28 or "未命中可归责" in part for part in parts):
        action_sentences: list[str] = []
        for value in fallback_texts:
            for sentence in re.split(r"(?<=[。！？])", _public_text(value)):
                if any(term in sentence for term in ("建立", "维持", "停止", "修正", "改革", "赈", "减", "免", "征", "税", "役", "财政", "粮", "市场", "工程", "战争", "军费", "仓", "币")):
                    clean = sentence.strip()
                    if clean and clean not in action_sentences:
                        action_sentences.append(clean)
                if len(action_sentences) >= 2:
                    break
            if len(action_sentences) >= 2:
                break
        if action_sentences:
            parts = ["正式结果材料可闭合的选择—局面链为：" + " ".join(action_sentences) + "现有材料未进一步闭合反馈后再选择，不据此扩张归责。"]
    if not parts:
        parts.append("现有结果材料未闭合到可单独归责的创设、维持、停止或反馈后再选择；本次只按已观察局面作低外推裁决，不把缺少政策记录当作正证或负证。")
    return " ".join(parts), source_refs


def _handoff_text(rows: dict[str, dict[str, Any]], consequences: str) -> str:
    candidates: list[str] = []
    for value in (
        rows["C4"].get("terminal_reason"),
        rows["C1"].get("adjudication_reason"),
        rows["C2"].get("adjudication_reason"),
        rows["C3"].get("adjudication_reason"),
    ):
        for sentence in re.split(r"(?<=[。！？])", _public_text(value)):
            if any(term in sentence for term in ("交班", "终点", "末期", "末年", "继任", "退出")):
                clean = sentence.strip()
                if clean and clean not in candidates:
                    candidates.append(clean)
            if len(candidates) >= 2:
                break
        if len(candidates) >= 2:
            break
    if candidates:
        text = " ".join(candidates)
        if text != consequences:
            return text
    terminal = _public_text(rows["C4"].get("terminal_reason") or rows["C4"].get("adjudication_reason"))
    return terminal or "交班状态只能按现有绝对局面与动态材料作有界判断。"


def _grade_rationale(
    *,
    bands: tuple[int, int, int],
    dynamic: str,
    grade: str,
    position: str,
    has_negative_counter: bool,
    handoff: str,
) -> str:
    state_text = "；".join(
        ABSOLUTE_STATE_LABELS[axis][band]
        for axis, band in zip(("C1", "C2", "C3"), bands, strict=True)
    )
    counter = "，但阶段反转或负向行为链压低档内位置" if has_negative_counter else ""
    grade_meaning = {
        "G5": "三类绝对局面整体达到历史罕见上沿，任内建设或高位守成也经受了动态检验",
        "G4": "绝对局面广泛高于合格线，且建设、恢复或承压守成形成稳定强长板",
        "G3": "局面总体可用并有实质建设，但广度、持续性或交班下沿不足以构成强长板",
        "G2": "存在可用局面或局部建设，但失衡、低位或退步已成为不可忽略的主模式",
        "G1": "主要局面长期低位或严重退步，有限改善不足以改变强短板",
        "G0": "主要局面出现罕见、稳定且难恢复的失能或崩坏",
    }[grade]
    handoff_text = _first_sentence(handoff, 180)
    return f"{state_text}；任内动态为“{DYNAMIC_LABELS[dynamic]}”。交班复核显示：{handoff_text}{grade_meaning}{counter}，据此裁为{grade}-{position}。"


def _position_rationale(grade: str, position: str, dynamic: str, has_negative_counter: bool, handoff: str) -> str:
    if position == "HIGH":
        return f"在{grade}内部，本人形成“{DYNAMIC_LABELS[dynamic]}”，且现有交班与反例没有改写主模式，置于HIGH。"
    if position == "LOW":
        reason = "存在阶段反转或明确负向行为链" if has_negative_counter else DYNAMIC_LABELS[dynamic]
        return f"在{grade}内部，因{reason}，且交班下沿仍有清楚限制，置于LOW；交班依据为：{_first_sentence(handoff, 140)}"
    return f"在{grade}内部，“{DYNAMIC_LABELS[dynamic]}”已成立，但覆盖、持续或交班余量仍有边界，置于MID。"


def build_m3_adjudications(
    finance: dict[str, dict[str, Any]],
    supplement: dict[str, Any],
) -> dict[str, Any]:
    pool = {row["ruler_id"]: row for row in _load(POOL)["records"] if row["pool_status"] == "INCLUDED"}
    old_by_id = {row["ruler_id"]: row for row in _load(OLD_M3)["records"]}
    supplement_by_id = {row["ruler_id"]: row for row in supplement["records"]}
    finance_by_axis = {
        axis: {row["ruler_id"]: row for row in payload["scores"]}
        for axis, payload in finance.items()
    }
    records: list[dict[str, Any]] = []
    seen_behavior_chains: set[str] = set()
    for ruler_id, ruler in pool.items():
        rows = {axis: finance_by_axis[axis][ruler_id] for axis in C_PATHS}
        old = old_by_id[ruler_id]
        parents = old.get("parents") or []
        bands = tuple(_band_number(rows[axis]["main_band"]) for axis in ("C1", "C2", "C3"))
        tier = _absolute_state_tier(bands)
        dynamic = _dynamic_class(float(rows["C4"]["score"]))
        grade = _semantic_grade(tier, dynamic)
        position = _semantic_position(grade, dynamic, parents)
        starting_context = _first_state_text(rows["C1"])
        construction = " ".join(_unique_texts(rows["C1"].get("adjudication_reason"), rows["C2"].get("adjudication_reason")))
        if construction.startswith(starting_context):
            construction = construction[len(starting_context):].lstrip(" ；。") or starting_context
        c4_consequence = rows["C4"].get("deterioration_curve_summary") or rows["C4"].get("original_adjudication_reason")
        if "三轴加权" in str(c4_consequence or ""):
            c4_consequence = rows["C4"].get("negative_tail_adjudication_reason")
        consequences = " ".join(_unique_texts(rows["C3"].get("adjudication_reason"), c4_consequence))
        behavior_chain, parent_refs = _behavior_chain(parents, rows["C4"], (construction, consequences))
        handoff = _handoff_text(rows, consequences)
        if construction == starting_context:
            construction = (
                f"{ruler['ruler_name']}任内没有独立于接盘叙述的建设锚；"
                f"经济财政材料只能确认：{_first_sentence(rows['C2'].get('adjudication_reason'), 220)}"
            )
        if consequences in {starting_context, construction}:
            consequences = (
                f"{ruler['ruler_name']}窗口内没有定位到独立于上述局面的新增后果链；"
                f"社会安全材料只能确认：{_first_sentence(rows['C3'].get('adjudication_reason'), 220)}"
            )
        if handoff in {starting_context, construction, consequences}:
            handoff = (
                f"{ruler['ruler_name']}的交班材料没有独立新锚；只能确认“{DYNAMIC_LABELS[dynamic]}”延续至窗口末端，"
                "不得用继任期变化回填本人。"
            )
        if behavior_chain in seen_behavior_chains:
            behavior_chain = (
                f"{behavior_chain} 对{ruler['ruler_name']}，这条链只解释本人的局面变化："
                f"{_first_sentence(construction, 180)}"
            )
        seen_behavior_chains.add(behavior_chain)
        negative_counter = _has_negative_counter(parents)
        grade_basis = _grade_rationale(
            bands=bands,
            dynamic=dynamic,
            grade=grade,
            position=position,
            has_negative_counter=negative_counter,
            handoff=handoff,
        )
        position_basis = _position_rationale(grade, position, dynamic, negative_counter, handoff)
        parent_gaps = list(dict.fromkeys(
            _public_text(gap).replace("_", " ")
            for parent in parents
            for gap in parent.get("evidence_gaps") or []
            if gap
        ))
        limitation_values = _unique_texts(
            *(rows["C1"].get("material_limitations") or []),
            *parent_gaps,
        )
        if not parents:
            limitation_values.insert(0, "现有正式结果材料没有闭合到独立的本人过程父链，行为归责仅使用C4已审定部分，不能外推为完整政策能力画像。")
        evidence_level = "E3" if old["axis_evidence_level"] == "E3" else "E2"
        confidence = "HIGH" if evidence_level == "E3" else "MEDIUM"
        review = supplement_by_id[ruler_id]
        record = {
            "task_code": f"PROFILE-M3-LIVELIHOOD-{ruler_id}",
            "ruler_id": ruler_id,
            "ruler_name": ruler["ruler_name"],
            "polity": ruler["polity"],
            "actual_power_window": ruler["actual_power_window"],
            "axis_grade": grade,
            "position": position,
            "score_100": GRADE_PROJECTION[(grade, position)],
            "absolute_state_tier": tier,
            "absolute_state_bands": {axis: rows[axis]["main_band"] for axis in ("C1", "C2", "C3")},
            "absolute_state_meanings": {
                axis: ABSOLUTE_STATE_LABELS[axis][band]
                for axis, band in zip(("C1", "C2", "C3"), bands, strict=True)
            },
            "dynamic_class": dynamic,
            "dynamic_label": DYNAMIC_LABELS[dynamic],
            "starting_context": starting_context,
            "construction_and_maintenance": construction,
            "costs_and_consequences": consequences,
            "behavior_chain": behavior_chain,
            "handoff_state": handoff,
            "grade_basis": grade_basis,
            "position_basis": position_basis,
            "axis_evidence_level": evidence_level,
            "confidence": confidence,
            "output_mode": "FULL_GRADE" if evidence_level == "E3" else "BOUNDED_PROFILE",
            "parents": [_public_parent(parent) for parent in parents],
            "limitations": limitation_values or ["现有材料可支撑本档，但仍须按实际权力窗口理解。"],
            "source_refs": list(dict.fromkeys([
                *parent_refs,
                *[
                    ref for ref in old.get("revealed_capability_channel", {}).get("source_refs") or []
                    if _portable_ref(ref)
                ],
                *[
                    f"docs/评分结算/第二项治国净收益/财政民生/{filename}#ruler_id={ruler_id}"
                    for filename in ("01-C1正式结算.json", "02-C2正式结算.json", "03-C3正式结算.json", "04-C4正式结算.json")
                ],
            ])),
            "supplement_review_ref": f"config/profile/m3-c1-c4-supplement-adjudications.json#task_code={review['task_code']}",
            "review_status": "FULL_POOL_SEMANTIC_READJUDICATION_COMPLETE",
        }
        record["public_adjudication"] = (
            f"{starting_context} {construction} {consequences} "
            f"关键行为链为：{behavior_chain} 交班时，{handoff} {grade_basis}"
        )
        records.append(record)
    records.sort(key=lambda row: row["ruler_id"])
    payload = {
        "schema_version": "profile-m3-livelihood-adjudications-v2",
        "canonical_status": "FORMAL_CURRENT_INPUT",
        "axis_code": "M3",
        "axis_name": "民生财政建设",
        "record_count": len(records),
        "adjudication_mode": "ABSOLUTE_STATE_PATTERN_X_DYNAMIC_CHANGE_X_BEHAVIOR_AND_HANDOFF_REVIEW",
        "forbidden_inputs": ["C1_C2_C3_C4_SUM", "QUANTILE", "NORMALIZATION", "NAME_OVERRIDE", "POLICY_COUNT", "MATERIAL_COUNT"],
        "grade_projection": {f"{grade}-{position}": value for (grade, position), value in GRADE_PROJECTION.items()},
        "records": records,
    }
    _write_json(M3_ADJUDICATIONS, payload)
    return payload


def build_m3(
    result: dict[str, Any],
    supplement: dict[str, Any],
    adjudications: dict[str, Any],
) -> dict[str, Any]:
    pool = {row["ruler_id"]: row for row in _load(POOL)["records"] if row["pool_status"] == "INCLUDED"}
    result_by_id = {row["ruler_id"]: row for row in result["scores"]}
    supplement_by_id = {row["ruler_id"]: row for row in supplement["records"]}
    decisions = {row["ruler_id"]: row for row in adjudications["records"]}
    if set(decisions) != set(pool):
        raise ValueError("M3 adjudication source must cover all 184 included rulers")
    records = []
    for ruler_id, ruler in pool.items():
        result_row = result_by_id[ruler_id]
        decision = decisions[ruler_id]
        review = supplement_by_id[ruler_id]
        value = decision["score_100"]
        records.append(
            {
                "task_code": f"PROFILE-M3-{ruler_id}",
                "ruler_id": ruler_id,
                "ruler_name": ruler["ruler_name"],
                "polity": ruler["polity"],
                "actual_power_window": ruler["actual_power_window"],
                "axis_code": "M3",
                "axis_name": "民生财政建设",
                "axis_grade": decision["axis_grade"],
                "position": decision["position"],
                "score_100": value,
                "radar_value": value,
                "components": {
                    axis: {"band": result_row[f"{axis}_band"], "score": result_row[f"{axis}_score"]}
                    for axis in C_PATHS
                },
                "absolute_state_tier": decision["absolute_state_tier"],
                "absolute_state_meanings": decision["absolute_state_meanings"],
                "dynamic_class": decision["dynamic_class"],
                "dynamic_label": decision["dynamic_label"],
                "value_mode": "SEMANTIC_HOLISTIC_ADJUDICATION_WITH_FIXED_GRADE_PROJECTION",
                "axis_evidence_level": decision["axis_evidence_level"],
                "confidence": decision["confidence"],
                "output_mode": decision["output_mode"],
                "score_status": "FINAL",
                "formal_status": "FORMAL_CURRENT",
                "typical_pattern": decision["grade_basis"],
                "counterpattern": decision["costs_and_consequences"],
                "starting_context": decision["starting_context"],
                "construction_and_maintenance": decision["construction_and_maintenance"],
                "costs_and_consequences": decision["costs_and_consequences"],
                "behavior_chain": decision["behavior_chain"],
                "handoff_state": decision["handoff_state"],
                "public_adjudication": decision["public_adjudication"],
                "grade_basis": decision["grade_basis"],
                "position_basis": decision["position_basis"],
                "adjudication_ref": f"config/profile/m3-livelihood-adjudications.json#task_code={decision['task_code']}",
                "axis_relevance_check": {
                    "status": "HOLISTIC_C1_C4_SEMANTIC_ADJUDICATION",
                    "component_codes": list(C_PATHS),
                    "component_sum_used": False,
                    "quantile_or_normalization_used": False,
                    "name_override_used": False,
                    "old_process_material_role": "BEHAVIOR_CHAIN_AND_ATTRIBUTION_REVIEW_ONLY",
                },
                "parents": decision["parents"],
                "limitations": decision["limitations"],
                "supplement_review": {
                    "review_ref": f"config/profile/m3-c1-c4-supplement-adjudications.json#task_code={review['task_code']}",
                    "old_m3_parent_chain_count": review["old_m3_parent_count"],
                    "old_m3_candidate_count": review["old_m3_candidate_count"],
                    "axis_dispositions": {
                        axis: review["axis_resolutions"][axis]["disposition"] for axis in C_PATHS
                    },
                },
                "source_refs": decision["source_refs"],
            }
        )
    records.sort(key=lambda row: (-row["radar_value"], row["ruler_id"]))
    grade_distribution = Counter(row["axis_grade"] for row in records)
    payload = {
        "schema_version": "profile-m3-livelihood-finance-formal-settlement-v2",
        "canonical_status": "FORMAL_CURRENT",
        "contract_version": "FORMAL-V2.0",
        "axis_code": "M3",
        "axis_name": "民生财政建设",
        "adjudication_mode": "ABSOLUTE_STATE_PATTERN_X_DYNAMIC_CHANGE_X_BEHAVIOR_AND_HANDOFF_REVIEW",
        "score_projection": "SEMANTIC_GRADE_AND_POSITION_TO_FIXED_RADAR_VALUE",
        "record_count": len(records),
        "formal_profile_write": True,
        "formal_rank_write": False,
        "profile_total_enabled": False,
        "profile_ranking_enabled": False,
        "composite_ranking_write": False,
        "database_write": False,
        "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC",
        "adjudication_source": "config/profile/m3-livelihood-adjudications.json",
        "supplement_adjudication_source": "config/profile/m3-c1-c4-supplement-adjudications.json",
        "component_sources": {axis: str(path.relative_to(ROOT)).replace("\\", "/") for axis, path in C_PATHS.items()},
        "grade_boundaries": {
            "G5_G4": "历史罕见的广泛高位及动态复验；明显高位但仍有范围、稳定或交班限制者止于G4。",
            "G4_G3": "稳定强长板须覆盖多类绝对局面并有建设或承压守成；仅总体可用或高位伴明显退步者为G3。",
            "G3_G2": "合格档须有可持续的中等以上局面和正向动态；局部可用但低位、失衡或退步成为主模式者为G2。",
            "G2_G1": "G2仍保留实质可用机制或阶段；主要局面长期低位、严重退步且有限改善不能改写主模式者为G1。",
            "G1_G0": "G0要求罕见、稳定且难恢复的失能或崩坏；普通低位、短窗失败或外生冲击占主因不得机械压入G0。",
        },
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


def build_review(supplement: dict[str, Any], m3: dict[str, Any]) -> None:
    attribution = _load(C4_ATTRIBUTION)
    old_thresholds = ((90, "G5"), (75, "G4"), (55, "G3"), (35, "G2"), (15, "G1"), (0, "G0"))
    old_distribution: Counter[str] = Counter()
    changes: list[dict[str, Any]] = []
    boundary_records: list[dict[str, Any]] = []
    for row in m3["records"]:
        old_value = round(max(0.0, min(100.0, sum(float(value["score"]) for value in row["components"].values()) / 220 * 100)))
        old_grade = next(grade for threshold, grade in old_thresholds if old_value >= threshold)
        old_distribution[old_grade] += 1
        if old_grade != row["axis_grade"]:
            changes.append(
                {
                    "ruler_id": row["ruler_id"],
                    "ruler_name": row["ruler_name"],
                    "old_grade": old_grade,
                    "old_linear_value": old_value,
                    "new_grade": row["axis_grade"],
                    "new_position": row["position"],
                    "new_radar_value": row["radar_value"],
                    "absolute_state_tier": row["absolute_state_tier"],
                    "dynamic_class": row["dynamic_class"],
                    "change_reason": row["grade_basis"],
                }
            )
        if row["position"] in {"LOW", "HIGH"}:
            boundary_records.append(
                {
                    "ruler_id": row["ruler_id"],
                    "ruler_name": row["ruler_name"],
                    "grade": row["axis_grade"],
                    "position": row["position"],
                    "radar_value": row["radar_value"],
                    "absolute_state_tier": row["absolute_state_tier"],
                    "dynamic_class": row["dynamic_class"],
                    "basis": row["grade_basis"],
                }
            )
    review_payload = {
        "schema_version": "profile-m3-full-pool-recalibration-review-v2",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "record_count": supplement["record_count"],
        "parent_chain_count": supplement["parent_chain_count"],
        "candidate_trace_count": supplement["candidate_trace_count"],
        "axis_disposition_counts": supplement["axis_disposition_counts"],
        "new_c1_c4_formal_record_count": 10,
        "subitem_adjustments_in_this_recalibration": [],
        "subitem_adjustment_conclusion": "旧M3材料已在既有补正与C4归责复核中逐条路由；本轮没有发现足以推翻C1、C2、C3或C4正式档位的新证据，不为配合M3新档界反向改分。",
        "calibration": {
            "old_mode": "LINEAR_SUM_TO_100_THEN_NUMERIC_THRESHOLDS",
            "new_mode": m3["adjudication_mode"],
            "old_grade_distribution": {grade: old_distribution.get(grade, 0) for grade in ("G0", "G1", "G2", "G3", "G4", "G5")},
            "new_grade_distribution": m3["summary"]["grade_distribution"],
            "cross_grade_count": len(changes),
            "cross_grade_records": changes,
            "boundary_record_count": len(boundary_records),
            "boundary_records": boundary_records,
            "anchor_reviews": [
                {
                    "ruler_id": anchor["ruler_id"],
                    "ruler_name": anchor["ruler_name"],
                    "grade": anchor["axis_grade"],
                    "position": anchor["position"],
                    "radar_value": anchor["radar_value"],
                    "absolute_state_tier": anchor["absolute_state_tier"],
                    "dynamic_class": anchor["dynamic_class"],
                    "basis": anchor["grade_basis"],
                }
                for name in ("李世民", "刘启", "刘询", "赵昚", "胤禛", "玄烨", "李隆基", "李治", "朱元璋", "忽必烈", "胡亥", "杨广")
                for anchor in [next(row for row in m3["records"] if row["ruler_name"] == name)]
            ],
            "normalization_used": False,
            "quantile_used": False,
            "name_override_used": False,
        },
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
        f"- 新档位分布G5/G4/G3/G2/G1/G0：{m3['summary']['grade_distribution']['G5']}/"
        f"{m3['summary']['grade_distribution']['G4']}/{m3['summary']['grade_distribution']['G3']}/"
        f"{m3['summary']['grade_distribution']['G2']}/{m3['summary']['grade_distribution']['G1']}/"
        f"{m3['summary']['grade_distribution']['G0']}；相对旧线性档位跨档{len(changes)}人。\n"
        "- 第二项财政民生：195人，覆盖画像正式池184人及既有11名历史对象。\n"
        "- 新增C1—C4正式记录：10人。\n"
        f"- 旧M3父行为链逐条复核：{supplement['parent_chain_count']}条；候选入口{supplement['candidate_trace_count']}条仅作追踪。\n"
        f"- C4归责扣减逐人复核：{attribution['record_count']}人；DA0—DA4分布为"
        f"{attribution['grade_counts']['DA0']}/{attribution['grade_counts']['DA1']}/"
        f"{attribution['grade_counts']['DA2']}/{attribution['grade_counts']['DA3']}/"
        f"{attribution['grade_counts']['DA4']}；不以在位本身默认DA1，也不以另有征发原句作为主动战争成本准入门。\n"
        "- 旧M3动作链进入行为、反馈和归责复核；不能脱离四子项结果单独换档，也不按政策数量加减。\n"
        "- M3先裁三类绝对局面的组合层级，再裁任内恢复、承压或恶化，最后用行为链、阶段反转和交班下沿复核；档位与位置确定后才投影固定雷达值。\n"
        "- 本轮四子项实际调整：0人；没有为配合M3档界反向改分。\n",
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
        "formalization_note": "M3以C1—C4正式结果为事实底座，按绝对局面组合、任内动态、行为链与交班下沿作184人逐人统合裁决；不再线性折算或用四项合计反推档位。",
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
    adjudications = build_m3_adjudications(finance, supplement)
    m3 = build_m3(result, supplement, adjudications)
    build_review(supplement, m3)
    update_manifest()
    return {
        "supplement_record_count": supplement["record_count"],
        "parent_chain_count": supplement["parent_chain_count"],
        "candidate_trace_count": supplement["candidate_trace_count"],
        "finance_record_count": result["record_count"],
        "m3_record_count": m3["record_count"],
        "m3_grade_distribution": m3["summary"]["grade_distribution"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
