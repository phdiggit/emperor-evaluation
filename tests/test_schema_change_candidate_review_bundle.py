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

from scripts.platform import schema_change_candidate_review_bundle as bundle  # noqa: E402


SQL_CLIENT = "p" + "sql"
PROTECTED_SCHEMA_PATHS = [
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
]
REQUIRED_FLAGS = {
    "schema_change_candidate_review_bundle_only": True,
    "schema_change_pr_approved": False,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_files_modified": False,
    "schema_file_hashes_read_only": True,
    "migration_sql_executable_in_this_pr": False,
    "migration_sql_artifact_emitted": False,
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


def test_render_candidate_json_has_pr_number_and_required_flags() -> None:
    report = bundle.render_candidate_json()

    assert report["pr_number"] == 278
    assert report["title"] == "platform: add schema-change candidate review bundle"
    assert report["scope"] == "schema_change_candidate_review_bundle_only"
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected
    assert report["db_touching"] is False
    assert report["dsn_required"] is False
    assert report["blocked_by_default_pr_body_template"] is True


def test_contract_report_includes_source_inputs_and_future_required_prs() -> None:
    report = bundle.build_contract_report()

    assert report["mode"] == "contract-report"
    assert "db/schema.sql" in report["source_inputs"]
    assert "db/postgres/001_init.sql" in report["source_inputs"]
    assert "future schema-changing PR requires explicit user approval" in report["future_required_prs"]
    assert "do not read data or exports as migration inputs" in report["source_input_checklist"]


def test_cli_modes_print_expected_output_and_do_not_touch_schema(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--candidate-bundle-report"], "candidate-bundle-report"),
        (["--render-candidate-json"], "render-candidate-json"),
        (["--lint-candidate-bundle-report"], "lint-candidate-bundle-report"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert bundle.main(args) == 0
        assert json.loads(buffer.getvalue())["mode"] == mode

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert bundle.main(["--render-pr-body-template"]) == 0
    assert "## Candidate schema files" in buffer.getvalue()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def test_render_pr_body_template_is_blocked_by_default() -> None:
    template = bundle.render_pr_body_template()

    for needle in [
        "## Scope",
        "This future PR is intended to be a schema-changing PR only after explicit user approval.",
        "## Explicit approval gate",
        "Explicit user approval for schema file modification: NOT RECORDED IN THIS PR",
        "Human schema reviewer sign-off: PLACEHOLDER ONLY",
        "Migration operator sign-off: PLACEHOLDER ONLY",
        "Rollback owner sign-off: PLACEHOLDER ONLY",
        "Final maintainer sign-off: PLACEHOLDER ONLY",
        "## Candidate schema files",
        "db/schema.sql: CURRENT HASH ONLY / FUTURE DIFF NOT INCLUDED IN THIS PR",
        "db/postgres/001_init.sql: CURRENT HASH ONLY / FUTURE DIFF NOT INCLUDED IN THIS PR",
        "## Candidate review checklist",
        "Exact schema diff must be reviewed in a later PR.",
        "Executable migration SQL must not be emitted by this PR.",
        "Live apply must be separate opt-in.",
        "Seed apply must be separate opt-in.",
        "## Non-execution guarantees for this candidate review bundle",
        "This PR does not modify schema files.",
        "This PR does not execute SQL.",
        "This PR does not connect to PostgreSQL.",
        "This PR does not read production DSN.",
        "ready_for_schema_change_pr=false.",
        "ready_for_production_migration=false.",
    ]:
        assert needle in template
    assert SQL_CLIENT not in template
    assert "postgresql://" not in template


def test_schema_file_fingerprints_are_hash_line_count_only_and_read_only() -> None:
    fingerprints = bundle.schema_file_fingerprints()

    assert [item["path"] for item in fingerprints] == ["db/schema.sql", "db/postgres/001_init.sql"]
    for item in fingerprints:
        assert set(item) == {"path", "read_only", "sha256", "line_count"}
        assert item["read_only"] is True
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        assert isinstance(item["line_count"], int)
        assert item["line_count"] >= 0


def test_report_does_not_include_schema_file_contents() -> None:
    rendered = bundle.report_as_json(bundle.render_candidate_json())
    schema_text = (ROOT / "db" / "postgres" / "001_init.sql").read_text(encoding="utf-8").splitlines()
    non_empty_lines = [line.strip() for line in schema_text if line.strip()]

    assert "CREATE TABLE" not in rendered
    assert "INSERT INTO" not in rendered
    if non_empty_lines:
        assert non_empty_lines[0] not in rendered


def test_builders_do_not_modify_schema_mtimes_or_access_network(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    bundle.build_contract_report()
    bundle.render_candidate_json()
    bundle.build_candidate_bundle_report()
    bundle.lint_candidate_bundle_report()
    bundle.render_pr_body_template()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def test_lint_fails_if_required_false_flag_becomes_true() -> None:
    false_flags = [key for key, expected in REQUIRED_FLAGS.items() if expected is False]

    for flag in false_flags:
        report = bundle.render_candidate_json()
        report[flag] = True
        lint = bundle.lint_candidate_bundle_report(report)
        assert lint["passed"] is False
        assert any(flag in failed for failed in lint["failed"]) or "no_approval_ready_or_signoff_claim" in lint["failed"]


def test_lint_fails_if_required_true_flag_becomes_false() -> None:
    true_flags = [key for key, expected in REQUIRED_FLAGS.items() if expected is True]

    for flag in true_flags:
        report = bundle.render_candidate_json()
        report[flag] = False
        lint = bundle.lint_candidate_bundle_report(report)
        assert lint["passed"] is False
        assert any(flag in failed for failed in lint["failed"])


def test_lint_fails_if_connection_material_is_injected() -> None:
    for injected in ["postgresql://example", "postgres://example", "password=example", "connection string"]:
        report = bundle.render_candidate_json()
        report["warnings"] = [injected]
        lint = bundle.lint_candidate_bundle_report(report)
        assert lint["passed"] is False
        assert "no_connection_material_values" in lint["failed"]


def test_lint_fails_if_sql_client_or_shell_out_instruction_appears() -> None:
    report = bundle.render_candidate_json()
    report["warnings"] = [f"{SQL_CLIENT} command"]
    lint = bundle.lint_candidate_bundle_report(report)
    assert lint["passed"] is False
    assert "no_sql_client_instruction" in lint["failed"]

    for injected in ["shell out command", "subprocess command"]:
        report = bundle.render_candidate_json()
        report["warnings"] = [injected]
        lint = bundle.lint_candidate_bundle_report(report)
        assert lint["passed"] is False
        assert "no_shell_out_instruction" in lint["failed"]


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-schema-change-candidate-review-bundle.md"

    assert path.is_file()
    check = bundle.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert bundle.status_value(path.read_text(encoding="utf-8")) == "Proposed / Candidate review bundle only"


def test_adr_check_fails_if_approval_or_ready_claim_is_injected(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-schema-change-candidate-review-bundle.md"
    base = (ROOT / "archive" / "docs" / "adr" / "ADR-schema-change-candidate-review-bundle.md").read_text(encoding="utf-8")
    for injected in ["schema_change_pr_approved=true", "ready_for_schema_change_pr=true"]:
        adr.write_text(base + f"\n\n{injected}\n", encoding="utf-8")
        check = bundle.build_adr_check(adr)
        assert check["passed"] is False
        assert "no_approval_or_ready_claim" in check["failed"]


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (ROOT / "scripts" / "platform" / "schema_change_candidate_review_bundle.py").read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_SOURCE_TOKENS:
        assert forbidden not in source
    assert SQL_CLIENT not in source


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in schema-change candidate review bundle")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
