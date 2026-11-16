"""Reader navigation behavior with synthetic identities and DOM fixtures."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_node(tmp_path, script):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for reader behavior')
    path = tmp_path / 'navigation.cjs'
    path.write_text("const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');\n" + script, encoding='utf-8')
    result = subprocess.run([node, str(path)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_late_person_and_comparison_failure_cannot_replace_net_page(tmp_path):
    run_node(tmp_path, r'''
const code=fs.readFileSync('reader/lazy-details.js','utf8');
async function check(kind) {
 let reject;
 const record={ruler_id:'synthetic',ruler_name:'Test',detail_ref:'data/test.json',detail_version:'v'};
 const context={person(){},compare(){},home(){},guide(){},route(){},nav(){},esc:String,
   window:{fetch:()=>new Promise((_,failure)=>{reject=failure;})},
   location:{hash:kind==='person'?'#person/synthetic':'#compare/synthetic/other'},
   screen:{innerHTML:''},state:{compare:['synthetic','other']},
   byId:new Map([['synthetic',record],['other',{ruler_id:'other',detail_loaded:true}]]),
   DATA:{source_availability:{}},console:{error(){},warn(){}},URL,Response};
 context.personId=()=>context.location.hash.slice(8).split('/')[0];
 context.fetch=(...args)=>context.window.fetch(...args);
 vm.createContext(context);vm.runInContext(code,context);
 if(kind==='person')context.person(record);else context.compare();
 context.location.hash='#net/other/second';context.screen.innerHTML='CURRENT';
 reject(Error('delayed failure'));
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(context.screen.innerHTML,'CURRENT');
}
(async()=>{await check('person');await check('compare');})().catch(e=>{console.error(e);process.exitCode=1;});
''')


def test_reading_state_restores_folds_scroll_and_waits_for_async_render(tmp_path):
    run_node(tmp_path, r'''
const queue=[],events={};let observe,details=[],loading=false;
const screen={addEventListener:(name,fn)=>events[name]=fn,
 querySelectorAll:()=>details,querySelector:selector=>selector==='.empty'&&loading?{}:null};
function detail(id,open=false){return {id,open,tagName:'DETAILS',parentElement:screen};}
const context={screen,location:{hash:'#person/synthetic/profile'},
 byId:new Map(),state:{compare:[]},
 document:{getElementById:id=>details.find(d=>d.id===id)},
 requestAnimationFrame:fn=>queue.push(fn),
 MutationObserver:class{constructor(fn){observe=fn;}observe(){}},
 scrollX:0,scrollY:0,scrollTo(x,y){this.scrollX=x;this.scrollY=y;},
 addEventListener(){},removeEventListener(){},person(){},compare(){},home(){},guide(){}};
context.window=context;
context.route=()=>{details=[detail('reason-C1'),detail('reason-C2')];context.scrollTo(0,0);observe();};
vm.createContext(context);
vm.runInContext(fs.readFileSync('reader/person-narratives.js','utf8'),context);
vm.runInContext(fs.readFileSync('reader/reading-state.js','utf8'),context);
function flush(){let limit=50;while(queue.length&&limit--)queue.shift()();assert.ok(limit>0);}
flush();
details=[detail('reason-C1',true),detail('reason-C2',true)];context.scrollY=420;
context.location.hash='#person/other/impact';context.route();flush();
assert.equal(details[0].open,false,'other person must not inherit folds');
context.location.hash='#person/synthetic/profile';loading=true;context.route();flush();
assert.equal(context.scrollY,0,'wait for the real detail DOM');
loading=false;observe();flush();
assert.equal(details[0].open,true);assert.equal(details[1].open,true);assert.equal(context.scrollY,420);
details[0].open=false;events.toggle({target:details[0]});
context.location.hash='#person/synthetic/profile/C2';context.route();flush();
assert.equal(details[0].open,false);assert.equal(details[1].open,true);
assert.equal(context.scrollY,0,'new focus does not inherit the old page scroll');
context.location.hash='#person/synthetic/profile/C1';context.route();flush();
assert.equal(details[0].open,true,'explicit axis link opens a previously closed fold');
context.location.hash='#net/synthetic/second/reading-second-source-1';
loading=true;context.route();flush();
details=[detail('reading-second-sources'),{id:'reading-second-source-1',parentElement:null}];
details[1].parentElement=details[0];loading=false;observe();flush();
assert.ok(details[0].open,'a source link opens its fold after the async render');
''')


def test_versioned_generated_shards_match_bootstrap():
    import hashlib
    from emperor_v4.json_format import json_text
    html = (ROOT / 'reader/index.html').read_text(encoding='utf-8')
    source_links_version = hashlib.sha256((ROOT / 'reader/source-links.js').read_bytes()).hexdigest()
    assert f'src="source-links.js?v={source_links_version}"' in html
    data = json.loads(html.split('<script type="application/json" id="reader-data">')[1].split('</script>')[0])
    authored = json.loads((ROOT / 'reader/person-reading-notes.json').read_text(encoding='utf-8'))['records']
    for summary in data['records']:
        payload = json.loads((ROOT / 'reader' / summary['detail_ref']).read_text(encoding='utf-8'))
        assert 'reader_overviews' not in summary
        assert payload['record']['reader_overviews'] == authored[summary['ruler_id']]['overview']
        assert summary['detail_version'] == payload['detail_version']
        version = payload.pop('detail_version')
        assert hashlib.sha256(json_text(payload).encode('utf-8')).hexdigest() == version
    notes = (ROOT / 'reader/data/person-reading-notes.json').read_text(encoding='utf-8')
    assert hashlib.sha256(notes.encode('utf-8')).hexdigest() == data['notes_version']
    for path in (ROOT / 'reader/data/first-item').glob('*.json'):
        assert json.loads(path.read_text(encoding='utf-8'))['source_version'] == data['first_source_version']


@pytest.mark.parametrize('route,system', [('person','profile'),('person','impact'),('net','second')])
def test_initial_source_deep_link_waits_for_shard_before_restoring(tmp_path, route, system):
    run_node(tmp_path, f"const route={json.dumps(route)},system={json.dumps(system)};\n" + r'''
let loading=true,observe;const queue=[],events={};
const fold={id:`reading-${system}-sources`,tagName:'DETAILS',open:false};
const target={id:`reading-${system}-source-1`,parentElement:fold};
const screen={addEventListener(){},querySelector:()=>loading?{}:null,querySelectorAll:()=>loading?[]:[fold]};
fold.parentElement=screen;
const context={screen,location:{hash:`#${route}/synthetic/${system}/${target.id}`},byId:new Map(),state:{compare:[]},
 document:{getElementById:id=>!loading&&id===target.id?target:null},
 requestAnimationFrame:fn=>queue.push(fn),MutationObserver:class{constructor(fn){observe=fn;}observe(){}},
 addEventListener:(name,fn)=>events[name]=fn,removeEventListener(){},person(){},compare(){},home(){},guide(){},route(){},scrollTo(){}};
context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync('reader/person-narratives.js','utf8'),context);
vm.runInContext(fs.readFileSync('reader/reading-state.js','utf8'),context);
function flush(){let limit=50;while(queue.length&&limit--)queue.shift()();assert.ok(limit>0);}
flush();assert.equal(fold.open,false);
loading=false;events.scroll();observe();flush();
assert.equal(fold.open,true,'initial browser scroll must not save a closed fold over the explicit destination');
''')


def test_page_titles_follow_person_system_comparison_and_home(tmp_path):
    run_node(tmp_path, r'''
const source=fs.readFileSync('reader/reading-state.js','utf8');
const context={};vm.createContext(context);vm.runInContext(source.slice(0,source.indexOf('(() => {')),context);
const records=new Map([['RULER-甲',{ruler_name:'甲君'}],['other',{ruler_name:'乙君'}]]);
const title=hash=>context.readerPageTitle(hash,records,['other','RULER-甲']);
assert.equal(title('#person/RULER-%E7%94%B2'),'甲君 · 人物总览 · 帝王三镜');
assert.equal(title('#person/RULER-%E7%94%B2/profile/reading-profile-source-1'),'甲君 · 人物画像 · 帝王三镜');
assert.equal(title('#net/RULER-%E7%94%B2/second/reading-second-source-1'),'甲君 · 治国成效 · 帝王三镜');
assert.equal(title('#person/other/impact'),'乙君 · 历史影响 · 帝王三镜');
assert.equal(title('#compare/RULER-%E7%94%B2/other'),'甲君与乙君 · 人物对照 · 帝王三镜');
assert.equal(title('#compare'),'乙君与甲君 · 人物对照 · 帝王三镜');
assert.equal(title('#overview'),'综合阅读 · 帝王三镜');
assert.equal(title('#guide'),'阅读指南 · 帝王三镜');
assert.equal(title('#person/missing'),'未找到人物 · 帝王三镜');
assert.equal(title('#person/%'),'地址无效 · 帝王三镜');
''')


def test_overviews_use_loaded_person_shard_and_recheck_evidence_without_fetch(tmp_path):
    run_node(tmp_path, r'''
const block={text:'合成提要',evidence:[{path:['impact','public_boundary'],quote:'合成事实'}]};
const record={ruler_id:'HIMPACT-synthetic',detail_loaded:true,impact:{public_boundary:'合成事实'},reader_overviews:{impact:block}};
let rendered;
const makeNode=()=>({children:[],append(...nodes){this.children.push(...nodes);},addEventListener(){}});
const panel={querySelector:selector=>selector.includes('.person-reading-note')?rendered:{after:node=>{rendered=node;}}};
const context={document:{getElementById:id=>id==='screen'?{}:id==='person-impact'?panel:id==='person-reading-notes-style'?{}:null,createElement:makeNode},
 location:{hash:'#person/HIMPACT-synthetic/impact'},byId:new Map([[record.ruler_id,record]]),
 personId:()=>record.ruler_id,personView:()=> 'impact',fetch(){throw Error('unexpected network request');}};
vm.createContext(context);vm.runInContext(fs.readFileSync('reader/person-reading-notes.js','utf8'),context);
context.PersonReadingNotes.enhance();
assert.equal(rendered.children[1].textContent,block.text);
rendered=null;record.impact.public_boundary='事实已经变更';
context.PersonReadingNotes.enhance();
assert.ok(rendered.children[1].textContent.includes('依据已更新'));
context.location.hash='#overview';rendered=null;context.PersonReadingNotes.enhance();
assert.equal(rendered,null);
''')


def test_source_version_rejection_does_not_fall_back_or_poison_retry(tmp_path):
    run_node(tmp_path, r'''
let requests=0,version='new';
const context={person(){},compare(){},home(){},guide(){},route(){},
 window:{fetch:async()=>{requests++;return {ok:true,json:async()=>({
   ruler_id:'synthetic',documents:{'A统一贡献':'synthetic source'},public_outcome:{},source_version:version
 })};}},location:{hash:'#net/synthetic/first'},DATA:{first_source_version:'old'},
 console:{warn(){},error(){}},URL,Response};
vm.createContext(context);vm.runInContext(fs.readFileSync('reader/lazy-details.js','utf8'),context);
(async()=>{
 await assert.rejects(context.window.fetch('01-第一项A统一主链客观贡献正式结算.md'),e=>e.readerVersionMismatch);
 assert.equal(requests,1,'a version mismatch must not silently use another source');
 version='old';
 const response=await context.window.fetch('01-第一项A统一主链客观贡献正式结算.md');
 assert.equal(await response.text(),'synthetic source');assert.equal(requests,2);
})().catch(e=>{console.error(e);process.exitCode=1;});
''')


def test_source_text_digest_rejects_changes_and_accepts_line_endings(tmp_path):
    run_node(tmp_path, r'''
const template=fs.readFileSync('reader/index.template.html','utf8');
const begin=template.indexOf('async function requireReaderTextVersion(');
const code=template.slice(begin,template.indexOf('const state=',begin));
const context={crypto:require('node:crypto').webcrypto,TextEncoder,Uint8Array};
vm.createContext(context);vm.runInContext(code,context);
const expected=require('node:crypto').createHash('sha256').update('synthetic\n').digest('hex');
(async()=>{
 assert.equal(await context.requireReaderTextVersion('synthetic\r\n',expected),'synthetic\r\n');
 await assert.rejects(context.requireReaderTextVersion('changed\n',expected),e=>e.readerVersionMismatch);
 await assert.rejects(context.requireReaderTextVersion('synthetic\n',undefined),e=>e.readerVersionMismatch);
})().catch(e=>{console.error(e);process.exitCode=1;});
''')


def test_person_and_compare_load_retry_preserves_destination(tmp_path):
    run_node(tmp_path,r'''
async function check(kind){
 let requests=0;
 const originalHash=kind==='person'?'#person/synthetic/profile/reading-profile-source-1':'#compare/synthetic/other';
 const record={ruler_id:'synthetic',ruler_name:'Test',detail_ref:'data/test.json',detail_version:'v'};
 const ctx={person(){ctx.screen.innerHTML='LOADED';},compare(){ctx.screen.innerHTML='LOADED';},home(){},guide(){},route(){},nav(){},esc:String,
 window:{fetch:async()=>{requests++;if(requests===1)throw Error('offline');return {ok:true,json:async()=>({record:{ruler_id:'synthetic'},detail_version:'v'})};}},
 location:{hash:originalHash},screen:{innerHTML:''},state:{compare:['synthetic','other']},
 byId:new Map([['synthetic',record],['other',{ruler_id:'other',detail_loaded:true}]]),DATA:{source_availability:{}},console:{error(){},warn(){}},URL,Response};
 ctx.personId=()=> 'synthetic';ctx.fetch=(...args)=>ctx.window.fetch(...args);
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('reader/lazy-details.js','utf8'),ctx);
 ctx.route=()=>kind==='person'?ctx.person(ctx.byId.get('synthetic')):ctx.compare();
 ctx.route();await new Promise(resolve=>setImmediate(resolve));
 assert.ok(ctx.screen.innerHTML.includes('data-reader-retry'));
 const handler=ctx.screen.innerHTML.match(/data-reader-retry onclick="([^"]+)"/)[1];
 vm.runInContext(handler,ctx);await new Promise(resolve=>setImmediate(resolve));
 assert.equal(requests,2);assert.equal(ctx.screen.innerHTML,'LOADED');assert.equal(ctx.location.hash,originalHash);
}
(async()=>{await check('person');await check('compare');})().catch(e=>{console.error(e);process.exitCode=1;});
''')


def test_net_load_retry_preserves_entry_and_version_mismatch_requires_refresh(tmp_path):
    run_node(tmp_path,r'''
const source=fs.readFileSync('reader/home-interactions.js','utf8');
const code=source.slice(source.indexOf('  async function loadNetRecord('),source.indexOf('  function runReaderEnhancer('));
let requests=0,version='v';
const record={ruler_id:'synthetic',ruler_name:'Test',detail_ref:'data/test.json',detail_version:'v'};
const focus='entry-method-合成条目',hash='#net/synthetic/second/'+encodeURIComponent(focus);
const ctx={parseNetRoute:()=>({rulerId:'synthetic',major:'second',focus}),byId:new Map([['synthetic',record]]),
 DATA:{source_availability:{}},screen:{innerHTML:'',querySelector:()=>null},location:{hash},window:{scrollTo(){}},nav(){},esc:String,
 console:{error(){}},fetch:async()=>{requests++;if(requests===1)throw Error('offline');return {ok:true,json:async()=>({record:{ruler_id:'synthetic',net:{}},detail_version:version})};},
 renderNetMajor:(r,major,target)=>{assert.equal(target,focus);ctx.screen.innerHTML='LOADED';}};
vm.createContext(ctx);vm.runInContext('let netRenderGeneration=0;const pendingNetRecords=new Map();'+code,ctx);
ctx.route=ctx.renderNetRoute;
(async()=>{
 await ctx.route();assert.ok(ctx.screen.innerHTML.includes('data-reader-retry'));
 const handler=ctx.screen.innerHTML.match(/data-reader-retry onclick="([^"]+)"/)[1];
 await vm.runInContext(handler,ctx);assert.equal(ctx.screen.innerHTML,'LOADED');assert.equal(ctx.location.hash,hash);
 ctx.byId.set('synthetic',record);version='changed';await ctx.route();
 assert.ok(ctx.screen.innerHTML.includes('刷新页面'));assert.ok(!ctx.screen.innerHTML.includes('data-reader-retry'));
 assert.equal(requests,3);
})().catch(e=>{console.error(e);process.exitCode=1;});
''')
