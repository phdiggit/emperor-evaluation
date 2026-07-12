from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.boundary import (
    AmbiguityIssue,
    EpisodeBoundaryReviewResult,
    EpisodeRelation,
    EpisodeReviewUnit,
    PropositionCluster,
    RuleEvidenceUnitDraft,
)
from emperor_v4.contracts.episode import HistoricalEpisodePacket
from emperor_v4.domain.episode import (
    build_episode_packet,
    group_episode_candidates_with_hints,
)


BOUNDARY_POLICY_VERSION = "episode-boundary-policy-v2"
BOUNDARY_OUTPUT_SCHEMA_VERSION = "episode-boundary-review-v2"
DEFAULT_MODEL_FAMILY = "semantic-boundary-reviewer"


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
            code=flag,
            slot="identity",
            severity="blocking",
            source_flag=flag,
        )
    return AmbiguityIssue(
        code=flag,
        slot="unspecified",
        severity="blocking",
        source_flag=flag,
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


def _focal_person(assertion: AssertionDraft) -> str:
    context = _normalized(assertion.qualifiers.get("evaluation_context"))
    roles = assertion.qualifiers.get("candidate_participant_roles") or ()
    candidates = [
        _normalized(person)
        for person, role in roles
        if _normalized(person) != context and _normalized(role) != "ruler"
    ]
    return candidates[0] if candidates else _normalized(assertion.subject)


def _proposition_group_key(assertion: AssertionDraft) -> tuple[str, str]:
    context = _normalized(assertion.qualifiers.get("evaluation_context"))
    claim_key = _normalized(assertion.extraction_provenance.get("claim_key"))
    if claim_key:
        return context, f"claim:{claim_key}"
    semantic = {
        "subject": _normalized(assertion.subject),
        "predicate": _normalized(assertion.predicate),
        "object": _normalized(assertion.object),
        "time": _normalized(assertion.time_expression),
        "location": _normalized(assertion.location_expression),
        "episode_type": _normalized(assertion.qualifiers.get("episode_type")),
        "responsibility": _normalized(assertion.qualifiers.get("office_or_domain")),
        "polarity": _normalized(assertion.polarity),
    }
    return context, f"semantic:{_hash(semantic)}"


def cluster_propositions(
    assertions: Iterable[AssertionDraft],
) -> tuple[PropositionCluster, ...]:
    grouped: dict[tuple[str, str], list[AssertionDraft]] = defaultdict(list)
    seen: set[str] = set()
    for assertion in assertions:
        if assertion.assertion_code in seen:
            raise ValueError(f"重复 assertion 输入: {assertion.assertion_code}")
        seen.add(assertion.assertion_code)
        grouped[_proposition_group_key(assertion)].append(assertion)

    clusters = []
    for (context, group_key), items in grouped.items():
        items.sort(key=lambda item: item.assertion_code)
        episode_types = {
            _normalized(item.qualifiers.get("episode_type") or item.predicate)
            for item in items
        }
        focal_people = {_focal_person(item) for item in items}
        if len(episode_types) != 1 or len(focal_people) != 1:
            raise ValueError(f"Proposition cluster 语义污染: {group_key}")
        semantic_rows = [
            {
                "subject": _normalized(item.subject),
                "predicate": _normalized(item.predicate),
                "object": _normalized(item.object),
                "time": _normalized(item.time_expression),
                "location": _normalized(item.location_expression),
                "responsibility": _normalized(
                    item.qualifiers.get("office_or_domain")
                ),
                "outcome": _normalized(item.qualifiers.get("outcome")),
                "polarity": _normalized(item.polarity),
            }
            for item in items
        ]
        unique_semantic_rows = {
            _hash(row): row for row in semantic_rows
        }
        semantic_hash = _hash(
            {
                "evaluation_context": context,
                "focal_person": next(iter(focal_people)),
                "episode_type": next(iter(episode_types)),
                "semantic_rows": [
                    unique_semantic_rows[key]
                    for key in sorted(unique_semantic_rows)
                ],
            }
        )
        proposition_code = f"PROP-{semantic_hash[:20].upper()}"
        clusters.append(
            PropositionCluster(
                proposition_code=proposition_code,
                semantic_hash=semantic_hash,
                assertion_refs=tuple(item.assertion_code for item in items),
                evidence_refs=tuple(item.source_passage_ref for item in items),
                evaluation_context=context,
                focal_person=next(iter(focal_people)),
                episode_type=next(iter(episode_types)),
                action=" | ".join(sorted({item.predicate for item in items})),
                responsibility_domain=" | ".join(
                    sorted(
                        {
                            str(item.qualifiers.get("office_or_domain"))
                            for item in items
                            if item.qualifiers.get("office_or_domain")
                        }
                    )
                )
                or None,
                time_expression=" | ".join(
                    sorted(
                        {
                            str(item.time_expression)
                            for item in items
                            if item.time_expression
                        }
                    )
                )
                or None,
                location_expression=" | ".join(
                    sorted(
                        {
                            str(item.location_expression)
                            for item in items
                            if item.location_expression
                        }
                    )
                )
                or None,
                outcomes=tuple(
                    sorted(
                        {
                            str(item.qualifiers.get("outcome"))
                            for item in items
                            if item.qualifiers.get("outcome")
                        }
                    )
                ),
            )
        )
    return tuple(sorted(clusters, key=lambda item: item.proposition_code))


def _year(cluster: PropositionCluster) -> int | None:
    years = [int(value) for value in re.findall(r"(?<!\d)(1[0-9]{3})(?!\d)", cluster.time_expression or "")]
    return min(years) if years else None


def _review_unit_cache_key(
    clusters: Iterable[PropositionCluster],
    *,
    boundary_policy_version: str,
    output_schema_version: str,
    model_family: str,
) -> str:
    return _hash(
        {
            "proposition_semantic_hashes": sorted(
                item.semantic_hash for item in clusters
            ),
            "boundary_policy_version": boundary_policy_version,
            "output_schema_version": output_schema_version,
            "model_family": model_family,
        }
    )


def build_review_units(
    clusters: Iterable[PropositionCluster],
    *,
    max_adjacent_year_gap: int = 25,
    boundary_policy_version: str = BOUNDARY_POLICY_VERSION,
    output_schema_version: str = BOUNDARY_OUTPUT_SCHEMA_VERSION,
    model_family: str = DEFAULT_MODEL_FAMILY,
) -> tuple[EpisodeReviewUnit, ...]:
    coarse: dict[tuple[str, str, str], list[PropositionCluster]] = defaultdict(list)
    for cluster in clusters:
        coarse[
            (
                cluster.evaluation_context,
                cluster.focal_person,
                cluster.episode_type,
            )
        ].append(cluster)

    partitions: list[list[PropositionCluster]] = []
    for items in coarse.values():
        ordered = sorted(
            items,
            key=lambda item: (
                _year(item) is None,
                _year(item) or 0,
                item.proposition_code,
            ),
        )
        current: list[PropositionCluster] = []
        previous_year: int | None = None
        for item in ordered:
            item_year = _year(item)
            if (
                current
                and previous_year is not None
                and item_year is not None
                and item_year - previous_year > max_adjacent_year_gap
            ):
                partitions.append(current)
                current = []
            current.append(item)
            if item_year is not None:
                previous_year = item_year
        if current:
            partitions.append(current)

    units = []
    for items in partitions:
        years = sorted(year for item in items for year in [_year(item)] if year)
        time_window = (
            f"{years[0]}-{years[-1]}" if years else "undated-source-expression"
        )
        domains = sorted(
            {item.responsibility_domain for item in items if item.responsibility_domain}
        )
        cache_key = _review_unit_cache_key(
            items,
            boundary_policy_version=boundary_policy_version,
            output_schema_version=output_schema_version,
            model_family=model_family,
        )
        units.append(
            EpisodeReviewUnit(
                review_unit_code=f"RU-{cache_key[:20].upper()}",
                cache_key=cache_key,
                evaluation_context=items[0].evaluation_context,
                focal_person=items[0].focal_person,
                time_window=time_window,
                responsibility_domain=" | ".join(domains) or "unspecified",
                proposition_cluster_refs=tuple(
                    item.proposition_code for item in items
                ),
                proposition_semantic_hashes=tuple(
                    item.semantic_hash for item in items
                ),
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


def materialize_boundary_review(
    assertions: Iterable[AssertionDraft],
    review: EpisodeBoundaryReviewResult,
) -> tuple[tuple[HistoricalEpisodePacket, ...], tuple[EpisodeRelation, ...]]:
    assertion_items = tuple(assertions)
    by_ref = {item.assertion_code: item for item in assertion_items}
    review.validate_assertion_coverage(set(by_ref))
    core_refs = {
        ref for group in review.episode_groups for ref in group.core_assertion_refs
    }
    core_assertions = tuple(by_ref[ref] for ref in sorted(core_refs))
    hints = {
        ref: group.local_episode_code
        for group in review.episode_groups
        for ref in group.core_assertion_refs
    }
    groups = group_episode_candidates_with_hints(core_assertions, hints)
    packets = tuple(build_episode_packet(group) for group in groups)
    local_to_packet = {
        group.boundary_hint: packet
        for group, packet in zip(groups, packets, strict=True)
    }
    resolved_relations = tuple(
        EpisodeRelation(
            from_episode_ref=local_to_packet[item.from_episode_ref].episode_id,
            to_episode_ref=local_to_packet[item.to_episode_ref].episode_id,
            relation_type=item.relation_type,
            evidence_assertion_refs=item.evidence_assertion_refs,
            confidence=item.confidence,
        )
        for item in review.relations
    )
    return packets, resolved_relations


def draft_rule_evidence_unit(
    *,
    rule_code: str,
    evaluation_context: str,
    episode_refs: Iterable[str],
    relation_refs: Iterable[str],
    aggregation_reason: str,
) -> RuleEvidenceUnitDraft:
    episode_items = tuple(sorted(set(episode_refs)))
    relation_items = tuple(sorted(set(relation_refs)))
    identity = _hash(
        {
            "rule_code": rule_code,
            "evaluation_context": evaluation_context,
            "episode_refs": episode_items,
            "relation_refs": relation_items,
        }
    )
    return RuleEvidenceUnitDraft(
        unit_code=f"REU-{identity[:20].upper()}",
        rule_code=rule_code,
        evaluation_context=evaluation_context,
        episode_refs=episode_items,
        relation_refs=relation_items,
        aggregation_reason=aggregation_reason,
    )
