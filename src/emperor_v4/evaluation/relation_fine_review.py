from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any, Mapping

from emperor_v4.contracts.boundary import EPISODE_RELATION_TYPES


FINE_RELATION_POLICY_VERSION = "relation-fine-type-v2"
FINE_RELATION_REVIEW_SCHEMA_VERSION = "relation-fine-type-review-output-v2"
FINE_RELATION_GAP_SCHEMA_VERSION = "relation-fine-type-gap-review-output-v2"

COARSE_FINE_TYPES = {
    "authority_change": frozenset(
        {"revokes", "renews_authority", "promotion_after"}
    ),
    "mandate_or_outcome": frozenset(
        {"outcome_of", "same_mandate_phase", "continues"}
    ),
    "explicit_causal": frozenset({"causal_followup"}),
}

_ACYCLIC_RELATION_TYPES = EPISODE_RELATION_TYPES - {"context_for"}
_FORBIDDEN_KEYS = frozenset(
    {
        "historical_gold",
        "relation_gold",
        "gold_relations",
        "old_relation_review",
        "score",
        "scores",
        "formal_acceptance",
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
                raise ValueError(f"Fine Relation 输入包含禁止字段: {path}.{key}")
            _reject_forbidden(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_forbidden(value, f"{path}[{index}]")


def build_fine_relation_worklist(
    endpoint_worklist: Mapping[str, Any],
    endpoint_final: Mapping[str, Any],
) -> dict[str, Any]:
    """只把 endpoint Gate 后的 direct proposals 封装为细类型送审输入。"""

    _reject_forbidden(endpoint_worklist)
    _reject_forbidden(endpoint_final)
    if (
        endpoint_final.get("status")
        != "endpoint_agreement_gate_passed_after_adjudication"
        or endpoint_final.get("agreement_gate_passed") is not True
        or endpoint_final.get("source_task_code") != endpoint_worklist.get("task_code")
        or endpoint_final.get("formal_acceptance_performed") is not False
        or endpoint_final.get("formal_relation_count") != 0
        or endpoint_final.get("database_write_count") != 0
    ):
        raise ValueError("Fine Relation 输入未通过 endpoint Gate 或越过副作用边界")

    endpoint_tasks = {
        str(task.get("candidate_code") or ""): task
        for task in endpoint_worklist.get("tasks") or ()
    }
    proposals = tuple(endpoint_final.get("final_proposals") or ())
    proposal_by_code = {
        str(row.get("candidate_code") or ""): row for row in proposals
    }
    if (
        "" in endpoint_tasks
        or "" in proposal_by_code
        or len(endpoint_tasks) != len(endpoint_worklist.get("tasks") or ())
        or len(proposal_by_code) != len(proposals)
        or set(endpoint_tasks) != set(proposal_by_code)
    ):
        raise ValueError("Fine Relation 输入未完整且唯一覆盖 endpoint 候选")

    tasks = []
    for code in sorted(endpoint_tasks):
        proposal = proposal_by_code[code]
        if proposal.get("proposed_disposition") != "proposed_direct_relation":
            continue
        coarse_type = proposal.get("coarse_type")
        if coarse_type not in COARSE_FINE_TYPES:
            raise ValueError("direct proposal 缺少合法 coarse type")
        endpoint_task = endpoint_tasks[code]
        tasks.append(
            {
                "candidate_code": code,
                "dataset_code": endpoint_task.get("dataset_code"),
                "coarse_type": coarse_type,
                "allowed_relation_types": sorted(COARSE_FINE_TYPES[coarse_type]),
                "left": endpoint_task["left"],
                "right": endpoint_task["right"],
            }
        )
    expected_direct = int(
        (endpoint_final.get("proposal_counts") or {}).get(
            "proposed_direct_relation", -1
        )
    )
    if not tasks or len(tasks) != expected_direct:
        raise ValueError("Fine Relation direct proposal 计数不一致")

    basis = {
        "source_task_code": endpoint_worklist.get("task_code"),
        "source_worklist_sha256": endpoint_worklist.get("worklist_sha256"),
        "endpoint_final_sha256": _hash(endpoint_final),
        "candidate_codes": [task["candidate_code"] for task in tasks],
        "fine_relation_policy_version": FINE_RELATION_POLICY_VERSION,
    }
    worklist_hash = _hash(basis)
    return {
        "schema_version": 1,
        "status": "fine_relation_worklist_ready",
        "task_code": f"G3R-FINE-{worklist_hash[:20].upper()}",
        "worklist_sha256": worklist_hash,
        "source_task_code": endpoint_worklist.get("task_code"),
        "source_worklist_sha256": endpoint_worklist.get("worklist_sha256"),
        "endpoint_final_sha256": basis["endpoint_final_sha256"],
        "fine_relation_policy_version": FINE_RELATION_POLICY_VERSION,
        "output_schema_version": FINE_RELATION_REVIEW_SCHEMA_VERSION,
        "candidate_count": len(tasks),
        "tasks": tasks,
        "review_policy": {
            "decision_values": ["proposed_relation", "unresolved"],
            "direction_rule": "从较早授权、命令、原因或状态指向后续变化、结果或后果。",
            "fail_closed_rule": "证据不足以在 coarse 允许集合内唯一确定方向和细类型时必须 unresolved。",
        },
        "gold_accessed": False,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "database_write_count": 0,
    }


def validate_fine_relation_response(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    *,
    expected_reviewer: str | None = None,
) -> dict[str, Mapping[str, Any]]:
    _reject_forbidden(response)
    reviewer = str(response.get("reviewer") or "")
    if not reviewer or (expected_reviewer is not None and reviewer != expected_reviewer):
        raise ValueError("Fine Relation reviewer 身份缺失或不匹配")
    if (
        response.get("status") != "fine_relation_reviews_complete"
        or response.get("task_code") != worklist.get("task_code")
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("fine_relation_policy_version")
        != FINE_RELATION_POLICY_VERSION
        or response.get("output_schema_version")
        != FINE_RELATION_REVIEW_SCHEMA_VERSION
    ):
        raise ValueError("Fine Relation response 与 worklist/policy/schema 不一致")
    if (
        response.get("reviewed_without_forbidden_inputs") is not True
        or response.get("gold_accessed") is not False
        or response.get("old_relation_review_accessed") is not False
        or response.get("formal_acceptance_performed") is not False
        or response.get("database_write_count") != 0
    ):
        raise ValueError("Fine Relation reviewer 未声明完整隔离与零副作用")

    task_by_code = {
        str(task["candidate_code"]): task for task in worklist.get("tasks") or ()
    }
    results = tuple(response.get("results") or ())
    result_by_code = {
        str(row.get("candidate_code") or ""): row for row in results
    }
    if (
        "" in result_by_code
        or len(result_by_code) != len(results)
        or set(result_by_code) != set(task_by_code)
    ):
        raise ValueError("Fine Relation reviewer 未完整且唯一覆盖候选")

    for code, task in task_by_code.items():
        row = result_by_code[code]
        decision = row.get("decision")
        if decision not in {"proposed_relation", "unresolved"}:
            raise ValueError("Fine Relation decision 非法")
        if not str(row.get("reason") or "").strip():
            raise ValueError("Fine Relation review 缺少 reason")
        evidence_refs = tuple(str(ref) for ref in row.get("evidence_assertion_refs") or ())
        if not evidence_refs or len(evidence_refs) != len(set(evidence_refs)):
            raise ValueError("Fine Relation evidence refs 缺失或重复")
        left_refs = {
            str(item["assertion_ref"]) for item in task["left"]["assertions"]
        }
        right_refs = {
            str(item["assertion_ref"]) for item in task["right"]["assertions"]
        }
        if (
            not set(evidence_refs) <= left_refs | right_refs
            or not set(evidence_refs) & left_refs
            or not set(evidence_refs) & right_refs
        ):
            raise ValueError("Fine Relation evidence 必须只引用且覆盖两端")

        relation_type = row.get("relation_type")
        source = row.get("from_episode_ref")
        target = row.get("to_episode_ref")
        confidence = row.get("confidence")
        if decision == "unresolved":
            if relation_type is not None or source is not None or target is not None:
                raise ValueError("unresolved 不得声明方向或 relation_type")
            if confidence is not None:
                raise ValueError("unresolved 不得声明 confidence")
            continue
        if relation_type not in set(task["allowed_relation_types"]):
            raise ValueError("Fine Relation type 与 coarse proposal 不兼容")
        endpoints = {str(task["left"]["episode_ref"]), str(task["right"]["episode_ref"])}
        if {str(source), str(target)} != endpoints or source == target:
            raise ValueError("Fine Relation 方向必须精确覆盖两个 endpoint")
        if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
            raise ValueError("Fine Relation confidence 必须在 0 到 1 之间")
    return result_by_code


def _has_path(
    adjacency: Mapping[str, set[str]], source: str, target: str
) -> bool:
    pending = [source]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency.get(current, ()))
    return False


def _episode_ref(endpoint: Mapping[str, Any]) -> str:
    episode_ref = str(endpoint.get("episode_ref") or "")
    if not episode_ref:
        raise ValueError("Fine Relation endpoint 缺少 Episode 身份")
    if not str(endpoint.get("episode_semantic_fingerprint") or ""):
        raise ValueError("Fine Relation endpoint 缺少 semantic fingerprint")
    return episode_ref


def materialize_fine_relation_proposals(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Any]:
    """构造只读 proposal 图并检查身份、lineage、方向、环和纯传递冗余。"""

    rows = validate_fine_relation_response(worklist, response)
    task_by_code = {
        str(task["candidate_code"]): task for task in worklist.get("tasks") or ()
    }
    proposals = []
    unresolved = []
    for code in sorted(task_by_code):
        task = task_by_code[code]
        row = rows[code]
        if row["decision"] == "unresolved":
            unresolved.append(
                {"candidate_code": code, "reason": row["reason"]}
            )
            continue
        source = str(row["from_episode_ref"])
        target = str(row["to_episode_ref"])
        relation_type = str(row["relation_type"])
        endpoint_by_ref = {
            str(task["left"]["episode_ref"]): task["left"],
            str(task["right"]["episode_ref"]): task["right"],
        }
        identity = {
            "from_episode_ref": _episode_ref(endpoint_by_ref[source]),
            "to_episode_ref": _episode_ref(endpoint_by_ref[target]),
            "relation_type": relation_type,
        }
        semantic_fingerprint = _hash(identity)
        passage_by_assertion = {
            str(assertion["assertion_ref"]): str(assertion["source_passage_ref"])
            for side in (task["left"], task["right"])
            for assertion in side["assertions"]
        }
        proposals.append(
            {
                "relation_id": f"ER-{semantic_fingerprint[:20].upper()}",
                **identity,
                "semantic_fingerprint": semantic_fingerprint,
                "relation_status": "proposed",
                "evidence_links": [
                    {
                        "assertion_ref": ref,
                        "source_passage_ref": passage_by_assertion[ref],
                        "evidence_status": "draft",
                    }
                    for ref in row["evidence_assertion_refs"]
                ],
                "confidence": float(row["confidence"]),
                "lineage": {
                    "candidate_code": code,
                    "source_endpoint_task_code": str(worklist["source_task_code"]),
                },
                "provenance": {
                    "fine_relation_policy_version": FINE_RELATION_POLICY_VERSION,
                    "fine_worklist_sha256": str(worklist["worklist_sha256"]),
                    "reviewer": str(response["reviewer"]),
                },
            }
        )

    invariant_errors = []
    ids = [row["relation_id"] for row in proposals]
    fingerprints = [row["semantic_fingerprint"] for row in proposals]
    if len(ids) != len(set(ids)) or len(fingerprints) != len(set(fingerprints)):
        invariant_errors.append("duplicate_relation_identity")

    combined_adjacency: dict[str, set[str]] = defaultdict(set)
    adjacency_by_type: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for proposal in proposals:
        relation_type = str(proposal["relation_type"])
        if relation_type not in _ACYCLIC_RELATION_TYPES:
            continue
        source = str(proposal["from_episode_ref"])
        target = str(proposal["to_episode_ref"])
        if _has_path(combined_adjacency, target, source):
            invariant_errors.append("directed_cycle:temporal_or_causal")
        combined_adjacency[source].add(target)
        adjacency_by_type[relation_type][source].add(target)
    for relation_type, adjacency in adjacency_by_type.items():
        for source, targets in tuple(adjacency.items()):
            for target in tuple(targets):
                adjacency[source].remove(target)
                if _has_path(adjacency, source, target):
                    invariant_errors.append(f"transitive_redundancy:{relation_type}")
                adjacency[source].add(target)

    type_counts = Counter(str(row["relation_type"]) for row in proposals)
    graph_gate_passed = not unresolved and not invariant_errors
    return {
        "schema_version": 1,
        "status": (
            "fine_relation_graph_gate_passed"
            if graph_gate_passed
            else "fine_relation_graph_gate_failed_closed"
        ),
        "task_code": worklist.get("task_code"),
        "worklist_sha256": worklist.get("worklist_sha256"),
        "candidate_count": len(task_by_code),
        "proposed_relation_count": len(proposals),
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
        "relation_type_counts": dict(sorted(type_counts.items())),
        "invariant_errors": sorted(set(invariant_errors)),
        "graph_invariants_passed": not invariant_errors,
        "fine_relation_graph_gate_passed": graph_gate_passed,
        "relation_proposals": proposals,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "database_write_count": 0,
    }


def build_fine_relation_gap_worklist(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Any]:
    """只把 unresolved fine-type 项封装为 SourcePassage 定向核对输入。"""

    rows = validate_fine_relation_response(worklist, response)
    task_by_code = {
        str(task["candidate_code"]): task for task in worklist.get("tasks") or ()
    }
    tasks = [
        {
            **task_by_code[code],
            "original_unresolved_reason": rows[code]["reason"],
        }
        for code in sorted(task_by_code)
        if rows[code]["decision"] == "unresolved"
    ]
    if not tasks:
        raise ValueError("Fine Relation 没有需要补证核对的 unresolved 项")
    basis = {
        "source_worklist_sha256": worklist.get("worklist_sha256"),
        "source_response_sha256": _hash(response),
        "candidate_codes": [task["candidate_code"] for task in tasks],
        "fine_relation_policy_version": FINE_RELATION_POLICY_VERSION,
    }
    worklist_hash = _hash(basis)
    return {
        "schema_version": 1,
        "status": "fine_relation_gap_worklist_ready",
        "task_code": f"G3R-FINE-GAP-{worklist_hash[:20].upper()}",
        "worklist_sha256": worklist_hash,
        "source_task_code": worklist.get("task_code"),
        "source_worklist_sha256": worklist.get("worklist_sha256"),
        "source_response_sha256": basis["source_response_sha256"],
        "fine_relation_policy_version": FINE_RELATION_POLICY_VERSION,
        "output_schema_version": FINE_RELATION_GAP_SCHEMA_VERSION,
        "candidate_count": len(tasks),
        "tasks": tasks,
        "review_policy": {
            "decision_values": [
                "evidence_sufficient",
                "additional_source_required",
            ],
            "rule": "只核对两端现有 SourcePassage 上下文；不足时保留 unresolved，不得用 Gold、旧 Relation 或 score 补型。",
        },
        "gold_accessed": False,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "database_write_count": 0,
    }


def validate_fine_relation_gap_response(
    gap_worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Mapping[str, Any]]:
    _reject_forbidden(response)
    if (
        response.get("status") != "fine_relation_gap_reviews_complete"
        or response.get("task_code") != gap_worklist.get("task_code")
        or response.get("worklist_sha256") != gap_worklist.get("worklist_sha256")
        or response.get("fine_relation_policy_version")
        != FINE_RELATION_POLICY_VERSION
        or response.get("output_schema_version") != FINE_RELATION_GAP_SCHEMA_VERSION
        or not str(response.get("reviewer") or "")
    ):
        raise ValueError("Fine Relation gap response 与 worklist/policy/schema 不一致")
    if (
        response.get("reviewed_without_forbidden_inputs") is not True
        or response.get("gold_accessed") is not False
        or response.get("old_relation_review_accessed") is not False
        or response.get("formal_acceptance_performed") is not False
        or response.get("database_write_count") != 0
    ):
        raise ValueError("Fine Relation gap reviewer 未声明完整隔离与零副作用")

    task_by_code = {
        str(task["candidate_code"]): task
        for task in gap_worklist.get("tasks") or ()
    }
    results = tuple(response.get("results") or ())
    result_by_code = {
        str(row.get("candidate_code") or ""): row for row in results
    }
    if (
        "" in result_by_code
        or len(result_by_code) != len(results)
        or set(result_by_code) != set(task_by_code)
    ):
        raise ValueError("Fine Relation gap reviewer 未完整且唯一覆盖候选")

    for code, task in task_by_code.items():
        row = result_by_code[code]
        decision = row.get("decision")
        if decision not in {"evidence_sufficient", "additional_source_required"}:
            raise ValueError("Fine Relation gap decision 非法")
        if not str(row.get("reason") or "").strip():
            raise ValueError("Fine Relation gap review 缺少 reason")
        passage_refs = tuple(
            str(ref) for ref in row.get("evidence_source_passage_refs") or ()
        )
        if not passage_refs or len(passage_refs) != len(set(passage_refs)):
            raise ValueError("Fine Relation gap passage refs 缺失或重复")
        left_passages = {
            str(item["source_passage_ref"])
            for item in task["left"]["source_passages"]
        }
        right_passages = {
            str(item["source_passage_ref"])
            for item in task["right"]["source_passages"]
        }
        if (
            not set(passage_refs) <= left_passages | right_passages
            or not set(passage_refs) & left_passages
            or not set(passage_refs) & right_passages
        ):
            raise ValueError("Fine Relation gap evidence 必须只引用且覆盖两端 Passage")

        relation_type = row.get("relation_type")
        source = row.get("from_episode_ref")
        target = row.get("to_episode_ref")
        confidence = row.get("confidence")
        if decision == "additional_source_required":
            if relation_type is not None or source is not None or target is not None:
                raise ValueError("additional_source_required 不得声明方向或类型")
            if confidence is not None:
                raise ValueError("additional_source_required 不得声明 confidence")
            continue
        if relation_type not in set(task["allowed_relation_types"]):
            raise ValueError("Fine Relation gap type 与 coarse proposal 不兼容")
        endpoints = {
            str(task["left"]["episode_ref"]),
            str(task["right"]["episode_ref"]),
        }
        if {str(source), str(target)} != endpoints or source == target:
            raise ValueError("Fine Relation gap 方向必须精确覆盖两个 endpoint")
        if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
            raise ValueError("Fine Relation gap confidence 必须在 0 到 1 之间")
    return result_by_code


def apply_fine_relation_gap_review(
    worklist: Mapping[str, Any],
    original_response: Mapping[str, Any],
    gap_worklist: Mapping[str, Any],
    gap_response: Mapping[str, Any],
) -> dict[str, Any]:
    """只用 gap review 替换可解 unresolved，再重跑完整 proposal 图审计。"""

    original_rows = validate_fine_relation_response(worklist, original_response)
    gap_rows = validate_fine_relation_gap_response(gap_worklist, gap_response)
    expected_gap_codes = {
        code for code, row in original_rows.items() if row["decision"] == "unresolved"
    }
    if (
        gap_worklist.get("source_task_code") != worklist.get("task_code")
        or gap_worklist.get("source_worklist_sha256")
        != worklist.get("worklist_sha256")
        or gap_worklist.get("source_response_sha256") != _hash(original_response)
        or set(gap_rows) != expected_gap_codes
    ):
        raise ValueError("Fine Relation gap worklist 与原审查绑定不一致")

    revised_results = []
    resolved_count = 0
    for row in original_response.get("results") or ():
        code = str(row["candidate_code"])
        gap = gap_rows.get(code)
        if gap is None:
            revised_results.append(dict(row))
            continue
        if gap["decision"] == "evidence_sufficient":
            resolved_count += 1
            revised_results.append(
                {
                    "candidate_code": code,
                    "decision": "proposed_relation",
                    "from_episode_ref": gap["from_episode_ref"],
                    "to_episode_ref": gap["to_episode_ref"],
                    "relation_type": gap["relation_type"],
                    "evidence_assertion_refs": list(row["evidence_assertion_refs"]),
                    "confidence": gap["confidence"],
                    "reason": gap["reason"],
                }
            )
        else:
            revised_results.append(
                {
                    **dict(row),
                    "reason": gap["reason"],
                }
            )
    revised_response = {
        **dict(original_response),
        "reviewer": f"{original_response['reviewer']}+{gap_response['reviewer']}",
        "results": revised_results,
    }
    report = materialize_fine_relation_proposals(worklist, revised_response)
    return {
        **report,
        "status": (
            "fine_relation_graph_gate_passed_after_gap_review"
            if report["fine_relation_graph_gate_passed"]
            else "fine_relation_graph_gate_failed_closed_after_gap_review"
        ),
        "gap_candidate_count": len(gap_rows),
        "gap_resolved_count": resolved_count,
        "additional_source_required_count": len(gap_rows) - resolved_count,
        "gap_task_code": gap_worklist.get("task_code"),
        "gap_reviewer": gap_response.get("reviewer"),
    }
