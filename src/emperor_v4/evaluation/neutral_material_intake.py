from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from typing import Mapping, Sequence

from emperor_v4.persistence.core_registry import (
    GovernanceAchievementMember,
    GovernanceAchievementRecord,
)


def _hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _unique(values: Sequence[str]) -> list[str]:
    return sorted({value for value in values if value})


def _is_exact_source_ref(value: str) -> bool:
    try:
        page_revision, quote = value.rsplit("#", 1)
        page, revision = page_revision.rsplit("@", 1)
    except ValueError:
        return False
    return bool(page and revision and quote)


def build_neutral_material_intake(
    *,
    ruler_fanouts: Sequence[Mapping[str, object]] = (),
    person_lifecycle_fanouts: Sequence[Mapping[str, object]] = (),
    governance_fact_sets: Sequence[Mapping[str, object]] = (),
    governance_registries: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Merge the three neutral-material channels without making rule judgments.

    Native fact identifiers are the only automatic deduplication key.  Similar
    prose from different sources remains separate until a semantic settlement
    explicitly links it.  Governance achievements retain links to their
    underlying neutral facts and only advertise projection targets; they do not
    become HistoricalEpisodes or scores here.
    """

    facts: dict[str, dict[str, object]] = {}
    person_materials: dict[str, set[str]] = defaultdict(set)
    ruler_materials: dict[str, set[str]] = defaultdict(set)

    def merge_fact(
        fact_ref: str,
        *,
        channel: str,
        summary: str,
        source_page: str,
        revision_ref: str,
        date: str,
        person_ref: str | None = None,
        ruler_contexts: Sequence[str] = (),
        assertion_anchors: Sequence[str] = (),
        exact_source_refs: Sequence[str] = (),
        profile_eligible: bool = False,
    ) -> None:
        material_ref = f"NMAT-{_hash(fact_ref)[:20].upper()}"
        row = facts.setdefault(
            fact_ref,
            {
                "material_ref": material_ref,
                "neutral_fact_ref": fact_ref,
                "source_channels": [],
                "neutral_summaries": [],
                "source_refs": [],
                "dates": [],
                "person_refs": [],
                "ruler_contexts": [],
                "assertion_anchors": [],
                "profile_eligible": False,
                "episode_intake_status": "needs_assertion_lineage",
            },
        )
        row["source_channels"] = _unique([*row["source_channels"], channel])
        row["neutral_summaries"] = _unique([*row["neutral_summaries"], summary])
        fallback_source_ref = (
            f"{source_page}@{revision_ref}" if revision_ref else source_page
        )
        row["source_refs"] = _unique(
            [*row["source_refs"], *exact_source_refs, fallback_source_ref]
        )
        row["dates"] = _unique([*row["dates"], date])
        row["ruler_contexts"] = _unique([*row["ruler_contexts"], *ruler_contexts])
        row["assertion_anchors"] = _unique(
            [*row["assertion_anchors"], *assertion_anchors]
        )
        row["profile_eligible"] = bool(row["profile_eligible"] or profile_eligible)
        if person_ref:
            row["person_refs"] = _unique([*row["person_refs"], person_ref])
            person_materials[person_ref].add(material_ref)
        for ruler in ruler_contexts:
            ruler_materials[ruler].add(material_ref)

    for fanout in ruler_fanouts:
        ruler = fanout.get("ruler") or {}
        ruler_ref = (
            str(ruler.get("ruler_ref") or ruler.get("name") or "")
            if isinstance(ruler, Mapping)
            else str(ruler)
        )
        for person in fanout.get("person_fanout") or ():
            person_ref = str(person["person_ref"])
            for record in person.get("records") or ():
                review = record.get("review") or {}
                merge_fact(
                    str(record["neutral_record_id"]),
                    channel="ruler_chronicle",
                    summary=str(record["neutral_summary"]),
                    source_page=str(record["source_page"]),
                    revision_ref=str(record.get("revision_ref") or ""),
                    date=str(record.get("date") or ""),
                    person_ref=person_ref,
                    ruler_contexts=(ruler_ref,) if ruler_ref else (),
                    assertion_anchors=tuple(review.get("supporting_assertion_anchors") or ()),
                    profile_eligible=bool(review.get("profile_eligibility")),
                )

    for fanout in person_lifecycle_fanouts:
        for person in fanout.get("people") or ():
            person_ref = str(person["person_ref"])
            for record in person.get("records") or ():
                merge_fact(
                    str(record["record_ref"]),
                    channel="person_biography",
                    summary=str(record["neutral_summary"]),
                    source_page=str(record["source_page"]),
                    revision_ref=str(record.get("revision_ref") or ""),
                    date=str(record.get("date") or ""),
                    person_ref=person_ref,
                    ruler_contexts=tuple(record.get("ruler_contexts") or ()),
                    assertion_anchors=tuple(
                        str(item.get("locator_anchor") or "")
                        for item in record.get("assertions") or ()
                    ),
                    profile_eligible=True,
                )

    for fact_set in governance_fact_sets:
        for fact in fact_set.get("facts") or ():
            fact_ref = str(fact.get("fact_ref") or "")
            source_refs = tuple(str(value) for value in fact.get("source_refs") or ())
            if not fact_ref or not source_refs:
                raise ValueError(
                    "dynasty_governance fact 必须同时提供 fact_ref 和 source_refs"
                )
            if any(not _is_exact_source_ref(source_ref) for source_ref in source_refs):
                raise ValueError(
                    "dynasty_governance source_refs 必须使用 page@revision#quote"
                )
            summary_parts = _unique(
                [
                    str(fact.get("title") or ""),
                    str(fact.get("action") or ""),
                    str(fact.get("implementation") or ""),
                    str(fact.get("observable_result") or ""),
                ]
            )
            anchors = tuple(
                source_ref.rsplit("#", 1)[1]
                for source_ref in source_refs
                if "#" in source_ref and source_ref.rsplit("#", 1)[1]
            )
            merge_fact(
                fact_ref,
                channel="dynasty_governance",
                summary="；".join(summary_parts),
                source_page="",
                revision_ref="",
                date=str(fact.get("period") or ""),
                ruler_contexts=tuple(fact.get("ruler_contexts") or ()),
                assertion_anchors=anchors,
                exact_source_refs=source_refs,
            )

    achievements = []
    projection_queue = []
    for registry in governance_registries:
        for achievement in registry.get("achievements") or ():
            achievement_ref = str(achievement["achievement_ref"])
            linked = [
                facts[ref]["material_ref"]
                for ref in achievement.get("neutral_fact_refs") or ()
                if ref in facts
            ]
            unresolved = [
                ref
                for ref in achievement.get("neutral_fact_refs") or ()
                if ref not in facts
            ]
            people = [str(item["person_ref"]) for item in achievement.get("participants") or ()]
            rulers = [str(item["ruler_ref"]) for item in achievement.get("ruler_links") or ()]
            for person_ref in people:
                person_materials[person_ref].update(linked)
            for ruler_ref in rulers:
                ruler_materials[ruler_ref].update(linked)
            achievements.append(
                {
                    "achievement_ref": achievement_ref,
                    "independent_governance_key": achievement["independent_governance_key"],
                    "canonical_label": achievement["canonical_label"],
                    "person_refs": _unique(people),
                    "ruler_refs": _unique(rulers),
                    "neutral_material_refs": _unique(linked),
                    "unresolved_neutral_fact_refs": _unique(unresolved),
                    "projection_status": (
                        "ready_for_rule_judge" if not unresolved else "needs_fact_resolution"
                    ),
                    "payload": achievement,
                }
            )
            if not unresolved:
                for target in achievement.get("reuse_targets") or ():
                    projection_queue.append(
                        {
                            "candidate_ref": f"PROJ-{_hash([achievement_ref, target])[:20].upper()}",
                            "target": target,
                            "achievement_ref": achievement_ref,
                            "status": "needs_rule_judge",
                        }
                    )

    material_rows = sorted(facts.values(), key=lambda row: row["material_ref"])
    return {
        "contract": "neutral-material-intake",
        "status": "shadow_only",
        "input_fingerprint": _hash(
            {
                "materials": material_rows,
                "achievements": achievements,
                "projection_queue": projection_queue,
            }
        ),
        "material_count": len(material_rows),
        "materials": material_rows,
        "governance_achievement_count": len(achievements),
        "governance_achievements": sorted(
            achievements, key=lambda row: row["achievement_ref"]
        ),
        "person_evidence": [
            {"person_ref": ref, "material_refs": sorted(materials)}
            for ref, materials in sorted(person_materials.items())
        ],
        "ruler_evidence": [
            {"ruler_ref": ref, "material_refs": sorted(materials)}
            for ref, materials in sorted(ruler_materials.items())
        ],
        "projection_queue": sorted(
            projection_queue, key=lambda row: row["candidate_ref"]
        ),
        "database_writes": 0,
        "formal_writes": 0,
        "score_writes": 0,
    }


def governance_records_from_registry(
    registry: Mapping[str, object], *, dynasty: str
) -> tuple[GovernanceAchievementRecord, ...]:
    """Convert an accepted registry to current-value PostgreSQL records."""

    records = []
    for row in registry.get("achievements") or ():
        members = tuple(
            [
                GovernanceAchievementMember(
                    str(item["person_ref"]), "person", str(item["responsibility_role"])
                )
                for item in row.get("participants") or ()
            ]
            + [
                GovernanceAchievementMember(
                    str(item["ruler_ref"]), "ruler", "authorized"
                )
                for item in row.get("ruler_links") or ()
                if item.get("authorization_status") != "not_established"
            ]
        )
        records.append(
            GovernanceAchievementRecord(
                achievement_ref=str(row["achievement_ref"]),
                independent_governance_key=str(row["independent_governance_key"]),
                dynasty=dynasty,
                domain=str(row["domain"]),
                title=str(row["canonical_label"]),
                implementation_status=str(row["implementation_status"]),
                result_direction=str(row["result_direction"]),
                impact_level=str(row["scale"]["level"]),
                semantic_fingerprint=_hash(row),
                payload=dict(row),
                members=members,
            )
        )
    return tuple(sorted(records, key=lambda item: item.achievement_ref))
