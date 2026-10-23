from copy import deepcopy
from pathlib import Path

import pytest

from emperor_v4.evaluation import composite_details as module


def inputs():
    pool = [dict(ruler_id=k, ruler_name=k, pool_status='INCLUDED',
                 settlement_readiness='COMPOSITE_READY', source_item_ids={'second_item': k + '-source'})
            for k in ('alpha', 'beta')]
    return pool, [dict(ruler_id=k, ruler_name=k) for k in ('beta', 'alpha')]


def test_reading_joins_by_identity_and_does_not_mutate(monkeypatch):
    pool, rows = inputs()
    before = deepcopy((pool, rows))
    calls = []
    monkeypatch.setattr(module, 'load_detail_sources', lambda root: calls.append(root) or {})
    monkeypatch.setattr(module, 'component_details', lambda sources, p, r: {'source': p['source_item_ids']['second_item']})
    result = module.reading_records(Path('.'), rows, pool)
    assert [r['component_details']['source'] for r in result] == ['beta-source', 'alpha-source']
    assert len(calls) == 1
    assert (pool, rows) == before
    result[0]['ruler_name'] = 'changed'
    assert rows[0]['ruler_name'] == 'beta'


@pytest.mark.parametrize('case', ['pool_duplicate', 'row_duplicate', 'missing', 'foreign', 'identity', 'embedded'])
def test_reading_rejects_invalid_identity_or_embedded_copy(case):
    pool, rows = inputs()
    if case == 'pool_duplicate': pool.append(deepcopy(pool[0]))
    elif case == 'row_duplicate': rows.append(deepcopy(rows[0]))
    elif case == 'missing': rows.pop()
    elif case == 'foreign': rows[0]['ruler_id'] = 'foreign'
    elif case == 'identity': rows[0]['ruler_name'] = 'wrong'
    else: rows[0]['component_details'] = {}
    with pytest.raises(ValueError):
        module.reading_records(Path('.'), rows, pool)
