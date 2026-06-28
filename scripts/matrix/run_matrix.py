from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if sys.path[:1] != [str(SCRIPTS_DIR)]:
    sys.path = [str(SCRIPTS_DIR), *[path for path in sys.path if path != str(SCRIPTS_DIR)]]

from shared import config_loaders
from shared.i5b_markdown_display import display_field_label, display_value, load_display_dictionary


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DEFAULT_EXPORT_DIR = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "自动结算草案"
)


def safe_filename_part(value: object) -> str:
    return str(value).replace("/", "_").replace("\\", "_").strip()


def default_matrix_export_path() -> Path:
    config = config_loaders.get_i5b_active_workflow_config()
    subitem = safe_filename_part(config.get("subitem") or "第五项B")
    group_label = safe_filename_part(config.get("group_label") or config.get("group") or "当前人物组")
    return DEFAULT_EXPORT_DIR / f"{subitem}{group_label}正负证矩阵.md"


EXPORT_PATH = default_matrix_export_path()
DEFAULT_EXPORT_PATH = EXPORT_PATH

HEADERS = [
    "person",
    "item",
    "subitem",
    "polarity",
    "trigger_family",
    "core_terms",
    "extended_terms",
    "matrix_status",
    "note",
]


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


def escape_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def human_display_config() -> dict[str, object]:
    config = dict(load_display_dictionary())
    config["keep_machine_field_name"] = False
    return config


def active_matrix_export_path(config: dict[str, Any]) -> Path:
    if EXPORT_PATH != DEFAULT_EXPORT_PATH:
        return EXPORT_PATH
    subitem = safe_filename_part(config.get("subitem") or "第五项B")
    group_label = safe_filename_part(config.get("group_label") or config.get("group") or "当前人物组")
    return DEFAULT_EXPORT_PATH.parent / f"{subitem}{group_label}正负证矩阵.md"


def term_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("term_id", "")), str(row.get("term", ""))


def grouped_terms(
    trigger_terms: list[dict[str, Any]],
    item: str,
    subitem: str,
) -> list[dict[str, str]]:
    groups: dict[tuple[str, str], dict[str, list[str]]] = {}

    for row in sorted(trigger_terms, key=term_sort_key):
        if row.get("item") != item or row.get("subitem") != subitem:
            continue

        polarity = str(row.get("polarity", ""))
        trigger_family = str(row.get("trigger_family", ""))
        tier = str(row.get("tier", ""))
        term = str(row.get("term", ""))
        group = groups.setdefault((polarity, trigger_family), {"core": [], "extended": []})
        if tier in group and term:
            group[tier].append(term)

    polarity_order = {"positive": 0, "negative": 1}
    rows = []
    for (polarity, trigger_family), tiers in sorted(
        groups.items(),
        key=lambda item_: (polarity_order.get(item_[0][0], 99), item_[0][1]),
    ):
        rows.append(
            {
                "polarity": polarity,
                "trigger_family": trigger_family,
                "core_terms": "、".join(tiers["core"]),
                "extended_terms": "、".join(tiers["extended"]),
            }
        )
    return rows


def export_matrix() -> Path:
    display_config = human_display_config()
    trigger_terms = read_jsonl(DATA_DIR / "trigger_terms.jsonl")
    config = config_loaders.get_i5b_active_workflow_config()
    item = str(config["item"])
    subitem = str(config["subitem"])
    targets = list(config["targets"])
    group_label = str(config.get("group_label") or config.get("group") or "当前人物组")
    term_groups = grouped_terms(trigger_terms, item, subitem)
    export_path = active_matrix_export_path(config)

    export_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {subitem}{group_label}正负证矩阵",
        "",
        "本文件为矩阵骨架，尚未检索，不写入 search_logs，不生成 evidence_cards，不生成评分。",
        "",
        f"- **活动人物组**：{group_label}",
        f"- **覆盖人物**：{'、'.join(str(person) for person in targets)}",
        "",
        "| " + " | ".join(display_field_label(header, display_config) for header in HEADERS) + " |",
        "| " + " | ".join("---" for _ in HEADERS) + " |",
    ]

    for person in targets:
        for group in term_groups:
            row = {
                "person": person,
                "item": item,
                "subitem": subitem,
                "polarity": group["polarity"],
                "trigger_family": group["trigger_family"],
                "core_terms": group["core_terms"],
                "extended_terms": group["extended_terms"],
                "matrix_status": "planned_not_searched",
                "note": "矩阵骨架，尚未检索，不得入分",
            }
            lines.append("| " + " | ".join(escape_cell(display_value(row[header], display_config)) for header in HEADERS) + " |")

    export_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return export_path


def main() -> int:
    export_path = export_matrix()
    print(f"exported {export_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
