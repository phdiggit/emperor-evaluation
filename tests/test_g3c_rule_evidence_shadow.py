from __future__ import annotations

from copy import deepcopy

import pytest

from emperor_v4.evaluation.rule_evidence_shadow import (
    AGGREGATION_POLICY_VERSION,
    RULE_EVIDENCE_SHADOW_POLICY_VERSION,
    RULE_EVIDENCE_SHADOW_SCHEMA_VERSION,
    RULE_VERSION,
    build_rule_evidence_shadow_worklist,
    materialize_rule_evidence_shadow,
)


def _episode(ref: str, person: str, action: str) -> dict[str, object]:
    return {
        "episode_ref": ref,
        "focal_person_ref": person,
        "action": action,
        "assertions": [
            {
                "assertion_ref": f"AST-{ref}",
                "subject": "皇帝甲",
                "source_passage_ref": f"SP-{ref}",
            }
        ],
    }


def _scoring_inputs() -> tuple[dict[str, object], dict[str, object]]:
    episodes = {
        "EP-1": _episode("EP-1", "PER-1", "任命"),
        "EP-2": _episode("EP-2", "PER-1", "授权"),
        "EP-3": _episode("EP-3", "PER-1", "纠正"),
        "EP-4": _episode("EP-4", "PER-2", "处分"),
        "EP-5": _episode("EP-5", "PER-2", "结局"),
    }
    pairs = (("C-1", "EP-1", "EP-2"), ("C-2", "EP-2", "EP-3"), ("C-3", "EP-4", "EP-5"))
    tasks = [
        {
            "candidate_code": code,
            "dataset_code": "emperor-shadow-fixture",
            "left": episodes[left],
            "right": episodes[right],
        }
        for code, left, right in pairs
    ]
    worklist = {
        "task_code": "G3R-FIXTURE",
        "worklist_sha256": "fixture-worklist-sha",
        "tasks": tasks,
    }
    final = {
        "status": "minimum_sufficient_relation_slice_passed",
        "task_code": "G3R-FIXTURE",
        "minimum_sufficient_gate_passed": True,
        "unresolved_count": 0,
        "formal_relation_count": 0,
        "formal_rule_evidence_unit_count": 0,
        "database_write_count": 0,
        "scoring_relation_proposals": [
            {
                "scoring_relation_proposal_id": "SRP-1",
                "from_episode_version_ref": "EP-1@v1",
                "to_episode_version_ref": "EP-2@v1",
                "relation_family": "authority_change",
                "relation_direction": "expands_authority",
                "scope_match": "same_person_same_domain",
                "fine_type": "appointment_to_delegation",
                "fine_type_status": "supported",
                "lineage": {"candidate_code": "C-1"},
            },
            {
                "scoring_relation_proposal_id": "SRP-2",
                "from_episode_version_ref": "EP-2@v1",
                "to_episode_version_ref": "EP-3@v1",
                "relation_family": "authority_change",
                "relation_direction": "contracts_authority",
                "scope_match": "same_person_same_domain",
                "fine_type": "delegation_to_correction",
                "fine_type_status": "supported",
                "lineage": {"candidate_code": "C-2"},
            },
        ],
        "scoring_arc_memberships": [
            {
                "scoring_arc_membership_id": "SAM-1",
                "episode_version_refs": ["EP-4@v1", "EP-5@v1"],
                "relation_family": "mandate_or_outcome",
                "relation_direction": "same_scoring_arc",
                "scope_match": "same_person_same_domain",
                "unit_member_roles": ["context", "outcome"],
                "lineage": {"candidate_code": "C-3"},
            }
        ],
    }
    return worklist, final


def _response(worklist: dict[str, object]) -> dict[str, object]:
    components = worklist["components"]
    applicable = next(row for row in components if "EP-1@v1" in row["episode_version_refs"])
    excluded = next(row for row in components if "EP-4@v1" in row["episode_version_refs"])
    return {
        "status": "rule_evidence_shadow_reviews_complete",
        "task_code": worklist["task_code"],
        "worklist_sha256": worklist["worklist_sha256"],
        "rule_evidence_shadow_policy_version": RULE_EVIDENCE_SHADOW_POLICY_VERSION,
        "output_schema_version": RULE_EVIDENCE_SHADOW_SCHEMA_VERSION,
        "reviewer": "fixture-reviewer",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_rule_evidence_accessed": False,
        "formal_acceptance_performed": False,
        "judgment_performed": False,
        "scoring_performed": False,
        "database_write_count": 0,
        "results": [
            {
                "component_code": applicable["component_code"],
                "applicability": "applicable",
                "reason": "任命、授权与纠正形成足以回答 B 项问题的最小评分弧。",
                "ruler_ref": "皇帝甲",
                "person_ref": "PER-1",
                "decision_arc_family": "appointment_feedback_correction",
                "episode_member_roles": {
                    "EP-1@v1": "initial_appointment",
                    "EP-2@v1": "delegation",
                    "EP-3@v1": "correction",
                },
                "included_link_refs": ["SRP-1", "SRP-2"],
                "evidence_assertion_refs": ["AST-EP-1", "AST-EP-2", "AST-EP-3"],
                "question_readiness": {
                    "delegation_quality": "ready",
                    "supervision_quality": "ready",
                    "correction_timeliness": "ready",
                    "net_effect": "evidence_gap",
                },
            },
            {
                "component_code": excluded["component_code"],
                "applicability": "not_applicable",
                "reason": "只有处分与结局，不足以形成用人与授权评分单元。",
                "ruler_ref": None,
                "person_ref": None,
                "decision_arc_family": None,
                "episode_member_roles": {},
                "included_link_refs": [],
                "evidence_assertion_refs": ["AST-EP-4", "AST-EP-5"],
                "question_readiness": {},
            },
        ],
    }


def test_rule_evidence_shadow_groups_scoring_links_into_components() -> None:
    scoring_worklist, scoring_final = _scoring_inputs()

    worklist = build_rule_evidence_shadow_worklist(scoring_worklist, scoring_final)

    assert worklist["component_count"] == 2
    assert worklist["rule_version"] == RULE_VERSION
    assert worklist["aggregation_policy_version"] == AGGREGATION_POLICY_VERSION
    assert sorted(len(row["episode_version_refs"]) for row in worklist["components"]) == [2, 3]
    assert worklist["formal_rule_evidence_unit_count"] == 0


def test_rule_evidence_shadow_materializes_draft_only_and_excludes_non_rule_arc() -> None:
    scoring_worklist, scoring_final = _scoring_inputs()
    worklist = build_rule_evidence_shadow_worklist(scoring_worklist, scoring_final)

    result = materialize_rule_evidence_shadow(worklist, _response(worklist))

    assert result["status"] == "rule_evidence_unit_shadow_ready"
    assert result["draft_unit_count"] == 1
    assert result["not_applicable_component_count"] == 1
    assert result["unresolved_component_count"] == 0
    assert result["readiness_evidence_gap_count"] == 1
    assert result["duplicate_consumption_episode_refs"] == []
    draft = result["rule_evidence_unit_drafts"][0]
    assert draft["status"] == "draft"
    assert [member["member_ref"] for member in draft["members"] if member["member_type"] == "relation"] == ["SRP-1", "SRP-2"]
    assert result["formal_rule_evidence_unit_count"] == 0
    assert result["formal_projection_count"] == 0
    assert result["judgment_count"] == 0
    assert result["score_count"] == 0
    assert result["database_write_count"] == 0


def test_rule_evidence_shadow_rejects_missing_episode_evidence() -> None:
    scoring_worklist, scoring_final = _scoring_inputs()
    worklist = build_rule_evidence_shadow_worklist(scoring_worklist, scoring_final)
    response = _response(worklist)
    response["results"][0]["evidence_assertion_refs"].pop()

    with pytest.raises(ValueError, match="覆盖每个 Episode"):
        materialize_rule_evidence_shadow(worklist, response)


def test_rule_evidence_shadow_rejects_partial_link_consumption() -> None:
    scoring_worklist, scoring_final = _scoring_inputs()
    worklist = build_rule_evidence_shadow_worklist(scoring_worklist, scoring_final)
    response = _response(worklist)
    response["results"][0]["included_link_refs"].pop()

    with pytest.raises(ValueError, match="完整且唯一覆盖 component"):
        materialize_rule_evidence_shadow(worklist, response)


def test_rule_evidence_shadow_fails_closed_on_unresolved_component() -> None:
    scoring_worklist, scoring_final = _scoring_inputs()
    worklist = build_rule_evidence_shadow_worklist(scoring_worklist, scoring_final)
    response = _response(worklist)
    unresolved = deepcopy(response["results"][0])
    unresolved.update(
        {
            "applicability": "unresolved",
            "reason": "皇帝归责仍不足。",
            "ruler_ref": None,
            "person_ref": None,
            "decision_arc_family": None,
            "episode_member_roles": {},
            "included_link_refs": [],
            "question_readiness": {},
        }
    )
    response["results"][0] = unresolved

    result = materialize_rule_evidence_shadow(worklist, response)

    assert result["status"] == "rule_evidence_unit_shadow_failed_closed"
    assert result["shadow_gate_passed"] is False
    assert result["unresolved_component_count"] == 1
    assert result["draft_unit_count"] == 0
