from decimal import Decimal
from pathlib import Path

from scripts.dev import retrieval_v3_team_building_object_pool as tool


def options():
    return {
        "talent_quality_factor": {
            "T1": {"option_code": "T1", "label": "历史级人才。", "value_num": Decimal("2")},
            "T3": {"option_code": "T3", "label": "重要人才。", "value_num": Decimal("1")},
        },
        "role_complementarity_factor": {"R": {"option_code": "R", "label": "高度互补", "value_num": Decimal("1.3")}},
        "long_term_stability_factor": {"S": {"option_code": "S", "label": "稳定", "value_num": Decimal("0.8")}},
    }


def test_object_pool_collapses_duplicate_target_rows_and_scores_each_person_once() -> None:
    people = [
        {"emperor_name": "甲", "object_id": 1, "canonical_name": "甲臣", "talent_grade": "historic_talent", "talent_grade_version": "v", "readiness_status": "profile_complete", "source_target_ids": [1, 2], "target_object_ids": [10, 20]},
        {"emperor_name": "甲", "object_id": 2, "canonical_name": "乙臣", "talent_grade": "important_talent", "talent_grade_version": "v", "readiness_status": "profile_complete", "source_target_ids": [2], "target_object_ids": [21]},
    ]
    clusters = tool.build_clusters(
        people=people,targets={"甲": {"target_id": 2, "target_code": "T", "emperor_name": "甲", "item_code": "I5B"}},
        options=options(),choices={"甲": {"role_complementarity_factor": "R", "long_term_stability_factor": "S", "basis": "审定"}},
        formula_code="F",
    )
    cluster = clusters[0]
    assert cluster["positive_signal"] == Decimal("3.120")
    assert cluster["action_counts"]["score"] == 2
    assert cluster["calc_detail"]["duplicate_target_rows_collapsed"] == 1
    assert len(cluster["calc_detail"]["team_object_components"]) == 2


def test_object_pool_rejects_incomplete_profile() -> None:
    people = [{"emperor_name": "甲", "object_id": 1, "canonical_name": "甲臣", "talent_grade": None, "readiness_status": "no_claim", "source_target_ids": [1], "target_object_ids": [1]}]
    try:
        tool.build_clusters(people=people,targets={"甲": {"target_id": 1}},options=options(),choices={"甲": {"role_complementarity_factor": "R", "long_term_stability_factor": "S"}},formula_code="F")
    except tool.TeamBuildingObjectPoolError as exc:
        assert "incomplete profile" in str(exc)
    else:
        raise AssertionError("expected incomplete profile rejection")


def test_object_pool_accepts_punctuation_normalized_labels_and_label_choices() -> None:
    factor_options = options()
    factor_options["talent_quality_factor"]["T1"]["label"] = "历史级人才"
    resolved = tool.option(factor_options, "role_complementarity_factor", "高度互补。")
    assert resolved["option_code"] == "R"
    people = [{"emperor_name": "甲", "object_id": 1, "canonical_name": "甲臣", "talent_grade": "historic_talent", "talent_grade_version": "v", "readiness_status": "profile_complete", "source_target_ids": [1], "target_object_ids": [1]}]
    clusters = tool.build_clusters(
        people=people, targets={"甲": {"target_id": 1}}, options=factor_options,
        choices={"甲": {"role_complementarity_factor": "高度互补。", "long_term_stability_factor": "稳定"}},
        formula_code="F",
    )
    assert clusters[0]["positive_signal"] == Decimal("2.080")
