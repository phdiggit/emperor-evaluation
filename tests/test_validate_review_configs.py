from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VALIDATE_REVIEW_CONFIGS_SPEC = importlib.util.spec_from_file_location(
    "validate_review_configs",
    ROOT / "scripts" / "validate_review_configs.py",
)
assert VALIDATE_REVIEW_CONFIGS_SPEC is not None
validate_review_configs = importlib.util.module_from_spec(VALIDATE_REVIEW_CONFIGS_SPEC)
assert VALIDATE_REVIEW_CONFIGS_SPEC.loader is not None
VALIDATE_REVIEW_CONFIGS_SPEC.loader.exec_module(validate_review_configs)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def test_validate_review_configs_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_review_configs.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Review config validation passed." in result.stdout


def test_validate_review_configs_rejects_non_array_top_level(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "人工复核配置"
    config_dir.mkdir()
    config_path = config_dir / "第五项B_检索关键词基础.json"
    write_json(config_path, {"profile_id": "P1"})

    monkeypatch.setattr(validate_review_configs, "REVIEW_CONFIG_DIR", config_dir)

    errors = validate_review_configs.validate()

    assert errors == [f"{config_path}: line 1: expected top-level JSON array, got dict"]


def test_validate_review_configs_rejects_non_object_rows(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "人工复核配置"
    config_dir.mkdir()
    config_path = config_dir / "第五项B_检索关键词基础.json"
    write_json(config_path, [["not", "object"]])

    monkeypatch.setattr(validate_review_configs, "REVIEW_CONFIG_DIR", config_dir)

    errors = validate_review_configs.validate()

    assert errors == [f"{config_path}: line 1: expected array item to be JSON object, got list"]


def test_validate_review_configs_checks_terms_scope_and_duplicate_ids(
    tmp_path: Path, monkeypatch
) -> None:
    config_dir = tmp_path / "人工复核配置"
    config_dir.mkdir()
    config_path = config_dir / "第五项B_检索关键词基础.json"
    write_json(
        config_path,
        [
            {
                "profile_id": "KW-I5B-001",
                "subitem": "第五项B",
                "scope_type": "subitem",
                "scope_key": "第五项B",
                "terms": ["任用", "授权"],
            },
            {
                "profile_id": "KW-I5B-001",
                "subitem": "第五项B",
                "scope_type": "person",
                "scope_key": "刘邦",
                "person": "",
                "terms": "任用",
            },
            {
                "note": "missing scope and terms",
            },
        ],
    )

    monkeypatch.setattr(validate_review_configs, "REVIEW_CONFIG_DIR", config_dir)

    errors = validate_review_configs.validate()

    assert any("duplicate profile_id 'KW-I5B-001'" in error for error in errors)
    assert any(error.endswith("person must be a non-empty string") for error in errors)
    assert any(error.endswith("terms must be a list of non-empty strings") for error in errors)
    assert any(error.endswith("profile_id must be a non-empty string") for error in errors)
    assert any(error.endswith("subitem must be '第五项B'") for error in errors)
    assert any(error.endswith("scope_type must be a non-empty string") for error in errors)
    assert any(error.endswith("scope_key must be a non-empty string") for error in errors)
    assert any(error.endswith("must include at least one keyword terms field") for error in errors)


def test_validate_review_configs_checks_required_i5b_schema_fields(
    tmp_path: Path, monkeypatch
) -> None:
    config_dir = tmp_path / "人工复核配置"
    config_dir.mkdir()
    profile_path = config_dir / "第五项B_检索关键词基础.json"
    override_path = config_dir / "第五项B_检索关键词补丁.json"
    write_json(
        profile_path,
        [
            {
                "profile_id": "",
                "subitem": "第五项A",
                "scope_type": "",
                "scope_key": "",
                "positive_terms": [],
            }
        ],
    )
    write_json(
        override_path,
        [
            {
                "subitem": "第五项B",
                "scope_type": "person",
                "scope_key": "刘邦",
                "source_scopes": ["列传"],
            }
        ],
    )

    monkeypatch.setattr(validate_review_configs, "REVIEW_CONFIG_DIR", config_dir)

    errors = validate_review_configs.validate()

    assert any(str(profile_path) in error and "profile_id must be a non-empty string" in error for error in errors)
    assert any(str(profile_path) in error and "subitem must be '第五项B'" in error for error in errors)
    assert any(str(profile_path) in error and "positive_terms must be a list of non-empty strings" in error for error in errors)
    assert any(str(override_path) in error and "override_id must be a non-empty string" in error for error in errors)
    assert any(str(override_path) in error and "must include at least one keyword terms field" in error for error in errors)


def test_validate_review_configs_rejects_cjk_unicode_escape(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "人工复核配置"
    config_dir.mkdir()
    config_path = config_dir / "第五项B_检索关键词基础.json"
    config_path.write_text(
        '[{"profile_id": "KW-I5B-001", "subitem": "\\u7b2c\\u4e94\\u9879B", "scope_type": "subitem", "scope_key": "第五项B", "terms": ["任用"]}]\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(validate_review_configs, "REVIEW_CONFIG_DIR", config_dir)

    errors = validate_review_configs.validate()

    assert errors == [
        f"{config_path}: line 1: found escaped CJK unicode sequence '\\\\u7b2c'; "
        "user-editable config must use UTF-8 Chinese text directly"
    ]
