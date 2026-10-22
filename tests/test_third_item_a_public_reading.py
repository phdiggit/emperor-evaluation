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
    return dict(start_grade=4, end_grade=3, end_state_value=30, positive_value_delta=0,
                negative_value_delta=-8, ceiling_progress_bonus=4,
                maintenance_bonus=8, reversal_penalty=2,
                within_band_deterioration_penalty=5,
                unclamped_trajectory_value=29, axis_points=17.4,
                settlement_type='CROSS_GRADE_DETERIORATION', settlement_type_label='跨档恶化型')


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
                               inherited='接手时河谷有防御支点，交通尚未连贯。',handover='关隘恢复互援，仍有一处缺口。',
                               responsibility='本人决定调配援军。',window='独立构造的责任时期',boundary='不采用后继者成果。',
                               sources=[dict(path='synthetic.json',label='独立合成来源',kind='合成用例')])
    original=copy.deepcopy(axis)
    result=reading_projection('A1',axis,contract())
    for key in ('inherited','handover','story','decision','responsibility','window','boundary'):
        assert result[key] == original['public_reading'][key]
    assert axis == original
    assert result['calculation']
    assert (result['start_label'], result['end_label']) == ('A档', 'B档')
    assert result['type_label'] == '跨档恶化型'
    assert result['scale'][0].startswith('E档（内部0档）')
    axis['public_reading']['story']='依据父卡撤回原档。'
    with pytest.raises(ValueError,match='内部术语'):
        reading_projection('A1',axis,contract())


def test_reading_rejects_a_missing_handoff_panel():
    axis = synthetic_axis()
    axis['public_reading'] = dict(story='独立合成经历。', decision='独立判断。',
                                 inherited='接手局面。', responsibility='本人部署。',
                                 window='合成时期', boundary='合成范围',
                                 sources=[dict(path='synthetic.json',label='合成来源',kind='合成用例')])
    with pytest.raises(ValueError, match='缺少handover'):
        reading_projection('A1', axis, contract())


def test_renderer_preserves_all_panels_and_full_experience(tmp_path):
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for renderer behavior')
    script = tmp_path / 'a-reading.cjs'
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={link:(path,label)=>label};context.globalThis=context;
vm.runInNewContext(fs.readFileSync('reader/third-item-a-public.js','utf8'),context);
const reading={inherited:'上游接班<文本>',handover:'上游交班文本',story:'完整经历甲。\n\n完整经历乙。',
 responsibility:'共同贡献不能独占。',decision:'主要方向仍有缺口。',window:'合成时期',
 boundary:'独立合成范围。',sources:[],start_label:'C档',end_label:'A档',type_label:'合成类型',
 method:'合成方法。',calculation:'合成计算。',source_note:'合成来源。',state_grade_note:'合成档位。',scale:[]};
const html=context.ThirdItemAReading.html({reader_public_a:reading},{});
assert(html.includes('接班 · C档'));assert(html.includes('交班 · A档'));
assert(html.includes('上游接班&lt;文本&gt;'));assert(html.includes('上游交班文本'));
assert(html.includes('完整经历甲。'));assert(html.includes('完整经历乙。'));
assert(html.includes('共同贡献不能独占。'));
assert(html.indexOf('完整经历甲。')>html.indexOf('<details>'));
delete reading.handover;
assert.throws(()=>context.ThirdItemAReading.html({reader_public_a:reading},{}),/接班或交班正文/);
''', encoding='utf-8')
    result = subprocess.run([node,str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_current_sources_and_all_reader_surfaces_share_a_reading():
    credit=load_json(ROOT/'config/third-item/third-item-result-credit-adjudications.json')
    ab=load_json(ROOT/'docs/评分结算/净收益/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json')
    ab_by_id={r['ruler_id']:r for r in ab['records']}
    expected={}
    for row in credit['records']:
        for axis_name,axis in row['axes'].items():
            reading=axis['public_reading']
            assert reading == reading_projection(axis_name,axis,credit['contract'])
            assert 'public_axis_projections' not in row
            assert 'public_axis_projections' not in ab_by_id[row['ruler_id']]
            assert 'public_reading' not in ab_by_id[row['ruler_id']]['axes'][axis_name]
            assert reading['story'] != axis['public_adjudication_summary']
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
