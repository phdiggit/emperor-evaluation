import pytest

from scripts.dev import retrieval_v3_candidate_review_consumer as tool


def patch_row(**overrides):
    row = {
        "review_code": "CRW-X",
        "review_verdict": "accepted_candidate",
        "review_note": "原文明确支持任用、职责和结果反馈。",
        "required_facts": {
            "has_appointment_or_authorization": True,
            "has_named_actor": True,
            "has_task_or_responsibility": True,
            "has_result_or_feedback": True,
            "has_continuity_or_reuse": False,
        },
        "candidate_role": "civil_official",
        "direction": "positive",
        "scoring_candidate": True,
        "usable_for_scoring_cluster": True,
        "identity_gate": "identity_pending",
        "evidence_passage_codes": ["PAS-X"],
    }
    row.update(overrides)
    return row


def test_validate_patch_maps_review_status_and_keeps_gate() -> None:
    validated = tool.validate_patch(patch_row())
    assert validated["review_status"] == "accepted"
    assert validated["identity_gate"] == "identity_pending"


def test_validate_patch_rejects_protocol_violation() -> None:
    with pytest.raises(tool.CandidateReviewConsumerError, match="protocol"):
        tool.validate_patch(patch_row(scoring_candidate=True, usable_for_scoring_cluster=False))


def test_validate_patch_rejects_free_text_role() -> None:
    with pytest.raises(tool.CandidateReviewConsumerError, match="candidate_role"):
        tool.validate_patch(patch_row(candidate_role="任用并授权") )
