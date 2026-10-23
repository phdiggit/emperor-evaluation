from copy import deepcopy
import json

import pytest

from emperor_v4.evaluation.third_item_b_sources import (
    AXES, CATALOG, expand_readings, pack_sources, validate_source_catalog,
)


def sample():
    source = dict(path='synthetic.md#window', label='合成来源', kind='现存摘要', binding='责任窗口')
    readings = {axis: dict(story=f'{axis}正文', sources=[deepcopy(source)], evidence_items=[
        dict(basis='保留本人的采用范围。', sources=[deepcopy(source), deepcopy(source)]),
        dict(basis='空列表保持为空。', sources=[]),
    ]) for axis in AXES}
    readings['B4']['sources'].append(dict(source, binding='另一窗口'))
    return dict(ruler_id='synthetic', score=7, axes={axis: dict(public_reading=reading) for axis, reading in readings.items()})


def expanded_row(packed):
    row = deepcopy(packed)
    for axis, reading in expand_readings(packed).items():
        row['axes'][axis]['public_reading'] = reading
    return row


def test_source_roundtrip_preserves_order_repeated_adoption_and_private_copies():
    original = sample()
    before = deepcopy(original)
    packed = pack_sources(original)
    assert original == before
    assert len(packed[CATALOG]) == 2
    refs = packed['axes']['B1']['public_reading']['source_refs']
    assert packed['axes']['B2']['public_reading']['evidence_items'][0]['source_refs'] == refs * 2
    restored = expanded_row(packed)
    del restored[CATALOG]
    assert json.dumps(restored, ensure_ascii=False) == json.dumps(original, ensure_ascii=False)
    assert pack_sources(expanded_row(packed)) == packed
    restored['axes']['B1']['public_reading']['sources'][0]['binding'] = '消费端改动'
    assert expand_readings(packed)['B1']['sources'] == original['axes']['B1']['public_reading']['sources']


@pytest.mark.parametrize('problem', ['dangling', 'inline', 'duplicate', 'missing_catalog', 'unused', 'missing_refs', 'invalid_refs'])
def test_invalid_source_storage_fails_closed(problem):
    packed = pack_sources(sample())
    entry = packed['axes']['B2']['public_reading']['evidence_items'][0]
    if problem == 'dangling':
        entry['source_refs'] = ['ANOTHER-PERSON-SOURCE']
    elif problem == 'inline':
        entry['sources'] = []
    elif problem == 'duplicate':
        packed[CATALOG]['duplicate'] = deepcopy(next(iter(packed[CATALOG].values())))
    elif problem == 'missing_catalog':
        del packed[CATALOG]
    elif problem == 'unused':
        packed[CATALOG]['unused'] = dict(path='unused.md')
    elif problem == 'missing_refs':
        del entry['source_refs']
    else:
        entry['source_refs'] = 'not-a-list'
    with pytest.raises(ValueError):
        expand_readings(packed)


def test_edited_catalog_keeps_stable_ids_through_refresh():
    packed = pack_sources(sample())
    ref = packed['axes']['B1']['public_reading']['source_refs'][0]
    packed[CATALOG][ref]['binding'] = '修订后的责任窗口'
    validate_source_catalog(packed)
    readings = expand_readings(packed)
    assert readings['B4']['evidence_items'][0]['sources'][1]['binding'] == '修订后的责任窗口'
    assert pack_sources(expanded_row(packed)) == packed


def test_packing_does_not_accept_mixed_or_already_packed_sources():
    with pytest.raises(ValueError, match='混合两种结构'):
        pack_sources(pack_sources(sample()))


def test_only_exact_objects_merge_including_binding_kind_and_field_order():
    row = sample()
    sources = row['axes']['B1']['public_reading']['sources']
    original = sources[0]
    sources.extend([dict(original, kind='其他采用角色'), dict(reversed(list(original.items())))])
    packed = pack_sources(row)
    assert len(set(packed['axes']['B1']['public_reading']['source_refs'])) == len(sources)
