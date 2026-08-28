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
        load("C2/19-C2信息处理学习与纠错正式结算.json"),
        load("C2/20-C2主要入口单元处置审计.json"),
        load("C2/21-C2高档学习周期与横向校准复核.json"),
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
    assert result["evidence_level_distribution"] == {"E1": 153, "E2": 31}
    assert result["grade_distribution"] == {"G0": 11, "G1": 62, "G2": 86, "G3": 17, "G4": 8}
    assert result["parent_count"] == 222
    assert result["no_parent_evidence_limited_count"] == 47
    assert result["intuitive_candidate_count"] == 16
    assert result["score_70_or_above_count"] == 16


def test_c2_high_grades_are_reopened_and_li_shimin_volume_193_is_consumed() -> None:
    settlement, _, high = payloads()
    by_name = {row["ruler_name"]: row for row in settlement["records"]}
    assert {(row["ruler_name"], row["axis_grade"]) for row in high["profiles"]} == {
        (name, "G4") for name in {"李世民", "刘邦", "刘恒", "柴荣", "赵祯", "完颜雍", "皇太极", "玄烨"}
    }
    assert {p["parent_id"] for p in by_name["李世民"]["parents"]} >= {
        "C2-P153-CONSTRUCTION-COST-RETEST-630-631",
        "C2-P153-HEXI-SUPPLY-VERIFICATION-630",
        "C2-P153-LUZUSHANG-JUDICIAL-REGRET",
        "C2-P153-PALACE-WOMAN-RECHECK",
        "C2-P153-MUSICIAN-BLAME-REVIEW",
        "C2-P153-LEGAL-REVIEW-SYSTEM",
        "C2-P153-DELIBERATION-RECHECK",
        "C2-P153-LATE-FEEDBACK-CONTRACTION",
    }
    assert all("贞观政要" not in ref and "貞觀政要" not in ref for p in by_name["李世民"]["parents"] for ref in p["cycle_anchor_refs"])


def test_c2_candidate_reading_budget_is_hard_capped_and_intuition_frozen() -> None:
    settlement, _, high = payloads()
    assert high["material_budget_policy"] == "MAX_4_SUPPLEMENTAL_PRIMARY_SOURCE_UNITS_PER_CANDIDATE"
    assert len(high["candidate_reviews"]) == 16
    assert all(1 <= row["unit_count"] <= 4 for row in high["candidate_reviews"])
    assert all(row["normative_entry_refs"] for row in high["candidate_reviews"])
    assert all(row["combined_source_refs"] == list(dict.fromkeys(row["normative_entry_refs"] + row["supplemental_primary_units"])) for row in high["candidate_reviews"])
    assert {row["ruler_name"] for row in high["candidate_reviews"]} == {
        "嬴政", "刘邦", "刘恒", "刘秀", "刘询", "曹操", "杨坚", "李世民",
        "柴荣", "赵祯", "萧绰", "完颜雍", "铁木真", "皇太极", "玄烨", "胤禛",
    }

    def overflow(settlement, audit, high):
        row = high["candidate_reviews"][0]
        row["supplemental_primary_units"].append("https://example.invalid/fifth-unit")
        row["unit_count"] = 5
    assert_rejected(overflow)

    def keyword_selection(settlement, audit, high):
        high["selection_keywords"] = ["从之", "悔"]
    assert_rejected(keyword_selection)


def test_c2_candidate_union_excludes_person_specific_sources_and_separates_directional_strength() -> None:
    settlement, _, high = payloads()
    by_name = {row["ruler_name"]: row for row in settlement["records"]}
    candidates = {row["ruler_name"]: row for row in high["candidate_reviews"]}
    assert "MC-TANG-TS-DELIBERATION-M3-AUDIT" in candidates["李世民"]["normative_entry_refs"]
    assert all("贞观政要" not in ref and "貞觀政要" not in ref for row in candidates.values() for ref in row["combined_source_refs"])
    intensities = {p["material_intensity"] for name in candidates for p in by_name[name]["parents"]}
    assert {"MI1_CASE", "MI2_LIFECYCLE", "MI3_SUSTAINED_SYSTEMIC"} <= intensities
    assert (by_name["嬴政"]["radar_value"], by_name["胤禛"]["radar_value"]) == (58, 65)
    assert by_name["刘秀"]["radar_value"] == 71
    assert (by_name["杨坚"]["axis_grade"], by_name["杨坚"]["position"], by_name["杨坚"]["radar_value"]) == ("G3", "MID", 65)


def test_c2_candidate_b2_materials_are_individually_bound_and_suppression_is_asymmetric() -> None:
    settlement, audit, high = payloads()
    by_name = {row["ruler_name"]: row for row in settlement["records"]}
    candidates = {row["ruler_name"]: row for row in high["candidate_reviews"]}
    assert high["candidate_b2_material_count"] == 58
    assert sum(
        item["status"] == "SCORING_PARENT"
        for row in candidates.values()
        for item in row["b2_material_disposition_review"]
    ) == settlement["summary"]["candidate_b2_scoring_parent_count"] == 33
    assert all(
        "另由具体父链" not in item["reason"]
        for row in candidates.values()
        for item in row["b2_material_disposition_review"]
    )
    yang = by_name["杨坚"]
    assert set(yang["directional_strength_balance_review"]["suppression_parent_ids"]) == {
        "C2-P119-PERSONNEL-DISSENT-SUPPRESSION",
        "C2-P119-PALACE-EXTRALEGAL-BEATING-RECURRENCE",
        "C2-P119-SUCCESSION-MISINFORMATION",
        "C2-P119-YANGSU-CAPTURE-RECURRENCE",
    }
    purge = next(p for p in yang["parents"] if p["parent_id"] == "C2-P119-PERSONNEL-DISSENT-SUPPRESSION")
    assert purge["intensity"] == "MI3_SUSTAINED_SYSTEMIC"
    assert purge["feedback_suppression_review"]["sanction_or_exclusion_intensity"] == "EXTREME"
    assert purge["feedback_suppression_review"]["future_channel_effect"] == "CHANNEL_DESTRUCTION"
    beating = next(p for p in yang["parents"] if p["parent_id"] == "C2-P119-PALACE-EXTRALEGAL-BEATING-RECURRENCE")
    assert beating["intensity"] == "MI3_SUSTAINED_SYSTEMIC"
    assert {"LAW-16-005", "LAW-16-007"} <= set(beating["source_parent_refs"])

    def empty_background_binding(settlement, audit, high):
        item = next(
            item
            for candidate in high["candidate_reviews"]
            for item in candidate["b2_material_disposition_review"]
            if item["status"] == "BACKGROUND_VALIDATION"
        )
        item["supports_parent_ids"] = []
    assert_rejected(empty_background_binding)

    def erase_suppression_strength(settlement, audit, high):
        row = next(row for row in settlement["records"] if row["ruler_name"] == "杨坚")
        parent = next(p for p in row["parents"] if p["parent_id"] == "C2-P119-PERSONNEL-DISSENT-SUPPRESSION")
        parent["feedback_suppression_review"]["recurrence_scope"] = "SINGLE_CASE"
    assert_rejected(erase_suppression_strength)


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
