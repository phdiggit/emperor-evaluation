from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VALIDATE_CHINESE_VIEW_CONFIGS_SPEC = importlib.util.spec_from_file_location(
    "validate.validate_chinese_view_configs",
    ROOT / "scripts" / "validate" / "validate_chinese_view_configs.py",
)
assert VALIDATE_CHINESE_VIEW_CONFIGS_SPEC is not None
validate_chinese_view_configs = importlib.util.module_from_spec(VALIDATE_CHINESE_VIEW_CONFIGS_SPEC)
assert VALIDATE_CHINESE_VIEW_CONFIGS_SPEC.loader is not None
VALIDATE_CHINESE_VIEW_CONFIGS_SPEC.loader.exec_module(validate_chinese_view_configs)


def write_json_array(path: Path, rows: list[object]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def test_validate_chinese_view_configs_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate" / "validate_chinese_view_configs.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Chinese view config validation passed." in result.stdout


def test_validate_chinese_view_configs_rejects_invalid_json(tmp_path: Path, monkeypatch) -> None:
    pool_path = tmp_path / "第五项B_人物池.json"
    groups_path = tmp_path / "第五项B_视图分组.json"
    pool_path.write_text("{bad json}\n", encoding="utf-8")
    groups_path.write_text("[]\n", encoding="utf-8")

    monkeypatch.setattr(validate_chinese_view_configs, "PERSON_POOL_PATH", pool_path)
    monkeypatch.setattr(validate_chinese_view_configs, "VIEW_GROUPS_PATH", groups_path)

    errors = validate_chinese_view_configs.validate()

    assert any(f"{pool_path}: line 1: invalid JSON" in error for error in errors)


def test_validate_chinese_view_configs_rejects_non_object_rows(tmp_path: Path, monkeypatch) -> None:
    pool_path = tmp_path / "第五项B_人物池.json"
    groups_path = tmp_path / "第五项B_视图分组.json"
    write_json_array(pool_path, [["not", "object"]])
    write_json_array(groups_path, [])

    monkeypatch.setattr(validate_chinese_view_configs, "PERSON_POOL_PATH", pool_path)
    monkeypatch.setattr(validate_chinese_view_configs, "VIEW_GROUPS_PATH", groups_path)

    errors = validate_chinese_view_configs.validate()

    assert errors[0] == f"{pool_path}: line 1: expected array item to be JSON object, got list"


def test_validate_chinese_view_configs_checks_cross_file_coverage_and_types(
    tmp_path: Path, monkeypatch
) -> None:
    pool_path = tmp_path / "第五项B_人物池.json"
    groups_path = tmp_path / "第五项B_视图分组.json"

    write_json_array(
        pool_path,
        [
            {"person": "李世民", "subitem": "第五项B"},
            {"person": "李世民", "subitem": "第五项B"},
            {"person": "刘邦", "subitem": ""},
        ],
    )
    write_json_array(
        groups_path,
        [
            {
                "group_id": "第五项B_三人试点",
                "group_name": "三人试点",
                "group_type": "试点人物组",
                "subitem": "第五项B",
                "persons": ["李世民", "刘秀"],
                "note": "n1",
            },
            {
                "group_id": "第五项B_扩展第一批",
                "group_name": "扩展第一批",
                "group_type": "扩展人物组",
                "subitem": "第五项B",
                "persons": "bad",
                "note": "n2",
            },
            {
                "group_id": "第五项B_净证据导出目标",
                "group_name": "净证据导出目标",
                "group_type": "导出人物组",
                "subitem": "第五项B",
                "persons": ["刘秀"],
                "path_template": "exports/markdown_views/wrong-{person}.md",
                "note": "n3",
            },
        ],
    )

    monkeypatch.setattr(validate_chinese_view_configs, "PERSON_POOL_PATH", pool_path)
    monkeypatch.setattr(validate_chinese_view_configs, "VIEW_GROUPS_PATH", groups_path)

    errors = validate_chinese_view_configs.validate()

    assert any(
        error.startswith(f"{pool_path}: line ")
        and "duplicate person '李世民' (already defined at line " in error
        for error in errors
    )
    assert any(
        error.startswith(f"{pool_path}: line ") and error.endswith("subitem must be a non-empty string")
        for error in errors
    )
    assert any(
        error.startswith(f"{groups_path}: line ")
        and error.endswith("persons must be a non-empty list of non-empty strings")
        for error in errors
    )
    assert any(
        error.startswith(f"{groups_path}: line ")
        and f"person '刘秀' is not defined in {pool_path.name}" in error
        for error in errors
    )
    assert any(
        error.startswith(f"{groups_path}: line ")
        and "required group_id '第五项B_扩展第一批' is missing or invalid" in error
        for error in errors
    )
    assert any(
        error.startswith(f"{groups_path}: line ")
        and "path_template for '第五项B_净证据导出目标'" in error
        for error in errors
    )


def test_validate_chinese_view_configs_rejects_non_array_top_level(tmp_path: Path, monkeypatch) -> None:
    pool_path = tmp_path / "第五项B_人物池.json"
    groups_path = tmp_path / "第五项B_视图分组.json"
    pool_path.write_text('{"person": "李世民"}\n', encoding="utf-8")
    write_json_array(groups_path, [])

    monkeypatch.setattr(validate_chinese_view_configs, "PERSON_POOL_PATH", pool_path)
    monkeypatch.setattr(validate_chinese_view_configs, "VIEW_GROUPS_PATH", groups_path)

    errors = validate_chinese_view_configs.validate()

    assert errors[0] == f"{pool_path}: line 1: expected top-level JSON array, got dict"

