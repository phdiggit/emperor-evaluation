from __future__ import annotations

import json
import re
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


_ACTION_ANCHOR_PRIORITY = {
    "任命": 0,
    "任命统兵": 0,
    "授权": 1,
    "荐举": 2,
    "处置": 3,
    "保全": 4,
    "战役": 5,
}
_BOUNDARY_BREAK_MARKERS = ("撤销", "罢免", "解除", "再次", "重新")
_GENERIC_BIGRAMS = frozenset(
    {
        "太祖",
        "皇帝",
        "任命",
        "授权",
        "处置",
        "战役",
        "军事",
        "中枢",
        "边疆",
        "任务",
        "结果",
        "行军",
        "总管",
        "大使",
        "大将",
        "人物",
        "事件",
    }
)


def _raw_roles(assertion: AssertionDraft) -> tuple[tuple[str, str], ...]:
    context = assertion.qualifiers.get("evaluation_context")
    return tuple(
        (str(person), str(role))
        for person, role in (
            assertion.qualifiers.get("candidate_participant_roles")
            or ((context, "ruler"), (assertion.subject, "actor"))
        )
        if person and role
    )


def _entity_names(assertion: AssertionDraft) -> set[str]:
    context = _normalized(assertion.qualifiers.get("evaluation_context"))
    return {
        _normalized(person)
        for person, role in _raw_roles(assertion)
        if _normalized(person) and _normalized(person) != context and role != "ruler"
    }


def _object_mentions_entity(assertion: AssertionDraft, entities: set[str]) -> bool:
    object_text = _normalized(assertion.object)
    return any(len(entity) >= 2 and entity in object_text for entity in entities)


def _semantic_bigrams(text: object, excluded_names: set[str] | None = None) -> set[str]:
    normalized = _normalized(text)
    for name in excluded_names or ():
        normalized = normalized.replace(name, "")
    normalized = re.sub(r"[^\u3400-\u9fff0-9a-z]+", "", normalized)
    return {
        normalized[index : index + 2]
        for index in range(max(0, len(normalized) - 1))
        if normalized[index : index + 2] not in _GENERIC_BIGRAMS
    }


def _time_core(value: str | None) -> str:
    normalized = _normalized(value)
    return re.sub(r"[（(][^）)]*[）)]", "", normalized)


def _regnal_year(value: str | None) -> tuple[str, str] | None:
    match = re.match(
        r"^([\u3400-\u9fff]{2,4}?)(元|[一二三四五六七八九十百]+)年",
        value or "",
    )
    return (match.group(1), match.group(2)) if match else None


def _has_explicit_same_era_conflict(left: str | None, right: str | None) -> bool:
    left_year = _regnal_year(left)
    right_year = _regnal_year(right)
    return bool(
        left_year
        and right_year
        and left_year[0] == right_year[0]
        and left_year[1] != right_year[1]
    )


def _incompatible_action_boundary(left: str, right: str) -> bool:
    if left == right:
        return False
    return any(marker in left or marker in right for marker in _BOUNDARY_BREAK_MARKERS)


def _terminal_followup_mismatch(left: AssertionDraft, right: AssertionDraft) -> bool:
    markers = ("死后", "卒后", "被诛后", "死之明年", "诛杀后")
    left_terminal = any(marker in (left.time_expression or "") for marker in markers)
    right_terminal = any(marker in (right.time_expression or "") for marker in markers)
    if left_terminal == right_terminal:
        return False
    non_terminal = right if left_terminal else left
    non_terminal_payload = "".join(
        (
            non_terminal.object,
            str(non_terminal.qualifiers.get("outcome") or ""),
            str(
                non_terminal.qualifiers.get("claim_summary")
                or non_terminal.qualifiers.get("legacy_claim_summary")
                or ""
            ),
        )
    )
    return not any(marker in non_terminal_payload for marker in ("死", "诛", "杀"))


def _should_merge_assertions(left: AssertionDraft, right: AssertionDraft) -> bool:
    if left.assertion_code == right.assertion_code:
        return True
    if _normalized(left.qualifiers.get("evaluation_context")) != _normalized(
        right.qualifiers.get("evaluation_context")
    ):
        return False
    if _normalized(left.qualifiers.get("episode_type") or left.predicate) != _normalized(
        right.qualifiers.get("episode_type") or right.predicate
    ):
        return False
    if _incompatible_action_boundary(left.predicate, right.predicate):
        return False
    if _terminal_followup_mismatch(left, right):
        return False

    left_claim = left.extraction_provenance.get("claim_key")
    right_claim = right.extraction_provenance.get("claim_key")
    if left_claim and left_claim == right_claim:
        return True

    left_entities = _entity_names(left)
    right_entities = _entity_names(right)
    entities_connected = bool(left_entities & right_entities)
    entities_connected = entities_connected or _object_mentions_entity(
        left, right_entities
    )
    entities_connected = entities_connected or _object_mentions_entity(
        right, left_entities
    )
    if not entities_connected:
        return False

    excluded_names = left_entities | right_entities | {
        _normalized(left.qualifiers.get("evaluation_context")),
    }
    left_topic = _semantic_bigrams(
        "".join(
            (
                left.object,
                str(left.qualifiers.get("office_or_domain") or ""),
                str(
                    left.qualifiers.get("claim_summary")
                    or left.qualifiers.get("legacy_claim_summary")
                    or ""
                ),
            )
        ),
        excluded_names,
    )
    right_topic = _semantic_bigrams(
        "".join(
            (
                right.object,
                str(right.qualifiers.get("office_or_domain") or ""),
                str(
                    right.qualifiers.get("claim_summary")
                    or right.qualifiers.get("legacy_claim_summary")
                    or ""
                ),
            )
        ),
        excluded_names,
    )
    topic_overlap = left_topic & right_topic
    left_time = _time_core(left.time_expression)
    right_time = _time_core(right.time_expression)
    time_equivalent = bool(left_time and left_time == right_time)
    time_contains = bool(
        left_time
        and right_time
        and min(len(left_time), len(right_time)) >= 3
        and (left_time in right_time or right_time in left_time)
    )
    same_source_slice = bool(
        left.source_attribution.get("source_slice_ref")
        and left.source_attribution.get("source_slice_ref")
        == right.source_attribution.get("source_slice_ref")
    )
    same_scope = bool(
        left.qualifiers.get("event_scope")
        and left.qualifiers.get("event_scope") == right.qualifiers.get("event_scope")
    )
    domain_overlap = _semantic_bigrams(
        left.qualifiers.get("office_or_domain"), excluded_names
    ) & _semantic_bigrams(right.qualifiers.get("office_or_domain"), excluded_names)

    if (
        time_equivalent
        and left.predicate == right.predicate
        and left.qualifiers.get("office_or_domain")
        and right.qualifiers.get("office_or_domain")
        and _normalized(left.qualifiers.get("office_or_domain"))
        != _normalized(right.qualifiers.get("office_or_domain"))
    ):
        return False
    if time_equivalent and (topic_overlap or domain_overlap or same_scope):
        return True
    if time_contains and (topic_overlap or domain_overlap):
        return True
    if _has_explicit_same_era_conflict(
        left.time_expression, right.time_expression
    ) and not (
        same_source_slice
        and len(topic_overlap) >= 2
        and left.predicate != right.predicate
    ):
        return False
    if same_source_slice and (topic_overlap or domain_overlap):
        return True
    if topic_overlap and (
        len(topic_overlap) >= 2
        or same_scope
        or left.predicate == right.predicate
        or {left.predicate, right.predicate} <= {"任命", "授权", "战役", "处置", "其他", "失职"}
    ):
        return True
    return False


def _anchor_assertion(assertions: Iterable[AssertionDraft]) -> AssertionDraft:
    return min(
        assertions,
        key=lambda item: (
            _ACTION_ANCHOR_PRIORITY.get(item.predicate, 50),
            _normalized(item.time_expression),
            _normalized(item.qualifiers.get("office_or_domain")),
            item.assertion_code,
        ),
    )


def group_episode_candidates(
    assertions: Iterable[AssertionDraft],
) -> tuple[EpisodeCandidateGroup, ...]:
    items = tuple(assertions)
    assertion_membership: set[str] = set()
    for assertion in items:
        if assertion.assertion_code in assertion_membership:
            raise ValueError(f"重复 assertion 输入: {assertion.assertion_code}")
        assertion_membership.add(assertion.assertion_code)

    parents = list(range(len(items)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left_index: int, right_index: int) -> None:
        left_root = find(left_index)
        right_root = find(right_index)
        if left_root != right_root:
            parents[right_root] = left_root

    for left_index, left in enumerate(items):
        for right_index in range(left_index + 1, len(items)):
            if _should_merge_assertions(left, items[right_index]):
                union(left_index, right_index)

    components: dict[int, list[AssertionDraft]] = {}
    for index, assertion in enumerate(items):
        components.setdefault(find(index), []).append(assertion)

    groups = []
    for component in components.values():
        anchor = _anchor_assertion(component)
        groups.append(
            EpisodeCandidateGroup(
                key=candidate_key(anchor),
                assertions=tuple(
                    sorted(component, key=lambda assertion: assertion.assertion_code)
                ),
            )
        )
    return tuple(sorted(groups, key=lambda group: group.key.fingerprint))


def group_episode_candidates_exact(
    assertions: Iterable[AssertionDraft],
) -> tuple[EpisodeCandidateGroup, ...]:
    """V1 exact-key grouping retained only for Oracle artifact reproducibility."""

    groups: dict[EpisodeCandidateKey, list[AssertionDraft]] = {}
    seen: set[str] = set()
    for assertion in assertions:
        if assertion.assertion_code in seen:
            raise ValueError(f"重复 assertion 输入: {assertion.assertion_code}")
        seen.add(assertion.assertion_code)
        groups.setdefault(candidate_key(assertion), []).append(assertion)
    return tuple(
        EpisodeCandidateGroup(
            key=key,
            assertions=tuple(sorted(items, key=lambda item: item.assertion_code)),
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
    for item in assertions:
        for person, role in _raw_roles(item):
            normalized_person = _normalized(person)
            normalized_role = _normalized(role)
            if normalized_person and normalized_role:
                roles_by_person.setdefault(normalized_person, set()).add(normalized_role)
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
