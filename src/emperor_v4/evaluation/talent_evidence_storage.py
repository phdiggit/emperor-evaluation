"""Lossless sharing of exact leading evidence fields inside one profile."""
from collections import Counter, defaultdict
from copy import deepcopy
import json

STORAGE = 'military-talent-evidence-prefixes-v1'
CATALOG = 'talent_evidence_catalog'
REF = 'talent_evidence_ref'
FIELDS = ('consumed_achievements', 'capability_episode_anchors',
          'negative_or_mixed_command_records', 'failure_accountability')


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _check_plain(value):
    if isinstance(value, dict):
        if REF in value or CATALOG in value:
            raise ValueError('人才证据含嵌套目录或越界占位符')
        for child in value.values():
            _check_plain(child)
    elif isinstance(value, list):
        for child in value:
            _check_plain(child)


def _entries(profile):
    for field in FIELDS:
        values = profile.get(field, [])
        if isinstance(values, list):
            for index, value in enumerate(values):
                if isinstance(value, dict):
                    yield field, index, value


def compact_evidence(profile):
    """Only share equal field sequences; never infer identity or attribution."""
    _check_plain(profile)
    groups = defaultdict(list)
    for field, index, value in _entries(profile):
        if len(value) >= 2:
            groups[_encoded(list(value.items())[:2])].append((field, index, value))
    catalog = {}
    replacements = {}
    for entries in groups.values():
        if len(entries) < 2:
            continue
        items = list(entries[0][2].items())
        length = len(items)
        for _, _, value in entries[1:]:
            other = list(value.items())
            index = 0
            while index < min(length, len(other)) and _encoded(items[index]) == _encoded(other[index]):
                index += 1
            length = index
        common = dict(items[:length])
        ref = str(len(catalog))
        packed = [{REF: ref, 'fields': dict(list(value.items())[length:])} for _, _, value in entries]
        gain = sum(len(_encoded(value)) for _, _, value in entries) - len(_encoded(common)) - sum(len(_encoded(v)) for v in packed) - len(_encoded(ref)) - 2
        if gain <= 0:
            continue
        catalog[ref] = common
        for (field, index, _), value in zip(entries, packed, strict=True):
            replacements[field, index] = value
    if not catalog:
        return deepcopy(profile)
    result = deepcopy(profile)
    for (field, index), value in replacements.items():
        result[field][index] = value
    result[CATALOG] = catalog
    return result if len(_encoded(result)) < len(_encoded(profile)) else deepcopy(profile)


def expand_evidence(profile):
    catalog = profile.get(CATALOG, {})
    if not isinstance(catalog, dict) or (CATALOG in profile and not catalog):
        raise ValueError('人才证据目录无效或为空')
    signatures = set()
    for ref, value in catalog.items():
        if not isinstance(ref, str) or not ref or not isinstance(value, dict) or len(value) < 2:
            raise ValueError('人才证据目录条目无效')
        _check_plain(value)
        signature = _encoded(value)
        if signature in signatures:
            raise ValueError('人才证据目录重复')
        signatures.add(signature)
    result = deepcopy(profile)
    result.pop(CATALOG, None)
    used = Counter()
    for field, index, value in _entries(result):
        if REF not in value:
            continue
        ref = value[REF]
        suffix = value.get('fields')
        if (set(value) != {REF, 'fields'} or not isinstance(ref, str) or ref not in catalog
                or not isinstance(suffix, dict) or set(suffix) & set(catalog[ref])):
            raise ValueError('人才证据引用悬空、格式无效或覆盖共享字段')
        _check_plain(suffix)
        result[field][index] = {**deepcopy(catalog[ref]), **deepcopy(suffix)}
        used[ref] += 1
    _check_plain(result)
    if set(used) != set(catalog) or any(n < 2 for n in used.values()):
        raise ValueError('人才证据目录存在未共用条目')
    return result


def expand_shard(shard):
    version = shard.get('evidence_storage')
    if version not in (None, STORAGE):
        raise ValueError('人才证据存储版本无效')
    if version is None and any(CATALOG in row for row in shard.get('profiles', [])):
        raise ValueError('人才证据分片缺少存储声明')
    return {**shard, 'profiles': [expand_evidence(row) for row in shard.get('profiles', [])]}
