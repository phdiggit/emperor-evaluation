"""Store identical authored source notes once, without inferring their meaning."""
from copy import deepcopy

CATALOG = 'public_source_note_catalog'
NOTE = 'public_source_note'
REF = 'public_source_note_ref'

STANDARD_SOURCE_NOTE = (
    '来源分为逐条采用的依据和相关材料汇集。材料汇集保留原有摘录、摘要及裁决线索，'
    '不表示其中每份材料都能证明每一条叙述；具体采用范围与推断性质见各条说明。'
)
SOURCE_GUIDE = (
    '“逐条史源”列出本卡绑定的来源，采用范围见各卡。'
    '“材料汇集”保存本人物本轴的相关摘录、摘要和裁决线索，供回查。汇集材料与各条叙述的支持关系尚未逐条核实。'
)
STANDARD_COLLECTION_SCOPE = (
    '本条沿用现行正式裁决叙述；下列人物材料尚未逐条核实与本条事实的支持关系，不据材料同列推定已经获证。'
)


def specific_source_note(note: str) -> str:
    """Separate the exact common introduction from a person's own source note."""
    first = note.strip()
    if first == STANDARD_SOURCE_NOTE:
        return ''
    suffix = first.removeprefix(STANDARD_SOURCE_NOTE)
    return suffix.lstrip() if suffix != first and suffix[:1].isspace() else note


def uses_shared_collection_scope(item: dict) -> bool:
    return (item.get('source_binding_kind') == 'MATERIAL_COLLECTION'
            and item.get('public_scope') == STANDARD_COLLECTION_SCOPE)



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
