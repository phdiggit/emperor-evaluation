from copy import deepcopy
import math
from pathlib import Path

import pytest

from emperor_v4.reader_scores import SCALES, BANDS, MERIT_TRIAL_BANDS, MERIT_BOUNDARY_DISTANCE, COMPONENT_SCALES, COMPONENT_BANDS, FOUNDER_BANDS, convert, rating, project, metadata, merit_trial, merit_levels, component_rating, signed_increment, _convert


@pytest.mark.parametrize('key', SCALES)
def test_display_anchors_are_continuous_and_monotone(key):
    points = SCALES[key]['anchors']
    for x, y in points:
        assert convert(x, key) == y
        assert convert(x-1e-7, key) <= y <= convert(x+1e-7, key)
        assert abs(convert(x-1e-7, key)-convert(x+1e-7, key)) < 1e-5
    inputs = [-100, -10, -0.1, 0] + [x for x,_ in points[1:]] + [points[-1][0]+25, points[-1][0]+150]
    assert all(convert(a,key)<convert(b,key) for a,b in zip(inputs,inputs[1:]))
    for raw in inputs:
        r=rating(raw,key)
        assert 0 <= r['score'] <= 99.9
        assert r['grade']==next(g for lower,g in BANDS if r['score']>=lower)


@pytest.mark.parametrize('raw', [None, True, '10', math.nan, math.inf, -math.inf])
def test_invalid_values_are_not_zero(raw):
    with pytest.raises(ValueError):
        rating(raw)


def synthetic_net():
    return dict(total_score=240, second_item_score=150, third_item_score=90,
                first_item_status='NOT_APPLICABLE', first_item_raw_score=None,
                first_item_add_on=0, fourth_item_adjustment=0,
                component_details=dict(civilization=[{f'reader_public_fourth_{k}':dict(evidence_items=[])} for k in 'abc'] +
                    [dict(reader_signed_balance=dict(positive_gross=0, negative_gross=0, result_count=0))]))


def test_applicability_and_zero_cancellation_are_distinct_without_mutation():
    n=synthetic_net();before=deepcopy(n)
    p=project(n)
    assert p['first']['state']=='NOT_APPLICABLE' and p['first']['score'] is None
    assert p['fourth']['state']=='NO_CONFIRMED_CHANGE' and p['fourth']['score'] is None
    assert n==before
    n['first_item_status']='APPLICABLE';n['first_item_raw_score']=0
    n['component_details']['civilization'][0]['reader_public_fourth_a']['evidence_items']=[{},{}]
    n['component_details']['civilization'][-1]['reader_signed_balance']=dict(positive_gross=3,negative_gross=3,result_count=2)
    p=project(n)
    assert {k:p['first'][k] for k in ('state','score','grade')}==rating(0,'first')
    assert {k:p['fourth'][k] for k in ('state','score','grade')}==rating(0,'fourth')
    assert p['fourth']['score']==60
    assert p['first']['trial_rating']['score']==0
    assert p['fourth']['trial_rating']['score']==0
    assert p['fourth']['trial_rating']['grade']=='正负相抵'
    assert p['fourth']['trial_rating']['positive_gross']==p['fourth']['trial_rating']['negative_gross']==3
    n['component_details']['civilization']=[]
    with pytest.raises(ValueError):project(n)


@pytest.mark.parametrize('key', COMPONENT_SCALES)
def test_component_calibration_is_monotone_continuous_and_population_independent(key):
    spec=COMPONENT_SCALES[key]
    points=spec['anchors']
    for x,y in points:
        assert _convert(x,spec)==y
        if x>0 or spec['negative'] is not None:
            assert _convert(x-1e-7,spec)<=y<=_convert(x+1e-7,spec)
            assert abs(_convert(x-1e-7,spec)-_convert(x+1e-7,spec))<1e-5
    inputs=([0] if key=='first' else [-500,-50,-1,0])+[x for x,_ in points[1:]]+[points[-1][0]+50]
    precise=[_convert(v,spec) for v in inputs]
    assert all(a<b for a,b in zip(precise,precise[1:]))
    before=[component_rating(v,key) for v in inputs]
    component_rating(1_000_000,key)
    assert before==[component_rating(v,key) for v in inputs]
    bands=FOUNDER_BANDS if key=='first' else COMPONENT_BANDS
    for value in before:
        assert value['grade']==next(label for lower,label in bands if value['score']>=lower)
    if key=='first':
        with pytest.raises(ValueError):component_rating(-1,key)


@pytest.mark.parametrize('key', COMPONENT_SCALES)
@pytest.mark.parametrize('value', [True,None,'1',math.nan,math.inf,-math.inf])
def test_component_scales_reject_invalid_input(key,value):
    with pytest.raises(ValueError):component_rating(value,key)


def test_signed_increment_has_no_ceiling_or_asymmetric_curve_and_checks_sources():
    n=synthetic_net()
    balance=n['component_details']['civilization'][-1]['reader_signed_balance']
    for value in [1.5,250,-1.5,-250,0]:
        balance.update(positive_gross=max(value,0)+4,negative_gross=max(-value,0)+4,result_count=3)
        n['fourth_item_adjustment']=value
        result=signed_increment(n,True)
        assert result['score']==value
        assert result['positive_gross']-result['negative_gross']==value
    balance['positive_gross']+=1
    with pytest.raises(ValueError,match='gross amounts'):signed_increment(n,True)
    balance.update(positive_gross=0,negative_gross=0,result_count=0)
    assert signed_increment(n,False)['score'] is None
    with pytest.raises(ValueError,match='state'):signed_increment(n,True)


def test_grade_boundary_and_negative_total_do_not_round_into_another_grade():
    assert rating(450-0.01)['grade']=='A'
    assert rating(450)['grade']=='S'
    assert rating(-0.001)['grade']=='E−'
    assert rating(0)['grade']=='E'
    data=metadata();data['scales']['total']['tail']=1
    assert SCALES['total']['tail']!=1


def test_merit_trial_boundaries_are_fixed_monotone_and_preserve_original_score():
    for index, (minimum, code, label, _) in enumerate(MERIT_TRIAL_BANDS):
        if minimum is None:
            continue
        assert merit_trial(minimum)['code'] == code
        assert merit_trial(minimum)['label'] == label
        assert merit_trial(minimum)['position'] == '下'
        assert merit_trial(minimum-0.001)['code'] == MERIT_TRIAL_BANDS[index+1][1]
    codes = [code for _, code, _, _ in MERIT_TRIAL_BANDS]
    points = [-1000, -1, 0, 60, 120, 200, 250, 300, 350, 400, 450, 1000]
    indices = [codes.index(merit_trial(value)['code']) for value in points]
    assert all(a >= b for a, b in zip(indices, indices[1:]))
    net = synthetic_net()
    before = deepcopy(net)
    projected = project(net)['total']
    assert {key: projected[key] for key in ('state', 'score', 'grade')} == rating(net['total_score'])
    assert projected['trial_tier'] == merit_trial(net['total_score'])
    assert net == before
    data = metadata()
    assert data['merit_trial']['status'] == 'READING_TRIAL'
    data['merit_trial']['bands'][0]['label'] = '消费端修改'
    assert metadata()['merit_trial']['bands'][0]['label'] == MERIT_TRIAL_BANDS[0][2]


@pytest.mark.parametrize('raw', [None, True, '10', math.nan, math.inf, -math.inf])
def test_merit_trial_rejects_invalid_scores(raw):
    with pytest.raises(ValueError):
        merit_trial(raw)


def test_merit_trial_boundary_hints_and_subgrades():
    for index, (minimum, code, _, _) in enumerate(MERIT_TRIAL_BANDS):
        if minimum is None:
            continue
        at = merit_trial(minimum)
        below = merit_trial(minimum-0.001)
        assert at['boundary_neighbor'] == MERIT_TRIAL_BANDS[index+1][2]
        assert below['boundary_neighbor'] == MERIT_TRIAL_BANDS[index][2]
        assert at['score'] == convert(minimum, 'total_trial')
        assert at['display_label'] == at['label']+at['position']
    for value in range(-200, 1000, 3):
        result = merit_trial(value)
        boundaries = [convert(raw,'total_trial') for raw, *_ in MERIT_TRIAL_BANDS if raw is not None]
        nearest = min(abs(convert(value,'total_trial')-point) for point in boundaries)
        assert bool(result['boundary_neighbor']) == (nearest <= MERIT_BOUNDARY_DISTANCE)
        assert result['score'] == rating(value,'total_trial')['score']


@pytest.mark.parametrize('raw, expected', [
    (410,'圣下'),(460,'圣中'),(650,'圣上'),
    (330,'明下'),(360,'明中'),(380,'明上'),
    (225,'平下'),(270,'平中'),(310,'平上'),
    (90,'庸下'),(150,'庸中'),(210,'庸上'),
    (-100,'昏下'),(0,'昏中'),(60,'昏上'),
])
def test_fifteen_reading_levels_with_synthetic_scores(raw, expected):
    assert merit_trial(raw)['display_label'] == expected


def test_displayed_score_determines_subgrade_even_at_third_boundaries():
    # Distinct raw values with the same displayed tenth must not get different
    # labels. Derive the thresholds from the active scale, not real people.
    seen = {}
    for raw in (n / 100 for n in range(-10000, 70001)):
        result = merit_trial(raw)
        score = result['score']
        assert seen.setdefault(score, result['display_label']) == result['display_label']
    for i, band in enumerate(metadata()['merit_trial']['bands']):
        assert band['levels'] == [dict(minimum_score=s, position=p, label=band['label']+p)
                                  for s,p in merit_levels(i)]
        assert all(round(s*10) == pytest.approx(s*10) for s,_ in merit_levels(i))


def test_current_display_is_order_preserving_and_population_independent():
    from emperor_v4.evaluation.formal_json_store import load_json
    root=Path(__file__).resolve().parents[1]
    rows=load_json(root/'docs/评分结算/净收益/00-统治绩效综合评分榜.json')['records']
    ordered=sorted(rows,key=lambda r:r['total_score'])
    for a,b in zip(ordered,ordered[1:]):
        x,y=convert(a['total_score']),convert(b['total_score'])
        assert (x==y) if a['total_score']==b['total_score'] else (x<y)
    before=[rating(r['total_score']) for r in rows]
    # Introducing an unrelated extreme score cannot rescale existing people.
    rating(1_000_000)
    assert [rating(r['total_score']) for r in rows]==before


def test_built_pages_use_the_same_projection_as_person_details():
    import json
    from emperor_v4.evaluation.formal_json_store import load_json
    root=Path(__file__).resolve().parents[1]
    html=(root/'reader/index.html').read_text(encoding='utf-8')
    data=json.loads(html.split('id="reader-data"',1)[1].split('>',1)[1].split('</script>',1)[0])
    formal={r['ruler_id']:r for r in load_json(root/'docs/评分结算/净收益/00-统治绩效综合评分榜.json')['records']}
    fourth={r['ruler_id']:r for r in load_json(root/'docs/评分结算/净收益/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json')['records']}
    assert data['public_score_scale']==json.loads(json.dumps(metadata()))
    for summary in data['records']:
        if not summary.get('net'):
            continue
        full=json.loads((root/'reader'/summary['detail_ref']).read_text(encoding='utf-8'))['record']
        assert summary['net']['public_scores']==full['net']['public_scores']==project(full['net'])
        source=formal[summary['ruler_id']]
        fid=next(item['reader_c_collection_id'] for item in full['net']['component_details']['civilization'] if 'reader_c_collection_id' in item)
        increment=summary['net']['public_scores']['fourth']['trial_rating']
        assert increment['positive_gross']==fourth[fid]['positive_gross']
        assert increment['negative_gross']==fourth[fid]['negative_gross']
        assert increment['result_count']==sum(len(axis['results']) for axis in fourth[fid]['axis_results'])
        assert increment['score']==(fourth[fid]['fourth_item_signed_adjustment'] if increment['result_count'] else None)
        for key in ('rank','total_score','first_item_raw_score','first_item_add_on','second_item_score','third_item_score','fourth_item_adjustment'):
            assert full['net'][key]==summary['net'][key]==source[key]
