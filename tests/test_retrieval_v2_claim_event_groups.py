from __future__ import annotations

from scripts.dev import retrieval_v2_claim_event_groups as tool
from scripts.dev import retrieval_v2_claim_quality as quality


def claim(**overrides):
    row = {
        "claim_key": "CLMK-001",
        "emperor_name": "李世民",
        "object_name": "萧瑀",
        "object_type": "person",
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
    first = claim()
    second = claim(claim_summary="萧瑀奏称房玄龄以下内臣结为朋党。")

    assert quality.claim_outcome_support(second) == "missing"
    assert quality.claim_usage_role_hint(second) == "supporting_context"
    assert quality.event_group_payload(first) == quality.event_group_payload(second)
    assert quality.event_group_key(first) == quality.event_group_key(second)
    assert "direction" not in quality.event_group_payload(second)


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
    assert built["members"][0]["member_payload"]["negative_support"]["support"] == "not_applicable"
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


def test_owner_scope_values_default_to_target_emperor() -> None:
    assert tool.owner_scope_values([]) == ["target_emperor"]
    assert tool.owner_scope_values(["external_or_unregistered_owner", "target_emperor"]) == [
        "external_or_unregistered_owner",
        "target_emperor",
    ]


def test_event_group_fetch_uses_owner_scope_view_without_prompt_cost() -> None:
    source = (tool.ROOT / "scripts/dev/retrieval_v2_claim_event_groups.py").read_text(encoding="utf-8")
    prompt_source = (tool.ROOT / "scripts/dev/retrieval_v2_candidate_prompt.py").read_text(encoding="utf-8")

    assert "claim_owner_scopes" in source
    assert "os.owner_scope = any(%s)" in source
    assert "c.last_run_code = any(%s)" in source
    assert "c.atomic_fact_payload" in source
    assert "c.event_group_payload" in source
    assert "direction::text as direction" not in source
    assert "join retrieval_v2.claim_cache cc" not in source
    assert "--owner-scope" in source
    assert "--last-run-code" in source
    assert "--replace-existing" in source
    assert "claim_owner_scopes" not in prompt_source
    assert "external_or_unregistered_owner" not in prompt_source


def test_claim_member_row_uses_atomic_negative_support_without_direction() -> None:
    row = claim(
        atomic_fact_payload={"negative_support": "governance_damage_supported", "outcome_support": "direct"},
        event_group_key="CEG-STORED",
        event_group_payload={"object_name": "萧瑀"},
        fact_type="material_action",
        outcome_support="direct",
    )

    member = tool.claim_member_row(row)
    seed = tool.claim_group_seed(row)

    assert member["group_key"] == "CEG-STORED"
    assert member["member_payload"]["negative_support"]["support"] == "governance_damage_supported"
    assert member["member_payload"]["atomic_fact_payload"]["negative_support"] == "governance_damage_supported"
    assert seed["group_key"] == "CEG-STORED"
    assert seed["group_payload"] == {"object_name": "萧瑀"}


class CaptureCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[object] = []
        self.rowcount = 0

    def execute(self, sql: str, params=None) -> None:
        normalized = " ".join(sql.split())
        self.statements.append(normalized)
        self.params.append(params)
        if normalized.startswith("delete from retrieval_v2.claim_event_group_members"):
            self.rowcount = 2
        elif normalized.startswith("delete from retrieval_v2.claim_event_groups"):
            self.rowcount = 1
        else:
            self.rowcount = 0


def test_replace_existing_event_groups_deletes_selected_scope_before_rebuild() -> None:
    cur = CaptureCursor()

    deleted = tool.replace_existing_event_groups(cur, owner_scopes=["target_emperor"], emperor_names=["李世民"])

    assert deleted == {"deleted_groups": 1, "deleted_members": 2}
    assert cur.statements[0].startswith("delete from retrieval_v2.claim_event_group_members")
    assert cur.statements[1].startswith("delete from retrieval_v2.claim_event_groups")
    assert cur.params[0] == [["target_emperor"], ["李世民"]]
    assert cur.params[1] == [["target_emperor"], ["李世民"]]
