from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.profile_c2_verifier import verify, verify_payloads


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs" / "评分结算" / "皇帝人物画像"


def load(name: str):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def payloads():
    return (
        load("19-C2信息处理学习与纠错正式结算.json"),
        load("20-C2主要入口单元处置审计.json"),
        load("21-C2高档学习周期与横向校准复核.json"),
    )


def assert_rejected(mutator) -> None:
    settlement, audit, high = map(copy.deepcopy, payloads())
    mutator(settlement, audit, high)
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high)


def test_c2_verifier_closes_pool_and_bounded_coverage_ledger() -> None:
    result = verify()
    assert result["status"] == "PASS"
    assert result["record_count"] == 184
    assert result["evidence_limited_count"] == 184
    assert result["evidence_level_distribution"] == {"E1": 161, "E2": 23}
    assert result["parent_count"] == 167
    assert result["no_parent_evidence_limited_count"] == 54


def test_c2_high_grades_are_reopened_and_li_shimin_volume_193_is_consumed() -> None:
    settlement, _, high = payloads()
    by_name = {row["ruler_name"]: row for row in settlement["records"]}
    assert {(row["ruler_name"], row["axis_grade"]) for row in high["profiles"]} == {
        ("李世民", "G4"), ("刘邦", "G4")
    }
    assert {p["parent_id"] for p in by_name["李世民"]["parents"]} >= {
        "C2-P153-CONSTRUCTION-COST-RETEST-630-631",
        "C2-P153-HEXI-SUPPLY-VERIFICATION-630",
    }
    assert (by_name["刘恒"]["axis_grade"], by_name["完颜雍"]["axis_grade"]) == ("G3", "G3")
    assert (by_name["皇太极"]["axis_grade"], by_name["玄烨"]["axis_grade"]) == ("G3", "G3")


def test_c2_rejects_keyword_hits_as_coverage() -> None:
    def mutate(settlement, audit, high):
        settlement["records"][0]["coverage_review"]["keyword_hits"] = ["从之"]
    assert_rejected(mutate)


def test_c2_rejects_targeted_summary_as_full_lifetime_e3() -> None:
    def mutate(settlement, audit, high):
        row = settlement["records"][0]
        row["axis_evidence_level"] = "E3"
    assert_rejected(mutate)


def test_c2_rejects_no_parent_neutral_default_and_template_basis() -> None:
    def neutral(settlement, audit, high):
        row = next(row for row in settlement["records"] if not row["parents"])
        row["score_status"] = "FINAL"
    assert_rejected(neutral)

    def template(settlement, audit, high):
        row = settlement["records"][0]
        row["grade_basis"] = f"{row['ruler_name']}：该直接材料记录其他制度行政机制；人工回读确认信息或反证已到达本人。"
    assert_rejected(template)


def test_c2_rejects_uniform_entry_disposition_and_giant_high_parent() -> None:
    def uniform(settlement, audit, high):
        for unit in audit["units"]:
            unit["status"] = "BACKGROUND_VALIDATION"
    assert_rejected(uniform)

    def giant(settlement, audit, high):
        row = next(row for row in settlement["records"] if row["axis_grade"] == "G4")
        row["parents"] = row["parents"][:1]
        row["axis_relevance_check"]["scoring_parent_refs"] = [row["parents"][0]["parent_id"]]
    assert_rejected(giant)


def test_c2_rejects_text_grade_contradiction_behavior_inference_and_c5_backflow() -> None:
    def contradiction(settlement, audit, high):
        row = next(row for row in settlement["records"] if row["axis_grade"] == "G4")
        for parent in row["parents"]:
            parent["direction"] = "NEGATIVE"
    assert_rejected(contradiction)

    def behavior_only(settlement, audit, high):
        row = next(row for row in settlement["records"] if row["parents"])
        row["parents"][0]["basis"] = "战败后改变策略，因此证明认知更新。"
    assert_rejected(behavior_only)

    def c5_backflow(settlement, audit, high):
        row = next(row for row in settlement["records"] if row["parents"])
        row["parents"][0]["secondary_projection_reason"] = "C5异议者安全与处罚比例直接支持C2。"
    assert_rejected(c5_backflow)
