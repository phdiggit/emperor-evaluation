"""Source lineage and synthesis behavior; no frozen person scores or counts."""
from copy import deepcopy
from pathlib import Path
import json
import pytest

from emperor_v4.evaluation.fourth_item_c_public import sources, axis_reading, markdown_reading
from emperor_v4.evaluation.fourth_item_results import SCHEMA, axis_reading as formal_axis_reading, totals, price, disposition
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.third_fourth_item_public import FOURTH_PATH, _refresh_fourth, _signature

ROOT = Path(__file__).resolve().parents[1]


def result(level=2, band='MID', direction='POSITIVE'):
    return dict(eligibility='ADMITTED',level=level,band=band,direction=direction)


def test_sources_cannot_drop_or_redirect_existing_links():
    ref='https://example.org/original'
    items=[dict(original=ref,target=ref,label='原引文献',kind='研究入口')]
    assert sources(items,[ref])==items
    items[0]['target']='https://example.org/unrelated'
    with pytest.raises(ValueError,match='链接'):
        sources(items,[ref])
    items[0]['target']=''
    with pytest.raises(ValueError,match='链接'):
        sources(items,[ref])
    with pytest.raises(ValueError,match='不同值'):
        sources([], [ref])


def test_independent_results_add_without_budget_or_regrading():
    ps=[result() for _ in range(20)]
    assert totals(ps)==dict(positive_gross=80,negative_gross=0,signed_adjustment=80)
    assert all(p['level']==2 for p in ps)


def test_positive_and_negative_use_the_same_prices():
    for level in range(1,5):
        for band in ['LOW','MID','HIGH']:
            p=result(level,band);n=result(level,band,'NEGATIVE')
            assert price(p)==-price(n)
            assert totals([p,n])['signed_adjustment']==0
            assert totals([p,n])['negative_gross']>0


def test_large_damage_is_retained_without_repricing_other_results():
    ps=[result(4,'HIGH','NEGATIVE'),result(3,'HIGH'),result(3,'HIGH')]
    assert totals(ps)==dict(positive_gross=24,negative_gross=24,signed_adjustment=0)
    assert disposition(ps)=='OBSERVED_OFFSETTING_OR_BALANCED_EFFECTS'
    assert disposition([])=='NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW'


def test_fourth_reading_shares_axis_context_and_keeps_each_results_evidence():
    common = '两项工程都曾在本时期交付。'
    responsibility = '本人下令，两组官员分别执行。'
    boundary = '后任扩编属于另一时期。'
    entries = []
    for name, direction, body in [('P', 'POSITIVE', '第一种典籍公开刊行。'),
                                  ('N', 'NEGATIVE', '第二种典籍遭到禁毁。')]:
        entry = {**result(direction=direction), 'result_id': name, 'title': name,
                 'basis': common + '\n\n' + body,
                 'cross_item_handoff': {'basis': f'{body}{boundary}'},
                 'source_refs': [f'https://example.org/{name}']}
        entry['contribution'] = price(entry)
        entries.append(entry)
    row = {'ruler_name': '合成对象', 'actual_power_window': [[100, 110]]}
    axis = {'axis': 'C', 'calculation_version': SCHEMA, 'results': entries,
            'baseline_basis': '起点有不同文献产品。', 'handoff_basis': '交班信息有限。',
            'decision_basis': '正向和负向分别成立。', 'responsibility': responsibility,
            'cross_item_handoff': {'owned_outcome': '采用本轴文化结果。'}, **totals(entries)}
    before = deepcopy(axis)
    reading = axis_reading(row, axis, {})
    assert reading['common_result_basis'] == common
    assert [item['level_basis'] for item in reading['evidence_items']] == ['第一种典籍公开刊行。', '第二种典籍遭到禁毁。']
    assert all(item['boundary'] == boundary for item in reading['evidence_items'])
    text = markdown_reading(reading)
    assert text.count(common) == text.count(responsibility) == 1
    assert text.count(boundary) == 2
    assert all(e['source_refs'][0] in text for e in entries)
    assert axis == before


@pytest.mark.parametrize('changes',[dict(eligibility='UNRESOLVED'),dict(level=0),dict(level=True),dict(band=None),dict(direction='MIXED')])
def test_unresolved_or_invalid_result_cannot_be_priced(changes):
    with pytest.raises(ValueError):price({**result(),**changes})


def test_current_coverage_readonly_sources_and_person_caches():
    payload=load_json(ROOT/FOURTH_PATH)
    before=deepcopy(payload)
    packages={p['package_code']:p for p in payload['accepted_packages']}
    by_id={r['ruler_id']:r for r in payload['records']}
    projected=_refresh_fourth(deepcopy(payload))
    assert projected==payload and _signature(projected)==_signature(payload) and payload==before
    for row in payload['records']:
        a=next(a for a in row['axis_results'] if a['axis']=='C')
        reading=axis_reading(row,a,packages)
        assert [e['result_id'] for e in reading['evidence_items']]==[r['result_id'] for r in a['results']]
        assert all('public_reading' not in axis for axis in row['axis_results'])
        for result_row,item in zip(a['results'],formal_axis_reading(row,a)['evidence_items'],strict=True):
            assert set(result_row['source_refs']) <= {s['original'] for s in item['sources']}
            assert all(s['target'] in ('',s['original']) for s in item['sources'])
        for item in reading['evidence_items']:
            assert all('original' not in s and (not s['target'] or s['target'].startswith(('https://', 'http://')))
                       for s in item['sources'])
        md=markdown_reading(reading)
        assert reading['calculation'] in md
        assert reading.get('display_decision', reading['decision_basis']) in md
        if not a['signed_adjustment']:
            assert reading['zero_reason'] == reading['decision_basis']
    for path in (ROOT/'reader/data/people').glob('*.json'):
        record=json.loads(path.read_text(encoding='utf-8'))['record']
        for item in (record.get('net') or {}).get('component_details',{}).get('civilization',[]):
            if item['label']!='C文化知识': continue
            rid=(record['net'].get('source_item_ids') or {}).get('fourth_item',record['ruler_id'])
            row=by_id[rid];a=next(a for a in row['axis_results'] if a['axis']=='C')
            assert item['reader_public_fourth_c']==axis_reading(row,a,packages)
            assert item['reader_how']==item['reader_public_fourth_c']['calculation']
