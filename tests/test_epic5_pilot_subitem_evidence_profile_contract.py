from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import epic5_pilot_subitem_evidence_profile_contract as evidence  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_declares_evidence_profile_package_after_profile_merge() -> None:
    report = evidence.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "epic5-pilot-subitem-evidence-profile-contract-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["profile_contract_pr"] == 315
    assert report["profile_contract_merge_commit"] == evidence.PROFILE_CONTRACT_MERGE_COMMIT
    assert report["does_not_lookup_sources"] is True
    assert report["does_not_build_person_specific_evidence"] is True
    assert report["does_not_release_formal_grade_results"] is True
    assert report["does_not_publish_scores"] is True
    assert report["current_state"]["current_phase"] == "epic5_pilot_subitem_evidence_profile_contract_package_ready"
    assert report["current_state"]["positive_benefit_total"] == 1500
    assert report["current_state"]["epic5_pilot_subitem_evidence_profile_contract_ready"] is True
    assert report["current_state"]["person_specific_evidence_profiles_built"] is False
    assert report["current_state"]["formal_grade_results_released_for_new_subitems"] is False
    assert report["current_state"]["new_subitem_formal_scores_released"] is False
    assert report["current_state"]["new_subitem_formal_rankings_released"] is False
    assert report["current_state"]["stage_or_final_total_table_released"] is False
    assert report["current_state"]["cross_subitem_leaderboard_released"] is False


def test_evidence_contracts_cover_three_pilot_subitems_without_person_evidence() -> None:
    report = evidence.build_contract_report()
    by_id = {contract["subitem_id"]: contract for contract in report["evidence_profile_contracts"]}

    assert set(by_id) == {
        "second_governance_net_benefit",
        "third_military_border_net_benefit",
        "sixth_key_decision_capacity",
    }
    assert report["current_state"]["evidence_profile_contract_count"] == 3
    for contract in by_id.values():
        assert contract["person_id"] == evidence.TEMPLATE_PERSON_ID
        assert contract["confidence"] == evidence.TEMPLATE_CONFIDENCE
        assert contract["source_traceability_status"] == evidence.TEMPLATE_SOURCE_TRACEABILITY_STATUS
        assert contract["template_not_for_scoring"] is True
        assert contract["person_specific_evidence_included"] is False
        assert contract["source_lookup_performed"] is False
        assert contract["formal_grade_result_included"] is False
        assert contract["score_publication_result_included"] is False
        assert contract["subitem_profile"]["subitem_id"] == contract["subitem_id"]
        assert contract["positive_signal_profile"]["schema_only"] is True
        assert contract["negative_signal_profile"]["schema_only"] is True


def test_positive_negative_signal_groups_and_split_contracts_are_subitem_specific() -> None:
    report = evidence.build_contract_report()
    by_id = {contract["subitem_id"]: contract for contract in report["evidence_profile_contracts"]}

    second_positive = {
        group["group_id"] for group in by_id["second_governance_net_benefit"]["positive_signal_profile"]["positive_signal_groups"]
    }
    assert second_positive == {
        "institutional_benefit",
        "administrative_benefit",
        "livelihood_economic_benefit",
        "succession_sustainability_benefit",
    }
    assert "military_security_result_routes_to_third_item" in by_id["second_governance_net_benefit"][
        "cross_item_split_signals"
    ]

    third_positive = {
        group["group_id"]
        for group in by_id["third_military_border_net_benefit"]["positive_signal_profile"]["positive_signal_groups"]
    }
    assert third_positive == {
        "strategic_security_benefit",
        "frontier_control_benefit",
        "military_system_effectiveness",
        "military_cost_benefit",
    }
    assert "livelihood_result_routes_to_second_item_c" in by_id["third_military_border_net_benefit"][
        "cross_item_split_signals"
    ]

    sixth_positive = {
        group["group_id"] for group in by_id["sixth_key_decision_capacity"]["positive_signal_profile"]["positive_signal_groups"]
    }
    assert sixth_positive == {
        "major_node_judgment",
        "risk_control_and_stop_loss",
        "long_term_strategic_vision",
    }
    assert "specific_military_outcome_routes_to_third_item" in by_id["sixth_key_decision_capacity"][
        "cross_item_split_signals"
    ]


def test_contract_invariants_and_blocked_outputs_prevent_score_publication_claims() -> None:
    report = evidence.build_contract_report()
    invariants = set(report["evidence_contract_invariants"])

    assert "evidence_profile_subitem_id_matches_pilot_subitem_profile" in invariants
    assert "template_person_id_is_not_a_real_person" in invariants
    assert "no_formal_grade_or_score_publication_result_included" in invariants
    assert "formal_grade_result" in report["blocked_outputs"]
    assert "score_publication_result" in report["blocked_outputs"]
    assert "new_subitem_formal_scores" in report["blocked_outputs"]
    assert "cross_subitem_leaderboard" in report["blocked_outputs"]
    assert report["next_required_work"] == "epic5_formal_grade_result_contract_package"


def test_report_text_does_not_claim_real_sources_people_or_publication() -> None:
    text = evidence.report_as_json(evidence.build_contract_report()).lower()

    assert '"positive_benefit_total": 1500' in text
    assert '"person_specific_evidence_profiles_built": false' in text
    assert '"formal_grade_results_released_for_new_subitems": false' in text
    assert '"new_subitem_formal_scores_released": false' in text
    assert '"new_subitem_formal_rankings_released": false' in text
    assert '"stage_or_final_total_table_released": false' in text
    assert '"cross_subitem_leaderboard_released": false' in text
    assert "evd-" not in text
    assert "srch-" not in text
    assert '"person_specific_evidence_profiles_built": true' not in text
    assert '"formal_grade_results_released_for_new_subitems": true' not in text
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
        raise AssertionError("network access is forbidden in Epic5 evidence profile tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = evidence.build_contract_report()
    markdown = evidence.render_evidence_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "Epic5 Pilot Subitem Evidence Profile Contract" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert evidence.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert evidence.main(["--evidence-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Epic5 Pilot Subitem Evidence Profile Contract" in markdown
    assert "second_governance_net_benefit" in markdown
    assert "template_not_for_scoring=`true`" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "epic5_pilot_subitem_evidence_profile_contract.py").read_text(
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
