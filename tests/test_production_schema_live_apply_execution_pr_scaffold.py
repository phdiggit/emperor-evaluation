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

from scripts.platform import production_schema_live_apply_execution_pr_scaffold as scaffold  # noqa: E402


SCHEMA_PATHS = [
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
]
REQUIRED_FLAGS = {
    "live_apply_execution_pr_scaffold_only": True,
    "schema_files_modified": False,
    "schema_files_read_only": True,
    "schema_files_byte_identical_required": True,
    "production_schema_hashes_rendered": True,
    "live_apply_pr_approved": False,
    "live_apply_executed": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "production_seed_executed": False,
    "seed_apply_executed": False,
    "operator_evidence_recorded": False,
    "human_signoffs_recorded": False,
    "ready_for_live_apply": False,
    "ready_for_production_migration": False,
    "future_live_apply_execution_pr_required": True,
    "future_seed_apply_pr_required": True,
}
SQL_CLIENT = "p" + "sql"
SHELL_PROCESS_TOKEN = "sub" + "process"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
FORBIDDEN_SOURCE_TOKENS = [
    SHELL_PROCESS_TOKEN,
    "psycopg",
    "asyncpg",
    "sqlalchemy",
    "os.environ",
    PRIMARY_ENV_DSN,
    LEGACY_ENV_DSN,
]


def test_execution_request_json_has_required_flags_and_metadata_fingerprints() -> None:
    report = scaffold.render_execution_request_json()

    assert report["pr_number"] == 283
    assert report["title"] == "platform: add production schema live-apply execution PR scaffold"
    assert report["scope"] == "production_schema_live_apply_execution_pr_scaffold_only"
    assert report["required_flags"] == REQUIRED_FLAGS
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected
    assert report["schema_consistency"] == {
        "byte_identical": True,
        "table_sets_same": True,
        "anchors_table_exists": True,
    }
    _assert_fingerprints_metadata_only(report["schema_file_fingerprints"])


def test_contract_report_declares_modes_sources_and_forbidden_actions() -> None:
    report = scaffold.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["status"] == "Proposed / Production schema live-apply execution PR scaffold only"
    assert set(report["supported_modes"]) == {
        "contract-report",
        "execution-scaffold-report",
        "render-execution-request-json",
        "render-future-pr-body-template",
        "render-operator-evidence-template-md",
        "lint-execution-scaffold-report",
        "adr-check",
    }
    assert "db/schema.sql" in report["source_inputs"]
    assert "db/postgres/001_init.sql" in report["source_inputs"]
    assert "execute_sql" in report["forbidden_actions"]
    assert "read_production_dsn" in report["forbidden_actions"]
    assert "forge_human_signoff" in report["forbidden_actions"]


def test_cli_modes_return_json_or_markdown_and_do_not_modify_schema(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in SCHEMA_PATHS}

    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--execution-scaffold-report"], "execution-scaffold-report"),
        (["--render-execution-request-json"], "render-execution-request-json"),
        (["--lint-execution-scaffold-report"], "lint-execution-scaffold-report"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert scaffold.main(args) == 0
        assert json.loads(buffer.getvalue())["mode"] == mode

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert scaffold.main(["--render-future-pr-body-template"]) == 0
    assert "BLOCKED BY DEFAULT." in buffer.getvalue()

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert scaffold.main(["--render-operator-evidence-template-md"]) == 0
    assert "TEMPLATE ONLY. NO APPROVAL IS RECORDED HERE." in buffer.getvalue()

    after = {path: _mtime(path) for path in SCHEMA_PATHS}
    assert after == before


def test_schema_files_are_read_only_byte_identical_and_have_same_tables() -> None:
    before = {path: _mtime(path) for path in SCHEMA_PATHS}

    assert scaffold.schema_files_byte_identical() is True
    assert scaffold.schema_table_sets_same() is True
    assert scaffold.anchors_table_exists() is True
    texts = [path.read_text(encoding="utf-8") for path in SCHEMA_PATHS]
    assert texts[0] == texts[1]
    assert set(scaffold.created_tables(texts[0])) == set(scaffold.created_tables(texts[1]))
    assert "anchors" in scaffold.created_tables(texts[0])

    after = {path: _mtime(path) for path in SCHEMA_PATHS}
    assert after == before


def test_schema_fingerprints_do_not_include_raw_schema_text() -> None:
    report_text = scaffold.report_as_json(scaffold.render_execution_request_json())
    schema_text = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    first_table_line = next(line.strip() for line in schema_text.splitlines() if line.strip().startswith("CREATE TABLE"))

    assert "CREATE TABLE" not in report_text
    assert "ALTER TABLE" not in report_text
    assert "INSERT INTO" not in report_text
    assert first_table_line not in report_text
    _assert_fingerprints_metadata_only(scaffold.schema_file_fingerprints())


def test_future_pr_body_template_is_blocked_by_default_and_non_executing() -> None:
    body = scaffold.render_future_pr_body_template()
    lowered = body.lower()

    for needle in [
        "BLOCKED BY DEFAULT.",
        "It does not approve live apply.",
        "It does not execute SQL.",
        "It does not connect to PostgreSQL.",
        "It does not read DSN material.",
        "It does not execute production seed.",
        "`ready_for_live_apply=false`.",
        "`ready_for_production_migration=false`.",
        "Future live apply execution PR remains required.",
        "Future seed apply PR remains required.",
    ]:
        assert needle in body
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
        PRIMARY_ENV_DSN,
        LEGACY_ENV_DSN,
    ]:
        assert forbidden.lower() not in lowered


def test_operator_evidence_template_records_no_approval_or_signoff() -> None:
    template = scaffold.render_operator_evidence_template_md()
    lowered = template.lower()

    assert "TEMPLATE ONLY. NO APPROVAL IS RECORDED HERE." in template
    assert "placeholder only" in lowered
    assert "not recorded by this scaffold" in lowered
    assert "ready_for_live_apply: `false`" in template
    assert "ready_for_production_migration: `false`" in template
    assert "approved by" not in lowered
    assert "signed by" not in lowered


def test_lint_fails_for_required_flag_drift() -> None:
    for key, expected in REQUIRED_FLAGS.items():
        report = scaffold.render_execution_request_json()
        report[key] = not expected
        lint = scaffold.lint_execution_scaffold_report(report)
        assert lint["passed"] is False
        assert f"{key}_{str(expected).lower()}" in lint["failed"]

        report = scaffold.render_execution_request_json()
        report["required_flags"][key] = not expected
        lint = scaffold.lint_execution_scaffold_report(report)
        assert lint["passed"] is False
        assert f"{key}_{str(expected).lower()}" in lint["failed"]


def test_lint_fails_for_injected_blocking_values() -> None:
    injected_by_rule = {
        "live_apply_executed_false": ("live_apply_executed", True),
        "sql_executed_false": ("sql_executed", True),
        "production_db_connected_false": ("production_db_connected", True),
        "production_dsn_read_false": ("production_dsn_read", True),
        "ready_for_live_apply_false": ("ready_for_live_apply", True),
        "ready_for_production_migration_false": ("ready_for_production_migration", True),
    }
    for expected_rule, (key, injected) in injected_by_rule.items():
        report = scaffold.render_execution_request_json()
        report[key] = injected
        lint = scaffold.lint_execution_scaffold_report(report)
        assert lint["passed"] is False
        assert expected_rule in lint["failed"]

    injected_text_by_rule = {
        "no_connection_material": ["postgresql://example", "password=example"],
        "no_seed_or_data_load": ["INSERT INTO demo VALUES (1)", "COPY demo FROM STDIN"],
        "no_execution_hints": [f"{SQL_CLIENT} command", SHELL_PROCESS_TOKEN + " command", "apply-ready command"],
        "no_completion_claim": ["production migration completed"],
    }
    for expected_rule, values in injected_text_by_rule.items():
        for value in values:
            report = scaffold.render_execution_request_json()
            report["warnings"] = [value]
            lint = scaffold.lint_execution_scaffold_report(report)
            assert lint["passed"] is False
            assert expected_rule in lint["failed"]


def test_lint_fails_if_fingerprint_contains_schema_material() -> None:
    report = scaffold.render_execution_request_json()
    report["schema_file_fingerprints"][0]["schema_text"] = "CREATE TABLE demo (id bigint);"

    lint = scaffold.lint_execution_scaffold_report(report)

    assert lint["passed"] is False
    assert "schema_fingerprints_are_metadata_only" in lint["failed"]


def test_execution_scaffold_report_is_clean_when_default() -> None:
    report = scaffold.build_execution_scaffold_report()

    assert report["mode"] == "execution-scaffold-report"
    assert report["execution_scaffold_lint_passed"] is True
    assert report["blocking_failures"] == []
    assert report["schema_consistency"]["byte_identical"] is True
    assert report["schema_consistency"]["anchors_table_exists"] is True


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-production-schema-live-apply-execution-pr-scaffold.md"

    assert path.is_file()
    check = scaffold.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert scaffold.status_value(path.read_text(encoding="utf-8")) == (
        "Proposed / Production schema live-apply execution PR scaffold only"
    )


def test_adr_check_fails_for_ready_executed_connected_or_completed_claims(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-production-schema-live-apply-execution-pr-scaffold.md"
    base = (ROOT / "archive" / "docs" / "adr" / "ADR-production-schema-live-apply-execution-pr-scaffold.md").read_text(
        encoding="utf-8"
    )
    for injected in [
        "live_apply_executed=true",
        "sql_executed=true",
        "production_db_connected=true",
        "production_dsn_read=true",
        "ready_for_live_apply=true",
        "ready_for_production_migration=true",
        "production migration completed",
        "seed apply completed",
    ]:
        adr.write_text(base + f"\n\n{injected}\n", encoding="utf-8")
        check = scaffold.build_adr_check(adr)
        assert check["passed"] is False
        assert "no_ready_executed_connected_or_completed_claim" in check["failed"]


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (
        Path(scaffold.__file__)
    ).read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_SOURCE_TOKENS:
        assert forbidden not in source
    assert "subprocess.run" not in source


def test_builders_do_not_use_network(monkeypatch) -> None:
    _guard_network(monkeypatch)

    scaffold.build_contract_report()
    scaffold.render_execution_request_json()
    scaffold.build_execution_scaffold_report()
    scaffold.render_future_pr_body_template()
    scaffold.render_operator_evidence_template_md()
    scaffold.lint_execution_scaffold_report()
    scaffold.build_adr_check()


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
        raise AssertionError("network access is forbidden in production schema live-apply execution PR scaffold")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
