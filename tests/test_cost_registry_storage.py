from copy import deepcopy

import pytest

from emperor_v4.evaluation.cost_registry_storage import (
    CATALOG, MARKER, REF, STORAGE, SHARD_SCHEMA,
    compact_shard, expand_shard,
)
from emperor_v4.evaluation.formal_json_store import load_json, write_json
from emperor_v4.json_format import json_text


def sample():
    refs = ['docs/' + '出处' * 40 + '.md#位置', '重复', '重复']
    return {'schema_version': SHARD_SCHEMA, 'source_pool': 'synthetic', 'record_count': 1,
            'records': [{'cycle_identity': 'synthetic-cycle', 'boundary': '周期与归责独立保留',
                         'source_refs': refs, 'axes': {
                             'A': {'grade': 2, 'source_refs': deepcopy(refs)},
                             'P': {'grade': 1, 'source_refs': list(reversed(refs))}}}]}


def test_round_trip_order_determinism_and_private_lists(tmp_path):
    original = sample(); before = deepcopy(original)
    packed = compact_shard(original)
    assert packed[MARKER] == STORAGE
    assert len(packed['records'][0][CATALOG]) == 1
    restored = expand_shard(packed)
    assert json_text(restored) == json_text(original) == json_text(before)
    assert compact_shard(restored) == packed
    path = tmp_path / 'shard.json'; path.write_bytes(json_text(packed).encode('utf-8'))
    assert load_json(path) == original
    content = path.read_bytes()
    write_json(path, load_json(path))
    assert path.read_bytes() == content
    restored['records'][0]['source_refs'].append('调用方修改')
    assert restored['records'][0]['axes']['A']['source_refs'] == before['records'][0]['source_refs']
    assert original == before
    assert sample()['records'][0]['axes']['P']['source_refs'] == expand_shard(packed)['records'][0]['axes']['P']['source_refs']


@pytest.mark.parametrize('case', ['version', 'marker', 'dangling'])
def test_invalid_storage_fails_closed(case):
    packed = compact_shard(sample())
    if case == 'version': packed[MARKER] = 'unknown'
    elif case == 'marker': packed.pop(MARKER)
    else: packed['records'][0]['source_refs'][REF] = 'missing'
    with pytest.raises(ValueError): expand_shard(packed)


def test_plain_shards_and_empty_sources_are_preserved():
    data = sample(); data['records'][0] = {'cycle_identity': 'plain', 'source_refs': []}
    assert expand_shard(data) == data
    assert expand_shard(compact_shard(data)) == data
    with pytest.raises(ValueError): compact_shard(compact_shard(data))
