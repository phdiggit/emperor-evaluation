from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from scripts.dev import retrieval_v2_claim_quality as claim_quality


AMBIGUOUS_CLAIM_ALIAS_TERMS = {
    "王",
    "公",
    "侯",
    "太子",
    "皇太子",
    "皇后",
    "太后",
    "太常",
    "侍中",
    "尚书",
    "仆射",
    "中书令",
    "黄门侍郎",
    "大将军",
    "将军",
    "丞相",
    "相国",
    "太尉",
    "司徒",
    "司空",
}
AMBIGUOUS_TITLE_SUFFIXES = ("王", "公", "侯")
TEMPLE_OR_POSTHUMOUS_ALIAS_SUFFIXES = (
    "高祖",
    "太宗",
    "高宗",
    "中宗",
    "睿宗",
    "玄宗",
    "肃宗",
    "代宗",
    "德宗",
    "文帝",
    "武帝",
    "明帝",
    "宣帝",
    "昭帝",
)
HARD_FILTER_FLAGS = [
    "navigation_header",
    "weak_late_object_mention",
    "wrong_person_section",
    "ambiguous_alias_only_mention",
]
REVIEW_ONLY_FLAGS = ["object_heading_late_context_prefix"]


def text(value: Any) -> str:
    return str(value or "").strip()


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", text(value))


def increment_counter(mapping: dict[str, int], key: str) -> None:
    mapping[key] = int(mapping.get(key, 0)) + 1


def candidate_alias_positions(candidate: Mapping[str, Any]) -> list[int]:
    raw_text = text(candidate.get("text"))
    aliases = [text(candidate.get("object_name"))]
    aliases.extend(text(alias) for alias in candidate.get("matched_aliases") or [])
    positions: set[int] = set()
    for alias in sorted({alias for alias in aliases if alias}, key=len, reverse=True):
        start = 0
        while True:
            idx = raw_text.find(alias, start)
            if idx < 0:
                break
            positions.add(idx)
            start = idx + len(alias)
    return sorted(positions)


def object_name_present_in_candidate(candidate: Mapping[str, Any]) -> bool:
    object_name = compact_text(candidate.get("object_name"))
    if not object_name:
        return False
    raw_text = compact_text(candidate.get("text"))
    payload = candidate.get("object_source_cache") if isinstance(candidate.get("object_source_cache"), Mapping) else {}
    metadata = compact_text(" ".join([text(payload.get("section_heading")), text(payload.get("source_title"))]))
    return object_name in raw_text or object_name in metadata


def ambiguous_claim_alias(alias: str, *, object_name: str) -> bool:
    value = compact_text(alias)
    object_value = compact_text(object_name)
    if not value or value == object_value:
        return False
    if value in AMBIGUOUS_CLAIM_ALIAS_TERMS:
        return True
    if 2 <= len(value) <= 3 and value.endswith(AMBIGUOUS_TITLE_SUFFIXES):
        return True
    if value.endswith(TEMPLE_OR_POSTHUMOUS_ALIAS_SUFFIXES):
        return True
    return False


def ambiguous_alias_only_mention_candidate(candidate: Mapping[str, Any]) -> bool:
    payload = candidate.get("object_source_cache") if isinstance(candidate.get("object_source_cache"), Mapping) else {}
    if text(payload.get("source_shape")) != "object_mention_candidate":
        return False
    object_name = text(candidate.get("object_name"))
    if object_name_present_in_candidate(candidate):
        return False
    aliases = [text(alias) for alias in candidate.get("matched_aliases") or [] if text(alias)]
    if not aliases:
        return False
    return all(ambiguous_claim_alias(alias, object_name=object_name) for alias in aliases)


def object_heading_late_context_prefix(candidate: Mapping[str, Any]) -> bool:
    object_name = text(candidate.get("object_name"))
    raw_text = text(candidate.get("text"))
    if not object_name or not raw_text:
        return False
    for marker in (f"{object_name} [ 编辑 ]", f"{object_name}[编辑]", f"{object_name}【", f"{object_name}："):
        idx = raw_text.find(marker)
        if idx >= 120:
            return True
    return False


def claim_candidate_quality_flags(candidate: Mapping[str, Any]) -> list[str]:
    raw_text = text(candidate.get("text"))
    object_name = text(candidate.get("object_name"))
    payload = candidate.get("object_source_cache") if isinstance(candidate.get("object_source_cache"), Mapping) else {}
    shape = text(payload.get("source_shape"))
    role = text(payload.get("source_role"))
    section_heading = text(payload.get("section_heading"))
    flags: list[str] = []
    positions = candidate_alias_positions(candidate)
    first_alias_pos = min(positions) if positions else -1
    aliases = [object_name, *(text(alias) for alias in candidate.get("matched_aliases") or [])]

    if section_heading and shape in {"object_biography_candidate", "object_existing_source_candidate", "title_name_candidate"}:
        if not claim_quality.section_heading_matches_candidate(section_heading, aliases):
            flags.append("wrong_person_section")

    first_heading = re.search(r"([^\s\[]+)\s*\[\s*编辑\s*\]", raw_text)
    if first_heading and first_heading.group(1) != object_name and 0 <= first_alias_pos < first_heading.start():
        prefix = raw_text[: first_heading.start()]
        if any(marker in prefix for marker in ("姊妹计划", "数据项", "►", "◄", "←", "→")):
            flags.append("navigation_header")

    if shape in {"object_biography_candidate", "object_existing_source_candidate", "title_name_candidate"}:
        if role == "object_biography" and len(positions) <= 1 and first_alias_pos >= 120:
            flags.append("weak_late_object_mention")
    if ambiguous_alias_only_mention_candidate(candidate):
        flags.append("ambiguous_alias_only_mention")
    if object_heading_late_context_prefix(candidate):
        flags.append("object_heading_late_context_prefix")
    return flags


def is_claim_candidate_slice_eligible(candidate: Mapping[str, Any]) -> bool:
    flags = set(claim_candidate_quality_flags(candidate))
    return not (set(HARD_FILTER_FLAGS) & flags)


def claim_candidate_quality_audit(
    candidates: Sequence[Mapping[str, Any]],
    *,
    excluded_object_names: set[str] | None = None,
) -> dict[str, Any]:
    excluded = excluded_object_names or set()
    totals = {
        "input_slice_rows": 0,
        "missing_object_or_text": 0,
        "excluded_object_rows": 0,
        "eligible_slice_rows": 0,
        "ineligible_slice_rows": 0,
    }
    flag_counts: dict[str, int] = {}
    by_object: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        totals["input_slice_rows"] += 1
        object_name = text(candidate.get("object_name"))
        if not object_name or not text(candidate.get("text")):
            totals["missing_object_or_text"] += 1
            continue
        if object_name in excluded:
            totals["excluded_object_rows"] += 1
            continue
        flags = claim_candidate_quality_flags(candidate)
        for flag in flags:
            increment_counter(flag_counts, flag)
        eligible = is_claim_candidate_slice_eligible(candidate)
        totals["eligible_slice_rows" if eligible else "ineligible_slice_rows"] += 1
        current = by_object.setdefault(
            object_name,
            {
                "input_slice_rows": 0,
                "eligible_slice_rows": 0,
                "ineligible_slice_rows": 0,
                "quality_flag_counts": {},
            },
        )
        current["input_slice_rows"] += 1
        current["eligible_slice_rows" if eligible else "ineligible_slice_rows"] += 1
        for flag in flags:
            increment_counter(current["quality_flag_counts"], flag)
    return {
        **totals,
        "quality_flag_counts": dict(sorted(flag_counts.items())),
        "by_object": {
            name: {
                **payload,
                "quality_flag_counts": dict(sorted((payload.get("quality_flag_counts") or {}).items())),
            }
            for name, payload in sorted(by_object.items())
        },
        "hard_filter_flags": HARD_FILTER_FLAGS,
        "review_only_flags": REVIEW_ONLY_FLAGS,
    }
