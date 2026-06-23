from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "agent_rules" / "scripts_registry.json"
REPO_TOOL_PATH = ROOT / "scripts" / "dev" / "repo_tool.py"


def load_repo_tool():
    spec = importlib.util.spec_from_file_location("repo_tool_under_test_agents", REPO_TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_agents_files_are_inside_registry_budgets() -> None:
    registry = load_registry()
    for rel_path, budget in registry["agents_budgets"].items():
        path = ROOT / rel_path
        assert line_count(path) <= budget["max_lines"]
        assert len(path.read_bytes()) <= budget["max_bytes"]


def test_agents_route_to_scripts_agents_and_registry() -> None:
    root_agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    scripts_agents = (ROOT / "scripts" / "AGENTS.md").read_text(encoding="utf-8")

    assert "scripts/AGENTS.md" in root_agents
    assert "docs/agent_rules/scripts_registry.json" in root_agents
    assert "docs/agent_rules/scripts_registry.json" in scripts_agents


def test_registry_is_valid_and_paths_exist() -> None:
    registry = load_registry()
    assert registry["schema_version"] == 1
    assert registry["legacy_wrapper_policy"] == "retired"
    for rel_path in registry["directories"].values():
        assert (ROOT / rel_path).is_dir()
    for module in registry["modules"]:
        assert (ROOT / module["implementation"]).is_file()
        assert module.get("legacy_wrapper") is None
        for field in ("audit_docs", "required_tests"):
            for rel_path in module[field]:
                assert (ROOT / rel_path).is_file()
    module_ids = {module["id"] for module in registry["modules"]}
    for retired_path, module_id in registry["retired_legacy_wrappers"].items():
        assert module_id in module_ids
        assert retired_path.startswith("scripts/")
        assert retired_path.endswith(".py")
        assert not (ROOT / retired_path).exists()
    for entry in registry["root_exceptions"]:
        path = ROOT / entry["path"]
        assert path.is_file()
        assert path.parent == ROOT / "scripts"


def test_root_scripts_are_fully_covered_by_registry() -> None:
    registry = load_registry()
    exceptions = {entry["path"] for entry in registry["root_exceptions"]}
    root_scripts = {path.relative_to(ROOT).as_posix() for path in (ROOT / "scripts").glob("*.py")}

    assert root_scripts == set()
    assert "scripts/publish_pr.ps1" in exceptions


def test_repo_tool_agents_check_passes_for_real_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_TOOL_PATH), "agents-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_agent_rules_readme_has_decision_table() -> None:
    readme = (ROOT / "docs" / "agent_rules" / "README.md").read_text(encoding="utf-8")
    for needle in (
        "新增规则分类决策表",
        "所有任务都适用",
        "只适用于 scripts",
        "当前路径或迁移状态",
        "可机器验证",
        "当前任务临时要求",
        "历史背景或设计解释",
    ):
        assert needle in readme


def test_root_agents_no_longer_lists_migrated_module_statuses() -> None:
    content = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    forbidden_status_sentences = (
        "export_md.py` 已迁移",
        "validate_all.py` 已迁移",
        "config_loaders.py` 已迁移",
        "i5b_markdown_display.py` 已迁移",
        "真实实现位于 `scripts/export/`",
        "真实实现位于 `scripts/shared/`",
    )
    for sentence in forbidden_status_sentences:
        assert sentence not in content
