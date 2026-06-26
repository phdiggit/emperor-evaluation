from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g6_formal_evidence_boundary_package as g6  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_records_g6_required_without_releasing_evidence() -> None:
    report = g6.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "g6-formal-evidence-boundary-package-v1"
    assert report["gate"] == "G6_FORMAL_EVIDENCE_RELEASE"
    assert report["gate_status"] == "required_not_approved"
    assert report["g1_to_g5_completion"]["g5_result_pr"] == 302
    assert report["current_state"] == {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_credentials_enabled": True,
        "rabbitmq_live": True,
        "network_ingestion_live": True,
        "production_runtime_live": True,
        "g6_approved": False,
        "formal_evidence_released": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
        "epic_2_entered": False,
    }
    assert report["next_required_user_gate"] == "G6"


def test_g6_boundaries_separate_formal_evidence_from_later_outputs() -> None:
    report = g6.build_contract_report()

    allowed = set(report["g6_would_allow_after_explicit_approval"])
    denied = set(report["g6_does_not_allow"])

    assert "formal_evidence_release_execution_package" in allowed
    assert "source_backed_candidate_evidence_review" in allowed
    assert "candidate_to_formal_evidence_audit_report" in allowed
    assert "formal_scoring_or_score_release" in denied
    assert "formal_ranking_or_leaderboard_release" in denied
    assert "source_document_passage_merge_policy_write" in denied
    assert "evidence_cluster_anchor_relationship_business_table_write_without_followup_gate" in denied
    assert "epic_2_scope_entry_without_separate_ready_review" in denied


def test_followup_gate_boundaries_are_explicit() -> None:
    boundaries = g6.build_contract_report()["followup_gate_boundaries"]

    assert boundaries["source_documents_passages"]["requires"] == "source_document_passage_merge_policy"
    assert (
        boundaries["evidence_clusters_anchors_relationships"]["requires"]
        == "resolver_outputs_manual_review_and_relationship_gate"
    )
    assert boundaries["scoring_rules"]["status"] == "blocked_until_g7"
    assert boundaries["scoring_algorithm"]["status"] == "blocked_until_g8"
    assert boundaries["formal_score_or_ranking_publication"]["status"] == "blocked_until_g9"
    assert boundaries["destructive_cleanup"]["status"] == "blocked_until_g10"


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
        raise AssertionError("network access is forbidden in G6 boundary tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g6.build_contract_report()
    markdown = g6.render_boundary_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "G6 Formal Evidence Boundary Package" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g6.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert g6.main(["--boundary-md"]) == 0
    markdown = capsys.readouterr().out
    assert "G6 Formal Evidence Boundary Package" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "g6_formal_evidence_boundary_package.py").read_text(encoding="utf-8")

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
