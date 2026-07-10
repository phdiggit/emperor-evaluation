from scripts.dev import retrieval_v3_candidate_review_worklist as tool


def test_classify_identity_gate() -> None:
    assert tool.classify_identity_gate({"matching_objects": [], "target_objects": []}) == "identity_missing"
    assert tool.classify_identity_gate({"matching_objects": [{"object_id": 1}], "target_objects": []}) == "identity_pending"
    assert tool.classify_identity_gate(
        {"matching_objects": [{"object_id": 1}], "target_objects": [{"review_status": "accepted"}]}
    ) == "identity_ready"
    assert tool.classify_identity_gate(
        {"matching_objects": [{"object_id": 1}, {"object_id": 2}], "target_objects": []}
    ) == "identity_ambiguous"


def test_build_workitem_keeps_identity_gate_and_patch_defaults() -> None:
    row = {
        "candidate_id": 7,
        "candidate_code": "CLM-X::CANDIDATE::appointment_delegation",
        "claim_id": 8,
        "target_code": "TGT-X",
        "emperor_name": "李世民",
        "source_pack_code": "SPK-X",
        "object_name": "魏徵",
        "claim_direction": "positive",
        "claim_summary": "命魏徵谏诤。",
        "candidate_reason": "命",
        "candidate_payload": {"formal_binding_allowed": False},
        "source_passages": [{"passage_code": "P-X", "raw_text": "命魏徵谏诤。"}],
        "matching_objects": [{"object_id": 1}],
        "target_objects": [],
    }
    item = tool.build_workitem(row)
    assert item["identity_gate"] == "identity_pending"
    assert item["required_patch"]["direction"] == "positive"
    assert item["source_passages"][0]["passage_code"] == "P-X"
    assert item["required_patch"]["scoring_candidate"] is False
    assert item["required_patch"]["usable_for_scoring_cluster"] is False
