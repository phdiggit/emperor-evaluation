from __future__ import annotations

from typing import Any

from export.dimension_export.evidence_index import unique_values
from export.dimension_adapters.i5b_people_delegation.dictionary_readthrough import values_by_symbol


_GRADE_DICTIONARY_VALUES = values_by_symbol("i5b.grade_dictionary.v1")
TRIAL_SCORE_MAP = {str(label): dict(value) for label, value in _GRADE_DICTIONARY_VALUES["TRIAL_SCORE_MAP"].items()}
_RULE_KEYWORD_VALUES = values_by_symbol("i5b.rule_keyword_dictionary.v1")
HIGH_VALUE_ANCHOR_KEYWORDS = tuple(_RULE_KEYWORD_VALUES["HIGH_VALUE_ANCHOR_KEYWORDS"])
STARTUP_ANCHOR_KEYWORDS = tuple(_RULE_KEYWORD_VALUES["STARTUP_ANCHOR_KEYWORDS"])
BOUNDARY_ANCHOR_KEYWORDS = tuple(_RULE_KEYWORD_VALUES["BOUNDARY_ANCHOR_KEYWORDS"])
DIRECT_SAFETY_KEYWORDS = tuple(_RULE_KEYWORD_VALUES["DIRECT_SAFETY_KEYWORDS"])
POSITIVE_CORE_KEYWORDS = {
    str(core): tuple(keywords)
    for core, keywords in _RULE_KEYWORD_VALUES["POSITIVE_CORE_KEYWORDS"].items()
}
REQUIRED_POSITIVE_RULE_CORES = tuple(POSITIVE_CORE_KEYWORDS)


_RULE_DICTIONARY_VALUES = values_by_symbol("i5b.rule_dictionary.v1")
RULE_SENSITIVE_POINTS = [dict(item) for item in _RULE_DICTIONARY_VALUES["RULE_SENSITIVE_POINTS"]]
_RULE_RUNTIME_TEXT = _RULE_DICTIONARY_VALUES["RULE_RUNTIME_TEXT"]
_INFER_DIMENSION_FALLBACK_RULES = tuple(
    {
        "keywords": tuple(item["keywords"]),
        "dimension": str(item["dimension"]),
    }
    for item in _RULE_RUNTIME_TEXT["infer_dimension_fallback_rules"]
)
_NEGATIVE_BOUNDARY_RESULTS = _RULE_RUNTIME_TEXT["negative_boundary_results"]
_RULE_SENSITIVE_DECISIONS = _RULE_RUNTIME_TEXT["rule_sensitive_decisions"]
_FORMAL_BAND_MAP = _RULE_RUNTIME_TEXT["formal_band_map"]
_SCORE_PENDING_DRAFT = dict(_RULE_RUNTIME_TEXT["score_pending_draft"])
_RULE_RESOLUTION_TEXT = _RULE_RUNTIME_TEXT["rule_resolution_text"]
_REMAINING_QUESTION_TEXT = _RULE_RUNTIME_TEXT["remaining_question_text"]
_SCORE_STAGE_PREREQUISITE_TEXT = _RULE_RUNTIME_TEXT["score_stage_prerequisite_text"]
_NEGATIVE_INTERCEPT_STATUS = _RULE_RUNTIME_TEXT["negative_intercept_status"]
_ADJACENT_ITEM_STRIPPING_STATUS = _RULE_RUNTIME_TEXT["adjacent_item_stripping_status"]
AUTO_BAND_DIRECTIONS = _RULE_RUNTIME_TEXT["auto_band_directions"]
_AUTO_BAND_DIRECTIONS = AUTO_BAND_DIRECTIONS
_DIRECTION_GRADE_MAPPING_VALUES = values_by_symbol("i5b.direction_grade_mapping.v1")
DIMENSION_RULES = tuple(tuple(item) for item in _DIRECTION_GRADE_MAPPING_VALUES["DIMENSION_RULES"])


def contains_any(value: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in value for keyword in keywords)


def card_text(card: dict[str, Any]) -> str:
    parts = [
        card.get("object_anchor"),
        card.get("evidence_role"),
        card.get("mitigation_flag"),
        card.get("upper_bound_flag"),
        card.get("cluster_role"),
        card.get("trigger_family"),
        card.get("cross_item_split"),
        card.get("quote_short"),
    ]
    return " ".join(str(part) for part in parts if part)


def infer_dimension(card: dict[str, Any]) -> str:
    anchor = str(card.get("object_anchor") or "")
    trigger_family = str(card.get("trigger_family") or "")
    text = f"{anchor} {trigger_family}"

    for keyword, dimension in DIMENSION_RULES:
        if keyword in text:
            return dimension

    for rule in _INFER_DIMENSION_FALLBACK_RULES:
        if contains_any(text, rule["keywords"]):
            return rule["dimension"]
    return trigger_family or anchor or str(_RULE_RUNTIME_TEXT["unclassified_label"])


def infer_positive_rule_core(card: dict[str, Any]) -> str | None:
    primary_text = " ".join(
        str(part)
        for part in (
            card.get("evidence_role"),
            card.get("cluster_role"),
            card.get("quote_short"),
            card.get("scoring_effect"),
        )
        if part
    )
    for core, keywords in POSITIVE_CORE_KEYWORDS.items():
        if contains_any(primary_text, keywords):
            return core

    text = card_text(card)
    for core, keywords in POSITIVE_CORE_KEYWORDS.items():
        if contains_any(text, keywords):
            return core
    return None


def infer_positive_rule_cores(cards: list[dict[str, Any]]) -> list[str]:
    strong_core_cards = [
        card
        for card in cards
        if int(card.get("strength") or 0) >= 3
        and ("核心" in str(card.get("evidence_role") or "") or "核心" in str(card.get("cluster_role") or ""))
    ]
    return unique_values([infer_positive_rule_core(card) for card in strong_core_cards])


def has_required_positive_rule_cores(cards: list[dict[str, Any]]) -> bool:
    cores = set(infer_positive_rule_cores(cards))
    return set(REQUIRED_POSITIVE_RULE_CORES).issubset(cores)


def is_startup_card(card: dict[str, Any]) -> bool:
    text = f"{card.get('object_anchor') or ''} {card.get('trigger_family') or ''}"
    return contains_any(text, STARTUP_ANCHOR_KEYWORDS)


def is_high_value_anchor(card: dict[str, Any]) -> bool:
    text = f"{card.get('object_anchor') or ''} {card.get('trigger_family') or ''} {card.get('evidence_role') or ''}"
    return contains_any(text, HIGH_VALUE_ANCHOR_KEYWORDS)


def is_boundary_card(card: dict[str, Any]) -> bool:
    text = f"{card.get('object_anchor') or ''} {card.get('evidence_role') or ''} {card.get('cluster_role') or ''} {card.get('trigger_family') or ''}"
    return contains_any(text, BOUNDARY_ANCHOR_KEYWORDS) or bool(card.get("mitigation_flag")) or bool(card.get("upper_bound_flag"))


def has_direct_safety_hard_evidence(cards: list[dict[str, Any]]) -> bool:
    for card in cards:
        text = card_text(card)
        if contains_any(text, DIRECT_SAFETY_KEYWORDS):
            return True
    return False


def safe_join(values: list[object]) -> str:
    return "；".join(unique_values([value for value in values if value not in (None, "")]))


def classify_negative_boundary(
    linked_cards: list[dict[str, Any]],
    cluster_candidate_strength: int | None = None,
) -> dict[str, Any]:
    max_strength = max((int(card.get("strength") or 0) for card in linked_cards), default=0)
    direct_safety_hard = has_direct_safety_hard_evidence(linked_cards)
    has_boundary = any(is_boundary_card(card) for card in linked_cards)
    cluster_strength = int(cluster_candidate_strength or 0)

    if direct_safety_hard:
        return dict(_NEGATIVE_BOUNDARY_RESULTS["direct_safety_hard"])

    if max_strength >= 3 or cluster_strength >= 3:
        return dict(_NEGATIVE_BOUNDARY_RESULTS["strong_or_cluster_strength"])

    if max_strength == 2:
        return dict(_NEGATIVE_BOUNDARY_RESULTS["medium_strength"])

    if max_strength == 1:
        return dict(_NEGATIVE_BOUNDARY_RESULTS["weak_strength"])

    if has_boundary:
        return dict(_NEGATIVE_BOUNDARY_RESULTS["boundary_only"])

    return dict(_NEGATIVE_BOUNDARY_RESULTS["none"])


def build_rule_sensitive_points(report: dict[str, Any]) -> list[dict[str, str]]:
    points: list[dict[str, str]] = []
    negative_boundary_tier = str(report.get("negative_boundary_tier") or "none")

    if negative_boundary_tier == "weak_to_medium":
        points.append(dict(_RULE_SENSITIVE_DECISIONS["weak_to_medium"]))
    elif negative_boundary_tier == "medium_to_strong":
        points.append(dict(_RULE_SENSITIVE_DECISIONS["medium_to_strong"]))
    elif negative_boundary_tier == "adjacent_item_medium_residual":
        points.append(dict(_RULE_SENSITIVE_DECISIONS["adjacent_item_medium_residual"]))

    if bool(report.get("single_dimension_flag")) and int(report.get("strong_positive_count") or 0) >= 3:
        if bool(report.get("positive_three_core_coverage")):
            decision = _RULE_SENSITIVE_DECISIONS["single_dimension_three_core"]["decision_when_covered"]
        else:
            decision = _RULE_SENSITIVE_DECISIONS["single_dimension_three_core"]["decision_when_not_covered"]
        points.append(
            {
                "rule": _RULE_SENSITIVE_DECISIONS["single_dimension_three_core"]["rule"],
                "decision": decision,
            }
        )

    if bool(report.get("has_strong_negative_core")):
        points.append(dict(_RULE_SENSITIVE_DECISIONS["strong_negative_core"]))

    if negative_boundary_tier == "adjacent_item_medium_residual":
        points.append(dict(_RULE_SENSITIVE_DECISIONS["default_medium_negative_residual"]))

    return points


def build_formal_band_draft(report: dict[str, Any]) -> str:
    auto_band_direction = str(report.get("auto_band_direction") or "")
    return _FORMAL_BAND_MAP.get(auto_band_direction, auto_band_direction or str(_RULE_RUNTIME_TEXT["pending_label"]))


def build_trial_score_draft(report: dict[str, Any]) -> dict[str, Any]:
    formal_band_draft = build_formal_band_draft(report)
    return TRIAL_SCORE_MAP.get(formal_band_draft, dict(_SCORE_PENDING_DRAFT))


def format_rule_resolutions(report: dict[str, Any]) -> str:
    points = report.get("rule_sensitive_points") or []
    if not points:
        return str(_RULE_RESOLUTION_TEXT["none"])
    resolutions = []
    for point in points:
        rule = str(point.get("rule") or _RULE_RESOLUTION_TEXT["unnamed_rule"])
        decision = str(point.get("decision") or "").rstrip("。")
        if decision:
            resolutions.append(_RULE_RESOLUTION_TEXT["resolved_with_decision"].format(rule=rule, decision=decision))
        else:
            resolutions.append(_RULE_RESOLUTION_TEXT["resolved"].format(rule=rule))
    return "；".join(resolutions)


def format_remaining_questions(report: dict[str, Any]) -> str:
    questions: list[str] = []
    if str(report.get("negative_boundary_tier") or "") == "none":
        questions.append(str(_REMAINING_QUESTION_TEXT["no_new_rule_question"]))
    if bool(report.get("has_extreme_negative_core")) and not bool(report.get("negative_boundary_blocking")):
        questions.append(str(_REMAINING_QUESTION_TEXT["extreme_negative_core_followup"]))
    return "；".join(questions) if questions else str(_RULE_RESOLUTION_TEXT["none"])


def format_score_stage_prerequisites(report: dict[str, Any]) -> str:
    if str(report.get("auto_band_direction") or "") == _AUTO_BAND_DIRECTIONS["rule_review_pending"]:
        return str(_SCORE_STAGE_PREREQUISITE_TEXT["rule_review_required"])
    return str(_SCORE_STAGE_PREREQUISITE_TEXT["g8_g9_ready"])


def build_negative_intercept_status(report: dict[str, Any]) -> str:
    if bool(report.get("negative_boundary_blocking")):
        return str(_NEGATIVE_INTERCEPT_STATUS["blocked"])
    return str(_NEGATIVE_INTERCEPT_STATUS["not_blocked"])


def build_adjacent_item_stripping_status(report: dict[str, Any]) -> str:
    tier = str(report.get("negative_boundary_tier") or "")
    return str(_ADJACENT_ITEM_STRIPPING_STATUS.get(tier, _ADJACENT_ITEM_STRIPPING_STATUS["default"]))
