from __future__ import annotations

"""Deterministic material-support lint for the current I5B factor contracts.

The public validator accepts one worklist task and one Gold unit payload.  V2
semantic evidence is read from ``semantic_evidence`` on either object (the two
mappings may be split, but conflicting values are rejected).  Every ``*_refs``
field is a non-empty list of assertion refs declared by the task.  Timeline
markers are integer sequence numbers, not inferred historical dates.
"""

from collections.abc import Mapping, Sequence
from typing import Any


SUPPORTED_RULES = frozenset(
    {"talent_discovery", "tolerate_talent", "anti_nepotism"}
)
TOLERATE_TALENT_SEMANTIC_CONTRACT_VERSION = "tolerate-talent-factor-agent-v3"

_TD_VERIFIED_BASIS = frozenset(
    {
        "direct_observation_or_interview",
        "recommendation_verified_by_ruler",
        "reputation_then_direct_demonstration",
        "work_product_then_interview",
    }
)
_TD_BARRIER_CROSSED = frozenset(
    {
        "cross_camp_barrier_crossed",
        "reluctance_or_access_barrier_crossed",
        "status_or_access_barrier_crossed",
    }
)

_AN_OWNED_FACTORS = {
    "episode": frozenset(
        {"capability_basis", "process_integrity", "public_power_exposure"}
    ),
    "aggregate_context": frozenset({"network_effect"}),
}


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _task_assertion_refs(task: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for item in task.get("assertions") or ():
        if isinstance(item, Mapping):
            ref = item.get("assertion_ref")
            if isinstance(ref, str) and ref:
                refs.add(ref)
    for ref in task.get("assertion_refs") or ():
        if isinstance(ref, str) and ref:
            refs.add(ref)
    for episode in task.get("episodes") or ():
        if not isinstance(episode, Mapping):
            continue
        for ref in episode.get("assertion_refs") or ():
            if isinstance(ref, str) and ref:
                refs.add(ref)
    return refs


def _semantic_evidence(
    task: Mapping[str, Any], gold: Mapping[str, Any], errors: list[str]
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for owner, payload in (("task", task), ("gold", gold)):
        evidence = payload.get("semantic_evidence")
        if evidence is None:
            continue
        if not isinstance(evidence, Mapping):
            errors.append(f"{owner}.semantic_evidence:not_mapping")
            continue
        for key, value in evidence.items():
            if key in merged and merged[key] != value:
                errors.append(f"semantic_evidence.{key}:conflict")
            else:
                merged[str(key)] = value
    return merged


def _option(factors: Mapping[str, Any], name: str) -> str | None:
    value = factors.get(name)
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        option = value.get("option_code")
        return option if isinstance(option, str) and option else None
    return None


def _factor_refs(factors: Mapping[str, Any], name: str) -> object:
    value = factors.get(name)
    return value.get("assertion_refs") if isinstance(value, Mapping) else None


def _check_refs(
    field: str,
    value: object,
    available: set[str],
    errors: list[str],
    *,
    required: bool = True,
) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not _is_sequence(value) or not value:
        errors.append(f"{field}:missing_or_empty")
        return ()
    refs = tuple(value)
    if any(not isinstance(ref, str) or not ref for ref in refs):
        errors.append(f"{field}:invalid_ref")
        return ()
    if len(set(refs)) != len(refs):
        errors.append(f"{field}:duplicate_ref")
    unknown = sorted(set(refs) - available)
    if unknown:
        errors.append(f"{field}:unknown_ref:{','.join(unknown)}")
    return refs


def _require_semantic_refs(
    semantic: Mapping[str, Any],
    key: str,
    available: set[str],
    errors: list[str],
) -> tuple[str, ...]:
    return _check_refs(
        f"semantic_evidence.{key}", semantic.get(key), available, errors
    )


def _check_factor_refs(
    factors: Mapping[str, Any], available: set[str], errors: list[str]
) -> None:
    for name in sorted(factors):
        if _option(factors, name) in {None, "not_applicable"}:
            continue
        _check_refs(
            f"factors.{name}.assertion_refs",
            _factor_refs(factors, name),
            available,
            errors,
        )


def _lint_talent_discovery(
    semantic: Mapping[str, Any],
    factors: Mapping[str, Any],
    available: set[str],
    errors: list[str],
) -> None:
    timeline_keys = (
        "visibility_basis_at",
        "verification_at",
        "first_substantive_use_at",
    )
    for key in timeline_keys:
        if key not in semantic:
            errors.append(f"semantic_evidence.{key}:missing")
    visibility = semantic.get("visibility_basis_at")
    verification = semantic.get("verification_at")
    first_use = semantic.get("first_substantive_use_at")
    for key, value in ((timeline_keys[0], visibility), (timeline_keys[2], first_use)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append(f"semantic_evidence.{key}:invalid_sequence")
    if verification is not None and (
        isinstance(verification, bool)
        or not isinstance(verification, int)
        or verification < 0
    ):
        errors.append("semantic_evidence.verification_at:invalid_sequence")
    if isinstance(visibility, int) and isinstance(first_use, int):
        if isinstance(visibility, bool) or isinstance(first_use, bool):
            pass
        elif visibility >= first_use:
            errors.append("talent_discovery:visibility_must_precede_first_use")
    if (
        isinstance(visibility, int)
        and not isinstance(visibility, bool)
        and isinstance(verification, int)
        and not isinstance(verification, bool)
        and verification < visibility
    ):
        errors.append("talent_discovery:verification_precedes_visibility")

    basis = _option(factors, "recognition_basis")
    if basis in _TD_VERIFIED_BASIS:
        if not isinstance(verification, int) or isinstance(verification, bool):
            errors.append("talent_discovery:verified_basis_missing_verification")
        elif isinstance(first_use, int) and not isinstance(first_use, bool):
            if verification >= first_use:
                errors.append("talent_discovery:verification_not_before_first_use")
    elif basis == "reputation_only_unverified" and verification is not None:
        errors.append("talent_discovery:unverified_basis_has_verification")
    elif basis == "missing_or_posthoc" and isinstance(verification, int):
        if isinstance(first_use, int) and verification < first_use:
            errors.append("talent_discovery:missing_or_posthoc_has_preuse_verification")

    barrier = _option(factors, "barrier_crossing")
    if barrier in _TD_BARRIER_CROSSED:
        _require_semantic_refs(semantic, "explicit_barrier_refs", available, errors)
        _require_semantic_refs(
            semantic, "ruler_crossing_action_refs", available, errors
        )


def _check_observation(
    field: str,
    value: object,
    available: set[str],
    errors: list[str],
) -> tuple[int | None, str | None]:
    if not isinstance(value, Mapping):
        errors.append(f"{field}:missing_or_invalid")
        return None, None
    _check_refs(
        f"{field}.assertion_refs", value.get("assertion_refs"), available, errors
    )
    order = value.get("order")
    if isinstance(order, bool) or not isinstance(order, int) or order < 0:
        errors.append(f"{field}.order:invalid_sequence")
        order = None
    observation_id = value.get("observation_id")
    if not isinstance(observation_id, str) or not observation_id:
        errors.append(f"{field}.observation_id:missing_or_invalid")
        observation_id = None
    return order, observation_id


def _lint_subject_chain(
    semantic: Mapping[str, Any], available: set[str], errors: list[str]
) -> dict[str, tuple[int | None, str | None]]:
    chain = semantic.get("subject_ownership_chain")
    if not isinstance(chain, Mapping):
        errors.append("semantic_evidence.subject_ownership_chain:missing_or_invalid")
        return {}
    subject_refs: set[str] = set()
    observations: dict[str, tuple[int | None, str | None]] = {}
    for step in ("feedback_trigger", "ruler_response", "safety_or_authority_effect"):
        item = chain.get(step)
        if not isinstance(item, Mapping):
            errors.append(f"subject_ownership_chain.{step}:missing_or_invalid")
            continue
        subject_ref = item.get("subject_ref")
        if not isinstance(subject_ref, str) or not subject_ref:
            errors.append(f"subject_ownership_chain.{step}.subject_ref:missing")
        else:
            subject_refs.add(subject_ref)
        observations[step] = _check_observation(
            f"subject_ownership_chain.{step}",
            item,
            available,
            errors,
        )
    if len(subject_refs) > 1:
        errors.append("tolerate_talent:subject_ownership_chain_mismatch")
    return observations


def _lint_tolerate_talent(
    semantic: Mapping[str, Any],
    factors: Mapping[str, Any],
    available: set[str],
    errors: list[str],
) -> None:
    chain = _lint_subject_chain(semantic, available, errors)
    feedback = _option(factors, "feedback_reception")
    if feedback == "accepted_after_conflict":
        _require_semantic_refs(semantic, "explicit_conflict_refs", available, errors)
        _require_semantic_refs(semantic, "later_acceptance_refs", available, errors)
    elif feedback == "actively_solicited":
        _require_semantic_refs(semantic, "prior_ruler_request_refs", available, errors)
    elif feedback == "accepted_without_conflict":
        _require_semantic_refs(semantic, "direct_acceptance_refs", available, errors)

    safety = _option(factors, "talent_safety")
    if safety == "safe_without_retaliation":
        followup = _check_observation(
            "semantic_evidence.positive_safety_followup",
            semantic.get("positive_safety_followup"),
            available,
            errors,
        )
        response = chain.get("ruler_response", (None, None))
        if (
            followup[0] is not None
            and response[0] is not None
            and followup[0] <= response[0]
        ):
            errors.append("tolerate_talent:safety_followup_not_after_ruler_response")
        if (
            followup[1] is not None
            and response[1] is not None
            and followup[1] == response[1]
        ):
            errors.append("tolerate_talent:safety_followup_reuses_ruler_response")
    elif safety == "severe_threat_or_coercion":
        _require_semantic_refs(semantic, "severe_threat_refs", available, errors)

    continuity = _option(factors, "conflict_repair_continuity")
    independent_followups = {
        "timely_repair": "independent_repair_followup",
        "delayed_partial_repair": "independent_repair_followup",
        "formal_reversal_without_trust_repair": "independent_repair_followup",
        "stable_without_conflict": "independent_continuity_followup",
    }
    if continuity in independent_followups:
        field = independent_followups[continuity]
        followup = _check_observation(
            f"semantic_evidence.{field}", semantic.get(field), available, errors
        )
        response = chain.get("ruler_response", (None, None))
        if (
            followup[0] is not None
            and response[0] is not None
            and followup[0] <= response[0]
        ):
            errors.append("tolerate_talent:continuity_followup_not_after_ruler_response")
        if (
            followup[1] is not None
            and response[1] is not None
            and followup[1] == response[1]
        ):
            errors.append("tolerate_talent:continuity_followup_not_independent")

        if continuity in {
            "timely_repair",
            "delayed_partial_repair",
            "formal_reversal_without_trust_repair",
        }:
            assessment = semantic.get("repair_assessment")
            if not isinstance(assessment, Mapping):
                errors.append("semantic_evidence.repair_assessment:missing_or_invalid")
            else:
                timing = assessment.get("timing")
                scope = assessment.get("scope")
                trust_restored = assessment.get("trust_restored")
                if timing not in {"timely", "delayed", "not_established"}:
                    errors.append("semantic_evidence.repair_assessment.timing:invalid")
                if scope not in {
                    "substantive_full",
                    "substantive_partial",
                    "formal_only",
                    "none",
                }:
                    errors.append("semantic_evidence.repair_assessment.scope:invalid")
                if not isinstance(trust_restored, bool):
                    errors.append(
                        "semantic_evidence.repair_assessment.trust_restored:invalid"
                    )
                elif continuity == "timely_repair" and (
                    timing != "timely"
                    or scope != "substantive_full"
                    or trust_restored is not True
                ):
                    errors.append("tolerate_talent:timely_repair_assessment_mismatch")
                elif continuity == "delayed_partial_repair" and (
                    scope not in {"substantive_full", "substantive_partial"}
                    or not (timing == "delayed" or scope == "substantive_partial")
                ):
                    errors.append(
                        "tolerate_talent:delayed_partial_repair_assessment_mismatch"
                    )
                elif continuity == "delayed_partial_repair" and timing == "delayed":
                    _require_semantic_refs(
                        semantic, "delay_basis_refs", available, errors
                    )
                elif continuity == "formal_reversal_without_trust_repair" and (
                    scope != "formal_only" or trust_restored is not False
                ):
                    errors.append("tolerate_talent:formal_reversal_assessment_mismatch")
                elif continuity == "formal_reversal_without_trust_repair":
                    continuity_followup = _check_observation(
                        "semantic_evidence.independent_continuity_followup",
                        semantic.get("independent_continuity_followup"),
                        available,
                        errors,
                    )
                    if (
                        continuity_followup[0] is not None
                        and followup[0] is not None
                        and continuity_followup[0] <= followup[0]
                    ):
                        errors.append(
                            "tolerate_talent:trust_followup_not_after_formal_reversal"
                        )
                    prior_ids = {item for item in (response[1], followup[1]) if item}
                    if continuity_followup[1] in prior_ids:
                        errors.append(
                            "tolerate_talent:trust_followup_not_independent"
                        )
                    _require_semantic_refs(
                        semantic, "bounded_nonrestoration_refs", available, errors
                    )
    elif continuity == "persistent_unrepaired":
        _require_semantic_refs(
            semantic, "repeated_or_cross_period_refs", available, errors
        )


def _network_entities(
    semantic: Mapping[str, Any], key: str, errors: list[str]
) -> tuple[str, ...]:
    value = semantic.get(key)
    if not _is_sequence(value) or not value:
        errors.append(f"semantic_evidence.{key}:missing_or_empty")
        return ()
    result = tuple(value)
    if any(not isinstance(item, str) or not item for item in result):
        errors.append(f"semantic_evidence.{key}:invalid")
        return ()
    if len(set(result)) != len(result):
        errors.append(f"semantic_evidence.{key}:duplicate")
    return result


def _lint_anti_nepotism(
    task: Mapping[str, Any],
    gold: Mapping[str, Any],
    semantic: Mapping[str, Any],
    factors: Mapping[str, Any],
    available: set[str],
    errors: list[str],
) -> None:
    context_kind = gold.get("context_kind", task.get("context_kind"))
    if context_kind not in _AN_OWNED_FACTORS:
        errors.append("anti_nepotism:invalid_context_kind")
    elif set(factors) != _AN_OWNED_FACTORS[context_kind]:
        errors.append("anti_nepotism:owned_factor_set_mismatch")

    applicability_case = gold.get(
        "applicability_case", semantic.get("applicability_case")
    )
    applicability_requirements = {
        "pollution_event": (
            "private_relation_anchor_refs",
            "public_appointment_or_office_effect_refs",
            "ruler_responsibility_refs",
        ),
        "prevention_event": (
            "private_relation_anchor_refs",
            "proposed_public_appointment_refs",
            "ruler_recusal_or_refusal_refs",
        ),
        "correction_event": (
            "established_pollution_refs",
            "ruler_correction_action_refs",
        ),
        "outside_rule": (),
        "unresolved": (),
    }
    if applicability_case not in applicability_requirements:
        errors.append("anti_nepotism:invalid_or_missing_applicability_case")
    else:
        for field in applicability_requirements[applicability_case]:
            _require_semantic_refs(semantic, field, available, errors)
        applicability = gold.get("applicability")
        expected_applicability = {
            "pollution_event": "applicable",
            "prevention_event": "applicable",
            "correction_event": "applicable",
            "outside_rule": "not_applicable",
            "unresolved": "insufficient_evidence",
        }[applicability_case]
        if applicability != expected_applicability:
            errors.append("anti_nepotism:applicability_case_state_mismatch")

    process = _option(factors, "process_integrity")
    if process == "channel_captured":
        _require_semantic_refs(
            semantic, "appointment_gate_control_refs", available, errors
        )

    network = _option(factors, "network_effect")
    if network in {
        "cross_person_single_channel",
        "cross_channel_capture",
        "durable_capture",
    }:
        people = _network_entities(semantic, "network_people", errors)
        channels = _network_entities(semantic, "appointment_channels", errors)
        _require_semantic_refs(semantic, "network_people_refs", available, errors)
        _require_semantic_refs(semantic, "network_channel_refs", available, errors)
        if len(set(people)) < 2:
            errors.append("anti_nepotism:network_requires_two_people")
        if network == "cross_person_single_channel" and len(set(channels)) != 1:
            errors.append("anti_nepotism:single_channel_requires_exactly_one_channel")
        if network in {"cross_channel_capture", "durable_capture"}:
            if len(set(channels)) < 2:
                errors.append("anti_nepotism:cross_channel_requires_two_channels")
            _require_semantic_refs(
                semantic, "channel_control_refs", available, errors
            )
        if network == "durable_capture":
            _require_semantic_refs(
                semantic, "cross_period_or_repeated_refs", available, errors
            )
    elif network == "dismantled_by_ruler":
        _require_semantic_refs(
            semantic, "ruler_correction_action_refs", available, errors
        )
    elif network == "isolated_no_network":
        _require_semantic_refs(semantic, "bounded_absence_refs", available, errors)


def lint_i5b_rule_semantic_gold(
    rule_code: str, task: Mapping[str, Any], gold_factors: Mapping[str, Any]
) -> tuple[str, ...]:
    """Return stable error codes for one v2 task/Gold unit, without I/O."""

    errors: list[str] = []
    if rule_code not in SUPPORTED_RULES:
        return (f"rule_code:unsupported:{rule_code}",)
    if not isinstance(task, Mapping):
        return ("task:not_mapping",)
    if not isinstance(gold_factors, Mapping):
        return ("gold_factors:not_mapping",)

    available = _task_assertion_refs(task)
    if not available:
        errors.append("task:missing_assertion_refs")
    semantic = _semantic_evidence(task, gold_factors, errors)
    factors = gold_factors.get("factors")
    if not isinstance(factors, Mapping) or not factors:
        errors.append("gold_factors.factors:missing_or_invalid")
        return tuple(sorted(set(errors)))

    applicability = gold_factors.get("applicability")
    if applicability not in {"applicable", "not_applicable", "insufficient_evidence"}:
        errors.append("gold_factors.applicability:invalid_or_missing")
    if applicability != "applicable":
        non_terminal = [
            name for name in factors if _option(factors, name) != applicability
        ]
        if non_terminal:
            errors.append("gold_factors:terminal_unit_has_substantive_factor")
        if rule_code == "anti_nepotism":
            _lint_anti_nepotism(
                task, gold_factors, semantic, factors, available, errors
            )
        return tuple(sorted(set(errors)))

    _check_factor_refs(factors, available, errors)
    if rule_code == "talent_discovery":
        _lint_talent_discovery(semantic, factors, available, errors)
    elif rule_code == "tolerate_talent":
        _lint_tolerate_talent(semantic, factors, available, errors)
    else:
        _lint_anti_nepotism(
            task, gold_factors, semantic, factors, available, errors
        )
    return tuple(sorted(set(errors)))


def validate_i5b_rule_semantic_gold(
    rule_code: str, task: Mapping[str, Any], gold_factors: Mapping[str, Any]
) -> None:
    """Fail closed when a v2 Gold factor payload outruns its task material."""

    errors = lint_i5b_rule_semantic_gold(rule_code, task, gold_factors)
    if errors:
        raise ValueError("I5B rule semantic Gold lint failed: " + "; ".join(errors))
