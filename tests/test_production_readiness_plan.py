from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import platform_chain_checkpoint, production_readiness_plan


FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in production readiness report")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        blocked_parts = {".env", "batches"}
        if self.name in blocked_parts or ("archive" in self.parts and "data" in self.parts):
            raise AssertionError(f"production readiness report must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = production_readiness_plan.build_contract_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["plan_version"] == "production-readiness-plan-v1"
    assert report["status"] == "Proposed"
    assert set(report) == {
        "mode",
        "plan_version",
        "status",
        "adr_files",
        "completed_platform_chain",
        "formal_migration_preconditions",
        "cutover_phases",
        "rollback_strategy",
        "backup_strategy",
        "seed_strategy",
        "validation_gates",
        "non_goals",
        "strict_boundaries",
        "future_work",
        "limitations",
    }
    assert "does_not_read_dotenv" in report["strict_boundaries"]
    assert "does_not_connect_to_database" in report["strict_boundaries"]
    assert "does_not_read_data_batches_or_archive_data" in report["strict_boundaries"]


def test_adr_files_exist_and_are_proposed() -> None:
    report = production_readiness_plan.build_contract_report()

    assert report["adr_files"] == [
        "docs/adr/ADR-postgres-formal-migration-plan.md",
        "docs/adr/ADR-jsonl-to-target-cutover-plan.md",
        "docs/adr/ADR-platform-rollback-backup-seed-strategy.md",
    ]
    for rel_path in report["adr_files"]:
        path = ROOT / rel_path
        assert path.is_file()
        assert _status_value(path) == "Proposed."


def test_report_includes_completed_platform_chain() -> None:
    report = production_readiness_plan.build_contract_report()

    assert report["completed_platform_chain"] == platform_chain_checkpoint.COMPLETED_CHAIN
    assert "anchors_target_mapper_prototype" in report["completed_platform_chain"]


def test_formal_migration_preconditions_cover_required_gates() -> None:
    preconditions = production_readiness_plan.build_contract_report()["formal_migration_preconditions"]
    text = " ".join(preconditions)

    assert "smoke matrix" in text
    assert "rollback plan accepted" in preconditions
    assert "seed strategy accepted" in preconditions
    assert "read path dual-run accepted" in preconditions
    assert "manual review gates for relationship tables accepted" in preconditions


def test_cutover_phases_keep_jsonl_source_boundary() -> None:
    phases = production_readiness_plan.build_contract_report()["cutover_phases"]
    text = " ".join(phases)

    assert "JSONL remains write source" in text
    assert "no production write switch" in text
    assert "write source switch requires separate approval" in text


def test_rollback_backup_and_seed_strategies_are_complete() -> None:
    report = production_readiness_plan.build_contract_report()

    assert "rollback by restoring pre-migration DB snapshot" in report["rollback_strategy"]
    assert "rollback by reverting config flags" in report["rollback_strategy"]
    assert "rollback by reverting PR / commit" in report["rollback_strategy"]
    assert "rollback by dropping isolated/proposed schema" in report["rollback_strategy"]
    assert "pre-migration DB snapshot" in report["backup_strategy"]
    assert "seed generated from canonical JSONL only" in report["seed_strategy"]
    assert "seed artifacts are derived" in report["seed_strategy"]


def test_non_goals_and_strict_boundaries_exclude_production_changes() -> None:
    report = production_readiness_plan.build_contract_report()
    text = " ".join(report["non_goals"] + report["strict_boundaries"])

    assert "does not switch the JSONL write source" in report["non_goals"]
    assert "does not write formal schema" in report["non_goals"]
    assert "does not modify metric or adjudication logic" in report["non_goals"]
    assert "does_not_modify_canonical_jsonl" in text
    assert "does_not_run_backup_or_restore" in text


def test_report_contains_no_blocked_terms() -> None:
    text = production_readiness_plan.report_as_json(production_readiness_plan.build_contract_report()).lower()

    for term in production_readiness_plan.BLOCKED_REPORT_TERMS:
        assert term not in text


def test_source_is_contract_only() -> None:
    source = (ROOT / "scripts" / "platform" / "production_readiness_plan.py").read_text(encoding="utf-8")

    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "psycopg" not in source


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in production readiness CLI")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert production_readiness_plan.main(["--contract-report"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["status"] == "Proposed"


def _status_value(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "## Status":
            for candidate in lines[index + 1 :]:
                if candidate.strip():
                    return candidate.strip()
    raise AssertionError(f"missing status section: {path}")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
