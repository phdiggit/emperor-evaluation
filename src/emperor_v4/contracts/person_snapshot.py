from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


TALENT_GRADES = {"historic", "top", "important", "usable", "ordinary"}
AUTHORITY_CONSENSUS_VALUES = {"weak", "moderate", "strong", "disputed"}
EVIDENCE_STRENGTH_VALUES = {"none", "weak", "moderate", "strong"}
EVIDENCE_COVERAGE_VALUES = {
    "insufficient",
    "partial",
    "substantial",
    "comprehensive",
}
NEGATIVE_TALENT_CLASSES = {
    "sycophant",
    "favorite",
    "power_abuser",
    "framer",
    "extractive_official",
    "cruel_official",
    "incompetent_harmful",
    "traitorous_actor",
    "mixed_or_disputed",
}
NEGATIVE_TALENT_SEVERITIES = {"minor", "material", "major", "historic"}


@dataclass(frozen=True, slots=True)
class PersonProfileSnapshot:
    profile_ref: str
    canonical_person_ref: str
    snapshot_version: str
    talent_grade: str
    talent_grade_version: str
    talent_grade_confidence: float
    talent_authority_consensus: str
    talent_performance_support: str
    talent_evidence_coverage: str
    capability_domains: tuple[str, ...]
    negative_talent_class: str | None
    negative_talent_severity: str | None
    negative_talent_version: str
    lineage_refs: tuple[str, ...]
    source_profile_ref: str
    source_row_fingerprint: str
    semantic_fingerprint: str
    review_status: str = "human_frozen"

    def __post_init__(self) -> None:
        if not all(
            (
                self.profile_ref,
                self.canonical_person_ref,
                self.snapshot_version,
                self.talent_grade_version,
                self.negative_talent_version,
                self.source_profile_ref,
                self.source_row_fingerprint,
                self.semantic_fingerprint,
            )
        ):
            raise ValueError("PersonProfileSnapshot 缺少稳定身份或版本")
        if self.talent_grade not in TALENT_GRADES:
            raise ValueError("PersonProfileSnapshot talent_grade 非法")
        if not 0 <= self.talent_grade_confidence <= 1:
            raise ValueError("PersonProfileSnapshot talent_grade_confidence 非法")
        if self.talent_authority_consensus not in AUTHORITY_CONSENSUS_VALUES:
            raise ValueError("PersonProfileSnapshot talent_authority_consensus 非法")
        if self.talent_performance_support not in EVIDENCE_STRENGTH_VALUES:
            raise ValueError("PersonProfileSnapshot talent_performance_support 非法")
        if self.talent_evidence_coverage not in EVIDENCE_COVERAGE_VALUES:
            raise ValueError("PersonProfileSnapshot talent_evidence_coverage 非法")
        if self.negative_talent_class is None:
            if self.negative_talent_severity is not None:
                raise ValueError("PersonProfileSnapshot 负面画像轴形状非法")
        elif (
            self.negative_talent_class not in NEGATIVE_TALENT_CLASSES
            or self.negative_talent_severity not in NEGATIVE_TALENT_SEVERITIES
        ):
            raise ValueError("PersonProfileSnapshot 负面画像轴非法")
        if len(self.source_row_fingerprint) != 64:
            raise ValueError("PersonProfileSnapshot 源行指纹非法")
        if not self.lineage_refs:
            raise ValueError("PersonProfileSnapshot 缺少 lineage")
        if self.review_status != "human_frozen":
            raise ValueError("PersonProfileSnapshot 必须先经人工冻结")


@dataclass(frozen=True, slots=True)
class RulerTeamWindowMember:
    person_ref: str
    profile_ref: str
    active_from: str
    active_to: str
    role_families: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all((self.person_ref, self.profile_ref, self.active_from, self.active_to)):
            raise ValueError("RulerTeamWindowMember 缺少身份或活动时间")
        if not self.role_families or not self.evidence_refs:
            raise ValueError("RulerTeamWindowMember 缺少角色或证据")


TEAM_RELATIONSHIP_ORIGINS = {
    "self_selected",
    "inherited_and_retained",
    "recalled",
    "passive_holdover",
}
TEAM_POOL_DISPOSITIONS = {
    "included",
    "excluded_passive_holdover",
    "insufficient_membership_evidence",
}
WINDOW_RISK_EXPOSURE_STATES = {
    "not_required_no_global_risk",
    "exposed_in_window",
    "not_exposed_after_bounded_review",
    "insufficient_evidence",
}


@dataclass(frozen=True, slots=True)
class RulerTeamWindowMemberAssessment:
    """Versioned relationship overlay; it never splits a person's career grade."""

    window_ref: str
    person_ref: str
    assessment_policy_version: str
    relationship_origin: str
    substantive_role_status: str
    team_pool_disposition: str
    window_risk_exposure: str
    membership_evidence_refs: tuple[str, ...]
    risk_exposure_evidence_refs: tuple[str, ...] = ()
    review_status: str = "human_frozen"

    def __post_init__(self) -> None:
        if not all((self.window_ref, self.person_ref, self.assessment_policy_version)):
            raise ValueError("团队窗口成员适用性缺少版本化身份")
        if self.relationship_origin not in TEAM_RELATIONSHIP_ORIGINS:
            raise ValueError("团队窗口成员关系来源非法")
        if self.substantive_role_status not in {"confirmed", "insufficient_evidence"}:
            raise ValueError("团队窗口成员实质履职状态非法")
        if self.team_pool_disposition not in TEAM_POOL_DISPOSITIONS:
            raise ValueError("团队窗口成员人物池处置非法")
        if self.window_risk_exposure not in WINDOW_RISK_EXPOSURE_STATES:
            raise ValueError("团队窗口成员风险暴露状态非法")
        if not self.membership_evidence_refs:
            raise ValueError("团队窗口成员适用性缺少履职证据")
        if self.relationship_origin == "passive_holdover" and (
            self.team_pool_disposition != "excluded_passive_holdover"
        ):
            raise ValueError("被动留任不得进入团队人物池")
        if self.team_pool_disposition == "included" and (
            self.substantive_role_status != "confirmed"
            or self.relationship_origin == "passive_holdover"
        ):
            raise ValueError("进入团队人物池必须确认实质履职且非被动留任")
        if self.window_risk_exposure == "exposed_in_window" and not (
            self.risk_exposure_evidence_refs
        ):
            raise ValueError("窗口内风险暴露必须有独立证据")
        if self.review_status != "human_frozen":
            raise ValueError("团队窗口成员适用性必须人工冻结")


@dataclass(frozen=True, slots=True)
class RulerTeamWindowSnapshot:
    window_ref: str
    ruler_ref: str
    start: str
    end: str
    date_precision: str
    window_policy_version: str
    roster_version: str
    profile_snapshot_version: str
    members: tuple[RulerTeamWindowMember, ...]
    lineage: Mapping[str, str]
    status: str = "human_frozen"

    def __post_init__(self) -> None:
        if not all(
            (
                self.window_ref,
                self.ruler_ref,
                self.start,
                self.end,
                self.window_policy_version,
                self.roster_version,
                self.profile_snapshot_version,
            )
        ):
            raise ValueError("RulerTeamWindowSnapshot 缺少窗口身份或版本")
        if self.date_precision not in {"day", "month", "year", "reign_year"}:
            raise ValueError("RulerTeamWindowSnapshot 时间精度非法")
        people = [item.person_ref for item in self.members]
        if not people or len(set(people)) != len(people):
            raise ValueError("同一团队窗口内人物必须完整且唯一")
        if self.status != "human_frozen":
            raise ValueError("RulerTeamWindowSnapshot 必须先经人工冻结")
