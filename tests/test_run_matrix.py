from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
RUN_MATRIX_PATH = SCRIPTS_DIR / "matrix" / "run_matrix.py"
LEGACY_RUN_MATRIX_PATH = SCRIPTS_DIR / "run_matrix.py"
EXPECTED_EXPORT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "自动结算草案"
    / "第五项B三人试点正负证矩阵.md"
)
EXPECTED_HEADERS = [
    "person",
    "item",
    "subitem",
    "polarity",
    "trigger_family",
    "core_terms",
    "extended_terms",
    "matrix_status",
    "note",
]

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

run_matrix = importlib.import_module("matrix.run_matrix")
legacy_run_matrix = importlib.import_module("run_matrix")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_new_and_legacy_modules_are_importable() -> None:
    assert run_matrix.__file__ == str(RUN_MATRIX_PATH)
    assert legacy_run_matrix.export_matrix is run_matrix.export_matrix
    assert legacy_run_matrix.main is run_matrix.main


def test_paths_and_headers_do_not_drift() -> None:
    assert run_matrix.ROOT == ROOT
    assert run_matrix.DATA_DIR == ROOT / "data"
    assert run_matrix.EXPORT_PATH == EXPECTED_EXPORT_PATH
    assert run_matrix.HEADERS == EXPECTED_HEADERS


def test_legacy_wrapper_is_short_and_contains_no_matrix_logic() -> None:
    wrapper_text = LEGACY_RUN_MATRIX_PATH.read_text(encoding="utf-8")
    assert len(wrapper_text.splitlines()) <= 25
    assert "from matrix.run_matrix import *" in wrapper_text
    assert "def export_matrix" not in wrapper_text
    assert "def grouped_terms" not in wrapper_text
    assert "HEADERS =" not in wrapper_text
    assert "EXPORT_PATH =" not in wrapper_text
    assert "第五项B三人试点正负证矩阵" not in wrapper_text


def test_external_matrix_package_conflict_is_cleared(tmp_path: Path, monkeypatch) -> None:
    external_package_dir = tmp_path / "site-packages" / "matrix"
    external_package_dir.mkdir(parents=True)
    external_module = types.ModuleType("matrix")
    external_module.__path__ = [str(external_package_dir)]
    external_module.__file__ = str(external_package_dir / "__init__.py")
    monkeypatch.setitem(sys.modules, "matrix", external_module)
    monkeypatch.delitem(sys.modules, "matrix.run_matrix", raising=False)
    monkeypatch.syspath_prepend(str(tmp_path / "site-packages"))

    spec = importlib.util.spec_from_file_location("legacy_run_matrix_conflict_test", LEGACY_RUN_MATRIX_PATH)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    assert Path(sys.modules["matrix"].__path__[0]).resolve() == SCRIPTS_DIR / "matrix"
    assert Path(legacy.export_matrix.__code__.co_filename).resolve() == RUN_MATRIX_PATH
    assert Path(legacy.main.__code__.co_filename).resolve() == RUN_MATRIX_PATH


def test_read_jsonl_missing_file_and_empty_lines(tmp_path: Path) -> None:
    assert run_matrix.read_jsonl(tmp_path / "missing.jsonl") == []
    path = tmp_path / "rows.jsonl"
    path.write_text('\n{"term": "甲"}\n\n{"term": "乙"}\n', encoding="utf-8")
    assert run_matrix.read_jsonl(path) == [{"term": "甲"}, {"term": "乙"}]


def test_escape_cell_preserves_existing_behavior() -> None:
    assert run_matrix.escape_cell(None) == ""
    assert run_matrix.escape_cell("甲|乙") == "甲\\|乙"
    assert run_matrix.escape_cell("甲\n乙") == "甲 乙"
    assert run_matrix.escape_cell(3) == "3"


def test_human_display_config_hides_machine_field_name_without_mutating_source(monkeypatch) -> None:
    source = {"keep_machine_field_name": True, "field_labels": {"person": "人物"}}
    monkeypatch.setattr(run_matrix, "load_display_dictionary", lambda: source)

    config = run_matrix.human_display_config()

    assert config["keep_machine_field_name"] is False
    assert config["field_labels"] == {"person": "人物"}
    assert source["keep_machine_field_name"] is True


def test_grouped_terms_filters_groups_and_sorts_without_changing_semantics() -> None:
    rows = [
        {
            "term_id": "T-004",
            "item": "第五项",
            "subitem": "第五项B",
            "polarity": "negative",
            "trigger_family": "严刑",
            "tier": "extended",
            "term": "廷杖",
        },
        {
            "term_id": "T-001",
            "item": "第五项",
            "subitem": "第五项B",
            "polarity": "positive",
            "trigger_family": "任使",
            "tier": "core",
            "term": "纳谏",
        },
        {
            "term_id": "T-003",
            "item": "第五项",
            "subitem": "第五项B",
            "polarity": "positive",
            "trigger_family": "任使",
            "tier": "unknown",
            "term": "不应入列",
        },
        {
            "term_id": "T-002",
            "item": "第五项",
            "subitem": "第五项B",
            "polarity": "positive",
            "trigger_family": "任使",
            "tier": "extended",
            "term": "用人",
        },
        {
            "term_id": "T-005",
            "item": "第五项",
            "subitem": "第五项B",
            "polarity": "other",
            "trigger_family": "边界",
            "tier": "core",
            "term": "",
        },
        {
            "term_id": "T-006",
            "item": "第五项",
            "subitem": "第五项A",
            "polarity": "positive",
            "trigger_family": "错项",
            "tier": "core",
            "term": "错项",
        },
    ]

    assert run_matrix.grouped_terms(rows, "第五项", "第五项B") == [
        {
            "polarity": "positive",
            "trigger_family": "任使",
            "core_terms": "纳谏",
            "extended_terms": "用人",
        },
        {
            "polarity": "negative",
            "trigger_family": "严刑",
            "core_terms": "",
            "extended_terms": "廷杖",
        },
        {
            "polarity": "other",
            "trigger_family": "边界",
            "core_terms": "",
            "extended_terms": "",
        },
    ]


def test_export_matrix_uses_trial_config_and_temp_output(tmp_path: Path, monkeypatch) -> None:
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
            },
            {
                "term_id": "TERM-002",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "negative",
                "trigger_family": "刑辱",
                "tier": "core",
                "term": "廷杖",
            },
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

    monkeypatch.setattr(run_matrix, "DATA_DIR", data_dir)
    monkeypatch.setattr(run_matrix, "EXPORT_PATH", export_path)
    monkeypatch.setattr(run_matrix.config_loaders, "I5B_VIEW_GROUPS_PATH", group_path)
    monkeypatch.setattr(run_matrix, "load_display_dictionary", lambda: {})

    result_path = run_matrix.export_matrix()
    content = result_path.read_text(encoding="utf-8")

    assert result_path == export_path
    assert not EXPECTED_EXPORT_PATH.exists() or EXPECTED_EXPORT_PATH != result_path
    assert content.startswith("# 第五项B三人试点正负证矩阵\n\n")
    assert "本文件为矩阵骨架，尚未检索，不写入 search_logs，不生成 evidence_cards，不生成评分。" in content
    assert "planned_not_searched" in content
    assert "矩阵骨架，尚未检索，不得入分" in content
    assert content.index("甲") < content.index("乙")
    assert "纳谏" in content
    assert "廷杖" in content
    assert "李世民" not in content
