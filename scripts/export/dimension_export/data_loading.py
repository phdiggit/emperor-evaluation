from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.i5b_markdown_display_defaults import default_markdown_display_config


DEFAULT_DISPLAY_CONFIG: dict[str, Any] = default_markdown_display_config()

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
    if path is not None:
        raise ValueError("Markdown display defaults are code-owned; external display config files are retired")
    return default_markdown_display_config()
