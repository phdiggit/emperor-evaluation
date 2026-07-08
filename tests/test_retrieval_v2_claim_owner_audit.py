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
