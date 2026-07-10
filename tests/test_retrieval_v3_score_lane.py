from scripts.dev import retrieval_v3_score_lane as tool


def test_direct_formal_binding_uses_normal_lane() -> None:
    decision = tool.classify_score_lane(
        {"rule_code": "appointment_delegation", "binding_usable_for_scoring_cluster": True, "identity_ready": True}
    )

    assert decision.lane == "normal_direct"
    assert decision.allowed is True


def test_candidate_is_an_exception_not_a_direct_lane_requirement() -> None:
    decision = tool.classify_score_lane(
        {
            "rule_code": "appointment_delegation",
            "binding_usable_for_scoring_cluster": True,
            "identity_ready": True,
            "candidate_id": 1,
            "candidate_payload": {"scoring_candidate": False},
        }
    )

    assert decision.lane == "exception_blocked"
    assert decision.reason == "candidate_not_scoring"


def test_identity_anchor_is_required_before_any_score_lane() -> None:
    decision = tool.classify_score_lane(
        {"rule_code": "appointment_delegation", "binding_usable_for_scoring_cluster": True, "identity_ready": False}
    )

    assert decision.allowed is False
    assert decision.reason == "identity_not_ready"


def test_object_identity_fields_are_a_score_lane_gate_when_present() -> None:
    decision = tool.classify_score_lane(
        {"rule_code": "appointment_delegation", "binding_usable_for_scoring_cluster": True, "object_id": 7, "target_object_id": None}
    )

    assert decision.allowed is False
    assert decision.reason == "identity_not_ready"
