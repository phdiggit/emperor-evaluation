from __future__ import annotations

from copy import deepcopy

import pytest

from emperor_v4.evaluation.projection_judgment_shadow import (
    JUDGMENT_SHADOW_POLICY_VERSION,
    JUDGMENT_SHADOW_SCHEMA_VERSION,
    PROJECTION_SHADOW_POLICY_VERSION,
    build_projection_shadow_worklist,
)
from emperor_v4.evaluation.projection_readiness_rerun import (
    build_incremental_projection_rerun_worklist,
    materialize_incremental_judgment_rerun,
)


def _unit(code: str, fingerprint: str) -> dict[str, object]:
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
        "lineage": {},
        "provenance": {},
        "ruler_ref": "皇帝甲",
        "person_ref": f"PER-{code}",
        "decision_arc_family": "appointment_to_mandate",
        "included_link_refs": [f"SRP-{code}"],
        "scoring_arc_only_refs": [],
        "evidence_assertion_refs": [f"AST-{code}"],
        "question_readiness": {
            "delegation_quality": "ready",
            "supervision_quality": "ready",
            "correction_timeliness": "not_applicable",
            "net_effect": "ready",
        },
    }


def _prior_and_delta() -> tuple[dict[str, object], dict[str, object]]:
    prior_final = {
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
            _unit("RUE-CHANGED", "a" * 64),
            _unit("RUE-REUSED", "b" * 64),
        ],
    }
    prior = build_projection_shadow_worklist(prior_final)
    changed = _unit("RUE-CHANGED", "c" * 64)
    changed["semantic_version"] = 2
    changed["evidence_version"] = 2
    unchanged = _unit("RUE-REUSED", "b" * 64)
    delta = {
        "status": "rule_evidence_shadow_delta_ready_for_projection_rebuild",
        "shadow_delta_gate_passed": True,
        "readiness_rerun_authorized": True,
        "remaining_readiness_gap_count": 0,
        "duplicate_consumption_episode_refs": [],
        "updated_unit_count": 1,
        "unchanged_unit_count": 1,
        "projection_rebuild_unit_refs": ["RUE-CHANGED"],
        "unchanged_unit_refs": ["RUE-REUSED"],
        "rule_evidence_unit_drafts": [changed, unchanged],
        "formal_acceptance_performed": False,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }
    return prior, delta


def _result(projection: dict[str, object]) -> dict[str, object]:
    evidence = projection["projection_payload"]["evidence_assertion_refs"]
    observation = {
        "value": "positive_signal",
        "reason": "fixture positive signal",
        "evidence_assertion_refs": [evidence[0]],
    }
    return {
        "projection_code": projection["projection_code"],
        "review_disposition": "judgment_shadow_ready",
        "shadow_direction": "positive",
        "review_reason": "四项 readiness 完整。",
        "observations": {
            "person_task_fit": deepcopy(observation),
            "authority_clarity": deepcopy(observation),
            "feedback_handling": deepcopy(observation),
            "attributable_outcome": deepcopy(observation),
        },
    }


def _response(worklist: dict[str, object], results: list[dict[str, object]]) -> dict[str, object]:
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
        "results": results,
    }


def test_incremental_projection_worklist_rebuilds_changed_and_reuses_unchanged() -> None:
    prior, delta = _prior_and_delta()

    rerun = build_incremental_projection_rerun_worklist(prior, delta)

    assert rerun["projection_count"] == 2
    assert rerun["rebuilt_projection_count"] == 1
    assert rerun["reused_projection_count"] == 1
    change = next(row for row in rerun["projection_change_map"] if row["input_ref"] == "RUE-CHANGED")
    reuse = next(row for row in rerun["projection_change_map"] if row["input_ref"] == "RUE-REUSED")
    assert change["prior_projection_code"] != change["current_projection_code"]
    assert reuse["prior_projection_code"] == reuse["current_projection_code"]
    assert reuse["cache_disposition"] == "cache_reused"


def test_incremental_judgment_rerun_reuses_one_row_and_passes_all_readiness() -> None:
    prior, delta = _prior_and_delta()
    rerun = build_incremental_projection_rerun_worklist(prior, delta)
    prior_results = [_result(row) for row in prior["projections"]]
    prior_response = _response(prior, prior_results)
    current_results = []
    for projection in rerun["projections"]:
        if projection["projection_code"] in rerun["reused_projection_codes"]:
            current_results.append(
                deepcopy(
                    next(
                        row
                        for row in prior_results
                        if row["projection_code"] == projection["projection_code"]
                    )
                )
            )
        else:
            current_results.append(_result(projection))
    response = _response(rerun, current_results)

    result = materialize_incremental_judgment_rerun(rerun, response, prior_response)

    assert result["status"] == "incremental_judgment_shadow_rerun_passed"
    assert result["judgment_shadow_candidate_count"] == 2
    assert result["blocked_evidence_count"] == 0
    assert result["reused_judgment_count"] == 1
    assert result["rejudged_projection_count"] == 1
    assert result["all_projection_readiness_passed"] is True
    assert result["formal_judgment_count"] == 0
    assert result["score_count"] == 0


def test_incremental_judgment_rerun_rejects_mutated_cached_row() -> None:
    prior, delta = _prior_and_delta()
    rerun = build_incremental_projection_rerun_worklist(prior, delta)
    prior_results = [_result(row) for row in prior["projections"]]
    prior_response = _response(prior, prior_results)
    current_results = [_result(row) for row in rerun["projections"]]
    cached = next(row for row in current_results if row["projection_code"] in rerun["reused_projection_codes"])
    cached["review_reason"] = "mutated"

    with pytest.raises(ValueError, match="逐字段复用"):
        materialize_incremental_judgment_rerun(
            rerun, _response(rerun, current_results), prior_response
        )


def test_incremental_projection_worklist_rejects_reuse_when_fingerprint_changed() -> None:
    prior, delta = _prior_and_delta()
    reused = next(row for row in delta["rule_evidence_unit_drafts"] if row["unit_code"] == "RUE-REUSED")
    reused["semantic_fingerprint"] = "d" * 64

    with pytest.raises(ValueError, match="reuse 输入 fingerprint"):
        build_incremental_projection_rerun_worklist(prior, delta)
