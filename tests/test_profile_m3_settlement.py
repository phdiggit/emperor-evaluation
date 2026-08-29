from __future__ import annotations

import json

from emperor_v4.evaluation.profile_m3_livelihood_settlement import (
    C4_ATTRIBUTION,
    C_PATHS,
    GRADE_PROJECTION,
    M3_ADJUDICATIONS,
    M3_SETTLEMENT,
    MISSING,
    RESULT,
    SUPPLEMENT,
)
from emperor_v4.evaluation.profile_m3_verifier import verify


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_profile_m3_is_holistically_adjudicated_from_second_item_c1_c4() -> None:
    settlement = _load(M3_SETTLEMENT)
    adjudications = {row["ruler_id"]: row for row in _load(M3_ADJUDICATIONS)["records"]}
    result = {row["ruler_id"]: row for row in _load(RESULT)["scores"]}
    assert settlement["axis_name"] == "民生财政建设"
    assert settlement["record_count"] == len(settlement["records"]) == 184
    for row in settlement["records"]:
        source = result[row["ruler_id"]]
        decision = adjudications[row["ruler_id"]]
        assert row["score_100"] == row["radar_value"] == GRADE_PROJECTION[(row["axis_grade"], row["position"])]
        assert row["axis_grade"] == decision["axis_grade"]
        assert row["position"] == decision["position"]
        assert set(row["components"]) == set(C_PATHS)
        assert row["components"]["C1"]["band"] == source["C1_band"]
        assert row["components"]["C4"]["score"] == source["C4_score"]
        assert row["value_mode"] == "SEMANTIC_HOLISTIC_ADJUDICATION_WITH_FIXED_GRADE_PROJECTION"
        assert row["axis_relevance_check"]["component_sum_used"] is False
        assert row["axis_relevance_check"]["quantile_or_normalization_used"] is False
        assert row["public_adjudication"]
    assert verify() == {
        "profile_population": 184,
        "finance_population": 195,
        "old_m3_candidate_count": 316,
        "old_m3_parent_chain_count": 204,
        "new_finance_record_count": 10,
        "m3_grade_distribution": {"G0": 18, "G1": 45, "G2": 54, "G3": 46, "G4": 16, "G5": 5},
        "m3_cross_grade_count": 109,
    }


def test_profile_m3_old_material_is_routed_without_process_to_result_conversion() -> None:
    supplement = _load(SUPPLEMENT)
    assert supplement["record_count"] == len(supplement["records"]) == 184
    assert supplement["parent_chain_count"] == 204
    assert supplement["candidate_trace_count"] == 316
    assert supplement["policy"]["no_process_to_result_conversion"] is True
    assert all(row["review_status"] == "FULLY_ROUTED_TO_C1_C2_C3_C4" for row in supplement["records"])
    parents = [parent for row in supplement["records"] for parent in row["parent_chain_reviews"]]
    orphans = [candidate for row in supplement["records"] for candidate in row["orphan_candidate_reviews"]]
    assert len(parents) == 204
    assert len(orphans) == 59
    assert all(set(parent["axis_routes"]) == set(C_PATHS) for parent in parents)
    assert all(set(candidate["axis_routes"]) == set(C_PATHS) for candidate in orphans)
    by_name = {row["ruler_name"]: row for row in supplement["records"]}
    anquan = by_name["李安全"]
    assert any(
        route["disposition"] == "EXCLUDED_WRONG_RULER_WINDOW"
        for route in anquan["parent_chain_reviews"]
    )
    guangxu = by_name["载湉"]
    assert any(
        route["disposition"] == "EXCLUDED_UNBOUND_DYNASTIC_TREATISE"
        for route in guangxu["parent_chain_reviews"]
    )


def test_profile_m3_missing_finance_records_are_added_for_all_ten_profile_rulers() -> None:
    missing = _load(MISSING)
    missing_ids = {row["ruler_id"] for row in missing["records"]}
    assert missing["record_count"] == len(missing_ids) == 10
    for axis, path in C_PATHS.items():
        rows = {row["ruler_id"]: row for row in _load(path)["scores"]}
        assert len(rows) == 195
        assert missing_ids <= set(rows)
        if axis == "C4":
            assert all(
                rows[ruler_id]["m3_supplement_review"]["disposition"]
                in {"REVIEWED_C4_ATTRIBUTION_RETAINED", "APPLIED_C4_ATTRIBUTION_READJUDICATION"}
                for ruler_id in missing_ids
            )
        else:
            assert all(
                rows[ruler_id]["m3_supplement_review"]["disposition"]
                == "APPLIED_SCORE_CHANGE_NEW_FORMAL_RECORD"
                for ruler_id in missing_ids
            )


def test_c4_attribution_is_individually_adjudicated_without_default_da1() -> None:
    audit = _load(C4_ATTRIBUTION)
    assert audit["record_count"] == len(audit["records"]) == 184
    assert audit["grade_counts"] == {"DA0": 15, "DA1": 51, "DA2": 74, "DA3": 41, "DA4": 3}
    assert all(row["review_status"] == "FULLY_ADJUDICATED" for row in audit["records"])
    assert all(row["source_refs"] for row in audit["records"])
    assert all(
        row["closed_residual_harm_observations"]
        for row in audit["records"]
        if row["decision"]["final_grade"] != "DA0"
    )
    by_name = {row["ruler_name"]: row for row in audit["records"]}
    assert by_name["杨坚"]["decision"]["final_grade"] == "DA3"
    assert by_name["武则天"]["decision"]["final_grade"] == "DA3"
    assert by_name["高纬"]["decision"]["final_grade"] == "DA3"
    assert by_name["玄烨"]["decision"]["final_grade"] == "DA2"
    assert by_name["李治"]["decision"]["final_grade"] == "DA3"


def test_profile_m3_anchor_values_follow_semantic_boundaries_and_handoff() -> None:
    by_name = {row["ruler_name"]: row for row in _load(M3_SETTLEMENT)["records"]}
    assert (by_name["李世民"]["axis_grade"], by_name["李世民"]["position"], by_name["李世民"]["score_100"]) == ("G5", "LOW", 91)
    assert (by_name["刘启"]["axis_grade"], by_name["刘启"]["position"], by_name["刘启"]["score_100"]) == ("G5", "LOW", 91)
    assert (by_name["李治"]["axis_grade"], by_name["李治"]["position"], by_name["李治"]["score_100"]) == ("G2", "LOW", 38)
    assert (by_name["胤禛"]["axis_grade"], by_name["胤禛"]["position"], by_name["胤禛"]["score_100"]) == ("G5", "LOW", 91)
    assert by_name["李世民"]["components"]["C4"]["score"] == 25.2
    assert by_name["李治"]["components"]["C4"]["score"] == -19.8
    assert (by_name["玄烨"]["axis_grade"], by_name["玄烨"]["position"], by_name["玄烨"]["score_100"]) == ("G4", "LOW", 77)
    assert by_name["玄烨"]["components"]["C4"]["score"] == 7.5
    assert by_name["李隆基"]["axis_grade"] == "G2"
    assert by_name["杨广"]["axis_grade"] == "G0"
