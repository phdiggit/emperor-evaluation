from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Iterable, Mapping

from emperor_v4.contracts.boundary import (
    AssertionDisposition,
    BoundaryReviewRequest,
    EpisodeBoundaryGroup,
    EpisodeBoundaryReviewResult,
    EpisodeRelationDraft,
)
from emperor_v4.domain.boundary import (
    InMemoryBoundaryReviewCache,
    execute_boundary_reviews,
    materialize_boundary_review,
    plan_boundary_reviews,
)
from emperor_v4.evaluation.blind_holdout import assertions_from_blind_input


def build_boundary_review_plan(
    payload: Mapping[str, Any], *, cached_review_keys: Iterable[str] = ()
) -> dict[str, Any]:
    assertions = assertions_from_blind_input(payload)
    plan = plan_boundary_reviews(assertions, cached_review_keys=cached_review_keys)
    return {
        "schema_version": 2,
        "status": "boundary_review_units_planned",
        "input_dataset_code": payload.get("dataset_code"),
        "input_assertion_count": len(assertions),
        "proposition_cluster_count": len(plan.proposition_clusters),
        "review_unit_count": len(plan.review_units),
        "cache_hit_unit_count": len(plan.cache_hit_unit_codes),
        "cache_miss_unit_count": len(plan.cache_miss_unit_codes),
        "model_call_budget_before_fast_path": plan.model_call_count,
        "proposition_clusters": [asdict(item) for item in plan.proposition_clusters],
        "review_units": [asdict(item) for item in plan.review_units],
        "cache_hit_unit_codes": list(plan.cache_hit_unit_codes),
        "cache_miss_unit_codes": list(plan.cache_miss_unit_codes),
    }


def review_result_from_payload(payload: Mapping[str, Any]) -> EpisodeBoundaryReviewResult:
    return EpisodeBoundaryReviewResult(
        review_unit_ref=str(payload.get("review_unit_ref") or ""),
        review_unit_cache_key=str(payload.get("review_unit_cache_key") or ""),
        proposition_semantic_hashes=tuple(
            payload.get("proposition_semantic_hashes") or ()
        ),
        boundary_policy_version=str(payload.get("boundary_policy_version") or ""),
        output_schema_version=str(payload.get("output_schema_version") or ""),
        model_family=str(payload.get("model_family") or ""),
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
            EpisodeRelationDraft(
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
        assertion_dispositions=tuple(
            AssertionDisposition(
                assertion_ref=str(item.get("assertion_ref") or ""),
                disposition=str(item.get("disposition") or ""),
                episode_refs=tuple(item.get("episode_refs") or ()),
                reason=str(item.get("reason") or ""),
                follow_up=(str(item["follow_up"]) if item.get("follow_up") else None),
            )
            for item in payload.get("assertion_dispositions") or ()
        ),
        review_provenance={
            str(key): str(value)
            for key, value in (payload.get("review_provenance") or {}).items()
        },
    )


def execute_boundary_review_payload(
    blind_input: Mapping[str, Any],
    *,
    cached_review_payloads: Iterable[Mapping[str, Any]] = (),
    reviewer: Callable[[BoundaryReviewRequest], EpisodeBoundaryReviewResult] | None = None,
) -> dict[str, Any]:
    assertions = assertions_from_blind_input(blind_input)
    cache = InMemoryBoundaryReviewCache(
        review_result_from_payload(item) for item in cached_review_payloads
    )
    result = execute_boundary_reviews(assertions, cache=cache, reviewer=reviewer)
    return {
        "schema_version": 2,
        "status": (
            "boundary_reviews_complete"
            if not result.pending_unit_codes
            else "boundary_reviews_pending_cache_misses"
        ),
        "review_results": [asdict(item) for item in result.review_results],
        "deterministic_unit_codes": list(result.deterministic_unit_codes),
        "cache_hit_unit_codes": list(result.cache_hit_unit_codes),
        "model_called_unit_codes": list(result.model_called_unit_codes),
        "pending_unit_codes": list(result.pending_unit_codes),
        "model_call_count": result.model_call_count,
        "database_write_count": 0,
    }


def materialize_boundary_review_payload(
    blind_input: Mapping[str, Any], review_payload: Mapping[str, Any]
) -> dict[str, Any]:
    assertions = assertions_from_blind_input(blind_input)
    plan = plan_boundary_reviews(assertions)
    review = review_result_from_payload(review_payload)
    unit_by_ref = {item.review_unit_code: item for item in plan.review_units}
    if review.review_unit_ref not in unit_by_ref:
        raise ValueError("Review result 引用了当前输入中不存在的 ReviewUnit")
    result = materialize_boundary_review(
        assertions,
        review,
        review_unit=unit_by_ref[review.review_unit_ref],
        proposition_clusters=plan.proposition_clusters,
    )
    return {
        "schema_version": 2,
        "status": "boundary_review_materialized_as_proposals",
        **asdict(result),
        "formal_acceptance_performed": False,
        "database_write_count": 0,
    }
