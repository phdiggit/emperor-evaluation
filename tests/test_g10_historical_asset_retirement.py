from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_historical_asset_retirement as retirement  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_retirement_report_declares_g10_2_scope_and_boundaries() -> None:
    report = retirement.build_retirement_report()

    assert report["mode"] == "retirement-report"
    assert report["package_version"] == "g10-historical-asset-retirement-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["plan_issue"] == 331
    assert report["dictionary_cleanup_issue"] == 332
    assert report["retirement_issue"] == 333
    assert report["prerequisite_pr"] == 337
    assert report["prerequisite_merge_commit"] == retirement.PREREQUISITE_MERGE_COMMIT
    assert report["does_not_read_batch_payloads"] is True
    assert report["does_not_read_generated_export_contents"] is True
    assert report["does_not_move_delete_or_archive_files"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True


def test_retirement_current_state_records_manifested_non_destructive_execution() -> None:
    state = retirement.build_retirement_report()["current_state"]

    assert state["current_phase"] == "g10_historical_asset_retirement_ready"
    assert state["g10_2_historical_asset_retirement_ready"] is True
    assert state["g10_execution_started"] is True
    assert state["g10_cleanup_execution_started"] is True
    assert state["g10_destructive_cleanup_started"] is False
    assert state["changed_removed_archived_paths_manifested"] is True
    assert state["actual_moved_deleted_archived_path_count"] == 0
    assert state["destructive_path_actions_deferred"] is True
    assert state["registry_dangling_active_entries"] == 0
    assert state["default_validate_retired_script_invocations"] == 0
    assert state["replacement_mapping_auditable"] is True
    assert state["restore_instructions_complete"] is True
    assert state["stage_or_final_total_table_released"] is False
    assert state["cross_subitem_leaderboard_released"] is False


def test_retirement_manifest_covers_issue_333_candidates_and_restore_instructions() -> None:
    report = retirement.build_retirement_report()
    manifest = {item["asset_id"]: item for item in report["retirement_manifest"]}

    assert report["retirement_manifest_count"] == 5
    assert set(manifest) == {
        "epic5_pre_g10_contract_packages",
        "docs_registry_archived_and_retired_mappings",
        "archive_docs_historical_decision_records",
        "archive_data_jsonl_batch_history",
        "generated_markdown_and_governance_exports",
    }
    assert manifest["epic5_pre_g10_contract_packages"]["execution_status"] == "audit_only_confirmed"
    assert manifest["archive_docs_historical_decision_records"]["execution_status"] == "audit_only_confirmed"
    assert manifest["archive_data_jsonl_batch_history"]["execution_status"] == "archive_deferred"
    assert manifest["generated_markdown_and_governance_exports"]["execution_status"] == "delete_deferred"
    assert all(item["restore_instructions"] for item in manifest.values())
    assert all(not item["actual_moved_deleted_archived_paths"] for item in manifest.values())
    assert report["removed_paths_manifest"] == []
    assert report["archived_paths_manifest"] == []


def test_destructive_candidates_are_deferred_with_reference_evidence() -> None:
    report = retirement.build_retirement_report()
    by_asset = {item["asset_id"]: item for item in report["retirement_manifest"]}

    assert report["destructive_action_deferred_asset_ids"] == [
        "archive_data_jsonl_batch_history",
        "generated_markdown_and_governance_exports",
    ]
    assert by_asset["archive_data_jsonl_batch_history"]["destructive_action_deferred"] is True
    assert by_asset["archive_data_jsonl_batch_history"]["existing_file_count"] > 0
    assert by_asset["generated_markdown_and_governance_exports"]["destructive_action_deferred"] is True
    assert by_asset["generated_markdown_and_governance_exports"]["existing_file_count"] > 0
    assert report["generated_export_existing_file_count"] > 0
    assert report["generated_export_registry_reference_count"] > 0
    assert report["batch_archive_existing_file_count"] > 0
    assert "exports/" in report["protected_destructive_roots"]
    assert "archive/data/" in report["protected_destructive_roots"]


def test_changed_removed_archived_paths_are_manifested() -> None:
    report = retirement.build_retirement_report()

    assert set(report["changed_paths_manifest"]) == set(retirement.PACKAGE_CHANGED_PATHS)
    assert "scripts/platform/g10_historical_asset_retirement.py" in report["changed_paths_manifest"]
    assert "tests/test_g10_historical_asset_retirement.py" in report["changed_paths_manifest"]
    assert report["removed_paths_manifest"] == []
    assert report["archived_paths_manifest"] == []


def test_default_retirement_report_does_not_read_payload_or_export_contents(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {
        retirement.inventory_plan.SCRIPT_REGISTRY_PATH.resolve(),
        retirement.inventory_plan.DOCS_REGISTRY_PATH.resolve(),
    }

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        parts = tuple(path.parts)
        if path not in allowed_reads:
            if (
                path.name == ".env"
                or "batches" in parts
                or ("archive" in parts and "data" in parts)
                or "exports" in parts
            ):
                raise AssertionError(f"forbidden payload/content read: {path}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G10-2 retirement tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = retirement.build_retirement_report()
    markdown = retirement.render_retirement_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert "G10 Historical Asset Retirement" in markdown
    assert "archive_data_jsonl_batch_history" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert retirement.main(["--retirement-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["retirement_manifest_count"] == 5

    assert retirement.main(["--retirement-md"]) == 0
    markdown = capsys.readouterr().out
    assert "generated_markdown_and_governance_exports" in markdown
    assert "issue334_script_asset_risk_governance" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "g10_historical_asset_retirement.py").read_text(
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
