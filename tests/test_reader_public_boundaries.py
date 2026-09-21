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
for(const file of ['reader/second-item-a-public.js','reader/second-item-b1-public.js']){
 const dedicated=fs.readFileSync(file,'utf8');
 assert.ok(!dedicated.includes('secondMethodDetailsMarkup(item, record)'));
 assert.ok(dedicated.includes('appendDedicatedAudit'));
 assert.ok(dedicated.includes('SecondItemMaterialCards'));
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
const context={DATA:{records,impact_grades:['B'],main_count:2,ranked_count:0,supplementary_count:1,capability_axes:[],independent_axes:[],axis_specs:{}},state,screen,byId:new Map(records.map(r=>[r.ruler_id,r])),document:{getElementById:id=>nodes[id]},nav(){},number:String,conf:String};
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


def test_public_time_context_and_impact_scales_do_not_gate_records(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for browser behavior')
    script = tmp_path / 'reader-scale-context.cjs'
    script.write_text(r'''
const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const source=fs.readFileSync('reader/index.template.html','utf8');
function section(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert.ok(a>=0&&b>a);return source.slice(a,b);}
const dimNames={scope:'影响范围',depth_duration:'深度与持续',personal_causality:'个人因果',paradigm:'政治范式'};
const record={ruler_id:'synthetic',ruler_name:'本名',polity:'合成时期',axes:{},impact:{identity_label:'本名（正式称呼）',public_grade:'B',impact_nature:'合成性质',confidence:'MEDIUM',dimensions:Object.fromEntries(Object.keys(dimNames).map(k=>[k,{grade:'A',public_basis:'应完整保留的分项说明。'}]))}};
// No actual_power_window: lack of background metadata cannot block profile rendering.
const original=JSON.stringify(record);
const screen={innerHTML:''};
const context={record,screen,DATA:{capability_axes:[],independent_axes:[],axis_order:[]},nav(){},dimNames,impactMeaning:{},conf:String,gradeHelp:()=>'',axisRows:()=>'',radar:()=>'',historySections:()=>'',netPanel:()=>'<section>合成结果</section>'};
vm.createContext(context);
vm.runInContext(section('const esc=','const number=')+section('const letters=','const groupNames=')+section('function impactPanel(','function axisEvidence(')+section('function person(r){','function compare(){'),context);
vm.runInContext('person(record)',context);
assert.ok(screen.innerHTML.includes('本名（正式称呼）'));
assert.ok(screen.innerHTML.includes('掌权背景：未列'));
assert.ok(screen.innerHTML.includes('各项具体范围以各自依据为准'));
assert.ok(screen.innerHTML.includes('各时期'));
assert.ok(screen.innerHTML.includes('id="person-capability"'),'profile must remain visible without a power-period field');
assert.ok(screen.innerHTML.includes('四维分项与总等级使用不同刻度'));
assert.ok(screen.innerHTML.indexOf('impact-scale-note')<screen.innerHTML.indexOf('class="dimensions"'));
for(const key of Object.keys(dimNames))assert.ok(screen.innerHTML.includes('data-section="history-dimension-'+key+'"'));
const technical=vm.runInContext('impactTechnicalHelp()',context);
assert.ok(technical.startsWith('<details '));assert.ok(!technical.includes(' open'));
assert.equal(JSON.stringify(record),original,'renderers must not invent or attach an evidence window');
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_profile_public_names_do_not_leak_codes_or_rewrite_other_identifiers(tmp_path):
    """Names are context-specific; source records and fiscal prose stay untouched."""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for browser behavior')
    script = tmp_path / 'public-axis-names.cjs'
    script.write_text(r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/readability.js','utf8');
const start=source.indexOf('  const baseReaderText'),end=source.indexOf('\n  function foldHomeStatus',start);
const api=new Function('readerText',source.slice(start,end)+';return {map:readerText,names:profileCodeNames,scope:conflictScopeText};')(String);
for(const [code,name] of Object.entries({M1:'军事统帅',M2:'外交博弈',M4:'内部联盟',M5:'组织执行',C1:'战略判断',C2:'学习纠错',C3:'用人授权',C4:'制度设计',C5:'权力运用与克制'})) {
 assert.equal(api.names(code),name);
 assert.equal(api.names('这里的'+code+'依据。'),'这里的'+name+'依据。');
}
assert.equal(api.names('C5权力运用风格与克制'),'权力运用与克制');
assert.equal(api.names('M1.4反馈'),'失败识别、止损与重组反馈');
assert.equal(api.names('C2-SYNTHETIC-CASE'),'学习纠错情境记录');
for(const s of ['MODEL-C5','C5.md','C2.9','C50','aC5','MAC5','未知CODE'])assert.equal(api.names(s),s);
assert.equal(api.scope('R2_BOUNDED'),'扩大到单一家庭或窄亲属群');
// Public names only act in the profile renderer, never by mutating stored data.
const original={axis:'C5',source:'docs/C5/source.json',prose:'C5具体行为'};
const before=JSON.stringify(original);api.map(original.prose);assert.equal(JSON.stringify(original),before);
const person=fs.readFileSync('reader/person-readability.js','utf8');
const direct=person.match(/const netPublicText = [^;]+;/)[0];
const net=new Function(direct+'return netPublicText;')();
assert.equal(net('C1民生原公开文字'),'C1民生原公开文字');
assert.ok(!person.includes('"C5越接近'));
const template=fs.readFileSync('reader/index.template.html','utf8');
const copy=JSON.parse(fs.readFileSync('reader/public-copy.json','utf8'));
assert.ok(!copy.some(x=>/C5单独|C5越接近/.test(x.to)));
assert.ok(template.includes('权力运用与克制不并入能力图'));
assert.ok(source.includes('.reading-original-record, .note-evidence'),'original quotations stay verbatim');
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
const api=new Function('esc','prose','axisProse','link',source.slice(start,end)+';return {contextIntensity,contexts};')(
 escape,x=>'<p>'+escape(x)+'</p>',x=>'<p>'+escape(x)+'</p>',()=>'<a>合同</a>');
for(const [code,label] of Object.entries({MI1:'单一情境',MI1_CASE:'单一情境',MI2:'完整生命周期情境',MI2_LIFECYCLE:'完整生命周期情境',MI3:'持续系统性情境',MI3_SUSTAINED_SYSTEMIC:'持续系统性情境',MI4:'跨阶段系统性情境',MI4_CROSS_PHASE_SYSTEMIC:'跨阶段系统性情境'})){
 assert.equal(api.contextIntensity({intensity:code}),label);
 assert.equal(api.contextIntensity({material_intensity:code}),label);
 assert.equal(api.contextIntensity({intensity:code,material_intensity:code}),label);
}
assert.equal(api.contextIntensity({basis:'跨阶段多年反复，有MI4字样。',axis_grade:'G5'}),'未列');
assert.equal(api.contextIntensity({intensity:null}),'未列');
assert.equal(api.contextIntensity({intensity:'FUTURE_CODE'}),'未设中文展示，请查原始记录');
assert.equal(api.contextIntensity({intensity:'MI1_CASE',material_intensity:'MI4_CROSS_PHASE_SYSTEMIC'}),'上游字段不一致，请查原始记录');
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


def test_generated_reader_runtime_is_self_contained_after_build():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    index = (root / "reader/index.html").read_text(encoding="utf-8")
    military = (root / "reader/military.html").read_text(encoding="utf-8")
    for filename in (
        "second-item-public-alias.js",
        "second-item-a-public.js",
        "second-item-b1-public.js",
        "second-item-public-labels.js",
        "person-reading-notes.js",
    ):
        assert f'src="{filename}"' not in index
    assert 'src="military-archive.js"' not in military


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


def test_new_viewer_layers_and_compact_c5_hint():
    from pathlib import Path
    import json
    root = Path(__file__).resolve().parents[1]
    template = (root / "reader/index.template.html").read_text(encoding="utf-8")
    person_js = (root / "reader/person-readability.js").read_text(encoding="utf-8")
    copy = json.loads((root / "reader/public-copy.json").read_text(encoding="utf-8"))
    assert "30秒读懂" in template
    assert "三者可以不一致" in template
    assert "axis-further-check" in template
    assert "进一步核对：代表情境、反例与限制" in template
    assert any("原始记录与专业信息" in item["to"] for item in copy)
    assert "S端表示更能约束自身权力" in person_js
    assert "这项评价描述权力使用方式，不属于能力评价" not in person_js


def test_second_item_material_card_phase_two_scope():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "adjudication-material-card" in alias
    assert "持续／系统" in alias
    assert 'label === "B2反馈与约束"' in alias
    assert "renderFinanceMaterialGroups(label, evidence)" in alias
    for label in ("C1民生", "C2经济财政", "C3社会安全", "C4恢复与成本"):
        assert label in alias
    assert '"主要状态"' in alias
    assert '"低谷"' in alias
    assert '"恢复"' in alias
    assert '"责任范围"' in alias
    assert '"状态恶化"' in alias
    assert '"额外代价"' in alias
    assert "renderHandoffMaterialGroups(label, evidence)" in alias
    assert "D1继任行政连续性" in alias
    assert "D3政权交接稳定" in alias

def test_generated_net_judgments_have_complete_public_reading_fields_across_pool():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    groups = ("method", "finance", "handoff", "strategic", "military", "civilization")
    third_fourth = {"strategic", "military", "civilization"}
    seen = 0

    for path in sorted((root / "reader/data/people").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8")).get("record") or {}
        details = ((record.get("net") or {}).get("component_details") or {})
        for group in groups:
            for item in details.get(group) or []:
                if item.get("reader_kind") != "judgment":
                    continue
                seen += 1
                prefix = f"{path.name}:{record.get('ruler_name')}:{group}:{item.get('label')}"
                assert str(item.get("reader_summary") or "").strip(), prefix + ": missing reader_summary"
                assert str(item.get("reader_boundary") or "").strip(), prefix + ": missing reader_boundary"
                evidence = item.get("reader_public_evidence_items")
                assert isinstance(evidence, list) and evidence, prefix + ": missing public evidence"
                for index, entry in enumerate(evidence):
                    assert isinstance(entry, dict), prefix + f": evidence[{index}] is not an object"
                    for field in ("public_label", "public_basis"):
                        assert str(entry.get(field) or "").strip(), prefix + f": evidence[{index}] missing {field}"
                    if group in third_fourth:
                        assert str(entry.get("public_boundary") or "").strip(), prefix + f": evidence[{index}] missing public_boundary"
                if group in third_fourth:
                    assert str(item.get("public_component_label") or "").strip(), prefix + ": missing public_component_label"
                    assert str(item.get("public_level_label") or "").strip(), prefix + ": missing public_level_label"

    assert seen > 0


def test_b1_public_projection_has_a_separate_cli_from_formal_recalculation():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/emperor_v4/eval.py").read_text(encoding="utf-8")
    settlement = (root / "src/emperor_v4/evaluation/second_item_b1_settlement.py").read_text(encoding="utf-8")
    assert 'commands.add_parser("second-item-b1-public")' in source
    assert 'refresh_b1_public_projection_file' in source
    assert 'def refresh_b1_public_projection_file' in settlement
    assert 'def refresh_b1_payload' in settlement


def test_b1_public_projection_refresh_preserves_formal_scoring_signature():
    import copy
    from pathlib import Path
    from emperor_v4.evaluation.formal_json_store import load_json
    from emperor_v4.evaluation.second_item_b1_settlement import (
        B1_PATH,
        B1_PUBLIC_BOUNDARY,
        _scoring_signature,
        refresh_b1_public_projection,
        validate_public_profile_contract,
    )

    root = Path(__file__).resolve().parents[1]
    payload = load_json(root / B1_PATH)
    before = _scoring_signature(payload)
    projected = refresh_b1_public_projection(copy.deepcopy(payload))

    assert _scoring_signature(projected) == before
    validate_public_profile_contract(projected)
    assert projected["records"]
    for row in projected["records"]:
        assert row["public_boundary"] == B1_PUBLIC_BOUNDARY
        assert isinstance(row["public_evidence_items"], list) and row["public_evidence_items"]


def test_a_public_evidence_does_not_repeat_scope_or_reception_already_in_basis():
    import copy
    from pathlib import Path
    from emperor_v4.evaluation.formal_json_store import load_json
    from emperor_v4.evaluation.second_item_a_public import A_PATH, _refresh_payload

    root = Path(__file__).resolve().parents[1]
    projected = _refresh_payload(copy.deepcopy(load_json(root / A_PATH)), root)
    checked = 0
    for row in projected["records"]:
        nodes = row.get("public_institution_nodes") or []
        evidence = row.get("public_evidence_items") or []
        if not nodes:
            continue
        assert len(nodes) == len(evidence)
        for node, item in zip(nodes, evidence):
            basis = str(node.get("public_adjudication_basis") or "")
            scope = str(node.get("public_scope") or "")
            reception = str(node.get("public_reception") or "")
            rendered = str(item.get("public_basis") or "")
            if scope and scope in basis:
                assert f"\n\n{scope}" not in rendered
                checked += 1
            if reception and reception in basis:
                assert f"\n\n{reception}" not in rendered
                checked += 1
    assert checked > 0


def test_a_public_projection_supplies_row_evidence_even_without_institution_nodes():
    import copy
    from pathlib import Path
    from emperor_v4.evaluation.formal_json_store import load_json
    from emperor_v4.evaluation.second_item_a_public import (
        A_PATH,
        A_PUBLIC_BOUNDARY,
        _refresh_payload,
        verify_public_projection,
    )

    root = Path(__file__).resolve().parents[1]
    payload = load_json(root / A_PATH)
    projected = _refresh_payload(copy.deepcopy(payload), root)
    verify_public_projection(root, projected)

    empty_rows = [row for row in projected["records"] if not row.get("public_institution_nodes")]
    assert empty_rows
    for row in empty_rows:
        assert row["public_boundary"] == A_PUBLIC_BOUNDARY
        evidence = row["public_evidence_items"]
        assert len(evidence) == 1
        assert evidence[0]["public_label"] == "当前没有可单列制度节点"
        assert evidence[0]["public_boundary"] == A_PUBLIC_BOUNDARY


def test_method_reader_consumes_row_level_formal_evidence_for_a_and_b1():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    build = (root / "reader/build.py").read_text(encoding="utf-8")
    start = build.index("def _attach_method_public_reader")
    end = build.index("\ndef ", start + 4)
    block = build[start:end]
    assert block.count('evidence = record.get("public_evidence_items")') == 2
    assert "public_institution_nodes" not in block
    assert "M_positive_profile" not in block
    assert "M_mixed_profile" not in block
    assert "M_negative_profile" not in block


def test_b1_reader_consumes_formal_public_projection_instead_of_rebuilding_profiles():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    settlement = (root / "src/emperor_v4/evaluation/second_item_b1_settlement.py").read_text(encoding="utf-8")
    build = (root / "reader/build.py").read_text(encoding="utf-8")

    assert "B1_PUBLIC_BOUNDARY" in settlement
    assert 'row["public_boundary"] = B1_PUBLIC_BOUNDARY' in settlement
    assert 'row["public_evidence_items"] = _public_evidence_items(row)' in settlement
    assert 'evidence = record.get("public_evidence_items")' in build
    assert 'declared_boundary = record.get("public_boundary")' in build


def test_third_fourth_detail_material_cards_use_formal_public_fields_only():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'const MATERIAL_CARD_GROUPS = new Set(["strategic", "military", "civilization"]);' in source
    start = source.index("function metricMaterialCards(item, groupKey)")
    end = source.index("function metricDetail(item, record, groupKey", start)
    block = source[start:end]
    for field in (
        "reader_public_evidence_items",
        "public_label",
        "public_role",
        "public_direction",
        "public_tags",
        "public_basis",
        "public_boundary",
    ):
        assert field in block
    for forbidden in (
        "reader_summary",
        "reader_full_basis",
        "grade_basis",
        "position_basis",
        "material_strength",
        "strengthFrom",
    ):
        assert forbidden not in block
    assert "metricDetail(item, record, key)" in source
    assert '正式层级：' in source

def test_profile_material_strength_is_public_first_and_raw_code_is_audit_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    template = (root / "reader/index.template.html").read_text(encoding="utf-8")
    css = (root / "reader/readability.css").read_text(encoding="utf-8")
    assert "formal-context-chip" in template
    assert "材料强度原始字段" in template
    metadata_start = template.index("function formalContextMetadata")
    story_start = template.index("function formalContextStory", metadata_start)
    metadata_block = template[metadata_start:story_start]
    assert "formal-context-raw" not in metadata_block
    assert "正式字段：" not in metadata_block
    assert ".formal-context-story" in css
    assert ".formal-context-chip.context-intensity" in css

def test_second_item_detail_renderer_keeps_public_takeover_hook():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'const SECOND_PUBLIC_GROUPS = new Set(["method", "finance", "handoff"]);' in source
    assert 'data-second-source-label="' in source
    assert 'SECOND_PUBLIC_GROUPS.has(groupKey)' in source
    # A/B1 and the shared B2/C/D public renderers all locate detail nodes through this hook.
    for label in ("A制度建设", "B1官僚治理", "B2反馈与约束"):
        assert label in source
def test_first_item_public_layer_hides_axis_codes_outside_formula_folds():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader/person-readability.js").read_text(encoding="utf-8")

    for source in (home, person):
        assert "A · 统一主链客观贡献" not in source
        assert "B2 · 创业组织" not in source
        assert "下面再按A、B1、B2、C" not in source
        assert "第一项原始净分 S1" not in source

    assert '"统一成果", "先看本人真正留下了什么"' in home
    assert '"创业组织与政治整合", "多线并行、专业分工与异质整合"' in home
    assert "统一成果 ${score[0]} + 创业难度与效率 ${score[1]} + 创业组织 ${score[2]} + 本人统帅 ${score[3]}" in home
    assert "<strong>统一成果</strong>" in person
    assert "<strong>创业组织与政治整合</strong>" in person
    assert "L档怎么换分" not in person
    # Internal formulas remain available inside collapsed calculation details.
    assert "四轴毛分 = A + B1 + B2 + C" in home
    assert "B2 = 并行执行分" in person
def test_first_item_public_grade_translator_uses_letter_grades_and_named_cost_severity():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader/person-readability.js").read_text(encoding="utf-8")

    for source in (home, person):
        assert 'const FIRST_PUBLIC_C_GRADES = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};' in source
        assert '"起点R$1级"' not in source
        assert '"L$1级"' not in source
        assert '第${n}档' not in source
        assert "L0—L5" not in source
        assert "E、D、C、B、A、S 六档" in source

    assert 'const severity = ["无显著代价","很低成本","较低成本","中等成本","较高成本","高成本","极高成本","灾难级成本"];' in home
    assert '["成本程度", publicLevel]' in home


def test_first_item_a_how_block_shows_exact_public_curve():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "项目A池 = 120 × (min(1000, U) / 1000)^0.65" in source
    assert "共同项目再按本人控制信用占项目总信用的比例分配" in source


def test_first_item_cost_body_and_commander_calculation_hide_internal_levels():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "function firstCostPublicText(value)" in source
    assert "很低成本" in source
    assert "极高成本" in source
    assert "灾难级成本" in source
    assert 'firstCostPublicText(data.public_basis)' in source
    assert "当前能力裁决：" in source
    assert 'firstItemPublicText(item.grade || "")' in source


def test_mobile_material_cards_stack_labels_and_scores():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    css = (root / "reader/readability.css").read_text(encoding="utf-8")

    assert "@media(max-width:700px)" in alias
    assert ".adjudication-material-head{display:block}" in alias
    assert ".adjudication-material-meta{justify-content:flex-start;margin-top:6px}" in alias
    assert ".net-metric-detail>summary{grid-template-columns:minmax(0,1fr);gap:5px}" in home
    assert ".net-material-head{display:block}" in home
    assert ".net-material-meta{justify-content:flex-start;margin-top:6px}" in home
    assert "overflow-wrap:anywhere" in alias
    assert "overflow-wrap:anywhere" in home
    assert ".formal-context-chip" in css
    assert "white-space: normal" in css
def test_second_item_material_groups_do_not_render_empty_categories():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "if (!cards.length) return document.createDocumentFragment();" in source
    assert "当前没有该类材料。" not in source


def test_structured_material_pages_avoid_default_summary_and_scope_duplication():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")

    assert 'if (scope || boundary)' in alias
    assert 'details.append(makeTextBlock("summary", "", "范围与边界"))' in alias
    assert 'card.append(box);' not in alias[alias.index('const scope = publicText(data.scope)'):alias.index('const footer = publicText(data.footer)')]
    assert 'const structuredMaterials = MATERIAL_CARD_GROUPS.has(groupKey) && publicEvidence.length > 0;' in home
    assert '总体裁决摘要' in home
    assert 'const logic = structuredMaterials ? "" : summary;' in home
    assert 'class="net-overall-boundary"' in home
    assert '<summary>总体范围与边界</summary>' in home
def test_source_coverage_and_material_strength_are_explained_as_different_scales():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    template = (root / "reader/index.template.html").read_text(encoding="utf-8")
    assert "hasSourceCoverage" in home
    assert "来源覆盖”只表示当前公开证据包的来源是否足够" in home
    assert "不表示材料强度、结果方向或得分高低" in home
    assert "“材料强度”描述情境的持续性、作用范围和机制化程度" in template
    assert "“来源覆盖”描述公开证据包的来源是否足够" in template
    assert "两者不是同一尺度" in template


def test_fourth_item_public_source_coverage_is_rendered_only_when_formally_published():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'const coverage = format(entry?.public_source_coverage || "");' in source
    assert '[role, direction, coverage, ...tags]' in source
    assert "net-material-chip" in source


def test_profile_material_intensity_aliases_compare_by_public_semantics_not_raw_code():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "const publicValues=rawValues.map(value=>materialIntensityNames[value]||value);" in template
    assert "publicValues.some(value=>value!==publicValues[0])" in template
    assert "rawValues.some(v=>v!==rawValues[0])" not in template


def test_profile_material_intensity_short_aliases_have_public_labels():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    for token in (
        "MI1:'单一情境'",
        "MI2:'完整生命周期情境'",
        "MI3:'持续系统性情境'",
        "MI4:'跨阶段系统性情境'",
    ):
        assert token in template


def test_profile_axis_summary_shows_formal_material_coverage_in_public_words():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "const evidenceLevel=readerText(a.axis_evidence_level||'');" in template
    assert 'class="axis-evidence-level">材料覆盖：' in template
    assert "材料覆盖 '+esc(evidenceLevel)" in template
    assert "材料级别 ${esc(a.axis_evidence_level" not in template


def test_reader_guide_preserves_material_strength_display_boundary():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "只有正式记录明确发布相应字段时页面才展示" in template
    assert "没有这类标签只表示上游没有发布，不等于证据弱" in template
    assert "第三、第四项若只发布结果层级和范围边界" in template
    assert "不由页面补判强弱" in template


def test_public_scope_copy_avoids_internal_pool_and_public_band_jargon():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "不在人物画像主池" not in template
    assert "不进入本展示的人物画像主池" not in template
    assert "历史影响池外补充样本" not in template
    assert " · 补充样本" not in template
    assert "公众总档和四个维度" not in template
    assert "<b>公众总档</b>" not in template
    assert "人物画像正式评价范围" in template
    assert "补充历史样本" in template
    assert "历史影响总等级" in template


def test_public_power_context_copy_avoids_internal_evidence_window_jargon():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "不是统一取证边界" not in template
    assert "非统一取证期" not in template
    assert "各项具体范围以各自依据为准" in template
    assert "掌权背景（各项范围另见依据）" in template


def test_net_detail_renderer_uses_public_performance_language_and_current_person_section_title():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'title: "统治绩效构成"' in source
    assert 'title: "第三项 · 军事与边疆"' in source
    assert '["统治绩效构成", "净收益构成"].includes' in source
    assert 'aria-label="统治绩效详情"' in source
    assert "正在加载${esc(summary.ruler_name)}的统治绩效详情" in source
    assert "总榜净收益" not in source
    assert "净收益计分详情加载失败" not in source


def test_compare_net_breakdown_hides_internal_grades_notes_and_calculation_rows():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index("function compareNetValue")
    end = template.index("const impactAuditSource", start)
    block = template[start:end]
    assert "x.reader_kind==='judgment'" in block
    assert "x.grade" not in block
    assert "x.note" not in block
    assert "内部档位码、折算中间项和小计不在对照页展开" in block
    assert "row('分项构成'" in template
    assert "<summary>展开分项</summary>" in template


def test_base_template_uses_current_second_item_public_terms_before_runtime_patching():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "治国净收益" not in template
    assert "财政与民生" not in template
    assert "交接质量" not in template
    assert "治国成效" in template
    assert "民生与社会" in template
    assert "政权交接" in template


def test_edge_states_distinguish_not_applicable_zero_pending_and_signed_adjustment():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    template = (root / "reader/index.template.html").read_text(encoding="utf-8")
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")

    assert "治国成效待正式结算" in template
    assert "不适用；总分按0计入" in template
    assert "本项适用，但未形成正向净收益" in template
    assert "这与“不适用”不同" in template
    assert "compareFirstAddOn" in template
    assert "signedAdjustment" in template
    assert 'groupKey === "civilization"' in home
    assert "本项适用，但没有形成正向净收益" in home
    assert 'major === "fourth" && Number(value) > 0' in home
def test_overview_major_link_matching_tolerates_public_state_notes():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'label.startsWith(publicLabel + " ")' in source
    assert "Object.entries(overviewMajorByLabel)" in source
def test_supplementary_simple_card_does_not_offer_unavailable_profile():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "不在人物画像正式评价范围" in template
    assert "r.supplementary?'<span class=\"muted\">不在人物画像正式评价范围</span>'" in template
def test_compare_edge_helpers_are_self_contained_and_supplementary_profile_has_no_dead_help():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    compare_start = template.index("function compare(){")
    compare_end = template.index("function guide()", compare_start)
    block = template[compare_start:compare_end]
    assert "const missingNetLabel=r=>" in block
    assert "const compareFirstAddOn=r=>" in block
    assert "const signedAdjustment=value=>" in block
    assert "该对象只作为补充历史样本，不进入人物画像正式评价范围。" in template
    assert "r.supplementary?'<p>该对象只作为补充历史样本" in template

def test_handoff_public_layer_uses_letter_grades_not_numeric_level_inputs():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    build = (root / "reader/build.py").read_text(encoding="utf-8")
    reading = (root / "reader/second-item-reading.js").read_text(encoding="utf-8")

    assert 'HANDOFF_PUBLIC_GRADE = {0: "E", 1: "D", 2: "C", 3: "B", 4: "A", 5: "S"}' in build
    assert "正式交班裁决换算为" not in build
    assert "级输入" not in build
    assert "D1 {values.get" not in build
    assert "D3 {values.get" not in build
    assert "公开档位为 {handoff_public_grade" in build
    assert "行政连续性 {handoff_public_grade" in build
    assert "交接稳定 {handoff_public_grade" in build

    assert 'const HANDOFF_PUBLIC_GRADE = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};' in reading
    assert "/ 5 级" not in reading
    assert "/ 5级" not in reading
    assert "等级输入·" not in reading
    assert 'setRowLabel(span,"行政连续性")' in reading
    assert 'setRowLabel(span,"交接稳定")' in reading


def test_public_runtime_formatters_and_non_scoring_axes_behave_as_rendered(tmp_path):
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

const thirdCtx={cleanNetText:v=>String(v??'').replace(/\s+/g,' ').trim()};
vm.createContext(thirdCtx);
vm.runInContext(
  section(home,'  const MATERIAL_CARD_GROUPS','  const SECOND_PUBLIC_GROUPS')
  +'\nthis.thirdPublicText=thirdPublicText;', thirdCtx);
assert.equal(thirdCtx.thirdPublicText('结束时第5级安全水平','A1'),'结束时S档安全水平');
assert.equal(thirdCtx.thirdPublicText('1→5档','A1'),'D档→S档');
assert.equal(
  thirdCtx.thirdPublicText('B1控制规模与B2战略价值按55%/45%合成，再由B4交班成熟度修正','B80'),
  '控制范围与战略价值按55%/45%合成，再由成果稳定性修正'
);
assert.equal(thirdCtx.thirdPublicText('普通军事代价为第5级、中位','普通成本扣分'),'普通军事代价为严重军事成本、中位');

const civCtx={
  cleanNetText:v=>String(v??'').replace(/\s+/g,' ').trim(),
  THIRD_CN_LEVEL:{'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7},
  esc:String
};
vm.createContext(civCtx);
vm.runInContext(
  section(home,'  const CIV_PUBLIC_DIRECTION','  function civilizationPublicStatus')
  +'\nthis.civilizationPublicText=civilizationPublicText;', civCtx);
assert.equal(civCtx.civilizationPublicText('正向变化第3级'),'正向变化达到主要领域的稳定改变');
assert.equal(civCtx.civilizationPublicText('负向变化第4级'),'负向变化达到系统性破坏');
assert.equal(civCtx.civilizationPublicText('净文明影响幅度第1级'),'净影响为局部、短期或低强度变化');
assert.equal(civCtx.civilizationPublicText('第三级影响幅度'),'主要领域的稳定改变');

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


def test_third_item_public_layer_translates_numeric_grades_without_reversing_cost_meaning():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'const THIRD_PUBLIC_GRADE = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};' in source
    assert '5:"严重军事成本"' in source
    assert '6:"极端军事成本"' in source
    assert '7:"灾难性军事耗竭"' in source
    assert 'function thirdPublicText(value, itemLabel = "")' in source
    assert "三方面均为" in source
    assert "客观状态变化按已裁本人责任计入" in source
    assert 'groupKey === "strategic" || groupKey === "military"' in source
    assert "thirdPublicText(item.reader_how" in source

def test_score_explanations_live_inside_subitems_not_repeated_in_top_bridge():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    a = (root / "reader/second-item-a-public.js").read_text(encoding="utf-8")
    b1 = (root / "reader/second-item-b1-public.js").read_text(encoding="utf-8")

    assert "net-score-bridge" not in home
    assert "majorScoreBridge" not in home
    assert "function scoreHowDetails(item, groupKey, how, formalLevel, record)" in home
    assert "当前裁决" in home
    assert "换算规则" in home
    assert "当前结果" in home
    assert "FINANCE_BASE_SCORES" in alias
    assert "FINANCE_LOSS_RATE" in alias
    assert "SecondItemScoreHowDetails" in alias
    assert 'SecondItemScoreHowDetails?.(item, "A制度建设")' in a
    assert 'SecondItemScoreHowDetails?.(item, "B1官僚治理")' in b1


def test_second_item_subitem_how_blocks_include_actual_group_formula():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "function secondMethodExpandedHow(label)" in source
    assert "制度建设与官僚治理不各自直接加分" in source
    assert "0.8 × [较高表现指数" in source
    assert "反馈与约束单独占45分" in source
    assert "function secondHandoffExpandedHow()" in source
    assert "其中0—5只作为 E—S 档在合成公式中的权重" in source
    assert "并不是另一套数字档位" in source
    assert 'handoff.get("交接得分")' in source


def test_calculation_blocks_keep_only_public_subtotals_not_repeated_intermediate_steps():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert 'method:new Set(["治理手段"])' in home
    assert 'finance:new Set(["治理结果"])' in home
    assert 'handoff:new Set(["交接得分"])' in home
    assert 'strategic:new Set(["A120","B80"])' in home
    assert 'military:new Set(["第三项合计"])' in home
    assert 'civilization:new Set(["第四项调整"])' in home
    assert "<summary>本组小计怎么形成？</summary>" in home
    assert 'method:new Set(["治理手段"])' in alias
    assert 'finance:new Set(["治理结果"])' in alias
    assert 'handoff:new Set(["交接得分"])' in alias


def test_generic_net_group_keeps_non_scoring_military_judgment_axes_visible():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    start = source.index("function genericNetGroup")
    end = source.index("function firstItemRawUrl", start)
    block = source[start:end]
    assert 'item.unit === "不单独计分"' in block
    assert "item.public_level_label" in block
    assert 'item.value != null || item.unit === "不单独计分" || item.public_level_label' in block


def test_third_item_non_scoring_military_axes_remain_visible_and_explain_composite():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'item.unit === "不单独计分"' in source
    assert 'detailedHowText(item, groupKey, how, record)' in source
    assert 'groupItems.get("C50")' in source
    assert "当前三方面：" in source
    assert "军事体系结果为" in source
    assert "当前三项得分率为控制范围" in source
    assert "两个战略安全轴最后直接相加" in source


def test_first_item_cost_explains_current_fixed_debit_lookup():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader/person-readability.js").read_text(encoding="utf-8")
    for source in (home, person):
        assert "const FIRST_COST_DEBIT" in source
        assert "5:{LOW:18,MID:22.5,HIGH:27}" in source
        assert "7:{LOW:60,MID:68,HIGH:76,HIGHEST:80}" in source
        assert "function firstCostExactHow(item)" in source
        assert "固定扣分表直接对应" in source
        assert "所以本项扣" in source


def test_first_item_b1_explains_start_opponent_and_efficiency_subscores():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader/person-readability.js").read_text(encoding="utf-8")
    for source in (home, person):
        assert "function firstB1ScoreText(item)" in source
        assert "B1满分50 = 起点难度15 + 对手难度15 + 完成效率20" in source
        assert "资源越弱，创业难度分越高" in source
        assert "E档15、D档13、C档11、B档8、A档5、S档2、S+档0" in source
        assert "最强全值，第二强取50%" in source
        assert "期望完成年 = 4 + 8 × √(本阶段有效控制信用 / 1000)" in source
        assert "速度比≤0.75、1.00、1.25、1.50、2.00、2.50、3.00、4.00" in source



def test_major_cards_explain_third_and_fourth_item_scales():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "250分制净分" in source
    assert "再扣实际军事代价" in source
    assert "有符号调整，三轴合计范围为 -67.5～+67.5" in source
    assert "本项进入总榜的净分：" in source
    assert "本项进入总榜的有符号调整：" in source
    assert "理论范围 -67.5～+67.5" in source

def test_person_page_builds_compact_net_summary_without_transient_full_detail_tree():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'if (!section) return;' in source
    assert 'if (!reading) {' in source
    assert 'reading = document.createElement("div");' in source
    assert 'reading.className = "net-reading";' in source
    assert 'section.dataset.netReadable = "done";' in source
    assert "independent #net page" in source



def test_first_item_overview_keeps_outcome_boundary_in_detail_only():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    start = source.index("function firstItemOverview")
    end = source.index("async function renderFirstMajor", start)
    block = source[start:end]
    assert "起点背景：" in block
    assert "实际成果：" in block
    assert "a.public_scope" in block
    assert "a.public_boundary" not in block

def test_first_item_overview_cost_is_compact_and_does_not_repeat_full_basis():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    start = source.index("function firstItemOverview")
    end = source.index("async function renderFirstMajor", start)
    block = source[start:end]
    assert 'const costData = cost?.reader_public_cost || {};' in block
    assert 'firstCostPublicText(costData.public_level_label || "")' in block
    assert "costData.public_status_label" in block
    assert "costData.public_responsibility_window" in block
    assert "costData.public_basis" not in block


def test_fourth_item_material_cards_split_long_basis_after_public_translation():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "function civilizationBasisMarkup(value)" in source
    assert "civilizationPublicText(value)" in source
    assert "fourthItem" in source
    assert "civilizationBasisMarkup(entry?.public_basis || \"\")" in source
    assert "裁决说明" in source


def test_first_item_commander_grade_has_public_fixed_score_table():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader/person-readability.js").read_text(encoding="utf-8")
    for source in (home, person):
        assert "function firstCommanderScoreText(item)" in source
        assert "D档（基础统帅）低/中/高位=4/7/10分" in source
        assert "C档（重要统帅）=12/15/18分" in source
        assert "B档（优秀统帅）=20/23/26分" in source
        assert "A档（顶级统帅）=28/31/34分" in source
        assert "S档（历史级统帅）=36/38/40分" in source
        assert "对应${item.value}分" in source


def test_second_item_calculation_rows_use_public_labels_and_readable_summary():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert '"AB计分块":"制度建设与官僚治理合成"' in source
    assert '"B2折算":"反馈与约束折算"' in source
    assert '"治理手段":"制度与行政合计"' in source
    assert '"治理结果":"民生与社会合计"' in source
    assert '"低侧封顶":"交接短板上限"' in source
    assert '"第二项合计":"治国成效合计"' in source
    assert "function patchCalculationRows(root, record)" in source
    assert 'summary.textContent = "本组小计怎么形成？"' in source
    assert "publicCalculationText(item.reader_how" in source
    assert "patchCalculationRows(root, net);" in source



def test_legacy_second_item_renderer_uses_same_public_grade_language():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/second-item-reading.js").read_text(encoding="utf-8")
    assert 'const METHOD_BAND_LABELS = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};' in source
    assert "最低档" not in source
    assert "最高档" not in source
    assert "主要状态第" not in source
    assert "低谷修正${low}级" not in source
    assert "原始表现指数" in source
    assert "合成输入，不单独加分" in source
    assert '"A制度建设":"制度建设"' in source
    assert '"C1民生":"民生"' in source
    assert 'setNodeText(value,`${methodBand(item)}档`)' in source
    assert ',"恢复与额外成本");' in source


def test_second_item_reader_does_not_recompute_current_pool_rank():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    reading = (root / "reader/second-item-reading.js").read_text(encoding="utf-8")
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    for source in (reading, alias):
        assert "currentSecondPool" not in source
        assert "secondPoolPosition" not in source
        assert "secondRankText" not in source
        assert "rankText(" not in source
        assert "当前公开名次" not in source
        assert "排名与数据口径" not in source
        assert "约前 " not in source
    assert "制度与行政 + 民生与社会 + 政权交接" in reading


def test_second_item_method_index_is_explicitly_an_input_not_a_direct_score():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "原始方向指数" not in source
    assert "原始表现指数" in source
    assert "合成输入，不单独加分" in source
    assert "作为制度与行政合成输入，不单独加分" in source
    assert "较高表现指数" in source
    assert "当前表现指数" in source


def test_third_item_public_aliases_replace_compound_internal_labels_before_bare_codes():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'replace(/\\bB1控制规模/g, "控制范围")' in source
    assert 'replace(/\\bB2战略价值/g, "战略价值")' in source
    assert 'replace(/\\bB4交班成熟度/g, "成果稳定性")' in source
    assert source.index('replace(/\\bB1控制规模/g') < source.index('replace(/\\bB1\\b/g')
    assert source.index('replace(/\\bB2战略价值/g') < source.index('replace(/\\bB2\\b/g')
    assert source.index('replace(/\\bB4交班成熟度/g') < source.index('replace(/\\bB4\\b/g')


def test_third_item_strategic_axis_explains_formula_without_reverse_deriving_formal_intermediate():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "function strategicAxisExactHow(item, groupItems)" in source
    assert "“轨迹值”只是计分中间值，不是另一项评价" in source
    assert "轨迹值 = 10 × 结束档位数值 + 14 × 本人可归责档差 + 专项信用 − 负向调整" in source
    assert "E=0、D=1、C=2、B=3、A=4、S=5" in source
    assert "0—5只是在公式中的档位权重" in source
    assert "公开裁决仍使用 E—S" in source
    assert "当前人物正式结算记录" in source
    assert "不由阅读层反推中间值" in source
    assert "正式轨迹值为" not in source
    assert "score / 0.6" not in source


def test_fourth_item_public_layer_uses_semantic_magnitude_labels_instead_of_numbered_levels():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert '1:"局部、短期或低强度变化"' in source
    assert '2:"清晰但有限的变化"' in source
    assert '3:"主要领域的稳定改变"' in source
    assert '4:"跨场景或系统性改变"' in source
    assert "function civilizationPublicText(value)" in source
    assert "正向变化达到" in source
    assert "负向变化达到" in source
    assert "净影响为" in source
    assert "正负相抵 · 净调整为0" in source
    assert "正向与负向材料在本轴净算后相抵，因此本轴调整为0分" in source
    assert 'fourthItem ? civilizationPublicText(value)' in source
    assert '第${magnitude[1]}级影响' not in source


def test_first_item_summary_does_not_repeat_the_same_scoreline_after_detail_cards():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    first_totals = source[source.index("function firstTotals(items)"):source.index("function firstItemOverview", source.index("function firstTotals(items)"))]
    assert "查看第一项完整折算公式" in first_totals
    assert "first-item-scoreline" not in first_totals
    assert "军事代价扣减 =" in first_totals


def test_first_item_not_applicable_uses_formal_status_instead_of_reader_inference():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader/person-readability.js").read_text(encoding="utf-8")
    for source in (home, person):
        assert 'record.net?.first_item_status === "NOT_APPLICABLE"' in source
        assert "items.every(item =>" not in source


def test_material_cards_show_optional_formal_source_coverage_without_reader_inference():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'const coverage = format(entry?.public_source_coverage || "");' in source
    assert '[role, direction, coverage, ...tags]' in source
    assert "entry?.source_coverage" not in source


def test_fourth_item_zero_total_explains_cross_axis_cancellation():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "function fourthAdjustmentNote(record)" in source
    assert "hasPositive && hasNegative" in source
    assert "存在正向与负向分轴，合计后相抵" in source
    assert "0不代表各轴都没有变化" in source


def test_third_item_long_public_basis_is_losslessly_split_for_readability():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'function thirdBasisParts(value, itemLabel = "")' in source
    assert 'function thirdBasisMarkup(value, itemLabel = "")' in source
    assert "net-third-basis-list" in source
    assert "裁决说明" in source
    assert "match(/[^。！？；]+[。！？；]?/g)" in source
    assert "三方面分别定档但不单独加分" in source
    assert "固定成本系数" in source
    assert "CIV_PUBLIC_POINTS" in source



def test_reader_guide_explains_material_strength_badges_are_upstream_only():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "只有正式记录明确发布相应字段时页面才展示" in template
    assert "没有这类标签只表示上游没有发布，不等于证据弱" in template
    assert "不由页面补判强弱" in template


def test_second_item_compare_enhancers_accept_public_breakdown_row_title():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    reading = (root / "reader/second-item-reading.js").read_text(encoding="utf-8")
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert '["分项构成","构成与依据"].includes' in reading
    assert '["分项构成", "构成与依据"].includes' in alias
