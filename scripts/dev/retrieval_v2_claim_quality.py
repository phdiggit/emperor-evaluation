from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence


BIOGRAPHY_SOURCE_SHAPES = {"object_biography_candidate", "object_existing_source_candidate", "title_name_candidate"}
ACTION_ANCHORS = (
    "诏",
    "命",
    "拜",
    "授",
    "任",
    "用",
    "擢",
    "封",
    "使",
    "遣",
    "令",
    "领",
    "将兵",
    "将军",
    "帅",
    "率",
    "督",
    "镇",
    "守",
    "留守",
    "总制",
    "提督",
    "征",
    "讨",
    "伐",
    "攻",
    "克",
    "破",
    "平",
    "谏",
    "荐",
    "保",
    "诛",
    "罢",
    "废",
    "黜",
)
OUTCOME_ANCHORS = (
    "胜",
    "败",
    "克",
    "破",
    "平",
    "降",
    "定",
    "捷",
    "功",
    "封",
    "进",
    "复",
    "失",
    "败绩",
    "伏诛",
    "被诛",
    "坐",
    "罪",
    "害",
    "乱",
)
OPPORTUNITY_ACTION_TERMS = tuple(dict.fromkeys((*ACTION_ANCHORS, "独专", "专擅", "擅权", "纳贿", "构党", "结党", "壅蔽")))
OPPORTUNITY_OUTCOME_TERMS = tuple(dict.fromkeys((*OUTCOME_ANCHORS, "获", "俘", "斩", "擒", "降", "赐", "赏", "追封", "配享")))
NEGATIVE_ACTION_TERMS = ("诛", "伏诛", "被诛", "罢", "废", "黜", "下狱", "坐罪", "谋反", "专擅", "擅权", "纳贿", "构党", "结党", "壅蔽")
TACTICAL_SUBEVENT_ANCHORS = ("攻", "克", "破", "下", "败", "追", "斩", "擒")
CHAIN_ANCHORS = ("征", "讨", "伐", "平", "镇", "守", "留守", "总制", "提督", "任", "拜", "授", "命")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def normalized_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def sha256_text(value: str, *, length: int = 20) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length].upper()


def unique_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def object_cache_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    return row.get("object_source_cache") if isinstance(row.get("object_source_cache"), Mapping) else {}


def candidate_aliases(row: Mapping[str, Any]) -> list[str]:
    aliases = unique_strings([row.get("object_name"), row.get("person_name"), *(row.get("matched_aliases") or [])])
    return sorted(aliases, key=len, reverse=True)


def alias_positions(text: str, aliases: list[str]) -> list[int]:
    positions: set[int] = set()
    for alias in aliases:
        if not alias:
            continue
        start = 0
        while True:
            index = text.find(alias, start)
            if index < 0:
                break
            positions.add(index)
            start = index + len(alias)
    return sorted(positions)


def alias_mention_count(text: str, aliases: list[str]) -> int:
    positions = alias_positions(normalized_text(text), [normalized_text(alias) for alias in aliases])
    return len(positions)


def biography_like_source(row: Mapping[str, Any]) -> bool:
    object_cache = object_cache_row(row)
    source_shape = str(object_cache.get("source_shape") or row.get("source_shape") or "")
    quality_flags = {str(flag) for flag in object_cache.get("quality_flags") or row.get("quality_flags") or []}
    return source_shape in BIOGRAPHY_SOURCE_SHAPES or "object_biography" in quality_flags


def has_anchor_near_alias(text: str, aliases: list[str], anchors: tuple[str, ...], *, window: int = 18) -> bool:
    if not text or not aliases:
        return False
    positions = alias_positions(text, aliases)
    for position in positions:
        start = max(0, position - window)
        end = min(len(text), position + max((len(alias) for alias in aliases), default=1) + window)
        nearby = text[start:end]
        if any(anchor in nearby for anchor in anchors):
            return True
    return False


def candidate_slice_risk_flags(row: Mapping[str, Any]) -> list[str]:
    if not biography_like_source(row):
        return []
    object_cache = object_cache_row(row)
    aliases = candidate_aliases(row)
    section_heading = str(object_cache.get("section_heading") or row.get("section_heading") or "").strip()
    flags: list[str] = []
    if section_heading and aliases and not any(alias in section_heading for alias in aliases):
        flags.append("wrong_person_section_risk")
    text = str(row.get("text") or row.get("raw_text") or "")
    if len(text) >= 260 and alias_mention_count(text, aliases) <= 1:
        flags.append("weak_single_mention_risk")
    return flags


def slice_claim_eligibility(row: Mapping[str, Any]) -> dict[str, Any]:
    text = str(row.get("text") or row.get("raw_text") or "")
    aliases = candidate_aliases(row)
    risk_flags = candidate_slice_risk_flags(row)
    mention_count = alias_mention_count(text, aliases)
    has_action = has_anchor_near_alias(text, aliases, ACTION_ANCHORS)
    has_outcome = has_anchor_near_alias(text, aliases, OUTCOME_ANCHORS)
    mention_role = "primary" if mention_count > 1 or has_action or has_outcome else "incidental"
    claim_eligible = True
    reasons: list[str] = []
    if risk_flags and mention_role == "incidental":
        claim_eligible = False
        reasons.extend(risk_flags)
        reasons.append("no_action_or_outcome_near_object")
    return {
        "claim_eligible": claim_eligible,
        "mention_role": mention_role,
        "mention_count": mention_count,
        "support_level_hint": "direct" if claim_eligible else "context",
        "risk_flags": risk_flags,
        "near_object_anchors": {"action": has_action, "outcome": has_outcome},
        "reasons": reasons,
    }


def anchor_terms_in_text(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term and term in text]


def slice_opportunity(row: Mapping[str, Any]) -> dict[str, Any]:
    text = str(row.get("text") or row.get("raw_text") or "")
    eligibility = slice_claim_eligibility(row)
    action_terms = anchor_terms_in_text(text, OPPORTUNITY_ACTION_TERMS)
    outcome_terms = anchor_terms_in_text(text, OPPORTUNITY_OUTCOME_TERMS)
    negative_terms = anchor_terms_in_text(text, NEGATIVE_ACTION_TERMS)
    has_opportunity = bool(eligibility["claim_eligible"] and (action_terms or outcome_terms))
    weight = 0
    if has_opportunity:
        weight = 1
        if action_terms and outcome_terms:
            weight += 1
        if negative_terms:
            weight += 1
        if len(set(action_terms)) >= 3 or len(set(outcome_terms)) >= 3:
            weight += 1
    return {
        "has_opportunity": has_opportunity,
        "opportunity_weight": weight,
        "action_terms": action_terms[:12],
        "outcome_terms": outcome_terms[:12],
        "negative_terms": negative_terms[:8],
        "slice_code": str(row.get("slice_code") or row.get("slice_cache_code") or ""),
        "object_name": str(row.get("object_name") or row.get("person_name") or ""),
        "claim_eligible": eligibility["claim_eligible"],
    }


def suggested_claim_budget(opportunity_count: int, opportunity_weight: int, slice_count: int) -> int:
    if opportunity_count <= 0:
        return 0
    base = max(opportunity_count, (opportunity_weight + 1) // 2)
    cap = 8 if slice_count >= 4 else max(3, slice_count * 2)
    return max(1, min(cap, base))


def estimate_claim_opportunities(
    candidate_slices: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    by_object: dict[str, dict[str, Any]] = {}
    for row in candidate_slices:
        object_name = str(row.get("object_name") or row.get("person_name") or "").strip()
        if not object_name:
            continue
        entry = by_object.setdefault(
            object_name,
            {
                "slice_count": 0,
                "eligible_slice_count": 0,
                "opportunity_count": 0,
                "opportunity_weight": 0,
                "action_terms": set(),
                "outcome_terms": set(),
                "negative_terms": set(),
                "opportunity_slices": [],
            },
        )
        entry["slice_count"] += 1
        opportunity = slice_opportunity(row)
        if opportunity["claim_eligible"]:
            entry["eligible_slice_count"] += 1
        if opportunity["has_opportunity"]:
            entry["opportunity_count"] += 1
            entry["opportunity_weight"] += int(opportunity["opportunity_weight"])
            entry["action_terms"].update(opportunity["action_terms"])
            entry["outcome_terms"].update(opportunity["outcome_terms"])
            entry["negative_terms"].update(opportunity["negative_terms"])
            entry["opportunity_slices"].append(opportunity["slice_code"])
    claim_counts: dict[str, int] = {}
    for claim in claims or []:
        object_name = claim_text(claim, "object_name", "object").strip()
        if object_name:
            claim_counts[object_name] = claim_counts.get(object_name, 0) + 1
    objects: dict[str, dict[str, Any]] = {}
    for object_name, entry in sorted(by_object.items()):
        budget = suggested_claim_budget(
            int(entry["opportunity_count"]),
            int(entry["opportunity_weight"]),
            int(entry["slice_count"]),
        )
        actual = claim_counts.get(object_name, 0)
        risk = ""
        if actual and budget and actual < max(1, budget - 1):
            risk = "possible_undercoverage"
        elif not actual and budget:
            risk = "missing_claims"
        objects[object_name] = {
            "slice_count": entry["slice_count"],
            "eligible_slice_count": entry["eligible_slice_count"],
            "opportunity_count": entry["opportunity_count"],
            "opportunity_weight": entry["opportunity_weight"],
            "suggested_claim_budget": budget,
            "actual_claim_count": actual,
            "undercoverage_risk": risk,
            "action_terms": sorted(entry["action_terms"]),
            "outcome_terms": sorted(entry["outcome_terms"]),
            "negative_terms": sorted(entry["negative_terms"]),
            "opportunity_slices": entry["opportunity_slices"][:16],
        }
    return {
        "objects": objects,
        "totals": {
            "objects": len(objects),
            "candidate_slices": sum(int(row["slice_count"]) for row in objects.values()),
            "opportunities": sum(int(row["opportunity_count"]) for row in objects.values()),
            "suggested_claim_budget": sum(int(row["suggested_claim_budget"]) for row in objects.values()),
            "actual_claim_count": sum(int(row["actual_claim_count"]) for row in objects.values()),
            "undercoverage_objects": sum(1 for row in objects.values() if row["undercoverage_risk"]),
        },
    }


def source_ref_policy(candidates: Mapping[str, Any]) -> dict[str, Any]:
    refs_by_object: dict[str, list[str]] = {}
    for row in candidates.get("candidate_slices") or []:
        if not isinstance(row, Mapping):
            continue
        object_name = str(row.get("object_name") or "").strip()
        slice_code = str(row.get("slice_code") or "").strip()
        if not object_name or not slice_code:
            continue
        refs_by_object.setdefault(object_name, []).append(slice_code)
    refs_by_object = {key: value for key, value in sorted(refs_by_object.items()) if value}
    if len(refs_by_object) <= 1:
        return {}
    return {
        "policy_code": "object_ref_gate_v1",
        "allowed_source_refs_by_object": refs_by_object,
        "runner_enforced": True,
    }


def claim_fact(claim: Mapping[str, Any]) -> dict[str, Any]:
    payload = claim.get("fact_payload")
    return dict(payload) if isinstance(payload, Mapping) else {}


def claim_text(claim: Mapping[str, Any], *keys: str) -> str:
    fact = claim_fact(claim)
    for key in keys:
        value = claim.get(key)
        if value not in (None, ""):
            return str(value)
        value = fact.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def canonical_event_payload(claim: Mapping[str, Any]) -> dict[str, str]:
    summary = claim_text(claim, "claim_summary", "summary")
    return {
        "emperor_name": normalized_text(claim_text(claim, "emperor_name")),
        "object_name": normalized_text(claim_text(claim, "object_name", "object")),
        "direction": normalized_text(claim_text(claim, "direction")),
        "action_type": normalized_text(claim_text(claim, "action_type")),
        "event_scope": normalized_text(claim_text(claim, "event_scope")),
        "office_or_domain": normalized_text(claim_text(claim, "office_or_domain")),
        "time_context": normalized_text(claim_text(claim, "time_context")),
        "outcome": normalized_text(claim_text(claim, "outcome")),
        "summary_signature": normalized_text(summary),
    }


def canonical_event_key(claim: Mapping[str, Any]) -> str:
    return "CEK-" + sha256_text(stable_json(canonical_event_payload(claim)))


def near_duplicate_group_payload(claim: Mapping[str, Any]) -> dict[str, str]:
    payload = canonical_event_payload(claim)
    return {
        key: payload[key]
        for key in (
            "emperor_name",
            "object_name",
            "direction",
            "action_type",
            "event_scope",
            "office_or_domain",
            "time_context",
            "outcome",
        )
    }


def near_duplicate_group_key(claim: Mapping[str, Any]) -> tuple[str, ...]:
    payload = near_duplicate_group_payload(claim)
    return tuple(payload[key] for key in sorted(payload))


def claim_grain(claim: Mapping[str, Any]) -> str:
    text = normalized_text(
        claim_text(claim, "claim_summary", "summary")
        + claim_text(claim, "office_or_domain")
        + claim_text(claim, "outcome")
    )
    tactical_hits = sum(1 for anchor in TACTICAL_SUBEVENT_ANCHORS if anchor in text)
    chain_hits = sum(1 for anchor in CHAIN_ANCHORS if anchor in text)
    if tactical_hits and not chain_hits:
        return "sub_event"
    if len(text) >= 48 or any(marker in text for marker in ("并", "又", "复", "诸", "等", "平定")):
        return "event_chain"
    return "event_chain"


def claim_quality_payload(claim: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_event_key": canonical_event_key(claim),
        "canonical_event_payload": canonical_event_payload(claim),
        "near_duplicate_group_payload": near_duplicate_group_payload(claim),
        "claim_grain": claim_grain(claim),
    }
