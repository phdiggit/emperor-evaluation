from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
REGISTRY_PATH = ROOT / "docs" / "文档与脚本登记" / "scripts_registry.json"
REPO_TOOL_PATH = SCRIPTS_DIR / "dev" / "repo_tool.py"


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_repo_tool():
    spec = importlib.util.spec_from_file_location("repo_tool_under_test_retirement", REPO_TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_records_retired_wrapper_policy() -> None:
    registry = load_registry()

    assert registry["legacy_wrapper_policy"] == "retired"
    assert all(module.get("legacy_wrapper") is None for module in registry["modules"])
    assert registry["retired_legacy_wrappers"]
    assert registry["retired_legacy_wrappers"]["scripts/build_db.py"] == "build_db"
    assert registry["retired_legacy_wrappers"]["scripts/config_loaders.py"] == "config_loaders"


def test_retired_paths_are_absent_and_canonical_implementations_exist() -> None:
    registry = load_registry()
    module_ids = {module["id"]: module for module in registry["modules"]}

    for retired_path, module_id in registry["retired_legacy_wrappers"].items():
        assert retired_path.startswith("scripts/")
        assert retired_path.endswith(".py")
        assert not (ROOT / retired_path).exists()
        assert module_id in module_ids
        assert (ROOT / module_ids[module_id]["implementation"]).is_file()


def test_scripts_root_has_no_python_files_and_keeps_publish_pr_exception() -> None:
    registry = load_registry()
    root_exceptions = {entry["path"] for entry in registry["root_exceptions"]}

    assert sorted(SCRIPTS_DIR.glob("*.py")) == []
    assert "scripts/publish_pr.ps1" in root_exceptions
    assert (SCRIPTS_DIR / "publish_pr.ps1").is_file()


def test_canonical_imports_are_available_for_retired_modules() -> None:
    repo_tool = load_repo_tool()
    registry = load_registry()

    sys.path.insert(0, str(SCRIPTS_DIR))
    for module_id in registry["retired_legacy_wrappers"].values():
        implementation = next(module["implementation"] for module in registry["modules"] if module["id"] == module_id)
        dotted = repo_tool._canonical_module_path(implementation)
        assert importlib.import_module(dotted) is not None


def test_retirement_governance_checks_pass() -> None:
    repo_tool = load_repo_tool()

    assert repo_tool.check_canonical_imports() == []
    assert repo_tool.check_agents() == []


def test_retirement_governance_clis_pass() -> None:
    for command in ("canonical-imports-check", "agents-check"):
        result = subprocess.run(
            [sys.executable, str(REPO_TOOL_PATH), command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_readme_uses_canonical_main_commands() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for old_command in (
        "python scripts/validate_evidence.py",
        "python scripts/validate/validate_evidence.py",
        "python scripts/export_md.py",
        "python scripts/build_db.py",
        "python scripts/run_matrix.py",
    ):
        assert old_command not in readme
    for canonical_command in (
        "python scripts/validate/validate_all.py",
        "python scripts/export/export_md.py",
        "python scripts/build/build_db.py",
        "python scripts/matrix/run_matrix.py",
    ):
        assert canonical_command in readme
