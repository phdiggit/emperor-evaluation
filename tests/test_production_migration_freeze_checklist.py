from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import production_migration_freeze_checklist as freeze  # noqa: E402
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
    "freeze_version",
    "status",
    "supported_modes",
    "source_reports",
    "freeze_sections",
    "freeze_inputs",
    "freeze_gate_categories",
    "freeze_lint_rules",
    "human_freeze_checklist",
    "non_goals",
    "boundaries",
    "limitations",
    "future_work",
}
REQUIRED_FREEZE_JSON_KEYS = {
    "mode",
    "production_migration_freeze_checklist_only",
    "production_migration_approved",
    "production_migration_executed",
    "production_seed_executed",
    "schema_files_modified",
    "sql_executed",
    "production_db_connected",
    "future_production_migration_pr_required",
    "source_report_statuses",
    "freeze_inputs",
    "machine_freeze_gates",
    "human_freeze_checklist",
    "human_signoffs_recorded",
    "rollback_freeze_checklist",
    "seed_checksum_freeze_checklist",
    "operator_freeze_checklist",
    "validation_command_matrix",
    "ready_for_next_scaffold_pr",
    "ready_for_production_migration",
    "freeze_blockers",
    "warnings",
}
REQUIRED_FREEZE_REPORT_KEYS = {
    "mode",
    "freeze_version",
    "freeze_status",
    "production_migration_freeze_checklist_only",
    "production_migration_approved",
    "production_migration_executed",
    "production_seed_executed",
    "schema_files_modified",
    "sql_executed",
    "production_db_connected",
    "future_production_migration_pr_required",
    "bundle_status",
    "schema_diff_status",
    "migration_sql_draft_status",
    "dry_run_package_status",
    "admission_status",
    "proposal_status",
    "readiness_state",
    "freeze_json_sha256",
    "freeze_lint_passed",
    "freeze_lint_failed",
    "machine_freeze_gate_summary",
    "human_signoffs_recorded",
    "ready_for_next_scaffold_pr",
    "ready_for_production_migration",
    "blocking_failures",
    "warnings",
}
REQUIRED_LINT_RULES = {
    "freeze_checklist_only_true",
    "production_migration_approved_false",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "source_reports_present",
    "freeze_inputs_present",
    "machine_freeze_gates_present",
    "human_freeze_checklist_present",
    "human_signoffs_recorded_false",
    "rollback_freeze_checklist_present",
    "seed_checksum_freeze_checklist_present",
    "operator_freeze_checklist_present",
    "validation_command_matrix_present",
    "ready_for_production_migration_false",
    "no_dsn_or_secret",
    "no_" + SQL_CLIENT + "_instruction",
    "no_subprocess_instruction",
    "no_db_write_claim",
    "no_data_or_exports_artifact_claim",
    "no_human_signoff_forged",
    "no_blocked_report_terms",
}
REQUIRED_REPORT_GATES = {
    "migration_bundle_review_pack_available",
    "schema_diff_draft_report_available",
    "migration_sql_draft_report_available",
    "dry_run_package_report_available",
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "freeze_status_is_proposed",
    "freeze_checklist_only_true",
    "production_migration_approved_false",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "freeze_json_rendered",
    "freeze_lint_passed",
    "human_signoffs_recorded_false",
    "ready_for_production_migration_false",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
}


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_data_and_export_reads(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = freeze.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_CONTRACT_KEYS
    assert report["mode"] == "contract-report"
    assert report["freeze_version"] == "production-migration-freeze-checklist-v1"
    assert report["status"] == "Proposed"
    assert report["supported_modes"] == [
        "contract-report",
        "freeze-report",
        "render-freeze-json",
        "lint-freeze-report",
        "adr-check",
    ]
    assert set(report["freeze_lint_rules"]) == REQUIRED_LINT_RULES
    assert "migration bundle review pack report" in report["freeze_inputs"]
    assert "human sign-off gates" in report["freeze_gate_categories"]


def test_render_freeze_json_is_offline_and_has_required_false_flags(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = freeze.render_freeze_json()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_FREEZE_JSON_KEYS
    assert report["mode"] == "render-freeze-json"
    assert report["production_migration_freeze_checklist_only"] is True
    assert report["production_migration_approved"] is False
    assert report["production_migration_executed"] is False
    assert report["production_seed_executed"] is False
    assert report["schema_files_modified"] is False
    assert report["sql_executed"] is False
    assert report["production_db_connected"] is False
    assert report["future_production_migration_pr_required"] is True
    assert report["human_signoffs_recorded"] is False
    assert report["ready_for_next_scaffold_pr"] is True
    assert report["ready_for_production_migration"] is False
    assert report["source_report_statuses"] == {
        "bundle_status": "Proposed",
        "schema_diff_status": "Proposed",
        "migration_sql_draft_status": "Proposed",
        "dry_run_package_status": "Proposed",
        "admission_status": "Proposed",
        "proposal_status": "Proposed",
        "readiness_state": "passed",
    }
    assert report["freeze_inputs"]
    assert report["machine_freeze_gates"]
    assert report["human_freeze_checklist"]
    assert report["rollback_freeze_checklist"]
    assert report["seed_checksum_freeze_checklist"]
    assert report["operator_freeze_checklist"]
    assert report["validation_command_matrix"]


def test_freeze_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = freeze.build_freeze_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_FREEZE_REPORT_KEYS
    assert report["mode"] == "freeze-report"
    assert report["freeze_status"] == "Proposed"
    assert report["production_migration_freeze_checklist_only"] is True
    assert report["production_migration_approved"] is False
    assert report["production_migration_executed"] is False
    assert report["production_seed_executed"] is False
    assert report["schema_files_modified"] is False
    assert report["sql_executed"] is False
    assert report["production_db_connected"] is False
    assert report["future_production_migration_pr_required"] is True
    assert report["bundle_status"] == "Proposed"
    assert report["schema_diff_status"] == "Proposed"
    assert report["migration_sql_draft_status"] == "Proposed"
    assert report["dry_run_package_status"] == "Proposed"
    assert report["admission_status"] == "Proposed"
    assert report["proposal_status"] == "Proposed"
    assert report["readiness_state"] == "passed"
    assert report["freeze_lint_passed"] is True
    assert report["freeze_lint_failed"] == []
    assert report["human_signoffs_recorded"] is False
    assert report["ready_for_next_scaffold_pr"] is True
    assert report["ready_for_production_migration"] is False
    assert report["blocking_failures"] == []
    assert set(report["machine_freeze_gate_summary"]["passed"]) == REQUIRED_REPORT_GATES
    assert report["machine_freeze_gate_summary"]["failed"] == []


def test_cli_modes_do_not_read_dotenv_or_run_db_evidence(monkeypatch, capsys) -> None:
    _guard_network(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)
    _guard_dotenv_reads(monkeypatch)

    assert freeze.main(["--contract-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "contract-report"

    assert freeze.main(["--freeze-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "freeze-report"

    assert freeze.main(["--render-freeze-json"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "render-freeze-json"

    assert freeze.main(["--lint-freeze-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "lint-freeze-report"


def test_reports_do_not_read_or_render_dsn_values(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    env = {
        LEGACY_ENV_DSN: "postgresql://legacy/example",
        PRIMARY_ENV_DSN: "postgresql://primary/example",
    }
    monkeypatch.setenv(LEGACY_ENV_DSN, env[LEGACY_ENV_DSN])
    monkeypatch.setenv(PRIMARY_ENV_DSN, env[PRIMARY_ENV_DSN])

    reports = [
        freeze.build_contract_report(),
        freeze.render_freeze_json(),
        freeze.lint_freeze_report(),
        freeze.build_freeze_report(),
        freeze.build_adr_check(),
    ]
    rendered = "\n".join(freeze.report_as_json(report) for report in reports)

    assert "legacy" not in rendered
    assert "primary" not in rendered
    assert env[LEGACY_ENV_DSN] not in rendered
    assert env[PRIMARY_ENV_DSN] not in rendered


def test_lint_passes_for_rendered_freeze_json() -> None:
    report = freeze.lint_freeze_report(freeze.render_freeze_json())

    assert report["mode"] == "lint-freeze-report"
    assert report["passed"] is True
    assert report["failed"] == []
    assert {rule["rule"] for rule in report["checked_rules"]} == REQUIRED_LINT_RULES


def test_lint_fails_if_dsn_is_injected() -> None:
    rendered = freeze.render_freeze_json()
    rendered["warnings"] = ["postgresql://example"]

    report = freeze.lint_freeze_report(rendered)

    assert report["passed"] is False
    assert "no_dsn_or_secret" in report["failed"]


def test_lint_fails_if_sql_client_is_injected() -> None:
    rendered = freeze.render_freeze_json()
    rendered["warnings"] = [f"{SQL_CLIENT} command"]

    report = freeze.lint_freeze_report(rendered)

    assert report["passed"] is False
    assert "no_" + SQL_CLIENT + "_instruction" in report["failed"]


def test_lint_fails_if_subprocess_is_injected() -> None:
    rendered = freeze.render_freeze_json()
    rendered["warnings"] = ["subprocess command"]

    report = freeze.lint_freeze_report(rendered)

    assert report["passed"] is False
    assert "no_subprocess_instruction" in report["failed"]


def test_lint_fails_if_production_migration_is_approved() -> None:
    rendered = freeze.render_freeze_json()
    rendered["production_migration_approved"] = True

    report = freeze.lint_freeze_report(rendered)

    assert report["passed"] is False
    assert "production_migration_approved_false" in report["failed"]
    assert "no_db_write_claim" in report["failed"]


def test_lint_fails_if_human_signoff_is_forged() -> None:
    rendered = freeze.render_freeze_json()
    rendered["human_signoffs_recorded"] = True

    report = freeze.lint_freeze_report(rendered)

    assert report["passed"] is False
    assert "human_signoffs_recorded_false" in report["failed"]
    assert "no_human_signoff_forged" in report["failed"]


def test_lint_fails_if_ready_for_production_migration_is_true() -> None:
    rendered = freeze.render_freeze_json()
    rendered["ready_for_production_migration"] = True

    report = freeze.lint_freeze_report(rendered)

    assert report["passed"] is False
    assert "ready_for_production_migration_false" in report["failed"]
    assert "no_db_write_claim" in report["failed"]


def test_lint_fails_if_data_or_exports_artifact_write_is_claimed() -> None:
    rendered = freeze.render_freeze_json()
    rendered["warnings"] = ["wrote exports artifact"]

    report = freeze.lint_freeze_report(rendered)

    assert report["passed"] is False
    assert "no_data_or_exports_artifact_claim" in report["failed"]


def test_lint_fails_if_blocked_report_term_appears() -> None:
    rendered = freeze.render_freeze_json()
    rendered["warnings"] = ["leaderboard"]

    report = freeze.lint_freeze_report(rendered)

    assert report["passed"] is False
    assert "no_blocked_report_terms" in report["failed"]


def test_lint_fails_when_source_report_status_is_missing() -> None:
    rendered = freeze.render_freeze_json()
    rendered["source_report_statuses"].pop("bundle_status")

    report = freeze.lint_freeze_report(rendered)

    assert report["passed"] is False
    assert "source_reports_present" in report["failed"]


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-production-migration-freeze-checklist.md"

    assert path.is_file()
    check = freeze.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert freeze.status_value(path.read_text(encoding="utf-8")) == "Proposed"


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "archive" / "docs" / "adr" / "ADR-production-migration-freeze-checklist.md").read_text(encoding="utf-8")
    normalized = freeze.normalize_text(content)
    for needle in [
        "production_migration_freeze_checklist_only=true",
        "production_migration_approved=false",
        "production_migration_executed=false",
        "production_seed_executed=false",
        "schema_files_modified=false",
        "sql_executed=false",
        "production_db_connected=false",
        "human_signoffs_recorded=false",
        "ready_for_production_migration=false",
        "future production migration PR required",
        "Freeze Inputs",
        "Freeze Gate Categories",
        "Human Freeze Checklist",
        "Freeze Boundaries",
        "no production migration",
        "no production seed",
    ]:
        assert freeze.normalize_text(needle) in normalized


def test_adr_check_cli_prints_json_and_uses_exit_code(capsys) -> None:
    assert freeze.main(["--adr-check"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "adr-check"
    assert payload["passed"] is True


def test_missing_status_fails_adr_check(tmp_path: Path) -> None:
    adr = tmp_path / "freeze.md"
    adr.write_text("# ADR\n\n## Context\n\n`production_migration_freeze_checklist_only=true`\n", encoding="utf-8")

    check = freeze.build_adr_check(adr)

    assert check["passed"] is False
    assert "status_is_proposed" in check["failed"]


def test_missing_freeze_checklist_only_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(
        adr.read_text(encoding="utf-8").replace("`production_migration_freeze_checklist_only=true`\n", ""),
        encoding="utf-8",
    )

    check = freeze.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_freeze_checklist_only" in check["failed"]


def test_production_migration_approved_phrase_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(
        adr.read_text(encoding="utf-8").replace("production_migration_approved=false", "production_migration_approved=true"),
        encoding="utf-8",
    )

    check = freeze.build_adr_check(adr)

    assert check["passed"] is False
    assert "production_migration_approved_false" in check["failed"]
    assert "no_blocked_report_terms" in check["failed"]


def test_missing_freeze_inputs_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("## Freeze Inputs", "## Freeze Notes"), encoding="utf-8")

    check = freeze.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_freeze_inputs" in check["failed"]


def test_blocked_term_in_adr_fails_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8") + "\n\nleaderboard\n", encoding="utf-8")

    check = freeze.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_blocked_report_terms" in check["failed"]


def test_bundle_review_pack_unavailable_blocks_freeze_report(monkeypatch) -> None:
    def fail_report() -> dict[str, Any]:
        raise AssertionError("bundle review pack report unavailable")

    monkeypatch.setattr(freeze.migration_bundle_review_pack, "build_bundle_report", fail_report)

    report = freeze.build_freeze_report()

    assert "migration_bundle_review_pack_available" in report["blocking_failures"]
    assert "freeze_json_rendered" in report["blocking_failures"]
    assert report["bundle_status"] is None
    assert report["ready_for_next_scaffold_pr"] is False
    assert report["ready_for_production_migration"] is False


def test_source_reports_and_output_have_no_blocked_report_terms() -> None:
    reports = [
        freeze.build_contract_report(),
        freeze.render_freeze_json(),
        freeze.lint_freeze_report(),
        freeze.build_freeze_report(),
        freeze.build_adr_check(),
    ]

    for report in reports:
        text = freeze.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (Path(freeze.__file__)).read_text(encoding="utf-8")

    for forbidden in [
        "PG_SEARCH_BENCH_DSN",
        "EMPEROR_EVAL_PG_DSN",
        "subprocess.run",
        '"' + SQL_CLIENT + '"',
        "psycopg",
        "public.",
        "production_migration_approved = True",
        "production_migration_executed = True",
        "production_seed_executed = True",
        "schema_files_modified = True",
        "sql_executed = True",
        "production_db_connected = True",
        "ready_for_production_migration = True",
        "human_signoffs_recorded = True",
    ]:
        assert forbidden not in source


def test_guard_paths_use_utf8_chinese_names() -> None:
    protected_paths = {path.as_posix() for path in PROTECTED_PATHS}

    assert any(path.endswith("docs/\u7687\u5e1d\u7efc\u5408\u8bc4\u4ef7\u4f53\u7cfb\u8bc4\u5206\u6807\u51c6.md") for path in protected_paths)
    assert any(path.endswith("docs/\u5206\u9879\u89c4\u5219") for path in protected_paths)
    assert any(path.endswith("docs/\u8bc1\u636e\u89c4\u5219") for path in protected_paths)
    assert any(path.endswith("db/schema.sql") for path in protected_paths)
    assert any(path.endswith("db/postgres/001_init.sql") for path in protected_paths)


def test_freeze_checklist_does_not_touch_protected_path_mtimes() -> None:
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    freeze.render_freeze_json()
    freeze.build_freeze_report()
    freeze.lint_freeze_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before


def _tmp_adr(tmp_path: Path) -> Path:
    adr = tmp_path / "ADR-production-migration-freeze-checklist.md"
    adr.write_text(
        (ROOT / "archive" / "docs" / "adr" / "ADR-production-migration-freeze-checklist.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return adr


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in production migration freeze checklist")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_db_evidence_calls(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("database evidence functions must not run")

    matrix = freeze.cutover_readiness_matrix
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
            raise AssertionError(f"production migration freeze checklist must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if forbidden_path(self):
            raise AssertionError(f"production migration freeze checklist must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"production migration freeze checklist must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"production migration freeze checklist must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
