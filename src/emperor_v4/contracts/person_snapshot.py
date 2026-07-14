from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


TALENT_GRADES = {"historic", "top", "important", "usable", "ordinary"}
RISK_CLASSES = {"none", "political", "integrity", "security", "mixed"}


@dataclass(frozen=True, slots=True)
class PersonProfileSnapshot:
    profile_ref: str
    canonical_person_ref: str
    snapshot_version: str
    talent_grade: str
    capability_domains: tuple[str, ...]
    negative_risk_class: str
    negative_risk_severity: str
    lineage_refs: tuple[str, ...]
    semantic_fingerprint: str
    review_status: str = "human_frozen"

    def __post_init__(self) -> None:
        if not all(
            (
                self.profile_ref,
                self.canonical_person_ref,
                self.snapshot_version,
                self.semantic_fingerprint,
            )
        ):
            raise ValueError("PersonProfileSnapshot 缺少稳定身份或版本")
        if self.talent_grade not in TALENT_GRADES:
            raise ValueError("PersonProfileSnapshot talent_grade 非法")
        if self.negative_risk_class not in RISK_CLASSES:
            raise ValueError("PersonProfileSnapshot negative_risk_class 非法")
        if not self.capability_domains or not self.lineage_refs:
            raise ValueError("PersonProfileSnapshot 缺少能力域或 lineage")
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
