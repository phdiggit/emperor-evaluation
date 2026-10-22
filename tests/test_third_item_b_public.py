"""B-reader invariants and synthetic boundaries; never freeze ruler decisions."""
import copy
import json
from pathlib import Path
import pytest
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.third_item_b_public import AXES, reading_projection, combination, region_values, verify_sources

ROOT = Path(__file__).resolve().parents[1]
AB = Path('docs/评分结算/净收益/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json')
CREDIT = Path('config/third-item/third-item-result-credit-adjudications.json')


def synthetic():
    text = dict(story='边郡恢复控制，交班保有常设驻防。', decision='保留当前有据的控制成果。',
                responsibility='本人决定恢复驻军，地方官执行。', window='独立构造的责任窗口',
                boundary='不采用继任者独立取得的成果。', adoption_basis='与另一项重复的控制成果排除。',
                evidence_items=[dict(label='边郡控制',basis='边郡已有常设驻防。',sources=[dict(path='source.json',label='合成来源',kind='合成用例')])],
                sources=[dict(path='source.json',label='合成来源',kind='合成用例')],source_note='合成用例，没有真实人物。',review_explanation='')
    axes={}
    for key,level,position,rate in [('B1',1,'MID',37),('B2',4,'LOW',75),('B4',2,'MID',52)]:
        axes[key]=dict(grade=f'{key}-{level}',band_position=position,score_rate=rate,public_reading=copy.deepcopy(text))
    b=dict(formal_B1_rate=37,formal_B2_rate=75,formal_B4_rate=52,
           adjudicated_B1_rate=37,adjudicated_B2_rate=0,adjudicated_B4_rate=0,B80_points=11.4)
    row=dict(ruler_name='合成人物',ruler_id='SYNTHETIC',axes=axes,B80_score_points=11.4,
             control_contribution_type='NEW_RECOVERED_REBUILT',b1_control_equivalents=dict(start=1,end=1,net_change=0,weighted_value=.4),
             b1_region_adjudications=[])
    return row,dict(B80_adjudication=b)


def test_raw_and_adopted_rates_are_separate_and_inputs_stay_read_only():
    row,credit=synthetic();before=copy.deepcopy((row,credit))
    reading=reading_projection('B2',row,credit)
    assert reading['raw_rate']==75 and reading['adopted_rate']==0
    assert '正式合成采用0%' in reading['rate_note']
    assert '11.40分' in reading['combination']
    assert (row,credit)==before


def test_another_recorded_diagnostic_rate_does_not_replace_current_axis():
    row,credit=synthetic();credit['B80_adjudication']['formal_B2_rate']=100
    reading=reading_projection('B2',row,credit)
    assert reading['raw_rate']==75 and reading['recorded_diagnostic_rate']==100
    assert reading['adopted_rate']==0 and '不参与当前合成' in reading['diagnostic_note']


@pytest.mark.parametrize('status',['NOT_REVIEWED','EVIDENCE_GAP','CONFIRMED'])
def test_b4_review_status_is_explicit_and_never_inferred_from_grade(status):
    row,credit=synthetic()
    if status!='NOT_REVIEWED':
        row['axes']['B4']['maturity_review']=dict(status=status,basis='合成边界说明')
        row['axes']['B4']['public_reading']['review_explanation']='合成边界说明'
        row['axes']['B4']['public_reading']['review_source_basis']='合成边界说明'
    reading=reading_projection('B4',row,credit)
    assert reading['review_status']==status and reading['review_note']
    assert row['axes']['B4']['score_rate']==52
    if status!='CONFIRMED':assert '尚未' in reading['review_note']


def test_unknown_review_state_and_wrong_total_fail_instead_of_modifying_scores():
    row,credit=synthetic();row['axes']['B4']['maturity_review']=dict(status='UNDECLARED')
    with pytest.raises(ValueError,match='未知B4'):reading_projection('B4',row,credit)
    credit['B80_adjudication']['B80_points']=1
    with pytest.raises(ValueError,match='禁止为展示改分'):combination(row,credit)
    assert row['B80_score_points']==11.4


def test_region_missing_anchor_is_not_invented_as_zero():
    result=region_values(dict(object_name='边郡',anchors=['end'],control_equivalent=.5))
    assert result['start'] is None and result['end']==.5


def test_b4_changed_review_basis_requires_authored_prose_to_be_checked():
    row,credit=synthetic()
    row['axes']['B4']['maturity_review']=dict(status='CONFIRMED',basis='新的运行判断')
    row['axes']['B4']['public_reading']['review_source_basis']='先前的运行判断'
    with pytest.raises(ValueError,match='同步公开判词'):reading_projection('B4',row,credit)


def test_source_cannot_support_itself_from_its_public_copy(tmp_path):
    (tmp_path/'source.json').write_text(json.dumps(dict(ruler_id='SYNTHETIC',public_copy='UNSUPPORTED')),encoding='utf-8')
    ref=dict(path='source.json',label='合成来源',kind='合成材料',binding='UNSUPPORTED')
    payload=dict(records=[dict(axes={axis:dict(public_reading=dict(sources=[ref],evidence_items=[])) for axis in AXES})])
    with pytest.raises(ValueError,match='定位不匹配'):verify_sources(tmp_path,payload)


def test_formal_narratives_review_states_and_reader_values_share_current_authorities():
    ab=load_json(ROOT/AB);credits={row['ruler_id']:row for row in load_json(ROOT/CREDIT)['records']}
    expected={}
    for row in ab['records']:
        for axis in AXES:
            reading=row['axes'][axis]['public_reading']
            assert reading==reading_projection(axis,row,credits[row['ruler_id']])
            if axis=='B4':
                assert reading['review_status']==row['axes'][axis].get('maturity_review',{}).get('status','NOT_REVIEWED')
            expected[row['ruler_id'],axis]=reading
    pool={row['ruler_id']:row for row in load_json(ROOT/'config/common/canonical-ruler-pool.json')['records']}
    observed=[]
    for path in (ROOT/'reader/data/people').glob('*.json'):
        detail=json.loads(path.read_text(encoding='utf-8'));row=detail['record']
        for item in (row.get('net') or {}).get('component_details',{}).get('strategic',[]):
            if item['label'] not in AXES:continue
            source_id=pool[row['ruler_id']]['source_item_ids']['third_item']
            assert item['reader_public_b']==expected[source_id,item['label']]
            assert item['value']==item['reader_public_b']['raw_rate']
            assert item['applied_value']==item['reader_public_b']['adopted_rate']
            assert all(detail['source_availability'][ref] for ref in item['reader_source_refs'])
            observed.append(item)
    assert observed
