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
    assert validated["review_route"] == "identity_gate"
    assert validated["second_review_required"] is False
    assert validated["identity_gate"] == "identity_pending"


def test_review_routes_supporting_only_without_second_review() -> None:
    validated = tool.validate_patch(
        patch_row(
            review_verdict="supporting_only",
            scoring_candidate=False,
            usable_for_scoring_cluster=False,
        )
    )
    assert validated["review_status"] == "needs_review"
    assert validated["review_route"] == "terminal_supporting_only"
    assert validated["second_review_required"] is False


def test_review_routes_needs_context_to_expansion() -> None:
    validated = tool.validate_patch(
        patch_row(
            review_verdict="needs_context",
            scoring_candidate=False,
            usable_for_scoring_cluster=False,
        )
    )
    assert validated["review_route"] == "needs_context_expansion"
    assert validated["second_review_required"] is True


def test_validate_patch_rejects_protocol_violation() -> None:
    with pytest.raises(tool.CandidateReviewConsumerError, match="protocol"):
        tool.validate_patch(patch_row(scoring_candidate=True, usable_for_scoring_cluster=False))


def test_validate_patch_rejects_free_text_role() -> None:
    with pytest.raises(tool.CandidateReviewConsumerError, match="candidate_role"):
        tool.validate_patch(patch_row(candidate_role="任用并授权") )


def test_validate_talent_discovery_uses_rule_specific_protocol() -> None:
    validated = tool.validate_patch(
        {
            "review_code": "CRW-DISC",
            "rule_code": "talent_discovery",
            "review_verdict": "accepted_candidate",
            "review_note": "材料明确显示皇帝接受荐举并召见任用具名人才。",
            "required_facts": {
                "has_named_talent": True,
                "has_discovery_or_recommendation": True,
                "has_entry_into_view_or_appointment": True,
                "has_emperor_attribution": True,
                "has_high_difficulty_background": False,
            },
            "candidate_role": "recommended_talent",
            "direction": "positive",
            "scoring_candidate": True,
            "usable_for_scoring_cluster": True,
            "identity_gate": "identity_ready",
            "evidence_passage_codes": ["PAS-X"],
        }
    )
    assert validated["rule_code"] == "talent_discovery"
    assert validated["review_status"] == "accepted"


def tolerate_patch(*, direction: str, concrete: bool, fault: bool) -> dict:
    return {
        "review_code": "CRW-TOL",
        "rule_code": "tolerate_talent",
        "review_verdict": "accepted_candidate",
        "review_note": "材料明确显示皇帝采纳具名人才进谏并维持表达安全。",
        "required_facts": {
            "has_named_talent": True,
            "has_emperor_handling_action": True,
            "has_talent_or_expression_safety_relevance": True,
            "has_concrete_protection_or_harm": concrete,
            "has_fault_boundary": fault,
        },
        "candidate_role": "remonstrance_actor" if direction == "positive" else "harmed_talent",
        "direction": direction,
        "scoring_candidate": True,
        "usable_for_scoring_cluster": True,
        "identity_gate": "identity_ready",
        "evidence_passage_codes": ["PAS-X"],
    }


def test_tolerate_positive_accepts_advice_without_separate_protection_event() -> None:
    assert tool.validate_patch(tolerate_patch(direction="positive", concrete=False, fault=False))["review_status"] == "accepted"


def test_tolerate_negative_still_requires_concrete_harm_and_fault_boundary() -> None:
    with pytest.raises(tool.CandidateReviewConsumerError, match="protocol"):
        tool.validate_patch(tolerate_patch(direction="negative", concrete=False, fault=True))
