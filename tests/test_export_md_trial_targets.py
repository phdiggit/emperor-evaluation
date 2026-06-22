from __future__ import annotations

import importlib
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

EXPORT_MD_SPEC = importlib.util.spec_from_file_location(
    "export.export_md",
    ROOT / "scripts" / "export" / "export_md.py",
)
assert EXPORT_MD_SPEC is not None
export_md = importlib.util.module_from_spec(EXPORT_MD_SPEC)
sys.modules[EXPORT_MD_SPEC.name] = export_md
assert EXPORT_MD_SPEC.loader is not None
EXPORT_MD_SPEC.loader.exec_module(export_md)

LEGACY_EXPORT_MD_SPEC = importlib.util.spec_from_file_location(
    "export_md",
    ROOT / "scripts" / "export_md.py",
)
assert LEGACY_EXPORT_MD_SPEC is not None
legacy_export_md = importlib.util.module_from_spec(LEGACY_EXPORT_MD_SPEC)
sys.modules[LEGACY_EXPORT_MD_SPEC.name] = legacy_export_md
assert LEGACY_EXPORT_MD_SPEC.loader is not None
LEGACY_EXPORT_MD_SPEC.loader.exec_module(legacy_export_md)


def test_export_md_new_and_legacy_imports_share_implementation() -> None:
    assert legacy_export_md.main is export_md.main
    assert legacy_export_md.export_search_logs_markdown is export_md.export_search_logs_markdown
    assert sys.modules["export_md"] is export_md
    assert importlib.import_module("export_md") is export_md


def test_export_md_root_still_points_to_repo_root() -> None:
    assert export_md.ROOT.resolve() == ROOT.resolve()
    assert legacy_export_md.ROOT.resolve() == ROOT.resolve()


def test_legacy_export_md_wrapper_stays_short() -> None:
    wrapper_text = (ROOT / "scripts" / "export_md.py").read_text(encoding="utf-8")

    assert len(wrapper_text.splitlines()) <= 16
    assert "from export import export_md" in wrapper_text
    assert "def export_" not in wrapper_text


def test_load_i5b_trial_targets_prefers_chinese_view_group_config(
    tmp_path: Path, monkeypatch
) -> None:
    group_path = tmp_path / "第五项B_视图分组.json"
    group_path.write_text(
        json.dumps(
            [
                {
                    "group_id": "第五项B_三人试点",
                    "group_name": "三人试点",
                    "group_type": "试点人物组",
                    "subitem": "第五项B",
                    "persons": ["甲", "乙"],
                    "note": "测试",
                }
            ],
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(export_md.config_loaders, "I5B_VIEW_GROUPS_PATH", group_path)

    targets = export_md.load_i5b_trial_targets()

    assert targets == ["甲", "乙"]


def test_export_search_logs_markdown_uses_trial_targets_config(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "evidence_cache.sqlite"
    group_path = tmp_path / "第五项B_视图分组.json"
    export_path = tmp_path / "第五项B三人试点检索线索.md"

    group_path.write_text(
        json.dumps(
            [
                {
                    "group_id": "第五项B_三人试点",
                    "group_name": "三人试点",
                    "group_type": "试点人物组",
                    "subitem": "第五项B",
                    "persons": ["甲", "乙"],
                    "note": "测试",
                }
            ],
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE search_logs (
                search_id TEXT,
                person TEXT,
                subitem TEXT,
                polarity TEXT,
                trigger_family TEXT,
                query_terms TEXT,
                result_status TEXT,
                result_summary TEXT,
                linked_evidence_id TEXT,
                note TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO search_logs (
                search_id, person, subitem, polarity, trigger_family,
                query_terms, result_status, result_summary, linked_evidence_id, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("S1", "甲", "第五项B", "positive", "family-a", "q1", "pending", "summary-1", "", ""),
                ("S2", "乙", "第五项B", "negative", "family-b", "q2", "pending", "summary-2", "", ""),
                ("S3", "丙", "第五项B", "positive", "family-c", "q3", "pending", "summary-3", "", ""),
                ("S4", "甲", "第五项A", "positive", "family-d", "q4", "pending", "summary-4", "", ""),
            ],
        )
        connection.commit()

    export_md.DB_PATH = db_path
    monkeypatch.setattr(export_md.config_loaders, "I5B_VIEW_GROUPS_PATH", group_path)
    export_md.I5B_TRIAL_TARGETS = export_md.load_i5b_trial_targets()
    export_md.SEARCH_LOGS_EXPORT_PATH = export_path

    written_path = export_md.export_search_logs_markdown()
    content = written_path.read_text(encoding="utf-8")

    assert written_path == export_path
    assert "S1" in content
    assert "S2" in content
    assert "甲" in content
    assert "乙" in content
    assert "S3" not in content
    assert "丙" not in content
    assert "S4" not in content
