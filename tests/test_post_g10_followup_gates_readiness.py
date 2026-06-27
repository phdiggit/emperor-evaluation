from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import post_g10_followup_gates_readiness as gates  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_gates_report_declares_post_g10_scope_and_boundaries() -> None:
    report = gates.build_gates_report()

    assert report["mode"] == "gates-report"
    assert report["package_version"] == "post-g10-followup-gates-readiness-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["handoff_issue"] == 335
    assert report["handoff_pr"] == 340
    assert report["handoff_merge_commit"] == gates.HANDOFF_MERGE_COMMIT
    assert report["does_not_read_dotenv"] is True
    assert report["does_not_connect_database"] is True
    assert report["does_not_access_network"] is True
    assert report["does_not_read_batch_payloads"] is True
    assert report["does_not_read_generated_export_contents"] is True
    assert report["does_not_move_delete_or_archive_files"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["does_not_publish_leaderboards"] is True
    assert report["does_not_enter_epic2_or_epic3"] is True


def test_gates_current_state_records_ready_boundary_without_gate_execution() -> None:
    state = gates.build_gates_report()["current_state"]

    assert state["current_phase"] == "post_g10_ready_for_followup_gates_ready"
    assert state["post_g10_ready_for_followup_gates_ready"] is True
    assert state["post_g10_followup_gates_package"] == "post-g10-followup-gates-readiness-v1"
    assert state["post_g10_handoff_pr"] == 340
    assert state["post_g10_handoff_merge_commit"] == gates.HANDOFF_MERGE_COMMIT
    assert state["post_g10_followup_gate_count"] == 8
    assert state["post_g10_followup_gates_requiring_separate_review"] == 8
    assert state["post_g10_next_action"] == "select_one_followup_gate_and_open_separate_ready_review"
    assert state["epic5_per_subitem_g9_publication_gate_approved"] is False
    assert state["epic5_cross_subitem_leaderboard_publication_gate_approved"] is False
    assert state["epic5_stage_or_final_total_table_publication_gate_approved"] is False
    assert state["g10_destructive_cleanup_gate_approved"] is False
    assert state["source_document_passage_merge_policy_gate_approved"] is False
    assert state["evidence_cluster_anchor_relationship_followup_gates_approved"] is False
    assert state["epic2_separate_ready_review_approved"] is False
    assert state["epic3_separate_ready_review_approved"] is False
    assert state["g10_destructive_cleanup_started"] is False
    assert state["stage_or_final_total_table_released"] is False
    assert state["cross_subitem_leaderboard_released"] is False
    assert state["new_subitem_formal_scores_released"] is False
    assert state["new_subitem_formal_rankings_released"] is False
    assert state["epic_2_entered"] is False
    assert state["epic_3_entered"] is False


def test_followup_gates_all_require_separate_ready_review() -> None:
    report = gates.build_gates_report()

    assert [gate["gate_id"] for gate in report["followup_gates"]] == [
        "epic5_per_subitem_g9_publication_gate",
        "epic5_cross_subitem_leaderboard_publication_gate",
        "epic5_stage_or_final_total_table_publication_gate",
        "g10_destructive_cleanup_gate",
        "source_document_passage_merge_policy_gate",
        "evidence_cluster_anchor_relationship_followup_gates",
        "epic2_separate_ready_review",
        "epic3_separate_ready_review",
    ]
    assert all(gate["current_status"] == "requires_separate_ready_review" for gate in report["followup_gates"])
    assert all(gate["separate_ready_review_required"] is True for gate in report["followup_gates"])
    assert all(gate["approved_in_this_package"] is False for gate in report["followup_gates"])
    assert all(gate["executed_in_this_package"] is False for gate in report["followup_gates"])
    assert report["next_required_work"] == "select_one_followup_gate_and_open_separate_ready_review"


def test_handoff_summary_and_changed_paths_are_manifested() -> None:
    report = gates.build_gates_report()

    summary = report["handoff_summary"]
    assert summary["g10_4_completion_verification_handoff_ready"] is True
    assert summary["next_required_work"] == "post_g10_ready_for_followup_gates"
    assert summary["registry_dangling_references"] == 0
    assert summary["g10_report_complete"] is True
    assert summary["g10_destructive_cleanup_started"] is False
    assert set(report["changed_paths_manifest"]) == set(gates.PACKAGE_CHANGED_PATHS)
    assert "scripts/platform/post_g10_followup_gates_readiness.py" in report["changed_paths_manifest"]


def test_default_gates_report_is_side_effect_free(monkeypatch) -> None:
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
        raise AssertionError("network access is forbidden in post-G10 gates tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = gates.build_gates_report()
    markdown = gates.render_gates_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert "Post-G10 Follow-Up Gates Readiness" in markdown
    assert "requires_separate_ready_review" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert gates.main(["--gates-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["current_state"]["post_g10_ready_for_followup_gates_ready"] is True

    assert gates.main(["--gates-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Follow-Up Gates" in markdown
    assert "g10_destructive_cleanup_gate" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "post_g10_followup_gates_readiness.py").read_text(
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
