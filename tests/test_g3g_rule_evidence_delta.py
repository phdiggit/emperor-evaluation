from __future__ import annotations

from copy import deepcopy

import pytest

from emperor_v4.evaluation.rule_evidence_delta import apply_rule_evidence_shadow_delta


def _unit(code: str, gap: bool) -> dict[str, object]:
    members = [
        {"member_ref": f"EP-{code}@v1", "member_type": "episode", "member_role": "initial_appointment"}
    ]
    return {
        "unit_code": code,
        "rule_code": "appointment_delegation",
        "rule_version": "appointment-delegation-v1-shadow",
        "aggregation_policy_version": "minimum-sufficient-scoring-arc-v1",
        "evaluation_context": "fixture-context",
        "semantic_fingerprint": f"fingerprint-{code}",
        "semantic_version": 1,
        "evidence_version": 1,
        "members": members,
        "aggregation_reason": "fixture",
        "status": "draft",
        "lineage": {"component_code": f"COMP-{code}"},
        "provenance": {"policy_version": "fixture"},
        "ruler_ref": "皇帝甲",
        "person_ref": f"PER-{code}",
        "decision_arc_family": "authority_trajectory",
        "included_link_refs": [f"SRP-{code}"],
        "scoring_arc_only_refs": [],
        "evidence_assertion_refs": [f"AST-{code}"],
        "question_readiness": {
            "delegation_quality": "ready",
            "supervision_quality": "ready",
            "correction_timeliness": "ready",
            "net_effect": "evidence_gap" if gap else "ready",
        },
    }


def _inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    base = {
        "status": "rule_evidence_unit_shadow_ready",
        "task_code": "G3C-FIXTURE",
        "shadow_gate_passed": True,
        "formal_acceptance_performed": False,
        "formal_rule_evidence_unit_count": 0,
        "formal_projection_count": 0,
        "judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
        "rule_evidence_unit_drafts": [_unit("RUE-GAP", True), _unit("RUE-UNCHANGED", False)],
    }
    worklist = {
        "task_code": "G3F-FIXTURE",
        "tasks": [
            {
                "gap_code": "JSG-1",
                "input_ref": "RUE-GAP",
                "current_episode_refs": ["EP-RUE-GAP@v1"],
                "open_readiness_questions": ["net_effect"],
            }
        ],
    }
    final = {
        "status": "source_gap_input_gate_passed_for_shadow_delta",
        "task_code": "G3F-FIXTURE",
        "shadow_delta_authorized": True,
        "readiness_rerun_authorized": False,
        "accepted_shadow_delta_count": 1,
        "unresolved_count": 0,
        "rejected_count": 0,
        "formal_acceptance_performed": False,
        "formal_assertion_count": 0,
        "formal_episode_count": 0,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
        "accepted_shadow_deltas": [
            {
                "gap_code": "JSG-1",
                "boundary_disposition": "context_for_rule_evidence_unit",
                "candidate_assertion": {
                    "assertion_code": "AST-CONTEXT",
                    "source_passage_ref": "SP-CONTEXT",
                },
                "member_role": "context",
            }
        ],
    }
    return base, worklist, final


def test_rule_evidence_delta_preserves_unit_identity_and_increments_versions() -> None:
    base, worklist, final = _inputs()
    old_unchanged = deepcopy(base["rule_evidence_unit_drafts"][1])

    result = apply_rule_evidence_shadow_delta(base, worklist, final)

    assert result["status"] == "rule_evidence_shadow_delta_ready_for_projection_rebuild"
    assert result["updated_unit_count"] == 1
    assert result["unchanged_unit_count"] == 1
    assert result["new_context_assertion_count"] == 1
    assert result["remaining_readiness_gap_count"] == 0
    assert result["readiness_rerun_authorized"] is True
    updated = next(row for row in result["rule_evidence_unit_drafts"] if row["unit_code"] == "RUE-GAP")
    assert updated["unit_code"] == "RUE-GAP"
    assert updated["semantic_version"] == 2
    assert updated["evidence_version"] == 2
    assert updated["semantic_fingerprint"] != "fingerprint-RUE-GAP"
    assert updated["question_readiness"]["net_effect"] == "ready"
    unchanged = next(row for row in result["rule_evidence_unit_drafts"] if row["unit_code"] == "RUE-UNCHANGED")
    assert unchanged == old_unchanged


def test_rule_evidence_delta_keeps_all_formal_side_effects_zero() -> None:
    result = apply_rule_evidence_shadow_delta(*_inputs())

    for key in (
        "formal_assertion_count",
        "formal_episode_count",
        "formal_relation_count",
        "formal_rule_evidence_unit_count",
        "formal_projection_count",
        "formal_judgment_count",
        "score_count",
        "database_write_count",
    ):
        assert result[key] == 0
    assert result["formal_acceptance_performed"] is False


def test_rule_evidence_delta_rejects_updating_non_gap_readiness() -> None:
    base, worklist, final = _inputs()
    base["rule_evidence_unit_drafts"][0]["question_readiness"]["net_effect"] = "ready"

    with pytest.raises(ValueError, match="非 gap readiness"):
        apply_rule_evidence_shadow_delta(base, worklist, final)


def test_rule_evidence_delta_rejects_two_deltas_for_same_unit() -> None:
    base, worklist, final = _inputs()
    second_task = deepcopy(worklist["tasks"][0])
    second_task["gap_code"] = "JSG-2"
    worklist["tasks"].append(second_task)
    second_delta = deepcopy(final["accepted_shadow_deltas"][0])
    second_delta["gap_code"] = "JSG-2"
    second_delta["candidate_assertion"] = {
        "assertion_code": "AST-CONTEXT-2",
        "source_passage_ref": "SP-CONTEXT-2",
    }
    final["accepted_shadow_deltas"].append(second_delta)
    final["accepted_shadow_delta_count"] = 2

    with pytest.raises(ValueError, match="重复更新"):
        apply_rule_evidence_shadow_delta(base, worklist, final)
