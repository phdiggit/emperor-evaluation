from __future__ import annotations

from scripts.dev import retrieval_v3_claim_rule_route_plan as tool


def claim(**overrides):
    row = {
        "claim_key": "CLMK-001",
        "emperor_name": "朱元璋",
        "object_name": "胡惟庸",
        "fact_type": "material_action",
        "action_type": "任命",
        "office_or_domain": "中书省丞相",
        "claim_summary": "朱元璋任命胡惟庸为丞相。",
        "atomic_fact_payload": {
            "actor": "朱元璋",
            "fact_object": "胡惟庸",
            "action_type": "任命",
            "office_or_domain": "中书省丞相",
            "outcome_support": "direct",
        },
    }
    row.update(overrides)
    return row


def test_tolerate_talent_routes_execution_and_imprisonment_terms() -> None:
    for term in ("处斩", "赐死", "下狱", "械系", "籍没"):
        routes = tool.route_claim(claim(claim_summary=f"某功臣被{term}。"))
        tolerate = next(row for row in routes if row["candidate_rule_code"] == "tolerate_talent")
        assert any(token in term or term in token for token in tolerate["reason_codes"])


def test_route_claim_uses_mechanical_appointment_and_team_signals() -> None:
    routes = tool.route_claim(claim())

    by_rule = {row["candidate_rule_code"]: row for row in routes}
    assert by_rule["appointment_delegation"]["route_status"] == "mechanical_current_rule_candidate"
    assert by_rule["team_building"]["route_status"] == "defer_to_object_pool"
    assert by_rule["appointment_delegation"]["formal_binding_allowed"] is False


def test_route_claim_sends_ambiguous_tolerance_and_nepotism_to_light_review() -> None:
    routes = tool.route_claim(
        claim(
            claim_key="CLMK-002",
            action_type="其他",
            office_or_domain="",
            claim_summary="权臣近臣结党纳贿，后被罢免。",
            atomic_fact_payload={"actor": "权臣", "fact_object": "近臣", "action_type": "其他"},
        )
    )

    assert {row["candidate_rule_code"] for row in routes} == {"tolerate_talent", "anti_nepotism"}
    assert {row["route_status"] for row in routes} == {"needs_light_rule_review"}


def test_route_chain_only_promotes_relevant_appointment_chains() -> None:
    routes = tool.route_chain(
        {
            "chain_key": "CCG-001",
            "emperor_name": "朱元璋",
            "object_name": "胡惟庸",
            "chain_type": "delegated_power_abuse_chain",
            "chain_strength": "strong_chain",
            "route_readiness": "ready_for_chain_route_review",
            "member_count": 6,
            "role_family_counts": {"damage": 2},
            "source_slice_refs": ["OSS-001"],
        }
    )

    assert routes[0]["candidate_rule_code"] == "appointment_delegation"
    assert routes[0]["route_status"] == "ready_for_rule_route_review"
    assert tool.route_chain({"chain_type": "multi_claim_context_bundle"}) == []


def test_build_plan_keeps_claim_routes_and_chain_routes_separate() -> None:
    plan = tool.build_plan([claim()], min_members=3)

    assert plan["write_db"] is False
    assert plan["formal_binding_allowed"] is False
    assert plan["candidate_rule_counts"]["appointment_delegation"] == 1
    assert plan["candidate_rule_counts"]["team_building"] == 1


def test_route_claim_recognizes_summoned_tested_and_personally_noticed_talent() -> None:
    routes = tool.route_claim(claim(
        object_name="夏原吉",
        action_type="任命",
        office_or_domain="户部主事",
        claim_summary="朱元璋见夏原吉危坐俨然而异之，遂擢为户部主事。",
        atomic_fact_payload={"actor": "朱元璋", "fact_object": "夏原吉", "action_type": "任命"},
    ))
    assert "talent_discovery" in {row["candidate_rule_code"] for row in routes}
