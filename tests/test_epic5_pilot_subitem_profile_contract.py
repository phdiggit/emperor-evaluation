from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import epic5_pilot_subitem_profile_contract as profiles  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_declares_pilot_profile_package_after_interface_merge() -> None:
    report = profiles.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "epic5-pilot-subitem-profile-contract-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["interface_pr"] == 314
    assert report["interface_merge_commit"] == profiles.INTERFACE_MERGE_COMMIT
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["does_not_release_formal_grade_results"] is True
    assert report["current_state"]["current_phase"] == "epic5_pilot_subitem_profile_contract_package_ready"
    assert report["current_state"]["positive_benefit_total"] == 1500
    assert report["current_state"]["epic5_pilot_subitem_profile_contract_ready"] is True
    assert report["current_state"]["new_subitem_formal_scores_released"] is False
    assert report["current_state"]["new_subitem_formal_rankings_released"] is False
    assert report["current_state"]["stage_or_final_total_table_released"] is False
    assert report["current_state"]["cross_subitem_leaderboard_released"] is False


def test_pilot_profiles_lock_active_scoring_standard_caps_and_components() -> None:
    report = profiles.build_contract_report()
    by_id = {profile["subitem_id"]: profile for profile in report["pilot_subitem_profiles"]}

    assert set(by_id) == {
        "second_governance_net_benefit",
        "third_military_border_net_benefit",
        "sixth_key_decision_capacity",
    }
    assert by_id["second_governance_net_benefit"]["subitem_name"] == "第二项治国净收益"
    assert by_id["second_governance_net_benefit"]["score_cap"] == "460"
    assert by_id["second_governance_net_benefit"]["component_cap_sum"] == "460"
    assert [component["score_cap"] for component in by_id["second_governance_net_benefit"]["component_cap_profile"]] == [
        140,
        160,
        110,
        50,
    ]
    assert by_id["third_military_border_net_benefit"]["subitem_name"] == "第三项军事与边疆净收益"
    assert by_id["third_military_border_net_benefit"]["score_cap"] == "250"
    assert by_id["third_military_border_net_benefit"]["component_cap_sum"] == "250"
    assert [component["score_cap"] for component in by_id["third_military_border_net_benefit"]["component_cap_profile"]] == [
        80,
        80,
        50,
        40,
    ]
    assert by_id["sixth_key_decision_capacity"]["subitem_name"] == "第六项关键历史决策能力"
    assert by_id["sixth_key_decision_capacity"]["score_cap"] == "180"
    assert by_id["sixth_key_decision_capacity"]["component_cap_sum"] == "180"
    assert [component["score_cap"] for component in by_id["sixth_key_decision_capacity"]["component_cap_profile"]] == [
        60,
        50,
        70,
    ]


def test_profiles_use_subitem_contract_and_block_publication_outputs() -> None:
    report = profiles.build_contract_report()
    invariants = set(report["profile_contract_invariants"])

    assert "score_cap_matches_active_1500_scoring_standard" in invariants
    assert "component_caps_sum_to_subitem_score_cap" in invariants
    assert "no_evidence_profile_formal_grade_or_publication_result_included" in invariants
    assert "new_subitem_formal_scores" in report["blocked_outputs"]
    assert "new_subitem_formal_rankings" in report["blocked_outputs"]
    assert "cross_subitem_leaderboard" in report["blocked_outputs"]
    assert report["next_required_work"] == "epic5_pilot_subitem_evidence_profile_contract_package"

    for profile in report["pilot_subitem_profiles"]:
        assert profile["grade_scale_version"] == profiles.GRADE_SCALE_VERSION
        assert profile["algorithm_version"] == profiles.ALGORITHM_VERSION
        assert profile["g8_gate_status"] == "not_requested_profile_contract_only"
        assert profile["g9_publication_status"] == "blocked_profile_contract_only"
        assert profile["stage_or_final_total_release_allowed"] is False
        assert profile["cross_subitem_leaderboard_release_allowed"] is False
        assert profile["publication_allowed_in_this_package"] is False
        assert profile["evidence_profile_contract_included"] is False
        assert profile["formal_grade_result_included"] is False
        assert profile["score_publication_result_included"] is False


def test_report_text_does_not_claim_followup_publication() -> None:
    text = profiles.report_as_json(profiles.build_contract_report()).lower()

    assert '"positive_benefit_total": 1500' in text
    assert '"new_subitem_formal_scores_released": false' in text
    assert '"new_subitem_formal_rankings_released": false' in text
    assert '"stage_or_final_total_table_released": false' in text
    assert '"cross_subitem_leaderboard_released": false' in text
    assert '"does_not_build_evidence_profiles": true' in text
    assert '"does_not_release_formal_grade_results": true' in text
    assert '"new_subitem_formal_scores_released": true' not in text
    assert '"new_subitem_formal_rankings_released": true' not in text
    assert '"stage_or_final_total_table_released": true' not in text
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
        raise AssertionError("network access is forbidden in Epic5 pilot profile tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = profiles.build_contract_report()
    markdown = profiles.render_profiles_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "Epic5 Pilot Subitem Profile Contract" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert profiles.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert profiles.main(["--profiles-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Epic5 Pilot Subitem Profile Contract" in markdown
    assert "second_governance_net_benefit" in markdown
    assert "publication_allowed_in_this_package=`false`" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "epic5_pilot_subitem_profile_contract.py").read_text(
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
