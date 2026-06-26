from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g7_rule_change_scope_package as g7  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_records_g7_approval_without_rule_changes() -> None:
    report = g7.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "g7-rule-change-scope-package-v1"
    assert report["gate"] == "G7_SCORING_RULE_CHANGE"
    assert report["gate_status"] == "approved_scope_package_ready"
    assert report["does_not_modify_rule_sources"] is True
    assert report["g1_to_g6_completion"]["g6_observation_pr"] == 305
    assert report["g1_to_g6_completion"]["g6_observation_merge_commit"] == g7.G6_OBSERVATION_MERGE_COMMIT
    assert report["current_state"] == {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_credentials_enabled": True,
        "rabbitmq_live": True,
        "network_ingestion_live": True,
        "production_runtime_live": True,
        "formal_evidence_released": True,
        "g7_approved": True,
        "g7_rule_change_scope_package_ready": True,
        "formal_algorithm_released": False,
        "formal_score_values_released": False,
        "formal_ranking_released": False,
        "epic_2_entered": False,
    }
    assert report["next_required_user_gate"] == "G8"


def test_g7_boundaries_allow_rule_scope_but_block_later_outputs() -> None:
    report = g7.build_contract_report()
    allowed = set(report["g7_allows"])
    denied = set(report["g7_does_not_allow"])

    assert "prepare_explicit_rule_change_workset" in allowed
    assert "review_subitem_rule_definition_diffs" in allowed
    assert "document_rule_change_impact_without_score_values" in allowed
    assert "formal_algorithm_release" in denied
    assert "formal_score_values_release" in denied
    assert "formal_ranking_or_leaderboard_release" in denied
    assert "source_document_passage_merge_policy_write" in denied
    assert "evidence_cluster_anchor_relationship_business_table_write_without_followup_gate" in denied
    assert "epic_2_scope_entry_without_separate_ready_review" in denied


def test_g7_required_artifacts_and_followup_gates_are_explicit() -> None:
    report = g7.build_contract_report()
    required = set(report["g7_required_artifacts_for_rule_change_pr"])
    boundaries = report["followup_gate_boundaries"]

    assert "changed_rule_paths" in required
    assert "before_after_rule_diff_summary" in required
    assert "impact_scope_statement" in required
    assert "regression_tests_for_rule_boundaries" in required
    assert "confirmation_that_algorithm_and_score_publication_remain_blocked" in required
    assert boundaries["formal_algorithm"]["status"] == "blocked_until_g8"
    assert boundaries["formal_score_values_or_ranking_publication"]["status"] == "blocked_until_g9"
    assert boundaries["destructive_cleanup"]["status"] == "blocked_until_g10"


def test_default_reports_do_not_read_secret_data_or_runtime_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if (
            self.name == ".env"
            or "batches" in parts
            or ("archive" in parts and "data" in parts)
            or self.name in {"evidence_cards.jsonl", "evidence_clusters.jsonl"}
        ):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G7 scope tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g7.build_contract_report()
    markdown = g7.render_scope_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "G7 Rule Change Scope Package" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g7.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert g7.main(["--scope-md"]) == 0
    markdown = capsys.readouterr().out
    assert "G7 Rule Change Scope Package" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "g7_rule_change_scope_package.py").read_text(encoding="utf-8")

    assert "import psycopg" not in source
    assert "import pika" not in source
    assert "aio_pika" not in source
    assert "import requests" not in source
    assert "subprocess.run" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "PG_SEARCH_BENCH_DSN" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
