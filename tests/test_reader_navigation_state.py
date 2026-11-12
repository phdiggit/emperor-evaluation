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
 document:{getElementById:id=>details.find(d=>d.id===id)},
 requestAnimationFrame:fn=>queue.push(fn),
 MutationObserver:class{constructor(fn){observe=fn;}observe(){}},
 scrollX:0,scrollY:0,scrollTo(x,y){this.scrollX=x;this.scrollY=y;},
 addEventListener(){},removeEventListener(){},person(){},compare(){},home(){},guide(){}};
context.window=context;
context.route=()=>{details=[detail('reason-C1'),detail('reason-C2')];context.scrollTo(0,0);observe();};
vm.createContext(context);vm.runInContext(fs.readFileSync('reader/reading-state.js','utf8'),context);
function flush(){let limit=50;while(queue.length&&limit--)queue.shift()();assert.ok(limit>0);}
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
''')


def test_versioned_generated_shards_match_bootstrap():
    import hashlib
    from emperor_v4.json_format import json_text
    html = (ROOT / 'reader/index.html').read_text(encoding='utf-8')
    data = json.loads(html.split('<script type="application/json" id="reader-data">')[1].split('</script>')[0])
    for summary in data['records']:
        payload = json.loads((ROOT / 'reader' / summary['detail_ref']).read_text(encoding='utf-8'))
        assert summary['detail_version'] == payload['detail_version']
        version = payload.pop('detail_version')
        assert hashlib.sha256(json_text(payload).encode('utf-8')).hexdigest() == version
    notes = (ROOT / 'reader/data/person-reading-notes.json').read_text(encoding='utf-8')
    assert hashlib.sha256(notes.encode('utf-8')).hexdigest() == data['notes_version']
    for path in (ROOT / 'reader/data/first-item').glob('*.json'):
        assert json.loads(path.read_text(encoding='utf-8'))['source_version'] == data['first_source_version']


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
