from __future__ import annotations

import pytest

from scripts.dev import i5b_finite_values as values


def test_period_aliases_normalize_to_canonical_values() -> None:
    assert values.normalize_period_alias("Qing") == "清"
    assert values.normalize_period_alias("Northern Song") == "北宋"
    assert values.normalize_period_alias("唐、武周") == "武周"


def test_require_canonical_period_rejects_unknown_text() -> None:
    with pytest.raises(values.FiniteValueError, match="unsupported period"):
        values.require_canonical_period("Neo-Qing", field_name="period")


def test_require_choice_rejects_unknown_rule_and_attr_values() -> None:
    with pytest.raises(values.FiniteValueError, match="rule_code"):
        values.require_choice("TODO_RULE_CODE", choices=values.I5B_RULE_CODES, field_name="rule_code")

    with pytest.raises(values.FiniteValueError, match="attr_code"):
        values.require_choice("free_text_level", choices=values.OBJECT_ATTR_CODES, field_name="attr_code")


def test_object_alias_finite_values_are_registered() -> None:
    assert values.require_choice("temple_name", choices=values.OBJECT_ALIAS_KINDS, field_name="alias_kind") == "temple_name"
    assert values.require_choice("emperor", choices=values.OBJECT_ALIAS_SCOPES, field_name="scope") == "emperor"


def test_direction_sets_separate_source_links_from_cluster_signals() -> None:
    assert "neutral" in values.ALLOWED_DIRECTIONS
    assert "neutral" not in values.CLUSTER_DIRECTIONS
    assert values.require_direction("mixed") == "mixed"


def test_talent_quality_rank_keeps_legacy_label_compatible_but_not_canonical() -> None:
    assert values.talent_quality_rank("高质量人才") == 3
    assert values.talent_quality_polarity("高质量人才") == "positive"
    with pytest.raises(values.FiniteValueError, match="unsupported value"):
        values.require_talent_quality("高质量人才")


def test_team_person_name_strips_phase_suffix_only() -> None:
    assert values.normalize_team_person_name("姚崇早期") == "姚崇"
    assert values.normalize_team_person_name("早期") == "早期"
