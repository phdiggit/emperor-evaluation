"""Lossless, shard-local storage for repeated authored public-reading strings."""
from collections import Counter
from copy import deepcopy
import json

STORAGE = 'formal-public-reading-texts-v1'
FIELD_STORAGE = 'formal-public-reading-texts-v2'
CATALOG = 'reading_text_catalog'
REF = 'reading_text_ref'
MARKER = 'public_reading_storage'
FIELDS = 'reading_text_fields'
C_SCHEMA = 'emperor-v4-third-item-c-formal-settlement-v4-strategy-chain'
FINANCE_SCHEMAS = frozenset([
    *(f'SECOND-ITEM-{axis}-FORMAL-V7.0-L-ADJUSTMENT' for axis in ('C1', 'C2', 'C3')),
    'SECOND-ITEM-C4-FORMAL-V8.0-RECOVERY-DETERIORATION-DA6',
])


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _readings(shard, fields):
    for block in shard.get('collections', {}).values():
        for row in block.get('records', []):
            for field in fields:
                if field in row:
                    yield row[field]


def _validate_fields(fields):
    if (not isinstance(fields, (list, tuple)) or not fields
            or any(not isinstance(k, str) or not k.startswith('public_') for k in fields)
            or len(set(fields)) != len(fields)):
        raise ValueError('正式阅读文本字段范围无效')


def _check_plain(value):
    if isinstance(value, dict):
        if REF in value or CATALOG in value or MARKER in value or FIELDS in value:
            raise ValueError('正式阅读正文含存储占位符')
        for child in value.values():
            _check_plain(child)
    elif isinstance(value, list):
        for child in value:
            _check_plain(child)


def compact_reading_texts(shard, *, fields=('public_reading',)):
    """Accept expanded records only; do not share roles, IDs or similar prose."""
    _check_plain(shard)
    _validate_fields(fields)
    counts = Counter()

    def collect(value):
        if isinstance(value, str) and len(value.encode('utf-8')) >= 60:
            counts[value] += 1
        elif isinstance(value, dict):
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for reading in _readings(shard, fields):
        collect(reading)
    catalog = {}
    refs = {}
    for value, count in counts.items():
        ref = str(len(catalog))
        # Count the exact JSON overhead before selecting a shared string.
        gain = (count - 1) * len(_encoded(value)) - count * len(_encoded({REF: ref})) - len(_encoded(ref)) - 2
        if count > 1 and gain > 0:
            catalog[ref] = value
            refs[value] = ref
    if not catalog:
        return deepcopy(shard)

    def replace(value):
        if isinstance(value, str) and value in refs:
            return {REF: refs[value]}
        if isinstance(value, dict):
            return {key: replace(child) for key, child in value.items()}
        if isinstance(value, list):
            return [replace(child) for child in value]
        return value

    result = deepcopy(shard)
    for block in result['collections'].values():
        for row in block['records']:
            for field in fields:
                if field in row:
                    row[field] = replace(row[field])
    result[MARKER] = STORAGE if tuple(fields) == ('public_reading',) else FIELD_STORAGE
    if result[MARKER] == FIELD_STORAGE:
        result[FIELDS] = list(fields)
    result[CATALOG] = catalog
    return result if len(_encoded(result)) < len(_encoded(shard)) else deepcopy(shard)


def expand_reading_texts(shard):
    """Expand into private records; reject corrupt or misplaced references."""
    if MARKER not in shard and CATALOG not in shard and FIELDS not in shard:
        _check_plain(shard)
        return shard
    version = shard.get(MARKER)
    if version not in (STORAGE, FIELD_STORAGE):
        raise ValueError('正式阅读文本存储版本无效')
    fields = ('public_reading',) if version == STORAGE else shard.get(FIELDS)
    _validate_fields(fields)
    if version == STORAGE and FIELDS in shard:
        raise ValueError('正式阅读文本存储版本与字段范围不符')
    catalog = shard.get(CATALOG)
    if (not isinstance(catalog, dict) or not catalog
            or any(not isinstance(k, str) or not k or not isinstance(v, str) for k, v in catalog.items())
            or len(set(catalog.values())) != len(catalog)):
        raise ValueError('正式阅读文本目录无效或重复')
    used = Counter()

    def expand(value):
        if isinstance(value, dict):
            if REF in value:
                ref = value[REF]
                if set(value) != {REF} or not isinstance(ref, str) or ref not in catalog:
                    raise ValueError('正式阅读文本引用悬空或格式无效')
                used[ref] += 1
                return catalog[ref]
            if CATALOG in value or MARKER in value or FIELDS in value:
                raise ValueError('正式阅读正文含嵌套存储目录')
            return {key: expand(child) for key, child in value.items()}
        if isinstance(value, list):
            return [expand(child) for child in value]
        return value

    result = deepcopy(shard)
    result.pop(MARKER)
    result.pop(CATALOG)
    result.pop(FIELDS, None)
    for block in result.get('collections', {}).values():
        for row in block.get('records', []):
            for field in fields:
                if field in row:
                    row[field] = expand(row[field])
    # Any remaining placeholder lies outside the declared public fields.
    _check_plain(result)
    if set(used) != set(catalog) or any(n < 2 for n in used.values()):
        raise ValueError('正式阅读文本目录存在未共用条目')
    return result
