from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g5_runtime_execution as g5  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
    ROOT / ".env",
    ROOT / "docs" / "鐨囧笣缁煎悎璇勪环浣撶郴璇勫垎鏍囧噯.md",
]


def test_contract_report_records_g5_approval_without_executing_runtime() -> None:
    report = g5.build_contract_report(source_root=ROOT)

    assert report["mode"] == "contract-report"
    assert report["execution_version"] == "g5-runtime-execution-v1"
    assert report["gate_status"] == "G5_APPROVED"
    assert report["approval_token_required"] is True
    assert report["approval_token_value"] == g5.APPROVAL_TOKEN
    assert report["boundary_source_pr"] == 300
    assert report["boundary_head_sha"] == g5.G5_BOUNDARY_HEAD_SHA
    assert report["boundary_merge_commit"] == g5.G5_BOUNDARY_MERGE_COMMIT
    assert report["runtime_marker"]["target_table"] == "imports"
    assert report["runtime_marker"]["code"] == g5.G5_RUNTIME_IMPORT_CODE
    assert report["execution_completed_by_this_report"] is False
    assert report["post_apply_observation_completed_by_this_report"] is False
    assert report["next_user_gate"] == "G6_REQUIRED_BEFORE_FORMAL_EVIDENCE_RELEASE"


def test_execution_plan_is_stable_and_keeps_formal_outputs_blocked() -> None:
    plan = g5.render_execution_plan_json(source_root=ROOT)

    assert plan["execution_plan_sha256"] == g5.stable_json_sha256(plan)
    assert plan["runtime_state_after_success"] == {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_credentials_enabled": True,
        "rabbitmq_live": True,
        "network_ingestion_live": True,
        "production_runtime_live": True,
        "formal_evidence_released": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
        "epic_2_entered": False,
    }
    assert plan["execute_write"]["target_tables"] == ["imports"]
    assert plan["execute_write"]["business_target_tables_written"] == []
    assert plan["followup_gate_boundaries"]["formal_evidence"] == "blocked_until_g6"
    assert plan["followup_gate_boundaries"]["epic_2_entry"] == "blocked_until_separate_ready_review"


def test_default_reports_do_not_read_env_or_touch_network(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if self.name == ".env" or "batches" in parts or ("archive" in parts and "data" in parts):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G5 default report tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g5.build_contract_report(source_root=ROOT)
    plan = g5.render_execution_plan_json(source_root=ROOT)
    checklist = g5.render_operator_checklist_md(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert plan["runtime_marker"]["code"] == g5.G5_RUNTIME_IMPORT_CODE
    assert "G5 Runtime Execution Operator Checklist" in checklist


def test_execute_blocks_before_operator_config_when_gate_invalid(monkeypatch) -> None:
    def fail_read_operator_config() -> g5.OperatorConfig:
        raise AssertionError("gate failures must not read operator config")

    monkeypatch.setattr(g5, "read_operator_config", fail_read_operator_config)
    plan = g5.render_execution_plan_json(source_root=ROOT)

    report = g5.execute_runtime(approval_token=None, expected_plan_sha256=plan["execution_plan_sha256"])
    assert report["execution_status"] == "blocked"
    assert report["operator_config_read"] is False
    assert "blocked_missing_or_invalid_g5_approval_token" in report["blocking_failures"]

    report = g5.execute_runtime(approval_token=g5.APPROVAL_TOKEN, expected_plan_sha256=None)
    assert "blocked_missing_expected_plan_sha256" in report["blocking_failures"]

    report = g5.execute_runtime(approval_token=g5.APPROVAL_TOKEN, expected_plan_sha256="0" * 64)
    assert "blocked_execution_plan_sha256_mismatch" in report["blocking_failures"]


def test_execute_blocks_missing_operator_configuration_without_connecting(monkeypatch) -> None:
    plan = g5.render_execution_plan_json(source_root=ROOT)
    monkeypatch.setattr(g5, "read_operator_config", lambda: g5.OperatorConfig({}))

    def fail_connect(_dsn: str) -> object:
        raise AssertionError("missing config must block before database connection")

    monkeypatch.setattr(g5, "connect_to_database", fail_connect)

    report = g5.execute_runtime(
        approval_token=g5.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )

    assert report["execution_status"] == "blocked"
    assert report["failure_stage"] == "operator_configuration"
    assert "blocked_missing_dsn" in report["blocking_failures"]
    assert "blocked_missing_rabbitmq_url" in report["blocking_failures"]
    assert "blocked_missing_g5_network_source_allowlist" in report["blocking_failures"]
    assert report["production_runtime_live"] is False
    assert report["runtime_marker_written"] is False


def test_execute_blocks_if_g4_marker_or_g3_readback_missing(monkeypatch) -> None:
    plan = g5.render_execution_plan_json(source_root=ROOT)
    conn = FakeConnection(include_g3_host=False, include_g4_marker=False, g5_plan=plan)
    monkeypatch.setattr(g5, "read_operator_config", lambda: full_operator_config())
    monkeypatch.setattr(g5, "connect_to_database", lambda _dsn: conn)

    report = g5.execute_runtime(
        approval_token=g5.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )

    assert report["execution_status"] == "blocked"
    assert report["failure_stage"] == "postgres_observation"
    assert "blocked_postgres_runtime_prerequisite_readback" in report["blocking_failures"]
    assert report["runtime_marker_written"] is False
    assert not any("INSERT INTO imports" in query for query, _params in conn.executed)


def test_execute_writes_g5_marker_after_all_smokes_pass(monkeypatch) -> None:
    plan = g5.render_execution_plan_json(source_root=ROOT)
    conn = FakeConnection(include_g3_host=True, include_g4_marker=True, g5_plan=plan)
    secret_dsn = "postgresql://user:password@example.local/prod?password=secret"
    monkeypatch.setattr(g5, "read_operator_config", lambda: full_operator_config(dsn=secret_dsn))
    monkeypatch.setattr(g5, "connect_to_database", lambda _dsn: conn)
    monkeypatch.setattr(g5, "run_rabbitmq_binding_smoke", lambda _config: rabbitmq_success())
    monkeypatch.setattr(g5, "run_network_ingestion_pilot", lambda _config: network_success())

    report = g5.execute_runtime(
        approval_token=g5.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )
    rendered = g5.report_as_json(report)

    assert report["execution_status"] == "succeeded"
    assert report["runtime_marker_written"] is True
    assert report["post_apply_observation_completed"] is True
    assert report["post_apply_observation"]["observation_passed"] is True
    assert report["g5_runtime_executed"] is True
    assert report["production_credentials_enabled"] is True
    assert report["rabbitmq_live"] is True
    assert report["network_ingestion_live"] is True
    assert report["production_runtime_live"] is True
    assert report["formal_evidence_released"] is False
    assert report["formal_scoring_released"] is False
    assert report["formal_ranking_released"] is False
    assert report["epic_2_entered"] is False
    assert conn.committed is True
    assert conn.imports[g5.G5_RUNTIME_IMPORT_CODE]["input_hash"] == plan["execution_plan_sha256"]
    assert secret_dsn not in rendered
    assert "password=secret" not in rendered


def test_observe_is_readback_only(monkeypatch) -> None:
    plan = g5.render_execution_plan_json(source_root=ROOT)
    conn = FakeConnection(include_g3_host=True, include_g4_marker=True, g5_plan=plan)
    conn.imports[g5.G5_RUNTIME_IMPORT_CODE] = _g5_marker_row(plan)
    monkeypatch.setattr(g5, "read_operator_config", lambda: full_operator_config())
    monkeypatch.setattr(g5, "connect_to_database", lambda _dsn: conn)

    report = g5.observe_runtime(
        approval_token=g5.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )

    assert report["mode"] == "observe-report"
    assert report["execution_status"] == "succeeded"
    assert report["g5_runtime_executed"] is False
    assert report["production_runtime_live"] is True
    assert not any("INSERT INTO imports" in query for query, _params in conn.executed)


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g5.main(["--contract-report", "--source-root", str(ROOT)]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert g5.main(["--execution-plan-json", "--source-root", str(ROOT)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "execution-plan-json"

    assert g5.main(["--operator-checklist-md", "--source-root", str(ROOT)]) == 0
    checklist = capsys.readouterr().out
    assert "G5 Runtime Execution Operator Checklist" in checklist


def test_source_keeps_runtime_adapters_gated() -> None:
    source = (ROOT / "scripts" / "platform" / "g5_runtime_execution.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "import psycopg" in source
    assert "import pika" in source
    assert "urllib.request.urlopen" in source


class FakeConnection:
    def __init__(self, *, include_g3_host: bool, include_g4_marker: bool, g5_plan: dict[str, Any]) -> None:
        self.imports: dict[str, dict[str, Any]] = {}
        self.src_hosts: dict[str, tuple[str, str, str, str, str, str]] = {}
        if include_g3_host:
            self.src_hosts["zh.wikisource.org"] = (
                "zh.wikisource.org",
                "zh.wikisource.org",
                "canonical_jsonl_source_host",
                "https://zh.wikisource.org",
                "manual_source_jsonl",
                "active",
            )
        if include_g4_marker:
            self.imports[g5.G4_CUTOVER_IMPORT_CODE] = _g4_marker_row()
        self.g5_plan = g5_plan
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
        self._many: list[tuple[str, str, str, str, str, str]] = []

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
        if "FROM src_hosts" in query:
            assert isinstance(params, tuple)
            codes = sorted(params[0])
            self._many = [self.conn.src_hosts[code] for code in codes if code in self.conn.src_hosts]
            return
        raise AssertionError(f"unexpected query: {query}")

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._one

    def fetchall(self) -> list[tuple[str, str, str, str, str, str]]:
        return list(self._many)


def full_operator_config(*, dsn: str = "postgresql://example/db") -> g5.OperatorConfig:
    return g5.OperatorConfig(
        {
            g5.DSN_ENV_NAME: dsn,
            "RABBITMQ_URL": "amqp://user:pass@example.local:5672/%2F",
            "RABBITMQ_VHOST": "/",
            "RABBITMQ_EXCHANGE": "emperor.jobs",
            "RABBITMQ_QUEUE": "emperor.jobs.ready",
            "RABBITMQ_ROUTING_KEY": "jobs.ready",
            "RABBITMQ_PREFETCH": "10",
            "RABBITMQ_TLS_ENABLED": "false",
            "G5_NETWORK_SOURCE_ALLOWLIST": "zh.wikisource.org",
            "G5_NETWORK_PILOT_URL": "https://zh.wikisource.org/wiki/Main_Page",
            "G5_NETWORK_TIMEOUT_SECONDS": "5",
        }
    )


def rabbitmq_success() -> dict[str, Any]:
    return {
        "smoke": "rabbitmq_queue_exchange_binding_smoke",
        "smoke_passed": True,
        "exchange": "emperor.jobs",
        "queue": "emperor.jobs.ready",
        "routing_key": "jobs.ready",
    }


def network_success() -> dict[str, Any]:
    return {
        "smoke": "allowlisted_network_ingestion_pilot",
        "smoke_passed": True,
        "blocking_failure": None,
        "network_pilot_host": "zh.wikisource.org",
        "http_status": 200,
    }


def _g4_marker_row() -> dict[str, Any]:
    return {
        "code": g5.G4_CUTOVER_IMPORT_CODE,
        "source_kind": "write_source_cutover",
        "source_ref": "issue-292-g4",
        "status": "succeeded",
        "tool_version": "g4-write-source-cutover-execution-v1",
        "input_hash": g5.G4_CUTOVER_PLAN_SHA256,
        "row_count": 1,
        "meta": {
            "canonical_write_source": "postgresql",
            "jsonl_write_frozen": True,
            "postgres_unique_write_source": True,
        },
    }


def _g5_marker_row(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": g5.G5_RUNTIME_IMPORT_CODE,
        "source_kind": g5.G5_SOURCE_KIND,
        "source_ref": g5.G5_SOURCE_REF,
        "status": "succeeded",
        "tool_version": g5.EXECUTION_VERSION,
        "input_hash": plan["execution_plan_sha256"],
        "row_count": 1,
        "meta": {
            **g5.expected_runtime_state(),
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
