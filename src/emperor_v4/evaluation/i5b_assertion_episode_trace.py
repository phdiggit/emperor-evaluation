from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.contracts.episode import (
    AssertionLink,
    EpisodeParticipant,
    HistoricalEpisodePacket,
)
from emperor_v4.domain.boundary import draft_rule_evidence_unit


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


def _string_values(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, Sequence):
        return (str(value),)
    return tuple(str(item) for item in value if str(item))


def _event_node_ref(assertion: Mapping[str, Any]) -> str:
    return str(
        assertion.get("event_node_ref")
        or assertion.get("candidate_episode_key")
        or ""
    ).strip()


def _episode_uncertainties(
    unit: Mapping[str, Any], assertions: Sequence[Mapping[str, Any]]
) -> tuple[str, ...]:
    values: list[str] = []
    values.extend(_string_values(unit.get("remaining_uncertainties")))
    for assertion in assertions:
        values.extend(_string_values(assertion.get("ambiguity_flags")))
        values.extend(_string_values(assertion.get("remaining_uncertainties")))
        values.extend(
            _string_values(
                (assertion.get("qualifiers") or {}).get("remaining_uncertainties")
            )
        )
    return tuple(dict.fromkeys(values))


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
    units = {
        str(item.get("unit_ref") or ""): item
        for item in _rows(assertion_payload.get("units"), "assertion review units")
    }
    episodes: list[dict[str, Any]] = []
    evidence_units: list[dict[str, Any]] = []
    assertion_link_count = 0
    for material in trace_units:
        unit_ref = material["unit_ref"]
        unit = units.get(unit_ref)
        if unit is None:
            continue
        allowed_dispositions = (
            {"formally_accepted"}
            if formal_acceptance
            else {"reviewed_ready_for_episode_shadow"}
        )
        if unit.get("review_disposition") not in allowed_dispositions:
            raise ValueError(f"assertion unit 尚未完成 review: {unit_ref}")
        assertions = _rows(unit.get("assertion_drafts"), f"{unit_ref} assertions")

        grouped_assertions: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        grouping_mode = "explicit_event_node" if formal_acceptance else "source_passage"
        for assertion in assertions:
            passage_ref = str(assertion.get("source_passage_ref") or "")
            if not passage_ref:
                raise ValueError(f"assertion 缺少 passage lineage: {unit_ref}")
            if formal_acceptance:
                group_ref = _event_node_ref(assertion)
                if not group_ref:
                    raise ValueError(
                        f"formal assertion 缺少 event_node_ref/candidate_episode_key: "
                        f"{unit_ref}/{assertion.get('assertion_code')}"
                    )
            else:
                group_ref = passage_ref
            grouped_assertions[group_ref].append(assertion)

        episode_members: dict[str, str] = {}
        assertion_refs: list[str] = []
        for group_ref, episode_assertions in sorted(grouped_assertions.items()):
            assertion_refs.extend(
                str(item.get("assertion_code") or "") for item in episode_assertions
            )
            focal_refs = sorted(
                {
                    str(ref)
                    for item in episode_assertions
                    for ref in (
                        (item.get("qualifiers") or {}).get(
                            "candidate_focal_person_refs"
                        )
                        or ()
                    )
                    if str(ref).startswith("PER-") and str(ref) != ruler_ref
                }
            )
            participants = [
                EpisodeParticipant(ruler_ref, ("ruler",), "resolved")
            ] + [
                EpisodeParticipant(ref, ("focal_person",), "resolved")
                for ref in focal_refs
            ]
            links = tuple(
                AssertionLink(
                    assertion_ref=str(item["assertion_code"]),
                    source_passage_ref=str(item["source_passage_ref"]),
                    relation=(
                        "supports_accepted_episode"
                        if formal_acceptance
                        else "supports_episode_draft"
                    ),
                    supported_fields=tuple(
                        (item.get("passage_support") or {}).get("supported_fields")
                        or ()
                    ),
                    evidence_status="accepted" if formal_acceptance else "draft",
                    representative=index == 0,
                )
                for index, item in enumerate(episode_assertions)
            )
            assertion_link_count += len(links)
            source_passage_refs = sorted(
                {item.source_passage_ref for item in links}
            )
            uncertainties = (
                _episode_uncertainties(unit, episode_assertions)
                if formal_acceptance
                else ()
            )
            episode_payload = (
                {
                    "rule_code": rule_code,
                    "unit_ref": unit_ref,
                    "grouping_mode": grouping_mode,
                    "group_ref": group_ref,
                    "assertion_refs": [item.assertion_ref for item in links],
                }
                if formal_acceptance
                else {
                    "rule_code": rule_code,
                    "unit_ref": unit_ref,
                    "passage_ref": group_ref,
                    "assertion_refs": [item.assertion_ref for item in links],
                }
            )
            episode_fingerprint = _hash(episode_payload)
            episode = HistoricalEpisodePacket(
                episode_id=f"EP-{episode_fingerprint[:20].upper()}",
                episode_type=f"{rule_code}_evidence_episode",
                episode_status=(
                    "accepted_with_uncertainty"
                    if formal_acceptance and uncertainties
                    else "accepted" if formal_acceptance else "proposed"
                ),
                evaluation_context=ruler_ref,
                semantic_version=1,
                evidence_version=1,
                semantic_fingerprint=episode_fingerprint,
                time_start=None,
                time_end=None,
                time_precision="source_expression_only",
                locations=tuple(
                    sorted(
                        {
                            str(item["location_expression"])
                            for item in episode_assertions
                            if item.get("location_expression")
                        }
                    )
                ),
                participants=tuple(participants),
                action="；".join(
                    dict.fromkeys(str(item["predicate"]) for item in episode_assertions)
                ),
                responsibility=(
                    "formal ruler-context attribution accepted"
                    if formal_acceptance
                    else "shadow routing only; formal attribution not accepted"
                ),
                outcome=tuple(
                    dict.fromkeys(str(item["object"]) for item in episode_assertions)
                ),
                consequence=(),
                assertion_links=links,
                conflicts=(),
                uncertainties=(
                    uncertainties
                    if formal_acceptance
                    else tuple(
                        dict.fromkeys(
                            (*uncertainties, "draft assertions; no formal fact acceptance")
                        )
                    )
                ),
                completeness={
                    "identity": "complete",
                    "time": "partial",
                    "action": "complete",
                    "responsibility": "partial",
                    "outcome": "partial",
                    "consequence": "partial",
                    "source_diversity": "partial",
                    "conflict_resolution": "not_applicable",
                },
                lineage=(
                    {
                        "assertion_report_sha256": str(
                            assertion_payload.get("report_sha256") or ""
                        ),
                        "unit_ref": unit_ref,
                        "event_node_ref": group_ref,
                        "source_passage_refs": ",".join(source_passage_refs),
                    }
                    if formal_acceptance
                    else {
                        "assertion_report_sha256": str(
                            assertion_payload.get("report_sha256") or ""
                        ),
                        "unit_ref": unit_ref,
                        "source_passage_ref": group_ref,
                    }
                ),
                provenance={
                    "builder": (
                        "i5b_assertion_episode_trace_v2"
                        if formal_acceptance
                        else "i5b_joint_projection_episode_trace_v1"
                    ),
                    "input_version": str(
                        assertion_payload.get("schema_version") or "unknown"
                    ),
                    "input_hash": str(
                        assertion_payload.get("report_sha256") or "unknown"
                    ),
                },
            )
            episodes.append(asdict(episode))
            episode_members[episode.episode_id] = (
                "negative_credit_chain_component"
                if material["side"] == "negative"
                else "positive_feedback_chain_component"
            )
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
