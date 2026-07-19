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
POLITICAL_RISK_STATUSES = {
    "established",
    "below_floor",
    "reviewed_no_material_risk",
    "insufficient_evidence",
}
POLITICAL_RISK_SEVERITIES = {
    "limited",
    "material",
    "serious",
    "major",
    "systemic",
}
POLITICAL_RISK_HISTORICAL_REACH = {
    "bounded",
    "regional",
    "national",
    "era_shaping",
}
POLITICAL_RISK_DISCOVERY_CHANNEL = "google_ai_overview_browser"
POLITICAL_RISK_OVERVIEW_STATUSES = {"visible", "unavailable", "blocked"}
POLITICAL_RISK_DOMAINS = {
    "mass_violence",
    "unlawful_repression",
    "power_abuse",
    "corruption_extraction",
    "factional_capture",
    "state_subversion",
    "military_command_harm",
    "governance_harm",
    "mixed_or_disputed",
}
POLITICAL_RISK_REALIZATION = {"alleged", "attempted", "realized"}
POLITICAL_RISK_RESPONSIBILITY = {
    "direct_order",
    "direct_execution",
    "command_responsibility",
    "policy_design",
    "enabling",
    "failed_to_prevent",
    "attributed",
    "disputed",
}
POLITICAL_RISK_VICTIM_SCOPE = {
    "individual",
    "bounded_group",
    "city_or_population",
    "multi_region",
    "state_system",
}
POLITICAL_RISK_RECURRENCE = {"single", "repeated", "systematic"}
POLITICAL_RISK_DURATION = {"short", "multi_year", "institutional", "era_shaping"}
POLITICAL_RISK_SEARCH_DOMAINS = POLITICAL_RISK_DOMAINS - {"mixed_or_disputed"}
POLITICAL_RISK_COVERAGE = {"complete", "partial"}
POLITICAL_RISK_HIT_READINGS = {
    "mass_harm",
    "city_capture_or_destruction",
    "combat_killing",
    "punitive_execution",
    "property_destruction",
    "figurative",
    "ambiguous",
    "not_applicable",
}
POLITICAL_RISK_HIT_DISPOSITIONS = {"included", "excluded", "unresolved"}
POLITICAL_RISK_HIT_POLARITIES = {"affirmative", "negated", "prohibited", "prevented"}
POLITICAL_RISK_HIT_MODALITIES = {
    "asserted",
    "proposed",
    "threatened",
    "predicted",
    "conditional",
    "disputed",
}
POLITICAL_RISK_HIT_PHASES = {
    "proposed",
    "ordered",
    "attempted",
    "realized",
    "prevented",
    "unclear",
}


@dataclass(frozen=True, slots=True)
class PoliticalRiskHitDisposition:
    hit_ref: str
    source_ref: str
    source_url: str
    source_locator: str
    quote: str
    source_period: str
    genre: str
    subject: str
    object_text: str
    object_type: str
    polarity: str
    modality: str
    event_phase: str
    semantic_reading: str
    responsibility: str
    disposition: str
    reason_codes: tuple[str, ...]
    corroboration_refs: tuple[str, ...] = ()
    conflict_notes: str = ""

    def __post_init__(self) -> None:
        if not all(
            (
                self.hit_ref,
                self.source_ref,
                self.source_url,
                self.source_locator,
                self.quote,
                self.source_period,
                self.genre,
                self.subject,
                self.object_text,
                self.object_type,
            )
        ):
            raise ValueError("政治风险命中缺少原文定位或句法上下文")
        if not self.source_url.startswith(("https://", "http://")):
            raise ValueError("政治风险命中缺少可访问史源 URL")
        checks = (
            (self.polarity, POLITICAL_RISK_HIT_POLARITIES, "极性"),
            (self.modality, POLITICAL_RISK_HIT_MODALITIES, "情态"),
            (self.event_phase, POLITICAL_RISK_HIT_PHASES, "事件阶段"),
            (self.semantic_reading, POLITICAL_RISK_HIT_READINGS, "语义"),
            (self.responsibility, POLITICAL_RISK_RESPONSIBILITY, "责任"),
            (self.disposition, POLITICAL_RISK_HIT_DISPOSITIONS, "处置"),
        )
        for value, allowed, label in checks:
            if value not in allowed:
                raise ValueError(f"政治风险命中{label}非法")
        if not self.reason_codes:
            raise ValueError("政治风险命中缺少可审计处置理由")
        if self.disposition == "included" and (
            self.semantic_reading == "ambiguous"
            or self.event_phase not in {"attempted", "realized"}
            or self.polarity != "affirmative"
            or self.modality != "asserted"
        ):
            raise ValueError("歧义、未实现或非肯定命中不得纳入风险事件")
        if self.disposition == "included" and any(
            code.endswith("_UNRESOLVED") or code == "CONFLICTING_SOURCES"
            for code in self.reason_codes
        ):
            raise ValueError("已纳入命中不得保留未解决理由")


@dataclass(frozen=True, slots=True)
class PoliticalRiskRetrievalReceipt:
    domain: str
    applicability: str
    queries: tuple[str, ...]
    sources_scanned: tuple[str, ...]
    hit_refs: tuple[str, ...]
    included_hit_refs: tuple[str, ...]
    excluded_hit_refs: tuple[str, ...]
    unresolved_hit_refs: tuple[str, ...]
    hit_dispositions: tuple[PoliticalRiskHitDisposition, ...]
    coverage_status: str

    def __post_init__(self) -> None:
        if self.domain not in POLITICAL_RISK_SEARCH_DOMAINS:
            raise ValueError("政治风险检索域非法")
        if self.applicability != "applicable":
            raise ValueError("全员政治风险重审不得跳过查询域")
        if self.coverage_status not in POLITICAL_RISK_COVERAGE:
            raise ValueError("政治风险检索覆盖状态非法")
        if not self.queries or not self.sources_scanned:
            raise ValueError("适用风险域缺少查询或已检索史源")
        disposition_refs = {item.hit_ref for item in self.hit_dispositions}
        if disposition_refs != set(self.hit_refs):
            raise ValueError("政治风险命中回执与处置明细不一致")
        expected = {
            "included": set(self.included_hit_refs),
            "excluded": set(self.excluded_hit_refs),
            "unresolved": set(self.unresolved_hit_refs),
        }
        if set().union(*expected.values()) != set(self.hit_refs):
            raise ValueError("政治风险命中分类未完整覆盖全部命中")
        if sum(len(refs) for refs in expected.values()) != len(set(self.hit_refs)):
            raise ValueError("政治风险命中被重复分类")
        for disposition, refs in expected.items():
            if {
                item.hit_ref
                for item in self.hit_dispositions
                if item.disposition == disposition
            } != refs:
                raise ValueError("政治风险命中处置分类不一致")


@dataclass(frozen=True, slots=True)
class PoliticalRiskDiscoveryReceipt:
    query: str
    channel: str
    overview_status: str
    lead_summaries: tuple[str, ...]
    source_links: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.query.strip() or not any(
            marker in self.query for marker in ("政治风险", "劣迹", "败绩")
        ):
            raise ValueError("政治风险宽发现查询缺少风险或败绩焦点")
        if self.channel != POLITICAL_RISK_DISCOVERY_CHANNEL:
            raise ValueError("政治风险宽发现渠道非法")
        if self.overview_status not in POLITICAL_RISK_OVERVIEW_STATUSES:
            raise ValueError("政治风险 AI 概览状态非法")
        if any(not item.strip() for item in self.lead_summaries):
            raise ValueError("政治风险 AI 概览线索不得为空")
        if any(
            not item.startswith(("https://", "http://")) for item in self.source_links
        ):
            raise ValueError("政治风险 AI 概览来源链接非法")
        if self.overview_status == "visible" and (
            not self.lead_summaries or not self.source_links
        ):
            raise ValueError("可见 AI 概览必须保存线索与来源链接")


@dataclass(frozen=True, slots=True)
class PoliticalRiskEventAssessment:
    event_ref: str
    domain: str
    realization: str
    responsibility: str
    victim_scope: str
    recurrence: str
    duration: str
    source_refs: tuple[str, ...]
    evidence_summary: str
    semantic_analysis: str

    def __post_init__(self) -> None:
        if (
            not self.event_ref
            or self.domain not in POLITICAL_RISK_DOMAINS
            or not self.source_refs
            or not self.evidence_summary
            or not self.semantic_analysis
        ):
            raise ValueError("政治风险事件缺少稳定身份或史源")
        checks = (
            (self.realization, POLITICAL_RISK_REALIZATION, "实现状态"),
            (self.responsibility, POLITICAL_RISK_RESPONSIBILITY, "责任"),
            (self.victim_scope, POLITICAL_RISK_VICTIM_SCOPE, "受害范围"),
            (self.recurrence, POLITICAL_RISK_RECURRENCE, "重复性"),
            (self.duration, POLITICAL_RISK_DURATION, "持续性"),
        )
        for value, allowed, label in checks:
            if value not in allowed:
                raise ValueError(f"政治风险事件{label}非法")


@dataclass(frozen=True, slots=True)
class PoliticalRiskAssessment:
    task_code: str
    person_ref: str
    input_version: str
    policy_version: str
    assessment_status: str
    risk_domains: tuple[str, ...]
    severity: str | None
    historical_reach: str | None
    discovery_receipt: PoliticalRiskDiscoveryReceipt
    event_assessments: tuple[PoliticalRiskEventAssessment, ...]
    retrieval_receipts: tuple[PoliticalRiskRetrievalReceipt, ...]
    source_refs: tuple[str, ...]
    counterevidence_refs: tuple[str, ...]
    confidence: float
    semantic_notes: Mapping[str, str]
    review_status: str = "shadow_candidate"

    def __post_init__(self) -> None:
        if not all((self.task_code, self.person_ref, self.input_version, self.policy_version)):
            raise ValueError("政治风险评估缺少稳定任务或输入版本")
        if not isinstance(self.discovery_receipt, PoliticalRiskDiscoveryReceipt):
            raise ValueError("政治风险评估缺少真实宽发现回执")
        if self.assessment_status not in POLITICAL_RISK_STATUSES:
            raise ValueError("政治风险评估状态非法")
        if not 0 <= self.confidence <= 1:
            raise ValueError("政治风险评估置信度非法")
        if self.review_status not in {"shadow_candidate", "human_accepted"}:
            raise ValueError("政治风险评估复核状态非法")
        if not self.semantic_notes or any(
            not str(key).strip() or not str(value).strip()
            for key, value in self.semantic_notes.items()
        ):
            raise ValueError("政治风险评估缺少结构化语义说明")
        if len(set(self.risk_domains)) != len(self.risk_domains) or any(
            item not in POLITICAL_RISK_DOMAINS for item in self.risk_domains
        ):
            raise ValueError("政治风险域非法或重复")
        receipt_domains = [item.domain for item in self.retrieval_receipts]
        if len(set(receipt_domains)) != len(receipt_domains):
            raise ValueError("同一政治风险检索域回执重复")
        receipt_domain_set = set(receipt_domains)
        if not receipt_domain_set.issubset(POLITICAL_RISK_SEARCH_DOMAINS):
            raise ValueError("政治风险评估查询域非法")
        if self.assessment_status == "reviewed_no_material_risk" and (
            receipt_domain_set != POLITICAL_RISK_SEARCH_DOMAINS
        ):
            raise ValueError("已审无实质风险必须覆盖全部查询域")
        included_hit_refs = {
            hit_ref
            for receipt in self.retrieval_receipts
            for hit_ref in receipt.included_hit_refs
        }
        if self.assessment_status == "established":
            if (
                not self.risk_domains
                or self.severity not in POLITICAL_RISK_SEVERITIES
                or self.historical_reach not in POLITICAL_RISK_HISTORICAL_REACH
                or not self.event_assessments
                or not self.source_refs
            ):
                raise ValueError(
                    "已确立政治风险缺少风险域、严重度、历史影响范围、事件或史源"
                )
            if not included_hit_refs:
                raise ValueError("已确立政治风险必须有已纳入命中")
            if not receipt_domain_set:
                raise ValueError("已确立政治风险必须有候选域检索回执")
            event_domains = {item.domain for item in self.event_assessments}
            if event_domains != set(self.risk_domains):
                raise ValueError("政治风险事件域与结论风险域不一致")
            if any(
                item.realization not in {"attempted", "realized"}
                for item in self.event_assessments
            ):
                raise ValueError("已确立政治风险不得包含指控性伪事件")
            if any(
                source_ref not in self.source_refs
                for item in self.event_assessments
                for source_ref in item.source_refs
            ):
                raise ValueError("政治风险事件史源未进入评估 lineage")
        elif (
            self.risk_domains
            or self.severity is not None
            or self.historical_reach is not None
            or self.event_assessments
        ):
            raise ValueError(
                "未确立政治风险不得携带风险域、严重度、历史影响范围或风险事件"
            )
        elif included_hit_refs:
            raise ValueError("已有纳入命中的任务不得降为无风险或证据不足")
        if self.assessment_status == "below_floor":
            below_floor_hits = {
                item.hit_ref
                for receipt in self.retrieval_receipts
                for item in receipt.hit_dispositions
                if item.disposition == "excluded"
                and "BELOW_POLITICAL_MATERIALITY_FLOOR" in item.reason_codes
            }
            if not below_floor_hits or not self.source_refs:
                raise ValueError("低于政治风险门槛必须有排除命中与史源")
        if self.assessment_status == "reviewed_no_material_risk" and not self.source_refs:
            raise ValueError("已审无实质风险必须有完整检索史源")
        if self.assessment_status == "reviewed_no_material_risk" and any(
            item.coverage_status == "partial" or item.unresolved_hit_refs
            for item in self.retrieval_receipts
        ):
            raise ValueError("终局政治风险判断不得存在部分覆盖或未解决命中")


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
