"""Store identical authored source notes once, without inferring their meaning."""
from copy import deepcopy

CATALOG = 'public_source_note_catalog'
NOTE = 'public_source_note'
REF = 'public_source_note_ref'


def _rows(payload):
    rows = payload.get('scores', payload.get('records'))
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError('第二项C来源说明缺少人物记录列表')
    return rows


def source_note_records(payload):
    catalog = payload.get(CATALOG)
    if not isinstance(catalog, dict) or any(
        not isinstance(k, str) or not k or not isinstance(v, str) or not v.strip()
        for k, v in catalog.items()
    ):
        raise ValueError('第二项C来源说明目录缺失或无效')
    if len(set(catalog.values())) != len(catalog):
        raise ValueError('第二项C来源说明目录正文重复')
    used = set()
    for row in _rows(payload):
        ref = row.get(REF)
        if NOTE in row:
            raise ValueError('第二项C不得内嵌来源说明副本')
        if not isinstance(ref, str) or ref not in catalog:
            raise ValueError('第二项C来源说明引用缺失或悬空')
        used.add(ref)
    if used != set(catalog):
        raise ValueError('第二项C来源说明目录存在未使用条目')
    return [{(NOTE if k == REF else k): (catalog[v] if k == REF else deepcopy(v))
             for k, v in row.items()} for row in _rows(payload)]


def compact_source_notes(payload):
    """Return a compact private payload; accept expanded authoring input."""
    if CATALOG in payload:
        source_note_records(payload)
        return deepcopy(payload)
    refs, catalog = {}, {}
    for row in _rows(payload):
        note = row.get(NOTE)
        if REF in row or not isinstance(note, str) or not note.strip():
            raise ValueError('第二项C缺少直接维护的来源说明或混用引用')
        if note not in refs:
            refs[note] = str(len(refs))
            catalog[refs[note]] = note
    result = deepcopy(payload)
    key = 'scores' if 'scores' in result else 'records'
    result[key] = [{(REF if k == NOTE else k): (refs[v] if k == NOTE else deepcopy(v))
                    for k, v in row.items()} for row in _rows(payload)]
    result[CATALOG] = catalog
    return result
