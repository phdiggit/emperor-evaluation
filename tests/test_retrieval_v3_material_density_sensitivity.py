from __future__ import annotations

from decimal import Decimal

from scripts.dev import retrieval_v3_material_density_sensitivity as tool


def material(claim: str, event: str, score: str, *, object_id: int = 1, side: str = "positive") -> dict:
    return {
        "claim_key": claim, "event_group_keys": [event], "abs_score": score,
        "object_id": object_id, "binding_code": f"B-{claim}", "side": side,
    }


def test_rank_decay_accounts_for_every_material_without_cap() -> None:
    result = tool.aggregate_side(
        [material("C1", "E1", "2"), material("C2", "E1", "1"), material("C3", "E2", "1")],
        material_decay=Decimal("1"), event_decay=Decimal("1"), object_decay=Decimal("0.5"),
    )

    assert result["material_count"] == 3
    assert result["event_count"] == 2
    assert result["all_materials_accounted"] is True
    assert Decimal(result["minimum_material_stage_weight"]) > 0
    assert Decimal(result["signal"]) == Decimal("3.000")
    accounted_claims = {
        component["claim_key"]
        for event in result["event_rows"]
        for component in event["material_components"]
    }
    assert accounted_claims == {"C1", "C2", "C3"}


def test_adding_weak_material_has_strictly_positive_marginal_contribution() -> None:
    base = tool.aggregate_side(
        [material("C1", "E1", "2")],
        material_decay=Decimal("1"), event_decay=Decimal("1"), object_decay=Decimal("1"),
    )
    thickened = tool.aggregate_side(
        [material("C1", "E1", "2"), material("C2", "E1", "0.2")],
        material_decay=Decimal("1"), event_decay=Decimal("1"), object_decay=Decimal("1"),
    )

    assert Decimal(thickened["signal"]) > Decimal(base["signal"])


def test_report_is_read_only_and_never_drops_materials() -> None:
    details = {"T": {
        "emperor_name": "甲", "positive_signal": "2", "negative_signal": "0",
        "calc_detail": {
            "materials": [material("C1", "E1", "2")],
            "object_side_scores": {"positive": {"1": {}}, "negative": {}},
        },
    }}
    report = tool.build_sensitivity_report(score_details=details, emperors=["甲"])

    assert report["write_db"] is False
    assert report["scale_scope"] == "three_emperor_lane_totals_preserved_for_sensitivity_only"
    assert report["formal_score_changed"] is False
    assert report["all_scored_materials_must_contribute"] is True
    assert all(row["drops_scored_materials"] is False for row in report["scenarios"])
    assert all(row["hard_cap_applied"] is False for row in report["scenarios"])
