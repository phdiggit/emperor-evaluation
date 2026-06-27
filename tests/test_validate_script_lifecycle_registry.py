from __future__ import annotations

import copy
import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate import validate_script_lifecycle_registry as guard  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / "data",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def load_registry() -> dict[str, object]:
    return guard._load_json(guard.inventory_plan.SCRIPT_REGISTRY_PATH)


def test_current_scripts_registry_passes_lifecycle_guard() -> None:
    report = guard.build_guard_report()

    assert report["guard_version"] == "script-lifecycle-registry-guard-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["script_governance_enforcement_issue"] == 342
    assert report["errors"] == []
    assert report["current_state"]["registry_lifecycle_guard_ready"] is True
    assert report["current_state"]["transitional_scripts_without_sunset"] == 0
    assert report["current_state"]["retired_scripts_in_default_validate_or_public_cli"] == 0
    assert report["current_state"]["duplicate_capability_groups_reviewed"] >= 5
    assert report["current_state"]["duplicate_capability_exceptions_explicit"] is True
    assert report["current_state"]["duplicate_capability_exception_count"] >= 5


def test_bad_transitional_lifecycle_fixture_fails() -> None:
    registry = copy.deepcopy(load_registry())
    registry["platform_modules"].append(
        {
            "id": "bad_transitional",
            "implementation": "scripts/platform/bad_transitional.py",
            "capability": "temporary script",
            "lifecycle_status": "transitional",
            "epic_owner": "Epic X",
            "risk_class": "medium",
            "replacement": "scripts/platform/platform_chain_checkpoint.py",
            "sunset_milestone": "",
            "last_required_by": "bad fixture",
            "public_cli_stable": False,
        }
    )

    errors = guard.validate_registry_lifecycle(registry, {})

    assert errors == [
        "scripts/platform/bad_transitional.py: transitional lifecycle_status requires sunset_milestone"
    ]


def test_retired_default_and_public_routes_fail() -> None:
    registry = copy.deepcopy(load_registry())
    registry["platform_modules"].append(
        {
            "id": "bad_retired",
            "implementation": "scripts/platform/bad_retired.py",
            "capability": "old public script",
            "lifecycle_status": "retired",
            "epic_owner": "Epic X",
            "risk_class": "low",
            "replacement": "scripts/platform/platform_chain_checkpoint.py",
            "sunset_milestone": "bad fixture",
            "last_required_by": "bad fixture",
            "public_cli_stable": True,
        }
    )

    errors = guard.validate_registry_lifecycle(
        registry,
        {"scripts/validate/validate_all.py": "python scripts/platform/bad_retired.py"},
    )

    assert errors == [
        "scripts/platform/bad_retired.py: retired lifecycle_status must not be public_cli_stable",
        "scripts/validate/validate_all.py: retired script route reference is forbidden: scripts/platform/bad_retired.py",
    ]


def test_duplicate_capability_exception_without_reason_or_plan_fails() -> None:
    registry = copy.deepcopy(load_registry())

    errors = guard.validate_registry_lifecycle(
        registry,
        {},
        duplicate_reviews=[
            {
                "group_id": "bad_duplicate_family",
                "module_count": 2,
                "retain_or_consolidation_reason": "",
                "governance_plan": "",
            }
        ],
    )

    assert errors == [
        "duplicate capability group bad_duplicate_family: module_count > 1 requires "
        "retain_or_consolidation_reason or governance_plan"
    ]


def test_duplicate_capability_exception_with_reason_or_plan_passes() -> None:
    registry = copy.deepcopy(load_registry())

    assert (
        guard.validate_registry_lifecycle(
            registry,
            {},
            duplicate_reviews=[
                {
                    "group_id": "kept_with_reason",
                    "module_count": 2,
                    "retain_or_consolidation_reason": "Separate stage gates are intentionally auditable.",
                },
                {
                    "group_id": "planned_consolidation",
                    "module_count": 3,
                    "governance_plan": "Consolidate after current G10 handoff.",
                },
            ],
        )
        == []
    )


def test_default_guard_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {
        guard.inventory_plan.SCRIPT_REGISTRY_PATH.resolve(),
        *(path.resolve() for path in guard.governance.DEFAULT_VALIDATE_ENTRYPOINTS),
    }

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        parts = tuple(path.parts)
        if path not in allowed_reads:
            if (
                path.name == ".env"
                or "data" in parts
                or ("archive" in parts and "data" in parts)
                or "exports" in parts
            ):
                raise AssertionError(f"forbidden payload/content read: {path}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in script lifecycle registry guard")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = guard.build_guard_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["does_not_touch_data_archive_export_roots"] is True


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert guard.main([]) == 0
    assert "Script lifecycle registry validation passed." in capsys.readouterr().out

    assert guard.main(["--guard-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["current_state"]["registry_lifecycle_guard_ready"] is True


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "validate" / "validate_script_lifecycle_registry.py").read_text(
        encoding="utf-8"
    )

    assert "import psycopg" not in source
    assert "import pika" not in source
    assert "aio_pika" not in source
    assert "import requests" not in source
    assert "subprocess.run" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "PG_SEARCH_BENCH_DSN" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
