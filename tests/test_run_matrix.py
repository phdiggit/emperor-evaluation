from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

RUN_MATRIX_SPEC = importlib.util.spec_from_file_location(
    "run_matrix",
    ROOT / "scripts" / "run_matrix.py",
)
assert RUN_MATRIX_SPEC is not None
run_matrix = importlib.util.module_from_spec(RUN_MATRIX_SPEC)
assert RUN_MATRIX_SPEC.loader is not None
RUN_MATRIX_SPEC.loader.exec_module(run_matrix)


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_export_matrix_prefers_chinese_view_group_config(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    export_path = tmp_path / "matrix.md"
    group_path = tmp_path / "第五项B_视图分组.json"
    data_dir.mkdir()

    write_jsonl(
        data_dir / "trigger_terms.jsonl",
        [
            {
                "term_id": "TERM-001",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "trigger_family": "任使",
                "tier": "core",
                "term": "纳谏",
            }
        ],
    )
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

    run_matrix.DATA_DIR = data_dir
    run_matrix.EXPORT_PATH = export_path
    monkeypatch.setattr(run_matrix.config_loaders, "I5B_VIEW_GROUPS_PATH", group_path)

    result_path = run_matrix.export_matrix()
    content = result_path.read_text(encoding="utf-8")

    assert result_path == export_path
    assert "甲" in content
    assert "乙" in content
    assert "纳谏" in content
