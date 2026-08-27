from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(".")
B_PATH = ROOT / "docs/评分结算/第一项创业与政权取得能力/政治整合能力/01-第一项B政治整合能力结算.json"
B_CONFIG_PATH = ROOT / "config/first-item/first-item-b-team-contribution-adjudications.json"
FORMAL_PATH = ROOT / "docs/评分结算/第一项创业与政权取得能力/01-第一项创业与政权取得能力正式结算.json"
TRIAL_NAMES = {"刘崇", "孟知祥", "李克用", "杨行密", "钱镠", "马殷", "高季兴", "李德明"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_first_item_b_completed_founder_coverage_and_scores() -> None:
    payload = _load(B_PATH)
    completed = {
        row["ruler_name"]: row
        for row in payload["records"]
        if row["ruler_name"] in TRIAL_NAMES
    }
    assert payload["schema_version"] == "first-item-b-registry-v4"
    assert payload["canonical_status"] == "CURRENT"
    assert payload["record_count"] == 193
    assert payload["eligible_count"] == 84
    assert payload["trial_count"] == payload["unresolved_count"] == 0
    assert payload["unanchored_scoring_outcome_count"] == 0
    assert payload["formal_score_write"] is False
    assert set(completed) == TRIAL_NAMES
    assert {
        name: row["B_score_points"] for name, row in completed.items()
    } == {
        "刘崇": 27.7,
        "孟知祥": 44.5,
        "李克用": 41.4,
        "杨行密": 44.9,
        "钱镠": 44.5,
        "马殷": 45.5,
        "高季兴": 27.0,
        "李德明": 27.9,
    }
    for row in completed.values():
        assert row["adjudication_status"] == "CURRENT_ACCEPTED"
        assert row["evidence_lower_bound"] is False
        assert 1 <= len(row["B1"]["scoring_outcomes"]) <= 2
        assert all(outcome["source_refs"] for outcome in row["B1"]["scoring_outcomes"])
        assert all(row["ruler_name"] not in outcome["actors"] for outcome in row["B1"]["outcome_evidence"])


def test_first_item_b_completed_records_preserve_attribution_and_dedup_boundaries() -> None:
    payload = _load(B_CONFIG_PATH)
    trial = {
        row["ruler_name"]: row for row in payload["records"]
        if row.get("ruler_name") in TRIAL_NAMES
    }
    scoring_refs: list[str] = []
    for row in trial.values():
        assert len(row["scoring_outcome_refs"]) == len(set(row["scoring_outcome_refs"]))
        evidence = {item["outcome_ref"]: item for item in row["outcome_evidence"]}
        assert set(row["scoring_outcome_refs"]) <= set(evidence)
        scoring_refs.extend(row["scoring_outcome_refs"])
    assert len(scoring_refs) == len(set(scoring_refs))
    assert trial["杨行密"]["outcome_evidence"][0]["non_founder_responsibility"] == "JOINT"
    assert trial["高季兴"]["scoring_outcome_refs"] == ["BOUT-TRIAL-GAO-RESTORE"]
    assert trial["高季兴"]["outcome_evidence"][0]["actors"] == ["倪可福"]
    assert trial["刘崇"]["outcome_evidence"][1]["actors"] == ["北汉太原守军"]
    assert trial["李克用"]["outcome_evidence"][0]["actors"] == ["李克修"]
    li_keyong_sources = trial["李克用"]["outcome_evidence"][1]["source_refs"]
    assert all(source.startswith("資治通鑑/卷266#") for source in li_keyong_sources)


def test_first_item_b_completed_records_enter_formal_settlement() -> None:
    formal = _load(FORMAL_PATH)
    formal_names = {row["ruler_name"] for row in formal["records"]}
    assert formal["record_count"] == 193
    assert formal["eligible_count"] == 84
    assert TRIAL_NAMES <= formal_names
