from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.episode import (
    AssertionLink,
    EpisodeParticipant,
    HistoricalEpisodePacket,
)


def _normalized(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return "".join(text.split()).casefold()


@dataclass(frozen=True, slots=True)
class EpisodeCandidateKey:
    evaluation_context: str
    participant_roles: tuple[tuple[str, str], ...]
    episode_type: str
    action_kind: str
    responsibility_domain: str
    normalized_time: str
    location: str
    candidate_boundary_key: str = ""

    @property
    def fingerprint(self) -> str:
        payload = {
            "evaluation_context": self.evaluation_context,
            "participant_roles": self.participant_roles,
            "episode_type": self.episode_type,
            "action_kind": self.action_kind,
            "responsibility_domain": self.responsibility_domain,
            "normalized_time": self.normalized_time,
            "location": self.location,
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EpisodeCandidateGroup:
    key: EpisodeCandidateKey
    assertions: tuple[AssertionDraft, ...]
    boundary_hint: str | None = None


def candidate_key(assertion: AssertionDraft) -> EpisodeCandidateKey:
    qualifiers = assertion.qualifiers
    context = qualifiers.get("evaluation_context")
    if not context:
        raise ValueError(f"assertion 缺少 evaluation_context: {assertion.assertion_code}")

    raw_roles = qualifiers.get("candidate_participant_roles") or (
        (context, "ruler"),
        (assertion.subject, "actor"),
    )
    participant_roles = tuple(
        sorted(
            {
                (_normalized(person), _normalized(role))
                for person, role in raw_roles
                if person and role
            }
        )
    )
    if not participant_roles:
        raise ValueError(f"assertion 缺少候选 participant: {assertion.assertion_code}")

    return EpisodeCandidateKey(
        evaluation_context=_normalized(context),
        participant_roles=participant_roles,
        episode_type=_normalized(qualifiers.get("episode_type") or assertion.predicate),
        action_kind=_normalized(assertion.predicate),
        responsibility_domain=_normalized(qualifiers.get("office_or_domain")),
        normalized_time=_normalized(assertion.time_expression),
        location=_normalized(assertion.location_expression),
    )


def group_episode_candidates(
    assertions: Iterable[AssertionDraft],
) -> tuple[EpisodeCandidateGroup, ...]:
    groups: dict[EpisodeCandidateKey, list[AssertionDraft]] = {}
    assertion_membership: set[str] = set()
    for assertion in assertions:
        if assertion.assertion_code in assertion_membership:
            raise ValueError(f"重复 assertion 输入: {assertion.assertion_code}")
        assertion_membership.add(assertion.assertion_code)
        groups.setdefault(candidate_key(assertion), []).append(assertion)

    return tuple(
        EpisodeCandidateGroup(
            key=key,
            assertions=tuple(sorted(items, key=lambda assertion: assertion.assertion_code)),
        )
        for key, items in sorted(groups.items(), key=lambda item: item[0].fingerprint)
    )


def group_episode_candidates_with_hints(
    assertions: Iterable[AssertionDraft],
    boundary_hints: dict[str, str],
) -> tuple[EpisodeCandidateGroup, ...]:
    """按显式语义边界提示聚合，再从组内结构化字段生成身份候选。"""

    groups: dict[str, list[AssertionDraft]] = {}
    seen: set[str] = set()
    for assertion in assertions:
        if assertion.assertion_code in seen:
            raise ValueError(f"重复 assertion 输入: {assertion.assertion_code}")
        seen.add(assertion.assertion_code)
        hint = boundary_hints.get(assertion.assertion_code)
        if not hint:
            raise ValueError(f"assertion 缺少显式边界提示: {assertion.assertion_code}")
        groups.setdefault(hint, []).append(assertion)

    results: list[EpisodeCandidateGroup] = []
    for hint, items in groups.items():
        contexts = {_normalized(item.qualifiers.get("evaluation_context")) for item in items}
        if "" in contexts or len(contexts) != 1:
            raise ValueError(f"边界提示跨 evaluation context: {hint}")
        episode_types = {
            _normalized(item.qualifiers.get("episode_type") or item.predicate)
            for item in items
        }
        if "" in episode_types or len(episode_types) != 1:
            raise ValueError(f"边界提示跨 episode type: {hint}")
        participant_roles = tuple(
            sorted(
                {
                    (_normalized(person), _normalized(role))
                    for item in items
                    for person, role in (
                        item.qualifiers.get("candidate_participant_roles")
                        or (
                            (item.qualifiers.get("evaluation_context"), "ruler"),
                            (item.subject, "actor"),
                        )
                    )
                    if person and role
                }
            )
        )
        domains = sorted(
            {
                _normalized(item.qualifiers.get("office_or_domain"))
                for item in items
                if item.qualifiers.get("office_or_domain")
            }
        )
        times = sorted(
            {_normalized(item.time_expression) for item in items if item.time_expression}
        )
        locations = sorted(
            {
                _normalized(item.location_expression)
                for item in items
                if item.location_expression
            }
        )
        action_kinds = sorted({_normalized(item.predicate) for item in items})
        key = EpisodeCandidateKey(
            evaluation_context=next(iter(contexts)),
            participant_roles=participant_roles,
            episode_type=next(iter(episode_types)),
            action_kind="|".join(action_kinds),
            responsibility_domain="|".join(domains),
            normalized_time="|".join(times),
            location="|".join(locations),
            candidate_boundary_key=_normalized(hint),
        )
        results.append(
            EpisodeCandidateGroup(
                key=key,
                assertions=tuple(
                    sorted(items, key=lambda assertion: assertion.assertion_code)
                ),
                boundary_hint=hint,
            )
        )
    return tuple(sorted(results, key=lambda group: group.key.fingerprint))


def _slot_state(values: list[str], *, allow_not_applicable: bool = False) -> str:
    present = [value for value in values if value]
    if present:
        return "complete" if len(present) == len(values) else "partial"
    return "not_applicable" if allow_not_applicable else "missing"


def build_episode_packet(
    group: EpisodeCandidateGroup,
    *,
    episode_status: str = "proposed",
) -> HistoricalEpisodePacket:
    assertions = group.assertions
    if not assertions:
        raise ValueError("不能从空候选组构造 episode")

    outcomes = tuple(
        sorted(
            {
            str(item.qualifiers.get("outcome"))
            for item in assertions
            if item.qualifiers.get("outcome")
            }
        )
    )
    consequences = tuple(
        sorted(
            {
            str(
                item.qualifiers.get("consequence")
                or item.qualifiers.get("cost_or_damage")
            )
            for item in assertions
            if item.qualifiers.get("consequence")
            or item.qualifiers.get("cost_or_damage")
            }
        )
    )
    conflicts = tuple(
        sorted(item.assertion_code for item in assertions if item.polarity == "disputed")
    )
    source_documents = {
        item.source_attribution.get("document_code")
        for item in assertions
        if item.source_attribution.get("document_code")
    }
    completeness = {
        "identity": "complete" if group.key.participant_roles else "missing",
        "time": _slot_state([item.time_expression or "" for item in assertions]),
        "action": _slot_state([item.predicate for item in assertions]),
        "responsibility": _slot_state(
            [str(item.qualifiers.get("office_or_domain") or "") for item in assertions]
        ),
        "outcome": "complete" if outcomes else "missing",
        "consequence": "complete" if consequences else "not_applicable",
        "source_diversity": "complete" if len(source_documents) > 1 else "partial",
        "conflict_resolution": "conflicted" if conflicts else "complete",
    }
    roles_by_person: dict[str, set[str]] = {}
    for person, role in group.key.participant_roles:
        roles_by_person.setdefault(person, set()).add(role)
    participants = tuple(
        EpisodeParticipant(person_ref=person, role_codes=tuple(sorted(roles)))
        for person, roles in sorted(roles_by_person.items())
    )
    links = tuple(
        AssertionLink(
            assertion_ref=item.assertion_code,
            source_passage_ref=item.source_passage_ref,
            relation="contradicts" if item.polarity == "disputed" else "supports",
            supported_fields=("action", "responsibility", "outcome"),
        )
        for item in sorted(assertions, key=lambda assertion: assertion.assertion_code)
    )
    uncertainties = tuple(
        sorted({flag for item in assertions for flag in item.ambiguity_flags})
    )
    actions = sorted({item.predicate for item in assertions})

    provenance = {"builder": "deterministic_episode_kernel_v1"}
    if group.boundary_hint:
        provenance["candidate_boundary_key"] = group.boundary_hint

    return HistoricalEpisodePacket(
        episode_id=f"EP-{group.key.fingerprint[:20].upper()}",
        episode_type=group.key.episode_type,
        episode_status=episode_status,
        evaluation_context=group.key.evaluation_context,
        semantic_version=1,
        evidence_version=1,
        semantic_fingerprint=group.key.fingerprint,
        time_start=group.key.normalized_time or None,
        time_end=group.key.normalized_time or None,
        time_precision="source_expression" if group.key.normalized_time else "unknown",
        locations=(group.key.location,) if group.key.location else (),
        participants=participants,
        action=" | ".join(actions),
        responsibility=group.key.responsibility_domain or None,
        outcome=outcomes,
        consequence=consequences,
        assertion_links=links,
        conflicts=conflicts,
        uncertainties=uncertainties,
        completeness=completeness,
        lineage={"origin": "created"},
        provenance=provenance,
    )
