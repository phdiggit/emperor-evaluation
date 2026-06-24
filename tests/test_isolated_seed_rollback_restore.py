from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import isolated_seed_rollback_restore as rollback_restore  # noqa: E402
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PROTECTED_PATHS = [
    ROOT / "data",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
    ROOT / "exports",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_contract_report_is_offline_and_preserves_guarded_paths(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = rollback_restore.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["rehearsal_version"] == rollback_restore.REHEARSAL_VERSION
    assert report["status"] == "Proposed"
    assert report["dsn_env"] == rollback_restore.PRIMARY_ENV_DSN
    assert report["driver"] == "psycopg"
    assert report["apply_mode"] == "explicit --rehearse only"
    assert report["restore_strategy"] == rollback_restore.RESTORE_REHEARSAL_MODE
    assert report["no_production_write_flags"] == rollback_restore.NO_PRODUCTION_WRITE_FLAGS


def test_check_only_reads_primary_env_presence_and_does_not_connect(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    result = rollback_restore.check_environment(env={}, driver_available=False)

    assert result["mode"] == "check"
    assert result["dsn_present"] is False
    assert result["dsn_source"] == "skip"
    assert result["driver_available"] is False
    assert result["will_connect"] is False
    assert result["will_write_isolated_schema"] is False
    assert result["will_write_public_schema"] is False
    assert result["will_restore_production"] is False


def test_check_ignores_legacy_dsn_names_and_never_prints_secret() -> None:
    result = rollback_restore.check_environment(
        env={
            LEGACY_ENV_DSN: "postgresql://legacy/example",
            rollback_restore.PRIMARY_ENV_DSN: "postgresql://primary/example",
        },
        driver_available=True,
    )

    rendered = rollback_restore.report_as_json(result)
    assert result["dsn_present"] is True
    assert result["dsn_source"] == f"env:{rollback_restore.PRIMARY_ENV_DSN}"
    assert "legacy" not in rendered
    assert "primary" not in rendered

    legacy_only = rollback_restore.check_environment(env={LEGACY_ENV_DSN: "postgresql://legacy/example"})
    assert legacy_only["dsn_present"] is False
    assert legacy_only["dsn_source"] == "skip"


def test_reports_contain_no_blocked_terms() -> None:
    reports = [
        rollback_restore.build_contract_report(),
        rollback_restore.check_environment(env={}, driver_available=False),
        rollback_restore.build_skip_report(
            reason=f"{rollback_restore.PRIMARY_ENV_DSN} is not set",
            dsn_present=False,
            driver_available=False,
        ),
    ]

    for report in reports:
        text = rollback_restore.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_schema_prefix_guard_rejects_reserved_or_invalid_values() -> None:
    for value in ["", "bad-name", "1bad", "public", "postgres", "pg_catalog", "information_schema"]:
        with pytest.raises(ValueError):
            rollback_restore.formal_ddl_live_rehearsal.validate_schema_prefix(value)


def test_schema_generation_always_adds_random_suffix() -> None:
    schema = rollback_restore.formal_ddl_live_rehearsal.generate_schema_name(
        "emperor_eval_seed_rollback",
        token="a1b2c3d4e5",
    )

    assert schema == "emperor_eval_seed_rollback_a1b2c3d4e5"
    assert schema != "emperor_eval_seed_rollback"
    assert rollback_restore.formal_ddl_live_rehearsal.generate_schema_name(
        "emperor_eval_seed_rollback"
    ) != rollback_restore.formal_ddl_live_rehearsal.generate_schema_name("emperor_eval_seed_rollback")


def test_rehearse_without_dsn_returns_skip_report_and_does_not_connect(monkeypatch, capsys) -> None:
    _guard_network(monkeypatch)
    monkeypatch.delenv(rollback_restore.PRIMARY_ENV_DSN, raising=False)

    assert rollback_restore.main(["--rehearse", "--schema-prefix", "emperor_eval_seed_rollback"]) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "rehearse"
    assert payload["dsn_present"] is False
    assert payload["passed"] is False
    assert payload["rollback_performed"] is False
    assert payload["restore_performed"] is False
    assert payload["failed"] == [f"{rollback_restore.PRIMARY_ENV_DSN} is not set"]


def test_rehearse_without_psycopg_returns_skip_report_and_does_not_connect(monkeypatch, capsys) -> None:
    _guard_network(monkeypatch)
    monkeypatch.setenv(rollback_restore.PRIMARY_ENV_DSN, "postgresql://example/db")
    monkeypatch.setattr(rollback_restore, "is_psycopg_available", lambda: False)

    assert rollback_restore.main(["--rehearse", "--schema-prefix", "emperor_eval_seed_rollback"]) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "rehearse"
    assert payload["dsn_present"] is True
    assert payload["driver_available"] is False
    assert payload["passed"] is False
    assert payload["rollback_performed"] is False
    assert payload["restore_performed"] is False
    assert payload["failed"] == ["psycopg is not installed"]


def test_artifact_validation_failure_happens_before_database_connection(monkeypatch) -> None:
    class FakePsycopg:
        @staticmethod
        def connect(_dsn: str) -> object:
            raise AssertionError("database connection must not happen when artifact validation fails")

    monkeypatch.setattr(rollback_restore, "is_psycopg_available", lambda: True)
    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)
    monkeypatch.setattr(
        rollback_restore.seed_artifact_validation_matrix,
        "validate_artifact_and_manifest",
        lambda _artifact, _manifest: {"passed": False, "failed": ["example_artifact_rule"]},
    )

    report = rollback_restore.run_rehearsal(
        "emperor_eval_seed_rollback",
        env={rollback_restore.PRIMARY_ENV_DSN: "postgresql://example/db"},
        token="a1b2c3d4e5",
    )

    assert report["passed"] is False
    assert report["artifact_valid"] is False
    assert report["dry_apply_passed"] is False
    assert report["rollback_performed"] is False
    assert report["restore_performed"] is False
    assert report["failed"] == ["artifact_validation_passed_before_rehearsal", "example_artifact_rule"]


def test_dry_apply_setup_failure_happens_before_database_connection(monkeypatch) -> None:
    class FakePsycopg:
        @staticmethod
        def connect(_dsn: str) -> object:
            raise AssertionError("database connection must not happen when DDL lint fails")

    monkeypatch.setattr(rollback_restore, "is_psycopg_available", lambda: True)
    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)
    monkeypatch.setattr(rollback_restore.formal_ddl_rehearsal, "lint_sql", lambda _sql, _schema: {"passed": False})

    report = rollback_restore.run_rehearsal(
        "emperor_eval_seed_rollback",
        env={rollback_restore.PRIMARY_ENV_DSN: "postgresql://example/db"},
        token="a1b2c3d4e5",
    )

    assert report["passed"] is False
    assert report["artifact_valid"] is False
    assert report["dry_apply_passed"] is False
    assert report["failed"] == ["dry_apply_passed_before_snapshot"]


def test_rehearsal_recreates_drops_and_compares_snapshots(monkeypatch) -> None:
    fake_conn = FakeConnection()

    class FakePsycopg:
        @staticmethod
        def connect(_dsn: str) -> FakeConnection:
            return fake_conn

    snapshots = [
        _snapshot("emperor_eval_seed_rollback_a1b2c3d4e5"),
        _snapshot("emperor_eval_seed_rollback_a1b2c3d4e5"),
    ]

    monkeypatch.setattr(rollback_restore, "is_psycopg_available", lambda: True)
    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)
    monkeypatch.setattr(rollback_restore, "_apply_seed_to_schema", lambda _cur, _sql, schema, _artifact: fake_conn.create(schema))
    monkeypatch.setattr(
        rollback_restore.formal_ddl_live_rehearsal,
        "schema_exists",
        lambda _cur, schema: fake_conn.exists(schema),
    )
    monkeypatch.setattr(rollback_restore, "capture_snapshot", lambda _cur, _schema, _artifact, _manifest: snapshots.pop(0))

    report = rollback_restore.run_rehearsal(
        "emperor_eval_seed_rollback",
        env={rollback_restore.PRIMARY_ENV_DSN: "postgresql://example/db"},
        token="a1b2c3d4e5",
    )

    assert report["passed"] is True
    assert report["artifact_valid"] is True
    assert report["dry_apply_passed"] is True
    assert report["rollback_performed"] is True
    assert report["schema_exists_after_rollback"] is False
    assert report["restore_performed"] is True
    assert report["snapshot_matches_after_restore"] is True
    assert report["final_drop_performed"] is True
    assert report["schema_exists_after_final_drop"] is False
    assert report["cleanup_verified"] is True
    assert report["public_schema_touched"] is False
    assert report["production_schema_touched"] is False
    assert report["production_restore_performed"] is False
    assert report["repo_artifact_written"] is False
    assert report["data_written"] is False
    assert report["exports_written"] is False


def test_cli_contract_and_check_print_json(capsys) -> None:
    assert rollback_restore.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert rollback_restore.main(["--check"]) == 0
    check = json.loads(capsys.readouterr().out)
    assert check["mode"] == "check"
    assert check["will_connect"] is False
    assert check["will_write_public_schema"] is False
    assert check["will_restore_production"] is False


def test_source_uses_python_driver_and_blocks_forbidden_paths() -> None:
    source = (ROOT / "scripts" / "platform" / "isolated_seed_rollback_restore.py").read_text(encoding="utf-8")

    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "public." not in source
    assert "production_restore_performed = True" not in source
    assert "import psycopg" in source
    assert rollback_restore.PRIMARY_ENV_DSN in source


def test_guard_paths_use_utf8_chinese_names() -> None:
    protected_paths = {path.as_posix() for path in PROTECTED_PATHS}
    protected_path_text = "\n".join(sorted(protected_paths))

    assert any(path.endswith("docs/皇帝综合评价体系评分标准.md") for path in protected_paths)
    assert any(path.endswith("docs/分项规则") for path in protected_paths)
    assert any(path.endswith("docs/证据规则") for path in protected_paths)
    for mojibake in ["鐨囧笣", "鍒嗛」", "璇佹嵁"]:
        assert mojibake not in protected_path_text


@pytest.mark.db
@pytest.mark.integration
def test_live_rehearsal_rolls_back_restores_and_cleans_up() -> None:
    dsn = os.environ.get(rollback_restore.PRIMARY_ENV_DSN)
    if not dsn:
        pytest.skip(f"{rollback_restore.PRIMARY_ENV_DSN} is not set")
    if not rollback_restore.is_psycopg_available():
        pytest.skip("psycopg is not installed")

    report = rollback_restore.run_rehearsal(
        "emperor_eval_seed_rollback_pytest",
        drop_schema_after=True,
        env=os.environ,
    )

    assert report["passed"] is True
    assert report["artifact_valid"] is True
    assert report["dry_apply_passed"] is True
    assert set(report["initial_snapshot"]["expected_tables"]) == set(rollback_restore.EXPECTED_TABLES)
    assert set(report["initial_snapshot"]["row_counts_by_table"]) == set(rollback_restore.EXPECTED_TABLES)
    assert report["initial_snapshot"]["forbidden_tables_present"] == []
    assert report["rollback_performed"] is True
    assert report["schema_exists_after_rollback"] is False
    assert report["restore_performed"] is True
    assert report["restored_snapshot"] == report["initial_snapshot"]
    assert report["snapshot_matches_after_restore"] is True
    assert report["final_drop_performed"] is True
    assert report["schema_exists_after_final_drop"] is False
    assert report["cleanup_verified"] is True
    assert report["public_schema_touched"] is False
    assert report["production_schema_touched"] is False
    assert report["production_restore_performed"] is False
    assert report["repo_artifact_written"] is False
    assert report["data_written"] is False
    assert report["exports_written"] is False


class FakeConnection:
    def __init__(self) -> None:
        self.schemas: set[str] = set()

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> "FakeCursor":
        return FakeCursor(self)

    def create(self, schema: str) -> None:
        self.schemas.add(schema)

    def drop(self, schema: str) -> None:
        self.schemas.discard(schema)

    def exists(self, schema: str) -> bool:
        return schema in self.schemas

    def rollback(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


class FakeCursor:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str, _params: Any = None) -> None:
        if statement.startswith("DROP SCHEMA"):
            schema = statement.split('"')[1]
            self.conn.drop(schema)


def _snapshot(schema: str) -> dict[str, Any]:
    return {
        "schema": schema,
        "expected_tables": list(rollback_restore.EXPECTED_TABLES),
        "row_counts_by_table": {table: 1 for table in rollback_restore.EXPECTED_TABLES},
        "forbidden_tables_present": [],
        "artifact_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "source_of_truth": rollback_restore.seed_artifact_renderer.SOURCE_OF_TRUTH,
    }


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden before explicit rehearsal connection")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"isolated seed rollback/restore must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"isolated seed rollback/restore must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
