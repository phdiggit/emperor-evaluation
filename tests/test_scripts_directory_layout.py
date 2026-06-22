from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATE_DIR = ROOT / "scripts" / "validate"
MIGRATED_VALIDATORS = [
    "validate_evidence.py",
    "validate_canonical_data_integrity.py",
    "validate_view_configs.py",
    "validate_chinese_view_configs.py",
    "validate_review_configs.py",
    "validate_config_comments.py",
    "validate_human_readable_markdown_exports.py",
    "validate_i5b_cluster_adjudication_configs.py",
    "validate_config_readability.py",
]
NEWLY_MIGRATED_VALIDATORS = [
    "validate_evidence",
    "validate_canonical_data_integrity",
    "validate_view_configs",
    "validate_chinese_view_configs",
    "validate_review_configs",
    "validate_config_readability",
]


def test_scripts_validate_directory_exists() -> None:
    assert VALIDATE_DIR.is_dir()
    assert (VALIDATE_DIR / "__init__.py").is_file()


def test_migrated_validator_implementations_live_under_validate_dir() -> None:
    for name in MIGRATED_VALIDATORS:
        assert (VALIDATE_DIR / name).is_file()


def test_legacy_validator_paths_remain_short_wrappers() -> None:
    for name in MIGRATED_VALIDATORS:
        wrapper_path = ROOT / "scripts" / name
        content = wrapper_path.read_text(encoding="utf-8")

        assert wrapper_path.is_file()
        assert len(content.splitlines()) <= 14
        assert "from validate." in content
        assert "def validate" not in content
        assert "def validate_exports" not in content
        assert "def validate_row" not in content
        assert "REQUIRED_" not in content
        assert "VALID_" not in content


def test_validate_all_points_migrated_validators_to_new_paths() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate.validate_all", VALIDATE_DIR / "validate_all.py")
    assert spec is not None
    validate_all = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(validate_all)

    steps = dict(validate_all.VALIDATION_STEPS)

    for module_name in NEWLY_MIGRATED_VALIDATORS:
        assert steps[module_name] == VALIDATE_DIR / f"{module_name}.py"
    assert steps["validate_config_comments"] == VALIDATE_DIR / "validate_config_comments.py"
    assert (
        steps["validate_human_readable_markdown_exports"]
        == VALIDATE_DIR / "validate_human_readable_markdown_exports.py"
    )
    assert (
        steps["validate_i5b_cluster_adjudication_configs"]
        == VALIDATE_DIR / "validate_i5b_cluster_adjudication_configs.py"
    )


def test_validate_all_entrypoint_implementation_lives_under_validate_dir() -> None:
    implementation_path = VALIDATE_DIR / "validate_all.py"
    wrapper_path = ROOT / "scripts" / "validate_all.py"
    wrapper_text = wrapper_path.read_text(encoding="utf-8")

    assert implementation_path.is_file()
    assert wrapper_path.is_file()
    assert len(wrapper_text.splitlines()) <= 16
    assert "from validate import validate_all" in wrapper_text
    assert "VALIDATION_STEPS = [" not in wrapper_text
    assert "def run_step" not in wrapper_text


@pytest.mark.parametrize("name", MIGRATED_VALIDATORS)
@pytest.mark.parametrize("script_root", [VALIDATE_DIR, ROOT / "scripts"])
def test_new_and_legacy_validator_commands_run(name: str, script_root: Path) -> None:
    script_path = script_root / name
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("module_name", NEWLY_MIGRATED_VALIDATORS)
def test_new_and_legacy_validator_imports_remain_compatible(module_name: str) -> None:
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))

    new_module = importlib.import_module(f"validate.{module_name}")
    legacy_module = importlib.import_module(module_name)

    assert new_module.ROOT.resolve() == ROOT.resolve()
    assert legacy_module.ROOT.resolve() == ROOT.resolve()
    assert callable(new_module.main)
    assert callable(legacy_module.main)


@pytest.mark.parametrize("module_name", NEWLY_MIGRATED_VALIDATORS)
def test_newly_migrated_new_and_legacy_commands_return_same_exit_code(module_name: str) -> None:
    new_script = VALIDATE_DIR / f"{module_name}.py"
    legacy_script = ROOT / "scripts" / f"{module_name}.py"
    new_result = subprocess.run(
        [sys.executable, str(new_script)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    legacy_result = subprocess.run(
        [sys.executable, str(legacy_script)], cwd=ROOT, capture_output=True, text=True, check=False
    )

    assert new_result.returncode == legacy_result.returncode == 0


def test_new_and_legacy_validate_all_commands_run() -> None:
    for script_path in (VALIDATE_DIR / "validate_all.py", ROOT / "scripts" / "validate_all.py"):
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "[validate_all] all validation steps passed" in result.stdout


def test_scripts_layout_doc_mentions_validate_directory() -> None:
    content = (ROOT / "docs" / "scripts目录规范.md").read_text(encoding="utf-8")

    assert "scripts/validate/" in content
    assert "新增 validator 应放入这里" in content
    assert "兼容 wrapper" in content


def test_agents_mentions_new_validator_layout_rule() -> None:
    content = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "新增 validator 应放入 `scripts/validate/`" in content
    assert "旧 validator 仅作为兼容 wrapper" in content
