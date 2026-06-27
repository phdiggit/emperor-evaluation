from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import isolated_seed_dry_apply as dry_apply  # noqa: E402
from scripts.platform.formal_schema_draft import (  # noqa: E402
    BLOCKED_REPORT_TERMS,
    PHASE_1_BASE_TABLES,
    PHASE_2_RELATIONSHIP_TABLES,
    PHASE_3_DOWNSTREAM_TABLES,
)


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
EXPECTED_TABLES = [*PHASE_1_BASE_TABLES, "schema_rehearsal_meta"]
FORBIDDEN_TABLES = [*PHASE_2_RELATIONSHIP_TABLES, *PHASE_3_DOWNSTREAM_TABLES]


def test_contract_report_is_offline_and_preserves_guarded_paths(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = dry_apply.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["dry_apply_version"] == dry_apply.DRY_APPLY_VERSION
    assert report["status"] == "Proposed"
    assert report["dsn_env"] == dry_apply.PRIMARY_ENV_DSN
    assert report["driver"] == "psycopg"
    assert report["apply_mode"] == "explicit --dry-apply only"
    assert report["expected_tables"] == EXPECTED_TABLES
    assert report["forbidden_tables"] == FORBIDDEN_TABLES
    assert report["no_production_write_flags"] == dry_apply.NO_PRODUCTION_WRITE_FLAGS


def test_check_only_reads_primary_env_presence_and_does_not_connect(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    result = dry_apply.check_environment(env={}, driver_available=False)

    assert result["mode"] == "check"
    assert result["dsn_present"] is False
    assert result["dsn_source"] == "skip"
    assert result["driver_available"] is False
    assert result["will_connect"] is False
    assert result["will_write_isolated_schema"] is False
    assert result["will_write_public_schema"] is False
    assert result["will_apply_production_seed"] is False


def test_check_ignores_legacy_dsn_names_and_never_prints_secret() -> None:
    result = dry_apply.check_environment(
        env={
            LEGACY_ENV_DSN: "postgresql://legacy/example",
            dry_apply.PRIMARY_ENV_DSN: "postgresql://primary/example",
        },
        driver_available=True,
    )

    rendered = dry_apply.report_as_json(result)
    assert result["dsn_present"] is True
    assert result["dsn_source"] == f"env:{dry_apply.PRIMARY_ENV_DSN}"
    assert "legacy" not in rendered
    assert "primary" not in rendered

    legacy_only = dry_apply.check_environment(env={LEGACY_ENV_DSN: "postgresql://legacy/example"})
    assert legacy_only["dsn_present"] is False
    assert legacy_only["dsn_source"] == "skip"


def test_reports_contain_no_blocked_terms() -> None:
    reports = [
        dry_apply.build_contract_report(),
        dry_apply.check_environment(env={}, driver_available=False),
        dry_apply.build_skip_report(
            reason=f"{dry_apply.PRIMARY_ENV_DSN} is not set",
            dsn_present=False,
            driver_available=False,
        ),
    ]

    for report in reports:
        text = dry_apply.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_schema_prefix_guard_rejects_reserved_or_invalid_values() -> None:
    for value in ["", "bad-name", "1bad", "public", "postgres", "pg_catalog", "information_schema"]:
        with pytest.raises(ValueError):
            dry_apply.formal_ddl_live_rehearsal.validate_schema_prefix(value)


def test_schema_generation_always_adds_random_suffix() -> None:
    schema = dry_apply.formal_ddl_live_rehearsal.generate_schema_name(
        "emperor_eval_seed_dry_apply",
        token="a1b2c3d4e5",
    )

    assert schema == "emperor_eval_seed_dry_apply_a1b2c3d4e5"
    assert schema != "emperor_eval_seed_dry_apply"
    assert dry_apply.formal_ddl_live_rehearsal.generate_schema_name(
        "emperor_eval_seed_dry_apply"
    ) != dry_apply.formal_ddl_live_rehearsal.generate_schema_name("emperor_eval_seed_dry_apply")


def test_dry_apply_without_dsn_returns_skip_report_and_does_not_connect(monkeypatch, capsys) -> None:
    _guard_network(monkeypatch)
    monkeypatch.delenv(dry_apply.PRIMARY_ENV_DSN, raising=False)

    assert dry_apply.main(["--dry-apply", "--schema-prefix", "emperor_eval_seed_dry_apply"]) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry-apply"
    assert payload["dsn_present"] is False
    assert payload["passed"] is False
    assert payload["dry_apply_performed"] is False
    assert payload["schema_created"] is False
    assert payload["failed"] == [f"{dry_apply.PRIMARY_ENV_DSN} is not set"]


def test_dry_apply_without_psycopg_returns_skip_report_and_does_not_connect(monkeypatch, capsys) -> None:
    _guard_network(monkeypatch)
    monkeypatch.setenv(dry_apply.PRIMARY_ENV_DSN, "postgresql://example/db")
    monkeypatch.setattr(dry_apply, "is_psycopg_available", lambda: False)

    assert dry_apply.main(["--dry-apply", "--schema-prefix", "emperor_eval_seed_dry_apply"]) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry-apply"
    assert payload["dsn_present"] is True
    assert payload["driver_available"] is False
    assert payload["passed"] is False
    assert payload["dry_apply_performed"] is False
    assert payload["schema_created"] is False
    assert payload["failed"] == ["psycopg is not installed"]


def test_lint_failure_happens_before_database_connection(monkeypatch) -> None:
    def fail_connect(_dsn: str) -> object:
        raise AssertionError("database connection must not happen when DDL lint fails")

    class FakePsycopg:
        @staticmethod
        def connect(dsn: str) -> object:
            return fail_connect(dsn)

    monkeypatch.setattr(dry_apply, "is_psycopg_available", lambda: True)
    monkeypatch.setattr(dry_apply.formal_ddl_rehearsal, "lint_sql", lambda _sql, _schema: {"passed": False})
    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)

    report = dry_apply.run_dry_apply(
        "emperor_eval_seed_dry_apply",
        env={dry_apply.PRIMARY_ENV_DSN: "postgresql://example/db"},
        token="a1b2c3d4e5",
    )

    assert report["passed"] is False
    assert report["ddl_lint_passed"] is False
    assert report["artifact_valid"] is False
    assert report["schema_created"] is False
    assert report["failed"] == ["ddl_lint_passed_before_connect"]


def test_artifact_validation_failure_happens_before_database_connection(monkeypatch) -> None:
    def fail_connect(_dsn: str) -> object:
        raise AssertionError("database connection must not happen when artifact validation fails")

    class FakePsycopg:
        @staticmethod
        def connect(dsn: str) -> object:
            return fail_connect(dsn)

    monkeypatch.setattr(dry_apply, "is_psycopg_available", lambda: True)
    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)
    monkeypatch.setattr(
        dry_apply.seed_artifact_validation_matrix,
        "validate_artifact_and_manifest",
        lambda _artifact, _manifest: {"passed": False, "failed": ["example_artifact_rule"]},
    )

    report = dry_apply.run_dry_apply(
        "emperor_eval_seed_dry_apply",
        env={dry_apply.PRIMARY_ENV_DSN: "postgresql://example/db"},
        token="a1b2c3d4e5",
    )

    assert report["passed"] is False
    assert report["ddl_lint_passed"] is True
    assert report["artifact_valid"] is False
    assert report["schema_created"] is False
    assert report["failed"] == ["artifact_validation_passed_before_insert", "example_artifact_rule"]


def test_cli_contract_and_check_print_json(capsys) -> None:
    assert dry_apply.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert dry_apply.main(["--check"]) == 0
    check = json.loads(capsys.readouterr().out)
    assert check["mode"] == "check"
    assert check["will_connect"] is False
    assert check["will_write_public_schema"] is False
    assert check["will_apply_production_seed"] is False


def test_source_uses_python_driver_and_guarded_insert_strategy() -> None:
    source = (Path(dry_apply.__file__)).read_text(encoding="utf-8")

    for term in ["COPY ", "ON CONFLICT", "UPSERT", "LOAD DATA", "public."]:
        assert term not in source
    assert "subprocess" + ".run" not in source
    assert '"p' + 'sql"' not in source
    assert LEGACY_ENV_DSN not in source
    assert "import psycopg" in source
    assert dry_apply.PRIMARY_ENV_DSN in source
    assert "INSERT INTO" in source
    assert "quote_allowed_table" in source
    assert "EXPECTED_TABLES" in source
    assert "stable_code" in source


def test_guard_paths_use_utf8_chinese_names() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    protected_paths = {path.as_posix() for path in PROTECTED_PATHS}

    assert any(path.endswith("docs/皇帝综合评价体系评分标准.md") for path in protected_paths)
    assert any(path.endswith("docs/分项规则") for path in protected_paths)
    assert any(path.endswith("docs/证据规则") for path in protected_paths)
    for mojibake in ["\u9428\u56e7\u7b23", "\u934a\u55d8\u300d", "\u7487\u4f7a\u5d41"]:
        assert mojibake not in source


@pytest.mark.db
@pytest.mark.integration
def test_live_dry_apply_inserts_verifies_and_cleans_up() -> None:
    dsn = os.environ.get(dry_apply.PRIMARY_ENV_DSN)
    if not dsn:
        pytest.skip(f"{dry_apply.PRIMARY_ENV_DSN} is not set")
    if not dry_apply.is_psycopg_available():
        pytest.skip("psycopg is not installed")

    report = dry_apply.run_dry_apply(
        "emperor_eval_seed_dry_apply_pytest",
        drop_schema_after=True,
        env=os.environ,
    )

    assert report["passed"] is True
    assert report["ddl_lint_passed"] is True
    assert report["artifact_valid"] is True
    assert report["schema_created"] is True
    assert report["dry_apply_performed"] is True
    assert set(report["existing_expected_tables"]) == set(dry_apply.EXPECTED_TABLES)
    assert report["missing_expected_tables"] == []
    assert report["existing_forbidden_tables"] == []
    assert report["row_count_matches"] is True
    assert report["inserted_rows_by_table"] == report["expected_rows_by_table"]
    assert report["actual_rows_by_table"] == report["expected_rows_by_table"]
    assert report["inserted_rows_by_table"]["schema_rehearsal_meta"] == 1
    assert report["public_schema_touched"] is False
    assert report["production_schema_touched"] is False
    assert report["production_seed_applied"] is False
    assert report["repo_artifact_written"] is False
    assert report["data_written"] is False
    assert report["exports_written"] is False
    assert report["dropped"] is True
    assert report["schema_exists_after_drop"] is False
    assert report["cleanup_verified"] is True


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden before explicit dry-apply connection")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"isolated seed dry apply must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"isolated seed dry apply must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
