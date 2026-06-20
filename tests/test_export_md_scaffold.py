from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCAFFOLD_SPEC = importlib.util.spec_from_file_location(
    "export_md_scaffold",
    ROOT / "scripts" / "export_md_scaffold.py",
)
assert SCAFFOLD_SPEC is not None
scaffold = importlib.util.module_from_spec(SCAFFOLD_SPEC)
sys.modules[SCAFFOLD_SPEC.name] = scaffold
assert SCAFFOLD_SPEC.loader is not None
SCAFFOLD_SPEC.loader.exec_module(scaffold)


def test_export_db_table_markdown_renders_basic_table(tmp_path: Path) -> None:
    db_path = tmp_path / "evidence_cache.sqlite"
    export_path = tmp_path / "out.md"

    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE demo (raw_json TEXT)")
        connection.execute(
            "INSERT INTO demo (raw_json) VALUES (?)",
            ('{"id":"ROW-001","label":"值|带分隔符","tags":["甲","乙"]}',),
        )
        connection.commit()

    result_path = scaffold.export_db_table_markdown(
        db_path,
        export_path,
        "测试表",
        "demo",
        ["id", "label", "tags"],
        "rowid",
    )

    content = result_path.read_text(encoding="utf-8")
    assert result_path == export_path
    assert "# 测试表" in content
    assert "| id | label | tags |" in content
    assert "值\\|带分隔符" in content
    assert '["甲", "乙"]' in content


def test_run_export_steps_emits_all_exported_paths(capsys: object, tmp_path: Path) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    third = tmp_path / "third.md"

    steps = [
        scaffold.ExportStep("one", lambda: first),
        scaffold.ExportStep("two", lambda: (second, third)),
    ]

    scaffold.run_export_steps(steps)

    output = capsys.readouterr().out
    assert f"exported {first}" in output
    assert f"exported {second}" in output
    assert f"exported {third}" in output
