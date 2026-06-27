from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import post_g10_script_lifecycle_finalization as finalization  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_finalization_report_declares_scope_and_boundaries() -> None:
    report = finalization.build_finalization_report()

    assert report["mode"] == "finalization-report"
    assert report["package_version"] == "post-g10-script-lifecycle-finalization-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["post_g10_s1_issue"] == 346
    assert report["prerequisite_pr"] == 345
    assert report["prerequisite_merge_commit"] == finalization.PREREQUISITE_MERGE_COMMIT
    assert report["does_not_read_dotenv"] is True
    assert report["does_not_connect_database"] is True
    assert report["does_not_access_network"] is True
    assert report["does_not_read_batch_payloads"] is True
    assert report["does_not_read_generated_exports"] is True
    assert report["does_not_touch_data_archive_export_roots"] is True
    assert report["does_not_move_delete_or_archive_files"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["does_not_publish_leaderboards"] is True
    assert report["does_not_enter_epic2_or_epic3"] is True


def test_finalization_current_state_records_real_lifecycle_actions() -> None:
    state = finalization.build_finalization_report()["current_state"]

    assert state["current_phase"] == "post_g10_s1_script_lifecycle_finalization_ready"
    assert state["post_g10_s1_script_lifecycle_finalization_ready"] is True
    assert state["post_g10_script_lifecycle_finalization_package"] == (
        "post-g10-script-lifecycle-finalization-v1"
    )
    assert state["script_lifecycle_finalization_non_active_item_count"] == 30
    assert state["script_lifecycle_finalization_updated_registry_entries"] == 24
    assert state["script_lifecycle_finalization_retired_in_place_count"] == 30
    assert state["script_lifecycle_finalization_missing_ids"] == 0
    assert state["script_lifecycle_finalization_unexpected_final_fields"] == 0
    assert state["script_lifecycle_finalization_restore_instructions_complete"] is True
    assert state["script_lifecycle_finalization_actual_moved_deleted_archived_path_count"] == 0
    assert state["script_lifecycle_finalization_replacement_paths_exist"] is True
    assert state["transitional_scripts_without_sunset"] == 0
    assert state["retired_scripts_in_default_validate_or_public_cli"] == 0
    assert state["duplicate_capability_groups_reviewed"] >= 5
    assert state["duplicate_capability_groups_without_reason"] == 0
    assert state["registry_lifecycle_guard_ready"] is True
    assert state["report_only_tests_replaced"] is True
    assert state["remaining_script_governance_debt"] == []
    assert state["script_lifecycle_finalization_remaining_debt_count"] == 0
    assert state["script_governance_report_only_fallback_allowed"] is False
    assert state["g10_destructive_cleanup_started"] is False
    assert state["stage_or_final_total_table_released"] is False
    assert state["cross_subitem_leaderboard_released"] is False
    assert state["epic_2_entered"] is False
    assert state["epic_3_entered"] is False


def test_all_non_active_script_assets_have_final_decisions_and_restore_instructions() -> None:
    report = finalization.build_finalization_report()
    manifest = report["script_lifecycle_finalization_manifest"]

    assert len(manifest) == 30
    assert {item["id"] for item in manifest} == set(finalization.FINALIZED_SCRIPT_IDS)
    assert sum(1 for item in manifest if item["actual_registry_lifecycle_finalization"]) == 24
    assert all(item["final_lifecycle_decision"] == "retire_in_place" for item in manifest)
    assert all(item["file_path_action"] == "retained_in_place" for item in manifest)
    assert all(item["actual_moved_deleted_archived_paths"] == [] for item in manifest)
    assert all(item["replacement_exists"] is True for item in manifest)
    assert all(item["restore_instructions"] for item in manifest)

    finalized = {
        item["id"]: item
        for item in manifest
        if item["id"] in finalization.FINALIZE_RETIRE_IN_PLACE_IDS
    }
    assert len(finalized) == 24
    for item in finalized.values():
        fields = item["current_field_values"]
        assert fields["lifecycle_status"] == "retired"
        assert fields["sunset_milestone"] == finalization.SUNSET_MILESTONE
        assert fields["last_required_by"] == finalization.LAST_REQUIRED_BY
        assert fields["public_cli_stable"] is False
        assert "git show" in item["restore_instructions"][0]


def test_current_registry_has_no_non_final_platform_script_lifecycle_statuses() -> None:
    report = finalization.build_finalization_report()
    counts = report["scripts_registry_analysis"]["platform_lifecycle_status_counts"]

    assert counts["retired"] == 30
    assert counts["active"] >= 60
    assert set(counts) == {"active", "retired"}
    assert report["scripts_registry_analysis"]["transitional_scripts_without_sunset"] == []
    assert report["scripts_registry_analysis"]["retired_public_cli_modules"] == []
    assert report["scripts_registry_analysis"]["default_validate_retired_script_references"] == []
    assert report["scripts_registry_analysis"]["retired_scripts_in_default_validate_or_public_cli"] == 0


def test_duplicate_capability_groups_are_governed_after_finalization() -> None:
    reviews = {
        item["group_id"]: item
        for item in finalization.build_finalization_report()["scripts_registry_analysis"][
            "duplicate_capability_review"
        ]
    }

    assert reviews["schema_migration_seed_scaffolds"]["module_count"] >= 1
    assert "retired-in-place audit records after #346" in reviews["schema_migration_seed_scaffolds"][
        "retain_or_consolidation_reason"
    ]
    assert all(
        review["retain_or_consolidation_reason"] or review.get("governance_plan")
        for review in reviews.values()
        if review["module_count"] > 1
    )


def test_report_only_test_consolidation_is_recorded() -> None:
    report = finalization.build_finalization_report()

    consolidation = {item["test_path"]: item for item in report["report_only_test_consolidation"]}
    assert "tests/test_g10_script_asset_risk_governance.py" in consolidation
    assert "transitional-count expectations" in consolidation[
        "tests/test_g10_script_asset_risk_governance.py"
    ]["issue_346_action"]
    assert consolidation["tests/test_post_g10_script_lifecycle_finalization.py"]["superseded_by"] is None


def test_default_finalization_report_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {
        finalization.inventory_plan.SCRIPT_REGISTRY_PATH.resolve(),
        *(path.resolve() for path in finalization.governance.DEFAULT_VALIDATE_ENTRYPOINTS),
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
        raise AssertionError("network access is forbidden in #346 script finalization tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = finalization.build_finalization_report()
    markdown = finalization.render_finalization_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert "Post-G10 Script Lifecycle Finalization" in markdown
    assert "platform_seed_artifact_validation_matrix" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert finalization.main(["--finalization-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["current_state"]["post_g10_s1_script_lifecycle_finalization_ready"] is True

    assert finalization.main(["--finalization-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Lifecycle Finalization Manifest" in markdown
    assert "Report-Only Test Consolidation" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "post_g10_script_lifecycle_finalization.py").read_text(
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
