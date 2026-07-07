from __future__ import annotations

from scripts.dev import retrieval_v2_cross_rule_router as tool


def source_row(**overrides):
    row = {
        "target_id": 1,
        "target_code": "TGT-I5B-LB",
        "emperor_name": "刘邦",
        "item_code": "I5B",
        "source_pack_id": 10,
        "source_pack_code": "SPK-I5B-LB-DELEGATION-A",
        "claim_id": 100,
        "claim_code": "SPK-I5B-LB-DELEGATION-A::CLM-001",
        "object_name": "韩信",
        "object_group_key": "韩信",
        "claim_summary": "刘邦任韩信为左丞相击魏，又给兵北举燕赵、东击齐。",
        "claim_summary_hash": "HASH-001",
        "source_contract_rule_id": 20,
        "source_rule_code": "appointment_delegation",
        "predicate": "delegated_authority",
        "object_role": "military_delegate",
        "binding_direction": "positive",
        "binding_payload": {},
    }
    row.update(overrides)
    return row


def test_route_claim_emits_formal_appointment_and_team_candidates() -> None:
    routes = {route.rule_code: route for route in tool.route_claim(source_row())}

    assert {"team_building"} <= set(routes)
    assert routes["team_building"].future_hint is False


def test_disposition_claim_is_tolerate_candidate_with_caution_not_scoring_direction() -> None:
    row = source_row(
        object_name="彭越",
        claim_summary="陈豨反时刘邦征梁兵，彭越称病仅遣兵，后被捕废为庶人并遭诛族。",
        claim_summary_hash="HASH-PY",
        predicate="revoked_authority",
        object_role="revoked_or_failed_delegate",
        binding_direction="negative",
    )
    routes = {route.rule_code: route for route in tool.route_claim(row)}
    candidate = tool.candidate_row({**row, "candidate_contract_rule_id": 21}, routes["tolerate_talent"])

    assert candidate["candidate_rule_code"] == "tolerate_talent"
    assert candidate["candidate_lane"] == "I5B.tolerate_talent"
    assert candidate["hint_status"] == "current_rule_candidate"
    assert candidate["required_facts_present"]["source_claim"] is True
    assert candidate["routed_by_profile"] == "retrieval_v2_cross_rule_router"
    assert candidate["candidate_direction"] is None
    assert "不单凭处置结果定为负向" in candidate["candidate_payload"]["caution"]
    assert candidate["candidate_payload"]["hint_status"] == "current_rule_candidate"


def test_attacked_talent_protection_routes_to_tolerate_candidate() -> None:
    row = source_row(
        object_name="陈平",
        claim_summary="或言陈平盗嫂受金，刘邦不疑，卒复用陈平。",
        claim_summary_hash="HASH-CP",
        predicate="appointed_or_delegated_authority",
        object_role="trusted_minister",
        binding_direction="positive",
    )
    routes = {route.rule_code: route for route in tool.route_claim(row)}

    assert "tolerate_talent" in routes
    assert {"盗嫂", "受金"} <= set(routes["tolerate_talent"].terms)


def test_future_hints_are_marked_and_do_not_get_contract_rule_id() -> None:
    row = source_row(
        object_name="隆科多",
        claim_summary="隆科多因专擅结党、受贿欺罔等被削职夺爵并禁锢。",
        claim_summary_hash="HASH-LKD",
        predicate="revoked_authority",
        binding_direction="negative",
    )
    routes = {route.rule_code: route for route in tool.route_claim(row)}
    formal = tool.candidate_row({**row, "candidate_contract_rule_id": 22}, routes["anti_nepotism"])
    future = tool.candidate_row({**row, "candidate_contract_rule_id": 99}, routes["inner_favorite_power_control"])

    assert formal["candidate_rule_code"] == "anti_nepotism"
    assert formal["candidate_contract_rule_id"] == 22
    assert future["candidate_rule_code"] == "inner_favorite_power_control"
    assert future["candidate_contract_rule_id"] is None
    assert future["candidate_lane"] == "inner_favorite_power_control"
    assert future["hint_status"] == "future_rule_hint"
    assert future["candidate_payload"]["hint_status"] == "future_rule_hint"


def test_cross_item_future_hint_terms_route_to_generic_lanes() -> None:
    row = source_row(
        object_name="某臣",
        claim_summary="帝因边疆失地与徭役横征，问策某臣，遂罢兵议和班师。",
        claim_summary_hash="HASH-FUTURE",
        predicate="appointed_or_delegated_authority",
        object_role="trusted_minister",
        binding_direction="neutral",
    )
    routes = {route.rule_code: route for route in tool.route_claim(row)}

    assert "cognition_learning" in routes
    assert "key_decision" in routes
    assert "military_frontier_result" in routes
    assert "historical_debt" in routes
    assert routes["cognition_learning"].future_hint is True
    assert routes["key_decision"].future_hint is True
    assert {"问策"} <= set(routes["cognition_learning"].terms)
    assert {"罢兵", "议和", "班师"} <= set(routes["key_decision"].terms)
    assert {"徭役", "横征"} <= set(routes["historical_debt"].terms)


def test_dedupe_candidates_keeps_one_semantic_candidate_per_rule() -> None:
    row_a = source_row(source_pack_id=10, claim_id=100, claim_code="A::CLM-001")
    row_b = source_row(source_pack_id=11, claim_id=101, claim_code="B::CLM-001")
    route = tool.RouteSpec("appointment_delegation", ("任用/信任/撤任事实",), ("任",))
    candidates = [
        tool.candidate_row({**row_a, "candidate_contract_rule_id": 21}, route),
        tool.candidate_row({**row_b, "candidate_contract_rule_id": 21}, route),
    ]

    deduped, skipped = tool.dedupe_candidates(candidates, canonical_only=True)

    assert skipped == 1
    assert len(deduped) == 1
    assert deduped[0]["source_pack_id"] == 11


def test_all_duplicates_mode_keeps_every_candidate() -> None:
    route = tool.RouteSpec("appointment_delegation", ("任用/信任/撤任事实",), ("任",))
    candidates = [
        tool.candidate_row({**source_row(claim_id=100, claim_code="A::CLM-001"), "candidate_contract_rule_id": 21}, route),
        tool.candidate_row({**source_row(claim_id=101, claim_code="B::CLM-001"), "candidate_contract_rule_id": 21}, route),
    ]

    deduped, skipped = tool.dedupe_candidates(candidates, canonical_only=False)

    assert skipped == 0
    assert len(deduped) == 2
