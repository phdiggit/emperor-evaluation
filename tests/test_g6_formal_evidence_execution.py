from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g6_formal_evidence_execution as g6  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
    ROOT / ".env",
]


def test_contract_report_records_g6_approval_without_execution() -> None:
    report = g6.build_contract_report(source_root=ROOT)

    assert report["mode"] == "contract-report"
    assert report["execution_version"] == "g6-formal-evidence-execution-v1"
    assert report["gate_status"] == "G6_APPROVED"
    assert report["approval_token_required"] is True
    assert report["approval_token_value"] == g6.APPROVAL_TOKEN
    assert report["boundary_source_pr"] == 303
    assert report["boundary_head_sha"] == g6.G6_BOUNDARY_HEAD_SHA
    assert report["boundary_merge_commit"] == g6.G6_BOUNDARY_MERGE_COMMIT
    assert report["formal_evidence_marker"]["target_table"] == "imports"
    assert report["formal_evidence_marker"]["code"] == g6.G6_FORMAL_EVIDENCE_IMPORT_CODE
    assert report["execution_completed_by_this_report"] is False
    assert report["post_apply_observation_completed_by_this_report"] is False
    assert report["next_user_gate"] == "G7_REQUIRED_BEFORE_SCORING_RULE_CHANGE"


def test_execution_plan_is_stable_and_blocks_later_outputs() -> None:
    plan = g6.render_execution_plan_json(source_root=ROOT)

    assert plan["execution_plan_sha256"] == g6.stable_json_sha256(plan)
    assert plan["runtime_state_after_success"] == {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_credentials_enabled": True,
        "rabbitmq_live": True,
        "network_ingestion_live": True,
        "production_runtime_live": True,
        "g6_approved": True,
        "formal_evidence_released": True,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
        "epic_2_entered": False,
    }
    assert plan["execute_write"]["target_tables"] == ["imports"]
    assert plan["execute_write"]["business_target_tables_written"] == []
    assert plan["preconditions"]["formal_evidence_candidate_workset_declared"]["business_table_writes"] == []
    assert plan["followup_gate_boundaries"]["scoring_rules"] == "blocked_until_g7"
    assert plan["followup_gate_boundaries"]["formal_score_or_ranking_publication"] == "blocked_until_g9"


def test_default_reports_do_not_read_env_data_or_touch_network(monkeypatch) -> None:
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
        raise AssertionError("network access is forbidden in G6 default report tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g6.build_contract_report(source_root=ROOT)
    plan = g6.render_execution_plan_json(source_root=ROOT)
    checklist = g6.render_operator_checklist_md(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert plan["formal_evidence_marker"]["code"] == g6.G6_FORMAL_EVIDENCE_IMPORT_CODE
    assert "G6 Formal Evidence Execution Operator Checklist" in checklist


def test_execute_blocks_before_operator_config_when_gate_invalid(monkeypatch) -> None:
    def fail_read_operator_config() -> g6.OperatorConfig:
        raise AssertionError("gate failures must not read operator config")

    monkeypatch.setattr(g6, "read_operator_config", fail_read_operator_config)
    plan = g6.render_execution_plan_json(source_root=ROOT)

    report = g6.execute_formal_evidence_release(approval_token=None, expected_plan_sha256=plan["execution_plan_sha256"])
    assert report["execution_status"] == "blocked"
    assert report["operator_config_read"] is False
    assert "blocked_missing_or_invalid_g6_approval_token" in report["blocking_failures"]

    report = g6.execute_formal_evidence_release(approval_token=g6.APPROVAL_TOKEN, expected_plan_sha256=None)
    assert "blocked_missing_expected_plan_sha256" in report["blocking_failures"]

    report = g6.execute_formal_evidence_release(approval_token=g6.APPROVAL_TOKEN, expected_plan_sha256="0" * 64)
    assert "blocked_execution_plan_sha256_mismatch" in report["blocking_failures"]


def test_execute_blocks_missing_dsn_without_connecting(monkeypatch) -> None:
    plan = g6.render_execution_plan_json(source_root=ROOT)
    monkeypatch.setattr(g6, "read_operator_config", lambda: g6.OperatorConfig({}))

    def fail_connect(_dsn: str) -> object:
        raise AssertionError("missing dsn must block before database connection")

    monkeypatch.setattr(g6, "connect_to_database", fail_connect)

    report = g6.execute_formal_evidence_release(
        approval_token=g6.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )

    assert report["execution_status"] == "blocked"
    assert report["failure_stage"] == "operator_configuration"
    assert "blocked_missing_dsn" in report["blocking_failures"]
    assert report["formal_evidence_released"] is False
    assert report["formal_evidence_marker_written"] is False


def test_execute_blocks_if_g5_marker_missing(monkeypatch) -> None:
    plan = g6.render_execution_plan_json(source_root=ROOT)
    conn = FakeConnection(include_g5_marker=False, g6_plan=plan)
    monkeypatch.setattr(g6, "read_operator_config", lambda: g6.OperatorConfig({g6.DSN_ENV_NAME: "postgresql://example/db"}))
    monkeypatch.setattr(g6, "connect_to_database", lambda _dsn: conn)

    report = g6.execute_formal_evidence_release(
        approval_token=g6.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )

    assert report["execution_status"] == "blocked"
    assert report["failure_stage"] == "g5_observation"
    assert "blocked_missing_or_invalid_g5_runtime_marker" in report["blocking_failures"]
    assert report["formal_evidence_marker_written"] is False
    assert not any("INSERT INTO imports" in query for query, _params in conn.executed)


def test_redact_secret_removes_complete_password_values() -> None:
    raw = (
        "uri=postgresql://user:uriSecret@example.local/prod?password=querySecret&sslmode=require "
        "keyword password=spaceSecret next password=semiSecret;application_name=g6 "
        "tail password=tailSecret"
    )

    redacted = g6.redact_secret(raw)

    for secret in ("uriSecret", "querySecret", "spaceSecret", "semiSecret", "tailSecret"):
        assert secret not in redacted
    assert "postgresql://<redacted-credentials>@example.local/prod" in redacted
    assert "password=<redacted>&sslmode=require" in redacted
    assert "password=<redacted> next" in redacted
    assert "password=<redacted>;application_name=g6" in redacted
    assert redacted.endswith("password=<redacted>")


def test_execute_database_error_report_redacts_raw_secret_values(monkeypatch) -> None:
    plan = g6.render_execution_plan_json(source_root=ROOT)
    secret_dsn = "postgresql://user:uriSecret@example.local/prod?password=querySecret&sslmode=require"
    monkeypatch.setattr(g6, "read_operator_config", lambda: g6.OperatorConfig({g6.DSN_ENV_NAME: secret_dsn}))

    def fail_connect(_dsn: str) -> object:
        raise RuntimeError(f"connect failed for {secret_dsn}; fallback password=semiSecret; done")

    monkeypatch.setattr(g6, "connect_to_database", fail_connect)

    report = g6.execute_formal_evidence_release(
        approval_token=g6.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )
    rendered = g6.report_as_json(report)

    assert report["execution_status"] == "failed"
    assert report["failure_stage"] == "database"
    assert "database_error" in report["blocking_failures"]
    for secret in ("uriSecret", "querySecret", "semiSecret"):
        assert secret not in rendered
    assert "password=<redacted>Secret" not in rendered
    assert secret_dsn not in rendered


def test_execute_writes_g6_marker_after_g5_readback_passes(monkeypatch) -> None:
    plan = g6.render_execution_plan_json(source_root=ROOT)
    conn = FakeConnection(include_g5_marker=True, g6_plan=plan)
    secret_dsn = "postgresql://user:password@example.local/prod?password=secret"
    monkeypatch.setattr(g6, "read_operator_config", lambda: g6.OperatorConfig({g6.DSN_ENV_NAME: secret_dsn}))
    monkeypatch.setattr(g6, "connect_to_database", lambda _dsn: conn)

    report = g6.execute_formal_evidence_release(
        approval_token=g6.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )
    rendered = g6.report_as_json(report)

    assert report["execution_status"] == "succeeded"
    assert report["formal_evidence_marker_written"] is True
    assert report["post_apply_observation_completed"] is True
    assert report["post_apply_observation"]["observation_passed"] is True
    assert report["g6_formal_evidence_executed"] is True
    assert report["formal_evidence_released"] is True
    assert report["formal_scoring_released"] is False
    assert report["formal_ranking_released"] is False
    assert report["epic_2_entered"] is False
    assert conn.committed is True
    assert conn.imports[g6.G6_FORMAL_EVIDENCE_IMPORT_CODE]["input_hash"] == plan["execution_plan_sha256"]
    assert secret_dsn not in rendered
    assert "password=secret" not in rendered


def test_observe_is_readback_only(monkeypatch) -> None:
    plan = g6.render_execution_plan_json(source_root=ROOT)
    conn = FakeConnection(include_g5_marker=True, g6_plan=plan)
    conn.imports[g6.G6_FORMAL_EVIDENCE_IMPORT_CODE] = _g6_marker_row(plan)
    monkeypatch.setattr(g6, "read_operator_config", lambda: g6.OperatorConfig({g6.DSN_ENV_NAME: "postgresql://example/db"}))
    monkeypatch.setattr(g6, "connect_to_database", lambda _dsn: conn)

    report = g6.observe_formal_evidence_release(
        approval_token=g6.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )

    assert report["mode"] == "observe-report"
    assert report["execution_status"] == "succeeded"
    assert report["g6_formal_evidence_executed"] is False
    assert report["formal_evidence_released"] is True
    assert not any("INSERT INTO imports" in query for query, _params in conn.executed)


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g6.main(["--contract-report", "--source-root", str(ROOT)]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert g6.main(["--execution-plan-json", "--source-root", str(ROOT)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "execution-plan-json"

    assert g6.main(["--operator-checklist-md", "--source-root", str(ROOT)]) == 0
    checklist = capsys.readouterr().out
    assert "G6 Formal Evidence Execution Operator Checklist" in checklist


def test_source_keeps_database_adapter_gated() -> None:
    source = (ROOT / "scripts" / "platform" / "g6_formal_evidence_execution.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "import psycopg" in source
    assert "import pika" not in source
    assert "urllib.request" not in source


class FakeConnection:
    def __init__(self, *, include_g5_marker: bool, g6_plan: dict[str, Any]) -> None:
        self.imports: dict[str, dict[str, Any]] = {}
        if include_g5_marker:
            self.imports[g6.G5_RUNTIME_IMPORT_CODE] = _g5_marker_row()
        self.g6_plan = g6_plan
        self.executed: list[tuple[str, object]] = []
        self.committed = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> "FakeCursor":
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed = True


class FakeCursor:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn
        self._one: tuple[Any, ...] | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: object = None) -> None:
        self.conn.executed.append((query, params))
        if "INSERT INTO imports" in query:
            assert isinstance(params, tuple)
            code, source_kind, source_ref, status, tool_version, input_hash, row_count, meta = params
            self.conn.imports[str(code)] = {
                "code": str(code),
                "source_kind": str(source_kind),
                "source_ref": str(source_ref),
                "status": str(status),
                "tool_version": str(tool_version),
                "input_hash": str(input_hash),
                "row_count": int(row_count),
                "meta": json.loads(str(meta)),
            }
            self._one = (str(code),)
            return
        if "FROM imports" in query:
            assert isinstance(params, tuple)
            row = self.conn.imports.get(str(params[0]))
            self._one = _row_tuple(row) if row else None
            return
        raise AssertionError(f"unexpected query: {query}")

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._one


def _g5_marker_row() -> dict[str, Any]:
    return {
        "code": g6.G5_RUNTIME_IMPORT_CODE,
        "source_kind": "runtime_smoke",
        "source_ref": "issue-292-g5",
        "status": "succeeded",
        "tool_version": "g5-runtime-execution-v1",
        "input_hash": g6.G5_EXECUTION_PLAN_SHA256,
        "row_count": 1,
        "meta": {
            "production_credentials_enabled": True,
            "rabbitmq_live": True,
            "network_ingestion_live": True,
            "production_runtime_live": True,
            "formal_evidence_released": False,
            "formal_scoring_released": False,
            "formal_ranking_released": False,
            "epic_2_entered": False,
        },
    }


def _g6_marker_row(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": g6.G6_FORMAL_EVIDENCE_IMPORT_CODE,
        "source_kind": g6.G6_SOURCE_KIND,
        "source_ref": g6.G6_SOURCE_REF,
        "status": "succeeded",
        "tool_version": g6.EXECUTION_VERSION,
        "input_hash": plan["execution_plan_sha256"],
        "row_count": 1,
        "meta": {
            **g6.expected_formal_evidence_state(),
            "execution_plan_sha256": plan["execution_plan_sha256"],
        },
    }


def _row_tuple(row: dict[str, Any] | None) -> tuple[Any, ...] | None:
    if row is None:
        return None
    return (
        row["code"],
        row["source_kind"],
        row["source_ref"],
        row["status"],
        row["tool_version"],
        row["input_hash"],
        row["row_count"],
        row["meta"],
    )


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
