from copy import deepcopy
import pytest
from emperor_v4.evaluation.second_item_c_source_notes import (
    CATALOG, NOTE, REF, STANDARD_COLLECTION_SCOPE, STANDARD_SOURCE_NOTE, compact_source_notes,
    source_note_records, specific_source_note, uses_shared_collection_scope,
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


def test_display_removes_only_exact_shared_introduction():
    limit = '该书仅用于核对财政条目的年代。'
    assert specific_source_note(STANDARD_SOURCE_NOTE) == ''
    assert specific_source_note(STANDARD_SOURCE_NOTE + '\n\n' + limit) == limit
    assert specific_source_note(limit) == limit
    joined = STANDARD_SOURCE_NOTE + limit
    assert specific_source_note(joined) == joined


def test_only_material_collection_cards_can_share_the_standard_scope():
    item = {'source_binding_kind': 'MATERIAL_COLLECTION', 'public_scope': STANDARD_COLLECTION_SCOPE}
    assert uses_shared_collection_scope(item)
    assert not uses_shared_collection_scope({**item, 'source_binding_kind': 'CLAIM_SUPPORT'})
    assert not uses_shared_collection_scope({**item, 'public_scope': '该来源仅用于核对登记年代。'})
