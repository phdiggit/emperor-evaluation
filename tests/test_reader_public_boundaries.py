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
const render=new Function('esc','firstPublicSharePercent','firstPublicOutcomeParts','firstPublicOutcomeText','firstFactText','personLabel',overview+'return firstItemOverview;')(esc,()=>'',a=>[['成果',a.public_outcome_basis]],String,String,personLabel);
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
assert.ok(screen.innerHTML.includes('不是统一取证边界'));
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
for(const [code,label] of Object.entries({MI1_CASE:'单一情境',MI2_LIFECYCLE:'完整生命周期情境',MI3_SUSTAINED_SYSTEMIC:'持续系统性情境',MI4_CROSS_PHASE_SYSTEMIC:'跨阶段系统性情境'})){
 assert.equal(api.contextIntensity({intensity:code}),label);
 assert.equal(api.contextIntensity({material_intensity:code}),label);
 assert.equal(api.contextIntensity({intensity:code,material_intensity:code}),label);
}
assert.equal(api.contextIntensity({basis:'跨阶段多年反复，有MI4字样。',axis_grade:'G5'}),'未列');
assert.equal(api.contextIntensity({intensity:null}),'未列');
assert.equal(api.contextIntensity({intensity:'MI4'}),'未设中文展示，请查原始记录');
assert.equal(api.contextIntensity({intensity:'MI1_CASE',material_intensity:'MI4_CROSS_PHASE_SYSTEMIC'}),'上游字段不一致，请查原始记录');
const record={counterpattern:{negative_parent_refs:['P']},context_lookup:{P:{intensity:'MI2_LIFECYCLE',basis:'完整正式说明，包括反证和限制。'}}};
const before=JSON.stringify(record),html=api.contexts(record,true);
assert.ok(html.includes('context-intensity'));
assert.ok(html.includes('完整生命周期情境'));
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


def test_second_item_material_card_phase_one_scope():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "adjudication-material-card" in alias
    assert "持续／系统" in alias
    # Phase one deliberately leaves C1-C4 on the existing generic renderer.
    assert 'label === "B2反馈与约束"' in alias
    for label in ("C1民生", "C2经济财政", "C3社会安全", "C4恢复与成本"):
        assert f'label === "{label}"' not in alias
