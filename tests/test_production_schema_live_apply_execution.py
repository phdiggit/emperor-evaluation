from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import production_schema_live_apply_execution as live  # noqa: E402


def test_default_modes_do_not_read_dsn_or_connect(monkeypatch) -> None:
    def fail_read() -> str | None:
        raise AssertionError("default modes must not read DSN")

    def fail_connect(_dsn: str) -> object:
        raise AssertionError("default modes must not connect")

    monkeypatch.setattr(live, "read_dsn", fail_read)
    monkeypatch.setattr(live, "connect_to_database", fail_connect)

    assert live.build_contract_report()["mode"] == "contract-report"
    assert live.render_execution_plan_json()["mode"] == "render-execution-plan-json"
    assert "Operator Checklist" in live.render_operator_checklist_md()
    assert live.build_adr_check()["passed"] is True


def test_execute_requires_approval_token() -> None:
    report = live.execute_live_apply(None, live.schema_sha256())

    assert report["schema_live_apply_executed"] is False
    assert report["sql_executed"] is False
    assert report["production_db_connected"] is False
    assert report["failure_stage"] == "gate"
    assert "blocked_missing_or_invalid_approval_token" in report["blocking_failures"]


def test_execute_requires_matching_schema_hash() -> None:
    report = live.execute_live_apply(live.APPROVAL_TOKEN, "0" * 64)

    assert report["schema_live_apply_executed"] is False
    assert report["failure_stage"] == "gate"
    assert "blocked_schema_hash_mismatch" in report["blocking_failures"]


def test_execute_blocks_when_schema_files_differ(monkeypatch) -> None:
    monkeypatch.setattr(live, "schema_files_byte_identical", lambda: False)

    report = live.execute_live_apply(live.APPROVAL_TOKEN, live.schema_sha256())

    assert report["schema_live_apply_executed"] is False
    assert report["failure_stage"] == "gate"
    assert "blocked_schema_files_not_byte_identical" in report["blocking_failures"]


def test_execute_missing_dsn_is_blocked_without_success(monkeypatch) -> None:
    monkeypatch.setattr(live, "read_dsn", lambda: None)

    report = live.execute_live_apply(live.APPROVAL_TOKEN, live.schema_sha256())

    assert report["production_dsn_read"] is False
    assert report["schema_live_apply_executed"] is False
    assert report["verification_passed"] is False
    assert report["ready_for_production_migration"] is False
    assert report["failure_stage"] == "dsn_read"


def test_read_dsn_falls_back_to_dotenv_without_overriding_process_env(monkeypatch) -> None:
    monkeypatch.setitem(live.os.environ, live.DSN_ENV_NAME, "process-dsn")
    monkeypatch.setattr(live, "read_dotenv_values", lambda: {live.DSN_ENV_NAME: "dotenv-dsn"})

    assert live.read_dsn() == "process-dsn"

    monkeypatch.delitem(live.os.environ, live.DSN_ENV_NAME)

    assert live.read_dsn() == "dotenv-dsn"


def test_evidence_redacts_dsn_and_password(monkeypatch) -> None:
    secret = "postgresql://user:password@example.local:5432/prod?password=secret"
    monkeypatch.setattr(live, "read_dsn", lambda: secret)

    def fail_connect(_dsn: str) -> object:
        raise RuntimeError(f"could not connect to {secret}")

    monkeypatch.setattr(live, "connect_to_database", fail_connect)

    report = live.execute_live_apply(live.APPROVAL_TOKEN, live.schema_sha256())
    rendered = live.report_as_json(report)

    assert secret not in rendered
    assert "password=secret" not in rendered
    assert "<redacted-dsn>" in rendered
    assert report["schema_live_apply_executed"] is False


def test_successful_execute_uses_mock_connection_and_keeps_migration_not_ready(monkeypatch) -> None:
    conn = FakeConnection(
        table_rows=[(table,) for table in live.CORE_TABLES],
        column_rows=[
            ("search_hits", "hit_position"),
            ("cand_matches", "match_confidence"),
        ],
    )
    monkeypatch.setattr(live, "read_dsn", lambda: "redacted-test-dsn")
    monkeypatch.setattr(live, "connect_to_database", lambda _dsn: conn)

    report = live.execute_live_apply(live.APPROVAL_TOKEN, live.schema_sha256())

    assert report["schema_live_apply_executed"] is True
    assert report["sql_executed"] is True
    assert report["production_db_connected"] is True
    assert report["verification_passed"] is True
    assert report["ready_for_production_migration"] is False
    assert report["future_target_importer_gate_required"] is True
    assert conn.committed is True
    assert "CREATE TABLE anchors" in conn.executed[0]


def test_verify_report_does_not_claim_execution(monkeypatch) -> None:
    conn = FakeConnection(
        table_rows=[(table,) for table in live.CORE_TABLES],
        column_rows=[
            ("search_hits", "hit_position"),
            ("cand_matches", "match_confidence"),
        ],
    )
    monkeypatch.setattr(live, "read_dsn", lambda: "redacted-test-dsn")
    monkeypatch.setattr(live, "connect_to_database", lambda _dsn: conn)

    report = live.verify_live_apply(live.APPROVAL_TOKEN, live.schema_sha256())

    assert report["schema_live_apply_executed"] is False
    assert report["sql_executed"] is False
    assert report["post_apply_verification_executed"] is True
    assert report["verification_passed"] is True


def test_verification_query_builder_is_read_only() -> None:
    table_query, _ = live.build_table_check_query(live.CORE_TABLES)
    column_query, _ = live.build_column_check_query(live.EXPECTED_COLUMNS_PRESENT)
    sql = f"{table_query}\n{column_query}".lower()

    for forbidden in ("insert", "copy", "delete", "update", "create table", "alter table", "load data"):
        assert forbidden not in sql
    assert "information_schema" in sql


def test_lint_rejects_secret_material_and_false_success() -> None:
    blocked = live.blocked_evidence("2026-06-25T00:00:00Z", "dsn_read", "blocked_missing_dsn", False)
    assert live.lint_execution_report(blocked)["passed"] is True

    leaked = dict(blocked)
    leaked["redacted_stderr_summary"] = ["postgresql://user:password@example/prod"]
    assert "secret_material_present" in live.lint_execution_report(leaked)["failed"]

    false_success = dict(blocked)
    false_success["verification_passed"] = True
    assert "blocked_report_claims_verification_success" in live.lint_execution_report(false_success)["failed"]


def test_cli_safe_modes_output_expected_modes() -> None:
    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--render-execution-plan-json"], "render-execution-plan-json"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert live.main(args) == 0
        assert json.loads(buffer.getvalue())["mode"] == mode

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert live.main(["--render-operator-checklist-md"]) == 0
    assert "Operator Checklist" in buffer.getvalue()


def test_source_does_not_print_or_return_dsn_raw() -> None:
    source = (ROOT / "scripts" / "platform" / "production_schema_live_apply_execution.py").read_text(
        encoding="utf-8"
    )
    assert "print(dsn" not in source
    assert '"dsn": dsn' not in source
    assert "'dsn': dsn" not in source
    assert "dsn_value_redacted" in source


class FakeConnection:
    def __init__(self, table_rows: list[tuple[str]], column_rows: list[tuple[str, str]]) -> None:
        self.table_rows = table_rows
        self.column_rows = column_rows
        self.executed: list[str] = []
        self.committed = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def cursor(self) -> "FakeCursor":
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed = True


class FakeCursor:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn
        self.last_query = ""

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute(self, query: str, _params: object = None) -> None:
        self.last_query = query
        self.conn.executed.append(query)

    def fetchall(self) -> list[tuple[str, ...]]:
        if "information_schema.tables" in self.last_query:
            return self.conn.table_rows
        return self.conn.column_rows
