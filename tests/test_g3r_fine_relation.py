from __future__ import annotations

from copy import deepcopy

import pytest

from emperor_v4.evaluation.relation_fine_review import (
    FINE_RELATION_GAP_SCHEMA_VERSION,
    FINE_RELATION_POLICY_VERSION,
    FINE_RELATION_REVIEW_SCHEMA_VERSION,
    apply_fine_relation_gap_review,
    build_fine_relation_gap_worklist,
    build_fine_relation_worklist,
    materialize_fine_relation_proposals,
    validate_fine_relation_gap_response,
    validate_fine_relation_response,
)


def _endpoint_inputs() -> tuple[dict, dict]:
    endpoint_worklist = {
        "task_code": "G3R-ENDPOINT-TEST",
        "worklist_sha256": "a" * 64,
        "tasks": [
            {
                "candidate_code": "RBC-1",
                "dataset_code": "I",
                "left": {
                    "episode_ref": "EP-1",
                    "source_passages": [
                        {"source_passage_ref": "SP-1", "raw_text": "前件"}
                    ],
                    "assertions": [
                        {
                            "assertion_ref": "A-1",
                            "source_passage_ref": "SP-1",
                        }
                    ],
                },
                "right": {
                    "episode_ref": "EP-2",
                    "source_passages": [
                        {"source_passage_ref": "SP-2", "raw_text": "后件"}
                    ],
                    "assertions": [
                        {
                            "assertion_ref": "A-2",
                            "source_passage_ref": "SP-2",
                        }
                    ],
                },
            },
            {
                "candidate_code": "RBC-2",
                "dataset_code": "I",
                "left": {
                    "episode_ref": "EP-2",
                    "source_passages": [
                        {"source_passage_ref": "SP-2", "raw_text": "前件"}
                    ],
                    "assertions": [
                        {
                            "assertion_ref": "A-2",
                            "source_passage_ref": "SP-2",
                        }
                    ],
                },
                "right": {
                    "episode_ref": "EP-3",
                    "source_passages": [
                        {"source_passage_ref": "SP-3", "raw_text": "后件"}
                    ],
                    "assertions": [
                        {
                            "assertion_ref": "A-3",
                            "source_passage_ref": "SP-3",
                        }
                    ],
                },
            },
        ],
    }
    endpoint_final = {
        "status": "endpoint_agreement_gate_passed_after_adjudication",
        "agreement_gate_passed": True,
        "source_task_code": "G3R-ENDPOINT-TEST",
        "final_proposals": [
            {
                "candidate_code": "RBC-1",
                "proposed_disposition": "proposed_direct_relation",
                "coarse_type": "authority_change",
            },
            {
                "candidate_code": "RBC-2",
                "proposed_disposition": "proposed_distinct_unrelated",
                "coarse_type": None,
            },
        ],
        "proposal_counts": {
            "proposed_direct_relation": 1,
            "proposed_distinct_unrelated": 1,
        },
        "gold_accessed": False,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "database_write_count": 0,
    }
    return endpoint_worklist, endpoint_final


def _response(worklist: dict, *, unresolved: bool = False) -> dict:
    task = worklist["tasks"][0]
    row = {
        "candidate_code": task["candidate_code"],
        "decision": "unresolved" if unresolved else "proposed_relation",
        "from_episode_ref": None if unresolved else "EP-1",
        "to_episode_ref": None if unresolved else "EP-2",
        "relation_type": None if unresolved else "renews_authority",
        "evidence_assertion_refs": ["A-1", "A-2"],
        "confidence": None if unresolved else 0.9,
        "reason": "证据支持续权。" if not unresolved else "证据不能唯一确定细类型。",
    }
    return {
        "status": "fine_relation_reviews_complete",
        "task_code": worklist["task_code"],
        "worklist_sha256": worklist["worklist_sha256"],
        "fine_relation_policy_version": FINE_RELATION_POLICY_VERSION,
        "output_schema_version": FINE_RELATION_REVIEW_SCHEMA_VERSION,
        "reviewer": "fine-reviewer",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_relation_review_accessed": False,
        "formal_acceptance_performed": False,
        "database_write_count": 0,
        "results": [row],
    }


def test_fine_worklist_selects_only_direct_endpoint_proposals() -> None:
    endpoint_worklist, endpoint_final = _endpoint_inputs()

    worklist = build_fine_relation_worklist(endpoint_worklist, endpoint_final)

    assert worklist["candidate_count"] == 1
    assert worklist["tasks"][0]["candidate_code"] == "RBC-1"
    assert worklist["tasks"][0]["allowed_relation_types"] == [
        "promotion_after",
        "renews_authority",
        "revokes",
    ]
    assert worklist["formal_relation_count"] == 0
    assert worklist["database_write_count"] == 0


def test_fine_worklist_rejects_unpassed_or_incomplete_endpoint_result() -> None:
    endpoint_worklist, endpoint_final = _endpoint_inputs()
    failed = deepcopy(endpoint_final)
    failed["agreement_gate_passed"] = False
    with pytest.raises(ValueError, match="未通过 endpoint Gate"):
        build_fine_relation_worklist(endpoint_worklist, failed)

    incomplete = deepcopy(endpoint_final)
    incomplete["final_proposals"].pop()
    with pytest.raises(ValueError, match="完整且唯一覆盖"):
        build_fine_relation_worklist(endpoint_worklist, incomplete)


def test_fine_response_enforces_coarse_type_direction_and_lineage() -> None:
    endpoint_worklist, endpoint_final = _endpoint_inputs()
    worklist = build_fine_relation_worklist(endpoint_worklist, endpoint_final)
    valid = _response(worklist)
    assert len(validate_fine_relation_response(worklist, valid)) == 1

    wrong_type = deepcopy(valid)
    wrong_type["results"][0]["relation_type"] = "causal_followup"
    with pytest.raises(ValueError, match="不兼容"):
        validate_fine_relation_response(worklist, wrong_type)

    wrong_evidence = deepcopy(valid)
    wrong_evidence["results"][0]["evidence_assertion_refs"] = ["A-1"]
    with pytest.raises(ValueError, match="覆盖两端"):
        validate_fine_relation_response(worklist, wrong_evidence)


def test_materialized_fine_relation_is_versioned_proposal_only() -> None:
    endpoint_worklist, endpoint_final = _endpoint_inputs()
    worklist = build_fine_relation_worklist(endpoint_worklist, endpoint_final)

    report = materialize_fine_relation_proposals(worklist, _response(worklist))

    assert report["fine_relation_graph_gate_passed"] is True
    assert report["proposed_relation_count"] == 1
    assert report["formal_relation_count"] == 0
    relation = report["relation_proposals"][0]
    assert relation["from_episode_version_ref"] == "EP-1@v1"
    assert relation["relation_status"] == "proposed"
    assert relation["semantic_version"] == relation["evidence_version"] == 1
    assert {link["evidence_status"] for link in relation["evidence_links"]} == {
        "draft"
    }


def test_unresolved_fine_type_fails_closed_without_relation_proposal() -> None:
    endpoint_worklist, endpoint_final = _endpoint_inputs()
    worklist = build_fine_relation_worklist(endpoint_worklist, endpoint_final)

    report = materialize_fine_relation_proposals(
        worklist, _response(worklist, unresolved=True)
    )

    assert report["status"] == "fine_relation_graph_gate_failed_closed"
    assert report["unresolved_count"] == 1
    assert report["proposed_relation_count"] == 0
    assert report["graph_invariants_passed"] is True


def _gap_response(gap_worklist: dict, *, sufficient: bool) -> dict:
    task = gap_worklist["tasks"][0]
    return {
        "status": "fine_relation_gap_reviews_complete",
        "task_code": gap_worklist["task_code"],
        "worklist_sha256": gap_worklist["worklist_sha256"],
        "fine_relation_policy_version": FINE_RELATION_POLICY_VERSION,
        "output_schema_version": FINE_RELATION_GAP_SCHEMA_VERSION,
        "reviewer": "gap-reviewer",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_relation_review_accessed": False,
        "formal_acceptance_performed": False,
        "database_write_count": 0,
        "results": [
            {
                "candidate_code": task["candidate_code"],
                "decision": (
                    "evidence_sufficient"
                    if sufficient
                    else "additional_source_required"
                ),
                "from_episode_ref": "EP-1" if sufficient else None,
                "to_episode_ref": "EP-2" if sufficient else None,
                "relation_type": "renews_authority" if sufficient else None,
                "evidence_source_passage_refs": ["SP-1", "SP-2"],
                "confidence": 0.91 if sufficient else None,
                "reason": (
                    "上下文补足了续权链。"
                    if sufficient
                    else "现有上下文仍不足，需要补充史源。"
                ),
            }
        ],
    }


def test_gap_worklist_contains_only_unresolved_and_validates_passage_lineage() -> None:
    endpoint_worklist, endpoint_final = _endpoint_inputs()
    worklist = build_fine_relation_worklist(endpoint_worklist, endpoint_final)
    original = _response(worklist, unresolved=True)

    gap_worklist = build_fine_relation_gap_worklist(worklist, original)
    response = _gap_response(gap_worklist, sufficient=True)

    assert gap_worklist["candidate_count"] == 1
    assert len(validate_fine_relation_gap_response(gap_worklist, response)) == 1
    one_sided = deepcopy(response)
    one_sided["results"][0]["evidence_source_passage_refs"] = ["SP-1"]
    with pytest.raises(ValueError, match="覆盖两端 Passage"):
        validate_fine_relation_gap_response(gap_worklist, one_sided)


def test_gap_review_resolves_only_supported_item_and_remains_proposal_only() -> None:
    endpoint_worklist, endpoint_final = _endpoint_inputs()
    worklist = build_fine_relation_worklist(endpoint_worklist, endpoint_final)
    original = _response(worklist, unresolved=True)
    gap_worklist = build_fine_relation_gap_worklist(worklist, original)

    report = apply_fine_relation_gap_review(
        worklist,
        original,
        gap_worklist,
        _gap_response(gap_worklist, sufficient=True),
    )

    assert report["status"] == "fine_relation_graph_gate_passed_after_gap_review"
    assert report["gap_resolved_count"] == 1
    assert report["additional_source_required_count"] == 0
    assert report["proposed_relation_count"] == 1
    assert report["formal_relation_count"] == 0
    assert report["database_write_count"] == 0
