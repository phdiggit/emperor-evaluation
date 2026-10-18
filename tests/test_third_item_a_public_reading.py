"""Contract behavior with independent synthetic cases; no frozen ruler scores."""
import copy
import json
from pathlib import Path
import pytest
from emperor_v4.evaluation.third_fourth_item_public import _level_label
from emperor_v4.evaluation.third_item_a_public import calculation, reading_projection
from emperor_v4.evaluation.formal_json_store import load_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('zero', [0, '0', 'A1S0_EXISTENTIAL_CRISIS'])
def test_zero_state_is_a_real_level(zero):
    assert _level_label(zero) == '第0级'
    assert _level_label(None) == '未单列等级'


def synthetic_axis():
    return dict(end_grade=3, end_state_value=30, positive_value_delta=0,
                negative_value_delta=-8, ceiling_progress_bonus=4,
                maintenance_bonus=8, reversal_penalty=2,
                within_band_deterioration_penalty=5,
                unclamped_trajectory_value=29, axis_points=17.4)


def contract():
    return dict(change_weights=dict(improvement=1.4, deterioration=.5),
                construction_base_points=dict(SIGNIFICANT=14, DECISIVE=28),
                state_values=dict(A1=[0,8,18,30,40,50], A2=[0,8,16,30,40,50]))


def test_calculation_explains_take_higher_and_preserves_input():
    axis=synthetic_axis(); before=copy.deepcopy(axis)
    text=calculation(axis, contract())
    assert '只计其中最高的8' in text
    assert '只扣其中最高的5' in text
    assert '最终为17.40分' in text
    assert axis == before


def test_calculation_rejects_disagreement_instead_of_changing_score():
    axis=synthetic_axis();axis['axis_points']=20
    with pytest.raises(ValueError, match='禁止修改分数'):
        calculation(axis,contract())
    assert axis['axis_points'] == 20


@pytest.mark.parametrize(('positive','negative','raw','points'), [(80,0,142,60),(0,-80,-10,0)])
def test_calculation_preserves_clipping(positive,negative,raw,points):
    axis=synthetic_axis()
    axis.update(positive_value_delta=positive,negative_value_delta=negative,
                ceiling_progress_bonus=0,maintenance_bonus=0,reversal_penalty=0,
                within_band_deterioration_penalty=0,
                unclamped_trajectory_value=raw,axis_points=points)
    text=calculation(axis,contract())
    assert f'最终为{points:.2f}分' in text


def test_authored_text_is_preserved_while_calculation_is_refreshed():
    axis=synthetic_axis()
    axis['public_reading']=dict(story='河谷防线恢复，关隘能够互相增援。',decision='主要方向仍有缺口。',
                               responsibility='本人决定调配援军。',window='独立构造的责任时期',boundary='不采用后继者成果。',
                               sources=[dict(path='synthetic.json',label='独立合成来源',kind='合成用例')])
    original=copy.deepcopy(axis)
    result=reading_projection('A1',axis,contract())
    for key in ('story','decision','responsibility','window','boundary'):
        assert result[key] == original['public_reading'][key]
    assert axis == original
    assert result['calculation']
    axis['public_reading']['story']='依据父卡撤回原档。'
    with pytest.raises(ValueError,match='内部术语'):
        reading_projection('A1',axis,contract())


def test_current_sources_and_all_reader_surfaces_share_a_reading():
    credit=load_json(ROOT/'config/third-item/third-item-result-credit-adjudications.json')
    ab=load_json(ROOT/'docs/评分结算/净收益/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json')
    ab_by_id={r['ruler_id']:r for r in ab['records']}
    expected={}
    for row in credit['records']:
        for axis_name,axis in row['axes'].items():
            reading=axis['public_reading']
            assert reading == reading_projection(axis_name,axis,credit['contract'])
            assert reading == ab_by_id[row['ruler_id']]['axes'][axis_name]['public_reading']
            assert reading['story'] != row['public_axis_projections'][axis_name]['public_adjudication_summary']
            assert not reading['unresolved_refs']
            expected[row['ruler_id'],axis_name]=reading
    seen=0
    pool=load_json(ROOT/'config/common/canonical-ruler-pool.json')
    pool_by_id={row['ruler_id']:row for row in pool['records']}
    for path in (ROOT/'reader/data/people').glob('*.json'):
        row=json.loads(path.read_text(encoding='utf-8'))['record']
        for item in (row.get('net') or {}).get('component_details',{}).get('strategic',[]):
            if item['label'] not in ('A1','A2'):continue
            # Third-item source IDs are those declared by the canonical pool.
            canonical=pool_by_id[row['ruler_id']]
            source_id=canonical['source_item_ids']['third_item']
            assert item['reader_public_a'] == expected[source_id,item['label']]
            assert item['reader_how'] == item['reader_public_a']['calculation']
            seen+=1
    assert seen
    for filename in ('reader/person-readability.js','reader/home-interactions.js','reader/index.template.html','reader/second-item-public-labels.js'):
        assert 'globalThis.ThirdItemAReading.html' in (ROOT/filename).read_text(encoding='utf-8')
