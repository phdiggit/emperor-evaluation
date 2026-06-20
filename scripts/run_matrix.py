from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config_loaders


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIG_PATH = ROOT / "configs" / "i5b_trial_targets.json"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人试点正负证矩阵.md"

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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def escape_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


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
    trigger_terms = read_jsonl(DATA_DIR / "trigger_terms.jsonl")
    config = config_loaders.get_i5b_trial_config()
    item = str(config["item"])
    subitem = str(config["subitem"])
    targets = list(config["targets"])
    term_groups = grouped_terms(trigger_terms, item, subitem)

    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 第五项B三人试点正负证矩阵",
        "",
        "本文件为矩阵骨架，尚未检索，不写入 search_logs，不生成 evidence_cards，不生成评分。",
        "",
        "| " + " | ".join(HEADERS) + " |",
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
            lines.append("| " + " | ".join(escape_cell(row[header]) for header in HEADERS) + " |")

    EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return EXPORT_PATH


def main() -> int:
    export_path = export_matrix()
    print(f"exported {export_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
