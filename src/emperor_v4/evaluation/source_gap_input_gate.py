from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from emperor_v4.contracts.assertion import AssertionDraft, PassageSupport
from emperor_v4.contracts.source import LinkedPassageRef, SourcePassage


INPUT_GATE_POLICY_VERSION = "appointment-delegation-source-gap-input-gate-v2"
INPUT_GATE_SCHEMA_VERSION = "source-gap-input-gate-output-v2"

DISPOSITIONS = frozenset(
    {"accepted_for_shadow_delta", "rejected", "unresolved"}
)
BOUNDARY_DISPOSITIONS = frozenset(
    {"episode_arc_member", "context_for_rule_evidence_unit", "core_of_new_episode"}
)

_FORBIDDEN_KEYS = frozenset(
    {
        "score",
        "scores",
        "judgment_id",
        "formal_projection_id",
        "formal_judgment_id",
        "accepted_assertion",
        "accepted_episode",
        "historical_gold",
        "rule_gold",
    }
)


def _hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _reject_forbidden(payload: object, path: str = "$") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).strip().casefold()
            if normalized in _FORBIDDEN_KEYS or normalized.startswith("gold_"):
                if normalized == "gold_accessed" and value is False:
                    continue
                raise ValueError(f"Source-gap input Gate 包含禁止字段: {path}.{key}")
            _reject_forbidden(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_forbidden(value, f"{path}[{index}]")


def build_source_gap_input_gate_worklist(
    source_gap_worklist: Mapping[str, Any],
    source_gap_response: Mapping[str, Any],
    source_gap_final: Mapping[str, Any],
) -> dict[str, Any]:
    _reject_forbidden(source_gap_worklist)
    _reject_forbidden(source_gap_response)
    _reject_forbidden(source_gap_final)
    if (
        source_gap_final.get("status")
        != "source_gap_inventory_complete_pending_input_gates"
        or source_gap_final.get("all_gap_requests_covered") is not True
        or source_gap_final.get("readiness_rerun_authorized") is not False
        or source_gap_final.get("formal_acceptance_performed") is not False
        or source_gap_final.get("formal_assertion_count") != 0
        or source_gap_final.get("formal_episode_count") != 0
        or source_gap_final.get("formal_projection_count") != 0
        or source_gap_final.get("formal_judgment_count") != 0
        or source_gap_final.get("score_count") != 0
        or source_gap_final.get("database_write_count") != 0
        or source_gap_response.get("task_code") != source_gap_worklist.get("task_code")
        or source_gap_final.get("task_code") != source_gap_worklist.get("task_code")
    ):
        raise ValueError("Source-gap input Gate 上游状态不一致或存在副作用")

    request_by_code = {
        str(row["gap_code"]): row
        for row in source_gap_worklist.get("gap_requests") or ()
    }
    inventory_by_code = {
        str(row["gap_code"]): row for row in source_gap_response.get("results") or ()
    }
    if set(request_by_code) != set(inventory_by_code) or not request_by_code:
        raise ValueError("Source-gap input Gate 未完整覆盖库存候选")

    tasks = []
    stopped_requests = []
    for code in sorted(request_by_code):
        request = request_by_code[code]
        inventory = inventory_by_code[code]
        if inventory["resolution_kind"] == "not_found_stop":
            stopped_requests.append(
                {
                    "gap_code": code,
                    "input_ref": request["input_ref"],
                    "resolution_kind": "not_found_stop",
                    "reason": inventory["reason"],
                    "stop_condition": inventory.get("stop_condition"),
                }
            )
            continue
        tasks.append(
            {
                "gap_code": code,
                "input_ref": request["input_ref"],
                "ruler_ref": request["ruler_ref"],
                "person_ref": request["person_ref"],
                "decision_arc_family": request["decision_arc_family"],
                "current_episode_refs": request["current_episode_refs"],
                "open_observation_dimensions": request[
                    "open_observation_dimensions"
                ],
                "open_readiness_questions": request["open_readiness_questions"],
                "candidate_kind": inventory["resolution_kind"],
                "candidate_episode_refs": inventory["candidate_episode_refs"],
                "existing_assertion_refs": inventory["existing_assertion_refs"],
                "source_passage_refs": inventory["source_passage_refs"],
                "proposed_assertion_summary": inventory.get(
                    "proposed_assertion_summary"
                ),
                "required_gate": inventory["follow_up_gate"],
                "inventory_reason": inventory["reason"],
            }
        )

    basis = {
        "source_gap_task_code": source_gap_worklist.get("task_code"),
        "source_gap_final_sha256": _hash(source_gap_final),
        "gap_codes": [row["gap_code"] for row in tasks],
        "stopped_gap_codes": [row["gap_code"] for row in stopped_requests],
        "input_gate_policy_version": INPUT_GATE_POLICY_VERSION,
    }
    worklist_hash = _hash(basis)
    return {
        "schema_version": 1,
        "status": "source_gap_input_gate_worklist_ready",
        "task_code": f"G3F-INPUT-GATE-{worklist_hash[:20].upper()}",
        "worklist_sha256": worklist_hash,
        **basis,
        "output_schema_version": INPUT_GATE_SCHEMA_VERSION,
        "source_gap_request_count": len(request_by_code),
        "task_count": len(tasks),
        "tasks": tasks,
        "stopped_request_count": len(stopped_requests),
        "stopped_requests": stopped_requests,
        "gate_policy": {
            "episode_rule": "现有 Episode 只审查是否进入同一 scoring arc，不改写其事实。",
            "assertion_rule": "新 Assertion 必须通过 AssertionDraft、PassageSupport 与边界校验。",
            "passage_rule": "新 Passage 必须通过 SourcePassage v2 hash/span/lineage 校验。",
            "side_effect_rule": "通过仅授权 shadow delta，不形成正式事实、判断或分数。",
        },
        "gold_accessed": False,
        "formal_assertion_count": 0,
        "formal_episode_count": 0,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }


def _source_passage(payload: Mapping[str, Any]) -> SourcePassage:
    return SourcePassage(
        passage_cache_id=str(payload["passage_cache_id"]),
        document_cache_id=str(payload["document_cache_id"]),
        locator=str(payload["locator"]),
        raw_text=str(payload["raw_text"]),
        context_before=str(payload.get("context_before") or ""),
        context_after=str(payload.get("context_after") or ""),
        content_hash=str(payload["content_hash"]),
        selection_reason=tuple(payload.get("selection_reason") or ()),
        contract_version=str(payload["contract_version"]),
        content_version=payload.get("content_version"),
        section_id=payload.get("section_id"),
        section_heading=payload.get("section_heading"),
        span_start=payload.get("span_start"),
        span_end=payload.get("span_end"),
        passage_kind=payload.get("passage_kind"),
        linked_passages=tuple(
            LinkedPassageRef(str(row["passage_ref"]), str(row["relation"]))
            for row in payload.get("linked_passages") or ()
        ),
        overlap_group=payload.get("overlap_group"),
        window_policy_version=payload.get("window_policy_version"),
    )


def _assertion(payload: Mapping[str, Any]) -> AssertionDraft:
    support_payload = payload.get("passage_support") or {}
    support = PassageSupport(
        support_mode=str(support_payload["support_mode"]),
        assertion_semantic_key=str(support_payload["assertion_semantic_key"]),
        supported_fields=tuple(support_payload["supported_fields"]),
        binding_provenance=dict(support_payload.get("binding_provenance") or {}),
    )
    return AssertionDraft(
        assertion_code=str(payload["assertion_code"]),
        source_passage_ref=str(payload["source_passage_ref"]),
        assertion_type=str(payload["assertion_type"]),
        subject=str(payload["subject"]),
        predicate=str(payload["predicate"]),
        object=str(payload["object"]),
        time_expression=payload.get("time_expression"),
        location_expression=payload.get("location_expression"),
        qualifiers=dict(payload.get("qualifiers") or {}),
        polarity=str(payload["polarity"]),
        source_attribution=dict(payload.get("source_attribution") or {}),
        candidate_episode_key=payload.get("candidate_episode_key"),
        confidence=float(payload["confidence"]),
        ambiguity_flags=tuple(payload.get("ambiguity_flags") or ()),
        extraction_provenance=dict(payload.get("extraction_provenance") or {}),
        passage_support=support,
    )


def validate_source_gap_input_gate_response(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Mapping[str, Any]]:
    _reject_forbidden(response)
    if (
        response.get("status") != "source_gap_input_gate_reviews_complete"
        or response.get("task_code") != worklist.get("task_code")
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("input_gate_policy_version") != INPUT_GATE_POLICY_VERSION
        or response.get("output_schema_version") != INPUT_GATE_SCHEMA_VERSION
        or not str(response.get("reviewer") or "")
    ):
        raise ValueError("Source-gap input Gate response 与 worklist/policy/schema 不一致")
    if (
        response.get("proposal_only") is not True
        or response.get("gold_accessed") is not False
        or response.get("formal_acceptance_performed") is not False
        or response.get("judgment_performed") is not False
        or response.get("scoring_performed") is not False
        or response.get("database_write_count") != 0
    ):
        raise ValueError("Source-gap input Gate 未保持 proposal-only 与零副作用")

    task_by_code = {str(row["gap_code"]): row for row in worklist.get("tasks") or ()}
    results = tuple(response.get("results") or ())
    result_by_code = {str(row.get("gap_code") or ""): row for row in results}
    if (
        "" in result_by_code
        or len(result_by_code) != len(results)
        or set(result_by_code) != set(task_by_code)
    ):
        raise ValueError("Source-gap input Gate 未完整且唯一覆盖 task")

    for code, task in task_by_code.items():
        row = result_by_code[code]
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            raise ValueError("Source-gap input Gate disposition 非法")
        if not str(row.get("reason") or "").strip():
            raise ValueError("Source-gap input Gate 缺少 reason")
        if disposition != "accepted_for_shadow_delta":
            if any(
                row.get(key) not in (None, {}, [], ())
                for key in (
                    "boundary_disposition",
                    "episode_arc_review",
                    "source_passage_snapshot",
                    "candidate_source_passage",
                    "candidate_assertion",
                    "proposed_episode_ref",
                    "member_role",
                )
            ):
                raise ValueError("未通过的 input Gate 不得携带 shadow delta")
            continue

        boundary = row.get("boundary_disposition")
        if boundary not in BOUNDARY_DISPOSITIONS:
            raise ValueError("Source-gap input Gate boundary disposition 非法")
        if task["candidate_kind"] == "existing_episode_candidate":
            arc = row.get("episode_arc_review") or {}
            if (
                boundary != "episode_arc_member"
                or arc.get("decision") != "same_scoring_arc"
                or arc.get("candidate_episode_ref")
                not in task["candidate_episode_refs"]
                or set(arc.get("evidence_assertion_refs") or ())
                != set(task["existing_assertion_refs"])
                or set(arc.get("source_passage_refs") or ())
                != set(task["source_passage_refs"])
                or row.get("member_role") not in {"outcome", "feedback", "correction"}
                or any(
                    row.get(key) not in (None, {}, [], ())
                    for key in (
                        "source_passage_snapshot",
                        "candidate_source_passage",
                        "candidate_assertion",
                        "proposed_episode_ref",
                    )
                )
            ):
                raise ValueError("现有 Episode arc review 不完整或越界")
            continue

        existing_snapshot = row.get("source_passage_snapshot")
        candidate_passage_payload = row.get("candidate_source_passage")
        if bool(existing_snapshot) == bool(candidate_passage_payload):
            raise ValueError("SourcePassage 候选必须且只能选择现有 snapshot 或新 passage")
        passage = _source_passage(existing_snapshot or candidate_passage_payload)
        if task["source_passage_refs"][0] not in {
            passage.passage_cache_id,
            *(item.passage_ref for item in passage.linked_passages),
        }:
            raise ValueError("SourcePassage 候选未保留库存 lineage")
        assertion = _assertion(row.get("candidate_assertion") or {})
        if assertion.source_passage_ref != passage.passage_cache_id:
            raise ValueError("Assertion source_passage_ref 与候选 Passage 不一致")
        if assertion.extraction_provenance.get("status") != "proposal_only":
            raise ValueError("Assertion candidate 未声明 proposal_only")
        if assertion.subject != task["ruler_ref"] or task["person_ref"] not in {
            str(value)
            for value in assertion.qualifiers.get("candidate_focal_person_refs") or ()
        }:
            raise ValueError("Assertion candidate 皇帝归责或人物身份不一致")
        if boundary == "context_for_rule_evidence_unit":
            if row.get("proposed_episode_ref") is not None or row.get("member_role") != "context":
                raise ValueError("context Assertion 不得伪造 Episode")
        elif boundary == "core_of_new_episode":
            if not str(row.get("proposed_episode_ref") or "").startswith("EP-SHADOW-"):
                raise ValueError("new Episode candidate 缺少 shadow ref")
            if row.get("member_role") not in {"outcome", "feedback", "correction"}:
                raise ValueError("new Episode candidate member role 非法")
        else:
            raise ValueError("SourcePassage candidate boundary 类型不匹配")
    return result_by_code


def materialize_source_gap_input_gate(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Any]:
    rows = validate_source_gap_input_gate_response(worklist, response)
    accepted = [rows[code] for code in sorted(rows) if rows[code]["disposition"] == "accepted_for_shadow_delta"]
    unresolved = [rows[code] for code in sorted(rows) if rows[code]["disposition"] == "unresolved"]
    rejected = [rows[code] for code in sorted(rows) if rows[code]["disposition"] == "rejected"]
    gate_passed = len(accepted) == len(rows) and not unresolved and not rejected
    stopped_requests = list(worklist.get("stopped_requests") or ())
    has_delta = bool(accepted)
    return {
        "schema_version": 1,
        "status": (
            "source_gap_input_gate_passed_for_shadow_delta"
            if gate_passed and has_delta
            else "source_gap_input_gate_no_candidates_stopped"
            if gate_passed
            else "source_gap_input_gate_failed_closed"
        ),
        "task_code": worklist.get("task_code"),
        "source_gap_request_count": worklist.get("source_gap_request_count"),
        "task_count": len(rows),
        "stopped_request_count": len(stopped_requests),
        "stopped_requests": stopped_requests,
        "accepted_shadow_delta_count": len(accepted),
        "episode_arc_member_count": sum(
            row.get("boundary_disposition") == "episode_arc_member" for row in accepted
        ),
        "context_assertion_candidate_count": sum(
            row.get("boundary_disposition") == "context_for_rule_evidence_unit"
            for row in accepted
        ),
        "new_passage_candidate_count": sum(
            bool(row.get("candidate_source_passage")) for row in accepted
        ),
        "new_assertion_candidate_count": sum(
            bool(row.get("candidate_assertion")) for row in accepted
        ),
        "new_episode_candidate_count": sum(
            row.get("boundary_disposition") == "core_of_new_episode"
            for row in accepted
        ),
        "unresolved_count": len(unresolved),
        "rejected_count": len(rejected),
        "shadow_delta_authorized": gate_passed and has_delta,
        "readiness_rerun_authorized": False,
        "accepted_shadow_deltas": accepted,
        "unresolved": unresolved,
        "rejected": rejected,
        "formal_acceptance_performed": False,
        "formal_assertion_count": 0,
        "formal_episode_count": 0,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }
