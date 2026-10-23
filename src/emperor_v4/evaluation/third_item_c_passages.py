"""Store exact C source excerpts once per person; keep adoption links separate."""
from copy import deepcopy
import hashlib
import json


def _encoded(passage):
    # Preserve field order as well as values so expanded output is unchanged.
    return json.dumps(passage, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _entries(authored):
    yield from authored.get('evidence_items', [])
    yield from authored.get('source_reviews', {}).values()


def validate_passages(authored):
    catalog = authored.get('source_passage_catalog')
    if not isinstance(catalog, dict):
        raise ValueError('C来源摘录缺少人物级唯一登记')
    seen = set()
    for ref, passage in catalog.items():
        if not isinstance(ref, str) or not ref or not isinstance(passage, dict):
            raise ValueError('C来源摘录登记须有稳定ID和完整对象')
        encoded = _encoded(passage)
        if encoded in seen:
            raise ValueError('C来源摘录登记存在完全相同的副本')
        seen.add(encoded)
    used = set()
    for entry in _entries(authored):
        if 'source_passages' in entry:
            raise ValueError('C材料和复核只引用来源摘录，不得内嵌副本')
        if 'source_passage_refs' not in entry:
            continue
        refs = entry['source_passage_refs']
        if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in catalog for ref in refs):
            raise ValueError('C来源摘录引用缺失或未在本人登记')
        used.update(refs)
    if set(catalog) - used:
        raise ValueError('C来源摘录登记包含未被材料或复核引用的对象')


def expand_entry(authored, entry):
    """Return a private reading copy, preserving absent versus empty excerpts."""
    catalog = authored['source_passage_catalog']
    return {
        ('source_passages' if key == 'source_passage_refs' else key):
        ([deepcopy(catalog[ref]) for ref in value] if key == 'source_passage_refs' else deepcopy(value))
        for key, value in entry.items()
    }


def expand_passages(authored):
    validate_passages(authored)
    result = deepcopy(authored)
    result.pop('source_passage_catalog')
    if 'evidence_items' in result:
        result['evidence_items'] = [expand_entry(authored, e) for e in authored['evidence_items']]
    if 'source_reviews' in result:
        result['source_reviews'] = {key: expand_entry(authored, e) for key, e in authored['source_reviews'].items()}
    return result


def pack_passages(authored):
    """Explicitly register authored excerpts; never merge similar text or roles.

    IDs are assigned from exact contents when registering. Later edits retain
    the ID; validation checks references and sources, not a frozen text hash.
    """
    if 'source_passage_catalog' in authored:
        raise ValueError('C摘录登记输入须为展开正文，不得混合两种结构')
    result = deepcopy(authored)
    catalog = result['source_passage_catalog'] = {}
    for entry in _entries(result):
        if 'source_passage_refs' in entry:
            raise ValueError('C展开正文不得含未解析的摘录引用')
        if 'source_passages' not in entry:
            continue
        refs = []
        for passage in entry['source_passages']:
            encoded = _encoded(passage)
            ref = 'P-' + hashlib.sha256(encoded).hexdigest()[:16]
            if ref in catalog and _encoded(catalog[ref]) != encoded:
                raise ValueError('C来源摘录ID冲突')
            catalog.setdefault(ref, deepcopy(passage))
            refs.append(ref)
        replacement = {('source_passage_refs' if key == 'source_passages' else key):
                       refs if key == 'source_passages' else value for key, value in entry.items()}
        entry.clear()
        entry.update(replacement)
    validate_passages(result)
    return result
