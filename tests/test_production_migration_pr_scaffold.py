from __future__ import annotations

import json
import socket
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import production_migration_pr_scaffold as scaffold  # noqa: E402


SQL_CLIENT = "p" + "sql"
PROTECTED_SCHEMA_PATHS = [
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
]
REQUIRED_FLAGS = {
    "production_migration_pr_scaffold_only": True,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_files_modified": False,
    "sql_executed": False,
    "production_db_connected": False,
    "human_signoffs_recorded": False,
    "ready_for_production_migration": False,
    "future_executable_migration_pr_required": True,
}
FORBIDDEN_SOURCE_TOKENS = [
    "subprocess",
    "psycopg",
    "asyncpg",
    "sqlalchemy",
    "PG_SEARCH_BENCH_DSN",
    "EMPEROR_EVAL_PG_DSN",
    "os.environ",
]


def test_render_scaffold_json_has_required_flags() -> None:
    report = scaffold.render_scaffold_json()

    assert report["pr_number"] == 275
    assert report["title"] == "platform: add production migration PR scaffold"
    assert report["scope"] == "production_migration_pr_scaffold_only"
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected
    assert report["db_touching"] is False
    assert report["dsn_required"] is False
    assert report["human_approval_required_before_execution"] is True
    assert "stdout_report" in report["allowed_outputs"]
    assert "forge_human_signoff" in report["forbidden_actions"]


def test_cli_render_scaffold_json_outputs_valid_json(capsys) -> None:
    assert scaffold.main(["--render-scaffold-json"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["scope"] == "production_migration_pr_scaffold_only"
    for key, expected in REQUIRED_FLAGS.items():
        assert payload[key] is expected


def test_lint_scaffold_report_passes_for_default_report() -> None:
    report = scaffold.lint_scaffold_report()

    assert report["mode"] == "lint-scaffold-report"
    assert report["passed"] is True
    assert report["failed"] == []


def test_scaffold_report_includes_machine_readable_flags() -> None:
    report = scaffold.build_scaffold_report()

    assert report["mode"] == "scaffold-report"
    assert report["scaffold_lint_passed"] is True
    assert report["blocking_failures"] == []
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected


def test_contract_report_is_static_and_offline(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    report = scaffold.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["scaffold_version"] == "production-migration-pr-scaffold-v1"
    assert report["required_flags"] == REQUIRED_FLAGS
    assert "human sign-off placeholders are named" in report["scaffold_checklist"]
    assert "does not connect to PostgreSQL" in report["non_goals"]


def test_cli_modes_print_json_and_do_not_touch_schema(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--scaffold-report"], "scaffold-report"),
        (["--render-scaffold-json"], "render-scaffold-json"),
        (["--lint-scaffold-report"], "lint-scaffold-report"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert scaffold.main(args) == 0
        assert json.loads(buffer.getvalue())["mode"] == mode

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def test_lint_fails_if_required_flags_are_changed() -> None:
    report = scaffold.render_scaffold_json()
    report["production_migration_approved"] = True
    report["ready_for_production_migration"] = True
    report["human_signoffs_recorded"] = True

    lint = scaffold.lint_scaffold_report(report)

    assert lint["passed"] is False
    assert "production_migration_approved_false" in lint["failed"]
    assert "ready_for_production_migration_false" in lint["failed"]
    assert "human_signoffs_recorded_false" in lint["failed"]
    assert "no_human_signoff_forged" in lint["failed"]


def test_lint_fails_if_connection_material_or_sql_client_is_injected() -> None:
    report = scaffold.render_scaffold_json()
    report["warnings"] = ["postgresql://example"]

    lint = scaffold.lint_scaffold_report(report)

    assert lint["passed"] is False
    assert "no_connection_material_values" in lint["failed"]

    report = scaffold.render_scaffold_json()
    report["warnings"] = [f"{SQL_CLIENT} command"]
    lint = scaffold.lint_scaffold_report(report)
    assert "no_sql_client_instruction" in lint["failed"]


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "docs" / "adr" / "ADR-production-migration-pr-scaffold.md"

    assert path.is_file()
    check = scaffold.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert scaffold.status_value(path.read_text(encoding="utf-8")) == "Proposed / Scaffold only"


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "docs" / "adr" / "ADR-production-migration-pr-scaffold.md").read_text(encoding="utf-8")
    normalized = scaffold.normalize_text(content)
    for needle in [
        "scaffold only",
        "No production migration execution",
        "No production seed execution",
        "No DB connection",
        "No DSN access",
        "No human sign-off forged",
        "future executable migration PR required",
        "production_migration_pr_scaffold_only=true",
        "production_migration_approved=false",
        "ready_for_production_migration=false",
    ]:
        assert scaffold.normalize_text(needle) in normalized


def test_adr_check_fails_when_required_semantics_are_missing(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-production-migration-pr-scaffold.md"
    adr.write_text("# ADR\n\n## Status\n\nProposed / Scaffold only\n", encoding="utf-8")

    check = scaffold.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_scaffold_only" in check["failed"]
    assert "future_executable_migration_pr_required" in check["failed"]


def test_adr_check_fails_if_approval_is_claimed(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-production-migration-pr-scaffold.md"
    adr.write_text(
        (ROOT / "docs" / "adr" / "ADR-production-migration-pr-scaffold.md").read_text(encoding="utf-8")
        + "\n\nproduction_migration_approved=true\n",
        encoding="utf-8",
    )

    check = scaffold.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_approval_or_execution_claim" in check["failed"]


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (ROOT / "scripts" / "platform" / "production_migration_pr_scaffold.py").read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_SOURCE_TOKENS:
        assert forbidden not in source
    assert SQL_CLIENT not in source


def test_scaffold_does_not_touch_protected_schema_path_mtimes() -> None:
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    scaffold.build_contract_report()
    scaffold.render_scaffold_json()
    scaffold.build_scaffold_report()
    scaffold.lint_scaffold_report()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in production migration PR scaffold")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
