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

from scripts.platform import seed_artifact_db_preflight as preflight  # noqa: E402
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

    report = preflight.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["preflight_version"] == preflight.PREFLIGHT_VERSION
    assert report["status"] == "Proposed"
    assert report["dsn_env"] == preflight.PRIMARY_ENV_DSN
    assert report["driver"] == "psycopg"
    assert report["apply_mode"] == "explicit --preflight only"
    assert report["expected_schema_tables"] == EXPECTED_TABLES
    assert report["forbidden_schema_tables"] == FORBIDDEN_TABLES
    assert report["artifact_expected_tables"] == EXPECTED_TABLES


def test_check_only_reads_primary_env_presence_and_does_not_connect(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    result = preflight.check_environment(env={}, driver_available=False)

    assert result["mode"] == "check"
    assert result["dsn_present"] is False
    assert result["dsn_source"] == "skip"
    assert result["driver_available"] is False
    assert result["will_connect"] is False
    assert result["will_apply_seed"] is False
    assert result["default_tests_require_postgres"] is False


def test_check_ignores_legacy_dsn_names_and_never_prints_secret() -> None:
    result = preflight.check_environment(
        env={
            LEGACY_ENV_DSN: "postgresql://legacy/example",
            preflight.PRIMARY_ENV_DSN: "postgresql://primary/example",
        },
        driver_available=True,
    )

    rendered = preflight.report_as_json(result)
    assert result["dsn_present"] is True
    assert result["dsn_source"] == f"env:{preflight.PRIMARY_ENV_DSN}"
    assert "legacy" not in rendered
    assert "primary" not in rendered

    legacy_only = preflight.check_environment(env={LEGACY_ENV_DSN: "postgresql://legacy/example"})
    assert legacy_only["dsn_present"] is False
    assert legacy_only["dsn_source"] == "skip"


def test_reports_contain_no_blocked_terms() -> None:
    reports = [
        preflight.build_contract_report(),
        preflight.check_environment(env={}, driver_available=False),
        preflight.build_skip_report(
            reason=f"{preflight.PRIMARY_ENV_DSN} is not set",
            dsn_present=False,
            driver_available=False,
        ),
    ]

    for report in reports:
        text = preflight.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_schema_prefix_guard_rejects_reserved_or_invalid_values() -> None:
    for value in ["", "bad-name", "1bad", "public", "postgres", "pg_catalog", "information_schema"]:
        with pytest.raises(ValueError):
            preflight.formal_ddl_live_rehearsal.validate_schema_prefix(value)


def test_schema_generation_always_adds_random_suffix() -> None:
    schema = preflight.formal_ddl_live_rehearsal.generate_schema_name(
        "emperor_eval_seed_preflight",
        token="a1b2c3d4e5",
    )

    assert schema == "emperor_eval_seed_preflight_a1b2c3d4e5"
    assert schema != "emperor_eval_seed_preflight"
    assert preflight.formal_ddl_live_rehearsal.generate_schema_name(
        "emperor_eval_seed_preflight"
    ) != preflight.formal_ddl_live_rehearsal.generate_schema_name("emperor_eval_seed_preflight")


def test_preflight_without_dsn_returns_skip_report_and_does_not_connect(monkeypatch, capsys) -> None:
    _guard_network(monkeypatch)
    monkeypatch.delenv(preflight.PRIMARY_ENV_DSN, raising=False)

    assert preflight.main(["--preflight", "--schema-prefix", "emperor_eval_seed_preflight"]) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "preflight"
    assert payload["dsn_present"] is False
    assert payload["passed"] is False
    assert payload["schema_created"] is False
    assert payload["failed"] == [f"{preflight.PRIMARY_ENV_DSN} is not set"]


def test_preflight_without_psycopg_returns_skip_report_and_does_not_connect(monkeypatch, capsys) -> None:
    _guard_network(monkeypatch)
    monkeypatch.setenv(preflight.PRIMARY_ENV_DSN, "postgresql://example/db")
    monkeypatch.setattr(preflight, "is_psycopg_available", lambda: False)

    assert preflight.main(["--preflight", "--schema-prefix", "emperor_eval_seed_preflight"]) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "preflight"
    assert payload["dsn_present"] is True
    assert payload["driver_available"] is False
    assert payload["passed"] is False
    assert payload["schema_created"] is False
    assert payload["failed"] == ["psycopg is not installed"]


def test_lint_failure_happens_before_database_connection(monkeypatch) -> None:
    def fail_connect(_dsn: str) -> object:
        raise AssertionError("database connection must not happen when DDL lint fails")

    class FakePsycopg:
        @staticmethod
        def connect(dsn: str) -> object:
            return fail_connect(dsn)

    monkeypatch.setattr(preflight, "is_psycopg_available", lambda: True)
    monkeypatch.setattr(preflight.formal_ddl_rehearsal, "lint_sql", lambda _sql, _schema: {"passed": False})
    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)

    report = preflight.run_preflight(
        "emperor_eval_seed_preflight",
        env={preflight.PRIMARY_ENV_DSN: "postgresql://example/db"},
        token="a1b2c3d4e5",
    )

    assert report["passed"] is False
    assert report["ddl_lint_passed"] is False
    assert report["schema_created"] is False
    assert report["failed"] == ["ddl_lint_failed_before_connect"]


def test_cli_contract_and_check_print_json(capsys) -> None:
    assert preflight.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert preflight.main(["--check"]) == 0
    check = json.loads(capsys.readouterr().out)
    assert check["mode"] == "check"
    assert check["will_connect"] is False
    assert check["will_apply_seed"] is False


def test_source_uses_python_driver_and_forbids_seed_write_terms() -> None:
    source = (ROOT / "scripts" / "platform" / "seed_artifact_db_preflight.py").read_text(encoding="utf-8")

    for term in ["INSERT INTO", "COPY ", "ON CONFLICT", "UPSERT", "LOAD DATA"]:
        assert term not in source
    assert "subprocess" + ".run" not in source
    assert '"p' + 'sql"' not in source
    assert LEGACY_ENV_DSN not in source
    assert "import psycopg" in source
    assert preflight.PRIMARY_ENV_DSN in source


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
def test_live_preflight_applies_verifies_and_cleans_up() -> None:
    dsn = os.environ.get(preflight.PRIMARY_ENV_DSN)
    if not dsn:
        pytest.skip(f"{preflight.PRIMARY_ENV_DSN} is not set")
    if not preflight.is_psycopg_available():
        pytest.skip("psycopg is not installed")

    report = preflight.run_preflight(
        "emperor_eval_seed_preflight_pytest",
        drop_schema_after=True,
        env=os.environ,
    )

    assert report["passed"] is True
    assert report["ddl_lint_passed"] is True
    assert report["schema_created"] is True
    assert set(report["existing_expected_schema_tables"]) == set(preflight.EXPECTED_SCHEMA_TABLES)
    assert report["missing_expected_schema_tables"] == []
    assert report["existing_forbidden_schema_tables"] == []
    assert set(report["artifact_payload_tables"]) == set(preflight.EXPECTED_SCHEMA_TABLES)
    assert report["artifact_extra_tables"] == []
    assert report["artifact_missing_tables"] == []
    assert set(preflight.FORBIDDEN_SCHEMA_TABLES) <= set(report["artifact_blocked_tables"])
    assert report["seed_application_performed"] is False
    assert report["insert_performed"] is False
    assert report["copy_performed"] is False
    assert report["upsert_performed"] is False
    assert report["db_row_write_performed"] is False
    assert report["dropped"] is True
    assert report["schema_exists_after_drop"] is False
    assert report["cleanup_verified"] is True


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden before explicit preflight connection")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"seed artifact DB preflight must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"seed artifact DB preflight must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
