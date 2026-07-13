from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any, Mapping

from emperor_v4.evaluation.relation_fine_review import (
    COARSE_FINE_TYPES,
    build_fine_relation_worklist,
)


SCORING_RELATION_POLICY_VERSION = "relation-minimum-sufficient-scoring-v2"
SCORING_RELATION_SCHEMA_VERSION = "relation-scoring-arc-review-output-v2"

RELATION_DIRECTIONS = {
    "authority_change": frozenset(
        {"grant", "expand", "transfer", "reduce", "terminate", "restore"}
    ),
    "mandate_or_outcome": frozenset(
        {"mandate", "feedback", "result", "continuation"}
    ),
    "explicit_causal": frozenset({"cause_to_followup"}),
}

SCOPE_MATCHES = {
    "authority_change": frozenset(
        {
            "exact_office",
            "same_authority_domain",
            "same_mandate",
            "whole_person_status",
        }
    ),
    "mandate_or_outcome": frozenset({"same_mandate", "decision_to_result"}),
    "explicit_causal": frozenset({"explicit_causal_chain"}),
}

REVIEW_DECISIONS = frozenset(
    {"proposed_relation", "scoring_arc_only", "unresolved"}
)
SAME_SCORING_ARC_VALUES = frozenset({"yes", "no", "uncertain"})
RULER_RESPONSIBILITY_VALUES = frozenset(
    {"direct", "partial", "none", "uncertain"}
)
DIRECTNESS_VALUES = frozenset({"explicit", "strongly_implied", "trajectory_only"})
FINE_TYPE_STATUSES = frozenset(
    {"resolved", "not_required_for_scoring", "unresolved"}
)

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
                raise ValueError(f"Scoring Relation 输入包含禁止字段: {path}.{key}")
            _reject_forbidden(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_forbidden(value, f"{path}[{index}]")


def build_scoring_relation_worklist(
    endpoint_worklist: Mapping[str, Any], endpoint_final: Mapping[str, Any]
) -> dict[str, Any]:
    """把 endpoint direct proposals 转为评分最小充分审查输入。"""

    legacy = build_fine_relation_worklist(endpoint_worklist, endpoint_final)
    tasks = [
        {
            "candidate_code": task["candidate_code"],
            "dataset_code": task.get("dataset_code"),
            "relation_family": task["coarse_type"],
            "allowed_directions": sorted(RELATION_DIRECTIONS[task["coarse_type"]]),
            "allowed_scope_matches": sorted(SCOPE_MATCHES[task["coarse_type"]]),
            "optional_fine_types": sorted(COARSE_FINE_TYPES[task["coarse_type"]]),
            "left": task["left"],
            "right": task["right"],
        }
        for task in legacy["tasks"]
    ]
    basis = {
        "source_endpoint_task_code": endpoint_worklist.get("task_code"),
        "source_endpoint_worklist_sha256": endpoint_worklist.get("worklist_sha256"),
        "source_endpoint_final_sha256": legacy["endpoint_final_sha256"],
        "candidate_codes": [task["candidate_code"] for task in tasks],
        "scoring_relation_policy_version": SCORING_RELATION_POLICY_VERSION,
    }
    worklist_hash = _hash(basis)
    return {
        "schema_version": 1,
        "status": "scoring_relation_worklist_ready",
        "task_code": f"G3R-SCORING-{worklist_hash[:20].upper()}",
        "worklist_sha256": worklist_hash,
        **basis,
        "output_schema_version": SCORING_RELATION_SCHEMA_VERSION,
        "candidate_count": len(tasks),
        "tasks": tasks,
        "review_policy": {
            "decision_values": sorted(REVIEW_DECISIONS),
            "minimum_sufficient_rule": (
                "能够可靠支持皇帝归责、权责方向、结果与去重时，不得因 fine type 为空而阻断。"
            ),
            "relation_rule": (
                "仅在逐对边对评分归责、方向、结果、去重或追溯有直接用途时 proposed_relation。"
            ),
            "scoring_arc_rule": (
                "同一评分决策弧内有用但不值得逐对建边时 scoring_arc_only。"
            ),
        },
        "gold_accessed": False,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "formal_rule_evidence_unit_count": 0,
        "database_write_count": 0,
    }


def validate_scoring_relation_response(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Mapping[str, Any]]:
    _reject_forbidden(response)
    if (
        response.get("status") != "scoring_relation_reviews_complete"
        or response.get("task_code") != worklist.get("task_code")
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("scoring_relation_policy_version")
        != SCORING_RELATION_POLICY_VERSION
        or response.get("output_schema_version") != SCORING_RELATION_SCHEMA_VERSION
        or not str(response.get("reviewer") or "")
    ):
        raise ValueError("Scoring Relation response 与 worklist/policy/schema 不一致")
    if (
        response.get("reviewed_without_forbidden_inputs") is not True
        or response.get("gold_accessed") is not False
        or response.get("old_relation_review_accessed") is not False
        or response.get("formal_acceptance_performed") is not False
        or response.get("database_write_count") != 0
    ):
        raise ValueError("Scoring Relation reviewer 未声明完整隔离与零副作用")

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
        raise ValueError("Scoring Relation reviewer 未完整且唯一覆盖候选")

    for code, task in task_by_code.items():
        row = result_by_code[code]
        decision = row.get("decision")
        if decision not in REVIEW_DECISIONS:
            raise ValueError("Scoring Relation decision 非法")
        if row.get("same_scoring_arc") not in SAME_SCORING_ARC_VALUES:
            raise ValueError("same_scoring_arc 非法")
        if row.get("ruler_responsibility") not in RULER_RESPONSIBILITY_VALUES:
            raise ValueError("ruler_responsibility 非法")
        if row.get("evidence_directness") not in DIRECTNESS_VALUES:
            raise ValueError("evidence_directness 非法")
        if row.get("fine_type_status") not in FINE_TYPE_STATUSES:
            raise ValueError("fine_type_status 非法")
        if not str(row.get("reason") or "").strip():
            raise ValueError("Scoring Relation review 缺少 reason")
        confidence = row.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
            raise ValueError("Scoring Relation confidence 必须在 0 到 1 之间")

        evidence_refs = tuple(str(ref) for ref in row.get("evidence_assertion_refs") or ())
        if not evidence_refs or len(evidence_refs) != len(set(evidence_refs)):
            raise ValueError("Scoring Relation evidence refs 缺失或重复")
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
            raise ValueError("Scoring Relation evidence 必须只引用且覆盖两端")

        family = row.get("relation_family")
        direction = row.get("relation_direction")
        scope = row.get("scope_match")
        fine_type = row.get("fine_type")
        fine_status = row.get("fine_type_status")
        source = row.get("from_episode_ref")
        target = row.get("to_episode_ref")
        if decision == "unresolved":
            if row.get("same_scoring_arc") != "uncertain":
                raise ValueError("unresolved 必须声明 same_scoring_arc=uncertain")
            if any(value is not None for value in (family, direction, scope, fine_type, source, target)):
                raise ValueError("unresolved 不得声明关系或评分弧语义")
            if fine_status != "unresolved":
                raise ValueError("unresolved 必须声明 fine_type_status=unresolved")
            continue

        if row.get("same_scoring_arc") != "yes":
            raise ValueError("resolved scoring candidate 必须属于同一评分弧")
        if family != task["relation_family"]:
            raise ValueError("relation_family 与 endpoint coarse proposal 不一致")
        if direction not in set(task["allowed_directions"]):
            raise ValueError("relation_direction 与 relation_family 不兼容")
        if scope not in set(task["allowed_scope_matches"]):
            raise ValueError("scope_match 与 relation_family 不兼容")
        if fine_status == "resolved":
            if fine_type not in set(task["optional_fine_types"]):
                raise ValueError("resolved fine_type 非法或与 family 不兼容")
        elif fine_status == "not_required_for_scoring":
            if fine_type is not None:
                raise ValueError("not_required_for_scoring 时 fine_type 必须为 null")
        else:
            raise ValueError("resolved scoring candidate 的 fine_type_status 非法")

        if decision == "proposed_relation":
            endpoints = {
                str(task["left"]["episode_ref"]),
                str(task["right"]["episode_ref"]),
            }
            if {str(source), str(target)} != endpoints or source == target:
                raise ValueError("proposed_relation 必须精确覆盖两个 endpoint")
            if row.get("unit_member_roles") not in (None, [], ()):
                raise ValueError("proposed_relation 不得声明 unit_member_roles")
        else:
            if source is not None or target is not None:
                raise ValueError("scoring_arc_only 不得伪造有向 Relation")
            roles = tuple(str(value).strip() for value in row.get("unit_member_roles") or ())
            if len(roles) != 2 or not all(roles):
                raise ValueError("scoring_arc_only 必须声明两个成员角色")
    return result_by_code


def _has_path(adjacency: Mapping[str, set[str]], source: str, target: str) -> bool:
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


def _episode_version_ref(endpoint: Mapping[str, Any]) -> str:
    episode_ref = str(endpoint.get("episode_ref") or "")
    version_ref = str(endpoint.get("episode_version_ref") or "")
    semantic_version = endpoint.get("semantic_version")
    if (
        not episode_ref
        or not isinstance(semantic_version, int)
        or semantic_version < 1
        or version_ref != f"{episode_ref}@v{semantic_version}"
    ):
        raise ValueError("Scoring Relation endpoint 缺少一致的 Episode 版本身份")
    if not str(endpoint.get("episode_semantic_fingerprint") or ""):
        raise ValueError("Scoring Relation endpoint 缺少 semantic fingerprint")
    return version_ref


def materialize_scoring_relation_slice(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Any]:
    """构造只读 Relation proposals 与 RuleEvidenceUnit 成员建议。"""

    rows = validate_scoring_relation_response(worklist, response)
    task_by_code = {
        str(task["candidate_code"]): task for task in worklist.get("tasks") or ()
    }
    relation_proposals = []
    arc_memberships = []
    unresolved = []
    for code in sorted(task_by_code):
        task = task_by_code[code]
        row = rows[code]
        if row["decision"] == "unresolved":
            unresolved.append({"candidate_code": code, "reason": row["reason"]})
            continue
        passage_by_assertion = {
            str(assertion["assertion_ref"]): str(assertion["source_passage_ref"])
            for side in (task["left"], task["right"])
            for assertion in side["assertions"]
        }
        evidence_links = [
            {
                "assertion_ref": ref,
                "source_passage_ref": passage_by_assertion[ref],
                "evidence_status": "draft",
            }
            for ref in row["evidence_assertion_refs"]
        ]
        semantic = {
            "relation_family": row["relation_family"],
            "relation_direction": row["relation_direction"],
            "scope_match": row["scope_match"],
            "fine_type": row["fine_type"],
            "ruler_responsibility": row["ruler_responsibility"],
            "evidence_directness": row["evidence_directness"],
        }
        if row["decision"] == "proposed_relation":
            endpoint_by_ref = {
                str(task["left"]["episode_ref"]): task["left"],
                str(task["right"]["episode_ref"]): task["right"],
            }
            identity = {
                "from_episode_version_ref": _episode_version_ref(
                    endpoint_by_ref[str(row["from_episode_ref"])]
                ),
                "to_episode_version_ref": _episode_version_ref(
                    endpoint_by_ref[str(row["to_episode_ref"])]
                ),
                **semantic,
            }
            fingerprint = _hash(identity)
            relation_proposals.append(
                {
                    "scoring_relation_proposal_id": f"SRP-{fingerprint[:20].upper()}",
                    **identity,
                    "semantic_fingerprint": fingerprint,
                    "semantic_version": 1,
                    "evidence_version": 1,
                    "proposal_status": "proposed",
                    "fine_type_status": row["fine_type_status"],
                    "same_scoring_arc": row["same_scoring_arc"],
                    "evidence_links": evidence_links,
                    "confidence": float(row["confidence"]),
                    "lineage": {"candidate_code": code},
                }
            )
        else:
            endpoints = [
                _episode_version_ref(task["left"]),
                _episode_version_ref(task["right"]),
            ]
            identity = {
                "rule_code": "appointment_delegation",
                "episode_version_refs": endpoints,
                "unit_member_roles": list(row["unit_member_roles"]),
                **semantic,
            }
            fingerprint = _hash(identity)
            arc_memberships.append(
                {
                    "scoring_arc_membership_id": f"SAM-{fingerprint[:20].upper()}",
                    **identity,
                    "semantic_fingerprint": fingerprint,
                    "proposal_status": "proposal_only",
                    "fine_type_status": row["fine_type_status"],
                    "same_scoring_arc": row["same_scoring_arc"],
                    "evidence_links": evidence_links,
                    "confidence": float(row["confidence"]),
                    "lineage": {"candidate_code": code},
                }
            )

    invariant_errors = []
    identities = [
        row["semantic_fingerprint"] for row in relation_proposals + arc_memberships
    ]
    if len(identities) != len(set(identities)):
        invariant_errors.append("duplicate_semantic_identity")
    adjacency: dict[str, set[str]] = defaultdict(set)
    for proposal in relation_proposals:
        source = str(proposal["from_episode_version_ref"])
        target = str(proposal["to_episode_version_ref"])
        if _has_path(adjacency, target, source):
            invariant_errors.append("directed_cycle")
        adjacency[source].add(target)

    decision_counts = Counter(row["decision"] for row in rows.values())
    family_counts = Counter(
        str(row["relation_family"])
        for row in rows.values()
        if row["decision"] != "unresolved"
    )
    gate_passed = not unresolved and not invariant_errors
    return {
        "schema_version": 1,
        "status": (
            "minimum_sufficient_relation_slice_passed"
            if gate_passed
            else "minimum_sufficient_relation_slice_failed_closed"
        ),
        "task_code": worklist.get("task_code"),
        "candidate_count": len(task_by_code),
        "decision_counts": dict(sorted(decision_counts.items())),
        "relation_family_counts": dict(sorted(family_counts.items())),
        "scoring_relation_proposal_count": len(relation_proposals),
        "scoring_arc_only_count": len(arc_memberships),
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
        "invariant_errors": sorted(set(invariant_errors)),
        "graph_invariants_passed": not invariant_errors,
        "minimum_sufficient_gate_passed": gate_passed,
        "scoring_relation_proposals": relation_proposals,
        "scoring_arc_memberships": arc_memberships,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "formal_rule_evidence_unit_count": 0,
        "database_write_count": 0,
    }
