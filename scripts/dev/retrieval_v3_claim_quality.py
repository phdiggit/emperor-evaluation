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
    "迁",
    "封",
    "使",
    "遣",
    "令",
    "领",
    "同知",
    "定策",
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
    "劝",
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
OUTCOME_SUPPORT_TERMS = tuple(dict.fromkeys((*OUTCOME_ANCHORS, "贬", "左迁", "削", "罢", "免", "释", "不问", "不发", "失权", "械系")))
DISPOSITION_ONLY_TERMS = ("伏诛", "被诛", "诛", "谋反", "废", "罢", "下狱", "坐罪", "族诛")
GOVERNANCE_DAMAGE_TERMS = (
    "专擅",
    "擅权",
    "纳贿",
    "壅蔽",
    "隐匿不上闻",
    "不奏",
    "害政",
    "乱政",
    "败",
    "失",
    "误",
    "构陷",
    "诬奏",
    "驱斥",
    "斥逐",
    "左迁",
    "贬",
    "削官爵",
    "免官",
    "致人死亡",
    "族诛",
    "族誅",
    "夷三族",
    "夷灭",
    "夷滅",
    "坐诛",
    "坐誅",
    "尽诛",
    "盡誅",
    "尽诛其僚属党与",
    "盡誅其僚屬黨與",
    "僚属党与",
    "僚屬黨與",
    "万五千人",
    "萬五千人",
    "家口",
    "妻女弟侄",
    "七十余人",
    "七十馀人",
    "构党",
    "结党",
)
NEGATIVE_CONTEXT_TERMS = tuple(dict.fromkeys((*DISPOSITION_ONLY_TERMS, "弹劾", "劾", "谏", "诤", "讽", "罢", "斥")))


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


def primary_candidate_aliases(row: Mapping[str, Any]) -> list[str]:
    aliases = unique_strings([row.get("object_name"), row.get("person_name")])
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


def alias_in_slice_metadata(row: Mapping[str, Any], aliases: list[str]) -> bool:
    object_cache = object_cache_row(row)
    metadata_text = normalized_text(
        " ".join(
            str(value or "")
            for value in (
                row.get("section_heading"),
                row.get("source_title"),
                object_cache.get("section_heading"),
                object_cache.get("source_title"),
            )
        )
    )
    return bool(metadata_text and any(normalized_text(alias) in metadata_text for alias in aliases if alias))


def section_heading_matches_candidate(section_heading: str, aliases: Sequence[str]) -> bool:
    heading = normalized_text(section_heading)
    if not heading:
        return True
    for alias in aliases:
        normalized_alias = normalized_text(alias)
        if not normalized_alias:
            continue
        if normalized_alias in heading:
            return True
        if len(heading) >= 2 and heading in normalized_alias:
            return True
    return False


def biography_section_context_aliases(row: Mapping[str, Any], aliases: Sequence[str]) -> list[str]:
    if not biography_like_source(row):
        return []
    object_cache = object_cache_row(row)
    section_heading = str(object_cache.get("section_heading") or row.get("section_heading") or "").strip()
    if not section_heading or not section_heading_matches_candidate(section_heading, aliases):
        return []
    heading = normalized_text(section_heading)
    candidates = [heading, *(normalized_text(alias) for alias in aliases)]
    short_aliases: list[str] = []
    for candidate in candidates:
        if 2 <= len(candidate) <= 4:
            short_aliases.append(candidate[-1])
    return unique_strings(short_aliases)


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
        object_cache = object_cache_row(row)
        quality_flags = {str(flag) for flag in object_cache.get("quality_flags") or row.get("quality_flags") or []}
        flags: list[str] = []
        if "ambiguous_alias_only_mention" in quality_flags:
            flags.append("ambiguous_alias_only_mention_risk")
        return flags
    object_cache = object_cache_row(row)
    quality_flags = {str(flag) for flag in object_cache.get("quality_flags") or row.get("quality_flags") or []}
    aliases = candidate_aliases(row)
    section_heading = str(object_cache.get("section_heading") or row.get("section_heading") or "").strip()
    flags: list[str] = []
    if section_heading and aliases and not section_heading_matches_candidate(section_heading, aliases):
        flags.append("wrong_person_section_risk")
    text = str(row.get("text") or row.get("raw_text") or "")
    if len(text) >= 260 and alias_mention_count(text, aliases) <= 1:
        flags.append("weak_single_mention_risk")
    if "ambiguous_alias_only_mention" in quality_flags:
        flags.append("ambiguous_alias_only_mention_risk")
    if "object_heading_late_context_prefix" in quality_flags:
        flags.append("object_heading_late_context_risk")
    return flags


def slice_claim_eligibility(row: Mapping[str, Any]) -> dict[str, Any]:
    text = str(row.get("text") or row.get("raw_text") or "")
    aliases = candidate_aliases(row)
    effective_aliases = unique_strings([*aliases, *biography_section_context_aliases(row, aliases)])
    risk_flags = candidate_slice_risk_flags(row)
    mention_count = alias_mention_count(text, effective_aliases)
    has_action = has_anchor_near_alias(text, effective_aliases, ACTION_ANCHORS)
    has_outcome = has_anchor_near_alias(text, effective_aliases, OUTCOME_ANCHORS)
    mention_role = "primary" if mention_count > 1 or has_action or has_outcome else "incidental"
    claim_eligible = True
    reasons: list[str] = []
    if aliases and mention_count == 0 and not alias_in_slice_metadata(row, aliases):
        risk_flags = [*risk_flags, "object_absent_risk"]
    if "ambiguous_alias_only_mention_risk" in risk_flags:
        claim_eligible = False
        reasons.extend(risk_flags)
    elif risk_flags and mention_role == "incidental":
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
    primary_aliases = primary_candidate_aliases(row)
    has_primary_object_signal = bool(
        alias_mention_count(text, primary_aliases) or alias_in_slice_metadata(row, primary_aliases)
    )
    action_terms = anchor_terms_in_text(text, OPPORTUNITY_ACTION_TERMS)
    outcome_terms = anchor_terms_in_text(text, OPPORTUNITY_OUTCOME_TERMS)
    negative_terms = anchor_terms_in_text(text, NEGATIVE_ACTION_TERMS)
    has_opportunity = bool(eligibility["claim_eligible"] and has_primary_object_signal and (action_terms or outcome_terms))
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
        "has_primary_object_signal": has_primary_object_signal,
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
        "action_type": normalized_text(claim_text(claim, "action_type")),
        "event_scope": normalized_text(claim_text(claim, "event_scope")),
        "office_or_domain": normalized_text(claim_text(claim, "office_or_domain")),
        "time_context": normalized_text(claim_text(claim, "time_context")),
        "outcome": normalized_text(claim_text(claim, "outcome")),
        "summary_signature": normalized_text(summary),
    }


def normalized_time_context(value: Any) -> str:
    normalized = normalized_text(value)
    return re.sub(r"[（(]\d{3,4}年[）)]", "", normalized)


def canonical_event_identity_payload(claim: Mapping[str, Any]) -> dict[str, str]:
    payload = canonical_event_payload(claim)
    identity = {
        "emperor_name": payload["emperor_name"],
        "object_name": payload["object_name"],
        "action_type": payload["action_type"],
        "event_scope": payload["event_scope"],
        "office_or_domain": payload["office_or_domain"],
        "time_context": normalized_time_context(payload["time_context"]),
    }
    if any(identity[key] for key in ("action_type", "event_scope", "office_or_domain", "time_context")):
        return identity
    return payload


def claim_fact_type(claim: Mapping[str, Any]) -> str:
    explicit = claim_text(claim, "fact_type", "claim_type")
    if explicit:
        return explicit
    schema = claim_text(claim, "fact_schema")
    if schema == "political_action_v1":
        return "material_action"
    if schema.endswith("_v1"):
        stem = schema.removesuffix("_v1")
        return "numeric" if stem == "numeric_fact" else stem
    return "material_action"


def claim_outcome_support(claim: Mapping[str, Any]) -> str:
    fact_type = claim_fact_type(claim)
    if fact_type in {"evaluation", "relationship", "institution", "numeric", "context"}:
        return "not_applicable"
    fact = claim_fact(claim)
    completeness = fact.get("completeness") if isinstance(fact.get("completeness"), Mapping) else {}
    if completeness.get("has_outcome") is True:
        return "direct"
    outcome_text = claim_text(claim, "outcome")
    cost_text = claim_text(claim, "cost_or_damage")
    if normalized_text(outcome_text) or normalized_text(cost_text):
        return "direct"
    summary = claim_text(claim, "claim_summary", "summary")
    if any(term in summary for term in OUTCOME_SUPPORT_TERMS):
        return "implicit"
    return "missing"


def terms_in_claim(claim: Mapping[str, Any], terms: tuple[str, ...]) -> list[str]:
    combined = (
        claim_text(claim, "claim_summary", "summary")
        + claim_text(claim, "outcome")
        + claim_text(claim, "cost_or_damage")
    )
    fact = claim_fact(claim)
    if fact:
        combined += str(fact.get("outcome") or "") + str(fact.get("cost_or_damage") or "")
    return [term for term in terms if term and term in combined]


def claim_negative_support(claim: Mapping[str, Any]) -> dict[str, Any]:
    damage_terms = terms_in_claim(claim, GOVERNANCE_DAMAGE_TERMS)
    context_terms = terms_in_claim(claim, NEGATIVE_CONTEXT_TERMS)
    if damage_terms:
        support = "governance_damage_supported"
    elif context_terms:
        support = "negative_context_without_damage_anchor"
    else:
        support = "not_applicable"
    return {
        "support": support,
        "has_governance_damage": bool(damage_terms),
        "has_negative_context": bool(context_terms),
        "damage_terms": damage_terms,
        "context_terms": context_terms,
    }


def atomic_fact_payload(claim: Mapping[str, Any]) -> dict[str, str]:
    return {
        "emperor_name": normalized_text(claim_text(claim, "emperor_name")),
        "object_name": normalized_text(claim_text(claim, "object_name", "object")),
        "fact_type": normalized_text(claim_fact_type(claim)),
        "actor": normalized_text(claim_text(claim, "actor")),
        "fact_object": normalized_text(claim_text(claim, "object")),
        "action_type": normalized_text(claim_text(claim, "action_type")),
        "event_scope": normalized_text(claim_text(claim, "event_scope")),
        "office_or_domain": normalized_text(claim_text(claim, "office_or_domain")),
        "time_context": normalized_text(claim_text(claim, "time_context")),
        "outcome": normalized_text(claim_text(claim, "outcome")),
        "cost_or_damage": normalized_text(claim_text(claim, "cost_or_damage")),
        "outcome_support": claim_outcome_support(claim),
        "negative_support": claim_negative_support(claim)["support"],
    }


def event_group_payload(claim: Mapping[str, Any]) -> dict[str, str]:
    identity = canonical_event_identity_payload(claim)
    return {key: value for key, value in identity.items() if key != "summary_signature"}


def event_group_key(claim: Mapping[str, Any]) -> str:
    return "CEG-" + sha256_text(stable_json(event_group_payload(claim)))


def claim_usage_role_hint(claim: Mapping[str, Any]) -> str:
    fact_type = claim_fact_type(claim)
    support = claim_outcome_support(claim)
    if fact_type == "evaluation":
        return "evaluation_context"
    if fact_type == "context":
        return "background_context"
    if support in {"direct", "implicit"}:
        return "direct_material_candidate"
    return "supporting_context"


def canonical_event_key(claim: Mapping[str, Any]) -> str:
    return "CEK-" + sha256_text(stable_json(canonical_event_identity_payload(claim)))


def near_duplicate_group_payload(claim: Mapping[str, Any]) -> dict[str, str]:
    return canonical_event_identity_payload(claim)


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
        "fact_type": claim_fact_type(claim),
        "outcome_support": claim_outcome_support(claim),
        "negative_support_payload": claim_negative_support(claim),
        "atomic_fact_payload": atomic_fact_payload(claim),
        "event_group_key": event_group_key(claim),
        "event_group_payload": event_group_payload(claim),
        "usage_role_hint": claim_usage_role_hint(claim),
    }
