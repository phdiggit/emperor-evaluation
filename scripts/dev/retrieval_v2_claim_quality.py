from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


BIOGRAPHY_SOURCE_SHAPES = {"object_biography_candidate", "object_existing_source_candidate", "title_name_candidate"}
ACTION_ANCHORS = (
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
