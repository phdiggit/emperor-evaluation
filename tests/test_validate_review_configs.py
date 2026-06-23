from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

VALIDATE_REVIEW_CONFIGS_SPEC = importlib.util.spec_from_file_location(
    "validate.validate_review_configs",
    ROOT / "scripts" / "validate" / "validate_review_configs.py",
)
assert VALIDATE_REVIEW_CONFIGS_SPEC is not None
validate_review_configs = importlib.util.module_from_spec(VALIDATE_REVIEW_CONFIGS_SPEC)
sys.modules[VALIDATE_REVIEW_CONFIGS_SPEC.name] = validate_review_configs
assert VALIDATE_REVIEW_CONFIGS_SPEC.loader is not None
VALIDATE_REVIEW_CONFIGS_SPEC.loader.exec_module(validate_review_configs)


def test_validate_review_configs_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate" / "validate_review_configs.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "retired keyword configs are absent" in result.stdout


def test_validate_review_configs_rejects_retired_keyword_configs(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "人工复核配置"
    config_dir.mkdir()
    (config_dir / "第五项B_检索关键词基础.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(validate_review_configs, "REVIEW_CONFIG_DIR", config_dir)

    errors = validate_review_configs.validate()

    assert len(errors) == 1
    assert "retired keyword config must not exist" in errors[0]
