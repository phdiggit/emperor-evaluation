from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Any, Mapping


SOURCE_GAP_POLICY_VERSION = "appointment-delegation-judgment-source-gap-v1"
SOURCE_GAP_SCHEMA_VERSION = "judgment-source-gap-inventory-output-v1"

RESOLUTION_KINDS = frozenset(
    {"existing_episode_candidate", "source_passage_candidate", "not_found_stop"}
)
FOLLOW_UP_GATES = frozenset(
    {
        "episode_arc_review",
        "assertion_boundary_review",
        "segmentation_assertion_boundary_review",
        "none",
    }
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
                raise ValueError(f"Judgment source-gap 输入包含禁止字段: {path}.{key}")
            _reject_forbidden(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_forbidden(value, f"{path}[{index}]")


def build_judgment_source_gap_worklist(
    judgment_worklist: Mapping[str, Any],
    judgment_response: Mapping[str, Any],
    judgment_final: Mapping[str, Any],
) -> dict[str, Any]:
    """只为 blocked_evidence Projection 建立最小、可停止的库存补证请求。"""

    _reject_forbidden(judgment_worklist)
    _reject_forbidden(judgment_response)
    _reject_forbidden(judgment_final)
    if (
        judgment_final.get("status") != "judgment_shadow_readiness_passed"
        or judgment_final.get("shadow_gate_passed") is not True
        or judgment_final.get("blocked_rule_boundary_count") != 0
        or judgment_final.get("formal_acceptance_performed") is not False
        or judgment_final.get("formal_projection_count") != 0
        or judgment_final.get("formal_judgment_count") != 0
        or judgment_final.get("score_count") != 0
        or judgment_final.get("database_write_count") != 0
        or judgment_response.get("task_code") != judgment_worklist.get("task_code")
        or judgment_final.get("task_code") != judgment_worklist.get("task_code")
    ):
        raise ValueError("Judgment source-gap 输入未通过 readiness Gate 或存在副作用")

    projections = {
        str(row["projection_code"]): row
        for row in judgment_worklist.get("projections") or ()
    }
    response_rows = {
        str(row["projection_code"]): row
        for row in judgment_response.get("results") or ()
    }
    blocked_refs = {
        str(row["projection_code"])
        for row in judgment_final.get("blocked_reviews") or ()
        if row.get("review_disposition") == "blocked_evidence"
    }
    if (
        len(blocked_refs) != judgment_final.get("blocked_evidence_count")
        or not blocked_refs
        or not blocked_refs <= set(projections)
        or not blocked_refs <= set(response_rows)
    ):
        raise ValueError("Judgment source-gap blocked Projection 集合不一致")

    requests = []
    for projection_code in sorted(blocked_refs):
        projection = projections[projection_code]
        review = response_rows[projection_code]
        open_dimensions = sorted(
            dimension
            for dimension, observation in review["observations"].items()
            if observation["value"] == "evidence_gap"
        )
        readiness_gaps = sorted(
            question
            for question, value in projection["projection_payload"][
                "question_readiness"
            ].items()
            if value == "evidence_gap"
        )
        if not open_dimensions or not readiness_gaps:
            raise ValueError("blocked_evidence 缺少 observation/readiness 缺口")
        basis = {
            "projection_code": projection_code,
            "input_ref": projection["input_ref"],
            "open_observation_dimensions": open_dimensions,
            "open_readiness_questions": readiness_gaps,
            "source_gap_policy_version": SOURCE_GAP_POLICY_VERSION,
        }
        gap_hash = _hash(basis)
        requests.append(
            {
                "gap_code": f"JSG-{gap_hash[:20].upper()}",
                **basis,
                "ruler_ref": projection["projection_payload"]["ruler_ref"],
                "person_ref": projection["projection_payload"]["person_ref"],
                "decision_arc_family": projection["projection_payload"][
                    "decision_arc_family"
                ],
                "current_episode_refs": sorted(
                    member["member_ref"]
                    for member in projection["projection_payload"]["members"]
                    if member["member_type"] == "episode"
                ),
                "current_evidence_assertion_refs": sorted(
                    projection["projection_payload"]["evidence_assertion_refs"]
                ),
            }
        )

    basis = {
        "source_judgment_task_code": judgment_worklist.get("task_code"),
        "source_judgment_final_sha256": _hash(judgment_final),
        "gap_codes": [row["gap_code"] for row in requests],
        "source_gap_policy_version": SOURCE_GAP_POLICY_VERSION,
    }
    worklist_hash = _hash(basis)
    return {
        "schema_version": 1,
        "status": "judgment_source_gap_worklist_ready",
        "task_code": f"G3E-SOURCE-GAP-{worklist_hash[:20].upper()}",
        "worklist_sha256": worklist_hash,
        **basis,
        "output_schema_version": SOURCE_GAP_SCHEMA_VERSION,
        "gap_request_count": len(requests),
        "gap_requests": requests,
        "inventory_policy": {
            "first_scope": "只读当前 source-v2 input 与无 Gold 的 blocking episode inventory。",
            "stop_rule": "每个缺口找到一个最小高价值候选即停止；未命中则记录 not_found_stop。",
            "forbidden_scope": "不得读取 Gold、旧 Relation、旧 Judgment、score、V3 数据库或人物传记式全量材料。",
        },
        "gold_accessed": False,
        "external_fetch_performed": False,
        "formal_assertion_count": 0,
        "formal_episode_count": 0,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }


def validate_source_gap_inventory_response(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Mapping[str, Any]]:
    _reject_forbidden(response)
    if (
        response.get("status") != "judgment_source_gap_inventory_complete"
        or response.get("task_code") != worklist.get("task_code")
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("source_gap_policy_version") != SOURCE_GAP_POLICY_VERSION
        or response.get("output_schema_version") != SOURCE_GAP_SCHEMA_VERSION
        or not str(response.get("reviewer") or "")
    ):
        raise ValueError("Judgment source-gap response 与 worklist/policy/schema 不一致")
    if (
        response.get("inventory_only") is not True
        or response.get("gold_accessed") is not False
        or response.get("old_relation_accessed") is not False
        or response.get("old_judgment_accessed") is not False
        or response.get("external_fetch_performed") is not False
        or response.get("formal_acceptance_performed") is not False
        or response.get("database_write_count") != 0
    ):
        raise ValueError("Judgment source-gap response 未保持库存隔离与零副作用")

    inventory_sources = tuple(str(path) for path in response.get("inventory_sources") or ())
    if not inventory_sources:
        raise ValueError("Judgment source-gap 缺少 inventory_sources")
    for path in inventory_sources:
        lowered_parts = {part.casefold() for part in PurePosixPath(path.replace("\\", "/")).parts}
        if any("gold" in part or "relation" in part or "judgment" in part for part in lowered_parts):
            raise ValueError("Judgment source-gap inventory source 越过禁止范围")

    request_by_code = {
        str(row["gap_code"]): row for row in worklist.get("gap_requests") or ()
    }
    results = tuple(response.get("results") or ())
    result_by_code = {str(row.get("gap_code") or ""): row for row in results}
    if (
        "" in result_by_code
        or len(result_by_code) != len(results)
        or set(result_by_code) != set(request_by_code)
    ):
        raise ValueError("Judgment source-gap response 未完整且唯一覆盖 gap request")

    for code, request in request_by_code.items():
        row = result_by_code[code]
        kind = row.get("resolution_kind")
        if kind not in RESOLUTION_KINDS:
            raise ValueError("Judgment source-gap resolution_kind 非法")
        if row.get("follow_up_gate") not in FOLLOW_UP_GATES:
            raise ValueError("Judgment source-gap follow_up_gate 非法")
        if not str(row.get("reason") or "").strip() or not str(
            row.get("stop_condition") or ""
        ).strip():
            raise ValueError("Judgment source-gap 缺少 reason/stop condition")
        addressed_dimensions = set(row.get("addressed_observation_dimensions") or ())
        addressed_questions = set(row.get("addressed_readiness_questions") or ())
        if (
            not addressed_dimensions
            or not addressed_dimensions <= set(request["open_observation_dimensions"])
            or not addressed_questions
            or not addressed_questions <= set(request["open_readiness_questions"])
        ):
            raise ValueError("Judgment source-gap addressed 范围为空或越界")
        candidate_episode_refs = tuple(row.get("candidate_episode_refs") or ())
        source_passage_refs = tuple(row.get("source_passage_refs") or ())
        assertion_refs = tuple(row.get("existing_assertion_refs") or ())
        if kind == "existing_episode_candidate":
            if (
                not candidate_episode_refs
                or not assertion_refs
                or not source_passage_refs
                or row.get("follow_up_gate") != "episode_arc_review"
            ):
                raise ValueError("existing episode candidate 缺少 Episode/Assertion/Passage 或 Gate")
        elif kind == "source_passage_candidate":
            if (
                candidate_episode_refs
                or assertion_refs
                or not source_passage_refs
                or row.get("follow_up_gate")
                not in {
                    "assertion_boundary_review",
                    "segmentation_assertion_boundary_review",
                }
                or not str(row.get("proposed_assertion_summary") or "").strip()
            ):
                raise ValueError("source passage candidate 未保持 proposal-only 边界")
        elif (
            candidate_episode_refs
            or assertion_refs
            or source_passage_refs
            or row.get("follow_up_gate") != "none"
        ):
            raise ValueError("not_found_stop 不得伪造候选")
    return result_by_code


def materialize_source_gap_inventory(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Any]:
    rows = validate_source_gap_inventory_response(worklist, response)
    kinds = [row["resolution_kind"] for row in rows.values()]
    pending = [row for row in rows.values() if row["follow_up_gate"] != "none"]
    all_covered = len(rows) == worklist.get("gap_request_count")
    return {
        "schema_version": 1,
        "status": (
            "source_gap_inventory_complete_pending_input_gates"
            if all_covered and pending
            else "source_gap_inventory_complete_stopped"
            if all_covered
            else "source_gap_inventory_failed_closed"
        ),
        "task_code": worklist.get("task_code"),
        "gap_request_count": len(rows),
        "existing_episode_candidate_count": kinds.count("existing_episode_candidate"),
        "source_passage_candidate_count": kinds.count("source_passage_candidate"),
        "not_found_stop_count": kinds.count("not_found_stop"),
        "pending_episode_arc_review_count": sum(
            row["follow_up_gate"] == "episode_arc_review" for row in rows.values()
        ),
        "pending_assertion_boundary_review_count": sum(
            row["follow_up_gate"]
            in {"assertion_boundary_review", "segmentation_assertion_boundary_review"}
            for row in rows.values()
        ),
        "all_gap_requests_covered": all_covered,
        "readiness_rerun_authorized": False,
        "results": [rows[code] for code in sorted(rows)],
        "formal_acceptance_performed": False,
        "formal_assertion_count": 0,
        "formal_episode_count": 0,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }
