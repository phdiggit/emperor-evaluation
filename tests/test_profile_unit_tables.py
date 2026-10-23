from copy import deepcopy
import json

import pytest

from emperor_v4.evaluation.profile_unit_tables import (
    STORAGE, LIST_STORAGE, C1_SCHEMA, M4_SCHEMA, TABLE_SCHEMAS, MARKER, COLUMNS, ROWS, DICTIONARIES, LIST_DICTIONARIES,
    compact_unit_table, expand_unit_table,
)
from emperor_v4.evaluation.profile_unit_reasons import compact_reasons, load_unit_dispositions, write_unit_dispositions


def sample():
    return {'schema_version': C1_SCHEMA, 'units': [
        {'unit_id': f'synthetic-{i}', 'source_ref': '合成来源路径/' * 20,
         'status': '合成独立处置', 'reason': '独立构造的完整理由。' * 8,
         'optional': None, 'links': ['independent-source'], 'flag': False}
        for i in range(12)], 'note': '保留顺序与原值'}


def test_round_trip_preserves_order_values_and_independent_mutable_cells():
    original = sample(); before = deepcopy(original)
    packed = compact_unit_table(original)
    assert packed[MARKER] == STORAGE
    assert json.dumps(expand_unit_table(packed), ensure_ascii=False) == json.dumps(original, ensure_ascii=False)
    assert original == before
    assert len(json.dumps(packed, ensure_ascii=False)) < len(json.dumps(original, ensure_ascii=False))
    assert compact_unit_table(expand_unit_table(packed)) == compact_unit_table(packed) == packed
    expanded = expand_unit_table(packed)
    expanded['units'][0]['links'].append('consumer edit')
    assert expanded['units'][1]['links'] == original['units'][1]['links']
    assert expand_unit_table(packed) == original


def test_mixed_layouts_missing_fields_and_small_inputs_stay_inline():
    for data in ({'units': []}, {'units': [{}]}, {'units': [{'x': 1}]},
                 {'units': [{'x': None}, {}]}, {'units': [{'x': 1, 'y': 2}, {'y': 2, 'x': 1}]}):
        assert compact_unit_table(data) == data
        assert expand_unit_table(data) == data


@pytest.mark.parametrize('damage', ['version', 'row_width', 'index', 'boolean'])
def test_invalid_table_fails_closed(damage):
    packed = compact_unit_table(sample()); index = packed[COLUMNS].index('source_ref')
    if damage == 'version': packed[MARKER] = 'unknown'
    elif damage == 'row_width': packed[ROWS][0].append('extra')
    else: packed[ROWS][0][index] = True if damage == 'boolean' else 999
    with pytest.raises(ValueError): expand_unit_table(packed)


@pytest.mark.parametrize('schema', sorted(TABLE_SCHEMAS))
def test_common_json_api_preserves_audit_objects_and_deterministic_storage(tmp_path, schema):
    from emperor_v4.evaluation.formal_json_store import load_json, write_json, json_read_session
    data = list_sample()
    data['schema_version'] = schema
    original = deepcopy(data)
    path = tmp_path / 'audit.json'
    write_json(path, data, route=False)
    assert data == original
    assert MARKER in json.loads(path.read_text(encoding='utf-8'))
    with json_read_session():
        first = load_json(path)
        first['units'][0]['links'].append('consumer edit')
        assert load_json(path) == original
    before = path.read_bytes()
    write_json(path, load_json(path), route=False)
    assert path.read_bytes() == before
    raw = json.loads(before)
    raw[MARKER] = 'unknown'
    path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises(ValueError):
        load_json(path)


def test_unknown_audit_schema_is_not_automatically_repacked(tmp_path):
    from emperor_v4.evaluation.formal_json_store import load_json, write_json
    data = {**sample(), 'schema_version': 'independent-other-audit'}
    path = tmp_path / 'other.json'
    write_json(path, data, route=False)
    assert MARKER not in json.loads(path.read_text(encoding='utf-8'))
    assert load_json(path) == data


def test_file_round_trip_composes_reason_catalog_and_repeat_write(tmp_path):
    path = tmp_path / 'units.json'
    original = sample()
    write_unit_dispositions(path, original)
    physical = json.loads(path.read_text(encoding='utf-8'))
    assert physical[MARKER] == STORAGE
    assert 'units' not in physical
    assert physical['reason_storage'] == compact_reasons(original)['reason_storage']
    assert load_unit_dispositions(path) == original
    before = path.read_bytes()
    write_unit_dispositions(path, load_unit_dispositions(path))
    assert path.read_bytes() == before
    # Non-C1 audits retain the established object-list storage.
    other = {**sample(), 'schema_version': 'other-audit'}
    write_unit_dispositions(path, other)
    assert MARKER not in json.loads(path.read_text(encoding='utf-8'))
    assert load_unit_dispositions(path) == other


def list_sample():
    data = sample()
    data['schema_version'] = M4_SCHEMA
    for i, unit in enumerate(data['units']):
        unit['source_refs'] = [] if i == 0 else ['source-b/' * 30, 'source-a/' * 30, 'source-b/' * 30]
    return data


def test_list_columns_preserve_order_duplicates_empty_values_and_independence(tmp_path):
    data = list_sample(); before = deepcopy(data)
    packed = compact_unit_table(data, list_columns=('source_refs',))
    assert packed[MARKER] == LIST_STORAGE
    assert list(packed[LIST_DICTIONARIES]) == ['source_refs']
    assert json.dumps(expand_unit_table(packed), ensure_ascii=False) == json.dumps(data, ensure_ascii=False)
    assert data == before
    assert compact_unit_table(packed) == packed
    assert compact_unit_table(expand_unit_table(packed), list_columns=('source_refs',)) == packed
    expanded = expand_unit_table(packed)
    expanded['units'][1]['source_refs'].append('consumer edit')
    assert expanded['units'][2]['source_refs'] == data['units'][2]['source_refs']
    path = tmp_path / 'm4.json'
    write_unit_dispositions(path, data)
    assert load_unit_dispositions(path) == data
    saved = path.read_bytes()
    write_unit_dispositions(path, load_unit_dispositions(path))
    assert path.read_bytes() == saved


@pytest.mark.parametrize('damage', ['missing', 'negative', 'boolean'])
def test_list_storage_rejects_invalid_catalogs_and_indices(damage):
    packed = compact_unit_table(list_sample(), list_columns=('source_refs',))
    if damage == 'missing': packed.pop(LIST_DICTIONARIES)
    else: packed[ROWS][1][packed[COLUMNS].index('source_refs')][0] = True if damage == 'boolean' else -1
    with pytest.raises(ValueError): expand_unit_table(packed)
