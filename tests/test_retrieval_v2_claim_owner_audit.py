from __future__ import annotations

from scripts.dev import retrieval_v2_claim_owner_audit as tool


def claim_row(**overrides):
    row = {
        "claim_key": "CLMK-001",
        "emperor_name": "李世民",
        "object_name": "褚遂良",
        "status": "active",
        "direction": "negative",
        "action_type": "处置",
        "time_context": "永徽六年前后",
        "outcome": "左授潭州都督",
        "claim_summary": "高宗欲废王皇后后，褚遂良因忤旨被左授潭州都督。",
        "fact_payload": {"actor": "高宗", "object": "褚遂良", "action_type": "处置"},
    }
    row.update(overrides)
    return row


def test_owner_aliases_resolve_titles_to_canonical_personal_names() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(claim_row(), aliases)

    assert result["owner_status"] == "rebind_candidate"
    assert result["owner_risk_kind"] == "ruler_action_actor_matches_other_owner"
    assert result["suggested_owner_name"] == "李治"
    assert result["matched_owner_alias"] == "高宗"
    assert "direction" not in result


def test_owner_aliases_resolve_han_wendi_to_liu_heng() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="刘邦",
            object_name="周勃",
            action_type="任命",
            time_context="文帝前元年",
            claim_summary="文帝前元年，周勃由太尉迁为右丞相。",
            fact_payload={"actor": "文帝", "object": "周勃", "action_type": "任命"},
        ),
        aliases,
    )

    assert result["owner_status"] == "rebind_candidate"
    assert result["suggested_owner_name"] == "刘恒"
    assert result["matched_owner_alias"] == "文帝"


def test_scoped_gaozu_alias_keeps_liubang_claims_on_liubang() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="刘邦",
            object_name="萧何",
            action_type="任命",
            direction="positive",
            time_context="高祖时",
            claim_summary="高祖任萧何为相国。",
            fact_payload={"actor": "高祖", "object": "萧何", "action_type": "任命"},
        ),
        aliases,
    )

    assert result["owner_status"] == "matched"
    assert result["suggested_owner_name"] == "刘邦"
    assert result["matched_owner_alias"] == "高祖"


def test_matching_target_owner_stays_matched() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            action_type="任命",
            direction="positive",
            time_context="贞观十年",
            claim_summary="贞观十年，李世民任褚遂良为起居郎。",
            fact_payload={"actor": "李世民", "object": "褚遂良", "action_type": "任命"},
        ),
        aliases,
    )

    assert result["owner_status"] == "matched"
    assert result["suggested_owner_name"] == "李世民"
    assert result["matched_owner_alias"] == "李世民"


def test_person_material_without_requested_owner_is_not_rejected() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="朱元璋",
            object_name="傅友德",
            action_type="战役",
            direction="positive",
            time_context="北伐时",
            claim_summary="傅友德率军攻克要地。",
            fact_payload={"actor": "傅友德", "object": "敌军", "action_type": "战役"},
        ),
        aliases,
    )

    assert result["owner_status"] == "person_material"
    assert result["suggested_owner_name"] == ""


def test_rebind_plan_keeps_review_and_person_material_but_not_matched() -> None:
    aliases = tool.load_owner_aliases()
    findings = [
        tool.classify_claim_owner(
            claim_row(
                claim_key="CLMK-MATCHED",
                fact_payload={"actor": "李世民", "object": "褚遂良", "action_type": "任命"},
                claim_summary="李世民任褚遂良为起居郎。",
                action_type="任命",
            ),
            aliases,
        ),
        tool.classify_claim_owner(claim_row(claim_key="CLMK-REBIND"), aliases),
    ]

    plan = tool.rebind_plan(findings)

    assert [row["claim_key"] for row in plan] == ["CLMK-REBIND"]


def test_executable_rebind_plan_keeps_actor_and_unique_context_rebinds() -> None:
    aliases = tool.load_owner_aliases()
    findings = [
        tool.classify_claim_owner(claim_row(claim_key="CLMK-REBIND"), aliases),
        tool.classify_claim_owner(
            claim_row(
                claim_key="CLMK-REVIEW",
                fact_payload={"actor": "褚遂良", "object": "废后议", "action_type": "纳谏"},
                claim_summary="高宗时，褚遂良固谏。",
                action_type="纳谏",
            ),
            aliases,
        ),
        tool.classify_claim_owner(
            claim_row(
                claim_key="CLMK-MATCHED",
                fact_payload={"actor": "李世民", "object": "褚遂良", "action_type": "任命"},
                claim_summary="李世民任褚遂良为起居郎。",
                action_type="任命",
            ),
            aliases,
        ),
    ]

    plan = tool.executable_rebind_plan(findings)

    assert [row["claim_key"] for row in plan] == ["CLMK-REBIND", "CLMK-REVIEW"]
    assert [row["suggested_owner_name"] for row in plan] == ["李治", "李治"]


def test_unique_other_owner_context_without_requested_owner_is_rebind_candidate() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="刘邦",
            object_name="萧何",
            action_type="荐举",
            claim_summary="惠帝探问萧何身后相国继任者，萧何认可曹参可代己任。",
            fact_payload={"actor": "萧何", "object": "曹参", "action_type": "荐举"},
        ),
        aliases,
    )

    assert result["owner_status"] == "rebind_candidate"
    assert result["owner_risk_kind"] == "single_other_owner_context_without_requested_owner"
    assert result["suggested_owner_name"] == "刘盈"
    assert result["matched_owner_alias"] == "惠帝"


def test_target_death_after_anchor_does_not_block_other_owner_rebind() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="刘邦",
            object_name="萧何",
            action_type="荐举",
            time_context="高祖崩后萧何病重时",
            claim_summary="惠帝探问萧何身后相国继任者，萧何认可曹参可代己任。",
            fact_payload={"actor": "萧何", "object": "曹参", "action_type": "荐举"},
        ),
        aliases,
    )

    assert result["owner_status"] == "rebind_candidate"
    assert result["suggested_owner_name"] == "刘盈"
    assert result["target_owner_mentioned"] is False


def test_zhulu_after_phrase_does_not_match_lvhou_alias() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="刘邦",
            object_name="周勃",
            action_type="处置",
            claim_summary="诛灭诸吕后，周勃等大臣共谋迎立代王，并由周勃向代王跪上天子玺符。",
            fact_payload={"actor": "周勃等大臣", "object": "代王", "action_type": "处置"},
        ),
        aliases,
    )

    assert result["owner_status"] == "rebind_candidate"
    assert result["suggested_owner_name"] == "刘恒"
    assert result["matched_owner_alias"] == "代王"
    assert result["other_owner_mentions"] == [{"owner_name": "刘恒", "alias": "代王"}]


def test_fact_payload_object_does_not_protect_requested_owner_when_text_points_elsewhere() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="刘邦",
            object_name="韩信",
            action_type="谋反",
            time_context="汉十年陈豨反时",
            claim_summary="韩信阴使人通陈豨并与家臣谋发兵袭吕后、太子，后被吕后、萧何诈召入宫斩杀。",
            fact_payload={"actor": "韩信", "object": "刘邦", "action_type": "谋反"},
        ),
        aliases,
    )

    assert result["owner_status"] == "rebind_candidate"
    assert result["suggested_owner_name"] == "吕雉"
    assert result["target_owner_mentioned"] is False


def test_fact_object_owner_breaks_multi_owner_context_toward_event_target() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="刘邦",
            object_name="周勃",
            action_type="处置",
            time_context="高后八年后九月",
            claim_summary="诛灭诸吕后，周勃等大臣共谋迎立代王，并由周勃向代王跪上天子玺符。",
            fact_payload={"actor": "周勃等大臣", "object": "代王刘恒", "action_type": "处置"},
        ),
        aliases,
    )

    assert result["owner_status"] == "rebind_candidate"
    assert result["owner_risk_kind"] == "fact_object_owner_context_without_requested_owner"
    assert result["suggested_owner_name"] == "刘恒"


def test_context_only_requested_owner_mention_does_not_block_unique_other_owner_rebind() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="李世民",
            object_name="房玄龄",
            action_type="处置",
            time_context="武德末隐太子将有变前",
            claim_summary="隐太子忌惮房玄龄、杜如晦受李世民亲礼，向高祖谮毁二人，使房玄龄与杜如晦被驱斥。",
            fact_payload={"actor": "隐太子", "object": "房玄龄", "action_type": "处置", "outcome": "被驱斥"},
        ),
        aliases,
    )

    assert result["owner_status"] == "rebind_candidate"
    assert result["owner_risk_kind"] == "single_other_owner_context_with_requested_owner_context_only"
    assert result["suggested_owner_name"] == "李渊"
    assert result["target_owner_context_only"] is True


def test_executable_review_status_plan_keeps_multi_owner_timelines_out_of_active_rebinds() -> None:
    aliases = tool.load_owner_aliases()
    finding = tool.classify_claim_owner(
        claim_row(
            emperor_name="刘邦",
            object_name="陈平",
            action_type="任命",
            time_context="孝惠六年至孝文元年",
            claim_summary="官表记载惠帝六年陈平为左丞相，高后元年转为右丞相，文帝元年又为左丞相。",
            fact_payload={"actor": "汉廷", "object": "陈平", "action_type": "任命"},
        ),
        aliases,
    )

    assert tool.executable_rebind_plan([finding]) == []
    assert [row["claim_key"] for row in tool.executable_review_status_plan([finding])] == ["CLMK-001"]


def test_owner_audit_reads_atomic_fact_view_without_direction_hint() -> None:
    source = (tool.ROOT / "scripts/dev/retrieval_v2_claim_owner_audit.py").read_text(encoding="utf-8")

    assert "from retrieval_v2.claim_atomic_facts" in source
    assert "direction::text as direction" not in source
    assert '"direction",' not in source
