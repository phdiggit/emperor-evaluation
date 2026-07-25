from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.episode import HistoricalEpisodePacket
from emperor_v4.contracts.source import SourceDocumentDraft, SourcePassage
from emperor_v4.contracts.boundary import RuleEvidenceMember


EPISODE_DISPOSITIONS = frozenset({"core_of_episode", "context_for_episode"})


@dataclass(frozen=True, slots=True)
class SourceDocumentRecord:
    document: SourceDocumentDraft
    revision_ref: str

    def __post_init__(self) -> None:
        if not self.revision_ref.strip():
            raise ValueError("SourceDocumentRecord 必须声明史源 revision_ref")

    @property
    def key(self) -> str:
        return self.document.document_cache_id


@dataclass(frozen=True, slots=True)
class EpisodeDispositionRecord:
    episode_id: str
    assertion_ref: str
    disposition: str
    reason: str
    follow_up: str | None = None

    def __post_init__(self) -> None:
        if not self.episode_id or not self.assertion_ref or not self.reason:
            raise ValueError("EpisodeDispositionRecord 缺少身份、Assertion 或理由")
        if self.disposition not in EPISODE_DISPOSITIONS:
            raise ValueError("EpisodeDispositionRecord disposition 非法")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.episode_id, self.assertion_ref, self.disposition)


@dataclass(frozen=True, slots=True)
class HistoricalOutcomeMember:
    actor_ref: str
    actor_kind: str
    role_code: str
    contribution_scope: str


@dataclass(frozen=True, slots=True)
class HistoricalOutcomeClusterRecord:
    outcome_ref: str
    outcome_kind: str
    independent_key: str
    canonical_label: str
    result_status: str
    result_direction: str
    scale_level: str
    semantic_fingerprint: str
    input_fingerprint: str
    acceptance_status: str
    payload: Mapping[str, object]
    members: tuple[HistoricalOutcomeMember, ...] = ()
    episode_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleEvidenceUnitRecord:
    unit_ref: str
    rule_code: str
    evaluation_context: str
    direction: str
    semantic_fingerprint: str
    status: str
    payload: Mapping[str, object]
    members: tuple[RuleEvidenceMember, ...]


@dataclass(frozen=True, slots=True)
class CoreRegistryBatch:
    source_documents: tuple[SourceDocumentRecord, ...] = ()
    source_passages: tuple[SourcePassage, ...] = ()
    assertions: tuple[AssertionDraft, ...] = ()
    episodes: tuple[HistoricalEpisodePacket, ...] = ()
    episode_dispositions: tuple[EpisodeDispositionRecord, ...] = ()
    episode_identity_anchors: Mapping[str, str] = field(default_factory=dict)
    outcome_clusters: tuple[HistoricalOutcomeClusterRecord, ...] = ()
    rule_evidence_units: tuple[RuleEvidenceUnitRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class CoreRegistryWriteResult:
    table_writes: Mapping[str, int]
    business_write_count: int
    model_call_count: int = 0


@dataclass(slots=True)
class InMemoryCoreRegistry:
    """Current-only 事务语义参考实现。"""

    _source_documents: dict[str, SourceDocumentRecord] = field(default_factory=dict)
    _source_passages: dict[str, SourcePassage] = field(default_factory=dict)
    _assertions: dict[str, AssertionDraft] = field(default_factory=dict)
    _episodes: dict[str, HistoricalEpisodePacket] = field(default_factory=dict)
    _episode_identity: dict[str, str] = field(default_factory=dict)
    _episode_anchor_by_id: dict[str, str] = field(default_factory=dict)
    _episode_participants: dict[tuple[str, str, str], str] = field(default_factory=dict)
    _episode_dispositions: dict[
        tuple[str, str, str], EpisodeDispositionRecord
    ] = field(default_factory=dict)
    _historical_outcome_clusters: dict[str, HistoricalOutcomeClusterRecord] = field(default_factory=dict)
    _outcome_cluster_members: dict[tuple[str, str, str], str] = field(default_factory=dict)
    _outcome_episode_links: dict[tuple[str, str], str] = field(default_factory=dict)
    _rule_evidence_units: dict[str, RuleEvidenceUnitRecord] = field(default_factory=dict)
    _rule_evidence_members: dict[tuple[str, str, str], str] = field(default_factory=dict)

    @staticmethod
    def _upsert_current(store: dict, key: object, value: object) -> int:
        if store.get(key) == value:
            return 0
        store[key] = value
        return 1

    def apply(self, batch: CoreRegistryBatch) -> CoreRegistryWriteResult:
        state = {
            name: dict(getattr(self, f"_{name}"))
            for name in (
                "source_documents",
                "source_passages",
                "assertions",
                "episodes",
                "episode_identity",
                "episode_anchor_by_id",
                "episode_participants",
                "episode_dispositions",
                "historical_outcome_clusters",
                "outcome_cluster_members",
                "outcome_episode_links",
                "rule_evidence_units",
                "rule_evidence_members",
            )
        }
        writes = {
            "source_documents": 0,
            "source_passages": 0,
            "assertions": 0,
            "historical_episodes": 0,
            "episode_participants": 0,
            "episode_assertion_dispositions": 0,
            "historical_outcome_clusters": 0,
            "outcome_cluster_members": 0,
            "outcome_episode_links": 0,
            "rule_evidence_units": 0,
            "rule_evidence_members": 0,
        }
        for record in batch.source_documents:
            writes["source_documents"] += self._upsert_current(
                state["source_documents"], record.key, record
            )
        for passage in batch.source_passages:
            if passage.document_cache_id not in state["source_documents"]:
                raise ValueError("SourcePassage 引用了未知 SourceDocument")
            writes["source_passages"] += self._upsert_current(
                state["source_passages"], passage.passage_cache_id, passage
            )
        for assertion in batch.assertions:
            if assertion.source_passage_ref not in state["source_passages"]:
                raise ValueError("Assertion 引用了未知 SourcePassage")
            writes["assertions"] += self._upsert_current(
                state["assertions"], assertion.assertion_code, assertion
            )
        for packet in batch.episodes:
            for link in packet.assertion_links:
                assertion = state["assertions"].get(link.assertion_ref)
                if assertion is None or assertion.source_passage_ref != link.source_passage_ref:
                    raise ValueError("HistoricalEpisode lineage 引用不闭合")
            anchor = str(batch.episode_identity_anchors.get(packet.episode_id) or packet.episode_id)
            existing_id = state["episode_identity"].get(anchor)
            if existing_id is not None and existing_id != packet.episode_id:
                raise ValueError("identity_anchor 已绑定其他 Episode")
            old = state["episodes"].get(packet.episode_id)
            if old is not None and state["episode_anchor_by_id"][packet.episode_id] != anchor:
                raise ValueError("Episode identity_anchor 不得变化")
            writes["historical_episodes"] += self._upsert_current(
                state["episodes"], packet.episode_id, packet
            )
            state["episode_identity"][anchor] = packet.episode_id
            state["episode_anchor_by_id"][packet.episode_id] = anchor
            current_participants = {
                (packet.episode_id, participant.person_ref, role_code): participant.role_status
                for participant in packet.participants
                for role_code in participant.role_codes
            }
            old_keys = {
                key for key in state["episode_participants"] if key[0] == packet.episode_id
            }
            new_keys = set(current_participants)
            for key in old_keys - new_keys:
                del state["episode_participants"][key]
                writes["episode_participants"] += 1
            for key, value in current_participants.items():
                writes["episode_participants"] += self._upsert_current(
                    state["episode_participants"], key, value
                )
        for disposition in batch.episode_dispositions:
            if disposition.episode_id not in state["episodes"]:
                raise ValueError("Disposition 引用了未知 Episode")
            if disposition.assertion_ref not in state["assertions"]:
                raise ValueError("Disposition 引用了未知 Assertion")
            writes["episode_assertion_dispositions"] += self._upsert_current(
                state["episode_dispositions"], disposition.key, disposition
            )
        for cluster in batch.outcome_clusters:
            unknown_episode_refs = sorted(set(cluster.episode_refs) - set(state["episodes"]))
            if unknown_episode_refs:
                raise ValueError(
                    f"HistoricalOutcomeCluster 引用未知 Episode: {unknown_episode_refs}"
                )
            writes["historical_outcome_clusters"] += self._upsert_current(
                state["historical_outcome_clusters"], cluster.outcome_ref, cluster
            )
            current_members = {
                (cluster.outcome_ref, member.actor_ref, member.actor_kind): (
                    member.role_code,
                    member.contribution_scope,
                )
                for member in cluster.members
            }
            writes["outcome_cluster_members"] += self._replace_members(
                state["outcome_cluster_members"], cluster.outcome_ref, current_members
            )
            current_episodes = {
                (cluster.outcome_ref, episode_ref): "core_result_chain"
                for episode_ref in cluster.episode_refs
            }
            writes["outcome_episode_links"] += self._replace_members(
                state["outcome_episode_links"], cluster.outcome_ref, current_episodes
            )
        for unit in batch.rule_evidence_units:
            writes["rule_evidence_units"] += self._upsert_current(
                state["rule_evidence_units"], unit.unit_ref, unit
            )
            current = {
                (unit.unit_ref, member.member_ref, member.member_type): member.member_role
                for member in unit.members
            }
            writes["rule_evidence_members"] += self._replace_members(
                state["rule_evidence_members"], unit.unit_ref, current
            )
        for name, value in state.items():
            setattr(self, f"_{name}", value)
        return CoreRegistryWriteResult(
            table_writes=writes,
            business_write_count=sum(writes.values()),
        )

    @classmethod
    def _replace_members(cls, store: dict, owner_ref: str, current: dict) -> int:
        writes = 0
        old_keys = {key for key in store if key[0] == owner_ref}
        for key in old_keys - set(current):
            del store[key]
            writes += 1
        for key, value in current.items():
            writes += cls._upsert_current(store, key, value)
        return writes

    def active_packets_by_identity(
        self, identity_anchors: tuple[str, ...]
    ) -> Mapping[str, HistoricalEpisodePacket]:
        return {
            anchor: self._episodes[self._episode_identity[anchor]]
            for anchor in identity_anchors
            if anchor in self._episode_identity
        }

    def snapshot_counts(self) -> Mapping[str, int]:
        return {
            "source_documents": len(self._source_documents),
            "source_passages": len(self._source_passages),
            "assertions": len(self._assertions),
            "historical_episodes": len(self._episodes),
            "episode_participants": len(self._episode_participants),
            "episode_assertion_dispositions": len(self._episode_dispositions),
            "historical_outcome_clusters": len(self._historical_outcome_clusters),
            "outcome_cluster_members": len(self._outcome_cluster_members),
            "outcome_episode_links": len(self._outcome_episode_links),
            "rule_evidence_units": len(self._rule_evidence_units),
            "rule_evidence_members": len(self._rule_evidence_members),
        }
