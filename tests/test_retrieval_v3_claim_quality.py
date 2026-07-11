from __future__ import annotations

from scripts.dev import retrieval_v3_claim_quality as tool


def test_slice_claim_eligibility_keeps_action_near_object_claimable() -> None:
    row = {
        "object_name": "李世民",
        "matched_aliases": ["秦王"],
        "source_shape": "object_biography_candidate",
        "section_heading": "尉迟敬德",
        "text": "高祖命秦王为西讨元帅，诸将皆受节制。",
    }

    eligibility = tool.slice_claim_eligibility(row)

    assert "wrong_person_section_risk" in eligibility["risk_flags"]
    assert eligibility["claim_eligible"] is True
    assert eligibility["mention_role"] == "primary"
    assert eligibility["near_object_anchors"]["action"] is True


def test_slice_claim_eligibility_rejects_incidental_wrong_section_mentions() -> None:
    row = {
        "object_name": "李文忠",
        "matched_aliases": ["李文忠"],
        "source_shape": "object_biography_candidate",
        "section_heading": "邓愈",
        "text": "愈为人简重慎密，诸将早贵未有如愈与李文忠者。",
    }

    eligibility = tool.slice_claim_eligibility(row)

    assert eligibility["claim_eligible"] is False
    assert eligibility["support_level_hint"] == "context"
    assert eligibility["reasons"] == ["wrong_person_section_risk", "no_action_or_outcome_near_object"]


def test_slice_claim_eligibility_allows_given_name_subheading_in_group_biography() -> None:
    right_section = {
        "object_name": "李孝恭",
        "matched_aliases": ["河间王"],
        "source_shape": "object_biography_candidate",
        "section_heading": "孝恭",
        "text": "河间王孝恭从平萧铣，拜荆州大总管，威惠著于江汉。",
    }
    wrong_section = {
        **right_section,
        "section_heading": "道宗",
        "text": "道宗从征高丽，道宗请罪，太宗舍而不问。旁及河间王旧事。",
    }

    right = tool.slice_claim_eligibility(right_section)
    wrong = tool.slice_claim_eligibility(wrong_section)

    assert "wrong_person_section_risk" not in right["risk_flags"]
    assert right["claim_eligible"] is True
    assert "wrong_person_section_risk" in wrong["risk_flags"]


def test_slice_claim_eligibility_allows_biography_heading_short_name_context() -> None:
    row = {
        "object_name": "宋濂",
        "matched_aliases": ["宋景濂"],
        "source_shape": "object_biography_candidate",
        "section_heading": "宋濂",
        "text": "帝得舆图一卷，令濂询访，随处言之。翼日，问濂昨饮酒否，濂具以实对。",
    }
    wrong_section = {**row, "section_heading": "刘基"}

    eligibility = tool.slice_claim_eligibility(row)
    wrong = tool.slice_claim_eligibility(wrong_section)

    assert eligibility["claim_eligible"] is True
    assert eligibility["mention_role"] == "primary"
    assert eligibility["near_object_anchors"]["action"] is True
    assert wrong["claim_eligible"] is False


def test_slice_claim_eligibility_rejects_ambiguous_alias_only_mentions() -> None:
    row = {
        "object_name": "卢绾",
        "matched_aliases": ["燕王"],
        "object_source_cache": {
            "source_shape": "object_mention_candidate",
            "quality_flags": ["ambiguous_alias_only_mention"],
        },
        "text": "燕王旦谋反，事在昭帝时。",
    }

    eligibility = tool.slice_claim_eligibility(row)

    assert eligibility["claim_eligible"] is False
    assert eligibility["risk_flags"] == ["ambiguous_alias_only_mention_risk"]
    assert eligibility["support_level_hint"] == "context"


def test_canonical_near_duplicate_group_ignores_summary_wording() -> None:
    first = {
        "emperor_name": "朱元璋",
        "object_name": "汤和",
        "claim_summary": "朱元璋命汤和守常州。",
        "fact_payload": {
            "action_type": "授权",
            "event_scope": "军事",
            "office_or_domain": "常州镇守",
            "time_context": "洪武初",
            "outcome": "守常州",
        },
    }
    second = {**first, "claim_summary": "太祖令汤和镇守常州。"}

    assert tool.canonical_event_key(first) != tool.canonical_event_key(second)
    assert tool.near_duplicate_group_key(first) == tool.near_duplicate_group_key(second)
    assert tool.claim_quality_payload(first)["claim_grain"] == "event_chain"


def test_claim_negative_support_distinguishes_context_from_damage() -> None:
    context_only = {
        "claim_summary": "魏徵劝李世民斥退阎立本，李世民因其强济而未斥。",
        "outcome": "未斥",
        "fact_payload": {},
    }
    damage = {
        "claim_summary": "胡惟庸专擅中书省事，壅蔽奏章，害政甚多。",
        "fact_payload": {},
    }
    consequence = {
        "claim_summary": "褚遂良构陷卢承庆，使卢承庆左迁简州司马；房玄龄与杜如晦也一度被斥逐。",
        "fact_payload": {},
    }
    family_execution = {
        "claim_summary": "胡惟庸案中，帝遂并李善长妻女弟侄家口七十余人诛之。",
        "fact_payload": {"cost_or_damage": "妻女弟侄家口七十馀人被诛"},
    }
    mass_execution = {
        "claim_summary": "朱元璋处死胡惟庸，夷三族，并尽诛其僚属党与一万五千人。",
        "fact_payload": {},
    }
    neutral = {"claim_summary": "戴胄同知国政。", "fact_payload": {}}

    assert tool.claim_negative_support(context_only)["support"] == "negative_context_without_damage_anchor"
    assert tool.atomic_fact_payload(context_only)["negative_support"] == "negative_context_without_damage_anchor"
    assert tool.claim_negative_support(damage)["support"] == "governance_damage_supported"
    assert tool.claim_negative_support(consequence)["support"] == "governance_damage_supported"
    assert tool.claim_negative_support(family_execution)["support"] == "governance_damage_supported"
    assert tool.claim_negative_support(mass_execution)["support"] == "governance_damage_supported"
    assert tool.claim_negative_support(neutral)["support"] == "not_applicable"


def test_opportunity_estimator_suggests_budget_and_uses_new_action_anchors() -> None:
    slices = [
        {
            "slice_code": "SLI-001",
            "object_name": "李文忠",
            "matched_aliases": ["李文忠"],
            "source_shape": "object_biography_candidate",
            "section_heading": "李文忠",
            "text": "洪武二年，太祖诏李文忠领常遇春众，仍命其北征，克应昌。",
        },
        {
            "slice_code": "SLI-002",
            "object_name": "李文忠",
            "matched_aliases": ["李文忠"],
            "source_shape": "object_biography_candidate",
            "section_heading": "李文忠",
            "text": "李文忠往蜀拊循，筑成都新城，发军戍诸郡要害。",
        },
    ]

    report = tool.estimate_claim_opportunities(slices, claims=[])
    row = report["objects"]["李文忠"]

    assert row["opportunity_count"] == 2
    assert row["suggested_claim_budget"] >= 2
    assert row["actual_claim_count"] == 0
    assert row["undercoverage_risk"] == "missing_claims"
    assert "诏" in row["action_terms"]
    assert "领" in row["action_terms"]


def test_slice_claim_eligibility_recognizes_classical_advice_and_office_anchors() -> None:
    advice = {
        "slice_code": "SLI-ADVICE",
        "object_name": "魏徵",
        "matched_aliases": ["魏徵"],
        "source_shape": "object_biography_candidate",
        "text": "所司必谘而后行。魏徵见其倚昵，恐浸启侈端，劝帝斥之。",
    }
    office = {
        "slice_code": "SLI-OFFICE",
        "object_name": "戴胄",
        "matched_aliases": ["戴胄"],
        "source_shape": "object_biography_candidate",
        "text": "太宗时，戴胄与房玄龄、李靖、温彦博、魏徵、王珪同知国政。",
    }

    advice_eligibility = tool.slice_claim_eligibility(advice)
    office_opportunity = tool.slice_opportunity(office)

    assert advice_eligibility["claim_eligible"] is True
    assert advice_eligibility["near_object_anchors"]["action"] is True
    assert office_opportunity["has_opportunity"] is True
    assert "同知" in office_opportunity["action_terms"]


def test_opportunity_estimator_marks_possible_undercoverage() -> None:
    slices = [
        {
            "slice_code": f"SLI-{idx}",
            "object_name": "汤和",
            "matched_aliases": ["汤和"],
            "source_shape": "object_biography_candidate",
            "section_heading": "汤和",
            "text": text,
        }
        for idx, text in enumerate(
            [
                "朱元璋命汤和守常州，常州安辑。",
                "汤和从伐陈友谅，克其水寨。",
                "汤和镇守海防，筑城备倭。",
            ],
            start=1,
        )
    ]
    claims = [{"object_name": "汤和", "claim_summary": "朱元璋命汤和守常州。"}]

    report = tool.estimate_claim_opportunities(slices, claims=claims)
    row = report["objects"]["汤和"]

    assert row["opportunity_count"] == 3
    assert row["actual_claim_count"] == 1
    assert row["undercoverage_risk"] == "possible_undercoverage"


def test_opportunity_estimator_ignores_absent_object_false_positive() -> None:
    slices = [
        {
            "slice_code": "SLI-001",
            "object_name": "卢绾",
            "matched_aliases": ["燕王"],
            "object_source_cache": {
                "source_shape": "object_mention_candidate",
                "source_title": "漢書/卷063",
            },
            "text": "太子之亡也，东至湖。久之，巫蛊事多不信，天子乃下诏宽赦。",
        }
    ]

    eligibility = tool.slice_claim_eligibility(slices[0])
    report = tool.estimate_claim_opportunities(slices, claims=[])
    row = report["objects"]["卢绾"]

    assert eligibility["claim_eligible"] is False
    assert "object_absent_risk" in eligibility["risk_flags"]
    assert row["eligible_slice_count"] == 0
    assert row["opportunity_count"] == 0
    assert row["suggested_claim_budget"] == 0
    assert row["undercoverage_risk"] == ""


def test_opportunity_estimator_requires_primary_object_signal_for_alias_hits() -> None:
    slices = [
        {
            "slice_code": "SLI-001",
            "object_name": "卢绾",
            "matched_aliases": ["燕王"],
            "object_source_cache": {
                "source_shape": "object_mention_candidate",
                "source_title": "漢書/卷063",
            },
            "text": "燕王使人入朝，天子下诏封赏，又命将军率兵平乱。",
        }
    ]

    opportunity = tool.slice_opportunity(slices[0])
    report = tool.estimate_claim_opportunities(slices, claims=[])
    row = report["objects"]["卢绾"]

    assert opportunity["claim_eligible"] is True
    assert opportunity["has_primary_object_signal"] is False
    assert row["eligible_slice_count"] == 1
    assert row["opportunity_count"] == 0
    assert row["suggested_claim_budget"] == 0
    assert row["undercoverage_risk"] == ""
