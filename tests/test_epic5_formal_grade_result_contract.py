from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import epic5_formal_grade_result_contract as formal_grade  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_declares_formal_grade_package_after_evidence_merge() -> None:
    report = formal_grade.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "epic5-formal-grade-result-contract-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["evidence_profile_contract_pr"] == 316
    assert report["evidence_profile_contract_merge_commit"] == formal_grade.EVIDENCE_PROFILE_CONTRACT_MERGE_COMMIT
    assert report["does_not_lookup_sources"] is True
    assert report["does_not_build_person_specific_evidence"] is True
    assert report["does_not_release_person_specific_formal_grade_results"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["current_state"]["current_phase"] == "epic5_formal_grade_result_contract_package_ready"
    assert report["current_state"]["positive_benefit_total"] == 1500
    assert report["current_state"]["epic5_formal_grade_result_contract_ready"] is True
    assert report["current_state"]["formal_grade_result_contract_count"] == 3
    assert report["current_state"]["person_specific_evidence_profiles_built"] is False
    assert report["current_state"]["person_specific_formal_grade_results_built"] is False
    assert report["current_state"]["formal_grade_results_released_for_new_subitems"] is False
    assert report["current_state"]["score_publication_results_built"] is False
    assert report["current_state"]["new_subitem_formal_scores_released"] is False
    assert report["current_state"]["new_subitem_formal_rankings_released"] is False
    assert report["current_state"]["stage_or_final_total_table_released"] is False
    assert report["current_state"]["cross_subitem_leaderboard_released"] is False


def test_formal_grade_templates_cover_three_pilot_subitems_without_real_person_results() -> None:
    report = formal_grade.build_contract_report()
    by_id = {contract["subitem_id"]: contract for contract in report["formal_grade_result_contracts"]}

    assert set(by_id) == {
        "second_governance_net_benefit",
        "third_military_border_net_benefit",
        "sixth_key_decision_capacity",
    }
    for contract in by_id.values():
        template = contract["formal_grade_result_template"]
        assert contract["person_id"] == formal_grade.TEMPLATE_PERSON_ID
        assert contract["template_not_for_scoring"] is True
        assert contract["template_not_for_publication"] is True
        assert contract["person_specific_evidence_included"] is False
        assert contract["person_specific_formal_grade_result_included"] is False
        assert contract["score_publication_result_included"] is False
        assert contract["publication_result"] is None
        assert contract["source_lookup_performed"] is False
        assert template["person_id"] == formal_grade.TEMPLATE_PERSON_ID
        assert template["formal_grade"] == formal_grade.TEMPLATE_FORMAL_GRADE
        assert template["candidate_value"] == "0"
        assert template["candidate_value_is_placeholder"] is True
        assert template["template_not_for_publication"] is True
        assert template["score_range_policy"] == formal_grade.SCORE_RANGE_POLICY
        assert template["score_range"]["lower"] == "0"
        assert template["score_range"]["upper"] == contract["subitem_profile"]["score_cap"]
        assert template["algorithm_version"] == contract["subitem_profile"]["algorithm_version"]
        assert template["deterministic_rerun_key"].startswith(
            formal_grade.TEMPLATE_DETERMINISTIC_RERUN_KEY_PREFIX
        )
        assert contract["evidence_profile_template"]["subitem_id"] == contract["subitem_id"]
        assert template["subitem_id"] == contract["subitem_id"]


def test_formal_grade_templates_lock_grade_values_no_override_and_publication_boundary() -> None:
    report = formal_grade.build_contract_report()

    for contract in report["formal_grade_result_contracts"]:
        template = contract["formal_grade_result_template"]
        assert template["formal_grade_allowed_values"] == list(formal_grade.FORMAL_GRADE_ALLOWED_VALUES)
        assert template["no_override_policy"] == {
            "person_specific_override_allowed": False,
            "manual_final_grade_allowed": False,
            "manual_final_score_allowed": False,
        }
        assert contract["g8_release_performed"] is False
        assert contract["g9_publication_performed"] is False
        assert contract["subitem_profile"]["stage_or_final_total_release_allowed"] is False
        assert contract["subitem_profile"]["cross_subitem_leaderboard_release_allowed"] is False


def test_contract_invariants_and_blocked_outputs_prevent_score_publication_claims() -> None:
    report = formal_grade.build_contract_report()
    invariants = set(report["formal_grade_contract_invariants"])

    assert "formal_grade_subitem_id_matches_pilot_subitem_profile" in invariants
    assert "formal_grade_person_id_matches_template_evidence_person_id" in invariants
    assert "candidate_value_is_contract_placeholder_inside_score_range" in invariants
    assert "no_override_policy_locked_false" in invariants
    assert "score_publication_result_not_included" in invariants
    assert "person_specific_formal_grade_result" in report["blocked_outputs"]
    assert "score_publication_result" in report["blocked_outputs"]
    assert "new_subitem_formal_scores" in report["blocked_outputs"]
    assert "new_subitem_formal_rankings" in report["blocked_outputs"]
    assert "cross_subitem_leaderboard" in report["blocked_outputs"]
    assert report["next_required_work"] == "epic5_score_publication_result_contract_package"


def test_report_text_does_not_claim_real_sources_people_or_publication() -> None:
    text = formal_grade.report_as_json(formal_grade.build_contract_report()).lower()

    assert '"positive_benefit_total": 1500' in text
    assert '"person_specific_evidence_profiles_built": false' in text
    assert '"person_specific_formal_grade_results_built": false' in text
    assert '"formal_grade_results_released_for_new_subitems": false' in text
    assert '"score_publication_results_built": false' in text
    assert '"new_subitem_formal_scores_released": false' in text
    assert '"new_subitem_formal_rankings_released": false' in text
    assert '"stage_or_final_total_table_released": false' in text
    assert '"cross_subitem_leaderboard_released": false' in text
    assert "evd-" not in text
    assert "srch-" not in text
    assert '"person_specific_formal_grade_results_built": true' not in text
    assert '"new_subitem_formal_scores_released": true' not in text
    assert '"cross_subitem_leaderboard_released": true' not in text
    assert "formal_score_value" not in text
    assert "publication_gate" not in text


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
        raise AssertionError("network access is forbidden in Epic5 formal grade tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = formal_grade.build_contract_report()
    markdown = formal_grade.render_formal_grade_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "Epic5 Formal Grade Result Contract" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert formal_grade.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert formal_grade.main(["--formal-grade-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Epic5 Formal Grade Result Contract" in markdown
    assert "second_governance_net_benefit" in markdown
    assert "score_publication_result_included=`false`" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "epic5_formal_grade_result_contract.py").read_text(
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
