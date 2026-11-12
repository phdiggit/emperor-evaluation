"""Authored reader prose stays linked to current evidence, without score snapshots."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def node(tmp_path, body):
    binary=shutil.which('node')
    if not binary:
        pytest.skip('Node.js required for reader behavior')
    script=tmp_path/'narratives.cjs'
    script.write_text("const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');\n"+body,encoding='utf-8')
    result=subprocess.run([binary,str(script)],cwd=ROOT,text=True,encoding='utf-8',capture_output=True)
    assert result.returncode==0,result.stderr


def test_narratives_validate_current_references_and_do_not_cross_systems(tmp_path):
    node(tmp_path,r'''
const api=require(process.cwd()+'/reader/person-reading-notes.js');
const notes=api.validateNotes(JSON.parse(fs.readFileSync('reader/person-reading-notes.json','utf8')));
for(const [id,entry] of Object.entries(notes.records)){
 if(!entry.reading)continue;
 const record=JSON.parse(fs.readFileSync('reader/data/people/'+id+'.json','utf8')).record;
 for(const chapters of Object.values(entry.reading))for(const chapter of chapters)
  assert.equal(api.assessBlock(chapter,record).status,'current');
}
const block={text:'合成正文',evidence:[{path:['axes','C1','typical_pattern'],quote:'合成事实'}]};
const synthetic={schema_id:'reader-person-overviews-v2',records:{'RULER-SYNTHETIC':{
 overview:{outcome:block,profile:block,impact:block},reading:{profile:[{title:'具体选择',...block}]}}}};
api.validateNotes(synthetic);
synthetic.records['RULER-SYNTHETIC'].reading.fourth=synthetic.records['RULER-SYNTHETIC'].reading.profile;
assert.throws(()=>api.validateNotes(synthetic),/another system/);
''')


def test_narrative_render_preserves_evidence_and_rejects_stale_quotes(tmp_path):
    node(tmp_path,r'''
const context={esc:v=>String(v).replace(/</g,'&lt;'),screen:{}};
vm.createContext(context);vm.runInContext(fs.readFileSync('reader/person-narratives.js','utf8'),context);
const r={ruler_id:'synthetic',axes:{C1:{typical_pattern:'具体选择'}},reader_narratives:{profile:[{
 title:'<主题>',text:'合成正文',evidence:[{path:['axes','C1','typical_pattern'],quote:'具体选择'}]}]}};
let html=context.personNarrative(r,'profile');
assert.ok(html.includes('&lt;主题>'));assert.ok(html.includes('合成正文'));assert.ok(html.includes('#person/synthetic/profile/C1'));
const original=JSON.stringify(r);
assert.ok(context.narrativeEvidence(r,'profile','<p>全部反证</p>').includes('<p>全部反证</p>'));
assert.equal(JSON.stringify(r),original);
r.axes.C1.typical_pattern='已经修改';html=context.personNarrative(r,'profile');
assert.ok(!html.includes('合成正文'));assert.ok(html.includes('依据已更新'));
assert.equal(context.narrativeEvidence({},'profile','original'),'original');
const outer={tagName:'DETAILS',open:false,parentElement:context.screen};
const inner={tagName:'DETAILS',open:false,parentElement:outer};
context.openReadingAncestors(inner);assert.ok(inner.open&&outer.open);
''')


def test_method_summary_and_detail_share_position_precision(tmp_path):
    node(tmp_path,r'''
const context={};vm.createContext(context);
vm.runInContext(fs.readFileSync('reader/second-item-display.js','utf8'),context);
for(const [value,expected] of [['G2 / middle-upper','C+'],['G4 / lower','A-'],['G3 / middle','B']])
 assert.equal(context.SecondItemDisplay.methodGrade({grade:value}),expected);
assert.equal(context.SecondItemDisplay.methodGrade({reader_b2_grade:'B−',grade:'G2 / middle'}),'B−');
for(const [file,name,next] of [['second-item-reading.js','methodBand','stateMeta'],['second-item-public-alias.js','publicMethodGrade','stateGradeMeta']]){
 const source=fs.readFileSync('reader/'+file,'utf8');
 const begin=source.indexOf('  function '+name+'('),end=source.indexOf('  function '+next+'(',begin);
 vm.runInContext(source.slice(begin,end),context);
 assert.equal(context[name]({grade:'G2 / middle-upper'}),'C+');
}
''')


def test_exploration_preview_uses_actual_grades_and_preserves_unrated_state(tmp_path):
    node(tmp_path,r'''
const context={esc:String,grade:axis=>axis.display};
vm.createContext(context);
const template=fs.readFileSync('reader/index.template.html','utf8');
vm.runInContext(template.slice(template.indexOf('function profileGradeScope('),template.indexOf('function profileGradeScopeMarkup(')),context);
vm.runInContext(fs.readFileSync('reader/person-narratives.js','utf8'),context);
const record={axes:{C1:{display:'A−',evidence_floor_review:true},C3:{display:'待补证'},C5:{display:'B',output_mode:'BOUNDED_PROFILE'}}};
const before=JSON.stringify(record),html=context.explorationSummary(record,'profile');
for(const value of ['战略判断','A−','用人授权','待补证','权力克制','B'])assert.ok(html.includes(value));
assert.equal(JSON.stringify(record),before);
assert.ok(html.includes('证据下限'));assert.ok(html.includes('结论有范围'));
const evidence=context.explorationSummary(record,'evidence');
assert.ok(evidence.includes('反例与限制'));assert.ok(evidence.includes('史料出处'));
assert.ok(!evidence.includes('<button'));
''')


def test_narrative_citations_keep_distinct_destinations_without_duplicate_quotes(tmp_path):
    node(tmp_path,r'''
const context={esc:String};vm.createContext(context);
vm.runInContext(fs.readFileSync('reader/person-narratives.js','utf8'),context);
const r={ruler_id:'synthetic',net:{component_details:{method:[{reader_story:'同一事实'}],finance:[{reader_story:'同一事实'}]}},reader_narratives:{second:[{
title:'合成主题',text:'正文',evidence:['method','finance'].map(group=>({path:['net','component_details',group,0,'reader_story'],quote:'同一事实'}))}]}};
const html=context.personNarrative(r,'second');
assert.equal(html.split('<blockquote>同一事实</blockquote>').length-1,1);
assert.ok(html.includes('#net/synthetic/second/method'));assert.ok(html.includes('#net/synthetic/second/finance'));
assert.ok(html.includes('查看制度与行政依据'));assert.ok(html.includes('查看民生与社会依据'));
''')


def test_control_combination_is_displayed_once_for_the_group(tmp_path):
    node(tmp_path,r'''
const context={};vm.createContext(context);vm.runInContext(fs.readFileSync('reader/third-item-b-public.js','utf8'),context);
const items=['B1','B2','B4'].map(label=>({label,public_component_label:label,reader_public_b:{
 evidence_items:[],sources:[],rate_table:[],scale:[],method:'共同规则',combination:'共同合成',calculation:'本轴计算'}}));
const html=items.map(item=>context.ThirdItemBReading.html(item,{})).join('')+context.ThirdItemBReading.combinationHtml(items);
assert.equal(html.split('共同规则').length-1,1);assert.equal(html.split('共同合成').length-1,1);
assert.equal(html.split('本轴计算').length-1,3);
''')
