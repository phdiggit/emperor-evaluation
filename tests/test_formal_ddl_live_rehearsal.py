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

from scripts.platform import formal_ddl_live_rehearsal as live  # noqa: E402
from scripts.platform.formal_schema_draft import (  # noqa: E402
    BLOCKED_REPORT_TERMS,
    PHASE_1_BASE_TABLES,
    PHASE_2_RELATIONSHIP_TABLES,
    PHASE_3_DOWNSTREAM_TABLES,
)


LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
FORBIDDEN_PATHS = [
    ROOT / "data",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_contract_report_is_offline_and_preserves_guarded_paths(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in formal DDL live rehearsal contract")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"formal DDL live rehearsal must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = live.build_contract_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["apply_mode"] == "explicit --apply only"
    assert report["dsn_env"] == live.PRIMARY_ENV_DSN
    assert report["driver"] == "psycopg"
    assert report["phase_1_expected_tables"] == [*PHASE_1_BASE_TABLES, live.SCHEMA_REHEARSAL_META_TABLE]
    assert report["phase_2_forbidden_tables"] == list(PHASE_2_RELATIONSHIP_TABLES)
    assert report["phase_3_forbidden_tables"] == list(PHASE_3_DOWNSTREAM_TABLES)


def test_check_without_dsn_only_reads_primary_env_and_does_not_connect(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in formal DDL live rehearsal check")

    monkeypatch.setattr(socket, "socket", fail_socket)
    result = live.check_environment(env={}, driver_available=False)

    assert result["mode"] == "check"
    assert result["dsn_present"] is False
    assert result["dsn_source"] == "skip"
    assert result["driver_available"] is False
    assert result["will_apply"] is False
    assert result["default_tests_require_postgres"] is False


def test_check_ignores_legacy_dsn_names() -> None:
    result = live.check_environment(
        env={
            LEGACY_ENV_DSN: "postgresql://legacy/example",
            live.PRIMARY_ENV_DSN: "postgresql://primary/example",
        },
        driver_available=True,
    )

    assert result["dsn_present"] is True
    assert result["dsn_source"] == f"env:{live.PRIMARY_ENV_DSN}"
    assert "legacy" not in live.report_as_json(result)

    legacy_only = live.check_environment(env={LEGACY_ENV_DSN: "postgresql://legacy/example"})
    assert legacy_only["dsn_present"] is False
    assert legacy_only["dsn_source"] == "skip"


def test_reports_contain_no_blocked_terms() -> None:
    reports = [
        live.build_contract_report(),
        live.check_environment(env={}, driver_available=False),
        live.build_apply_skip_report(
            reason=f"{live.PRIMARY_ENV_DSN} is not set",
            dsn_present=False,
            driver_available=False,
        ),
    ]

    for report in reports:
        text = live.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_schema_prefix_guard_rejects_reserved_or_invalid_values() -> None:
    for value in ["", "bad-name", "1bad", "public", "postgres", "pg_catalog", "information_schema"]:
        with pytest.raises(ValueError):
            live.validate_schema_prefix(value)


def test_schema_generation_always_adds_random_suffix() -> None:
    schema = live.generate_schema_name("emperor_eval_formal_live", token="a1b2c3d4e5")

    assert schema == "emperor_eval_formal_live_a1b2c3d4e5"
    assert schema != "emperor_eval_formal_live"
    assert live.generate_schema_name("emperor_eval_formal_live") != live.generate_schema_name(
        "emperor_eval_formal_live"
    )


def test_apply_without_dsn_returns_skip_report_and_does_not_connect(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden before apply preflight passes")

    monkeypatch.delenv(live.PRIMARY_ENV_DSN, raising=False)
    monkeypatch.setattr(socket, "socket", fail_socket)
    assert live.main(["--apply", "--schema-prefix", "emperor_eval_formal_live", "--drop-schema-after"]) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "apply"
    assert payload["dsn_present"] is False
    assert payload["passed"] is False
    assert payload["created_schema"] is False
    assert payload["failed"] == [f"{live.PRIMARY_ENV_DSN} is not set"]


def test_apply_without_psycopg_returns_skip_report_and_does_not_connect(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden when psycopg is unavailable")

    monkeypatch.setenv(live.PRIMARY_ENV_DSN, "postgresql://example/db")
    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(live, "is_psycopg_available", lambda: False)

    assert live.main(["--apply", "--schema-prefix", "emperor_eval_formal_live", "--drop-schema-after"]) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "apply"
    assert payload["dsn_present"] is True
    assert payload["driver_available"] is False
    assert payload["passed"] is False
    assert payload["created_schema"] is False
    assert payload["failed"] == ["psycopg is not installed"]


def test_lint_failure_happens_before_database_connection(monkeypatch) -> None:
    def fail_connect(_dsn: str) -> object:
        raise AssertionError("database connection must not happen when lint fails")

    monkeypatch.setattr(live, "is_psycopg_available", lambda: True)
    monkeypatch.setattr(live.formal_ddl_rehearsal, "lint_sql", lambda _sql, _schema: {"passed": False})

    class FakePsycopg:
        @staticmethod
        def connect(dsn: str) -> object:
            return fail_connect(dsn)

    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)

    report = live.apply_live_rehearsal("postgresql://example/db", token="a1b2c3d4e5")

    assert report["passed"] is False
    assert report["failed"] == ["sql_lint_failed"]
    assert report["created_schema"] is False


def test_cli_contract_and_check_print_json(capsys) -> None:
    assert live.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert live.main(["--check"]) == 0
    check = json.loads(capsys.readouterr().out)
    assert check["mode"] == "check"
    assert check["will_apply"] is False


def test_source_uses_python_driver_and_forbids_shell_database_client_terms() -> None:
    source = (ROOT / "scripts" / "platform" / "formal_ddl_live_rehearsal.py").read_text(encoding="utf-8")

    assert "subprocess" + ".run" not in source
    assert '"p' + 'sql"' not in source
    assert LEGACY_ENV_DSN not in source
    assert "import psycopg" in source
    assert live.PRIMARY_ENV_DSN in source


def test_guard_paths_use_utf8_chinese_names() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    protected_paths = {path.as_posix() for path in FORBIDDEN_PATHS}

    assert any(path.endswith("docs/皇帝综合评价体系评分标准.md") for path in protected_paths)
    assert any(path.endswith("docs/分项规则") for path in protected_paths)
    assert any(path.endswith("docs/证据规则") for path in protected_paths)
    for mojibake in ["\u9428\u56e7\u7b23", "\u9352\u55cc\u300d", "\u7487\u4f7a\u5d41"]:
        assert mojibake not in source


@pytest.mark.db
@pytest.mark.integration
def test_live_apply_rehearsal_applies_verifies_and_cleans_up() -> None:
    resolved = live.resolve_dsn(env=os.environ)
    reason = live.integration_skip_reason(resolved)
    if reason:
        pytest.skip(reason)

    report = live.apply_live_rehearsal(
        resolved.dsn or "",
        schema_prefix="emperor_eval_formal_live_pytest",
        drop_schema_after=True,
    )

    assert report["passed"] is True
    assert report["sql_lint_passed"] is True
    assert set(report["existing_expected_tables"]) == set(live.EXPECTED_TABLES)
    assert report["missing_expected_tables"] == []
    assert report["existing_forbidden_tables"] == []
    assert report["phase_1_table_count"] == len(PHASE_1_BASE_TABLES)
    assert report["phase_2_forbidden_table_count"] == 0
    assert report["phase_3_forbidden_table_count"] == 0
    assert report["dropped"] is True
    assert report["schema_exists_after_drop"] is False
    assert report["cleanup_verified"] is True


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
