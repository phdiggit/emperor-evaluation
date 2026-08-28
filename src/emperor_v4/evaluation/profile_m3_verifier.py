from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.profile_m3_settlement import (
    ACCEPTANCE, AUDIT, CALIBRATION_THRESHOLDS, CONTRACT, COVERAGE_MATRIX, FULL_POOL_REVIEW, HIGH_REVIEW, MANIFEST, MANUAL, NATURAL_RECOVERY_COMPARATOR, NEGATIVE_EXPLANATORY_REVIEW, RETAINED_MANUAL_PARENT_REVIEW, SCREENING, SEMANTIC_REVIEW,
    MARKDOWN, POOL, ROOT, SCORES, SETTLEMENT,
)
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


PROJECT = ROOT / "config/project.yml"


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {path}"
    raw.decode("utf-8")
    return raw


def _load(path: Path) -> Any:
    return json.loads(_read(path).decode("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(_read(path)).hexdigest()


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def verify_payloads(settlement: dict[str, Any], audit: dict[str, Any], high: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    records = settlement["records"]
    pool = _load(POOL)
    included = {row["ruler_id"] for row in pool["records"] if row["pool_status"] == "INCLUDED"}
    assert settlement["schema_version"] == "profile-m3-formal-settlement-v1"
    assert settlement["canonical_status"] == "FORMAL_CURRENT" and settlement["axis_code"] == "M3"
    assert all(row["formal_status"] == "FORMAL_CURRENT" for row in settlement["records"])
    assert _load(SCREENING)["canonical_status"] == "FORMAL_CURRENT_INPUT"
    assert _load(COVERAGE_MATRIX)["canonical_status"] == "FORMAL_CURRENT_INPUT"
    assert _load(SEMANTIC_REVIEW)["canonical_status"] == "FORMAL_CURRENT_AUDIT_SOURCE"
    assert _load(RETAINED_MANUAL_PARENT_REVIEW)["canonical_status"] == "FORMAL_CURRENT_AUDIT_SOURCE"
    assert _load(NATURAL_RECOVERY_COMPARATOR)["canonical_status"] == "FORMAL_CURRENT_COMPARATOR_SOURCE"
    assert _load(NEGATIVE_EXPLANATORY_REVIEW)["canonical_status"] == "FORMAL_CURRENT_AUDIT_SOURCE"
    assert settlement["contract_sha256"] == _sha(CONTRACT)
    assert settlement["canonical_pool_sha256"] == _sha(POOL)
    assert settlement["manual_adjudication_sha256"] == _sha(MANUAL)
    assert settlement["pressure_screening_sha256"] == _sha(SCREENING)
    assert settlement["input_sha256"][SCREENING.relative_to(ROOT).as_posix()] == _sha(SCREENING)
    assert settlement["coverage_matrix_sha256"] == _sha(COVERAGE_MATRIX)
    assert settlement["input_sha256"][COVERAGE_MATRIX.relative_to(ROOT).as_posix()] == _sha(COVERAGE_MATRIX)
    assert settlement["calibration_thresholds_sha256"] == _sha(CALIBRATION_THRESHOLDS)
    assert settlement["input_sha256"][CALIBRATION_THRESHOLDS.relative_to(ROOT).as_posix()] == _sha(CALIBRATION_THRESHOLDS)
    assert settlement["blocking_gap_count"] == 0
    assert settlement["formally_bounded_negative_mechanism_gap_count"] == 14
    assert settlement["record_count"] == len(records) == 184
    assert {row["ruler_id"] for row in records} == included
    assert len({row["task_code"] for row in records}) == 184
    assert all(row["task_code"] == f"PROFILE-M3-{row['ruler_id']}" for row in records)
    assert records == sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"]))
    assert not any(settlement[key] for key in ("formal_rank_write", "profile_total_enabled", "profile_ranking_enabled", "composite_ranking_write", "database_write"))

    forbidden = {"source_axis_grade", "source_axis_position", "source_axis_score", "inherited_grade", "keyword_score", "reform_count_score", "second_item_score"}
    assert not any(isinstance(value, str) and value in forbidden for value in _walk(settlement)), "score/band/count conversion field forbidden"
    parent_ids = []
    for row in records:
        assert row["radar_value"] == row["score_100"] == SCORES[row["axis_grade"]][row["position"]]
        assert row["axis_evidence_level"] in {"E1", "E2", "E3"}
        assert row["output_mode"] in {"BOUNDED_PROFILE", "FULL_GRADE"}
        assert row["score_status"] in {"FINAL", "EVIDENCE_LIMITED"}
        assert row["value_mode"] in {"DUAL_CHANNEL_ADJUDICATED", "RESULT_CONSTRAINED_INFERENCE"}
        assert row["confidence"] == {"E1": "LOW", "E2": "MEDIUM", "E3": "HIGH"}[row["axis_evidence_level"]]
        assert row["axis_relevance_check"] == {
            "second_item_score_used": False, "second_item_band_used": False,
            "final_outcome_backsolve_used": False, "reform_count_used": False,
            "cross_axis_grade_used": False, "result_curve_used_as_constraint": True,
        }
        assert row["calibration"]["name_override_used"] is False
        assert row["calibration"]["second_item_band_conversion_used"] is False
        assert len(row["typical_pattern"]) >= 30 and row["limitations"]
        if not row["parents"]:
            assert row["axis_evidence_level"] == "E1" and row["score_status"] == "EVIDENCE_LIMITED"
            assert row["value_mode"] == "RESULT_CONSTRAINED_INFERENCE"
        for parent in row["parents"]:
            parent_ids.append(parent["parent_id"])
            assert parent["direction"] in {"POSITIVE", "NEGATIVE", "MIXED", "MIXED_POSITIVE", "MIXED_NEGATIVE", "UNRESOLVED_DIRECTION"}
            assert parent["material_intensity"] in {"MI1_CASE", "MI2_LIFECYCLE", "MI3_SUSTAINED_SYSTEMIC", "MI4_CROSS_PHASE_SYSTEMIC"}
            for field in ("constraint_and_task", "available_alternatives", "personal_choice", "tool_fit_and_burden", "delivery_status", "feedback_and_response", "result_boundary"):
                assert str(parent[field]).strip(), f"open M3 lifecycle {parent['parent_id']} {field}"
            assert parent["source_refs"] and parent["diagnostic_mechanisms"]
        if row["axis_grade"] in {"G4", "G5"}:
            assert len(row["major_mechanisms_observed"]) >= 2
            assert row["axis_evidence_level"] == "E3" and row["score_status"] == "FINAL"
            regime = [parent for parent in row["parents"] if parent["parent_type"] in {"REGIME_CHAIN", "COUNTER_REGIME_CHAIN"}]
            candidate_count = len({candidate for parent in regime for candidate in parent.get("candidate_ids", [])})
            assert regime and (len(row["parents"]) >= 2 or candidate_count >= 2)
    assert len(parent_ids) == len(set(parent_ids))
    assert len({row["typical_pattern"] for row in records}) >= 175

    assert audit["schema_version"] == "profile-m3-unit-disposition-audit-v1"
    assert audit["record_count"] == 184 and audit["unresolved_count"] == 0
    assert audit["unit_count"] == len(audit["units"])
    assert set(audit["normative_entries"]) == {"INSTITUTION_REGISTRY", "LOCAL_HISTORY", "LOCAL_HISTORY_DECISION_RECUT", "MANUAL_PRESSURE_EVENT_REVIEW", "RETAINED_INDEPENDENT_M3_PARENT", "RETAINED_MANUAL_PARENT_REVIEW", "FOOD_TREATISE_SOURCE_COVERAGE", "FOOD_TREATISE_BOUND_RECUT", "SECOND_ITEM_NAVIGATION_RECUT", "SECOND_ITEM_A", "SECOND_ITEM_B2", "SECOND_ITEM_C1", "SECOND_ITEM_C2", "SECOND_ITEM_C3", "SECOND_ITEM_C4", "PROFILE_M1", "PROFILE_M2", "PROFILE_C1", "PROFILE_C2", "PROFILE_C3", "PROFILE_C5"}
    allowed = {"SCORING_PARENT", "BACKGROUND_VALIDATION", "AXIS_OUT_WITH_REASON", "UNRESOLVED_EVIDENCE_GAP"}
    assert all(unit["status"] in allowed and unit["reason"].strip() for unit in audit["units"])
    assert len({unit["unit_id"] for unit in audit["units"]}) == audit["unit_count"]
    parent_set = set(parent_ids)
    assert all(unit["scoring_parent_id"] in parent_set for unit in audit["units"] if unit["status"] == "SCORING_PARENT")
    scoring_units = [unit for unit in audit["units"] if unit["status"] == "SCORING_PARENT"]
    assert {unit["scoring_parent_id"] for unit in scoring_units} == parent_set
    assert not any(unit["status"] == "SCORING_PARENT" for unit in audit["units"] if unit["entry"] in {"SECOND_ITEM_C1", "SECOND_ITEM_C2"})
    food = audit["food_treatise_coverage"]
    assert food["entry_status"] == "INDEPENDENT_NORMATIVE_ENTRY_SCREENED"
    assert food["source_count"] == food["fetched_source_count"] == 50
    assert food["mechanical_candidate_count"] == 2144 and food["three_signal_candidate_count"] == 1302

    assert high["schema_version"] == "profile-m3-high-grade-review-v1"
    high_ids = {row["ruler_id"] for row in records if row["axis_grade"] in {"G4", "G5"}}
    assert {row["ruler_id"] for row in high["reviews"]} == high_ids
    assert all(row["independent_constraint_class_count"] >= 2 and row["regime_chain_count"] >= 1 and row["independent_chain_support"] for row in high["reviews"])
    assert all(row["review_outcome"] == "HIGH_GRADE_SUPPORTED" for row in high["reviews"])

    assert review["schema_version"] == "profile-m3-two-pass-full-pool-review-v1"
    assert review["mechanical_screen_count"] == review["semantic_review_count"] == len(review["records"]) == 184
    assert all(row["positive_and_negative_checked"] and row["search_complete"] for row in review["records"])
    assert all(row["lifecycle_closed"] == bool(row["scoring_parent_count"]) for row in review["records"])
    assert review["grade_change_count"] == len(review["grade_changes"])
    by_id = {row["ruler_id"]: row for row in records}
    assert all(change["to"] == f"{by_id[change['ruler_id']]['axis_grade']}-{by_id[change['ruler_id']]['position']}" for change in review["grade_changes"])
    return {"status": "PASS", "record_count": 184, "parent_count": len(parent_ids), "audit_unit_count": audit["unit_count"], "high_grade_count": len(high_ids), "grade_change_count": review["grade_change_count"]}


def verify() -> dict[str, Any]:
    manual = _load(MANUAL)
    if manual.get("canonical_status") == "CALIBRATION_PENDING":
        screening = _load(SCREENING)
        matrix = _load(COVERAGE_MATRIX)
        semantic_review = _load(SEMANTIC_REVIEW)
        comparator = _load(NATURAL_RECOVERY_COMPARATOR)
        negative_review = _load(NEGATIVE_EXPLANATORY_REVIEW)
        retained_manual_review = _load(RETAINED_MANUAL_PARENT_REVIEW)
        records = manual["records"]
        parents = [parent for row in manual["records"] for parent in row["parents"]]
        by_id = {row["ruler_id"]: row for row in records}
        pool = _load(POOL)
        included = {row["ruler_id"] for row in pool["records"] if row["pool_status"] == "INCLUDED"}
        assert len(records) == 184
        assert set(by_id) == included
        assert all(row["axis_grade"] and row["score_100"] is not None for row in records)
        assert all(row["axis_evidence_level"] in {"E1", "E2", "E3"} for row in records)
        assert all(row["value_mode"] in {"DUAL_CHANNEL_ADJUDICATED", "RESULT_CONSTRAINED_INFERENCE"} for row in records)
        assert all(row["formal_status"] == "CALIBRATION_PENDING_PROVISIONAL" for row in records)
        assert all(row["process_channel"]["level"] in {"P0", "P1", "P2", "P3", "P4"} for row in records)
        assert all(row["revealed_capability_channel"]["channel"] == "REVEALED_CAPABILITY_CHANNEL" for row in records)
        assert all(row["revealed_capability_channel"]["natural_recovery_envelope"]["status"] == "COMPARATOR_GROUP_SETTLED_FOR_PROVISIONAL_CALIBRATION" for row in records)
        assert all(row["axis_relevance_check"]["result_curve_used_as_constraint"] for row in records)
        forbidden = ("史料只闭合所载选择及其反面", "本人窗口内的可定位选择")
        assert not any(any(token in str(parent) for token in forbidden) for parent in parents)
        assert not any(
            "/财政民生/01-C1正式结算.json" in ref or "/财政民生/02-C2正式结算.json" in ref
            for parent in parents for ref in parent["source_refs"]
            if parent["parent_type"] == "DECISION_CHAIN" and parent["parent_id"].startswith("M3P-")
            and parent["parent_id"] not in {"M3P-TANG-GAOZONG-CURRENCY-PALACE-REVERSAL"}
        )
        assert all(parent.get("channel") == "PROCESS_CHANNEL" for parent in parents)
        assert all(parent.get("phase_coverage") and parent.get("choice_types") for parent in parents)
        assert all(parent.get("closure_level") and "evidence_gaps" in parent for parent in parents)
        assert manual["removed_synthetic_parent_count"] == 415
        assert manual["retained_or_rebuilt_process_parent_count"] == len(parents) == 204
        assert manual["anchor_semantic_review_count"] == 184
        assert manual["full_pool_semantic_review_pending_count"] == 0
        assert sum(row["score_100"] == 45 for row in records) < 119
        by_name = {row["ruler_name"]: row for row in records}
        assert (by_name["李世民"]["axis_grade"], by_name["李世民"]["position"], by_name["李世民"]["score_100"]) == ("G4", "LOW", 77)
        assert (by_name["李治"]["axis_grade"], by_name["李治"]["position"], by_name["李治"]["score_100"]) == ("G2", "LOW", 38)
        assert (by_name["刘启"]["axis_grade"], by_name["刘启"]["position"], by_name["刘启"]["score_100"]) == ("G4", "LOW", 77)
        assert by_name["李世民"]["process_channel"]["level"] == "P3"
        assert by_name["李世民"]["revealed_capability_channel"]["unexplained_result_residual"]["level"] == "R3"
        assert by_name["李治"]["dual_channel_adjudication"]["result_level"] == "R0"
        assert by_name["李治"]["revealed_capability_channel"]["negative_explanatory_review"]["required"]
        assert by_name["刘启"]["dual_channel_adjudication"]["result_level"] == "R3"
        assert by_name["刘启"]["revealed_capability_channel"]["unexplained_result_residual"]["stability_class"] == "HIGH_LEVEL_MAINTENANCE_UNDER_PRESSURE"
        assert screening["canonical_status"] == "CALIBRATION_PENDING_INPUT"
        assert screening["semantic_review_complete_count"] == 184
        assert screening["semantic_review_pending_count"] == 0
        assert screening["status_counts"].get("SEMANTIC_REVIEW_PENDING", 0) == 0
        scoring_parent_ids = {
            unit["scoring_parent_id"] for row in screening["records"] for unit in row["units"]
            if unit["status"] in {"SCORING_PARENT", "PROCESS_EVIDENCE_ACCEPTED"}
        }
        assert scoring_parent_ids == {parent["parent_id"] for parent in parents}
        assert matrix["canonical_status"] == "CALIBRATION_PENDING_INPUT"
        assert matrix["record_count"] == len(matrix["records"]) == 184
        assert matrix["cell_count_per_ruler"] == 2520
        assert matrix["total_cell_count"] == 463680
        assert matrix["anchor_semantic_review_count"] == 184
        assert matrix["full_pool_semantic_review_pending_count"] == 0
        assert {row["matrix_status"] for row in matrix["records"]} == {"MECHANICAL_AND_SEMANTIC_REVIEW_COMPLETE"}
        allowed_codes = set(matrix["status_code_legend"])
        for row in matrix["records"]:
            assert row["cell_count"] == 2520
            assert len(row["coverage"]) == 5
            for phase in row["coverage"]:
                assert len(phase["mechanisms"]) == 8
                for mechanism in phase["mechanisms"]:
                    assert len(mechanism["choices"]) == 7
                    assert all(len(choice["source_status_vector"]) == 9 for choice in mechanism["choices"])
                    assert all(set(choice["source_status_vector"]) <= allowed_codes for choice in mechanism["choices"])
        project = yaml.safe_load(_read(PROJECT).decode("utf-8"))["profile_assessment"]
        assert project["status"] == "seven_axes_formally_settled_m3_recalibration_pending"
        assert "M3" in project["pending_axes"] and "M3" not in project["settled_axes"]
        assert project["pending_axes"]["M3"]["coverage_matrix_json"] == COVERAGE_MATRIX.relative_to(ROOT).as_posix()
        assert project["pending_axes"]["M3"]["semantic_review_decisions_json"] == SEMANTIC_REVIEW.relative_to(ROOT).as_posix()
        assert project["pending_axes"]["M3"]["natural_recovery_comparator_json"] == NATURAL_RECOVERY_COMPARATOR.relative_to(ROOT).as_posix()
        assert project["pending_axes"]["M3"]["negative_explanatory_review_json"] == NEGATIVE_EXPLANATORY_REVIEW.relative_to(ROOT).as_posix()
        assert project["pending_axes"]["M3"]["retained_manual_parent_review_json"] == RETAINED_MANUAL_PARENT_REVIEW.relative_to(ROOT).as_posix()
        assert semantic_review["record_count"] == len(semantic_review["records"]) == 316
        assert semantic_review["ruler_count"] == 184
        assert semantic_review["disposition_counts"] == {
            "PROCESS_EVIDENCE_ACCEPTED": 260,
            "AXIS_OUT_WITH_REASON": 43,
            "RESULT_VALIDATION_ONLY": 13,
        }
        assert not any(row["disposition"] == "SEMANTIC_REVIEW_PENDING" for row in semantic_review["records"])
        assert comparator["canonical_status"] == "CALIBRATION_PENDING_COMPARATOR_SOURCE"
        assert comparator["record_count"] == len(comparator["records"]) == 184
        assert comparator["group_count"] == len(comparator["groups"]) == 21
        assert comparator["residual_counts"] == {
            "ABOVE_NATURAL_RECOVERY_ENVELOPE": 47,
            "WITHIN_NATURAL_RECOVERY_ENVELOPE": 70,
            "BELOW_COMPARATOR_ENVELOPE": 57,
            "SOURCE_UNAVAILABLE_BOUNDED": 10,
        }
        assert comparator["negative_explanatory_unresolved_count"] == 14
        assert {row["ruler_id"] for row in comparator["records"]} == set(by_id)
        assert all(row["source_unavailability_bias"] for row in comparator["records"] if row["residual_class"] == "SOURCE_UNAVAILABLE_BOUNDED")
        assert not any("PENDING_SEMANTIC_DECOMPOSITION" in str(row["revealed_capability_channel"]["negative_explanatory_review"]) for row in records)
        assert negative_review["trigger_count"] == len(negative_review["records"]) == 59
        assert negative_review["reverse_search_complete_count"] == 59
        assert negative_review["reverse_search_pending_count"] == 0
        assert negative_review["outcome_counts"] == {
            "PROCESS_NEGATIVE_CHAIN_LOCATED": 21,
            "CURRENT_C4_ATTRIBUTION_LOCATED_PROCESS_CHAIN_STILL_LIMITED": 24,
            "REVEALED_NEGATIVE_CAPABILITY_WITH_MECHANISM_GAP": 14,
        }
        assert all(row["reverse_search"]["status"] == "REVERSE_SEARCH_COMPLETE" for row in negative_review["records"])
        assert retained_manual_review["candidate_count"] == 11
        assert retained_manual_review["regime_chain_count"] == 5
        assert retained_manual_review["pending_count"] == 0
        manifest = _load(MANIFEST)
        axis = next(row for row in manifest["axes"] if row["axis_code"] == "M3")
        assert manifest["settled_axis_count"] == 7 and manifest["unsettled_axis_count"] == 1
        assert axis["status"] == "CALIBRATION_PENDING"
        return {
            "status": "CALIBRATION_PENDING", "provisional_value_count": 184,
            "process_parent_count": len(parents),
            "matrix_cell_count": matrix["total_cell_count"],
            "anchor_semantic_review_count": 184,
            "full_pool_semantic_review_pending_count": 0,
            "full_pool_result_review_count": 184,
            "negative_explanatory_gap_count": 14,
        }
    settlement, audit, high, review = (_load(path) for path in (SETTLEMENT, AUDIT, HIGH_REVIEW, FULL_POOL_REVIEW))
    assert _read(MARKDOWN).decode("utf-8") == render_profile_markdown(settlement)
    assert "不进入五项综合总榜" in _read(ACCEPTANCE).decode("utf-8")
    result = verify_payloads(settlement, audit, high, review)
    project = yaml.safe_load(_read(PROJECT).decode("utf-8"))["profile_assessment"]
    assert project["status"] == "eight_axes_formally_settled"
    assert set(project["settled_axes"]) == {"M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5"}
    manifest = _load(MANIFEST)
    assert manifest["settled_axis_count"] == 8 and manifest["unsettled_axis_count"] == 0
    axis = next(row for row in manifest["axes"] if row["axis_code"] == "M3")
    assert (
        axis["json"] == SETTLEMENT.relative_to(MANIFEST.parent).as_posix()
        and axis["json_sha256"] == _sha(SETTLEMENT)
    )
    assert axis["markdown_sha256"] == _sha(MARKDOWN)
    assert set(axis["audit_jsons"]) == {
        path.relative_to(MANIFEST.parent).as_posix()
        for path in (AUDIT, HIGH_REVIEW, FULL_POOL_REVIEW)
    }
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
