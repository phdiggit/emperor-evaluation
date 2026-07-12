from scripts.dev import retrieval_v3_needs_context_worklist as tool


def row(*, facts=None, identity_gate="identity_pending", passages=None):
    return {
        "candidate_id": 7,
        "candidate_code": "CLM-X::CANDIDATE::appointment_delegation",
        "claim_id": 8,
        "claim_code": "CLM-X",
        "emperor_name": "李世民",
        "object_name": "魏徵",
        "claim_summary": "命魏徵谏诤。",
        "source_pack_code": "SPK-X",
        "target_code": "TGT-X",
        "source_passages": [{
            "source_document_id": 11,
            "passage_code": "P-X",
            "document_code": "DOC-X",
            "raw_text": "命魏徵谏诤。",
        }] if passages is None else passages,
        "candidate_payload": {
            "candidate_review": {
                "identity_gate": identity_gate,
                "required_facts": facts or {
                    "has_appointment_or_authorization": True,
                    "has_named_actor": True,
                    "has_task_or_responsibility": True,
                    "has_result_or_feedback": False,
                    "has_continuity_or_reuse": False,
                },
            }
        },
    }


def test_classify_context_reasons_tracks_missing_facts_and_identity() -> None:
    reasons = tool.classify_context_reasons(row())
    assert "missing_result" in reasons
    assert "missing_continuity" in reasons
    assert "identity_blocked" in reasons


def test_rank_context_passages_excludes_current_and_prefers_object_match() -> None:
    item = row()
    passages = [
        {"passage_code": "P-X", "raw_text": "命魏徵谏诤。"},
        {"passage_code": "P-Y", "raw_text": "太宗再任魏徵，诏劳其谏诤，政事皆听。"},
        {"passage_code": "P-Z", "raw_text": "无关人物任将军。"},
    ]
    ranked = tool.rank_context_passages(passages, item)
    assert [item["passage_code"] for item in ranked] == ["P-Y", "P-Z"]
    assert "object_name" in ranked[0]["context_match_reasons"]


def test_build_workitem_is_v3_only_and_records_fallback() -> None:
    item = row(passages=[])
    built = tool.build_workitem(item, {})
    assert "source_missing" in built["context_reasons"]
    assert "identity_blocked" in built["context_reasons"]
    assert built["context_passages"] == []
    assert built["context_search_plan"]["scope"] == "retrieval_v3_same_source_document"
    assert built["context_search_plan"]["legacy_data_reads"] is False


def test_identity_only_context_routes_to_identity_resolution_and_promotion() -> None:
    facts = {
        "has_appointment_or_authorization": True,
        "has_named_actor": True,
        "has_task_or_responsibility": True,
        "has_result_or_feedback": True,
        "has_continuity_or_reuse": False,
    }
    built = tool.build_workitem(row(facts=facts, passages=[]), {})
    assert built["material_protocol_satisfied"] is True
    assert built["next_action"] == "identity_resolution_only"
    patch = tool.identity_resolution_patch(built)
    assert patch["review_verdict"] == "accepted_candidate"
    assert patch["scoring_candidate"] is True


def test_identity_only_items_do_not_count_as_second_review(tmp_path) -> None:
    facts = {
        "has_appointment_or_authorization": True,
        "has_named_actor": True,
        "has_task_or_responsibility": True,
        "has_result_or_feedback": True,
        "has_continuity_or_reuse": False,
    }
    workitem = tool.build_workitem(row(facts=facts, passages=[]), {})
    summary = tool.write_outputs([workitem], tmp_path)
    assert summary["next_action_counts"] == {"identity_resolution_only": 1}
    assert summary["second_review_required"] == 0
