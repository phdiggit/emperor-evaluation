from __future__ import annotations

import importlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
BUILD_DIR = SCRIPTS_DIR / "build"
REAL_DB_PATH = ROOT / "evidence_cache.sqlite"
SQLITE_SCHEMA_PATH = ROOT / "db" / "sqlite" / "001_cache.sql"
pytestmark = pytest.mark.db

EXPECTED_TABLE_FILES = {
    "sources": ROOT / "data" / "sources.jsonl",
    "evidence_cards": ROOT / "data" / "evidence_cards.jsonl",
    "events": ROOT / "data" / "events.jsonl",
    "trigger_terms": ROOT / "data" / "trigger_terms.jsonl",
    "search_logs": ROOT / "data" / "search_logs.jsonl",
    "evidence_clusters": ROOT / "data" / "evidence_clusters.jsonl",
    "thematic_anchors": ROOT / "data" / "thematic_anchors.jsonl",
    "anchor_objects": ROOT / "data" / "thematic_anchor_objects.jsonl",
    "anchor_events": ROOT / "data" / "thematic_anchor_events.jsonl",
    "anchor_mechanisms": ROOT / "data" / "thematic_anchor_mechanisms.jsonl",
    "query_profiles": ROOT / "data" / "query_profiles.jsonl",
}

EXPECTED_TABLE_COLUMNS = {
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


@pytest.fixture()
def build_module() -> Any:
    sys.path.insert(0, str(SCRIPTS_DIR))
    for module_name in ("build_db", "build.build_db", "build"):
        sys.modules.pop(module_name, None)

    return importlib.import_module("build.build_db")


def test_canonical_build_module_is_importable(build_module: Any) -> None:
    new_module = build_module

    assert new_module.ROOT.resolve() == ROOT.resolve()
    assert Path(new_module.__file__).resolve() == BUILD_DIR / "build_db.py"
    assert callable(new_module.main)


def test_retired_build_db_wrapper_path_is_absent() -> None:
    assert not (SCRIPTS_DIR / "build_db.py").exists()


def test_table_files_and_columns_match_original_database_contract(build_module: Any) -> None:
    new_module = build_module

    assert new_module.TABLE_FILES == EXPECTED_TABLE_FILES
    assert new_module.TABLE_COLUMNS == EXPECTED_TABLE_COLUMNS


def test_sqlite_schema_is_dedicated_and_separate_from_postgres_schema(build_module: Any) -> None:
    new_module = build_module

    schema = new_module.SQLITE_SCHEMA_PATH.read_text(encoding="utf-8")

    assert new_module.POSTGRES_SCHEMA_PATH == ROOT / "db" / "schema.sql"
    assert new_module.SQLITE_SCHEMA_PATH == SQLITE_SCHEMA_PATH
    assert "source_id TEXT PRIMARY KEY" in schema
    assert "raw_json TEXT NOT NULL" in schema
    assert "polarity TEXT NOT NULL CHECK (polarity IN ('positive', 'negative'))" in schema
    assert "strength INTEGER NOT NULL CHECK (strength IN (1, 2, 3, 4))" in schema
    assert "FOREIGN KEY (source_id) REFERENCES sources(source_id)" in schema
    assert "CREATE INDEX IF NOT EXISTS idx_evidence_person_subitem" in schema
    assert "CREATE EXTENSION" not in schema
    assert "GENERATED ALWAYS AS IDENTITY" not in schema


def test_sqlite_schema_enforces_cache_contract(build_module: Any) -> None:
    new_module = build_module
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(new_module.SQLITE_SCHEMA_PATH.read_text(encoding="utf-8"))

    connection.execute(
        """
        INSERT INTO sources (source_id, title, raw_json)
        VALUES ('SRC-OK', '测试来源', '{"source_id": "SRC-OK"}')
        """
    )
    valid_values = (
        "EVD-OK",
        "李世民",
        "第五项",
        "第五项B",
        "positive",
        3,
        "强正",
        "SRC-OK",
        "短摘",
        "解释",
        "触发族",
        '["触发"]',
        "已核验",
        '{"evidence_id": "EVD-OK"}',
    )
    connection.execute(
        """
        INSERT INTO evidence_cards (
            evidence_id, person, item, subitem, polarity, strength,
            human_level, source_id, quote_short, interpretation,
            trigger_family, trigger_terms, verification_status, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        valid_values,
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO evidence_cards (
                evidence_id, person, item, subitem, polarity, strength,
                human_level, source_id, quote_short, interpretation,
                trigger_family, trigger_terms, verification_status, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("EVD-BAD-POLARITY", *valid_values[1:4], "mixed", *valid_values[5:]),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO evidence_cards (
                evidence_id, person, item, subitem, polarity, strength,
                human_level, source_id, quote_short, interpretation,
                trigger_family, trigger_terms, verification_status, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("EVD-BAD-STRENGTH", *valid_values[1:5], 9, *valid_values[6:]),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO evidence_cards (
                evidence_id, person, item, subitem, polarity, strength,
                human_level, source_id, quote_short, interpretation,
                trigger_family, trigger_terms, verification_status, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("EVD-MISSING-SOURCE", *valid_values[1:7], "SRC-MISSING", *valid_values[8:]),
        )

    evidence_columns = {
        row[1]: row[2] for row in connection.execute("PRAGMA table_info(evidence_cards)").fetchall()
    }
    event_columns = {row[1]: row[2] for row in connection.execute("PRAGMA table_info(events)").fetchall()}
    cluster_columns = {
        row[1]: row[2] for row in connection.execute("PRAGMA table_info(evidence_clusters)").fetchall()
    }
    indexes = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_autoindex_%'"
        )
    }

    assert evidence_columns["strength"].upper() == "INTEGER"
    assert event_columns["severity"].upper() == "INTEGER"
    assert cluster_columns["candidate_strength"].upper() == "INTEGER"
    assert {
        "idx_evidence_person_subitem",
        "idx_evidence_polarity_strength",
        "idx_evidence_source_id",
        "idx_search_person_subitem",
        "idx_search_result_status",
        "idx_clusters_person_subitem",
        "idx_anchors_theme_subitem",
        "idx_query_profiles_item_subitem",
    } <= indexes


def test_read_jsonl_handles_missing_empty_chinese_and_invalid_rows(
    build_module: Any,
    tmp_path: Path,
) -> None:
    new_module = build_module
    jsonl_path = tmp_path / "rows.jsonl"

    assert new_module.read_jsonl(tmp_path / "missing.jsonl") == []

    jsonl_path.write_text('\n{"name": "刘秀"}\n\n{"name": "李世民"}\n', encoding="utf-8")
    assert new_module.read_jsonl(jsonl_path) == [{"name": "刘秀"}, {"name": "李世民"}]

    jsonl_path.write_text('{"ok": true}\n["not", "object"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2 must be a JSON object"):
        new_module.read_jsonl(jsonl_path)


def test_encode_value_preserves_non_ascii_json(build_module: Any) -> None:
    new_module = build_module

    assert new_module.encode_value({"name": "刘秀"}) == '{"name": "刘秀"}'
    assert new_module.encode_value(["李世民"]) == '["李世民"]'
    assert new_module.encode_value("plain") == "plain"


def test_insert_rows_writes_declared_columns_and_sorted_raw_json(build_module: Any) -> None:
    new_module = build_module
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE sources (
            source_id TEXT PRIMARY KEY,
            title TEXT,
            author TEXT,
            dynasty TEXT,
            volume TEXT,
            location TEXT,
            url TEXT,
            note TEXT,
            raw_json TEXT
        )
        """
    )

    row = {
        "title": "后汉书",
        "source_id": "SRC-TEST-001",
        "note": {"kind": "测试"},
        "extra": "kept only in raw_json",
    }
    new_module.insert_rows(connection, "sources", [row])

    saved = connection.execute("SELECT source_id, title, note, raw_json FROM sources").fetchone()
    assert saved[0] == "SRC-TEST-001"
    assert saved[1] == "后汉书"
    assert saved[2] == '{"kind": "测试"}'
    assert saved[3] == json.dumps(row, ensure_ascii=False, sort_keys=True)


def test_build_database_uses_temporary_schema_jsonl_and_database(
    build_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    new_module = build_module
    db_path = tmp_path / "evidence_cache.sqlite"
    source_path = tmp_path / "sources.jsonl"
    executed_pragmas: list[str] = []

    db_path.write_text("old database", encoding="utf-8")
    source_path.write_text('{"source_id": "SRC-TMP-001", "title": "临时来源"}\n', encoding="utf-8")

    class TrackingConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters: Any = (), /) -> sqlite3.Cursor:
            if sql == "PRAGMA foreign_keys = ON":
                executed_pragmas.append(sql)
            return super().execute(sql, parameters)

    real_connect = sqlite3.connect

    def connect(path: Path) -> sqlite3.Connection:
        return real_connect(path, factory=TrackingConnection)

    monkeypatch.setattr(new_module, "DB_PATH", db_path)
    monkeypatch.setattr(new_module, "SQLITE_SCHEMA_PATH", SQLITE_SCHEMA_PATH)
    monkeypatch.setattr(new_module, "TABLE_FILES", {"sources": source_path})
    monkeypatch.setattr(new_module, "TABLE_COLUMNS", {"sources": ["source_id", "title"]})
    monkeypatch.setattr(new_module.sqlite3, "connect", connect)

    assert new_module.build_database() == db_path
    assert executed_pragmas == ["PRAGMA foreign_keys = ON"]

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT source_id, title, raw_json FROM sources").fetchall()
    assert rows == [
        (
            "SRC-TMP-001",
            "临时来源",
            '{"source_id": "SRC-TMP-001", "title": "临时来源"}',
        )
    ]


def test_main_returns_zero_and_prints_created_path(
    build_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    new_module = build_module
    db_path = tmp_path / "evidence_cache.sqlite"

    monkeypatch.setattr(new_module, "build_database", lambda: db_path)

    assert new_module.main() == 0
    assert capsys.readouterr().out == f"created {db_path}\n"


def test_canonical_cli_runs_only_in_temporary_repository(tmp_path: Path) -> None:
    temp_root = tmp_path / "repo"
    temp_scripts = temp_root / "scripts"
    temp_build = temp_scripts / "build"
    temp_data = temp_root / "data"
    temp_db_dir = temp_root / "db" / "sqlite"
    temp_build.mkdir(parents=True)
    temp_data.mkdir()
    temp_db_dir.mkdir(parents=True)

    shutil.copy2(BUILD_DIR / "build_db.py", temp_build / "build_db.py")
    shutil.copy2(BUILD_DIR / "__init__.py", temp_build / "__init__.py")
    shutil.copy2(SQLITE_SCHEMA_PATH, temp_db_dir / "001_cache.sql")
    for path in EXPECTED_TABLE_FILES.values():
        (temp_data / path.name).write_text("", encoding="utf-8")

    before_exists = REAL_DB_PATH.exists()
    before_mtime = REAL_DB_PATH.stat().st_mtime_ns if before_exists else None

    result = subprocess.run(
        [sys.executable, str(temp_build / "build_db.py")],
        cwd=temp_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"created {temp_root / 'evidence_cache.sqlite'}" in result.stdout

    assert (temp_root / "evidence_cache.sqlite").is_file()
    assert REAL_DB_PATH.exists() is before_exists
    if before_exists:
        assert REAL_DB_PATH.stat().st_mtime_ns == before_mtime
