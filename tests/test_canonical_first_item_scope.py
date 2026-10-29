from pathlib import Path

from emperor_v4.evaluation.canonical_ruler_pool import build_canonical_ruler_pool


def test_settled_first_item_is_not_described_as_inapplicable():
    root = Path(__file__).resolve().parents[1]
    pool = build_canonical_ruler_pool(root)
    for row in pool['records']:
        if row['pool_status'] != 'INCLUDED':
            continue
        if row['first_item_readiness'].startswith('FORMAL_RECORD_PRESENT'):
            assert row['source_item_ids']['first_item'] is not None
            assert '不适用' not in row['first_item_scope_note']
            assert 'F=0' not in row['first_item_scope_note']
