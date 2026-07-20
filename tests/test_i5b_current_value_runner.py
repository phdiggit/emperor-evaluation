from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.i5b_current_value_runner import build_i5b_current_value
from emperor_v4.eval import main as eval_main


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("ruler", ["李世民", "刘邦"])
def test_current_value_chain_is_complete_and_shadow_only(ruler: str) -> None:
    report = build_i5b_current_value(ROOT / "eval/i5b_current_value" / ruler / "source-pack.json")

    assert report["status"] == "current_shadow_chain_complete_profile_values_provisional"
    assert report["declarations"]["three_channel_materials_consumed"] is True
    assert report["declarations"]["linked_ruler_context_count"] > 0
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
    assert report["declarations"]["profile_material_coverage_complete"] is False
    assert report["declarations"]["profile_values_frozen"] is False
    assert report["declarations"]["profile_freeze_gate_passed"] is False
    assert report["declarations"]["formal_scoring_ready"] is False
    assert report["declarations"]["profile_member_with_open_gap_count"] == report[
        "declarations"
    ]["profile_member_count"]
    assert report["net_signal_status"] == "provisional_profile_inputs"
    assert all(
        row["value_status"] == "provisional_material_coverage_open"
        for row in report["profile_projection_review"]
    )
    assert report["declarations"]["score_45"] is None
    assert report["declarations"]["ranking"] is None
    assert report["net_signal"] == report["material_budget"]["summary"]["weighted_raw_signal"]
    assert all(
        episode["episode_type"] == "ruler_person_governance_event"
        for episode in report["episodes"]
    )
    linked_episodes = [
        episode for episode in report["episodes"]
        if episode["lineage"]["ruler_context_refs"]
    ]
    assert linked_episodes
    assert all(
        any(link["relation"] == "corroborates" for link in episode["assertion_links"])
        for episode in linked_episodes
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


def test_duplicate_settlement_event_fails_closed(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["materials"][1]["settlement_event_key"] = payload["materials"][0][
        "independence_key"
    ]
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="重复结算事件"):
        build_i5b_current_value(target)


def test_profile_values_cannot_freeze_before_material_coverage(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["profile_projection_gate"]["freeze_allowed"] = True
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="材料覆盖未闭合"):
        build_i5b_current_value(target)


def test_governance_support_is_selected_by_current_result_quality() -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    team_reu = next(
        row for row in report["rule_evidence_units"] if row["rule_code"] == "team_building"
    )
    selected = {
        row["governance_achievement_ref"]
        for row in team_reu["payload"]["governance_dispositions"]
        if row["disposition"] == "selected_team_result_support"
    }
    assert "GOVACH-74B3A10FA62F4D512DA2" in selected
    assert "GOVACH-05D296EF7EE008316103" not in selected


def test_representative_military_materials_keep_three_channel_lineage() -> None:
    li = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    li_contexts = set(li["linked_ruler_context_refs"])
    assert "NMAT-900F470DB8A079C3F11F" in li_contexts
    assert "NMAT-2830CE53C58D4AF38E77" in li_contexts

    liu = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    appointment = next(
        row for row in liu["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    appointment_ids = {
        row["material_id"]
        for key in ("settled_materials", "supporting_only_materials")
        for row in appointment[key]
    }
    assert "MAT-刘邦-AD-LB-ZHOUBO-WARTIME-COMMAND" in appointment_ids
    zhou_bo = next(
        row for row in liu["profile_projection_review"] if row["person"] == "周勃"
    )
    assert set(zhou_bo["profile_evidence_refs"]["political_risk"]) == {
        "PFACT-B16F3241641256A60A24",
        "PFACT-41CE7721509571B8E874",
    }


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
