"""Current decision consistency, using synthetic records rather than frozen rulings."""
import pytest

from emperor_v4.evaluation.profile_c3_verifier import verify_resolved_gate_decision


def sample(outcome):
    return {
        "ruler_id": "synthetic-ruler", "ruler_name": "合成对象",
        "axis_grade": "G3", "position": "HIGH",
        "resolved_high_gate_decision": {
            "ruler_id": "synthetic-ruler", "ruler_name": "合成对象",
            "outcome": outcome, "reason": "独立闭环仍不足。",
        },
    }


@pytest.mark.parametrize("outcome", ["UPGRADE_G4_LOW", "RETAIN_G3_LOW", "RETAIN_G2_HIGH"])
def test_rejects_stale_grade_or_position(outcome):
    with pytest.raises(AssertionError, match="stale C3 gate decision"):
        verify_resolved_gate_decision(sample(outcome))


@pytest.mark.parametrize("outcome", ["RETAIN_G3_HIGH", "RETAIN_G3_HIGH_EXCEPTIONAL_MILITARY_CHAIN"])
def test_accepts_matching_decisions_and_qualified_codes(outcome):
    verify_resolved_gate_decision(sample(outcome))


def test_legitimate_grade_change_passes_when_decision_is_synchronized():
    row = sample("UPGRADE_G4_LOW")
    row.update(axis_grade="G4", position="LOW")
    verify_resolved_gate_decision(row)


def test_decision_must_belong_to_the_same_person():
    row = sample("RETAIN_G3_HIGH")
    row["resolved_high_gate_decision"]["ruler_id"] = "another-person"
    with pytest.raises(AssertionError, match="detached"):
        verify_resolved_gate_decision(row)


def test_absent_optional_decision_is_allowed():
    row = sample("RETAIN_G3_HIGH")
    row.pop("resolved_high_gate_decision")
    verify_resolved_gate_decision(row)
