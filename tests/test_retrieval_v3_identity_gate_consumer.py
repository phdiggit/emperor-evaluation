from pathlib import Path

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


def test_identity_ready_still_synchronizes_candidate_gate() -> None:
    decision, _ = tool.classify_group([row(target_object_status="accepted")])
    assert decision == "identity_ready"
    assert tool.syncs_candidate_identity_gate(decision) is True
    assert tool.syncs_candidate_identity_gate("identity_missing") is False


def test_identity_gate_resolves_accepted_alias_names() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "from retrieval_v3.object_names onm" in source
    assert "lower(onm.normalized_name) = lower(mc.object_name)" in source
