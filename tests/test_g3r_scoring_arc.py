from __future__ import annotations

from copy import deepcopy

import pytest

from emperor_v4.evaluation.relation_scoring_arc import (
    SCORING_RELATION_POLICY_VERSION,
    SCORING_RELATION_SCHEMA_VERSION,
    build_scoring_relation_worklist,
    materialize_scoring_relation_slice,
    validate_scoring_relation_response,
)


def _inputs() -> tuple[dict, dict]:
    tasks = []
    proposals = []
    for index, coarse in enumerate(("authority_change", "authority_change"), 1):
        tasks.append(
            {
                "candidate_code": f"RBC-{index}",
                "dataset_code": "I",
                "left": {
                    "episode_ref": f"EP-{index}A",
                    "assertions": [
                        {
                            "assertion_ref": f"A-{index}L",
                            "source_passage_ref": f"SP-{index}L",
                        }
                    ],
                    "source_passages": [
                        {"source_passage_ref": f"SP-{index}L", "raw_text": "前件"}
                    ],
                },
                "right": {
                    "episode_ref": f"EP-{index}B",
                    "assertions": [
                        {
                            "assertion_ref": f"A-{index}R",
                            "source_passage_ref": f"SP-{index}R",
                        }
                    ],
                    "source_passages": [
                        {"source_passage_ref": f"SP-{index}R", "raw_text": "后件"}
                    ],
                },
            }
        )
        proposals.append(
            {
                "candidate_code": f"RBC-{index}",
                "proposed_disposition": "proposed_direct_relation",
                "coarse_type": coarse,
            }
        )
    return (
        {
            "task_code": "G3R-ENDPOINT-TEST",
            "worklist_sha256": "a" * 64,
            "tasks": tasks,
        },
        {
            "status": "endpoint_agreement_gate_passed_after_adjudication",
            "agreement_gate_passed": True,
            "source_task_code": "G3R-ENDPOINT-TEST",
            "final_proposals": proposals,
            "proposal_counts": {"proposed_direct_relation": 2},
            "gold_accessed": False,
            "formal_acceptance_performed": False,
            "formal_relation_count": 0,
            "database_write_count": 0,
        },
    )


def _row(task: dict, *, arc_only: bool) -> dict:
    return {
        "candidate_code": task["candidate_code"],
        "decision": "scoring_arc_only" if arc_only else "proposed_relation",
        "same_scoring_arc": "yes",
        "relation_family": "authority_change",
        "relation_direction": "reduce",
        "scope_match": "whole_person_status",
        "fine_type": None,
        "fine_type_status": "not_required_for_scoring",
        "from_episode_ref": None if arc_only else task["left"]["episode_ref"],
        "to_episode_ref": None if arc_only else task["right"]["episode_ref"],
        "unit_member_roles": ["initial_contraction", "major_contraction"] if arc_only else None,
        "ruler_responsibility": "direct",
        "evidence_directness": "strongly_implied",
        "evidence_assertion_refs": [
            task["left"]["assertions"][0]["assertion_ref"],
            task["right"]["assertions"][0]["assertion_ref"],
        ],
        "confidence": 0.9,
        "reason": "权力总体收缩足以支持评分，不要求精确官名对称。",
    }


def _response(worklist: dict) -> dict:
    return {
        "status": "scoring_relation_reviews_complete",
        "task_code": worklist["task_code"],
        "worklist_sha256": worklist["worklist_sha256"],
        "scoring_relation_policy_version": SCORING_RELATION_POLICY_VERSION,
        "output_schema_version": SCORING_RELATION_SCHEMA_VERSION,
        "reviewer": "scoring-reviewer",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_relation_review_accessed": False,
        "formal_acceptance_performed": False,
        "database_write_count": 0,
        "results": [
            _row(worklist["tasks"][0], arc_only=False),
            _row(worklist["tasks"][1], arc_only=True),
        ],
    }


def test_scoring_worklist_reuses_only_endpoint_direct_candidates() -> None:
    endpoint, final = _inputs()
    worklist = build_scoring_relation_worklist(endpoint, final)

    assert worklist["candidate_count"] == 2
    assert "whole_person_status" in worklist["tasks"][0]["allowed_scope_matches"]
    assert worklist["formal_relation_count"] == 0
    assert worklist["formal_rule_evidence_unit_count"] == 0


def test_optional_fine_type_does_not_block_minimum_sufficient_relation() -> None:
    endpoint, final = _inputs()
    worklist = build_scoring_relation_worklist(endpoint, final)
    rows = validate_scoring_relation_response(worklist, _response(worklist))

    assert rows["RBC-1"]["fine_type"] is None
    assert rows["RBC-1"]["fine_type_status"] == "not_required_for_scoring"


def test_scoring_arc_only_does_not_create_fake_relation() -> None:
    endpoint, final = _inputs()
    worklist = build_scoring_relation_worklist(endpoint, final)

    report = materialize_scoring_relation_slice(worklist, _response(worklist))

    assert report["status"] == "minimum_sufficient_relation_slice_passed"
    assert report["scoring_relation_proposal_count"] == 1
    assert report["scoring_arc_only_count"] == 1
    assert report["unresolved_count"] == 0
    assert report["formal_relation_count"] == 0
    assert report["formal_rule_evidence_unit_count"] == 0
    assert report["database_write_count"] == 0


def test_not_required_fine_type_rejects_hidden_enum_value() -> None:
    endpoint, final = _inputs()
    worklist = build_scoring_relation_worklist(endpoint, final)
    response = _response(worklist)
    response["results"][0]["fine_type"] = "revokes"

    with pytest.raises(ValueError, match="fine_type 必须为 null"):
        validate_scoring_relation_response(worklist, response)


def test_unresolved_scoring_semantics_still_fail_closed() -> None:
    endpoint, final = _inputs()
    worklist = build_scoring_relation_worklist(endpoint, final)
    response = _response(worklist)
    response["results"][0] = {
        **response["results"][0],
        "decision": "unresolved",
        "same_scoring_arc": "uncertain",
        "relation_family": None,
        "relation_direction": None,
        "scope_match": None,
        "fine_type": None,
        "fine_type_status": "unresolved",
        "from_episode_ref": None,
        "to_episode_ref": None,
    }

    report = materialize_scoring_relation_slice(worklist, response)

    assert report["status"] == "minimum_sufficient_relation_slice_failed_closed"
    assert report["unresolved_count"] == 1
