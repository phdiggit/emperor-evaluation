from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import i5b_rule_display_dictionary_governance_gate as governance  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_governance_report_declares_issue311_dictionary_gate() -> None:
    report = governance.build_governance_report()

    assert report["mode"] == "governance-report"
    assert report["package_version"] == "i5b-rule-display-dictionary-governance-gate-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["tech_debt_issue"] == 311
    assert report["cleanup_pr"] == 328
    assert report["cleanup_merge_commit"] == governance.CLEANUP_MERGE_COMMIT
    assert report["governance_blockers"] == []
    assert report["does_not_import_runtime_adapter"] is True
    assert report["does_not_render_exports"] is True
    assert report["does_not_write_postgres_dictionary_tables"] is True
    assert report["does_not_write_canonical_dictionary"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True


def test_governance_current_state_keeps_future_write_gates_required() -> None:
    state = governance.build_governance_report()["current_state"]

    assert state["current_phase"] == "issue311_rule_display_dictionary_governance_gate_ready"
    assert state["issue311_rule_display_dictionary_governance_gate_ready"] is True
    assert state["dictionary_governance_policy_recorded"] is True
    assert state["immutable_snapshot_runtime_mode_retained"] is True
    assert state["future_postgres_dictionary_schema_gate_required"] is True
    assert state["future_canonical_dictionary_write_gate_required"] is True
    assert state["snapshot_validation_passed"] is True
    assert state["python_constant_cleanup_passed"] is True
    assert state["postgres_dictionary_tables_created"] is False
    assert state["canonical_dictionary_write_performed"] is False
    assert state["ordinary_exports_require_live_dsn"] is False
    assert state["g10_destructive_cleanup_entered"] is False


def test_governance_decisions_record_snapshot_and_future_schema_policy() -> None:
    report = governance.build_governance_report()
    decisions = {item["decision"]: item for item in report["governance_decisions"]}

    assert decisions["repo_immutable_snapshot_is_current_offline_release_artifact"]["status"] == (
        "accepted_for_pre_g10_runtime"
    )
    assert decisions["postgres_dictionary_tables_require_separate_schema_gate"]["status"] == "deferred"
    assert decisions["canonical_dictionary_write_requires_separate_write_gate"]["status"] == "deferred"
    assert "run_snapshot_validator_and_readthrough_parity_tests" in report["change_control_requirements"]
    assert "separate PR for PostgreSQL dictionary table DDL" in report["future_schema_gate_requirements"]
    assert "postgres_dictionary_table_creation" in report["blocked_outputs"]
    assert "canonical_dictionary_write" in report["blocked_outputs"]
    assert "g10_destructive_cleanup" in report["blocked_outputs"]
    assert report["next_required_work"] == "epic5_pre_g10_contract_schema_report_test_plumbing"


def test_default_governance_report_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {
        governance.ROOT / source_path
        for source_path in governance.contract.SOURCE_MODULES
    } | {governance.snapshot_loader.DEFAULT_SNAPSHOT_PATH}
    allowed_resolved = {path.resolve() for path in allowed_reads}

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        parts = tuple(path.parts)
        if path not in allowed_resolved:
            if (
                path.name == ".env"
                or "batches" in parts
                or ("archive" in parts and "data" in parts)
                or path.name == "evidence_cards.jsonl"
                or "exports" in parts
            ):
                raise AssertionError(f"forbidden path read: {path}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in governance tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = governance.build_governance_report()
    markdown = governance.render_governance_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "I5B Rule And Display Dictionary Governance Gate" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert governance.main(["--governance-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["governance_blockers"] == []

    assert governance.main(["--governance-md"]) == 0
    markdown = capsys.readouterr().out
    assert "postgres_dictionary_tables_require_separate_schema_gate" in markdown
    assert "canonical_dictionary_write" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "i5b_rule_display_dictionary_governance_gate.py").read_text(
        encoding="utf-8"
    )

    assert "import psycopg" not in source
    assert "import pika" not in source
    assert "aio_pika" not in source
    assert "import requests" not in source
    assert "subprocess.run" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "import scripts.export.dimension_adapters.i5b_people_delegation.adapter" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
