from copy import deepcopy
import pytest
from emperor_v4.evaluation.second_item_c_source_notes import (
    CATALOG, NOTE, REF, compact_source_notes, source_note_records,
)


def sample():
    return {'scores': [dict(ruler_id=k, public_source_note=n) for k, n in
                       [('alpha', '材料汇集，尚未逐条证明。'), ('beta', '直接来源。'),
                        ('gamma', '材料汇集，尚未逐条证明。')]]}


def test_exact_round_trip_identity_order_and_independent_variants():
    original = sample(); before = deepcopy(original)
    compact = compact_source_notes(original)
    assert len(compact[CATALOG]) == 2
    assert source_note_records(compact) == original['scores']
    assert compact_source_notes(compact) == compact
    assert original == before
    compact['scores'].reverse()
    expanded = source_note_records(compact)
    assert [r['ruler_id'] for r in expanded] == ['gamma', 'beta', 'alpha']
    ref = compact['scores'][0][REF]
    compact[CATALOG][ref] = '更新后的共同说明。'
    expanded = source_note_records(compact)
    assert [r[NOTE] for r in expanded] == ['更新后的共同说明。', '直接来源。', '更新后的共同说明。']
    expanded[0]['ruler_id'] = 'consumer-edit'
    assert compact['scores'][0]['ruler_id'] == 'gamma'


@pytest.mark.parametrize('case', ['catalog', 'duplicate', 'unused', 'blank', 'missing', 'dangling', 'embedded'])
def test_invalid_storage_fails_closed(case):
    data = compact_source_notes(sample())
    if case == 'catalog': data.pop(CATALOG)
    elif case == 'duplicate': data[CATALOG]['1'] = data[CATALOG]['0']
    elif case == 'unused': data[CATALOG]['extra'] = '未使用说明'
    elif case == 'blank': data[CATALOG]['0'] = ''
    elif case == 'missing': data['scores'][0].pop(REF)
    elif case == 'dangling': data['scores'][0][REF] = 'absent'
    else: data['scores'][0][NOTE] = '副本'
    with pytest.raises(ValueError): source_note_records(data)


def test_no_default_note_is_invented():
    data = sample(); data['scores'][0].pop(NOTE)
    with pytest.raises(ValueError): compact_source_notes(data)
