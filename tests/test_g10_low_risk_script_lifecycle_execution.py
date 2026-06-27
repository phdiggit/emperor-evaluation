from __future__ import annotations

import copy
import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_low_risk_script_lifecycle_execution as lifecycle  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / "data",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_lifecycle_report_declares_issue_341_scope_inputs_and_boundaries() -> None:
    report = lifecycle.build_lifecycle_report()

    assert report["mode"] == "lifecycle-report"
    assert report["package_version"] == "g10-low-risk-script-lifecycle-execution-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["plan_issue"] == 331
    assert report["script_governance_issue"] == 334
    assert report["lifecycle_execution_issue"] == 341
    assert report["next_guard_issue"] == 342
    assert report["final_handoff_issue"] == 335
    assert report["prerequisite_pr"] == 339
    assert report["prerequisite_merge_commit"] == lifecycle.PREREQUISITE_MERGE_COMMIT
    assert report["source_inputs"]["issue_331_inventory_candidate_count"] >= 10
    assert report["source_inputs"]["issue_333_retirement_manifest_package"]
    assert report["source_inputs"]["issue_334_script_risk_report_package"]
    assert report["does_not_touch_data_archive_export_roots"] is True
    assert report["does_not_move_delete_or_archive_files"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True


def test_lifecycle_execution_manifest_records_real_registry_updates_and_restore() -> None:
    report = lifecycle.build_lifecycle_report()
    state = report["current_state"]
    manifest = {item["id"]: item for item in report["lifecycle_execution_manifest"]}

    assert state["current_phase"] == "g10_low_risk_script_lifecycle_execution_ready"
    assert state["g10_2b_low_risk_script_lifecycle_execution_ready"] is True
    assert state["g10_low_risk_lifecycle_update_count"] == len(lifecycle.LOW_RISK_LIFECYCLE_EXECUTION_IDS)
    assert state["g10_low_risk_updated_registry_entries"] == len(lifecycle.LOW_RISK_LIFECYCLE_EXECUTION_IDS)
    assert state["actual_moved_deleted_archived_path_count"] == 0
    assert state["transitional_scripts_without_sunset"] == 0
    assert state["retired_scripts_in_default_validate_or_public_cli"] == 0
    assert state["registry_dangling_reference_count"] == 0
    assert state["restore_instructions_complete"] is True
    assert set(manifest) == set(lifecycle.LOW_RISK_LIFECYCLE_EXECUTION_IDS)

    for item in manifest.values():
        assert item["risk_class"] == "low"
        assert item["previous_field_values"]["lifecycle_status"] == "audit_only"
        assert item["current_field_values"] == item["expected_current_field_values"]
        assert item["current_field_values"]["lifecycle_status"] == "retired"
        assert item["current_field_values"]["replacement"] == lifecycle.REPLACEMENT
        assert item["current_field_values"]["sunset_milestone"] == lifecycle.SUNSET_MILESTONE
        assert item["current_field_values"]["last_required_by"] == lifecycle.LAST_REQUIRED_BY
        assert item["current_field_values"]["public_cli_stable"] is False
        assert item["actual_lifecycle_update"] is True
        assert item["actual_registry_field_update_count"] == 3
        assert item["actual_moved_deleted_archived_paths"] == []
        assert item["default_or_public_route_violation"] is False
        assert len(item["restore_instructions"]) >= 2
        assert "previous_field_values" in item["restore_instructions"][0]


def test_current_registry_has_retired_low_risk_lifecycle_entries() -> None:
    report = lifecycle.build_lifecycle_report()
    retired = set(report["scripts_registry_analysis"]["retired_platform_modules"])

    for item in report["lifecycle_execution_manifest"]:
        assert item["implementation"] in retired

    counts = report["scripts_registry_analysis"]["platform_lifecycle_status_counts"]
    assert counts["retired"] >= len(lifecycle.LOW_RISK_LIFECYCLE_EXECUTION_IDS)


def test_bad_registry_or_route_fixture_is_not_ready() -> None:
    registry = copy.deepcopy(lifecycle._load_json(lifecycle.inventory_plan.SCRIPT_REGISTRY_PATH))
    first_id = lifecycle.LOW_RISK_LIFECYCLE_EXECUTION_IDS[0]
    for module in registry["platform_modules"]:
        if module["id"] == first_id:
            module["lifecycle_status"] = "audit_only"
            module["sunset_milestone"] = None
            break

    report = lifecycle.build_lifecycle_report(
        registry=registry,
        default_route_sources={
            "scripts/validate/validate_all.py": "python scripts/platform/formal_schema_draft.py"
        },
    )

    assert report["current_state"]["g10_2b_low_risk_script_lifecycle_execution_ready"] is False
    assert report["unexpected_current_field_values"][0]["id"] == first_id
    assert report["current_state"]["retired_scripts_in_default_validate_or_public_cli"] >= 1


def test_default_lifecycle_report_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {
        lifecycle.inventory_plan.SCRIPT_REGISTRY_PATH.resolve(),
        *(path.resolve() for path in lifecycle.governance.DEFAULT_VALIDATE_ENTRYPOINTS),
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
        raise AssertionError("network access is forbidden in G10-2b lifecycle execution tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = lifecycle.build_lifecycle_report()
    markdown = lifecycle.render_lifecycle_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert "G10 Low-risk Script Lifecycle Execution" in markdown
    assert "issue342_registry_lifecycle_guard_then_issue335_completion_handoff" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert lifecycle.main(["--lifecycle-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["current_state"]["g10_low_risk_lifecycle_update_count"] == len(
        lifecycle.LOW_RISK_LIFECYCLE_EXECUTION_IDS
    )

    assert lifecycle.main(["--lifecycle-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Restore Instructions" in markdown
    assert "scripts/platform/schema_diff_draft_renderer.py" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "g10_low_risk_script_lifecycle_execution.py").read_text(
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
