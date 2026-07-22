from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence


SCALES = ("local", "important", "regional", "national", "era_shaping")
CAMPAIGN_TIERS = ("C", "B", "A", "S-", "S", "S+")
MILITARY_STRATEGIC_WEIGHTS = {"C": 0, "B": 0, "A": 1, "S-": 2, "S": 3, "S+": 4}
LEGACY_CAMPAIGN_TIER_BY_SCALE = {
    "local": "C",
    "important": "B",
    "regional": "A",
    "national": "S",
    "era_shaping": "S+",
}
MILITARY_RESPONSIBILITY_ROLES = (
    "commander_in_chief",
    "principal_commander",
    "participant",
)
CIVIL_RESPONSIBILITY_ROLES = ("exclusive", "lead", "participant")
COUNTED_MILITARY_ROLES = {"commander_in_chief", "principal_commander"}
COUNTED_CIVIL_ROLES = {"exclusive", "lead"}
POSITIVE_RESULTS = {"implemented_positive", "completed_positive"}
NATIONAL_CONSEQUENCES = {
    "national_war_outcome",
    "state_survival",
    "unification",
    "state_conquest",
    "era_order_reconstruction",
}


def _eligible_achievements(
    domain: str,
    achievements: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    seen: set[str] = set()
    eligible = []
    for row in achievements:
        independent_key = str(row.get("independent_key") or "").strip()
        scale = str(row.get("scale") or "")
        responsibility_role = str(row.get("responsibility_role") or "")
        result = str(row.get("result") or "")
        if not independent_key:
            raise ValueError("成就缺少 independent_key")
        campaign_tier = str(row.get("campaign_tier") or "")
        if domain == "military":
            if not campaign_tier:
                if scale not in SCALES:
                    raise ValueError("军事成就缺少 campaign_tier")
                campaign_tier = LEGACY_CAMPAIGN_TIER_BY_SCALE[scale]
            if campaign_tier not in CAMPAIGN_TIERS:
                raise ValueError("军事成就 campaign_tier 不在当前合同")
        elif scale not in SCALES:
            raise ValueError("成就 scale 不在当前合同")
        allowed_roles = (
            MILITARY_RESPONSIBILITY_ROLES
            if domain == "military"
            else CIVIL_RESPONSIBILITY_ROLES
        )
        if responsibility_role not in allowed_roles:
            raise ValueError("成就 responsibility_role 不在当前领域合同")
        if independent_key in seen:
            raise ValueError("同一 independent_key 必须先合并为一个成就簇")
        seen.add(independent_key)
        positive_result = result in POSITIVE_RESULTS or (
            result == "implemented_mixed"
            and bool(row.get("positive_result_preserved"))
        )
        counted_roles = (
            COUNTED_MILITARY_ROLES if domain == "military" else COUNTED_CIVIL_ROLES
        )
        if responsibility_role in counted_roles and positive_result:
            eligible.append(
                {**row, "campaign_tier": campaign_tier}
                if domain == "military"
                else row
            )
    return eligible


def assess_domain_historic_path(
    domain: str, achievements: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """判定分领域 historic 事实路径是否闭合，不替代权威校准或人工冻结。"""

    domain = domain.strip()
    if domain not in {"military", "civil_governance", "culture_and_scholarship", "all_round"}:
        raise ValueError(f"未知人才领域：{domain}")
    responsibility_domain = "military" if domain == "military" else "civil_governance"
    eligible = _eligible_achievements(responsibility_domain, achievements)
    path = None
    matched_independent_keys: list[str] = []
    counts: dict[str, object]

    if domain == "military":
        tier_rank = {tier: index for index, tier in enumerate(CAMPAIGN_TIERS)}
        a_or_higher = [
            row
            for row in eligible
            if tier_rank[str(row["campaign_tier"])] >= tier_rank["A"]
        ]
        s_or_higher = [
            row
            for row in eligible
            if tier_rank[str(row["campaign_tier"])] >= tier_rank["S"]
        ]
        s_minus_or_higher = [
            row
            for row in eligible
            if tier_rank[str(row["campaign_tier"])] >= tier_rank["S-"]
        ]
        s_plus = [
            row for row in eligible if str(row["campaign_tier"]) == "S+"
        ]
        decisive_s_or_higher = [
            row
            for row in s_or_higher
            if bool(row.get("decisive"))
        ]
        order_key = lambda row: (
            -tier_rank[str(row["campaign_tier"])],
            str(row["independent_key"]),
        )
        if len(decisive_s_or_higher) >= 2:
            path = "military_peak_pair"
            matched_independent_keys = [
                str(row["independent_key"])
                for row in sorted(decisive_s_or_higher, key=order_key)[:2]
            ]
        else:
            decisive_s_plus = [row for row in s_plus if bool(row.get("decisive"))]
            if decisive_s_plus and len(a_or_higher) >= 2:
                path = "military_peak_pair"
                anchor = sorted(decisive_s_plus, key=order_key)[0]
                support = next(
                    row
                    for row in sorted(a_or_higher, key=order_key)
                    if row["independent_key"] != anchor["independent_key"]
                )
                matched_independent_keys = [
                    str(anchor["independent_key"]),
                    str(support["independent_key"]),
                ]
        strategic_weight = sum(
            MILITARY_STRATEGIC_WEIGHTS[str(row["campaign_tier"])]
            for row in a_or_higher
        )
        if (
            path is None
            and len(a_or_higher) >= 3
            and s_or_higher
            and strategic_weight >= 7
        ):
            path = "military_sustained_strategic_portfolio"
            matched_rows = sorted(a_or_higher, key=order_key)
            matched_independent_keys = [
                str(row["independent_key"]) for row in matched_rows
            ]
        counts = {
            "eligible_independent": len(eligible),
            "a_or_higher": len(a_or_higher),
            "s_minus_or_higher": len(s_minus_or_higher),
            "s_or_higher": len(s_or_higher),
            "s_plus": len(s_plus),
            "strategic_weight": strategic_weight,
            "tier_counts": dict(
                Counter(str(row["campaign_tier"]) for row in eligible)
            ),
        }
    elif domain == "civil_governance":
        scale_rank = {scale: index for index, scale in enumerate(SCALES)}
        national = [row for row in eligible if scale_rank[str(row["scale"])] >= scale_rank["national"]]
        regional = [row for row in eligible if scale_rank[str(row["scale"])] >= scale_rank["regional"]]
        exclusive_national = [
            row for row in national if row["responsibility_role"] == "exclusive"
        ]
        lead_national = [row for row in national if row["responsibility_role"] == "lead"]
        responsibility_ok = bool(exclusive_national) or len(lead_national) >= 2
        if len(national) >= 2 and len(regional) >= 3 and responsibility_ok:
            path = "civil_two_national_plus_one_regional"
        else:
            foundational = [
                row
                for row in national
                if bool(row.get("foundational"))
                and bool(row.get("durable_cross_stage"))
                and row["responsibility_role"] in COUNTED_CIVIL_ROLES
            ]
            for anchor in foundational:
                others = [
                    row for row in eligible if row["independent_key"] != anchor["independent_key"]
                ]
                other_national = [
                    row
                    for row in others
                    if scale_rank[str(row["scale"])] >= scale_rank["national"]
                ]
                other_regional = [
                    row
                    for row in others
                    if scale_rank[str(row["scale"])] >= scale_rank["regional"]
                ]
                if other_national or len(other_regional) >= 2:
                    path = "civil_foundational_system_plus_independent_results"
                    break
        counts = {
            "eligible_independent": len(eligible),
            "regional_or_higher": len(regional),
            "national_or_higher": len(national),
            "exclusive_national_or_higher": len(exclusive_national),
            "lead_national_or_higher": len(lead_national),
            "scale_counts": dict(Counter(str(row["scale"]) for row in eligible)),
        }
    elif domain == "culture_and_scholarship":
        scale_rank = {scale: index for index, scale in enumerate(SCALES)}
        national = [row for row in eligible if scale_rank[str(row["scale"])] >= scale_rank["national"]]
        foundational_work = [
            row
            for row in eligible
            if row["scale"] == "era_shaping"
            and bool(row.get("foundational"))
            and bool(row.get("durable_cross_stage"))
            and bool(row.get("personally_authored_or_finalized"))
        ]
        if foundational_work:
            path = "culture_civilization_foundational_single_work"
        elif len(national) >= 3:
            path = "culture_repeated_field_shaping"
        counts = {
            "eligible_independent": len(eligible),
            "national_or_higher": len(national),
            "scale_counts": dict(Counter(str(row["scale"]) for row in eligible)),
        }
    elif domain == "all_round":
        top_domains = {
            str(row.get("top_domain") or "")
            for row in eligible
            if bool(row.get("domain_top_level"))
        } - {""}
        if len(top_domains) >= 2:
            path = "all_round_multiple_independent_top_domains"
        counts = {
            "eligible_independent": len(eligible),
            "top_domain_count": len(top_domains),
        }
    return {
        "schema_version": "talent-grade-domain-equivalent-assessment-v1",
        "domain": domain,
        "historic_fact_path_status": "eligible" if path else "not_established",
        "matched_path": path,
        "matched_independent_keys": matched_independent_keys,
        "counts": counts,
        "authority_calibration_required": True,
        "formal_grade_write_allowed": False,
    }


def validate_campaign_registry(payload: Mapping[str, object]) -> dict[str, object]:
    """执行 JSON Schema 之外的战役身份、层级和人物归责不变量。"""

    if payload.get("schema_version") != "campaign-registry-v1":
        raise ValueError("战役登记表 schema_version 不正确")
    campaigns = payload.get("campaigns")
    if not isinstance(campaigns, list):
        raise ValueError("战役登记表 campaigns 必须是 array")
    campaign_refs: set[str] = set()
    independent_keys: set[str] = set()
    participant_count = 0
    for campaign in campaigns:
        if not isinstance(campaign, Mapping):
            raise ValueError("campaign 必须是 object")
        campaign_ref = str(campaign.get("campaign_ref") or "")
        independent_key = str(campaign.get("independent_campaign_key") or "")
        if not campaign_ref or campaign_ref in campaign_refs:
            raise ValueError("campaign_ref 缺失或重复")
        if not independent_key or independent_key in independent_keys:
            raise ValueError("独立战役链必须先合并，independent_campaign_key 不得重复")
        campaign_refs.add(campaign_ref)
        independent_keys.add(independent_key)
        scale = campaign.get("scale")
        if not isinstance(scale, Mapping) or scale.get("level") not in SCALES:
            raise ValueError("战役 scale 不正确")
        campaign_tier = str(campaign.get("campaign_tier") or "")
        if campaign_tier not in CAMPAIGN_TIERS:
            raise ValueError("战役 campaign_tier 不正确")
        strategic_result_class = str(campaign.get("strategic_result_class") or "")
        strategic_result_tier = {
            "local_tactical": "C",
            "important_objective": "B",
            "major_stage_or_crisis": "A",
            "independent_direction": "S-",
            "single_pole_or_state_terminal": "S",
            "composite_poles_terminal": "S+",
            "unification_terminal": "S+",
            "external_hegemony_terminal": "S+",
        }
        if strategic_result_tier.get(strategic_result_class) != campaign_tier:
            raise ValueError("战役战略结果类与 campaign_tier 不匹配")
        if campaign.get("combat_difficulty") not in {"D0", "D1", "D2", "D3"}:
            raise ValueError("战役 combat_difficulty 不正确")
        if not campaign.get("combat_difficulty_basis"):
            raise ValueError("战役必须说明 combat_difficulty_basis")
        if campaign.get("land_strategic_value") not in {
            "local_point",
            "important_region",
            "strategic_gateway",
            "core_heartland",
            "capital_or_state_survival",
        }:
            raise ValueError("战役 land_strategic_value 不正确")
        basis = str(scale.get("consequence_basis") or "")
        decisiveness = str(scale.get("decisiveness") or "")
        if decisiveness not in {"supporting", "major", "decisive"}:
            raise ValueError("战役 decisiveness 不正确")
        if campaign_tier in {"S", "S+"} and basis not in NATIONAL_CONSEQUENCES:
            raise ValueError("S级以上战役必须由统一、存亡、灭国或整场战争结果支持")
        if (
            campaign_tier in {"S", "S+"}
            and basis == "state_conquest"
            and scale.get("opponent_condition") == "residual"
        ):
            raise ValueError("击败残余政权不能仅凭灭国名义登记为S级以上")
        if (
            campaign_tier in {"S", "S+"}
            and basis == "state_conquest"
            and scale.get("opponent_strategic_weight")
            not in {"regional_major", "first_tier_pole", "dominant_pole", "external_state", "external_hegemony"}
        ):
            raise ValueError("S级以上灭国必须证明对手具有主要区域或更高战略分量")
        participants = campaign.get("participants")
        if not isinstance(participants, list) or not participants:
            raise ValueError("战役必须有参与人物")
        person_refs = [str(row.get("person_ref") or "") for row in participants]
        if "" in person_refs or len(person_refs) != len(set(person_refs)):
            raise ValueError("同一战役人物归责不得缺失或重复")
        command_roles = [str(row.get("command_role") or "") for row in participants]
        if any(role not in MILITARY_RESPONSIBILITY_ROLES for role in command_roles):
            raise ValueError("战役人物 command_role 不在主帅、主将、从攻合同")
        participant_count += len(participants)
        if not campaign.get("episode_refs") or not campaign.get("source_refs"):
            raise ValueError("战役必须引用中性 Episode 与史源")
    return {
        "schema_version": "campaign-registry-validation-v1",
        "status": "passed",
        "campaign_count": len(campaigns),
        "participant_count": participant_count,
        "formal_score_write_allowed": False,
    }
