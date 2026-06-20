from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VALIDATE_CONFIG_READABILITY_SPEC = importlib.util.spec_from_file_location(
    "validate_config_readability",
    ROOT / "scripts" / "validate_config_readability.py",
)
assert VALIDATE_CONFIG_READABILITY_SPEC is not None
validate_config_readability = importlib.util.module_from_spec(VALIDATE_CONFIG_READABILITY_SPEC)
assert VALIDATE_CONFIG_READABILITY_SPEC.loader is not None
VALIDATE_CONFIG_READABILITY_SPEC.loader.exec_module(validate_config_readability)


def test_validate_config_readability_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_config_readability.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Config readability validation passed." in result.stdout


def test_validate_config_readability_rejects_cjk_unicode_escape(
    tmp_path: Path, monkeypatch
) -> None:
    view_dir = tmp_path / "view_configs"
    review_dir = tmp_path / "review_configs"
    view_dir.mkdir()
    review_dir.mkdir()
    escaped_path = view_dir / "escaped.jsonl"
    escaped_path.write_text('{"person": "\\u5218\\u90a6"}\n', encoding="utf-8")

    monkeypatch.setattr(
        validate_config_readability,
        "USER_CONFIG_DIRS",
        [view_dir, review_dir],
    )

    errors = validate_config_readability.validate()

    assert errors == [
        f"{escaped_path}: line 1: found escaped CJK unicode sequence '\\\\u5218'; "
        "user-editable config must use UTF-8 Chinese text directly"
    ]


def test_validate_config_readability_reports_file_and_line_for_later_line(
    tmp_path: Path, monkeypatch
) -> None:
    view_dir = tmp_path / "view_configs"
    review_dir = tmp_path / "review_configs"
    view_dir.mkdir()
    review_dir.mkdir()
    escaped_path = review_dir / "escaped.jsonl"
    escaped_path.write_text('{"ok": "中文"}\n{"person": "\\u5218\\u90a6"}\n', encoding="utf-8")

    monkeypatch.setattr(
        validate_config_readability,
        "USER_CONFIG_DIRS",
        [view_dir, review_dir],
    )

    errors = validate_config_readability.validate()

    assert len(errors) == 1
    assert f"{escaped_path}: line 2:" in errors[0]


def test_validate_config_readability_accepts_direct_chinese_and_normal_escape(
    tmp_path: Path, monkeypatch
) -> None:
    view_dir = tmp_path / "view_configs"
    review_dir = tmp_path / "review_configs"
    view_dir.mkdir()
    review_dir.mkdir()
    readable_path = view_dir / "readable.jsonl"
    readable_path.write_text('{"person": "刘邦", "note": "第一行\\n第二行"}\n', encoding="utf-8")

    monkeypatch.setattr(
        validate_config_readability,
        "USER_CONFIG_DIRS",
        [view_dir, review_dir],
    )

    errors = validate_config_readability.validate()

    assert errors == []


def test_validate_config_readability_scans_data_configs_tree(
    tmp_path: Path, monkeypatch
) -> None:
    view_dir = tmp_path / "view_configs"
    review_dir = tmp_path / "review_configs"
    configs_dir = tmp_path / "data" / "configs"
    nested_dir = configs_dir / "视图配置"
    view_dir.mkdir()
    review_dir.mkdir()
    nested_dir.mkdir(parents=True)
    escaped_path = nested_dir / "第五项B_人物池.json"
    escaped_path.write_text('{"person": "\\u5218\\u90a6"}\n', encoding="utf-8")

    monkeypatch.setattr(validate_config_readability, "USER_CONFIG_DIRS", [view_dir, review_dir])
    monkeypatch.setattr(validate_config_readability, "ROOT", tmp_path)

    errors = validate_config_readability.validate()

    assert errors == [
        f"{escaped_path}: line 1: found escaped CJK unicode sequence '\\\\u5218'; "
        "user-editable config must use UTF-8 Chinese text directly"
    ]
