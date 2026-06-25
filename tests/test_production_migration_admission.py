from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import production_migration_admission as admission  # noqa: E402
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
PROTECTED_PATHS = [
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]
REQUIRED_CONTRACT_KEYS = {
    "mode",
    "admission_version",
    "status",
    "supported_modes",
    "source_reports",
    "admission_sections",
    "allowed_future_file_scope",
    "forbidden_current_pr_actions",
    "machine_gates",
    "human_gates",
    "non_goals",
    "boundaries",
    "limitations",
    "future_work",
}
REQUIRED_ADMISSION_KEYS = {
    "mode",
    "admission_version",
    "adr_path",
    "proposal_status",
    "readiness_state",
    "ready_for_next_stage",
    "ready_for_production_migration",
    "admission_status",
    "admission_only",
    "production_migration_executed",
    "future_production_migration_pr_required",
    "allowed_future_file_scope",
    "forbidden_current_pr_actions",
    "machine_gates",
    "human_gates",
    "rollback_plan_requirements",
    "gates",
    "blocking_failures",
    "warnings",
}
REQUIRED_ADMISSION_GATES = {
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "proposal_status_is_proposed",
    "admission_status_is_proposed",
    "admission_only_true",
    "production_migration_executed_false",
    "future_production_migration_pr_required",
    "allowed_future_file_scope_declared",
    "current_pr_forbids_schema_file_edits",
    "current_pr_forbids_production_migration",
    "current_pr_forbids_production_seed",
    "current_pr_forbids_public_schema_write",
    "machine_gates_declared",
    "human_gates_declared",
    "rollback_plan_declared",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
}


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_data_and_export_reads(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = admission.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_CONTRACT_KEYS
    assert report["mode"] == "contract-report"
    assert report["admission_version"] == admission.ADMISSION_VERSION
    assert report["status"] == "Proposed"
    assert report["supported_modes"] == ["contract-report", "admission-report", "adr-check"]


def test_admission_report_is_offline_and_uses_readiness_matrix_without_db(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = admission.build_admission_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_ADMISSION_KEYS
    assert report["mode"] == "admission-report"
    assert report["proposal_status"] == "Proposed"
    assert report["readiness_state"] == "passed"
    assert report["ready_for_next_stage"] is True
    assert report["ready_for_production_migration"] is False
    assert report["admission_status"] == "Proposed"
    assert report["admission_only"] is True
    assert report["production_migration_executed"] is False
    assert report["future_production_migration_pr_required"] is True
    assert report["blocking_failures"] == []
    assert {gate["gate"] for gate in report["gates"]} == REQUIRED_ADMISSION_GATES
    assert all(gate["passed"] for gate in report["gates"])


def test_reports_do_not_read_or_render_dsn_values(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    env = {
        LEGACY_ENV_DSN: "postgresql://legacy/example",
        PRIMARY_ENV_DSN: "postgresql://primary/example",
    }
    monkeypatch.setenv(LEGACY_ENV_DSN, env[LEGACY_ENV_DSN])
    monkeypatch.setenv(PRIMARY_ENV_DSN, env[PRIMARY_ENV_DSN])

    report = admission.build_admission_report()
    rendered = admission.report_as_json(report)

    assert "legacy" not in rendered
    assert "primary" not in rendered
    assert env[LEGACY_ENV_DSN] not in rendered
    assert env[PRIMARY_ENV_DSN] not in rendered


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-production-migration-pr-admission.md"

    assert path.is_file()
    check = admission.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert admission.status_value(path.read_text(encoding="utf-8")) == "Proposed"


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "archive" / "docs" / "adr" / "ADR-production-migration-pr-admission.md").read_text(encoding="utf-8")
    normalized = admission.normalize_text(content)
    for needle in [
        "admission_only=true",
        "production_migration_executed=false",
        "future production migration PR required",
        "no production migration in this PR",
        "no production seed in this PR",
        "no schema file edits in this PR",
        "Allowed Future Production Migration PR File Scope",
        "Required Machine Gates",
        "Required Human Gates",
        "Required Rollback Plan",
    ]:
        assert admission.normalize_text(needle) in normalized


def test_adr_check_cli_prints_json_and_uses_exit_code(capsys) -> None:
    assert admission.main(["--adr-check"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "adr-check"
    assert payload["passed"] is True


def test_cli_modes_print_json(capsys, monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    assert admission.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert admission.main(["--admission-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "admission-report"
    assert report["admission_only"] is True
    assert report["production_migration_executed"] is False
    assert report["future_production_migration_pr_required"] is True
    assert report["ready_for_production_migration"] is False


def test_missing_status_fails_adr_check(tmp_path: Path) -> None:
    adr = tmp_path / "admission.md"
    adr.write_text("# ADR\n\n## Context\n\nadmission_only=true\n", encoding="utf-8")

    check = admission.build_adr_check(adr)

    assert check["passed"] is False
    assert "status_is_proposed" in check["failed"]


def test_missing_admission_only_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("`admission_only=true`\n\n", ""), encoding="utf-8")

    check = admission.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_admission_only" in check["failed"]


def test_production_migration_executed_phrase_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(
        adr.read_text(encoding="utf-8").replace("production_migration_executed=false", "production_migration_executed=true"),
        encoding="utf-8",
    )

    check = admission.build_adr_check(adr)

    assert check["passed"] is False
    assert "production_migration_executed_false" in check["failed"]
    assert "no_blocked_report_terms" in check["failed"]


def test_missing_human_gates_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("## Required Human Gates", "## Reviewer Sign-offs"), encoding="utf-8")

    check = admission.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_required_human_gates" in check["failed"]


def test_formal_migration_proposal_unavailable_blocks_admission_report(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise RuntimeError("proposal unavailable")

    monkeypatch.setattr(admission.formal_migration_proposal, "build_proposal_report", fail_call)

    report = admission.build_admission_report()

    assert report["ready_for_next_stage"] is False
    assert "formal_migration_proposal_available" in report["blocking_failures"]


def test_blocked_term_in_adr_fails_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8") + "\n\nleaderboard\n", encoding="utf-8")

    check = admission.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_blocked_report_terms" in check["failed"]


def test_source_inspection_forbids_unsafe_terms() -> None:
    source = (ROOT / "scripts" / "platform" / "production_migration_admission.py").read_text(encoding="utf-8")

    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "psycopg" not in source
    assert "public." not in source
    assert "production_migration_executed = True" not in source
    assert "ready_for_production_migration = True" not in source


def test_reports_contain_no_blocked_terms(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    reports = [
        admission.build_contract_report(),
        admission.build_admission_report(),
        admission.build_adr_check(),
    ]

    for report in reports:
        text = admission.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_guard_paths_use_utf8_chinese_names() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    protected_paths = {path.as_posix() for path in PROTECTED_PATHS}

    assert any(path.endswith("docs/皇帝综合评价体系评分标准.md") for path in protected_paths)
    assert any(path.endswith("docs/分项规则") for path in protected_paths)
    assert any(path.endswith("docs/证据规则") for path in protected_paths)
    mojibake_terms = [
        "".join(chr(codepoint) for codepoint in (0x9428, 0x56E7, 0x7B23)),
        "".join(chr(codepoint) for codepoint in (0x9352, 0x55DB, 0x300D)),
        "".join(chr(codepoint) for codepoint in (0x7487, 0x4F79, 0x5D41)),
    ]
    for mojibake in mojibake_terms:
        assert mojibake not in source


def _tmp_adr(tmp_path: Path) -> Path:
    adr = tmp_path / "ADR-production-migration-pr-admission.md"
    adr.write_text(
        (ROOT / "archive" / "docs" / "adr" / "ADR-production-migration-pr-admission.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return adr


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in production migration admission")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_db_evidence_calls(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("database evidence functions must not run")

    matrix = admission.cutover_readiness_matrix
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
            raise AssertionError(f"production migration admission must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if forbidden_path(self):
            raise AssertionError(f"production migration admission must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"production migration admission must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"production migration admission must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
