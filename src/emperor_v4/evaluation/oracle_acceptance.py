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
    oracle_decision: str,
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
        "oracle_decision": oracle_decision,
    }


def build_oracle_assisted_acceptance_package(
    manifest_path: Path,
    review_package_path: Path,
    identity_manifest_path: Path,
    decision_path: Path,
) -> dict[str, Any]:
    manifest = _load_yaml(manifest_path)
    review = _load_json(review_package_path)
    identity_manifest = _load_yaml(identity_manifest_path)
    decision_record = _load_yaml(decision_path)
    frozen_codes = set(manifest.get("frozen_episode_codes") or ())
    episode_by_code = {
        item["episode_code"]: item
        for item in manifest.get("episodes", [])
        if item.get("episode_code") in frozen_codes
    }
    review_by_code = {item["episode_code"]: item for item in review.get("items", [])}
    if set(review_by_code) != frozen_codes:
        raise ValueError("oracle review package 未覆盖全部 frozen episode")

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

    decisions = decision_record.get("decisions") or {}
    if set(decisions) != frozen_codes:
        raise ValueError("oracle decisions 必须逐项覆盖 frozen episode")
    policy = decision_record["decision_policy"]
    packets: list[HistoricalEpisodePacket] = []
    packet_rows: list[dict[str, Any]] = []
    core_assertion_membership: set[str] = set()

    for episode_code in sorted(frozen_codes):
        gold = episode_by_code[episode_code]
        proposal = review_by_code[episode_code]
        oracle_decision = decisions[episode_code]
        decision_name = oracle_decision.get("decision")
        if decision_name not in {
            "oracle_accept_candidate",
            "oracle_accept_candidate_with_uncertainty",
        }:
            raise ValueError(f"未知 oracle decision: {episode_code}")

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
                    role_status=policy["participant_role_status"],
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
                    evidence_status=policy["assertion_evidence_status"],
                    representative=index == 0,
                )
            )

        completeness = dict(proposal["completeness"])
        completeness.update(oracle_decision.get("completeness") or {})
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
            "action": proposal.get("action"),
            "responsibility": proposal.get("responsibility"),
            "outcome": proposal.get("outcome") or [],
            "consequence": (
                oracle_decision.get("consequence")
                or proposal.get("consequence")
                or []
            ),
            "time_start": proposal.get("time_start"),
            "time_end": proposal.get("time_end"),
            "locations": proposal.get("locations") or [],
        }
        fingerprint = _semantic_fingerprint(semantic_payload)
        packet = HistoricalEpisodePacket(
            episode_id=f"EP-{fingerprint[:20].upper()}",
            episode_type=proposal["episode_type"],
            episode_status="proposed",
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
                oracle_decision.get("consequence")
                or proposal.get("consequence")
                or ()
            ),
            assertion_links=tuple(links),
            conflicts=tuple(
                oracle_decision.get("conflicts") or proposal.get("conflicts") or ()
            ),
            uncertainties=tuple(
                oracle_decision.get("uncertainties")
                or proposal.get("uncertainties")
                or ()
            ),
            completeness=completeness,
            lineage={
                "origin": "oracle_assisted_candidate",
                "proposal_episode_id": proposal["proposed_episode_id"],
            },
            provenance={
                "builder": "oracle_assisted_packet_compiler_v1",
                "decision_code": decision_record["decision_code"],
                "identity_manifest_code": identity_manifest[
                    "identity_manifest_code"
                ],
            },
        )
        packets.append(packet)
        packet_rows.append(
            _packet_json(
                episode_code, packet, identities_by_id, decision_name
            )
        )

    uncertainty_candidate_count = sum(
        item["oracle_decision"] == "oracle_accept_candidate_with_uncertainty"
        for item in packet_rows
    )
    candidate_identity_count = sum(
        participant.role_status == "candidate_resolved"
        for packet in packets
        for participant in packet.participants
    )
    draft_link_count = sum(
        link.evidence_status == "draft"
        for packet in packets
        for link in packet.assertion_links
    )
    missing_lineage_count = sum(
        not link.source_passage_ref
        for packet in packets
        for link in packet.assertion_links
    )
    semantic_fingerprints = [packet.semantic_fingerprint for packet in packets]
    summary = {
        "gold_episode_count": len(frozen_codes),
        "oracle_assisted_candidate_packet_count": len(packets),
        "oracle_uncertainty_candidate_count": uncertainty_candidate_count,
        "accuracy_metrics_status": "not_computable_oracle_contaminated",
        "semantic_fingerprint_collision_count": (
            len(semantic_fingerprints) - len(set(semantic_fingerprints))
        ),
        "canonical_identity_count": len(identities_by_id),
        "candidate_resolved_participant_count": candidate_identity_count,
        "draft_assertion_link_count": draft_link_count,
        "missing_passage_lineage_count": missing_lineage_count,
        "production_write_count": 0,
        "rule_projection_count": 0,
    }
    if len(packets) != len(frozen_codes):
        raise ValueError("oracle compiler 未构造全部 Gold-assisted candidate")
    if missing_lineage_count:
        raise ValueError("oracle candidate 缺少 passage lineage")

    return {
        "schema_version": 1,
        "package_code": "episode_pilot_v1_oracle_assisted_packet_acceptance",
        "status": "conditional_pass",
        "qualification": "oracle_assisted_constructability_passed",
        "g2_status": "reopen_required",
        "summary": summary,
        "constructability_checks": {
            "all_gold_assisted_candidates_constructed": len(packets)
            == len(frozen_codes),
            "lineage_passed": missing_lineage_count == 0,
            "automatic_acceptance_disabled": True,
            "accuracy_claim_disabled": True,
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
        "limitations": [
            "candidate grouping 使用 Gold boundary hint",
            "identity resolution 使用 Gold expected participants",
            "不得据此计算 episode recall、precision 或 wrong merge/split",
            "blind reconciliation 尚未验证",
        ],
    }
