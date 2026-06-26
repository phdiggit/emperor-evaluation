from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import epic5_score_publication_result_contract as publication  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_declares_publication_package_after_formal_grade_merge() -> None:
    report = publication.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "epic5-score-publication-result-contract-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["formal_grade_contract_pr"] == 317
    assert report["formal_grade_contract_merge_commit"] == publication.FORMAL_GRADE_CONTRACT_MERGE_COMMIT
    assert report["does_not_lookup_sources"] is True
    assert report["does_not_build_person_specific_evidence"] is True
    assert report["does_not_release_person_specific_formal_grade_results"] is True
    assert report["does_not_release_person_specific_score_publication_results"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["current_state"]["current_phase"] == "epic5_score_publication_result_contract_package_ready"
    assert report["current_state"]["positive_benefit_total"] == 1500
    assert report["current_state"]["epic5_score_publication_result_contract_ready"] is True
    assert report["current_state"]["score_publication_result_contract_count"] == 3
    assert report["current_state"]["score_publication_result_templates_built"] is True
    assert report["current_state"]["person_specific_evidence_profiles_built"] is False
    assert report["current_state"]["person_specific_formal_grade_results_built"] is False
    assert report["current_state"]["person_specific_score_publication_results_built"] is False
    assert report["current_state"]["formal_grade_results_released_for_new_subitems"] is False
    assert report["current_state"]["new_subitem_formal_scores_released"] is False
    assert report["current_state"]["new_subitem_formal_rankings_released"] is False
    assert report["current_state"]["stage_or_final_total_table_released"] is False
    assert report["current_state"]["cross_subitem_leaderboard_released"] is False


def test_publication_templates_cover_three_pilot_subitems_without_real_person_publication() -> None:
    report = publication.build_contract_report()
    by_id = {contract["subitem_id"]: contract for contract in report["score_publication_result_contracts"]}

    assert set(by_id) == {
        "second_governance_net_benefit",
        "third_military_border_net_benefit",
        "sixth_key_decision_capacity",
    }
    for contract in by_id.values():
        template = contract["score_publication_result_template"]
        formal_grade = contract["formal_grade_result_template"]
        assert contract["person_id"] == publication.TEMPLATE_PERSON_ID
        assert contract["template_not_for_scoring"] is True
        assert contract["template_not_for_publication"] is True
        assert contract["person_specific_evidence_included"] is False
        assert contract["person_specific_formal_grade_result_included"] is False
        assert contract["person_specific_score_publication_result_included"] is False
        assert contract["source_lookup_performed"] is False
        assert contract["g8_release_performed"] is False
        assert contract["g9_publication_performed"] is False
        assert template["person_id"] == publication.TEMPLATE_PERSON_ID
        assert template["subitem_id"] == contract["subitem_id"]
        assert template["formal_score_value"] == formal_grade["candidate_value"]
        assert template["formal_score_value_is_placeholder"] is True
        assert template["subitem_rank"] == publication.TEMPLATE_SUBITEM_RANK
        assert template["subitem_rank_is_placeholder"] is True
        assert template["publication_gate"] == publication.TEMPLATE_PUBLICATION_GATE
        assert template["publication_scope"] == publication.TEMPLATE_PUBLICATION_SCOPE
        assert template["publication_boundary_policy"] == publication.PUBLICATION_BOUNDARY_POLICY
        assert template["stage_or_final_total_table_released"] is False
        assert template["cross_subitem_leaderboard_released"] is False


def test_publication_templates_keep_subitem_g9_separate_from_total_and_leaderboard_outputs() -> None:
    report = publication.build_contract_report()

    for contract in report["score_publication_result_contracts"]:
        template = contract["score_publication_result_template"]
        assert template["publication_gate"] == "G9"
        assert contract["stage_or_final_total_table_released"] is False
        assert contract["cross_subitem_leaderboard_released"] is False
        assert contract["subitem_profile"]["stage_or_final_total_release_allowed"] is False
        assert contract["subitem_profile"]["cross_subitem_leaderboard_release_allowed"] is False


def test_contract_invariants_and_blocked_outputs_prevent_actual_publication_claims() -> None:
    report = publication.build_contract_report()
    invariants = set(report["score_publication_contract_invariants"])

    assert "publication_person_id_matches_formal_grade_template" in invariants
    assert "publication_gate_is_g9_contract_requirement" in invariants
    assert "formal_score_value_equals_deterministic_candidate_placeholder" in invariants
    assert "person_specific_publication_result_not_included" in invariants
    assert "person_specific_score_publication_result" in report["blocked_outputs"]
    assert "new_subitem_formal_scores" in report["blocked_outputs"]
    assert "new_subitem_formal_rankings" in report["blocked_outputs"]
    assert "cross_subitem_leaderboard" in report["blocked_outputs"]
    assert report["next_required_work"] == "epic5_deterministic_rerun_and_report_contract_package"


def test_report_text_does_not_claim_real_sources_people_or_publication_release() -> None:
    text = publication.report_as_json(publication.build_contract_report()).lower()

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
        raise AssertionError("network access is forbidden in Epic5 score publication tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = publication.build_contract_report()
    markdown = publication.render_publication_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "Epic5 Score Publication Result Contract" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert publication.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert publication.main(["--publication-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Epic5 Score Publication Result Contract" in markdown
    assert "second_governance_net_benefit" in markdown
    assert "formal_score_value_is_placeholder=`true`" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "epic5_score_publication_result_contract.py").read_text(
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
