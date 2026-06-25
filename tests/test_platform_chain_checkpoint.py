from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import platform_chain_checkpoint


BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard", "评分", "排名", "裁判结论")
FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_checkpoint_report_has_complete_platform_chain() -> None:
    report = platform_chain_checkpoint.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["checkpoint_version"] == "platform-chain-checkpoint-v1"
    assert report["current_state"] == {
        "current_phase": "platform-schema-live-data-not-cutover",
        "canonical_write_source": "jsonl",
        "postgres_schema_live": True,
        "postgres_business_data_migrated": False,
        "sqlite_build_operational": False,
        "full_pytest_operational": False,
        "jsonl_write_frozen": False,
        "postgres_unique_write_source": False,
        "production_runtime_live": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
    }
    assert report["completed_chain"] == platform_chain_checkpoint.COMPLETED_CHAIN
    assert "production_schema_live_apply" in report["completed_chain"]
    assert "production_seed_manifest_import_audit_scaffold" in report["completed_chain"]
    assert "jsonl_query_search_target_mapper" in report["apply_capable_tools"]
    assert "jsonl_sources_target_mapper" in report["apply_capable_tools"]
    assert "jsonl_evidence_cards_target_mapper" in report["apply_capable_tools"]
    assert "jsonl_evidence_clusters_resolver" in report["apply_capable_tools"]
    assert "jsonl_anchors_target_mapper" in report["apply_capable_tools"]
    assert "anchors_resolver_contract" in report["contract_only_tools"]
    assert "epic_1_g1_canonical_manifest_approval" in report["next_epic_gates"]
    assert report["baseline_repair_tracking"]["sqlite_build_operational"] is False
    assert report["baseline_repair_tracking"]["required_follow_up"].startswith("Epic 0")


def test_checkpoint_report_is_offline_and_does_not_touch_forbidden_paths(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in platform checkpoint")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env" or "batches" in self.parts or ("archive" in self.parts and "data" in self.parts):
            raise AssertionError(f"checkpoint must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = platform_chain_checkpoint.build_contract_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert "does_not_read_dotenv" in report["limitations"]
    assert "does_not_read_batch_or_archive_inputs" in report["limitations"]


def test_checkpoint_report_contains_no_blocked_business_terms() -> None:
    text = platform_chain_checkpoint.report_as_json(platform_chain_checkpoint.build_contract_report()).lower()
    text = text.replace('"formal_ranking_released": false', "")

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_checkpoint_cli_prints_json(capsys) -> None:
    assert platform_chain_checkpoint.main(["--contract-report"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["known_ci_history"][0]["fix"] == "install_requirements_before_validate_all"


def test_checkpoint_source_is_contract_only() -> None:
    source = (ROOT / "scripts" / "platform" / "platform_chain_checkpoint.py").read_text(encoding="utf-8")

    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "psycopg" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
