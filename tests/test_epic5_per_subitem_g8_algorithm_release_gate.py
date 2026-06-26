from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import epic5_per_subitem_g8_algorithm_release_gate as g8_gate  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_declares_per_subitem_g8_gate_package() -> None:
    report = g8_gate.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "epic5-per-subitem-g8-algorithm-release-gate-contract-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["dictionary_governance_pr"] == 329
    assert report["dictionary_governance_merge_commit"] == g8_gate.DICTIONARY_GOVERNANCE_MERGE_COMMIT
    assert report["does_not_lookup_sources"] is True
    assert report["does_not_build_person_specific_evidence"] is True
    assert report["does_not_release_person_specific_formal_grade_results"] is True
    assert report["does_not_release_person_specific_score_publication_results"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["current_state"]["current_phase"] == (
        "epic5_per_subitem_g8_algorithm_release_gate_contract_ready"
    )
    assert report["current_state"]["epic5_per_subitem_g8_algorithm_release_gate_contract_ready"] is True
    assert report["current_state"]["per_subitem_g8_gate_contract_count"] == 3
    assert report["current_state"]["per_subitem_g8_algorithm_release_performed"] is False


def test_g8_gate_templates_cover_three_pilot_subitems_without_releasing_algorithms() -> None:
    report = g8_gate.build_contract_report()
    by_id = {contract["subitem_id"]: contract for contract in report["g8_gate_contracts"]}

    assert set(by_id) == {
        "second_governance_net_benefit",
        "third_military_border_net_benefit",
        "sixth_key_decision_capacity",
    }
    for contract in by_id.values():
        assert contract["g8_gate_template_ready"] is True
        assert contract["g8_gate_status"] == "contract_template_only_not_approved"
        assert contract["g8_release_performed"] is False
        assert contract["g9_publication_performed"] is False
        assert contract["template_not_for_scoring"] is True
        assert contract["template_not_for_publication"] is True
        assert contract["person_specific_evidence_included"] is False
        assert contract["person_specific_formal_grade_result_included"] is False
        assert contract["person_specific_score_publication_result_included"] is False
        assert contract["source_lookup_performed"] is False
        assert contract["algorithm_version"] == contract["subitem_profile"]["algorithm_version"]
        assert contract["deterministic_rerun_key"]
        assert contract["impact_report_template"]["template_not_for_publication"] is True
        assert contract["publication_report_template"]["template_not_for_publication"] is True
        assert contract["publication_report_template"]["stage_or_final_total_table_released"] is False
        assert contract["publication_report_template"]["cross_subitem_leaderboard_released"] is False


def test_g8_gate_required_checks_and_boundaries_match_epic5_policy() -> None:
    report = g8_gate.build_contract_report()

    for contract in report["g8_gate_contracts"]:
        assert list(g8_gate.G8_RELEASE_REQUIRED_CHECKS) == contract["required_checks"]
        assert "impact_report_without_formal_person_values" in contract["allowed_outputs"]
        assert "new_subitem_formal_scores" in contract["blocked_outputs"]
        assert "new_subitem_formal_rankings" in contract["blocked_outputs"]
        assert "cross_subitem_leaderboard" in contract["blocked_outputs"]
        assert contract["no_override_policy"] == {
            "person_specific_override_allowed": False,
            "manual_final_grade_allowed": False,
            "manual_final_score_allowed": False,
        }
    assert "publication_report_template_blocks_g9_outputs" in report["g8_gate_contract_invariants"]
    assert report["next_required_work"] == "epic5_per_subitem_g8_algorithm_release_review_or_execution_gate"


def test_report_text_does_not_claim_real_sources_people_or_publication_release() -> None:
    text = g8_gate.report_as_json(g8_gate.build_contract_report()).lower()

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
    assert '"per_subitem_g8_algorithm_release_performed": true' not in text
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
        raise AssertionError("network access is forbidden in Epic5 G8 gate tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g8_gate.build_contract_report()
    markdown = g8_gate.render_g8_gate_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "Epic5 Per-Subitem G8 Algorithm Release Gate Contract" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g8_gate.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert g8_gate.main(["--g8-gate-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Epic5 Per-Subitem G8 Algorithm Release Gate Contract" in markdown
    assert "second_governance_net_benefit" in markdown
    assert "g8_release_performed=`false`" in markdown


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
