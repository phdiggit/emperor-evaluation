import copy
import json

import pytest

from emperor_v4.evaluation.first_item_c_evidence import project_evidence, declared_positive_values


def fixture():
    person = '合成主帅'
    member = {'actor_ref': 'SYN-PERSON', 'actor_name': person, 'role_code': 'commander_in_chief',
              'contribution_scope': '在侧翼受阻后改道，取得实际方向结果。',
              'person_command_index': {'consumption_mode': 'person_result', 'capability_mode': 'integrated_command'},
              'person_command_result': {'result_ref': 'SYN-RESULT', 'result_direction': 'positive', 'result_tier': 'A',
                                        'combat_difficulty': 'D2', 'basis': '只取本人侧翼方向。', 'source_refs': ['合成史源/一']}}
    action = {'evidence_ref': 'SYN-ACTION', 'person': person, 'canonical_label': '侧翼调整', 'evidence_kind': 'military_operation',
              'personal_role': '实际主帅', 'military_judgment': '避免正面坚垒，改道侧翼。', 'implementation': '方案实际执行。',
              'personal_result': '侧翼取得。', 'source_refs': ['合成史源/一']}
    parent = {'war_event_id': 'SYN-WAR', 'canonical_label': '合成战争', 'campaign_tier': 'S', 'combat_difficulty': 'D4',
              'members': [member], 'personal_action_attributions': [action], 'source_refs': ['合成史源/一']}
    index = {'records': {'SYN-WAR': parent}, 'scope_notes': {'SYN-SCOPE': {'scope_note_ref': 'SYN-SCOPE', 'person': person,
             'context': '仅有政治授职', 'established_actions': '任命将领。', 'source_refs': ['合成史源/二']}}}
    binding = {'kind': 'member', 'war_event_id': 'SYN-WAR', 'ref': 'SYN-PERSON', 'actor_name': person,
               'disposition': '采用', 'case_group': 'SYN-CYCLE', 'window_basis': '合成建基期内。', 'reason': '本人实际主军方向。'}
    return person, index, binding


def test_resolves_exact_public_person_and_preserves_source_fields():
    person, index, binding = fixture()
    result = project_evidence(json.dumps([binding]), index, person=person)[0]
    assert result['source_refs'] == ['合成史源/一']
    assert result['public_facts'] == [['公共本人依据', '在侧翼受阻后改道，取得实际方向结果。']]
    assert json.loads(json.dumps(result, ensure_ascii=False)) == result
    assert result['case_group'] == binding['case_group']


def test_personal_grade_is_not_inherited_from_parent():
    _, index, binding = fixture()
    assert declared_positive_values(index, binding) == {('前线作战', 'A', 'B')}
    index['records']['SYN-WAR']['campaign_tier'] = 'S+'
    assert declared_positive_values(index, binding) == {('前线作战', 'A', 'B')}


@pytest.mark.parametrize('mutation', ['missing_person', 'other_person', 'missing_window', 'unknown_disposition', 'm1_source', 'authorization_only', 'unresolved'])
def test_rejects_invented_or_unqualified_personal_evidence(mutation):
    person, index, binding = fixture()
    member = index['records']['SYN-WAR']['members'][0]
    if mutation == 'missing_person':
        binding['ref'] = 'ABSENT'
    elif mutation == 'other_person':
        member['actor_name'] = '另一合成人物'
        binding['actor_name'] = '另一合成人物'
    elif mutation == 'missing_window':
        binding['window_basis'] = ''
    elif mutation == 'unknown_disposition':
        binding['disposition'] = 'UNKNOWN'
    elif mutation == 'm1_source':
        member['person_command_result']['source_refs'] = []
        member['source_refs'] = ['docs/评分结算/人物画像/M1/结果.json']
    elif mutation == 'authorization_only':
        member['ruler_campaign_relation'] = 'authorization_only'
    else:
        member['person_command_index']['capability_mode'] = 'unresolved'
    with pytest.raises(ValueError):
        project_evidence(json.dumps([binding]), index, person=person)


def test_organization_action_and_scope_note_cannot_become_military_positive():
    person, index, binding = fixture()
    action = index['records']['SYN-WAR']['personal_action_attributions'][0]
    action['evidence_kind'] = 'organization_only'
    binding.update(kind='action', ref='SYN-ACTION')
    with pytest.raises(ValueError, match='组织授权'):
        project_evidence(json.dumps([binding]), index, person=person)
    binding.update(kind='scope_note', ref='SYN-SCOPE')
    with pytest.raises(ValueError, match='范围说明'):
        project_evidence(json.dumps([binding]), index, person=person)
    binding['disposition'] = '非战争取得'
    assert project_evidence(json.dumps([binding]), index, person=person)[0]['label'] == '仅有政治授职'


def test_missing_evidence_blocks_publication_instead_of_inventing_zero_or_facts():
    person, index, binding = fixture()
    for value in ('[]', '', 'null'):
        with pytest.raises(ValueError):
            project_evidence(value, index, person=person)
    with pytest.raises(ValueError, match='重复'):
        project_evidence(json.dumps([binding, copy.deepcopy(binding)]), index, person=person)
