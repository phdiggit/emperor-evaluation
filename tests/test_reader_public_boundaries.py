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
const cleanStart=home.indexOf('  function cleanNetText(value)');
const cleanEnd=home.indexOf('\n\n  function uniqueSourceRefs',cleanStart);
assert.ok(cleanStart>=0&&cleanEnd>cleanStart);
const publicText=new Function(home.slice(cleanStart,cleanEnd)+';return cleanNetText;')();
assert.ok(!person.includes('const netPublicText ='),'legacy person net renderer must stay retired');
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
 const audit=dedicated.slice(dedicated.indexOf('function appendDedicatedAudit'),dedicated.indexOf('function ensureStyles'));
 assert.ok(audit.includes('"正式记录来源"'));
 assert.ok(!audit.includes('reader_how'));
 assert.ok(dedicated.includes('SecondItemMaterialCards'));
}
const alias=fs.readFileSync('reader/second-item-public-alias.js','utf8');
assert.ok(!alias.includes('patchInstitutionDetail'));
assert.ok(alias.includes('renderB2MaterialGroups(evidence, item.reader_boundary)'));

const overview=home.slice(home.indexOf('  function firstItemOverview'),home.indexOf('  async function renderFirstMajor'));
const long='已有成果。'.repeat(100)+'末尾仍有不能归给本人的部分。';
const template=fs.readFileSync('reader/index.template.html','utf8');
const identitySource=template.slice(template.indexOf('function personLabel('),template.indexOf('const powerContextNote='));
const personLabel=new Function(identitySource+'return personLabel;')();
const firstTextStart=home.indexOf('function firstPublicText(value)');
const firstTextEnd=home.indexOf('\n\nfunction firstB1Markup',firstTextStart);
const firstPublicText=new Function(home.slice(firstTextStart,firstTextEnd)+';return firstPublicText;')();
const costStart=home.indexOf('function firstCostPublicText');
const costEnd=home.indexOf('\n\nfunction firstCostMarkup',costStart);
const firstCostPublicText=new Function('firstPublicText',home.slice(costStart,costEnd)+';return firstCostPublicText;')(firstPublicText);
const render=new Function('esc','firstPublicSharePercent','firstPublicOutcomeParts','firstPublicOutcomeText','firstFactText','personLabel','firstCostPublicText','firstPublicText',overview+'return firstItemOverview;')(esc,()=>'',a=>[['成果',a.public_outcome_basis]],String,String,personLabel,firstCostPublicText,firstPublicText);
const html=render({ruler_name:'合成对象'}, {'B2组织与整合':{'并行执行':long}}, {'A统一贡献':{reader_public_outcome:{public_outcome_basis:long}}});
assert.equal(html.split(long).length-1,2);
// Exercise current public data, without storing any adjudication snapshot.
for(const path of fs.readdirSync('reader/data/people')) {
 const record=JSON.parse(fs.readFileSync('reader/data/people/'+path,'utf8')).record;
 for(const items of Object.values(record.net?.component_details||{})) {
  for(const item of items)for(const key of ['reader_summary','reader_boundary']) {
   if(item[key])assert.equal(publicText(item[key]),String(item[key]).replace(/\s+/g,' ').trim());
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
 esc:String,number:v=>String(v??'—'),scoreNumber:v=>String(v??'—'),conf:String,dimNames:{extent:'范围'},gradeHelp:()=>'',evidenceAssessment:()=>'',
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
const context={DATA:{records,impact_grades:['B'],main_count:2,ranked_count:0,supplementary_count:1,capability_axes:[],independent_axes:[],axis_specs:{}},state,screen,byId:new Map(records.map(r=>[r.ruler_id,r])),document:{getElementById:id=>nodes[id]},nav(){},number:String,scoreNumber:String,conf:String};
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
vm.runInContext(section('const esc=','const number=')+section('const letters=','const groupNames=')+section('function impactPanel(','function axisEvidence(')+section('function profilePanel(r)','function compare(){'),context);
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
assert.equal(
 api.map('本轮MI2_LIFECYCLE材料未过G5硬门，最新重裁后仍保留MI4_CROSS_PHASE_SYSTEMIC正链；整改前显示已撤回。'),
 '当前公开材料范围内完整生命周期情境材料未过G5定档条件，重新核对后仍保留跨阶段系统性情境正链；此前显示已撤回。'
);
assert.equal(
 api.map('洛阳—虎牢S+/D4与河东反攻S-/D4构成极高压力直接统帅高峰。'),
 '洛阳—虎牢S+成果／高压任务与河东反攻S-成果／高压任务构成极高压力直接统帅高峰。'
);
assert.equal(
 api.map('最新B1显示行政正链；重新反向检索后发现硬负例，三条重要下沿需要同时消费，极强军事链仍保留。'),
 '现行官僚治理材料显示行政正向证据链；补充反例核对后发现明确强反例，三条重要下限证据需要同时计入，极强军事证据链仍保留。'
);
// Public names only act in the profile renderer, never by mutating stored data.
const original={axis:'C5',source:'docs/C5/source.json',prose:'C5具体行为'};
const before=JSON.stringify(original);api.map(original.prose);assert.equal(JSON.stringify(original),before);
const home=fs.readFileSync('reader/home-interactions.js','utf8');
const person=fs.readFileSync('reader/person-readability.js','utf8');
const cleanStart=home.indexOf('  function cleanNetText(value)');
const cleanEnd=home.indexOf('\n\n  function uniqueSourceRefs',cleanStart);
assert.ok(cleanStart>=0&&cleanEnd>cleanStart);
const net=new Function(home.slice(cleanStart,cleanEnd)+';return cleanNetText;')();
assert.equal(net('C1民生原公开文字'),'C1民生原公开文字');
assert.ok(!person.includes('const netPublicText ='));
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


def test_generated_reader_runtime_is_self_contained_after_build():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    index = (root / "reader/index.html").read_text(encoding="utf-8")
    military = (root / "reader/military.html").read_text(encoding="utf-8")
    for filename in (
        "second-item-reading.js",
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


def test_reader_global_enum_fallbacks_hide_unknown_raw_codes():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "const conf=v=>({HIGH:'高',MEDIUM:'中',LOW:'低'}[v]||'未列');" in template
    assert "const pos=v=>({HIGH:'高位',MID:'中位',LOW:'低位'}[v]||'');" in template
    assert "const mode=v=>({FULL_GRADE:'完整定档',BOUNDED_PROFILE:'有界画像',MATERIAL_DENSITY_LIMITED:'材料密度受限',NOT_APPLICABLE:'不适用',EPISODE_TAG:'仅有局部情境证据',NO_GRADE:'证据不足，无档结案'}[v]||'未列');" in template
    assert "||v||'未声明'" not in template
    assert "未声明" not in template


def test_new_viewer_layers_and_compact_c5_hint():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    template = (root / "reader/index.template.html").read_text(encoding="utf-8")
    person_js = (root / "reader/person-readability.js").read_text(encoding="utf-8")
    assert "30秒读懂" in template
    assert "三者可以不一致" in template
    assert "axis-further-check" in template
    assert "进一步核对：代表情境、反例与限制" in template
    assert "原始记录与专业信息" in template
    assert "S端表示更能约束自身权力" in person_js
    assert "这项评价描述权力使用方式，不属于能力评价" not in person_js


def test_second_item_material_card_phase_two_scope():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "adjudication-material-card" in alias
    assert "materialStrengthFromTags" not in alias
    assert "MATERIAL_STRENGTH_TAGS" not in alias
    assert 'data.tags.map(tag => [tag, "tag"])' in alias
    assert 'label === "B2反馈与约束"' in alias
    assert "renderFinanceMaterialGroups(label, evidence, item.reader_boundary)" in alias
    for label in ("C1民生", "C2经济财政", "C3社会安全", "C4恢复与成本"):
        assert label in alias
    assert '"主要状态"' in alias
    assert '"低谷"' in alias
    assert '"恢复"' in alias
    assert '"责任范围"' in alias
    assert '"状态恶化"' in alias
    assert '"额外代价"' in alias
    assert "renderHandoffMaterialGroups(label, evidence, item.reader_boundary)" in alias
    assert "D1继任行政连续性" in alias
    assert "D3政权交接稳定" in alias


def test_third_item_public_formatter_cleans_current_people_pool(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "third-item-pool-leaks.cjs"
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const home=fs.readFileSync('reader/home-interactions.js','utf8');
function section(source,start,end){
  const a=source.indexOf(start),b=source.indexOf(end,a);
  assert.ok(a>=0&&b>a,start);
  return source.slice(a,b);
}
const ctx={cleanNetText:v=>String(v??'').replace(/\s+/g,' ').trim()};
vm.createContext(ctx);
vm.runInContext(
  section(home,'  const MATERIAL_CARD_GROUPS','  const SECOND_PUBLIC_GROUPS')
  +'\nthis.thirdItemPublicText=thirdItemPublicText;',ctx
);

const forbidden=[
  /父周期/,
  /父任务只作证据下钻/,
  /正式横校/,
  /旧账/,
  /本次重做/,
  /用户冻结/,
  /得分率/,
  /机械落/,
  /回灌/,
  /底账/,
  /补门/,
  /核心门/,
  /本包事实/,
  /控制包/,
  /现行贡献类型/,
  /战略链化/,
  /采用比例/,
  /实际控制范围率/,
  /1:1链化/,
  /\d+票(?:降至|升至)\d+票/,
  /第三项本体/,
  /第三项现期/,
  /第三项只读/,
  /第三项独立(?:计入|方向)/,
  /三轴/,
  /独立战果票/,
  /军事体系整体[SABCDE]档=\d/,
  /倒灌/,
  /旧\d+(?:\.\d+)?→\d/,
  /此前(?:接手时|结束时)控制存量[^。；]*→/,
  /(?:严重军事成本|极端军事成本|灾难性军事耗竭)(?:高位|中位|低位|极端上沿)?军事成本/,
  /重复计票/,
  /旧标识规范化/,
  /旧实际控制范围/,
  /同一口径后为[^。；]*→/,
  /规范后[^。；]*→/,
  /准入/,
  /硬门/,
  /机械/,
  /路由/,
  /切片/,
  /闭环/,
  /旧版|上一版/,
  /(?:拆票|计票|混合票|\d+票)/,
  /锚/,
  /证据不足证据/,
  /独立独立/,
  /旧只记[^。；]*→/,
  /此前记录[^。；]*→/,
  /旧卡|两票|436—437卡/,
  /旧[ABCDE]档→[ABCDE]档/,
  /重建(?:为)?\d+(?:\.\d+)?→/,
  /旧\d+(?:\.\d+)?(?:临时包|西州残值|总量)/,
  /旧\d{3,4}—\d{3,4}合并/
];

function check(value,item,where){
  if(value==null||value==='')return;
  const out=ctx.thirdItemPublicText(item,String(value));
  for(const pattern of forbidden){
    assert.doesNotMatch(out,pattern,where+' => '+out);
  }
}
for(const filename of fs.readdirSync('reader/data/people').filter(name=>name.endsWith('.json')).sort()){
  const record=JSON.parse(fs.readFileSync('reader/data/people/'+filename,'utf8')).record||{};
  const details=record.net?.component_details||{};
  for(const group of ['strategic','military']){
    for(const item of details[group]||[]){
      const where=filename+':'+(record.ruler_name||record.ruler_id||'?')+':'+group+':'+(item.label||'?');
      for(const key of ['reader_summary','reader_boundary','reader_how','public_level_label']){
        check(item[key],item,where+':'+key);
      }
      for(const [index,entry] of (item.reader_public_evidence_items||[]).entries()){
        for(const key of ['public_label','public_role','public_direction','public_source_coverage','public_basis','public_boundary']){
          check(entry?.[key],item,where+':evidence['+index+'].'+key);
        }
        for(const [tagIndex,tag] of (entry?.public_tags||[]).entries()){
          check(tag,item,where+':evidence['+index+'].public_tags['+tagIndex+']');
        }
      }
    }
  }
}
''',encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr



def test_fourth_item_public_formatter_cleans_current_people_pool(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "fourth-item-pool-leaks.cjs"
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const home=fs.readFileSync('reader/home-interactions.js','utf8');
function section(source,start,end){
  const a=source.indexOf(start),b=source.indexOf(end,a);
  assert.ok(a>=0&&b>a,start);
  return source.slice(a,b);
}
const ctx={
  cleanNetText:v=>String(v??'').replace(/\s+/g,' ').trim(),
  THIRD_CN_LEVEL:{'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7},
  esc:String
};
vm.createContext(ctx);
vm.runInContext(
  section(home,'  const CIV_PUBLIC_DIRECTION','  function civilizationPublicStatus')
  +'\nthis.civilizationPublicText=civilizationPublicText;',ctx
);

const forbidden=[
  /(?:本|现|原|旧|新|另)包/,
  /正包/,
  /负包/,
  /同包/,
  /独立增强包/,
  /计分资格/,
  /扩搜新证/,
  /净轴/,
  /净带位/,
  /限制带位/,
  /共同限制带位/,
  /硬门/,
  /硬负记录/,
  /硬负向/,
  /回填/,
  /倒算(?:本人|给)/,
  /轴级/,
  /作净算/,
  /洗掉/,
  /退出第四项/,
  /相对变化第[1-4一二三四]级/,
  /文明影响幅度第[0-4零一二三四]级/,
  /第[1-4一二三四]级影响幅度/,
  /结果方向未单列/,
  /相对既有状态/,
  /责任范围按现有材料区分/,
  /补充限制/,
  /归第二项/,
  /同账/,
  /另定整数负向变化/,
  /机械/
];

function assertClean(out,where){
  for(const pattern of forbidden){
    assert.doesNotMatch(out,pattern,where+' => '+out);
  }
}
function checkJudgment(value,where){
  if(value==null||value==='')return;
  assertClean(ctx.civilizationPublicText(String(value)),where);
}
assert.equal(ctx.civilizationPublicText('两条清晰但有限的变化不能机械堆成主要领域的稳定改变。'),'两条清晰但有限的变化不能直接叠加为主要领域的稳定改变。');
assert.equal(ctx.civilizationPublicText('不把整体声誉机械转化为高分。'),'不把整体声誉直接转化为高分。');
assert.equal(ctx.civilizationPublicText('不以字数缺失机械判零。'),'不以字数缺失直接判为零。');

function checkCalculation(value,where){
  if(value==null||value==='')return;
  assertClean(ctx.cleanNetText(String(value)),where);
}

for(const filename of fs.readdirSync('reader/data/people').filter(name=>name.endsWith('.json')).sort()){
  const record=JSON.parse(fs.readFileSync('reader/data/people/'+filename,'utf8')).record||{};
  const items=record.net?.component_details?.civilization||[];
  for(const item of items){
    const where=filename+':'+(record.ruler_name||record.ruler_id||'?')+':civilization:'+(item.label||'?');
    if(item.reader_kind==='calculation'){
      checkCalculation(item.reader_how,where+':reader_how');
      continue;
    }
    for(const key of ['reader_summary','reader_boundary','reader_how','public_level_label']){
      checkJudgment(item[key],where+':'+key);
    }
    for(const [index,entry] of (item.reader_public_evidence_items||[]).entries()){
      for(const key of ['public_label','public_role','public_direction','public_source_coverage','public_basis','public_boundary']){
        checkJudgment(entry?.[key],where+':evidence['+index+'].'+key);
      }
      for(const [tagIndex,tag] of (entry?.public_tags||[]).entries()){
        checkJudgment(tag,where+':evidence['+index+'].public_tags['+tagIndex+']');
      }
    }
  }
}
''',encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


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


def test_generic_net_full_basis_is_clearly_marked_as_unedited_audit_text():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert '<summary>正式裁决原文（未改写）</summary>${prose(fullBasis)}' in source
    assert "当前人物的完整裁决原文" not in source


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
    assert block.count("const format = value =>") == 1
    assert block.index("const format = value =>") < block.index("const cards = evidence.map")
    assert "const hasSourceCoverage = evidence.some(entry => format(" in block
    assert "metricDetail(item, record, key)" in source
    assert '当前判断：' in source

def test_profile_material_strength_is_public_first_and_raw_code_is_audit_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    template = (root / "reader/index.template.html").read_text(encoding="utf-8")
    css = (root / "reader/readability.css").read_text(encoding="utf-8")
    assert "formal-context-chip" in template
    assert "材料强度原始字段" in template
    assert "情境记录编号：" in template
    metadata_start = template.index("function formalContextMetadata")
    story_start = template.index("function formalContextStory", metadata_start)
    metadata_block = template[metadata_start:story_start]
    assert "formal-context-raw" not in metadata_block
    assert "正式字段：" not in metadata_block
    assert ".formal-context-story" in css
    assert 'const genericTitle=/^(?:(?:主要)?父情境\\d+|父链[A-ZＡ-Ｚ]|主要结构链\\d+|代表情境\\d+)$/' in template
    assert "rawTitle&&!genericTitle" in template
    assert ".formal-context-chip.context-intensity" in css

def test_home_full_table_uses_current_performance_accessibility_label():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'section === "person-outcome" ? "统治绩效"' in source
    assert 'section === "person-outcome" ? "净收益"' not in source

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

    assert "A · 统一主链客观贡献" not in home
    assert "B2 · 创业组织" not in home
    assert "下面再按A、B1、B2、C" not in home
    assert "第一项原始净分 S1" not in home
    assert '"统一成果", "先看本人真正留下了什么"' in home
    assert '"创业组织与政治整合", "多线并行、专业分工与异质整合"' in home
    assert "第一项结算分 <strong>${scoreNumber(netScore)} / 240</strong> · 统治绩效附加 <strong>+${scoreNumber(addOn)}</strong>" in home
    assert "四轴毛分 = 统一成果 + 创业难度与效率 + 创业组织与整合 + 本人统帅" in home
    assert "第一项结算分 S1" not in home
    assert "总榜附加 F" not in home
    for legacy in ("renderFirstA", "renderFirstB1", "renderFirstB2", "renderFirstC", "buildNetReading"):
        assert legacy not in person
    assert not (root / "reader/first-item-reading.js").exists()

def test_first_item_public_grade_translator_uses_letter_grades_and_named_cost_severity():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader/person-readability.js").read_text(encoding="utf-8")

    assert 'const FIRST_PUBLIC_C_GRADES = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};' in home
    assert '"起点R$1级"' not in home
    assert '"L$1级"' not in home
    assert '第${n}档' not in home
    assert "L0—L5" not in home
    assert "E、D、C、B、A、S 六档" in home
    assert 'const severity = ["无显著代价","很低成本","较低成本","中等成本","较高成本","高成本","极高成本","灾难级成本"];' in home
    assert '["成本程度", publicLevel]' in home
    assert "FIRST_PUBLIC_C_GRADES" not in person

def test_first_item_a_how_block_shows_exact_public_curve():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "统一成果分 = 120 × (min(1000, 本人有效控制成果值) / 1000)^0.65" in source
    assert "多人共同完成时再按正式归责分配个人成果" in source
    assert "firstOutcomeCalculationText(item.reader_how || \"\")" in source
    assert "项目A池 = " not in source
    assert "有效控制信用U" not in source


def test_first_item_commander_battle_letters_are_labeled_as_battle_scales():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "战役成果：" in source
    assert "任务难度：" in source
    assert "不是人物画像等级" in source
    assert "${esc(battle.result)}成果" not in source

def test_first_item_scope_routes_cost_boundary_through_public_formatter():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert '军事成本责任范围</dt><dd>${esc(firstPublicText(byLabel["军事成本扣分"].reader_boundary))}' in source
    assert '军事成本责任范围</dt><dd>${esc(byLabel["军事成本扣分"].reader_boundary)}' not in source


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
    assert "相关战争若已在军事与边疆项计入，本项不重复计算" in source
    assert "由奠基与统一项计入" in source
    assert "留在军事与边疆项" in source
    assert "function firstPublicText(value)" in source
    assert 'return firstPublicText(value)' in source
    assert 'prose(firstPublicText(value))' in source
    assert 'prose(firstPublicText(source.public_basis))' in source
    assert 'prose(firstPublicText(source.public_boundary))' in source
    assert 'firstCostPublicText(data.public_responsibility_window)' in source


def test_first_item_public_formatter_cleans_current_people_pool(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "first-item-pool-leaks.cjs"
    script.write_text(r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const home=fs.readFileSync('reader/home-interactions.js','utf8');
const start=home.indexOf('function firstPublicText(value)');
const end=home.indexOf('\n\nfunction firstB1Markup',start);
assert.ok(start>=0&&end>start,'firstPublicText block');
const firstPublicText=new Function(home.slice(start,end)+';return firstPublicText;')();

const forbidden=[
  /尚未?闭合/,
  /闭合/,
  /倒灌/,
  /回填/,
  /父链/,
  /准入条件/,
  /机械/,
  /合同/,
  /拆票/
];
function check(value,where){
  if(value==null||value==='')return;
  const out=firstPublicText(String(value));
  for(const pattern of forbidden)assert.doesNotMatch(out,pattern,where+' => '+out);
}
function walk(value,where,key=''){
  if(value==null)return;
  if(typeof value==='string'){
    if(!/(?:url|path|source)/i.test(key))check(value,where);
    return;
  }
  if(Array.isArray(value)){
    value.forEach((v,i)=>walk(v,where+'['+i+']',key));
    return;
  }
  if(typeof value==='object'){
    for(const [k,v] of Object.entries(value))walk(v,where+'.'+k,k);
  }
}
for(const filename of fs.readdirSync('reader/data/first-item').filter(name=>name.endsWith('.json')).sort()){
  const payload=JSON.parse(fs.readFileSync('reader/data/first-item/'+filename,'utf8'));
  for(const key of ['public_outcome','public_b1','public_commander','public_cost'])walk(payload[key],filename+':'+key,key);
}
for(const filename of fs.readdirSync('reader/data/people').filter(name=>name.endsWith('.json')).sort()){
  const record=JSON.parse(fs.readFileSync('reader/data/people/'+filename,'utf8')).record||{};
  for(const [i,item] of (record.net?.component_details?.first||[]).entries()){
    for(const key of ['reader_public_outcome','reader_public_b1','reader_public_commander','reader_public_cost']){
      walk(item?.[key],filename+':first['+i+'].'+key,key);
    }
  }
}
assert.equal(firstPublicText('后续阶段不回填，共同父链尚未闭合，未过准入条件。'),'后续阶段不追溯计入，共同主链尚未形成完整证据，未过计入条件。');
''',encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


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
def test_second_item_public_formatter_cleans_current_people_pool(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "second-item-pool-leaks.cjs"
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/second-item-public-alias.js','utf8');
const start=source.indexOf('  const PUBLIC_GRADE');
const end=source.indexOf('\n  function secondMethodExpandedHow',start);
assert.ok(start>=0&&end>start,'second public formatter block');
const ctx={};
vm.createContext(ctx);
vm.runInContext(
  source.slice(start,end)
  +'\nthis.publicText=publicText;this.publicTechnicalText=publicTechnicalText;this.publicFinanceText=publicFinanceText;this.publicHandoffText=publicHandoffText;this.publicBoundaryText=publicBoundaryText;this.publicFinanceBoundaryText=publicFinanceBoundaryText;this.publicMaterialTitleText=publicMaterialTitleText;this.publicMaterialBodyText=publicMaterialBodyText;this.publicBoundaryDifference=publicBoundaryDifference;',
  ctx
);

assert.equal(
  ctx.publicText('当前正式结构中已经闭合为独立制度节点；制度净值为+5；不机械降低等级；合同规定仍需保留限制。'),
  '当前正式结构中已经确认为独立制度节点；制度正负影响合计为+5；不直接降低等级；评价规则规定仍需保留限制。'
);
assert.equal(
  ctx.publicTechnicalText('整改时应删除旧版宗室谋乱材料，纯经济财政保C档；本轮不机械扣分。'),
  '复核时此前混入的宗室谋乱材料应移出本项，经济财政维持C档；当前不直接扣分。'
);
assert.equal(
  ctx.publicFinanceText('正式状态判断与损失修正按本轴合同换算为 28.2 分。'),
  '正式状态判断与损失修正按本轴规则换算为 28.2 分。'
);
assert.equal(
  ctx.publicText('不把后继司法改革倒灌计入；本批没有地区执行统计。'),
  '不把后继司法改革追溯计入；当前复核没有地区执行统计。'
);
assert.equal(
  ctx.publicFinanceText('旧任期结束状态=民生“广泛困顿”主要由病末及死后后秦迅速分裂反推，纯民生家庭结果不足，故终点2→3。'),
  '此前把病末及身后后秦分裂反推为本人任期结束时的民生状态；现有家庭生活材料不足以支持这一反推，因此任期结束状态改为“基本维持”。'
);
assert.equal(
  ctx.publicFinanceText('但旧任期结束状态=经济财政“失灵崩解”偏重。亡国不能自动等于经济财政“失灵崩解”，因此任期结束端修为2。'),
  '但此前把任期结束状态判断为经济财政“失灵崩解”，结论偏重。亡国不能自动等于经济财政“失灵崩解”，因此任期结束状态修正为D档。'
);
assert.equal(
  ctx.publicFinanceText('旧任期结束状态=4下调为3。'),
  '此前的任期结束状态由B档下调为C档。'
);
assert.equal(
  ctx.publicText('军队损耗与战役结果归第三项，居民结果归C1/C2/C4。'),
  '军队损耗与战役结果归第三项，居民结果归入民生、经济财政与恢复和额外代价。'
);
const repeatedFinanceBlock='这段材料同时说明常态运行和局部损害，包含足够长的事实链、责任边界与结果说明，用来验证长段重复只保留一份正文。'.repeat(2);
assert.equal(
  ctx.publicFinanceText('主要状态：可运行秩序。'+repeatedFinanceBlock+' 重要地区或群体出现明显损害：'+repeatedFinanceBlock+' 评价范围：这里只展示居民安全结果。'),
  '主要状态：可运行秩序。'+repeatedFinanceBlock+' 重要地区或群体出现明显损害：上述材料同时构成本项的重要地区或群体损害依据。 评价范围：这里只展示居民安全结果。'
);
const duplicateDamage=ctx.publicFinanceText('主要状态：可运行秩序。另有独立常态说明。 重要地区或群体出现明显损害：'+repeatedFinanceBlock+' 重要地区或群体出现明显损害：'+repeatedFinanceBlock+' 评价范围：这里只展示居民安全结果。');
assert.equal((duplicateDamage.match(/重要地区或群体出现明显损害：/g)||[]).length,1);
assert.equal(
  ctx.publicMaterialBodyText('范质泣谏使窦仪免于枉杀','范质泣谏使窦仪免于枉杀；已观察到实际结果'),
  '已观察到实际结果'
);
assert.equal(
  ctx.publicMaterialBodyText('制度建设','制度建设推动长期变化'),
  '制度建设推动长期变化'
);
assert.equal(
  ctx.publicMaterialTitleText('刘备外出时诸葛亮镇成都署府事并维持中枢交付中枢',['中枢行政链']),
  '刘备外出时诸葛亮镇成都署府事并维持中枢交付'
);
assert.equal(
  ctx.publicMaterialTitleText('中枢权力俘获与反馈压制',['中枢行政链']),
  '中枢权力俘获与反馈压制'
);
assert.equal(
  ctx.publicMaterialBodyText('徐邈任用、地方交付与中央奖升核心','徐邈任用、地方交付与中央奖升核心；该材料形成独立行政运行链，计入本项'),
  ''
);
assert.equal(ctx.publicBoundaryDifference('同一机制只作一次判断。','同一机制只作一次判断。'),'');
assert.equal(ctx.publicBoundaryDifference('本卡特有边界。','总体边界。'),'本卡特有边界。');

const forbidden=[
  /未?闭合/,
  /(?:制度|本项)?净值/,
  /机械/,
  /合同/,
  /整改/,
  /旧版/,
  /闭环/,
  /路由/,
  /切片/,
  /锚/,
  /可独立审计|固定语义审计/,
  /追溯计入计入/,
  /本批/,
  /N3·L4·READY/,
  /归C1\/C2\/C4/,
  /旧任期结束状态=/,
  /终点\d+→\d+/,
  /审计/
];
function format(group,key,value){
  if(value==null||value==='')return '';
  if(group==='finance')return key==='reader_boundary'?ctx.publicFinanceBoundaryText(value):ctx.publicFinanceText(value);
  if(group==='handoff')return key==='reader_boundary'?ctx.publicBoundaryText(ctx.publicHandoffText(value)):ctx.publicHandoffText(value);
  if(key==='reader_how')return ctx.publicTechnicalText(value);
  if(key==='reader_boundary')return ctx.publicBoundaryText(value);
  return ctx.publicText(value);
}
function assertNoFinanceSectionDuplication(out,where){
  const pattern=/(主要状态：|任期结束状态依据：|有界局部或短时损害：|重要地区或群体出现明显损害：|严重且广泛或长期反复的本轴损害：|未另证独立有效低谷：|评价范围：)/g;
  const matches=[...out.matchAll(pattern)];
  const sections=matches.map((match,index)=>({
    label:match[0],
    body:out.slice(match.index+match[0].length,index+1<matches.length?matches[index+1].index:out.length).replace(/\s+/g,' ').trim(),
  }));
  const main=sections.find(section=>section.label==='主要状态：')?.body||'';
  const seen=new Set();
  for(const section of sections){
    const sectionKey=section.label+'|'+section.body;
    if(section.body.length>=80)assert.ok(!seen.has(sectionKey),where+' => duplicate section '+section.label+section.body);
    seen.add(sectionKey);
    if(['有界局部或短时损害：','重要地区或群体出现明显损害：','严重且广泛或长期反复的本轴损害：'].includes(section.label)&&section.body.length>=80&&main){
      assert.ok(!main.includes(section.body),where+' => repeated main-state block under '+section.label+section.body);
    }
  }
}

function check(value,group,key,where){
  const out=format(group,key,value);
  if(!out)return;
  for(const pattern of forbidden)assert.doesNotMatch(out,pattern,where+' => '+out);
  if(group==='finance')assertNoFinanceSectionDuplication(out,where);
}
for(const filename of fs.readdirSync('reader/data/people').filter(name=>name.endsWith('.json')).sort()){
  const record=JSON.parse(fs.readFileSync('reader/data/people/'+filename,'utf8')).record||{};
  const details=record.net?.component_details||{};
  for(const group of ['method','finance','handoff']){
    for(const item of details[group]||[]){
      const root=filename+':'+(record.ruler_name||record.ruler_id||'?')+':'+group+':'+(item.label||'?');
      for(const key of ['reader_summary','reader_boundary','reader_how','public_level_label'])check(item[key],group,key,root+':'+key);
      const evidence=item.reader_public_evidence_items||item.public_evidence_items||[];
      for(const [i,entry] of evidence.entries()){
        for(const key of ['public_label','public_direction','public_role','public_basis','public_boundary','public_source_coverage']){
          check(entry?.[key],group,key,root+':evidence['+i+'].'+key);
        }
        for(const [j,tag] of (entry?.public_tags||[]).entries())check(tag,group,'public_tags',root+':evidence['+i+'].public_tags['+j+']');
      }
    }
  }
}
''',encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_second_item_material_groups_do_not_render_empty_categories():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "if (!cards.length) return document.createDocumentFragment();" in source
    assert "当前没有该类材料。" not in source


def test_structured_material_pages_avoid_default_summary_and_scope_duplication():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    a_public = (root / "reader/second-item-a-public.js").read_text(encoding="utf-8")
    b1_public = (root / "reader/second-item-b1-public.js").read_text(encoding="utf-8")
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")

    assert 'if (scope || boundary)' in alias
    assert 'details.append(makeTextBlock("summary", "", "范围与边界"))' in alias
    assert 'card.append(box);' not in alias[alias.index('const scope = publicText(data.scope)'):alias.index('const footer = publicText(data.footer)')]
    assert 'title.textContent = publicMaterialTitleText(rawTitle, data.tags);' in alias
    assert 'const body = publicMaterialBodyText(rawTitle, data.body);' in alias
    assert '["核心行政链", "核心"]' in alias
    assert '["中枢行政链", "中枢"]' in alias
    assert '["多责任官行政链", "多责任官"]' in alias
    assert 'renderB2MaterialGroups(evidence, item.reader_boundary)' in alias
    assert 'renderFinanceMaterialGroups(label, evidence, item.reader_boundary)' in alias
    assert 'renderHandoffMaterialGroups(label, evidence, item.reader_boundary)' in alias
    assert 'api.boundaryDifference(entry?.public_boundary, sharedBoundary)' in a_public
    assert 'api.boundaryDifference(entry?.public_boundary, sharedBoundary)' in b1_public
    for public_source in (a_public, b1_public):
        assert "正式人物级公开投影" not in public_source
        assert "上游裁决" not in public_source
        assert "原始记录与计算口径" not in public_source
        assert "正式记录来源" in public_source
        assert "正式依据与计算说明" not in public_source
        audit_start = public_source.index("function appendDedicatedAudit")
        audit_end = public_source.index("function ensureStyles", audit_start)
        assert "reader_how" not in public_source[audit_start:audit_end]
    assert "内部影响权重" not in a_public
    assert 'const structuredMaterials = MATERIAL_CARD_GROUPS.has(groupKey) && publicEvidence.length > 0;' in home
    assert '总体裁决摘要' in home
    assert 'const logic = structuredMaterials ? "" : summary;' in home
    assert 'class="net-overall-boundary"' in home
    assert '<summary>总体范围与边界</summary>' in home
def test_structured_material_cards_deduplicate_single_summary_and_shared_boundary():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")

    assert "function materialSummaryCoveredBySingleEvidence(summaryValue, basisValue)" in source
    assert "if (summary === basis) return true;" in source
    assert "summaryTail.length >= 20 && summaryTail === basisTail" in source
    assert 'const overallBoundary = format(item.reader_boundary || "");' in source
    assert 'const boundary = candidateBoundary && candidateBoundary !== overallBoundary ? candidateBoundary : "";' in source
    assert "const summaryCoveredByEvidence = structuredMaterials" in source
    assert "structuredMaterials && summary && !summaryCoveredByEvidence" in source


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
    assert "const evidenceScope=axisEvidenceScope(a,c),evidenceLevel=evidenceScope.coverage;" in template
    assert "coverage:scope.material_coverage_label" in template
    assert 'class="axis-evidence-level">材料覆盖：' in template
    assert "材料覆盖：'+esc(evidenceLevel)" in template
    assert "材料级别 ${esc(a.axis_evidence_level" not in template


def test_reader_guide_preserves_material_strength_display_boundary():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "只有正式记录明确发布相应字段时页面才展示" in template
    assert "没有这类标签只表示正式记录未发布该字段，不等于证据弱" in template
    assert "这是离线交互设计样稿" not in template
    assert "更新正式记录后重新构建阅读页" not in template
    assert "本页展示最近一次正式发布的结算数据" in template
    assert "本页只展示已经裁定的事实和限制。" in template
    assert "本阅读层展示" not in template
    assert "正式记录更新后会在后续发布中同步" in template
    assert "两者不是同一尺度" in template
    assert "页面也不会自行补判" in template


def test_public_scope_copy_avoids_internal_pool_and_public_band_jargon():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "不在人物画像主池" not in template
    assert "不进入本展示的人物画像主池" not in template
    assert "历史影响池外补充样本" not in template
    assert " · 补充样本" not in template
    assert "公众总档" not in template
    assert "人物画像正式评价范围" in template
    assert "补充历史样本" in template
    assert "历史影响总等级" in template
    assert "历史影响 · 总等级" in template
    assert '<option value="impact">历史影响总等级</option>' in template
    assert "全部影响等级" in template
    assert "统治绩效主池" not in template
    assert "统治绩效总榜" not in template
    assert "统治绩效正式排序" in template
    assert "主池" not in template
    assert '<option value="main">正式评价对象</option>' in template
    assert "不在统治绩效正式评价范围" in template
    assert "该补充样本不在人物画像正式评价范围。" in template
    assert "M2终局" not in template
    assert "八轴分别观察军事、外交、联盟、组织、判断、学习、用人与制度设计等能力" in template
    assert "看治国、军事、统一与文明整合如何共同构成统治绩效" in template


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
    assert "计算中间项和小计不在对照页展开" in block
    assert "内部档位码" not in block
    assert "row('分项构成'" in template
    assert "<summary>展开分项</summary>" in template


def test_compare_net_breakdown_keeps_formal_public_level_labels():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index("function compareNetPublicLevel")
    end = template.index("const impactAuditSource", start)
    block = template[start:end]
    assert "item?.public_level_label" in block
    assert "item?.grade" not in block
    assert "当前判断按正式记录展示" in block
    assert "普通成本扣分" in block
    assert "严重军事成本" in block
    assert "清晰但有限的变化" in block
    assert "if(level)return" in block
    assert "不单独计分" in block


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
    assert "本项适用，但第一项结算分为0" in template
    assert "这与“不适用”不同" in template
    assert "compareFirstAddOn" in template
    assert "function firstRawScore" in template
    assert "Number(n.first_item_raw_score)===0" not in template
    assert "Number(r.net.first_item_raw_score)===0" not in template
    assert "signedAdjustment" in template
    assert 'groupKey === "civilization"' in home
    assert "本项适用，但第一项结算分归零" in home
    assert "function finiteNetNumber(value)" in home
    assert '&& Number(record.net?.first_item_raw_score) === 0' not in home
    assert '&& Number(record.net.first_item_raw_score) === 0' not in home
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
    assert "r.supplementary?'<div class=\"home-profile-static\">" in template
    simple_start = template.index(" const simple=()=>")
    simple_end = template.index(" const full=()=>", simple_start)
    simple = template[simple_start:simple_end]
    assert 'data-home-section="person-capability"' in simple
    assert "home-profile-static" in simple
def test_compare_edge_helpers_are_self_contained_and_supplementary_profile_has_no_dead_help():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    compare_start = template.index("function compare(){")
    compare_end = template.index("function guide()", compare_start)
    block = template[compare_start:compare_end]
    assert "const missingNetLabel=r=>" in block
    assert "const firstRawScore=n=>" in block
    assert "const compareFirstAddOn=r=>" in block
    assert "const signedAdjustment=value=>" in block
    assert "该对象只作为补充历史样本，不进入人物画像正式评价范围。" in template
    assert "r.supplementary?'<p>该对象只作为补充历史样本" in template
    assert "const stateLabel=r=>r.supplementary?'不在人物画像正式评价范围':grade(r.axes[c])" in block
    assert "r.supplementary?'<span class=\"muted\">不在人物画像正式评价范围</span>'" in block

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



def test_reader_formats_structured_power_windows_without_changing_formal_source():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/build.py").read_text(encoding="utf-8")
    assert "def public_power_window(value):" in source
    assert 'return "；".join(spans)' in source
    assert 'f"前{abs(year)}"' in source
    assert 'record["actual_power_window"] = public_power_window(record.get("actual_power_window"))' in source
    assert 'projected_net["governance_context"] = public_governance_context(' in source
    assert 'actual_power_window=public_power_window(row.get("reference_power_window", ""))' in source

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
  +'\nthis.thirdPublicText=thirdPublicText; this.thirdItemPublicText=thirdItemPublicText;', thirdCtx);
assert.equal(
  thirdCtx.thirdPublicText('接手时为第3级。现有上层证据未显示摄政替代；本窗口未见替代者，故交班为第4级。','A1'),
  '接手时为B档。现有材料未显示摄政替代；任内未见替代者，故结束时为A档。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第5级、高位。规模与控制强度：总量不变；全部旧唐代区域标识迁移到同一口径。','B1'),
  '实际控制范围当前为S档、高位。现有材料支持维持当前控制范围等级。'
);
assert.equal(
  thirdCtx.thirdPublicText('统一核心领土由第一项计入；本项只读岭南成果，阶段扩张只留在战争卡和军事体系/相关正式记录。','B2'),
  '统一核心领土由奠基与统一项计入；这里只计岭南成果，阶段扩张只作为战争与军事体系表现背景，不计作可移交控制成果。'
);
assert.equal(
  thirdCtx.thirdPublicText('终点值由3.0修正为3.8，净变化由2.2修正为3.0，加权值由2.52修正为3.32；实际控制范围由第三级高位的74调整为第四级低位的75。','B1'),
  ''
);
assert.equal(thirdCtx.thirdPublicText('结束时第5级安全水平','A1'),'结束时S档安全水平');
assert.equal(thirdCtx.thirdPublicText('1→5档','A1'),'D档→S档');
assert.equal(thirdCtx.thirdPublicText('0.25→0.75覆盖','B1'),'0.25→0.75覆盖');
assert.equal(thirdCtx.thirdPublicText('旧终点值 3.6→3.4，净变化 1.3→1.1，加权值 2.22→2.02；档位和得分率不变。','B1'),'重新核对控制存量后，档位和合成比例不变。');
assert.equal(thirdCtx.thirdPublicText('当前结果先得到 37.0% 的得分率，合成时采用 37%。','B1'),'当前等级进入合成时采用 37%。');
assert.equal(thirdCtx.thirdPublicText('旧起点值 3.6→3.4，终点值 4.0→3.8，加权值 1.84→1.76；档位和得分率不变。','B1'),'重新核对控制存量后，档位和合成比例不变。');
assert.equal(thirdCtx.thirdPublicText('采用比例 0→15。','B1'),'合成比例由 0% 调整为 15%。');
assert.equal(thirdCtx.thirdPublicText('实际控制范围率44→60。','B1'),'控制范围合成比例由 44% 调整为 60%。');
assert.equal(thirdCtx.thirdPublicText('客观起终库存保留，交班库存与继承库存分别核对。','B1'),'接手与结束时的控制存量保留，任期结束时可移交的控制存量与继承控制存量分别核对。');
assert.equal(thirdCtx.thirdPublicText('军事成本为第六级低位。成本是否达到第七级。','ML扣分'),'军事成本为极端军事成本、低位。成本是否达到灾难性军事耗竭。');
assert.equal(thirdCtx.thirdPublicText('战略链化不会把阶段性反击冲销终局失效。','C1实战交付'),'按战略主链归并不会把阶段性反击冲销终局失效。');
assert.equal(thirdCtx.thirdPublicText('不回填朱祁镇灾后再动员。','ML扣分'),'不把朱祁镇灾后再动员重复计入本人。');
assert.equal(
  thirdCtx.thirdPublicText('B1控制规模与B2战略价值按55%/45%合成，再由B4交班成熟度修正','B80'),
  '控制范围与战略价值按55%/45%合成，再由成果稳定性修正'
);
assert.equal(thirdCtx.thirdPublicText('普通军事代价为第5级、中位','普通成本扣分'),'普通军事代价为严重军事成本、中位');
assert.equal(
  thirdCtx.thirdPublicText('父周期仅完成边界证实，任务成员与独立父周期结构未变；没有产生新的升降档理由。','C1实战交付'),
  ''
);
assert.equal(
  thirdCtx.thirdPublicText('该方面为第5级水平。已核对5项独立任务，其中较好结果0项、低回报0项、负向结果0项。三个重大成功能力信号且无重大失败。','C1实战交付'),
  '该方面为S档水平。三个重大成功能力信号且无重大失败。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第4级、中位。规模与控制强度：废止‘1206—1227新增整链一律归第一项’的形式节点切法；只排除灭夏终局0.8及攻金遗留控制0.5，花剌子模—中亚—西亚4.25保留在第三项，机械落实际控制范围第4级 中位。','B1'),
  '实际控制范围当前为A档、中位。统一主链中已由奠基与统一项承担的灭夏终局与攻金遗留控制不重复计入；花剌子模—中亚—西亚的控制成果保留在本项。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第3级、低位。规模与控制强度：西北0.8继承；统一后北方边郡0.8仅作客观库存；河南地—朔方新增0.6、岭南新增0.8；删除旧西南0.5与1.05非标准草原包。','B1'),
  '实际控制范围当前为B档、低位。河南地—朔方与岭南的新增控制计入本项；继承存量及未达到正式标准的控制成果不重复计算。'
);
assert.equal(
  thirdCtx.thirdPublicText('按重大压力下保全封顶4档。机械落实际控制范围第4级 中位。','B1'),
  '按重大压力下保全最高计至A档。据此定为实际控制范围A档中位。'
);
assert.equal(
  thirdCtx.thirdPublicText('战争保留为第三项现期；相关战争仅按军事体系规定作为能力专用证据。','C1实战交付'),
  '战争保留为本项当前窗口；相关战争只作为军事体系判断的补充证据。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第0级、低位。规模与控制强度：承接嬴政真实3.0边疆库存后逐区退出；不使用终局 强制修正。','B1'),
  '实际控制范围当前为E档、低位。承接嬴政既有边疆控制存量后逐区退出；按政权终结时的实际控制结果判断。'
);
assert.equal(
  thirdCtx.thirdPublicText('战略成果价值为当前结果为第0级、低位。本人任内中央与边疆控制随秦政权崩溃归零，统一执行终局门；没有可在任期结束时保留的控制成果。','B2'),
  '战略成果价值当前为E档、低位。本人任内中央与边疆控制随秦政权崩溃归零，按政权终结时的实际控制结果判断；没有可在任期结束时保留的控制成果。'
);
assert.equal(
  thirdCtx.thirdPublicText('按用户冻结规则，轴5必须由第三项本体重大体系胜绩复验。最终4/4/4、军事体系整体第4级。','C1实战交付'),
  '按当前固定口径，S档必须由本项自身的重大体系胜绩再次验证。三方面均为A档。'
);
assert.equal(
  thirdCtx.thirdPublicText('靖难不再作为第三项军事体系军事体系正证；其能力只保留在人物画像。','C1实战交付'),
  '靖难不再作为本项军事体系的正向证据；其能力只保留在人物画像。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第3级、低位。规模与控制强度：旧账错误按靖康覆亡把赵佶终点值直接清零，采用比例29；修正终局时点并保留西北真实扩张后升至60。','B1'),
  '实际控制范围当前为B档、低位。按赵佶实际退位时点判断，不把1127年的靖康覆亡倒推到1126年；退位前已经形成的西北控制成果仍计入。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第0级、低位。规模与控制强度：有效率仍0，但旧0→0改为0.725→0，真实表达终局退控。','B1'),
  '实际控制范围当前为E档、低位。任期内实际控制继续收缩，并在政权终结时归零。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第3级、低位。规模与控制强度：旧0.65→2.1使用安南临时0.5尺度；规范后0.8→2.4，加权值 1.71→1.92，得分率仍60。','B1'),
  '实际控制范围当前为B档、低位。按统一口径重新核对安南及相关边疆控制后，当前控制范围等级不变。'
);
assert.equal(
  thirdCtx.thirdPublicText('本人可本人责任主干改为党项方向；两个本人窗口合并，景泰间实际控制范围存量没有跨阶梯变化。','B2'),
  '本人可归责的主干成果改为党项方向；两个本人窗口合并，景泰间实际控制范围存量没有跨公开等级变化。'
);
assert.equal(
  thirdCtx.thirdPublicText('重大失败不是独立倍增计票，但共同证明持续作战与体系可靠性进入1档，军事体系整体第1级维持2。','C1实战交付'),
  '重大失败不会因事件拆分而重复加重判断，但共同证明持续作战与体系可靠性进入D档，军事体系整体维持D档。'
);
assert.equal(
  thirdCtx.thirdPublicText('可移交控制结构的覆盖、持续和承载强度判断为控制成果稳定性第0级；不重复计算安全态势项宏观边疆态势。','B4'),
  '可移交控制结构的覆盖、持续和承载强度判断为控制成果稳定性E档；不重复计算已经在安全态势中判断的宏观边疆变化。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第0级、低位。规模与控制强度：原正式控制规模值为52，实际采用值为0；统一参照点后，客观加权值为0.72，对应正式值应为44，但第三项有效采用比例仍为0。','B1'),
  '实际控制范围当前为E档、低位。相关控制成果已在奠基与统一项计入，本项不再重复计入。'
);
assert.equal(
  thirdCtx.thirdPublicText('按军事体系整体第4级重大胜绩硬门封顶军事体系整体第3级。','C1实战交付'),
  '尚未达到A档所需的重大体系胜绩条件，军事体系整体维持B档。'
);
assert.equal(
  thirdCtx.thirdPublicText('采石构成重大体系胜绩并通过军事体系整体第4级条件。','C1实战交付'),
  '采石构成重大体系胜绩并达到军事体系整体A档所需条件。'
);
assert.equal(
  thirdCtx.thirdPublicText('正式军事体系按8条当前任务与4条仅作能力证据支撑三轴4档；创业恢复链不回灌第三项结果/成本。','C1实战交付'),
  '现有正式任务与补充能力证据共同支持三方面均为A档；创业恢复链不重复计入本项结果与成本。'
);
assert.equal(
  thirdCtx.thirdPublicText('普通军事代价为不适用或尚未定级。当前第三项成本清单将其标记为不适用。按当前评定用户指定范围，不重新审查该状态的跨项来源；只确认没有独立军事体系档需要重新定级。','普通成本扣分'),
  '本项不单独结算军事代价。相关战争成本已按评价边界在其他项目处理，本项不重复结算。'
);
assert.equal(
  thirdCtx.thirdPublicText('1161父卡将临机整军归于将领，客观终点升档但不生成本人改善信用；创业恢复链不回灌第三项结果。','A1'),
  '1161任务记录将临机整军归于将领，客观终点升档但不计为本人改善成果；创业恢复链不重复计入本项结果。'
);
assert.equal(
  thirdCtx.thirdPublicText('关键证据仍有缺口缺口保留。','普通成本扣分'),
  '关键证据仍有缺口。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第0级、中位。规模与控制强度：数值不变；旧标识规范化。','B1'),
  '实际控制范围当前为E档、中位。现有材料支持维持这一控制范围等级。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第0级、低位。规模与控制强度：承接北方边郡遗漏修正：起点值 5.8→6.6，加权值 -3.48→-3.96；终局门下档位与得分率不变。','B1'),
  '实际控制范围当前为E档、低位。补齐北方边郡材料后，政权终结这一结论不变，因此控制范围等级仍维持当前判断。'
);
assert.equal(
  thirdCtx.thirdPublicText('战略成果价值为当前结果为第0级、低位。终局门覆盖任内阶段性占领或扩域尝试。','B2'),
  '战略成果价值当前为E档、低位。政权终结后，任内阶段性占领或扩域尝试不作为可移交成果。'
);
assert.equal(
  thirdCtx.thirdPublicText('974—975水陆军连续失效；这是单一但国家级终局崩溃链，1/1/0维持。','C1实战交付'),
  '974—975水陆军连续失效；这是单一但国家级终局崩溃链，实战任务交付D档、持续作战D档、体系可靠性E档。'
);
assert.equal(
  thirdCtx.thirdPublicText('河西树机能270、277、279三票归为同一连续父周期，7项降至5项；完整河西周期取回报与投入相称，278西陵独立突袭由证据不足证据支持评为低回报。去重后故三轴4/4/3不变。','C1实战交付'),
  '河西树机能270、277、279三次相关行动归为同一连续任务周期；完整河西周期取回报与投入相称，278年西陵独立突袭现有证据仅支持判断为低回报。去重后故实战任务交付A档、持续作战A档、体系可靠性B档。'
);
assert.equal(
  thirdCtx.thirdPublicText('本批父周期边界未改变足以影响三轴的事实基础，正式横校沿用正式三轴/既有能力专用判断。','C1实战交付'),
  '重新核对任务边界后，三方面事实基础未变，现有等级维持不变。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第0级、低位。规模与控制强度：旧账仅以1.3→0并启用按终局崩溃强制清零。现改为从杨坚真实4.2交班库存逐区域核退出；吐谷浑、伊吾阶段新增另存峰值但不进入618终点。最终实际控制范围率仍0，但不是由终局标签强制清零。','B1'),
  '实际控制范围当前为E档、低位。按杨坚任期结束时的实际控制存量逐区域核对；吐谷浑、伊吾虽有阶段新增，但至618年均未形成可保留的终点控制，因此实际控制范围归零。'
);
const strategicItem={label:'A1',grade:'3→0档'};
assert.equal(
  thirdCtx.thirdItemPublicText(strategicItem,'接手时为第3级，结束时为未单列等级。李隆基 主要安全威胁与战略主动（主要威胁能力与战略主动）本人责任判断：主要威胁转为安史叛军；故客观变动-3档按-3档本人责任。'),
  '接手时为B档，结束时为E档。主要威胁转为安史叛军；相应状态变化按本人责任计入。'
);
assert.equal(
  thirdCtx.thirdPublicText('接手时为第2级，结束时为第3级。刘秀 主要安全威胁与战略主动（主要威胁能力与战略主动）本人责任判断：北方改善部分来自外部因素；故客观变动+1档中取0.5档。本人和其他责任中心共同承担。','A1'),
  '接手时为C档，结束时为B档。北方改善部分来自外部因素。本人和其他责任中心共同承担。'
);
assert.equal(
  thirdCtx.thirdPublicText('因此实战任务交付=4而持续作战与任务承载/军事体系可靠性=3。','C1实战交付'),
  '因此实战任务交付为A档而持续作战与任务承载/军事体系可靠性为B档。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第2级、高位。规模与控制强度：旧5.0→2.2把安史危机过度转成空间退控；重建后3.225→3.225，实际控制范围率15→59。主要安全威胁与战略主动/防线协同与战略纵深仍完整承担安史终局崩坏。','B1'),
  '实际控制范围当前为C档、高位。重新核对后，不再把安史危机整体换算为空间退控；当前控制范围合成比例为59%。主要安全威胁与战略主动/防线协同与战略纵深仍完整承担安史终局崩坏。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第0级、中位。规模与控制强度：旧起点值/旧终点值 6.7→4.7体系存在东北满额包和北方残量误继承；同一口径后为5.8→2.925，实际控制范围率44→15。','B1'),
  '实际控制范围当前为E档、中位。重新核对后，东北控制存量和北方残余控制不再错误计入；当前控制范围合成比例为15%。'
);
assert.equal(
  thirdCtx.thirdPublicText('实际控制范围为当前结果为第2级、中位。旧终点值 6.7→5.8，加权值 1.90→1.00，实际控制范围率60→52；核心修正是高丽—百济故地1.4改为辽东0.5。','B1'),
  '实际控制范围当前为C档、中位。重新核对后，当前控制范围合成比例为52%；高丽—百济故地仅按辽东部分计入。'
);
assert.equal(
  thirdCtx.thirdPublicText('十节度与边帅权力集中只作体系观察，不当作独立战果票。军事体系整体第3级=1。','C1实战交付'),
  '十节度与边帅权力集中只作体系观察，不当作独立战果。军事体系整体B档。'
);
assert.equal(
  thirdCtx.thirdPublicText('支持第六级高位军事成本；肃宗重建不倒灌本人。','ML扣分'),
  '支持极端军事成本（高位）；肃宗后续重建不归入本人。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧只记燕云0→0.8，漏掉阿保机交班草原和辽东库存；45→59。','B1'),
  '此前只计燕云控制，漏掉阿保机任期结束时的草原和辽东控制存量；补全后当前控制范围判断相应上调。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧954—955合并上层证据先整体退出，955胡卢河若独立拆链后再复核。','普通成本扣分'),
  '954—955年合并材料不再作为本项独立成本依据；955年胡卢河仅在能够形成独立任务链时另行判断。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧E档→E档无法表达真实退控；重建为3.0→1.65，控制范围合成比例由 0% 调整为 15%。','B1'),
  '重新核对控制存量后，明确记录任期内真实退控；当前控制范围合成比例为15%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧E档→E档掩盖蒙古造成的真实退控；重建3.0→1.5，合成比例由 0% 调整为 15%。','B1'),
  '重新核对控制存量后，纳入蒙古进攻造成的真实退控；当前控制范围合成比例为15%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧E档→E档无法表达河北、山东、河东、陕西持续退控；重建1.5→0.725，合成比例由 0% 调整为 29%。','B1'),
  '重新核对控制存量后，纳入河北、山东、河东、陕西的持续退控；当前控制范围合成比例为29%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧1.0临时包改为草原规范锚0.875+辽东0.5；45→59。','B1'),
  '统一草原与辽东控制口径后，当前控制范围合成比例为59%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧1.0临时包改为草原规范依据0.875+辽东0.5；45→59。','B1'),
  '统一草原与辽东控制口径后，当前控制范围合成比例为59%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧0.2西州残值改为0.3三受降城实际控制存量；综合控制量已重新核对，合成比例仍为30%。','B1'),
  '重新核对后，删除西州错误残余控制并计入三受降城实际控制存量；合成比例仍为30%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧5.0总量被东北1.4+松外0.5高估；三受降城0.3保留。控制范围合成比例由 67% 调整为 59%。','B1'),
  '重新核对后，东北与松外控制存量不再高估，三受降城控制仍保留；当前控制范围合成比例为59%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧0→0把实际仍存的燕云、辽东、松外和部分草原网络全部漏掉；0→37。','B1'),
  '补全燕云、辽东、松外与草原控制存量后，当前控制范围合成比例为37%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧0→0完全漏继承库存；0→45。','B1'),
  '补全继承控制存量后，当前控制范围合成比例为45%。'
);
assert.equal(
  thirdCtx.thirdPublicText('452北伐由证据不足证据支持评为负向，另一独立独立任务周期维持。','C1实战交付'),
  '452北伐现有证据仅支持判断为负向，另一独立任务周期维持。'
);
assert.equal(
  thirdCtx.thirdPublicText('默啜防御与三受降城本属同一705—708连续北边战略链：先败、再反击、再筑三城烽候形成耐久防务，不能拆成一低一高两票。军事体系整体D档因此C档→B档；但安西—突骑施方向仍发生关键枢纽失陷且未证明恢复，军事体系整体B档保持2，最终评定仍军事体系整体C档。','C1实战交付'),
  '默啜防御与三受降城本属同一705—708连续北边战略链：先败、再反击、再筑三城烽候形成耐久防务，不能拆成一项低回报和一项高回报分别计算。这一北边主链改善了军事体系判断；但安西—突骑施方向仍发生关键枢纽失陷且未证明恢复，因此最终军事体系整体仍维持C档。'
);
assert.equal(
  thirdCtx.thirdPublicText('数值不变；伊吾0.2改用哈密门户，其余旧标识规范化。','B1'),
  '伊吾部分改用哈密门户口径，当前控制范围等级不变。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧0→1.0、综合控制量1.0、合成比例 45%只记南西恢复；补入继承控制存量和北方恢复后1.65→3.0、综合控制量2.01、合成比例 67%。','B1'),
  '此前只计南、西方向恢复；补入继承控制存量和北方恢复后，当前合成比例为67%。'
);
assert.equal(
  thirdCtx.thirdPublicText('相关任务按统一边界重新归并；凉州重大失败仍保留，只取消阶段负面重复计票。','C1实战交付'),
  '相关任务按统一边界重新归并；凉州重大失败仍保留，阶段负面不重复计入。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧实际控制范围 E档→E档与其安全态势/控制成果材料直接矛盾；补全三方向继承控制存量后合成比例由 0% 调整为 52%。','B1'),
  '此前控制范围判断与安全态势、控制成果材料不一致；补全三方向继承控制存量后，当前合成比例为52%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧实际控制范围=30；修复继承存量断链后升至37。','B1'),
  '修复继承存量断链后，当前控制范围合成比例为37%。'
);
assert.equal(
  thirdCtx.thirdPublicText('旧实际控制范围=30；旧区域对象漂移导致继承存量漏记，修正后升至44。','B1'),
  '此前区域对象口径漂移导致继承存量漏记，修正后，当前控制范围合成比例为44%。'
);

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
assert.equal(
  civCtx.civilizationPublicText('负向变化第2级.5；原理由中的相对变化第3级与文明影响幅度第3级为过期表述。'),
  '负向变化在清晰但有限基础上进一步强化；此前较高等级表述已不再采用。'
);
assert.equal(civCtx.civilizationPublicText('净文明影响幅度第1级'),'净影响为局部、短期或低强度变化');
assert.equal(civCtx.civilizationPublicText('第三级影响幅度'),'主要领域的稳定改变');
assert.equal(civCtx.civilizationPublicText('与负向变化第2级同账。'),'与负向变化达到清晰但有限的变化在同一维度合并判断。');
assert.equal(civCtx.civilizationPublicText('正向变化第2级，但不足以洗掉系统性负向变化。'),'正向变化达到清晰但有限的变化，但不足以抵消系统性负向变化。');
assert.equal(civCtx.civilizationPublicText('与本轴另包的严苛限制作净算。'),'与本轴另一项材料的严苛限制合并判断。');
assert.equal(civCtx.civilizationPublicText('不把后继军事成果回填。'),'不把后继军事成果重复计入本人。');
assert.equal(civCtx.civilizationPublicText('不把后世结果倒算给本朝。'),'不把后世结果追溯计入本朝。');
assert.equal(civCtx.civilizationPublicText('后来峰值不全部倒算本人。'),'后来峰值不全部追溯计入本人。');
assert.equal(civCtx.civilizationPublicText('不足以把抽象控制另定整数负向变化第1级。'),'不足以把抽象控制另定为独立负向变化达到局部、短期或低强度变化。');
assert.equal(civCtx.civilizationPublicText('轴级仍按正向变化第3级判断。'),'本轴仍按正向变化达到主要领域的稳定改变判断。');
assert.equal(
  civCtx.civilizationPublicText('本包只计入目录；同轴禁毁负包不因此减轻。覆盖与持续性未同时强，取中位，撤去原高位。'),
  '该项材料只计入目录；同一维度中的禁毁负向材料不因此减轻。覆盖与持续性未同时强，取中位，不再维持此前高位。'
);
assert.equal(
  civCtx.civilizationPublicText('直接人身后果退出第四项，归第二项社会安全；晚年收束进一步压低净带位，净轴复核为文明影响幅度第2级低位负。'),
  '直接人身后果不在文明与国家整合项重复计入，归入治国成效中的社会安全；晚年收束进一步降低综合档位，综合判断为文明影响幅度为清晰但有限的变化低位负。'
);
assert.equal(
  civCtx.civilizationPublicText('本包未证成独立社会身份变化；不得以未知写成正向变化第1级。撤销本包计分资格，割地事实仍保留，不在第四项复制军事损益。'),
  '该项材料尚未证明独立社会身份变化；不能在证据不足时写成正向变化达到局部、短期或低强度变化。该材料不再单独形成调整，割地事实仍保留，不在文明与国家整合项重复计算军事得失。'
);
assert.equal(
  civCtx.civilizationPublicText('撤销的燕云交割包仍无计分资格；本包是扩搜新证，不能随旧包撤销而漏计。两条链共同限制带位，保强迁硬负向。'),
  '撤销的燕云交割包仍无单独调整依据；该项材料是新增材料，不能随原有材料撤销而漏计。两条链共同限制档内位置，强迁仍属强负向。'
);
assert.equal(
  civCtx.civilizationPublicText('与独立负相对变化第2级同账，轴净文明影响幅度第0级，不能把两个表现写成两个独立增强包。'),
  '与独立负向清晰但有限的变化在同一维度合并判断，本轴综合正负相抵，净调整为0，不能把两个表现写成两个独立加成。'
);
assert.equal(
  civCtx.civilizationPublicText('因此定相对变化第2级，不进相对变化第3级；原高位持续性不足。'),
  '因此定清晰但有限的变化，不足以达到主要领域的稳定改变；此前高位所需的持续性不足。'
);
assert.equal(
  civCtx.civilizationPublicText('政治反馈后果退出本轴，归第二项反馈纠错与权力约束；净档仍受重大负向限制第4级下限约束，不以科学生产消去硬负记录。'),
  '政治反馈后果不在本轴重复计入，归入治国成效中的反馈与约束；净档仍受重大负向限制达到系统性破坏下限约束，不以科学生产消去明确负向记录。'
);
assert.equal(
  civCtx.civilizationPublicText('结果方向未单列：甲。相对既有状态：乙。责任范围按现有材料区分。补充限制：丙。'),
  '正负变化并存：甲。比较起点：乙。限制：丙。'
);
assert.equal(
  civCtx.civilizationPublicText('故本知识包按轴边界撤资格，保留史实。撤销本包，不否认原事实。同窗文字标准化。'),
  '因此该材料保留为背景，但不再单独形成本轴调整。该材料不再单独计入，不否认原事实。同轴文字标准化。'
);

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
    assert "相应状态变化按本人责任计入" in source
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
    assert 'military:new Set(["C50","实际扣分","第三项合计"])' in home
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



def test_first_item_readers_do_not_backfill_missing_cost_or_net_as_zero():
    from pathlib import Path
    home = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")

    assert "[a, b1, b2, c, gross, cost, net, addOn]" in home
    assert ".some(value => value == null)" in home
    assert "cost ?? 0" not in home

def test_first_item_cost_explains_current_fixed_debit_lookup():
    from pathlib import Path
    home = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "const FIRST_COST_DEBIT" in home
    assert "5:{LOW:18,MID:22.5,HIGH:27}" in home
    assert "7:{LOW:60,MID:68,HIGH:76,HIGHEST:80}" in home
    assert "function firstCostExactHow(item)" in home
    assert "固定扣分表直接对应" in home
    assert "所以本项扣" in home

def test_first_item_b1_explains_start_opponent_and_efficiency_subscores():
    from pathlib import Path
    home = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "function firstB1ScoreText(item)" in home
    assert "“起点、强敌与速度”满分50 = 起点难度15 + 对手难度15 + 完成效率20" in home
    assert "B1满分50" not in home
    assert "资源越弱，创业难度分越高" in home
    assert "E档15、D档13、C档11、B档8、A档5、S档2、S+档0" in home
    assert "最强全值，第二强取50%" in home
    assert "期望完成年 = 4 + 8 × √(本阶段有效控制信用 / 1000)" in home
    assert "速度比≤0.75、1.00、1.25、1.50、2.00、2.50、3.00、4.00" in home

def test_major_cards_explain_third_and_fourth_item_scales():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "250分制净分" in source
    assert "再扣实际军事代价" in source
    assert "分项小数来自统一计分公式，不表示历史判断本身具有同等测量精度" in source
    assert "阅读时先看公开档位与事实依据" in source
    assert "三个分项合计范围为 -67.5～+67.5；正负值直接计入统治绩效总分" in source
    assert "本项计入统治绩效总分的净分：" in source
    assert "本项计入统治绩效总分的有符号调整：" in source
    assert "理论范围 -67.5～+67.5" not in source

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
    assert "function firstCommanderScoreText(item)" in home
    assert "D档（基础统帅）低/中/高位=4/7/10分" in home
    assert "C档（重要统帅）=12/15/18分" in home
    assert "B档（优秀统帅）=20/23/26分" in home
    assert "A档（顶级统帅）=28/31/34分" in home
    assert "S档（历史级统帅）=36/38/40分" in home
    assert "对应${item.value}分" in home
    assert "firstCommanderScoreText" not in person


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



def test_second_item_renderer_uses_same_public_grade_language():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/second-item-reading.js").read_text(encoding="utf-8")
    assert 'const METHOD_BAND_LABELS = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};' in source
    assert "最低档" not in source
    assert "最高档" not in source
    assert "主要状态第" not in source
    assert "低谷修正${low}级" not in source
    assert "原始表现指数" in source
    assert "用于本组折算，不单列得分" in source
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
    assert "用于本组折算，不单列得分" in source
    assert "用于制度与行政折算，不单列得分" in source
    assert "较高表现指数" in source
    assert "当前表现指数" in source




def test_second_item_public_boundary_display_deduplicates_repeated_clauses():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "function dedupeBoundaryText(value)" in source
    assert "function publicBoundaryText(value)" in source
    assert "function publicFinanceBoundaryText(value)" in source
    assert "boundaryText: publicBoundaryText" in source
    assert 'const boundary = publicBoundaryText(data.boundary);' in source
    assert 'financeItem ? publicFinanceBoundaryText(item.reader_boundary || "") : publicBoundaryText(item.reader_boundary || "")' in source


def test_second_item_a_and_b1_lead_with_reader_summary_not_internal_ledger_copy():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    a_source = (root / "reader/second-item-a-public.js").read_text(encoding="utf-8")
    b1_source = (root / "reader/second-item-b1-public.js").read_text(encoding="utf-8")
    assert "text: publicText" in alias
    assert "function publicSummary(item, evidence)" in a_source
    assert "影响权重、后世接收折算和原始表现指数只放在计算说明中" in a_source
    assert 'const formalSummary = globalThis.SecondItemMaterialCards?.text?.(item.reader_summary) || String(item.reader_summary || "").trim();' in a_source
    assert 'detailsBlock("为什么最终是这个等级？", formalSummary)' in a_source
    assert "function summaryText(item, evidence)" in b1_source
    assert "链条数量用于组织阅读，不按条数直接相减" in b1_source
    assert 'const formalSummary = globalThis.SecondItemMaterialCards?.text?.(item.reader_summary) || String(item.reader_summary || "").trim();' in b1_source
    assert 'detailsBlock("为什么最终是这个等级？", formalSummary || summary)' in b1_source



def test_historical_impact_public_copy_hides_model_version_and_review_jargon():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "function impactPublicText(t)" in source
    assert "V\\d+(?:\\.\\d+)+硬门复核通过" in source
    assert "最高档条件复核通过" in source
    assert "V\\d+(?:\\.\\d+)+范围只消费" in source
    assert "当前公开口径不再把" in source
    assert "剔除仅由名号、法统或制度惯性造成的接收后" in source
    assert "剔除名号与制度惯性的复核" in source
    assert "但不能把五代十国全部归入本人”这一主链中" in source
    assert "人物画像“战略判断”材料" in source
    assert "人物画像“'+(shortNames[code]||code)+'”材料" in source
    assert "军事结算材料" in source
    assert "奠基与统一中的组织与整合材料显示" in source
    assert "判断把握为中等" in source
    assert "制度结算材料" in source
    assert "较强但归责受限的有效责任链" in source
    assert "人物画像“用人授权”材料对此只确认有限的个人用人授权信用" in source
    assert "系统性、持续性的可观察制度成果" in source
    assert "顶级强度负向链" in source
    assert "社会安全处于E档的残局" in source
    assert "官僚治理材料又显示" in source
    assert "而非完全归于本人" in source
    assert "民力成本分项不再追加独立残余成本" in source
    assert ".replace(/\\bNEGATIVE\\b/g,\'负向\')" in source
    assert ".replace(/\\bMI3\\b/g,\'持续系统性情境\')" in source
    assert "极端劣势或濒临崩溃的逆转任务" in source
    assert "民生与财政结算材料" in source
    assert "集团机制材料复核" in source
    assert "相关正式材料" in source
    assert "重大内部恶化" in source
    assert "同一条国家级主链" in source
    assert "全国核心尺度25%" in source
    assert "皇帝主要承担批准、整合、维持与责任规则调整" in source
    assert "明确区分" in source
    assert "核对《帝鉴图说》" in source
    assert "不因后世名望提高等级" in source
    assert "当前公开裁决已把" in source
    assert "现有归责材料认为，这一终局变化高度依赖本人选择。" in source
    assert ".replace(/\\bDECISIVE_DRIVER\\b/g,\'决定性个人驱动\')" in source
    assert ".replace(/项目D/g,\'现有归责材料\')" in source
    assert "正式计入条件" in source
    assert ".replace(/只消费/g,'只计入')" in source
    assert ".replace(/硬变化/g,'已确认的实际变化')" in source
    assert ".replace(/去重桥接/g,'去重后综合判断')" in source
    assert ".replace(/有效空间当量/g,'实际影响范围')" in source
    assert ".replace(/本人分叉/g,'取决于本人选择的分支')" in source
    assert ".replace(/闭合为/g,'发展为')" in source
    assert "尚未形成多个最高权力稳定接收的独立证据链" in source
    assert "扩大本人归责范围" in source
    assert "足以支持$1档" in source
    assert "因此维持$1档" in source
    assert "function impactDimensionPublicText(key,value)" in source
    assert "const publicBasis=key=>impactDimensionPublicText(" in source
    assert 'if(key==="paradigm"){' in source
    assert 'text=text.replace(/^范式' in source
    assert 'text=text.replace(/^[SABCDE](?:[+−-])?[。；:]\\s*/' in source
    assert "const counterfactual=impactPublicText(" in source
    assert "const personalBoundary=impactPublicText(" in source
    assert "const evidenceBoundary=impactPublicText(" in source
    assert "prose(impactTotalPublicText(h))" in source
    assert "prose(impactPublicText(h.impact_nature_basis))" in source
    assert "prose(impactPublicText(c.narrative))" in source
    assert "<summary>${esc(impactPublicText(c.title))}</summary>" in source
    assert "统治绩效中的统一成果未保留，不等于历史影响范围为0" in source
    assert "没有形成可继承的稳定统治终点" in source
    assert "统治绩效中的统一成果只保留稳定控制" in source
    assert "统治绩效中的控制成果只看可继承的稳定终点" in source
    assert "直接抬高等级" in source
    assert "交叉核对结论" in source
    assert "直接结构风险" in source
    assert "人物画像“'+(shortNames[a]||a)+'”与“'+(shortNames[b]||b)+'”材料" in source
    assert "社会安全结算材料" in source
    assert "既有反向材料核对" in source
    assert "不能把全部结果都归于本人" in source
    assert ".replace(/倒灌/g,'归入')" in source
    assert ".replace(/回填/g,'归入')" in source
    assert ".replace(/父链/g,'主链')" in source
    assert ".replace(/闭合/g,'形成')" in source
    assert "国家基本运行架构重构" in source
    assert "高能力档位下的重大负向统帅案例" in source
    assert "当时可确认的外部等效控制记录" in source
    assert ".replace(/刷分/g,'重复计分')" in source
    assert ".replace(/底账/g,'结算材料')" in source
    assert "机械(?=计数|叠加|相加|换档|提高|降低|下降|映射|等价|当作)" in source
    assert "([SABCDE][+−-]?)门" in source
    assert "prose(impactPublicText(r.actual_use||'未另列说明'))" in source
    assert ".replace(/项目正式结算显示/g,'正式结算材料显示')" in source
    assert ".replace(/项目重审/g,'复核材料')" in source
    assert ".replace(/重审/g,'复核')" in source
    assert ".replace(/现有硬证据/g,'现有明确证据')" in source
    assert ".replace(/硬证/g,'明确证据')" in source
    assert ".replace(/本轮/g,'当前材料')" in source
    assert "判断把握为中等，并保留明确边界" in source
    assert ".replace(/尚尚未/g,'尚未')" in source




def test_historical_impact_public_formatter_cleans_current_people_pool(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "impact-pool-leaks.cjs"
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/index.template.html','utf8');
const start=source.indexOf('function impactPublicText(t)');
const end=source.indexOf('\nfunction paradigmReceptionProse',start);
assert.ok(start>=0&&end>start,'impactPublicText fragment not found');

const letters={G5:'S',G4:'A',G3:'B',G2:'C',G1:'D',G0:'E'};
const shortNames={M1:'军事统帅',M2:'外交博弈',M4:'内部联盟',M5:'组织执行',C1:'战略判断',C2:'学习纠错',C3:'用人授权',C4:'制度设计',C5:'权力运用与克制'};
const readingTerms={PS0:'仅有结果或资源背景',PS1:'局部正确选择',PS2:'完整独立决策周期',PS3:'可跨情境迁移的强模式',PS4:'不同约束下反复兑现的罕见模式',DW0:'未能归责本人的负面结果',DW1:'已纠正且未复发的局部误判',DW2:'造成显著损失但已恢复或未同类复发的错误',DW3:'同类机制重复失败、反馈后加码或优势下崩盘',DW4:'跨机制与阶段的稳定失能',AM1:'局部制度接口',AM2:'全国重要子系统',AM3:'国家核心系统',AM4:'国家基本运行架构重构'};
const grade=a=>letters[a.axis_grade]+({LOW:'−',MID:'',HIGH:'+'}[a.position]||'');
const ctx={letters,shortNames,readingTerms,grade};
vm.createContext(ctx);
vm.runInContext(source.slice(start,end)+';this.impactPublicText=impactPublicText;this.impactDimensionPublicText=impactDimensionPublicText;',ctx);

const forbidden=[
  /V\d+(?:\.\d+)+/i,
  /硬门/,
  /(?:补档|加档)/,
  /去名测试/,
  /底账/,
  /(?:回填|倒灌)/,
  /父链/,
  /消费/,
  /刷(?:分|档)/,
  /横校/,
  /上收/,
  /闭合/,
  /机械(?:计数|叠加|相加|换档|提高|降低|下降|映射|等价|当作)/,
  /external_equivalent_block/,
  /\bDECISIVE_DRIVER\b/,
  /\bFULL\b/,
  /\b(?:PS[0-4]|DW[0-4]|AM[1-4]|MI[1-4](?:_[A-Z_]+)?|G[0-5](?:[- /](?:LOW|MID|HIGH))?)\b/,
  /(?<![A-Za-z0-9_.-])(?:M[1245]|C[1-5])(?![A-Za-z0-9_.-])/,
  /\bO[0-3](?:-[A-Z])?\b/,
  /\bEN\d\b/,
  /\bN\d\b/,
  /硬证/,
  /重审/,
  /项目正式结算/,
  /本轮/,
  /按中置信有界发布/,
  /尚尚未/,
  /闭环/,
  /合同/,
  /机械/,
  /重裁/,
  /门槛/
];

const violations=[];
function assertClean(value,where,{transform=true}={}){
  if(value==null||value==='')return;
  const out=transform?ctx.impactPublicText(String(value)):String(value);
  for(const pattern of forbidden){
    if(pattern.test(out)){
      violations.push(where+' ['+String(pattern)+'] => '+out);
      break;
    }
  }
}

for(const filename of fs.readdirSync('reader/data/people').filter(name=>name.endsWith('.json')).sort()){
  const record=JSON.parse(fs.readFileSync('reader/data/people/'+filename,'utf8')).record||{};
  const h=record.impact;
  if(!h)continue;
  const root=filename+':'+(record.ruler_name||record.ruler_id||'?');

  for(const [key,value] of Object.entries({
    public_total_basis:h.public_total_basis,
    impact_nature_basis:h.impact_nature_basis,
    nearest_feasible_counterfactual:h.nearest_feasible_counterfactual,
    functional_alternative:h.counterfactual_entry?.functional_alternative,
    personal_causal_boundary:h.personal_causal_boundary,
    public_boundary:h.public_boundary,
    confidence_basis:h.confidence_basis,
  })) assertClean(value,root+':'+key);

  for(const [key,dimension] of Object.entries(h.dimensions||{})){
    const shown=ctx.impactDimensionPublicText(key,dimension?.public_basis||'');
    assertClean(shown,root+':dimension.'+key+'.public_basis',{transform:false});
    if(key==='paradigm'&&/^范式[SABCDE](?:[+−-])?[。；:]?/.test(shown)){
      violations.push(root+': duplicated paradigm grade => '+shown);
    }
    assertClean(dimension?.boundary_note,root+':dimension.'+key+'.boundary_note');
  }
  for(const [index,chain] of (h.macro_chains||[]).entries()){
    assertClean(chain?.title,root+':macro_chains['+index+'].title');
    assertClean(chain?.narrative,root+':macro_chains['+index+'].narrative');
  }
  for(const [index,reception] of (h.paradigm_review?.receptions||[]).entries()){
    assertClean(reception?.receiver,root+':reception['+index+'].receiver',{transform:false});
    assertClean(reception?.carrier,root+':reception['+index+'].carrier',{transform:false});
    assertClean(reception?.actual_use,root+':reception['+index+'].actual_use');
  }
}
assert.equal(violations.length,0,violations.slice(0,80).join('\n\n'));
''',encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr



def test_profile_public_formatter_cleans_current_people_pool(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "profile-pool-leaks.cjs"
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/index.template.html','utf8');
const start=source.indexOf('function profilePublicPattern(value)');
const end=source.indexOf('\nfunction profileSourceMarkup',start);
assert.ok(start>=0&&end>start,'profilePublicPattern fragment not found');

const shortNames={M1:'军事统帅',M2:'外交博弈',M4:'内部联盟',M5:'组织执行',C1:'战略判断',C2:'学习纠错',C3:'用人授权',C4:'制度设计',C5:'权力运用与克制'};
const materialIntensityNames={
  MI1:'单一情境',MI1_CASE:'单一情境',
  MI2:'完整生命周期情境',MI2_LIFECYCLE:'完整生命周期情境',
  MI3:'持续系统性情境',MI3_SUSTAINED_SYSTEMIC:'持续系统性情境',
  MI4:'跨阶段系统性情境',MI4_CROSS_PHASE_SYSTEMIC:'跨阶段系统性情境'
};
const formalDirectionNames={
  POSITIVE:'正向',NEGATIVE:'负向',MIXED_POSITIVE:'正向为主',MIXED_NEGATIVE:'负向为主',
  MIXED_BALANCED:'正负并存',MIXED:'正负并存',LIMITATION:'限制'
};
const readingTerms={
  PS0:'仅有结果或资源背景',PS1:'局部正确选择',PS2:'完整独立决策周期',
  PS3:'可跨情境迁移的强模式',PS4:'不同约束下反复兑现的罕见模式',
  DW0:'未能归责本人的负面结果',DW1:'已纠正且未复发的局部误判',
  DW2:'造成显著损失但已恢复或未同类复发的错误',
  DW3:'同类机制重复失败、反馈后加码或优势下崩盘',DW4:'跨机制与阶段的稳定失能',
  AM1:'局部制度接口',AM2:'全国重要子系统',AM3:'国家核心系统',AM4:'国家基本运行架构重构'
};
const letters={G5:'S',G4:'A',G3:'B',G2:'C',G1:'D',G0:'E'};
const grade=a=>letters[a.axis_grade]+({LOW:'−',MID:'',HIGH:'+'}[a.position]||'');
function readerText(t){
  return String(t??'')
    .replace(/\b(?:PS[0-4]|DW[0-4]|AM[1-4])\b/g,k=>readingTerms[k])
    .replace(/\b(?:MI1(?:_CASE)?|MI2(?:_LIFECYCLE)?|MI3(?:_SUSTAINED_SYSTEMIC)?|MI4(?:_CROSS_PHASE_SYSTEMIC)?)\b/g,k=>materialIntensityNames[k]||k)
    .replace(/\b(?:POSITIVE|NEGATIVE|MIXED_POSITIVE|MIXED_NEGATIVE|MIXED_BALANCED|MIXED|LIMITATION)\b/g,k=>formalDirectionNames[k]||k)
    .replace(/G([0-5])[- /]*(LOW|MID|HIGH)/g,(_,g,p)=>grade({axis_grade:'G'+g,position:p}))
    .replace(/G([0-5])/g,(_,g)=>letters['G'+g]+'档')
    .replace(/EPISODE_TAG/g,'局部情境证据')
    .replace(/BOUNDED_PROFILE/g,'有明确适用边界的画像')
    .replace(/FULL_GRADE/g,'完整定档')
    .replace(/\bE1\b/g,'少量情境材料')
    .replace(/\bE2\b/g,'多个独立情境材料')
    .replace(/\bE3\b/g,'主要命题已有代表性材料')
    .replace(/\bC5\b/g,'权力运用与克制')
    .replace(/COUNTEREVIDENCE_FOUND/g,'已找到明确反例');
}
const ctx={shortNames,materialIntensityNames,formalDirectionNames,readingTerms,letters,grade,readerText};
vm.createContext(ctx);
vm.runInContext(source.slice(start,end)+';this.profilePublicPattern=profilePublicPattern;',ctx);

const forbidden=[
  /\b(?:MI1(?:_CASE)?|MI2(?:_LIFECYCLE)?|MI3(?:_SUSTAINED_SYSTEMIC)?|MI4(?:_CROSS_PHASE_SYSTEMIC)?)\b/,
  /\b(?:PS[0-4]|DW[0-4]|AM[1-4])\b/,
  /\bG[0-5](?:[- /](?:LOW|MID|HIGH))?\b/,
  /(?<![A-Za-z0-9_.-])(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)(?![A-Za-z0-9_.-])/,
  /\bN[1-5](?:-(?:LOW|MID|HIGH))?\b/,
  /\bREV1\b/,
  /\b(?:DIRECT_COMMAND|OPERATIONAL_COORDINATION|STRATEGIC_DIRECTION|NOMINAL_AUTHORIZATION|ROLE_UNRESOLVED|ROLE_SEMANTIC_CONFLICT)\b/,
  /\b(?:TRUTH_ACQUISITION|REFUSAL_OR_RECURRENCE|BACKGROUND_VALIDATION|AXIS_OUT_WITH_REASON)\b/,
  /\b(?:FORMAL_CURRENT|SCORING_PARENT|UNRESOLVED_NEGATIVE_CANDIDATE|UNRESOLVED_EVIDENCE_GAP|SOURCE_DENSITY_ASYMMETRY_REVIEW)\b/,
  /\b(?:VERY_DEEP_MERIT_FLOOR|VERY_DEEP_EXPRESSION_FLOOR|EXTREME_DEEP_FLOOR|DEEP_FLOOR)\b/,
  /\b(?:WARLORD-IMPUNITY|ARMY-IMPUNITY|OPERATING_SELF_BINDING_INSTITUTION|DEEP_FAMILY_EXPANSION|EXTENDED_CLAN_PURGE|EXTENDED_FAMILY_PURGE|FAMILY_CHAIN_DEEP_FLOOR|CLAN_EXTINCTION_EXTREME_FLOOR)\b/,
  /\b(?:SOURCE_CONFLICT|SUPPORTING_ONLY|POLITICAL_STRUGGLE|BORDERLINE|ATTRIBUTION_LIMITED|ATTRIBUTION_CONFLICT|PARTICIPATION_SCOPE_UNCERTAIN|SELF_CAUSED|NO_FAULT|EVIDENCE_LIMITED_ATTRIBUTION|EVIDENCE_LIMITED_POWER|POWER_CONSTRAINED|CONTESTED_OR_SHARED_ATTRIBUTION)\b/,
  /\b(?:R1_LIMITED|R2_BOUNDED|R3_BROAD|R4_SYSTEMIC_EXTREME)\b/,
  /\b(?:PROBLEM_PRIORITY|GOAL_RESOURCE_FIT|RISK_OPTIONALITY|FEEDBACK_RECOURSE|ERROR_CORRECTION|GENERAL_JUDICIAL_GOVERNANCE|ACTIVE_SELF_RESTRAINT|STOPLOSS|CLAN_EXPANSION|UNEQUAL-LAW)\b/,
  /\bFORMAL-V\d+(?:\.\d+)?\b/,
  /\bV\d+(?:\.\d+)+\b/,
  /父链/,
  /硬门/,
  /横校/,
  /刷档/,
  /整改前/,
  /规范池/,
  /事件准入截止线/,
  /底账/,
  /倒灌/,
  /回填/,
  /分账/,
  /重裁/,
  /闭合/,
  /本轮/,
  /准入/,
  /窗口门/,
  /M5\/A4/,
  /A4\/A5投入/,
  /第三项A1/,
  /第三项正式结算显示安全态势A1/,
  /正链/,
  /负链/,
  /构念/,
  /硬伤/,
  /底盘/,
  /闭环/,
  /路由/,
  /切片/,
  /命题/,
  /复验/,
  /机械/,
  /锚/,
  /门槛/,
  /尚尚未/,
  /整改/,
  /高档审计/,
  /拆票/,
  /按合同/,
  /纳入判断合同/,
  /组织执行合同/,
  /审计/,
  /附件终审/,
  /本批/,
  /跨轴/,
  /项目内部联盟\/军事统帅/,
  /按武将登记逐项复核/,
  /`/,
  /\*\*/,
  /[SABCDE][+−-]?\s*(?:\/|／)\s*\d+(?:\.\d+)?\b/,
  /[SABCDE][+−-]?（\d+(?:\.\d+)?）/
];

const violations=[];
function inspect(value,where){
  if(value==null||value==='')return;
  const out=ctx.profilePublicPattern(String(value));
  for(const pattern of forbidden){
    if(pattern.test(out)){
      violations.push(where+' ['+String(pattern)+'] => '+out);
      break;
    }
  }
}

function inspectContext(c,where){
  if(!c||typeof c!=='object')return;
  for(const key of ['title','mechanism','cycle_basis','basis','intensity_and_role_basis','attribution','attribution_basis','role_attribution','limitations','limitation']){
    const value=c[key];
    if(Array.isArray(value)) value.forEach((v,i)=>inspect(v,where+'.'+key+'['+i+']'));
    else inspect(value,where+'.'+key);
  }
}

for(const filename of fs.readdirSync('reader/data/people').filter(name=>name.endsWith('.json')).sort()){
  const record=JSON.parse(fs.readFileSync('reader/data/people/'+filename,'utf8')).record||{};
  if(record.supplementary)continue;
  for(const [axisCode,a] of Object.entries(record.axes||{})){
    const root=filename+':'+(record.ruler_name||record.ruler_id||'?')+':'+axisCode;
    for(const key of ['typical_pattern','grade_basis','position_basis','evidence_assessment_basis','applicability_basis','not_applicable_reason']){
      inspect(a?.[key],root+':'+key);
    }
    for(const [i,value] of (Array.isArray(a?.limitations)?a.limitations:[]).entries()) inspect(value,root+':limitations['+i+']');
    if(typeof a?.counterpattern==='string')inspect(a.counterpattern,root+':counterpattern');

    const scope=a?.evidence_scope||{};
    for(const key of ['material_coverage_basis','ability_evidence_label','attribution_boundary','confidence_basis','grade_boundary']){
      inspect(scope[key],root+':evidence_scope.'+key);
    }

    inspect(a?.m1_stability_review?.basis,root+':m1_stability_review.basis');
    for(const [i,item] of (a?.m1_stability_review?.cases||[]).entries()){
      for(const key of ['label','consequence','attribution','feedback','recovery','residual_loss','decision_basis']){
        inspect(item?.[key],root+':m1_stability_review.cases['+i+'].'+key);
      }
    }

    for(const [i,c] of (a?.representative_contexts||[]).entries()) inspectContext(c,root+':representative_contexts['+i+']');
    for(const [id,c] of Object.entries(a?.context_lookup||{})) inspectContext(c,root+':context_lookup.'+id);
    for(const [i,point] of (a?.public_evidence_points||[]).entries()){
      inspect(point?.title,root+':public_evidence_points['+i+'].title');
      inspect(point?.details,root+':public_evidence_points['+i+'].details');
    }

    const noGrade=a?.no_grade_closure||{};
    for(const key of ['review_scope','evidence_gap','reopen_condition']) inspect(noGrade[key],root+':no_grade_closure.'+key);
  }
}
assert.equal(violations.length,0,violations.slice(0,100).join('\n\n'));
''',encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr



def test_profile_adjudication_deduplicates_grade_basis_when_it_repeats_primary_pattern(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "profile-dedup.cjs"
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/index.template.html','utf8');

const shortNames={M1:'军事统帅',M2:'外交博弈',M4:'内部联盟',M5:'组织执行',C1:'战略判断',C2:'学习纠错',C3:'用人授权',C4:'制度设计',C5:'权力运用与克制'};
const materialIntensityNames={MI1:'单一情境',MI1_CASE:'单一情境',MI2:'完整生命周期情境',MI2_LIFECYCLE:'完整生命周期情境',MI3:'持续系统性情境',MI3_SUSTAINED_SYSTEMIC:'持续系统性情境',MI4:'跨阶段系统性情境',MI4_CROSS_PHASE_SYSTEMIC:'跨阶段系统性情境'};
const formalDirectionNames={POSITIVE:'正向',NEGATIVE:'负向',MIXED_POSITIVE:'正向为主',MIXED_NEGATIVE:'负向为主',MIXED_BALANCED:'正负并存',MIXED:'正负并存',LIMITATION:'限制'};
const readingTerms={PS0:'仅有结果或资源背景',PS1:'局部正确选择',PS2:'完整独立决策周期',PS3:'可跨情境迁移的强模式',PS4:'不同约束下反复兑现的罕见模式',DW0:'未能归责本人的负面结果',DW1:'已纠正且未复发的局部误判',DW2:'造成显著损失但已恢复或未同类复发的错误',DW3:'同类机制重复失败、反馈后加码或优势下崩盘',DW4:'跨机制与阶段的稳定失能',AM1:'局部制度接口',AM2:'全国重要子系统',AM3:'国家核心系统',AM4:'国家基本运行架构重构'};
const letters={G5:'S',G4:'A',G3:'B',G2:'C',G1:'D',G0:'E'};
const grade=a=>letters[a.axis_grade]+({LOW:'−',MID:'',HIGH:'+'}[a.position]||'');
function readerText(t){return String(t??'').replace(/\b(?:PS[0-4]|DW[0-4]|AM[1-4])\b/g,k=>readingTerms[k]).replace(/\b(?:MI1(?:_CASE)?|MI2(?:_LIFECYCLE)?|MI3(?:_SUSTAINED_SYSTEMIC)?|MI4(?:_CROSS_PHASE_SYSTEMIC)?)\b/g,k=>materialIntensityNames[k]||k).replace(/\b(?:POSITIVE|NEGATIVE|MIXED_POSITIVE|MIXED_NEGATIVE|MIXED_BALANCED|MIXED|LIMITATION)\b/g,k=>formalDirectionNames[k]||k).replace(/G([0-5])[- /]*(LOW|MID|HIGH)/g,(_,g,p)=>grade({axis_grade:'G'+g,position:p})).replace(/G([0-5])/g,(_,g)=>letters['G'+g]+'档').replace(/EPISODE_TAG/g,'局部情境证据').replace(/BOUNDED_PROFILE/g,'有明确适用边界的画像').replace(/FULL_GRADE/g,'完整定档').replace(/\bE1\b/g,'少量情境材料').replace(/\bE2\b/g,'多个独立情境材料').replace(/\bE3\b/g,'主要命题已有代表性材料').replace(/\bC5\b/g,'权力运用与克制').replace(/COUNTEREVIDENCE_FOUND/g,'已找到明确反例')}
const start=source.indexOf('function profilePublicPattern(value)');
const end=source.indexOf('\nfunction profileSourceMarkup',start);
assert.ok(start>=0&&end>start);
const ctx={shortNames,materialIntensityNames,formalDirectionNames,readingTerms,letters,grade,readerText};
vm.createContext(ctx);
vm.runInContext(source.slice(start,end)+';this.profileDistinctGradeBasis=profileDistinctGradeBasis;this.profilePositionPublicPattern=profilePositionPublicPattern;this.profileDistinctPositionBasis=profileDistinctPositionBasis;this.profileDistinctLimitations=profileDistinctLimitations;',ctx);

const same='方面军识别、接替和授权长期稳定，且对失败将领多能重配而非机械清洗；行政用人亦有正面基础。';
assert.equal(ctx.profileDistinctGradeBasis('G4-MID：'+same,same),'');
assert.equal(
  ctx.profileDistinctGradeBasis('G4-LOW：G4门槛复核：王翦复起与逐客令撤回分属军事、行政，两条链都不是单纯成功。','王翦复起与逐客令撤回分属军事、行政，两条链都不是单纯成功。'),
  ''
);
assert.equal(
  ctx.profileDistinctGradeBasis('G4-LOW：主要表现成立，但另有晚期反例，因此只取下沿。',same),
  'A−：主要表现成立，但另有晚期反例，因此只取下沿。'
);
assert.equal(
  ctx.profilePublicPattern('反向窗口已审阅但尚尚未形成；整改后恢复；现有高档审计只确认一条链。'),
  '反向窗口已审阅但尚未形成；调整后恢复；现有高档复核只确认一条链。'
);
assert.equal(
  ctx.profilePublicPattern('按A档纳入判断合同；不拆票凑A档；组织执行合同只约束本轴。'),
  '按A档判断规则；不把同一证据链拆成多条来提高到A档；组织执行规则只约束本轴。'
);
assert.equal(
  ctx.profilePublicPattern('附件终审逐人材料吸纳：某人是本批代表；跨轴补查显示项目内部联盟/军事统帅可以确认，诊断：局部正确选择。'),
  '某人是当前复核代表；补充核对显示人物画像“内部联盟”与“军事统帅”材料可以确认，判断：局部正确选择。'
);
assert.equal(
  ctx.profilePublicPattern('原战略判断既有情境材料已经不是单一链；正式战略判断几乎只计入终局事件；原E档过低。'),
  '既有战略判断材料已经不是单一链；既有战略判断主要只依据终局事件；此前E档过低。'
);
assert.equal(
  ctx.profilePublicPattern("'本轮按武将登记逐项复核：A/D3，某战役完成多路协同并形成高压逆转。卡内细节支持D3。，角色=commander_in_chief。某战役完成多路协同并形成高压逆转。卡内细节支持D3。'"),
  '当前按战役情境逐项核对：A档战役成果／多重重大约束的高压任务，某战役完成多路协同并形成高压逆转。卡内细节支持D3。，登记角色：最高指挥者。'
);
assert.equal(ctx.profileDistinctPositionBasis('MID：'+same,same,'G4-MID：'+same),'');
assert.equal(ctx.profileDistinctPositionBasis('档内中位：'+same,same,'G4-MID：'+same),'');
assert.equal(
  ctx.profileDistinctPositionBasis('LOW：主要表现成立，但晚期反例使其只能落在本档下沿。',same,''),
  '低位：主要表现成立，但晚期反例使其只能落在本档下沿。'
);
assert.equal(
  ctx.profilePositionPublicPattern('档内高位：规范池实际权力窗口为951-954，仅作主政背景；本裁决消费全生涯已闭合的可归责军事机会，不以该窗口作为事件准入截止线。；只在现行父链明确记录失败到达和后续调整时解释；本人归责和恢复是否发生分别判断，不虚构未发生的能力复验。；限制：材料底池已覆盖；本人能力外推须按已连接的实际角色和独立任务判断。'),
  '高位'
);
assert.equal(
  ctx.profileDistinctPositionBasis('档内高位：规范池实际权力窗口为951-954，仅作主政背景；本裁决消费全生涯已闭合的可归责军事机会，不以该窗口作为事件准入截止线。；只在现行父链明确记录失败到达和后续调整时解释；本人归责和恢复是否发生分别判断，不虚构未发生的能力复验。；限制：材料底池已覆盖。','',''),
  ''
);
assert.equal(
  ctx.profileDistinctPositionBasis('档内中位：规范池实际权力窗口为1722—1735年，仅作主政背景；本裁决消费全生涯已闭合的可归责军事机会，不以该窗口作为事件准入截止线。；准噶尔战争的大军重败与指挥层折损已经到达最高决策层，后续惩处将领并转向议和，但未在任内完成同方向军事恢复；属于可用机制仍存、重大授权判断明显失衡。；限制：亲临统帅不可观察。','',''),
  '中位：准噶尔战争的大军重败与指挥层折损已经到达最高决策层，后续惩处将领并转向议和，但未在任内完成同方向军事恢复；属于可用机制仍存、重大授权判断明显失衡。'
);
assert.equal(
  ctx.profileDistinctPositionBasis('档内中位：只计十年准备、用人配置和最终下令，不把六路前线解题归给皇帝。；本人无临阵角色，成功高度依赖羊祜、杜预、王濬等；战略设计偏强但不达到历史级全机制。；限制：可归责强军事表现集中于同一任务或生命周期。','',''),
  '中位：只计十年准备、用人配置和最终下令，不把六路前线解题归给皇帝。；本人无临阵角色，成功高度依赖羊祜、杜预、王濬等；战略设计偏强但不达到历史级全机制。'
);
const duplicateLimitation='军事授权和行政正链均强，但最高中枢配置连续失稳，纠偏后也未恢复稳定高授权责任中心。';
assert.deepEqual(
  ctx.profileDistinctLimitations([duplicateLimitation,'另有一条独立证据边界。'],duplicateLimitation,''),
  ['另有一条独立证据边界。']
);
assert.deepEqual(
  ctx.profileDistinctLimitations(['短边界仍应保留。'],'这是一段很长的主要表现，但不包含短边界内容。',''),
  ['短边界仍应保留。']
);
assert.equal(
  ctx.profileDistinctLimitations('同一完整限制句已经在主要表现中明确出现，并且没有增加新的证据边界或反例。','主要表现前文；同一完整限制句已经在主要表现中明确出现，并且没有增加新的证据边界或反例。',''),
  ''
);
''',encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_profile_primary_pattern_hides_internal_summary_labels():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "function profilePublicPattern(value)" in source
    assert "帝国基础架构能力突出；后世影响力不直接换算为本轴能力" in source
    assert "本轴存在明确的低档反向制度表现" in source
    assert "武举与监察重组形成正向制度建设，同时告密—酷吏机制构成强反例" in source
    assert "科举与法源恢复形成正向制度建设，但货币与军政架构存在明显失配" in source
    assert "prose(profilePublicPattern(a.typical_pattern" in source


def test_first_item_commander_explains_why_profile_m1_may_differ():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader/person-readability.js").read_text(encoding="utf-8")
    expected = "人物画像“军事统帅”是独立能力轴，事件范围与归责门槛不同，两者不能按档位或分数直接换算"
    assert expected in home
    assert "first-item-cross-system-note" in home
    assert expected not in person
    assert "first-item-cross-system-note" not in person



def test_second_item_group_intros_explain_scope_without_repeating_current_subtotals():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    reading = (root / "reader/second-item-reading.js").read_text(encoding="utf-8")
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")

    assert '当前得分为 ${fmt(t.methodScore)} / 165' not in reading
    assert '四项合计为 ${fmt(t.resultScore)} / 202' not in reading
    assert '最终得分 ${fmt(score)} / 20' not in reading
    assert '当前合计 ${fmt(values.method)} 分' not in alias
    assert '当前合计 ${fmt(values.finance)} 分' not in alias

    assert '制度与行政<b>${fmt(t.methodScore)} / 165</b>' in reading
    assert '民生与社会<b>${fmt(t.resultScore)} / 202</b>' in reading
    assert '政权交接<b>${fmt(t.handoffScore)} / 20</b>' in reading
    assert '本组小计怎么形成？' in alias


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
    assert "最终等级仍按 E—S 表示" in source
    assert "当前人物：" in source
    assert "专项信用与负向调整均采用当前已确定值，不从最终分数反推" in source
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
    totals_start = source.index("function firstTotals(items)")
    overview_start = source.index("function firstItemOverview", totals_start)
    overview_end = source.index("async function renderFirstMajor", overview_start)
    first_totals = source[totals_start:overview_start]
    overview = source[overview_start:overview_end]

    assert "查看第一项完整折算公式" in first_totals
    assert "军事代价扣减 =" in first_totals
    assert "四轴毛分 =" not in overview
    assert "统一成果 ${score[0]} +" not in overview
    assert "第一项结算分 <strong>${scoreNumber(netScore)} / 240</strong>" in overview



def test_first_item_applicability_is_three_state_and_never_inferred_from_items():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader/person-readability.js").read_text(encoding="utf-8")
    template = (root / "reader/index.template.html").read_text(encoding="utf-8")

    assert '"NOT_APPLICABLE"' in home
    assert '"APPLICABLE"' in home
    assert "第一项正式适用状态" in home
    assert "items.every(item =>" not in home
    assert "buildNetReading" not in person
    assert "正式适用状态未发布，因此不作适用性推断" in template
    assert "阅读层不判断" not in template
    assert "n.first_item_status==='NOT_APPLICABLE'" in template

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
    assert "const adjustment = finiteNetNumber(record.net?.fourth_item_adjustment);" in source
    assert "Number(record.net?.fourth_item_adjustment) === 0" not in source
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



def test_reader_notices_avoid_internal_system_voice_and_paths():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    template = (root / "reader/index.template.html").read_text(encoding="utf-8")
    home = (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "该历史引用暂不可打开" in template
    assert "当前文件不可用" not in template
    assert "历史引用（当前文件不可用）" not in template
    assert "正式记录未提供本人统帅的公开说明。" in home
    assert "公开说明尚未同步" not in home
    assert "阅读层不判断" not in home
    assert "阅读层不根据" not in home
    assert "阅读层不作默认判断" not in home
    assert "因此不作适用性推断" in home
    assert "因此不作默认推断" in home


def test_reader_guide_explains_material_strength_badges_are_formal_record_only():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "只有正式记录明确发布相应字段时页面才展示" in template
    assert "没有这类标签只表示正式记录未发布该字段，不等于证据弱" in template
    assert "页面也不会自行补判" in template
    assert "上游没有发布" not in template


def test_second_item_compare_enhancers_accept_public_breakdown_row_title():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    reading = (root / "reader/second-item-reading.js").read_text(encoding="utf-8")
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert '["分项构成","构成与依据"].includes' in reading
    assert '["分项构成", "构成与依据"].includes' in alias


def test_person_reading_note_overviews_avoid_project_workflow_language():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "reader/person-reading-notes.json").read_text(encoding="utf-8"))
    forbidden = ("正式记录", "回填", "倒灌", "闭合", "整改", "本项", "该项", "项目同时", "现有裁决", "正式裁决", "现有结算", "正式画像", "提前计入", "取证", "复验", "正式评价", "评价依据", "归责")
    for ruler_id, notes in payload["records"].items():
        for key, block in notes["overview"].items():
            for token in forbidden:
                assert token not in block["text"], f"{ruler_id}:{key} => {token}: {block['text']}"

    runtime = (root / "reader/person-reading-notes.js").read_text(encoding="utf-8")
    for token in forbidden:
        assert token in runtime
    assert "项目现有记录中的定位语句" not in runtime
    assert "本段提要对应的定位语句" in runtime


def test_stale_editorial_overviews_are_not_exposed_as_public_status():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/person-reading-notes.js").read_text(encoding="utf-8")
    assert "这段阅读提要待复核" not in source
    assert "阅读提要暂未加载" not in source
    assert 'if (assessBlock(block, record).status !== "current") return null;' in source
    assert "if (block) panel.querySelector" in source


def test_third_item_percentages_are_labeled_as_composite_adoption_rates():
    from pathlib import Path
    home = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    person = (Path(__file__).resolve().parents[1] / "reader/person-readability.js").read_text(encoding="utf-8")
    assert 'groupKey === "strategic" && item.unit === "%" && ["B1","B2","B4"].includes(item.label)' in home
    assert "合成采用 ${Number(item.value)}%" in home
    assert "buildNetReading" not in person
    assert "合成采用 ${esc(String(Number(item.value)))}%" in template
    assert "参与合成，不单列分值" in home
    assert "参与合成，不单列分值" in template



def test_person_compact_net_summary_prefers_public_third_and_fourth_item_status(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "compact-net-public-value.cjs"
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/home-interactions.js','utf8');
const start=source.indexOf('  const FIRST_COMPACT_LABELS =');
const end=source.indexOf('\n  function compactNetReading(',start);
assert.ok(start>=0&&end>start);
const ctx={
  netValue:(item,key)=>item.value==null?'参与合成，不单列分值':(item.unit==='%'?'合成采用 '+item.value+'%':item.value+' 分'),
  thirdItemPublicText:(item,value)=>String(value||'').replace('第4级','A档').replace('第1级','D档'),
  civilizationPublicStatus:(item,value)=>String(value||''),
  finiteNetNumber:value=>value==null?null:Number(value)
};
vm.createContext(ctx);
vm.runInContext(source.slice(start,end)+';this.compactNetPublicValue=compactNetPublicValue;this.compactNetPublicLabel=compactNetPublicLabel;',ctx);

assert.equal(
  ctx.compactNetPublicValue({label:'C1实战交付',value:null,unit:'不单独计分',public_level_label:'实战任务交付为第4级'},'military'),
  '实战任务交付为A档'
);
assert.equal(
  ctx.compactNetPublicValue({label:'B1',value:37,unit:'%',public_level_label:'当前结果为第1级、中位'},'strategic'),
  '当前结果为D档、中位 · 合成采用 37%'
);
assert.equal(ctx.compactNetPublicLabel({label:'A统一贡献'},'first'),'统一成果');
assert.equal(ctx.compactNetPublicLabel({label:'B1创业难度与效率'},'first'),'起点、强敌与速度');
assert.equal(ctx.compactNetPublicLabel({label:'B2组织与整合'},'first'),'创业组织与政治整合');
assert.equal(ctx.compactNetPublicLabel({label:'C军事统帅与战争解题'},'first'),'本人统帅');
assert.equal(ctx.compactNetPublicLabel({label:'军事成本扣分'},'first'),'军事代价');
assert.equal(ctx.compactNetPublicLabel({label:'A制度建设'},'method'),'制度建设与实际运行');
assert.equal(ctx.compactNetPublicLabel({label:'B1官僚治理'},'method'),'官僚治理与行政执行');
assert.equal(ctx.compactNetPublicLabel({label:'C1民生'},'finance'),'民生状况');
assert.equal(ctx.compactNetPublicLabel({label:'C4恢复与成本'},'finance'),'恢复能力与额外代价');
assert.equal(ctx.compactNetPublicLabel({label:'D1继任行政连续性'},'handoff'),'继任后的行政连续性');
assert.equal(ctx.compactNetPublicLabel({label:'D3政权交接稳定'},'handoff'),'政权交接稳定性');
assert.equal(ctx.compactNetPublicValue({label:'军事成本扣分',value:27,unit:'分'},'first'),'扣 27 分');
assert.equal(
  ctx.compactNetPublicValue({value:0,unit:'分',public_level_label:'正负相抵 · 净调整为0'},'civilization'),
  '正负相抵 · 净调整为0'
);
assert.equal(
  ctx.compactNetPublicValue({value:0,unit:'分',public_level_label:'没有确认独立变化'},'civilization'),
  '没有确认独立变化'
);
assert.equal(
  ctx.compactNetPublicValue({value:6,unit:'分',public_level_label:'正向 · 局部变化'},'civilization'),
  '正向 · 局部变化 · 6 分'
);
''',encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr

    source = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8")
    compact = source[source.index("const FIRST_COMPACT_LABELS"):source.index("function cleanNetText")]
    assert "thirdItemPublicText(item, item?.public_level_label || \"\")" in compact
    assert "civilizationPublicStatus(item, item?.public_level_label || \"\")" in compact
    assert "compactNetPublicLabel(item, key)" in compact
    assert "publicNetComponentLabel(item)" in source
    assert "const displayLabel = publicNetComponentLabel(item);" in source
    assert "esc(publicNetComponentLabel(item))" in source
    assert "compactNetPublicValue(item, key)" in compact


def test_third_public_level_heading_drops_redundant_current_result_prefix():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'formalLevel.replace(/^当前结果为\\s*/, "")' in source
    assert 'const repeatedPrefix = displayLabel + "为";' in source
    assert "formalLevelBase.startsWith(repeatedPrefix)" in source
    assert '当前判断：${esc(formalLevelDisplay)}' in source
    assert '当前判断：${esc(formalLevel)}' not in source


def test_fourth_item_group_heading_is_not_identical_to_page_title():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'title: "第四项 · 文明与国家整合"' in source
    assert 'civilization: "文明与国家整合 · 分项结算"' in source


def test_first_item_public_copy_uses_settlement_score_not_legacy_net_benefit_term():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel in ("reader/home-interactions.js", "reader/person-readability.js", "reader/index.template.html"):
        source = (root / rel).read_text(encoding="utf-8")
        assert "原始净收益" not in source
    assert "第一项结算分" in (root / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "buildNetReading" not in (root / "reader/person-readability.js").read_text(encoding="utf-8")


def test_third_item_score_explanations_avoid_release_process_language():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")

    for phrase in ("页面不自行反推中间值", "当前人物正式结算记录", "两轴小计正式记录", "正式合成结果", "当前本项："):
        assert phrase not in source
    for phrase in ("最终等级仍按 E—S 表示", "专项信用与负向调整均采用当前已确定值", "当前两轴小计：", "当前合成结果为", "当前结果说明："):
        assert phrase in source


def test_third_item_reader_separates_scoring_chains_and_exposes_intermediate_totals():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "function thirdMajorGroups(record, details)" in source
    for phrase in ("安全状态变化", "控制成果质量", "军事体系表现", "军事代价"):
        assert phrase in source
    assert "不是领土占比、现实概率或独立得分" in source
    assert 'const THIRD_MILITARY_SYSTEM_LABELS = ["C1实战交付","C2持续作战","C3体系可靠性"]' in source
    assert "function thirdMilitarySharedSummary(items)" in source
    assert "function thirdMilitarySharedEvidence(items)" in source
    assert "function thirdMilitarySystemCards(record, items)" in source
    assert "军事体系共同裁决摘要" in source
    assert "军事体系共同裁决依据" in source
    assert 'reader_public_evidence_items:[], reader_highlights:[]' in source
    assert 'return metricDetail(publicItem, record, "military");' in source
    assert "${thirdMilitarySystemCards(record, military)}" in source
    assert 'thirdCalculationRows(strategic, ["A120"]' in source
    assert 'thirdCalculationRows(strategic, ["B80"]' in source
    assert 'thirdCalculationRows(military, ["C50"]' in source
    assert 'thirdCalculationRows(military, ["实际扣分"]' in source
    assert 'thirdCalculationRows(military, ["第三项合计"]' in source
    assert 'military:new Set(["C50","实际扣分","第三项合计"])' in source


def test_third_item_military_system_shared_summary_deduplicates_repeated_prose(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    script = tmp_path / "third-military-shared-summary.cjs"
    script.write_text(r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/home-interactions.js','utf8');
const start=source.indexOf('  const THIRD_MILITARY_SYSTEM_LABELS');
const end=source.indexOf('\n  function thirdCalculationRows',start);
assert.ok(start>=0&&end>start,'third military helper fragment');
const calls=[];
const api=new Function(
  'thirdItemPublicText','cleanNetText','metricDetail','prose',
  source.slice(start,end)+';return {thirdMilitarySharedSummary,thirdMilitarySharedEvidence,thirdMilitarySystemCards};'
)(
  (item,value)=>String(value||''),
  value=>String(value||'').replace(/\s+/g,' ').trim(),
  item=>{calls.push(item);return '<card>'+item.label+'</card>';},
  value=>'<p>'+value+'</p>'
);
const labels=['C1实战交付','C2持续作战','C3体系可靠性'];
const common='共同依据：多个方向的成功与失败共同决定体系判断。';
const items=labels.map((label,index)=>{
  const boundary='边界'+index;
  return {
    label,
    reader_kind:'judgment',
    reader_summary:'该方面为'+['A','B','C'][index]+'档水平。'+common,
    reader_boundary:boundary,
    reader_public_evidence_items:[{
      public_label:label,
      public_role:label,
      public_basis:'该方面为'+['A','B','C'][index]+'档水平。'+common,
      public_boundary:boundary,
      public_tags:[],
      public_direction:'',
      public_source_coverage:''
    }]
  };
});
assert.equal(api.thirdMilitarySharedSummary(items),common);
assert.equal(api.thirdMilitarySharedEvidence(items),common);
const html=api.thirdMilitarySystemCards({},items);
assert.ok(html.includes('军事体系共同裁决依据'));
assert.equal(calls.length,3);
for(const item of calls){
  assert.equal(item.reader_summary,'');
  assert.deepEqual(item.reader_public_evidence_items,[]);
  assert.deepEqual(item.reader_highlights,[]);
}
calls.length=0;
items[2].reader_public_evidence_items[0].public_source_coverage='来源充分';
const fallback=api.thirdMilitarySystemCards({},items);
assert.ok(fallback.includes('军事体系共同裁决摘要'));
assert.ok(!fallback.includes('军事体系共同裁决依据'));
assert.equal(calls.length,3);
for(const item of calls)assert.equal(item.reader_public_evidence_items.length,1);
items[2]={...items[2],reader_summary:'该方面为C档水平。另一段专属依据。'};
assert.equal(api.thirdMilitarySharedSummary(items),'');
''',encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_compare_highlight_excludes_context_uncertainty_and_preserves_profile_evidence_strength():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    template = (root / "reader" / "index.template.html").read_text(encoding="utf-8")
    readability = (root / "reader" / "readability.js").read_text(encoding="utf-8")
    css = (root / "reader" / "readability.css").read_text(encoding="utf-8")

    block = template[template.index("function compare(){"):template.index("function guide()")]
    assert "突出当前展示值／档位差异" in block
    assert "不表示差异已经超出审慎位置投影、证据厚度或判断把握" in block
    assert "量级置信度" not in template
    assert ">置信度 " not in template
    assert "判断把握：" in template
    assert "row('掌权背景（各项范围另见依据）',r=>esc(r.actual_power_window||'未列'),false)" in block
    assert "row('判断把握',r=>conf(r.impact.confidence),false)" in block
    assert "row('影响性质',r=>esc(r.impact.impact_nature),false)" in block

    magnitude = block[block.index("row('历史影响量级'"):block.index("row('影响性质'")]
    assert "impact-grade" in magnitude
    assert "impact_nature" not in magnitude

    assert 'const coverage = summary.querySelector(".axis-evidence-level")?.textContent.trim() || "";' in readability
    assert "axisRecordForEvidence(summary.parentElement)" in readability
    assert "判断把握：" in readability
    assert 'meta.className = "compare-evidence-meta"' in readability
    assert ".compare-evidence-meta{" in css


def test_fourth_item_reader_distinguishes_zero_sources_and_rejects_progress_ranking_reading():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "不是文明程度或时代先进程度排名" in source
    assert "hasBalancedZero" in source
    assert "hasNoIndependentChange" in source
    assert "这些0的来源并不相同" in source
    assert "0不等于没有变化" in source
    assert "没有形成独立有符号调整" in source
    assert "废除诽谤、妖言罪的制度与受理边界变化已由相关治理材料承担" in source
    assert "不能证明已经形成实际反馈效果" in source
    assert "归入相关制度与社会治理材料" in source



def test_active_first_item_renderer_uses_public_formula_vocabulary():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    for forbidden in ("内部指标：A", "内部指标：B1", "内部指标：B2", "内部四项：A + B1 + B2 + C", "第一项净分 S1", "总榜附加分 F", "成果占比", "正向净收益"):
        assert forbidden not in source
    assert "本人成果规模" in source
    assert "不是共同项目分成，也不是领土、人口或军队比例" in source
    assert "统一成果分 = 120 × (min(1000, 本人有效控制成果值) / 1000)^0.65" in source
    assert "四轴毛分 = 统一成果 + 创业难度与效率 + 创业组织与整合 + 本人统帅" in source
    assert "第一项结算分 = max(0" in source
    assert "统治绩效附加 = 0.20 × 637 × (第一项结算分 / 240)^1.25" in source

def test_first_item_shared_project_percentage_is_labeled_as_allocation_share():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "reader" / "home-interactions.js").read_text(encoding="utf-8")
    person = (root / "reader" / "person-readability.js").read_text(encoding="utf-8")
    template = (root / "reader" / "index.template.html").read_text(encoding="utf-8")

    assert "本人成果规模" in home
    assert "全国核心统一尺度" in home
    assert "不是共同项目分成，也不是领土、人口或军队比例" in home
    assert "成果占比" not in home
    assert "正向净收益" not in home
    assert "buildNetReading" not in person
    assert "本项适用，但第一项结算分为0" in template
    assert "正向净收益" not in template


def test_finance_public_copy_collapses_repeated_no_low_point_phrase():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    start = source.index("function publicFinanceText(value)")
    end = source.index("function publicCalculationText(value)", start)
    block = source[start:end]
    assert "未另证独立有效低谷[：:]\\s*未另证独立有效低谷" in block
    assert "军事与边疆项的战略结果未单独计入" in block
    assert "直接等同" in source
    assert "因此整体判断上调" in source
    assert "压低当前等级的档内位置" in source
    assert "能够保留到任期结束的明确恢复" in block
    assert "可在任期结束确认的恢复" in block
    assert "不能把1127年的靖康终局倒推为赵佶1126年退位时的经济财政状态" in block
    assert "民生主要状态维持为“$1”" in block
    assert "现有证据尚不足" in block
    assert "按评价窗口，前者不计入本期" in block
    assert "不再作为独立低谷重复计入" in block
    assert "不再单列“重要地区或群体出现明显损害”" in block
    assert "function publicHandoffText(value)" in block
    assert "实际率领百官" in block
    assert "这只能证明部分行政承接" in block
    assert '.replace(/。、/g, "。")' in block
    assert '.replace(/。；/g, "；")' in block


def test_history_total_public_explanation_stays_on_public_scale():
    from pathlib import Path

    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index("function impactTotalPublicText(h)")
    end = template.index("function impactDimensionPublicText", start)
    block = template[start:end]
    assert "综合后公开等级为" in block
    assert "最终量级为" not in block
    assert "对应公开等级" not in block
    assert "政治范式[^。；]*(?:上调一档|提高一档)" in block
    assert "后世最高权力的实际接收证据足够强" in block
    assert "形成一档上调" in block
    assert "政治范式[^。；]*(?:不改变|不提高|仅修正|不再改变量级)" in block
    assert "本次没有单独改变前三项形成的综合判断" in block
    assert "prose(impactTotalPublicText(h))" in template
    assert "impactTechnicalHelp()" in template
    assert "总等级为什么和四维字母不同？" in template
    assert "同一个字母不能跨两套刻度直接比较" in template
    assert "最终内部裁判带" not in template
    public_copy = (Path(__file__).resolve().parents[1] / "reader/public-copy.json").read_text(encoding="utf-8")
    assert "这是离线交互设计样稿" not in public_copy
    assert "本站是正式结算数据的只读阅读层" not in public_copy
    assert "本页展示最近一次正式发布的结算数据" in template
    assert "正式记录更新后会在后续发布中同步" in template
    dimension_start = template.index("function impactDimensionPublicText")
    dimension_end = template.index("function paradigmReceptionProse", dimension_start)
    dimension = template[dimension_start:dimension_end]
    assert "text.replace(/^[SABCDE](?:[+−-])?[。；:]\\s*/" in dimension




def test_history_scale_note_is_not_repeated_on_person_or_standalone_impact_pages():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index("function historySections(")
    end = template.index("const format=", start)
    block = template[start:end]
    assert "${compact?impactScaleNote():''}" in block
    assert "${impactScaleNote()}<details class=\"impact-core-chains" not in block
    impact_start = template.index("function impactPanel(")
    impact_end = template.index("function m1FailureReview", impact_start)
    impact = template[impact_start:impact_end]
    assert "${impactScaleNote()}" in impact


def test_paradigm_reception_windows_are_secondary_collapsed_evidence():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index("function paradigmReceptionProse")
    end = template.index("function axisProse", start)
    block = template[start:end]
    assert '<details class="impact-receptions"><summary>查看实际接收窗口</summary>' in block
    assert '<details class="impact-receptions" open' not in block
    history_start = template.index("function historySections(")
    history_end = template.index("const format=", history_start)
    history = template[history_start:history_end]
    assert "const paradigmBody=`${prose(publicBasis('paradigm'))}${paradigmReceptionProse(paradigmReview)}" in history



def test_every_ranked_reader_record_has_prudent_score_and_rank_projection():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    ranked = 0
    for path in sorted((root / "reader/data/people").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8")).get("record") or {}
        net = record.get("net") or {}
        rank = net.get("rank")
        if not isinstance(rank, int):
            continue
        ranked += 1
        prefix = f"{path.name}:{record.get('ruler_name')}:rank={rank}"

        interval = net.get("prudent_score_interval")
        assert isinstance(interval, dict), prefix + ": missing prudent_score_interval"
        lower, upper = interval.get("lower"), interval.get("upper")
        assert isinstance(lower, (int, float)) and isinstance(upper, (int, float)), prefix + ": invalid prudent score bounds"
        assert lower <= upper, prefix + ": prudent score interval reversed"
        assert str(interval.get("basis") or "").strip(), prefix + ": prudent score basis missing"

        projection = net.get("prudent_rank_projection")
        assert isinstance(projection, dict), prefix + ": missing prudent_rank_projection"
        best, worst = projection.get("best"), projection.get("worst")
        assert isinstance(best, int) and isinstance(worst, int), prefix + ": invalid prudent rank bounds"
        assert 1 <= best <= worst, prefix + ": prudent rank projection reversed or out of range"
        assert str(projection.get("basis") or "").strip(), prefix + ": prudent rank basis missing"

    assert ranked > 0



def test_every_ranked_reader_record_has_governance_context():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    ranked = 0
    for path in sorted((root / "reader/data/people").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8")).get("record") or {}
        net = record.get("net") or {}
        if not isinstance(net.get("rank"), int):
            continue
        ranked += 1
        prefix = f"{path.name}:{record.get('ruler_name')}:rank={net.get('rank')}"
        context = net.get("governance_context")
        assert isinstance(context, dict), prefix + ": missing governance_context"
        assert str(context.get("scale_label") or "").strip(), prefix + ": missing scale_label"
        assert str(context.get("complexity_label") or "").strip(), prefix + ": missing complexity_label"
        assert str(context.get("basis") or "").strip(), prefix + ": missing governance context basis"

    assert ranked > 0


def test_prudent_evidence_details_hide_internal_grade_codes():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index("const prudentAxisNames=")
    end = template.index("function prudentPositionText", start)
    block = template[start:end]
    assert 'C1:"民生",C2:"经济财政",C3:"社会安全"' in block
    assert '0:"未见独立有效低谷"' in block
    assert '5:"严重军事成本",6:"极端军事成本"' in block
    assert "function prudentEndpointText" in block
    assert "function prudentCostText" in block
    assert "function prudentIssueText" in block
    assert "现有史料允许的审慎判断" in block
    assert "军事成本的审慎边界" in block
    assert "本轮合法端点" not in block
    assert "单命题条件分差" not in block
    assert "现有史料允许的审慎上端" in block
    assert "prudentGeneralText(a.public_basis)" in block
def test_net_panel_uses_public_component_names_in_total_formula():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index("function netPanel(r)")
    end = template.index("function impactPanel", start)
    block = template[start:end]
    assert "统治绩效总分 = 治国成效 + 军事与边疆 + 奠基与统一附加 + 文明与国家整合。" in block
    assert "DATA.formula" not in block

def test_prudent_rank_is_primary_and_formal_rank_is_point_estimate():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    template = (root / "reader/index.template.html").read_text(encoding="utf-8")
    css = (root / "reader/readability.css").read_text(encoding="utf-8")

    start = template.index("function netPositionSummary(n)")
    end = template.index("function netPanel(r)", start)
    block = template[start:end]
    assert "const lead=prudent?" in block
    assert "审慎位置" in block
    assert "规则点位 第" in block
    assert "<strong>正式第" not in block
    assert "正式第 ${" not in template
    assert "已闭合情景分数范围" not in template
    assert "已验证情景分数范围" in template
    assert "三体系总规则 ↗" in template
    assert "历史影响规则 ↗" in template
    assert "人物画像规则 ↗" in template
    assert "统治绩效规则 ↗" in template
    assert "入口配置 ↗" not in template

    assert 'class="home-net-rank"><strong>' in template
    assert 'class="home-formal-rank">规则点位 第' in template
    assert 'class="home-full-position"' in template
    assert "审慎位置、规则点位与治理背景" in template
    assert "页面优先展示这一范围" in template
    assert "主页面总分只显示1位小数以避免制造虚假精度" in template
    assert "排序与规则点位仍按未舍入的正式结算值计算" in template
    assert "非计分 · 未校准规模难度" in template
    assert "跨规模名次不能理解为已经消除治理难度差异" in template
    assert "当前榜单没有对区域、广域与超广域治理难度做分数校准" in template

    compare_start = template.index("function compare(){")
    compare_end = template.index("function guide()", compare_start)
    compare = template[compare_start:compare_end]
    assert "row('审慎位置投影'" in compare
    assert "row('规则点位（点估计）'" in compare
    assert "function governanceContextDiffers" not in compare  # helper is a const closure, not a global classifier
    assert "const governanceContextDiffers=()=>{" in compare
    assert "governanceCompareWarning=governanceContextDiffers()" in compare
    assert "当前统治绩效未对这些差异加权" in compare
    assert "治理背景（非计分；未校准规模难度）" in compare
    assert "row('正式绩效'" not in compare

    assert ".net-position-summary>.net-formal-position{color:var(--muted)}" in css
    assert ".home-formal-rank,.home-full-position" in css



def test_top_level_performance_scores_use_reader_precision_but_audit_precision_is_preserved():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")

    assert "const number=v=>typeof v==='number'?v.toFixed(2):'—';" in template
    assert "const scoreNumber=v=>typeof v==='number'?v.toFixed(1):'—';" in template

    assert '<b class="home-simple-score">${scoreNumber(r.net.total_score)}</b>' in template
    assert '<span class="number">${scoreNumber(r.net.total_score)}</span>' in template
    assert '<div class="big">${scoreNumber(n.total_score)}</div>' in template
    assert '<span>治国成效</span><b>${scoreNumber(n.second_item_score)}</b>' in template
    assert '<span>军事与边疆</span><b>${scoreNumber(n.third_item_score)}</b>' in template

    compare_start = template.index("function compare(){")
    compare_end = template.index("function guide()", compare_start)
    compare = template[compare_start:compare_end]
    assert "row('统治绩效',r=>r.net?`<b>${scoreNumber(r.net.total_score)}</b>`" in compare
    assert "row('治国成效',r=>scoreNumber(r.net?.second_item_score))" in compare
    assert "row('军事与边疆',r=>scoreNumber(r.net?.third_item_score))" in compare
    assert "firstRawScore(r.net)===0?'0.0 · 本项适用':scoreNumber(r.net.first_item_add_on)" in compare
    assert "return Number.isFinite(n)&&n>0?'+'+scoreNumber(n):scoreNumber(value)" in compare
    assert "number(r.net.first_item_add_on)" not in compare

    assert "number(prudent.lower)" in template
    assert "number(prudent.upper)" in template
    assert "number(x.delta)" in template

    home = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "统治绩效总分 ${scoreNumber(record.net?.total_score)}" in home
    assert "当前显示正式附加分 ${scoreNumber(record.net?.first_item_add_on)}" in home
    assert "第一项结算分：${scoreNumber(rawFirstScore)}" in home
    assert 'major === "fourth" && Number(value) > 0 ? `+${scoreNumber(value)}` : scoreNumber(value)' in home

def test_profile_metadata_hides_internal_axis_codes_and_raw_radar_values():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index('<details class="metadata"><summary>原始记录与专业信息</summary>')
    end = template.index('</details></details>', start)
    block = template[start:end]
    assert "展示模式：" in block
    assert "判断把握：" in block
    assert "公开等级：" in block
    assert "当前状态：无档结案" in block
    assert "grade(a)" in block
    assert "a.axis_grade" not in block
    assert "a.radar_value" not in block
    assert "pos(a.position)" not in block
    assert " · ${c} " not in block


def test_profile_metadata_uses_reader_friendly_source_labels():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    assert "function profileSourceMarkup(ref,index,r)" in template
    assert "正式材料 ${index+1} ↗" in template
    assert "史料来源 ${index+1} ↗" in template
    assert "link(ref,ref)" not in template
    assert "profileSourceMarkup(ref,index,r)" in template

def test_profile_public_pattern_hides_cross_axis_work_codes():
    from pathlib import Path

    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index("function profilePublicPattern(value)")
    end = template.index("function axisEvidence(", start)
    block = template[start:end]
    assert "shortNames[code]||code" in block
    assert "直接证据有限：" in block
    assert "剔除与其他能力轴重复的材料后，本轴依据更集中" in block
    assert "负向证据" in block
    assert "目前证据链尚未完整" in block
    assert "没有确认由本人直接造成的完整负向链" in block
    assert '.replace(/父链/g,"证据链")' in block
    assert '.replace(/硬门/g,"必要条件")' in block
    assert '.replace(/(?:正式)?横校/g,"交叉核对")' in block
    assert '.replace(/整改前/g,"此前")' in block
    assert "正式材料范围" in block
    assert "事件纳入范围的截止线" in block
    assert "展示等级" in block
    assert "function axisProse(t){if(typeof t===\'string\')return prose(profilePublicPattern(t));" in template
    assert "esc(profilePublicPattern(rawTitle))" in template
    assert "现有证据只支持到完整生命周期情境的强度" in block
    assert "当前判断不过度奖励“判断正确”；执行闭环仍明显不足。" in block
    assert "MI1(?:_CASE)?" in template
    assert "MI2(?:_LIFECYCLE)?" in template
    assert "MI3(?:_SUSTAINED_SYSTEMIC)?" in template
    assert "MI4(?:_CROSS_PHASE_SYSTEMIC)?" in template
    assert "materialIntensityNames[k]||k" in template
    assert "formalDirectionNames[k]||k" in template
    assert "负向$1材料" in block
    assert "正向$1材料" in block
    assert "-P[A-Za-z0-9_-]+" in block
    assert '"既有情境材料"' in block
    assert "const cleaned=String(value??'')" in block
    assert block.index("const cleaned=String(value??'')") < block.index("return readerText(cleaned)")
    assert "没有形成" in block
    assert "尚未形成" in block
    assert "相关证据链已" in block
    assert "A-Za-z0-9_:-" in block
    assert "较广外溢范围" in block
    assert "过错归责仍未确定" in block
    assert "第${n}组材料" in block
    assert "本人不在直接指挥链中" in block
    assert "投入大量资源却" in block
    assert "相关正式材料已完成核对" in block
    assert "材料有限" in block
    assert "完整生命周期的强负向材料" in block
    assert "战区或多军统筹" in block
    assert "军事角色尚未确定" in block
    assert "角色字段与事实叙述存在冲突" in block
    assert "档战役成果／多重重大约束的高压任务" in block
    assert "档战役成果／极端劣势或濒临崩溃的逆转任务" in block
    assert "登记角色：主要指挥者" in block
    assert "登记角色：最高指挥者" in block
    assert "求真取证情境" in block
    assert "拒绝更新或同类复发情境" in block
    assert "多功能、广域行政链整体失效" in block
    assert "治理恢复的具体工具专业性由民生财政相关结果承担" in block
    assert '.replace(/\\bM3\\b/g,"民生财政相关结果")' not in block
    assert "官僚治理现有材料已确认岭南物流的持续运行链与有限选任链" in block
    assert '.replace(/\\bB1\\b/g,"官僚治理")' in block
    assert '.replace(/\\bB2\\b/g,"反馈与约束")' in block
    assert "正向为主的系统性机制" in block
    assert "负向系统性机制" in block
    assert "系统性、持续性的稳定交付" in block
    assert "法律简化主要属于民生财政相关结果／学习纠错辅助背景" in block
    assert "具体制度专业判断不在本轴重复计入" in block
    assert "高压与极端逆转任务数量" in block
    assert "任务压力尚未达到高压或极端逆转级" in block
    assert "前线高压任务锚" in block
    assert "原“常规风险任务”难度不足以反映兵力与接战条件" in block
    assert "多重重大约束的高压任务" in block
    assert "极端劣势或濒临崩溃的逆转任务" in block
    assert "学习纠错与反馈约束" in block
    assert "反馈后调整路径" in block
    assert "错误纠正情境" in block
    assert "不是国家运行架构换代" in block
    assert "官僚治理材料" in block
    assert "制度设计或制度建设等相关评价" in block
    assert '.replace(/消费/g,"计入")' in block
    assert "极广外溢范围" in block
    assert "极深负向下沿" in block
    assert "负向风险链" in block
    assert "官僚治理正式材料" in block
    assert '.replace(/actual_power_window/g,"掌权时期")' in block
    assert '.replace(/重裁/g,"重新核对")' in block
    assert '.replace(/倒灌/g,"追溯计入")' in block
    assert '.replace(/回填/g,"追溯计入")' in block
    assert '.replace(/分账/g,"分开评价")' in block
    assert '.replace(/(?:正式)?底账/g,"正式材料")' in block
    assert '.replace(/窗口门/g,"适用范围")' in block
    assert '.replace(/最新重裁/g,"最新核对")' in block
    assert '.replace(/闭合/g,"确认")' in block
    assert '.replace(/准入/g,"纳入判断")' in block
    assert "尚未确认的负向候选材料" in block
    assert "背景材料" in block
    assert "单一家庭或窄亲属群范围" in block
    assert "功臣安全的极深负向下沿" in block
    assert "政治表达安全的极深负向下沿" in block
    assert "强藩违法特权" in block
    assert "军队违法特权" in block
    assert "反例覆盖复核" in block
    assert "史源冲突" in block
    assert "实际权力受限" in block
    assert "归责存在争议或共享" in block
    assert "极重安全恶化并伴随重要区域控制丧失" in block
    assert "严重安全恶化并伴随重要区域控制丧失" in block
    assert "核心区域军政功能严重受损并伴随严重安全恶化" in block
    assert "仅有局部安全改善但整体出现明显持续安全恶化" in block
    assert "高到极高强度军事资源投入或损失" in block
    assert "继任行政连续性" in block
    assert "高压任务难度完整归给" in block
    assert "极端逆转级前线压力" in block
    assert "中等强度负向证据" in block
    assert "极高强度负向证据" in block
    assert "最高指挥者" in block
    assert "问题优先级判断" in block
    assert "目标—资源匹配" in block
    assert "风险与可选方案控制" in block
    assert "一般司法治理" in block
    assert "现实武装威胁下的安全处置" in block
    assert "差异法域" in block
    assert "创业主阶段" in block
    assert "雁门危机战役材料" in block
    assert "葛陂南进撤退阶段材料" in block
    assert "稳定证据链[A-Za-z0-9_:-]{4,}已" in block
    assert "精英级" in block
    assert "跨家庭或较广党附范围的族诛" in block
    assert "面向一般民众或多个无关群体的系统性恐怖" in block
    assert "反馈与约束中的异议安全" in block
    assert "主要归组织执行与官僚治理" in block
    assert '.replace(/\\bLOW\\b/g,"低位")' in block
    assert '.replace(/\\bMID\\b/g,"中位")' in block
    assert '.replace(/\\bHIGH\\b/g,"高位")' in block
    assert "横向负向证据强度校准" in block
    assert "最大负向证据校准" in block
    assert "事件后果尺度，不是人物画像等级" in template
    assert "未单列独立负向后果等级" in template
    assert "相关情境材料未附正文" in template
    assert "esc(profilePublicPattern(point.title))" in template
    assert "定档依据（原文）" not in template
    assert "档内定位（原文）" not in template
    assert "const distinctPositionBasis=profileDistinctPositionBasis" in template
    assert "function profilePositionPublicPattern(value)" in template
    assert "function profileDistinctLimitations(value,...priorValues)" in template
    assert "const distinctLimitations=profileDistinctLimitations" in template
    assert "boundaryParts" in template
    assert "const adjudicationBody=" in template
    assert "const adjudicationDetails=adjudicationBody?" in template
    assert "${adjudicationDetails}" in template
    assert "规范池实际权力窗口为[^；]+" in template
    assert "；?限制：[\\s\\S]*$" in template
    assert 'distinctPositionBasis?`<div class="label">档内定位</div>' in template
    assert "限制与证据边界（原文）" not in template


def test_third_public_copy_hides_fallen_regime_audit_codes():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    start = source.index("function thirdPublicText")
    end = source.index("function thirdItemPublicText", start)
    block = source[start:end]

    assert "仍为0，但从错误0→0重建为真实" in block
    assert "重新核对后，确认任内发生大规模边疆退控并最终归零。" in block
    assert "本人对后续(恶化|改善)主要本人责任" in block
    assert "本人对后续${direction}承担主要责任" in block
    assert "(^|[^\\d])([0-5])\\/([0-5])\\/([0-5])(?=$|[^\\d])" in block
    assert "实战任务交付${thirdGradeText(delivery)}、持续作战${thirdGradeText(endurance)}、体系可靠性${thirdGradeText(reliability)}" in block
    assert "当前没有可与创业统一主链分离的独立体系压力任务" in block
    assert "同一主链的安全态势和控制成果不在本项重复计入" in block
    assert "终点值由-?\\d+" in block
    assert "重新核对本人窗口内的实际控制范围后" in block
    assert "\\d+票(?:降至|升至)\\d+票" in block
    assert "相关任务按统一边界重新归并" in block
    assert '.replace(/现行贡献类型为/g, "当前成果类型为")' in block
    assert '.replace(/本包事实/g, "本项已经确认的事实")' in block
    assert '.replace(/控制包/g, "控制成果")' in block
    assert '.replace(/重复交付与恢复/g, "多次维持并在受压后恢复")' in block
    assert "重大压力下保全的等级上限" in block
    assert "父级重新裁任务回报类别" in block
    assert "在合并后的任务周期重新判断整体回报" in block
    assert "正式横校档" in block
    assert "当前等级" in block
    assert "客观状态确有改善，但相关创业统一主链已由奠基与统一项计入" in block
    assert "只把淮河、荆湖北缘和川陕三个真实外部边疆方向计入实际控制范围" in block
    assert "材料覆盖缺口" in block
    assert "已达到$1所需条件" in block
    assert "补足该条件" in block
    assert "不提高到" in block




def test_supplementary_person_page_is_history_impact_only():
    from pathlib import Path

    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    start = template.index("function person(r){")
    end = template.index("\nfunction compare(){", start)
    block = template[start:end]

    assert "const pageMode=supplementary?'历史影响补充样本':'三套评价';" in block
    assert "该对象只进入历史影响补充样本，不纳入统治绩效正式评价范围或人物画像正式评价范围。" in block
    assert "本页只展开历史影响正式依据。" in block
    assert "supplementary?'':" in block
    assert "历史影响概览" in block
    assert "history.replaceState(null,\'\',`#person/${encodeURIComponent(r.ruler_id)}/impact`);impactPage(r);return" in block


def test_first_item_not_applicable_card_uses_explicit_label():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    start = source.index("function majorCard(record, major)")
    end = source.index("function renderNetShell", start)
    block = source[start:end]

    assert 'major === "first" && firstStatus === "NOT_APPLICABLE"' in block
    assert '? "不适用"' in block
    assert "该人物第一项不适用。" in block


def test_b1_independent_public_cards_reject_duplicate_titles_and_bases():
    from emperor_v4.evaluation.second_item_b1_settlement import _validate_independent_public_card_distinctness

    duplicate_basis = {
        "ruler_name": "测试人物",
        "M_positive_profile": [
            {"profile_id": "P1", "material_id": "M1", "adjudication_status": "COUNTED_INDEPENDENT", "public_label": "甲链", "adjudication_basis": "同一正文"},
            {"profile_id": "P2", "material_id": "M2", "adjudication_status": "COUNTED_INDEPENDENT", "public_label": "乙链", "adjudication_basis": "同一正文"},
        ],
    }
    with pytest.raises(ValueError, match="公开裁决正文重复"):
        _validate_independent_public_card_distinctness(duplicate_basis)

    duplicate_label = {
        "ruler_name": "测试人物",
        "M_positive_profile": [
            {"profile_id": "P1", "material_id": "M1", "adjudication_status": "COUNTED_INDEPENDENT", "public_label": "同名卡", "adjudication_basis": "正文甲"},
            {"profile_id": "P2", "material_id": "M2", "adjudication_status": "COUNTED_INDEPENDENT", "public_label": "同名卡", "adjudication_basis": "正文乙"},
        ],
    }
    with pytest.raises(ValueError, match="公开名称重复"):
        _validate_independent_public_card_distinctness(duplicate_label)
