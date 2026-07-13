from __future__ import annotations

from copy import deepcopy

import pytest

from emperor_v4.evaluation.judgment_source_gap import (
    SOURCE_GAP_POLICY_VERSION,
    SOURCE_GAP_SCHEMA_VERSION,
    build_judgment_source_gap_worklist,
    materialize_source_gap_inventory,
)


def _inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    projection = {
        "projection_code": "RPS-1",
        "input_ref": "RUE-1",
        "projection_payload": {
            "ruler_ref": "皇帝甲",
            "person_ref": "PER-1",
            "decision_arc_family": "appointment_to_mandate",
            "members": [
                {"member_ref": "EP-1@v1", "member_type": "episode", "member_role": "initial_appointment"}
            ],
            "evidence_assertion_refs": ["AST-1"],
            "question_readiness": {
                "delegation_quality": "ready",
                "supervision_quality": "ready",
                "correction_timeliness": "not_applicable",
                "net_effect": "evidence_gap",
            },
        },
    }
    worklist = {"task_code": "G3D-FIXTURE", "projections": [projection]}
    response = {
        "task_code": "G3D-FIXTURE",
        "results": [
            {
                "projection_code": "RPS-1",
                "review_disposition": "blocked_evidence",
                "observations": {
                    "person_task_fit": {"value": "positive_signal"},
                    "authority_clarity": {"value": "positive_signal"},
                    "feedback_handling": {"value": "positive_signal"},
                    "attributable_outcome": {"value": "evidence_gap"},
                },
            }
        ],
    }
    final = {
        "status": "judgment_shadow_readiness_passed",
        "task_code": "G3D-FIXTURE",
        "shadow_gate_passed": True,
        "blocked_evidence_count": 1,
        "blocked_rule_boundary_count": 0,
        "blocked_reviews": [
            {"projection_code": "RPS-1", "review_disposition": "blocked_evidence"}
        ],
        "formal_acceptance_performed": False,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }
    return worklist, response, final


def _inventory_response(worklist: dict[str, object]) -> dict[str, object]:
    gap = worklist["gap_requests"][0]
    return {
        "status": "judgment_source_gap_inventory_complete",
        "task_code": worklist["task_code"],
        "worklist_sha256": worklist["worklist_sha256"],
        "source_gap_policy_version": SOURCE_GAP_POLICY_VERSION,
        "output_schema_version": SOURCE_GAP_SCHEMA_VERSION,
        "reviewer": "fixture-reviewer",
        "inventory_only": True,
        "inventory_sources": ["eval/source-v2/input.json"],
        "gold_accessed": False,
        "old_relation_accessed": False,
        "old_judgment_accessed": False,
        "external_fetch_performed": False,
        "formal_acceptance_performed": False,
        "database_write_count": 0,
        "results": [
            {
                "gap_code": gap["gap_code"],
                "resolution_kind": "existing_episode_candidate",
                "addressed_observation_dimensions": ["attributable_outcome"],
                "addressed_readiness_questions": ["net_effect"],
                "candidate_episode_refs": ["EP-2@v1"],
                "existing_assertion_refs": ["AST-2"],
                "source_passage_refs": ["SP-2"],
                "proposed_assertion_summary": None,
                "follow_up_gate": "episode_arc_review",
                "reason": "现有结果 Episode 可定向进入弧审查。",
                "stop_condition": "找到首个直接结果 Episode 后停止。",
            }
        ],
    }


def test_source_gap_worklist_only_contains_blocked_evidence_dimensions() -> None:
    worklist = build_judgment_source_gap_worklist(*_inputs())

    assert worklist["gap_request_count"] == 1
    gap = worklist["gap_requests"][0]
    assert gap["open_observation_dimensions"] == ["attributable_outcome"]
    assert gap["open_readiness_questions"] == ["net_effect"]
    assert worklist["external_fetch_performed"] is False
    assert worklist["formal_assertion_count"] == 0


def test_inventory_candidate_stays_pending_and_does_not_authorize_readiness_rerun() -> None:
    worklist = build_judgment_source_gap_worklist(*_inputs())

    result = materialize_source_gap_inventory(worklist, _inventory_response(worklist))

    assert result["status"] == "source_gap_inventory_complete_pending_input_gates"
    assert result["existing_episode_candidate_count"] == 1
    assert result["pending_episode_arc_review_count"] == 1
    assert result["readiness_rerun_authorized"] is False
    assert result["formal_episode_count"] == 0
    assert result["formal_judgment_count"] == 0
    assert result["score_count"] == 0


def test_inventory_rejects_gold_or_relation_source_paths() -> None:
    worklist = build_judgment_source_gap_worklist(*_inputs())
    response = _inventory_response(worklist)
    response["inventory_sources"] = ["eval/historical_gold_relation_v2.json"]

    with pytest.raises(ValueError, match="禁止范围"):
        materialize_source_gap_inventory(worklist, response)


def test_source_passage_candidate_cannot_claim_existing_assertion() -> None:
    worklist = build_judgment_source_gap_worklist(*_inputs())
    response = deepcopy(_inventory_response(worklist))
    row = response["results"][0]
    row.update(
        {
            "resolution_kind": "source_passage_candidate",
            "candidate_episode_refs": [],
            "follow_up_gate": "assertion_boundary_review",
            "proposed_assertion_summary": "候选结果断言。",
        }
    )

    with pytest.raises(ValueError, match="proposal-only"):
        materialize_source_gap_inventory(worklist, response)
