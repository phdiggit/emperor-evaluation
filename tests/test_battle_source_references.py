from copy import deepcopy
import json
import pytest

from emperor_v4.evaluation.battle_source_references import (
    CATALOG, REF, compact_references, expand_references,
)
from emperor_v4.evaluation.battle_registry_store import load_battle_registry, write_battle_registry


def sample():
    refs = ['docs/' + 'long-source-' * 9 + '.md#location', 'same', 'same']
    return {'war_event_id': 'synthetic-a', 'dynasty_partition': 'p1',
            'source_refs': refs, 'views': [
                {'source_anchor_refs': deepcopy(refs), 'scope': '甲'},
                {'axis_source_refs': {'A': deepcopy(refs)}, 'scope': '乙'},
                {'source_refs': list(reversed(refs)), 'scope': '不同顺序'},
            ], 'source_quotes': ['独立原文']}


def test_round_trip_preserves_order_adoption_and_independent_copies():
    record = sample(); before = deepcopy(record)
    compact = compact_references(record)
    assert len(compact[CATALOG]) == 1
    assert compact['source_refs'] == compact['views'][0]['source_anchor_refs']
    assert compact['views'][2]['source_refs'] == record['views'][2]['source_refs']
    restored = expand_references(compact)
    assert restored == before == record
    assert json.dumps(restored, ensure_ascii=False) == json.dumps(before, ensure_ascii=False)
    assert compact_references(restored) == compact
    restored['source_refs'].append('consumer mutation')
    assert restored['views'][0]['source_anchor_refs'] == before['source_refs']
    assert record == before


@pytest.mark.parametrize('case', ['missing', 'wrong_place', 'cycle'])
def test_invalid_reference_storage_is_rejected(case):
    data = compact_references(sample()); ref = data['source_refs'][REF]
    if case == 'missing': data[CATALOG].pop(ref)
    elif case == 'wrong_place': data['text'] = data.pop('source_refs')
    else: data[CATALOG][ref] = [{REF: ref}]
    with pytest.raises(ValueError): expand_references(data)


@pytest.mark.parametrize('with_phase_objects', [False, True])
def test_military_browser_expands_raw_shards(tmp_path, with_phase_objects):
    import shutil, subprocess
    from pathlib import Path
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable')
    source = (Path(__file__).resolve().parents[1] / 'reader/military-archive.js').read_text(encoding='utf-8')
    function = source.split('  function expandBattleSourceReferences(record) {', 1)[1].split('  async function json(path)', 1)[0]
    script = 'const assert = require("node:assert/strict");\nfunction expandBattleSourceReferences(record) {' + function
    original = sample()
    if with_phase_objects:
        value = {'reason': '相同依据与归责限制。' * 25, 'source_refs': original['source_refs']}
        original['subject_phase_views'] = [{'phase_id': key, 'ruler_binding': deepcopy(value)} for key in ('a', 'b')]
    script += '\nconst original = ' + json.dumps(original, ensure_ascii=False) + ';'
    script += '\nconst packed = ' + json.dumps(compact_references(original), ensure_ascii=False) + ';'
    script += '''
const expanded = expandBattleSourceReferences(packed);
assert.deepEqual(expanded, original);
expanded.source_refs.push("consumer change");
assert.deepEqual(expanded.views[0].source_anchor_refs, original.source_refs);
assert.deepEqual(expandBattleSourceReferences(original), original);
packed.source_refs.source_list_ref = "missing";
assert.throws(() => expandBattleSourceReferences(packed));
'''
    path = tmp_path / 'test.cjs'; path.write_text(script, encoding='utf-8')
    subprocess.run([node, str(path)], check=True, capture_output=True, text=True)


def test_military_index_loader_expands_raw_shards(tmp_path):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'reader/_build_military_archive_core.py'
    spec = importlib.util.spec_from_file_location('battle_core_test', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    shard = tmp_path / 'shard.json'
    shard.write_text(json.dumps({'schema_version': 'battle-registry-shard-v1', 'records': [compact_references(sample())]}), encoding='utf-8')
    assert module._load(shard)['records'] == [sample()]


def test_store_partitions_order_round_trip_and_repeat_write(tmp_path):
    a = sample(); b = deepcopy(a); b.update(war_event_id='synthetic-b', dynasty_partition='p2')
    payload = {'schema_version': 'synthetic-content', 'records': [b, a], 'extra': {'source_refs': ['metadata']}}
    before = deepcopy(payload); path = tmp_path / 'registry.json'
    write_battle_registry(path, payload, bucket_count=2)
    assert load_battle_registry(path) == payload == before
    assert load_battle_registry(path, partitions=['p1'])['records'] == [a]
    files = {p: p.read_bytes() for p in tmp_path.rglob('*.json')}
    assert all(not raw.startswith(b'\xef\xbb\xbf') and b'\r\n' not in raw for raw in files.values())
    write_battle_registry(path, load_battle_registry(path), bucket_count=2)
    assert all(p.read_bytes() == raw for p, raw in files.items())
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['source_reference_storage'] = 'unknown'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError, match='存储版本'): load_battle_registry(path)

from emperor_v4.evaluation.battle_phase_objects import CATALOG as PHASE_CATALOG, REF as PHASE_REF, compact_objects, expand_objects

def phase_sample():
    value = {'reason': '同一份完整依据，不省略条件与限制。' * 12, 'source_refs': ['docs/' + 'long-' * 30]}
    return {'war_event_id': 'synthetic', 'subject_phase_views': [
        {'phase_id': 'a', 'ruler_binding': deepcopy(value), 'cost_evidence': deepcopy(value)},
        {'phase_id': 'b', 'ruler_binding': deepcopy(value)},
        {'phase_id': 'c', 'ruler_binding': dict(value, reason='独立归责依据')}]}

def test_phase_objects_round_trip_preserves_adoption_and_field_boundaries():
    before = phase_sample(); packed = compact_objects(before)
    assert len(packed[PHASE_CATALOG]) == 1
    assert packed['subject_phase_views'][0]['ruler_binding'] == packed['subject_phase_views'][1]['ruler_binding']
    assert PHASE_REF not in packed['subject_phase_views'][0]['cost_evidence']
    result = expand_objects(packed)
    assert json.dumps(result, ensure_ascii=False) == json.dumps(before, ensure_ascii=False)
    result['subject_phase_views'][0]['ruler_binding']['reason'] = 'consumer change'
    assert result['subject_phase_views'][1]['ruler_binding']['reason'] == before['subject_phase_views'][1]['ruler_binding']['reason']
    assert compact_objects(expand_objects(packed)) == packed
    assert expand_references(compact_references(before)) == before
    ref = packed['subject_phase_views'][0]['ruler_binding'][PHASE_REF]
    packed[PHASE_CATALOG].pop(ref)
    with pytest.raises(ValueError): expand_objects(packed)
