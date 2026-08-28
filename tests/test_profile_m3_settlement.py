from __future__ import annotations

import json
from collections import Counter

from emperor_v4.evaluation.profile_m3_settlement import CALIBRATION_THRESHOLDS, COVERAGE_MATRIX, MANUAL, NATURAL_RECOVERY_COMPARATOR, NEGATIVE_EXPLANATORY_REVIEW, RETAINED_MANUAL_PARENT_REVIEW, SCREENING, SEMANTIC_REVIEW, build
from emperor_v4.evaluation.profile_m3_verifier import verify


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_profile_m3_formal_build_consumes_the_accepted_dual_channel_calibration() -> None:
    result = build(write=False)
    settlement = result["settlement"]
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert {row["formal_status"] for row in settlement["records"]} == {"FORMAL_CURRENT"}
    assert _load(SCREENING)["canonical_status"] == "FORMAL_CURRENT_INPUT"
    assert _load(COVERAGE_MATRIX)["canonical_status"] == "FORMAL_CURRENT_INPUT"
    assert _load(SEMANTIC_REVIEW)["canonical_status"] == "FORMAL_CURRENT_AUDIT_SOURCE"
    assert _load(RETAINED_MANUAL_PARENT_REVIEW)["canonical_status"] == "FORMAL_CURRENT_AUDIT_SOURCE"
    assert _load(NATURAL_RECOVERY_COMPARATOR)["canonical_status"] == "FORMAL_CURRENT_COMPARATOR_SOURCE"
    assert _load(NEGATIVE_EXPLANATORY_REVIEW)["canonical_status"] == "FORMAL_CURRENT_AUDIT_SOURCE"
    assert settlement["record_count"] == 184
    assert settlement["blocking_gap_count"] == 0
    assert settlement["formally_bounded_negative_mechanism_gap_count"] == 14
    assert settlement["grade_distribution"] == {"G0": 8, "G1": 61, "G2": 75, "G3": 36, "G4": 4}
    assert verify()["status"] == "PASS"


def test_profile_m3_synthetic_parents_and_default_baseline_are_removed() -> None:
    payload = _load(MANUAL)
    records = payload["records"]
    parents = [parent for row in records for parent in row["parents"]]
    assert payload["removed_synthetic_parent_count"] == 415
    assert payload["retained_or_rebuilt_process_parent_count"] == len(parents) == 204
    assert all("史料只闭合所载选择及其反面" not in str(parent) for parent in parents)
    assert all("本人窗口内的可定位选择" not in str(parent) for parent in parents)
    assert all(parent["channel"] == "PROCESS_CHANNEL" for parent in parents)
    assert all(parent["phase_coverage"] and parent["choice_types"] for parent in parents)
    distribution = Counter(row["score_100"] for row in records)
    assert max(distribution.values()) == 44
    assert distribution[45] == 17
    assert len(distribution) >= 8
    assert all(row["score_100"] is not None and row["axis_grade"] for row in records)
    inferred = [row for row in records if not row["parents"]]
    assert inferred
    assert all(row["value_mode"] == "RESULT_CONSTRAINED_INFERENCE" for row in inferred)
    assert len({row["score_100"] for row in inferred}) > 1


def test_profile_m3_all_pool_has_independent_result_constraint_channel() -> None:
    records = _load(MANUAL)["records"]
    assert len(records) == 184
    for row in records:
        channel = row["revealed_capability_channel"]
        assert channel["channel"] == "REVEALED_CAPABILITY_CHANNEL"
        assert set(channel["observed_transition"]) == {"C1", "C2"}
        assert set(channel["observed_transition"]["C1"]) == {"S0", "S_avg", "S_end"}
        assert channel["natural_recovery_envelope"]["status"] == "FORMAL_CURRENT_COMPARATOR_GROUP"
        assert channel["legacy_d2_bottom_material"]["use_boundary"] == "BOTTOM_HANDOFF_MATERIAL_ONLY_NOT_RETIRED_SCORE"
        assert channel["use_boundary"] == "CONSTRAINS_PROVISIONAL_VALUE_AND_CONTRADICTION_REVIEW_NOT_ONE_TO_ONE_GRADE_CONVERSION"
        assert row["axis_relevance_check"]["result_curve_used_as_constraint"]
        assert not row["axis_relevance_check"]["second_item_score_used"]
        assert not row["axis_relevance_check"]["second_item_band_used"]
        assert not row["axis_relevance_check"]["final_outcome_backsolve_used"]


def test_profile_m3_negative_result_gaps_are_symmetric_and_explicit() -> None:
    records = _load(MANUAL)["records"]
    triggers = [
        row for row in records
        if row["revealed_capability_channel"]["negative_explanatory_review"]["required"]
    ]
    assert triggers
    assert all(
        set(row["revealed_capability_channel"]["negative_explanatory_review"]["decomposition"])
        == {"EXOGENOUS_EXPLAINED", "INHERITED_OR_SCOPE_EFFECT", "RULER_ATTRIBUTABLE", "UNRESOLVED_RESIDUAL"}
        for row in triggers
    )
    assert sum(row["same_chain_review"] == "REVERSE_SEARCH_COMPLETE_RESULT_CONSTRAINED_MECHANISM_GAP_ACCEPTED" for row in triggers) == 14
    assert not any("PENDING_SEMANTIC_DECOMPOSITION" in str(row["revealed_capability_channel"]["negative_explanatory_review"]) for row in records)
    review = _load(NEGATIVE_EXPLANATORY_REVIEW)
    assert review["trigger_count"] == len(review["records"]) == 59
    assert review["reverse_search_complete_count"] == 59
    assert review["reverse_search_pending_count"] == 0
    assert review["outcome_counts"] == {
        "PROCESS_NEGATIVE_CHAIN_LOCATED": 21,
        "CURRENT_C4_ATTRIBUTION_LOCATED_PROCESS_CHAIN_STILL_LIMITED": 24,
        "REVEALED_NEGATIVE_CAPABILITY_WITH_MECHANISM_GAP": 14,
    }
    retained = _load(RETAINED_MANUAL_PARENT_REVIEW)
    assert retained["candidate_count"] == 11
    assert retained["regime_chain_count"] == 5
    assert retained["pending_count"] == 0
    thresholds = _load(CALIBRATION_THRESHOLDS)
    assert thresholds["canonical_status"] == "FORMAL_CURRENT_RULE"
    assert thresholds["acceptance_gates"]["name_override_allowed"] is False
    assert thresholds["acceptance_gates"]["second_item_band_conversion_allowed"] is False


def test_profile_m3_natural_recovery_comparator_covers_all_people_without_penalizing_missing_sources() -> None:
    comparator = _load(NATURAL_RECOVERY_COMPARATOR)
    assert comparator["record_count"] == len(comparator["records"]) == 184
    assert comparator["group_count"] == len(comparator["groups"]) == 21
    assert comparator["residual_counts"] == {
        "ABOVE_NATURAL_RECOVERY_ENVELOPE": 47,
        "WITHIN_NATURAL_RECOVERY_ENVELOPE": 70,
        "BELOW_COMPARATOR_ENVELOPE": 57,
        "SOURCE_UNAVAILABLE_BOUNDED": 10,
    }
    unavailable = [row for row in comparator["records"] if row["residual_class"] == "SOURCE_UNAVAILABLE_BOUNDED"]
    assert len(unavailable) == 10
    assert all(row["metric"] is None and row["result_level"] == "R1" for row in unavailable)
    assert all(row["source_unavailability_bias"] for row in unavailable)


def test_profile_m3_second_item_recuts_no_longer_create_process_parents() -> None:
    screening = _load(SCREENING)
    original = [
        unit for row in screening["records"] for unit in row["units"]
        if unit["source_kind"] in {"SECOND_ITEM_C1", "SECOND_ITEM_C2", "SECOND_ITEM_NAVIGATION_RECUT"}
    ]
    assert original
    assert all(unit["status"] == "BACKGROUND_VALIDATION" for unit in original)
    assert all(unit["scoring_parent_id"] is None for unit in original)
    accepted = [unit for row in screening["records"] for unit in row["units"] if unit["status"] == "PROCESS_EVIDENCE_ACCEPTED"]
    retained = [unit for row in screening["records"] for unit in row["units"] if unit["status"] == "SCORING_PARENT"]
    scoring = accepted + retained
    assert len(accepted) == 260
    assert len(retained) == 17
    assert all(unit["source_kind"] != "SECOND_ITEM_NAVIGATION_RECUT" for unit in scoring)


def test_profile_m3_food_treatise_and_contextual_exemption_are_screened() -> None:
    screening = _load(SCREENING)
    food = screening["food_treatise_coverage"]
    assert food["source_count"] == food["fetched_source_count"] == 50
    assert food["mechanical_candidate_count"] == 2144
    assert "免" in food["keyword_policy"]["contextual_exemption"]
    assert "税" in screening["policy"] and "免" in screening["policy"]


def test_profile_m3_full_pool_matrix_and_candidate_semantics_are_complete() -> None:
    matrix = _load(COVERAGE_MATRIX)
    assert matrix["record_count"] == len(matrix["records"]) == 184
    assert matrix["cell_count_per_ruler"] == 2520
    assert matrix["total_cell_count"] == 463680
    assert matrix["anchor_semantic_review_count"] == 184
    assert matrix["full_pool_semantic_review_pending_count"] == 0
    assert {row["matrix_status"] for row in matrix["records"]} == {"MECHANICAL_AND_SEMANTIC_REVIEW_COMPLETE"}
    review = _load(SEMANTIC_REVIEW)
    assert review["record_count"] == len(review["records"]) == 316
    assert review["ruler_count"] == 184
    assert review["disposition_counts"] == {
        "PROCESS_EVIDENCE_ACCEPTED": 260,
        "AXIS_OUT_WITH_REASON": 43,
        "RESULT_VALIDATION_ONLY": 13,
    }
    allowed = set(matrix["status_code_legend"])
    for row in matrix["records"]:
        assert row["cell_count"] == 2520
        assert len(row["coverage"]) == 5
        assert all(len(phase["mechanisms"]) == 8 for phase in row["coverage"])
        vectors = [
            choice["source_status_vector"]
            for phase in row["coverage"]
            for mechanism in phase["mechanisms"]
            for choice in mechanism["choices"]
        ]
        assert len(vectors) == 280
        assert all(len(vector) == 9 and set(vector) <= allowed for vector in vectors)


def test_profile_m3_three_anchor_collision_is_resolved_by_dual_channels() -> None:
    by_name = {row["ruler_name"]: row for row in _load(MANUAL)["records"]}
    taizong, gaozong, jingdi = by_name["李世民"], by_name["李治"], by_name["刘启"]
    assert (taizong["axis_grade"], taizong["position"], taizong["score_100"]) == ("G4", "LOW", 77)
    assert (gaozong["axis_grade"], gaozong["position"], gaozong["score_100"]) == ("G1", "MID", 25)
    assert (jingdi["axis_grade"], jingdi["position"], jingdi["score_100"]) == ("G4", "LOW", 77)
    assert taizong["process_channel"]["level"] == "P3"
    assert taizong["revealed_capability_channel"]["unexplained_result_residual"]["level"] == "R3"
    assert gaozong["dual_channel_adjudication"]["result_level"] == "R0"
    assert gaozong["revealed_capability_channel"]["negative_explanatory_review"]["required"]
    assert jingdi["dual_channel_adjudication"]["result_level"] == "R3"
    assert jingdi["revealed_capability_channel"]["unexplained_result_residual"]["stability_class"] == "HIGH_LEVEL_MAINTENANCE_UNDER_PRESSURE"
    assert {parent["parent_type"] for parent in taizong["parents"]} == {"REGIME_CHAIN", "COUNTER_REGIME_CHAIN"}
    assert "REGIME_CHAIN" in {parent["parent_type"] for parent in jingdi["parents"]}
