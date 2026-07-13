from __future__ import annotations

from copy import deepcopy

import pytest

from emperor_v4.contracts.source import text_content_hash
from emperor_v4.evaluation.source_gap_input_gate import (
    INPUT_GATE_POLICY_VERSION,
    INPUT_GATE_SCHEMA_VERSION,
    build_source_gap_input_gate_worklist,
    materialize_source_gap_input_gate,
)


def _upstream(candidate_kind: str = "source_passage_candidate") -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    request = {
        "gap_code": "JSG-1",
        "input_ref": "RUE-1",
        "ruler_ref": "皇帝甲",
        "person_ref": "PER-1",
        "decision_arc_family": "authority_trajectory",
        "current_episode_refs": ["EP-1@v1"],
        "open_observation_dimensions": ["attributable_outcome"],
        "open_readiness_questions": ["net_effect"],
    }
    inventory = {
        "gap_code": "JSG-1",
        "resolution_kind": candidate_kind,
        "candidate_episode_refs": ["EP-2@v1"] if candidate_kind == "existing_episode_candidate" else [],
        "existing_assertion_refs": ["AST-2"] if candidate_kind == "existing_episode_candidate" else [],
        "source_passage_refs": ["SP-2"],
        "proposed_assertion_summary": "皇帝甲评价某人前期有功。" if candidate_kind == "source_passage_candidate" else None,
        "follow_up_gate": "assertion_boundary_review" if candidate_kind == "source_passage_candidate" else "episode_arc_review",
        "reason": "fixture inventory",
    }
    worklist = {"task_code": "G3E-FIXTURE", "gap_requests": [request]}
    response = {"task_code": "G3E-FIXTURE", "results": [inventory]}
    final = {
        "status": "source_gap_inventory_complete_pending_input_gates",
        "task_code": "G3E-FIXTURE",
        "all_gap_requests_covered": True,
        "readiness_rerun_authorized": False,
        "formal_acceptance_performed": False,
        "formal_assertion_count": 0,
        "formal_episode_count": 0,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }
    return worklist, response, final


def _passage() -> dict[str, object]:
    raw = "皇帝甲称某人前期有功，因而加以褒奖。"
    return {
        "passage_cache_id": "SP-2",
        "document_cache_id": "DOC-1",
        "locator": "卷一:10-29",
        "raw_text": raw,
        "context_before": "",
        "context_after": "",
        "content_hash": text_content_hash(raw),
        "selection_reason": ["targeted_source_gap"],
        "contract_version": "source-cache-contract-v2",
        "content_version": "sha256:doc-v1",
        "section_id": "卷一",
        "section_heading": "某人传",
        "span_start": 10,
        "span_end": 10 + len(raw),
        "passage_kind": "atomic",
        "linked_passages": [],
        "overlap_group": None,
        "window_policy_version": "fixture-v1",
    }


def _assertion() -> dict[str, object]:
    return {
        "assertion_code": "AST-SHADOW-1@SP-2",
        "source_passage_ref": "SP-2",
        "assertion_type": "context_fact",
        "subject": "皇帝甲",
        "predicate": "评价",
        "object": "某人前期有功",
        "time_expression": None,
        "location_expression": None,
        "qualifiers": {
            "candidate_focal_person_refs": ["PER-1"],
            "responsibility_family": "civil_governance",
        },
        "polarity": "asserted",
        "source_attribution": {"document_code": "DOC-1"},
        "candidate_episode_key": None,
        "confidence": 0.98,
        "ambiguity_flags": [],
        "extraction_provenance": {"status": "proposal_only"},
        "passage_support": {
            "support_mode": "single_passage",
            "assertion_semantic_key": "SEM-1",
            "supported_fields": ["identity", "action", "attribution", "outcome"],
            "binding_provenance": {"review": "fixture"},
        },
    }


def _response(worklist: dict[str, object]) -> dict[str, object]:
    return {
        "status": "source_gap_input_gate_reviews_complete",
        "task_code": worklist["task_code"],
        "worklist_sha256": worklist["worklist_sha256"],
        "input_gate_policy_version": INPUT_GATE_POLICY_VERSION,
        "output_schema_version": INPUT_GATE_SCHEMA_VERSION,
        "reviewer": "fixture-reviewer",
        "proposal_only": True,
        "gold_accessed": False,
        "formal_acceptance_performed": False,
        "judgment_performed": False,
        "scoring_performed": False,
        "database_write_count": 0,
        "results": [
            {
                "gap_code": "JSG-1",
                "disposition": "accepted_for_shadow_delta",
                "reason": "原文直接支持前期表现归因。",
                "boundary_disposition": "context_for_rule_evidence_unit",
                "episode_arc_review": None,
                "source_passage_snapshot": _passage(),
                "candidate_source_passage": None,
                "candidate_assertion": _assertion(),
                "proposed_episode_ref": None,
                "member_role": "context",
            }
        ],
    }


def test_input_gate_validates_passage_and_assertion_but_only_authorizes_shadow_delta() -> None:
    worklist = build_source_gap_input_gate_worklist(*_upstream())

    result = materialize_source_gap_input_gate(worklist, _response(worklist))

    assert result["status"] == "source_gap_input_gate_passed_for_shadow_delta"
    assert result["accepted_shadow_delta_count"] == 1
    assert result["context_assertion_candidate_count"] == 1
    assert result["shadow_delta_authorized"] is True
    assert result["readiness_rerun_authorized"] is False
    assert result["formal_assertion_count"] == 0
    assert result["formal_judgment_count"] == 0


def test_input_gate_rejects_source_passage_hash_mismatch() -> None:
    worklist = build_source_gap_input_gate_worklist(*_upstream())
    response = _response(worklist)
    response["results"][0]["source_passage_snapshot"]["content_hash"] = "bad"

    with pytest.raises(ValueError, match="content_hash"):
        materialize_source_gap_input_gate(worklist, response)


def test_input_gate_rejects_assertion_without_proposal_only_provenance() -> None:
    worklist = build_source_gap_input_gate_worklist(*_upstream())
    response = deepcopy(_response(worklist))
    response["results"][0]["candidate_assertion"]["extraction_provenance"] = {}

    with pytest.raises(ValueError, match="proposal_only"):
        materialize_source_gap_input_gate(worklist, response)


def test_existing_episode_candidate_requires_exact_inventory_lineage() -> None:
    worklist = build_source_gap_input_gate_worklist(*_upstream("existing_episode_candidate"))
    response = _response(worklist)
    response["results"][0].update(
        {
            "boundary_disposition": "episode_arc_member",
            "episode_arc_review": {
                "decision": "same_scoring_arc",
                "candidate_episode_ref": "EP-2@v1",
                "evidence_assertion_refs": ["WRONG"],
                "source_passage_refs": ["SP-2"],
            },
            "source_passage_snapshot": None,
            "candidate_assertion": None,
            "member_role": "outcome",
        }
    )

    with pytest.raises(ValueError, match="Episode arc review"):
        materialize_source_gap_input_gate(worklist, response)
