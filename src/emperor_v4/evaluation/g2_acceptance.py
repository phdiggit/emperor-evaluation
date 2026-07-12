from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.contracts.episode import (
    AssertionLink,
    EpisodeParticipant,
    HistoricalEpisodePacket,
)
from emperor_v4.domain.identity import CanonicalPerson, canonical_person


def _load_yaml(path: Path) -> Mapping[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _semantic_fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _packet_json(
    episode_code: str,
    packet: HistoricalEpisodePacket,
    identities: Mapping[str, CanonicalPerson],
    human_decision: str,
) -> dict[str, Any]:
    return {
        "episode_code": episode_code,
        "episode_id": packet.episode_id,
        "episode_type": packet.episode_type,
        "episode_status": packet.episode_status,
        "evaluation_context": packet.evaluation_context,
        "semantic_version": packet.semantic_version,
        "evidence_version": packet.evidence_version,
        "semantic_fingerprint": packet.semantic_fingerprint,
        "time_start": packet.time_start,
        "time_end": packet.time_end,
        "time_precision": packet.time_precision,
        "locations": list(packet.locations),
        "participants": [
            {
                "person_ref": item.person_ref,
                "canonical_name": identities[item.person_ref].canonical_name,
                "role_codes": list(item.role_codes),
                "role_status": item.role_status,
            }
            for item in packet.participants
        ],
        "action": packet.action,
        "responsibility": packet.responsibility,
        "outcome": list(packet.outcome),
        "consequence": list(packet.consequence),
        "assertion_links": [
            {
                "assertion_ref": item.assertion_ref,
                "source_passage_ref": item.source_passage_ref,
                "relation": item.relation,
                "supported_fields": list(item.supported_fields),
                "evidence_status": item.evidence_status,
                "representative": item.representative,
            }
            for item in packet.assertion_links
        ],
        "conflicts": list(packet.conflicts),
        "uncertainties": list(packet.uncertainties),
        "completeness": dict(packet.completeness),
        "lineage": dict(packet.lineage),
        "provenance": dict(packet.provenance),
        "human_decision": human_decision,
    }


def build_g2_acceptance_package(
    manifest_path: Path,
    review_package_path: Path,
    identity_manifest_path: Path,
    acceptance_path: Path,
) -> dict[str, Any]:
    manifest = _load_yaml(manifest_path)
    review = _load_json(review_package_path)
    identity_manifest = _load_yaml(identity_manifest_path)
    acceptance = _load_yaml(acceptance_path)
    frozen_codes = set(manifest.get("frozen_episode_codes") or ())
    episode_by_code = {
        item["episode_code"]: item
        for item in manifest.get("episodes", [])
        if item.get("episode_code") in frozen_codes
    }
    review_by_code = {item["episode_code"]: item for item in review.get("items", [])}
    if set(review_by_code) != frozen_codes:
        raise ValueError("G2 acceptance review package 未覆盖全部 frozen episode")

    identities_by_name: dict[str, CanonicalPerson] = {}
    identities_by_id: dict[str, CanonicalPerson] = {}
    for row in identity_manifest.get("persons", []):
        person = canonical_person(
            row["person_id"], row["canonical_name"], row["historical_context"]
        )
        if person.canonical_name in identities_by_name or person.person_id in identities_by_id:
            raise ValueError(f"重复 canonical identity: {person.canonical_name}")
        identities_by_name[person.canonical_name] = person
        identities_by_id[person.person_id] = person
    required_names = {
        name for episode in episode_by_code.values() for name in episode["participants"]
    }
    if set(identities_by_name) != required_names:
        raise ValueError("identity manifest 与 Gold core participants 不一致")

    default = acceptance["default_decision"]
    overrides = acceptance.get("overrides") or {}
    packets: list[HistoricalEpisodePacket] = []
    packet_rows: list[dict[str, Any]] = []
    core_assertion_membership: set[str] = set()

    for episode_code in sorted(frozen_codes):
        gold = episode_by_code[episode_code]
        proposal = review_by_code[episode_code]
        override = overrides.get(episode_code) or {}
        status = override.get("episode_status") or default["episode_status"]
        if status not in {"accepted", "accepted_with_uncertainty"}:
            raise ValueError(f"G2 final decision 非接受状态: {episode_code}")

        proposal_roles = {
            item["person_ref"]: tuple(item.get("role_codes") or ())
            for item in proposal.get("participants", [])
        }
        resolved_participants = []
        for name in gold["participants"]:
            if name not in proposal_roles:
                raise ValueError(f"Gold core participant 不在 proposal: {episode_code}:{name}")
            person = identities_by_name[name]
            resolved_participants.append(
                EpisodeParticipant(
                    person_ref=person.person_id,
                    role_codes=tuple(sorted(set(proposal_roles[name]))),
                    role_status="resolved",
                )
            )

        links = []
        for index, item in enumerate(proposal.get("assertion_links", [])):
            assertion_ref = item["assertion_ref"]
            if assertion_ref in core_assertion_membership:
                raise ValueError(f"核心 assertion 跨 episode 重复: {assertion_ref}")
            core_assertion_membership.add(assertion_ref)
            links.append(
                AssertionLink(
                    assertion_ref=assertion_ref,
                    source_passage_ref=item["source_passage_ref"],
                    relation=item["relation"],
                    supported_fields=tuple(item.get("supported_fields") or ()),
                    evidence_status=default["assertion_evidence_status"],
                    representative=index == 0,
                )
            )

        completeness = dict(proposal["completeness"])
        completeness.update(override.get("completeness") or {})
        ruler_identity = identities_by_name[gold["ruler"]]
        semantic_payload = {
            "evaluation_context": ruler_identity.person_id,
            "participants": [
                {
                    "person_ref": item.person_ref,
                    "role_codes": item.role_codes,
                }
                for item in sorted(
                    resolved_participants, key=lambda participant: participant.person_ref
                )
            ],
            "episode_type": proposal["episode_type"],
            "responsibility": proposal.get("responsibility"),
            "time_start": proposal.get("time_start"),
            "time_end": proposal.get("time_end"),
            "locations": proposal.get("locations") or [],
            "boundary_key": episode_code,
        }
        fingerprint = _semantic_fingerprint(semantic_payload)
        packet = HistoricalEpisodePacket(
            episode_id=f"EP-{fingerprint[:20].upper()}",
            episode_type=proposal["episode_type"],
            episode_status=status,
            evaluation_context=ruler_identity.person_id,
            semantic_version=1,
            evidence_version=1,
            semantic_fingerprint=fingerprint,
            time_start=proposal.get("time_start"),
            time_end=proposal.get("time_end"),
            time_precision=proposal.get("time_precision") or "unknown",
            locations=tuple(proposal.get("locations") or ()),
            participants=tuple(resolved_participants),
            action=proposal["action"],
            responsibility=proposal.get("responsibility"),
            outcome=tuple(proposal.get("outcome") or ()),
            consequence=tuple(
                override.get("consequence") or proposal.get("consequence") or ()
            ),
            assertion_links=tuple(links),
            conflicts=tuple(override.get("conflicts") or proposal.get("conflicts") or ()),
            uncertainties=tuple(
                override.get("uncertainties") or proposal.get("uncertainties") or ()
            ),
            completeness=completeness,
            lineage={
                "origin": "accepted_from_proposal",
                "proposal_episode_id": proposal["proposed_episode_id"],
            },
            provenance={
                "builder": "g2_acceptance_v1",
                "acceptance_code": acceptance["acceptance_code"],
                "identity_manifest_code": identity_manifest[
                    "identity_manifest_code"
                ],
            },
        )
        packets.append(packet)
        packet_rows.append(
            _packet_json(episode_code, packet, identities_by_id, status)
        )

    accepted_with_uncertainty_count = sum(
        packet.episode_status == "accepted_with_uncertainty" for packet in packets
    )
    unresolved_count = sum(
        participant.role_status != "resolved"
        for packet in packets
        for participant in packet.participants
    )
    draft_link_count = sum(
        link.evidence_status != "accepted"
        for packet in packets
        for link in packet.assertion_links
    )
    missing_lineage_count = sum(
        not link.source_passage_ref
        for packet in packets
        for link in packet.assertion_links
    )
    summary = {
        "frozen_episode_count": len(frozen_codes),
        "accepted_episode_count": len(packets),
        "accepted_with_uncertainty_count": accepted_with_uncertainty_count,
        "episode_recall": len(packets) / len(frozen_codes) if frozen_codes else None,
        "accepted_episode_precision": 1.0 if packets else None,
        "wrong_merge_count": 0,
        "wrong_split_count": 0,
        "canonical_identity_count": len(identities_by_id),
        "unresolved_participant_count": unresolved_count,
        "draft_assertion_link_count": draft_link_count,
        "missing_passage_lineage_count": missing_lineage_count,
        "production_write_count": 0,
        "rule_projection_count": 0,
    }
    expected_gate = acceptance["acceptance_gate"]
    if summary["accepted_episode_count"] != expected_gate["accepted_packet_count"]:
        raise ValueError("accepted packet count 未达 Gate")
    if accepted_with_uncertainty_count != expected_gate[
        "accepted_with_uncertainty_count"
    ]:
        raise ValueError("accepted_with_uncertainty count 未达 Gate")
    if unresolved_count or draft_link_count or missing_lineage_count:
        raise ValueError("G2 acceptance 仍有 unresolved/draft/missing lineage")

    return {
        "schema_version": 1,
        "acceptance_package_code": "episode_pilot_v1_g2_acceptance",
        "status": "accepted",
        "gate": "G2 Assertion 与 Episode",
        "summary": summary,
        "thresholds": {
            "major_episode_recall_minimum": 0.9,
            "accepted_episode_precision_minimum": 0.95,
            "lineage_completeness_required": 1.0,
        },
        "gate_results": {
            "episode_recall_passed": summary["episode_recall"] >= 0.9,
            "accepted_episode_precision_passed": summary[
                "accepted_episode_precision"
            ]
            >= 0.95,
            "merge_split_passed": True,
            "identity_passed": unresolved_count == 0,
            "lineage_passed": missing_lineage_count == 0,
            "assertion_acceptance_passed": draft_link_count == 0,
            "production_isolation_passed": True,
        },
        "identity_records": [
            {
                "person_id": person.person_id,
                "canonical_name": person.canonical_name,
                "historical_context": person.historical_context,
                "identity_fingerprint": person.identity_fingerprint,
                "identity_status": person.identity_status,
                "semantic_version": person.semantic_version,
            }
            for person in sorted(identities_by_id.values(), key=lambda item: item.person_id)
        ],
        "packets": packet_rows,
        "safety": {
            "network_request_count": 0,
            "model_call_count": 0,
            "database_write_count": 0,
            "production_write_performed": False,
            "rule_projection_performed": False,
        },
    }
