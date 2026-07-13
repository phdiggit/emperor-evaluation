from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.episode import HistoricalEpisodePacket
from emperor_v4.contracts.source import SourceDocumentDraft, SourcePassage
from emperor_v4.domain.versioning import evidence_payload_hash, semantic_payload_hash


REVIEW_ARTIFACT_TYPES = frozenset(
    {"boundary_review", "relation_review_artifact", "relation_proposal"}
)
REVIEW_ARTIFACT_STATUSES = frozenset({"draft", "proposed", "rejected", "superseded"})
EPISODE_DISPOSITIONS = frozenset({"core_of_episode", "context_for_episode"})


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceDocumentRecord:
    document: SourceDocumentDraft
    content_version: str

    def __post_init__(self) -> None:
        if not self.content_version.strip():
            raise ValueError("SourceDocumentRecord 必须声明 content_version")

    @property
    def key(self) -> tuple[str, str]:
        return (self.document.document_cache_id, self.content_version)


@dataclass(frozen=True, slots=True)
class EpisodeDispositionRecord:
    episode_id: str
    semantic_version: int
    evidence_version: int
    assertion_ref: str
    disposition: str
    reason: str
    follow_up: str | None = None

    def __post_init__(self) -> None:
        if not self.episode_id or not self.assertion_ref or not self.reason:
            raise ValueError("EpisodeDispositionRecord 缺少身份、Assertion 或理由")
        if self.semantic_version < 1 or self.evidence_version < 1:
            raise ValueError("EpisodeDispositionRecord version 必须从 1 开始")
        if self.disposition not in EPISODE_DISPOSITIONS:
            raise ValueError("G3A 只持久化与 Episode 直接关联的 disposition")

    @property
    def key(self) -> tuple[str, int, int, str, str]:
        return (
            self.episode_id,
            self.semantic_version,
            self.evidence_version,
            self.assertion_ref,
            self.disposition,
        )


@dataclass(frozen=True, slots=True)
class ReviewArtifactRecord:
    artifact_id: str
    artifact_type: str
    status: str
    basis_hash: str
    policy_version: str
    schema_version: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.artifact_id,
                self.basis_hash,
                self.policy_version,
                self.schema_version,
            )
        ):
            raise ValueError("ReviewArtifactRecord 缺少稳定身份或版本")
        if self.artifact_type not in REVIEW_ARTIFACT_TYPES:
            raise ValueError(f"G3A 不允许 artifact type: {self.artifact_type}")
        if self.status not in REVIEW_ARTIFACT_STATUSES:
            raise ValueError(f"G3A 不允许 artifact status: {self.status}")

    @property
    def idempotency_key(self) -> str:
        return _canonical_hash(
            {
                "artifact_type": self.artifact_type,
                "basis_hash": self.basis_hash,
                "policy_version": self.policy_version,
                "schema_version": self.schema_version,
                "payload": dict(self.payload),
            }
        )


@dataclass(frozen=True, slots=True)
class BoundaryReviewCacheEntry:
    cache_key: str
    input_hash: str
    policy_version: str
    schema_version: str
    model_family: str
    artifact_id: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.cache_key,
                self.input_hash,
                self.policy_version,
                self.schema_version,
                self.model_family,
                self.artifact_id,
            )
        ):
            raise ValueError("BoundaryReviewCacheEntry 缺少必填字段")


@dataclass(frozen=True, slots=True)
class CoreRegistryBatch:
    source_documents: tuple[SourceDocumentRecord, ...] = ()
    source_passages: tuple[SourcePassage, ...] = ()
    assertions: tuple[AssertionDraft, ...] = ()
    episodes: tuple[HistoricalEpisodePacket, ...] = ()
    episode_dispositions: tuple[EpisodeDispositionRecord, ...] = ()
    review_artifacts: tuple[ReviewArtifactRecord, ...] = ()
    boundary_cache_entries: tuple[BoundaryReviewCacheEntry, ...] = ()
    episode_identity_anchors: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CoreRegistryWriteResult:
    table_writes: Mapping[str, int]
    business_write_count: int
    model_call_count: int = 0


@dataclass(slots=True)
class InMemoryCoreRegistry:
    """G3A 离线事务语义参考实现；不连接数据库，不处理 Relation 或评分。"""

    _source_documents: dict[tuple[str, str], SourceDocumentRecord] = field(
        default_factory=dict
    )
    _source_passages: dict[str, SourcePassage] = field(default_factory=dict)
    _assertions: dict[str, AssertionDraft] = field(default_factory=dict)
    _episodes: dict[str, tuple[int, int]] = field(default_factory=dict)
    _episode_identity: dict[str, str] = field(default_factory=dict)
    _episode_anchor_by_id: dict[str, str] = field(default_factory=dict)
    _episode_versions: dict[
        tuple[str, int, int], HistoricalEpisodePacket
    ] = field(default_factory=dict)
    _episode_participants: dict[tuple[str, int, str, str], str] = field(
        default_factory=dict
    )
    _episode_dispositions: dict[
        tuple[str, int, int, str, str], EpisodeDispositionRecord
    ] = field(default_factory=dict)
    _review_artifacts: dict[str, ReviewArtifactRecord] = field(default_factory=dict)
    _artifact_idempotency: dict[str, str] = field(default_factory=dict)
    _boundary_cache: dict[str, BoundaryReviewCacheEntry] = field(default_factory=dict)

    def apply(self, batch: CoreRegistryBatch) -> CoreRegistryWriteResult:
        state = {
            "source_documents": dict(self._source_documents),
            "source_passages": dict(self._source_passages),
            "assertions": dict(self._assertions),
            "episodes": dict(self._episodes),
            "episode_identity": dict(self._episode_identity),
            "episode_anchor_by_id": dict(self._episode_anchor_by_id),
            "episode_versions": dict(self._episode_versions),
            "episode_participants": dict(self._episode_participants),
            "episode_dispositions": dict(self._episode_dispositions),
            "review_artifacts": dict(self._review_artifacts),
            "artifact_idempotency": dict(self._artifact_idempotency),
            "boundary_cache": dict(self._boundary_cache),
        }
        writes = {
            "source_documents": 0,
            "source_passages": 0,
            "assertions": 0,
            "historical_episodes": 0,
            "historical_episode_versions": 0,
            "episode_participants": 0,
            "episode_assertion_dispositions": 0,
            "review_artifacts": 0,
            "boundary_review_cache": 0,
        }

        for record in batch.source_documents:
            writes["source_documents"] += self._insert_immutable(
                state["source_documents"], record.key, record, "SourceDocument"
            )

        for passage in batch.source_passages:
            if not passage.is_contract_v2:
                raise ValueError("G3A 只持久化 SourcePassage v2")
            document_key = (passage.document_cache_id, str(passage.content_version or ""))
            if document_key not in state["source_documents"]:
                raise ValueError("SourcePassage 引用了未持久化的 document content version")
            writes["source_passages"] += self._insert_immutable(
                state["source_passages"],
                passage.passage_cache_id,
                passage,
                "SourcePassage",
            )

        for assertion in batch.assertions:
            if assertion.source_passage_ref not in state["source_passages"]:
                raise ValueError("Assertion 引用了未持久化的 SourcePassage")
            writes["assertions"] += self._insert_immutable(
                state["assertions"], assertion.assertion_code, assertion, "Assertion"
            )

        for packet in batch.episodes:
            for link in packet.assertion_links:
                assertion = state["assertions"].get(link.assertion_ref)
                if assertion is None or assertion.source_passage_ref != link.source_passage_ref:
                    raise ValueError("HistoricalEpisode lineage 引用了未知或不匹配的 Assertion")
            identity_anchor = str(
                batch.episode_identity_anchors.get(packet.episode_id) or packet.episode_id
            )
            episode_writes = self._stage_episode(state, packet, identity_anchor)
            writes["historical_episodes"] += episode_writes[0]
            writes["historical_episode_versions"] += episode_writes[1]
            writes["episode_participants"] += episode_writes[2]

        for disposition in batch.episode_dispositions:
            version_key = (
                disposition.episode_id,
                disposition.semantic_version,
                disposition.evidence_version,
            )
            if version_key not in state["episode_versions"]:
                raise ValueError("Disposition 引用了未知 Episode version")
            if disposition.assertion_ref not in state["assertions"]:
                raise ValueError("Disposition 引用了未知 Assertion")
            writes["episode_assertion_dispositions"] += self._insert_immutable(
                state["episode_dispositions"],
                disposition.key,
                disposition,
                "EpisodeDisposition",
            )

        for artifact in batch.review_artifacts:
            existing_id = state["artifact_idempotency"].get(artifact.idempotency_key)
            if existing_id is not None and existing_id != artifact.artifact_id:
                raise ValueError("ReviewArtifact idempotency key 已绑定其他 artifact_id")
            inserted = self._insert_immutable(
                state["review_artifacts"],
                artifact.artifact_id,
                artifact,
                "ReviewArtifact",
            )
            state["artifact_idempotency"][artifact.idempotency_key] = artifact.artifact_id
            writes["review_artifacts"] += inserted

        for entry in batch.boundary_cache_entries:
            if entry.artifact_id not in state["review_artifacts"]:
                raise ValueError("BoundaryReviewCache 引用了未知 ReviewArtifact")
            artifact = state["review_artifacts"][entry.artifact_id]
            if artifact.artifact_type != "boundary_review":
                raise ValueError("BoundaryReviewCache 只能引用 boundary_review artifact")
            writes["boundary_review_cache"] += self._insert_immutable(
                state["boundary_cache"], entry.cache_key, entry, "BoundaryReviewCache"
            )

        self._source_documents = state["source_documents"]
        self._source_passages = state["source_passages"]
        self._assertions = state["assertions"]
        self._episodes = state["episodes"]
        self._episode_identity = state["episode_identity"]
        self._episode_anchor_by_id = state["episode_anchor_by_id"]
        self._episode_versions = state["episode_versions"]
        self._episode_participants = state["episode_participants"]
        self._episode_dispositions = state["episode_dispositions"]
        self._review_artifacts = state["review_artifacts"]
        self._artifact_idempotency = state["artifact_idempotency"]
        self._boundary_cache = state["boundary_cache"]
        return CoreRegistryWriteResult(
            table_writes=writes,
            business_write_count=sum(writes.values()),
        )

    def counts(self) -> Mapping[str, int]:
        return {
            "source_documents": len(self._source_documents),
            "source_passages": len(self._source_passages),
            "assertions": len(self._assertions),
            "historical_episodes": len(self._episodes),
            "historical_episode_versions": len(self._episode_versions),
            "episode_participants": len(self._episode_participants),
            "episode_assertion_dispositions": len(self._episode_dispositions),
            "review_artifacts": len(self._review_artifacts),
            "boundary_review_cache": len(self._boundary_cache),
        }

    def active_packets_by_identity(
        self, identity_anchors: tuple[str, ...]
    ) -> Mapping[str, HistoricalEpisodePacket]:
        result = {}
        for anchor in identity_anchors:
            episode_id = self._episode_identity.get(anchor)
            if episode_id is None:
                continue
            semantic_version, evidence_version = self._episodes[episode_id]
            result[anchor] = self._episode_versions[
                (episode_id, semantic_version, evidence_version)
            ]
        return result

    @staticmethod
    def _insert_immutable(
        target: dict[Any, Any], key: Any, value: Any, label: str
    ) -> int:
        existing = target.get(key)
        if existing is None:
            target[key] = value
            return 1
        if existing != value:
            raise ValueError(f"{label} 稳定身份发生冲突")
        return 0

    @staticmethod
    def _stage_episode(
        state: dict[str, dict[Any, Any]],
        packet: HistoricalEpisodePacket,
        identity_anchor: str,
    ) -> tuple[int, int, int]:
        if packet.semantic_version < 1 or packet.evidence_version < 1:
            raise ValueError("HistoricalEpisode version 必须从 1 开始")
        version_key = (
            packet.episode_id,
            packet.semantic_version,
            packet.evidence_version,
        )
        existing_version = state["episode_versions"].get(version_key)
        if existing_version is not None:
            if existing_version != packet:
                raise ValueError("HistoricalEpisode version 身份发生冲突")
            return (0, 0, 0)

        current_ref = state["episodes"].get(packet.episode_id)
        episode_write = 0
        if current_ref is None:
            anchored_episode = state["episode_identity"].get(identity_anchor)
            if anchored_episode is not None and anchored_episode != packet.episode_id:
                raise ValueError("Episode identity_anchor 已绑定其他 episode_id")
            if (packet.semantic_version, packet.evidence_version) != (1, 1):
                raise ValueError("首次 Episode 持久化必须从 semantic/evidence v1 开始")
            state["episode_identity"][identity_anchor] = packet.episode_id
            state["episode_anchor_by_id"][packet.episode_id] = identity_anchor
            episode_write = 1
        else:
            if state["episode_anchor_by_id"].get(packet.episode_id) != identity_anchor:
                raise ValueError("HistoricalEpisode identity_anchor 不得变化")
            current = state["episode_versions"][(packet.episode_id, *current_ref)]
            semantic_step = packet.semantic_version - current.semantic_version
            evidence_step = packet.evidence_version - current.evidence_version
            if semantic_step == 0:
                if evidence_step != 1:
                    raise ValueError("Evidence revision 必须连续递增")
                if semantic_payload_hash(current) != semantic_payload_hash(packet):
                    raise ValueError("同一 semantic version 的语义 payload 不得变化")
                if evidence_payload_hash(current) == evidence_payload_hash(packet):
                    raise ValueError("Evidence version 不得在无证据变化时递增")
            elif semantic_step == 1:
                if evidence_step not in {0, 1}:
                    raise ValueError("Semantic revision 的 evidence version 不得跳号")
                if semantic_payload_hash(current) == semantic_payload_hash(packet):
                    raise ValueError("Semantic version 不得在语义无变化时递增")
            else:
                raise ValueError("Semantic version 必须连续递增")
            episode_write = 1

        state["episode_versions"][version_key] = packet
        state["episodes"][packet.episode_id] = (
            packet.semantic_version,
            packet.evidence_version,
        )
        participant_rows = 0
        for participant in packet.participants:
            for role_code in participant.role_codes:
                participant_rows += InMemoryCoreRegistry._insert_immutable(
                    state["episode_participants"],
                    (
                        packet.episode_id,
                        packet.semantic_version,
                        participant.person_ref,
                        role_code,
                    ),
                    participant.role_status,
                    "EpisodeParticipant",
                )
        return (episode_write, 1, participant_rows)
