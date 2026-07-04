from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "build" / "i5b_item_result_calculator.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_item_result_calculator_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_calculate_formula_uses_v9_negative_rollback_response() -> None:
    tool = load_tool()
    signals = {
        "tolerate_talent": tool.RuleSignals(
            positive_signal=Decimal("1.300"),
            negative_signal=Decimal("4.033"),
            cluster_id=172,
        )
    }

    result = tool.calculate_formula(signals=signals)

    assert result["positive_response_cap"] == "5.5"
    assert result["negative_response_cap"] == "7.0"
    assert result["negative_response_tau"] == "4.0"
    assert result["rules"]["tolerate_talent"]["positive_effect"] == "1.706"
    assert result["rules"]["tolerate_talent"]["negative_effect"] == "4.446"
    assert result["rules"]["tolerate_talent"]["rule_net_effect"] == "-2.740"
    assert result["rules"]["tolerate_talent"]["rule_weight"] == "0.180"
    assert "penalty_rate" not in result
    assert "severe_negative_excess" not in result


def test_negative_response_still_can_exceed_four_point_cap() -> None:
    tool = load_tool()
    signals = {
        "appointment_trust": tool.RuleSignals(
            positive_signal=Decimal("0.000"),
            negative_signal=Decimal("8.000"),
            cluster_id=161,
        )
    }

    result = tool.calculate_formula(signals=signals)

    assert result["rules"]["appointment_trust"]["negative_effect"] == "6.053"
    assert result["rules"]["appointment_trust"]["rule_net_effect"] == "-6.053"


def test_calculate_formula_marks_missing_rule_as_no_material() -> None:
    tool = load_tool()

    result = tool.calculate_formula(signals={})

    assert result["rules"]["anti_nepotism"]["no_material"] is True
    assert result["rules"]["anti_nepotism"]["positive_signal"] == "0.000"
    assert result["rules"]["anti_nepotism"]["negative_signal"] == "0.000"


def test_tier_for_rate_has_no_decimal_boundary_gaps() -> None:
    tool = load_tool()

    assert tool.tier_for_rate(Decimal("0.8956")) == ("优秀", "高段")
    assert tool.tier_for_rate(Decimal("0.5927")) == ("一般", "高段")


def test_parser_requires_at_least_one_emperor() -> None:
    tool = load_tool()
    parser = tool.build_parser()

    try:
        parser.parse_args([])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover
        raise AssertionError("argparse should reject missing --emperor")


def test_legacy_jsonl_log_entrypoint_is_removed() -> None:
    tool = load_tool()
    parser = tool.build_parser()
    options = {option for action in parser._actions for option in action.option_strings}

    assert "--log" not in options
    assert not hasattr(tool, "append_calc_log")
