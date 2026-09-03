import json
from pathlib import Path

from emperor_v4.evaluation.third_item_current_settlement import (
    FORMAL_PATH,
    _render_current_weighted_markdown,
)


ROOT = Path(__file__).resolve().parents[1]


def _payload():
    return json.loads((ROOT / FORMAL_PATH).read_text(encoding="utf-8"))


def test_fixed_cost_debit_and_ml_take_higher_for_full_pool():
    for row in _payload()["records"]:
        if row["third_item_score_points"] is None:
            continue
        cost = round(80 * (1 - row["cost_credit_factor"]), 2)
        applied = max(cost, abs(row["military_net_loss_penalty"]))
        assert row["cost_debit_points"] == cost
        assert row["applied_military_debit_points"] == applied
        assert row["third_item_score_points"] == round(
            row["A120_score_points"] + row["B80_score_points"] + row["C50_score_points"] - applied,
            2,
        )


def test_fixed_cost_debit_pressure_samples():
    rows = {row["ruler_name"]: row for row in _payload()["records"]}
    expected = {
        "李世民": 237.36,
        "刘彻": 151.87,
        "弘历": 150.84,
        "朱棣": 108.68,
        "杨广": -35.70,
    }
    assert {name: rows[name]["third_item_score_points"] for name in expected} == expected
    assert rows["杨广"]["applied_military_debit_source"] == "COST_AND_ML_EQUAL"


def test_contract_keeps_factor_anchors_and_converts_them_to_fixed_points():
    path = ROOT / "config/third-item/third-item-cost-credit-factors.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    factors = contract["factor_by_global_cost_band_and_position"]
    anchors = {
        ("C4", "MID"): (0.900, 8.0),
        ("C4", "HIGH"): (0.875, 10.0),
        ("C5", "HIGH"): (0.795, 16.4),
        ("C6", "MID"): (0.740, 20.8),
        ("C6", "HIGH"): (0.685, 25.2),
        ("C7", "HIGH"): (0.560, 35.2),
        ("C7", "HIGHEST"): (0.500, 40.0),
    }
    for (band, position), (factor, debit) in anchors.items():
        assert factors[band][position] == factor
        assert round(80 * (1 - factor), 2) == debit


def test_formal_markdown_is_exact_render_of_json():
    payload = _payload()
    markdown = (ROOT / FORMAL_PATH.with_suffix(".md")).read_text(encoding="utf-8")
    assert markdown == _render_current_weighted_markdown(payload["records"])
