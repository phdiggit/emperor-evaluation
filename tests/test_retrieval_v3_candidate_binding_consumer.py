from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_candidate_binding_consumer as tool


def candidate_row(**overrides):
    row = {
        "candidate_code": "CRBC-R3R-X",
        "candidate_direction": "positive",
        "claim_direction": "positive",
        "candidate_object_role": "civil_official",
        "candidate_payload": {
            "candidate_review": {
                "direction": "positive",
                "candidate_role": "military_commander",
            }
        },
    }
    row.update(overrides)
    return row


def test_binding_fields_maps_positive_candidate_to_appointment_predicate() -> None:
    fields = tool.binding_fields(candidate_row())

    assert fields == {
        "direction": "positive",
        "object_role": "military_commander",
        "predicate": "appointed_or_delegated_authority",
    }


def test_binding_fields_maps_negative_candidate_to_misappointment_predicate() -> None:
    fields = tool.binding_fields(
        candidate_row(
            candidate_payload={"candidate_review": {"direction": "negative", "candidate_role": "misappointed_actor"}}
        )
    )

    assert fields["direction"] == "negative"
    assert fields["object_role"] == "misappointed_actor"
    assert fields["predicate"] == "misappointed_or_misdelegated_authority"


def test_binding_fields_rejects_non_scoring_direction() -> None:
    with pytest.raises(tool.CandidateBindingConsumerError, match="unsupported"):
        tool.binding_fields(candidate_row(candidate_payload={"candidate_review": {"direction": "neutral"}}))


def test_candidate_binding_consumer_does_not_connect_nonworkflow_tables() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "target_rule_requirements" not in source
    assert "retrieval_intents" not in source


def test_candidate_binding_consumer_merges_material_candidates_into_native_binding_lane() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "MATERIAL_CANDIDATE_PROFILE" in source
    assert "c.routed_by_profile = any(%s)" in source
    assert "matched_object.canonical_name" in source
    assert "rc.contract_code = %s" in source
