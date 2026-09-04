from __future__ import annotations

import copy
from pathlib import Path

import pytest

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_c2_verifier import verify, verify_payloads


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs" / "评分结算" / "皇帝人物画像"


def load(name: str):
    return load_json(BASE / name)


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


def test_c2_candidate_reading_budget_is_hard_capped_and_intuition_frozen() -> None:
    settlement, _, high = payloads()
    assert high["material_budget_policy"] == "MAX_4_SUPPLEMENTAL_PRIMARY_SOURCE_UNITS_PER_CANDIDATE"
    assert all(1 <= row["unit_count"] <= 4 for row in high["candidate_reviews"])
    assert all(row["normative_entry_refs"] for row in high["candidate_reviews"])
    assert all(row["combined_source_refs"] == list(dict.fromkeys(row["normative_entry_refs"] + row["supplemental_primary_units"])) for row in high["candidate_reviews"])
    def overflow(settlement, audit, high):
        row = high["candidate_reviews"][0]
        row["supplemental_primary_units"].append("https://example.invalid/fifth-unit")
        row["unit_count"] = 5
    assert_rejected(overflow)

    def keyword_selection(settlement, audit, high):
        high["selection_keywords"] = ["从之", "悔"]
    assert_rejected(keyword_selection)


def test_c2_candidate_b2_materials_are_individually_bound_and_suppression_is_asymmetric() -> None:
    settlement, audit, high = payloads()
    candidates = {row["ruler_name"]: row for row in high["candidate_reviews"]}
    assert sum(
        item["status"] == "SCORING_PARENT"
        for row in candidates.values()
        for item in row["b2_material_disposition_review"]
    ) == settlement["summary"]["candidate_b2_scoring_parent_count"]
    assert all(
        "另由具体父链" not in item["reason"]
        for row in candidates.values()
        for item in row["b2_material_disposition_review"]
    )
    def empty_background_binding(settlement, audit, high):
        item = next(
            item
            for candidate in high["candidate_reviews"]
            for item in candidate["b2_material_disposition_review"]
            if item["status"] == "BACKGROUND_VALIDATION" and item["supports_parent_ids"]
        )
        item["supports_parent_ids"] = []
    assert_rejected(empty_background_binding)

    def erase_suppression_strength(settlement, audit, high):
        row = next(row for row in settlement["records"] if any(p.get("feedback_suppression_review", {}).get("recurrence_scope") not in {None, "SINGLE_CASE"} for p in row["parents"]))
        parent = next(p for p in row["parents"] if p.get("feedback_suppression_review", {}).get("recurrence_scope") not in {None, "SINGLE_CASE"})
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
