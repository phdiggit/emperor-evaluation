from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "文档与脚本登记" / "scripts_registry.json"
PLATFORM_DIR = ROOT / "scripts" / "platform"
REQUIRED_FIELDS = {
    "id",
    "implementation",
    "capability",
    "lifecycle_status",
    "epic_owner",
    "risk_class",
    "replacement",
    "sunset_milestone",
    "last_required_by",
    "public_cli_stable",
}


def load_registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def platform_scripts() -> set[str]:
    return {
        path.relative_to(ROOT).as_posix()
        for path in PLATFORM_DIR.rglob("*.py")
        if path.is_file()
    }


def test_platform_lifecycle_registry_covers_all_platform_python_files() -> None:
    registry = load_registry()
    registered = {module["implementation"] for module in registry["platform_modules"]}

    assert registered == platform_scripts()


def test_platform_lifecycle_entries_have_required_fields_and_allowed_statuses() -> None:
    registry = load_registry()
    allowed = set(registry["platform_lifecycle_statuses"])

    for module in registry["platform_modules"]:
        assert REQUIRED_FIELDS <= module.keys(), module["implementation"]
        assert module["lifecycle_status"] in allowed
        assert module["capability"], module["implementation"]
        assert module["epic_owner"], module["implementation"]
        assert module["risk_class"] in {"low", "medium", "high"}
        assert module["last_required_by"], module["implementation"]
        if module["lifecycle_status"] == "transitional":
            assert module["sunset_milestone"], module["implementation"]
        if module["public_cli_stable"]:
            assert module["lifecycle_status"] == "active", module["implementation"]


def test_platform_core_helpers_are_registered_as_active_shared_components() -> None:
    registry = load_registry()
    modules = {module["implementation"]: module for module in registry["platform_modules"]}

    for path in [
        "scripts/platform/core/evidence.py",
        "scripts/platform/core/fingerprints.py",
        "scripts/platform/core/gates.py",
        "scripts/platform/core/redaction.py",
    ]:
        assert modules[path]["lifecycle_status"] == "active"
        assert modules[path]["public_cli_stable"] is False
