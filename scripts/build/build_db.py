from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
POSTGRES_SCHEMA_PATH = ROOT / "db" / "schema.sql"
SQLITE_SCHEMA_SOURCE = "scripts/build/build_db.py:TABLE_COLUMNS"
DB_PATH = ROOT / "evidence_cache.sqlite"


TABLE_FILES = {
    "sources": DATA_DIR / "sources.jsonl",
    "evidence_cards": DATA_DIR / "evidence_cards.jsonl",
    "events": DATA_DIR / "events.jsonl",
    "trigger_terms": DATA_DIR / "trigger_terms.jsonl",
    "search_logs": DATA_DIR / "search_logs.jsonl",
    "evidence_clusters": DATA_DIR / "evidence_clusters.jsonl",
    "thematic_anchors": DATA_DIR / "thematic_anchors.jsonl",
    "anchor_objects": DATA_DIR / "thematic_anchor_objects.jsonl",
    "anchor_events": DATA_DIR / "thematic_anchor_events.jsonl",
    "anchor_mechanisms": DATA_DIR / "thematic_anchor_mechanisms.jsonl",
    "query_profiles": DATA_DIR / "query_profiles.jsonl",
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
    "evidence_clusters": [
        "cluster_id",
        "person",
        "item",
        "subitem",
        "cluster_type",
        "polarity",
        "linked_evidence_ids",
        "summary",
        "five_axis_assessment",
        "candidate_strength",
        "upper_probe",
        "cross_item_split",
        "adjudication_status",
        "note",
    ],
    "thematic_anchors": [
        "anchor_id",
        "theme",
        "item",
        "subitem",
        "persons",
        "linked_evidence_ids",
        "linked_cluster_ids",
        "anchor_summary",
        "comparative_value",
        "note",
    ],
    "anchor_objects": [
        "anchor_id",
        "item",
        "subitem",
        "anchor_kind",
        "anchor_scope",
        "object_type",
        "object_name",
        "object_level",
        "anchor_role",
        "usable_for",
        "cross_item_risks",
        "consensus_level",
        "review_status",
        "linked_persons",
        "source_batch",
        "note",
    ],
    "anchor_events": [
        "anchor_id",
        "item",
        "subitem",
        "anchor_kind",
        "anchor_scope",
        "object_type",
        "object_name",
        "object_level",
        "anchor_role",
        "usable_for",
        "cross_item_risks",
        "consensus_level",
        "review_status",
        "linked_persons",
        "source_batch",
        "note",
    ],
    "anchor_mechanisms": [
        "anchor_id",
        "item",
        "subitem",
        "anchor_kind",
        "anchor_scope",
        "object_type",
        "object_name",
        "object_level",
        "anchor_role",
        "usable_for",
        "cross_item_risks",
        "consensus_level",
        "review_status",
        "linked_persons",
        "source_batch",
        "note",
    ],
    "query_profiles": [
        "query_profile_id",
        "item",
        "subitem",
        "search_modes",
        "positive_terms",
        "negative_terms",
        "reversal_terms",
        "source_scopes",
        "reverse_search_required_when",
        "thematic_anchor_targets",
        "cross_item_split_notes",
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


def quote_identifier(identifier: str) -> str:
    if not identifier.replace("_", "").isalnum():
        raise ValueError(f"unsafe SQLite identifier: {identifier!r}")
    return f'"{identifier}"'


def create_table_sql(table: str, columns: list[str]) -> str:
    quoted_table = quote_identifier(table)
    column_definitions = []
    for index, column in enumerate(columns):
        definition = f"{quote_identifier(column)} TEXT"
        if index == 0:
            definition += " PRIMARY KEY"
        column_definitions.append(definition)
    column_definitions.append(f"{quote_identifier('raw_json')} TEXT NOT NULL")
    joined = ",\n    ".join(column_definitions)
    return f"CREATE TABLE {quoted_table} (\n    {joined}\n);"


def build_sqlite_schema(table_columns: dict[str, list[str]] | None = None) -> str:
    source = table_columns if table_columns is not None else TABLE_COLUMNS
    statements = [create_table_sql(table, columns) for table, columns in source.items()]
    return "\n\n".join(statements) + "\n"


def insert_rows(connection: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    columns = TABLE_COLUMNS[table] + ["raw_json"]
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(quote_identifier(column) for column in columns)
    sql = f"INSERT OR REPLACE INTO {quote_identifier(table)} ({column_sql}) VALUES ({placeholders})"

    for row in rows:
        values = [encode_value(row.get(column)) for column in TABLE_COLUMNS[table]]
        values.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
        connection.execute(sql, values)


def build_database() -> Path:
    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(build_sqlite_schema())
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
