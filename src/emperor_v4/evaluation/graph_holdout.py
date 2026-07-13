from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from typing import Any, Mapping

from emperor_v4.domain.boundary import (
    draft_rule_evidence_unit,
    materialize_boundary_review,
    plan_boundary_reviews,
)
from emperor_v4.evaluation.blind_holdout import assertions_from_blind_input
from emperor_v4.evaluation.boundary_review import review_result_from_payload
from emperor_v4.evaluation.boundary_score import score_boundary_graph


RULE_AGGREGATING_RELATION_TYPES = frozenset(
    {
        "continues",
        "same_mandate_phase",
        "renews_authority",
        "revokes",
        "outcome_of",
        "causal_followup",
    }
)


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def validate_boundary_review_freeze(
    blind_input: Mapping[str, Any], boundary_review: Mapping[str, Any]
) -> None:
    input_hash = _canonical_hash(blind_input)
    status = boundary_review.get("status")
    if status not in {"completed_before_gold_opened", "boundary_reviews_complete"}:
        raise ValueError("Boundary review 未在 Gold 打开前完成")
    isolated = (
        boundary_review.get("reviewed_without_gold_access") is True
        or boundary_review.get("reviewed_without_historical_gold_or_candidates") is True
    )
    if not isolated:
        raise ValueError("Boundary review 未声明 Gold/candidate 隔离")
    declared_hashes = {
        str(value)
        for value in (
            boundary_review.get("blind_input_sha256"),
            boundary_review.get("input_canonical_sha256"),
        )
        if value
    }
    if declared_hashes != {input_hash}:
        raise ValueError("Boundary review 与 blind input hash 不一致")


def materialize_boundary_graph_payload(
    blind_input: Mapping[str, Any], boundary_review: Mapping[str, Any]
) -> dict[str, Any]:
    input_hash = _canonical_hash(blind_input)
    validate_boundary_review_freeze(blind_input, boundary_review)

    assertions = assertions_from_blind_input(blind_input)
    plan = plan_boundary_reviews(assertions)
    units = {item.review_unit_code: item for item in plan.review_units}
    clusters_by_ref = {
        item.proposition_code: item for item in plan.proposition_clusters
    }
    review_rows = boundary_review.get("review_results") or ()
    reviews = [review_result_from_payload(item) for item in review_rows]
    if {item.review_unit_ref for item in reviews} != set(units):
        raise ValueError("Boundary review 未一一覆盖 Review Units")

    episode_rows = []
    relation_rows = []
    formal_relations = []
    disposition_rows = []
    pair_disposition_rows = []
    context_links = []
    unresolved = []
    excluded = []
    seen_assertions = set()
    for review in reviews:
        unit = units[review.review_unit_ref]
        unit_clusters = tuple(
            clusters_by_ref[ref] for ref in unit.proposition_cluster_refs
        )
        result = materialize_boundary_review(
            assertions,
            review,
            review_unit=unit,
            proposition_clusters=unit_clusters,
        )
        packet_by_core = {
            frozenset(link.assertion_ref for link in packet.assertion_links): packet
            for packet in result.episode_packets
        }
        local_to_packet = {
            group.local_episode_code: packet_by_core[frozenset(group.core_assertion_refs)]
            for group in review.episode_groups
        }
        atomic_key_by_episode = {
            local_to_packet[group.local_episode_code].episode_id: group.atomic_event_key
            for group in review.episode_groups
        }
        for packet in result.episode_packets:
            episode_rows.append(
                {
                    "local_episode_code": packet.episode_id,
                    "evaluation_context": packet.evaluation_context,
                    "focal_person_ref": unit.focal_person_ref,
                    "focal_roles": list(unit.focal_roles),
                    "responsibility_family": unit.responsibility_family,
                    "core_assertion_refs": [
                        link.assertion_ref for link in packet.assertion_links
                    ],
                    "assertion_links": [
                        {
                            "assertion_ref": link.assertion_ref,
                            "source_passage_ref": link.source_passage_ref,
                        }
                        for link in packet.assertion_links
                    ],
                    "action": packet.action,
                    "responsibility": packet.responsibility,
                    "semantic_fingerprint": packet.semantic_fingerprint,
                    "semantic_version": packet.semantic_version,
                    "evidence_version": packet.evidence_version,
                    "review_atomic_event_key": atomic_key_by_episode[
                        packet.episode_id
                    ],
                }
            )
        formal_relations.extend(asdict(item) for item in result.episode_relations)
        for relation in result.episode_relations:
            relation_rows.append(
                {
                    "relation_id": relation.relation_id,
                    "from_episode": relation.from_episode_version_ref.split("@v", 1)[0],
                    "to_episode": relation.to_episode_version_ref.split("@v", 1)[0],
                    "relation_type": relation.relation_type,
                    "evidence_assertion_refs": [
                        item.assertion_ref for item in relation.evidence_links
                    ],
                }
            )
        for item in review.assertion_dispositions:
            if item.assertion_ref in seen_assertions:
                raise ValueError("Graph materialization assertion disposition 重复")
            seen_assertions.add(item.assertion_ref)
            disposition_rows.append(
                {
                    "assertion_ref": item.assertion_ref,
                    "disposition": item.disposition,
                    "episode_refs": [
                        local_to_packet[ref].episode_id for ref in item.episode_refs
                    ],
                    "reason": item.reason,
                    "follow_up": item.follow_up,
                }
            )
        for item in review.pair_dispositions:
            pair_disposition_rows.append(
                {
                    "left_episode_ref": local_to_packet[
                        item.left_episode_ref
                    ].episode_id,
                    "right_episode_ref": local_to_packet[
                        item.right_episode_ref
                    ].episode_id,
                    "decision": item.decision,
                    "relation_type": item.relation_type,
                    "reason": item.reason,
                    "review_unit_ref": review.review_unit_ref,
                }
            )
        context_links.extend(asdict(item) for item in result.context_assertion_links)
        unresolved.extend(asdict(item) for item in result.unresolved_assertions)
        excluded.extend(asdict(item) for item in result.excluded_assertions)

    input_assertion_refs = {item.assertion_code for item in assertions}
    if seen_assertions != input_assertion_refs:
        raise ValueError("Graph materialization 未完整处置 blind assertions")
    return {
        "schema_version": 2,
        "status": "blind_episode_graph_proposed",
        "dataset_code": blind_input.get("dataset_code"),
        "input_sha256": input_hash,
        "input_assertion_refs": sorted(input_assertion_refs),
        "episode_groups": sorted(
            episode_rows, key=lambda item: item["local_episode_code"]
        ),
        "relations": sorted(
            relation_rows, key=lambda item: item["relation_id"]
        ),
        "formal_episode_relations": sorted(
            formal_relations, key=lambda item: item["relation_id"]
        ),
        "assertion_dispositions": sorted(
            disposition_rows, key=lambda item: item["assertion_ref"]
        ),
        "pair_dispositions": sorted(
            pair_disposition_rows,
            key=lambda item: (
                item["review_unit_ref"],
                item["left_episode_ref"],
                item["right_episode_ref"],
            ),
        ),
        "context_assertion_links": context_links,
        "unresolved_assertions": unresolved,
        "excluded_assertions": excluded,
        "review_unit_count": len(units),
        "external_reviewer_call_count": int(
            boundary_review.get("external_reviewer_call_count") or 0
        ),
        "safety": {
            "gold_fields_detected": 0,
            "network_request_count": 0,
            "database_write_count": 0,
        },
    }


def _member_role(action: str) -> str:
    if "任命" in action:
        return "appointment"
    if "授权" in action:
        return "delegation"
    if "战役" in action:
        return "outcome"
    if "处置" in action or "保全" in action:
        return "feedback"
    if "荐举" in action or "纳谏" in action or "监察" in action:
        return "advice"
    return "context"


def draft_rule_evidence_units_payload(
    graph: Mapping[str, Any],
    *,
    rule_code: str = "appointment_delegation",
    rule_version: str = "v1",
    aggregation_policy_version: str = "delegation-chain-v1",
) -> dict[str, Any]:
    episodes = {
        str(item["local_episode_code"]): item for item in graph.get("episode_groups") or ()
    }
    relations = tuple(graph.get("relations") or ())
    adjacency: dict[str, set[str]] = defaultdict(set)
    for relation in relations:
        if str(relation["relation_type"]) not in RULE_AGGREGATING_RELATION_TYPES:
            continue
        source = str(relation["from_episode"])
        target = str(relation["to_episode"])
        adjacency[source].add(target)
        adjacency[target].add(source)

    visited = set()
    components = []
    for episode_ref in sorted(episodes):
        if episode_ref in visited:
            continue
        stack = [episode_ref]
        component = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency.get(current, ()))
        visited |= component
        components.append(component)

    units = []
    consumed = set()
    duplicate_consumption = set()
    for component in components:
        rows = [episodes[ref] for ref in sorted(component)]
        if not any(
            "任命" in str(row.get("action") or "")
            or "授权" in str(row.get("action") or "")
            for row in rows
        ):
            continue
        contexts = {str(row.get("evaluation_context") or "") for row in rows}
        if len(contexts) != 1:
            raise ValueError("RuleEvidenceUnit candidate 跨 evaluation context")
        relation_members = {
            str(item["relation_id"]): str(item["relation_type"])
            for item in relations
            if item["from_episode"] in component and item["to_episode"] in component
        }
        episode_members = {
            ref: _member_role(str(episodes[ref].get("action") or ""))
            for ref in component
        }
        duplicate_consumption |= consumed & component
        consumed |= component
        unit = draft_rule_evidence_unit(
            rule_code=rule_code,
            rule_version=rule_version,
            aggregation_policy_version=aggregation_policy_version,
            evaluation_context=next(iter(contexts)),
            episode_members=episode_members,
            relation_members=relation_members,
            aggregation_reason="connected appointment/delegation episode graph component",
        )
        row = asdict(unit)
        row["episode_refs"] = list(unit.episode_refs)
        row["relation_refs"] = list(unit.relation_refs)
        units.append(row)
    return {
        "schema_version": 1,
        "status": "rule_evidence_unit_candidates_proposed",
        "input_sha256": graph.get("input_sha256"),
        "rule_code": rule_code,
        "rule_version": rule_version,
        "aggregation_policy_version": aggregation_policy_version,
        "rule_evidence_units": sorted(units, key=lambda item: item["unit_code"]),
        "direct_episode_projection_refs": [],
        "duplicate_consumption_episode_refs": sorted(duplicate_consumption),
        "database_write_count": 0,
    }


def score_graph_blind_holdout(
    graph: Mapping[str, Any],
    historical_gold: Mapping[str, Any],
    rule_candidates: Mapping[str, Any],
    rule_gold: Mapping[str, Any],
    runtime_audit: Mapping[str, Any],
) -> dict[str, Any]:
    input_hash = graph.get("input_sha256")
    for gold, label in (
        (historical_gold, "historical Gold"),
        (rule_gold, "rule Gold"),
    ):
        if gold.get("candidate_input_sha256") != input_hash:
            raise ValueError(f"{label} 与 graph input hash 不一致")
        if gold.get("status") != "frozen":
            raise ValueError(f"{label} 尚未冻结")
        if gold.get("frozen_without_candidate_or_review_access") is not True:
            raise ValueError(f"{label} 未声明 candidate/review 隔离")

    episode_score = score_boundary_graph(graph, historical_gold)
    input_assertion_refs = set(graph.get("input_assertion_refs") or ())
    gold_disposition_refs = [
        str(item.get("assertion_ref") or "")
        for item in historical_gold.get("gold_assertion_dispositions") or ()
    ]
    if (
        len(gold_disposition_refs) != len(set(gold_disposition_refs))
        or set(gold_disposition_refs) != input_assertion_refs
    ):
        raise ValueError("historical Gold assertion dispositions 未完整且唯一覆盖输入")
    episode_map = episode_score["diagnostics"]["exact_candidate_matches"]
    gold_relations = {
        (
            str(item["from_episode"]),
            str(item["to_episode"]),
            str(item["relation_type"]),
        ): str(item["gold_relation_code"])
        for item in historical_gold.get("gold_relations") or ()
    }
    relation_map = {}
    for relation in graph.get("relations") or ():
        source = episode_map.get(str(relation["from_episode"]))
        target = episode_map.get(str(relation["to_episode"]))
        key = (source, target, str(relation["relation_type"]))
        if source and target and key in gold_relations:
            relation_map[str(relation["relation_id"])] = gold_relations[key]

    candidate_signatures = {}
    candidate_episode_owners = {}
    for unit in rule_candidates.get("rule_evidence_units") or ():
        for episode_ref in unit.get("episode_refs") or ():
            previous = candidate_episode_owners.setdefault(
                str(episode_ref), str(unit["unit_code"])
            )
            if previous != str(unit["unit_code"]):
                raise ValueError("RuleEvidenceUnit candidate 重复消费 episode")
        mapped_episodes = [episode_map.get(str(ref)) for ref in unit.get("episode_refs") or ()]
        mapped_relations = [relation_map.get(str(ref)) for ref in unit.get("relation_refs") or ()]
        candidate_signatures[str(unit["unit_code"])] = (
            frozenset(item for item in mapped_episodes if item),
            frozenset(item for item in mapped_relations if item),
            len(mapped_episodes) == len([item for item in mapped_episodes if item]),
            len(mapped_relations) == len([item for item in mapped_relations if item]),
        )
    gold_signatures = {
        str(item["gold_rule_unit_code"]): (
            frozenset(item.get("episode_refs") or ()),
            frozenset(item.get("relation_refs") or ()),
        )
        for item in rule_gold.get("gold_rule_evidence_units") or ()
    }
    gold_episode_owners = {}
    for unit in rule_gold.get("gold_rule_evidence_units") or ():
        for episode_ref in unit.get("episode_refs") or ():
            previous = gold_episode_owners.setdefault(
                str(episode_ref), str(unit["gold_rule_unit_code"])
            )
            if previous != str(unit["gold_rule_unit_code"]):
                raise ValueError("rule Gold 重复消费 episode")
    exact_candidate_units = {
        candidate_code: gold_code
        for candidate_code, signature in candidate_signatures.items()
        if signature[2] and signature[3]
        for gold_code, gold_signature in gold_signatures.items()
        if signature[:2] == gold_signature
    }
    exact_gold_units = set(exact_candidate_units.values())
    rule_precision = (
        len(exact_candidate_units) / len(candidate_signatures)
        if candidate_signatures
        else None
    )
    rule_recall = (
        len(exact_gold_units) / len(gold_signatures) if gold_signatures else None
    )
    metrics = episode_score["episode_metrics"]
    relation_metrics = episode_score["relation_metrics"]
    duplicate_count = len(
        rule_candidates.get("duplicate_consumption_episode_refs") or ()
    )
    release_gate_passed = all(
        (
            (metrics["exact_episode_recall"] or 0) >= 0.85,
            (metrics["exact_candidate_precision"] or 0) >= 0.90,
            (metrics["pairwise_same_episode_precision"] or 0) >= 0.95,
            (metrics["pairwise_same_episode_recall"] or 0) >= 0.90,
            metrics["catastrophic_wrong_merge_count"] == 0,
            metrics["cross_ruler_contamination_count"] == 0,
            metrics["primary_assertion_disposition_coverage"] == 1.0,
            metrics["passage_lineage_completeness"] == 1.0,
            (relation_metrics["strict_relation_precision"] or 0) >= 0.90,
            (relation_metrics["strict_relation_recall"] or 0) >= 0.85,
            duplicate_count == 0,
            (rule_recall or 0) >= 0.85,
            (rule_precision or 0) >= 0.90,
            runtime_audit.get("unchanged_rerun_model_calls") == 0,
            runtime_audit.get("changed_unit_affects_other_unit_count") == 0,
        )
    )
    return {
        "schema_version": 1,
        "status": "g2_6e_graph_blind_scored_after_all_gold_opened",
        "episode_graph_score": episode_score,
        "rule_evidence_metrics": {
            "exact_rule_unit_recall": rule_recall,
            "exact_rule_unit_precision": rule_precision,
            "duplicate_consumption_count": duplicate_count,
            "exact_candidate_matches": exact_candidate_units,
        },
        "runtime_metrics": dict(runtime_audit),
        "release_gate_passed": release_gate_passed,
        "g3_authorized": release_gate_passed,
    }
