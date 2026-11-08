"""Reader score presentation behavior, using synthetic records."""
from pathlib import Path
import shutil
import subprocess
import pytest

def _run_reading_notes_node(tmp_path, body):
    node=shutil.which('node')
    if not node: pytest.skip('Node.js required for reader behavior')
    script=tmp_path/'score-display.cjs'
    script.write_text("const assert=require('node:assert/strict');\n"+body,encoding='utf-8')
    result=subprocess.run([node,str(script)],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr

def test_merit_trial_toggle_preserves_data_and_distinguishes_component_indices(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const template=fs.readFileSync('reader/index.template.html','utf8');
const source=template.slice(template.indexOf('function performanceScore('),template.indexOf('function performanceScaleHelp('));
const ctx={esc:String,DATA:{records:[]}};vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.net={public_scores:{total:{state:'SCORED',score:88.5,grade:'B',trial_tier:{code:'ming',label:'明',display_label:'明上',position:'上',score:87.5,boundary_neighbor:null}},second:{state:'SCORED',score:91.5,grade:'A',trial_rating:{kind:'performance',score:81.5,grade:'突出'}},first:{state:'NOT_APPLICABLE'},fourth:{state:'NO_CONFIRMED_CHANGE'}}};
const before=JSON.stringify(ctx.net);
let output=vm.runInContext('performanceScore(net)',ctx);
assert.ok(output.includes('明上')&&output.includes('87.5'));
const second=vm.runInContext("performanceScore(net,'second')",ctx);
assert.ok(second.includes('81.5')&&second.includes('突出')&&!second.includes('91.5')&&!second.includes('>A<')&&!second.includes('明上'));
vm.runInContext('meritTierPreview=false',ctx);
output=vm.runInContext('performanceScore(net)',ctx);
assert.ok(output.includes('88.5')&&output.includes('>B<')&&!output.includes('明上'));
const originalSecond=vm.runInContext("performanceScore(net,'second')",ctx);
assert.ok(originalSecond.includes('91.5')&&originalSecond.includes('>A<'));
assert.equal(vm.runInContext("performanceScore(net,'first')",ctx),'不适用');
assert.equal(vm.runInContext("performanceScore(net,'fourth')",ctx),'未确认独立变化');
assert.equal(JSON.stringify(ctx.net),before);
vm.runInContext('meritTierPreview=true',ctx);
ctx.net.public_scores.total.trial_tier={code:'hun',label:'昏',display_label:'昏上',score:39.5,position:'上',boundary_neighbor:'庸'};
output=vm.runInContext('performanceScore(net)',ctx);
assert.ok(output.includes('昏上')&&output.includes('近庸档界')&&!output.includes('高位'));
delete ctx.net.public_scores.total.trial_tier;
delete ctx.net.public_scores.second.trial_rating;
for(const key of ['total','second']){
 ctx.key=key;output=vm.runInContext('performanceScore(net,key)',ctx);
 assert.ok(output.includes('展示数据待同步'));
 assert.ok(!output.includes('88.5')&&!output.includes('91.5'));
}
vm.runInContext('meritTierPreview=false',ctx);
assert.ok(vm.runInContext("performanceScore(net,'second')",ctx).includes('91.5'));
''')


def test_scale_help_explains_the_selected_zero_point_and_active_anchors(tmp_path):
    import json
    from emperor_v4.reader_scores import metadata
    script=r'''
const fs=require('node:fs'),vm=require('node:vm');
const template=fs.readFileSync('reader/index.template.html','utf8');
const source=template.slice(template.indexOf('function performanceScore('),template.indexOf('const conf='));
const ctx={esc:String,DATA:{records:[],public_score_scale:__META__}};
vm.createContext(ctx);vm.runInContext(source,ctx);
let html=vm.runInContext('performanceScaleHelp()',ctx);
assert.ok(html.includes('适用者零净分对应0'));
assert.ok(html.includes('文明净增量不经过这条曲线'));
assert.ok(!html.includes('综合绩效（原方案对照）'));
vm.runInContext('meritTierPreview=false',ctx);
html=vm.runInContext('performanceScaleHelp()',ctx);
const meta=ctx.DATA.public_score_scale;
assert.ok(html.includes('文明的原分零点对应'+meta.scales.fourth.anchors[0][1]));
assert.ok(!html.includes('适用者零净分对应0'));
assert.ok(!html.includes('文明净增量不经过这条曲线'));
assert.ok(html.includes('综合绩效（原方案对照）'));
assert.ok(!html.includes('综合绩效（五档十五级试读）'));
'''
    _run_reading_notes_node(tmp_path, script.replace('__META__', json.dumps(metadata(), ensure_ascii=False)))


def test_net_detail_cache_rerenders_when_score_mode_changes(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const home=fs.readFileSync('reader/home-interactions.js','utf8');
const template=fs.readFileSync('reader/index.template.html','utf8');
const helpers=template.slice(template.indexOf('function performanceScore('),template.indexOf('function performanceScaleHelp('));
const shell=home.slice(home.indexOf('  function renderNetShell('),home.indexOf('  function renderNetLanding('));
const route=home.slice(home.indexOf('  async function renderNetRoute('),home.indexOf('  function runReaderEnhancer('));
const record={ruler_id:'synthetic',ruler_name:'合成人物',net:{public_scores:{
 total:{state:'SCORED',score:88,grade:'B',trial_tier:{code:'ming',display_label:'明中',score:84}},
 second:{state:'SCORED',score:85,grade:'B',trial_rating:{kind:'performance',score:65,grade:'中等'}}}}};
let current=null,renders=0;
const ctx={esc:String,personLabel:r=>r.ruler_name,nav(){},governanceScope(){return '';},majorNav(){return '';},performanceScaleHelp(){return '';},
 netMajorSpecs:{second:{title:'治国'}},netRenderGeneration:0,byId:new Map([['synthetic',record]]),
 parseNetRoute:()=>({rulerId:'synthetic',major:'second',focus:null}),location:{hash:'#net/synthetic/second'},
 screen:{innerHTML:'',querySelector:()=>current},window:{scrollTo(){}},document:{getElementById(){return null;}},
 loadNetRecord:async r=>r,console};
vm.createContext(ctx);vm.runInContext(helpers+shell+route,ctx);
ctx.renderNetMajor=(r,major)=>{
 renders++;ctx.activeRecord=r;ctx.activeMajor=major;
 vm.runInContext("renderNetShell(activeRecord,activeMajor,'合成正文')",ctx);
 const html=ctx.screen.innerHTML;
 current={dataset:{netPerson:html.match(/data-net-person="([^"]+)"/)[1],netMajor:html.match(/data-net-major="([^"]+)"/)[1],netScoreMode:html.match(/data-net-score-mode="([^"]+)"/)[1]}};
};
(async()=>{
 await vm.runInContext('renderNetRoute()',ctx);
 assert.equal(renders,1);assert.ok(ctx.screen.innerHTML.includes('65.0'));
 await vm.runInContext('renderNetRoute()',ctx);assert.equal(renders,1);
 vm.runInContext('meritTierPreview=false',ctx);
 await vm.runInContext('renderNetRoute()',ctx);
 assert.equal(renders,2);assert.equal(current.dataset.netScoreMode,'letter');assert.ok(ctx.screen.innerHTML.includes('85.0'));
 vm.runInContext('meritTierPreview=true',ctx);
 await vm.runInContext('renderNetRoute()',ctx);
 assert.equal(renders,3);assert.equal(current.dataset.netScoreMode,'merit');assert.ok(ctx.screen.innerHTML.includes('65.0'));
})().catch(error=>{console.error(error);process.exitCode=1;});
''')



def test_second_enhancement_preserves_public_scores_on_home_and_compare(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const publicMarkup='<b>83.2 <span class="performance-grade">C+</span></b>';
const score={innerHTML:publicMarkup,textContent:'83.2 C+',dataset:{}};
const label={textContent:'治国成效',dataset:{}};
const pendingCell={textContent:'未结算',dataset:{}};
const row={cells:[label,score,pendingCell]};
const screen={querySelectorAll(selector){return selector==='.comparison tbody tr'?[row]:[];}};
const personRow={querySelector(selector){return selector==='b'?score:{dataset:{},childNodes:[{nodeType:3,nodeValue:'治国成效'}]};}};
const panel={querySelectorAll(){return [personRow];}};
const ctx={document:{getElementById(id){return id==='screen'?screen:panel;}},
 window:{},location:{hash:'#person/SYNTHETIC'},Node:{TEXT_NODE:3},SecondItemDisplay:{}};
vm.createContext(ctx);
let source=fs.readFileSync('reader/second-item-reading.js','utf8');
source=source.replace('Object.freeze({enhance})','Object.freeze({enhance,enhancePersonOverview,enhanceCompare})');
vm.runInContext(source,ctx);
const secondApi=ctx.window.SecondItemReading;
const record={detail_loaded:true,net:{second_item_score:173.7,component_details:{}}};
const pending={detail_loaded:true,settlement_readiness:'PENDING_SECOND_ITEM_FORMAL_SETTLEMENT'};
for(let pass=0;pass<2;pass++){
 secondApi.enhancePersonOverview(record);secondApi.enhanceCompare([record,pending]);
 assert.equal(score.innerHTML,publicMarkup);assert.equal(score.textContent,'83.2 C+');
 assert.equal(pendingCell.textContent,'待正式结算');
}
// A new template render must also remain intact on the next enhancement pass.
score.innerHTML='<b>91.0 <span class="performance-grade">A</span></b>';
secondApi.enhanceCompare([record,pending]);assert.ok(score.innerHTML.includes('91.0'));
''')

