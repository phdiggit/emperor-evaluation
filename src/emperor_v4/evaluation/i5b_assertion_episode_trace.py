from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.contracts.episode import (
    AssertionLink,
    EpisodeParticipant,
    HistoricalEpisodePacket,
)
from emperor_v4.domain.boundary import draft_rule_evidence_unit
from emperor_v4.contracts.assertion import (
    AssertionDraft,
    assertion_draft_from_payload,
)
from emperor_v4.domain.episode import (
    EpisodeCandidateGroup,
    build_episode_packet,
    group_episode_candidates_with_hints,
)
from emperor_v4.persistence.postgres_schema_governance import canonical_person_ref


def _hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _rows(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} may contain only objects")
    return list(value)


def _event_node_ref(assertion: Mapping[str, Any]) -> str:
    return str(
        assertion.get("event_node_ref")
        or assertion.get("candidate_episode_key")
        or ""
    ).strip()


def _canonical_assertion(
    payload: Mapping[str, Any], *, ruler_ref: str
) -> AssertionDraft:
    draft = assertion_draft_from_payload(payload)
    qualifiers = dict(draft.qualifiers)
    focal_refs = tuple(
        dict.fromkeys(
            canonical_person_ref(ref)
            for ref in qualifiers.get("candidate_focal_person_refs") or ()
            if canonical_person_ref(ref).startswith("PER-")
            and canonical_person_ref(ref) != ruler_ref
        )
    )
    qualifiers = {
        "responsibility_family": qualifiers.get("responsibility_family"),
        "office_or_domain": qualifiers.get("office_or_domain"),
        "outcome": qualifiers.get("outcome"),
        "cost_or_damage": qualifiers.get("cost_or_damage"),
        "focal_person_ref": focal_refs[0] if len(focal_refs) == 1 else None,
        "candidate_focal_person_refs": list(focal_refs),
        "event_scope": qualifiers.get("event_scope"),
        "normalized_time": qualifiers.get("normalized_time"),
        "evaluation_context": ruler_ref,
        "episode_type": "political_action",
        "candidate_participant_roles": (
            (ruler_ref, "ruler"),
            *((ref, "focal_person") for ref in focal_refs),
        ),
    }
    return replace(draft, qualifiers=qualifiers)


def _accepted_episode(
    group: EpisodeCandidateGroup,
    *,
    assertion_payload: Mapping[str, Any],
    formal_acceptance: bool,
) -> HistoricalEpisodePacket:
    packet = build_episode_packet(group)
    if not formal_acceptance:
        return replace(
            packet,
            evaluation_context=str((assertion_payload.get("scope") or {})["ruler_ref"]),
            provenance={
                "builder": "deterministic_episode_kernel_v1",
                "input_version": str(
                    assertion_payload.get("schema_version") or "unknown"
                ),
                "input_hash": str(
                    assertion_payload.get("report_sha256") or "unknown"
                ),
            },
        )

    uncertainties = tuple(
        dict.fromkeys(
            flag
            for assertion in group.assertions
            for flag in assertion.ambiguity_flags
        )
    )
    links = tuple(
        AssertionLink(
            assertion_ref=assertion.assertion_code,
            source_passage_ref=assertion.source_passage_ref,
            relation=(
                "contradicts" if assertion.polarity == "disputed" else "supports"
            ),
            supported_fields=(
                tuple(assertion.passage_support.supported_fields)
                if assertion.passage_support is not None
                else ("identity", "action")
            ),
            evidence_status="accepted",
            representative=index == 0,
        )
        for index, assertion in enumerate(group.assertions)
    )
    roles_by_person: dict[str, set[str]] = {}
    for assertion in group.assertions:
        for person_ref, role_code in (
            assertion.qualifiers.get("candidate_participant_roles") or ()
        ):
            canonical_ref = canonical_person_ref(person_ref)
            if canonical_ref.startswith("PER-"):
                roles_by_person.setdefault(canonical_ref, set()).add(str(role_code))
    participants = tuple(
        EpisodeParticipant(
            person_ref=person_ref,
            role_codes=tuple(sorted(role_codes)),
            role_status="resolved",
        )
        for person_ref, role_codes in sorted(roles_by_person.items())
    )
    completeness = dict(packet.completeness)
    if completeness.get("responsibility") == "missing":
        completeness["responsibility"] = "not_applicable"
    source_passage_refs = sorted({link.source_passage_ref for link in links})
    episode_status = (
        "needs_evidence_review"
        if completeness.get("outcome") == "missing"
        else "accepted_with_uncertainty"
        if uncertainties
        else "accepted"
    )
    if episode_status == "needs_evidence_review":
        uncertainties = tuple(
            dict.fromkeys((*uncertainties, "outcome completeness missing"))
        )
    return replace(
        packet,
        episode_status=episode_status,
        evaluation_context=canonical_person_ref(
            (assertion_payload.get("scope") or {})["ruler_ref"]
        ),
        participants=participants,
        assertion_links=links,
        uncertainties=uncertainties,
        completeness=completeness,
        lineage={
            "origin": "created",
            "assertion_report_sha256": str(
                assertion_payload.get("report_sha256") or ""
            ),
            "source_passage_refs": ",".join(source_passage_refs),
        },
        provenance={
            "builder": "deterministic_episode_kernel_v1",
            "input_version": str(
                assertion_payload.get("schema_version") or "unknown"
            ),
            "input_hash": str(
                assertion_payload.get("report_sha256") or "unknown"
            ),
        },
    )


def _merge_neutral_identity_groups(
    groups: Sequence[EpisodeCandidateGroup],
) -> tuple[EpisodeCandidateGroup, ...]:
    """Collapse rule-boundary hints that resolve to the same neutral fact."""
    merged: dict[str, tuple[Any, dict[str, AssertionDraft]]] = {}
    for group in groups:
        fingerprint = group.key.fingerprint
        if fingerprint not in merged:
            merged[fingerprint] = (group.key, {})
        assertions = merged[fingerprint][1]
        for assertion in group.assertions:
            assertions[assertion.assertion_code] = assertion
    return tuple(
        EpisodeCandidateGroup(
            key=key,
            assertions=tuple(assertions[ref] for ref in sorted(assertions)),
            boundary_hint=None,
        )
        for fingerprint, (key, assertions) in sorted(merged.items())
    )


def build_assertion_episode_trace(
    *,
    rule_code: str,
    trace_units: list[dict[str, Any]],
    assertion_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if assertion_payload.get("profile_code") != f"{rule_code}_chain_v1":
        raise ValueError("assertion review profile 与 scored shadow rule 不一致")
    summary = assertion_payload.get("summary") or {}
    if int(summary.get("pending_blocking_review_unit_count", -1)) != 0:
        raise ValueError("assertion review 仍有 blocking unit，不得生成 Episode trace")
    ruler_ref = str((assertion_payload.get("scope") or {}).get("ruler_ref") or "")
    if not ruler_ref.startswith("PER-"):
        raise ValueError("assertion review 必须声明 canonical ruler_ref")
    formal_acceptance = bool(
        (assertion_payload.get("declarations") or {}).get("formal_fact_acceptance")
    )
    ruler_ref = canonical_person_ref(ruler_ref)
    units = {
        str(item.get("unit_ref") or ""): item
        for item in _rows(assertion_payload.get("units"), "assertion review units")
    }
    selected_unit_refs = {
        str(material.get("unit_ref") or "") for material in trace_units
    }
    allowed_dispositions = (
        {"formally_accepted"}
        if formal_acceptance
        else {"reviewed_ready_for_episode_shadow"}
    )
    assertion_by_ref: dict[str, AssertionDraft] = {}
    boundary_hints: dict[str, str] = {}
    assertion_refs_by_unit: dict[str, set[str]] = {}
    for unit_ref in sorted(selected_unit_refs):
        unit = units.get(unit_ref)
        if unit is None:
            continue
        if unit.get("review_disposition") not in allowed_dispositions:
            raise ValueError(f"assertion unit 尚未完成 review: {unit_ref}")
        unit_assertion_refs: set[str] = set()
        for raw_assertion in _rows(
            unit.get("assertion_drafts"), f"{unit_ref} assertions"
        ):
            assertion = _canonical_assertion(raw_assertion, ruler_ref=ruler_ref)
            if assertion.assertion_code in assertion_by_ref:
                raise ValueError(f"正式事实 Assertion 重复: {assertion.assertion_code}")
            group_ref = (
                _event_node_ref(raw_assertion)
                if formal_acceptance
                else assertion.source_passage_ref
            )
            if not group_ref:
                raise ValueError(
                    f"Assertion 缺少事件边界: {unit_ref}/{assertion.assertion_code}"
                )
            assertion_by_ref[assertion.assertion_code] = assertion
            boundary_hints[assertion.assertion_code] = group_ref
            unit_assertion_refs.add(assertion.assertion_code)
        assertion_refs_by_unit[unit_ref] = unit_assertion_refs

    groups = _merge_neutral_identity_groups(
        group_episode_candidates_with_hints(
            assertion_by_ref.values(), boundary_hints
        )
    )
    packets = tuple(
        _accepted_episode(
            group,
            assertion_payload=assertion_payload,
            formal_acceptance=formal_acceptance,
        )
        for group in groups
    )
    episode_by_assertion = {
        link.assertion_ref: packet.episode_id
        for packet in packets
        if packet.episode_status in {"accepted", "accepted_with_uncertainty"}
        for link in packet.assertion_links
    }
    episodes = [asdict(packet) for packet in packets]
    evidence_units: list[dict[str, Any]] = []
    assertion_link_count = sum(len(packet.assertion_links) for packet in packets)
    for material in trace_units:
        unit_ref = material["unit_ref"]
        unit = units.get(unit_ref)
        if unit is None:
            continue
        assertion_refs = sorted(assertion_refs_by_unit.get(unit_ref) or ())
        member_role = (
            "negative_credit_chain_component"
            if material["side"] == "negative"
            else "positive_feedback_chain_component"
        )
        episode_members = {
            episode_by_assertion[assertion_ref]: member_role
            for assertion_ref in assertion_refs
            if assertion_ref in episode_by_assertion
        }
        reu = draft_rule_evidence_unit(
            rule_code=rule_code,
            rule_version="i5b-factor-semantics-v2",
            aggregation_policy_version="i5b-joint-projection-score-contribution-v2",
            evaluation_context=ruler_ref,
            episode_members=episode_members,
            relation_members={},
            aggregation_reason=material["projection_basis"],
        )
        reu_payload = asdict(reu)
        if formal_acceptance:
            reu_payload["status"] = "shadow_from_formal_facts"
            reu_payload["lineage"] = {
                "origin": "formal_fact_acceptance",
                "acceptance_report_sha256": str(
                    assertion_payload.get("report_sha256") or ""
                ),
                "persistence_status": "not_persisted_by_core_registry",
            }
        evidence_units.append(reu_payload)
        material["assertion_draft_refs"] = sorted(assertion_refs)
        material["rule_evidence_unit_ref"] = reu.unit_code
        material["semantic_fingerprint"] = _hash(
            {
                key: value
                for key, value in material.items()
                if key != "semantic_fingerprint"
            }
        )
    result = {
        "status": (
            "accepted_assertion_to_episode_shadow_reu_trace_complete"
            if formal_acceptance
            else "reviewed_assertion_to_episode_reu_shadow_complete"
        ),
        "source_assertion_report_sha256": assertion_payload.get("report_sha256"),
        "episode_count": len(episodes),
        "rule_evidence_unit_count": len(evidence_units),
        "assertion_link_count": assertion_link_count,
        "episodes": episodes,
        "rule_evidence_units": evidence_units,
        "formal_acceptance_performed": formal_acceptance,
        "database_write_count": 0,
    }
    if formal_acceptance:
        result["rule_evidence_unit_persistence_performed"] = False
    return result
