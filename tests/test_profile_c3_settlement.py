from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.profile_c3_verifier import (
    AUDIT,
    HIGH_REVIEW,
    SETTLEMENT,
    verify,
    verify_payloads,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def payloads():
    return _load(SETTLEMENT), _load(AUDIT), _load(HIGH_REVIEW)


def test_profile_c3_formal_settlement_passes_stable_verifier() -> None:
    result = verify()
    assert result == {"status": "PASS", "record_count": 184, "parent_count": 175, "audit_unit_count": 2646}


def test_profile_c3_rejects_keyword_or_count_adjudicators(payloads) -> None:
    settlement, audit, high = copy.deepcopy(payloads)
    settlement["records"][0]["keyword_hits"] = ["名臣"]
    with pytest.raises(AssertionError, match="mechanical keyword/count"):
        verify_payloads(settlement, audit, high)


def test_profile_c3_rejects_parentless_full_or_high_publication(payloads) -> None:
    settlement, audit, high = copy.deepcopy(payloads)
    record = next(row for row in settlement["records"] if not row["parents"])
    record.update({"score_status": "FINAL", "axis_evidence_level": "E3", "output_mode": "FULL_GRADE"})
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high)


def test_profile_c3_rejects_template_person_bases(payloads) -> None:
    settlement, audit, high = copy.deepcopy(payloads)
    for record in settlement["records"]:
        record["typical_pattern"] = "统一模板依据，内容长度足够但没有人物、阶段、任务与反馈差异。"
    with pytest.raises(AssertionError, match="template person bases"):
        verify_payloads(settlement, audit, high)


def test_profile_c3_rejects_uniform_entry_disposition(payloads) -> None:
    settlement, audit, high = copy.deepcopy(payloads)
    audit["entry_status_counts"] = {key: {"BACKGROUND_VALIDATION": sum(value.values())} for key, value in audit["entry_status_counts"].items()}
    with pytest.raises(AssertionError, match="uniform entry disposition"):
        verify_payloads(settlement, audit, high)


def test_profile_c3_rejects_single_giant_chain_as_high_grade(payloads) -> None:
    settlement, audit, high = copy.deepcopy(payloads)
    record = next(row for row in settlement["records"] if row["axis_grade"] == "G4")
    record["parents"] = record["parents"][:1]
    record["major_task_domains_observed"] = record["major_task_domains_observed"][:1]
    with pytest.raises(AssertionError, match="single giant chain"):
        verify_payloads(settlement, audit, high)


def test_profile_c3_rejects_grade_direction_contradiction(payloads) -> None:
    settlement, audit, high = copy.deepcopy(payloads)
    record = next(row for row in settlement["records"] if row["axis_grade"] == "G0" and row["parents"])
    for parent in record["parents"]:
        parent["direction"] = "POSITIVE"
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high)


@pytest.mark.parametrize("field", ["c5_ethics_leakage", "m4_group_outcome_leakage", "final_outcome_backsolve_used"])
def test_profile_c3_rejects_cross_axis_or_result_leakage(payloads, field: str) -> None:
    settlement, audit, high = copy.deepcopy(payloads)
    settlement["records"][0]["axis_relevance_check"][field] = True
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high)


def test_profile_c3_rejects_unbound_scoring_units(payloads) -> None:
    settlement, audit, high = copy.deepcopy(payloads)
    unit = next(row for row in audit["units"] if row["status"] == "SCORING_PARENT")
    unit["scoring_parent_id"] = "C3P-MISSING"
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high)
