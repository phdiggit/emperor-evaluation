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

from scripts.platform import schema_change_explicit_approval_request_handoff as handoff  # noqa: E402


SQL_CLIENT = "p" + "sql"
PROTECTED_SCHEMA_PATHS = [
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
]
BOOLEAN_REQUIRED_FLAGS = {
    "schema_change_explicit_approval_request_handoff_only": True,
    "schema_change_user_approval_recorded": False,
    "schema_change_approval_request_rendered": True,
    "schema_change_pr_approved": False,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_files_modified": False,
    "schema_file_hashes_read_only": True,
    "migration_sql_executable_in_this_pr": False,
    "migration_sql_artifact_emitted": False,
    "apply_ready_schema_patch_artifact_emitted": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "human_signoffs_recorded": False,
    "ready_for_schema_change_pr": False,
    "ready_for_production_migration": False,
    "future_schema_change_pr_requires_explicit_user_approval": True,
    "future_schema_change_pr_required": True,
    "future_live_apply_pr_required": True,
    "future_seed_apply_pr_required": True,
}
REQUIRED_FLAGS = {
    **BOOLEAN_REQUIRED_FLAGS,
    "schema_change_approval_request_status": "pending_external_user_decision",
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


def test_render_approval_request_json_has_pr_number_title_scope_and_required_flags() -> None:
    report = handoff.render_approval_request_json()

    assert report["pr_number"] == 280
    assert report["title"] == "platform: add schema-change explicit approval request handoff package"
    assert report["scope"] == "schema_change_explicit_approval_request_handoff_only"
    assert report["required_flags"] == REQUIRED_FLAGS
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] == expected
    assert report["approval_request_status"] == "pending_external_user_decision"
    assert report["schema_change_user_approval_recorded"] is False
    assert report["schema_change_pr_approved"] is False
    assert report["ready_for_schema_change_pr"] is False
    assert report["ready_for_production_migration"] is False


def test_contract_report_includes_sources_and_future_required_prs() -> None:
    report = handoff.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["status"] == "Proposed / Explicit approval request handoff only"
    assert "archive/docs/adr/ADR-schema-change-explicit-approval-request-handoff.md" in report["source_inputs"]
    assert "archive/docs/adr/ADR-schema-change-approval-gate-package.md" in report["source_inputs"]
    assert "db/schema.sql" in report["source_inputs"]
    assert "db/postgres/001_init.sql" in report["source_inputs"]
    assert "future schema-changing PR requires explicit user approval outside PR #280" in report["future_required_prs"]


def test_cli_modes_print_expected_output_and_do_not_touch_schema(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--handoff-report"], "handoff-report"),
        (["--render-approval-request-json"], "render-approval-request-json"),
        (["--lint-handoff-report"], "lint-handoff-report"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert handoff.main(args) == 0
        assert json.loads(buffer.getvalue())["mode"] == mode

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert handoff.main(["--render-user-facing-approval-request-md"]) == 0
    assert "## Schema-change explicit approval request" in buffer.getvalue()

    buffer = StringIO()
    with redirect_stdout(buffer):
        assert handoff.main(["--render-blocked-schema-pr-body-template"]) == 0
    assert "Explicit approval record location: REQUIRED BEFORE THIS FUTURE PR" in buffer.getvalue()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def test_user_facing_approval_request_md_is_not_prechecked_or_recorded() -> None:
    markdown = handoff.render_user_facing_approval_request_md()

    for needle in [
        "NOT an approval record in PR #280",
        "explicitly reply with wording equivalent to",
        "outside PR #280",
        "live apply and seed apply still require separate opt-in PRs",
        "`schema_change_user_approval_recorded=false`",
        "`schema_change_pr_approved=false`",
        "`ready_for_schema_change_pr=false`",
        "`ready_for_production_migration=false`",
    ]:
        assert needle.lower() in markdown.lower()
    assert "- [x]" not in markdown.lower()
    assert "approval recorded" not in markdown.lower()


def test_blocked_schema_pr_body_template_is_blocked_by_default() -> None:
    template = handoff.render_blocked_schema_pr_body_template()

    for needle in [
        "Explicit approval record location: REQUIRED BEFORE THIS FUTURE PR",
        "Schema files changed: PLACEHOLDER ONLY",
        "Migration SQL source: PLACEHOLDER ONLY",
        "Rollback / restore plan: PLACEHOLDER ONLY",
        "Live apply: OUT OF SCOPE",
        "Seed apply: OUT OF SCOPE",
    ]:
        assert needle in template
    assert SQL_CLIENT not in template
    assert "CREATE TABLE" not in template
    assert "diff --git" not in template
    assert "patch content" not in template.lower()


def test_schema_file_fingerprints_are_hash_line_count_only_and_read_only() -> None:
    fingerprints = handoff.schema_file_fingerprints()

    assert [item["path"] for item in fingerprints] == ["db/schema.sql", "db/postgres/001_init.sql"]
    for item in fingerprints:
        assert set(item) == {"path", "read_only", "sha256", "line_count"}
        assert item["read_only"] is True
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        assert isinstance(item["line_count"], int)
        assert item["line_count"] >= 0


def test_report_does_not_include_schema_file_contents() -> None:
    rendered = handoff.report_as_json(handoff.render_approval_request_json())
    schema_text = (ROOT / "db" / "postgres" / "001_init.sql").read_text(encoding="utf-8").splitlines()
    non_empty_lines = [line.strip() for line in schema_text if line.strip()]

    assert "CREATE TABLE" not in rendered
    assert "INSERT INTO" not in rendered
    if non_empty_lines:
        assert non_empty_lines[0] not in rendered


def test_builders_do_not_modify_schema_mtimes_or_access_network(monkeypatch) -> None:
    _guard_network(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}

    handoff.build_contract_report()
    handoff.render_approval_request_json()
    handoff.build_handoff_report()
    handoff.lint_handoff_report()
    handoff.render_user_facing_approval_request_md()
    handoff.render_blocked_schema_pr_body_template()

    after = {path: _mtime(path) for path in PROTECTED_SCHEMA_PATHS}
    assert after == before


def test_lint_fails_if_required_false_flag_becomes_true() -> None:
    false_flags = [key for key, expected in BOOLEAN_REQUIRED_FLAGS.items() if expected is False]

    for flag in false_flags:
        report = handoff.render_approval_request_json()
        report[flag] = True
        lint = handoff.lint_handoff_report(report)
        assert lint["passed"] is False
        assert any(flag in failed for failed in lint["failed"]) or "no_approval_ready_or_signoff_claim" in lint["failed"]


def test_lint_fails_if_required_true_flag_becomes_false() -> None:
    true_flags = [key for key, expected in BOOLEAN_REQUIRED_FLAGS.items() if expected is True]

    for flag in true_flags:
        report = handoff.render_approval_request_json()
        report[flag] = False
        lint = handoff.lint_handoff_report(report)
        assert lint["passed"] is False
        assert any(flag in failed for failed in lint["failed"])


def test_lint_fails_if_status_is_not_pending_external_user_decision() -> None:
    report = handoff.render_approval_request_json()
    report["schema_change_approval_request_status"] = "approved"
    lint = handoff.lint_handoff_report(report)
    assert lint["passed"] is False
    assert "schema_change_approval_request_status_pending" in lint["failed"]


def test_lint_fails_if_connection_material_is_injected() -> None:
    for injected in ["postgresql://example", "postgres://example", "password=example", "connection string"]:
        report = handoff.render_approval_request_json()
        report["warnings"] = [injected]
        lint = handoff.lint_handoff_report(report)
        assert lint["passed"] is False
        assert "no_connection_material_values" in lint["failed"]


def test_lint_fails_if_sql_client_shell_out_sql_patch_or_claim_appears() -> None:
    injected_by_rule = {
        "no_sql_client_instruction": [f"{SQL_CLIENT} command"],
        "no_shell_process_instruction": ["shell out command", "subprocess command"],
        "no_executable_sql_or_schema_content": ["CREATE TABLE x", "ALTER TABLE x", "INSERT INTO x", "SQL snippet", "DDL body"],
        "no_apply_ready_patch_instruction": ["apply-ready patch", "diff --git a b", "patch content"],
        "no_approval_ready_or_signoff_claim": [
            "production migration approved",
            "schema-changing PR approved",
            "approval recorded",
            "sign-off recorded",
            "ready_for_schema_change_pr=true",
            "ready_for_production_migration=true",
        ],
    }

    for expected_rule, injected_values in injected_by_rule.items():
        for injected in injected_values:
            report = handoff.render_approval_request_json()
            report["warnings"] = [injected]
            lint = handoff.lint_handoff_report(report)
            assert lint["passed"] is False
            assert expected_rule in lint["failed"]


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-schema-change-explicit-approval-request-handoff.md"

    assert path.is_file()
    check = handoff.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert handoff.status_value(path.read_text(encoding="utf-8")) == "Proposed / Explicit approval request handoff only"


def test_adr_check_fails_if_approval_or_ready_claim_is_injected(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-schema-change-explicit-approval-request-handoff.md"
    base = (ROOT / "archive" / "docs" / "adr" / "ADR-schema-change-explicit-approval-request-handoff.md").read_text(
        encoding="utf-8"
    )
    for injected in [
        "schema_change_user_approval_recorded=true",
        "schema_change_pr_approved=true",
        "ready_for_schema_change_pr=true",
    ]:
        adr.write_text(base + f"\n\n{injected}\n", encoding="utf-8")
        check = handoff.build_adr_check(adr)
        assert check["passed"] is False
        assert "no_approval_or_ready_claim" in check["failed"]


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (Path(handoff.__file__)).read_text(
        encoding="utf-8"
    )

    for forbidden in FORBIDDEN_SOURCE_TOKENS:
        assert forbidden not in source
    assert SQL_CLIENT not in source


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in schema-change explicit approval request handoff")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
