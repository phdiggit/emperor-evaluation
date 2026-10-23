"""Lossless reason storage for retained profile unit dispositions.

This codec does not create dispositions or infer reasons from their status.
"""
from copy import deepcopy
from pathlib import Path

from .formal_json_store import load_json, write_json

STORAGE = 'profile-unit-reason-catalog-v1'


def _units(payload: dict) -> list[dict]:
    units = payload.get('units')
    if not isinstance(units, list) or any(not isinstance(u, dict) for u in units):
        raise ValueError('单元处置缺少units对象列表')
    return units


def expand_reasons(payload: dict) -> dict:
    """Validate compact storage and return a private, complete reading payload."""
    from .profile_unit_tables import expand_unit_table
    payload = expand_unit_table(payload)
    if payload.get('reason_storage') != STORAGE:
        raise ValueError('单元理由目录版本不合法')
    catalog = payload.get('reason_catalog')
    if not isinstance(catalog, dict) or any(
        not isinstance(k, str) or not k or not isinstance(v, str) or not v.strip()
        for k, v in catalog.items()
    ):
        raise ValueError('单元理由目录不合法')
    if len(set(catalog.values())) != len(catalog):
        raise ValueError('单元理由目录存在重复正文')
    used = set()
    for unit in _units(payload):
        ref = unit.get('reason_ref')
        if 'reason' in unit:
            raise ValueError('单元不得内嵌理由副本')
        if not isinstance(ref, str) or ref not in catalog:
            raise ValueError('单元理由引用缺失或悬空')
        used.add(ref)
    if used != set(catalog):
        raise ValueError('单元理由目录存在未使用条目')
    result = deepcopy(payload)
    result.pop('reason_storage')
    result.pop('reason_catalog')
    result['units'] = [
        {('reason' if k == 'reason_ref' else k): (catalog[v] if k == 'reason_ref' else v)
         for k, v in unit.items()}
        for unit in result['units']
    ]
    return result


def compact_reasons(payload: dict) -> dict:
    """Encode complete authored reasons; stable for the same ordered input."""
    if 'reason_storage' in payload or 'reason_catalog' in payload:
        expand_reasons(payload)
        return deepcopy(payload)
    catalog = {}
    refs = {}
    for unit in _units(payload):
        reason = unit.get('reason')
        if 'reason_ref' in unit or not isinstance(reason, str) or not reason.strip():
            raise ValueError('单元缺少完整理由或混用了引用')
        if reason not in refs:
            ref = str(len(refs))
            refs[reason] = ref
            catalog[ref] = reason
    result = deepcopy(payload)
    result['units'] = [
        {('reason_ref' if k == 'reason' else k): (refs[v] if k == 'reason' else v)
         for k, v in unit.items()}
        for unit in result['units']
    ]
    result.update(reason_storage=STORAGE, reason_catalog=catalog)
    return result


def load_unit_dispositions(path: Path) -> dict:
    return expand_reasons(load_json(path))


def write_unit_dispositions(path: Path, payload: dict) -> None:
    from .profile_unit_tables import C1_SCHEMA, M4_SCHEMA, compact_unit_table
    compact = compact_reasons(payload)
    if payload.get('schema_version') == C1_SCHEMA:
        compact = compact_unit_table(compact)
    elif payload.get('schema_version') == M4_SCHEMA:
        compact = compact_unit_table(compact, list_columns=('source_refs',))
    write_json(path, compact, route=False)
