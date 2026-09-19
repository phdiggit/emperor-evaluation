"""Public prose remains intact across overview, detail and profile renderers."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_public_readers_keep_complete_prose_and_independent_source_panels(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for browser behavior')
    script = tmp_path/'public-boundaries.cjs'
    script.write_text(r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const home=fs.readFileSync('reader/home-interactions.js','utf8');
const person=fs.readFileSync('reader/person-readability.js','utf8');
const readability=fs.readFileSync('reader/readability.js','utf8');
const esc=t=>String(t??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
const prose=t=>'<p>'+esc(t)+'</p>';
const text='上沿不是自动升档。消费下降；仍有责任限制。';
const termStart=readability.indexOf('  const baseReaderText');
const termEnd=readability.indexOf('\n  function foldHomeStatus',termStart);
const map=new Function('readerText',readability.slice(termStart,termEnd)+';return readerText;')(String);
assert.equal(map(text),text);
assert.equal(map('POSITIVE'),'正向');
const direct=person.match(/const netPublicText = [^;]+;/)[0];
const publicText=new Function(direct+'return netPublicText;')();
assert.equal(publicText(text),text);
assert.equal(publicText('G3属于原公开正文。'),'G3属于原公开正文。');

const helper=home.slice(home.indexOf('function secondMethodDetailsMarkup'),home.indexOf('function firstB1Markup'));
const supplements=new Function('esc','prose','link',helper+'return secondMethodDetailsMarkup;')(esc,prose,(ref)=>'<a>'+esc(ref)+'</a>');
const detail=supplements({reader_boundary:text,reader_how:'原计算口径。',reader_full_basis:'完整原始裁决。',source:'docs/a.json',reader_source_refs:['docs/b.json']},{});
for(const s of [text,'原计算口径。','完整原始裁决。','docs/a.json','docs/b.json'])assert.ok(detail.includes(s));
for(const file of ['reader/second-item-a-public.js','reader/second-item-b1-public.js'])assert.ok(fs.readFileSync(file,'utf8').includes('secondMethodDetailsMarkup(item, record)'));
const alias=fs.readFileSync('reader/second-item-public-alias.js','utf8');
assert.ok(!alias.includes('patchInstitutionDetail'));

const overview=home.slice(home.indexOf('  function firstItemOverview'),home.indexOf('  async function renderFirstMajor'));
const long='已有成果。'.repeat(100)+'末尾仍有不能归给本人的部分。';
const render=new Function('esc','firstPublicSharePercent','firstPublicOutcomeParts','firstPublicOutcomeText','firstFactText',overview+'return firstItemOverview;')(esc,()=>'',a=>[['成果',a.public_outcome_basis]],String,String);
const html=render({ruler_name:'合成对象'}, {'B2组织与整合':{'并行执行':long}}, {'A统一贡献':{reader_public_outcome:{public_outcome_basis:long}}});
assert.equal(html.split(long).length-1,2);
// Exercise current public data, without storing any adjudication snapshot.
for(const path of fs.readdirSync('reader/data/people')) {
 const record=JSON.parse(fs.readFileSync('reader/data/people/'+path,'utf8')).record;
 for(const items of Object.values(record.net?.component_details||{})) {
  for(const item of items)for(const key of ['reader_summary','reader_boundary']) {
   if(item[key])assert.equal(publicText(item[key]),String(item[key]).trim());
  }
 }
}
''',encoding='utf-8')
    result=subprocess.run([node,str(script)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    assert result.returncode == 0,result.stderr


def test_public_radar_levels_and_comparison_preserve_evidence(tmp_path):
    """Use synthetic axes/people, never fixed grades or ranks of real people."""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for browser behavior')
    script = tmp_path / 'reader-geometry-comparison.cjs'
    script.write_text(r'''
const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const source=fs.readFileSync('reader/index.template.html','utf8');
function section(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert.ok(a>=0&&b>a);return source.slice(a,b);}
const capabilities=['M1','M2','M4','M5','C1','C2','C3','C4'];
const codes=[...capabilities,'C5'];
let writes=0,html='',emphasis=false;
const checkbox={},table={classList:{toggle(name,value){assert.equal(name,'emphasize-differences');emphasis=value;}}};
const screen={set innerHTML(value){writes++;html=value;},get innerHTML(){return html;}};
const data={capability_axes:capabilities,independent_axes:['C5'],axis_specs:Object.fromEntries(codes.map(c=>[c,{name:c}]))};
const state={compare:['left','right'],differences:false};
const context={DATA:data,state,screen,byId:new Map(),nav(){},history:{replaceState(){}},
 document:{getElementById(id){assert.equal(id,'differences');return checkbox;},querySelector(selector){assert.equal(selector,'.comparison');return table;}},
 esc:String,number:v=>String(v??'—'),conf:String,dimNames:{extent:'范围'},gradeHelp:()=>'',
 netGroups:r=>`<p>构成-${r.ruler_id}</p>`,historySections:r=>`<p>后效-${r.ruler_id}</p>`,
 axisEvidence:(r,c)=>`<details><summary>${c}</summary><p>${r.axes[c].evidence}</p></details>`};
vm.createContext(context);
vm.runInContext(section('const letters=','const groupNames=')+section('function radar(r)','function axisRows(')+section('function compare(){','function guide()'),context);
function evalAxis(axis,fn='radarValue'){context.axis=axis;return vm.runInContext(`${fn}(axis)`,context);}
for(let i=0;i<18;i++){
 const axis={axis_grade:'G'+Math.floor(i/3),position:['LOW','MID','HIGH'][i%3],radar_value:-999};
 assert.equal(evalAxis(axis,'profileLevelIndex'),i);
 assert.ok(Math.abs(evalAxis(axis)-i/17*100)<1e-10);
 // Legacy projection is deliberately irrelevant, including when absent.
 delete axis.radar_value;assert.ok(Math.abs(evalAxis(axis)-i/17*100)<1e-10);
}
const valid={axis_grade:'G3',position:'MID'};
for(const axis of [null,{}, {...valid,axis_grade:'G9'}, {...valid,position:'UNKNOWN'},
 {...valid,adjudication_state:'EVIDENCE_INSUFFICIENT_CLOSED'},
 {...valid,adjudication_state:'UNRESOLVED_EVIDENCE_GAP'},
 {...valid,adjudication_state:'REASSESSMENT_REQUIRED'}, {...valid,display_point_only:true},
 {...valid,applicability_status:'NOT_APPLICABLE'}, {...valid,output_mode:'NOT_APPLICABLE'}])assert.equal(evalAxis(axis),null);
function record(id){return {ruler_id:id,ruler_name:id,actual_power_window:'合成时期',net:{total_score:10,rank:1,second_item_score:5},
 impact:{public_grade:'B',impact_nature:'合成说明',dimensions:{extent:{grade:'B'}},confidence:'medium'},
 axes:Object.fromEntries(codes.map(c=>[c,{...valid,evidence:`${id}-${c}-独立依据`}]))};}
const left=record('left'),right=record('right');right.axes.M2.position='HIGH';
context.byId.set('left',left);context.byId.set('right',right);
const before=JSON.stringify([left,right]);
context.person=left;
const radar=vm.runInContext('radar(person)',context);
assert.ok(radar.includes('data-level-index="17"'));
assert.ok(radar.includes('fill="#28655926"'));
left.axes.C5={axis_grade:'G0',position:'LOW'};
assert.equal(vm.runInContext('radar(person)',context),radar,'C5 must not affect ability geometry');
left.axes.C5=JSON.parse(before)[0].axes.C5;
left.axes.M1.display_point_only=true;
assert.ok(!vm.runInContext('radar(person)',context).includes('fill="#28655926"'),'missing evidence must not be filled with zero');
delete left.axes.M1.display_point_only;
vm.runInContext('compare()',context);
const initialHTML=html,initialWrites=writes,rowCount=(html.match(/<tr/g)||[]).length;
for(const id of ['left','right'])for(const c of codes)assert.ok(html.includes(`${id}-${c}-独立依据`));
assert.ok(html.includes('data-compare-equal="true"'));
assert.ok(html.includes('data-compare-equal="false"'));
assert.ok(html.includes('突出分数／等级差异'));
// Toggling only changes the table's class, not DOM/evidence/open state/scroll.
checkbox.onchange({target:{checked:true}});assert.equal(emphasis,true);
assert.equal(writes,initialWrites);assert.equal(html,initialHTML);
checkbox.onchange({target:{checked:false}});assert.equal(emphasis,false);assert.equal(writes,initialWrites);
state.differences=true;vm.runInContext('compare()',context);
assert.equal((html.match(/<tr/g)||[]).length,rowCount);
for(const id of ['left','right'])for(const c of codes)assert.ok(html.includes(`${id}-${c}-独立依据`));
assert.equal(JSON.stringify([left,right]),before,'rendering must not change formal inputs');
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
