"""Lossless expansion of M1's local registered campaign cells."""
from copy import deepcopy

STORAGE = 'm1-registry-cells-v1'
RESULTS = 'result_difficulty_combination_items'
CAMPAIGNS = 'campaign_group_role_items'
DERIVED = ('result_difficulty_combinations_display', 'campaign_group_roles_display',
           'paired_result_difficulty_campaign_role_items')


def _derived(projection: dict) -> dict:
    if RESULTS not in projection and CAMPAIGNS not in projection:
        if 'profile_ref' in projection:
            raise ValueError('M1登记投影缺少本人战役列表')
        return {}
    a, b = projection.get(RESULTS), projection.get(CAMPAIGNS)
    if (not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b)
            or any(not isinstance(v, str) for v in [*a, *b])):
        raise ValueError('M1登记投影两份列表长度或内容不合法')
    pairs = []
    for result, campaign in zip(a, b):
        left, sep, _ = result.partition(') ')
        right, right_sep, body = campaign.partition(') ')
        if sep != right_sep or (sep and left != right):
            raise ValueError('M1登记投影列表编号不对应')
        pairs.append(result + '｜' + (body if right_sep else campaign))
    return dict(zip(DERIVED, ('<br>'.join(a), '<br>'.join(b), pairs)))


def registry_projection(projection: dict) -> dict:
    """Expand only literal list copies; retain the authored paired display."""
    if projection.get('storage_version') != STORAGE:
        raise ValueError('M1登记投影存储版本不合法')
    if set(DERIVED) & projection.keys():
        raise ValueError('M1登记投影不得内嵌生成副本')
    result = deepcopy(projection)
    result.pop('storage_version')
    result.update(_derived(result))
    return result


def compact_registry_projection(projection: dict) -> dict:
    if 'storage_version' in projection:
        registry_projection(projection)
        return deepcopy(projection)
    derived = _derived(projection)
    if any(projection.get(k) != v for k, v in derived.items()):
        raise ValueError('M1登记投影副本与原列表不同值，不能精简')
    if set(DERIVED) & projection.keys() != set(derived):
        raise ValueError('M1未登记对象含有不完整展示副本')
    result = deepcopy(projection)
    for key in derived:
        result.pop(key)
    result['storage_version'] = STORAGE
    return result
