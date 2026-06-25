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

from scripts.platform import schema_change_pr_prep_pack as prep  # noqa: E402


SQL_CLIENT = "p" + "sql"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PROTECTED_SCHEMA_PATHS = [
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
]
REQUIRED_FLAGS = {
    "schema_change_pr_prep_pack_only": True,
    "schema_change_pr_approved": False,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_files_modified": False,
    "migration_sql_executable_in_this_pr": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "human_signoffs_recorded": False,
    "ready_for_schema_change_pr": False,
    "ready_for_production_migration": False,
    "future_schema_change_pr_required": True,
    "future_live_apply_pr_required": True,
    "future_seed_apply_pr_required": True,
}
FORBIDDEN_SOURCE_TOKENS = [
    "subprocess",
    "psycopg",
    "asyncpg",
    "sqlalchemy",
    "os.environ",
    "PG_SEARCH_BENCH_DSN",
    "EMPEROR_EVAL_PG_DSN",
]


def test_render_prep_json_has_required_flags() -> None:
    report = prep.render_prep_json()

    assert report["pr_number"] == 277
    assert report["title"] == "platform: add schema-change PR preparation pack"
    assert report["scope"] == "schema_change_pr_prep_pack_only"
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected
    assert report["db_touching"] is False
    assert report["dsn_required"] is False
    assert report["human_approval_required_before_schema_change"] is True
    assert "blocked_pr_body_template" in report["allowed_outputs"]


def test_cli_modes_print_expected_output_and_do_not_touch_schema(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--prep-pack-report"], "prep-pack-report"),
        (["--render-prep-json"], "render-prep-json"),
        (["--lint-prep-pack-report"], "lint-prep-pack-report"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert prep.main(args) == 0
        assert json.loads(buffer.getvalue())["mode"] == mode

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert prep.main(["--render-pr-body-template"]) == 0
    assert "## Explicit approval gate" in buffer.getvalue()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def test_prep_pack_report_lint_passes_and_has_no_blockers() -> None:
    report = prep.build_prep_pack_report()

    assert report["mode"] == "prep-pack-report"
    assert report["prep_pack_lint_passed"] is True
    assert report["prep_pack_lint_failed"] == []
    assert report["blocking_failures"] == []
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected


def test_lint_fails_if_required_false_flag_becomes_true() -> None:
    false_flags = [key for key, expected in REQUIRED_FLAGS.items() if expected is False]

    for flag in false_flags:
        report = prep.render_prep_json()
        report[flag] = True
        lint = prep.lint_prep_pack_report(report)
        assert lint["passed"] is False
        assert any(flag in failed for failed in lint["failed"])


def test_lint_fails_if_required_true_flag_becomes_false() -> None:
    true_flags = [key for key, expected in REQUIRED_FLAGS.items() if expected is True]

    for flag in true_flags:
        report = prep.render_prep_json()
        report[flag] = False
        lint = prep.lint_prep_pack_report(report)
        assert lint["passed"] is False
        assert any(flag in failed for failed in lint["failed"])


def test_lint_fails_if_connection_material_is_injected() -> None:
    for injected in ["postgresql://example", "postgres://example", "password=example"]:
        report = prep.render_prep_json()
        report["warnings"] = [injected]
        lint = prep.lint_prep_pack_report(report)
        assert lint["passed"] is False
        assert "no_connection_material_values" in lint["failed"]


def test_lint_fails_if_sql_client_or_shell_out_instruction_is_injected() -> None:
    report = prep.render_prep_json()
    report["warnings"] = [f"{SQL_CLIENT} command"]
    lint = prep.lint_prep_pack_report(report)
    assert lint["passed"] is False
    assert "no_sql_client_instruction" in lint["failed"]

    report = prep.render_prep_json()
    report["warnings"] = ["shell out command"]
    lint = prep.lint_prep_pack_report(report)
    assert lint["passed"] is False
    assert "no_shell_out_instruction" in lint["failed"]


def test_render_pr_body_template_is_blocked_by_default() -> None:
    template = prep.render_pr_body_template()

    for needle in [
        "## Scope",
        "## Explicit approval gate",
        "## Intended schema files",
        "## Proposed schema change summary",
        "## Migration SQL source",
        "## Rollback / restore plan",
        "## Non-execution guarantees for this preparation PR",
        "## Tests",
        "## Remaining separate opt-in work",
        "Explicit user approval for schema file modification: NOT RECORDED IN THIS PR",
        "Human schema reviewer sign-off: PLACEHOLDER ONLY",
        "Migration operator sign-off: PLACEHOLDER ONLY",
        "Rollback owner sign-off: PLACEHOLDER ONLY",
        "Final maintainer sign-off: PLACEHOLDER ONLY",
        "This preparation PR does not modify db/schema.sql or db/postgres/001_init.sql.",
        "This preparation PR does not execute migration SQL.",
        "This preparation PR does not connect to PostgreSQL.",
        "This preparation PR does not read production DSN.",
        "ready_for_schema_change_pr=false in this preparation PR.",
        "ready_for_production_migration=false in this preparation PR.",
        "Future live apply PR remains separate.",
        "Future seed apply PR remains separate.",
        "metric_records",
        "metric_releases",
        "downstream_release_tables",
        PRIMARY_ENV_DSN,
        LEGACY_ENV_DSN,
    ]:
        assert needle in template
    assert SQL_CLIENT not in template
    assert "postgresql://" not in template


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "docs" / "adr" / "ADR-schema-change-pr-prep-pack.md"

    assert path.is_file()
    check = prep.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert prep.status_value(path.read_text(encoding="utf-8")) == "Proposed / Preparation pack only"


def test_adr_check_fails_if_approval_or_ready_claim_is_added(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-schema-change-pr-prep-pack.md"
    base = (ROOT / "docs" / "adr" / "ADR-schema-change-pr-prep-pack.md").read_text(encoding="utf-8")
    for injected in ["schema_change_pr_approved=true", "ready_for_schema_change_pr=true"]:
        adr.write_text(base + f"\n\n{injected}\n", encoding="utf-8")
        check = prep.build_adr_check(adr)
        assert check["passed"] is False
        assert "no_approval_or_execution_ready_claim" in check["failed"]


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "docs" / "adr" / "ADR-schema-change-pr-prep-pack.md").read_text(encoding="utf-8")
    normalized = prep.normalize_text(content)
    for needle in [
        "Proposed / Preparation pack only",
        "No schema modification",
        "No DB connection",
        "No DSN access",
        "No executable SQL in this PR",
        "schema_change_pr_prep_pack_only=true",
        "schema_change_pr_approved=false",
        "ready_for_schema_change_pr=false",
        "future_seed_apply_pr_required=true",
    ]:
        assert prep.normalize_text(needle) in normalized


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (ROOT / "scripts" / "platform" / "schema_change_pr_prep_pack.py").read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_SOURCE_TOKENS:
        assert forbidden not in source
    assert SQL_CLIENT not in source


def test_builders_do_not_touch_protected_schema_path_mtimes_or_network(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    prep.build_contract_report()
    prep.render_prep_json()
    prep.build_prep_pack_report()
    prep.lint_prep_pack_report()
    prep.render_pr_body_template()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in schema-change PR preparation pack")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
