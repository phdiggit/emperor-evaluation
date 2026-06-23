from __future__ import annotations

import json
from typing import Any

from export.dimension_export.data_loading import load_markdown_view_config


def display_field_label(field: str, display_config: dict[str, Any] | None = None) -> str:
    config = display_config if display_config is not None else load_markdown_view_config()
    labels = config.get("field_labels") or {}
    label = str(labels.get(field) or field)
    if label != field and bool(config.get("keep_machine_field_name", True)):
        return f"{label}（{field}）"
    return label


def markdown_value_text(value: object) -> str:
    if value in (None, ""):
        return "无"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value).replace("\r\n", "\n")


def value_label_key(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def display_value(value: object, display_config: dict[str, Any] | None = None) -> str:
    config = display_config if display_config is not None else load_markdown_view_config()
    labels = config.get("value_labels") or {}
    key = value_label_key(value)
    if key in labels:
        return str(labels[key])
    if value in (None, ""):
        return str(labels.get("none") or "无")
    if isinstance(value, list):
        items = [display_value(item, config) for item in value]
        return "、".join(items) if items else str(labels.get("none") or "无")
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("\n", " ")


def markdown_code_block(value: object, display_config: dict[str, Any] | None = None) -> str:
    info = "json" if isinstance(value, (list, dict)) else "text"
    if isinstance(value, list):
        content = json.dumps([display_value(item, display_config) for item in value], ensure_ascii=False, indent=2)
    elif isinstance(value, dict):
        content = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        content = display_value(value, display_config)
    return f"```{info}\n{content}\n```"


def escape_cell(value: object, display_config: dict[str, Any] | None = None) -> str:
    if value is None:
        return ""
    return display_value(value, display_config).replace("|", "\\|").replace("\n", " ")


def table_appendix_href(appendix_link_target: str | None, anchor: str) -> str:
    target = str(appendix_link_target or "")
    if not target:
        return f"#{anchor}"
    return f"{target.split('#', 1)[0]}#{anchor}"


def add_table_appendix_item(
    appendix_items: list[dict[str, Any]],
    *,
    field: str,
    label: str,
    value: object,
    appendix_link_target: str | None = None,
    display_config: dict[str, Any] | None = None,
) -> str:
    config = display_config if display_config is not None else load_markdown_view_config()
    policy = config.get("table_render_policy") or {}
    anchor = make_appendix_anchor(field, appendix_items)
    appendix_items.append({"anchor": anchor, "field": field, "label": label, "value": value})
    link_text = str(policy.get("appendix_link_text_template") or "见附录：{label}").format(label=label, field=field)
    return f"[{link_text}]({table_appendix_href(appendix_link_target, anchor)})"


def render_table_cell(
    value: object,
    display_config: dict[str, Any] | None = None,
    *,
    field: str | None = None,
    label: str | None = None,
    table_appendix_items: list[dict[str, Any]] | None = None,
    appendix_link_target: str | None = None,
) -> str:
    config = display_config if display_config is not None else load_markdown_view_config()
    policy = config.get("table_render_policy") or {}
    cell = escape_cell(value, config)
    max_chars = int(policy.get("max_inline_table_cell_chars") or config.get("max_inline_table_cell_chars") or 72)
    if len(cell) <= max_chars:
        return cell
    strategy = str(policy.get("long_cell_strategy") or "degraded_inline")
    if strategy == "appendix_link" and table_appendix_items is not None:
        resolved_field = field or label or "table_cell"
        resolved_label = label or field or "表格字段"
        return add_table_appendix_item(
            table_appendix_items,
            field=resolved_field,
            label=resolved_label,
            value=value,
            appendix_link_target=appendix_link_target,
            display_config=config,
        )
    if strategy in {"degraded_inline", "appendix_link", "fenced_code_block"}:
        return str(policy.get("fallback_text") or "（超长内容已转入正文或附录展示）")
    return cell


def markdown_table(
    headers: list[str],
    rows: list[dict[str, Any]],
    *,
    display_config: dict[str, Any] | None = None,
    table_appendix_items: list[dict[str, Any]] | None = None,
    appendix_link_target: str | None = None,
    field_by_header: dict[str, str] | None = None,
) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                render_table_cell(
                    row.get(header),
                    display_config,
                    field=(field_by_header or {}).get(header, header),
                    label=header,
                    table_appendix_items=table_appendix_items,
                    appendix_link_target=appendix_link_target,
                )
                for header in headers
            )
            + " |"
        )
    return "\n".join(lines)


def markdown_display_table(
    fields: list[str],
    rows: list[dict[str, Any]],
    *,
    display_config: dict[str, Any] | None = None,
    table_appendix_items: list[dict[str, Any]] | None = None,
    appendix_link_target: str | None = None,
) -> str:
    config = display_config if display_config is not None else load_markdown_view_config()
    headers = [display_field_label(field, config) for field in fields]
    display_rows = [{display_field_label(field, config): row.get(field) for field in fields} for row in rows]
    return markdown_table(
        headers,
        display_rows,
        display_config=config,
        table_appendix_items=table_appendix_items,
        appendix_link_target=appendix_link_target,
        field_by_header=dict(zip(headers, fields, strict=True)),
    )


def markdown_inline_value(value: object, display_config: dict[str, Any] | None = None) -> str:
    return display_value(value, display_config)


def markdown_list_items(value: object, display_config: dict[str, Any] | None = None) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    return [markdown_inline_value(item, display_config) for item in items]


def markdown_field_item(
    label: str,
    value: object,
    bullet: str = "*",
    *,
    display_config: dict[str, Any] | None = None,
) -> str:
    return f"{bullet} **{label}**：{markdown_inline_value(value, display_config)}"


def cluster_card_value(value: object, display_config: dict[str, Any] | None = None) -> str:
    return display_value(value, display_config)


def render_numbered_list(label: str, value: object, display_config: dict[str, Any] | None = None) -> list[str]:
    items = markdown_list_items(value, display_config)
    if not items:
        return [markdown_field_item(label, "无", display_config=display_config)]
    lines = [f"* **{label}**："]
    lines.extend(f"  {index}. {item}" for index, item in enumerate(items, start=1))
    return lines


def field_render_policy(field: str, display_config: dict[str, Any]) -> dict[str, Any]:
    policies = display_config.get("field_render_policies") or {}
    policy = dict(policies.get("default") or {})
    policy.update(policies.get(field) or {})
    return policy


def make_appendix_anchor(field: str, appendix_items: list[dict[str, Any]]) -> str:
    base = "appendix-" + "".join(char if char.isascii() and (char.isalnum() or char in "-_") else "-" for char in field)
    base = base.strip("-") or "appendix-field"
    existing = {str(item["anchor"]) for item in appendix_items}
    if base not in existing:
        return base
    index = 2
    while f"{base}-{index}" in existing:
        index += 1
    return f"{base}-{index}"


def render_cluster_card(row: dict[str, Any], display_config: dict[str, Any] | None = None) -> str:
    config = display_config if display_config is not None else load_markdown_view_config()
    summary = "｜".join(
        [
            markdown_inline_value(row.get("cluster_id"), config),
            markdown_inline_value(row.get("polarity"), config),
            f"{display_field_label('candidate_strength', config)}={markdown_inline_value(row.get('candidate_strength'), config)}",
            markdown_inline_value(row.get("auto_cluster_result"), config),
        ]
    )
    lines = [
        f"**{summary}**",
        "",
        markdown_field_item(display_field_label("cluster_type", config), cluster_card_value(row.get("cluster_type"), config), display_config=config),
        markdown_field_item(display_field_label("boundary_tier", config), cluster_card_value(row.get("boundary_tier"), config), display_config=config),
        markdown_field_item(display_field_label("blocking_extreme", config), cluster_card_value(row.get("blocking_extreme"), config), display_config=config),
        markdown_field_item(display_field_label("residual_level", config), cluster_card_value(row.get("residual_level"), config), display_config=config),
    ]
    for field in [
        "linked_object_anchors",
        "linked_evidence_roles",
        "linked_trigger_families",
        "linked_strengths",
        "linked_upper_bound_flags",
        "linked_mitigation_flags",
        "linked_cluster_roles",
        "cross_item_split_signals",
    ]:
        lines.extend(["", *render_numbered_list(display_field_label(field, config), row.get(field), config)])
    return "\n".join(lines)


def render_cluster_cards(rows: list[dict[str, Any]], display_config: dict[str, Any] | None = None) -> str:
    return "\n\n---\n\n".join(render_cluster_card(row, display_config) for row in rows)


def render_table_appendix_section(
    appendix_items: list[dict[str, Any]],
    display_config: dict[str, Any] | None = None,
) -> str:
    config = display_config if display_config is not None else load_markdown_view_config()
    lines: list[str] = []
    for item in appendix_items:
        lines.extend(
            [
                f"### {item['anchor']}",
                "",
                f"#### {item['label']}",
                "",
                markdown_code_block(item["value"], config),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_table_appendix_page(
    title: str,
    back_link: str,
    appendix_items: list[dict[str, Any]],
    display_config: dict[str, Any] | None = None,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"[返回正文]({back_link})",
        "",
        "本附录只承接表格超长单元格的全量展示，不改变数据、裁判逻辑、评分或 warning 语义。",
        "",
    ]
    if appendix_items:
        lines.append(render_table_appendix_section(appendix_items, display_config).rstrip())
    else:
        lines.append("无附录字段。")
    return "\n".join(lines).rstrip() + "\n"
