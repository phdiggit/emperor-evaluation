from __future__ import annotations

import json
import re
import socket
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import production_schema_live_apply_entrypoint_guard as guard  # noqa: E402


SCHEMA_PATHS = [
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
]
REQUIRED_FLAGS = {
    "live_apply_entrypoint_guard_only": True,
    "schema_files_modified": False,
    "schema_files_read_only": True,
    "schema_files_byte_identical_required": True,
    "production_schema_hashes_rendered": True,
    "live_apply_approved": False,
    "live_apply_executed": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "production_seed_executed": False,
    "seed_apply_executed": False,
    "ready_for_live_apply": False,
    "ready_for_production_migration": False,
    "future_live_apply_execution_pr_required": True,
    "future_seed_apply_pr_required": True,
}
SQL_CLIENT = "p" + "sql"
FORBIDDEN_SOURCE_TOKENS = [
    "subprocess",
    "psycopg",
    "asyncpg",
    "sqlalchemy",
    "os.environ",
    "PG_SEARCH_BENCH_DSN",
    "EMPEROR_EVAL_PG_DSN",
]


def test_request_json_has_required_flags_and_schema_fingerprints_only() -> None:
    report = guard.render_live_apply_request_json()

    assert report["pr_number"] == 282
    assert report["scope"] == "production_schema_live_apply_entrypoint_guard_only"
    assert report["required_flags"] == REQUIRED_FLAGS
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected
    assert report["ready_for_live_apply"] is False
    assert report["ready_for_production_migration"] is False
    assert report["future_live_apply_execution_pr_required"] is True
    assert report["future_seed_apply_pr_required"] is True
    _assert_fingerprints_metadata_only(report["schema_file_fingerprints"])


def test_contract_report_includes_sources_modes_and_forbidden_actions() -> None:
    report = guard.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["status"] == "Proposed / Production schema live-apply entrypoint guard only"
    assert set(report["supported_modes"]) == {
        "contract-report",
        "entrypoint-guard-report",
        "render-live-apply-request-json",
        "render-operator-runbook-md",
        "lint-entrypoint-guard-report",
        "adr-check",
    }
    assert "db/schema.sql" in report["source_inputs"]
    assert "db/postgres/001_init.sql" in report["source_inputs"]
    assert "read_production_dsn" in report["forbidden_actions"]
    assert "execute_live_apply" in report["forbidden_actions"]


def test_cli_modes_print_expected_output_and_do_not_modify_schema(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in SCHEMA_PATHS}

    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--entrypoint-guard-report"], "entrypoint-guard-report"),
        (["--render-live-apply-request-json"], "render-live-apply-request-json"),
        (["--lint-entrypoint-guard-report"], "lint-entrypoint-guard-report"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert guard.main(args) == 0
        assert json.loads(buffer.getvalue())["mode"] == mode

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert guard.main(["--render-operator-runbook-md"]) == 0
    assert "THIS RUNBOOK IS NOT AN EXECUTION APPROVAL." in buffer.getvalue()

    after = {path: _mtime(path) for path in SCHEMA_PATHS}
    assert after == before


def test_schema_files_are_byte_identical_and_anchor_table_exists() -> None:
    assert guard.schema_files_byte_identical() is True
    assert guard.schema_table_sets_same() is True
    assert guard.anchors_table_exists() is True
    texts = [path.read_text(encoding="utf-8") for path in SCHEMA_PATHS]

    assert texts[0] == texts[1]
    assert "CREATE TABLE anchors (" in texts[0]
    assert "anchors" in guard.created_tables(texts[0])


def test_schema_fingerprints_do_not_include_raw_schema_text() -> None:
    report_text = guard.report_as_json(guard.render_live_apply_request_json())
    schema_text = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    first_non_empty = next(line.strip() for line in schema_text.splitlines() if line.strip())

    assert "CREATE TABLE" not in report_text
    assert "INSERT INTO" not in report_text
    assert first_non_empty not in report_text
    _assert_fingerprints_metadata_only(guard.schema_file_fingerprints())


def test_operator_runbook_contains_required_warning_and_no_execution_material() -> None:
    runbook = guard.render_operator_runbook_md()
    lowered = runbook.lower()

    for needle in [
        "THIS RUNBOOK IS NOT AN EXECUTION APPROVAL.",
        "NO DSN IS READ BY THIS PR.",
        "NO SQL IS EXECUTED BY THIS PR.",
        "FUTURE LIVE APPLY EXECUTION PR REQUIRED.",
    ]:
        assert needle in runbook
    for forbidden in [
        SQL_CLIENT,
        "postgres://",
        "postgresql://",
        "password=",
        "connection string",
        "CREATE TABLE",
        "ALTER TABLE",
        "INSERT INTO",
        "COPY ",
        "LOAD DATA",
        "apply-ready command",
        "EMPEROR_EVAL_PG_DSN",
        "PG_SEARCH_BENCH_DSN",
    ]:
        assert forbidden.lower() not in lowered


def test_lint_fails_for_required_flag_drift() -> None:
    for key, expected in REQUIRED_FLAGS.items():
        report = guard.render_live_apply_request_json()
        report[key] = not expected
        lint = guard.lint_entrypoint_guard_report(report)
        assert lint["passed"] is False
        assert f"{key}_{str(expected).lower()}" in lint["failed"]

        report = guard.render_live_apply_request_json()
        report["required_flags"][key] = not expected
        lint = guard.lint_entrypoint_guard_report(report)
        assert lint["passed"] is False
        assert f"{key}_{str(expected).lower()}" in lint["failed"]


def test_lint_fails_for_injected_blocking_values() -> None:
    injected_by_rule = {
        "live_apply_executed_false": ("live_apply_executed", True),
        "production_db_connected_false": ("production_db_connected", True),
        "production_dsn_read_false": ("production_dsn_read", True),
        "ready_for_live_apply_false": ("ready_for_live_apply", True),
        "ready_for_production_migration_false": ("ready_for_production_migration", True),
    }
    for expected_rule, (key, injected) in injected_by_rule.items():
        report = guard.render_live_apply_request_json()
        report[key] = injected
        lint = guard.lint_entrypoint_guard_report(report)
        assert lint["passed"] is False
        assert expected_rule in lint["failed"]

    injected_text_by_rule = {
        "no_connection_material": ["postgresql://example"],
        "no_seed_or_data_load": ["INSERT INTO demo VALUES (1)"],
        "no_execution_hints": [f"{SQL_CLIENT} command", "sub" + "process command"],
    }
    for expected_rule, values in injected_text_by_rule.items():
        for value in values:
            report = guard.render_live_apply_request_json()
            report["warnings"] = [value]
            lint = guard.lint_entrypoint_guard_report(report)
            assert lint["passed"] is False
            assert expected_rule in lint["failed"]


def test_lint_fails_if_fingerprint_contains_extra_schema_material() -> None:
    report = guard.render_live_apply_request_json()
    report["schema_file_fingerprints"][0]["schema_text"] = "CREATE TABLE demo (id bigint);"

    lint = guard.lint_entrypoint_guard_report(report)

    assert lint["passed"] is False
    assert "schema_fingerprints_are_metadata_only" in lint["failed"]


def test_entrypoint_guard_report_blocks_nothing_when_clean() -> None:
    report = guard.build_entrypoint_guard_report()

    assert report["entrypoint_guard_lint_passed"] is True
    assert report["blocking_failures"] == []
    assert report["schema_consistency"] == {
        "byte_identical": True,
        "table_sets_same": True,
        "anchors_table_exists": True,
    }


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-production-schema-live-apply-entrypoint-guard.md"

    assert path.is_file()
    check = guard.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert guard.status_value(path.read_text(encoding="utf-8")) == (
        "Proposed / Production schema live-apply entrypoint guard only"
    )


def test_adr_check_fails_for_live_apply_or_ready_claim(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-production-schema-live-apply-entrypoint-guard.md"
    base = (ROOT / "archive" / "docs" / "adr" / "ADR-production-schema-live-apply-entrypoint-guard.md").read_text(
        encoding="utf-8"
    )
    for injected in [
        "live_apply_executed=true",
        "production_db_connected=true",
        "production_dsn_read=true",
        "ready_for_live_apply=true",
        "ready_for_production_migration=true",
    ]:
        adr.write_text(base + f"\n\n{injected}\n", encoding="utf-8")
        check = guard.build_adr_check(adr)
        assert check["passed"] is False
        assert "no_completion_or_ready_claim" in check["failed"]


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (ROOT / "scripts" / "platform" / "production_schema_live_apply_entrypoint_guard.py").read_text(
        encoding="utf-8"
    )

    for forbidden in FORBIDDEN_SOURCE_TOKENS:
        assert forbidden not in source
    assert "subprocess.run" not in source


def _assert_fingerprints_metadata_only(fingerprints: list[dict[str, object]]) -> None:
    assert [item["path"] for item in fingerprints] == ["db/schema.sql", "db/postgres/001_init.sql"]
    for item in fingerprints:
        assert set(item) == {"path", "sha256", "line_count", "table_count", "read_only"}
        assert item["read_only"] is True
        assert re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"]))
        assert isinstance(item["line_count"], int)
        assert isinstance(item["table_count"], int)
        assert item["line_count"] > 0
        assert item["table_count"] > 0


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in production schema live-apply entrypoint guard")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
