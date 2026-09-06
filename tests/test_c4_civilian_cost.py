from copy import deepcopy

import pytest

from emperor_v4.evaluation.c4_civilian_cost import VERSION, validate_record


def record(mode="INFERRED", tier=1):
    penalty = 4.5 * tier
    return {
        "destructive_amplification_grade": f"DA{tier}",
        "destructive_amplification_penalty": penalty,
        "positive_score_retained": 8.0,
        "deterioration_penalty": 3.0,
        "score": 5.0 - penalty,
        "raw_score": 5.0 - penalty,
        "active_civilian_cost_review": {
            "version": VERSION, "status": "REVIEWED", "evidence_mode": mode,
            "military_input_double_charge": False,
            "choice_and_civilian_basis": "Synthetic discretionary deployment and household labor displacement.",
            "absorbed_and_excluded_basis": "Military supplies excluded; unrelated drought already consumed by the state axis.",
        },
    }


@pytest.mark.parametrize("mode,tier", [("NONE", 0), ("INFERRED", 1), ("DIRECT", 1), ("DIRECT", 4)])
def test_explicit_modes_and_fixed_mapping(mode, tier):
    row = record(mode, tier)
    before = deepcopy(row)
    validate_record(row)
    assert row == before


@pytest.mark.parametrize("mode,tier", [("INFERRED", 2), ("INFERRED", 0), ("NONE", 1), ("DIRECT", 0)])
def test_inference_cannot_become_high_grade_or_ignore_residual_admission(mode, tier):
    with pytest.raises(ValueError):
        validate_record(record(mode, tier))


def test_objective_military_input_cannot_be_charged_twice():
    row = record()
    row["active_civilian_cost_review"]["military_input_double_charge"] = True
    with pytest.raises(ValueError, match="double charge"):
        validate_record(row)


def test_cost_projection_must_match_adjudication():
    row = record()
    row["score"] += 1
    with pytest.raises(ValueError, match="score mismatch"):
        validate_record(row)
