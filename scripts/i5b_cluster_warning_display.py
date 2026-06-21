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

RENDER_FORBIDDEN_WARNING_FIELDS = {
    "formal_score",
    "ranking",
    "final_score",
    "definitive_band",
    "final_band",
    "leaderboard",
    "auto_band_direction",
    "candidate_strength",
    "net_adjudication_draft",
    "person",
    "evidence_id",
    "linked_evidence_ids",
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


def markdown_cell(value: object) -> str:
    if isinstance(value, list):
        text = "、".join(str(item) for item in value)
    elif isinstance(value, bool):
        text = str(value).lower()
    elif value is None:
        text = ""
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def markdown_inline_value(value: object) -> str:
    return markdown_cell(value) or "无"


def markdown_list_items(value: object) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    return [markdown_inline_value(item) for item in items]


WARNING_TYPE_LABELS = {
    "source_review_required": "回源核验提示",
    "single_evidence_limit": "单证不足提示",
    "adjacent_item_contamination": "相邻项污染提示",
    "mixed_polarity_review": "正负证并存提示",
}


def warning_title(warning: dict[str, Any]) -> str:
    warning_type = markdown_inline_value(warning.get("warning_type"))
    rule_id = markdown_inline_value(warning.get("warning_rule_id"))
    label = WARNING_TYPE_LABELS.get(warning_type, "未知提示")
    return f"{label}（{warning_type}｜{rule_id}）"


def markdown_field_item(label: str, value: object) -> str:
    return f"* **{label}**：{markdown_inline_value(value)}"


def summarize_list(value: object, max_items: int = 3) -> str:
    items = markdown_list_items(value)
    if not items:
        return "无"
    summary = "、".join(items[:max_items])
    if len(items) > max_items:
        summary += f"……（共{len(items)}项）"
    return summary


def validate_display_warning_for_render(warning: dict[str, Any]) -> None:
    forbidden = sorted(set(warning) & RENDER_FORBIDDEN_WARNING_FIELDS)
    if forbidden:
        raise ValueError(f"display-only warning contains forbidden fields: {', '.join(forbidden)}")
    if warning.get("display_only") is not True:
        raise ValueError("display-only warning must include display_only=true")
    if warning.get("no_score_effect") is not True:
        raise ValueError("display-only warning must include no_score_effect=true")
    if warning.get("required_human_review") is not True:
        raise ValueError("display-only warning must include required_human_review=true")


def render_display_only_cluster_warning_section(warnings: list[dict[str, Any]]) -> str:
    lines = [
        "## 人工复核提示（display-only）",
        "",
        "> 仅展示=true；需要人工复核=true；不影响分数=true",
        "",
    ]
    if not warnings:
        return "\n".join([*lines, "无额外提示。", ""])

    for index, warning in enumerate(warnings, start=1):
        validate_display_warning_for_render(warning)
        lines.extend(
            [
                f"**{index}. {warning_title(warning)}**",
                "",
                markdown_field_item("提示语", warning.get("warning_message")),
                markdown_field_item("命中词", summarize_list(warning.get("matched_terms"))),
                markdown_field_item("命中字段", summarize_list(warning.get("matched_fields"))),
                "",
            ]
        )

    return "\n".join(lines) + "\n"
