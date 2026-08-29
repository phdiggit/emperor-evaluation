from __future__ import annotations

import json

from emperor_v4.evaluation.profile_m3_livelihood_settlement import (
    C4_ATTRIBUTION,
    C_PATHS,
    M3_SETTLEMENT,
    MISSING,
    RESULT,
    SUPPLEMENT,
)
from emperor_v4.evaluation.profile_m3_verifier import verify


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_profile_m3_is_fully_synchronized_with_second_item_c1_c4() -> None:
    settlement = _load(M3_SETTLEMENT)
    result = {row["ruler_id"]: row for row in _load(RESULT)["scores"]}
    assert settlement["axis_name"] == "民生财政建设"
    assert settlement["record_count"] == len(settlement["records"]) == 184
    for row in settlement["records"]:
        source = result[row["ruler_id"]]
        expected = round(max(0.0, min(100.0, source["score"] / 220 * 100)))
        assert row["score_100"] == row["radar_value"] == expected
        assert row["component_total_220"] == source["score"]
        assert set(row["components"]) == set(C_PATHS)
        assert row["value_mode"] == "SECOND_ITEM_C1_C2_C3_C4_SYNCHRONIZED"
    assert verify() == {
        "profile_population": 184,
        "finance_population": 195,
        "old_m3_candidate_count": 316,
        "old_m3_parent_chain_count": 204,
        "new_finance_record_count": 10,
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
    assert audit["grade_counts"] == {"DA0": 28, "DA1": 57, "DA2": 56, "DA3": 40, "DA4": 3}
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
    assert by_name["玄烨"]["decision"]["final_grade"] == "DA0"


def test_profile_m3_anchor_values_are_separated_by_the_four_components() -> None:
    by_name = {row["ruler_name"]: row for row in _load(M3_SETTLEMENT)["records"]}
    assert by_name["李世民"]["score_100"] == 80
    assert by_name["刘启"]["score_100"] == 75
    assert by_name["李治"]["score_100"] == 49
    assert by_name["胤禛"]["score_100"] == 67
    assert by_name["李世民"]["components"]["C4"]["score"] == 25.2
    assert by_name["李治"]["components"]["C4"]["score"] == -10.8
