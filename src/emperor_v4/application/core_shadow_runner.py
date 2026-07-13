from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Protocol

from emperor_v4.contracts.episode import HistoricalEpisodePacket
from emperor_v4.domain.versioning import apply_episode_revision
from emperor_v4.persistence.core_registry import (
    CoreRegistryBatch,
    CoreRegistryWriteResult,
    EpisodeDispositionRecord,
)


class CoreRegistry(Protocol):
    def active_packets_by_identity(
        self, identity_anchors: tuple[str, ...]
    ) -> Mapping[str, HistoricalEpisodePacket]: ...

    def apply(self, batch: CoreRegistryBatch) -> CoreRegistryWriteResult: ...


@dataclass(frozen=True, slots=True)
class CoreShadowRunResult:
    write_result: CoreRegistryWriteResult
    new_identity_anchors: tuple[str, ...]
    semantic_revision_anchors: tuple[str, ...]
    evidence_revision_anchors: tuple[str, ...]
    unchanged_identity_anchors: tuple[str, ...]

    @property
    def business_write_count(self) -> int:
        return self.write_result.business_write_count

    @property
    def model_call_count(self) -> int:
        return self.write_result.model_call_count


def run_core_shadow_sync(
    registry: CoreRegistry, observed: CoreRegistryBatch
) -> CoreShadowRunResult:
    """G3B 同步 runner：按稳定事件身份做局部版本决策并单事务落库。"""

    observed_by_anchor: dict[str, HistoricalEpisodePacket] = {}
    for packet in observed.episodes:
        anchor = str(observed.episode_identity_anchors.get(packet.episode_id) or "")
        if not anchor:
            raise ValueError("G3B runner 要求每个 Episode 显式声明 identity_anchor")
        if anchor in observed_by_anchor:
            raise ValueError("G3B runner 不支持同批次重复 identity_anchor")
        observed_by_anchor[anchor] = packet

    anchors = tuple(sorted(observed_by_anchor))
    current_by_anchor = registry.active_packets_by_identity(anchors)
    packets_to_write = []
    packet_by_observed_id: dict[str, HistoricalEpisodePacket] = {}
    anchor_by_persisted_id: dict[str, str] = {}
    new_anchors = []
    semantic_anchors = []
    evidence_anchors = []
    unchanged_anchors = []

    for anchor in anchors:
        packet = observed_by_anchor[anchor]
        current = current_by_anchor.get(anchor)
        if current is None:
            if (packet.semantic_version, packet.evidence_version) != (1, 1):
                raise ValueError("新 Episode 必须从 semantic/evidence v1 开始")
            selected = packet
            packets_to_write.append(selected)
            new_anchors.append(anchor)
        else:
            normalized = replace(packet, episode_id=current.episode_id)
            decision = apply_episode_revision(current, normalized)
            selected = decision.packet
            if decision.write_required:
                packets_to_write.append(selected)
                if decision.semantic_changed:
                    semantic_anchors.append(anchor)
                else:
                    evidence_anchors.append(anchor)
            else:
                unchanged_anchors.append(anchor)
        packet_by_observed_id[packet.episode_id] = selected
        anchor_by_persisted_id[selected.episode_id] = anchor

    changed_episode_ids = {packet.episode_id for packet in packets_to_write}
    remapped_dispositions = tuple(
        _remap_disposition(item, packet_by_observed_id)
        for item in observed.episode_dispositions
    )
    dispositions = tuple(
        item
        for item in remapped_dispositions
        if item.episode_id in changed_episode_ids
    )
    write_batch = CoreRegistryBatch(
        source_documents=observed.source_documents,
        source_passages=observed.source_passages,
        assertions=observed.assertions,
        episodes=tuple(packets_to_write),
        episode_dispositions=dispositions,
        review_artifacts=observed.review_artifacts,
        boundary_cache_entries=observed.boundary_cache_entries,
        episode_identity_anchors=anchor_by_persisted_id,
    )
    result = registry.apply(write_batch)
    return CoreShadowRunResult(
        write_result=result,
        new_identity_anchors=tuple(new_anchors),
        semantic_revision_anchors=tuple(semantic_anchors),
        evidence_revision_anchors=tuple(evidence_anchors),
        unchanged_identity_anchors=tuple(unchanged_anchors),
    )


def _remap_disposition(
    disposition: EpisodeDispositionRecord,
    packet_by_observed_id: Mapping[str, HistoricalEpisodePacket],
) -> EpisodeDispositionRecord:
    packet = packet_by_observed_id.get(disposition.episode_id)
    if packet is None:
        raise ValueError("Disposition 引用了本批次不存在的 Episode")
    return replace(
        disposition,
        episode_id=packet.episode_id,
        semantic_version=packet.semantic_version,
        evidence_version=packet.evidence_version,
    )
