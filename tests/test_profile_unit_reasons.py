from copy import deepcopy
import json

import pytest

from emperor_v4.evaluation.profile_unit_reasons import (
    compact_reasons, expand_reasons, load_unit_dispositions, write_unit_dispositions,
)


def sample():
    return {'schema_version': 'synthetic', 'units': [
        {'unit_id': 'a', 'status': 'BACKGROUND', 'reason': '相同原文', 'source_ref': 'source-a'},
        {'unit_id': 'b', 'status': 'BACKGROUND', 'reason': '独立理由', 'source_ref': 'source-b'},
        {'unit_id': 'c', 'status': 'OTHER', 'reason': '相同原文', 'source_ref': 'source-c'},
    ]}


def test_lossless_deterministic_and_read_only():
    original = sample()
    before = deepcopy(original)
    compact = compact_reasons(original)
    assert len(compact['reason_catalog']) == 2
    assert compact['units'][0]['reason_ref'] == compact['units'][2]['reason_ref']
    assert compact['units'][0]['reason_ref'] != compact['units'][1]['reason_ref']
    assert expand_reasons(compact) == original == before
    assert [list(u) for u in expand_reasons(compact)['units']] == [list(u) for u in original['units']]
    assert compact_reasons(expand_reasons(compact)) == compact_reasons(compact) == compact
    expanded = expand_reasons(compact)
    expanded['units'][0]['source_ref'] = 'changed'
    assert original == before and compact['units'][0]['source_ref'] == 'source-a'


def test_reorder_and_catalog_edits_follow_references():
    compact = compact_reasons(sample())
    compact['units'].reverse()
    ref = compact['units'][0]['reason_ref']
    compact['reason_catalog'][ref] = '修改后的完整原文'
    expanded = expand_reasons(compact)
    assert [u['unit_id'] for u in expanded['units']] == ['c', 'b', 'a']
    assert [u['reason'] for u in expanded['units']] == ['修改后的完整原文', '独立理由', '修改后的完整原文']


@pytest.mark.parametrize('case', ['version', 'catalog', 'blank', 'duplicate', 'unused', 'missing', 'dangling', 'embedded'])
def test_rejects_invalid_compact_storage(case):
    data = compact_reasons(sample())
    if case == 'version': data['reason_storage'] = 'unknown'
    elif case == 'catalog': data['reason_catalog'] = []
    elif case == 'blank': data['reason_catalog']['0'] = ' '
    elif case == 'duplicate': data['reason_catalog']['1'] = data['reason_catalog']['0']
    elif case == 'unused': data['reason_catalog']['unused'] = '未使用理由'
    elif case == 'missing': data['units'][0].pop('reason_ref')
    elif case == 'dangling': data['units'][0]['reason_ref'] = 'absent'
    else: data['units'][0]['reason'] = '内嵌正文'
    with pytest.raises(ValueError): expand_reasons(data)
    with pytest.raises(ValueError): compact_reasons(data)


@pytest.mark.parametrize('reason', [None, '', ' ', 3])
def test_does_not_invent_missing_reason(reason):
    data = sample()
    data['units'][0]['reason'] = reason
    with pytest.raises(ValueError): compact_reasons(data)


def test_file_round_trip_and_repeat_write(tmp_path):
    path = tmp_path / 'units.json'
    write_unit_dispositions(path, sample())
    raw = path.read_bytes()
    assert not raw.startswith(b'\xef\xbb\xbf')
    assert b'\r\n' not in raw
    assert all('reason' not in u for u in json.loads(raw)['units'])
    assert load_unit_dispositions(path) == sample()
    write_unit_dispositions(path, load_unit_dispositions(path))
    assert path.read_bytes() == raw
