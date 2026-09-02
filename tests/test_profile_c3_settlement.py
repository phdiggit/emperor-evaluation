from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.formal_json_store import load_json

from emperor_v4.evaluation.profile_c3_verifier import (
    AUDIT,
    HIGH_REVIEW,
    SETTLEMENT,
    SYSTEMIC_REVIEW,
    verify,
    verify_payloads,
)


def _load(path: Path):
    return load_json(path)


@pytest.fixture()
def payloads():
    return _load(SETTLEMENT), _load(AUDIT), _load(HIGH_REVIEW), _load(SYSTEMIC_REVIEW)


def test_profile_c3_formal_settlement_passes_stable_verifier() -> None:
    result = verify()
    assert result["status"] == "PASS"
    assert result["record_count"] == 184
    assert result["parent_count"] == 195
    assert result["audit_unit_count"] == 2841


def test_profile_c3_rejects_keyword_or_count_adjudicators(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    settlement["records"][0]["keyword_hits"] = ["名臣"]
    with pytest.raises(AssertionError, match="mechanical keyword/count"):
        verify_payloads(settlement, audit, high, systemic)


def test_profile_c3_rejects_parentless_full_or_high_publication(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    record = next(row for row in settlement["records"] if not row["parents"])
    record.update({"score_status": "FINAL", "axis_evidence_level": "E3", "output_mode": "FULL_GRADE"})
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high, systemic)


def test_profile_c3_rejects_template_person_bases(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    for record in settlement["records"]:
        record["typical_pattern"] = "统一模板依据，内容长度足够但没有人物、阶段、任务与反馈差异。"
    with pytest.raises(AssertionError, match="template person bases"):
        verify_payloads(settlement, audit, high, systemic)


def test_profile_c3_rejects_duplicate_typical_pattern_clause(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    record = settlement["records"][0]
    record["typical_pattern"] = "同一句说明；同一句说明。"
    with pytest.raises(AssertionError, match="duplicate typical-pattern clause"):
        verify_payloads(settlement, audit, high, systemic)


def test_profile_c3_rejects_high_grade_template_lifecycle(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    record = next(row for row in settlement["records"] if row["axis_grade"] in {"G4", "G5"})
    for parent in record["parents"]:
        for field in (
            "task_requirement", "candidate_identification", "position_configuration", "actual_authority",
            "delivery", "feedback", "authorization_response",
        ):
            parent[field] = "同一模板"
        parent["lifecycle_narrative"] = "同一模板。"
    with pytest.raises(AssertionError, match="high-grade template lifecycle"):
        verify_payloads(settlement, audit, high, systemic)


def test_profile_c3_rejects_uniform_entry_disposition(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    audit["entry_status_counts"] = {key: {"BACKGROUND_VALIDATION": sum(value.values())} for key, value in audit["entry_status_counts"].items()}
    with pytest.raises(AssertionError, match="uniform entry disposition"):
        verify_payloads(settlement, audit, high, systemic)


def test_profile_c3_rejects_single_giant_chain_as_high_grade(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    record = next(row for row in settlement["records"] if row["axis_grade"] == "G4")
    record["parents"] = record["parents"][:1]
    record["major_task_domains_observed"] = record["major_task_domains_observed"][:1]
    with pytest.raises(AssertionError, match="single giant chain"):
        verify_payloads(settlement, audit, high, systemic)


def test_profile_c3_rejects_grade_direction_contradiction(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    record = next(row for row in settlement["records"] if row["axis_grade"] == "G0" and row["parents"])
    for parent in record["parents"]:
        parent["direction"] = "POSITIVE"
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high, systemic)


@pytest.mark.parametrize("field", ["c5_ethics_leakage", "m4_group_outcome_leakage", "final_outcome_backsolve_used"])
def test_profile_c3_rejects_cross_axis_or_result_leakage(payloads, field: str) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    settlement["records"][0]["axis_relevance_check"][field] = True
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high, systemic)


def test_profile_c3_rejects_unbound_scoring_units(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    unit = next(row for row in audit["units"] if row["status"] == "SCORING_PARENT")
    unit["scoring_parent_id"] = "C3P-MISSING"
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high, systemic)


def test_profile_c3_systemic_review_closes_li_yuan_and_template_gate_defects(payloads) -> None:
    settlement, _, high, systemic = payloads
    by_name = {row["ruler_name"]: row for row in settlement["records"]}
    li_yuan = by_name["李渊"]
    assert (li_yuan["axis_grade"], li_yuan["position"]) == ("G4", "LOW")
    assert {parent["parent_id"] for parent in li_yuan["parents"]} >= {
        "C3P-LIYUAN-LIUWENJING-TURK", "C3P-LIYUAN-LIUWENJING-PURGE"
    }
    assert (by_name["赵恒"]["axis_grade"], by_name["赵恒"]["position"]) == ("G2", "HIGH")
    assert by_name["赵恒"]["parents"] == []
    assert (by_name["刘聪"]["axis_grade"], by_name["刘聪"]["position"]) == ("G2", "HIGH")
    assert high["latent_high_candidate_count"] == systemic["open_latent_high_count"] == 0
    assert systemic["mechanical_screen_count"] == 184


def test_profile_c3_rejects_unreviewed_latent_high(payloads) -> None:
    settlement, audit, high, systemic = copy.deepcopy(payloads)
    record = next(row for row in settlement["records"] if row["ruler_name"] == "赵恒")
    record["latent_high_grade_hypothesis"] = {"axis_grade": "G4", "position": "LOW", "status": "MATERIAL_DENSITY_LIMITED"}
    with pytest.raises(AssertionError, match="person-specific decision"):
        verify_payloads(settlement, audit, high, systemic)
