from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
MATRIX_DIR = SCRIPTS_DIR / "matrix"
REGISTRY_PATH = ROOT / "docs" / "治理规则" / "scripts_registry.json"


def registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_scripts_matrix_directory_exists() -> None:
    assert MATRIX_DIR.is_dir()
    assert (MATRIX_DIR / "__init__.py").is_file()


def test_run_matrix_implementation_layout() -> None:
    implementation = MATRIX_DIR / "run_matrix.py"
    implementation_text = implementation.read_text(encoding="utf-8")

    assert implementation.is_file()
    assert not (SCRIPTS_DIR / "run_matrix.py").exists()
    assert "def export_matrix" in implementation_text
    assert "def grouped_terms" in implementation_text
    assert "HEADERS =" in implementation_text
    assert "EXPORT_PATH =" in implementation_text


def test_registry_records_matrix_directory_and_modules() -> None:
    data = registry()
    modules = {module["id"]: module for module in data["modules"]}
    root_exception_paths = {item["path"] for item in data["root_exceptions"]}

    assert data["directories"]["matrix"] == "scripts/matrix"
    assert modules["matrix_package"] == {
        "audit_docs": [],
        "category": "matrix",
        "id": "matrix_package",
        "implementation": "scripts/matrix/__init__.py",
        "legacy_wrapper": None,
        "required_tests": ["tests/test_scripts_matrix_directory_layout.py"],
        "status": "active",
    }
    assert modules["run_matrix"] == {
        "audit_docs": [],
        "category": "matrix",
        "id": "run_matrix",
        "implementation": "scripts/matrix/run_matrix.py",
        "legacy_wrapper": None,
        "required_tests": [
            "tests/test_run_matrix.py",
            "tests/test_scripts_matrix_directory_layout.py",
        ],
        "status": "migrated",
    }
    assert "scripts/run_matrix.py" not in root_exception_paths
    assert "scripts/publish_pr.ps1" in root_exception_paths


def test_docs_and_agents_mention_stable_matrix_rules() -> None:
    agents = (SCRIPTS_DIR / "AGENTS.md").read_text(encoding="utf-8")
    docs = next(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "docs").glob("scripts*.md")
        if "## scripts/dev/" in path.read_text(encoding="utf-8")
    )

    assert "`scripts/matrix/`" in agents
    assert "retired_legacy_wrappers" in agents
    assert "## scripts/matrix/" in docs
    assert "retired_legacy_wrappers" in docs


def test_agents_check_passes_with_matrix_layout() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "dev" / "repo_tool.py"), "agents-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
