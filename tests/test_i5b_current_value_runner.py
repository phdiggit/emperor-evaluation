from __future__ import annotations

import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.i5b_current_value_runner import build_i5b_current_value
from emperor_v4.eval import main as eval_main


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("ruler", ["李世民", "刘邦"])
def test_current_value_chain_is_complete_and_shadow_only(ruler: str) -> None:
    report = build_i5b_current_value(ROOT / "eval/i5b_current_value" / ruler / "source-pack.json")

    assert report["status"] == "current_shadow_chain_complete"
    assert report["declarations"]["three_channel_materials_consumed"] is True
    assert set(report["three_channel_input"]["channel_counts"]) == {
        "ruler_chronicle",
        "person_biography",
        "dynasty_governance",
    }
    assert report["declarations"]["episode_count"] > 0
    assert report["declarations"]["episode_count"] < report["declarations"]["rule_evidence_unit_count"]
    assert set(report["three_channel_disposition"]) == set(report["three_channel_input"]["channel_counts"])
    assert any(row["rule_code"] == "team_building" for row in report["rule_evidence_units"])
    assert report["declarations"]["database_write_count"] == 0
    assert report["declarations"]["formal_score_write_count"] == 0
    assert report["declarations"]["score_45"] is None
    assert report["declarations"]["ranking"] is None
    assert report["net_signal"] == report["material_budget"]["summary"]["weighted_raw_signal"]
    assert all(
        episode["episode_type"] == "ruler_person_governance_event"
        for episode in report["episodes"]
    )
    episode_member_refs = [
        member["member_ref"]
        for reu in report["rule_evidence_units"]
        for member in reu["members"]
        if member["member_type"] == "episode"
    ]
    assert len(episode_member_refs) > len(set(episode_member_refs))
    assert all(not any(key in episode for key in ("semantic_version", "evidence_version", "previous_status")) for episode in report["episodes"])


def test_source_pack_hash_fails_closed(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["materials"][0]["fact_summary"] += "篡改"
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        build_i5b_current_value(target)


def test_current_value_cli_writes_only_current_result(tmp_path: Path) -> None:
    assert eval_main([
        "i5b-current-value",
        "--ruler",
        "刘邦",
        "--workspace-root",
        str(ROOT),
        "--output-dir",
        str(tmp_path),
    ]) == 0
    assert (tmp_path / "result.json").is_file()
    assert (tmp_path / "result.md").is_file()
