from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import production_migration_dry_run_package as package  # noqa: E402
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
PROTECTED_PATHS = [
    ROOT / "docs" / "\u7687\u5e1d\u7efc\u5408\u8bc4\u4ef7\u4f53\u7cfb\u8bc4\u5206\u6807\u51c6.md",
    ROOT / "docs" / "\u5206\u9879\u89c4\u5219",
    ROOT / "docs" / "\u8bc1\u636e\u89c4\u5219",
]
REQUIRED_CONTRACT_KEYS = {
    "mode",
    "package_version",
    "status",
    "supported_modes",
    "source_reports",
    "package_sections",
    "dry_run_package_contents",
    "forbidden_current_pr_actions",
    "validation_command_matrix",
    "operator_checklist",
    "non_goals",
    "boundaries",
    "limitations",
    "future_work",
}
REQUIRED_PACKAGE_KEYS = {
    "mode",
    "package_version",
    "adr_path",
    "package_status",
    "dry_run_package_only",
    "production_migration_executed",
    "production_seed_executed",
    "schema_files_modified",
    "future_production_migration_pr_required",
    "admission_status",
    "proposal_status",
    "readiness_state",
    "schema_diff_outline",
    "migration_sql_draft_outline",
    "operator_checklist",
    "validation_command_matrix",
    "rollback_checklist",
    "seed_artifact_checksum_review",
    "forbidden_current_pr_actions",
    "gates",
    "blocking_failures",
    "warnings",
}
REQUIRED_PACKAGE_GATES = {
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "package_status_is_proposed",
    "dry_run_package_only_true",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "future_production_migration_pr_required",
    "schema_diff_outline_declared",
    "migration_sql_draft_outline_declared",
    "operator_checklist_declared",
    "validation_command_matrix_declared",
    "rollback_checklist_declared",
    "seed_artifact_checksum_review_declared",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
}


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_data_and_export_reads(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = package.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_CONTRACT_KEYS
    assert report["mode"] == "contract-report"
    assert report["package_version"] == package.PACKAGE_VERSION
    assert report["status"] == "Proposed"
    assert report["supported_modes"] == ["contract-report", "package-report", "adr-check"]


def test_package_report_is_offline_and_uses_readiness_matrix_without_db(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = package.build_package_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_PACKAGE_KEYS
    assert report["mode"] == "package-report"
    assert report["package_status"] == "Proposed"
    assert report["dry_run_package_only"] is True
    assert report["production_migration_executed"] is False
    assert report["production_seed_executed"] is False
    assert report["schema_files_modified"] is False
    assert report["future_production_migration_pr_required"] is True
    assert report["admission_status"] == "Proposed"
    assert report["proposal_status"] == "Proposed"
    assert report["readiness_state"] == "passed"
    assert report["blocking_failures"] == []
    assert {gate["gate"] for gate in report["gates"]} == REQUIRED_PACKAGE_GATES
    assert all(gate["passed"] for gate in report["gates"])


def test_reports_do_not_read_or_render_dsn_values(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    env = {
        LEGACY_ENV_DSN: "postgresql://legacy/example",
        PRIMARY_ENV_DSN: "postgresql://primary/example",
    }
    monkeypatch.setenv(LEGACY_ENV_DSN, env[LEGACY_ENV_DSN])
    monkeypatch.setenv(PRIMARY_ENV_DSN, env[PRIMARY_ENV_DSN])

    report = package.build_package_report()
    rendered = package.report_as_json(report)

    assert "legacy" not in rendered
    assert "primary" not in rendered
    assert env[LEGACY_ENV_DSN] not in rendered
    assert env[PRIMARY_ENV_DSN] not in rendered


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "docs" / "adr" / "ADR-production-migration-dry-run-package.md"

    assert path.is_file()
    check = package.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert package.status_value(path.read_text(encoding="utf-8")) == "Proposed"


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "docs" / "adr" / "ADR-production-migration-dry-run-package.md").read_text(encoding="utf-8")
    normalized = package.normalize_text(content)
    for needle in [
        "dry_run_package_only=true",
        "production_migration_executed=false",
        "production_seed_executed=false",
        "schema_files_modified=false",
        "future production migration PR required",
        "no production migration",
        "no production seed",
        "schema diff outline",
        "migration SQL draft outline",
        "operator checklist",
        "validation command matrix",
        "rollback checklist",
        "seed artifact checksum review",
    ]:
        assert package.normalize_text(needle) in normalized


def test_adr_check_cli_prints_json_and_uses_exit_code(capsys) -> None:
    assert package.main(["--adr-check"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "adr-check"
    assert payload["passed"] is True


def test_cli_modes_print_json(capsys, monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    assert package.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert package.main(["--package-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "package-report"
    assert report["dry_run_package_only"] is True
    assert report["production_migration_executed"] is False
    assert report["production_seed_executed"] is False
    assert report["schema_files_modified"] is False


def test_missing_status_fails_adr_check(tmp_path: Path) -> None:
    adr = tmp_path / "package.md"
    adr.write_text("# ADR\n\n## Context\n\n`dry_run_package_only=true`\n", encoding="utf-8")

    check = package.build_adr_check(adr)

    assert check["passed"] is False
    assert "status_is_proposed" in check["failed"]


def test_missing_dry_run_package_only_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("`dry_run_package_only=true`\n\n", ""), encoding="utf-8")

    check = package.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_dry_run_package_only" in check["failed"]


def test_production_migration_executed_phrase_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(
        adr.read_text(encoding="utf-8").replace("production_migration_executed=false", "production_migration_executed=true"),
        encoding="utf-8",
    )

    check = package.build_adr_check(adr)

    assert check["passed"] is False
    assert "production_migration_executed_false" in check["failed"]
    assert "no_blocked_report_terms" in check["failed"]


def test_missing_operator_checklist_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("## Operator Checklist", "## Operator Notes"), encoding="utf-8")

    check = package.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_operator_checklist" in check["failed"]


def test_admission_report_unavailable_blocks_package_report(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise RuntimeError("admission unavailable")

    monkeypatch.setattr(package.production_migration_admission, "build_admission_report", fail_call)

    report = package.build_package_report()

    assert "production_migration_admission_available" in report["blocking_failures"]


def test_blocked_term_in_adr_fails_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8") + "\n\nleaderboard\n", encoding="utf-8")

    check = package.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_blocked_report_terms" in check["failed"]


def test_source_inspection_forbids_unsafe_terms() -> None:
    source = (ROOT / "scripts" / "platform" / "production_migration_dry_run_package.py").read_text(encoding="utf-8")

    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "psycopg" not in source
    assert "public." not in source
    assert "production_migration_executed = True" not in source
    assert "production_seed_executed = True" not in source
    assert "schema_files_modified = True" not in source


def test_reports_contain_no_blocked_terms(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    reports = [
        package.build_contract_report(),
        package.build_package_report(),
        package.build_adr_check(),
    ]

    for report in reports:
        text = package.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_guard_paths_use_utf8_chinese_names() -> None:
    protected_paths = {path.as_posix() for path in PROTECTED_PATHS}

    assert any(path.endswith("docs/\u7687\u5e1d\u7efc\u5408\u8bc4\u4ef7\u4f53\u7cfb\u8bc4\u5206\u6807\u51c6.md") for path in protected_paths)
    assert any(path.endswith("docs/\u5206\u9879\u89c4\u5219") for path in protected_paths)
    assert any(path.endswith("docs/\u8bc1\u636e\u89c4\u5219") for path in protected_paths)


def _tmp_adr(tmp_path: Path) -> Path:
    adr = tmp_path / "ADR-production-migration-dry-run-package.md"
    adr.write_text(
        (ROOT / "docs" / "adr" / "ADR-production-migration-dry-run-package.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return adr


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in production migration dry-run package")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_db_evidence_calls(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("database evidence functions must not run")

    matrix = package.cutover_readiness_matrix
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
            raise AssertionError(f"production migration dry-run package must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if forbidden_path(self):
            raise AssertionError(f"production migration dry-run package must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"production migration dry-run package must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"production migration dry-run package must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
