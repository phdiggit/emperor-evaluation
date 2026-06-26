from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from shared.i5b_markdown_display_defaults import default_markdown_display_config


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HUMAN_REVIEW_TABLE_FIELDS = {
    "auto_adjudication_matrix": [
        "person",
        "auto_band_direction",
        "confidence",
        "negative_boundary_tier",
        "rule_sensitive_points",
    ],
    "auto_adjudication_overview": [
        "person",
        "auto_band_direction",
        "auto_feature_digest",
        "cluster_count_digest",
        "display_warning_count",
        "detail_page",
    ],
    "formal_landing_overview": [
        "person",
        "auto_band_direction",
        "formal_band_draft",
        "formal_v3_2_grade",
        "formal_score_value_45",
        "formal_rank",
        "confidence",
        "negative_boundary_tier",
        "publication_gate_status",
    ],
    "trial_closure_overview": [
        "person",
        "final_band",
        "formal_score_value_45",
        "formal_rank",
        "internal_trial_score_range",
        "internal_trial_score",
        "extend_pilot_ready",
    ],
    "score_mapping_draft": [
        "band",
        "entry_condition",
        "typical_evidence_structure",
        "negative_intercept_condition",
        "cross_item_split",
        "direct_score_allowed",
        "rule_confirmation_needed",
        "relative_score_range_draft",
    ],
    "expanded_batch_readiness": [
        "person",
        "current_draft_status",
        "recommended_next_step",
        "remaining_evidence_gaps",
        "must_human_review_points",
        "status",
    ],
    "expanded_batch_followup": [
        "person",
        "prior_next_step",
        "followup_action",
        "followup_outcome_summary",
        "current_readiness_recommendation",
        "remaining_notes",
        "status",
    ],
    "human_review_package_overview": [
        "person",
        "current_readiness_recommendation",
        "core_rule_question",
        "status",
    ],
    "relative_band_preparation": [
        "person",
        "current_review_stage",
        "positive_base_status",
        "negative_gate_status",
        "cross_item_split_status",
        "status",
    ],
    "targeted_supplement_sources": [
        "title",
        "volume",
        "location",
        "url",
    ],
    "targeted_supplement_evidence_cards": [
        "polarity",
        "object_anchor",
        "supplement_gap_addressed",
    ],
    "micro_supplement_evidence_cards": [
        "polarity",
        "object_anchor",
        "micro_gap_addressed",
    ],
    "net_evidence_clusters": [
        "person",
        "polarity",
        "candidate_strength",
        "adjudication_status",
        "summary_detail_link",
        "cross_item_split_detail_link",
    ],
    "net_evidence_cards": [
        "person",
        "polarity",
        "human_level",
        "trigger_family",
        "object_anchor",
        "evidence_role",
        "source_detail_link",
        "context_detail_link",
        "context_status",
        "context_effect",
        "context_review_queue",
        "adjudication_bridge_detail_link",
        "cross_item_split_detail_link",
        "scoring_effect",
        "adjudication_status",
    ],
    "evidence_cards_index": [
        "person",
        "polarity",
        "strength",
        "human_level",
        "trigger_family",
        "object_anchor",
        "evidence_role",
        "source_detail_link",
        "context_detail_link",
        "context_status",
        "context_effect",
        "context_review_queue",
        "adjudication_bridge_detail_link",
        "cross_item_split_detail_link",
        "scoring_effect",
        "verification_status",
        "adjudication_status",
    ],
    "evidence_clusters_index": [
        "person",
        "polarity",
        "candidate_strength",
        "adjudication_status",
        "summary_detail_link",
        "cross_item_split_detail_link",
    ],
}


@dataclass(frozen=True)
class AppendixEntry:
    anchor: str
    label: str
    value: object


def load_display_dictionary(path: Path | None = None) -> dict[str, object]:
    if path is not None:
        raise ValueError("Markdown display defaults are code-owned; external display config files are retired")
    return default_markdown_display_config()


def display_field_label(field: str, config: dict[str, object] | None = None) -> str:
    display_config = config if config is not None else load_display_dictionary()
    labels = display_config.get("field_labels") if isinstance(display_config.get("field_labels"), dict) else {}
    label = str(labels.get(field) or field)
    keep_machine_name = bool(display_config.get("keep_machine_field_name", True))
    if keep_machine_name and field.isascii() and label != field:
        return f"{label}（{field}）"
    return label


def human_review_table_fields(table_key: str, config: dict[str, object] | None = None) -> list[str]:
    display_config = config if config is not None else load_display_dictionary()
    view_profiles = display_config.get("view_profiles")
    human_profile = view_profiles.get("human_review") if isinstance(view_profiles, dict) else {}
    table_fields = human_profile.get("table_fields") if isinstance(human_profile, dict) else {}
    configured = table_fields.get(table_key) if isinstance(table_fields, dict) else None
    if isinstance(configured, list) and all(isinstance(field, str) and field for field in configured):
        return list(configured)
    return list(DEFAULT_HUMAN_REVIEW_TABLE_FIELDS.get(table_key, ()))


def _value_labels(config: dict[str, object]) -> dict[str, str]:
    labels = config.get("value_labels")
    if not isinstance(labels, dict):
        return {}
    return {str(key): str(value) for key, value in labels.items()}


def display_value(value: object, config: dict[str, object] | None = None) -> str:
    display_config = config if config is not None else load_display_dictionary()
    labels = _value_labels(display_config)
    if value is None:
        return ""
    if isinstance(value, bool):
        return labels.get(str(value).lower(), "是" if value else "否")
    if isinstance(value, list):
        return "；".join(display_value(item, display_config) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    text = str(value)
    return labels.get(text, labels.get(text.lower(), text))


def _raw_value_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _escape_table_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "appendix"


def _table_policy(config: dict[str, object]) -> dict[str, object]:
    policy = config.get("table_render_policy")
    return policy if isinstance(policy, dict) else {}


def _list_policy_for(field: str, config: dict[str, object]) -> dict[str, object]:
    policy = config.get("list_render_policy")
    if not isinstance(policy, dict) or not policy.get("enabled", False):
        return {"strategy": "preserve_items"}
    default = policy.get("default") if isinstance(policy.get("default"), dict) else {}
    overrides = policy.get("field_overrides") if isinstance(policy.get("field_overrides"), dict) else {}
    override = overrides.get(field) if isinstance(overrides.get(field), dict) else {}
    merged = dict(default)
    merged.update(override)
    return merged


def render_long_list(field: str, values: object, config: dict[str, object] | None = None) -> list[str]:
    if not isinstance(values, list):
        text = display_value(values, config)
        return [text] if text else []
    display_config = config if config is not None else load_display_dictionary()
    policy = _list_policy_for(field, display_config)
    strategy = str(policy.get("strategy") or "preserve_items")
    items = [display_value(item, display_config) for item in values if display_value(item, display_config)]
    if not items:
        return []
    if strategy == "compact_groups" and len(items) > int(policy.get("min_items_to_compact") or 6):
        separator = str(policy.get("separator") or "；")
        max_group_chars = int(policy.get("max_group_chars") or 120)
        template = str(policy.get("group_label_template") or "第{start}-{end}项")
        groups: list[list[str]] = []
        current: list[str] = []
        for item in items:
            candidate = current + [item]
            if current and len(separator.join(candidate)) > max_group_chars:
                groups.append(current)
                current = [item]
            else:
                current = candidate
        if current:
            groups.append(current)
        rendered: list[str] = []
        cursor = 1
        for group in groups:
            start = cursor
            end = cursor + len(group) - 1
            cursor = end + 1
            rendered.append(f"**{template.format(start=start, end=end)}**：{separator.join(group)}")
        return rendered
    return items


def render_appendix_link(appendix_relative_path: str, anchor: str, label: str, config: dict[str, object]) -> str:
    template = str(_table_policy(config).get("appendix_link_text_template") or "见附录：{label}")
    return f"[{template.format(label=label)}]({appendix_relative_path}#{anchor})"


def render_table_cell(
    value: object,
    *,
    field: str,
    row_anchor: str,
    appendix_relative_path: str,
    appendix_entries: list[AppendixEntry],
    config: dict[str, object] | None = None,
) -> str:
    display_config = config if config is not None else load_display_dictionary()
    label = display_field_label(field, display_config)
    policy = _table_policy(display_config)
    list_policy = _list_policy_for(field, display_config)
    max_chars = int(policy.get("max_inline_table_cell_chars") or display_config.get("max_inline_table_cell_chars") or 72)
    displayed = display_value(value, display_config)
    force_appendix = str(list_policy.get("strategy") or "") == "appendix_link"
    if displayed and (force_appendix or len(displayed) > max_chars):
        anchor = _slug(f"{row_anchor}-{field}")
        appendix_entries.append(AppendixEntry(anchor=anchor, label=label, value=value))
        return render_appendix_link(appendix_relative_path, anchor, label, display_config)
    return _escape_table_cell(displayed)


def render_markdown_table(
    rows: Iterable[dict[str, object]],
    headers: list[str],
    *,
    row_id_fields: tuple[str, ...],
    appendix_relative_path: str,
    appendix_entries: list[AppendixEntry],
    config: dict[str, object] | None = None,
) -> list[str]:
    display_config = config if config is not None else load_display_dictionary()
    labels = [display_field_label(header, display_config) for header in headers]
    lines = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join("---" for _ in labels) + " |",
    ]
    for index, row in enumerate(rows, start=1):
        row_anchor = ""
        for field in row_id_fields:
            if row.get(field):
                row_anchor = str(row[field])
                break
        if not row_anchor:
            row_anchor = f"row-{index}"
        cells = [
            render_table_cell(
                row.get(header),
                field=header,
                row_anchor=row_anchor,
                appendix_relative_path=appendix_relative_path,
                appendix_entries=appendix_entries,
                config=display_config,
            )
            for header in headers
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render_markdown_kv(field: str, value: object, config: dict[str, object] | None = None) -> list[str]:
    display_config = config if config is not None else load_display_dictionary()
    label = display_field_label(field, display_config)
    if isinstance(value, list):
        rendered_items = render_long_list(field, value, display_config)
        if not rendered_items:
            return [f"- **{label}**："]
        return [f"- **{label}**：", *[f"  {index}. {item}" for index, item in enumerate(rendered_items, start=1)]]
    return [f"- **{label}**：{display_value(value, display_config)}"]


def render_appendix_page(title: str, entries: list[AppendixEntry]) -> str:
    lines = [f"# {title}", ""]
    if not entries:
        lines.extend(["无长字段附录。", ""])
        return "\n".join(lines)
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        key = (entry.anchor, entry.label)
        if key in seen:
            continue
        seen.add(key)
        lines.extend(
            [
                f"## {entry.anchor}",
                "",
                f"### {entry.label}",
                "",
                "```text",
                _raw_value_text(entry.value),
                "```",
                "",
            ]
        )
    return "\n".join(lines)
