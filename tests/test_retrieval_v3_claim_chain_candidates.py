from __future__ import annotations

from scripts.dev import retrieval_v3_claim_chain_candidates as tool


def claim(**overrides):
    row = {
        "claim_key": "CLMK-001",
        "emperor_name": "朱元璋",
        "object_name": "胡惟庸",
        "claim_type": "material_action",
        "fact_schema": "political_action_v1",
        "fact_type": "material_action",
        "action_type": "任命",
        "event_scope": "中枢",
        "office_or_domain": "中书省",
        "time_context": "",
        "outcome": "",
        "claim_summary": "",
        "fact_payload": {},
        "atomic_fact_payload": {},
        "event_group_key": "",
        "status": "active",
        "source_slice_refs": ["OSS-HWY"],
        "document_codes": ["OSD-HWY"],
        "quote_previews": [],
    }
    row.update(overrides)
    if not row["atomic_fact_payload"]:
        row["atomic_fact_payload"] = {
            "emperor_name": row["emperor_name"],
            "object_name": row["object_name"],
            "fact_type": row["fact_type"],
            "actor": row.get("actor", row["emperor_name"]),
            "fact_object": row.get("fact_object", row["object_name"]),
            "action_type": row["action_type"],
            "event_scope": row["event_scope"],
            "office_or_domain": row["office_or_domain"],
            "time_context": row["time_context"],
            "outcome": row["outcome"],
            "cost_or_damage": row.get("cost_or_damage", ""),
            "outcome_support": row.get("outcome_support", "direct"),
            "negative_support": row.get("negative_support", "not_applicable"),
        }
    return row


def test_hu_weiyong_claims_build_delegated_power_abuse_strong_chain() -> None:
    claims = [
        claim(
            claim_key="CLMK-APPOINT-1",
            action_type="任命",
            time_context="洪武三年",
            office_or_domain="中书省参知政事",
            outcome="胡惟庸任中书省参知政事",
            claim_summary="洪武三年，胡惟庸被拜为中书省参知政事。",
        ),
        claim(
            claim_key="CLMK-APPOINT-2",
            action_type="任命",
            time_context="洪武六年七月以后",
            office_or_domain="右丞相、左丞相",
            outcome="胡惟庸先拜右丞相，后进左丞相",
            claim_summary="洪武六年七月，胡惟庸被拜为右丞相，后又进为左丞相。",
        ),
        claim(
            claim_key="CLMK-POWER-1",
            action_type="授权",
            time_context="洪武六年正月后",
            office_or_domain="中书省事",
            outcome="胡惟庸独专省事",
            claim_summary="因朱元璋难于择相、久不置相，胡惟庸一度独专中书省事。",
        ),
        claim(
            claim_key="CLMK-DAMAGE-1",
            action_type="其他",
            time_context="独相数岁期间",
            office_or_domain="奏章处理",
            actor="胡惟庸",
            fact_object="内外诸司封事",
            outcome="害己者被隐匿不上闻",
            claim_summary="胡惟庸先取阅内外诸司上封事，遇到害己内容就隐匿不上闻。",
        ),
        claim(
            claim_key="CLMK-DAMAGE-2",
            action_type="其他",
            time_context="独相数岁期间",
            office_or_domain="生杀黜陟",
            actor="胡惟庸",
            fact_object="中枢政务",
            outcome="有时不奏报皇帝而径行处置",
            claim_summary="胡惟庸专权期间，生杀黜陟有时不奏报即自行施行。",
        ),
        claim(
            claim_key="CLMK-TERMINAL",
            action_type="处置",
            time_context="最终",
            office_or_domain="叛逆处置",
            outcome="胡惟庸坐叛逆诛死",
            claim_summary="胡惟庸最终因叛逆罪被诛死。",
        ),
    ]

    candidates = tool.build_chain_candidates(claims)

    assert len(candidates) == 1
    chain = candidates[0]
    assert chain["chain_type"] == "delegated_power_abuse_chain"
    assert chain["chain_strength"] == "strong_chain"
    assert chain["route_readiness"] == "ready_for_chain_route_review"
    assert chain["time_model"]["ordered_enough"] is True
    assert chain["role_family_counts"]["damage"] == 2
    assert chain["role_family_counts"]["terminal"] == 1
    assert [member["member_role"] for member in chain["members"]][-1] == "terminal_negative_outcome"


def test_claim_member_carries_negative_support_without_changing_role() -> None:
    row = claim(
        claim_key="CLMK-NEG-CONTEXT",
        action_type="纳谏",
        outcome="未斥",
        negative_support="negative_context_without_damage_anchor",
        claim_summary="魏徵劝李世民斥退阎立本，李世民因其强济而未斥。",
    )

    member = tool.claim_member(row)

    assert member["negative_support"] == "negative_context_without_damage_anchor"
    assert member["member_role"] == "direct_material_candidate"


def test_same_biography_many_independent_merits_stays_context_bundle() -> None:
    claims = [
        claim(
            claim_key="CLMK-ZL-1",
            emperor_name="刘邦",
            object_name="张良",
            action_type="纳谏",
            event_scope="军事",
            office_or_domain="入关攻秦",
            time_context="秦二世三年六月",
            outcome="刘邦还军围宛",
            actor="张良",
            fact_object="刘邦",
            claim_summary="张良在刘邦入关途中谏称若不先下宛，刘邦遂还军围宛。",
            source_slice_refs=["OSS-ZL"],
            document_codes=["OSD-ZL"],
        ),
        claim(
            claim_key="CLMK-ZL-2",
            emperor_name="刘邦",
            object_name="张良",
            action_type="纳谏",
            event_scope="军事",
            office_or_domain="追击项羽战略",
            time_context="汉高祖四年九月鸿沟约后",
            outcome="刘邦从其计继续追楚",
            actor="张良",
            fact_object="刘邦",
            claim_summary="鸿沟议和后刘邦欲西归，张良、陈平劝其追取项羽，刘邦遣使并听从。",
            source_slice_refs=["OSS-ZL"],
            document_codes=["OSD-ZL"],
        ),
        claim(
            claim_key="CLMK-ZL-3",
            emperor_name="刘邦",
            object_name="张良",
            action_type="纳谏",
            event_scope="中枢",
            office_or_domain="定都长安",
            time_context="刘邦即皇帝位后",
            outcome="车驾西都长安",
            actor="张良",
            fact_object="刘邦",
            claim_summary="刘邦定都洛阳后询问张良，张良支持入关定都之策，使车驾西都长安。",
            source_slice_refs=["OSS-ZL"],
            document_codes=["OSD-ZL"],
        ),
    ]

    candidates = tool.build_chain_candidates(claims)

    assert len(candidates) == 1
    assert candidates[0]["chain_strength"] == "context_bundle"
    assert candidates[0]["route_readiness"] == "context_only_do_not_route_as_chain"
    assert candidates[0]["chain_type"] == "multi_claim_context_bundle"


def test_generic_death_or_battle_words_do_not_create_terminal_or_damage_roles() -> None:
    death = claim(
        claim_key="CLMK-DEATH",
        action_type="其他",
        time_context="魏徵薨后",
        outcome="李世民追称魏徵为一镜",
        claim_summary="魏徵薨后，李世民追称其为可明得失的一镜。",
    )
    battle = claim(
        claim_key="CLMK-BATTLE",
        action_type="纳谏",
        actor="张良",
        fact_object="刘邦",
        outcome="韩信、彭越皆引兵来",
        claim_summary="固陵战败后，张良建议刘邦以土地许韩信、彭越，使其各自为战。",
    )

    assert tool.member_role(death) == "direct_material_candidate"
    assert tool.member_role(battle) == "direct_material_candidate"


def test_time_model_allows_missing_member_times_when_chain_has_enough_anchors() -> None:
    claims = [
        claim(
            claim_key="CLMK-A",
            action_type="任命",
            time_context="洪武三年",
            office_or_domain="中书省参知政事",
            claim_summary="洪武三年，胡惟庸被拜为中书省参知政事。",
        ),
        claim(
            claim_key="CLMK-B",
            action_type="授权",
            time_context="",
            outcome="胡惟庸独专省事",
            claim_summary="胡惟庸一度独专中书省事。",
        ),
        claim(
            claim_key="CLMK-C",
            action_type="其他",
            time_context="独相数岁期间",
            actor="胡惟庸",
            fact_object="内外诸司封事",
            outcome="害己者被隐匿不上闻",
            claim_summary="独相数岁期间，胡惟庸遇到害己封事就隐匿不上闻。",
        ),
        claim(
            claim_key="CLMK-D",
            action_type="处置",
            time_context="最终",
            outcome="胡惟庸坐叛逆诛死",
            claim_summary="胡惟庸最终因叛逆罪被诛死。",
        ),
    ]

    chain = tool.build_chain_candidates(claims)[0]
    missing_time_member = next(member for member in chain["members"] if member["claim_key"] == "CLMK-B")

    assert missing_time_member["time_anchor_role"] == "none"
    assert chain["time_model"]["precision"] == "mixed"
    assert chain["time_model"]["ordered_enough"] is True


def test_same_document_candidate_is_not_promoted_directly_to_strong_chain() -> None:
    claims = [
        claim(
            claim_key="CLMK-A",
            action_type="任命",
            time_context="洪武三年",
            claim_summary="洪武三年，胡惟庸被拜为中书省参知政事。",
            source_slice_refs=["OSS-A"],
            document_codes=["OSD-HWY"],
        ),
        claim(
            claim_key="CLMK-B",
            action_type="授权",
            time_context="洪武六年正月后",
            office_or_domain="中书省事",
            outcome="胡惟庸独专省事",
            claim_summary="胡惟庸一度独专中书省事。",
            source_slice_refs=["OSS-B"],
            document_codes=["OSD-HWY"],
        ),
        claim(
            claim_key="CLMK-C",
            action_type="其他",
            time_context="独相数岁期间",
            office_or_domain="奏章处理",
            actor="胡惟庸",
            fact_object="内外诸司封事",
            outcome="害己者被隐匿不上闻",
            claim_summary="胡惟庸遇到害己封事就隐匿不上闻。",
            source_slice_refs=["OSS-C"],
            document_codes=["OSD-HWY"],
        ),
        claim(
            claim_key="CLMK-D",
            action_type="处置",
            time_context="最终",
            office_or_domain="叛逆处置",
            outcome="胡惟庸坐叛逆诛死",
            claim_summary="胡惟庸最终因叛逆罪被诛死。",
            source_slice_refs=["OSS-D"],
            document_codes=["OSD-HWY"],
        ),
    ]

    candidates = tool.build_chain_candidates(claims)

    assert candidates[0]["candidate_basis"] == "same_document"
    assert candidates[0]["chain_strength"] == "probable_chain"
    assert candidates[0]["route_readiness"] == "needs_light_chain_judge"


def test_markdown_report_contains_samples() -> None:
    report = tool.build_report(
        [
            claim(claim_key="CLMK-A", action_type="任命", time_context="洪武三年", claim_summary="洪武三年拜官。"),
            claim(claim_key="CLMK-B", action_type="授权", outcome="胡惟庸独专省事", claim_summary="胡惟庸独专省事。"),
            claim(
                claim_key="CLMK-C",
                action_type="其他",
                actor="胡惟庸",
                fact_object="中枢政务",
                outcome="生杀黜陟不奏径行",
                claim_summary="生杀黜陟不奏径行。",
            ),
        ],
        sample_limit=1,
    )

    markdown = tool.markdown_report(report)

    assert "Claim Chain Candidate Report" in markdown
    assert "CLMK-A" in markdown
    assert "write_db: `False`" in markdown


def test_chain_candidate_fetch_stays_on_direction_free_atomic_view() -> None:
    source = (tool.ROOT / "scripts/dev/retrieval_v3_claim_chain_candidates.py").read_text(encoding="utf-8")

    assert "from retrieval_v3.claim_atomic_facts c" in source
    assert "c.atomic_fact_payload" in source
    assert "direction::text as direction" not in source
    assert "join retrieval_v3.claim_cache" not in source
    assert "claim_cache.direction" not in source
