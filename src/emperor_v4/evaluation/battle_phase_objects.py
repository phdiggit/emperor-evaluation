"""Deduplicate identical, field-bound objects inside one battle only."""
from collections import Counter
from copy import deepcopy
import json

STORAGE = 'battle-phase-objects-v1'
CATALOG = 'phase_object_catalog'
REF = 'phase_object_ref'
FIELDS = frozenset(('axis_source_refs', 'P_inference', 'border_control', 'ruler_binding',
                    'founding_startup_ledger', 'cost_axes', 'cost_axis_basis', 'cost_evidence'))


def _token(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _check(value):
    if isinstance(value, dict):
        if CATALOG in value or REF in value:
            raise ValueError('战役阶段对象不得包含嵌套目录或占位符')
        for child in value.values():
            _check(child)
    elif isinstance(value, list):
        for child in value:
            _check(child)


def compact_objects(record):
    _check(record)
    counts, values = Counter(), {}

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'source_reference_catalog':
                    continue
                if key in FIELDS and isinstance(child, dict):
                    token = (key, _token(child))
                    if len(token[1].encode()) >= 100:
                        counts[token] += 1
                        values[token] = child
                else:
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(record)
    selected = {token: str(i) for i, (token, n) in enumerate(counts.items()) if n > 1}
    if not selected:
        return deepcopy(record)
    result = deepcopy(record)

    def replace(value):
        if isinstance(value, dict):
            for key, child in list(value.items()):
                if key == 'source_reference_catalog':
                    continue
                if key in FIELDS and isinstance(child, dict):
                    ref = selected.get((key, _token(child)))
                    if ref is not None:
                        value[key] = {REF: ref}
                else:
                    replace(child)
        elif isinstance(value, list):
            for child in value:
                replace(child)

    replace(result)
    result[CATALOG] = {ref: {'field': token[0], 'value': deepcopy(values[token])}
                       for token, ref in selected.items()}
    # A catalog is worthwhile only when its total overhead is smaller.
    return result if len(_token(result).encode()) < len(_token(record).encode()) else deepcopy(record)


def expand_objects(record):
    catalog = record.get(CATALOG, {})
    if not isinstance(catalog, dict) or (CATALOG in record and not catalog):
        raise ValueError('战役阶段对象目录无效或为空')
    signatures = set()
    for ref, entry in catalog.items():
        if (not isinstance(ref, str) or not ref or not isinstance(entry, dict)
                or set(entry) != {'field', 'value'} or not isinstance(entry['field'], str) or entry['field'] not in FIELDS
                or not isinstance(entry['value'], dict)):
            raise ValueError('战役阶段对象目录条目无效')
        _check(entry['value'])
        signature = (entry['field'], _token(entry['value']))
        if signature in signatures:
            raise ValueError('战役阶段对象目录重复')
        signatures.add(signature)
    used = Counter()

    def expand(value):
        if isinstance(value, dict):
            if REF in value or CATALOG in value:
                raise ValueError('战役阶段对象引用位置非法')
            result = {}
            for key, child in value.items():
                if isinstance(child, dict) and REF in child:
                    ref = child[REF]
                    if (set(child) != {REF} or not isinstance(ref, str) or ref not in catalog
                            or key != catalog[ref]['field']):
                        raise ValueError('战役阶段对象引用悬空或跨字段')
                    used[ref] += 1
                    result[key] = deepcopy(catalog[ref]['value'])
                else:
                    result[key] = expand(child)
            return result
        if isinstance(value, list):
            return [expand(child) for child in value]
        return value

    result = expand({k: v for k, v in record.items() if k != CATALOG})
    if set(used) != set(catalog) or any(n < 2 for n in used.values()):
        raise ValueError('战役阶段对象目录存在未共用条目')
    return result
