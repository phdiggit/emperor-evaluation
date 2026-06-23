from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_DISPLAY_CONFIG: dict[str, Any] = {
    "max_inline_table_cell_chars": 72,
    "max_inline_value_chars": 96,
    "long_field_strategy": "appendix_link",
    "fallback_long_field_strategy": "fenced_code_block",
    "table_render_policy": {
        "max_inline_table_cell_chars": 72,
        "long_cell_strategy": "appendix_link",
        "appendix_link_text_template": "见附录：{label}",
        "fallback_text": "（超长内容已转入正文或附录展示）",
    },
    "field_render_policies": {
        "default": {
            "max_inline_value_chars": 96,
            "long_field_strategy": "appendix_link",
            "fallback_long_field_strategy": "fenced_code_block",
        }
    },
    "field_labels": {},
    "value_labels": {},
    "keep_machine_field_name": True,
}


_display_config_path: Path | None = None


def configure_display_config(path: Path) -> None:
    global _display_config_path
    _display_config_path = path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def load_markdown_view_config(path: Path | None = None) -> dict[str, Any]:
    resolved_path = path or _display_config_path
    config = dict(DEFAULT_DISPLAY_CONFIG)
    config["table_render_policy"] = dict(DEFAULT_DISPLAY_CONFIG["table_render_policy"])
    config["field_render_policies"] = dict(DEFAULT_DISPLAY_CONFIG["field_render_policies"])
    config["field_render_policies"]["default"] = dict(DEFAULT_DISPLAY_CONFIG["field_render_policies"]["default"])
    if resolved_path is not None and resolved_path.exists():
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{resolved_path} must contain a top-level JSON object")
        for key, value in payload.items():
            if key == "table_render_policy" and isinstance(value, dict):
                config["table_render_policy"].update(value)
            elif key == "field_render_policies" and isinstance(value, dict):
                policies = dict(config["field_render_policies"])
                for field, policy in value.items():
                    if isinstance(policy, dict):
                        base = dict(policies.get(field) or {})
                        base.update(policy)
                        policies[field] = base
                config["field_render_policies"] = policies
            else:
                config[key] = value
    return config
