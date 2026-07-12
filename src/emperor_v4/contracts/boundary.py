from __future__ import annotations

from dataclasses import dataclass


AMBIGUITY_SEVERITIES = frozenset({"informational", "warning", "blocking"})
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
    focal_person: str
    episode_type: str
    action: str
    responsibility_domain: str | None
    time_expression: str | None
    location_expression: str | None
    outcomes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.proposition_code or not self.semantic_hash:
            raise ValueError("PropositionCluster 缺少稳定身份")
        if not self.assertion_refs or len(set(self.assertion_refs)) != len(
            self.assertion_refs
        ):
            raise ValueError("PropositionCluster assertion_refs 必须非空且唯一")
        if not self.evidence_refs:
            raise ValueError("PropositionCluster 必须保留 evidence refs")


@dataclass(frozen=True, slots=True)
class EpisodeReviewUnit:
    review_unit_code: str
    cache_key: str
    evaluation_context: str
    focal_person: str
    time_window: str
    responsibility_domain: str
    proposition_cluster_refs: tuple[str, ...]
    proposition_semantic_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.review_unit_code or not self.cache_key:
            raise ValueError("EpisodeReviewUnit 缺少 code/cache key")
        if not self.proposition_cluster_refs:
            raise ValueError("EpisodeReviewUnit 不能为空")
        if len(self.proposition_cluster_refs) != len(self.proposition_semantic_hashes):
            raise ValueError("ReviewUnit cluster refs 与 semantic hashes 数量不一致")


@dataclass(frozen=True, slots=True)
class EpisodeBoundaryGroup:
    local_episode_code: str
    core_assertion_refs: tuple[str, ...]
    boundary_reason: str
    confidence: float

    def __post_init__(self) -> None:
        if not self.local_episode_code or not self.core_assertion_refs:
            raise ValueError("EpisodeBoundaryGroup 必须有 code 和 core assertions")
        if len(set(self.core_assertion_refs)) != len(self.core_assertion_refs):
            raise ValueError("EpisodeBoundaryGroup core assertion 重复")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("EpisodeBoundaryGroup confidence 必须在 0 到 1 之间")


@dataclass(frozen=True, slots=True)
class EpisodeRelation:
    from_episode_ref: str
    to_episode_ref: str
    relation_type: str
    evidence_assertion_refs: tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        if self.from_episode_ref == self.to_episode_ref:
            raise ValueError("EpisodeRelation 不得自环")
        if self.relation_type not in EPISODE_RELATION_TYPES:
            raise ValueError(f"未知 episode relation type: {self.relation_type}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("EpisodeRelation confidence 必须在 0 到 1 之间")


@dataclass(frozen=True, slots=True)
class ContextAssertionLink:
    assertion_ref: str
    applies_to_episode_refs: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if not self.assertion_ref or not self.applies_to_episode_refs:
            raise ValueError("ContextAssertionLink 必须声明 assertion 和目标 episode")


@dataclass(frozen=True, slots=True)
class EpisodeBoundaryReviewResult:
    review_unit_ref: str
    episode_groups: tuple[EpisodeBoundaryGroup, ...]
    relations: tuple[EpisodeRelation, ...]
    context_assertions: tuple[ContextAssertionLink, ...]
    unresolved_assertion_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        codes = [item.local_episode_code for item in self.episode_groups]
        if not self.review_unit_ref or not codes or len(codes) != len(set(codes)):
            raise ValueError("BoundaryReview 必须有唯一 local episode codes")
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
                raise ValueError("EpisodeRelation 引用了未知 local episode")
        for link in self.context_assertions:
            if not set(link.applies_to_episode_refs) <= code_set:
                raise ValueError("ContextAssertionLink 引用了未知 local episode")

    def validate_assertion_coverage(self, available_assertion_refs: set[str]) -> None:
        core = {
            ref for group in self.episode_groups for ref in group.core_assertion_refs
        }
        context = {item.assertion_ref for item in self.context_assertions}
        unresolved = set(self.unresolved_assertion_refs)
        relation_evidence = {
            ref for relation in self.relations for ref in relation.evidence_assertion_refs
        }
        used = core | context | unresolved | relation_evidence
        unknown = used - available_assertion_refs
        missing = available_assertion_refs - used
        if unknown or missing:
            raise ValueError(
                f"BoundaryReview assertion coverage 非法: unknown={sorted(unknown)}, "
                f"missing={sorted(missing)}"
            )


@dataclass(frozen=True, slots=True)
class RuleEvidenceUnitDraft:
    unit_code: str
    rule_code: str
    evaluation_context: str
    episode_refs: tuple[str, ...]
    relation_refs: tuple[str, ...]
    aggregation_reason: str
    status: str = "draft"

    def __post_init__(self) -> None:
        if not self.unit_code or not self.rule_code or not self.episode_refs:
            raise ValueError("RuleEvidenceUnitDraft 缺少核心字段")
        if self.status != "draft":
            raise ValueError("RuleEvidenceUnitDraft 不能直接成为正式 Judgment")
