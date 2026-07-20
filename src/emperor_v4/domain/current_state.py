from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from emperor_v4.contracts.episode import HistoricalEpisodePacket


def _payload_hash(payload: object) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def semantic_payload_hash(packet: HistoricalEpisodePacket) -> str:
    return _payload_hash(
        {
            "semantic_fingerprint": packet.semantic_fingerprint,
            "episode_type": packet.episode_type,
            "evaluation_context": packet.evaluation_context,
            "time_start": packet.time_start,
            "time_end": packet.time_end,
            "time_precision": packet.time_precision,
            "locations": packet.locations,
            "participants": [
                {
                    "person_ref": item.person_ref,
                    "role_codes": item.role_codes,
                    "role_status": item.role_status,
                }
                for item in packet.participants
            ],
            "action": packet.action,
            "responsibility": packet.responsibility,
            "outcome": packet.outcome,
            "consequence": packet.consequence,
            "completeness": dict(packet.completeness),
        }
    )


def evidence_payload_hash(packet: HistoricalEpisodePacket) -> str:
    return _payload_hash(
        {
            "assertion_links": [
                {
                    "assertion_ref": item.assertion_ref,
                    "source_passage_ref": item.source_passage_ref,
                    "relation": item.relation,
                    "supported_fields": item.supported_fields,
                    "evidence_status": item.evidence_status,
                    "representative": item.representative,
                }
                for item in packet.assertion_links
            ],
            "conflicts": packet.conflicts,
            "uncertainties": packet.uncertainties,
            "lineage": dict(packet.lineage),
            "provenance": dict(packet.provenance),
        }
    )


@dataclass(frozen=True, slots=True)
class CurrentStateDecision:
    packet: HistoricalEpisodePacket
    write_required: bool
    semantic_changed: bool
    evidence_changed: bool


def decide_current_episode(
    current: HistoricalEpisodePacket,
    observed: HistoricalEpisodePacket,
) -> CurrentStateDecision:
    if current.episode_id != observed.episode_id:
        raise ValueError("current episode update must preserve episode_id")
    semantic_changed = semantic_payload_hash(current) != semantic_payload_hash(observed)
    evidence_changed = evidence_payload_hash(current) != evidence_payload_hash(observed)
    return CurrentStateDecision(
        packet=observed if semantic_changed or evidence_changed else current,
        write_required=semantic_changed or evidence_changed,
        semantic_changed=semantic_changed,
        evidence_changed=evidence_changed,
    )
