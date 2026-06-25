from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g3_postgres_business_write_execution as g3  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
    ROOT / ".env",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
]


def test_contract_report_records_g3_and_src_hosts_only() -> None:
    report = g3.build_contract_report(source_root=ROOT)

    assert report["mode"] == "contract-report"
    assert report["execution_version"] == g3.EXECUTION_VERSION
    assert report["gate_status"] == "G3_APPROVED"
    assert report["approval_token_required"] is True
    assert report["approval_token_value"] == g3.APPROVAL_TOKEN
    assert report["target_write_scope"]["source_files"] == ["data/sources.jsonl"]
    assert report["target_write_scope"]["target_tables"] == ["src_hosts"]
    assert report["planned_rows_by_table"] == {"src_hosts": 1}
    assert report["production_write_completed_by_this_report"] is False
    assert report["post_apply_observation_completed_by_this_report"] is False
    assert report["next_user_gate"] == "G4_REQUIRED_BEFORE_JSONL_FREEZE_OR_POSTGRES_UNIQUE_WRITE_SOURCE"


def test_execution_plan_is_stable_and_keeps_followup_writes_blocked() -> None:
    plan = g3.render_execution_plan_json(source_root=ROOT)

    assert plan["execution_plan_sha256"] == g3.stable_json_sha256(plan)
    assert plan["manifest_matches_g1"] is True
    assert plan["planned_rows_by_table"]["src_hosts"] == 1
    assert plan["planned_src_hosts"][0]["code"] == "zh.wikisource.org"
    assert plan["planned_src_hosts"][0]["source_id_count"] == 36
    assert plan["preflight_summary"]["sources_jsonl_rows"] == 36
    assert plan["preflight_summary"]["staging_validation_errors"] == 0
    blocked = {tuple(item["target_tables"]): item for item in plan["blocked_followup_writes"]}
    assert ("src_docs", "doc_revs", "passages") in blocked
    assert blocked[("src_docs", "doc_revs", "passages")]["duplicate_url_groups"]


def test_default_reports_do_not_read_dsn_or_forbidden_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if self.name == ".env" or "batches" in parts or ("archive" in parts and "data" in parts):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G3 default report tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g3.build_contract_report(source_root=ROOT)
    plan = g3.render_execution_plan_json(source_root=ROOT)
    checklist = g3.render_operator_checklist_md(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_db_touching"] is False
    assert plan["planned_rows_by_table"] == {"src_hosts": 1}
    assert "G3 PostgreSQL Business Write Operator Checklist" in checklist


def test_execute_blocks_before_dsn_when_token_or_plan_hash_missing(monkeypatch) -> None:
    def fail_read_dsn() -> str | None:
        raise AssertionError("gate failures must not read DSN")

    monkeypatch.setattr(g3, "read_dsn", fail_read_dsn)
    plan = g3.render_execution_plan_json(source_root=ROOT)

    report = g3.execute_business_write(approval_token=None, expected_plan_sha256=plan["execution_plan_sha256"])
    assert report["execution_status"] == "blocked"
    assert report["production_dsn_read"] is False
    assert "blocked_missing_or_invalid_g3_approval_token" in report["blocking_failures"]

    report = g3.execute_business_write(approval_token=g3.APPROVAL_TOKEN, expected_plan_sha256=None)
    assert "blocked_missing_expected_plan_sha256" in report["blocking_failures"]

    report = g3.execute_business_write(approval_token=g3.APPROVAL_TOKEN, expected_plan_sha256="0" * 64)
    assert "blocked_execution_plan_sha256_mismatch" in report["blocking_failures"]


def test_execute_blocks_missing_dsn_without_claiming_write(monkeypatch) -> None:
    plan = g3.render_execution_plan_json(source_root=ROOT)
    monkeypatch.setattr(g3, "read_dsn", lambda: None)

    report = g3.execute_business_write(
        approval_token=g3.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )

    assert report["execution_status"] == "blocked"
    assert report["failure_stage"] == "dsn"
    assert report["target_table_rows_written"] == {"src_hosts": 0}
    assert report["production_business_write_executed"] is False
    assert report["post_apply_observation_completed"] is False


def test_execute_writes_src_hosts_with_fake_connection_and_observes(monkeypatch) -> None:
    plan = g3.render_execution_plan_json(source_root=ROOT)
    conn = FakeConnection()
    secret = "postgresql://user:password@example.local/prod?password=secret"
    monkeypatch.setattr(g3, "read_dsn", lambda: secret)
    monkeypatch.setattr(g3, "connect_to_database", lambda _dsn: conn)

    report = g3.execute_business_write(
        approval_token=g3.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )
    rendered = g3.report_as_json(report)

    assert report["execution_status"] == "succeeded"
    assert report["target_table_rows_written"] == {"src_hosts": 1}
    assert report["post_apply_observation_completed"] is True
    assert report["post_apply_observation"]["observation_passed"] is True
    assert report["production_business_write_executed"] is True
    assert report["g4_approved"] is False
    assert report["jsonl_write_frozen"] is False
    assert report["postgres_unique_write_source"] is False
    assert conn.committed is True
    assert secret not in rendered
    assert "password=secret" not in rendered


def test_observe_is_readback_only(monkeypatch) -> None:
    plan = g3.render_execution_plan_json(source_root=ROOT)
    conn = FakeConnection()
    conn.rows["zh.wikisource.org"] = (
        "zh.wikisource.org",
        "zh.wikisource.org",
        "canonical_jsonl_source_host",
        "https://zh.wikisource.org",
        "manual_source_jsonl",
        "active",
    )
    monkeypatch.setattr(g3, "read_dsn", lambda: "postgresql://example/db")
    monkeypatch.setattr(g3, "connect_to_database", lambda _dsn: conn)

    report = g3.observe_business_write(
        approval_token=g3.APPROVAL_TOKEN,
        expected_plan_sha256=plan["execution_plan_sha256"],
    )

    assert report["mode"] == "observe-report"
    assert report["execution_status"] == "succeeded"
    assert report["production_business_write_executed"] is False
    assert not any("INSERT INTO src_hosts" in query for query, _params in conn.executed)


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g3.main(["--contract-report", "--source-root", str(ROOT)]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert g3.main(["--execution-plan-json", "--source-root", str(ROOT)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "execution-plan-json"

    assert g3.main(["--operator-checklist-md", "--source-root", str(ROOT)]) == 0
    checklist = capsys.readouterr().out
    assert "G3 PostgreSQL Business Write Operator Checklist" in checklist


def test_source_uses_python_driver_not_psql_or_subprocess() -> None:
    source = (ROOT / "scripts" / "platform" / "g3_postgres_business_write_execution.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "import psycopg" in source


class FakeConnection:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, str, str, str, str, str]] = {}
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
        self._one: tuple[str] | None = None
        self._many: list[tuple[str, str, str, str, str, str]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: object = None) -> None:
        self.conn.executed.append((query, params))
        if "INSERT INTO src_hosts" in query:
            assert isinstance(params, tuple)
            code, name, trust_class, base_url, adapter, status, _meta = params
            self.conn.rows[str(code)] = (
                str(code),
                str(name),
                str(trust_class),
                str(base_url),
                str(adapter),
                str(status),
            )
            self._one = (str(code),)
            return
        if "FROM src_hosts" in query:
            assert isinstance(params, tuple)
            codes = sorted(params[0])
            self._many = [self.conn.rows[code] for code in codes if code in self.conn.rows]
            return
        raise AssertionError(f"unexpected query: {query}")

    def fetchone(self) -> tuple[str] | None:
        return self._one

    def fetchall(self) -> list[tuple[str, str, str, str, str, str]]:
        return list(self._many)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
