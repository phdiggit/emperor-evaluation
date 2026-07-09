from __future__ import annotations

from scripts.dev import retrieval_v2_alias_pretag as tool


def test_same_dynasty_bare_temple_name_resolves_gaozong_to_li_zhi() -> None:
    mentions = tool.alias_mentions_in_text(
        "高宗欲废王皇后，褚遂良固谏，左授潭州都督。",
        requested_owner_name="李世民",
    )

    gaotzong = next(row for row in mentions if row["alias"] == "高宗")
    assert gaotzong["resolved_owner_name"] == "李治"
    assert gaotzong["resolution_status"] == "resolved"
    assert gaotzong["resolution_rule"] == "same_dynasty_bare_title_scope"
    assert gaotzong["owner_relation_to_requested"] == "other_owner"


def test_longer_dynasty_alias_wins_over_embedded_bare_title() -> None:
    mentions = tool.alias_mentions_in_text("宋高宗南渡后事。", requested_owner_name="李世民")

    assert [row["alias"] for row in mentions] == ["宋高宗"]
    assert mentions[0]["resolved_owner_name"] == "赵构"
    assert mentions[0]["resolution_rule"] == "unique_global_alias"


def test_canonical_owner_name_normalizes_full_aliases_not_bare_titles() -> None:
    assert tool.canonical_owner_name("隋炀帝") == "杨广"
    assert tool.canonical_owner_name("隋文帝") == "杨坚"
    assert tool.canonical_owner_name("高宗") == "高宗"


def test_title_alias_followed_by_other_person_name_is_not_owner_anchor() -> None:
    mentions = tool.alias_mentions_in_text(
        "炀帝即位后遣屈突通持诏召汉王谅。",
        requested_owner_name="李世民",
        source_title="隋书/卷五十三",
    )

    assert all(row["resolved_owner_name"] != "刘邦" for row in mentions)
    assert "汉王" not in [row["alias"] for row in mentions]


def test_title_alias_followed_by_owner_given_name_still_resolves() -> None:
    mentions = tool.alias_mentions_in_text(
        "秦王世民命房玄龄入府。",
        requested_owner_name="李渊",
        source_title="旧唐书/卷一",
    )

    qinwang = next(row for row in mentions if row["alias"] == "秦王")
    assert qinwang["resolved_owner_name"] == "李世民"


def test_short_owner_alias_inside_longer_person_name_is_not_owner_anchor() -> None:
    mentions = tool.alias_mentions_in_text(
        "李君羡从讨刘武周、王世充等，每战单骑先锋陷阵。",
        requested_owner_name="李世民",
        source_title="旧唐书/卷六十九",
    )

    assert "武周" not in [row["alias"] for row in mentions]
    assert all(row.get("resolved_owner_name") != "武则天" for row in mentions)


def test_suppressed_embedded_alias_is_available_for_debug_only() -> None:
    mentions = tool.alias_mentions_in_text(
        "李君羡从讨刘武周、王世充等，每战单骑先锋陷阵。",
        requested_owner_name="李世民",
        source_title="旧唐书/卷六十九",
        include_suppressed=True,
    )

    wuzhou = next(row for row in mentions if row["alias"] == "武周")
    assert wuzhou["resolution_status"] == "suppressed"
    assert wuzhou["resolved_owner_name"] == "武则天"
    assert wuzhou["owner_anchor_eligible"] is False
    assert wuzhou["mention_role"] == "suppressed_owner_alias"
    assert "short_alias_embedded_after_surname" in wuzhou["risk_flags"]


def test_suppressed_title_alias_is_available_for_debug_only() -> None:
    mentions = tool.alias_mentions_in_text(
        "炀帝即位后遣屈突通持诏召汉王谅。",
        requested_owner_name="李世民",
        source_title="隋书/卷五十三",
        include_suppressed=True,
    )

    hanwang = next(row for row in mentions if row["alias"] == "汉王")
    assert hanwang["resolution_status"] == "suppressed"
    assert hanwang["owner_anchor_eligible"] is False
    assert hanwang["suppression_reason"] == "title_alias_followed_by_non_owner_name"


def test_source_title_dynasty_resolves_bare_title_without_requested_scope() -> None:
    mentions = tool.alias_mentions_in_text(
        "高宗欲废王皇后，褚遂良固谏。",
        requested_owner_name="刘邦",
        source_title="旧唐书/卷八十",
    )

    assert mentions[0]["alias"] == "高宗"
    assert mentions[0]["resolved_owner_name"] == "李治"
    assert mentions[0]["resolution_rule"] == "source_title_dynasty_bare_title"
    assert mentions[0]["source_dynasty_prefixes"] == ["唐"]
    assert mentions[0]["owner_anchor_eligible"] is True
    assert mentions[0]["mention_role"] == "owner_anchor"


def test_prompt_relevant_mentions_omit_current_target_aliases() -> None:
    row = {"text": "太宗命褚遂良掌起居注，高宗后左授潭州都督。"}

    mentions = tool.slice_alias_mentions(row, requested_owner_name="李世民", only_prompt_relevant=True)

    assert [row["alias"] for row in mentions] == ["高宗"]
    assert mentions[0]["resolved_owner_name"] == "李治"


def test_claim_owner_rebind_uses_actor_alias_not_context_only_mentions() -> None:
    alias_mentions = {
        "SLI-001": tool.alias_mentions_in_text(
            "高宗欲废王皇后，褚遂良固谏，左授潭州都督。",
            requested_owner_name="李世民",
        )
    }
    claim = {
        "emperor_name": "李世民",
        "source_slice_refs": ["SLI-001"],
        "fact_payload": {"actor": "高宗", "object": "褚遂良", "action_type": "处置"},
    }

    rebind = tool.claim_owner_rebind_from_alias_mentions(
        claim,
        source_refs=["SLI-001"],
        alias_mentions_by_ref=alias_mentions,
    )
    rebound = tool.apply_claim_owner_rebind(claim, rebind)

    assert rebind["to_emperor_name"] == "李治"
    assert rebind["matched_aliases"] == ["高宗"]
    assert rebound["emperor_name"] == "李治"
    assert rebound["owner_rebind_payload"]["from_emperor_name"] == "李世民"


def test_claim_owner_rebind_ignores_suppressed_embedded_alias() -> None:
    alias_mentions = {
        "SLI-001": tool.alias_mentions_in_text(
            "李君羡从讨刘武周、王世充等，每战单骑先锋陷阵。",
            requested_owner_name="李世民",
            source_title="旧唐书/卷六十九",
            include_suppressed=True,
        )
    }
    claim = {
        "emperor_name": "李世民",
        "source_slice_refs": ["SLI-001"],
        "claim_summary": "李君羡从讨刘武周、王世充等，每战单骑先锋陷阵。",
        "fact_payload": {"actor": "李君羡", "object": "刘武周、王世充等", "action_type": "战役"},
    }

    rebind = tool.claim_owner_rebind_from_alias_mentions(
        claim,
        source_refs=["SLI-001"],
        alias_mentions_by_ref=alias_mentions,
    )

    assert rebind == {}


def test_claim_owner_rebind_uses_unique_other_owner_context_when_target_absent() -> None:
    alias_mentions = {
        "SLI-001": tool.alias_mentions_in_text(
            "高宗时，褚遂良固谏。",
            requested_owner_name="李世民",
        )
    }
    claim = {
        "emperor_name": "李世民",
        "source_slice_refs": ["SLI-001"],
        "claim_summary": "高宗时，褚遂良固谏废后议。",
        "fact_payload": {"actor": "褚遂良", "object": "废后议", "action_type": "纳谏"},
    }

    rebind = tool.claim_owner_rebind_from_alias_mentions(
        claim,
        source_refs=["SLI-001"],
        alias_mentions_by_ref=alias_mentions,
    )

    assert rebind["to_emperor_name"] == "李治"
    assert rebind["reason"] == "claim_context_unique_resolved_owner_without_requested_owner"


def test_claim_owner_rebind_uses_other_owner_when_target_is_context_only() -> None:
    alias_mentions = {
        "SLI-001": tool.alias_mentions_in_text(
            "隐太子忌惮房玄龄、杜如晦受李世民亲礼，向高祖谮毁二人，使房玄龄与杜如晦被驱斥。",
            requested_owner_name="李世民",
        )
    }
    claim = {
        "emperor_name": "李世民",
        "source_slice_refs": ["SLI-001"],
        "claim_summary": "隐太子忌惮房玄龄、杜如晦受李世民亲礼，向高祖谮毁二人，使房玄龄与杜如晦被驱斥。",
        "fact_payload": {"actor": "隐太子", "object": "房玄龄", "action_type": "处置", "outcome": "被驱斥"},
    }

    rebind = tool.claim_owner_rebind_from_alias_mentions(
        claim,
        source_refs=["SLI-001"],
        alias_mentions_by_ref=alias_mentions,
    )

    assert rebind["to_emperor_name"] == "李渊"
    assert rebind["matched_aliases"] == ["高祖"]
    assert rebind["reason"] == "claim_context_unique_resolved_owner_with_requested_owner_context_only"
