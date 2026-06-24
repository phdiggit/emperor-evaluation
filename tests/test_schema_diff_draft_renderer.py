from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import schema_diff_draft_renderer as renderer  # noqa: E402
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
SQL_CLIENT = "p" + "sql"
PROTECTED_PATHS = [
    ROOT / "docs" / "\u7687\u5e1d\u7efc\u5408\u8bc4\u4ef7\u4f53\u7cfb\u8bc4\u5206\u6807\u51c6.md",
    ROOT / "docs" / "\u5206\u9879\u89c4\u5219",
    ROOT / "docs" / "\u8bc1\u636e\u89c4\u5219",
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
]
REQUIRED_CONTRACT_KEYS = {
    "mode",
    "renderer_version",
    "status",
    "supported_modes",
    "source_reports",
    "read_only_inputs",
    "diff_sections",
    "lint_rules",
    "non_goals",
    "boundaries",
    "limitations",
    "future_work",
}
REQUIRED_DIFF_JSON_KEYS = {
    "mode",
    "schema_diff_draft_only",
    "schema_files_modified",
    "sql_executed",
    "production_db_connected",
    "current_schema_files",
    "current_schema_file_sha256",
    "currently_declared_schema_files",
    "formal_target_tables",
    "deferred_tables",
    "present_in_current_schema_files",
    "missing_from_current_schema_files",
    "proposal_only_changes",
    "warnings",
}
REQUIRED_DIFF_REPORT_KEYS = {
    "mode",
    "renderer_version",
    "diff_status",
    "schema_diff_draft_only",
    "schema_files_modified",
    "sql_executed",
    "production_db_connected",
    "future_production_migration_pr_required",
    "draft_status",
    "package_status",
    "admission_status",
    "proposal_status",
    "readiness_state",
    "current_schema_file_sha256",
    "target_table_summary",
    "deferred_table_summary",
    "present_in_current_schema_files",
    "missing_from_current_schema_files",
    "proposal_only_changes",
    "lint_passed",
    "lint_failed",
    "gates",
    "blocking_failures",
    "warnings",
}
REQUIRED_LINT_RULES = {
    "schema_diff_draft_only_true",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "current_schema_files_read_only",
    "current_schema_file_sha256_present",
    "formal_target_tables_present",
    "deferred_tables_present",
    "proposal_only_changes_present",
    "no_dsn_or_secret",
    "no_" + SQL_CLIENT + "_instruction",
    "no_subprocess_instruction",
    "no_db_write_claim",
    "no_blocked_report_terms",
}
REQUIRED_REPORT_GATES = {
    "migration_sql_draft_report_available",
    "dry_run_package_report_available",
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "diff_status_is_proposed",
    "schema_diff_draft_only_true",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "schema_diff_rendered",
    "schema_diff_lint_passed",
    "current_schema_files_checksummed",
    "target_table_summary_present",
    "deferred_table_summary_present",
    "no_data_or_exports_artifact_written",
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
        "diff-report",
        "render-diff-json",
        "lint-diff-report",
        "adr-check",
    ]
    assert {item["path"] for item in report["read_only_inputs"]} == {"db/schema.sql", "db/postgres/001_init.sql"}
    assert all(item["read_only"] is True for item in report["read_only_inputs"])
    assert set(report["lint_rules"]) == REQUIRED_LINT_RULES


def test_render_diff_json_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_data_and_export_reads(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = renderer.render_diff_json()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_DIFF_JSON_KEYS
    assert report["mode"] == "render-diff-json"
    assert report["schema_diff_draft_only"] is True
    assert report["schema_files_modified"] is False
    assert report["sql_executed"] is False
    assert report["production_db_connected"] is False
    assert report["current_schema_files"] == ["db/schema.sql", "db/postgres/001_init.sql"]
    assert set(report["current_schema_file_sha256"]) == {"db/schema.sql", "db/postgres/001_init.sql"}
    assert all(len(value) == 64 for value in report["current_schema_file_sha256"].values())
    assert "imports" in report["formal_target_tables"]
    assert "search_hits" in report["deferred_tables"]["phase_2_relationship_tables"]
    assert "review_items" in report["deferred_tables"]["phase_3_downstream_tables"]
    assert report["proposal_only_changes"]


def test_diff_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = renderer.build_diff_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_DIFF_REPORT_KEYS
    assert report["mode"] == "diff-report"
    assert report["diff_status"] == "Proposed"
    assert report["schema_diff_draft_only"] is True
    assert report["schema_files_modified"] is False
    assert report["sql_executed"] is False
    assert report["production_db_connected"] is False
    assert report["future_production_migration_pr_required"] is True
    assert report["draft_status"] == "Proposed"
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

    assert renderer.main(["--diff-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "diff-report"

    assert renderer.main(["--render-diff-json"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "render-diff-json"

    assert renderer.main(["--lint-diff-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "lint-diff-report"


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
        renderer.render_diff_json(),
        renderer.build_diff_report(),
        renderer.lint_diff_report(),
        renderer.build_adr_check(),
    ]
    rendered = "\n".join(renderer.report_as_json(report) for report in reports)

    assert "legacy" not in rendered
    assert "primary" not in rendered
    assert env[LEGACY_ENV_DSN] not in rendered
    assert env[PRIMARY_ENV_DSN] not in rendered


def test_lint_passes_for_rendered_diff() -> None:
    report = renderer.lint_diff_report(renderer.render_diff_json())

    assert report["mode"] == "lint-diff-report"
    assert report["passed"] is True
    assert report["failed"] == []
    assert {rule["rule"] for rule in report["checked_rules"]} == REQUIRED_LINT_RULES


def test_lint_fails_if_dsn_is_injected() -> None:
    diff = renderer.render_diff_json()
    diff["warnings"] = ["postgresql://example"]

    report = renderer.lint_diff_report(diff)

    assert report["passed"] is False
    assert "no_dsn_or_secret" in report["failed"]


def test_lint_fails_if_sql_client_appears() -> None:
    diff = renderer.render_diff_json()
    diff["warnings"] = [f"{SQL_CLIENT} command"]

    report = renderer.lint_diff_report(diff)

    assert report["passed"] is False
    assert "no_" + SQL_CLIENT + "_instruction" in report["failed"]


def test_lint_fails_if_subprocess_appears() -> None:
    diff = renderer.render_diff_json()
    diff["warnings"] = ["subprocess command"]

    report = renderer.lint_diff_report(diff)

    assert report["passed"] is False
    assert "no_subprocess_instruction" in report["failed"]


def test_lint_fails_if_schema_files_modified_true() -> None:
    diff = renderer.render_diff_json()
    diff["schema_files_modified"] = True

    report = renderer.lint_diff_report(diff)

    assert report["passed"] is False
    assert "schema_files_modified_false" in report["failed"]
    assert "no_db_write_claim" in report["failed"]


def test_lint_fails_if_checksum_missing() -> None:
    diff = renderer.render_diff_json()
    diff["current_schema_file_sha256"] = {}

    report = renderer.lint_diff_report(diff)

    assert report["passed"] is False
    assert "current_schema_file_sha256_present" in report["failed"]


def test_lint_fails_if_blocked_report_term_appears() -> None:
    diff = renderer.render_diff_json()
    diff["warnings"] = ["leaderboard"]

    report = renderer.lint_diff_report(diff)

    assert report["passed"] is False
    assert "no_blocked_report_terms" in report["failed"]


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "docs" / "adr" / "ADR-schema-diff-draft-renderer.md"

    assert path.is_file()
    check = renderer.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert renderer.status_value(path.read_text(encoding="utf-8")) == "Proposed"


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "docs" / "adr" / "ADR-schema-diff-draft-renderer.md").read_text(encoding="utf-8")
    normalized = renderer.normalize_text(content)
    for needle in [
        "schema_diff_draft_only=true",
        "schema_files_modified=false",
        "sql_executed=false",
        "production_db_connected=false",
        "future production migration PR required",
        "no production migration",
        "no production seed",
        "read-only schema inputs",
        "diff categories",
        "schema file boundaries",
    ]:
        assert renderer.normalize_text(needle) in normalized


def test_adr_check_cli_prints_json_and_uses_exit_code(capsys) -> None:
    assert renderer.main(["--adr-check"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "adr-check"
    assert payload["passed"] is True


def test_missing_status_fails_adr_check(tmp_path: Path) -> None:
    adr = tmp_path / "draft.md"
    adr.write_text("# ADR\n\n## Context\n\n`schema_diff_draft_only=true`\n", encoding="utf-8")

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "status_is_proposed" in check["failed"]


def test_missing_schema_diff_draft_only_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("`schema_diff_draft_only=true`\n\n", ""), encoding="utf-8")

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_schema_diff_draft_only" in check["failed"]


def test_schema_files_modified_phrase_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(
        adr.read_text(encoding="utf-8").replace("schema_files_modified=false", "schema_files_modified=true"),
        encoding="utf-8",
    )

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "schema_files_modified_false" in check["failed"]
    assert "no_blocked_report_terms" in check["failed"]


def test_missing_diff_categories_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("## Diff Categories", "## Diff Notes"), encoding="utf-8")

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_diff_categories" in check["failed"]


def test_migration_sql_draft_report_unavailable_blocks_diff_report(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise RuntimeError("draft unavailable")

    monkeypatch.setattr(renderer.migration_sql_draft_renderer, "build_draft_report", fail_call)

    report = renderer.build_diff_report()

    assert "migration_sql_draft_report_available" in report["blocking_failures"]


def test_blocked_term_in_adr_fails_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8") + "\n\nleaderboard\n", encoding="utf-8")

    check = renderer.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_blocked_report_terms" in check["failed"]


def test_source_inspection_forbids_unsafe_terms() -> None:
    source = (ROOT / "scripts" / "platform" / "schema_diff_draft_renderer.py").read_text(encoding="utf-8")

    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "subprocess.run" not in source
    assert '"' + SQL_CLIENT + '"' not in source
    assert "psycopg" not in source
    assert "public." not in source
    assert "schema_files_modified = True" not in source
    assert "sql_executed = True" not in source
    assert "production_db_connected = True" not in source


def test_reports_contain_no_blocked_terms(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    reports = [
        renderer.build_contract_report(),
        renderer.render_diff_json(),
        renderer.build_diff_report(),
        renderer.lint_diff_report(),
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
    assert any(path.endswith("db/schema.sql") for path in protected_paths)
    assert any(path.endswith("db/postgres/001_init.sql") for path in protected_paths)


def _tmp_adr(tmp_path: Path) -> Path:
    adr = tmp_path / "ADR-schema-diff-draft-renderer.md"
    adr.write_text(
        (ROOT / "docs" / "adr" / "ADR-schema-diff-draft-renderer.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return adr


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in schema diff draft renderer")

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
            raise AssertionError(f"schema diff draft renderer must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if forbidden_path(self):
            raise AssertionError(f"schema diff draft renderer must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"schema diff draft renderer must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"schema diff draft renderer must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
