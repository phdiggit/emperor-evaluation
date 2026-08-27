from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.profile_m4_settlement import (
    ACCEPTANCE,
    AUDIT,
    CONTRACT,
    FULL_POOL_REVIEW,
    HIGH_REVIEW,
    MANIFEST,
    MANUAL,
    MARKDOWN,
    NORMATIVE_INPUTS,
    POOL,
    PROJECT,
    ROOT,
    SCORES,
    SETTLEMENT,
    _normalized_sha,
)
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


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


def verify_payloads(
    settlement: dict[str, Any],
    audit: dict[str, Any],
    high: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    records = settlement["records"]
    pool = _load(POOL)
    included = {row["ruler_id"] for row in pool["records"] if row["pool_status"] == "INCLUDED"}
    assert settlement["schema_version"] == "profile-m4-formal-settlement-v1"
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["axis_code"] == "M4"
    assert settlement["contract_sha256"] == _sha(CONTRACT)
    assert settlement["canonical_pool_sha256"] == _sha(POOL)
    assert settlement["manual_adjudication_sha256"] == _sha(MANUAL)
    assert settlement["record_count"] == len(records) == 184
    assert {row["ruler_id"] for row in records} == included
    assert len({row["task_code"] for row in records}) == 184
    assert all(row["task_code"] == f"PROFILE-M4-{row['ruler_id']}" for row in records)
    assert records == sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"]))
    assert not any(settlement[key] for key in (
        "formal_rank_write", "profile_total_enabled", "profile_ranking_enabled",
        "composite_ranking_write", "database_write",
    ))
    assert settlement["unresolved_evidence_gap_count"] == 0
    assert settlement["input_sha256"] == {
        path.relative_to(ROOT).as_posix(): _normalized_sha(path)
        for path in NORMATIVE_INPUTS.values()
    }

    forbidden = {
        "source_axis_grade", "source_axis_position", "source_axis_score", "inherited_grade",
        "keyword_score", "group_count_score", "material_count_score", "first_item_b_score",
        "fourth_item_a_score", "second_item_score", "profile_rank",
    }
    assert not any(isinstance(value, str) and value in forbidden for value in _walk(settlement))
    parent_ids = []
    for row in records:
        assert row["radar_value"] == row["score_100"] == SCORES[row["axis_grade"]][row["position"]]
        assert row["axis_evidence_level"] in {"E1", "E2", "E3"}
        assert row["output_mode"] in {"EPISODE_TAG", "BOUNDED_PROFILE", "FULL_GRADE"}
        assert row["score_status"] in {"FINAL", "EVIDENCE_LIMITED"}
        assert row["formal_status"] == "FORMAL_CURRENT"
        assert len(row["parents"]) >= 2
        assert len(row["typical_pattern"]) >= 60
        assert row["limitations"] and row["counterpattern"]
        assert set(row["major_mechanisms_observed"]) == {
            "ALLIANCE_FORMATION", "INTEREST_STATUS_CONFIGURATION", "POLITICAL_CREDIT", "CONFLICT_AND_EXIT",
        }
        assert row["axis_relevance_check"] == {
            "m2_external_alliance_used": False,
            "c3_individual_talent_grade_used": False,
            "c5_ethics_grade_used": False,
            "first_item_b_score_used": False,
            "fourth_item_a_result_backsolve_used": False,
            "second_item_result_used": False,
            "group_count_used": False,
            "material_count_used": False,
        }
        for parent in row["parents"]:
            parent_ids.append(parent["parent_id"])
            assert parent["closure_status"] == "CLOSED"
            assert parent["direction"] in {"POSITIVE", "NEGATIVE", "MIXED", "MIXED_POSITIVE", "MIXED_NEGATIVE"}
            assert parent["material_intensity"] in {"MI1_CASE", "MI2_LIFECYCLE", "MI3_SUSTAINED_SYSTEMIC", "MI4_CROSS_PHASE_SYSTEMIC"}
            assert parent["delivery_status"] in {"ORDER_ONLY", "PARTIAL_DELIVERY", "SUSTAINED_DELIVERY", "RECONFIGURED_AFTER_FAILURE"}
            for field in (
                "actual_power_phase", "coalition_task", "group_structure",
                "interests_and_security_expectations", "personal_choice",
                "status_and_resource_configuration", "political_credit_and_delivery",
                "feedback_and_conflict_handling", "exit_result",
            ):
                assert str(parent[field]).strip(), f"open M4 lifecycle {parent['parent_id']} {field}"
            assert parent["source_refs"]
            assert set(parent["boundary_review"]) == {"m2", "c3", "c5", "result_axes"}
        if row["axis_grade"] in {"G4", "G5"}:
            assert row["axis_evidence_level"] == "E3"
            assert row["output_mode"] == "FULL_GRADE"
            assert row["confidence"] == "HIGH" and row["score_status"] == "FINAL"
    assert len(parent_ids) == len(set(parent_ids))
    assert len({row["typical_pattern"] for row in records}) == 184

    assert audit["schema_version"] == "profile-m4-unit-disposition-audit-v1"
    assert audit["record_count"] == 184 and audit["unresolved_count"] == 0
    assert audit["unit_count"] == len(audit["units"])
    assert set(audit["normative_entries"]) == {*NORMATIVE_INPUTS, "M4_EXPLICIT_ADJUDICATION"}
    allowed = {"SCORING_PARENT", "BACKGROUND_VALIDATION", "AXIS_OUT_WITH_REASON", "UNRESOLVED_EVIDENCE_GAP"}
    assert all(unit["status"] in allowed and unit["reason"].strip() for unit in audit["units"])
    assert len({unit["unit_id"] for unit in audit["units"]}) == audit["unit_count"]
    parent_set = set(parent_ids)
    scoring = [unit for unit in audit["units"] if unit["status"] == "SCORING_PARENT"]
    assert {unit["scoring_parent_id"] for unit in scoring} == parent_set
    assert all(unit["entry"] == "M4_EXPLICIT_ADJUDICATION" for unit in scoring)

    assert high["schema_version"] == "profile-m4-high-grade-alliance-lifecycle-review-v1"
    high_ids = {row["ruler_id"] for row in records if row["axis_grade"] in {"G4", "G5"}}
    assert {row["ruler_id"] for row in high["reviews"]} == high_ids
    assert all(row["lifecycle_count"] >= 2 and row["mechanism_count"] == 4 for row in high["reviews"])
    assert all(row["review_outcome"] == "HIGH_GRADE_SUPPORTED" for row in high["reviews"])

    assert review["schema_version"] == "profile-m4-two-pass-full-pool-review-v1"
    assert review["mechanical_screen_count"] == review["semantic_review_count"] == len(review["records"]) == 184
    assert all(row["positive_and_negative_checked"] and row["full_lifecycle_closed"] and row["all_normative_entries_consumed"] for row in review["records"])
    assert review["grade_change_count"] == len(review["grade_changes"])
    by_id = {row["ruler_id"]: row for row in records}
    assert all(change["to"] == f"{by_id[change['ruler_id']]['axis_grade']}-{by_id[change['ruler_id']]['position']}" for change in review["grade_changes"])
    return {
        "status": "PASS",
        "record_count": len(records),
        "parent_count": len(parent_ids),
        "audit_unit_count": audit["unit_count"],
        "high_grade_count": len(high_ids),
        "grade_change_count": review["grade_change_count"],
    }


def verify() -> dict[str, Any]:
    settlement, audit, high, review = (_load(path) for path in (SETTLEMENT, AUDIT, HIGH_REVIEW, FULL_POOL_REVIEW))
    assert _read(MARKDOWN).decode("utf-8") == render_profile_markdown(settlement)
    assert "不进入五项综合总榜" in _read(ACCEPTANCE).decode("utf-8")
    result = verify_payloads(settlement, audit, high, review)
    project = yaml.safe_load(_read(PROJECT).decode("utf-8"))["profile_assessment"]
    expected_axes = {"M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5"}
    assert project["status"] == "eight_axes_formally_settled"
    assert set(project["settled_axes"]) == expected_axes
    manifest = _load(MANIFEST)
    assert manifest["settled_axis_count"] == 8 and manifest["unsettled_axis_count"] == 0
    assert {axis["axis_code"] for axis in manifest["axes"]} == expected_axes
    axis = next(row for row in manifest["axes"] if row["axis_code"] == "M4")
    assert axis["json"] == SETTLEMENT.name and axis["json_sha256"] == _sha(SETTLEMENT)
    assert axis["markdown_sha256"] == _sha(MARKDOWN)
    assert set(axis["audit_jsons"]) == {AUDIT.name, HIGH_REVIEW.name, FULL_POOL_REVIEW.name}
    assert axis["audit_markdowns"] == [ACCEPTANCE.name]
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
