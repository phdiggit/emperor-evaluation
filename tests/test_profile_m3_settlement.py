from __future__ import annotations

import copy
import json

import pytest

from emperor_v4.evaluation.profile_m3_settlement import AUDIT, FULL_POOL_REVIEW, HIGH_REVIEW, SETTLEMENT
from emperor_v4.evaluation.profile_m3_verifier import verify, verify_payloads


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def payloads():
    return _load(SETTLEMENT), _load(AUDIT), _load(HIGH_REVIEW), _load(FULL_POOL_REVIEW)


def test_profile_m3_formal_settlement_passes_stable_verifier() -> None:
    result = verify()
    assert result == {
        "status": "PASS", "record_count": 184, "parent_count": 348,
        "audit_unit_count": 4307, "high_grade_count": 10, "grade_change_count": 109,
    }


def test_profile_m3_kangxi_closes_two_independent_tool_lifecycles(payloads) -> None:
    settlement, _, high, review = payloads
    record = next(row for row in settlement["records"] if row["ruler_name"] == "玄烨")
    assert (record["axis_grade"], record["position"], record["radar_value"]) == ("G4", "LOW", 77)
    assert record["axis_evidence_level"] == "E3" and record["score_status"] == "FINAL"
    assert {parent["parent_id"] for parent in record["parents"]} == {
        "M3P-KANGXI-FIXED-DING-QUOTA",
        "M3P-KANGXI-RELIEF-WAR-BURDEN",
    }
    assert all(parent["material_intensity"] == "MI3_SUSTAINED_SYSTEMIC" for parent in record["parents"])
    assert any(row["ruler_name"] == "玄烨" for row in high["reviews"])
    change = next(row for row in review["grade_changes"] if row["ruler_name"] == "玄烨")
    assert (change["from"], change["to"]) == ("G3-HIGH", "G4-LOW")


def test_profile_m3_rejects_second_item_score_conversion(payloads) -> None:
    settlement, audit, high, review = copy.deepcopy(payloads)
    settlement["records"][0]["second_item_score"] = 300
    with pytest.raises(AssertionError, match="conversion field"):
        verify_payloads(settlement, audit, high, review)


def test_profile_m3_rejects_open_lifecycle(payloads) -> None:
    settlement, audit, high, review = copy.deepcopy(payloads)
    settlement["records"][0]["parents"][0]["feedback_and_response"] = ""
    with pytest.raises(AssertionError, match="open M3 lifecycle"):
        verify_payloads(settlement, audit, high, review)


def test_profile_m3_rejects_unbound_scoring_unit(payloads) -> None:
    settlement, audit, high, review = copy.deepcopy(payloads)
    unit = next(row for row in audit["units"] if row["status"] == "SCORING_PARENT")
    unit["scoring_parent_id"] = "M3P-MISSING"
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high, review)


def test_profile_m3_rejects_high_grade_without_cross_constraint_retest(payloads) -> None:
    settlement, audit, high, review = copy.deepcopy(payloads)
    record = next(row for row in settlement["records"] if row["axis_grade"] in {"G4", "G5"})
    record["major_mechanisms_observed"] = record["major_mechanisms_observed"][:1]
    with pytest.raises(AssertionError):
        verify_payloads(settlement, audit, high, review)


def test_profile_m3_pending_second_item_objects_stay_evidence_limited(payloads) -> None:
    settlement, _, _, _ = payloads
    parentless = [row for row in settlement["records"] if not row["parents"]]
    assert len(parentless) == 10
    assert all(row["axis_evidence_level"] == "E1" for row in parentless)
    assert all(row["score_status"] == "EVIDENCE_LIMITED" for row in parentless)
