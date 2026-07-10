from pathlib import Path

from scripts.dev import retrieval_v3_contract_reanchor_consumer as tool


def candidate_row(**overrides):
    row = {
        "source_candidate_id": 18,
        "source_candidate_code": "CLM-X::CANDIDATE::appointment_delegation",
        "source_claim_id": 7,
        "source_claim_code": "CLM-X",
        "native_claim_code": "CLM-R3R-X",
        "source_target_object_id": 95,
        "candidate_payload": {
            "formal_binding_allowed": False,
            "candidate_review": {
                "identity_gate": "identity_ready",
                "formal_binding_allowed": False,
                "scoring_candidate": True,
                "usable_for_scoring_cluster": True,
            },
        },
    }
    row.update(overrides)
    return row


def test_candidate_payload_for_reanchor_opens_formal_gate() -> None:
    payload = tool.candidate_payload_for_reanchor(candidate_row(), native_claim_id=33, native_target_object_id=44)

    assert payload["created_from"] == tool.REANCHOR_PROFILE
    assert payload["formal_binding_allowed"] is True
    assert payload["candidate_review"]["formal_binding_allowed"] is True
    assert payload["candidate_review"]["identity_gate"] == "identity_ready"
    assert payload["reanchor"]["native_claim_id"] == 33
    assert payload["reanchor"]["native_target_object_id"] == 44
    assert payload["reanchor"]["legacy_data_migrated"] is False


def test_reanchor_consumer_does_not_connect_nonworkflow_tables() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "target_rule_requirements" not in source
    assert "retrieval_intents" not in source


def test_reanchor_consumer_resolves_accepted_alias_names() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "from retrieval_v2.object_names onm" in source
    assert "lower(onm.name_text) = lower(mc.object_name)" in source
    assert "onm.review_status::text = 'accepted'" in source
