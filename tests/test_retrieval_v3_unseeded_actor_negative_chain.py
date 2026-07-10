from __future__ import annotations

import json

import pytest

from scripts.dev import retrieval_v3_unseeded_actor_negative_chain_consumer as consumer
from scripts.dev import retrieval_v3_unseeded_actor_negative_chain_tasks as tasks


def actor_row(name: str = "杨宪") -> dict:
    return {
        "name": name,
        "target_emperors": ["朱元璋"],
        "discovery_candidate_code": "UAC-001",
        "discovery_evidence": [],
        "required_chain": {},
    }


def claim_payload() -> dict:
    return {
        "claims": [
            {
                "claim_code": "CLM-001",
                "emperor_name": "朱元璋",
                "object_name": "杨宪",
                "source_slice_refs": ["OSS-001"],
                "fact_payload": {"actor": "杨宪", "object": "汪广洋"},
            }
        ],
        "passages": [{"slice_code": "OSS-001", "quote": "右丞杨宪专决事。"}],
        "_target_emperor_gate": {"rejected_claims": []},
    }


def ready_patch() -> dict:
    return {
        "actor_name": "杨宪",
        "target_emperor": "朱元璋",
        "review_verdict": "negative_chain_ready",
        "has_appointment_or_authorization": True,
        "has_task_or_responsibility": True,
        "has_same_chain_harm_or_failure": True,
        "has_disposition_only": False,
        "appointment_claim_codes": ["CLM-001"],
        "harm_claim_codes": ["CLM-001"],
        "supporting_claim_codes": [],
        "source_slice_refs": ["OSS-001"],
        "recommended_action": "emit_negative_candidate",
        "review_note": "任用职责与任内损害在同一事实链中。",
    }


def test_task_generator_pins_luna_and_file_only_contract(tmp_path) -> None:
    workitems = tasks.build_chain_workitems([actor_row()], claim_payload())
    summary = tasks.write_outputs(workitems, tmp_path, batch_size=4)
    task = json.loads((tmp_path / "codex_tasks.jsonl").read_text(encoding="utf-8"))
    prompt = (tmp_path / "prompts" / f"{task['task_code']}.md").read_text(encoding="utf-8")

    assert summary["model"] == "gpt-5.6-luna"
    assert task["argv"][2] == "gpt-5.6-luna"
    assert "negative_chain_ready" in prompt
    assert "后来获罪、免官、贬谪、赐死本身不能当作损害" in prompt
    assert workitems[0]["allowed_source_slice_refs"] == ["OSS-001"]


def test_consumer_emits_only_file_candidate_for_complete_chain() -> None:
    workitem = tasks.build_chain_workitems([actor_row()], claim_payload())[0]
    reviewed, candidates = consumer.consume([workitem], [ready_patch()])

    assert reviewed[0]["review_verdict"] == "negative_chain_ready"
    assert candidates[0]["direction"] == "negative"
    assert candidates[0]["write_db"] is False
    assert candidates[0]["claim_refinement_required"] is True
    assert candidates[0]["binding_allowed"] is False
    assert candidates[0]["scoring_allowed"] is False


def test_consumer_rejects_incomplete_negative_ready_chain() -> None:
    workitem = tasks.build_chain_workitems([actor_row()], claim_payload())[0]
    patch = ready_patch()
    patch["has_appointment_or_authorization"] = False

    with pytest.raises(consumer.NegativeChainConsumerError, match="complete non-disposition chain"):
        consumer.consume([workitem], [patch])


def test_consumer_allows_discovery_window_as_appointment_support() -> None:
    payload = claim_payload()
    row = actor_row()
    row["discovery_evidence"] = [{"window_hash": "UAW-001", "focus_text": "太祖所任杨宪。"}]
    workitem = tasks.build_chain_workitems([row], payload)[0]
    patch = ready_patch()
    patch["appointment_claim_codes"] = []

    reviewed, candidates = consumer.consume([workitem], [patch])

    assert reviewed[0]["appointment_discovery_window_hashes"] == ["UAW-001"]
    assert candidates[0]["appointment_discovery_window_hashes"] == ["UAW-001"]


def test_identity_mismatch_requires_cross_target_evidence() -> None:
    workitem = tasks.build_chain_workitems([actor_row()], claim_payload())[0]
    patch = ready_patch()
    patch.update(
        {
            "review_verdict": "source_identity_mismatch",
            "recommended_action": "refine_identity_specific_sources",
            "has_appointment_or_authorization": False,
            "has_task_or_responsibility": False,
            "has_same_chain_harm_or_failure": False,
            "appointment_claim_codes": [],
            "harm_claim_codes": [],
            "source_slice_refs": [],
        }
    )

    with pytest.raises(consumer.NegativeChainConsumerError, match="requires cross-target evidence"):
        consumer.consume([workitem], [patch])
