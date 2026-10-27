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
const readability=fs.readFileSync('reader/readability.js','utf8');
const esc=t=>String(t??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
const prose=t=>'<p>'+esc(t)+'</p>';
const text='上沿不是自动升档。消费下降；仍有责任限制。';
const termStart=readability.indexOf('  const baseReaderText');
const termEnd=readability.indexOf('\n  function foldHomeStatus',termStart);
const map=new Function('readerText',readability.slice(termStart,termEnd)+';return readerText;')(String);
assert.equal(map(text),text);
assert.equal(map('POSITIVE'),'正向');
const helper=home.slice(home.indexOf('function secondMethodDetailsMarkup'),home.indexOf('function firstB1Markup'));
const supplements=new Function('esc','prose','link',helper+'return secondMethodDetailsMarkup;')(esc,prose,(ref)=>'<a>'+esc(ref)+'</a>');
const detail=supplements({reader_boundary:text,reader_how:'原计算口径。',reader_full_basis:'完整原始裁决。',source:'docs/a.json',reader_source_refs:['docs/b.json']},{});
for(const s of [text,'原计算口径。','完整原始裁决。','docs/a.json','docs/b.json'])assert.ok(detail.includes(s));
for(const file of ['reader/second-item-a-public.js','reader/second-item-b1-public.js']){
 const dedicated=fs.readFileSync(file,'utf8');
 assert.ok(!dedicated.includes('secondMethodDetailsMarkup(item, record)'));
 if(file.includes('second-item-a-')){
  assert.ok(dedicated.includes('entry.public_sources'));
  assert.ok(dedicated.includes('完整正式记录'));
  assert.ok(!dedicated.includes('SecondItemMaterialCards'));
 }else{
  assert.ok(dedicated.includes('appendDedicatedAudit'));
  assert.ok(dedicated.includes('SecondItemMaterialCards'));
 }
}
const alias=fs.readFileSync('reader/second-item-public-alias.js','utf8');
assert.ok(!alias.includes('patchInstitutionDetail'));
assert.ok(alias.includes('renderB2MaterialGroups(evidence)'));

const overview=home.slice(home.indexOf('  function firstItemOverview'),home.indexOf('  async function renderFirstMajor'));
const long='已有成果。'.repeat(100)+'末尾仍有不能归给本人的部分。';
const template=fs.readFileSync('reader/index.template.html','utf8');
const identitySource=template.slice(template.indexOf('function personLabel('),template.indexOf('const powerContextNote='));
const personLabel=new Function(identitySource+'return personLabel;')();
const costStart=home.indexOf('function firstCostPublicText');
const costEnd=home.indexOf('\n\nfunction firstCostMarkup',costStart);
const firstCostPublicText=new Function(home.slice(costStart,costEnd)+';return firstCostPublicText;')();
const render=new Function('esc','firstPublicSharePercent','firstPublicOutcomeParts','firstPublicOutcomeText','firstFactText','personLabel','firstCostPublicText',overview+'return firstItemOverview;')(esc,()=>'',a=>[['成果',a.public_outcome_basis]],String,String,personLabel,firstCostPublicText);
const html=render({ruler_name:'合成对象'}, {}, {'A统一贡献':{reader_public_outcome:{public_question:'合成阅读问题',public_story:long}}});
assert.equal(html.split(long).length-1,0); // The overview links to the full narrative card.
const aStart=home.indexOf('function firstAReadingMarkup'),aEnd=home.indexOf('// Formal public fields are shared',aStart);
const aMarkup=new Function('esc','prose','link',home.slice(aStart,aEnd)+'return firstAReadingMarkup;')(esc,prose,(ref)=>'<a>'+esc(ref)+'</a>');
const aHtml=aMarkup({value:12,reader_how:'合成计算。',source:'合成来源',reader_public_outcome:{public_question:'合成问题？',public_story:long,public_scope:'合成范围',public_outcome_basis:'合成起点',public_boundary:text,public_share_percent:10,public_scale_basis:'合成尺度说明'}},{});
assert.equal(aHtml.split(long).length-1,1);
assert.ok(aHtml.indexOf(long)<aHtml.indexOf('<details class="first-a-attribution">'));
assert.ok(aHtml.indexOf('<details class="first-a-attribution">')<aHtml.indexOf('<details class="first-a-method">'));
assert.ok(aHtml.includes(text));
assert.ok(aHtml.includes('合成计算。'));
assert.ok(!aHtml.includes('<details open'));
const noNote=aMarkup({value:12,reader_how:'合成计算。',reader_public_outcome:{public_question:'合成问题？',public_story:long,public_scope:'合成范围',public_outcome_basis:'合成起点',public_boundary:null,public_share_percent:10,public_scale_basis:'合成尺度说明'}},{});
assert.ok(!noNote.includes('<dt>具体范围说明</dt>'));
assert.ok(noNote.includes('合成范围'));
const b2Markup=new Function('esc','prose','link',home.slice(aStart,aEnd)+'return firstB2ReadingMarkup;')(esc,prose,(ref)=>'<a>'+esc(ref)+'</a>');
const b2Html=b2Markup({value:12,reader_public_b2:{public_question:'合成组织问题？',public_story:long,public_window:'本阶段',public_control:'授权两处主责',public_method:'逐项裁档相加',total_points:12,dimensions:[{label:'合成分项',points:4,basis:text}],public_sources:['docs/example.md']}},{});
assert.equal(b2Html.split(long).length-1,1);
assert.ok(b2Html.includes(text));
assert.ok(b2Html.indexOf(long)<b2Html.indexOf('<details class="first-b2-facts">'));
assert.ok(b2Html.indexOf('<details class="first-b2-facts">')<b2Html.indexOf('<details class="first-b2-method">'));
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
 esc:String,number:v=>String(v??'—'),scoreNumber:v=>String(v??'—'),conf:String,dimNames:{extent:'范围'},gradeHelp:()=>'',evidenceAssessment:()=>'',impactDimensionGrade:(key,grade)=>String(grade||'未列'),impactMeaning:{B:'合成影响量级'},
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
assert.ok(html.includes('突出当前展示值／档位差异'));
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


def test_home_filters_preserve_context_and_use_formal_identity(tmp_path):
    """Exercise the public control handlers without fixed real-world assessments."""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for browser behavior')
    script = tmp_path / 'reader-home-context.cjs'
    script.write_text(r'''
const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const source=fs.readFileSync('reader/index.template.html','utf8');
function section(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert.ok(a>=0&&b>a);return source.slice(a,b);}
const nodes=Object.fromEntries(['search','polity','scope','sort','impact-filter','toggle-home-view','toggle-filters','advanced-filters','filter-state','clear-filters','count','rows','selection'].map(id=>[id,{id,value:'',hidden:false,textContent:'',innerHTML:'',handlers:{},attributes:{},focus(){this.focused=true;},setAttribute(k,v){this.attributes[k]=v;},addEventListener(k,v){this.handlers[k]=v;}}]));
let writes=0,html='';
const screen={set innerHTML(v){writes++;html=v;},get innerHTML(){return html;}};
function record(id,extra={}){return {ruler_id:id,ruler_name:id,polity:'合成朝代',supplementary:false,axes:{},net:null,impact:{identity_label:id+'（合成称号）',reading_start_year:1,public_grade:'B',impact_nature:'合成性质',confidence:'MEDIUM'},...extra};}
const records=[record('left'),record('right'),record('supplement',{supplementary:true})];
records[0].impact.identity_label='left（<不作为HTML>）';
const original=JSON.stringify(records);
const state={q:'',polity:'',scope:'main',sort:'time',compare:['left'],grade:'',differences:false,filtersOpen:false,homeView:'simple'};
const context={DATA:{records,impact_grades:['B'],main_count:2,ranked_count:0,supplementary_count:1,capability_axes:[],independent_axes:[],axis_specs:{}},state,screen,byId:new Map(records.map(r=>[r.ruler_id,r])),document:{getElementById:id=>nodes[id]},nav(){},number:String,conf:String,impactMeaning:{B:'合成影响量级'}};
vm.createContext(context);
vm.runInContext(section('const esc=','const number=')+section('const letters=','const groupNames=')+section('function home(){','function netPanel('),context);
vm.runInContext('home()',context);
assert.equal(nodes['advanced-filters'].hidden,true);
assert.equal(nodes['toggle-filters'].attributes['aria-expanded'],'false');
assert.ok(nodes['filter-state'].textContent.includes('正式评价对象'));
assert.ok(nodes['rows'].innerHTML.includes('left（&lt;不作为HTML&gt;）'));
assert.ok(!nodes['rows'].innerHTML.includes('<不作为HTML>'));
assert.ok(!nodes['rows'].innerHTML.includes('undefined'));
assert.ok(nodes['rows'].innerHTML.includes('掌权背景：未列'));
assert.ok(nodes['rows'].innerHTML.includes('home-simple-list'));
assert.ok(!nodes['rows'].innerHTML.includes('<table>'));
nodes['toggle-home-view'].onclick();
assert.equal(state.homeView,'full');
assert.ok(nodes['rows'].innerHTML.includes('<table>'));
const firstWrites=writes;
nodes['toggle-filters'].onclick();
assert.equal(writes,firstWrites,'opening filters must not rebuild the page or lose focus');
assert.equal(nodes['advanced-filters'].hidden,false);
assert.equal(nodes['toggle-filters'].attributes['aria-expanded'],'true');
function change(id,value){nodes[id].value=value;nodes[id].handlers[id==='search'?'input':'change']({target:{value}});}
change('search','合成称号');assert.ok(!nodes['rows'].innerHTML.includes('data-person="left"'));assert.ok(nodes['rows'].innerHTML.includes('data-person="right"'));
change('search','');change('scope','supplementary');change('impact-filter','B');change('sort','impact');
assert.ok(nodes['rows'].innerHTML.includes('data-person="supplement"'));
assert.ok(!nodes['rows'].innerHTML.includes('data-person="right"'));
nodes['toggle-filters'].onclick();
assert.equal(nodes['advanced-filters'].hidden,true);
assert.ok(nodes['filter-state'].textContent.includes('补充历史样本'));
assert.ok(nodes['filter-state'].textContent.includes('影响等级 B'));
assert.ok(nodes['filter-state'].textContent.includes('历史影响等级排序'));
assert.ok(nodes['toggle-filters'].textContent.includes('3'));
vm.runInContext('home()',context); // Returning to the overview must preserve the query.
assert.equal(nodes.scope.value,'supplementary');assert.equal(nodes.sort.value,'impact');assert.equal(nodes['impact-filter'].value,'B');
assert.equal(nodes['advanced-filters'].hidden,true);
change('search','没有这个称号');assert.ok(nodes['rows'].innerHTML.includes('没有匹配人物'));
nodes['toggle-filters'].onclick();
const beforeReset=writes;
nodes['clear-filters'].onclick();
assert.equal(writes,beforeReset,'reset must preserve the same controls and keyboard focus');
assert.equal(nodes['advanced-filters'].hidden,false,'clearing filters does not reset disclosure state');
assert.equal(nodes.scope.value,'main');assert.equal(nodes.sort.value,'time');assert.equal(nodes.search.value,'');
assert.deepEqual(state.compare,['left'],'filter reset must not erase compare selection');
assert.ok(nodes['rows'].innerHTML.includes('data-person="left"'));
assert.equal(nodes['clear-filters'].disabled,true);assert.equal(nodes.search.focused,true);
assert.equal(JSON.stringify(records),original,'filtering must not mutate formal records');
assert.equal(vm.runInContext('personLabel({ruler_name:"只有本名"})',context),'只有本名');
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_context_strength_uses_formal_fields_not_prose(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for reader behavior')
    script = tmp_path / 'context-strength.cjs'
    script.write_text(r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/index.template.html','utf8');
const start=source.indexOf('const materialIntensityNames='),end=source.indexOf('\nfunction radar(',start);
assert.ok(start>=0&&end>start);
const escape=x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const api=new Function('esc','prose','axisProse','link',source.slice(start,end)+';return {contextDirection,contextIntensity,contexts};')(
 escape,x=>'<p>'+escape(x)+'</p>',x=>'<p>'+escape(x)+'</p>',()=>'<a>合同</a>');
for(const [code,label] of Object.entries({MI1:'单一情境',MI1_CASE:'单一情境',MI2:'完整生命周期情境',MI2_LIFECYCLE:'完整生命周期情境',MI3:'持续系统性情境',MI3_SUSTAINED_SYSTEMIC:'持续系统性情境',MI4:'跨阶段系统性情境',MI4_CROSS_PHASE_SYSTEMIC:'跨阶段系统性情境'})){
 assert.equal(api.contextIntensity({intensity:code}),label);
 assert.equal(api.contextIntensity({material_intensity:code}),label);
 assert.equal(api.contextIntensity({intensity:code,material_intensity:code}),label);
}
assert.equal(api.contextIntensity({basis:'跨阶段多年反复，有MI4字样。',axis_grade:'G5'}),'未列');
assert.equal(api.contextIntensity({intensity:null}),'未列');
assert.equal(api.contextIntensity({intensity:'FUTURE_CODE'}),'正式记录未提供可展示的标签');
assert.equal(api.contextDirection({direction:'POSITIVE'}),'正向');
assert.equal(api.contextDirection({direction:'FUTURE_DIRECTION'}),'正式记录未提供可展示的标签');
assert.equal(api.contextIntensity({intensity:'MI1_CASE',material_intensity:'MI4_CROSS_PHASE_SYSTEMIC'}),'正式记录中的材料强度字段存在冲突，请查看正式记录');
const record={counterpattern:{negative_parent_refs:['P']},context_lookup:{P:{intensity:'MI2_LIFECYCLE',basis:'完整正式说明，包括反证和限制。'}}};
const before=JSON.stringify(record),html=api.contexts(record,true);
assert.ok(html.includes('context-intensity'));
assert.ok(html.includes('完整生命周期情境'));
assert.ok(html.includes('formal-context-chip context-intensity'));
const auditIndex=html.indexOf('<details class="metadata">');
const rawIndex=html.indexOf('MI2_LIFECYCLE');
assert.ok(auditIndex>=0&&rawIndex>auditIndex,'raw intensity code must stay inside collapsed audit details');
assert.ok(html.includes(record.context_lookup.P.basis));
assert.equal(JSON.stringify(record),before);
assert.ok(!api.contexts(record,false).includes('context-intensity'),'do not add this presentation to unrelated axes');
record.context_lookup.P.intensity='<img onerror=alert(1)>';
const unsafe=api.contexts(record,true);
assert.ok(!unsafe.includes('<img'));
assert.ok(unsafe.includes('&lt;img'));
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_generated_reader_release_pins_dynamic_sources():
    import json
    import os
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    html = (root / "reader/index.html").read_text(encoding="utf-8")
    match = re.search(r'<script[^>]*\bid="reader-data"[^>]*>(.*?)</script>', html, flags=re.S)
    assert match
    payload = json.loads(match.group(1))
    expected = os.environ.get("GITHUB_SHA", "").lower()
    if expected:
        assert payload["source_revision"] == expected
        assert payload["source_repository"] == os.environ["GITHUB_REPOSITORY"]
        assert (root / "reader/source-revision.json").is_file()
        assert (root / "reader/data/person-reading-notes.json").is_file()
        assert "raw.githubusercontent.com" in html
        military = (root / "reader/military.html").read_text(encoding="utf-8")
        assert f'const READER_SOURCE_REVISION="{expected}"' in military
        assert "raw.githubusercontent.com" in military


def test_reader_formats_structured_power_windows_without_changing_formal_source():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/build.py").read_text(encoding="utf-8")

    namespace = {"json": __import__("json"), "deepcopy": __import__("copy").deepcopy}
    start = source.index("def public_power_window(value):")
    end = source.index("\ndef record_summary(record):", start)
    exec(source[start:end], namespace)
    fmt = namespace["public_power_window"]
    ctx = namespace["public_governance_context"]

    assert fmt("[[1435, 1449], [1457, 1464]]") == "1435—1449年；1457—1464年"
    assert fmt("[[-238, -221], [-220, -210]]") == "前238—前221年；前220—前210年"
    assert fmt("712—756年；756年失去实权后停止") == "712—756年；756年失去实权后停止"
    raw = {"actual_power_window":"[[1435, 1449], [1457, 1464]]",
           "basis":"本人实际权力窗口[[1435, 1449], [1457, 1464]]：全国州县继续运行。"}
    shown = ctx(raw)
    assert shown["actual_power_window"] == "1435—1449年；1457—1464年"
    assert "1435—1449年；1457—1464年" in shown["basis"]
    assert raw["actual_power_window"].startswith("[[")


def test_non_scoring_axes_and_fallback_totals_remain_visible(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "public-runtime-formatters.cjs"
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const home=fs.readFileSync('reader/home-interactions.js','utf8');
const second=fs.readFileSync('reader/second-item-reading.js','utf8');
function section(source,start,end){
  const a=source.indexOf(start),b=source.indexOf(end,a);
  assert.ok(a>=0&&b>a, start);
  return source.slice(a,b);
}

const genericCtx={
  esc:String,
  netGroupNames:{military:'第三项 · 军事体系与成本'},
  metricDetail:item=>'<metric>'+item.label+'</metric>',
  calculationBlock:()=>''
};
vm.createContext(genericCtx);
vm.runInContext(
  section(home,'  function genericNetGroup','  function firstItemRawUrl')
  +'\nthis.genericNetGroup=genericNetGroup;', genericCtx);
const rendered=genericCtx.genericNetGroup({},'military',[
  {label:'C1实战交付',reader_kind:'judgment',value:null,unit:'不单独计分'},
  {label:'C2持续作战',reader_kind:'judgment',value:null,public_level_label:'持续作战为S档'},
  {label:'隐藏空项',reader_kind:'judgment',value:null}
]);
assert.match(rendered,/C1实战交付/);
assert.match(rendered,/C2持续作战/);
assert.doesNotMatch(rendered,/隐藏空项/);

const fallbackCtx={
  finite:v=>{if(v==null||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null;},
  fmt:v=>Number(v).toFixed(1)
};
vm.createContext(fallbackCtx);
vm.runInContext(
  section(second,'  function componentFallbackSummary','  function ensureStyles')
  +'\nthis.componentFallbackSummary=componentFallbackSummary;', fallbackCtx);
const fallback=fallbackCtx.componentFallbackSummary({methodScore:88.5,resultScore:83.7,handoffScore:14});
assert.match(fallback,/制度与行政 88.5 \/ 165/);
assert.match(fallback,/民生与社会 83.7 \/ 202/);
assert.match(fallback,/政权交接 14.0 \/ 20/);
assert.doesNotMatch(fallback,/最强|最弱|主导/);
''', encoding="utf-8")
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
