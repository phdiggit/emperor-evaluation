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
    assert result["evidence_limited_count"] == 36
    assert result["grade_distribution"] == {
        "G0": 13,
        "G1": 52,
        "G2": 54,
        "G3": 57,
        "G4": 6,
        "G5": 2,
    }


def test_c2_high_grades_require_multiple_cycles_and_retest() -> None:
    settlement = load("19-C2信息处理学习与纠错正式结算.json")
    high_review = load("21-C2高档学习周期与横向校准复核.json")
    by_name = {row["ruler_name"]: row for row in settlement["records"]}
    assert {(row["ruler_name"], row["axis_grade"]) for row in high_review["profiles"]} == {
        ("赵祯", "G5"),
        ("李世民", "G5"),
        ("完颜雍", "G4"),
        ("刘恒", "G4"),
        ("赵匡胤", "G4"),
        ("耶律隆绪", "G4"),
        ("皇太极", "G4"),
        ("杨行密", "G4"),
    }
    assert all(row["cycle_anchor_count"] >= 2 for row in high_review["profiles"])
    assert (by_name["杨广"]["axis_grade"], by_name["杨广"]["position"]) == ("G0", "LOW")
    assert (by_name["胡亥"]["axis_grade"], by_name["胡亥"]["position"]) == ("G0", "LOW")


def test_c2_and_c5_consume_distinct_semantic_slices() -> None:
    settlement = load("19-C2信息处理学习与纠错正式结算.json")
    for record in settlement["records"]:
        for parent in record["parents"]:
            reason = parent["secondary_projection_reason"]
            assert "认知更新切片" in reason
            assert "C5" in reason
    audit = load("20-C2主要入口单元处置审计.json")
    assert audit["unresolved_count"] == 0
    assert audit["status_counts"]["UNRESOLVED_EVIDENCE_GAP"] == 0
