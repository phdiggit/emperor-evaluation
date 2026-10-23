from copy import deepcopy
import json

import pytest

from emperor_v4.evaluation.formal_reading_texts import (
    C_SCHEMA, STORAGE, FIELD_STORAGE, FINANCE_SCHEMAS, MARKER, CATALOG, REF, FIELDS,
    compact_reading_texts, expand_reading_texts,
)
from emperor_v4.evaluation.formal_json_store import load_json, write_json


def sample():
    text = '独立构造的来源摘要，保留换行\n空格、引号"和标点。' * 12
    return {'schema_version': 'formal-json-polity-shard-v1', 'polity': '合成朝',
            'collections': {'records': {'positions': [0, 1], 'records': [
                {'ruler_id': 'X', 'basis': text, 'public_reading': {
                    'story': text, 'evidence_items': [{'id': 'A', 'text': text}],
                    'empty': [], 'none': None, 'zero': 0}},
                {'ruler_id': 'Y', 'public_reading': {'story': text + '不同', 'window': text}},
            ]}}}


def test_exact_round_trip_preserves_text_order_fields_and_independent_records():
    original = sample()
    saved = deepcopy(original)
    packed = compact_reading_texts(original)
    assert original == saved
    assert packed[MARKER] == STORAGE
    assert len(json.dumps(packed, ensure_ascii=False)) < len(json.dumps(original, ensure_ascii=False))
    assert packed['collections']['records']['records'][0]['basis'] == original['collections']['records']['records'][0]['basis']
    assert expand_reading_texts(packed) == original
    # Different wording must remain separate; no normalization or semantic merge.
    assert packed['collections']['records']['records'][1]['public_reading']['story'].endswith('不同')
    expanded = expand_reading_texts(packed)
    expanded['collections']['records']['records'][0]['public_reading']['evidence_items'].append({})
    assert expand_reading_texts(packed) == original
    assert compact_reading_texts(expand_reading_texts(packed)) == packed
    with pytest.raises(ValueError):
        compact_reading_texts(packed)


@pytest.mark.parametrize('damage', ['missing', 'outside', 'version'])
def test_rejects_corrupt_or_misplaced_references(damage):
    packed = compact_reading_texts(sample())
    if damage == 'version': packed[MARKER] = 'unknown'
    elif damage == 'outside': packed['collections']['records']['records'][0]['basis'] = {REF: next(iter(packed[CATALOG]))}
    else: packed['collections']['records']['records'][0]['public_reading']['story'] = {REF: 'missing'}
    with pytest.raises(ValueError): expand_reading_texts(packed)


def test_uncompressed_or_small_reading_needs_no_catalog():
    original = {'collections': {'records': {'records': [{'public_reading': {'story': '短文'}}]}}}
    assert compact_reading_texts(original) == original
    assert expand_reading_texts(original) == original
    original['collections']['records']['records'][0]['public_reading']['story'] = {REF: 'orphan'}
    with pytest.raises(ValueError):
        expand_reading_texts(original)


def test_router_expands_partial_load_and_repeated_writes_are_byte_identical(tmp_path):
    path = tmp_path / 'formal.json'
    rows = sample()['collections']['records']['records']
    rows[0]['polity'] = '合成朝'
    rows[1]['polity'] = '合成朝'
    payload = {'schema_id': C_SCHEMA, 'records': rows}
    write_json(path, payload, ruler_polities={}, route=True)
    shard = path.with_suffix('') / '合成朝.json'
    assert json.loads(shard.read_text(encoding='utf-8'))[MARKER] == STORAGE
    before = {p: p.read_bytes() for p in (path, shard)}
    assert load_json(path) == payload
    assert load_json(path, polities=['合成朝']) == payload
    write_json(path, load_json(path), ruler_polities={})
    assert before == {p: p.read_bytes() for p in before}
    other = tmp_path / 'other.json'
    write_json(other, {**payload, 'schema_id': 'unrelated'}, ruler_polities={}, route=True)
    assert MARKER not in json.loads((other.with_suffix('') / '合成朝.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('schema', sorted(FINANCE_SCHEMAS))
def test_finance_public_fields_expand_without_touching_adjudication(schema, tmp_path):
    text = '独立合成的公开来源与说明。' * 30
    payload = {'schema_id': schema, 'scores': [
        {'ruler_id': 'X', 'polity': '合成朝', 'score': 3,
         'adjudication_reason': text, 'public_story': text,
         'public_related_source_refs': [{'path': text}, {'path': text}],
         'public_evidence_items': [{'id': 'A', 'text': text}]},
    ]}
    original = deepcopy(payload)
    path = tmp_path / 'formal.json'
    write_json(path, payload, ruler_polities={}, route=True)
    shard = path.with_suffix('') / '合成朝.json'
    packed = json.loads(shard.read_text(encoding='utf-8'))
    assert packed[MARKER] == FIELD_STORAGE
    assert set(packed[FIELDS]) == {k for k in payload['scores'][0] if k.startswith('public_')}
    stored = packed['collections']['scores']['records'][0]
    assert stored['adjudication_reason'] == text
    assert stored['score'] == 3
    assert stored['public_evidence_items'][0]['id'] == 'A'
    assert load_json(path) == original == payload
    assert load_json(path, polities=['合成朝']) == original
    before = shard.read_bytes()
    write_json(path, load_json(path), ruler_polities={})
    assert shard.read_bytes() == before
    loaded = load_json(path)
    loaded['scores'][0]['public_related_source_refs'].append({})
    assert load_json(path) == original


@pytest.mark.parametrize('fields', [None, ['public_story', 'public_story']])
def test_field_scoped_storage_rejects_invalid_declarations(fields):
    shard = sample()
    packed = compact_reading_texts(shard, fields=['public_reading', 'public_story'])
    packed[FIELDS] = fields
    with pytest.raises(ValueError):
        expand_reading_texts(packed)


def test_v1_rejects_a_field_declaration_and_v2_rejects_outside_references():
    packed = compact_reading_texts(sample())
    packed[FIELDS] = ['public_reading']
    with pytest.raises(ValueError):
        expand_reading_texts(packed)
    packed = compact_reading_texts(sample(), fields=['public_story', 'public_reading'])
    packed['collections']['records']['records'][0]['public_undeclared'] = {REF: next(iter(packed[CATALOG]))}
    with pytest.raises(ValueError):
        expand_reading_texts(packed)
