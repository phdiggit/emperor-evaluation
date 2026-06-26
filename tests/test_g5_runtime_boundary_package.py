from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g5_runtime_boundary_package as g5  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_records_g5_required_without_executing_runtime() -> None:
    report = g5.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "g5-runtime-boundary-package-v1"
    assert report["gate"] == "G5_RUNTIME_CREDENTIALS_NETWORK_INGESTION"
    assert report["gate_status"] == "required_not_approved"
    assert report["g1_to_g4_completion"]["g4_result_pr"] == 299
    assert report["current_state"] == {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_runtime_live": False,
        "rabbitmq_live": False,
        "network_ingestion_live": False,
        "production_credentials_enabled": False,
        "formal_evidence_released": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
        "epic_2_entered": False,
    }
    assert report["next_required_user_gate"] == "G5"


def test_g5_boundaries_separate_runtime_from_formal_outputs() -> None:
    report = g5.build_contract_report()

    allowed = set(report["g5_would_allow_after_explicit_approval"])
    denied = set(report["g5_does_not_allow"])

    assert "operator_scoped_production_credentials_read" in allowed
    assert "approved_postgresql_runtime_connection" in allowed
    assert "rabbitmq_queue_exchange_binding_smoke" in allowed
    assert "network_ingestion_pilot_against_approved_source_allowlist" in allowed
    assert "formal_evidence_promotion" in denied
    assert "formal_scoring_or_ranking_release" in denied
    assert "source_document_passage_merge_policy_write" in denied
    assert "evidence_cluster_anchor_relationship_business_table_write" in denied
    assert "epic_2_scope_entry_without_separate_ready_review" in denied


def test_followup_gate_boundaries_are_explicit() -> None:
    boundaries = g5.build_contract_report()["followup_gate_boundaries"]

    assert boundaries["source_documents_passages"]["requires"] == "source_document_passage_merge_policy"
    assert (
        boundaries["evidence_clusters_anchors_relationships"]["requires"]
        == "resolver_outputs_manual_review_and_relationship_gate"
    )
    assert boundaries["formal_evidence"]["status"] == "blocked_until_g6"
    assert boundaries["scoring_rules"]["status"] == "blocked_until_g7"
    assert boundaries["scoring_algorithm"]["status"] == "blocked_until_g8"
    assert boundaries["formal_publication"]["status"] == "blocked_until_g9"


def test_default_reports_do_not_read_secret_or_runtime_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if self.name == ".env" or "batches" in parts or ("archive" in parts and "data" in parts):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G5 boundary tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g5.build_contract_report()
    markdown = g5.render_boundary_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert "G5 Runtime Boundary Package" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g5.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert g5.main(["--boundary-md"]) == 0
    markdown = capsys.readouterr().out
    assert "G5 Runtime Boundary Package" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "g5_runtime_boundary_package.py").read_text(encoding="utf-8")

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
