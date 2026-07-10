from scripts.dev import retrieval_v3_identity_gate_consumer as tool


def row(**overrides):
    value = {
        "object_id": 10,
        "identity_status": "active",
        "target_object_id": 20,
        "target_object_status": "pending",
    }
    value.update(overrides)
    return value


def test_classify_group_exact_active_pending_is_eligible() -> None:
    decision, ids = tool.classify_group([row()])
    assert decision == "identity_ready_for_accept"
    assert ids == {"object_id": 10, "target_object_id": 20}


def test_classify_group_blocks_missing_and_ambiguous_identity() -> None:
    assert tool.classify_group([{"target_object_id": 20, "target_object_status": "pending"}])[0] == "identity_missing"
    assert tool.classify_group([row(), row(object_id=11)])[0] == "identity_ambiguous"


def test_classify_group_blocks_non_active_object() -> None:
    assert tool.classify_group([row(identity_status="needs_review")])[0] == "object_not_active"
