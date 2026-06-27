from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import migration_sql_draft_renderer as renderer  # noqa: E402
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
SQL_CLIENT = "p" + "sql"
PUBLIC_SCHEMA_QUALIFIER = "public" + "."
PROTECTED_PATHS = [
    ROOT / "docs" / "\u7687\u5e1d\u7efc\u5408\u8bc4\u4ef7\u4f53\u7cfb\u8bc4\u5206\u6807\u51c6.md",
    ROOT / "docs" / "\u5206\u9879\u89c4\u5219",
    ROOT / "docs" / "\u8bc1\u636e\u89c4\u5219",
]
REQUIRED_CONTRACT_KEYS = {
    "mode",
    "renderer_version",
    "status",
    "supported_modes",
    "source_reports",
    "draft_sections",
    "lint_rules",
    "non_goals",
    "boundaries",
    "limitations",
    "future_work",
}
REQUIRED_DRAFT_KEYS = {
    "mode",
    "renderer_version",
    "adr_path",
    "draft_status",
    "migration_sql_draft_only",
    "sql_executed",
    "schema_files_modified",
    "production_db_connected",
    "future_production_migration_pr_required",
    "package_status",
    "admission_status",
    "proposal_status",
    "readiness_state",
    "draft_sql_sha256",
    "draft_sql_line_count",
    "lint_passed",
    "lint_failed",
    "target_table_summary",
    "deferred_table_summary",
    "gates",
    "blocking_failures",
    "warnings",
}
REQUIRED_REPORT_GATES = {
    "dry_run_package_report_available",
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "draft_status_is_proposed",
    "migration_sql_draft_only_true",
    "sql_executed_false",
    "schema_files_modified_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "draft_sql_rendered",
    "draft_sql_lint_passed",
    "target_table_summary_present",
    "deferred_table_summary_present",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
}
REQUIRED_LINT_RULES = {
    "contains_draft_only_header",
    "contains_do_not_execute_warning",
    "contains_source_metadata",
    "contains_target_table_summary",
    "contains_deferred_table_summary",
    "no_dsn_or_secret",
    "no_" + SQL_CLIENT + "_instruction",
    "no_subprocess_instruction",
    "no_public_schema_hardcode",
    "no_production_seed_statement",
    "no_copy_load_data_upsert",
    "no_blocked_report_terms",
}


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_data_and_export_reads(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = renderer.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_CONTRACT_KEYS
    assert report["mode"] == "contract-report"
    assert report["renderer_version"] == renderer.RENDERER_VERSION
    assert report["status"] == "Proposed"
    assert report["supported_modes"] == [
        "contract-report",
        "draft-report",
        "render-draft-sql",
        "lint-draft-sql",
        "adr-check",
    ]
    assert set(report["lint_rules"]) == REQUIRED_LINT_RULES


def test_draft_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = renderer.build_draft_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_DRAFT_KEYS
    assert report["mode"] == "draft-report"
    assert report["draft_status"] == "Proposed"
    assert report["migration_sql_draft_only"] is True
    assert report["sql_executed"] is False
    assert report["schema_files_modified"] is False
    assert report["production_db_connected"] is False
    assert report["future_production_migration_pr_required"] is True
    assert report["package_status"] == "Proposed"
    assert report["admission_status"] == "Proposed"
    assert report["proposal_status"] == "Proposed"
    assert report["readiness_state"] == "passed"
    assert report["lint_passed"] is True
    assert report["lint_failed"] == []
    assert report["blocking_failures"] == []
    assert {gate["gate"] for gate in report["gates"]} == REQUIRED_REPORT_GATES
    assert all(gate["passed"] for gate in report["gates"])


def test_cli_modes_do_not_read_dotenv_or_db_evidence(monkeypatch, capsys) -> None:
    _guard_db_evidence_calls(monkeypatch)
    _guard_dotenv_reads(monkeypatch)

    assert renderer.main(["--contract-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "contract-report"

    assert renderer.main(["--draft-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "draft-report"

    assert renderer.main(["--render-draft-sql"]) == 0
    assert "MIGRATION SQL DRAFT ONLY" in capsys.readouterr().out

    assert renderer.main(["--lint-draft-sql"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "lint-draft-sql"


def test_reports_do_not_read_or_render_dsn_values(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    env = {
        LEGACY_ENV_DSN: "postgresql://legacy/example",
        PRIMARY_ENV_DSN: "postgresql://primary/example",
    }
    monkeypatch.setenv(LEGACY_ENV_DSN, env[LEGACY_ENV_DSN])
    monkeypatch.setenv(PRIMARY_ENV_DSN, env[PRIMARY_ENV_DSN])

    reports = [
        renderer.build_contract_report(),
        renderer.build_draft_report(),
        renderer.lint_draft_sql(),
        renderer.build_adr_check(),
    ]
    rendered = "\n".join(renderer.report_as_json(report) for report in reports)

    assert "legacy" not in rendered
    assert "primary" not in rendered
    assert env[LEGACY_ENV_DSN] not in rendered
    assert env[PRIMARY_ENV_DSN] not in rendered


def test_rendered_draft_sql_contains_required_sections() -> None:
    sql = renderer.render_draft_sql()

    assert "-- MIGRATION SQL DRAFT ONLY" in sql
    assert "-- Do not execute." in sql
    assert "-- Source: formal_schema_draft + formal_ddl_rehearsal" in sql
    assert "-- Target Phase 1 base tables:" in sql
    assert "-- Deferred Phase 2/3 tables:" in sql
    assert "CREATE TABLE imports" in sql
    assert "evd_src_links" in sql
    assert PUBLIC_SCHEMA_QUALIFIER not in sql.lower()


def test_lint_passes_for_rendered_draft() -> None:
    report = renderer.lint_draft_sql(renderer.render_draft_sql())

    assert report["mode"] == "lint-draft-sql"
    assert report["passed"] is True
    assert report["failed"] == []
    assert {rule["rule"] for rule in report["checked_rules"]} == REQUIRED_LINT_RULES


def test_lint_fails_if_dsn_is_injected() -> None:
    report = renderer.lint_draft_sql(renderer.render_draft_sql() + "\n-- postgresql://example\n")

    assert report["passed"] is False
    assert "no_dsn_or_secret" in report["failed"]


def test_lint_fails_if_sql_client_appears() -> None:
    report = renderer.lint_draft_sql(renderer.render_draft_sql() + f"\n-- {SQL_CLIENT} command\n")

    assert report["passed"] is False
    assert "no_" + SQL_CLIENT + "_instruction" in report["failed"]


def test_lint_fails_if_public_schema_appears() -> None:
    report = renderer.lint_draft_sql(renderer.render_draft_sql() + f"\nCREATE TABLE {PUBLIC_SCHEMA_QUALIFIER}imports (id bigint);\n")

    assert report["passed"] is False
    assert "no_public_schema_hardcode" in report["failed"]


def test_lint_fails_if_production_seed_statement_appears() -> None:
    report = renderer.lint_draft_sql(renderer.render_draft_sql() + "\nINSERT INTO production_seed VALUES (1);\n")

    assert report["passed"] is False
    assert "no_production_seed_statement" in report["failed"]


def test_lint_fails_if_blocked_report_term_appears() -> None:
    report = renderer.lint_draft_sql(renderer.render_draft_sql() + "\n-- leaderboard\n")

    assert report["passed"] is False
    assert "no_blocked_report_terms" in report["failed"]


def test_lint_fails_without_do_not_execute_warning() -> None:
    sql = renderer.render_draft_sql().replace("-- Do not execute.\n", "")

    report = renderer.lint_draft_sql(sql)

    assert report["passed"] is False
    assert "contains_do_not_execute_warning" in report["failed"]


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-migration-sql-draft-renderer.md"

    assert path.is_file()
    check = renderer.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert renderer.status_value(path.read_text(encoding="utf-8")) == "Proposed"


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "archive" / "docs" / "adr" / "ADR-migration-sql-draft-renderer.md").read_text(encoding="utf-8")
    normalized = renderer.normalize_text(content)
    for needle in [
        "migration_sql_draft_only=true",
        "sql_executed=false",
        "schema_files_modified=false",
        "production_db_connected=false",
        "future production migration PR required",
        "no production migration",
        "no production seed",
        "SQL draft boundaries",
        "lint rules",
    ]:
        assert renderer.normalize_text(needle) in normalized


def test_adr_check_cli_prints_json_and_uses_exit_code(capsys) -> None:
    assert renderer.main(["--adr-check"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "adr-check"
    assert payload["passed"] is True


def test_missing_status_fails_adr_check(tmp_path: Path) -> None:
    adr = tmp_path / "draft.md"
    adr.write_text("# ADR\n\n## Context\n\n`migration_sql_draft_only=true`\n", encoding="utf-8")

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "status_is_proposed" in check["failed"]


def test_missing_migration_sql_draft_only_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("`migration_sql_draft_only=true`\n\n", ""), encoding="utf-8")

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_migration_sql_draft_only" in check["failed"]


def test_sql_executed_phrase_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(
        adr.read_text(encoding="utf-8").replace("sql_executed=false", "sql_executed=true"),
        encoding="utf-8",
    )

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "sql_executed_false" in check["failed"]
    assert "no_blocked_report_terms" in check["failed"]


def test_missing_sql_draft_boundaries_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("## SQL Draft Boundaries", "## SQL Notes"), encoding="utf-8")

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_sql_draft_boundaries" in check["failed"]


def test_dry_run_package_report_unavailable_blocks_draft_report(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise RuntimeError("package unavailable")

    monkeypatch.setattr(renderer.production_migration_dry_run_package, "build_package_report", fail_call)

    report = renderer.build_draft_report()

    assert "dry_run_package_report_available" in report["blocking_failures"]


def test_blocked_term_in_adr_fails_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8") + "\n\nleaderboard\n", encoding="utf-8")

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_blocked_report_terms" in check["failed"]


def test_source_inspection_forbids_unsafe_terms() -> None:
    source = (Path(renderer.__file__)).read_text(encoding="utf-8")

    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "subprocess.run" not in source
    assert '"' + SQL_CLIENT + '"' not in source
    assert "psycopg" not in source
    assert PUBLIC_SCHEMA_QUALIFIER not in source
    assert "sql_executed = True" not in source
    assert "schema_files_modified = True" not in source
    assert "production_db_connected = True" not in source


def test_reports_contain_no_blocked_terms(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    reports = [
        renderer.build_contract_report(),
        renderer.build_draft_report(),
        renderer.lint_draft_sql(),
        renderer.build_adr_check(),
    ]

    for report in reports:
        text = renderer.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_guard_paths_use_utf8_chinese_names() -> None:
    protected_paths = {path.as_posix() for path in PROTECTED_PATHS}

    assert any(path.endswith("docs/\u7687\u5e1d\u7efc\u5408\u8bc4\u4ef7\u4f53\u7cfb\u8bc4\u5206\u6807\u51c6.md") for path in protected_paths)
    assert any(path.endswith("docs/\u5206\u9879\u89c4\u5219") for path in protected_paths)
    assert any(path.endswith("docs/\u8bc1\u636e\u89c4\u5219") for path in protected_paths)


def _tmp_adr(tmp_path: Path) -> Path:
    adr = tmp_path / "ADR-migration-sql-draft-renderer.md"
    adr.write_text(
        (ROOT / "archive" / "docs" / "adr" / "ADR-migration-sql-draft-renderer.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return adr


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in migration SQL draft renderer")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_db_evidence_calls(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("database evidence functions must not run")

    matrix = renderer.cutover_readiness_matrix
    monkeypatch.setattr(matrix.seed_artifact_db_preflight, "run_preflight", fail_call)
    monkeypatch.setattr(matrix.isolated_seed_dry_apply, "run_dry_apply", fail_call)
    monkeypatch.setattr(matrix.isolated_seed_rollback_restore, "run_rehearsal", fail_call)


def _guard_dotenv_data_and_export_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def forbidden_path(path: Path) -> bool:
        parts = set(path.parts)
        return path.name == ".env" or "data" in parts or "exports" in parts

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if forbidden_path(self):
            raise AssertionError(f"migration SQL draft renderer must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if forbidden_path(self):
            raise AssertionError(f"migration SQL draft renderer must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"migration SQL draft renderer must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"migration SQL draft renderer must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
