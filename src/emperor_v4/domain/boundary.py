from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Callable, Iterable, Mapping, Protocol

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.boundary import (
    AmbiguityIssue,
    AssertionDisposition,
    BoundaryMaterializationResult,
    BoundaryReviewRequest,
    ContextAssertionLink,
    EpisodeBoundaryGroup,
    EpisodeBoundaryReviewResult,
    EpisodeRelation,
    EpisodeRelationDraft,
    EpisodeReviewUnit,
    NormalizedTime,
    PropositionCluster,
    RelationEvidenceLink,
    RuleEvidenceMember,
    RuleEvidenceUnitDraft,
)
from emperor_v4.contracts.episode import HistoricalEpisodePacket
from emperor_v4.domain.episode import (
    build_episode_packet,
    group_episode_candidates_with_hints,
)


BOUNDARY_POLICY_VERSION = "episode-boundary-policy-v2.7"
BOUNDARY_OUTPUT_SCHEMA_VERSION = "episode-boundary-review-v2.7"
DEFAULT_MODEL_FAMILY = "semantic-boundary-reviewer"

_FOCAL_ROLE_PRIORITY = {
    "delegate": 0,
    "office_holder": 1,
    "commander": 2,
    "focus_person": 3,
    "subject_person": 4,
    "advisor": 5,
    "beneficiary": 6,
    "opponent": 7,
    "victim": 8,
    "actor": 9,
    "source_speaker": 10,
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


def _normalized(value: object) -> str:
    if value is None:
        return ""
    return "".join(unicodedata.normalize("NFKC", str(value)).split()).casefold()


def _hash(payload: object) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def classify_ambiguity(flag: str, episode_type: str) -> AmbiguityIssue:
    mappings = {
        "missing_location_expression": AmbiguityIssue(
            code="missing_location",
            slot="location",
            severity="informational",
            blocking_for_episode_types=("military_campaign", "territorial_operation"),
            source_flag=flag,
        ),
        "missing_time_expression": AmbiguityIssue(
            code="missing_time",
            slot="time",
            severity="warning",
            blocking_for_episode_types=("military_campaign", "territorial_operation"),
            source_flag=flag,
        ),
        "legacy_multi_passage_claim_fanned_out": AmbiguityIssue(
            code="legacy_multi_passage_fanout",
            slot="lineage",
            severity="informational",
            source_flag=flag,
        ),
    }
    if flag in mappings:
        return mappings[flag]
    if "identity" in flag or "pronoun" in flag or "同名" in flag:
        return AmbiguityIssue(
            code=flag, slot="identity", severity="blocking", source_flag=flag
        )
    return AmbiguityIssue(
        code=flag, slot="unspecified", severity="blocking", source_flag=flag
    )


def ambiguity_issues_for_packet(
    packet: HistoricalEpisodePacket,
) -> tuple[AmbiguityIssue, ...]:
    issues = {
        (issue.code, issue.slot, issue.severity, issue.blocking_for_episode_types): issue
        for flag in packet.uncertainties
        for issue in (classify_ambiguity(flag, packet.episode_type),)
    }
    return tuple(issues[key] for key in sorted(issues))


def _participant_roles(assertion: AssertionDraft) -> tuple[tuple[str, str], ...]:
    context = _normalized(assertion.qualifiers.get("evaluation_context"))
    raw = assertion.qualifiers.get("candidate_participant_roles") or (
        (context, "ruler"),
        (assertion.subject, "actor"),
    )
    return tuple(
        sorted(
            {
                (_normalized(person), _normalized(role))
                for person, role in raw
                if person and role
            }
        )
    )


def _focal_identity(
    assertion: AssertionDraft,
) -> tuple[str, str, tuple[str, ...]]:
    roles = _participant_roles(assertion)
    context = _normalized(assertion.qualifiers.get("evaluation_context"))
    explicit_person = _normalized(assertion.qualifiers.get("focal_person_ref"))
    explicit_role = _normalized(assertion.qualifiers.get("focal_role"))
    candidates = [
        (person, role)
        for person, role in roles
        if person != context and role != "ruler"
    ]
    if explicit_person:
        matching_roles = sorted(role for person, role in candidates if person == explicit_person)
        focal_role = explicit_role or (matching_roles[0] if matching_roles else "actor")
        focal_person = explicit_person
    elif candidates:
        focal_person, focal_role = min(
            candidates,
            key=lambda item: (
                _FOCAL_ROLE_PRIORITY.get(item[1], 50),
                item[0],
                item[1],
            ),
        )
    else:
        focal_person, focal_role = _normalized(assertion.subject), "actor"
    secondary = tuple(sorted({person for person, _ in candidates if person != focal_person}))
    return focal_person, focal_role, secondary


def _normalized_time(assertion: AssertionDraft) -> NormalizedTime:
    payload = assertion.qualifiers.get("normalized_time")
    if isinstance(payload, Mapping):
        start = payload.get("start_sort_key")
        end = payload.get("end_sort_key")
        return NormalizedTime(
            start_sort_key=int(start) if start is not None else None,
            end_sort_key=int(end) if end is not None else (int(start) if start is not None else None),
            precision=str(payload.get("precision") or "unknown"),
            dynasty_or_era=(
                str(payload.get("dynasty_or_era"))
                if payload.get("dynasty_or_era")
                else None
            ),
            source_expression=assertion.time_expression,
        )
    return NormalizedTime(
        start_sort_key=None,
        end_sort_key=None,
        precision="legacy_unstructured",
        dynasty_or_era=(
            str(assertion.qualifiers.get("dynasty_or_era"))
            if assertion.qualifiers.get("dynasty_or_era")
            else None
        ),
        source_expression=assertion.time_expression,
    )


def _normalized_time_identity(time: NormalizedTime) -> tuple[object, ...]:
    return (
        time.start_sort_key,
        time.end_sort_key,
        time.precision,
        _normalized(time.dynasty_or_era),
        _normalized(time.source_expression) if time.start_sort_key is None else "",
    )


def _responsibility_family(assertion: AssertionDraft) -> str:
    return _normalized(
        assertion.qualifiers.get("responsibility_family")
        or assertion.qualifiers.get("episode_type")
        or assertion.predicate
    )


def _proposition_tokens(assertion: AssertionDraft) -> tuple[tuple[str, str], ...]:
    context = _normalized(assertion.qualifiers.get("evaluation_context"))
    claim_key = _normalized(assertion.extraction_provenance.get("claim_key"))
    if assertion.passage_support is not None:
        # Passage-scoped v2 has already made an explicit, independently
        # reviewed atomization decision.  The legacy claim key must not join
        # distinct atomic components back together.  Scope the support key to
        # its source claim because semantic keys are only required to be
        # unique within one claim response.
        support_scope = claim_key or _normalized(assertion.assertion_code)
        return (
            (
                context,
                "passage-support:"
                f"{support_scope}:{assertion.passage_support.assertion_semantic_key}",
            ),
        )
    focal_person, focal_role, _ = _focal_identity(assertion)
    time = _normalized_time(assertion)
    semantic = {
        "subject": _normalized(assertion.subject),
        "predicate": _normalized(assertion.predicate),
        "object": _normalized(assertion.object),
        "normalized_time": {
            "start": time.start_sort_key,
            "end": time.end_sort_key,
            "precision": time.precision,
            "era": _normalized(time.dynasty_or_era),
            "legacy_source_expression": (
                _normalized(time.source_expression)
                if time.start_sort_key is None
                else ""
            ),
        },
        "location": _normalized(assertion.location_expression),
        "episode_type": _normalized(assertion.qualifiers.get("episode_type")),
        "responsibility_family": _responsibility_family(assertion),
        "responsibility": _normalized(assertion.qualifiers.get("office_or_domain")),
        "focal_person_ref": focal_person,
        "focal_role": focal_role,
        "polarity": _normalized(assertion.polarity),
        "atomic_event_key": _normalized(
            assertion.qualifiers.get("atomic_event_key")
        ),
    }
    tokens = [(context, f"semantic:{_hash(semantic)}")]
    if claim_key:
        tokens.append((context, f"claim:{claim_key}"))
    return tuple(tokens)


def cluster_propositions(
    assertions: Iterable[AssertionDraft],
) -> tuple[PropositionCluster, ...]:
    items = tuple(assertions)
    seen: set[str] = set()
    parents = list(range(len(items)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    token_owner: dict[tuple[str, str], int] = {}
    for index, assertion in enumerate(items):
        if assertion.assertion_code in seen:
            raise ValueError(f"重复 assertion 输入: {assertion.assertion_code}")
        seen.add(assertion.assertion_code)
        for token in _proposition_tokens(assertion):
            previous = token_owner.setdefault(token, index)
            union(index, previous)

    grouped: dict[int, list[AssertionDraft]] = defaultdict(list)
    for index, assertion in enumerate(items):
        grouped[find(index)].append(assertion)

    clusters = []
    for group_index, group_items in grouped.items():
        group_items.sort(key=lambda item: item.assertion_code)
        context = _normalized(group_items[0].qualifiers.get("evaluation_context"))
        group_key = str(group_index)
        episode_types = {
            _normalized(item.qualifiers.get("episode_type") or item.predicate)
            for item in group_items
        }
        focal_identities = {_focal_identity(item) for item in group_items}
        responsibility_families = {
            _responsibility_family(item) for item in group_items
        }
        time_items = tuple(_normalized_time(item) for item in group_items)
        time_identities = {_normalized_time_identity(item) for item in time_items}
        if (
            len(episode_types) != 1
            or len(focal_identities) != 1
            or len(responsibility_families) != 1
            or len(time_identities) != 1
        ):
            raise ValueError(f"Proposition cluster 语义污染: {group_key}")
        focal_person, focal_role, secondary = next(iter(focal_identities))
        normalized_time = min(
            time_items, key=lambda item: _normalized(item.source_expression)
        )
        semantic_rows = [
            {
                "subject": _normalized(item.subject),
                "predicate": _normalized(item.predicate),
                "object": _normalized(item.object),
                "location": _normalized(item.location_expression),
                "responsibility": _normalized(item.qualifiers.get("office_or_domain")),
                "outcome": _normalized(item.qualifiers.get("outcome")),
                "polarity": _normalized(item.polarity),
                "atomic_event_key": _normalized(
                    item.qualifiers.get("atomic_event_key")
                ),
            }
            for item in group_items
        ]
        unique_rows = {_hash(row): row for row in semantic_rows}
        semantic_hash = _hash(
            {
                "evaluation_context": context,
                "focal_person_ref": focal_person,
                "focal_role": focal_role,
                "secondary_participant_refs": secondary,
                "episode_type": next(iter(episode_types)),
                "responsibility_family": next(iter(responsibility_families)),
                "normalized_time": {
                    "start": normalized_time.start_sort_key,
                    "end": normalized_time.end_sort_key,
                    "precision": normalized_time.precision,
                    "era": _normalized(normalized_time.dynasty_or_era),
                    "legacy_source_expression": (
                        _normalized(normalized_time.source_expression)
                        if normalized_time.start_sort_key is None
                        else ""
                    ),
                },
                "semantic_rows": [unique_rows[key] for key in sorted(unique_rows)],
            }
        )
        clusters.append(
            PropositionCluster(
                proposition_code=f"PROP-{semantic_hash[:20].upper()}",
                semantic_hash=semantic_hash,
                assertion_refs=tuple(item.assertion_code for item in group_items),
                evidence_refs=tuple(item.source_passage_ref for item in group_items),
                evaluation_context=context,
                focal_person_ref=focal_person,
                focal_role=focal_role,
                secondary_participant_refs=secondary,
                episode_type=next(iter(episode_types)),
                action=" | ".join(
                    sorted({item.predicate for item in group_items})
                ),
                responsibility_family=next(iter(responsibility_families)),
                responsibility_domain=" | ".join(
                    sorted(
                        {
                            str(item.qualifiers.get("office_or_domain"))
                            for item in group_items
                            if item.qualifiers.get("office_or_domain")
                        }
                    )
                )
                or None,
                normalized_time=normalized_time,
                location_expression=" | ".join(
                    sorted(
                        {
                            str(item.location_expression)
                            for item in group_items
                            if item.location_expression
                        }
                    )
                )
                or None,
                outcomes=tuple(
                    sorted(
                        {
                            str(item.qualifiers.get("outcome"))
                            for item in group_items
                            if item.qualifiers.get("outcome")
                        }
                    )
                ),
            )
        )
    return tuple(sorted(clusters, key=lambda item: item.proposition_code))


def _review_unit_cache_key(
    clusters: Iterable[PropositionCluster],
    *,
    evaluation_context: str,
    focal_person_ref: str,
    focal_roles: tuple[str, ...],
    responsibility_family: str,
    boundary_policy_version: str,
    output_schema_version: str,
    model_family: str,
) -> str:
    return _hash(
        {
            "evaluation_context": evaluation_context,
            "focal_person_ref": focal_person_ref,
            "focal_roles": focal_roles,
            "responsibility_family": responsibility_family,
            "proposition_semantic_hashes": sorted(item.semantic_hash for item in clusters),
            "boundary_policy_version": boundary_policy_version,
            "output_schema_version": output_schema_version,
            "model_family": model_family,
        }
    )


def build_review_units(
    clusters: Iterable[PropositionCluster],
    *,
    max_adjacent_sort_gap: int = 25,
    boundary_policy_version: str = BOUNDARY_POLICY_VERSION,
    output_schema_version: str = BOUNDARY_OUTPUT_SCHEMA_VERSION,
    model_family: str = DEFAULT_MODEL_FAMILY,
) -> tuple[EpisodeReviewUnit, ...]:
    coarse: dict[tuple[str, str, str], list[PropositionCluster]] = defaultdict(list)
    for cluster in clusters:
        coarse[
            (
                cluster.evaluation_context,
                cluster.focal_person_ref,
                cluster.responsibility_family,
            )
        ].append(cluster)

    partitions: list[list[PropositionCluster]] = []
    for items in coarse.values():
        known = sorted(
            [item for item in items if item.normalized_time.start_sort_key is not None],
            key=lambda item: (
                item.normalized_time.start_sort_key,
                item.proposition_code,
            ),
        )
        unknown = sorted(
            [item for item in items if item.normalized_time.start_sort_key is None],
            key=lambda item: item.proposition_code,
        )
        current: list[PropositionCluster] = []
        previous_end: int | None = None
        for item in known:
            start = item.normalized_time.start_sort_key
            if current and previous_end is not None and start is not None and start - previous_end > max_adjacent_sort_gap:
                partitions.append(current)
                current = []
            current.append(item)
            previous_end = item.normalized_time.end_sort_key or start
        if current:
            partitions.append(current)
        if unknown:
            partitions.append(unknown)

    units = []
    for items in partitions:
        context = items[0].evaluation_context
        focal_person = items[0].focal_person_ref
        focal_roles = tuple(sorted({item.focal_role for item in items}))
        family = items[0].responsibility_family
        starts = [
            item.normalized_time.start_sort_key
            for item in items
            if item.normalized_time.start_sort_key is not None
        ]
        ends = [
            item.normalized_time.end_sort_key
            for item in items
            if item.normalized_time.end_sort_key is not None
        ]
        cache_key = _review_unit_cache_key(
            items,
            evaluation_context=context,
            focal_person_ref=focal_person,
            focal_roles=focal_roles,
            responsibility_family=family,
            boundary_policy_version=boundary_policy_version,
            output_schema_version=output_schema_version,
            model_family=model_family,
        )
        units.append(
            EpisodeReviewUnit(
                review_unit_code=f"RU-{cache_key[:20].upper()}",
                cache_key=cache_key,
                evaluation_context=context,
                focal_person_ref=focal_person,
                focal_roles=focal_roles,
                time_start_sort_key=min(starts) if starts else None,
                time_end_sort_key=max(ends) if ends else None,
                responsibility_family=family,
                proposition_cluster_refs=tuple(item.proposition_code for item in items),
                proposition_semantic_hashes=tuple(item.semantic_hash for item in items),
                boundary_policy_version=boundary_policy_version,
                output_schema_version=output_schema_version,
                model_family=model_family,
            )
        )
    return tuple(sorted(units, key=lambda item: item.review_unit_code))


@dataclass(frozen=True, slots=True)
class ReviewUnitPlan:
    proposition_clusters: tuple[PropositionCluster, ...]
    review_units: tuple[EpisodeReviewUnit, ...]
    cache_hit_unit_codes: tuple[str, ...]
    cache_miss_unit_codes: tuple[str, ...]

    @property
    def model_call_count(self) -> int:
        return len(self.cache_miss_unit_codes)


def plan_boundary_reviews(
    assertions: Iterable[AssertionDraft],
    *,
    cached_review_keys: Iterable[str] = (),
) -> ReviewUnitPlan:
    clusters = cluster_propositions(assertions)
    units = build_review_units(clusters)
    cached = set(cached_review_keys)
    return ReviewUnitPlan(
        proposition_clusters=clusters,
        review_units=units,
        cache_hit_unit_codes=tuple(
            item.review_unit_code for item in units if item.cache_key in cached
        ),
        cache_miss_unit_codes=tuple(
            item.review_unit_code for item in units if item.cache_key not in cached
        ),
    )


class BoundaryReviewCacheRepository(Protocol):
    def get(self, cache_key: str) -> EpisodeBoundaryReviewResult | None: ...
    def put(self, cache_key: str, result: EpisodeBoundaryReviewResult) -> None: ...


class InMemoryBoundaryReviewCache:
    def __init__(self, entries: Iterable[EpisodeBoundaryReviewResult] = ()) -> None:
        self._entries = {item.review_unit_cache_key: item for item in entries}

    def get(self, cache_key: str) -> EpisodeBoundaryReviewResult | None:
        return self._entries.get(cache_key)

    def put(self, cache_key: str, result: EpisodeBoundaryReviewResult) -> None:
        if cache_key != result.review_unit_cache_key:
            raise ValueError("cache repository key 与 review result 不一致")
        self._entries[cache_key] = result


def _unit_clusters(
    unit: EpisodeReviewUnit, clusters_by_ref: Mapping[str, PropositionCluster]
) -> tuple[PropositionCluster, ...]:
    return tuple(clusters_by_ref[ref] for ref in unit.proposition_cluster_refs)


def _assertions_by_cluster(
    clusters: Iterable[PropositionCluster],
) -> dict[str, tuple[str, ...]]:
    return {item.proposition_code: item.assertion_refs for item in clusters}


def _is_clear_fast_path(
    unit: EpisodeReviewUnit,
    clusters: tuple[PropositionCluster, ...],
    assertions_by_ref: Mapping[str, AssertionDraft],
) -> bool:
    if len(clusters) != 1:
        return False
    cluster = clusters[0]
    if not (
        cluster.focal_person_ref.startswith("per-")
        or cluster.focal_person_ref.startswith("obj-")
    ):
        return False
    for ref in cluster.assertion_refs:
        assertion = assertions_by_ref[ref]
        if assertion.polarity == "disputed":
            return False
        if any(
            classify_ambiguity(flag, cluster.episode_type).is_blocking_for(
                cluster.episode_type
            )
            for flag in assertion.ambiguity_flags
        ):
            return False
    return True


def _fast_path_result(
    unit: EpisodeReviewUnit, cluster: PropositionCluster
) -> EpisodeBoundaryReviewResult:
    local_code = "AUTO-E1"
    return EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup(
                local_episode_code=local_code,
                core_assertion_refs=cluster.assertion_refs,
                boundary_reason="single clear proposition cluster deterministic fast path",
                confidence=1.0,
                atomic_event_key=f"prop:{cluster.semantic_hash}",
            ),
        ),
        relations=(),
        assertion_dispositions=tuple(
            AssertionDisposition(
                assertion_ref=ref,
                disposition="core_of_episode",
                episode_refs=(local_code,),
                reason="single clear proposition cluster",
            )
            for ref in cluster.assertion_refs
        ),
        review_provenance={"route": "deterministic_fast_path_v1"},
        pair_dispositions=(),
    )


@dataclass(frozen=True, slots=True)
class BoundaryReviewExecutionResult:
    review_results: tuple[EpisodeBoundaryReviewResult, ...]
    deterministic_unit_codes: tuple[str, ...]
    cache_hit_unit_codes: tuple[str, ...]
    model_called_unit_codes: tuple[str, ...]
    pending_unit_codes: tuple[str, ...]

    @property
    def model_call_count(self) -> int:
        return len(self.model_called_unit_codes)


def execute_boundary_reviews(
    assertions: Iterable[AssertionDraft],
    *,
    cache: BoundaryReviewCacheRepository,
    reviewer: Callable[[BoundaryReviewRequest], EpisodeBoundaryReviewResult] | None,
) -> BoundaryReviewExecutionResult:
    assertion_items = tuple(assertions)
    assertions_by_ref = {item.assertion_code: item for item in assertion_items}
    clusters = cluster_propositions(assertion_items)
    clusters_by_ref = {item.proposition_code: item for item in clusters}
    cluster_assertions = _assertions_by_cluster(clusters)
    units = build_review_units(clusters)
    results = []
    deterministic = []
    cache_hits = []
    model_called = []
    pending = []
    for unit in units:
        unit_clusters = _unit_clusters(unit, clusters_by_ref)
        if _is_clear_fast_path(unit, unit_clusters, assertions_by_ref):
            result = _fast_path_result(unit, unit_clusters[0])
            deterministic.append(unit.review_unit_code)
        else:
            result = cache.get(unit.cache_key)
            if result is not None:
                cache_hits.append(unit.review_unit_code)
            elif reviewer is not None:
                refs = tuple(
                    ref for cluster in unit_clusters for ref in cluster.assertion_refs
                )
                result = reviewer(
                    BoundaryReviewRequest(
                        review_unit=unit,
                        proposition_clusters=unit_clusters,
                        assertion_refs=refs,
                    )
                )
                model_called.append(unit.review_unit_code)
                cache.put(unit.cache_key, result)
            else:
                pending.append(unit.review_unit_code)
                continue
        result.validate_for_unit(unit, cluster_assertions)
        results.append(result)
    return BoundaryReviewExecutionResult(
        review_results=tuple(results),
        deterministic_unit_codes=tuple(deterministic),
        cache_hit_unit_codes=tuple(cache_hits),
        model_called_unit_codes=tuple(model_called),
        pending_unit_codes=tuple(pending),
    )


def _relation_fingerprint(
    from_ref: str, to_ref: str, relation_type: str
) -> str:
    return _hash(
        {
            "from_episode_version_ref": from_ref,
            "to_episode_version_ref": to_ref,
            "relation_type": relation_type,
        }
    )


def validate_episode_relation_graph(
    relations: Iterable[EpisodeRelation],
    episode_context_by_version_ref: Mapping[str, str],
) -> None:
    items = tuple(relations)
    for relation in items:
        if (
            relation.from_episode_version_ref not in episode_context_by_version_ref
            or relation.to_episode_version_ref not in episode_context_by_version_ref
        ):
            raise ValueError("EpisodeRelation endpoint 不存在")
        if relation.relation_type != "context_for" and (
            episode_context_by_version_ref[relation.from_episode_version_ref]
            != episode_context_by_version_ref[relation.to_episode_version_ref]
        ):
            raise ValueError("非 context_for Relation 不得跨 evaluation context")
    adjacency: dict[str, set[str]] = defaultdict(set)
    for relation in items:
        if relation.relation_type in _ACYCLIC_RELATION_TYPES:
            adjacency[relation.from_episode_version_ref].add(
                relation.to_episode_version_ref
            )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("temporal/causal EpisodeRelation 不得形成环")
        if node in visited:
            return
        visiting.add(node)
        for target in adjacency.get(node, ()):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in tuple(adjacency):
        visit(node)


def _atomic_structure_signature(assertion: AssertionDraft) -> tuple[object, ...]:
    time = _normalized_time(assertion)
    _, focal_role, _ = _focal_identity(assertion)
    return (
        _normalized(assertion.predicate),
        _responsibility_family(assertion),
        focal_role,
        time.start_sort_key,
        time.end_sort_key,
        _normalized(time.dynasty_or_era),
        _normalized(time.source_expression) if time.start_sort_key is None else "",
    )


def validate_atomic_episode_groups(
    review: EpisodeBoundaryReviewResult,
    assertions_by_ref: Mapping[str, AssertionDraft],
) -> None:
    """Reject merges that need assertion atomization or an EpisodeRelation."""

    if review.output_schema_version not in {
        "episode-boundary-review-v2.2",
        "episode-boundary-review-v2.3",
        "episode-boundary-review-v2.4",
        "episode-boundary-review-v2.5",
        "episode-boundary-review-v2.6",
        "episode-boundary-review-v2.7",
    }:
        return
    for group in review.episode_groups:
        assertions = tuple(assertions_by_ref[ref] for ref in group.core_assertion_refs)
        if len(assertions) < 2:
            continue
        signatures = {_atomic_structure_signature(item) for item in assertions}
        if len(signatures) != 1:
            raise ValueError(
                "v2.7 Episode core 跨 action/time/responsibility-family/focal-role；"
                "必须拆成原子 Episode 并用 Relation 连接"
            )
        by_claim: dict[str, list[AssertionDraft]] = defaultdict(list)
        for assertion in assertions:
            claim_key = _normalized(
                assertion.extraction_provenance.get("claim_key")
            )
            if claim_key:
                by_claim[claim_key].append(assertion)
        for claim_items in by_claim.values():
            passages = {item.source_passage_ref for item in claim_items}
            if len(passages) < 2:
                continue
            if review.output_schema_version == "episode-boundary-review-v2.7":
                supports = tuple(item.passage_support for item in claim_items)
                if any(item is None for item in supports):
                    raise ValueError(
                        "v2.7 同一 claim 的多 passage core 缺少 PassageSupport；"
                        "Reviewer atomic_event_key 不得覆盖 assertion atomization"
                    )
                semantic_keys = {
                    item.assertion_semantic_key for item in supports if item is not None
                }
                support_modes = {
                    item.support_mode for item in supports if item is not None
                }
                semantic_payloads = {
                    _hash(
                        {
                            "subject": _normalized(item.subject),
                            "predicate": _normalized(item.predicate),
                            "object": _normalized(item.object),
                            "time": _normalized(item.time_expression),
                            "location": _normalized(item.location_expression),
                            "responsibility_family": _responsibility_family(item),
                            "responsibility_domain": _normalized(
                                item.qualifiers.get("office_or_domain")
                            ),
                            "outcome": _normalized(item.qualifiers.get("outcome")),
                            "polarity": _normalized(item.polarity),
                        }
                    )
                    for item in claim_items
                }
                if (
                    len(semantic_keys) != 1
                    or support_modes != {"equivalent_evidence"}
                    or len(semantic_payloads) != 1
                ):
                    raise ValueError(
                        "v2.7 同一 claim 的多 passage 只有显式 equivalent_evidence "
                        "且语义一致时才能合并；atomic components 必须拆分"
                    )
                continue
            atomic_keys = {
                _normalized(item.qualifiers.get("atomic_event_key"))
                for item in claim_items
            }
            reviewer_key = _normalized(group.atomic_event_key)
            assertions_share_key = "" not in atomic_keys and len(atomic_keys) == 1
            if not reviewer_key and not assertions_share_key:
                raise ValueError(
                    "同一旧 claim 的多 passage 扇出缺少共同或审查冻结的 atomic_event_key；"
                    "不得合并为正式 Episode，应拆分或进入 assertion atomization worklist"
                )


def materialize_boundary_review(
    assertions: Iterable[AssertionDraft],
    review: EpisodeBoundaryReviewResult,
    *,
    review_unit: EpisodeReviewUnit,
    proposition_clusters: Iterable[PropositionCluster],
) -> BoundaryMaterializationResult:
    assertion_items = tuple(assertions)
    by_ref = {item.assertion_code: item for item in assertion_items}
    clusters = tuple(proposition_clusters)
    review.validate_for_unit(review_unit, _assertions_by_cluster(clusters))
    available = {
        ref
        for cluster in clusters
        if cluster.proposition_code in set(review_unit.proposition_cluster_refs)
        for ref in cluster.assertion_refs
    }
    if not available <= set(by_ref):
        raise ValueError("Materialization 缺少 ReviewUnit assertion 输入")
    validate_atomic_episode_groups(review, by_ref)
    if review.output_schema_version in {
        "episode-boundary-review-v2.2",
        "episode-boundary-review-v2.3",
        "episode-boundary-review-v2.4",
        "episode-boundary-review-v2.5",
        "episode-boundary-review-v2.6",
        "episode-boundary-review-v2.7",
    } and any(
        item.decision == "unresolved" for item in review.pair_dispositions
    ):
        raise ValueError("存在 unresolved Episode pair，禁止物化正式候选图")
    core_refs = {
        item.assertion_ref
        for item in review.assertion_dispositions
        if item.disposition == "core_of_episode"
    }
    core_assertions = tuple(by_ref[ref] for ref in sorted(core_refs))
    hints = {
        ref: group.local_episode_code
        for group in review.episode_groups
        for ref in group.core_assertion_refs
    }
    atomic_event_keys = {
        group.local_episode_code: group.atomic_event_key or ""
        for group in review.episode_groups
    }
    groups = group_episode_candidates_with_hints(
        core_assertions, hints, atomic_event_keys
    )
    packets = tuple(build_episode_packet(group) for group in groups)
    packet_ids = [packet.episode_id for packet in packets]
    if len(packet_ids) != len(set(packet_ids)):
        raise ValueError(
            "不同 EpisodeBoundaryGroup 生成重复 Episode ID；"
            "必须为每个原子事件冻结不同 atomic_event_key"
        )
    local_to_packet = {
        group.boundary_hint: packet
        for group, packet in zip(groups, packets, strict=True)
    }
    relations = []
    for draft in review.relations:
        from_packet = local_to_packet[draft.from_episode_ref]
        to_packet = local_to_packet[draft.to_episode_ref]
        from_version_ref = f"{from_packet.episode_id}@v{from_packet.semantic_version}"
        to_version_ref = f"{to_packet.episode_id}@v{to_packet.semantic_version}"
        fingerprint = _relation_fingerprint(
            from_version_ref, to_version_ref, draft.relation_type
        )
        relations.append(
            EpisodeRelation(
                relation_id=f"ER-{fingerprint[:20].upper()}",
                from_episode_version_ref=from_version_ref,
                to_episode_version_ref=to_version_ref,
                relation_type=draft.relation_type,
                semantic_fingerprint=fingerprint,
                semantic_version=1,
                evidence_version=1,
                relation_status="proposed",
                evidence_links=tuple(
                    RelationEvidenceLink(
                        assertion_ref=ref,
                        source_passage_ref=by_ref[ref].source_passage_ref,
                    )
                    for ref in draft.evidence_assertion_refs
                ),
                confidence=draft.confidence,
                lineage={"origin": "created"},
                provenance={
                    "review_unit_ref": review.review_unit_ref,
                    "review_unit_cache_key": review.review_unit_cache_key,
                    "boundary_policy_version": review.boundary_policy_version,
                },
            )
        )
    contexts = {
        f"{packet.episode_id}@v{packet.semantic_version}": packet.evaluation_context
        for packet in packets
    }
    validate_episode_relation_graph(relations, contexts)
    context_links = tuple(
        ContextAssertionLink(
            assertion_ref=item.assertion_ref,
            applies_to_episode_refs=tuple(
                local_to_packet[ref].episode_id for ref in item.episode_refs
            ),
            reason=item.reason,
        )
        for item in review.assertion_dispositions
        if item.disposition == "context_for_episode"
    )
    return BoundaryMaterializationResult(
        episode_packets=packets,
        episode_relations=tuple(relations),
        context_assertion_links=context_links,
        unresolved_assertions=tuple(
            item
            for item in review.assertion_dispositions
            if item.disposition == "unresolved"
        ),
        excluded_assertions=tuple(
            item
            for item in review.assertion_dispositions
            if item.disposition == "excluded"
        ),
        assertion_dispositions=review.assertion_dispositions,
        review_provenance={
            **review.review_provenance,
            "review_unit_ref": review.review_unit_ref,
            "review_unit_cache_key": review.review_unit_cache_key,
            "boundary_policy_version": review.boundary_policy_version,
            "output_schema_version": review.output_schema_version,
            "model_family": review.model_family,
        },
    )


def draft_rule_evidence_unit(
    *,
    rule_code: str,
    rule_version: str,
    aggregation_policy_version: str,
    evaluation_context: str,
    episode_members: Mapping[str, str],
    relation_members: Mapping[str, str],
    aggregation_reason: str,
) -> RuleEvidenceUnitDraft:
    members = tuple(
        sorted(
            (
                *(
                    RuleEvidenceMember(ref, "episode", role)
                    for ref, role in episode_members.items()
                ),
                *(
                    RuleEvidenceMember(ref, "relation", role)
                    for ref, role in relation_members.items()
                ),
            ),
            key=lambda item: (item.member_type, item.member_ref, item.member_role),
        )
    )
    semantic_fingerprint = _hash(
        {
            "rule_code": rule_code,
            "rule_version": rule_version,
            "aggregation_policy_version": aggregation_policy_version,
            "evaluation_context": evaluation_context,
            "members": [
                {
                    "ref": item.member_ref,
                    "type": item.member_type,
                    "role": item.member_role,
                }
                for item in members
            ],
        }
    )
    return RuleEvidenceUnitDraft(
        unit_code=f"REU-{semantic_fingerprint[:20].upper()}",
        rule_code=rule_code,
        rule_version=rule_version,
        aggregation_policy_version=aggregation_policy_version,
        evaluation_context=evaluation_context,
        semantic_fingerprint=semantic_fingerprint,
        semantic_version=1,
        evidence_version=1,
        members=members,
        aggregation_reason=aggregation_reason,
        status="draft",
        lineage={"origin": "created"},
        provenance={"builder": "rule_evidence_unit_draft_v2"},
    )
