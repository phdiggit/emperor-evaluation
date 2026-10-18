"""Source lineage and synthesis behavior; no frozen person scores or counts."""
from copy import deepcopy
from pathlib import Path
import json
import pytest

from emperor_v4.evaluation.fourth_item_c_public import sources, calculation, axis_reading, verify_readings, markdown_reading
from emperor_v4.evaluation.fourth_item_a import net_result
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.third_fourth_item_public import FOURTH_PATH, _refresh_fourth, _signature

ROOT = Path(__file__).resolve().parents[1]


def package(p=0,n=0,hard=False,revoked=False):
    return dict(positive_component_level=f'R{p}' if p else None,negative_component_level=f'R{n}' if n else None,
                relative_change_level='R0',direction='MIXED',hard_negative_gate='ACTIVE' if hard else 'NONE',
                scoring_eligibility='REVOKED' if revoked else 'ELIGIBLE')


def axis(selected, points, band='MID'):
    result = net_result(selected)
    return dict(signed_adjustment=points,band=band,magnitude_grade=result['grade'],direction=result['direction'],
                disposition='SIGNED_CIVILIZATION_ADJUSTMENT_READY' if points else 'OBSERVED_OFFSETTING_OR_BALANCED_EFFECTS')


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


def test_fractional_independent_support_is_not_a_new_integer_grade():
    ps=[package(2),package(2)]
    text,status=calculation(axis(ps,9.5),ps)
    assert '补强0.5' in text and '= 2.5' in text
    assert '最终净幅度为2级' in text and '+9.5分' in text


def test_hard_negative_floor_and_positive_position_limit():
    ps=[package(2,3,hard=True)]
    text,_=calculation(axis(ps,-9.5),ps)
    assert '普通净算幅度为1级' in text
    assert '最终负向幅度至少2级' in text
    ps=[package(3,2,hard=True)]
    wrong=axis(ps,6,band='HIGH')
    with pytest.raises(ValueError,match='限制'):
        calculation(wrong,ps)


def test_fourth_level_retention_and_revoked_components():
    ps=[package(4,1)]
    text,_=calculation(axis(ps,21),ps)
    assert '普通净算幅度为3级' in text and '适用4级保留' in text
    ps=[package(2),package(0,4,hard=True,revoked=True)]
    text,_=calculation(axis(ps,9.5),ps)
    assert '没有触发重大负向限制' in text and '+9.5分' in text


def test_three_zero_states_and_retained_negative_record():
    empty=dict(signed_adjustment=0,disposition='NO_ELIGIBLE_CIVILIZATION_INCREMENT')
    _,status=calculation(empty,[])
    assert status=='没有确认独立变化'
    reviewed=dict(signed_adjustment=0,disposition='NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW')
    _,status=calculation(reviewed,[package(4,revoked=True)])
    assert status=='复核后未确认独立净变化'
    ps=[package(2,2,hard=True)]
    text,status=calculation(axis(ps,0,band=None),ps)
    assert status=='正负相抵，净调整为0'
    assert '保留2级重大负向记录' in text and '不再选低、中、高位' in text


def test_current_coverage_readonly_sources_and_person_caches():
    payload=load_json(ROOT/FOURTH_PATH)
    before=deepcopy(payload)
    assert verify_readings(payload,ROOT)==len(payload['records'])
    packages={p['package_code']:p for p in payload['accepted_packages']}
    by_id={r['ruler_id']:r for r in payload['records']}
    projected=_refresh_fourth(deepcopy(payload))
    assert _signature(projected)==_signature(payload) and payload==before
    for row in payload['records']:
        a=next(a for a in row['axis_results'] if a['axis']=='C')
        reading=axis_reading(row,a,packages)
        assert [e['package_ref'] for e in reading['evidence_items']]==a['package_refs']
        for item in reading['evidence_items']:
            assert [s['original'] for s in item['sources']]==packages[item['package_ref']]['source_refs']
        md=markdown_reading(reading)
        assert reading['calculation'] in md and reading['decision_basis'] in md
        if not a['signed_adjustment']:
            assert reading['zero_reason'] in md
    for path in (ROOT/'reader/data/people').glob('*.json'):
        record=json.loads(path.read_text(encoding='utf-8'))['record']
        for item in (record.get('net') or {}).get('component_details',{}).get('civilization',[]):
            if item['label']!='C文化知识': continue
            rid=(record['net'].get('source_item_ids') or {}).get('fourth_item',record['ruler_id'])
            row=by_id[rid];a=next(a for a in row['axis_results'] if a['axis']=='C')
            assert item['reader_public_fourth_c']==axis_reading(row,a,packages)
            assert item['reader_how']==item['reader_public_fourth_c']['calculation']


def test_shared_renderer_is_used_by_each_reader_route():
    for filename in ('index.template.html','home-interactions.js','person-readability.js'):
        script=(ROOT/'reader'/filename).read_text(encoding='utf-8')
        assert 'FourthItemCReading.html' in script and 'reader_public_fourth_c' in script
    renderer=(ROOT/'reader/fourth-item-c-public.js').read_text(encoding='utf-8')
    assert 'replace(/结果方向' not in renderer
    assert 'sourceList(e.sources,record)' in renderer
