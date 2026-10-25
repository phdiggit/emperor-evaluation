"""Current joint C projection, provenance, ownership and read-only contracts."""
from copy import deepcopy
import copy
import json
from pathlib import Path
import pytest
from c_joint_cases import row
from emperor_v4.evaluation.third_item_c_public import calculation,reading_projection,verify_sources,markdown,_json_passage_matches
from emperor_v4.evaluation.third_item_c_contract_reading import build_review,html_review,markdown_review
from emperor_v4.evaluation.third_item_c_joint import RETIRED_FIELDS,verify_joint
EMPTY={'systems':{},'o_grades':{}}

@pytest.mark.parametrize('field',sorted(RETIRED_FIELDS))
def test_retired_scoring_fields_are_rejected(field):
    r=row();r[field]=3
    with pytest.raises(ValueError):calculation(r)

@pytest.mark.parametrize('position,value',[('LOW',.25),('MID',.5),('HIGH',.75)])
def test_explicit_position_is_not_a_maximum_with_quality_or_surplus(position,value):
    r=row(3,position);r['strategy_chain_outcome_profile']={'return_class_counts':{'HIGH_RETURN':20}}
    before=deepcopy(r);out=calculation(r)
    assert r['C_score_band_position']==value and out['points']==r['C_score_points']
    assert r==before

def test_grade_five_uses_the_adopted_position_instead_of_full_marks():
    r=row(5,'LOW');out=calculation(r)
    assert out['rate']==92.5 and out['points']==46.3

def test_unknown_has_no_score_and_does_not_erase_material():
    r=row(None);p=reading_projection(r,context=EMPTY)
    assert p['axes']['C1']['grade'] is None and p['calculation']['points'] is None
    assert p['evidence_items']==r['public_reading']['evidence_items']
    r['C_score_points']=0
    with pytest.raises(ValueError):calculation(r)

@pytest.mark.parametrize('key',['story','window','responsibility','boundary','source_note','position_explanation'])
def test_authored_public_fields_are_required(key):
    r=row();del r['public_reading'][key]
    with pytest.raises(ValueError):reading_projection(r,context=EMPTY)

def test_projection_preserves_authored_text_and_does_not_mutate_inputs():
    r=row();before=deepcopy(r);p=reading_projection(r,context=EMPTY)
    assert p['story']==r['public_reading']['story'] and set(p['axes'])=={'C1'}
    assert '合成整体判断' in markdown(r,context=EMPTY)
    p['evidence_items'].clear();assert r==before


@pytest.mark.parametrize('key',['axes','calculation','contract_review'])
def test_stored_generated_copy_cannot_become_a_second_authority(key):
    r=row();r['public_reading'][key]={}
    with pytest.raises(ValueError):reading_projection(r,context=EMPTY)


def test_shared_javascript_renders_current_and_unknown_data_without_changing_scores(tmp_path):
    import shutil,subprocess
    node=shutil.which('node')
    if not node:pytest.skip('Node required for shared renderer')
    data=[reading_projection(row(),context=EMPTY),reading_projection(row(None),context=EMPTY)]
    script=tmp_path/'render.cjs'
    script.write_text("""const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const inputs=JSON.parse(fs.readFileSync(0,'utf8'));const context={link:(path,label)=>'<a>'+label+'</a>'};
vm.runInNewContext(fs.readFileSync('reader/third-item-c-public.js','utf8'),context);
for(const data of inputs){const before=JSON.stringify(data);const html=context.ThirdItemCReading.html({reader_public_third_c:data},{});
assert.ok(html.includes('合成整体判断'));assert.ok(html.includes('合成守御材料'));
assert.ok(context.ThirdItemCReading.heading({reader_public_third_c:data}).includes(data.calculation.total_label));assert.equal(JSON.stringify(data),before);}
assert.equal(inputs[1].calculation.points,null);
""",encoding='utf8')
    result=subprocess.run([node,str(script)],input=json.dumps(data,ensure_ascii=False),cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stderr


def test_authored_narrative_and_position_are_shown_once_without_appending_evidence_fields(tmp_path):
    import shutil,subprocess
    node=shutil.which('node')
    if not node:pytest.skip('Node required for shared renderer')
    r=row();r['joint_assessment']['reason']='内部整体理由'
    r['joint_assessment']['position_basis']='内部位置依据'
    r['joint_assessment']['positive_evidence']='内部正证'
    r['joint_assessment']['adverse_evidence']='内部反证'
    before=deepcopy(r);p=reading_projection(r,context=EMPTY)
    text=markdown(r,context=EMPTY)
    assert text.count(p['story'])==1 and text.count(p['position_explanation'])==1
    script=tmp_path/'authored-once.cjs'
    script.write_text("""const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const data=JSON.parse(fs.readFileSync(0,'utf8')),context={link:()=>'<a>来源</a>'};
vm.runInNewContext(fs.readFileSync('reader/third-item-c-public.js','utf8'),context);
const html=context.ThirdItemCReading.html({reader_public_third_c:data},{});
for(const text of [data.story,data.position_explanation])assert.equal(html.split(text).length-1,1);
for(const text of ['内部整体理由','内部位置依据','内部正证','内部反证'])assert.ok(!html.includes(text));
""",encoding='utf8')
    result=subprocess.run([node,str(script)],input=json.dumps(p,ensure_ascii=False),cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stderr
    assert r==before


def test_task_names_must_cover_current_tasks_without_a_renderer_guess():
    r=row();r['public_reading']['task_titles'].pop('SYNTHETIC-A')
    with pytest.raises(ValueError,match='任务名称'):reading_projection(r,context=EMPTY)

@pytest.mark.parametrize('fault',['duplicate','foreign_chain','unknown_kind'])
def test_material_identity_kind_and_scope_fail_closed(fault):
    r=row();e=r['public_reading']['evidence_items'][0]
    if fault=='duplicate':r['public_reading']['evidence_items'].append(deepcopy(e))
    elif fault=='foreign_chain':e['c_chain_refs']=['FOREIGN']
    else:e['kind']='猜测'
    with pytest.raises(ValueError):reading_projection(r,context=EMPTY)

def test_current_and_capability_chains_remain_separate_and_do_not_add_votes():
    r=row(4,'LOW');before=deepcopy(r)
    r['strategy_chains'][0]['member_parent_refs']=['P1','P2','P3']
    p=build_review(r,EMPTY)
    assert len(p['chains'])==2 and p['chains'][1]['scope']=='能力专用'
    assert calculation(r)['points']==calculation(before)['points']

def test_excluded_observation_is_visible_and_cannot_be_re_adopted():
    r=row();r['joint_assessment']['excluded_observations']={'SYNTHETIC-A':'交班后材料'}
    with pytest.raises(ValueError):verify_joint(r)
    r['joint_assessment']['adopted_chain_refs'].remove('SYNTHETIC-A')
    p=build_review(r,EMPTY)
    assert '交班后材料' in html_review(p) and '不计分' in markdown_review(p)

def test_a_long_chain_can_hold_independent_tasks_without_artificial_splitting():
    r=row(4,'LOW');r['joint_assessment']['adopted_chain_refs']=['SYNTHETIC-A']
    assert verify_joint(r)==4
    r['joint_assessment']['independent_revalidation_basis']=''
    with pytest.raises(ValueError):verify_joint(r)

@pytest.mark.parametrize('fault',['other_person','other_task','grade_mismatch'])
def test_registered_actual_opponent_window_is_owned_and_same_value(fault):
    r=row();w=dict(subject_ruler_id='SYNTHETIC',source_chain_refs=['SYNTHETIC-A'],organization_grade='O4')
    context={'systems':{'ENEMY':{'window_assessments':{'WINDOW':w}}}}
    entry=dict(opponent_system_ref='ENEMY',organization_grade='O4',registry_pointer='config/military/opponent-system-contract.json#/window_assessment_extensions/ENEMY/WINDOW',label='合成对手')
    r['joint_assessment']['opponent_windows']=[dict(ref='SYNTHETIC-A',label='合成任务',status='REGISTERED_ACTUAL_WINDOW',opponents=[entry])]
    assert build_review(r,context)['chains']
    if fault=='other_person':w['subject_ruler_id']='FOREIGN'
    elif fault=='other_task':w['source_chain_refs']=['FOREIGN']
    else:w['organization_grade']='O3'
    with pytest.raises(ValueError):build_review(r,context)

def test_source_excerpt_must_be_under_the_declared_markdown_heading(tmp_path):
    r=row();p=r['public_reading']['evidence_items'][0]
    p['sources']=[dict(path='synthetic.md',label='合成来源')]
    p['source_passages']=[dict(path='synthetic.md#OWN',quote='守住主防御',kind='既有史实摘要')]
    (tmp_path/'synthetic.md').write_text('### OWN 本人\n守住主防御\n### OTHER 他任\n别处事实\n',encoding='utf8')
    assert verify_sources(tmp_path,{'records':[r]},context=EMPTY)==1
    p['source_passages'][0]['quote']='别处事实'
    with pytest.raises(ValueError):verify_sources(tmp_path,{'records':[r]},context=EMPTY)

def test_json_anchor_and_each_excerpt_line_stay_in_one_card():
    d={'cards':[dict(campaign_group='A',battle_label='甲',first='进军',second='破主军'),dict(campaign_group='B',battle_label='乙',first='他任撤退')]}
    assert _json_passage_matches(d,'campaign_group=A&battle_label=甲','进军\n破主军')
    assert not _json_passage_matches(d,'campaign_group=A&battle_label=甲','进军\n他任撤退')
    with pytest.raises(ValueError):_json_passage_matches(d,'campaign_group=C','进军')

@pytest.mark.parametrize('fault',['foreign_person','foreign_ref','duplicate','no_delivery'])
def test_phase_evidence_scope_and_admission_are_not_an_automatic_grade(fault):
    r=row();phase=dict(ruler_id='SYNTHETIC',ref='SYNTHETIC-A',label='合成阶段',status='ACCEPT',adopted_difficulty='D3',
        joint_phase_reason='合成复合约束与破主军过程',source_passages=[dict(path='synthetic.md',quote='合成事实')])
    r['joint_assessment']['key_phase_reviews']=[phase]
    assert verify_joint(r)==3
    if fault=='foreign_person':phase['ruler_id']='FOREIGN'
    elif fault=='foreign_ref':phase['ref']='FOREIGN'
    elif fault=='duplicate':r['joint_assessment']['key_phase_reviews'].append(deepcopy(phase))
    else:phase['status']='LIMITED'
    with pytest.raises(ValueError):verify_joint(r)


def test_window_correction_resolves_legacy_difference_only_with_matching_review():
    from emperor_v4.evaluation.third_item_c_contract_reading import _opponent_grade_conflict
    opponent = dict(ref='SYNTHETIC-OPPONENT', grade='O4',
                    binding_status='SOURCE_WINDOW_REVIEWED', assessment_ref='SYNTHETIC-WINDOW')
    reviewed = dict(opponent_adjudication_notes={opponent['ref']: dict(
        basis='合成守军有区域征补与接续援军。', window_ref='SYNTHETIC-WINDOW')})
    assert not _opponent_grade_conflict('O2', [opponent], reviewed)
    assert _opponent_grade_conflict('O2', [opponent], {})
    stale = copy.deepcopy(reviewed)
    stale['opponent_adjudication_notes'][opponent['ref']]['window_ref'] = 'OTHER-WINDOW'
    assert _opponent_grade_conflict('O2', [opponent], stale)
    candidate = dict(opponent, binding_status='PUBLIC_TASK_CANDIDATE')
    assert _opponent_grade_conflict('O2', [candidate], reviewed)
    assert not _opponent_grade_conflict('O4', [opponent], {})

def test_local_material_review_keeps_non_system_and_missing_process_distinct():
    from emperor_v4.evaluation.third_item_c_contract_reading import _unresolved_opponent
    source = dict(actual_window='合成窗口', source_passages=[])
    entry = dict(label='合成营内兵变', basis='未证独立区域征补。', classification='NON_SYSTEM')
    result = _unresolved_opponent(entry, 'SYNTHETIC-CHAIN', [], source)
    assert result['grade'] == '未证独立体系'
    assert result['grade_range'] == []
    assert result['binding_status'] != 'SOURCE_WINDOW_REVIEWED'
    gap = _unresolved_opponent(dict(entry, classification='SOURCE_GAP'), 'SYNTHETIC-CHAIN', [], source)
    assert gap['grade'] == '缺具体过程'
    assert gap['source']
    with pytest.raises(ValueError, match='未知'):
        _unresolved_opponent(dict(entry, classification='UNREVIEWED_GUESS'), 'SYNTHETIC-CHAIN', [], source)
