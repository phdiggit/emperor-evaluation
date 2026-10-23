"""Store exact B source objects once per person, retaining every adoption link."""
from copy import deepcopy
import hashlib
import json

AXES = ('B1', 'B2', 'B4')
CATALOG = 'public_b_source_catalog'


def _encoded(source):
    # Field order is part of the roundtrip; only byte-identical objects merge.
    return json.dumps(source, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _entries(row):
    for axis in AXES:
        reading = row.get('axes', {}).get(axis, {}).get('public_reading')
        if not isinstance(reading, dict):
            raise ValueError(f'B来源登记缺少{axis}公开正文')
        yield reading
        items = reading.get('evidence_items', [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ValueError('B逐条依据须为对象列表')
        yield from items


def _catalog_index(catalog):
    if not isinstance(catalog, dict):
        raise ValueError('B来源缺少人物级唯一登记')
    index = {}
    for ref, source in catalog.items():
        if not isinstance(ref, str) or not ref or not isinstance(source, dict):
            raise ValueError('B来源登记须有稳定ID和完整对象')
        encoded = _encoded(source)
        if encoded in index:
            raise ValueError('B来源登记存在完全相同的副本')
        index[encoded] = ref
    return index


def validate_source_catalog(row):
    catalog = row.get(CATALOG)
    _catalog_index(catalog)
    used = set()
    for entry in _entries(row):
        if 'sources' in entry:
            raise ValueError('B正文和逐条依据只引用来源，不得内嵌副本')
        refs = entry.get('source_refs')
        if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in catalog for ref in refs):
            raise ValueError('B来源引用缺失或未在本人登记')
        used.update(refs)
    if set(catalog) - used:
        raise ValueError('B来源登记包含未被正文或依据引用的对象')


def expand_readings(row):
    """Return private readings, preserving source order and repeated adoption."""
    validate_source_catalog(row)
    catalog = row[CATALOG]
    readings = {axis: deepcopy(row['axes'][axis]['public_reading']) for axis in AXES}
    for reading in readings.values():
        for entry in [reading, *reading.get('evidence_items', [])]:
            expanded = {('sources' if key == 'source_refs' else key):
                        [deepcopy(catalog[ref]) for ref in value] if key == 'source_refs' else value
                        for key, value in entry.items()}
            entry.clear()
            entry.update(expanded)
    return readings


def pack_sources(row):
    """Explicitly pack expanded B readings; existing catalog IDs survive edits.

    Hashes assign IDs only to newly registered objects. Validation never requires
    an edited source to match its initial hash, and no similar prose is merged.
    """
    result = deepcopy(row)
    catalog = result.setdefault(CATALOG, {})
    index = _catalog_index(catalog)
    for entry in _entries(result):
        if 'source_refs' in entry or not isinstance(entry.get('sources'), list):
            raise ValueError('B来源登记输入须为展开正文，不得混合两种结构')
        refs = []
        for source in entry['sources']:
            if not isinstance(source, dict):
                raise ValueError('B来源须为完整对象')
            encoded = _encoded(source)
            ref = index.get(encoded)
            if ref is None:
                ref = 'BS-' + hashlib.sha256(encoded).hexdigest()[:16]
                if ref in catalog and _encoded(catalog[ref]) != encoded:
                    raise ValueError('B来源ID冲突')
                catalog[ref] = deepcopy(source)
                index[encoded] = ref
            refs.append(ref)
        packed = {('source_refs' if key == 'sources' else key):
                  refs if key == 'sources' else value for key, value in entry.items()}
        entry.clear()
        entry.update(packed)
    validate_source_catalog(result)
    return result
