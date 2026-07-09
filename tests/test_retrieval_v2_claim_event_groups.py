from __future__ import annotations

from scripts.dev import retrieval_v2_claim_event_groups as tool
from scripts.dev import retrieval_v2_claim_quality as quality


def claim(**overrides):
    row = {
        "claim_key": "CLMK-001",
        "emperor_name": "李世民",
        "object_name": "萧瑀",
        "object_type": "person",
        "direction": "neutral",
        "action_type": "处置",
        "event_scope": "中枢",
        "office_or_domain": "中书门下",
        "time_context": "贞观时",
        "outcome": "",
        "claim_summary": "萧瑀上奏称房玄龄以下内臣结为朋党。",
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "萧瑀",
            "object": "房玄龄以下内臣",
            "action_type": "处置",
            "event_scope": "中枢",
            "office_or_domain": "中书门下",
            "time_context": "贞观时",
            "completeness": {"has_outcome": False},
        },
        "status": "active",
    }
    row.update(overrides)
    return row


def test_claim_quality_builds_direction_free_event_group_payload() -> None:
    negative = claim(direction="negative")
    neutral = claim(direction="neutral")

    assert quality.claim_outcome_support(neutral) == "missing"
    assert quality.claim_usage_role_hint(neutral) == "supporting_context"
    assert quality.event_group_payload(negative) == quality.event_group_payload(neutral)
    assert quality.event_group_key(negative) == quality.event_group_key(neutral)
    assert "direction" not in quality.event_group_payload(neutral)


def test_claim_quality_marks_direct_outcome_as_direct_material_candidate() -> None:
    row = claim(
        claim_summary="萧瑀弹劾房玄龄，所劾之罪最终不问，萧瑀被罢御史大夫。",
        outcome="罢御史大夫",
        fact_payload={
            "fact_schema": "political_action_v1",
            "actor": "萧瑀",
            "object": "房玄龄",
            "action_type": "处置",
            "completeness": {"has_outcome": True},
        },
    )

    assert quality.claim_outcome_support(row) == "direct"
    assert quality.claim_usage_role_hint(row) == "direct_material_candidate"


def test_build_event_groups_keeps_action_only_claims_as_supporting_context() -> None:
    rows = [
        claim(claim_key="CLMK-ACTION"),
        claim(
            claim_key="CLMK-RESULT",
            outcome="不问",
            claim_summary="萧瑀弹劾房玄龄以下内臣，所劾之罪最终不问。",
            fact_payload={
                "fact_schema": "political_action_v1",
                "actor": "萧瑀",
                "object": "房玄龄以下内臣",
                "action_type": "处置",
                "event_scope": "中枢",
                "office_or_domain": "中书门下",
                "time_context": "贞观时",
                "outcome": "不问",
                "completeness": {"has_outcome": True},
            },
        ),
    ]

    built = tool.build_event_groups(rows)
    assert len(built["groups"]) == 1
    assert len(built["members"]) == 2
    assert "direction_hint" not in built["members"][0]["member_payload"]
    group = built["groups"][0]
    assert group["outcome_support_summary"] == {"direct": 1, "missing": 1}
    assert group["usage_summary"] == {"direct_material_candidate": 1, "supporting_context": 1}
    assert tool.group_category(group) == "action_only_with_result_claims"


def test_summarize_event_groups_counts_action_only_context() -> None:
    built = tool.build_event_groups([claim(claim_key="CLMK-ACTION")])

    summary = tool.summarize_event_groups(built["groups"], built["members"])

    assert summary["totals"]["event_groups"] == 1
    assert summary["totals"]["action_only_context_groups"] == 1
    assert summary["object_context"][0]["object_name"] == "萧瑀"
    assert summary["object_context"][0]["action_only_context_groups"] == 1
    assert summary["sample_groups"][0]["category"] == "action_only_context"


def test_claim_group_seed_has_clean_action_fields() -> None:
    seed = tool.claim_group_seed(claim())

    assert seed["emperor_name"] == "李世民"
    assert seed["object_name"] == "萧瑀"
    assert seed["fact_type"] == "material_action"
    assert seed["action_type"] == "处置"
    assert seed["event_scope"] == "中枢"
