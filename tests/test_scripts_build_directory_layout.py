from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
BUILD_DIR = SCRIPTS_DIR / "build"
REGISTRY_PATH = ROOT / "docs" / "agent_rules" / "scripts_registry.json"


def registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_scripts_build_directory_exists() -> None:
    assert BUILD_DIR.is_dir()
    assert (BUILD_DIR / "__init__.py").is_file()


def test_build_db_implementation_and_wrapper_layout() -> None:
    implementation = BUILD_DIR / "build_db.py"
    wrapper = SCRIPTS_DIR / "build_db.py"
    wrapper_text = wrapper.read_text(encoding="utf-8")
    implementation_text = implementation.read_text(encoding="utf-8")

    assert implementation.is_file()
    assert wrapper.is_file()
    assert "def build_database" in implementation_text
    assert "TABLE_FILES" in implementation_text
    assert len(wrapper_text.splitlines()) <= 25
    assert "from build.build_db import *" in wrapper_text
    assert "def build_database" not in wrapper_text
    assert "TABLE_FILES" not in wrapper_text
    assert "TABLE_COLUMNS" not in wrapper_text


def test_registry_records_build_directory_and_modules() -> None:
    data = registry()
    modules = {module["id"]: module for module in data["modules"]}
    root_exception_paths = {item["path"] for item in data["root_exceptions"]}

    assert data["directories"]["build"] == "scripts/build"
    assert modules["build_package"] == {
        "audit_docs": [],
        "category": "build",
        "id": "build_package",
        "implementation": "scripts/build/__init__.py",
        "legacy_wrapper": None,
        "required_tests": ["tests/test_scripts_build_directory_layout.py"],
        "status": "active",
    }
    assert modules["build_db"] == {
        "audit_docs": [],
        "category": "build",
        "id": "build_db",
        "implementation": "scripts/build/build_db.py",
        "legacy_wrapper": "scripts/build_db.py",
        "required_tests": [
            "tests/test_build_db.py",
            "tests/test_scripts_build_directory_layout.py",
            "tests/test_evidence_integrity.py",
        ],
        "status": "migrated",
    }
    assert "scripts/build_db.py" not in root_exception_paths
    assert "scripts/run_matrix.py" in root_exception_paths


def test_docs_and_agents_mention_stable_build_rules() -> None:
    agents = (SCRIPTS_DIR / "AGENTS.md").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "scripts目录规范.md").read_text(encoding="utf-8")

    assert "`scripts/build/`" in agents
    assert "构建脚本测试不得直接覆盖真实工作区数据库" in agents
    assert "默认使用 `tmp_path` 或临时仓库" in agents
    assert "## scripts/build/" in docs
    assert "数据库构建测试应隔离到 `tmp_path` 或临时仓库" in docs
    assert "根目录脚本当前状态继续由 `docs/agent_rules/scripts_registry.json` 管理" in docs


def test_agents_check_passes_with_build_layout() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "dev" / "repo_tool.py"), "agents-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
