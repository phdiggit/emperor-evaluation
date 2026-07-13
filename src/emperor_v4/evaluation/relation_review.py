from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from itertools import combinations
from typing import Any, Mapping

from emperor_v4.contracts.boundary import EPISODE_RELATION_TYPES


RELATION_POLICY_VERSION = "episode-relation-policy-v2"
RELATION_REVIEW_SCHEMA_VERSION = "episode-relation-review-v1"
RELATION_SEMANTIC_POLICY = {
    "selection_rule": (
        "Only emit a relation when the supplied endpoint evidence establishes a "
        "direct state-transition, mandate, consequence, or causal link. Shared "
        "person, ruler, time, office, or topic alone is distinct_unrelated."
    ),
    "direction_rule": (
        "Direct the edge from the earlier grant/order/cause/state to the later "
        "continuation/change/result/consequence."
    ),
    "minimal_graph_rule": (
        "Do not add a merely transitive edge when an existing direct path fully "
        "expresses the same relation, unless the source independently states the "
        "non-adjacent direct link."
    ),
    "type_precedence": [
        {
            "relation_type": "revokes",
            "rule": (
                "The target withdraws, reduces, suspends, accepts resignation "
                "from, demotes, or terminates authority held or granted in the source."
            ),
        },
        {
            "relation_type": "renews_authority",
            "rule": (
                "The target is a reappointment, additional office, promotion, "
                "transfer, broadened remit, or materially renewed authorization for "
                "the same focal person after the source authority state."
            ),
        },
        {
            "relation_type": "outcome_of",
            "rule": (
                "The target is the directly reported result or feedback of the "
                "source action and does not introduce an independent decision."
            ),
        },
        {
            "relation_type": "causal_followup",
            "rule": (
                "The source causes, motivates, enables, or forms the explicit stage "
                "basis for a distinct later decision, action, or consequence."
            ),
        },
        {
            "relation_type": "same_mandate_phase",
            "rule": (
                "Both episodes are distinct actions, advice, or feedback inside one "
                "continuing mandate, without a new authority grant, revocation, or "
                "direct causal transition between them."
            ),
        },
        {
            "relation_type": "continues",
            "rule": (
                "The target resumes, carries forward, delivers, or completes the "
                "same already-issued order or action, with no new authorization or "
                "independent decision."
            ),
        },
        {
            "relation_type": "promotion_after",
            "rule": (
                "Use only for explicit career/rank chronology that is not a renewed "
                "mandate, transfer of authority, or causal responsibility chain."
            ),
        },
        {
            "relation_type": "context_for",
            "rule": (
                "The source episode is explicit background needed to interpret the "
                "target but is not part of its mandate, result, or causal chain."
            ),
        },
    ],
}
_ACYCLIC_RELATION_TYPES = frozenset(
    {
        "continues",
        "same_mandate_phase",
        "promotion_after",
        "renews_authority",
        "revokes",
        "outcome_of",
        "causal_followup",
    }
)
_FORBIDDEN_KEYS = frozenset(
    {
        "episode_code",
        "gold_boundary",
        "gold_linkage",
        "historical_gold",
        "must_merge",
        "must_not_merge",
        "expected_participants",
        "acceptance_decision",
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
            if (
                (normalized == "gold_fields_detected" and value == 0)
                or (normalized == "gold_accessed" and value is False)
            ):
                continue
            if normalized in _FORBIDDEN_KEYS or normalized.startswith("gold_"):
                raise ValueError(f"Relation review 输入包含禁止字段: {path}.{key}")
            _reject_forbidden(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_forbidden(value, f"{path}[{index}]")


def _episode_basis(candidate_graph: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dataset_code": candidate_graph.get("dataset_code"),
        "input_sha256": candidate_graph.get("input_sha256"),
        "episode_groups": candidate_graph.get("episode_groups") or (),
        "assertion_dispositions": candidate_graph.get("assertion_dispositions") or (),
    }


def _review_evidence(
    episode_rows: tuple[Mapping[str, Any], ...],
    blind_input: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    expected_hash = _hash(blind_input)
    assertion_by_ref = {
        str(item.get("assertion_code") or ""): item
        for item in blind_input.get("assertions") or ()
    }
    passage_by_ref = {
        str(item.get("passage_code") or ""): item
        for item in blind_input.get("source_passages") or ()
    }
    if not assertion_by_ref or not passage_by_ref:
        raise ValueError("Relation review blind input 缺少 Assertion/Passage")

    evidence = {}
    for episode in episode_rows:
        code = str(episode["local_episode_code"])
        rows = []
        passages = {}
        for assertion_ref in episode.get("core_assertion_refs") or ():
            assertion_ref = str(assertion_ref)
            assertion = assertion_by_ref.get(assertion_ref)
            if assertion is None:
                raise ValueError("Relation review Episode 引用了 blind input 外的 Assertion")
            passage_ref = str(assertion.get("source_passage_ref") or "")
            passage = passage_by_ref.get(passage_ref)
            if passage is None:
                raise ValueError("Relation review Assertion 缺少 SourcePassage lineage")
            qualifiers = assertion.get("qualifiers") or {}
            rows.append(
                {
                    "assertion_ref": assertion_ref,
                    "subject": assertion.get("subject"),
                    "predicate": assertion.get("predicate"),
                    "object": assertion.get("object"),
                    "time_expression": assertion.get("time_expression"),
                    "location_expression": assertion.get("location_expression"),
                    "polarity": assertion.get("polarity"),
                    "claim_summary": qualifiers.get("claim_summary"),
                    "normalized_time": qualifiers.get("normalized_time"),
                    "outcome": qualifiers.get("outcome"),
                    "responsibility_family": qualifiers.get(
                        "responsibility_family"
                    ),
                    "source_passage_ref": passage_ref,
                }
            )
            passages[passage_ref] = {
                "source_passage_ref": passage_ref,
                "document_code": passage.get("document_code"),
                "section_heading": passage.get("section_heading"),
                "locator": passage.get("locator"),
                "context_before": passage.get("context_before"),
                "raw_text": passage.get("raw_text"),
                "context_after": passage.get("context_after"),
            }
        evidence[code] = {
            "assertions": sorted(rows, key=lambda item: item["assertion_ref"]),
            "source_passages": sorted(
                passages.values(), key=lambda item: item["source_passage_ref"]
            ),
        }
    return {"input_sha256": expected_hash, "by_episode": evidence}


def build_relation_review_plan(
    candidate_graph: Mapping[str, Any],
    blind_input: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _reject_forbidden(candidate_graph)
    if blind_input is not None:
        _reject_forbidden(blind_input)
    episode_rows = tuple(candidate_graph.get("episode_groups") or ())
    if not episode_rows:
        raise ValueError("Relation review plan 需要非空 Episode graph")
    episode_by_code = {}
    by_context: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in episode_rows:
        code = str(row.get("local_episode_code") or "")
        context = str(row.get("evaluation_context") or "")
        if not code or code in episode_by_code or not context:
            raise ValueError("Relation review episode code/context 缺失或重复")
        episode_by_code[code] = row
        by_context[context].append(row)

    basis_hash = _hash(_episode_basis(candidate_graph))
    evidence = (
        _review_evidence(episode_rows, blind_input)
        if blind_input is not None
        else None
    )
    if evidence is not None and evidence["input_sha256"] != candidate_graph.get(
        "input_sha256"
    ):
        raise ValueError("Relation review blind input 与 Candidate graph hash 不一致")
    evidence_hash = _hash(evidence) if evidence is not None else None
    units = []
    for context, rows in sorted(by_context.items()):
        rows = sorted(rows, key=lambda item: str(item["local_episode_code"]))
        episode_refs = tuple(str(item["local_episode_code"]) for item in rows)
        cache_key = _hash(
            {
                "evaluation_context": context,
                "episode_semantic_fingerprints": sorted(
                    str(item.get("semantic_fingerprint") or "") for item in rows
                ),
                "relation_policy_version": RELATION_POLICY_VERSION,
                "relation_review_schema_version": RELATION_REVIEW_SCHEMA_VERSION,
            }
        )
        units.append(
            {
                "review_unit_code": f"RRU-{cache_key[:20].upper()}",
                "cache_key": cache_key,
                "evaluation_context": context,
                "episode_refs": list(episode_refs),
                "episode_summaries": [
                    {
                        "episode_ref": item["local_episode_code"],
                        "focal_person_ref": item.get("focal_person_ref"),
                        "focal_roles": item.get("focal_roles") or (),
                        "responsibility_family": item.get("responsibility_family"),
                        "action": item.get("action"),
                        "responsibility": item.get("responsibility"),
                        "core_assertion_refs": item.get("core_assertion_refs") or (),
                        "assertion_links": item.get("assertion_links") or (),
                        "evidence": (
                            evidence["by_episode"][str(item["local_episode_code"])]
                            if evidence is not None
                            else None
                        ),
                    }
                    for item in rows
                ],
                "episode_pairs": [
                    list(pair) for pair in combinations(episode_refs, 2)
                ],
                "pair_count": len(episode_refs) * (len(episode_refs) - 1) // 2,
                "relation_policy_version": RELATION_POLICY_VERSION,
                "output_schema_version": RELATION_REVIEW_SCHEMA_VERSION,
            }
        )
    return {
        "schema_version": 1,
        "status": "relation_review_units_planned",
        "dataset_code": candidate_graph.get("dataset_code"),
        "candidate_episode_basis_sha256": basis_hash,
        "review_evidence_sha256": evidence_hash,
        "relation_policy_version": RELATION_POLICY_VERSION,
        "output_schema_version": RELATION_REVIEW_SCHEMA_VERSION,
        "relation_semantic_policy": RELATION_SEMANTIC_POLICY,
        "review_unit_count": len(units),
        "episode_count": len(episode_rows),
        "pair_count": sum(item["pair_count"] for item in units),
        "review_units": units,
        "gold_fields_detected": 0,
        "database_write_count": 0,
    }


def _pair(left: object, right: object) -> frozenset[str]:
    result = frozenset((str(left or ""), str(right or "")))
    if len(result) != 2 or "" in result:
        raise ValueError("Relation review pair 必须包含两个不同 Episode")
    return result


def _validate_relation_review(
    candidate_graph: Mapping[str, Any],
    review: Mapping[str, Any],
    blind_input: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Mapping[str, Any]]]:
    _reject_forbidden(review)
    plan = build_relation_review_plan(candidate_graph, blind_input)
    if review.get("status") != "relation_reviews_complete":
        raise ValueError("Relation review 尚未完成")
    if review.get("reviewed_without_historical_gold_or_score") is not True:
        raise ValueError("Relation review 未声明 Gold/score 隔离")
    if (
        review.get("candidate_episode_basis_sha256")
        != plan["candidate_episode_basis_sha256"]
        or review.get("review_evidence_sha256") != plan["review_evidence_sha256"]
        or review.get("relation_policy_version") != RELATION_POLICY_VERSION
        or review.get("output_schema_version") != RELATION_REVIEW_SCHEMA_VERSION
    ):
        raise ValueError("Relation review 与当前 Episode basis/policy 不一致")
    unit_by_ref = {item["review_unit_code"]: item for item in plan["review_units"]}
    result_rows = tuple(review.get("review_results") or ())
    result_by_ref = {
        str(item.get("review_unit_ref") or ""): item for item in result_rows
    }
    if (
        "" in result_by_ref
        or len(result_by_ref) != len(result_rows)
        or set(result_by_ref) != set(unit_by_ref)
    ):
        raise ValueError("Relation review 未一一覆盖 Review Units")
    all_dispositions = [
        item
        for result in result_rows
        for item in result.get("pair_dispositions") or ()
    ]
    all_review_relations = [
        item for result in result_rows for item in result.get("relations") or ()
    ]
    derived_unresolved_count = sum(
        item.get("decision") == "unresolved" for item in all_dispositions
    )
    if (
        review.get("dataset_code") != plan["dataset_code"]
        or review.get("review_unit_count") != plan["review_unit_count"]
        or review.get("pair_count") != plan["pair_count"]
        or review.get("related_pair_count") != len(all_review_relations)
        or review.get("unresolved_pair_count") != derived_unresolved_count
    ):
        raise ValueError("Relation review 顶层计数或 dataset 不一致")
    all_relations = []
    for unit_ref, unit in unit_by_ref.items():
        result = result_by_ref[unit_ref]
        if (
            result.get("cache_key") != unit["cache_key"]
            or result.get("relation_policy_version") != RELATION_POLICY_VERSION
            or result.get("output_schema_version") != RELATION_REVIEW_SCHEMA_VERSION
        ):
            raise ValueError("Relation review unit cache/policy/schema 不一致")
        episode_refs = set(unit["episode_refs"])
        expected_pairs = {
            _pair(left, right) for left, right in unit["episode_pairs"]
        }
        dispositions = tuple(result.get("pair_dispositions") or ())
        disposition_pairs = [
            _pair(item.get("left_episode_ref"), item.get("right_episode_ref"))
            for item in dispositions
        ]
        if len(disposition_pairs) != len(set(disposition_pairs)) or set(
            disposition_pairs
        ) != expected_pairs:
            raise ValueError("Relation review 必须完整且唯一处置所有 Episode pairs")
        related = {}
        for item, pair in zip(dispositions, disposition_pairs):
            decision = item.get("decision")
            if decision not in {"related", "distinct_unrelated", "unresolved"}:
                raise ValueError("Relation review pair decision 非法")
            relation_type = item.get("relation_type")
            if decision == "related":
                if relation_type not in EPISODE_RELATION_TYPES:
                    raise ValueError("related pair 缺少合法 relation_type")
                related[pair] = relation_type
            elif relation_type is not None:
                raise ValueError("非 related pair 不得声明 relation_type")
            if not str(item.get("reason") or "").strip():
                raise ValueError("Relation review pair 缺少 reason")
        relation_pairs = {}
        for item in result.get("relations") or ():
            pair = _pair(item.get("from_episode_ref"), item.get("to_episode_ref"))
            if not pair <= episode_refs or pair in relation_pairs:
                raise ValueError("Relation review relation endpoint 缺失或重复")
            relation_type = item.get("relation_type")
            if relation_type not in EPISODE_RELATION_TYPES:
                raise ValueError("Relation review relation_type 非法")
            evidence_refs = tuple(item.get("evidence_assertion_refs") or ())
            confidence = item.get("confidence")
            if (
                not evidence_refs
                or len(evidence_refs) != len(set(evidence_refs))
                or not isinstance(confidence, (int, float))
                or not 0.0 <= float(confidence) <= 1.0
            ):
                raise ValueError("Relation review relation evidence/confidence 非法")
            relation_pairs[pair] = relation_type
            all_relations.append(item)
        if relation_pairs != related:
            raise ValueError("Relation review relation 与 related pair disposition 不一致")
    _validate_acyclic_relations(all_relations)
    return plan, result_by_ref


def _validate_acyclic_relations(relations: list[Mapping[str, Any]]) -> None:
    adjacency: dict[str, set[str]] = defaultdict(set)
    nodes = set()
    for item in relations:
        if item.get("relation_type") not in _ACYCLIC_RELATION_TYPES:
            continue
        source = str(item["from_episode_ref"])
        target = str(item["to_episode_ref"])
        adjacency[source].add(target)
        nodes.update((source, target))
    visiting = set()
    visited = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("Relation review 产生有向关系环")
        if node in visited:
            return
        visiting.add(node)
        for target in adjacency.get(node, ()):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in nodes:
        visit(node)


def _reject_audit_leakage(payload: object, path: str = "$") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).strip().casefold()
            if normalized == "reviewed_without_candidate_or_score" and value is True:
                continue
            if (
                normalized.startswith("candidate_")
                or normalized.endswith("_score")
                or normalized
                in {
                    "candidate_graph",
                    "relation_review",
                    "boundary_review",
                    "qualification",
                    "score",
                    "scores",
                }
            ):
                raise ValueError(f"Relation Gold audit 包含 candidate/score 泄漏: {path}.{key}")
            _reject_audit_leakage(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_audit_leakage(value, f"{path}[{index}]")


def revise_relation_gold_from_audit(
    historical_gold: Mapping[str, Any], audit: Mapping[str, Any]
) -> dict[str, Any]:
    _reject_audit_leakage(audit)
    if audit.get("status") != "relation_gold_ontology_audit_complete":
        raise ValueError("Relation Gold ontology audit 尚未完成")
    if (
        audit.get("relation_policy_version") != RELATION_POLICY_VERSION
        or audit.get("reviewed_without_candidate_or_score") is not True
        or audit.get("dataset_code") != historical_gold.get("dataset_code")
    ):
        raise ValueError("Relation Gold audit 的 policy/isolation/dataset 不一致")
    episode_by_code = {
        str(item.get("gold_episode_code") or ""): item
        for item in historical_gold.get("gold_episodes") or ()
    }
    source_relations = {
        str(item.get("gold_relation_code") or ""): item
        for item in historical_gold.get("gold_relations") or ()
    }
    audit_rows = tuple(audit.get("audit_results") or ())
    audit_by_code = {
        str(item.get("gold_relation_code") or ""): item for item in audit_rows
    }
    if (
        "" in episode_by_code
        or "" in source_relations
        or "" in audit_by_code
        or len(audit_by_code) != len(audit_rows)
        or set(audit_by_code) != set(source_relations)
        or audit.get("relation_count") != len(source_relations)
    ):
        raise ValueError("Relation Gold audit 未一一覆盖原 Gold Relation")

    allowed_decisions = {
        "supported_as_declared",
        "supported_with_different_type",
        "unsupported_direct_relation",
        "insufficient_endpoint_evidence",
    }
    derived_counts = {decision: 0 for decision in sorted(allowed_decisions)}
    revised_relations = []
    for code, source in source_relations.items():
        row = audit_by_code[code]
        decision = str(row.get("audit_decision") or "")
        if decision not in allowed_decisions:
            raise ValueError("Relation Gold audit decision 非法")
        if not str(row.get("reason") or "").strip():
            raise ValueError("Relation Gold audit 缺少逐条 reason")
        derived_counts[decision] += 1
        if (
            row.get("from_episode") != source.get("from_episode")
            or row.get("to_episode") != source.get("to_episode")
            or row.get("declared_relation_type") != source.get("relation_type")
        ):
            raise ValueError("Relation Gold audit endpoint/type 与原 Gold 不一致")
        source_episode = episode_by_code.get(str(source.get("from_episode") or ""))
        target_episode = episode_by_code.get(str(source.get("to_episode") or ""))
        if source_episode is None or target_episode is None:
            raise ValueError("Relation Gold 引用了未知 Episode")
        evidence_refs = set(row.get("evidence_assertion_refs") or ())
        source_refs = set(source_episode.get("core_assertion_refs") or ())
        target_refs = set(target_episode.get("core_assertion_refs") or ())
        if (
            not evidence_refs
            or not evidence_refs <= source_refs | target_refs
            or not evidence_refs & source_refs
            or not evidence_refs & target_refs
        ):
            raise ValueError("Relation Gold audit evidence 未覆盖两个 endpoint")
        recommended = row.get("recommended_relation_type")
        if decision == "supported_as_declared":
            if recommended is not None:
                raise ValueError("原样支持的 Relation 不得声明新类型")
            revised_relations.append(dict(source))
        elif decision == "supported_with_different_type":
            if (
                recommended not in EPISODE_RELATION_TYPES
                or recommended == source.get("relation_type")
            ):
                raise ValueError("Relation Gold audit 推荐类型非法")
            revised_relations.append({**dict(source), "relation_type": recommended})
        elif decision == "unsupported_direct_relation":
            if recommended is not None:
                raise ValueError("不支持的 Relation 不得声明新类型")
        else:
            raise ValueError("Relation Gold audit 含 insufficient，阻断修订")
    declared_counts = {
        str(key): int(value)
        for key, value in (audit.get("decision_counts") or {}).items()
    }
    if declared_counts != derived_counts:
        raise ValueError("Relation Gold audit decision_counts 不一致")
    return {
        **dict(historical_gold),
        "status": "frozen_relation_gold_v2_open_development",
        "gold_relation_count": len(revised_relations),
        "gold_relations": revised_relations,
        "relation_gold_revision": {
            "relation_policy_version": RELATION_POLICY_VERSION,
            "source_relation_count": len(source_relations),
            "revised_relation_count": len(revised_relations),
            "audit_sha256": _hash(audit),
            "reviewed_without_candidate_or_score": True,
            "formal_blind_qualification": False,
        },
    }


def materialize_relation_review(
    candidate_graph: Mapping[str, Any],
    review: Mapping[str, Any],
    blind_input: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    plan, result_by_ref = _validate_relation_review(
        candidate_graph, review, blind_input
    )
    episode_rows = tuple(candidate_graph.get("episode_groups") or ())
    episode_by_code = {
        str(item["local_episode_code"]): item for item in episode_rows
    }
    passage_by_assertion = {
        str(link["assertion_ref"]): str(link["source_passage_ref"])
        for episode in episode_rows
        for link in episode.get("assertion_links") or ()
    }
    relation_rows = []
    formal_rows = []
    pair_rows = []
    unresolved_pairs = []
    for unit in plan["review_units"]:
        unit_ref = unit["review_unit_code"]
        result = result_by_ref[unit_ref]
        for item in result.get("pair_dispositions") or ():
            row = {
                "left_episode_ref": item["left_episode_ref"],
                "right_episode_ref": item["right_episode_ref"],
                "decision": item["decision"],
                "relation_type": item.get("relation_type"),
                "reason": item.get("reason"),
                "review_unit_ref": unit_ref,
            }
            pair_rows.append(row)
            if item["decision"] == "unresolved":
                unresolved_pairs.append(row)
        for item in result.get("relations") or ():
            source = str(item["from_episode_ref"])
            target = str(item["to_episode_ref"])
            relation_type = str(item["relation_type"])
            endpoint_assertions = set(
                episode_by_code[source].get("core_assertion_refs") or ()
            ) | set(episode_by_code[target].get("core_assertion_refs") or ())
            evidence_refs = tuple(item.get("evidence_assertion_refs") or ())
            if not evidence_refs or not set(evidence_refs) <= endpoint_assertions:
                raise ValueError("Relation evidence 必须来自两个 endpoint Episode")
            identity = {
                "from_episode": source,
                "to_episode": target,
                "relation_type": relation_type,
            }
            fingerprint = _hash(identity)
            relation_id = f"ER-{fingerprint[:20].upper()}"
            relation_rows.append(
                {
                    "relation_id": relation_id,
                    **identity,
                    "evidence_assertion_refs": list(evidence_refs),
                }
            )
            formal_rows.append(
                {
                    "relation_id": relation_id,
                    "from_episode_version_ref": f"{source}@v1",
                    "to_episode_version_ref": f"{target}@v1",
                    "relation_type": relation_type,
                    "semantic_fingerprint": fingerprint,
                    "semantic_version": 1,
                    "evidence_version": 1,
                    "relation_status": "proposed",
                    "evidence_links": [
                        {
                            "assertion_ref": ref,
                            "source_passage_ref": passage_by_assertion[ref],
                            "evidence_status": "draft",
                        }
                        for ref in evidence_refs
                    ],
                    "confidence": float(item.get("confidence") or 0.0),
                    "lineage": {"origin": "created"},
                    "provenance": {
                        "relation_policy_version": RELATION_POLICY_VERSION,
                        "review_unit_ref": unit_ref,
                    },
                }
            )
    if unresolved_pairs:
        raise ValueError("Relation review 含 unresolved pair，阻断图物化")
    return {
        **dict(candidate_graph),
        "status": "relation_graph_review_materialized",
        "boundary_unit_relations": candidate_graph.get("relations") or (),
        "relations": sorted(relation_rows, key=lambda item: item["relation_id"]),
        "formal_episode_relations": sorted(
            formal_rows, key=lambda item: item["relation_id"]
        ),
        "pair_dispositions": sorted(
            pair_rows,
            key=lambda item: (
                item["review_unit_ref"],
                item["left_episode_ref"],
                item["right_episode_ref"],
            ),
        ),
        "relation_review": {
            "candidate_episode_basis_sha256": plan[
                "candidate_episode_basis_sha256"
            ],
            "review_evidence_sha256": plan["review_evidence_sha256"],
            "relation_policy_version": RELATION_POLICY_VERSION,
            "output_schema_version": RELATION_REVIEW_SCHEMA_VERSION,
            "unresolved_pair_count": len(unresolved_pairs),
            "reviewed_without_historical_gold_or_score": True,
            "formal_acceptance_performed": False,
        },
        "safety": {
            **dict(candidate_graph.get("safety") or {}),
            "database_write_count": 0,
            "network_request_count": 0,
            "gold_fields_detected": 0,
        },
    }
