from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_cleanup_inventory_plan as g10_plan  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_inventory_report_declares_g10_0_scope_and_boundaries() -> None:
    report = g10_plan.build_inventory_report()

    assert report["mode"] == "inventory-report"
    assert report["package_version"] == "g10-cleanup-inventory-plan-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["plan_issue"] == 331
    assert report["last_merged_pr"] == 330
    assert report["last_merged_pr_merge_commit"] == g10_plan.LAST_MERGED_PR_MERGE_COMMIT
    assert report["does_not_read_dotenv"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_read_batch_payloads"] is True
    assert report["does_not_read_generated_exports"] is True
    assert report["does_not_move_delete_or_archive_files"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["current_state"]["current_phase"] == "g10_cleanup_inventory_plan_ready"
    assert report["current_state"]["g10_cleanup_inventory_plan_ready"] is True
    assert report["current_state"]["g10_execution_started"] is False
    assert report["current_state"]["g10_destructive_cleanup_started"] is False


def test_cleanup_candidates_cover_required_asset_types_and_lifecycle_mapping() -> None:
    report = g10_plan.build_inventory_report()
    candidates = report["cleanup_candidates"]
    asset_types = {candidate["asset_type"] for candidate in candidates}

    assert set(g10_plan.REQUIRED_ASSET_TYPES) <= asset_types
    assert report["current_state"]["cleanup_candidate_count"] == len(candidates)
    assert report["current_state"]["candidate_asset_types"] == sorted(asset_types)
    assert sum(report["current_state"]["lifecycle_classification_counts"].values()) == len(candidates)

    for candidate in candidates:
        classification = candidate["lifecycle_classification"]
        assert classification in g10_plan.LIFECYCLE_CLASSIFICATIONS
        assert candidate["paths"], candidate["asset_id"]
        assert candidate["execution_issue"] in {332, 333, 334, 335}
        if classification in g10_plan.DESTRUCTIVE_CLASSIFICATIONS:
            mapping = candidate["replacement_mapping"]
            assert mapping["replacement_path"] or mapping["archive_path"] or mapping["git_history_only"]
            assert mapping["registry_record"]
            assert candidate["restore_plan"], candidate["asset_id"]


def test_execution_split_locks_g10_issue_order() -> None:
    report = g10_plan.build_inventory_report()
    split = report["execution_split"]

    assert [item["issue"] for item in split] == [331, 332, 333, 334, 335]
    assert split[0]["must_land_before"] == [332, 333, 334, 335]
    assert "move_files" in split[0]["forbidden_actions"]
    assert "delete_files" in split[0]["forbidden_actions"]
    assert "archive_files" in split[0]["forbidden_actions"]
    assert split[-1]["depends_on"] == [332, 333, 334]


def test_registry_snapshot_uses_registry_counts_without_reading_payloads() -> None:
    report = g10_plan.build_inventory_report()
    snapshot = report["registry_snapshot"]

    assert snapshot["scripts_registry_path"] == "docs/文档与脚本登记/scripts_registry.json"
    assert snapshot["docs_registry_path"] == "docs/文档与脚本登记/docs_registry.json"
    assert snapshot["platform_module_count"] >= 80
    assert snapshot["scripts_module_count"] >= 40
    assert snapshot["retired_legacy_wrapper_count"] >= 20
    assert snapshot["docs_document_count"] >= 90
    assert snapshot["archived_document_path_count"] >= 50
    assert snapshot["retired_generated_document_path_count"] >= 1
    assert snapshot["retired_mixed_document_path_count"] >= 1


def test_default_reports_do_not_read_secret_data_exports_or_archive_payloads(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if (
            self.name == ".env"
            or "exports" in parts
            or "batches" in parts
            or ("archive" in parts and "data" in parts)
            or self.name in {"evidence_cards.jsonl", "evidence_clusters.jsonl"}
        ):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G10 inventory tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g10_plan.build_inventory_report()
    markdown = g10_plan.render_inventory_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert "G10 Cleanup Inventory" in markdown
    assert "classification=`delete_candidate`" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g10_plan.main(["--inventory-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "inventory-report"
    assert report["current_state"]["g10_cleanup_inventory_plan_ready"] is True

    assert g10_plan.main(["--inventory-md"]) == 0
    markdown = capsys.readouterr().out
    assert "G10 Cleanup Inventory, Mapping, And Restore Plan" in markdown
    assert "issue311_transition_audit_packages" in markdown
    assert "file_delete" in markdown


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
