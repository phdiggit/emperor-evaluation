from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json

from emperor_v4.contracts.episode import HistoricalEpisodePacket


@dataclass(frozen=True, slots=True)
class VersionDecision:
    packet: HistoricalEpisodePacket
    write_required: bool
    model_call_required: bool
    semantic_changed: bool
    evidence_changed: bool
    judgment_invalidation_required: bool


def _payload_hash(payload: object) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
            "completeness": {
                slot: packet.completeness.get(slot)
                for slot in (
                    "identity",
                    "time",
                    "action",
                    "responsibility",
                    "outcome",
                    "consequence",
                )
            },
        }
    )


def evidence_payload_hash(packet: HistoricalEpisodePacket) -> str:
    stable_provenance = {
        key: value
        for key, value in packet.provenance.items()
        if key not in {"input_hash", "input_version"}
    }
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
            "evidence_completeness": {
                slot: packet.completeness.get(slot)
                for slot in ("source_diversity", "conflict_resolution")
            },
            "provenance": stable_provenance,
        }
    )


def apply_episode_revision(
    current: HistoricalEpisodePacket,
    observed: HistoricalEpisodePacket,
) -> VersionDecision:
    """比较确定性 packet，生成语义/证据分离的版本决策。"""

    semantic_changed = semantic_payload_hash(current) != semantic_payload_hash(observed)
    evidence_changed = evidence_payload_hash(current) != evidence_payload_hash(observed)

    if not semantic_changed and not evidence_changed:
        return VersionDecision(
            packet=current,
            write_required=False,
            model_call_required=False,
            semantic_changed=False,
            evidence_changed=False,
            judgment_invalidation_required=False,
        )

    conflicts_changed = current.conflicts != observed.conflicts
    if semantic_changed:
        packet = replace(
            observed,
            episode_id=current.episode_id,
            semantic_version=current.semantic_version + 1,
            evidence_version=current.evidence_version + (1 if evidence_changed else 0),
            lineage={
                "origin": "revision",
                "supersedes_episode_id": current.episode_id,
                "supersedes_semantic_version": str(current.semantic_version),
            },
        )
    else:
        packet = replace(
            observed,
            episode_id=current.episode_id,
            semantic_version=current.semantic_version,
            evidence_version=current.evidence_version + 1,
            episode_status="needs_evidence_review" if conflicts_changed else current.episode_status,
            lineage={
                "origin": "evidence_revision",
                "supersedes_episode_id": current.episode_id,
                "supersedes_evidence_version": str(current.evidence_version),
            },
        )

    return VersionDecision(
        packet=packet,
        write_required=True,
        model_call_required=False,
        semantic_changed=semantic_changed,
        evidence_changed=evidence_changed,
        judgment_invalidation_required=semantic_changed or conflicts_changed,
    )
