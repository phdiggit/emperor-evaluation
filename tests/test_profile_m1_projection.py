from copy import deepcopy
import pytest

from emperor_v4.evaluation.profile_m1_projection import (
    compact_registry_projection, registry_projection, RESULTS, CAMPAIGNS, DERIVED,
)


def sample():
    return {'profile_ref': 'synthetic', RESULTS: ['1) 结果甲', '2) 结果乙'],
            CAMPAIGNS: ['1) 战役甲／统筹', '2) 战役乙／主将'],
            DERIVED[0]: '1) 结果甲<br>2) 结果乙',
            DERIVED[1]: '1) 战役甲／统筹<br>2) 战役乙／主将',
            DERIVED[2]: ['1) 结果甲｜战役甲／统筹', '2) 结果乙｜战役乙／主将'],
            'paired_result_difficulty_campaign_roles_display': '独立维护的不同表述。'}


def test_lossless_read_only_and_preserves_independent_display():
    original = sample()
    before = deepcopy(original)
    compact = compact_registry_projection(original)
    assert not set(DERIVED) & compact.keys()
    assert registry_projection(compact) == original == before
    assert compact_registry_projection(registry_projection(compact)) == compact
    expanded = registry_projection(compact)
    expanded[RESULTS].append('消费端修改')
    assert original == before and compact[RESULTS] == before[RESULTS]
    compact[RESULTS][0] = '1) 当前结果'
    rebuilt = registry_projection(compact)
    assert rebuilt[DERIVED[2]][0] == '1) 当前结果｜战役甲／统筹'
    assert rebuilt['paired_result_difficulty_campaign_roles_display'] == before['paired_result_difficulty_campaign_roles_display']


@pytest.mark.parametrize('case', ['length', 'number', 'type', 'copy', 'missing', 'version'])
def test_rejects_invalid_compact_projection(case):
    data = compact_registry_projection(sample())
    if case == 'length': data[CAMPAIGNS].pop()
    elif case == 'number': data[CAMPAIGNS].reverse()
    elif case == 'type': data[RESULTS][0] = None
    elif case == 'copy': data[DERIVED[0]] = '旧副本'
    elif case == 'missing': data.pop(RESULTS)
    else: data['storage_version'] = 'unknown'
    with pytest.raises(ValueError): registry_projection(data)


def test_refuses_to_discard_different_text():
    data = sample()
    data[DERIVED[0]] = '独立文本，不能丢弃'
    with pytest.raises(ValueError, match='不同值'): compact_registry_projection(data)


def test_unregistered_and_empty_profiles_remain_distinct():
    absent = {'status': 'NO_PROFILE'}
    assert registry_projection(compact_registry_projection(absent)) == absent
    empty = sample()
    empty[RESULTS] = []; empty[CAMPAIGNS] = []
    empty[DERIVED[0]] = ''; empty[DERIVED[1]] = ''; empty[DERIVED[2]] = []
    assert registry_projection(compact_registry_projection(empty)) == empty
