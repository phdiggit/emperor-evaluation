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

from scripts.platform import formal_migration_proposal as proposal  # noqa: E402
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
    "proposal_version",
    "status",
    "supported_modes",
    "source_reports",
    "proposal_sections",
    "non_goals",
    "boundaries",
    "limitations",
    "future_work",
}
REQUIRED_PROPOSAL_KEYS = {
    "mode",
    "proposal_version",
    "adr_path",
    "readiness_state",
    "ready_for_next_stage",
    "ready_for_production_migration",
    "next_stage",
    "proposal_status",
    "required_production_pr_gates",
    "migration_plan_outline",
    "non_goals",
    "risks",
    "rollback_strategy",
    "gates",
    "failed",
    "warnings",
}
REQUIRED_PROPOSAL_GATES = {
    "readiness_report_available",
    "readiness_next_stage_true",
    "production_migration_false",
    "proposal_status_is_proposed",
    "adr_exists",
    "adr_status_is_proposed",
    "adr_declares_separate_approved_pr",
    "adr_declares_no_production_migration",
    "adr_declares_no_production_seed",
    "adr_preserves_jsonl_source_of_truth",
    "adr_lists_required_production_gates",
    "adr_lists_rollback_restore_strategy",
    "no_schema_files_modified",
    "no_data_or_exports_written",
    "no_blocked_report_terms",
}


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = proposal.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_CONTRACT_KEYS
    assert report["mode"] == "contract-report"
    assert report["proposal_version"] == proposal.PROPOSAL_VERSION
    assert report["status"] == "Proposed"
    assert report["supported_modes"] == ["contract-report", "proposal-report", "adr-check"]


def test_proposal_report_is_offline_and_uses_readiness_matrix_without_db(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = proposal.build_proposal_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_PROPOSAL_KEYS
    assert report["mode"] == "proposal-report"
    assert report["readiness_state"] == "passed"
    assert report["ready_for_next_stage"] is True
    assert report["ready_for_production_migration"] is False
    assert report["proposal_status"] == "Proposed"
    assert report["failed"] == []
    assert {gate["gate"] for gate in report["gates"]} == REQUIRED_PROPOSAL_GATES
    assert all(gate["passed"] for gate in report["gates"])


def test_reports_do_not_read_or_render_dsn_values(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    env = {
        LEGACY_ENV_DSN: "postgresql://legacy/example",
        PRIMARY_ENV_DSN: "postgresql://primary/example",
    }
    monkeypatch.setattr(
        proposal.cutover_readiness_matrix,
        "build_readiness_report",
        lambda include_db_evidence=False, env=None: {
            "mode": "readiness-report",
            "readiness_state": "passed",
            "ready_for_next_stage": True,
            "ready_for_production_migration": False,
            "warnings": [],
        },
    )

    report = proposal.build_proposal_report()
    rendered = proposal.report_as_json(report)

    assert "legacy" not in rendered
    assert "primary" not in rendered
    assert env[LEGACY_ENV_DSN] not in rendered
    assert env[PRIMARY_ENV_DSN] not in rendered


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-formal-migration-proposal.md"

    assert path.is_file()
    check = proposal.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert proposal.status_value(path.read_text(encoding="utf-8")) == "Proposed"


def test_adr_contains_required_boundaries() -> None:
    content = (ROOT / "archive" / "docs" / "adr" / "ADR-formal-migration-proposal.md").read_text(encoding="utf-8")
    normalized = proposal.normalize_text(content)
    for needle in [
        "canonical JSONL remains source-of-truth",
        "ready_for_production_migration=false",
        "separate approved PR",
        "no production migration",
        "no production seed",
        "required production PR gates",
        "rollback / restore",
        "no db/schema.sql change",
        "no db/postgres/001_init.sql change",
    ]:
        assert proposal.normalize_text(needle) in normalized


def test_adr_check_cli_prints_json_and_uses_exit_code(capsys) -> None:
    assert proposal.main(["--adr-check"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "adr-check"
    assert payload["passed"] is True


def test_cli_modes_print_json(capsys, monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    assert proposal.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert proposal.main(["--proposal-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "proposal-report"
    assert report["ready_for_production_migration"] is False


def test_missing_status_fails_adr_check(tmp_path: Path) -> None:
    adr = tmp_path / "proposal.md"
    adr.write_text("# ADR\n\n## Context\n\nseparate approved PR\n", encoding="utf-8")

    check = proposal.build_adr_check(adr)

    assert check["passed"] is False
    assert "status_is_proposed" in check["failed"]


def test_missing_separate_approved_pr_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8").replace("separate approved PR", "later approval"), encoding="utf-8")

    check = proposal.build_adr_check(adr)

    assert check["passed"] is False
    assert "declares_separate_approved_pr" in check["failed"]


def test_production_migration_ready_phrase_fails_adr_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(
        adr.read_text(encoding="utf-8") + "\n\nproduction migration ready\n",
        encoding="utf-8",
    )

    check = proposal.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_blocked_report_terms" in check["failed"]


def test_readiness_report_not_ready_fails_proposal_report() -> None:
    readiness = {
        "mode": "readiness-report",
        "readiness_state": "failed",
        "ready_for_next_stage": False,
        "ready_for_production_migration": False,
        "warnings": ["example"],
    }

    report = proposal.build_proposal_report(readiness_report=readiness)

    assert "readiness_next_stage_true" in report["failed"]


def test_blocked_term_in_adr_fails_check(tmp_path: Path) -> None:
    adr = _tmp_adr(tmp_path)
    adr.write_text(adr.read_text(encoding="utf-8") + "\n\nleaderboard\n", encoding="utf-8")

    check = proposal.build_adr_check(adr)

    assert check["passed"] is False
    assert "no_blocked_report_terms" in check["failed"]


def test_source_inspection_forbids_unsafe_terms() -> None:
    source = (ROOT / "scripts" / "platform" / "formal_migration_proposal.py").read_text(encoding="utf-8")

    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "psycopg" not in source
    assert "public." not in source
    assert "production_seed_applied = True" not in source
    assert "ready_for_production_migration = True" not in source


def test_reports_contain_no_blocked_terms(monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    reports = [
        proposal.build_contract_report(),
        proposal.build_proposal_report(),
        proposal.build_adr_check(),
    ]

    for report in reports:
        text = proposal.report_as_json(report).lower()
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
    adr = tmp_path / "ADR-formal-migration-proposal.md"
    adr.write_text(
        (ROOT / "archive" / "docs" / "adr" / "ADR-formal-migration-proposal.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return adr


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in formal migration proposal")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_db_evidence_calls(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("database evidence functions must not run")

    matrix = proposal.cutover_readiness_matrix
    monkeypatch.setattr(matrix.seed_artifact_db_preflight, "run_preflight", fail_call)
    monkeypatch.setattr(matrix.isolated_seed_dry_apply, "run_dry_apply", fail_call)
    monkeypatch.setattr(matrix.isolated_seed_rollback_restore, "run_rehearsal", fail_call)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"formal migration proposal must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"formal migration proposal must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
