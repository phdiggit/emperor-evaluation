from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import migration_bundle_review_pack as bundle  # noqa: E402
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
    "bundle_version",
    "status",
    "supported_modes",
    "source_reports",
    "bundle_sections",
    "review_pack_contents",
    "bundle_lint_rules",
    "non_goals",
    "boundaries",
    "limitations",
    "future_work",
}
REQUIRED_BUNDLE_JSON_KEYS = {
    "mode",
    "migration_bundle_review_only",
    "production_migration_executed",
    "production_seed_executed",
    "schema_files_modified",
    "sql_executed",
    "production_db_connected",
    "future_production_migration_pr_required",
    "source_report_statuses",
    "bundle_contents",
    "operator_checklist",
    "validation_command_matrix",
    "rollback_checklist",
    "seed_artifact_checksum_review",
    "human_review_checklist",
    "risk_register",
    "warnings",
}
REQUIRED_BUNDLE_REPORT_KEYS = {
    "mode",
    "bundle_version",
    "bundle_status",
    "migration_bundle_review_only",
    "production_migration_executed",
    "production_seed_executed",
    "schema_files_modified",
    "sql_executed",
    "production_db_connected",
    "future_production_migration_pr_required",
    "schema_diff_status",
    "migration_sql_draft_status",
    "dry_run_package_status",
    "admission_status",
    "proposal_status",
    "readiness_state",
    "bundle_json_sha256",
    "bundle_lint_passed",
    "bundle_lint_failed",
    "bundle_gate_summary",
    "blocking_failures",
    "warnings",
}
REQUIRED_LINT_RULES = {
    "migration_bundle_review_only_true",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "source_reports_present",
    "schema_diff_status_present",
    "migration_sql_draft_status_present",
    "dry_run_package_status_present",
    "admission_status_present",
    "proposal_status_present",
    "readiness_state_present",
    "operator_checklist_present",
    "validation_command_matrix_present",
    "rollback_checklist_present",
    "seed_artifact_checksum_review_present",
    "human_review_checklist_present",
    "risk_register_present",
    "no_dsn_or_secret",
    "no_" + SQL_CLIENT + "_instruction",
    "no_subprocess_instruction",
    "no_db_write_claim",
    "no_data_or_exports_artifact_claim",
    "no_blocked_report_terms",
}
REQUIRED_REPORT_GATES = {
    "schema_diff_draft_report_available",
    "migration_sql_draft_report_available",
    "dry_run_package_report_available",
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "bundle_status_is_proposed",
    "migration_bundle_review_only_true",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "bundle_json_rendered",
    "bundle_lint_passed",
    "operator_checklist_present",
    "validation_command_matrix_present",
    "rollback_checklist_present",
    "human_review_checklist_present",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
}


def test_contract_report_shape_and_boundaries() -> None:
    report = bundle.build_contract_report()

    assert set(report) == REQUIRED_CONTRACT_KEYS
    assert report["mode"] == "contract-report"
    assert report["bundle_version"] == "migration-bundle-review-pack-v1"
    assert report["status"] == "Proposed"
    assert report["supported_modes"] == [
        "contract-report",
        "bundle-report",
        "render-bundle-json",
        "lint-bundle-report",
        "adr-check",
    ]
    assert "schema diff draft report" in report["review_pack_contents"]
    assert "future production migration PR remains separately required" in report["boundaries"]
    assert set(report["bundle_lint_rules"]) == REQUIRED_LINT_RULES


def test_render_bundle_json_shape_and_required_false_flags() -> None:
    report = bundle.render_bundle_json()

    assert set(report) == REQUIRED_BUNDLE_JSON_KEYS
    assert report["mode"] == "render-bundle-json"
    assert report["migration_bundle_review_only"] is True
    assert report["production_migration_executed"] is False
    assert report["production_seed_executed"] is False
    assert report["schema_files_modified"] is False
    assert report["sql_executed"] is False
    assert report["production_db_connected"] is False
    assert report["future_production_migration_pr_required"] is True
    assert report["source_report_statuses"] == {
        "schema_diff_status": "Proposed",
        "migration_sql_draft_status": "Proposed",
        "dry_run_package_status": "Proposed",
        "admission_status": "Proposed",
        "proposal_status": "Proposed",
        "readiness_state": "passed",
    }
    assert report["operator_checklist"]
    assert report["validation_command_matrix"]
    assert report["rollback_checklist"]
    assert report["seed_artifact_checksum_review"]
    assert report["human_review_checklist"]
    assert report["risk_register"]


def test_bundle_report_shape_and_gates_pass() -> None:
    report = bundle.build_bundle_report()

    assert set(report) == REQUIRED_BUNDLE_REPORT_KEYS
    assert report["mode"] == "bundle-report"
    assert report["bundle_status"] == "Proposed"
    assert report["migration_bundle_review_only"] is True
    assert report["production_migration_executed"] is False
    assert report["production_seed_executed"] is False
    assert report["schema_files_modified"] is False
    assert report["sql_executed"] is False
    assert report["production_db_connected"] is False
    assert report["future_production_migration_pr_required"] is True
    assert report["schema_diff_status"] == "Proposed"
    assert report["migration_sql_draft_status"] == "Proposed"
    assert report["dry_run_package_status"] == "Proposed"
    assert report["admission_status"] == "Proposed"
    assert report["proposal_status"] == "Proposed"
    assert report["readiness_state"] == "passed"
    assert report["bundle_lint_passed"] is True
    assert report["bundle_lint_failed"] == []
    assert report["blocking_failures"] == []
    assert set(report["bundle_gate_summary"]["passed"]) == REQUIRED_REPORT_GATES
    assert report["bundle_gate_summary"]["failed"] == []


def test_cli_modes_do_not_read_dotenv_or_run_db_evidence(monkeypatch, capsys) -> None:
    _guard_db_evidence_calls(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    _guard_network(monkeypatch)

    assert bundle.main(["--contract-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "contract-report"

    assert bundle.main(["--bundle-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "bundle-report"

    assert bundle.main(["--render-bundle-json"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "render-bundle-json"

    assert bundle.main(["--lint-bundle-report"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "lint-bundle-report"


def test_reports_do_not_read_or_render_dsn_values(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    env = {
        LEGACY_ENV_DSN: "postgresql://legacy/example",
        PRIMARY_ENV_DSN: "postgresql://primary/example",
    }
    monkeypatch.setenv(LEGACY_ENV_DSN, env[LEGACY_ENV_DSN])
    monkeypatch.setenv(PRIMARY_ENV_DSN, env[PRIMARY_ENV_DSN])

    reports = [
        bundle.build_contract_report(),
        bundle.render_bundle_json(),
        bundle.lint_bundle_report(),
        bundle.build_bundle_report(),
        bundle.build_adr_check(),
    ]
    rendered = "\n".join(bundle.report_as_json(report) for report in reports)

    assert "legacy" not in rendered
    assert "primary" not in rendered
    assert env[LEGACY_ENV_DSN] not in rendered
    assert env[PRIMARY_ENV_DSN] not in rendered


def test_lint_passes_for_rendered_bundle() -> None:
    report = bundle.lint_bundle_report(bundle.render_bundle_json())

    assert report["mode"] == "lint-bundle-report"
    assert report["passed"] is True
    assert report["failed"] == []
    assert {rule["rule"] for rule in report["checked_rules"]} == REQUIRED_LINT_RULES


def test_lint_fails_if_dsn_is_injected() -> None:
    rendered = bundle.render_bundle_json()
    rendered["warnings"] = ["postgresql://example"]

    report = bundle.lint_bundle_report(rendered)

    assert report["passed"] is False
    assert "no_dsn_or_secret" in report["failed"]


def test_lint_fails_if_sql_client_is_injected() -> None:
    rendered = bundle.render_bundle_json()
    rendered["warnings"] = [f"{SQL_CLIENT} command"]

    report = bundle.lint_bundle_report(rendered)

    assert report["passed"] is False
    assert "no_" + SQL_CLIENT + "_instruction" in report["failed"]


def test_lint_fails_if_subprocess_is_injected() -> None:
    rendered = bundle.render_bundle_json()
    rendered["warnings"] = ["subprocess command"]

    report = bundle.lint_bundle_report(rendered)

    assert report["passed"] is False
    assert "no_subprocess_instruction" in report["failed"]


def test_lint_fails_if_schema_files_modified_true() -> None:
    rendered = bundle.render_bundle_json()
    rendered["schema_files_modified"] = True

    report = bundle.lint_bundle_report(rendered)

    assert report["passed"] is False
    assert "schema_files_modified_false" in report["failed"]
    assert "no_db_write_claim" in report["failed"]


def test_lint_fails_if_data_or_exports_artifact_write_is_claimed() -> None:
    rendered = bundle.render_bundle_json()
    rendered["warnings"] = ["wrote data artifact"]

    report = bundle.lint_bundle_report(rendered)

    assert report["passed"] is False
    assert "no_data_or_exports_artifact_claim" in report["failed"]


def test_lint_fails_if_blocked_report_term_appears() -> None:
    rendered = bundle.render_bundle_json()
    rendered["warnings"] = ["leaderboard"]

    report = bundle.lint_bundle_report(rendered)

    assert report["passed"] is False
    assert "no_blocked_report_terms" in report["failed"]


def test_lint_fails_when_source_report_status_is_missing() -> None:
    rendered = bundle.render_bundle_json()
    rendered["source_report_statuses"].pop("schema_diff_status")

    report = bundle.lint_bundle_report(rendered)

    assert report["passed"] is False
    assert "source_reports_present" in report["failed"]
    assert "schema_diff_status_present" in report["failed"]


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "docs" / "adr" / "ADR-migration-bundle-review-pack.md"

    assert path.is_file()
    check = bundle.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert bundle.status_value(path.read_text(encoding="utf-8")) == "Proposed"


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "docs" / "adr" / "ADR-migration-bundle-review-pack.md").read_text(encoding="utf-8")
    normalized = bundle.normalize_text(content)
    for needle in [
        "migration_bundle_review_only=true",
        "production_migration_executed=false",
        "production_seed_executed=false",
        "schema_files_modified=false",
        "sql_executed=false",
        "production_db_connected=false",
        "future production migration PR required",
        "Bundle Contents",
        "Review Pack Boundaries",
        "Required Bundle Gates",
        "Human Review Checklist",
        "no production migration",
        "no production seed",
        "no schema file edits",
    ]:
        assert bundle.normalize_text(needle) in normalized


def test_adr_check_cli_prints_json_and_uses_exit_code(capsys) -> None:
    assert bundle.main(["--adr-check"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "adr-check"
    assert payload["passed"] is True


def test_missing_status_fails_adr_check(tmp_path: Path) -> None:
    adr = tmp_path / "bundle.md"
    adr.write_text("# ADR\n\n## Context\n\n`migration_bundle_review_only=true`\n", encoding="utf-8")

    check = bundle.build_adr_check(adr)

    assert check["passed"] is False
    assert "status_is_proposed" in check["failed"]


def test_missing_migration_bundle_review_only_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("`migration_bundle_review_only=true`\n", ""), encoding="utf-8")

    check = bundle.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_migration_bundle_review_only" in check["failed"]


def test_production_migration_executed_phrase_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(
        adr.read_text(encoding="utf-8").replace("production_migration_executed=false", "production_migration_executed=true"),
        encoding="utf-8",
    )

    check = bundle.build_adr_check(adr)

    assert check["passed"] is False
    assert "production_migration_executed_false" in check["failed"]
    assert "no_blocked_report_terms" in check["failed"]


def test_missing_bundle_contents_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("## Bundle Contents", "## Bundle Notes"), encoding="utf-8")

    check = bundle.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_bundle_contents" in check["failed"]


def test_blocked_term_in_adr_fails_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8") + "\n\nleaderboard\n", encoding="utf-8")

    check = bundle.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_blocked_report_terms" in check["failed"]


def test_schema_diff_report_unavailable_fails_bundle_report(monkeypatch) -> None:
    def fail_report() -> dict[str, Any]:
        raise AssertionError("schema diff report unavailable")

    monkeypatch.setattr(bundle.schema_diff_draft_renderer, "build_diff_report", fail_report)

    report = bundle.build_bundle_report()

    assert "schema_diff_draft_report_available" in report["blocking_failures"]
    assert "bundle_json_rendered" in report["blocking_failures"]
    assert report["schema_diff_status"] is None


def test_source_reports_and_output_have_no_blocked_report_terms() -> None:
    reports = [
        bundle.build_contract_report(),
        bundle.render_bundle_json(),
        bundle.lint_bundle_report(),
        bundle.build_bundle_report(),
        bundle.build_adr_check(),
    ]

    for report in reports:
        text = bundle.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (ROOT / "scripts" / "platform" / "migration_bundle_review_pack.py").read_text(encoding="utf-8")

    for forbidden in [
        "PG_SEARCH_BENCH_DSN",
        "EMPEROR_EVAL_PG_DSN",
        "subprocess.run",
        '"psql"',
        "psycopg",
        "public.",
        "production_migration_executed = True",
        "production_seed_executed = True",
        "schema_files_modified = True",
        "sql_executed = True",
        "production_db_connected = True",
    ]:
        assert forbidden not in source


def test_guard_paths_use_utf8_chinese_names() -> None:
    protected_paths = {path.as_posix() for path in PROTECTED_PATHS}

    assert any(path.endswith("docs/\u7687\u5e1d\u7efc\u5408\u8bc4\u4ef7\u4f53\u7cfb\u8bc4\u5206\u6807\u51c6.md") for path in protected_paths)
    assert any(path.endswith("docs/\u5206\u9879\u89c4\u5219") for path in protected_paths)
    assert any(path.endswith("docs/\u8bc1\u636e\u89c4\u5219") for path in protected_paths)
    assert any(path.endswith("db/schema.sql") for path in protected_paths)
    assert any(path.endswith("db/postgres/001_init.sql") for path in protected_paths)


def test_renderers_do_not_touch_protected_path_mtimes() -> None:
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    bundle.render_bundle_json()
    bundle.build_bundle_report()
    bundle.lint_bundle_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before


def _tmp_adr(tmp_path: Path) -> Path:
    adr = tmp_path / "ADR-migration-bundle-review-pack.md"
    adr.write_text(
        (ROOT / "docs" / "adr" / "ADR-migration-bundle-review-pack.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return adr


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in migration bundle review pack")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_db_evidence_calls(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("database evidence functions must not run")

    matrix = bundle.cutover_readiness_matrix
    monkeypatch.setattr(matrix.seed_artifact_db_preflight, "run_preflight", fail_call)
    monkeypatch.setattr(matrix.isolated_seed_dry_apply, "run_dry_apply", fail_call)
    monkeypatch.setattr(matrix.isolated_seed_rollback_restore, "run_rehearsal", fail_call)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"migration bundle review pack must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"migration bundle review pack must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
