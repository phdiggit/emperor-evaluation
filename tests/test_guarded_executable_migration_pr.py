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

from scripts.platform import guarded_executable_migration_pr as guarded  # noqa: E402


SQL_CLIENT = "p" + "sql"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PROTECTED_SCHEMA_PATHS = [
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
]
REQUIRED_FLAGS = {
    "guarded_executable_migration_pr_proposal_only": True,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_change_pr_approved": False,
    "schema_files_modified": False,
    "migration_sql_executable_in_this_pr": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "human_signoffs_recorded": False,
    "ready_for_production_migration": False,
    "future_schema_change_pr_requires_explicit_user_approval": True,
    "future_live_apply_pr_required": True,
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


def test_render_proposal_json_has_required_flags() -> None:
    report = guarded.render_proposal_json()

    assert report["pr_number"] == 276
    assert report["title"] == "platform: add guarded executable migration PR proposal"
    assert report["scope"] == "guarded_executable_migration_pr_proposal_only"
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected
    assert report["db_touching"] is False
    assert report["dsn_required"] is False
    assert report["human_approval_required_before_execution"] is True
    assert "blocked_pr_body_template" in report["allowed_outputs"]
    assert "claim_production_migration_approval" in report["forbidden_actions"]


def test_cli_render_proposal_json_outputs_valid_json(capsys) -> None:
    assert guarded.main(["--render-proposal-json"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["scope"] == "guarded_executable_migration_pr_proposal_only"
    for key, expected in REQUIRED_FLAGS.items():
        assert payload[key] is expected


def test_lint_proposal_report_passes_for_default_report() -> None:
    report = guarded.lint_proposal_report()

    assert report["mode"] == "lint-proposal-report"
    assert report["passed"] is True
    assert report["failed"] == []


def test_proposal_report_includes_machine_readable_flags() -> None:
    report = guarded.build_proposal_report()

    assert report["mode"] == "proposal-report"
    assert report["proposal_lint_passed"] is True
    assert report["blocking_failures"] == []
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected


def test_contract_report_is_static_and_offline(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    report = guarded.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["proposal_version"] == "guarded-executable-migration-pr-proposal-v1"
    assert report["required_flags"] == REQUIRED_FLAGS
    assert "future PR body template is blocked-by-default" in report["guard_checklist"]
    assert "does not approve schema-changing migration PR" in report["non_goals"]


def test_cli_modes_print_expected_output_and_do_not_touch_schema(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--proposal-report"], "proposal-report"),
        (["--render-proposal-json"], "render-proposal-json"),
        (["--lint-proposal-report"], "lint-proposal-report"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert guarded.main(args) == 0
        assert json.loads(buffer.getvalue())["mode"] == mode

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert guarded.main(["--render-pr-body-template"]) == 0
    assert "## Required approvals" in buffer.getvalue()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def test_lint_fails_if_required_false_flags_are_changed() -> None:
    failure_cases = [
        ("production_migration_approved", "production_migration_approved_false"),
        ("schema_change_pr_approved", "schema_change_pr_approved_false"),
        ("schema_files_modified", "schema_files_modified_false"),
        ("sql_executed", "sql_executed_false"),
        ("production_db_connected", "production_db_connected_false"),
        ("human_signoffs_recorded", "human_signoffs_recorded_false"),
        ("ready_for_production_migration", "ready_for_production_migration_false"),
    ]

    for flag, failed_rule in failure_cases:
        report = guarded.render_proposal_json()
        report[flag] = True
        lint = guarded.lint_proposal_report(report)
        assert lint["passed"] is False
        assert failed_rule in lint["failed"]


def test_lint_fails_if_connection_material_or_sql_client_is_injected() -> None:
    report = guarded.render_proposal_json()
    report["warnings"] = ["postgresql://example"]

    lint = guarded.lint_proposal_report(report)

    assert lint["passed"] is False
    assert "no_connection_material_values" in lint["failed"]

    report = guarded.render_proposal_json()
    report["warnings"] = [f"{SQL_CLIENT} command"]
    lint = guarded.lint_proposal_report(report)
    assert "no_sql_client_instruction" in lint["failed"]


def test_render_pr_body_template_is_blocked_by_default() -> None:
    template = guarded.render_pr_body_template()

    for needle in [
        "## Scope",
        "## Required approvals",
        "Explicit user approval for schema file modification: NOT RECORDED IN THIS PR",
        "Human schema reviewer sign-off: PLACEHOLDER ONLY",
        "Migration operator sign-off: PLACEHOLDER ONLY",
        "Rollback owner sign-off: PLACEHOLDER ONLY",
        "Final maintainer sign-off: PLACEHOLDER ONLY",
        "## Non-execution guarantees for this proposal PR",
        "Does not execute migration SQL.",
        "Does not execute production seed.",
        "Does not connect to PostgreSQL.",
        f"Does not read {PRIMARY_ENV_DSN} or {LEGACY_ENV_DSN}.",
        "Does not modify db/schema.sql or db/postgres/001_init.sql.",
        "Does not forge human sign-offs.",
        "ready_for_production_migration=false in this proposal PR.",
        "## Files changed",
        "## Tests",
        "## Rollback / restore plan",
        "Placeholder only; no command executed by this proposal PR.",
    ]:
        assert needle in template
    assert SQL_CLIENT not in template
    assert "postgresql://" not in template


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-guarded-executable-migration-pr.md"

    assert path.is_file()
    check = guarded.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert guarded.status_value(path.read_text(encoding="utf-8")) == "Proposed / Guarded proposal only"


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "archive" / "docs" / "adr" / "ADR-guarded-executable-migration-pr.md").read_text(encoding="utf-8")
    normalized = guarded.normalize_text(content)
    for needle in [
        "guarded proposal only",
        "No production migration execution",
        "No production seed execution",
        "No schema modification",
        "No DB connection",
        "No DSN access",
        "No human sign-off forged",
        "explicit user approval required for future schema-changing PR",
        "guarded_executable_migration_pr_proposal_only=true",
        "schema_change_pr_approved=false",
        "ready_for_production_migration=false",
    ]:
        assert guarded.normalize_text(needle) in normalized


def test_adr_check_fails_when_required_semantics_are_missing(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-guarded-executable-migration-pr.md"
    adr.write_text("# ADR\n\n## Status\n\nProposed / Guarded proposal only\n", encoding="utf-8")

    check = guarded.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_proposal_only" in check["failed"]
    assert "future_schema_change_pr_requires_explicit_user_approval" in check["failed"]


def test_adr_check_fails_if_approval_is_claimed(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-guarded-executable-migration-pr.md"
    adr.write_text(
        (ROOT / "archive" / "docs" / "adr" / "ADR-guarded-executable-migration-pr.md").read_text(encoding="utf-8")
        + "\n\nschema_change_pr_approved=true\n",
        encoding="utf-8",
    )

    check = guarded.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_approval_or_execution_claim" in check["failed"]


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (ROOT / "scripts" / "platform" / "guarded_executable_migration_pr.py").read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_SOURCE_TOKENS:
        assert forbidden not in source
    assert SQL_CLIENT not in source


def test_proposal_does_not_touch_protected_schema_path_mtimes() -> None:
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    guarded.build_contract_report()
    guarded.render_proposal_json()
    guarded.build_proposal_report()
    guarded.lint_proposal_report()
    guarded.render_pr_body_template()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in guarded executable migration PR proposal")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
