"""Store exact B source objects once per person, retaining every adoption link."""
from copy import deepcopy
import hashlib
import json
import re
from urllib.parse import quote

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


def supplemental_sources(reading):
    """List only references that are absent from the individual claims."""
    claim_refs = {
        _encoded(source)
        for evidence in reading['evidence_items']
        for source in evidence['sources']
    }
    return [source for source in reading['sources'] if _encoded(source) not in claim_refs]


def battle_source_routes(context):
    """Resolve only unique bindings within the cited public registry shard."""
    candidates = {}
    for battle_id in context['indexed_ids']:
        location = context['locations'].get(battle_id)
        if not location:
            continue
        shard = location.partition('#')[0]
        candidates[location] = {battle_id}
        record = context['battles'][battle_id]
        groups = {record.get('campaign_group_ref')}
        groups.update(phase.get('campaign_group_ref') for phase in record.get('subject_phase_views') or [])
        for group in groups - {None, ''}:
            candidates.setdefault(f'{shard}#campaign_group_ref={group}', set()).add(battle_id)
    return {path: next(iter(ids)) for path, ids in candidates.items() if len(ids) == 1}


def display_sources(sources, *, battle_routes=None):
    """Render book citations separately from references to project decisions."""
    from .second_item_c_source_display import bibliographic_source

    result = []
    for source in sources:
        citation = source.get('public_citation')
        if citation:
            display = {'kind': '史料原文', 'label': citation['title'], 'url': citation['url'],
                       'context': citation['context'], 'quote': citation['quote']}
        else:
            label = source['label'].removeprefix('原裁决引用：')
            if label == 'CROSS_ITEM::FIRST_ITEM_CLOSED_STOCK':
                label = '第一项已结算的控制成果'
            label = re.sub(r'^[^：\s]+\.(?:md|jsonl?)：', '', label)
            label = re.sub(r'[；，]?原文锚[PL]\d+(?:[—–-][PL]\d+)?$', '', label)
            if re.fullmatch(r'[^《》]+\.(?:md|jsonl?)|[a-z0-9_]+(?:-[a-z0-9_]+){2,}', label, re.I):
                title = bibliographic_source({'source_title': source['path'], 'source_locator': ''})['source_title']
                label = title or '所引项目记录'
            if source['kind'] in {'现行规则', '现行空间尺度'}:
                kind = '项目规则'
            elif label.startswith('《') and source['kind'] == '裁决中保留的书目或共享锚引用':
                kind = '所引书目'
            elif source['kind'] in {'现行军事材料记录', '既有军事材料记录'}:
                kind = '战役资料'
            else:
                kind = '项目依据'
            display = {'kind': kind, 'label': label}
            if kind == '战役资料' and battle_routes:
                battle_id = battle_routes.get(source['path'])
                if battle_id and source['path'].partition('=')[2] == source.get('binding'):
                    display['archive_href'] = 'military.html#battle=' + quote(battle_id, safe='')
        if display not in result:
            result.append(display)
    return result


def display_reading(reading, *, battle_routes=None):
    return {**reading, 'sources': display_sources(supplemental_sources(reading), battle_routes=battle_routes),
            'evidence_items': [{**item, 'sources': display_sources(item['sources'], battle_routes=battle_routes)}
                               for item in reading['evidence_items']]}


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
