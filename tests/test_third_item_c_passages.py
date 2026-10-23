from copy import deepcopy
import json

import pytest

from emperor_v4.evaluation.third_item_c_passages import (
    expand_passages, pack_passages, validate_passages,
)


def sample():
    source = dict(path='synthetic.md#window', quote='甲地获守，但乙地失守。', kind='既有摘要')
    return dict(evidence_items=[
        dict(id='one', source_passages=[source], scope='只采用本人任内部分。'),
        dict(id='two', source_passages=[deepcopy(source), dict(source, kind='范围核对')]),
        dict(id='absent'), dict(id='empty', source_passages=[]),
    ], source_reviews={'chain': dict(source_passages=[deepcopy(source), deepcopy(source)], facts='保留正反两侧。')})


def test_passage_catalog_roundtrip_keeps_order_roles_scope_and_private_copies():
    original = sample()
    before = deepcopy(original)
    packed = pack_passages(original)
    assert original == before
    assert len(packed['source_passage_catalog']) == 2
    refs = packed['evidence_items'][0]['source_passage_refs']
    assert packed['source_reviews']['chain']['source_passage_refs'] == refs * 2
    assert packed['evidence_items'][1]['source_passage_refs'][1] != refs[0]
    expanded = expand_passages(packed)
    assert json.dumps(expanded, ensure_ascii=False) == json.dumps(original, ensure_ascii=False)
    expanded['evidence_items'][0]['source_passages'][0]['quote'] = '消费者修改'
    assert expand_passages(packed) == original
    assert pack_passages(expand_passages(packed)) == packed


@pytest.mark.parametrize('problem', ['dangling', 'inline', 'duplicate_catalog', 'missing_catalog', 'unused'])
def test_invalid_passage_storage_fails_closed(problem):
    packed = pack_passages(sample())
    if problem == 'dangling':
        packed['evidence_items'][0]['source_passage_refs'] = ['OTHER-PERSON-PASSAGE']
    elif problem == 'inline':
        packed['evidence_items'][0]['source_passages'] = []
    elif problem == 'duplicate_catalog':
        packed['source_passage_catalog']['duplicate'] = deepcopy(next(iter(packed['source_passage_catalog'].values())))
    elif problem == 'unused':
        packed['source_passage_catalog']['unused'] = dict(path='unused.md', quote='未引用摘录。')
    else:
        del packed['source_passage_catalog']
    with pytest.raises(ValueError):
        expand_passages(packed)


def test_source_edit_preserves_ids_and_updates_every_expanded_occurrence():
    packed = pack_passages(sample())
    ref = packed['evidence_items'][0]['source_passage_refs'][0]
    packed['source_passage_catalog'][ref]['quote'] = '修订摘录仍保留责任限制。'
    validate_passages(packed)
    expanded = expand_passages(packed)
    assert expanded['evidence_items'][0]['source_passages'][0]['quote'] == '修订摘录仍保留责任限制。'
    assert expanded['source_reviews']['chain']['source_passages'][1]['quote'] == '修订摘录仍保留责任限制。'
