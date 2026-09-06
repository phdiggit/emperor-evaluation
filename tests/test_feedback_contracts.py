from copy import deepcopy
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.cost_sensitivity import analyze, run
from emperor_v4.evaluation.second_item_b1_settlement import (
    METHOD_PATH, TOTAL_PATH, FINANCE_PATHS,
    render_method_markdown, render_total_markdown, render_result_markdown,
    render_handoff_markdown, verify_derived_views,
)
from emperor_v4.evaluation.third_item_d_settlement import validate_quantity_inference_review


def _quantity():
    return {
        "quantity_role": "TOTAL_EXPEDITION_FORCE", "affected_group": "synthetic vanguard",
        "loss_type": "DEATH_WITH_UNRESOLVED_GROUP_SCOPE", "basis": "The rear guard left; its share is unknown.",
        "source_refs": ["synthetic-source"], "denominator_status": "UNRESOLVED",
        "reliable_death_lower_bound": None, "threshold_path_admitted": False,
    }


def test_unknown_casualties_remain_unknown_and_cannot_pass_personnel_gate():
    review = _quantity()
    validate_quantity_inference_review(review)
    assert review["reliable_death_lower_bound"] is None
    with pytest.raises(ValueError, match="分母未闭合"):
        validate_quantity_inference_review({**review, "reliable_death_lower_bound": 100000})
    with pytest.raises(ValueError, match="十万可靠下界"):
        validate_quantity_inference_review({**review, "threshold_path_admitted": True})
    with pytest.raises(ValueError, match="任意死亡比例"):
        validate_quantity_inference_review({**review, "assumed_death_fraction": 0.9})
    validate_quantity_inference_review({**review, "denominator_status": "CONFIRMED", "reliable_death_lower_bound": 100000, "threshold_path_admitted": True})


def _views(root):
    row = {"ruler_id": "synthetic-a", "ruler_name": "合成甲", "polity": "合成政权", "rank": 1,
           "score": 0.0, "second_item_score": 0.0, "governance_method_score": 0.0,
           "governance_result_score": 0.0, "handoff_score": 0.0,
           "A_direction_index": 0.0, "B1_direction_index": 0.0, "B2_direction_index": 0.0,
           "AB_block_120": 0.0, "B2_45": 0.0, "D1_level": 0, "D3_level": 0, "low_side_cap": 4.0}
    for axis in FINANCE_PATHS:
        row[f"{axis}_score"] = 0.0
        row[f"{axis}_band"] = axis
    for path, key, render in [
        (METHOD_PATH, "records", render_method_markdown),
        (TOTAL_PATH, "records", render_total_markdown),
        (FINANCE_PATHS["C1"].with_name("05-治理结果正式结算.json"), "scores", render_result_markdown),
        (TOTAL_PATH.parent / "政权交接稳定/03-交接质量20分正式结算.json", "records", render_handoff_markdown),
    ]:
        path = root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: [dict(row)]}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        path.with_suffix(".md").write_text(render(payload), encoding="utf-8")


@pytest.mark.parametrize("target", [METHOD_PATH, TOTAL_PATH, FINANCE_PATHS["C1"].with_name("05-治理结果正式结算.json"), TOTAL_PATH.parent / "政权交接稳定/03-交接质量20分正式结算.json"])
def test_summary_verifier_catches_stale_reading_value_without_writing(tmp_path, target):
    _views(tmp_path)
    verify_derived_views(tmp_path)
    path = (tmp_path / target).with_suffix(".md")
    path.write_text(path.read_text(encoding="utf-8").replace("**0.0**", "**1.0**"), encoding="utf-8")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="Markdown与正式JSON不一致"):
        verify_derived_views(tmp_path)
    assert before == {p: p.read_bytes() for p in before}


def test_matching_reading_page_cannot_hide_wrong_competition_rank(tmp_path):
    _views(tmp_path)
    path = tmp_path / METHOD_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["rank"] = 2
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.with_suffix(".md").write_text(render_method_markdown(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="竞争排名错误"):
        verify_derived_views(tmp_path)


def _analysis_inputs():
    records = [
        {"ruler_id": "a", "ruler_name": "合成甲", "rank": 1, "total_score": 85.0, "third_item_score": 80.0, "second_item_score": 5.0, "fourth_item_adjustment": 0.0, "first_item_raw_score": None},
        {"ruler_id": "b", "ruler_name": "合成乙", "rank": 2, "total_score": 70.0},
    ]
    third = {"a": {"global_cost_credit_profile": {"cost_band": "C5", "position": "HIGH"}, "military_net_loss_penalty": 0, "A120_score_points": 60.0, "B80_score_points": 30.0, "C50_score_points": 10.0}}
    factors = {"C5": {"HIGH": 0.75, "MID": 0.8}, "C6": {"HIGH": 0.5}}
    case = {"case_id": "synthetic", "ruler_id": "a", "baseline_cost_band": "C5", "baseline_cost_position": "HIGH", "source_refs": ["synthetic"], "scenarios": [
        {"scenario_id": "supported", "status": "SUPPORTED_INTERPRETATION", "cost_band": "C5", "cost_position": "MID", "basis": "synthetic uncertainty"},
        {"scenario_id": "rejected", "status": "REJECTED_DIAGNOSTIC", "cost_band": "C6", "cost_position": "HIGH", "basis": "synthetic excluded inference"},
    ]}
    return records, third, factors, [case]


def test_rejected_diagnostic_is_excluded_from_range_and_analysis_is_pure():
    args = _analysis_inputs()
    original = deepcopy(args)
    result = analyze(*args)
    case = result["cases"][0]
    assert case["supported_total_range"] == [85.0, 89.0]
    assert case["supported_rank_range"] == [1, 1]
    assert case["scenarios"][1]["total_score"] == 65.0
    assert {r["ruler_id"]: r["scenario_rank"] for r in case["scenarios"][1]["rank_changes"]} == {"a": 2, "b": 1}
    assert args == original
    assert analyze(*args) == result


def test_sensitivity_uses_ml_floor_and_competition_ties():
    records, third, factors, cases = _analysis_inputs()
    third["a"]["military_net_loss_penalty"] = -35.0
    records[0].update(total_score=70.0, third_item_score=65.0)
    records[1]["rank"] = 1
    case = analyze(records, third, factors, cases)["cases"][0]
    assert case["scenarios"][0]["applied_debit"] == 35.0
    assert case["scenarios"][0]["total_score"] == 70.0
    assert case["scenarios"][0]["rank"] == 1
    assert case["scenarios"][0]["rank_changes"] == []


def test_sensitivity_requires_review_when_baseline_changes():
    records, third, factors, cases = _analysis_inputs()
    third["a"]["global_cost_credit_profile"]["cost_band"] = "C6"
    with pytest.raises(ValueError, match="基准已变"):
        analyze(records, third, factors, cases)


def test_current_sensitivity_analysis_matches_current_formal_inputs():
    assert run(Path('.'))["non_scoring"] is True
