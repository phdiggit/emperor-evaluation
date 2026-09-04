from __future__ import annotations


from emperor_v4.evaluation.first_item_settlement import build_first_item_formal_settlement


def test_formal_settlement_propagates_a_b_c_limitations() -> None:
    common = {
        "ruler_id": "RULER-TEST",
        "ruler_name": "测试人物",
        "polity": "测试",
        "reign_range": "1-2",
        "score_applicable": True,
    }
    a_payload = {"schema_version": "a", "records": [{
        **common,
        "scope_status": "ELIGIBLE_DYNASTY_FOUNDER",
        "A1": {"points": 10.0},
        "A2": {"points": 10.0},
        "A_score_points": 20.0,
        "evidence_lower_bound": True,
        "limitations": ["A限制"],
    }]}
    b_payload = {"schema_version": "b", "records": [{
        **common,
        "B1": {"points": 10.0},
        "B2": {"points": 10.0},
        "B_score_points": 20.0,
        "limitations": ["B限制"],
    }]}
    c_payload = {"schema_version": "c", "records": [{
        **common,
        "C1": {"points": 10.0},
        "C2": {"points": 10.0},
        "C_score_points": 20.0,
        "coverage_status": "DEFAULT_ZERO_EVIDENCE_GAP",
        "default_applied": True,
        "default_basis": "C限制",
        "unresolved_gaps": [],
    }]}
    result = build_first_item_formal_settlement(
        a_payload=a_payload, b_payload=b_payload, c_payload=c_payload
    )
    row = result["records"][0]
    assert row["evidence_lower_bound"] is True
    assert row["limitations"] == ["A：A限制", "B：B限制", "C：C限制"]
