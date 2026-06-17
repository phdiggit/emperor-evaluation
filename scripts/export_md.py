from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "史料证据卡索引.md"
SEARCH_LOGS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人试点检索线索.md"

HEADERS = [
    "evidence_id",
    "person",
    "subitem",
    "human_level",
    "source_id",
    "quote_short",
    "verification_status",
]
SEARCH_LOG_HEADERS = [
    "search_id",
    "person",
    "subitem",
    "polarity",
    "trigger_family",
    "query_terms",
    "result_status",
    "result_summary",
    "linked_evidence_id",
    "note",
]
I5B_TRIAL_TARGETS = ["李世民", "刘秀", "刘庄"]


def escape_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def export_markdown() -> Path:
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = list(
                connection.execute(
                    """
                    SELECT evidence_id, person, subitem, human_level, source_id,
                           quote_short, verification_status
                    FROM evidence_cards
                    ORDER BY evidence_id
                    """
                )
            )

    lines = [
        "# 史料证据卡索引",
        "",
        "| " + " | ".join(HEADERS) + " |",
        "| " + " | ".join("---" for _ in HEADERS) + " |",
    ]

    for row in rows:
        lines.append("| " + " | ".join(escape_cell(row[header]) for header in HEADERS) + " |")

    EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return EXPORT_PATH


def export_search_logs_markdown() -> Path:
    SEARCH_LOGS_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if DB_PATH.exists():
        placeholders = ", ".join("?" for _ in I5B_TRIAL_TARGETS)
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = list(
                connection.execute(
                    f"""
                    SELECT search_id, person, subitem, polarity, trigger_family,
                           query_terms, result_status, result_summary,
                           linked_evidence_id, note
                    FROM search_logs
                    WHERE subitem = ?
                      AND person IN ({placeholders})
                    ORDER BY person, polarity, trigger_family, search_id
                    """,
                    ["第五项B", *I5B_TRIAL_TARGETS],
                )
            )

    lines = [
        "# 第五项B三人试点检索线索",
        "",
        "本文件导出待回源检索线索；未回源材料不得入分。",
        "",
        "| " + " | ".join(SEARCH_LOG_HEADERS) + " |",
        "| " + " | ".join("---" for _ in SEARCH_LOG_HEADERS) + " |",
    ]

    for row in rows:
        lines.append("| " + " | ".join(escape_cell(row[header]) for header in SEARCH_LOG_HEADERS) + " |")

    SEARCH_LOGS_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return SEARCH_LOGS_EXPORT_PATH


def main() -> int:
    export_path = export_markdown()
    print(f"exported {export_path}")
    search_logs_export_path = export_search_logs_markdown()
    print(f"exported {search_logs_export_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
