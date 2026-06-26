from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import epic5_deterministic_rerun_report_contract as rerun_report  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_declares_rerun_report_package_after_publication_merge() -> None:
    report = rerun_report.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "epic5-deterministic-rerun-report-contract-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["score_publication_contract_pr"] == 318
    assert report["score_publication_contract_merge_commit"] == rerun_report.SCORE_PUBLICATION_CONTRACT_MERGE_COMMIT
    assert report["does_not_lookup_sources"] is True
    assert report["does_not_build_person_specific_evidence"] is True
    assert report["does_not_release_person_specific_formal_grade_results"] is True
    assert report["does_not_release_person_specific_score_publication_results"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["current_state"]["current_phase"] == "epic5_deterministic_rerun_report_contract_package_ready"
    assert report["current_state"]["positive_benefit_total"] == 1500
    assert report["current_state"]["epic5_deterministic_rerun_report_contract_ready"] is True
    assert report["current_state"]["deterministic_rerun_report_contract_count"] == 3
    assert report["current_state"]["validator_contracts_built"] is True
    assert report["current_state"]["impact_report_templates_built"] is True
    assert report["current_state"]["publication_report_templates_built"] is True
    assert report["current_state"]["person_specific_score_publication_results_built"] is False
    assert report["current_state"]["new_subitem_formal_scores_released"] is False
    assert report["current_state"]["new_subitem_formal_rankings_released"] is False
    assert report["current_state"]["stage_or_final_total_table_released"] is False
    assert report["current_state"]["cross_subitem_leaderboard_released"] is False


def test_rerun_report_templates_cover_three_pilot_subitems_without_runtime_inputs() -> None:
    report = rerun_report.build_contract_report()
    by_id = {contract["subitem_id"]: contract for contract in report["rerun_report_contracts"]}

    assert set(by_id) == {
        "second_governance_net_benefit",
        "third_military_border_net_benefit",
        "sixth_key_decision_capacity",
    }
    for contract in by_id.values():
        rerun = contract["deterministic_rerun_key_contract"]
        assert contract["person_id"] == rerun_report.TEMPLATE_PERSON_ID
        assert contract["template_not_for_scoring"] is True
        assert contract["template_not_for_publication"] is True
        assert rerun["runtime_state_inputs_allowed"] is False
        assert rerun["source_lookup_inputs_allowed"] is False
        assert rerun["publication_inputs_allowed"] is False
        assert rerun["stable_sort_keys"] == ["subitem_id", "person_id", "deterministic_rerun_key"]
        assert set(rerun_report.RERUN_REQUIRED_INPUTS) <= set(rerun["required_inputs"])
        source_contract = contract["source_publication_contract"]
        assert rerun["deterministic_rerun_key"] == source_contract["formal_grade_result_template"][
            "deterministic_rerun_key"
        ]


def test_validator_impact_and_publication_report_templates_keep_release_flags_false() -> None:
    report = rerun_report.build_contract_report()

    for contract in report["rerun_report_contracts"]:
        validator = contract["validator_contract"]
        impact = contract["impact_report_template"]
        publication = contract["publication_report_template"]
        assert set(rerun_report.VALIDATOR_REQUIRED_CHECKS) <= set(validator["required_checks"])
        assert validator["fails_if_stage_or_final_total_released"] is True
        assert validator["fails_if_cross_subitem_leaderboard_released"] is True
        assert validator["fails_if_person_specific_publication_claimed"] is True
        assert impact["candidate_value_is_placeholder"] is True
        assert impact["template_not_for_publication"] is True
        assert publication["formal_score_value_is_placeholder"] is True
        assert publication["subitem_rank_is_placeholder"] is True
        assert publication["stage_or_final_total_table_released"] is False
        assert publication["cross_subitem_leaderboard_released"] is False
        assert publication["template_not_for_publication"] is True


def test_contract_invariants_and_blocked_outputs_prevent_actual_publication_claims() -> None:
    report = rerun_report.build_contract_report()
    invariants = set(report["rerun_report_contract_invariants"])

    assert "deterministic_key_reuses_formal_grade_template_key" in invariants
    assert "rerun_inputs_exclude_runtime_state_and_source_lookup" in invariants
    assert "validator_contract_blocks_person_specific_publication_claims" in invariants
    assert "publication_report_template_contains_g9_requirement_without_publication_release" in invariants
    assert "person_specific_score_publication_result" in report["blocked_outputs"]
    assert "new_subitem_formal_scores" in report["blocked_outputs"]
    assert "new_subitem_formal_rankings" in report["blocked_outputs"]
    assert "cross_subitem_leaderboard" in report["blocked_outputs"]
    assert (
        report["next_required_work"]
        == "issue_311_rule_display_dictionary_externalization_or_non_destructive_governance"
    )


def test_report_text_does_not_claim_real_sources_people_or_publication_release() -> None:
    text = rerun_report.report_as_json(rerun_report.build_contract_report()).lower()

    assert '"positive_benefit_total": 1500' in text
    assert '"person_specific_evidence_profiles_built": false' in text
    assert '"person_specific_formal_grade_results_built": false' in text
    assert '"person_specific_score_publication_results_built": false' in text
    assert '"formal_grade_results_released_for_new_subitems": false' in text
    assert '"new_subitem_formal_scores_released": false' in text
    assert '"new_subitem_formal_rankings_released": false' in text
    assert '"stage_or_final_total_table_released": false' in text
    assert '"cross_subitem_leaderboard_released": false' in text
    assert "evd-" not in text
    assert "srch-" not in text
    assert '"person_specific_score_publication_results_built": true' not in text
    assert '"new_subitem_formal_scores_released": true' not in text
    assert '"cross_subitem_leaderboard_released": true' not in text


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
        raise AssertionError("network access is forbidden in Epic5 rerun report tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = rerun_report.build_contract_report()
    markdown = rerun_report.render_rerun_report_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "Epic5 Deterministic Rerun And Report Contract" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert rerun_report.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert rerun_report.main(["--rerun-report-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Epic5 Deterministic Rerun And Report Contract" in markdown
    assert "second_governance_net_benefit" in markdown
    assert "validator_contract=`present`" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "epic5_deterministic_rerun_report_contract.py").read_text(
        encoding="utf-8"
    )

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
