"""Lossless source-list sharing for retained military cost cycle evidence."""
from copy import deepcopy

from .battle_source_references import (
    CATALOG, REF, STORAGE, compact_source_lists, expand_source_lists,
)

SHARD_SCHEMA = 'military-action-cost-benefit-registry-shard-v1'
MARKER = 'source_reference_storage'


def expand_shard(shard):
    if shard.get('schema_version') != SHARD_SCHEMA:
        raise ValueError('军事行动登记分片schema错误')
    if MARKER in shard and shard[MARKER] != STORAGE:
        raise ValueError('军事行动登记来源存储版本错误')
    rows = shard.get('records')
    if (not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows)
            or type(shard.get('record_count')) is not int or shard['record_count'] != len(rows)):
        raise ValueError('军事行动登记分片记录数或类型错误')
    if MARKER not in shard:
        # The shared decoder rejects placeholders outside their legal fields.
        def reserved(value):
            if isinstance(value, dict):
                return CATALOG in value or REF in value or any(reserved(v) for v in value.values())
            return isinstance(value, list) and any(reserved(v) for v in value)
        if reserved(rows):
            raise ValueError('军事行动登记分片缺少来源存储声明')
    result = {key: deepcopy(value) for key, value in shard.items() if key != MARKER}
    result['records'] = [expand_source_lists(row) for row in rows]
    return result


def compact_shard(shard):
    """Accept complete records only; retain every field and collection order."""
    if MARKER in shard:
        raise ValueError('军事行动登记压缩输入必须为展开分片')
    result = expand_shard(shard)
    result['records'] = [compact_source_lists(row) for row in result['records']]
    result[MARKER] = STORAGE
    return result
