from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.evaluation.profile_c2_verifier import verify


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs" / "评分结算" / "皇帝人物画像"


def load(name: str):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def test_c2_verifier_closes_full_pool_and_entry_dispositions() -> None:
    result = verify()
    assert result["status"] == "PASS"
    assert result["record_count"] == 184
    assert result["evidence_limited_count"] == 54
    assert result["grade_distribution"] == {
        "G0": 12,
        "G1": 86,
        "G2": 57,
        "G3": 23,
        "G4": 4,
        "G5": 2,
    }
    assert result["no_parent_evidence_limited_count"] == 26
    assert result["parent_count"] == 188


def test_c2_high_grades_require_multiple_cycles_and_retest() -> None:
    settlement = load("19-C2信息处理学习与纠错正式结算.json")
    high_review = load("21-C2高档学习周期与横向校准复核.json")
    by_name = {row["ruler_name"]: row for row in settlement["records"]}
    assert {(row["ruler_name"], row["axis_grade"]) for row in high_review["profiles"]} == {
        ("赵祯", "G5"),
        ("李世民", "G5"),
        ("刘恒", "G4"),
        ("完颜雍", "G4"),
        ("李昪", "G4"),
        ("杨行密", "G4"),
    }
    assert all(row["independent_cycle_count"] >= 2 for row in high_review["profiles"])
    assert all(len(row["learning_cycles"]) == row["independent_cycle_count"] for row in high_review["profiles"])
    assert (by_name["赵匡胤"]["axis_grade"], by_name["赵匡胤"]["score_status"]) == ("G1", "EVIDENCE_LIMITED")
    assert (by_name["耶律隆绪"]["axis_grade"], by_name["耶律隆绪"]["score_status"]) == ("G1", "EVIDENCE_LIMITED")
    assert (by_name["皇太极"]["axis_grade"], by_name["皇太极"]["score_status"]) == ("G1", "EVIDENCE_LIMITED")
    assert (by_name["杨广"]["axis_grade"], by_name["杨广"]["position"]) == ("G0", "LOW")
    assert (by_name["胡亥"]["axis_grade"], by_name["胡亥"]["position"]) == ("G0", "LOW")


def test_c2_and_c5_consume_distinct_semantic_slices() -> None:
    settlement = load("19-C2信息处理学习与纠错正式结算.json")
    for record in settlement["records"]:
        for parent in record["parents"]:
            reason = parent["secondary_projection_reason"]
            assert "C5" in reason
            assert any(token in reason for token in ("认知更新", "本人理解", "不以该切片", "明确反馈后仍不更新"))
    audit = load("20-C2主要入口单元处置审计.json")
    assert audit["unresolved_count"] == 0
    assert audit["status_counts"]["UNRESOLVED_EVIDENCE_GAP"] == 0
    assert audit["status_counts"]["AXIS_OUT_WITH_REASON"] > 0
    assert len({unit["reason"] for unit in audit["units"]}) >= int(audit["unit_count"] * 0.95)


def test_c2_rejects_template_basis_and_no_parent_neutral_default() -> None:
    settlement = load("19-C2信息处理学习与纠错正式结算.json")
    records = settlement["records"]
    assert len({row["grade_basis"] for row in records}) == 184
    assert len({row["position_basis"] for row in records}) == 184
    no_parent = [row for row in records if not row["parents"]]
    assert no_parent
    assert all(row["score_status"] == "EVIDENCE_LIMITED" for row in no_parent)
    assert all(row["axis_grade"] in {"G0", "G1"} for row in no_parent)
    assert all(len(row["limitations"]) >= 2 for row in no_parent)


def test_c2_grade_direction_and_single_parent_high_gates() -> None:
    settlement = load("19-C2信息处理学习与纠错正式结算.json")
    for row in settlement["records"]:
        directions = {parent["direction"] for parent in row["parents"]}
        assert not (row["grade_numeric"] >= 3 and directions and directions <= {"NEGATIVE", "MIXED_NEGATIVE"})
        if row["axis_grade"] in {"G4", "G5"}:
            assert len(row["parents"]) >= 2
