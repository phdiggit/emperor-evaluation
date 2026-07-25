from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Mapping

from emperor_v4.contracts.episode import HistoricalEpisodePacket


AMBIGUITY_SEVERITIES = frozenset({"informational", "warning", "blocking"})
ASSERTION_DISPOSITIONS = frozenset(
    {"core_of_episode", "context_for_episode", "unresolved", "excluded"}
)
EPISODE_RELATION_TYPES = frozenset(
    {
        "continues",
        "same_mandate_phase",
        "promotion_after",
        "renews_authority",
        "revokes",
        "outcome_of",
        "causal_followup",
        "context_for",
    }
)
RELATION_STATUSES = frozenset(
    {"proposed", "accepted", "accepted_with_uncertainty", "rejected", "superseded"}
)
EPISODE_PAIR_DECISIONS = frozenset(
    {"related", "distinct_unrelated", "unresolved"}
)


@dataclass(frozen=True, slots=True)
class NormalizedTime:
    start_sort_key: int | None
    end_sort_key: int | None
    precision: str
    dynasty_or_era: str | None
    source_expression: str | None

    def __post_init__(self) -> None:
        if (
            self.start_sort_key is not None
            and self.end_sort_key is not None
            and self.start_sort_key > self.end_sort_key
        ):
            raise ValueError("NormalizedTime start_sort_key 不得晚于 end_sort_key")
        if not self.precision:
            raise ValueError("NormalizedTime 必须声明 precision")


@dataclass(frozen=True, slots=True)
class AmbiguityIssue:
    code: str
    slot: str
    severity: str
    blocking_for_episode_types: tuple[str, ...] = ()
    source_flag: str | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.slot:
            raise ValueError("AmbiguityIssue 必须声明 code 和 slot")
        if self.severity not in AMBIGUITY_SEVERITIES:
            raise ValueError(f"未知 ambiguity severity: {self.severity}")

    def is_blocking_for(self, episode_type: str) -> bool:
        return self.severity == "blocking" or episode_type in set(
            self.blocking_for_episode_types
        )


@dataclass(frozen=True, slots=True)
class PropositionCluster:
    proposition_code: str
    semantic_hash: str
    assertion_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    evaluation_context: str
    focal_person_ref: str
    focal_role: str
    secondary_participant_refs: tuple[str, ...]
    episode_type: str
    action: str
    responsibility_family: str
    responsibility_domain: str | None
    normalized_time: NormalizedTime
    location_expression: str | None
    outcomes: tuple[str, ...]
    object_surface_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.proposition_code or not self.semantic_hash:
            raise ValueError("PropositionCluster 缺少稳定身份")
        if not self.assertion_refs or len(set(self.assertion_refs)) != len(
            self.assertion_refs
        ):
            raise ValueError("PropositionCluster assertion_refs 必须非空且唯一")
        if not self.evidence_refs:
            raise ValueError("PropositionCluster 必须保留 evidence refs")
        if not self.focal_person_ref or not self.focal_role:
            raise ValueError("PropositionCluster 必须有显式 focal person/role")
        if not self.responsibility_family:
            raise ValueError("PropositionCluster 必须有 responsibility_family")


@dataclass(frozen=True, slots=True)
class EpisodeReviewUnit:
    review_unit_code: str
    cache_key: str
    evaluation_context: str
    focal_person_ref: str
    focal_roles: tuple[str, ...]
    time_start_sort_key: int | None
    time_end_sort_key: int | None
    responsibility_family: str
    proposition_cluster_refs: tuple[str, ...]
    proposition_semantic_hashes: tuple[str, ...]
    boundary_policy_version: str
    output_schema_version: str
    model_family: str

    def __post_init__(self) -> None:
        if not self.review_unit_code or not self.cache_key:
            raise ValueError("EpisodeReviewUnit 缺少 code/cache key")
        if not self.focal_roles:
            raise ValueError("EpisodeReviewUnit 必须声明 focal roles")
        if not self.proposition_cluster_refs:
            raise ValueError("EpisodeReviewUnit 不能为空")
        if len(self.proposition_cluster_refs) != len(self.proposition_semantic_hashes):
            raise ValueError("ReviewUnit cluster refs 与 semantic hashes 数量不一致")


@dataclass(frozen=True, slots=True)
class BoundaryReviewRequest:
    review_unit: EpisodeReviewUnit
    proposition_clusters: tuple[PropositionCluster, ...]
    assertion_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if {item.proposition_code for item in self.proposition_clusters} != set(
            self.review_unit.proposition_cluster_refs
        ):
            raise ValueError("BoundaryReviewRequest clusters 与 ReviewUnit 不一致")
        if not self.assertion_refs:
            raise ValueError("BoundaryReviewRequest assertions 不能为空")


@dataclass(frozen=True, slots=True)
class EpisodeBoundaryGroup:
    local_episode_code: str
    core_assertion_refs: tuple[str, ...]
    boundary_reason: str
    confidence: float
    atomic_event_key: str | None = None

    def __post_init__(self) -> None:
        if not self.local_episode_code or not self.core_assertion_refs:
            raise ValueError("EpisodeBoundaryGroup 必须有 code 和 core assertions")
        if len(set(self.core_assertion_refs)) != len(self.core_assertion_refs):
            raise ValueError("EpisodeBoundaryGroup core assertion 重复")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("EpisodeBoundaryGroup confidence 必须在 0 到 1 之间")
        if self.atomic_event_key is not None and not self.atomic_event_key.strip():
            raise ValueError("atomic_event_key 不得是空字符串")


@dataclass(frozen=True, slots=True)
class AssertionDisposition:
    assertion_ref: str
    disposition: str
    episode_refs: tuple[str, ...]
    reason: str
    follow_up: str | None = None

    def __post_init__(self) -> None:
        if self.disposition not in ASSERTION_DISPOSITIONS:
            raise ValueError(f"未知 Assertion disposition: {self.disposition}")
        if not self.assertion_ref or not self.reason:
            raise ValueError("AssertionDisposition 必须声明 assertion 和 reason")
        if self.disposition == "core_of_episode" and len(self.episode_refs) != 1:
            raise ValueError("core_of_episode 必须且只能指向一个 episode")
        if self.disposition == "context_for_episode" and not self.episode_refs:
            raise ValueError("context_for_episode 必须指向至少一个 episode")
        if self.disposition in {"unresolved", "excluded"} and self.episode_refs:
            raise ValueError("unresolved/excluded 不得指向 episode")


@dataclass(frozen=True, slots=True)
class EpisodeRelationDraft:
    from_episode_ref: str
    to_episode_ref: str
    relation_type: str
    evidence_assertion_refs: tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        if self.from_episode_ref == self.to_episode_ref:
            raise ValueError("EpisodeRelationDraft 不得自环")
        if self.relation_type not in EPISODE_RELATION_TYPES:
            raise ValueError(f"未知 episode relation type: {self.relation_type}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("EpisodeRelationDraft confidence 必须在 0 到 1 之间")


@dataclass(frozen=True, slots=True)
class EpisodePairDisposition:
    left_episode_ref: str
    right_episode_ref: str
    decision: str
    reason: str
    relation_type: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.left_episode_ref
            or not self.right_episode_ref
            or self.left_episode_ref == self.right_episode_ref
        ):
            raise ValueError("EpisodePairDisposition 必须引用两个不同 episode")
        if self.decision not in EPISODE_PAIR_DECISIONS:
            raise ValueError(f"未知 episode pair decision: {self.decision}")
        if not self.reason:
            raise ValueError("EpisodePairDisposition 必须给出理由")
        if self.decision == "related":
            if self.relation_type not in EPISODE_RELATION_TYPES:
                raise ValueError("related pair 必须声明合法 relation_type")
        elif self.relation_type is not None:
            raise ValueError("非 related pair 不得声明 relation_type")

    @property
    def pair_key(self) -> frozenset[str]:
        return frozenset((self.left_episode_ref, self.right_episode_ref))


@dataclass(frozen=True, slots=True)
class RelationEvidenceLink:
    assertion_ref: str
    source_passage_ref: str
    evidence_status: str = "draft"


@dataclass(frozen=True, slots=True)
class EpisodeRelation:
    relation_id: str
    from_episode_ref: str
    to_episode_ref: str
    relation_type: str
    semantic_fingerprint: str
    relation_status: str
    evidence_links: tuple[RelationEvidenceLink, ...]
    confidence: float
    lineage: Mapping[str, str]
    provenance: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.from_episode_ref == self.to_episode_ref:
            raise ValueError("EpisodeRelation 不得自环")
        if self.relation_type not in EPISODE_RELATION_TYPES:
            raise ValueError(f"未知 episode relation type: {self.relation_type}")
        if self.relation_status not in RELATION_STATUSES:
            raise ValueError(f"未知 relation status: {self.relation_status}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("EpisodeRelation confidence 必须在 0 到 1 之间")
        if self.relation_status.startswith("accepted") and any(
            not link.source_passage_ref or link.evidence_status != "accepted"
            for link in self.evidence_links
        ):
            raise ValueError("accepted relation 必须有 accepted passage lineage")


@dataclass(frozen=True, slots=True)
class ContextAssertionLink:
    assertion_ref: str
    applies_to_episode_refs: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class EpisodeBoundaryReviewResult:
    review_unit_ref: str
    review_unit_cache_key: str
    proposition_semantic_hashes: tuple[str, ...]
    boundary_policy_version: str
    output_schema_version: str
    model_family: str
    episode_groups: tuple[EpisodeBoundaryGroup, ...]
    relations: tuple[EpisodeRelationDraft, ...]
    assertion_dispositions: tuple[AssertionDisposition, ...]
    review_provenance: Mapping[str, str]
    pair_dispositions: tuple[EpisodePairDisposition, ...] = ()

    def __post_init__(self) -> None:
        codes = [item.local_episode_code for item in self.episode_groups]
        if not self.review_unit_ref or len(codes) != len(set(codes)):
            raise ValueError("BoundaryReview local episode codes 必须唯一")
        if not self.review_unit_cache_key or not self.proposition_semantic_hashes:
            raise ValueError("BoundaryReview 未绑定 ReviewUnit cache/proposition hashes")
        code_set = set(codes)
        core_refs = [
            ref for group in self.episode_groups for ref in group.core_assertion_refs
        ]
        if len(core_refs) != len(set(core_refs)):
            raise ValueError("Assertion 最多只能属于一个 episode core")
        for relation in self.relations:
            if (
                relation.from_episode_ref not in code_set
                or relation.to_episode_ref not in code_set
            ):
                raise ValueError("EpisodeRelationDraft 引用了未知 local episode")
        pair_keys = [item.pair_key for item in self.pair_dispositions]
        if len(pair_keys) != len(set(pair_keys)):
            raise ValueError("每对 Episode 最多只能有一个 pair disposition")
        if any(not item.pair_key <= code_set for item in self.pair_dispositions):
            raise ValueError("EpisodePairDisposition 引用了未知 local episode")
        if self.output_schema_version in {
            "episode-boundary-review-v2.2",
            "episode-boundary-review-v2.3",
            "episode-boundary-review-v2.4",
            "episode-boundary-review-v2.5",
            "episode-boundary-review-v2.6",
            "episode-boundary-review-v2.7",
            "episode-boundary-review-v2.8",
        }:
            expected_pairs = {
                frozenset(pair) for pair in combinations(sorted(code_set), 2)
            }
            if set(pair_keys) != expected_pairs:
                raise ValueError("v2.2 BoundaryReview 必须完整处置所有 Episode pairs")
            relations_by_pair = {
                frozenset((item.from_episode_ref, item.to_episode_ref)): item
                for item in self.relations
            }
            for item in self.pair_dispositions:
                relation = relations_by_pair.get(item.pair_key)
                if item.decision == "related" and (
                    relation is None or relation.relation_type != item.relation_type
                ):
                    raise ValueError("related pair 与 EpisodeRelationDraft 不一致")
                if item.decision != "related" and relation is not None:
                    raise ValueError("非 related pair 不得生成 EpisodeRelationDraft")
            if set(relations_by_pair) != {
                item.pair_key
                for item in self.pair_dispositions
                if item.decision == "related"
            }:
                raise ValueError("每条 EpisodeRelationDraft 必须有 related pair disposition")
        disposition_refs = [item.assertion_ref for item in self.assertion_dispositions]
        if len(disposition_refs) != len(set(disposition_refs)):
            raise ValueError("每条 Assertion 必须且只能有一个主处置状态")
        for item in self.assertion_dispositions:
            if not set(item.episode_refs) <= code_set:
                raise ValueError("AssertionDisposition 引用了未知 local episode")

    def validate_for_unit(
        self,
        unit: EpisodeReviewUnit,
        assertions_by_cluster: Mapping[str, tuple[str, ...]],
    ) -> None:
        if (
            self.review_unit_ref != unit.review_unit_code
            or self.review_unit_cache_key != unit.cache_key
            or tuple(self.proposition_semantic_hashes)
            != tuple(unit.proposition_semantic_hashes)
            or self.boundary_policy_version != unit.boundary_policy_version
            or self.output_schema_version != unit.output_schema_version
            or self.model_family != unit.model_family
        ):
            raise ValueError("BoundaryReview 与 ReviewUnit 身份或版本不一致")
        if self.output_schema_version in {
            "episode-boundary-review-v2.4",
            "episode-boundary-review-v2.5",
            "episode-boundary-review-v2.6",
            "episode-boundary-review-v2.7",
            "episode-boundary-review-v2.8",
        } and any(
            not item.atomic_event_key for item in self.episode_groups
        ):
            raise ValueError("v2.4+ 每个 EpisodeBoundaryGroup 必须声明 atomic_event_key")
        available = {
            ref
            for cluster_ref in unit.proposition_cluster_refs
            for ref in assertions_by_cluster[cluster_ref]
        }
        disposition_by_ref = {
            item.assertion_ref: item for item in self.assertion_dispositions
        }
        if set(disposition_by_ref) != available:
            raise ValueError("BoundaryReview 主处置未完整覆盖当前 ReviewUnit assertions")
        core_by_ref = {
            ref: group.local_episode_code
            for group in self.episode_groups
            for ref in group.core_assertion_refs
        }
        if set(core_by_ref) != {
            ref
            for ref, item in disposition_by_ref.items()
            if item.disposition == "core_of_episode"
        }:
            raise ValueError("Episode core 与 AssertionDisposition 不一致")
        for ref, local_code in core_by_ref.items():
            if disposition_by_ref[ref].episode_refs != (local_code,):
                raise ValueError("core disposition 指向了错误 episode")
        relation_evidence = {
            ref for relation in self.relations for ref in relation.evidence_assertion_refs
        }
        if not relation_evidence <= available:
            raise ValueError("Relation evidence 引用了当前 ReviewUnit 之外的 assertion")


@dataclass(frozen=True, slots=True)
class BoundaryMaterializationResult:
    episode_packets: tuple[HistoricalEpisodePacket, ...]
    episode_relations: tuple[EpisodeRelation, ...]
    context_assertion_links: tuple[ContextAssertionLink, ...]
    unresolved_assertions: tuple[AssertionDisposition, ...]
    excluded_assertions: tuple[AssertionDisposition, ...]
    assertion_dispositions: tuple[AssertionDisposition, ...]
    review_provenance: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class AggregateContextMember:
    person_ref: str
    channel_ref: str
    episode_refs: tuple[str, ...]
    member_role: str
    supporting_only_for_aggregate: bool

    def __post_init__(self) -> None:
        if not self.person_ref or not self.channel_ref or not self.episode_refs:
            raise ValueError("AggregateContextMember 缺少人物、渠道或 episode")
        if not self.supporting_only_for_aggregate:
            raise ValueError("AggregateContext 成员必须声明仅支持集合层结算")


@dataclass(frozen=True, slots=True)
class AggregateContextDraft:
    context_code: str
    ruler_ref: str
    evaluation_window: str
    network_family: str
    channel_control_mode: str
    members: tuple[AggregateContextMember, ...]
    lineage: Mapping[str, str]
    status: str = "draft"

    def __post_init__(self) -> None:
        if not all(
            (
                self.context_code,
                self.ruler_ref,
                self.evaluation_window,
                self.network_family,
            )
        ):
            raise ValueError("AggregateContextDraft 缺少稳定身份字段")
        if self.status != "draft":
            raise ValueError("AggregateContextDraft 状态非法")
        if self.channel_control_mode not in {
            "multi_member_multi_channel",
            "single_controller_appointment_channel",
        }:
            raise ValueError("AggregateContextDraft 渠道控制模式非法")
        people = {item.person_ref for item in self.members}
        channels = {item.channel_ref for item in self.members}
        if self.channel_control_mode == "multi_member_multi_channel" and (
            len(people) < 2 or len(channels) < 2
        ):
            raise ValueError("长期私人网络至少需要两人和两条任用渠道")
        if not self.members:
            raise ValueError("AggregateContextDraft 缺少成员")

    @property
    def stable_key(self) -> str:
        return "|".join(
            (
                self.ruler_ref,
                self.evaluation_window,
                self.network_family,
            )
        )


@dataclass(frozen=True, slots=True)
class RuleEvidenceMember:
    member_ref: str
    member_type: str
    member_role: str

    def __post_init__(self) -> None:
        if self.member_type not in {
            "episode", "relation", "aggregate_context", "outcome_cluster"
        }:
            raise ValueError(
                "RuleEvidenceMember type 非法"
            )


@dataclass(frozen=True, slots=True)
class RuleEvidenceUnitDraft:
    unit_code: str
    rule_code: str
    evaluation_context: str
    semantic_fingerprint: str
    members: tuple[RuleEvidenceMember, ...]
    aggregation_reason: str
    status: str
    lineage: Mapping[str, str]
    provenance: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.unit_code or not self.rule_code or not self.members:
            raise ValueError("RuleEvidenceUnitDraft 缺少核心字段")
        if self.status != "draft":
            raise ValueError("RuleEvidenceUnitDraft 不能直接成为正式 Judgment")

    @property
    def episode_refs(self) -> tuple[str, ...]:
        return tuple(
            item.member_ref for item in self.members if item.member_type == "episode"
        )

    @property
    def relation_refs(self) -> tuple[str, ...]:
        return tuple(
            item.member_ref for item in self.members if item.member_type == "relation"
        )
