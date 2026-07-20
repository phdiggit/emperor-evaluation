from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from emperor_v4.contracts.person_snapshot import (
    NEGATIVE_TALENT_SEVERITIES,
    POLITICAL_RISK_HISTORICAL_REACH,
    POLITICAL_RISK_SEVERITIES,
    PoliticalRiskAssessment,
    PoliticalRiskDiscoveryReceipt,
    PoliticalRiskEventAssessment,
    PoliticalRiskHitDisposition,
    PoliticalRiskRetrievalReceipt,
)


ROOT = Path(__file__).resolve().parents[1]


def _discovery_receipt(
    *, overview_status: str = "visible"
) -> PoliticalRiskDiscoveryReceipt:
    visible = overview_status == "visible"
    return PoliticalRiskDiscoveryReceipt(
        query="某将领 劣迹",
        channel="google_ai_overview_browser",
        overview_status=overview_status,
        lead_summaries=("发现一项待反查的一手史源线索。",) if visible else (),
        source_links=("https://example.com/source",) if visible else (),
    )


def _event() -> PoliticalRiskEventAssessment:
    return PoliticalRiskEventAssessment(
        event_ref="RISK-EVENT-001",
        domain="mass_violence",
        realization="realized",
        responsibility="command_responsibility",
        victim_scope="city_or_population",
        recurrence="single",
        duration="short",
        source_refs=("SRC-001",),
        evidence_summary="史源明确记录事件。",
        semantic_analysis="地点词结合受害对象和结果链判断。",
    )


def _included_hit() -> PoliticalRiskHitDisposition:
    return PoliticalRiskHitDisposition(
        hit_ref="HIT-001",
        source_ref="SRC-001",
        source_url="https://zh.wikisource.org/example",
        source_locator="卷一某段",
        quote="明确记载已实现的群体伤害。",
        source_period="唐",
        genre="正史列传",
        subject="某将领",
        object_text="城中军民",
        object_type="city_or_population",
        polarity="affirmative",
        modality="asserted",
        event_phase="realized",
        semantic_reading="mass_harm",
        responsibility="command_responsibility",
        disposition="included",
        reason_codes=("DIRECT_EVENT_EVIDENCE", "RESPONSIBILITY_EXPLICIT"),
    )


def _below_floor_hit() -> PoliticalRiskHitDisposition:
    return PoliticalRiskHitDisposition(
        hit_ref="HIT-BELOW-FLOOR-001",
        source_ref="SRC-001",
        source_url="https://zh.wikisource.org/example",
        source_locator="卷一某段",
        quote="单次少量私取，未见强制侵夺或公共损害。",
        source_period="唐",
        genre="正史列传",
        subject="某官员",
        object_text="少量私物",
        object_type="private_property",
        polarity="affirmative",
        modality="asserted",
        event_phase="realized",
        semantic_reading="property_destruction",
        responsibility="direct_execution",
        disposition="excluded",
        reason_codes=("BELOW_POLITICAL_MATERIALITY_FLOOR",),
    )


def _receipts(
    *,
    coverage_status: str = "complete",
    include_mass_hit: bool = False,
    include_below_floor_hit: bool = False,
) -> tuple[PoliticalRiskRetrievalReceipt, ...]:
    domains = (
        "mass_violence",
        "unlawful_repression",
        "power_abuse",
        "corruption_extraction",
        "factional_capture",
        "state_subversion",
        "military_command_harm",
        "governance_harm",
    )
    def hit_for(domain: str) -> PoliticalRiskHitDisposition | None:
        if domain != "mass_violence":
            return None
        if include_mass_hit:
            return _included_hit()
        if include_below_floor_hit:
            return _below_floor_hit()
        return None

    return tuple(
        PoliticalRiskRetrievalReceipt(
            domain=domain,
            applicability="applicable",
            queries=(f"person+{domain}",),
            sources_scanned=("SRC-BIOGRAPHY",),
            hit_refs=(hit.hit_ref,) if (hit := hit_for(domain)) else (),
            included_hit_refs=(hit.hit_ref,) if hit and hit.disposition == "included" else (),
            excluded_hit_refs=(hit.hit_ref,) if hit and hit.disposition == "excluded" else (),
            unresolved_hit_refs=(),
            hit_dispositions=(hit,) if hit else (),
            coverage_status=coverage_status,
        )
        for domain in domains
    )


def test_political_risk_policy_fails_closed_on_missing_material() -> None:
    assessment = PoliticalRiskAssessment(
        task_code="POLRISK-V3-PER-V4-000000000001",
        person_ref="PER-V4-000000000001",
        input_version="profile-v1",
        policy_version="political-risk-v3",
        assessment_status="insufficient_evidence",
        risk_domains=(),
        severity=None,
        historical_reach=None,
        discovery_receipt=_discovery_receipt(overview_status="unavailable"),
        event_assessments=(),
        retrieval_receipts=_receipts(coverage_status="partial"),
        source_refs=(),
        counterevidence_refs=(),
        confidence=0.0,
        semantic_notes={"term_review": "八域检索未完成，失败关闭。"},
    )

    assert assessment.assessment_status == "insufficient_evidence"


def test_fast_risk_shadow_allows_only_the_candidate_domain_receipt() -> None:
    assessment = PoliticalRiskAssessment(
        task_code="POLRISK-V3-PER-V4-000000000001",
        person_ref="PER-V4-000000000001",
        input_version="profile-v1",
        policy_version="political-risk-v3",
        assessment_status="insufficient_evidence",
        risk_domains=(),
        severity=None,
        historical_reach=None,
        discovery_receipt=_discovery_receipt(),
        event_assessments=(),
        retrieval_receipts=(_receipts(coverage_status="partial")[0],),
        source_refs=("SRC-001",),
        counterevidence_refs=(),
        confidence=0.4,
        semantic_notes={"term_review": "仅候选域回源，责任仍未确立。"},
    )

    assert assessment.assessment_status == "insufficient_evidence"


def test_political_risk_discovery_receipt_accepts_structured_risk_prompt() -> None:
    receipt = PoliticalRiskDiscoveryReceipt(
        query="为项目宽搜李靖的政治风险与重大军事败绩线索。",
        channel="google_ai_overview_browser",
        overview_status="visible",
        lead_summaries=("军纪争议待回源。",),
        source_links=("https://zh.wikisource.org/wiki/舊唐書/卷67",),
    )

    assert receipt.query.startswith("为项目宽搜")


def test_established_political_risk_requires_event_and_source() -> None:
    with pytest.raises(ValueError, match="缺少风险域、严重度、历史影响范围、事件或史源"):
        PoliticalRiskAssessment(
            task_code="POLRISK-V3-PER-V4-000000000001",
            person_ref="PER-V4-000000000001",
            input_version="profile-v1",
            policy_version="political-risk-v3",
            assessment_status="established",
            risk_domains=("mass_violence",),
            severity="major",
            historical_reach="regional",
            discovery_receipt=_discovery_receipt(),
            event_assessments=(),
            retrieval_receipts=_receipts(),
            source_refs=(),
            counterevidence_refs=(),
            confidence=0.8,
            semantic_notes={"term_review": "存在已实现且语义明确的命中。"},
        )


def test_established_mass_violence_assessment_is_structured() -> None:
    assessment = PoliticalRiskAssessment(
        task_code="POLRISK-V3-PER-V4-000000000001",
        person_ref="PER-V4-000000000001",
        input_version="profile-v1",
        policy_version="political-risk-v3",
        assessment_status="established",
        risk_domains=("mass_violence",),
        severity="major",
        historical_reach="regional",
        discovery_receipt=_discovery_receipt(),
        event_assessments=(_event(),),
        retrieval_receipts=_receipts(include_mass_hit=True),
        source_refs=("SRC-001",),
        counterevidence_refs=(),
        confidence=0.9,
        semantic_notes={"term_review": "已结合宾语和事件结果判定。"},
    )

    assert assessment.event_assessments[0].victim_scope == "city_or_population"


def test_established_event_may_keep_unrelated_search_domains_partial() -> None:
    assessment = PoliticalRiskAssessment(
        task_code="POLRISK-V3-PER-V4-000000000001",
        person_ref="PER-V4-000000000001",
        input_version="profile-v1",
        policy_version="political-risk-v3",
        assessment_status="established",
        risk_domains=("mass_violence",),
        severity="major",
        historical_reach="regional",
        discovery_receipt=_discovery_receipt(),
        event_assessments=(_event(),),
        retrieval_receipts=_receipts(coverage_status="partial", include_mass_hit=True),
        source_refs=("SRC-001",),
        counterevidence_refs=(),
        confidence=0.7,
        semantic_notes={"term_review": "已确立事件不因无关域未完而被抹除。"},
    )

    assert assessment.assessment_status == "established"


def test_established_event_needs_only_its_candidate_domain_receipt() -> None:
    assessment = PoliticalRiskAssessment(
        task_code="POLRISK-V3-PER-V4-000000000001",
        person_ref="PER-V4-000000000001",
        input_version="profile-v1",
        policy_version="political-risk-v3",
        assessment_status="established",
        risk_domains=("mass_violence",),
        severity="major",
        historical_reach="regional",
        discovery_receipt=_discovery_receipt(),
        event_assessments=(_event(),),
        retrieval_receipts=(_receipts(include_mass_hit=True)[0],),
        source_refs=("SRC-001",),
        counterevidence_refs=(),
        confidence=0.7,
        semantic_notes={"term_review": "候选域命中已完成一手史源与上下文核验。"},
    )

    assert assessment.assessment_status == "established"


def test_reviewed_no_material_risk_requires_source_coverage() -> None:
    with pytest.raises(ValueError, match="必须有完整检索史源"):
        PoliticalRiskAssessment(
            task_code="POLRISK-V3-PER-V4-000000000001",
            person_ref="PER-V4-000000000001",
            input_version="profile-v1",
            policy_version="political-risk-v3",
            assessment_status="reviewed_no_material_risk",
            risk_domains=(),
            severity=None,
            historical_reach=None,
            discovery_receipt=_discovery_receipt(),
            event_assessments=(),
            retrieval_receipts=_receipts(),
            source_refs=(),
            counterevidence_refs=(),
            confidence=0.8,
            semantic_notes={"term_review": "八域完整且无未解决命中。"},
        )


def test_political_risk_policy_remains_shadow_and_talent_orthogonal() -> None:
    policy = yaml.safe_load((ROOT / "config" / "political-risk.yml").read_text(encoding="utf-8"))

    assert policy["runtime_policy"] == {
        "mode": "offline_report_only_shadow",
        "model_may_publish_formal_assessment": False,
        "database_writes_allowed": False,
        "talent_grade_mutation_allowed": False,
        "formal_scoring_allowed": False,
        "ranking_allowed": False,
    }
    assert policy["schema_version"] == "political-risk-v4"
    assert set(policy["severity_policy"]["severity_values"]) == POLITICAL_RISK_SEVERITIES
    assert (
        set(policy["severity_policy"]["historical_reach_values"])
        == POLITICAL_RISK_HISTORICAL_REACH
    )
    assert NEGATIVE_TALENT_SEVERITIES == {"minor", "material", "major", "historic"}
    assert "mass_violence" in policy["risk_domains"]
    assert "military_command_harm" in policy["risk_domains"]
    assert policy["evidence_gate"]["absence_may_not_be_inferred_from_missing_material"] is True
    assert policy["evidence_gate"]["local_source_inventory_lookup_required_before_web_discovery"] is True
    assert policy["severity_policy"]["political_materiality_floor"]["hard_rules"]
    regressions = {item["case"]: item for item in policy["calibration_regressions"]}
    assert regressions["tang_jian_private_sheep"]["expected"] == "excluded_below_political_materiality_floor"
    assert regressions["huo_qubing_kills_li_gan"]["expected_minimum"] == "material"
    assert regressions["xiao_yu_punishment_causes_death"]["expected_minimum"] == "material"
    assert regressions["zhu_shuang_repeated_abuse"]["expected_minimum"] == "major"
    assert set(policy["retrieval_protocol"]["domain_query_matrix"]) == {
        "mass_violence",
        "unlawful_repression",
        "power_abuse",
        "corruption_extraction",
        "factional_capture",
        "state_subversion",
        "military_command_harm",
        "governance_harm",
    }
    assert policy["retrieval_protocol"]["no_risk_gate"]["all_applicable_domains_complete"] is True
    assert policy["retrieval_protocol"]["shadow_fast_path"]["no_risk_conclusion_forbidden"] is True
    assert policy["retrieval_protocol"]["no_risk_exhaustive_path"]["applies_to"] == [
        "reviewed_no_material_risk"
    ]
    slaughter_rules = policy["retrieval_protocol"]["semantic_adjudication"]["hard_rules"]
    assert any("最高暂定serious" in rule for rule in slaughter_rules)
    assert any("人名断句" in rule for rule in slaughter_rules)
    assert any("不得单独作为未发生屠杀的反证" in rule for rule in slaughter_rules)


def test_ambiguous_location_object_hit_cannot_be_included() -> None:
    with pytest.raises(ValueError, match="歧义、未实现或非肯定命中"):
        PoliticalRiskHitDisposition(
            hit_ref="HIT-001",
            source_ref="SRC-001",
            source_url="https://zh.wikisource.org/example",
            source_locator="卷一某段",
            quote="屠城下邑",
            source_period="唐",
            genre="诏令",
            subject="军队",
            object_text="城下邑",
            object_type="city_or_territory",
            polarity="affirmative",
            modality="asserted",
            event_phase="realized",
            semantic_reading="ambiguous",
            responsibility="attributed",
            disposition="included",
            reason_codes=("LOCATION_OBJECT_POLYSEMY",),
        )


def test_non_established_result_cannot_hide_included_hits() -> None:
    with pytest.raises(ValueError, match="已有纳入命中的任务不得降为"):
        PoliticalRiskAssessment(
            task_code="POLRISK-V3-PER-V4-000000000001",
            person_ref="PER-V4-000000000001",
            input_version="profile-v1",
            policy_version="political-risk-v3",
            assessment_status="insufficient_evidence",
            risk_domains=(),
            severity=None,
            historical_reach=None,
            discovery_receipt=_discovery_receipt(),
            event_assessments=(),
            retrieval_receipts=_receipts(include_mass_hit=True),
            source_refs=("SRC-001",),
            counterevidence_refs=(),
            confidence=0.5,
            semantic_notes={"term_review": "局部坏项不能清空其他有效事件。"},
        )


def test_below_floor_is_an_exclusion_status_not_a_severity() -> None:
    assessment = PoliticalRiskAssessment(
        task_code="POLRISK-V3-PER-V4-000000000001",
        person_ref="PER-V4-000000000001",
        input_version="profile-v1",
        policy_version="political-risk-v3",
        assessment_status="below_floor",
        risk_domains=(),
        severity=None,
        historical_reach=None,
        discovery_receipt=_discovery_receipt(),
        event_assessments=(),
        retrieval_receipts=_receipts(include_below_floor_hit=True),
        source_refs=("SRC-001",),
        counterevidence_refs=(),
        confidence=0.9,
        semantic_notes={"materiality_review": "命中已审定低于政治风险门槛。"},
    )

    assert assessment.assessment_status == "below_floor"
    assert "below_floor" not in POLITICAL_RISK_SEVERITIES


def test_visible_ai_overview_requires_leads_and_source_links() -> None:
    with pytest.raises(ValueError, match="必须保存线索与来源链接"):
        PoliticalRiskDiscoveryReceipt(
            query="年羹尧 劣迹",
            channel="google_ai_overview_browser",
            overview_status="visible",
            lead_summaries=(),
            source_links=(),
        )


@pytest.mark.parametrize("overview_status", ["unavailable", "blocked"])
def test_ai_overview_absence_is_recorded_not_coerced_to_zero_hit(
    overview_status: str,
) -> None:
    receipt = _discovery_receipt(overview_status=overview_status)

    assert receipt.overview_status == overview_status
    assert receipt.lead_summaries == ()
    assert receipt.source_links == ()
