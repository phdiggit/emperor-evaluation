from copy import deepcopy
from math import isclose
import pytest
from emperor_v4.evaluation.talent_registry_store import talent_profiles_by_ref

from emperor_v4.evaluation.military_talent_value import (
    display_entries, episode_anchors, net_value, refresh_values, result_value, stability_counts, validate_mixed_result, validate_operational_role,
)


def result(ref, tier="A", difficulty="D3", direction="positive", **fields):
    return {"campaign_ref": ref, "capability_episode_ref": ref, "campaign_tier": tier,
            "combat_difficulty": difficulty, "result_direction": direction,
            "consumption_mode": "person_result", "capability_mode": "integrated_command",
            "decisive_relation": "decisive_creator", **fields}


def mixed_review():
    return {"decision": "mixed_review", "positive_result": "解围目标实际完成",
            "adverse_result": "同周期另一方向失守", "retention": "解围结果保持，失地未恢复",
            "personal_scope": "本人实际指挥的两个阶段", "source_refs": ["synthetic-source"]}


def operational_review(**overrides):
    return {"status": "QUALIFIED", "constraint": "两路援军无法同时到达",
            "operation": "优先保留渡口预备队并配置两路会合时机", "implementation": "命令采纳后两路按指定时机展开",
            "result_link": "预备队保持渡口并使两路安全会合", "personal_scope": "仅分路与预备队设计",
            "source_refs": ["synthetic-source"], "implemented": True, "outcome_established": True,
            "major_result": True, "failure_established": False, "failure_effect_tier": None, **overrides}


@pytest.mark.parametrize("field", ["operation", "implementation", "result_link", "personal_scope", "source_refs", "implemented", "outcome_established"])
def test_operational_admission_requires_an_implemented_personal_chain(field):
    review = operational_review()
    review.pop(field)
    with pytest.raises(ValueError):
        validate_operational_role(result("synthetic", consumption_mode="operational_result", capability_mode="operational_design",
                                         difficulty=None, operational_role_review=review))


def test_operational_authorization_has_no_credit_and_difficulty_is_not_inherited():
    row = result("synthetic", consumption_mode="operational_result", capability_mode="operational_design", difficulty=None,
                 operational_role_review=operational_review(status="AUTHORIZATION_ONLY"))
    assert result_value(row) == 0
    with pytest.raises(ValueError):
        validate_operational_role(row)
    with pytest.raises(ValueError):
        validate_operational_role({**row, "combat_difficulty": "D3", "operational_role_review": operational_review()})
    assert result_value({**row, "operational_role_review": operational_review(implemented=False)}) == 0
    assert result_value({**row, "operational_role_review": operational_review(outcome_established=False)}) == 0
    with pytest.raises(ValueError):
        validate_operational_role({**row, "operational_role_review": operational_review(major_result=False)})


def test_operational_major_failures_do_not_require_frontline_difficulty():
    positive = result("positive", consumption_mode="operational_result", capability_mode="operational_design", difficulty=None,
                      operational_role_review=operational_review())
    failure = result("failure", direction="negative", consumption_mode="operational_result", capability_mode="operational_design", difficulty=None,
                     role_code="not_in_command_chain", causal_fault="SUPPORTED_DECISION_RESPONSIBILITY",
                     operational_role_review=operational_review(major_result=False, failure_established=True, failure_effect_tier="A"))
    validate_operational_role(positive)
    validate_operational_role(failure)
    counts = stability_counts({"consumed_achievements": [positive], "negative_or_mixed_command_records": [failure]})
    assert counts["major_positive_context_count"] == counts["major_adverse_context_count"] == 1
    assert counts["operational_responsibility_major_failure_count"] == 1
    assert counts["frontline_major_adverse_context_count"] == 0
    assert counts["combined_major_adverse_episode_refs"] == counts["operational_major_adverse_episode_refs"] == ["failure"]
    cost_only = {**failure, "operational_role_review": operational_review(failure_established=False, failure_effect_tier=None)}
    assert stability_counts({"negative_or_mixed_command_records": [cost_only]})["major_adverse_context_count"] == 0


def test_frontline_and_operational_views_of_one_episode_are_not_double_counted():
    front = result("shared", role_code="commander_in_chief")
    op = result("shared", consumption_mode="operational_result", capability_mode="operational_design", difficulty=None,
                operational_role_review=operational_review())
    assert stability_counts({"consumed_achievements": [front, op]})["major_positive_context_count"] == 1


@pytest.mark.parametrize("field", ["positive_result", "adverse_result", "retention", "personal_scope", "source_refs"])
def test_closed_mixed_result_requires_independently_recorded_sides(field):
    review = mixed_review()
    review.pop(field)
    with pytest.raises(ValueError):
        validate_mixed_result(result("synthetic", direction="mixed_review", mixed_result_review=review))


def test_mixed_result_direction_and_pending_boundary():
    row = result("synthetic", direction="mixed_review", mixed_result_review=mixed_review())
    validate_mixed_result(row)
    with pytest.raises(ValueError):
        validate_mixed_result({**row, "mixed_result_review": {**mixed_review(), "decision": "negative"}})
    validate_mixed_result(result("synthetic", direction="mixed_review", detail_status="person_result_required"))


def test_objective_shortfall_and_non_military_records_do_not_enter_values():
    shortfall = result("goal", direction="objective_shortfall", canonical_label="目标未成")
    excluded = result("political", direction="not_applicable", canonical_label="政治处置")
    profile = {"objective_shortfalls": [shortfall], "excluded_command_records": [excluded]}
    assert net_value(profile)["net"] == 0
    entries = display_entries(profile)
    assert len(entries) == 2
    assert "目标未成" in entries[0][0] and "不计军事" in entries[1][0]


def test_positive_diminishing_and_episode_deduplication():
    rows = [result(str(i)) for i in range(4)]
    p = {"consumed_achievements": rows, "negative_or_mixed_command_records": []}
    assert net_value(p)["net"] == 3.5
    assert net_value({**p, "consumed_achievements": rows + [deepcopy(rows[0])]}) == net_value(p)
    assert net_value({**p, "consumed_achievements": list(reversed(rows))}) == net_value(p)


def test_operational_does_not_inherit_frontline_difficulty():
    row = result("org", tier="S", consumption_mode="operational_result", decisive_relation="none")
    assert result_value(row) == result_value({**row, "combat_difficulty": "D4"})
    assert isclose(result_value(row), 1.44)


def test_splus_premium_and_shared_positive_queue():
    assert result_value(result("peak", tier="S+", difficulty="D2")) == 4.5
    front = result("front", difficulty="D2")
    operational = result("org", consumption_mode="operational_result")
    value = net_value({"consumed_achievements": [operational, front]})
    assert value == {"frontline_positive": 1.0, "operational_positive": 0.32,
                     "command_adverse": 0, "net": 1.32}


def test_same_episode_uses_strongest_value_without_two_role_credits():
    front = result("shared", difficulty="D2")
    operational = result("shared", tier="S", consumption_mode="operational_result")
    expected = net_value({"consumed_achievements": [operational]})
    assert net_value({"consumed_achievements": [front, operational]}) == expected
    assert net_value({"consumed_achievements": [operational, front]}) == expected


def test_positive_tail_cap_is_shared_across_roles():
    head = [result(str(i), difficulty="D2") for i in range(4)]
    tail = [result(str(i), difficulty="D2") for i in range(4, 9)]
    tail += [result(str(i), consumption_mode="operational_result") for i in range(9, 14)]
    profile = {"consumed_achievements": head + tail}
    value = net_value(profile)
    assert value["net"] == 3.8  # Head 2.8 plus one shared cap of 1.
    assert value["frontline_positive"] == 3.51
    assert value["operational_positive"] == 0.29
    assert net_value({"consumed_achievements": list(reversed(head + tail))}) == value
    assert net_value({"consumed_achievements": head + tail + [result("extra", difficulty="D2")]})["net"] == value["net"]


def test_empty_positive_and_uncapped_tail():
    assert net_value({}) == {"frontline_positive": 0, "operational_positive": 0,
                             "command_adverse": 0, "net": 0}
    rows = [result(str(i), difficulty="D2") for i in range(5)]
    assert net_value({"consumed_achievements": rows})["net"] == 3.0


def test_decimal_midpoint_rounding_uses_unrounded_total():
    rows = [result("a", difficulty="D4"), result("b"), result("c"),
            result("d", decisive_relation="co_decisive")]
    loss = result("loss", tier="S-", difficulty="D1", direction="negative")
    value = net_value({"consumed_achievements": rows, "negative_or_mixed_command_records": [loss]})
    assert value["frontline_positive"] == 3.72  # Exact 3.725, ties to even.
    assert value["command_adverse"] == -1.32
    assert value["net"] == 2.4  # Exact 2.405, without rounding components first.


def test_source_conflict_is_neither_positive_nor_a_certain_debit():
    row = result("conflict", direction="mixed_review", causal_fault="NOT_APPLICABLE_SOURCE_CONFLICT")
    assert result_value(row) == 0
    assert episode_anchors([row]) == []
    assert result_value({**row, "result_direction": "positive"}) == 0


def test_objective_shortfall_is_visible_without_inventing_a_loss():
    shortfall = result("shortfall", direction="objective_shortfall", canonical_label="Synthetic unmet objective")
    profile = {"objective_shortfalls": [shortfall]}
    assert net_value(profile)["net"] == 0
    assert stability_counts(profile)["major_adverse_context_count"] == 0
    entries = display_entries(profile)
    assert len(entries) == 1
    assert "目标未成" in entries[0][0]
    assert "不计净值或稳定性败责" in entries[0][1]


def test_positive_and_adverse_phases_keep_both_without_extra_positive_thickness():
    p = {"consumed_achievements": [result("cycle")],
         "negative_or_mixed_command_records": [result("cycle", direction="negative")]}
    value = net_value(p)
    assert value == {"frontline_positive": 1.25, "operational_positive": 0.0, "command_adverse": -1.0, "net": 0.25}


def test_refresh_preserves_source_and_stable_identity():
    original = {"profiles": [{"profile_ref": "PROFILE-SYNTHETIC", "person_ref": "PERSON-SYNTHETIC",
        "military_grade": "capable", "grade_status": "evidence_lower_bound", "stability_status": "no_failure",
        "name_aliases": ["example"], "actor_ref_aliases": ["ACTOR-ONE", "ACTOR-ALIAS"],
        "consumed_achievements": [result("e")], "negative_or_mixed_command_records": []}]}
    before = deepcopy(original)
    refreshed = refresh_values(original)
    assert original == before
    assert refreshed["profiles"][0]["person_ref"] == "PERSON-SYNTHETIC"
    assert refreshed["profile_count"] == len(refreshed["profiles"])
    assert refreshed["grade_counts"] == {"capable": len(refreshed["profiles"])}
    assert refreshed["identity_alias_group_count"] == len(refreshed["profiles"])


def test_stability_counts_shared_episode_once_and_excludes_exempt_faults():
    failure = result("loss", direction="negative", role_code="commander_in_chief")
    duplicate = {**failure, "campaign_ref": "parent-alias"}
    exempt = result("exempt", direction="negative", role_code="commander_in_chief", causal_fault="NO_FAULT_EXTERNAL_DISASTER")
    p = {"consumed_achievements": [], "failure_accountability": [failure, duplicate, exempt]}
    counts = stability_counts(p)
    assert counts["major_adverse_context_count"] == counts["commander_responsibility_major_failure_count"] == 1


def test_identity_alias_resolves_to_one_canonical_person_and_fails_on_cycles():
    p = {"profile_ref": "CANONICAL", "person_ref": "PERSON"}
    payload = {"profiles": [p], "identity_aliases": [{"profile_ref": "OLD", "canonical_profile_ref": "CANONICAL"}]}
    index = talent_profiles_by_ref(payload)
    assert index["OLD"] is index["CANONICAL"]
    assert len(payload["profiles"]) == 1
    with pytest.raises(ValueError, match="循环"):
        talent_profiles_by_ref({"profiles": [p], "identity_aliases": [{"profile_ref": "A", "canonical_profile_ref": "B"}, {"profile_ref": "B", "canonical_profile_ref": "A"}]})
