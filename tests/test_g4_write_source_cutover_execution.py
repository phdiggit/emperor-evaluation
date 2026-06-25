from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g4_write_source_cutover_execution as g4  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
    ROOT / ".env",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
]


def test_contract_report_records_g4_without_claiming_cutover_complete() -> None:
    report = g4.build_contract_report(source_root=ROOT)

    assert report["mode"] == "contract-report"
    assert report["execution_version"] == g4.EXECUTION_VERSION
    assert report["gate_status"] == "G4_APPROVED"
    assert report["approval_token_required"] is True
    assert report["approval_token_value"] == g4.APPROVAL_TOKEN
    assert report["source_pr"] == 296
    assert report["source_head_sha"] == g4.G4_SOURCE_HEAD_SHA
    assert report["source_merge_commit"] == g4.G4_SOURCE_MERGE_COMMIT
    assert report["cutover_marker"]["target_table"] == "imports"
    assert report["cutover_marker"]["code"] == g4.CUTOVER_IMPORT_CODE
    assert report["cutover_completed_by_this_report"] is False
    assert report["post_apply_observation_completed_by_this_report"] is False
    assert report["next_user_gate"] == "G5_REQUIRED_BEFORE_PRODUCTION_RUNTIME_OR_ADDITIONAL_BUSINESS_WRITES"


def test_cutover_plan_is_stable_and_preserves_runtime_boundaries() -> None:
    plan = g4.render_cutover_plan_json(source_root=ROOT)

    assert plan["cutover_plan_sha256"] == g4.stable_json_sha256(plan)
    assert plan["g3_execution_plan_sha256"] == g4.G3_EXECUTION_PLAN_SHA256
    assert plan["freeze_point"]["jsonl_write_freeze_scope"] == ["data/*.jsonl"]
    assert plan["freeze_point"]["freeze_after_merge_commit"] == g4.G4_SOURCE_MERGE_COMMIT
    assert plan["execute_write"]["target_tables"] == ["imports"]
    assert plan["execute_write"]["business_target_tables_written"] == []
    assert plan["write_source_state_after_cutover"] == {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_runtime_live": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
    }
    assert plan["post_apply_observation_contract"]["expected_g3_src_host_codes"] == ["zh.wikisource.org"]


def test_default_reports_do_not_read_dsn_or_forbidden_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if self.name == ".env" or "batches" in parts or ("archive" in parts and "data" in parts):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G4 default report tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g4.build_contract_report(source_root=ROOT)
    plan = g4.render_cutover_plan_json(source_root=ROOT)
    checklist = g4.render_operator_checklist_md(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_db_touching"] is False
    assert plan["cutover_marker"]["target_table"] == "imports"
    assert "G4 Write-Source Cutover Operator Checklist" in checklist


def test_execute_blocks_before_dsn_when_token_or_plan_hash_missing(monkeypatch) -> None:
    def fail_read_dsn() -> str | None:
        raise AssertionError("gate failures must not read DSN")

    monkeypatch.setattr(g4, "read_dsn", fail_read_dsn)
    plan = g4.render_cutover_plan_json(source_root=ROOT)

    report = g4.execute_cutover(approval_token=None, expected_plan_sha256=plan["cutover_plan_sha256"])
    assert report["execution_status"] == "blocked"
    assert report["production_dsn_read"] is False
    assert "blocked_missing_or_invalid_g4_approval_token" in report["blocking_failures"]

    report = g4.execute_cutover(approval_token=g4.APPROVAL_TOKEN, expected_plan_sha256=None)
    assert "blocked_missing_expected_plan_sha256" in report["blocking_failures"]

    report = g4.execute_cutover(approval_token=g4.APPROVAL_TOKEN, expected_plan_sha256="0" * 64)
    assert "blocked_cutover_plan_sha256_mismatch" in report["blocking_failures"]


def test_execute_blocks_missing_dsn_without_claiming_cutover(monkeypatch) -> None:
    plan = g4.render_cutover_plan_json(source_root=ROOT)
    monkeypatch.setattr(g4, "read_dsn", lambda: None)

    report = g4.execute_cutover(
        approval_token=g4.APPROVAL_TOKEN,
        expected_plan_sha256=plan["cutover_plan_sha256"],
    )

    assert report["execution_status"] == "blocked"
    assert report["failure_stage"] == "dsn"
    assert report["cutover_marker_written"] is False
    assert report["cutover_executed"] is False
    assert report["canonical_write_source"] == "jsonl"
    assert report["jsonl_write_frozen"] is False


def test_execute_blocks_if_g3_src_hosts_readback_is_missing(monkeypatch) -> None:
    plan = g4.render_cutover_plan_json(source_root=ROOT)
    conn = FakeConnection(include_g3_host=False)
    monkeypatch.setattr(g4, "read_dsn", lambda: "postgresql://example/db")
    monkeypatch.setattr(g4, "connect_to_database", lambda _dsn: conn)

    report = g4.execute_cutover(
        approval_token=g4.APPROVAL_TOKEN,
        expected_plan_sha256=plan["cutover_plan_sha256"],
    )

    assert report["execution_status"] == "blocked"
    assert report["failure_stage"] == "g3_observation"
    assert report["cutover_marker_written"] is False
    assert report["cutover_executed"] is False
    assert not any("INSERT INTO imports" in query for query, _params in conn.executed)


def test_execute_writes_cutover_marker_with_fake_connection_and_observes(monkeypatch) -> None:
    plan = g4.render_cutover_plan_json(source_root=ROOT)
    conn = FakeConnection(include_g3_host=True)
    secret = "postgresql://user:password@example.local/prod?password=secret"
    monkeypatch.setattr(g4, "read_dsn", lambda: secret)
    monkeypatch.setattr(g4, "connect_to_database", lambda _dsn: conn)

    report = g4.execute_cutover(
        approval_token=g4.APPROVAL_TOKEN,
        expected_plan_sha256=plan["cutover_plan_sha256"],
    )
    rendered = g4.report_as_json(report)

    assert report["execution_status"] == "succeeded"
    assert report["cutover_marker_written"] is True
    assert report["post_apply_observation_completed"] is True
    assert report["post_apply_observation"]["observation_passed"] is True
    assert report["cutover_executed"] is True
    assert report["canonical_write_source"] == "postgresql"
    assert report["jsonl_write_frozen"] is True
    assert report["postgres_unique_write_source"] is True
    assert report["production_runtime_live"] is False
    assert conn.committed is True
    assert conn.imports[g4.CUTOVER_IMPORT_CODE]["input_hash"] == plan["cutover_plan_sha256"]
    assert secret not in rendered
    assert "password=secret" not in rendered


def test_observe_is_readback_only(monkeypatch) -> None:
    plan = g4.render_cutover_plan_json(source_root=ROOT)
    conn = FakeConnection(include_g3_host=True)
    conn.imports[g4.CUTOVER_IMPORT_CODE] = _marker_row(plan)
    monkeypatch.setattr(g4, "read_dsn", lambda: "postgresql://example/db")
    monkeypatch.setattr(g4, "connect_to_database", lambda _dsn: conn)

    report = g4.observe_cutover(
        approval_token=g4.APPROVAL_TOKEN,
        expected_plan_sha256=plan["cutover_plan_sha256"],
    )

    assert report["mode"] == "observe-report"
    assert report["execution_status"] == "succeeded"
    assert report["cutover_executed"] is False
    assert report["canonical_write_source"] == "postgresql"
    assert not any("INSERT INTO imports" in query for query, _params in conn.executed)


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g4.main(["--contract-report", "--source-root", str(ROOT)]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert g4.main(["--cutover-plan-json", "--source-root", str(ROOT)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "cutover-plan-json"

    assert g4.main(["--operator-checklist-md", "--source-root", str(ROOT)]) == 0
    checklist = capsys.readouterr().out
    assert "G4 Write-Source Cutover Operator Checklist" in checklist


def test_source_uses_python_driver_not_psql_or_subprocess() -> None:
    source = (ROOT / "scripts" / "platform" / "g4_write_source_cutover_execution.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "import psycopg" in source


class FakeConnection:
    def __init__(self, *, include_g3_host: bool) -> None:
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


def _marker_row(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": g4.CUTOVER_IMPORT_CODE,
        "source_kind": g4.CUTOVER_SOURCE_KIND,
        "source_ref": g4.CUTOVER_SOURCE_REF,
        "status": "succeeded",
        "tool_version": g4.EXECUTION_VERSION,
        "input_hash": plan["cutover_plan_sha256"],
        "row_count": 1,
        "meta": g4.marker_meta(plan),
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
