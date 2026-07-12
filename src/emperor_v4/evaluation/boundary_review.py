from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable, Mapping

from emperor_v4.contracts.boundary import (
    ContextAssertionLink,
    EpisodeBoundaryGroup,
    EpisodeBoundaryReviewResult,
    EpisodeRelation,
)
from emperor_v4.domain.boundary import (
    materialize_boundary_review,
    plan_boundary_reviews,
)
from emperor_v4.evaluation.blind_holdout import assertions_from_blind_input


def build_boundary_review_plan(
    payload: Mapping[str, Any], *, cached_review_keys: Iterable[str] = ()
) -> dict[str, Any]:
    assertions = assertions_from_blind_input(payload)
    plan = plan_boundary_reviews(
        assertions, cached_review_keys=cached_review_keys
    )
    return {
        "schema_version": 2,
        "status": "boundary_review_units_planned",
        "input_dataset_code": payload.get("dataset_code"),
        "input_assertion_count": len(assertions),
        "proposition_cluster_count": len(plan.proposition_clusters),
        "review_unit_count": len(plan.review_units),
        "cache_hit_unit_count": len(plan.cache_hit_unit_codes),
        "cache_miss_unit_count": len(plan.cache_miss_unit_codes),
        "model_call_budget_for_this_delta": plan.model_call_count,
        "proposition_clusters": [asdict(item) for item in plan.proposition_clusters],
        "review_units": [asdict(item) for item in plan.review_units],
        "cache_hit_unit_codes": list(plan.cache_hit_unit_codes),
        "cache_miss_unit_codes": list(plan.cache_miss_unit_codes),
    }


def _review_result(payload: Mapping[str, Any]) -> EpisodeBoundaryReviewResult:
    return EpisodeBoundaryReviewResult(
        review_unit_ref=str(payload.get("review_unit_ref") or ""),
        episode_groups=tuple(
            EpisodeBoundaryGroup(
                local_episode_code=str(item.get("local_episode_code") or ""),
                core_assertion_refs=tuple(item.get("core_assertion_refs") or ()),
                boundary_reason=str(item.get("boundary_reason") or ""),
                confidence=float(item.get("confidence")),
            )
            for item in payload.get("episode_groups") or ()
        ),
        relations=tuple(
            EpisodeRelation(
                from_episode_ref=str(item.get("from_episode_ref") or ""),
                to_episode_ref=str(item.get("to_episode_ref") or ""),
                relation_type=str(item.get("relation_type") or ""),
                evidence_assertion_refs=tuple(
                    item.get("evidence_assertion_refs") or ()
                ),
                confidence=float(item.get("confidence")),
            )
            for item in payload.get("relations") or ()
        ),
        context_assertions=tuple(
            ContextAssertionLink(
                assertion_ref=str(item.get("assertion_ref") or ""),
                applies_to_episode_refs=tuple(
                    item.get("applies_to_episode_refs") or ()
                ),
                reason=str(item.get("reason") or ""),
            )
            for item in payload.get("context_assertions") or ()
        ),
        unresolved_assertion_refs=tuple(
            payload.get("unresolved_assertion_refs") or ()
        ),
    )


def materialize_boundary_review_payload(
    blind_input: Mapping[str, Any], review_payload: Mapping[str, Any]
) -> dict[str, Any]:
    assertions = assertions_from_blind_input(blind_input)
    packets, relations = materialize_boundary_review(
        assertions, _review_result(review_payload)
    )
    return {
        "schema_version": 2,
        "status": "boundary_review_materialized_as_proposals",
        "episode_packets": [asdict(item) for item in packets],
        "episode_relations": [asdict(item) for item in relations],
        "formal_acceptance_performed": False,
        "database_write_count": 0,
    }
