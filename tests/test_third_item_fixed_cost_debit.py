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


def test_contract_keeps_factor_anchors_and_converts_them_to_fixed_points():
    path = ROOT / "config/third-item/third-item-cost-credit-factors.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    factors = contract["factor_by_global_cost_band_and_position"]
    anchors = {
        ("C4", "LOW"): (0.90625, 7.5),
        ("C4", "MID"): (0.875, 10.0),
        ("C4", "HIGH"): (0.84375, 12.5),
        ("C5", "LOW"): (0.7975, 16.2),
        ("C5", "MID"): (0.745, 20.4),
        ("C5", "HIGH"): (0.6925, 24.6),
        ("C6", "LOW"): (0.62375, 30.1),
        ("C6", "MID"): (0.545, 36.4),
        ("C6", "HIGH"): (0.44875, 44.1),
        ("C7", "LOW"): (0.35, 52.0),
        ("C7", "MID"): (0.24, 60.8),
        ("C7", "HIGH"): (0.120, 70.4),
        ("C7", "HIGHEST"): (0.000, 80.0),
    }
    for (band, position), (factor, debit) in anchors.items():
        assert factors[band][position] == factor
        assert round(80 * (1 - factor), 2) == debit

    ml_policy = json.loads(
        (ROOT / "config/third-item/third-item-military-net-loss-penalties.json").read_text(
            encoding="utf-8"
        )
    )["policy"]
    assert ml_policy == {"ML0": 0, "ML1": -20, "ML2": -40, "ML3": -60, "ML4": -80}


def test_formal_markdown_is_exact_render_of_json():
    payload = _payload()
    markdown = (ROOT / FORMAL_PATH.with_suffix(".md")).read_text(encoding="utf-8")
    assert markdown == _render_current_weighted_markdown(payload["records"])
