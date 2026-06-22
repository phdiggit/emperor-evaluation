from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VALIDATE_VIEW_CONFIGS_SPEC = importlib.util.spec_from_file_location(
    "validate.validate_view_configs",
    ROOT / "scripts" / "validate" / "validate_view_configs.py",
)
assert VALIDATE_VIEW_CONFIGS_SPEC is not None
validate_view_configs = importlib.util.module_from_spec(VALIDATE_VIEW_CONFIGS_SPEC)
assert VALIDATE_VIEW_CONFIGS_SPEC.loader is not None
VALIDATE_VIEW_CONFIGS_SPEC.loader.exec_module(validate_view_configs)


def test_validate_view_configs_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate" / "validate_view_configs.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "View config validation passed." in result.stdout


def test_validate_view_configs_rejects_invalid_json(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "view_configs"
    config_dir.mkdir()
    (config_dir / "broken.jsonl").write_text("{bad json}\n", encoding="utf-8")

    monkeypatch.setattr(validate_view_configs, "VIEW_CONFIG_DIR", config_dir)

    errors = validate_view_configs.validate()

    assert len(errors) == 1
    assert "broken.jsonl: line 1: invalid JSON" in errors[0]


def test_validate_view_configs_rejects_non_object_rows(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "view_configs"
    config_dir.mkdir()
    (config_dir / "not-object.jsonl").write_text('["not", "object"]\n', encoding="utf-8")

    monkeypatch.setattr(validate_view_configs, "VIEW_CONFIG_DIR", config_dir)

    errors = validate_view_configs.validate()

    assert errors == [f"{config_dir / 'not-object.jsonl'}: line 1: expected JSON object, got list"]


def test_validate_view_configs_accepts_generic_jsonl_object_rows(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "view_configs"
    config_dir.mkdir()
    (config_dir / "custom_view.jsonl").write_text('{"name": "A"}\n{"name": "B"}\n', encoding="utf-8")

    monkeypatch.setattr(validate_view_configs, "VIEW_CONFIG_DIR", config_dir)

    errors = validate_view_configs.validate()

    assert errors == []
