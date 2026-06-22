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

EXPECTED_TABLE_FILES = {
    "sources": ROOT / "data" / "sources.jsonl",
    "evidence_cards": ROOT / "data" / "evidence_cards.jsonl",
    "events": ROOT / "data" / "events.jsonl",
    "trigger_terms": ROOT / "data" / "trigger_terms.jsonl",
    "search_logs": ROOT / "data" / "search_logs.jsonl",
    "evidence_clusters": ROOT / "data" / "evidence_clusters.jsonl",
    "thematic_anchors": ROOT / "data" / "thematic_anchors.jsonl",
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
def build_modules() -> tuple[Any, Any]:
    sys.path.insert(0, str(SCRIPTS_DIR))
    for module_name in ("build_db", "build.build_db", "build"):
        sys.modules.pop(module_name, None)

    new_module = importlib.import_module("build.build_db")
    legacy_module = importlib.import_module("build_db")
    return new_module, legacy_module


def test_new_and_legacy_build_modules_are_importable(build_modules: tuple[Any, Any]) -> None:
    new_module, legacy_module = build_modules

    assert new_module.ROOT.resolve() == ROOT.resolve()
    assert legacy_module.ROOT.resolve() == ROOT.resolve()
    assert Path(new_module.__file__).resolve() == BUILD_DIR / "build_db.py"
    assert callable(new_module.main)
    assert callable(legacy_module.main)
    assert legacy_module.build_database is new_module.build_database


def test_legacy_wrapper_is_short_and_has_no_database_logic() -> None:
    wrapper = SCRIPTS_DIR / "build_db.py"
    content = wrapper.read_text(encoding="utf-8")

    assert len(content.splitlines()) <= 15
    assert "from build.build_db import *" in content
    assert "def build_database" not in content
    assert "TABLE_FILES" not in content
    assert "TABLE_COLUMNS" not in content


def test_table_files_and_columns_match_original_database_contract(build_modules: tuple[Any, Any]) -> None:
    new_module, _ = build_modules

    assert new_module.TABLE_FILES == EXPECTED_TABLE_FILES
    assert new_module.TABLE_COLUMNS == EXPECTED_TABLE_COLUMNS


def test_read_jsonl_handles_missing_empty_chinese_and_invalid_rows(
    build_modules: tuple[Any, Any],
    tmp_path: Path,
) -> None:
    new_module, _ = build_modules
    jsonl_path = tmp_path / "rows.jsonl"

    assert new_module.read_jsonl(tmp_path / "missing.jsonl") == []

    jsonl_path.write_text('\n{"name": "刘秀"}\n\n{"name": "李世民"}\n', encoding="utf-8")
    assert new_module.read_jsonl(jsonl_path) == [{"name": "刘秀"}, {"name": "李世民"}]

    jsonl_path.write_text('{"ok": true}\n["not", "object"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2 must be a JSON object"):
        new_module.read_jsonl(jsonl_path)


def test_encode_value_preserves_non_ascii_json(build_modules: tuple[Any, Any]) -> None:
    new_module, _ = build_modules

    assert new_module.encode_value({"name": "刘秀"}) == '{"name": "刘秀"}'
    assert new_module.encode_value(["李世民"]) == '["李世民"]'
    assert new_module.encode_value("plain") == "plain"


def test_insert_rows_writes_declared_columns_and_sorted_raw_json(build_modules: tuple[Any, Any]) -> None:
    new_module, _ = build_modules
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
    build_modules: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    new_module, _ = build_modules
    schema_path = tmp_path / "schema.sql"
    db_path = tmp_path / "evidence_cache.sqlite"
    source_path = tmp_path / "sources.jsonl"
    executed_pragmas: list[str] = []

    db_path.write_text("old database", encoding="utf-8")
    schema_path.write_text(
        """
        CREATE TABLE sources (
            source_id TEXT PRIMARY KEY,
            title TEXT,
            raw_json TEXT
        );
        """,
        encoding="utf-8",
    )
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
    monkeypatch.setattr(new_module, "SCHEMA_PATH", schema_path)
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
    build_modules: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    new_module, _ = build_modules
    db_path = tmp_path / "evidence_cache.sqlite"

    monkeypatch.setattr(new_module, "build_database", lambda: db_path)

    assert new_module.main() == 0
    assert capsys.readouterr().out == f"created {db_path}\n"


def test_new_and_legacy_cli_run_only_in_temporary_repository(tmp_path: Path) -> None:
    temp_root = tmp_path / "repo"
    temp_scripts = temp_root / "scripts"
    temp_build = temp_scripts / "build"
    temp_data = temp_root / "data"
    temp_db_dir = temp_root / "db"
    temp_build.mkdir(parents=True)
    temp_data.mkdir()
    temp_db_dir.mkdir()

    shutil.copy2(BUILD_DIR / "build_db.py", temp_build / "build_db.py")
    shutil.copy2(BUILD_DIR / "__init__.py", temp_build / "__init__.py")
    shutil.copy2(SCRIPTS_DIR / "build_db.py", temp_scripts / "build_db.py")
    shutil.copy2(ROOT / "db" / "schema.sql", temp_db_dir / "schema.sql")
    for path in EXPECTED_TABLE_FILES.values():
        (temp_data / path.name).write_text("", encoding="utf-8")

    before_exists = REAL_DB_PATH.exists()
    before_mtime = REAL_DB_PATH.stat().st_mtime_ns if before_exists else None

    commands = [
        temp_build / "build_db.py",
        temp_scripts / "build_db.py",
    ]
    for script_path in commands:
        result = subprocess.run(
            [sys.executable, str(script_path)],
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
