from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
DB_PATH = ROOT / "evidence_cache.sqlite"


TABLE_FILES = {
    "sources": DATA_DIR / "sources.jsonl",
    "evidence_cards": DATA_DIR / "evidence_cards.jsonl",
    "events": DATA_DIR / "events.jsonl",
    "trigger_terms": DATA_DIR / "trigger_terms.jsonl",
    "search_logs": DATA_DIR / "search_logs.jsonl",
}


TABLE_COLUMNS = {
    "sources": ["source_id", "title", "author", "dynasty", "volume", "location", "url", "note"],
    "evidence_cards": [
        "evidence_id",
        "person",
        "item",
        "subitem",
        "polarity",
        "strength",
        "human_level",
        "source_id",
        "quote_short",
        "interpretation",
        "trigger_family",
        "trigger_terms",
        "cross_item_split",
        "scoring_effect",
        "verification_status",
    ],
    "events": [
        "event_id",
        "person",
        "target",
        "action_type",
        "attribution_type",
        "outcome",
        "severity",
        "time_phase",
        "event_name",
        "event_date",
        "description",
        "source_id",
    ],
    "trigger_terms": ["term_id", "trigger_family", "term", "polarity", "tier", "item", "subitem", "note"],
    "search_logs": [
        "search_id",
        "person",
        "item",
        "subitem",
        "polarity",
        "trigger_family",
        "query_terms",
        "query",
        "source_scope",
        "searched_at",
        "result_status",
        "result_summary",
        "linked_evidence_id",
        "note",
    ],
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"{path}: line {line_number} must be a JSON object")
            rows.append(value)
    return rows


def encode_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def insert_rows(connection: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    columns = TABLE_COLUMNS[table] + ["raw_json"]
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    sql = f"INSERT OR REPLACE INTO {table} ({column_sql}) VALUES ({placeholders})"

    for row in rows:
        values = [encode_value(row.get(column)) for column in TABLE_COLUMNS[table]]
        values.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
        connection.execute(sql, values)


def build_database() -> Path:
    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        for table, path in TABLE_FILES.items():
            insert_rows(connection, table, read_jsonl(path))
        connection.commit()

    return DB_PATH


def main() -> int:
    db_path = build_database()
    print(f"created {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
