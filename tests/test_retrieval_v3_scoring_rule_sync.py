from decimal import Decimal

from scripts.dev import retrieval_v3_scoring_rule_sync as tool


def test_parse_rule_doc_covers_all_i5b_factors_and_weights() -> None:
    factors, weights = tool.parse_rule_doc()

    assert len(factors) == 84
    assert {row.rule_code for row in weights} == tool.RULE_CODES
    assert sum(row.value_num for row in weights) == Decimal("1.00")
    lookup = {(row.rule_code, row.factor_name, row.label): row.value_num for row in factors}
    assert lookup[("team_building", "long_term_stability_factor", "长期稳定核心班底。")] == Decimal("1.1")
    assert lookup[("team_building", "talent_quality_factor", "历史级人才")] == Decimal("1.6")
    assert lookup[("appointment_delegation", "appointment_effect", "长期或国家级错误任用授权造成连续性、结构性、大规模后续损害，或系统性任用污染、表达压制、关键人才损害。")] == Decimal("-2.6")


def test_synthetic_source_ids_are_stable_negative_and_distinct() -> None:
    first = tool.synthetic_source_id("I5B", "team_building", "talent_quality_factor")
    assert first < 0
    assert first == tool.synthetic_source_id("I5B", "team_building", "talent_quality_factor")
    assert first != tool.synthetic_source_id("I5B", "team_building", "long_term_stability_factor")


def test_diff_maps_reports_value_drift() -> None:
    expected = {"a": {"value_num": "1.1"}}
    actual = {"a": {"value_num": "1.15"}}

    result = tool.diff_maps(expected, actual)

    assert result["added"] == []
    assert result["retired"] == []
    assert result["changed"] == [{"key": "a", "fields": {"value_num": {"db": "1.15", "doc": "1.1"}}}]
