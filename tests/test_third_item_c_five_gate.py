from copy import deepcopy

import pytest

from emperor_v4.evaluation.third_item_c_five_gate import SCHEMA, verify_five_gate


def admission():
    chains = [{"chain_id": f"c{i}", "source_event_refs": [f"t{i}"],
               "major_system_success": True, "war_classification": "EXTERNAL_WAR"} for i in range(3)]
    systems = {"o1": {"organization_grade": "O4", "source_campaign_refs": ["t0", "t1"]},
               "o2": {"organization_grade": "O5", "source_campaign_refs": ["t2"]}}
    profiles = {ref: {"profile_ref": ref, "person": ref, "military_grade": "top",
                      "consumed_achievements": [{"campaign_ref": ref + "-result",
                       "campaign_tier": "A", "result_direction": "positive"}]}
                for ref in ["p1", "p2"]}
    gate = {"schema_version": SCHEMA,
            "current_major_success_revalidation": {a: {'status': 'PASSED', 'chain_refs': ['c0'], 'basis': '合成本体胜绩对本轴的独立复验'} for a in ['C1', 'C2', 'C3']},
            "major_outcome_review": {"failure_review_status": "REVIEWED_ZERO", "failure_review_basis": "合成完整窗口核对"},
            "C1_O4_plus_opponent_systems": [
                {"opponent_system_ref": "o1", "task_refs": ["c0", "c1"]},
                {"opponent_system_ref": "o2", "task_refs": ["c2"]}],
            "C2_O4_plus_strategic_directions": [
                {"direction": "north", "opponent_system_refs": ["o1"], "task_refs": ["c0", "c1"]},
                {"direction": "south", "opponent_system_refs": ["o2"], "task_refs": ["c2"]}],
            "C3_top_commander_deliveries": [
                {"profile_ref": ref, "achievement_refs": [ref + "-result"],
                 "subject_ruler_id": "owner", "own_window_basis": "合成本任授权与本人结果"}
                for ref in profiles],
            "axis_status": {a: "PASSED" for a in ["C1", "C2", "C3"]},
            "axis_ability_review": {a: {"grade": 5, "basis": "独立构造的能力事实"}
                                    for a in ["C1", "C2", "C3"]}}
    row = {"ruler_id": "owner", "ruler_name": "合成主政者", "strategy_chains": chains,
           "capability_only_strategy_chains": [], "combat_delivery_grade": "C1-5",
           "operational_sustainability_cap": "C2-5", "system_reliability_cap": "C3-5",
           "final_grade": "C-5", "c5_axis_gate": gate}
    return row, systems, profiles


def test_significant_result_uses_current_public_tiers():
    row, systems, profiles = admission()
    assert verify_five_gate(row, systems, profiles)["commander_count"] == 2
    profiles["p1"]["consumed_achievements"][0]["campaign_tier"] = "B"
    with pytest.raises(ValueError, match="A级及以上"):
        verify_five_gate(row, systems, profiles)


def test_empty_failure_flags_do_not_prove_reviewed_zero():
    row, systems, profiles = admission()
    row['c5_axis_gate'].pop('major_outcome_review')
    with pytest.raises(ValueError, match='零重大体系失败'):
        verify_five_gate(row, systems, profiles)
    row['final_grade'] = 'C-4'
    with pytest.raises(ValueError, match='C1五档缺少零重大体系失败'):
        verify_five_gate(row, systems, profiles)


def test_unification_only_samples_cannot_complete_axis_five():
    row, systems, profiles = admission()
    row['capability_only_strategy_chains'] = row.pop('strategy_chains')
    with pytest.raises(ValueError, match='本体重大体系胜绩复验'):
        verify_five_gate(row, systems, profiles)


def test_ordinary_rebellion_or_unqualified_opponent_cannot_revalidate_five():
    row, systems, profiles = admission()
    row['strategy_chains'][0]['war_classification'] = 'ORDINARY_INTERNAL_WAR'
    with pytest.raises(ValueError, match='普通平乱'):
        verify_five_gate(row, systems, profiles)
    row['strategy_chains'].append({'chain_id': 'ordinary', 'major_system_success': True})
    row['c5_axis_gate']['current_major_success_revalidation']['C1']['chain_refs'] = ['ordinary']
    with pytest.raises(ValueError, match='本体重大体系胜绩复验'):
        verify_five_gate(row, systems, profiles)


def test_repeated_parent_references_do_not_create_three_strategic_samples():
    row, systems, profiles = admission()
    row["c5_axis_gate"]["C1_O4_plus_opponent_systems"][0]["task_refs"] = ["c0", "c0"]
    row["c5_axis_gate"]["C2_O4_plus_strategic_directions"][0]["task_refs"] = ["c0"]
    with pytest.raises(ValueError, match="必要门"):
        verify_five_gate(row, systems, profiles)


def test_actual_window_does_not_inherit_mother_grade():
    row, systems, profiles = admission()
    systems["o2"]["window_assessments"] = {"w": {
        "subject_ruler_id": "owner", "source_chain_refs": ["c2"], "organization_grade": "O3"}}
    with pytest.raises(ValueError, match="实际窗口"):
        verify_five_gate(row, systems, profiles)


def test_current_talent_grade_and_identity_are_authoritative():
    row, systems, profiles = admission()
    profiles["p2"]["military_grade"] = "elite"
    with pytest.raises(ValueError, match="人才等级"):
        verify_five_gate(row, systems, profiles)
    profiles["p2"] = deepcopy(profiles["p1"])
    row["c5_axis_gate"]["C3_top_commander_deliveries"][1]["achievement_refs"] = ["p1-result"]
    with pytest.raises(ValueError, match="必要门"):
        verify_five_gate(row, systems, profiles)


def test_ruler_and_other_window_cannot_fill_commander_quota():
    row, systems, profiles = admission()
    profiles["p1"]["person"] = row["ruler_name"]
    with pytest.raises(ValueError, match="自己的部将"):
        verify_five_gate(row, systems, profiles)
    profiles["p1"]["person"] = "p1"
    row["c5_axis_gate"]["C3_top_commander_deliveries"][0]["subject_ruler_id"] = "other"
    with pytest.raises(ValueError, match="有效窗口"):
        verify_five_gate(row, systems, profiles)


def test_group_logistics_collapse_blocks_c2_not_other_axes():
    row, systems, profiles = admission()
    row["c5_axis_gate"]["logistics_group_collapse_refs"] = ["c1"]
    row["operational_sustainability_cap"] = "C2-4"; row["final_grade"] = "C-4"
    result = verify_five_gate(row, systems, profiles)
    assert result["necessary_axis_gates"] == {"C1": True, "C2": False, "C3": True}
    row["operational_sustainability_cap"] = "C2-5"
    with pytest.raises(ValueError, match="C2五档必要门"):
        verify_five_gate(row, systems, profiles)


def test_major_failure_blocks_c1_five_even_when_overall_is_capped():
    row, systems, profiles = admission()
    row["strategy_chains"][0]["major_system_failure"] = True
    row["final_grade"] = "C-4"
    with pytest.raises(ValueError, match="C1五档不得"):
        verify_five_gate(row, systems, profiles)
    row['combat_delivery_grade'] = 'C1-4'
    assert verify_five_gate(row, systems, profiles)['necessary_axis_gates'] == {'C1': False, 'C2': True, 'C3': True}


@pytest.mark.parametrize('war_classification', ['EXCEPTIONAL_INTERNAL_WAR', None])
def test_external_major_success_is_required_even_for_exceptional_internal_war(war_classification):
    row, systems, profiles = admission()
    row['strategy_chains'][0]['war_classification'] = war_classification
    with pytest.raises(ValueError, match='对外战争重大体系胜绩'):
        verify_five_gate(row, systems, profiles)
