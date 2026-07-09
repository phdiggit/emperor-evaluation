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
    assert result["owner_review_class"] == "rebind_candidate"
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
    assert result["owner_review_class"] == "target_owner_actor_matched"
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
    assert result["owner_review_class"] == "person_material_without_owner_anchor"
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


def test_short_alias_embedded_in_person_name_does_not_create_owner_rebind() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="李世民",
            object_name="李君羡",
            action_type="战役",
            claim_summary="李君羡从讨刘武周、王世充等，每战单骑先锋陷阵。",
            fact_payload={"actor": "李君羡", "object": "刘武周、王世充", "action_type": "战役", "source_title": "旧唐书/卷六十九"},
        ),
        aliases,
    )

    assert result["owner_status"] == "person_material"
    assert result["suggested_owner_name"] == ""
    assert result["matched_owner_alias"] == ""
    assert result["other_owner_mentions"] == []


def test_title_alias_followed_by_other_person_name_does_not_create_owner_rebind() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="杨坚",
            object_name="杨谅",
            action_type="处置",
            claim_summary="汉王谅起兵反，朝廷遣杨素讨平。",
            fact_payload={"actor": "汉王谅", "object": "杨素", "action_type": "处置", "source_title": "隋书/卷五十三"},
        ),
        aliases,
    )

    assert result["owner_status"] == "needs_review"
    assert result["owner_risk_kind"] == "ruler_action_without_requested_owner_mention"
    assert result["suggested_owner_name"] == ""
    assert result["matched_owner_alias"] == ""
    assert result["other_owner_mentions"] == []


def test_time_context_owner_alias_does_not_create_owner_rebind() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="刘邦",
            object_name="陆贾",
            action_type="其他",
            time_context="孝惠帝时，吕太后用事",
            claim_summary="吕太后用事、诸吕擅权时，陆贾自度不能争，称病免官家居。",
            fact_payload={
                "actor": "陆贾",
                "object": "诸吕擅权局面",
                "action_type": "其他",
                "time_context": "孝惠帝时，吕太后用事",
            },
        ),
        aliases,
    )

    assert result["owner_status"] == "person_material"
    assert result["suggested_owner_name"] == ""
    assert result["matched_owner_alias"] == ""
    assert result["other_owner_mentions"] == []


def test_book_title_owner_alias_does_not_create_owner_rebind() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="李世民",
            object_name="房玄龄",
            action_type="授权",
            claim_summary="李世民命监修国史房玄龄撰次《高祖》《今上实录》以闻，书成后又命削去浮词、直书其事。",
            fact_payload={
                "actor": "李世民",
                "object": "房玄龄",
                "action_type": "授权",
                "outcome": "房玄龄等删为《高祖》《今上实录》并上书",
                "source_title": "旧唐书/卷七十三",
            },
        ),
        aliases,
    )

    assert result["owner_status"] == "matched"
    assert result["suggested_owner_name"] == "李世民"
    assert result["matched_owner_alias"] == "李世民"
    assert result["other_owner_mentions"] == []


def test_tomb_reference_owner_alias_does_not_create_owner_rebind() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="李世民",
            object_name="房玄龄",
            action_type="其他",
            claim_summary="房玄龄等议定唐高祖陵坟高度，李世民采纳依原陵之制的方案。",
            fact_payload={
                "actor": "房玄龄等",
                "object": "高祖陵制",
                "action_type": "其他",
                "outcome": "从之",
                "source_title": "旧唐书/卷七十三",
            },
        ),
        aliases,
    )

    assert result["owner_status"] == "needs_review"
    assert result["owner_risk_kind"] == "minister_actor_requested_context_review"
    assert result["suggested_owner_name"] == ""
    assert result["matched_owner_alias"] == ""
    assert result["other_owner_mentions"] == []


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
    assert result["owner_review_class"] == "rebind_candidate"
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
    assert finding["owner_review_class"] == "multi_owner_timeline_review"


def test_minister_actor_target_context_is_downgraded_to_ok_class() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="李世民",
            object_name="萧瑀",
            action_type="处置",
            claim_summary="萧瑀弹劾房玄龄、魏徵、温彦博的小过失，李世民最终不问所劾之罪。",
            fact_payload={"actor": "萧瑀", "object": "房玄龄、魏徵、温彦博", "action_type": "处置"},
        ),
        aliases,
    )

    assert result["owner_status"] == "needs_review"
    assert result["owner_risk_kind"] == "minister_actor_requested_context_review"
    assert result["owner_review_class"] == "minister_actor_target_context_ok"


def test_ruler_action_without_owner_anchor_gets_specific_review_class() -> None:
    aliases = tool.load_owner_aliases()

    result = tool.classify_claim_owner(
        claim_row(
            emperor_name="李世民",
            object_name="萧瑀",
            action_type="处置",
            claim_summary="萧瑀弹劾房玄龄、魏徵、温彦博的小过失，所劾之罪最终不问。",
            fact_payload={"actor": "萧瑀", "object": "房玄龄、魏徵、温彦博", "action_type": "处置"},
        ),
        aliases,
    )

    assert result["owner_status"] == "needs_review"
    assert result["owner_review_class"] == "ruler_action_without_owner_anchor"


def test_owner_binding_inventory_reports_external_and_review_samples() -> None:
    aliases = tool.load_owner_aliases()
    findings = [
        tool.classify_claim_owner(
            claim_row(
                claim_key="CLMK-EXT",
                emperor_name="王世充",
                object_name="戴胄",
                action_type="其他",
                claim_summary="王世充谋篡时，戴胄切谏。",
                fact_payload={"actor": "戴胄", "object": "王世充", "action_type": "其他"},
            ),
            aliases,
        ),
        tool.classify_claim_owner(
            claim_row(
                claim_key="CLMK-REBIND",
                emperor_name="李世民",
                claim_summary="高宗欲废王皇后后，褚遂良因忤旨被左授潭州都督。",
                fact_payload={"actor": "高宗", "object": "褚遂良", "action_type": "处置"},
            ),
            aliases,
        ),
    ]

    inventory = tool.owner_binding_inventory(findings, aliases, sample_limit=1)

    assert inventory["claim_count_by_owner_pool_status"]["external_or_unregistered_owner"] == 1
    assert inventory["claim_count_by_owner_pool_status"]["registered_target_owner"] == 1
    assert inventory["external_or_unregistered_owners"] == [{"owner_name": "王世充", "claim_count": 1}]
    assert inventory["anomaly_counts"]["external_or_unregistered_owner"] == 1
    assert inventory["anomaly_counts"]["rebind_candidate"] == 1
    assert inventory["review_class_counts"]["person_material_without_owner_anchor"] == 1
    assert inventory["review_class_counts"]["rebind_candidate"] == 1
    assert inventory["samples"]["external_or_unregistered_owner_claims"][0]["claim_key"] == "CLMK-EXT"
    assert inventory["samples"]["rebind_candidates"][0]["claim_key"] == "CLMK-REBIND"


def test_owner_rebind_payload_inventory_flags_book_title_alias() -> None:
    aliases = tool.load_owner_aliases()
    rows = [
        claim_row(
            claim_key="CLMK-BOOK",
            emperor_name="李渊",
            object_name="房玄龄",
            action_type="授权",
            claim_summary="李世民命监修国史房玄龄撰次《高祖》《今上实录》以闻。",
            fact_payload={
                "actor": "李世民",
                "object": "房玄龄",
                "action_type": "授权",
                "owner_rebind_payload": {
                    "from_emperor_name": "李世民",
                    "to_emperor_name": "李渊",
                    "reason": "claim_context_unique_resolved_owner_without_requested_owner",
                    "matched_aliases": ["高祖"],
                    "resolution_rules": ["same_dynasty_bare_title_scope"],
                    "evidence": [{"alias": "高祖", "resolution_rule": "same_dynasty_bare_title_scope"}],
                },
            },
        )
    ]

    inventory = tool.owner_rebind_payload_inventory(rows, aliases, sample_limit=2)

    assert inventory["payload_claim_count"] == 1
    assert inventory["by_matched_alias"]["高祖"] == 1
    assert inventory["risk_counts"]["current_suppression.alias_inside_book_title"] == 1
    assert inventory["risk_counts"]["current_mechanism_suppresses_matched_alias"] == 1
    assert inventory["risk_counts"]["current_mechanism_does_not_reproduce_rebind_anchor"] == 1
    sample = inventory["samples"]["current_suppression.alias_inside_book_title"][0]
    assert sample["claim_key"] == "CLMK-BOOK"
    assert inventory["rows"][0]["claim_key"] == "CLMK-BOOK"
    assert inventory["rows"][0]["risk_flags"] == sample["risk_flags"]


def test_owner_rebind_payload_inventory_flags_time_context_only_alias(tmp_path) -> None:
    aliases = tool.load_owner_aliases()
    rows = [
        claim_row(
            claim_key="CLMK-TIME",
            emperor_name="刘盈",
            object_name="陆贾",
            action_type="其他",
            time_context="孝惠帝时，吕太后用事",
            claim_summary="吕太后用事、诸吕擅权时，陆贾自度不能争，称病免官家居。",
            fact_payload={
                "actor": "陆贾",
                "object": "诸吕擅权局面",
                "action_type": "其他",
                "time_context": "孝惠帝时，吕太后用事",
                "owner_rebind_payload": {
                    "from_emperor_name": "刘邦",
                    "to_emperor_name": "刘盈",
                    "reason": "claim_context_unique_resolved_owner_without_requested_owner",
                    "matched_aliases": ["惠帝"],
                    "resolution_rules": ["same_dynasty_bare_title_scope"],
                    "evidence": [{"alias": "惠帝", "resolution_rule": "same_dynasty_bare_title_scope"}],
                },
            },
        )
    ]

    inventory = tool.owner_rebind_payload_inventory(rows, aliases, sample_limit=2)

    assert inventory["payload_claim_count"] == 1
    assert inventory["risk_counts"]["time_context_only_matched_alias"] == 1
    assert inventory["risk_counts"]["high_risk_matched_alias"] == 1
    assert inventory["risk_counts"]["short_matched_alias"] == 1

    output_csv = tmp_path / "owner_rebind_payload.csv"
    tool.write_owner_rebind_payload_csv(output_csv, inventory["rows"])
    csv_text = output_csv.read_text(encoding="utf-8")
    assert "claim_key,emperor_name,object_name,status,from_emperor_name,to_emperor_name" in csv_text
    assert "CLMK-TIME" in csv_text
    assert "time_context_only_matched_alias" in csv_text


def test_owner_rebind_payload_inventory_flags_time_context_actor_from_owner() -> None:
    aliases = tool.load_owner_aliases()
    rows = [
        claim_row(
            claim_key="CLMK-TIME-ACTOR",
            emperor_name="李世民",
            object_name="殷开山",
            action_type="任命",
            time_context="癸亥秦王至长安后，己巳",
            claim_summary="李渊在长安享劳将士后，恢复殷开山爵位。",
            fact_payload={
                "actor": "李渊",
                "object": "殷开山",
                "action_type": "任命",
                "time_context": "癸亥秦王至长安后，己巳",
                "owner_rebind_payload": {
                    "from_emperor_name": "李渊",
                    "to_emperor_name": "李世民",
                    "reason": "claim_context_unique_resolved_owner_without_requested_owner",
                    "matched_aliases": ["秦王"],
                    "resolution_rules": ["unique_global_alias"],
                    "evidence": [{"alias": "秦王", "resolution_rule": "unique_global_alias"}],
                },
            },
        )
    ]

    inventory = tool.owner_rebind_payload_inventory(rows, aliases, sample_limit=2)

    assert inventory["risk_counts"]["time_context_only_matched_alias"] == 1
    assert inventory["risk_counts"]["time_context_only_actor_matches_from_owner"] == 1


def test_owner_rebind_payload_inventory_flags_time_context_actor_differs_from_owner_review() -> None:
    aliases = tool.load_owner_aliases()
    rows = [
        claim_row(
            claim_key="CLMK-TIME-ACTOR-DIFFERS",
            emperor_name="吕雉",
            object_name="陈平",
            action_type="收权",
            time_context="高后八年",
            claim_summary="吕氏将兵居南北军时，陈平与周勃谋划使吕禄交出兵权。",
            fact_payload={
                "actor": "陈平",
                "object": "吕禄",
                "action_type": "收权",
                "time_context": "高后八年",
                "owner_rebind_payload": {
                    "from_emperor_name": "刘邦",
                    "to_emperor_name": "吕雉",
                    "reason": "single_other_owner_context_without_requested_owner",
                    "matched_aliases": ["高后"],
                    "resolution_rules": [],
                    "evidence": [{"alias": "高后"}],
                },
            },
        )
    ]

    inventory = tool.owner_rebind_payload_inventory(rows, aliases, sample_limit=2)

    assert inventory["risk_counts"]["time_context_only_matched_alias"] == 1
    assert inventory["risk_counts"]["time_context_only_actor_differs_from_from_owner_review"] == 1
    assert "time_context_only_actor_matches_from_owner" not in inventory["risk_counts"]


def test_owner_rebind_payload_inventory_flags_source_title_rule_without_current_alias() -> None:
    aliases = tool.load_owner_aliases()
    rows = [
        claim_row(
            claim_key="CLMK-SOURCE-TITLE-ONLY",
            emperor_name="李世民",
            object_name="段志玄",
            action_type="战功",
            time_context="义兵起后",
            claim_summary="段志玄随军平霍邑、下绛郡、攻永丰仓，均担任先锋。",
            fact_payload={
                "actor": "段志玄",
                "object": "平霍邑、下绛郡、攻永丰仓",
                "action_type": "战功",
                "time_context": "义兵起后",
                "owner_rebind_payload": {
                    "from_emperor_name": "李渊",
                    "to_emperor_name": "李世民",
                    "reason": "source_unique_owner_anchor_without_requested_owner_in_claim",
                    "matched_aliases": ["太宗"],
                    "resolution_rules": ["source_title_dynasty_bare_title"],
                    "evidence": [{"alias": "太宗", "resolution_rule": "source_title_dynasty_bare_title"}],
                },
            },
        )
    ]

    inventory = tool.owner_rebind_payload_inventory(rows, aliases, sample_limit=2)

    assert inventory["risk_counts"]["matched_alias_not_in_current_claim_text"] == 1
    assert inventory["risk_counts"]["bare_title_rule_without_current_alias"] == 1
    assert inventory["risk_counts"]["source_title_rule_without_current_alias"] == 1
    assert inventory["risk_counts"]["source_title_rule_without_claim_or_evidence_alias"] == 1


def test_owner_rebind_payload_inventory_flags_bare_title_rule_without_claim_or_evidence_alias() -> None:
    aliases = tool.load_owner_aliases()
    rows = [
        claim_row(
            claim_key="CLMK-BARE-TITLE-NO-EVIDENCE",
            emperor_name="吕雉",
            object_name="彭越",
            action_type="评价",
            time_context="班固评",
            claim_summary="班固评价彭越等异姓王凭权变诈力成功，后因疑惧而谋叛灭亡。",
            evidence_text="班固评价异姓王得失。",
            fact_payload={
                "actor": "班固",
                "object": "彭越",
                "action_type": "评价",
                "time_context": "班固评",
                "owner_rebind_payload": {
                    "from_emperor_name": "刘邦",
                    "to_emperor_name": "吕雉",
                    "reason": "source_unique_owner_anchor_without_requested_owner_in_claim",
                    "matched_aliases": ["高后"],
                    "resolution_rules": ["same_dynasty_bare_title_scope"],
                    "evidence": [{"alias": "高后", "resolution_rule": "same_dynasty_bare_title_scope"}],
                },
            },
        )
    ]

    inventory = tool.owner_rebind_payload_inventory(rows, aliases, sample_limit=2)

    assert inventory["risk_counts"]["matched_alias_not_in_current_claim_text"] == 1
    assert inventory["risk_counts"]["bare_title_rule_without_current_alias"] == 1
    assert inventory["risk_counts"]["bare_title_rule_without_claim_or_evidence_alias"] == 1


def test_owner_rebind_payload_inventory_flags_alias_in_evidence_only() -> None:
    aliases = tool.load_owner_aliases()
    rows = [
        claim_row(
            claim_key="CLMK-EVIDENCE-ONLY",
            emperor_name="李世民",
            object_name="刘弘基",
            action_type="任命",
            time_context="师至河东后",
            claim_summary="刘弘基任渭北道大使时，以殷开山为副。",
            evidence_text="会高祖镇太原，遂自结托，又察太宗有非常之度，尤委心焉。",
            fact_payload={
                "actor": "刘弘基",
                "object": "殷开山",
                "action_type": "任命",
                "time_context": "师至河东后",
                "owner_rebind_payload": {
                    "from_emperor_name": "李渊",
                    "to_emperor_name": "李世民",
                    "reason": "source_unique_owner_anchor_without_requested_owner_in_claim",
                    "matched_aliases": ["太宗"],
                    "resolution_rules": ["source_title_dynasty_bare_title"],
                    "evidence": [{"alias": "太宗", "resolution_rule": "source_title_dynasty_bare_title"}],
                },
            },
        )
    ]

    inventory = tool.owner_rebind_payload_inventory(rows, aliases, sample_limit=2)

    assert inventory["risk_counts"]["matched_alias_not_in_current_claim_text"] == 1
    assert inventory["risk_counts"]["matched_alias_in_evidence_text_only"] == 1
    assert inventory["risk_counts"]["source_title_rule_without_current_alias"] == 1
    assert inventory["risk_counts"]["source_title_rule_evidence_only_review"] == 1
    assert "source_title_rule_without_claim_or_evidence_alias" not in inventory["risk_counts"]


def test_owner_audit_reads_atomic_fact_view_without_direction_hint() -> None:
    source = (tool.ROOT / "scripts/dev/retrieval_v2_claim_owner_audit.py").read_text(encoding="utf-8")

    assert "from retrieval_v2.claim_atomic_facts" in source
    assert "direction::text as direction" not in source
    assert '"direction",' not in source
