from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
MATRIX_DIR = SCRIPTS_DIR / "matrix"
REGISTRY_PATH = ROOT / "docs" / "agent_rules" / "scripts_registry.json"


def registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_scripts_matrix_directory_exists() -> None:
    assert MATRIX_DIR.is_dir()
    assert (MATRIX_DIR / "__init__.py").is_file()


def test_run_matrix_implementation_and_wrapper_layout() -> None:
    implementation = MATRIX_DIR / "run_matrix.py"
    wrapper = SCRIPTS_DIR / "run_matrix.py"
    implementation_text = implementation.read_text(encoding="utf-8")
    wrapper_text = wrapper.read_text(encoding="utf-8")

    assert implementation.is_file()
    assert wrapper.is_file()
    assert "def export_matrix" in implementation_text
    assert "def grouped_terms" in implementation_text
    assert "HEADERS =" in implementation_text
    assert "EXPORT_PATH =" in implementation_text
    assert len(wrapper_text.splitlines()) <= 25
    assert "from matrix.run_matrix import *" in wrapper_text
    assert "def export_matrix" not in wrapper_text
    assert "HEADERS =" not in wrapper_text
    assert "EXPORT_PATH =" not in wrapper_text


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
        "legacy_wrapper": "scripts/run_matrix.py",
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
    docs = (ROOT / "docs" / "scripts目录规范.md").read_text(encoding="utf-8")

    assert "`scripts/matrix/`" in agents
    assert "矩阵规划和矩阵视图生成脚本的真实实现目录" in agents
    assert "不允许直接重写真实 `exports/**`" in agents
    assert "不得写入评分或证据数据" in agents
    assert "## scripts/matrix/" in docs
    assert "矩阵测试必须隔离输出" in docs
    assert "当前路径、wrapper 和迁移状态继续由 `docs/agent_rules/scripts_registry.json` 管理" in docs


def test_agents_check_passes_with_matrix_layout() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "dev" / "repo_tool.py"), "agents-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
