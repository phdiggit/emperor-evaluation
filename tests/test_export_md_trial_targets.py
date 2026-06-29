from __future__ import annotations

import importlib.util
import json
import subprocess
import sqlite3
import sys
from pathlib import Path

import pytest


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

def test_export_md_root_still_points_to_repo_root() -> None:
    assert export_md.ROOT.resolve() == ROOT.resolve()


def test_retired_export_md_wrapper_path_is_absent() -> None:
    assert not (ROOT / "scripts" / "export_md.py").exists()


def test_list_profiles_command_lists_core_profiles() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export" / "export_md.py"), "--list-profiles"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "main:" in result.stdout
    assert "all:" in result.stdout
    assert "i5b-auto:" in result.stdout


def test_naked_export_defaults_to_main_profile(monkeypatch) -> None:
    called_step_names: list[str] = []

    def fake_run_export_steps(steps) -> None:
        called_step_names.extend(step.name for step in steps)

    monkeypatch.setattr(export_md, "run_export_steps", fake_run_export_steps)

    result = export_md.main([])

    assert result == 0
    assert called_step_names == export_md.step_names_for_profile("main")


def test_main_profile_is_composite_entry_only() -> None:
    main_steps = set(export_md.step_names_for_profile("main"))

    assert main_steps == {"evidence_index", "evidence_clusters", "thematic_anchors", "query_profiles"}
    assert "auto_adjudication" not in main_steps
    assert not any(step.startswith("expanded_batch1_") for step in main_steps)


def test_all_profile_preserves_full_export_step_set() -> None:
    all_steps = export_md.step_names_for_profile("all")

    assert all_steps == list(export_md.ALL_EXPORT_STEPS)
    for step_name in export_md.step_names_for_profile("main"):
        assert step_name in all_steps
    assert "auto_adjudication" in all_steps
    assert not any(step.startswith("expanded_batch1_") for step in all_steps)
    assert "i5b-expanded-batch1" not in export_md.EXPORT_PROFILES


def test_i5b_auto_profile_only_runs_auto_adjudication() -> None:
    assert export_md.step_names_for_profile("i5b-auto") == ["auto_adjudication"]


def test_load_i5b_active_targets_prefers_project_config(
    tmp_path: Path, monkeypatch, project_config_writer
) -> None:
    config_path = project_config_writer(
        tmp_path / "project_config.yml",
        view_groups=[
            {
                "group_id": "第五项B_三人试点",
                "group_name": "三人试点",
                "group_type": "试点人物组",
                "subitem": "第五项B",
                "persons": ["甲", "乙"],
                "note": "测试",
            }
        ],
    )
    monkeypatch.setattr(export_md.config_loaders, "PROJECT_CONFIG_PATH", config_path)

    targets = export_md.load_i5b_active_targets()

    assert targets == ["甲", "乙"]


def test_export_search_logs_markdown_uses_active_targets_config(
    tmp_path: Path, monkeypatch, project_config_writer
) -> None:
    db_path = tmp_path / "evidence_cache.sqlite"
    export_path = tmp_path / "第五项B三人试点检索线索.md"

    config_path = project_config_writer(
        tmp_path / "project_config.yml",
        view_groups=[
            {
                "group_id": "第五项B_三人试点",
                "group_name": "三人试点",
                "group_type": "试点人物组",
                "subitem": "第五项B",
                "persons": ["甲", "乙"],
                "note": "测试",
            }
        ],
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
    monkeypatch.setattr(export_md.config_loaders, "PROJECT_CONFIG_PATH", config_path)
    export_md.SEARCH_LOGS_EXPORT_PATH = export_path

    written_path = export_md.export_search_logs_markdown()
    content = written_path.read_text(encoding="utf-8")

    assert written_path == export_path
    assert "S1" in content
    assert "S2" in content
    assert "甲" in content
    assert "乙" in content
    assert "- **活动人物组**：三人试点" in content
    assert "S3" not in content
    assert "丙" not in content
    assert "S4" not in content


def test_db_backed_export_requires_sqlite_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(export_md, "DB_PATH", tmp_path / "missing.sqlite")
    monkeypatch.setattr(export_md, "EXPORT_PATH", tmp_path / "index.md")

    with pytest.raises(FileNotFoundError, match="build_db.py"):
        export_md.export_markdown()


def test_db_backed_export_rejects_empty_sqlite_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "evidence_cache.sqlite"
    with sqlite3.connect(db_path):
        pass
    monkeypatch.setattr(export_md, "DB_PATH", db_path)
    monkeypatch.setattr(export_md, "EXPORT_PATH", tmp_path / "index.md")

    with pytest.raises(RuntimeError, match="evidence_cards"):
        export_md.export_markdown()
