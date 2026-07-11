from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs/文档与脚本登记/scripts_registry.json"


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_current_v3_tools_are_registered_and_resolve() -> None:
    modules = load_registry()["modules"]
    implementations = {module["implementation"] for module in modules}
    current_tools = sorted((ROOT / "scripts/dev").glob("retrieval_v3_*.py"))

    assert current_tools
    for path in current_tools:
        relative = path.relative_to(ROOT).as_posix()
        assert relative in implementations


def test_registry_has_no_retired_v2_paths_or_missing_tests() -> None:
    registry = load_registry()
    serialized = json.dumps(registry, ensure_ascii=False)

    assert "retrieval_" + "v2" not in serialized
    assert registry["retired_legacy_wrappers"] == []
    for module in registry["modules"]:
        assert (ROOT / module["implementation"]).is_file()
        for test_path in module.get("required_tests", []):
            assert (ROOT / test_path).is_file()
