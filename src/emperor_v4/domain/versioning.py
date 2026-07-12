from __future__ import annotations

from dataclasses import dataclass, replace

from emperor_v4.contracts.episode import HistoricalEpisodePacket


@dataclass(frozen=True, slots=True)
class VersionDecision:
    packet: HistoricalEpisodePacket
    write_required: bool
    model_call_required: bool
    semantic_changed: bool
    evidence_changed: bool
    judgment_invalidation_required: bool


def apply_episode_revision(
    current: HistoricalEpisodePacket,
    observed: HistoricalEpisodePacket,
) -> VersionDecision:
    """比较确定性 packet，生成语义/证据分离的版本决策。"""

    current_refs = {
        (link.assertion_ref, link.source_passage_ref, link.relation)
        for link in current.assertion_links
    }
    observed_refs = {
        (link.assertion_ref, link.source_passage_ref, link.relation)
        for link in observed.assertion_links
    }
    semantic_changed = current.semantic_fingerprint != observed.semantic_fingerprint
    evidence_changed = current_refs != observed_refs or current.conflicts != observed.conflicts

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
