from copy import deepcopy
import pytest
from emperor_v4.evaluation.third_item_c_commander_reading import commander_projection, commander_html


def example():
    row = {'ruler_id': 'owner', 'ruler_name': '合成君主', 'public_reading': {'axes': {'C3': {
        'commander_links': [{'name_in_text': '甲帅', 'profile_refs': ['p1'], 'identity_status': 'RESOLVED'},
                            {'name_in_text': '乙帅', 'profile_refs': ['p2'], 'identity_status': 'RESOLVED'}]}}},
        'c5_axis_gate': {'C3_top_commander_deliveries': [{'profile_ref': 'p1', 'subject_ruler_id': 'owner',
            'own_window_basis': '合成本任成果', 'achievement_refs': ['own']} ]}}
    profiles = {'p1': {'profile_ref': 'p1', 'person': '甲帅', 'military_grade': 'top',
        'consumed_achievements': [{'campaign_ref': 'own', 'canonical_label': '合成方向胜绩',
            'campaign_tier': 'A', 'result_direction': 'positive'}]},
        'p2': {'profile_ref': 'p2', 'person': '乙帅', 'military_grade': 'elite', 'consumed_achievements': []}}
    return row, profiles


def test_current_talent_grade_and_bound_personal_result_are_distinct():
    row, profiles = example(); before = deepcopy(row)
    result = commander_projection(row, profiles)
    assert result['entries'][0]['qualification_status'] == 'OWN_WINDOW_SIGNIFICANT_RESULTS'
    assert result['entries'][1]['qualification_status'] == 'BELOW_FIVE_TALENT_GATE'
    assert 'military.html#commander=p1' in commander_html(result)
    assert result['entries'][0]['own_window_results'][0]['label'] == '合成方向胜绩'
    assert row == before
    profiles['p1']['military_grade'] = 'important'
    assert commander_projection(row, profiles)['entries'][0]['qualification_status'] == 'BELOW_FIVE_TALENT_GATE'


def test_other_reign_and_ruler_self_do_not_supply_subordinate_qualification():
    row, profiles = example()
    row['c5_axis_gate']['C3_top_commander_deliveries'][0]['subject_ruler_id'] = 'other'
    entry = commander_projection(row, profiles)['entries'][0]
    assert entry['qualification_status'] == 'OWN_WINDOW_NOT_BOUND' and not entry['own_window_results']
    row['ruler_name'] = '甲帅'
    assert commander_projection(row, profiles)['entries'][0]['qualification_status'] == 'RULER_SELF'


def test_identity_and_missing_link_do_not_invent_a_talent_grade():
    row, profiles = example()
    row['public_reading']['axes']['C3']['commander_links'][0]['identity_status'] = 'PENDING'
    assert commander_projection(row, profiles)['entries'][0]['qualification_status'] == 'IDENTITY_PENDING'
    row['public_reading']['axes']['C3']['commander_links'][0]['profile_refs'] = []
    assert commander_projection(row, profiles)['entries'][0]['grade'] is None
    row['public_reading']['axes']['C3']['commander_links'][0]['profile_refs'] = ['missing']
    with pytest.raises(ValueError, match='现行人才档案'):
        commander_projection(row, profiles)


def test_wrong_person_and_negative_results_cannot_supply_qualification():
    row, profiles = example()
    profiles['p1']['consumed_achievements'][0]['result_direction'] = 'negative'
    assert commander_projection(row, profiles)['entries'][0]['qualification_status'] == 'OWN_WINDOW_NOT_BOUND'
    row['public_reading']['axes']['C3']['commander_links'][0]['opponent_or_context'] = True
    assert commander_projection(row, profiles)['entries'][0]['qualification_status'] == 'OPPONENT_OR_CONTEXT'
    row['public_reading']['axes']['C3']['commander_links'][0]['name_in_text'] = '另一个人'
    with pytest.raises(ValueError, match='身份不符'):
        commander_projection(row, profiles)
