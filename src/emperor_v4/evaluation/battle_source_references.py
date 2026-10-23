"""Lossless per-battle storage of repeated source reference lists."""
from collections import Counter
from copy import deepcopy
import json
from .battle_phase_objects import compact_objects, expand_objects

STORAGE = 'battle-source-reference-lists-v1'
CATALOG = 'source_reference_catalog'
REF = 'source_list_ref'


def _source_key(key):
    return key.endswith('source_refs') or key in ('source_anchor_refs', 'source_revision_refs')


def _token(value):
    # Preserve list order and dictionary order, including duplicates within lists.
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _check_reserved(value):
    if isinstance(value, dict):
        if REF in value or CATALOG in value:
            raise ValueError('战役完整记录不得含来源目录或引用占位符')
        for child in value.values():
            _check_reserved(child)
    elif isinstance(value, list):
        for child in value:
            _check_reserved(child)


def compact_references(record):
    return compact_objects(compact_source_lists(record))


def compact_source_lists(record):
    """Encode only identical repeated lists; never infer source equivalence."""
    _check_reserved(record)
    counts, values = Counter(), {}

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if _source_key(key) and isinstance(child, list):
                    token = _token(child)
                    if len(token.encode('utf-8')) >= 80:
                        counts[token] += 1
                        values[token] = child
                else:
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(record)
    selected = {token: str(i) for i, (token, n) in enumerate(counts.items()) if n > 1}
    result = deepcopy(record)
    if not selected:
        return result

    def replace(value):
        if isinstance(value, dict):
            for key, child in list(value.items()):
                if _source_key(key) and isinstance(child, list):
                    ref = selected.get(_token(child))
                    if ref is not None:
                        value[key] = {REF: ref}
                else:
                    replace(child)
        elif isinstance(value, list):
            for child in value:
                replace(child)

    replace(result)
    result[CATALOG] = {ref: deepcopy(values[token]) for token, ref in selected.items()}
    return result


def expand_references(record):
    return expand_source_lists(expand_objects(record))


def expand_source_lists(record):
    """Validate storage and return independent copies at every adoption site."""
    catalog = record.get(CATALOG, {})
    if not isinstance(catalog, dict) or (CATALOG in record and not catalog):
        raise ValueError('战役来源目录无效或为空')
    for ref, value in catalog.items():
        if not isinstance(ref, str) or not ref or not isinstance(value, list):
            raise ValueError('战役来源目录必须保存具名完整列表')
        _check_reserved(value)
    if len({_token(v) for v in catalog.values()}) != len(catalog):
        raise ValueError('战役来源目录存在重复列表')
    used = Counter()

    def expand(value):
        if isinstance(value, dict):
            if REF in value or CATALOG in value:
                raise ValueError('战役来源占位符或目录位置非法')
            result = {}
            for key, child in value.items():
                if isinstance(child, dict) and REF in child:
                    ref = child[REF]
                    if (not _source_key(key) or set(child) != {REF}
                            or not isinstance(ref, str) or ref not in catalog):
                        raise ValueError('战役来源引用格式错误或悬空')
                    used[ref] += 1
                    result[key] = deepcopy(catalog[ref])
                else:
                    result[key] = expand(child)
            return result
        if isinstance(value, list):
            return [expand(child) for child in value]
        return value

    result = expand({k: v for k, v in record.items() if k != CATALOG})
    if set(used) != set(catalog) or any(n < 2 for n in used.values()):
        raise ValueError('战役来源目录存在未使用或未共用条目')
    return result
