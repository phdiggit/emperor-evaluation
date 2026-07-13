from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from emperor_v4.evaluation.relation_blocking import build_relation_candidate_blocks
from emperor_v4.evaluation.relation_endpoint_review import (
    ENDPOINT_ADJUDICATION_SCHEMA_VERSION,
    ENDPOINT_REVIEW_POLICY_VERSION,
    ENDPOINT_REVIEW_SCHEMA_VERSION,
    build_endpoint_review_worklist,
    build_endpoint_adjudication_worklist,
    build_stratified_endpoint_sample,
    compare_endpoint_reviewers,
    apply_endpoint_adjudication,
    validate_endpoint_adjudication_response,
    validate_endpoint_review_response,
)


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _inputs() -> tuple[dict, dict, dict]:
    assertions = [
        {
            "assertion_code": "A-1",
            "source_passage_ref": "SP-1",
            "subject": "皇帝",
            "predicate": "任命",
            "object": "官员甲",
            "time_expression": "元年",
            "location_expression": None,
            "polarity": "asserted",
            "qualifiers": {
                "normalized_time": {"start_sort_key": 100},
                "responsibility_family": "civil_governance",
                "outcome": "授职",
                "claim_summary": "授官员甲某职",
            },
        },
        {
            "assertion_code": "A-2",
            "source_passage_ref": "SP-2",
            "subject": "皇帝",
            "predicate": "调任",
            "object": "官员甲",
            "time_expression": "八年",
            "location_expression": None,
            "polarity": "asserted",
            "qualifiers": {
                "normalized_time": {"start_sort_key": 108},
                "responsibility_family": "civil_governance",
                "outcome": "迁职",
                "claim_summary": "调官员甲任新职",
            },
        },
        {
            "assertion_code": "A-3",
            "source_passage_ref": "SP-3",
            "subject": "皇帝",
            "predicate": "任命",
            "object": "官员乙",
            "time_expression": "百年后",
            "location_expression": None,
            "polarity": "asserted",
            "qualifiers": {"normalized_time": {"start_sort_key": 300}},
        },
    ]
    passages = [
        {
            "passage_code": f"SP-{index}",
            "document_code": "DOC-1",
            "section_heading": "本纪",
            "locator": f"section:{index}",
            "context_before": "前文",
            "raw_text": f"证据{index}",
            "context_after": "后文",
        }
        for index in (1, 2, 3)
    ]
    blind = {
        "dataset_code": "endpoint-test",
        "assertions": assertions,
        "source_passages": passages,
        "collection_provenance": {"gold_accessed": False},
    }
    graph = {
        "dataset_code": "endpoint-test",
        "input_sha256": _hash(blind),
        "episode_groups": [
            {
                "local_episode_code": "EP-1",
                "evaluation_context": "PER-RULER",
                "focal_person_ref": "官员甲",
                "focal_roles": ["office_holder"],
                "action": "任命",
                "responsibility": "旧职",
                "responsibility_family": "civil_governance",
                "core_assertion_refs": ["A-1"],
            },
            {
                "local_episode_code": "EP-2",
                "evaluation_context": "PER-RULER",
                "focal_person_ref": "官员甲",
                "focal_roles": ["office_holder"],
                "action": "调任",
                "responsibility": "新职",
                "responsibility_family": "civil_governance",
                "core_assertion_refs": ["A-2"],
            },
            {
                "local_episode_code": "EP-3",
                "evaluation_context": "PER-RULER",
                "focal_person_ref": "官员乙",
                "focal_roles": ["office_holder"],
                "action": "任命",
                "responsibility": "无关职务",
                "responsibility_family": "civil_governance",
                "core_assertion_refs": ["A-3"],
            },
        ],
    }
    blocking = build_relation_candidate_blocks(graph, blind)
    return graph, blind, blocking


def _response(worklist: dict, reviewer: str, *, direct: str = "yes", coarse="authority_change") -> dict:
    task = worklist["tasks"][0]
    return {
        "schema_version": 1,
        "status": "endpoint_reviews_complete",
        "task_code": worklist["task_code"],
        "worklist_sha256": worklist["worklist_sha256"],
        "endpoint_review_policy_version": ENDPOINT_REVIEW_POLICY_VERSION,
        "output_schema_version": ENDPOINT_REVIEW_SCHEMA_VERSION,
        "reviewer": reviewer,
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "other_reviewer_output_accessed": False,
        "formal_acceptance_performed": False,
        "results": [
            {
                "candidate_code": task["candidate_code"],
                "direct_relation": direct,
                "coarse_type": coarse,
                "evidence_assertion_refs": [
                    task["left"]["assertions"][0]["assertion_ref"],
                    task["right"]["assertions"][0]["assertion_ref"],
                ],
                "reason": "两端证据明确显示同一官员的连续调任。",
            }
        ],
    }


def test_worklist_contains_only_blocked_pair_and_minimum_endpoint_evidence() -> None:
    graph, blind, blocking = _inputs()

    worklist = build_endpoint_review_worklist(blocking, graph, blind)

    assert blocking["possible_pair_count"] == 3
    assert worklist["candidate_count"] == blocking["candidate_pair_count"] == 1
    assert worklist["tasks"][0]["left"]["assertions"][0]["assertion_ref"] == "A-1"
    assert worklist["tasks"][0]["right"]["source_passages"][0]["raw_text"] == "证据2"
    assert worklist["formal_relation_count"] == 0
    assert worklist["database_write_count"] == 0


def test_worklist_rejects_tampered_blocking_or_old_relation_review() -> None:
    graph, blind, blocking = _inputs()
    tampered = deepcopy(blocking)
    tampered["candidate_pair_count"] = 99
    with pytest.raises(ValueError, match="blocking 结果不一致"):
        build_endpoint_review_worklist(tampered, graph, blind)

    leaked = deepcopy(graph)
    leaked["relation_review"] = {}
    with pytest.raises(ValueError, match="禁止字段"):
        build_endpoint_review_worklist(blocking, leaked, blind)


def test_response_requires_valid_coarse_type_and_both_endpoint_evidence() -> None:
    graph, blind, blocking = _inputs()
    worklist = build_endpoint_review_worklist(blocking, graph, blind)
    valid = _response(worklist, "reviewer-a")

    rows = validate_endpoint_review_response(
        worklist, valid, expected_reviewer="reviewer-a"
    )
    assert len(rows) == 1

    invalid_coarse = _response(worklist, "reviewer-a", direct="no", coarse="authority_change")
    with pytest.raises(ValueError, match="coarse_type 必须为 null"):
        validate_endpoint_review_response(worklist, invalid_coarse)

    one_sided = _response(worklist, "reviewer-a")
    one_sided["results"][0]["evidence_assertion_refs"] = ["A-1"]
    with pytest.raises(ValueError, match="覆盖两端"):
        validate_endpoint_review_response(worklist, one_sided)


def test_dual_review_agreement_produces_proposal_not_formal_acceptance() -> None:
    graph, blind, blocking = _inputs()
    worklist = build_endpoint_review_worklist(blocking, graph, blind)

    report = compare_endpoint_reviewers(
        worklist,
        _response(worklist, "reviewer-a"),
        _response(worklist, "reviewer-b"),
    )

    assert report["agreement_gate_passed"] is True
    assert report["direct_agreement_rate"] == 1.0
    assert report["coarse_type_agreement_rate"] == 1.0
    assert report["comparisons"][0]["proposed_disposition"] == "proposed_direct_relation"
    assert report["formal_acceptance_performed"] is False


def test_disagreement_or_insufficient_fails_closed_to_adjudication() -> None:
    graph, blind, blocking = _inputs()
    worklist = build_endpoint_review_worklist(blocking, graph, blind)
    first = _response(worklist, "reviewer-a")
    second = _response(worklist, "reviewer-b", direct="insufficient", coarse=None)

    report = compare_endpoint_reviewers(worklist, first, second)

    assert report["agreement_gate_passed"] is False
    assert report["needs_adjudication_count"] == 1
    assert report["comparisons"][0]["proposed_disposition"] == "needs_adjudication"


def test_dual_review_rejects_same_reviewer_or_other_output_access() -> None:
    graph, blind, blocking = _inputs()
    worklist = build_endpoint_review_worklist(blocking, graph, blind)
    first = _response(worklist, "reviewer-a")
    second = _response(worklist, "reviewer-a")
    with pytest.raises(ValueError, match="不同 reviewer"):
        compare_endpoint_reviewers(worklist, first, second)

    leaked = _response(worklist, "reviewer-b")
    leaked["other_reviewer_output_accessed"] = True
    with pytest.raises(ValueError, match="完整隔离"):
        validate_endpoint_review_response(worklist, leaked)


def test_stratified_sample_is_deterministic_and_honors_dataset_quotas() -> None:
    graph, blind, blocking = _inputs()
    first = build_endpoint_review_worklist(blocking, graph, blind)
    second = deepcopy(first)
    second["dataset_code"] = "endpoint-test-b"
    second["task_code"] = "G3R-ENDPOINT-B"
    second["worklist_sha256"] = "b" * 64
    second["tasks"][0]["candidate_code"] = "RBC-B"

    sample, manifest = build_stratified_endpoint_sample(
        {"endpoint-test": first, "endpoint-test-b": second},
        {"endpoint-test": 1, "endpoint-test-b": 1},
    )
    repeated, repeated_manifest = build_stratified_endpoint_sample(
        {"endpoint-test": deepcopy(first), "endpoint-test-b": deepcopy(second)},
        {"endpoint-test": 1, "endpoint-test-b": 1},
    )

    assert sample == repeated
    assert manifest == repeated_manifest
    assert sample["candidate_count"] == 2
    assert {task["dataset_code"] for task in sample["tasks"]} == {
        "endpoint-test",
        "endpoint-test-b",
    }
    assert manifest["gold_accessed"] is False


def test_stratified_sample_rejects_invalid_or_unmatched_quota() -> None:
    graph, blind, blocking = _inputs()
    worklist = build_endpoint_review_worklist(blocking, graph, blind)
    with pytest.raises(ValueError, match="一一对应"):
        build_stratified_endpoint_sample(
            {"endpoint-test": worklist}, {"other": 1}
        )
    with pytest.raises(ValueError, match="quota 非法"):
        build_stratified_endpoint_sample(
            {"endpoint-test": worklist}, {"endpoint-test": 2}
        )


def test_adjudication_worklist_contains_only_disputes_and_no_formal_relation() -> None:
    graph, blind, blocking = _inputs()
    worklist = build_endpoint_review_worklist(blocking, graph, blind)
    first = _response(worklist, "reviewer-a")
    second = _response(worklist, "reviewer-b", direct="no", coarse=None)

    adjudication = build_endpoint_adjudication_worklist(worklist, first, second)

    assert adjudication["candidate_count"] == 1
    assert adjudication["tasks"][0]["candidate_code"] == worklist["tasks"][0][
        "candidate_code"
    ]
    assert set(adjudication["tasks"][0]["reviewer_results"]) == {
        "reviewer-a",
        "reviewer-b",
    }
    assert adjudication["gold_accessed"] is False
    assert adjudication["formal_acceptance_performed"] is False
    assert adjudication["formal_relation_count"] == 0


def test_adjudication_worklist_rejects_fully_agreed_reviews() -> None:
    graph, blind, blocking = _inputs()
    worklist = build_endpoint_review_worklist(blocking, graph, blind)
    with pytest.raises(ValueError, match="没有需要裁决"):
        build_endpoint_adjudication_worklist(
            worklist,
            _response(worklist, "reviewer-a"),
            _response(worklist, "reviewer-b"),
        )


def test_adjudication_response_is_validated_and_remains_proposal_only() -> None:
    graph, blind, blocking = _inputs()
    worklist = build_endpoint_review_worklist(blocking, graph, blind)
    first = _response(worklist, "reviewer-a")
    second = _response(worklist, "reviewer-b", direct="no", coarse=None)
    adjudication = build_endpoint_adjudication_worklist(worklist, first, second)
    task = adjudication["tasks"][0]
    response = {
        "schema_version": 1,
        "status": "endpoint_adjudication_complete",
        "task_code": adjudication["task_code"],
        "worklist_sha256": adjudication["worklist_sha256"],
        "output_schema_version": ENDPOINT_ADJUDICATION_SCHEMA_VERSION,
        "adjudicator": "reviewer-c",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_relation_review_accessed": False,
        "formal_acceptance_performed": False,
        "results": [
            {
                "candidate_code": task["candidate_code"],
                "direct_relation": "yes",
                "coarse_type": "authority_change",
                "evidence_assertion_refs": [
                    task["endpoint_task"]["left"]["assertions"][0][
                        "assertion_ref"
                    ],
                    task["endpoint_task"]["right"]["assertions"][0][
                        "assertion_ref"
                    ],
                ],
                "reason": "裁决仍只形成粗类型 proposal。",
            }
        ],
    }

    assert len(validate_endpoint_adjudication_response(adjudication, response)) == 1
    final = apply_endpoint_adjudication(
        worklist, first, second, adjudication, response
    )
    assert final["remaining_evidence_gap_count"] == 0
    assert final["formal_acceptance_performed"] is False
    assert final["formal_relation_count"] == 0


def test_adjudication_insufficient_keeps_evidence_gap_open() -> None:
    graph, blind, blocking = _inputs()
    worklist = build_endpoint_review_worklist(blocking, graph, blind)
    first = _response(worklist, "reviewer-a")
    second = _response(worklist, "reviewer-b", direct="no", coarse=None)
    adjudication = build_endpoint_adjudication_worklist(worklist, first, second)
    task = adjudication["tasks"][0]
    response = {
        "status": "endpoint_adjudication_complete",
        "task_code": adjudication["task_code"],
        "worklist_sha256": adjudication["worklist_sha256"],
        "output_schema_version": ENDPOINT_ADJUDICATION_SCHEMA_VERSION,
        "adjudicator": "reviewer-c",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_relation_review_accessed": False,
        "formal_acceptance_performed": False,
        "results": [
            {
                "candidate_code": task["candidate_code"],
                "direct_relation": "insufficient",
                "coarse_type": None,
                "evidence_assertion_refs": [
                    task["endpoint_task"]["left"]["assertions"][0]["assertion_ref"],
                    task["endpoint_task"]["right"]["assertions"][0]["assertion_ref"],
                ],
                "reason": "端点证据不足。",
            }
        ],
    }
    final = apply_endpoint_adjudication(
        worklist, first, second, adjudication, response
    )
    assert final["remaining_evidence_gap_count"] == 1
    assert final["agreement_gate_passed"] is False
