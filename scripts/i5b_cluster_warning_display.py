from __future__ import annotations

from typing import Any


DISPLAY_WARNING_KEYS = {
    "cluster_id",
    "warning_rule_id",
    "warning_type",
    "warning_message",
    "matched_terms",
    "matched_fields",
    "matched_reason",
    "required_human_review",
    "display_only",
    "no_score_effect",
}

CLUSTER_TEXT_FIELDS = (
    "cross_item_split",
    "five_axis_assessment",
    "trigger_terms",
    "notes",
    "note",
    "summary",
)

CARD_TEXT_FIELDS = (
    "trigger_terms",
    "trigger_family",
    "scoring_effect",
    "cross_item_split",
    "evidence_role",
    "cluster_role",
    "strength",
    "upper_bound_flag",
    "mitigation_flag",
    "excerpt",
    "quote",
    "summary",
)

MIXED_POLARITY_SIGNALS = ("正负并存", "正负", "mixed polarity")


def stringify_readonly_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(stringify_readonly_values(item))
        return values
    if isinstance(value, dict):
        values = []
        for item in value.values():
            values.extend(stringify_readonly_values(item))
        return values
    return [str(value)]


def collect_readonly_warning_text(
    cluster: dict[str, Any],
    linked_cards: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []

    for field in CLUSTER_TEXT_FIELDS:
        for text in stringify_readonly_values(cluster.get(field)):
            if text.strip():
                values.append((f"cluster.{field}", text))

    for index, card in enumerate(linked_cards):
        for field in CARD_TEXT_FIELDS:
            for text in stringify_readonly_values(card.get(field)):
                if text.strip():
                    values.append((f"linked_cards[{index}].{field}", text))

    return values


def cluster_strength_label(cluster: dict[str, Any]) -> str | None:
    strength = cluster.get("candidate_strength")
    if strength is None:
        return None
    try:
        return f"candidate_strength_{int(strength)}"
    except (TypeError, ValueError):
        return None


def unique_in_order(values: list[str]) -> list[str]:
    results: list[str] = []
    for value in values:
        if value not in results:
            results.append(value)
    return results


def rule_terms(rule: dict[str, Any]) -> list[str]:
    terms = rule.get("trigger_terms")
    if not isinstance(terms, list):
        return []
    return [term for term in terms if isinstance(term, str) and term.strip()]


def rule_scope_values(rule: dict[str, Any], field: str) -> list[str]:
    values = rule.get(field)
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value.strip()]


def term_matches_text(term: str, text: str) -> bool:
    return term.strip() in text


def has_mixed_polarity_signal(text_values: list[tuple[str, str]]) -> bool:
    return any(signal in text for _, text in text_values for signal in MIXED_POLARITY_SIGNALS)


def polarity_matches(rule: dict[str, Any], cluster: dict[str, Any], text_values: list[tuple[str, str]]) -> bool:
    scope = rule_scope_values(rule, "polarity_scope")
    if not scope:
        return True

    polarity = str(cluster.get("polarity") or "").strip()
    if polarity in scope:
        return True

    return "both" in scope and has_mixed_polarity_signal(text_values)


def strength_matches(rule: dict[str, Any], cluster: dict[str, Any]) -> bool:
    scope = rule_scope_values(rule, "evidence_strength_scope")
    if not scope:
        return True

    label = cluster_strength_label(cluster)
    return label in scope


def find_term_matches(
    terms: list[str],
    text_values: list[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    matched_terms: list[str] = []
    matched_fields: list[str] = []

    for term in terms:
        for field, text in text_values:
            if term_matches_text(term, text):
                matched_terms.append(term)
                matched_fields.append(field)

    return unique_in_order(matched_terms), unique_in_order(matched_fields)


def rule_matches_display_only(
    rule: dict[str, Any],
    cluster: dict[str, Any],
    linked_cards: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    # Current stage treats disabled rules only as display-only warning sources.
    if rule.get("enabled") is not False:
        return [], []
    if rule.get("required_human_review") is not True:
        return [], []

    text_values = collect_readonly_warning_text(cluster, linked_cards)
    if not polarity_matches(rule, cluster, text_values):
        return [], []
    if not strength_matches(rule, cluster):
        return [], []

    matched_terms, matched_fields = find_term_matches(rule_terms(rule), text_values)
    if matched_terms:
        return matched_terms, matched_fields

    if rule.get("warning_type") == "mixed_polarity_review" and str(cluster.get("polarity") or "") == "both":
        return ["polarity:both"], ["cluster.polarity"]

    return [], []


def build_display_warning(
    cluster: dict[str, Any],
    rule: dict[str, Any],
    matched_terms: list[str],
    matched_fields: list[str],
) -> dict[str, Any]:
    warning = {
        "cluster_id": cluster.get("cluster_id"),
        "warning_rule_id": rule.get("rule_id"),
        "warning_type": rule.get("warning_type"),
        "warning_message": rule.get("warning_message"),
        "matched_terms": matched_terms,
        "matched_fields": matched_fields,
        "matched_reason": (
            "display-only warning source matched read-only cluster/card text; "
            "no score, band, draft, ranking, or data mutation effect"
        ),
        "required_human_review": True,
        "display_only": True,
        "no_score_effect": True,
    }
    if set(warning) != DISPLAY_WARNING_KEYS:
        raise AssertionError("display warning keys must stay within the whitelist")
    return warning


def match_display_only_cluster_warnings(
    cluster: dict[str, Any],
    linked_cards: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for rule in rules:
        matched_terms, matched_fields = rule_matches_display_only(rule, cluster, linked_cards)
        if not matched_terms:
            continue
        warnings.append(build_display_warning(cluster, rule, matched_terms, matched_fields))
    return warnings
