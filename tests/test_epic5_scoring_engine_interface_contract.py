from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import epic5_scoring_engine_interface_contract as interface  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_declares_interface_package_after_scope_merge() -> None:
    report = interface.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "epic5-scoring-engine-interface-contract-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["scope_pr"] == 313
    assert report["scope_merge_commit"] == interface.SCOPE_MERGE_COMMIT
    assert report["does_not_publish_scores"] is True
    assert report["current_state"]["current_phase"] == "epic5_minimum_interface_contract_package_ready"
    assert report["current_state"]["epic5_minimum_interface_contract_ready"] is True
    assert report["current_state"]["new_subitem_formal_scores_released"] is False
    assert report["current_state"]["stage_or_final_total_table_released"] is False
    assert report["current_state"]["cross_subitem_leaderboard_released"] is False


def test_contract_objects_and_invariants_cover_minimum_interface() -> None:
    report = interface.build_contract_report()
    objects = {item["name"]: item for item in report["contract_objects"]}
    invariants = set(report["validation_invariants"])

    assert {"ScoreRange", "SubitemProfile", "EvidenceProfile", "NoOverridePolicy"} <= set(objects)
    assert {"FormalGradeResult", "ScorePublicationResult"} <= set(objects)
    assert "score_cap" in objects["SubitemProfile"]["fields"]
    assert "candidate_value" in objects["FormalGradeResult"]["fields"]
    assert "publication_gate" in objects["ScorePublicationResult"]["fields"]
    assert "publication_requires_g9" in invariants
    assert "person_specific_override_disallowed" in invariants
    assert "subitem_g9_does_not_release_stage_or_final_total_table" in invariants
    assert "subitem_g9_does_not_release_cross_subitem_leaderboard" in invariants


def test_report_templates_keep_impact_and_publication_contracts_separate() -> None:
    report = interface.build_contract_report()

    assert "formal_grade_result_without_publication_value_when_g8_only" in report["report_templates"]["impact_report"]
    assert "score_publication_result" in report["report_templates"]["publication_report"]
    assert "new_subitem_formal_scores_without_per_subitem_g9" in report["blocked_outputs"]
    assert "stage_total_table" in report["blocked_outputs"]
    assert "cross_subitem_leaderboard" in report["blocked_outputs"]
    assert report["next_required_work"] == "epic5_pilot_subitem_profile_contract_package"


def test_default_reports_do_not_read_secret_data_or_runtime_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if (
            self.name == ".env"
            or "batches" in parts
            or ("archive" in parts and "data" in parts)
            or self.name in {"evidence_cards.jsonl", "evidence_clusters.jsonl"}
        ):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in Epic5 interface tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = interface.build_contract_report()
    markdown = interface.render_interface_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "Epic5 Scoring Engine Interface Contract" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert interface.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert interface.main(["--interface-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Epic5 Scoring Engine Interface Contract" in markdown
    assert "ScorePublicationResult" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "epic5_scoring_engine_interface_contract.py").read_text(
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
