from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from emperor_v4.evaluation.talent_evidence_storage import (
    CATALOG, REF, STORAGE, compact_evidence, expand_evidence, expand_shard,
)
from emperor_v4.evaluation.talent_registry_store import write_talent_registry, load_talent_registry


def sample():
    base = {'campaign_ref': 'SYNTHETIC-CAMPAIGN', 'capability_episode_ref': 'SYNTHETIC-EPISODE',
            'basis': '独立构造的完整材料，保留空格 引号"与换行\n，不改写。' * 20,
            'source_refs': ['synthetic.json#source']}
    return {'profile_ref': 'SYNTHETIC-PERSON', 'person': '合成人物',
            'consumed_achievements': [deepcopy(base)],
            'capability_episode_anchors': [{**deepcopy(base), 'role': '独立能力角色', 'count': 1}],
            'negative_or_mixed_command_records': [{**deepcopy(base), 'adverse': '独立负面限定'}],
            'failure_accountability': [{**deepcopy(base), 'responsibility': '独立归责限定'}],
            'empty': [], 'none': None}


def test_round_trip_preserves_all_roles_text_and_key_order_without_aliasing():
    original = sample(); saved = deepcopy(original)
    packed = compact_evidence(original)
    assert original == saved
    assert len(packed[CATALOG]) == 1
    assert len(json.dumps(packed, ensure_ascii=False)) < len(json.dumps(original, ensure_ascii=False))
    assert json.dumps(expand_evidence(packed), ensure_ascii=False) == json.dumps(original, ensure_ascii=False)
    expanded = expand_evidence(packed)
    expanded['consumed_achievements'][0]['source_refs'].append('consumer change')
    assert expanded['failure_accountability'][0]['source_refs'] == original['failure_accountability'][0]['source_refs']
    assert expand_evidence(packed) == original
    assert compact_evidence(expand_evidence(packed)) == packed
    with pytest.raises(ValueError):
        compact_evidence(packed)


def test_similar_but_different_fields_are_preserved_in_own_suffixes():
    profile = sample()
    profile['capability_episode_anchors'][0]['basis'] += '另一解释。'
    # The common portion must stop before the first unequal field.
    packed = compact_evidence(profile)
    assert expand_evidence(packed) == profile
    if CATALOG in packed:
        assert all('basis' not in base for base in packed[CATALOG].values())
    small = {'consumed_achievements': [{'a': 1, 'b': 2}, {'a': 1, 'b': 2}]}
    assert compact_evidence(small) == small


@pytest.mark.parametrize('damage', ['missing', 'overlap', 'outside'])
def test_invalid_storage_is_rejected(damage):
    packed = compact_evidence(sample()); value = packed['consumed_achievements'][0]
    if damage == 'missing': value[REF] = 'missing'
    elif damage == 'overlap': value['fields']['basis'] = 'attempted overwrite'
    else: packed['other'] = deepcopy(value)
    with pytest.raises(ValueError): expand_evidence(packed)


def test_store_round_trip_order_and_repeated_write(tmp_path):
    path = tmp_path / 'registry.json'
    payload = {'title': '合成人才登记', 'profiles': [sample(), {**sample(), 'profile_ref': 'SECOND'}]}
    write_talent_registry(path, payload, bucket_count=2)
    assert load_talent_registry(path) == payload
    before = {p: p.read_bytes() for p in [path, *path.with_suffix('').glob('*.json')]}
    write_talent_registry(path, load_talent_registry(path), bucket_count=2)
    assert before == {p: p.read_bytes() for p in before}
    for shard in path.with_suffix('').glob('*.json'):
        data = json.loads(shard.read_text(encoding='utf-8'))
        assert data['evidence_storage'] == STORAGE
        data.pop('evidence_storage')
        with pytest.raises(ValueError):
            expand_shard(data)
        data['evidence_storage'] = 'unknown'
        with pytest.raises(ValueError):
            expand_shard(data)


def test_reader_index_loader_expands_raw_talent_shards(tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('talent_core_test', root / 'reader/_build_military_archive_core.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    path = tmp_path / 'shard.json'
    path.write_text(json.dumps({'schema_version': 'military-talent-registry-shard-v1',
                               'evidence_storage': STORAGE, 'profiles': [compact_evidence(sample())]}), encoding='utf-8')
    assert module._load(path)['profiles'] == [sample()]


def test_browser_expansion_matches_python_and_rejects_corruption(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable')
    source = (Path(__file__).resolve().parents[1] / 'reader/military-archive.js').read_text(encoding='utf-8')
    function = source.split('  function expandTalentEvidence(profile) {', 1)[1].split('  async function json(path)', 1)[0]
    script = 'const assert = require("node:assert/strict");\nfunction expandTalentEvidence(profile) {' + function
    script += '\nconst original = ' + json.dumps(sample(), ensure_ascii=False) + ';'
    script += '\nconst packed = ' + json.dumps(compact_evidence(sample()), ensure_ascii=False) + ';'
    script += '''
assert.deepEqual(expandTalentEvidence(packed), original);
assert.deepEqual(expandTalentEvidence(original), original);
const result = expandTalentEvidence(packed);
result.consumed_achievements[0].source_refs.push("consumer change");
assert.deepEqual(result.failure_accountability[0].source_refs, original.failure_accountability[0].source_refs);
const broken = JSON.parse(JSON.stringify(packed));
broken.consumed_achievements[0].fields.basis = "overwrite";
assert.throws(()=>expandTalentEvidence(broken));
packed.consumed_achievements[0].talent_evidence_ref = "missing";
assert.throws(()=>expandTalentEvidence(packed));
'''
    path = tmp_path / 'browser.cjs'; path.write_text(script, encoding='utf-8')
    result = subprocess.run([node, str(path)], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
