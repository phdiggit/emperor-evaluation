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

from scripts.platform import cutover_readiness_matrix as matrix  # noqa: E402
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PROTECTED_PATHS = [
    ROOT / "data",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
    ROOT / "exports",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_contract_report_is_offline_and_preserves_guarded_paths(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = matrix.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["matrix_version"] == matrix.MATRIX_VERSION
    assert report["status"] == "Proposed"
    assert set(report["readiness_dimensions"]) == set(matrix.READINESS_DIMENSIONS)
    assert set(report["required_gates"]) == set(matrix.REQUIRED_GATES)
    assert report["optional_db_evidence"]["enabled_by_default"] is False


def test_check_only_reads_primary_env_presence_and_does_not_connect(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    result = matrix.check_environment(env={}, driver_available=False)

    assert result["mode"] == "check"
    assert result["dsn_present"] is False
    assert result["dsn_source"] == "skip"
    assert result["driver_available"] is False
    assert result["will_connect_by_default"] is False
    assert result["include_db_evidence_required_for_connection"] is True
    assert result["will_write_db"] is False
    assert result["will_modify_repo"] is False


def test_check_ignores_legacy_dsn_names_and_never_prints_secret() -> None:
    result = matrix.check_environment(
        env={
            LEGACY_ENV_DSN: "postgresql://legacy/example",
            matrix.PRIMARY_ENV_DSN: "postgresql://primary/example",
        },
        driver_available=True,
    )

    rendered = matrix.report_as_json(result)
    assert result["dsn_present"] is True
    assert result["dsn_source"] == f"env:{matrix.PRIMARY_ENV_DSN}"
    assert "legacy" not in rendered
    assert "primary" not in rendered

    legacy_only = matrix.check_environment(env={LEGACY_ENV_DSN: "postgresql://legacy/example"})
    assert legacy_only["dsn_present"] is False
    assert legacy_only["dsn_source"] == "skip"


def test_reports_contain_no_blocked_terms() -> None:
    reports = [
        matrix.build_contract_report(),
        matrix.check_environment(env={}, driver_available=False),
        matrix.build_readiness_report(env={}),
        matrix.build_readiness_report(include_db_evidence=True, env={}),
    ]

    for report in reports:
        text = matrix.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_readiness_report_default_is_offline_and_complete(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_dotenv_reads(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = matrix.build_readiness_report(env={})

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert report["mode"] == "readiness-report"
    assert report["ready_for_next_stage"] is True
    assert report["ready_for_production_migration"] is False
    assert report["decision"]["next_stage"] == matrix.NEXT_STAGE
    assert report["decision"]["stage"] == "cutover_readiness_matrix"
    assert report["failed"] == []
    assert report["db_evidence"]["state"] == "skipped"
    assert report["db_evidence"]["reason"] == "not_requested"
    assert {dimension["name"] for dimension in report["dimensions"]} == set(matrix.READINESS_DIMENSIONS)
    assert all(gate["passed"] for gate in report["gates"] if gate["required"])


def test_cli_modes_print_json(capsys, monkeypatch) -> None:
    _guard_db_evidence_calls(monkeypatch)
    assert matrix.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert matrix.main(["--check"]) == 0
    check = json.loads(capsys.readouterr().out)
    assert check["mode"] == "check"
    assert check["will_connect_by_default"] is False

    assert matrix.main(["--readiness-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "readiness-report"
    assert report["db_evidence"]["reason"] == "not_requested"


def test_formal_schema_contract_failure_blocks_next_stage(monkeypatch) -> None:
    monkeypatch.setattr(
        matrix.formal_schema_draft,
        "build_contract_report",
        lambda: {"mode": "contract-report", "status": "Failed", "draft_version": "broken"},
    )

    report = matrix.build_readiness_report(env={})

    assert report["ready_for_next_stage"] is False
    assert "formal_schema_draft_contract_available" in report["failed"]


def test_seed_artifact_validation_failure_blocks_next_stage(monkeypatch) -> None:
    monkeypatch.setattr(
        matrix.seed_artifact_validation_matrix,
        "validate_artifact_and_manifest",
        lambda _artifact, _manifest: {
            "artifact_valid": False,
            "manifest_valid": False,
            "table_gate_valid": False,
            "source_boundary_valid": False,
            "passed": False,
            "failed": ["example_artifact_rule"],
            "checked_rules": [],
        },
    )

    report = matrix.build_readiness_report(env={})

    assert report["ready_for_next_stage"] is False
    assert "seed_artifact_validation_passed" in report["failed"]


def test_blocked_report_term_in_evidence_raises(monkeypatch) -> None:
    original = matrix.seed_artifact_plan.build_contract_report

    def poisoned_contract() -> dict[str, Any]:
        report = original()
        report["future_work"] = ["rank"]
        return report

    monkeypatch.setattr(matrix.seed_artifact_plan, "build_contract_report", poisoned_contract)

    with pytest.raises(AssertionError):
        matrix.build_readiness_report(env={})


def test_missing_source_of_truth_blocks_next_stage(monkeypatch) -> None:
    original = matrix.seed_artifact_renderer.build_seed_artifact

    def artifact_without_source(root: Path = matrix.ROOT) -> dict[str, Any]:
        artifact = original(root)
        artifact["source_of_truth"] = None
        return artifact

    monkeypatch.setattr(matrix.seed_artifact_renderer, "build_seed_artifact", artifact_without_source)

    report = matrix.build_readiness_report(env={})

    assert report["ready_for_next_stage"] is False
    assert "source_of_truth_is_canonical_jsonl" in report["failed"]


def test_production_guardrail_false_blocks_next_stage(monkeypatch) -> None:
    original = matrix.seed_artifact_renderer.build_seed_artifact

    def artifact_written_to_repo(root: Path = matrix.ROOT) -> dict[str, Any]:
        artifact = original(root)
        artifact["artifact_written_to_repo"] = True
        return artifact

    monkeypatch.setattr(matrix.seed_artifact_renderer, "build_seed_artifact", artifact_written_to_repo)

    report = matrix.build_readiness_report(env={})

    assert report["ready_for_next_stage"] is False
    assert "no_repo_artifact_write" in report["failed"]


def test_include_db_evidence_without_dsn_is_skipped_not_passed(monkeypatch) -> None:
    _guard_network(monkeypatch)
    _guard_db_evidence_calls(monkeypatch)

    report = matrix.build_readiness_report(include_db_evidence=True, env={})

    assert report["db_evidence"]["state"] == "skipped"
    assert report["db_evidence"]["reason"] == "no_dsn"
    assert report["db_evidence"]["passed"] is False
    assert report["ready_for_next_stage"] is True


def test_include_db_evidence_with_fake_env_can_pass(monkeypatch) -> None:
    monkeypatch.setattr(matrix, "is_psycopg_available", lambda: True)
    monkeypatch.setattr(matrix.seed_artifact_db_preflight, "run_preflight", _fake_db_report)
    monkeypatch.setattr(matrix.isolated_seed_dry_apply, "run_dry_apply", _fake_db_report)
    monkeypatch.setattr(matrix.isolated_seed_rollback_restore, "run_rehearsal", _fake_db_report)

    report = matrix.build_readiness_report(
        include_db_evidence=True,
        env={matrix.PRIMARY_ENV_DSN: "postgresql://example/db"},
    )

    assert report["db_evidence"]["state"] == "passed"
    assert report["db_evidence"]["passed"] is True
    assert report["ready_for_next_stage"] is True


def test_optional_db_evidence_failure_warns_without_blocking(monkeypatch) -> None:
    monkeypatch.setattr(matrix, "is_psycopg_available", lambda: True)
    monkeypatch.setattr(matrix.seed_artifact_db_preflight, "run_preflight", _fake_db_report)
    monkeypatch.setattr(matrix.isolated_seed_dry_apply, "run_dry_apply", _fake_failed_db_report)
    monkeypatch.setattr(matrix.isolated_seed_rollback_restore, "run_rehearsal", _fake_db_report)

    report = matrix.build_readiness_report(
        include_db_evidence=True,
        env={matrix.PRIMARY_ENV_DSN: "postgresql://example/db"},
    )

    assert report["db_evidence"]["state"] == "warning"
    assert report["db_evidence"]["failed"] == ["isolated_dry_apply"]
    assert report["ready_for_next_stage"] is True


def test_source_inspection_forbids_unsafe_terms() -> None:
    source = (ROOT / "scripts" / "platform" / "cutover_readiness_matrix.py").read_text(encoding="utf-8")

    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "public." not in source
    assert "production migration execution" not in source
    assert "production_seed_applied = True" not in source
    assert "ready_for_production_migration = True" not in source
    assert matrix.PRIMARY_ENV_DSN in source


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


def _fake_db_report(*_args: object, **_kwargs: object) -> dict[str, Any]:
    return {"mode": "fake", "passed": True, "failed": []}


def _fake_failed_db_report(*_args: object, **_kwargs: object) -> dict[str, Any]:
    return {"mode": "fake", "passed": False, "failed": ["example_db_rule"]}


def _guard_db_evidence_calls(monkeypatch) -> None:
    def fail_call(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("database evidence functions must not run")

    monkeypatch.setattr(matrix.seed_artifact_db_preflight, "run_preflight", fail_call)
    monkeypatch.setattr(matrix.isolated_seed_dry_apply, "run_dry_apply", fail_call)
    monkeypatch.setattr(matrix.isolated_seed_rollback_restore, "run_rehearsal", fail_call)


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden before explicit database evidence")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_dotenv_reads(monkeypatch) -> None:
    original_read_text = Path.read_text
    original_open = Path.open

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"cutover readiness matrix must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.name == ".env":
            raise AssertionError(f"cutover readiness matrix must not read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "open", guarded_open)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
