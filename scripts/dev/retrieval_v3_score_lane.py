from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from scripts.dev.retrieval_v2_candidate_promoter import appointment_delegation_protocol_allows_scoring
from scripts.dev.retrieval_v2_intake_manifest import text


@dataclass(frozen=True)
class ScoreLaneDecision:
    lane: str
    allowed: bool
    reason: str = ""


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def is_candidate_exception(row: Mapping[str, Any]) -> bool:
    binding_payload = as_mapping(row.get("binding_payload"))
    return text(binding_payload.get("source")) in {
        "retrieval_v2_candidate_promoter",
        "retrieval_v3_candidate_binding_consumer",
    } or row.get("candidate_id") is not None


def appointment_candidate_payload_allows_scoring(candidate_payload: Mapping[str, Any]) -> bool:
    if appointment_delegation_protocol_allows_scoring({"candidate_payload": candidate_payload}):
        return True
    review = as_mapping(candidate_payload.get("candidate_review"))
    required_facts = as_mapping(review.get("required_facts"))
    if not review or not required_facts:
        return False
    protocol_payload = {
        "scoring_candidate": review.get("scoring_candidate"),
        "usable_for_scoring_cluster": review.get("usable_for_scoring_cluster"),
        "direction": text(review.get("direction")),
        "candidate_role": text(review.get("candidate_role")),
        "appointment_delegation_chain": dict(required_facts),
    }
    return appointment_delegation_protocol_allows_scoring({"candidate_payload": protocol_payload})


def classify_score_lane(row: Mapping[str, Any]) -> ScoreLaneDecision:
    """Classify a formal binding without making candidates a normal prerequisite.

    Direct formal bindings use the normal lane.  Candidate-origin bindings remain
    admissible only after their existing protocol gate is satisfied; unresolved or
    under-specified rows are exception-lane blockers rather than score inputs.
    """

    if row.get("binding_usable_for_scoring_cluster") is False:
        return ScoreLaneDecision("exception_blocked", False, "binding_not_scoring")
    identity_ready = row.get("identity_ready")
    if identity_ready is None and ("object_id" in row or "target_object_id" in row):
        identity_ready = row.get("object_id") is not None and row.get("target_object_id") is not None
    if identity_ready is False:
        return ScoreLaneDecision("exception_blocked", False, "identity_not_ready")
    if text(row.get("rule_code")) != "appointment_delegation":
        return ScoreLaneDecision("normal_direct", True)
    if not is_candidate_exception(row):
        return ScoreLaneDecision("normal_direct", True)
    candidate_payload = as_mapping(row.get("candidate_payload"))
    if not candidate_payload:
        return ScoreLaneDecision("exception_blocked", False, "missing_candidate_payload")
    if not appointment_candidate_payload_allows_scoring(candidate_payload):
        return ScoreLaneDecision("exception_blocked", False, "candidate_not_scoring")
    return ScoreLaneDecision("normal_resolved_exception", True)
