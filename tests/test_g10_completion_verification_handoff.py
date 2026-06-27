from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_completion_verification_handoff as completion  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_completion_report_declares_g10_4_scope_and_boundaries() -> None:
    report = completion.build_completion_report()

    assert report["mode"] == "completion-report"
    assert report["package_version"] == "g10-completion-verification-handoff-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["plan_issue"] == 331
    assert report["completion_issue"] == 335
    assert report["prerequisite_pr"] == 344
    assert report["prerequisite_merge_commit"] == completion.PREREQUISITE_MERGE_COMMIT
    assert report["does_not_read_dotenv"] is True
    assert report["does_not_connect_database"] is True
    assert report["does_not_access_network"] is True
    assert report["does_not_read_batch_payloads"] is True
    assert report["does_not_read_generated_export_contents"] is True
    assert report["does_not_move_delete_or_archive_files"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True


def test_completion_current_state_records_handoff_acceptance() -> None:
    state = completion.build_completion_report()["current_state"]

    assert state["current_phase"] == "g10_completion_verification_handoff_ready"
    assert state["g10_4_completion_verification_handoff_ready"] is True
    assert state["g10_completion_report_package"] == "g10-completion-verification-handoff-v1"
    assert state["g10_completion_report_prerequisite_pr"] == 344
    assert state["g10_current_handoff_pr"] == 340
    assert state["g10_open_ready_prs_excluding_current_handoff"] == 0
    assert state["g10_validation_all_green"] is True
    assert state["g10_registry_dangling_references"] == 0
    assert state["g10_report_complete"] is True
    assert state["g10_low_risk_lifecycle_execution_complete"] is True
    assert state["g10_script_governance_guard_enabled"] is True
    assert state["g10_next_phase_after_handoff_merge"] == "post_g10_ready_for_followup_gates"
    assert state["g10_destructive_cleanup_started"] is False
    assert state["stage_or_final_total_table_released"] is False
    assert state["cross_subitem_leaderboard_released"] is False


def test_completion_summarizes_merged_g10_prs_and_results() -> None:
    report = completion.build_completion_report()

    assert [item["issue"] for item in report["merged_g10_prs"]] == [331, 332, 333, 334, 341, 342]
    assert [item["pr"] for item in report["merged_g10_prs"]] == [336, 337, 338, 339, 343, 344]
    assert all(item["merge_commit"] for item in report["merged_g10_prs"])

    summary = report["g10_result_summary"]
    assert summary["issue_332_dictionary_cleanup"]["ready"] is True
    assert summary["issue_332_dictionary_cleanup"]["snapshot_validated"] is True
    assert summary["issue_332_dictionary_cleanup"]["legacy_runtime_copy_matches"] == 0
    assert summary["issue_333_historical_asset_retirement"]["ready"] is True
    assert summary["issue_333_historical_asset_retirement"]["actual_moved_deleted_archived_path_count"] == 0
    assert summary["issue_333_historical_asset_retirement"]["removed_paths_manifest"] == []
    assert summary["issue_333_historical_asset_retirement"]["archived_paths_manifest"] == []
    assert summary["issue_334_script_asset_risk_governance"]["ready"] is True
    assert summary["issue_334_script_asset_risk_governance"]["transitional_scripts_without_sunset"] == 0
    assert summary["issue_334_script_asset_risk_governance"]["retired_scripts_in_default_validate_or_public_cli"] == 0
    assert summary["issue_334_script_asset_risk_governance"]["duplicate_capability_groups_without_reason"] == 0
    assert summary["issue_341_low_risk_script_lifecycle_execution"]["ready"] is True
    assert summary["issue_341_low_risk_script_lifecycle_execution"]["lifecycle_update_count"] == 6
    assert (
        summary["issue_341_low_risk_script_lifecycle_execution"][
            "actual_moved_deleted_archived_path_count"
        ]
        == 0
    )
    assert summary["issue_341_low_risk_script_lifecycle_execution"]["restore_instructions_complete"] is True
    assert summary["issue_342_script_governance_enforcement"]["ready"] is True
    assert summary["issue_342_script_governance_enforcement"]["transitional_scripts_without_sunset"] == 0
    assert (
        summary["issue_342_script_governance_enforcement"][
            "retired_scripts_in_default_validate_or_public_cli"
        ]
        == 0
    )
    assert summary["issue_342_script_governance_enforcement"]["duplicate_capability_exceptions_explicit"] is True
    assert summary["issue_342_script_governance_enforcement"]["errors"] == []


def test_completion_registry_and_acceptance_verification_are_complete() -> None:
    report = completion.build_completion_report()

    audit = report["registry_audit"]
    assert audit["scripts_registry_dangling_references"] == []
    assert audit["docs_registry_dangling_references"] == []
    assert audit["registry_dangling_references_total"] == 0

    acceptance = report["acceptance_verification"]
    assert acceptance["current_handoff_pr"] == 340
    assert acceptance["open_ready_prs_excluding_current_handoff"] == 0
    assert acceptance["validation_all_green"] is True
    assert acceptance["registry_dangling_references"] == 0
    assert acceptance["g10_report_complete"] is True
    assert acceptance["low_risk_lifecycle_execution_complete"] is True
    assert acceptance["script_governance_guard_enabled"] is True
    assert acceptance["next_phase_after_handoff_merge"] == "post_g10_ready_for_followup_gates"
    assert "g10_destructive_cleanup_gate" in acceptance["next_gates"]
    assert "epic2_separate_ready_review" in acceptance["next_gates"]
    assert "epic3_separate_ready_review" in acceptance["next_gates"]


def test_validation_matrix_and_changed_paths_are_manifested() -> None:
    report = completion.build_completion_report()

    commands = {item["name"]: item["command"] for item in report["validation_matrix"]}
    assert "focused_g10_completion_tests" in commands
    assert "script_lifecycle_registry_guard" in commands
    assert "validate_all" in commands
    assert "full_pytest" in commands
    assert set(report["changed_paths_manifest"]) == set(completion.PACKAGE_CHANGED_PATHS)
    assert "scripts/platform/g10_completion_verification_handoff.py" in report["changed_paths_manifest"]


def test_default_completion_report_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        parts = tuple(path.parts)
        if (
            path.name == ".env"
            or "batches" in parts
            or ("archive" in parts and "data" in parts)
            or "exports" in parts
        ):
            raise AssertionError(f"forbidden payload/content read: {path}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G10-4 completion tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = completion.build_completion_report()
    markdown = completion.render_completion_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert "G10 Completion Verification" in markdown
    assert "post_g10_ready_for_followup_gates" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert completion.main(["--completion-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["current_state"]["g10_4_completion_verification_handoff_ready"] is True

    assert completion.main(["--completion-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Merged G10 PRs" in markdown
    assert "g10_destructive_cleanup_gate" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "g10_completion_verification_handoff.py").read_text(
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
