from __future__ import annotations

from scripts.dev import retrieval_v3_material_candidate_plan as tool


def test_build_plan_routes_rule_after_neutral_material_intake() -> None:
    payload = tool.build_plan(
        [
            {
                "claim_code": "CLM-1",
                "source_pack_code": "SPK-1",
                "emperor_name": "李世民",
                "object_name": "王珪",
                "claim_summary": "李世民任王珪为魏王师并明确要求辅导李泰。",
            },
            {
                "claim_code": "CLM-2",
                "source_pack_code": "SPK-1",
                "emperor_name": "李世民",
                "object_name": "某人",
                "claim_summary": "某人家世与籍贯记载。",
            },
        ]
    )

    assert payload["input_material_claims"] == 2
    assert payload["candidate_count"] == 1
    assert payload["unrouted_count"] == 1
    assert payload["write_db"] is False
    candidate = payload["candidates"][0]
    assert candidate["candidate_rule_code"] == "appointment_delegation"
    assert candidate["candidate_payload"]["material_scope"] == "rule_neutral"
    assert candidate["candidate_payload"]["formal_binding_allowed"] is False


def test_build_plan_is_deterministic_for_duplicate_material_rows() -> None:
    row = {
        "claim_code": "CLM-1",
        "source_pack_code": "SPK-1",
        "emperor_name": "朱元璋",
        "object_name": "胡惟庸",
        "claim_summary": "朱元璋任胡惟庸为丞相并长期宠任。",
    }
    payload = tool.build_plan([row, row])

    assert payload["candidate_count"] == 1
    assert payload["unrouted_count"] == 0
