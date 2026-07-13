from __future__ import annotations

from copy import deepcopy

import pytest

from emperor_v4.evaluation.projection_judgment_shadow import (
    JUDGMENT_SHADOW_POLICY_VERSION,
    JUDGMENT_SHADOW_SCHEMA_VERSION,
    PROJECTION_SHADOW_POLICY_VERSION,
    build_projection_shadow_worklist,
    materialize_judgment_shadow_review,
)


def _unit(code: str, fingerprint: str, readiness: dict[str, str]) -> dict[str, object]:
    return {
        "unit_code": code,
        "rule_code": "appointment_delegation",
        "rule_version": "appointment-delegation-v1-shadow",
        "aggregation_policy_version": "minimum-sufficient-scoring-arc-v1",
        "evaluation_context": "fixture-context",
        "semantic_fingerprint": fingerprint,
        "semantic_version": 1,
        "evidence_version": 1,
        "members": [
            {"member_ref": f"EP-{code}@v1", "member_type": "episode", "member_role": "delegation"}
        ],
        "aggregation_reason": "fixture",
        "status": "draft",
        "lineage": {"component_code": f"COMP-{code}"},
        "provenance": {"policy_version": "fixture"},
        "ruler_ref": "皇帝甲",
        "person_ref": f"PER-{code}",
        "decision_arc_family": "appointment_feedback_correction",
        "included_link_refs": [f"SRP-{code}"],
        "scoring_arc_only_refs": [],
        "evidence_assertion_refs": [f"AST-{code}-1", f"AST-{code}-2"],
        "question_readiness": readiness,
    }


def _rule_evidence_final() -> dict[str, object]:
    ready = {
        "delegation_quality": "ready",
        "supervision_quality": "ready",
        "correction_timeliness": "ready",
        "net_effect": "ready",
    }
    gap = dict(ready, net_effect="evidence_gap")
    return {
        "status": "rule_evidence_unit_shadow_ready",
        "task_code": "G3C-FIXTURE",
        "draft_unit_count": 2,
        "unresolved_component_count": 0,
        "duplicate_consumption_episode_refs": [],
        "shadow_gate_passed": True,
        "formal_acceptance_performed": False,
        "formal_rule_evidence_unit_count": 0,
        "formal_projection_count": 0,
        "judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
        "rule_evidence_unit_drafts": [
            _unit("READY", "a" * 64, ready),
            _unit("GAP", "b" * 64, gap),
        ],
    }


def _observation(value: str, reason: str, evidence: list[str]) -> dict[str, object]:
    return {"value": value, "reason": reason, "evidence_assertion_refs": evidence}


def _response(worklist: dict[str, object]) -> dict[str, object]:
    by_input = {row["input_ref"]: row for row in worklist["projections"]}
    ready = by_input["READY"]
    gap = by_input["GAP"]
    return {
        "status": "judgment_shadow_reviews_complete",
        "task_code": worklist["task_code"],
        "worklist_sha256": worklist["worklist_sha256"],
        "projection_shadow_policy_version": PROJECTION_SHADOW_POLICY_VERSION,
        "judgment_shadow_policy_version": JUDGMENT_SHADOW_POLICY_VERSION,
        "output_schema_version": JUDGMENT_SHADOW_SCHEMA_VERSION,
        "reviewer": "fixture-reviewer",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_judgment_accessed": False,
        "formal_acceptance_performed": False,
        "scoring_performed": False,
        "database_write_count": 0,
        "results": [
            {
                "projection_code": ready["projection_code"],
                "review_disposition": "judgment_shadow_ready",
                "shadow_direction": "mixed",
                "review_reason": "正负信号并存且四项 readiness 完整。",
                "observations": {
                    "person_task_fit": _observation("positive_signal", "初始适配有支持。", ["AST-READY-1"]),
                    "authority_clarity": _observation("positive_signal", "职责明确。", ["AST-READY-1"]),
                    "feedback_handling": _observation("negative_signal", "反馈处理迟滞。", ["AST-READY-2"]),
                    "attributable_outcome": _observation("mixed_signal", "结果正负并存。", ["AST-READY-2"]),
                },
            },
            {
                "projection_code": gap["projection_code"],
                "review_disposition": "blocked_evidence",
                "shadow_direction": None,
                "review_reason": "净效果证据不足，不生成方向。",
                "observations": {
                    "person_task_fit": _observation("negative_signal", "适配存在负向信号。", ["AST-GAP-1"]),
                    "authority_clarity": _observation("positive_signal", "职责边界可识别。", ["AST-GAP-1"]),
                    "feedback_handling": _observation("positive_signal", "存在纠正动作。", ["AST-GAP-2"]),
                    "attributable_outcome": _observation("evidence_gap", "缺少净效果证据。", []),
                },
            },
        ],
    }


def test_projection_shadow_is_neutral_draft_and_deduplicated() -> None:
    worklist = build_projection_shadow_worklist(_rule_evidence_final())

    assert worklist["projection_count"] == 2
    assert len({row["projection_code"] for row in worklist["projections"]}) == 2
    assert {row["projection_status"] for row in worklist["projections"]} == {"draft"}
    assert {row["applicability_status"] for row in worklist["projections"]} == {"applicable"}
    assert worklist["formal_projection_count"] == 0
    assert worklist["formal_judgment_count"] == 0
    assert worklist["score_count"] == 0


def test_judgment_shadow_keeps_gap_case_blocked_and_materializes_ready_case_only() -> None:
    worklist = build_projection_shadow_worklist(_rule_evidence_final())

    result = materialize_judgment_shadow_review(worklist, _response(worklist))

    assert result["status"] == "judgment_shadow_readiness_passed"
    assert result["judgment_shadow_candidate_count"] == 1
    assert result["blocked_evidence_count"] == 1
    assert result["judgment_shadow_candidates"][0]["shadow_direction"] == "mixed"
    assert result["blocked_reviews"][0]["shadow_direction"] is None
    assert result["formal_projection_count"] == 0
    assert result["formal_judgment_count"] == 0
    assert result["score_count"] == 0
    assert result["database_write_count"] == 0


def test_judgment_shadow_rejects_direction_when_source_readiness_has_gap() -> None:
    worklist = build_projection_shadow_worklist(_rule_evidence_final())
    response = _response(worklist)
    gap = next(row for row in response["results"] if row["review_disposition"] == "blocked_evidence")
    gap["review_disposition"] = "judgment_shadow_ready"
    gap["shadow_direction"] = "mixed"

    with pytest.raises(ValueError, match="evidence_gap"):
        materialize_judgment_shadow_review(worklist, response)


def test_judgment_shadow_rejects_signal_without_assertion_support() -> None:
    worklist = build_projection_shadow_worklist(_rule_evidence_final())
    response = deepcopy(_response(worklist))
    response["results"][0]["observations"]["person_task_fit"]["evidence_assertion_refs"] = []

    with pytest.raises(ValueError, match="信号必须有 Assertion 支持"):
        materialize_judgment_shadow_review(worklist, response)
