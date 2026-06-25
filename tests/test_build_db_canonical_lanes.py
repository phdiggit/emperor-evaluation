from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUILD_DB_PATH = ROOT / "scripts" / "build" / "build_db.py"

pytestmark = pytest.mark.db

ANCHOR_LANES = {
    "anchor_objects": "thematic_anchor_objects.jsonl",
    "anchor_events": "thematic_anchor_events.jsonl",
    "anchor_mechanisms": "thematic_anchor_mechanisms.jsonl",
}

ANCHOR_COLUMNS = {
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
    "raw_json",
}

NON_STABLE_JOIN_KEYS = {"object_name", "object_anchor", "usable_for", "linked_persons"}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def copy_build_workspace(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts" / "build").mkdir(parents=True)
    (repo / "data").mkdir()

    shutil.copy2(BUILD_DB_PATH, repo / "scripts" / "build" / "build_db.py")

    for filename in [
        "events.jsonl",
        "trigger_terms.jsonl",
        "search_logs.jsonl",
        "evidence_clusters.jsonl",
        "thematic_anchors.jsonl",
        "query_profiles.jsonl",
    ]:
        (repo / "data" / filename).write_text("", encoding="utf-8")

    write_jsonl(
        repo / "data" / "sources.jsonl",
        [{"source_id": "SRC-CANON-LANE-001", "title": "测试来源"}],
    )
    write_jsonl(
        repo / "data" / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-CANON-LANE-001",
                "person": "李世民",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "strength": 3,
                "human_level": "强正",
                "source_id": "SRC-CANON-LANE-001",
                "quote_short": "测试短摘",
                "interpretation": "测试解释",
                "trigger_family": "测试触发词",
                "trigger_terms": ["测试"],
                "cross_item_split": "",
                "scoring_effect": "",
                "verification_status": "source_verified",
            }
        ],
    )

    lane_rows = {
        "thematic_anchor_objects.jsonl": [
            {
                "anchor_id": "ANCH-OBJ-001",
                "item": "第五项",
                "subitem": "第五项B",
                "anchor_kind": "person",
                "anchor_scope": "test_scope",
                "object_type": "人物",
                "object_name": "测试对象",
                "object_level": "中",
                "anchor_role": "范围校准",
                "usable_for": ["range_join"],
                "cross_item_risks": ["不要当作直接证据"],
                "consensus_level": "medium",
                "review_status": "provisional",
                "source_batch": "data/thematic_anchor_batches/test.jsonl",
                "note": "测试",
            },
            {
                "anchor_id": "ANCH-OBJ-002",
                "item": "第一项",
                "subitem": "第一项A",
                "anchor_kind": "person",
                "anchor_scope": "test_scope",
                "object_type": "人物",
                "object_name": "其他对象",
                "object_level": "低",
                "anchor_role": "范围校准",
                "usable_for": [],
                "cross_item_risks": [],
                "consensus_level": "low",
                "review_status": "provisional",
                "source_batch": "data/thematic_anchor_batches/test.jsonl",
                "note": "",
            },
        ],
        "thematic_anchor_events.jsonl": [
            {
                "anchor_id": "ANCH-EVT-001",
                "item": "第五项",
                "subitem": "第五项B",
                "anchor_kind": "event",
                "anchor_scope": "test_scope",
                "object_type": "事件",
                "object_name": "测试事件",
                "object_level": "高",
                "anchor_role": "事件校准",
                "usable_for": ["range_join"],
                "cross_item_risks": [],
                "consensus_level": "medium_high",
                "review_status": "provisional",
                "linked_persons": ["刘庄"],
                "source_batch": "data/thematic_anchor_batches/test.jsonl",
                "note": "",
            }
        ],
        "thematic_anchor_mechanisms.jsonl": [
            {
                "anchor_id": "ANCH-MECH-001",
                "item": "第五项",
                "subitem": "第五项B",
                "anchor_kind": "mechanism",
                "anchor_scope": "test_scope",
                "object_type": "机制",
                "object_name": "测试机制",
                "object_level": "高",
                "anchor_role": "机制校准",
                "usable_for": ["range_join"],
                "cross_item_risks": [],
                "consensus_level": "medium_high",
                "review_status": "provisional",
                "linked_persons": ["刘秀"],
                "source_batch": "data/thematic_anchor_batches/test.jsonl",
                "note": "",
            }
        ],
    }
    for filename, rows in lane_rows.items():
        write_jsonl(repo / "data" / filename, rows)

    return repo


def load_build_module(repo: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "temp_build_db",
        repo / "scripts" / "build" / "build_db.py",
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def non_empty_jsonl_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def test_thematic_anchor_lanes_are_loaded_into_sqlite_cache(tmp_path: Path) -> None:
    repo = copy_build_workspace(tmp_path)
    assert not (repo / "data" / "batches").exists()
    assert not (repo / "archive" / "data").exists()

    module = load_build_module(repo)
    db_path = module.build_database()

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert set(ANCHOR_LANES).issubset(table_names)

        for table, filename in ANCHOR_LANES.items():
            assert ANCHOR_COLUMNS.issubset(table_columns(connection, table))
            row_count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert row_count == non_empty_jsonl_count(repo / "data" / filename)

            saved = connection.execute(
                f"""
                SELECT anchor_id, object_name, anchor_kind, source_batch, raw_json
                FROM {table}
                ORDER BY anchor_id
                LIMIT 1
                """
            ).fetchone()
            assert all(saved)
            raw = json.loads(saved[4])
            assert raw["anchor_id"] == saved[0]
            assert raw["object_name"] == saved[1]

        join_rows = connection.execute(
            """
            SELECT ao.anchor_id, ec.evidence_id
            FROM anchor_objects AS ao
            JOIN evidence_cards AS ec
              ON ao.item = ec.item
             AND ao.subitem = ec.subitem
            ORDER BY ao.anchor_id, ec.evidence_id
            """
        ).fetchall()
        assert join_rows == [("ANCH-OBJ-001", "EVD-CANON-LANE-001")]


def test_canonical_lane_contract_names_stable_join_fields() -> None:
    stable_filter_fields = {"anchor_id", "item", "subitem", "source_batch", "review_status"}

    assert stable_filter_fields <= ANCHOR_COLUMNS
    assert NON_STABLE_JOIN_KEYS - {"object_anchor"} <= ANCHOR_COLUMNS
    assert "object_anchor" not in ANCHOR_COLUMNS
