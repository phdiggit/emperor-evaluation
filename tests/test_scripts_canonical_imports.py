from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "文档与脚本登记" / "scripts_registry.json"
REPO_TOOL_PATH = ROOT / "scripts" / "dev" / "repo_tool.py"


def load_repo_tool():
    spec = importlib.util.spec_from_file_location("repo_tool_under_test_canonical_imports", REPO_TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_real_repo_canonical_imports_check_passes() -> None:
    repo_tool = load_repo_tool()

    assert repo_tool.check_canonical_imports() == []


def test_real_repo_canonical_imports_cli_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_TOOL_PATH), "canonical-imports-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_registry_retired_wrapper_stems_map_to_canonical_dotted_paths() -> None:
    repo_tool = load_repo_tool()
    registry = load_registry()
    mapping = repo_tool._legacy_wrapper_import_map(registry)
    modules = {module["id"]: module for module in registry["modules"]}

    for retired_path, module_id in registry["retired_legacy_wrappers"].items():
        implementation = modules[module_id]["implementation"]
        assert Path(retired_path).stem in mapping
        assert mapping[Path(retired_path).stem] == repo_tool._canonical_module_path(implementation)
        assert mapping[Path(retired_path).stem]
        assert not mapping[Path(retired_path).stem].startswith("scripts.")


def test_registry_implementations_have_no_legacy_imports() -> None:
    registry = load_registry()
    legacy_stems = {Path(path).stem for path in registry["retired_legacy_wrappers"]}

    for module in registry["modules"]:
        implementation = module.get("implementation")
        if not implementation or not implementation.endswith(".py"):
            continue
        path = ROOT / implementation
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=implementation)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".", 1)[0] not in legacy_stems, implementation
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".", 1)[0] not in legacy_stems, implementation
