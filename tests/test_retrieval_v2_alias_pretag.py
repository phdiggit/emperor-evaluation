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
