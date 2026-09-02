from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.evaluation.formal_json_store import load_json


ROOT = Path(".")
C_PATH = ROOT / "docs/评分结算/第一项创业与政权取得能力/军事夺取能力/01-第一项C军事夺取能力结算.json"
C_CONFIG_PATH = ROOT / "config/first-item/first-item-c-acquisition-windows.json"
COMPLETED_NAMES = {"刘崇", "孟知祥", "李克用", "杨行密", "钱镠", "马殷", "高季兴", "李德明"}


def _load(path: Path) -> dict:
    return load_json(path)


def test_first_item_c_completed_founders_have_current_results() -> None:
    payload = _load(C_PATH)
    completed = {
        row["ruler_name"]: row
        for row in payload["records"]
        if row["ruler_name"] in COMPLETED_NAMES
    }
    assert payload["record_count"] == 193
    assert payload["eligible_count"] == 84
    assert payload["pending_count"] == 0
    assert set(completed) == COMPLETED_NAMES
    assert {name: row["C_score_points"] for name, row in completed.items()} == {
        "刘崇": 13.5,
        "孟知祥": 44.5,
        "李克用": 69.0,
        "杨行密": 47.1,
        "钱镠": 50.4,
        "马殷": 0.0,
        "高季兴": 22.0,
        "李德明": 7.5,
    }
    for name, row in completed.items():
        assert row["score_ready"] is True
        assert row["scope_status"] == "APPLICABLE_DYNASTY_FOUNDER"
        if name == "马殷":
            assert row["coverage_status"] == "NO_PERSONAL_MILITARY_CONTRIBUTION"
            assert "秦彦晖、李琼、吕师周" in row["default_basis"]
        else:
            assert row["coverage_status"] == "CALIBRATED_C_WINDOW_RESULT"
            assert row["C1"]["campaign_results"]


def test_first_item_c_completed_founders_consume_each_parent_direction_once() -> None:
    payload = _load(C_PATH)
    for row in payload["records"]:
        if row["ruler_name"] not in COMPLETED_NAMES:
            continue
        keys = [
            (result["campaign_group_id"], result["result_direction"])
            for result in row["C1"]["campaign_results"]
        ]
        assert len(keys) == len(set(keys))
        assert all(result["source_refs"] for result in row["C1"]["campaign_results"])


def test_first_item_c_completion_includes_losses_and_explicit_zero_review() -> None:
    payload = _load(C_CONFIG_PATH)
    talent = {
        row["ruler_name"]: row
        for row in payload["talent_episode_supplements"]
        if row["ruler_name"] in COMPLETED_NAMES
    }
    public = [
        row for row in payload["public_person_result_supplements"]
        if row["ruler_name"] in COMPLETED_NAMES
    ]
    reviews = {
        row["ruler_name"]: row
        for row in payload["no_personal_military_contribution_reviews"]
    }
    assert set(talent) == {"李克用", "杨行密", "钱镠"}
    assert len(talent["李克用"]["adverse_campaign_refs"]) == 2
    assert {row["ruler_name"] for row in public} == {"刘崇", "孟知祥", "高季兴", "李德明"}
    assert sum(row["result_direction"] == "negative" for row in public) == 4
    assert reviews["马殷"]["source_refs"]
