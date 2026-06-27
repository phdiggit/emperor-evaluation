from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import production_seed_data_apply_execution as seed  # noqa: E402


def approved_manifest() -> dict[str, object]:
    manifest: dict[str, object] = {
        "manifest_version": 1,
        "manifest_kind": "production_seed_data_apply",
        "approval_status": "approved",
        "approved_for_execution": True,
        "canonical_seed_source_identified": True,
        "candidate_source_count": 1,
        "candidate_sources": [
            {
                "path": "data/seed-approved.jsonl",
                "sha256": "a" * 64,
                "byte_count": 32,
                "line_count": 2,
                "detected_logical_kind": "seed",
                "read_only": True,
            }
        ],
        "source_roots": ["data"],
        "redaction": {"contains_row_payloads": False, "contains_secret_material": False},
    }
    manifest["manifest_sha256"] = seed.stable_sha256(seed.seed_manifest_hash_basis(manifest))
    return manifest


def test_default_modes_do_not_read_dsn_or_connect(monkeypatch) -> None:
    def fail_read() -> str | None:
        raise AssertionError("default modes must not read DSN")

    def fail_connect(_dsn: str) -> object:
        raise AssertionError("default modes must not connect")

    monkeypatch.setattr(seed, "read_dsn", fail_read)
    monkeypatch.setattr(seed, "connect_to_database", fail_connect)

    assert seed.build_contract_report()["mode"] == "contract-report"
    assert seed.build_seed_manifest()["manifest_kind"] == "production_seed_data_apply"
    assert seed.render_execution_plan_json()["mode"] == "render-execution-plan-json"
    assert "Operator Checklist" in seed.render_operator_checklist_md()
    assert seed.build_adr_check()["passed"] is True


def test_seed_manifest_defaults_to_fail_closed_without_approved_canonical_source() -> None:
    manifest = seed.build_seed_manifest()

    assert manifest["approved_for_execution"] is False
    assert manifest["approval_status"] == seed.BLOCKED_MISSING_SEED_MANIFEST
    assert manifest["manifest_sha256"] == seed.stable_sha256(seed.seed_manifest_hash_basis(manifest))
    assert manifest["redaction"]["contains_row_payloads"] is False
    assert all("/batches/" not in source["path"] for source in manifest["candidate_sources"])
    assert all(not source["path"].startswith("archive/data/") for source in manifest["candidate_sources"])
    assert "excluded_discovery_sources" not in seed.seed_manifest_hash_basis(manifest)


def test_batch_and_archive_discovery_do_not_affect_seed_manifest_hash() -> None:
    manifest = seed.build_seed_manifest()
    altered = dict(manifest)
    altered["excluded_discovery_sources"] = [
        {
            "path": "archive/data/not-canonical.jsonl",
            "sha256": "0" * 64,
            "byte_count": 1,
            "line_count": 1,
            "detected_logical_kind": "excluded",
            "read_only": True,
        }
    ]
    altered["excluded_discovery_source_count"] = 1

    assert manifest["excluded_discovery_source_count"] >= 0
    assert seed.stable_sha256(seed.seed_manifest_hash_basis(altered)) == manifest["manifest_sha256"]


def test_import_audit_status_constants_match_postgres_schema_contract() -> None:
    sql = seed.POSTGRES_SQL_PATH.read_text(encoding="utf-8")

    assert seed.AUDIT_IMPORT_STATUS == "dry_run"
    assert seed.AUDIT_IMPORT_ROW_STATUS == "skipped"
    assert "CONSTRAINT import_status_ck CHECK (status IN ('running', 'succeeded', 'failed', 'dry_run'))" in sql
    assert (
        "CONSTRAINT irow_status_ck CHECK (import_status IN ('pending', 'accepted', 'rejected', 'skipped', 'error'))"
        in sql
    )


def test_execute_requires_token_schema_hash_and_manifest_hash(monkeypatch) -> None:
    manifest = approved_manifest()
    monkeypatch.setattr(seed, "build_seed_manifest", lambda: manifest)

    report = seed.execute_seed_data_apply(None, seed.schema_sha256(), str(manifest["manifest_sha256"]))
    assert report["seed_data_apply_executed"] is False
    assert report["failure_stage"] == "gate"
    assert "blocked_missing_or_invalid_approval_token" in report["blocking_failures"]

    report = seed.execute_seed_data_apply(seed.APPROVAL_TOKEN, "0" * 64, str(manifest["manifest_sha256"]))
    assert "blocked_schema_hash_mismatch" in report["blocking_failures"]

    report = seed.execute_seed_data_apply(seed.APPROVAL_TOKEN, seed.schema_sha256(), "0" * 64)
    assert "blocked_seed_manifest_hash_mismatch" in report["blocking_failures"]


def test_pre_execution_gate_is_lazy_fail_first(monkeypatch) -> None:
    manifest = approved_manifest()

    def fail_later_check() -> str:
        raise AssertionError("later gate checks must not run after the first failure")

    monkeypatch.setattr(seed, "schema_sha256", fail_later_check)
    monkeypatch.setattr(seed, "schema_files_byte_identical", lambda: fail_later_check())

    assert (
        seed.pre_execution_gate(None, "expected-schema", str(manifest["manifest_sha256"]), manifest)
        == "blocked_missing_or_invalid_approval_token"
    )


def test_execute_blocks_missing_seed_manifest_before_dsn(monkeypatch) -> None:
    manifest = seed.build_seed_manifest()

    def fail_read() -> str | None:
        raise AssertionError("blocked missing manifest must not read DSN")

    monkeypatch.setattr(seed, "read_dsn", fail_read)
    report = seed.execute_seed_data_apply(
        seed.APPROVAL_TOKEN,
        seed.schema_sha256(),
        str(manifest["manifest_sha256"]),
    )

    assert report["production_dsn_read"] is False
    assert report["seed_data_apply_executed"] is False
    assert report["verification_passed"] is False
    assert report["ready_for_production_migration"] is False
    assert report["failure_stage"] == "gate"
    assert seed.BLOCKED_MISSING_SEED_MANIFEST in report["blocking_failures"]


def test_execute_missing_dsn_is_blocked_without_success(monkeypatch) -> None:
    manifest = approved_manifest()
    monkeypatch.setattr(seed, "build_seed_manifest", lambda: manifest)
    monkeypatch.setattr(seed, "read_dsn", lambda: None)

    report = seed.execute_seed_data_apply(seed.APPROVAL_TOKEN, seed.schema_sha256(), str(manifest["manifest_sha256"]))

    assert report["production_dsn_read"] is False
    assert report["seed_data_apply_executed"] is False
    assert report["import_audit_written"] is False
    assert report["verification_passed"] is False
    assert report["failure_stage"] == "dsn_read"


def test_read_dsn_falls_back_to_dotenv_without_overriding_process_env(monkeypatch) -> None:
    monkeypatch.setitem(seed.os.environ, seed.DSN_ENV_NAME, "process-dsn")
    monkeypatch.setattr(seed, "read_dotenv_values", lambda: {seed.DSN_ENV_NAME: "dotenv-dsn"})

    assert seed.read_dsn() == "process-dsn"

    monkeypatch.delitem(seed.os.environ, seed.DSN_ENV_NAME)

    assert seed.read_dsn() == "dotenv-dsn"


def test_evidence_redacts_dsn_and_password(monkeypatch) -> None:
    manifest = approved_manifest()
    secret = "postgresql://user:password@example.local:5432/prod?password=secret"
    monkeypatch.setattr(seed, "build_seed_manifest", lambda: manifest)
    monkeypatch.setattr(seed, "read_dsn", lambda: secret)

    def fail_connect(_dsn: str) -> object:
        raise RuntimeError(f"could not connect to {secret}")

    monkeypatch.setattr(seed, "connect_to_database", fail_connect)

    report = seed.execute_seed_data_apply(seed.APPROVAL_TOKEN, seed.schema_sha256(), str(manifest["manifest_sha256"]))
    rendered = seed.report_as_json(report)

    assert secret not in rendered
    assert "password=secret" not in rendered
    assert "<redacted-dsn>" in rendered
    assert report["seed_data_apply_executed"] is False


def test_execute_uses_mock_connection_for_import_audit_scaffold_without_business_success(monkeypatch) -> None:
    manifest = approved_manifest()
    conn = FakeConnection(schema_tables=[(table,) for table in seed.REQUIRED_SCHEMA_LIVE_TABLES])
    monkeypatch.setattr(seed, "build_seed_manifest", lambda: manifest)
    monkeypatch.setattr(seed, "read_dsn", lambda: "redacted-test-dsn")
    monkeypatch.setattr(seed, "connect_to_database", lambda _dsn: conn)

    report = seed.execute_seed_data_apply(seed.APPROVAL_TOKEN, seed.schema_sha256(), str(manifest["manifest_sha256"]))

    assert report["mode"] == "seed-data-apply-audit-scaffold-report"
    assert report["seed_data_apply_executed"] is False
    assert report["production_data_rows_written"] is False
    assert report["import_audit_written"] is True
    assert report["verification_passed"] is False
    assert report["audit_verification_passed"] is True
    assert report["ready_for_production_migration"] is False
    assert report["target_business_table_writes_executed"] is False
    assert seed.BLOCKED_TARGET_IMPORTER_NOT_IMPLEMENTED in report["blocking_failures"]
    assert conn.committed is True
    assert any("INSERT INTO imports" in query for query, _params in conn.executed)
    assert any("INSERT INTO import_rows" in query for query, _params in conn.executed)
    import_params = [params for query, params in conn.executed if "INSERT INTO imports" in query]
    assert import_params
    assert all(params[3] == seed.AUDIT_IMPORT_STATUS for params in import_params if isinstance(params, tuple))
    import_row_params = [params for query, params in conn.executed if "INSERT INTO import_rows" in query]
    assert import_row_params
    assert all(params[5] == seed.AUDIT_IMPORT_ROW_STATUS for params in import_row_params if isinstance(params, tuple))
    assert all(params[6] is None for params in import_row_params if isinstance(params, tuple))


def test_verify_report_does_not_claim_execution(monkeypatch) -> None:
    manifest = approved_manifest()
    conn = FakeConnection(schema_tables=[(table,) for table in seed.REQUIRED_SCHEMA_LIVE_TABLES], audit_present=True)
    monkeypatch.setattr(seed, "build_seed_manifest", lambda: manifest)
    monkeypatch.setattr(seed, "read_dsn", lambda: "redacted-test-dsn")
    monkeypatch.setattr(seed, "connect_to_database", lambda _dsn: conn)

    report = seed.verify_seed_data_apply_report(seed.APPROVAL_TOKEN, seed.schema_sha256(), str(manifest["manifest_sha256"]))

    assert report["seed_data_apply_executed"] is False
    assert report["production_data_rows_written"] is False
    assert report["import_audit_written"] is False
    assert report["verification_passed"] is False
    assert report["audit_verification_passed"] is True
    assert seed.BLOCKED_TARGET_IMPORTER_NOT_IMPLEMENTED in report["blocking_failures"]


def test_verification_query_builder_is_read_only() -> None:
    table_query, _ = seed.build_table_check_query(seed.REQUIRED_SCHEMA_LIVE_TABLES)
    sql = table_query.lower()

    for forbidden in ("insert", "copy", "delete", "update", "create table", "alter table", "load data"):
        assert forbidden not in sql
    assert "information_schema" in sql


def test_lint_rejects_secret_material_false_success_and_unsafe_ready() -> None:
    blocked = seed.blocked_evidence(
        "2026-06-25T00:00:00Z",
        "gate",
        seed.BLOCKED_MISSING_SEED_MANIFEST,
        seed.build_seed_manifest(),
        False,
    )
    assert seed.lint_execution_report(blocked)["passed"] is True

    leaked = dict(blocked)
    leaked["redacted_stderr_summary"] = ["postgresql://user:password@example/prod"]
    assert "secret_material_present" in seed.lint_execution_report(leaked)["failed"]

    false_success = dict(blocked)
    false_success["verification_passed"] = True
    assert "blocked_report_claims_verification_success" in seed.lint_execution_report(false_success)["failed"]

    unsafe_ready = dict(blocked)
    unsafe_ready["ready_for_production_migration"] = True
    assert "ready_for_production_migration_true_in_audit_scaffold" in seed.lint_execution_report(unsafe_ready)["failed"]


def test_cli_safe_modes_output_expected_modes() -> None:
    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--render-seed-manifest-json"], "production_seed_data_apply"),
        (["--render-execution-plan-json"], "render-execution-plan-json"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert seed.main(args) == 0
        payload = json.loads(buffer.getvalue())
        if "manifest_kind" in payload:
            assert payload["manifest_kind"] == mode
        else:
            assert payload["mode"] == mode

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert seed.main(["--render-operator-checklist-md"]) == 0
    assert "Operator Checklist" in buffer.getvalue()


def test_source_does_not_print_or_return_dsn_raw() -> None:
    source = (Path(seed.__file__)).read_text(encoding="utf-8")

    assert "print(dsn" not in source
    assert '"dsn": dsn' not in source
    assert "'dsn': dsn" not in source
    assert "subprocess" not in source
    assert "dsn_value_redacted" in source


def test_schema_and_data_inputs_remain_unchanged_across_safe_and_blocked_modes() -> None:
    watched = [
        seed.POSTGRES_SQL_PATH,
        seed.SCHEMA_SQL_PATH,
        next(path for root in seed.DATA_ROOTS for path in root.rglob("*.jsonl") if path.is_file()),
    ]
    before = {path: path.stat().st_mtime_ns for path in watched}
    manifest = seed.build_seed_manifest()

    seed.build_contract_report()
    seed.render_execution_plan_json()
    report = seed.execute_seed_data_apply(
        seed.APPROVAL_TOKEN,
        seed.schema_sha256(),
        str(manifest["manifest_sha256"]),
    )

    assert seed.BLOCKED_MISSING_SEED_MANIFEST in report["blocking_failures"]
    assert before == {path: path.stat().st_mtime_ns for path in watched}


class FakeConnection:
    def __init__(self, schema_tables: list[tuple[str]], audit_present: bool = False) -> None:
        self.schema_tables = schema_tables
        self.audit_present = audit_present
        self.import_id = 1001
        self.import_code = ""
        self.import_row_count = 0
        self.executed: list[tuple[str, object]] = []
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
        self.last_params: object = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute(self, query: str, params: object = None) -> None:
        self.last_query = query
        self.last_params = params
        self.conn.executed.append((query, params))
        if "INSERT INTO imports" in query:
            assert isinstance(params, tuple)
            self.conn.import_code = str(params[0])
            self.conn.audit_present = True
        if "INSERT INTO import_rows" in query:
            self.conn.import_row_count += 1

    def fetchone(self) -> tuple[object, ...] | None:
        if "RETURNING id" in self.last_query:
            return (self.conn.import_id,)
        if "SELECT code, status, row_count" in self.last_query:
            if not self.conn.audit_present:
                return None
            return (
                self.conn.import_code or "production_seed_data_apply_pr286_test",
                seed.AUDIT_IMPORT_STATUS,
                self.conn.import_row_count,
            )
        if "SELECT count(*)" in self.last_query:
            return (self.conn.import_row_count,)
        return None

    def fetchall(self) -> list[tuple[str, ...]]:
        if "information_schema.tables" in self.last_query:
            return self.conn.schema_tables
        return []
