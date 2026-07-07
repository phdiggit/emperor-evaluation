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


def test_calculate_formula_reports_raw_signal_without_fixed_response() -> None:
    tool = load_tool()
    signals = {
        "tolerate_talent": tool.RuleSignals(
            positive_signal=Decimal("1.300"),
            negative_signal=Decimal("4.033"),
            cluster_id=172,
        )
    }

    result = tool.calculate_formula(signals=signals)

    assert result["formula_stage"] == "raw_signal_only"
    assert result["dynamic_mapping_required"] is True
    assert result["score"] is None
    assert result["tier"] is None
    assert "positive_response_cap" not in result
    assert result["rules"]["tolerate_talent"]["rule_raw_net"] == "-2.733"
    assert result["rules"]["tolerate_talent"]["rule_weight"] == "0.180"
    assert result["rules"]["tolerate_talent"]["weighted_raw_signal"] == "-0.492"
    assert result["weighted_raw_signal"] == "-0.492"
    assert "penalty_rate" not in result
    assert "severe_negative_excess" not in result


def test_negative_raw_signal_is_not_response_capped() -> None:
    tool = load_tool()
    signals = {
        "appointment_delegation": tool.RuleSignals(
            positive_signal=Decimal("0.000"),
            negative_signal=Decimal("8.000"),
            cluster_id=161,
        )
    }

    result = tool.calculate_formula(signals=signals)

    assert result["rules"]["appointment_delegation"]["rule_raw_net"] == "-8.000"
    assert result["rules"]["appointment_delegation"]["weighted_raw_signal"] == "-2.880"
    assert result["weighted_raw_signal"] == "-2.880"


def test_calculate_formula_marks_missing_rule_as_no_material() -> None:
    tool = load_tool()

    result = tool.calculate_formula(signals={})

    assert result["rules"]["anti_nepotism"]["no_material"] is True
    assert result["rules"]["anti_nepotism"]["positive_signal"] == "0.000"
    assert result["rules"]["anti_nepotism"]["negative_signal"] == "0.000"


def test_fixed_tier_mapping_is_removed() -> None:
    tool = load_tool()

    assert not hasattr(tool, "tier_for_rate")


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
