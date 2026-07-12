from pathlib import Path

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


def test_worklist_resolves_claim_object_through_accepted_object_names() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "from retrieval_v3.object_names onm" in source
    assert "lower(onm.name_text) = lower(mc.object_name)" in source
    assert "onm.review_status::text = 'accepted'" in source


def test_review_prompt_does_not_route_qualifying_results_away() -> None:
    prompt = tool.prompt_for_task("CRW-TEST", [])

    assert "具体任务或职责" in prompt
    assert "has_result_or_feedback" in prompt


def test_tolerate_talent_prompt_uses_its_own_protocol() -> None:
    prompt = tool.prompt_for_task("CRW-TEST", [], rule_code="tolerate_talent")
    assert "战役中的杀伤" in prompt
    assert "has_fault_boundary" in prompt
    assert "harmed_talent" in prompt
