"""Lazy C collection behavior using synthetic pages, not fixed historical judgments."""
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer
from html.parser import HTMLParser
from threading import Thread
from urllib.parse import urlsplit
from urllib.request import urlopen
import json
import runpy
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('grade', [0, 1, 2, 3, 4, 5, None])
def test_grade_meaning_uses_each_axis_scale_and_keeps_unknown_distinct(grade):
    from emperor_v4.evaluation.third_item_c_public import SCALES
    build = runpy.run_path(str(ROOT / 'reader/build.py'))
    for scale in SCALES:
        axis = dict(grade=grade, scale=list(scale))
        assert build['third_c_grade_meaning'](axis) == ('证据不足，暂不定档' if grade is None else scale[grade])


def test_local_server_serves_generated_collection_details_and_search_index_as_data():
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.detail = self.search = None
        def handle_starttag(self, tag, attributes):
            attrs = dict(attributes)
            if tag == 'article' and attrs.get('data-detail-url') and self.detail is None:
                self.detail = (attrs['id'], attrs['data-detail-url'])
            if attrs.get('id') == 'search-status':
                self.search = attrs['data-search-url']
    links = Links()
    links.feed((ROOT / 'reader/third-item-c.html').read_text(encoding='utf-8'))
    server_module = runpy.run_path(str(ROOT / 'reader/serve.py'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(server_module['ReaderHandler'], directory=str(ROOT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ruler_id, detail_url = links.detail
        with urlopen(f'http://127.0.0.1:{server.server_port}/reader/{detail_url}') as response:
            assert response.headers.get_content_type() == 'text/html'
            assert response.read() == (ROOT / 'reader' / urlsplit(detail_url).path).read_bytes()
        with urlopen(f'http://127.0.0.1:{server.server_port}/reader/{links.search}') as response:
            assert response.headers.get_content_type() == 'application/json'
            data = json.loads(response.read())
            assert ruler_id in data
            assert data == json.loads((ROOT / 'reader' / urlsplit(links.search).path).read_text(encoding='utf-8'))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_collection_assets_check_content_coverage_and_only_clean_managed_files(tmp_path, monkeypatch):
    build = runpy.run_path(str(ROOT / 'reader/build.py'))
    monkeypatch.setitem(build['write_generated_text'].__globals__, 'ROOT', tmp_path)
    directory = tmp_path / 'details'
    expected = {'RULER-SYNTHETIC.html': '<p>合成正文</p>', 'search.json': '{}\n'}
    build['write_third_c_assets'](directory, expected)
    build['verify_third_c_assets'](directory, expected)
    note = directory / 'user-note.txt'
    note.write_text('保留', encoding='utf-8')
    stale = directory / 'RULER-RETIRED.html'
    stale.write_text('旧对象', encoding='utf-8')
    with pytest.raises(ValueError, match='coverage'):
        build['verify_third_c_assets'](directory, expected)
    build['write_third_c_assets'](directory, expected)
    assert note.read_text(encoding='utf-8') == '保留' and not stale.exists()
    (directory / 'RULER-SYNTHETIC.html').write_text('失配', encoding='utf-8')
    with pytest.raises(ValueError, match='asset is stale'):
        build['verify_third_c_assets'](directory, expected)
    (directory / 'search.json').unlink()
    with pytest.raises(ValueError, match='coverage'):
        build['verify_third_c_assets'](directory, expected)


def test_collection_runtime_loads_on_demand_retries_searches_and_reveals_materials(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for collection runtime')
    script = tmp_path / 'collection.cjs'
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(id='',tagName='DIV') {this.id=id;this.tagName=tagName;this.dataset={};this.events={};this.children=[];this.attributes={};this.value='';this.hidden=false;this.open=false;this.parentElement=null;this.textContent='';this.innerHTML='';}
  addEventListener(type,fn){this.events[type]=fn;}
  async emit(type,event={}){if(this.events[type])await this.events[type](event);}
  setAttribute(key,value){this.attributes[key]=value;}
  removeAttribute(key){delete this.attributes[key];}
  append(child){this.children.push(child);}
  querySelectorAll(){return this.links||[];}
  querySelector(selector){return selector==='.third-c-person'?this.details:this.slot;}
  scrollIntoView(){this.scrolled=true;}
  focus(){this.focused=true;}
}
const a=new Element('RULER-A'),b=new Element('RULER-B');
for(const [entry,text] of [[a,'甲 早期防御'],[b,'乙 后期远征']]){
 entry.dataset={detailUrl:entry.id+'.html?v=current',search:text};
 entry.details=new Element('', 'DETAILS');entry.details.parentElement=entry;
 entry.slot=new Element();entry.slot.parentElement=entry.details;
 const source=new Element();source.dataset.localSource='docs/synthetic.md#fact';entry.slot.links=[source];
}
const input=new Element('search'),scope=new Element('search-scope'),status=new Element('search-status'),count=new Element('count');
scope.value='overview';status.dataset.searchUrl='search.json?v=current';
const material=new Element('RULER-B--evidence--MATERIAL');
material.dataset.cEvidence='MATERIAL';material.slot=new Element('', 'DETAILS');
const materialDetails=new Element('', 'DETAILS');materialDetails.parentElement=b.slot;material.parentElement=materialDetails;
const nodes=new Map([a,b,input,scope,status,count,material].map(e=>[e.id,e]));
const document=new Element();document.querySelectorAll=()=>[a,b];document.getElementById=id=>nodes.get(id);document.createElement=tag=>new Element('',tag.toUpperCase());
const windowEvents={},requests=[],failures=new Map(),deferred=new Map();
const location={hash:'',hostname:'127.0.0.1'};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const fetch=async(url,options)=>{
 requests.push(url);assert.equal(options.cache,'no-cache');
 if(deferred.has(url))await deferred.get(url);
 const fail=failures.get(url)||0;if(fail){failures.set(url,fail-1);return {ok:false};}
 return {ok:true,text:async()=>'<div>完整材料与逐轴正文</div>',json:async()=>({'RULER-A':'甲 早期防御 隐藏证据甲','RULER-B':'乙 后期远征 隐藏证据乙'})};
};
vm.runInNewContext(fs.readFileSync('reader/third-item-c-collection.js','utf8'),{document,location,fetch,addEventListener:(type,fn)=>{windowEvents[type]=fn;}});
(async()=>{
 assert.equal(requests.length,0,'initial page must not fetch details or full-text index');
 a.details.open=true;
 let release;deferred.set(a.dataset.detailUrl,new Promise(resolve=>{release=resolve;}));
 await a.details.emit('toggle');await a.details.emit('toggle');
 assert.equal(requests.length,1,'simultaneous opens share one request');
 release();await flush();
 assert.ok(a.slot.innerHTML.includes('完整材料'));
 assert.equal(a.slot.links[0].href,'../docs/synthetic.md#fact');
 await a.details.emit('toggle');await flush();assert.equal(requests.length,1,'loaded details reuse page memory');
 failures.set(b.dataset.detailUrl,1);b.details.open=true;await b.details.emit('toggle');await flush();
 assert.ok(b.slot.textContent.includes('加载失败'));assert.ok(!('aria-busy' in b.slot.attributes));
 await b.slot.children.at(-1).emit('click');await flush();assert.ok(b.slot.innerHTML.includes('完整材料'));
 input.value='早期防御';await input.emit('input');await flush();
 assert.equal(a.hidden,false);assert.equal(b.hidden,true);assert.equal(count.textContent,1);
 assert.ok(!requests.includes(status.dataset.searchUrl),'overview searches need no full index');
 scope.value='full';input.value='隐藏证据乙';failures.set(status.dataset.searchUrl,1);
 await scope.emit('change');assert.ok(status.textContent.includes('搜索加载失败'));assert.equal(b.hidden,true,'failed search must not report false empty results');
 await status.children.at(-1).emit('click');await flush();
 assert.equal(a.hidden,true);assert.equal(b.hidden,false);assert.equal(count.textContent,1);
 const searchRequests=requests.filter(url=>url===status.dataset.searchUrl).length;
 input.value='隐藏证据甲';await input.emit('input');
 assert.equal(requests.filter(url=>url===status.dataset.searchUrl).length,searchRequests);
 assert.equal(b.hidden,true);
 location.hash='#'+encodeURIComponent(material.id);await windowEvents.hashchange();
 assert.equal(b.hidden,false);assert.equal(count.textContent,2,'direct links clear conflicting filters');
 assert.equal(b.details.open,true);assert.equal(materialDetails.open,true);assert.ok(material.scrolled&&material.focused);
assert.equal(material.slot.open,true,'deep links open the nested material body');
 let prevented=false;const link={dataset:{cMaterialRef:material.id}};
 await document.emit('click',{target:{closest:()=>link},button:0,preventDefault:()=>{prevented=true;}});
 assert.ok(prevented);assert.equal(location.hash,'#'+encodeURIComponent(material.id));
 location.hash='#invalid%';await windowEvents.hashchange();
 // A late full-text result must not overwrite a newer overview query.
 // The page-memory search index was already loaded, so test this in a fresh runtime.
 const lateEvents={};let finishSearch;
 const lateFetch=async(url,options)=>{if(url===status.dataset.searchUrl){await new Promise(r=>{finishSearch=r;});return fetch(url,options);}return fetch(url,options);};
 location.hash='';scope.value='full';input.value='隐藏证据乙';
 vm.runInNewContext(fs.readFileSync('reader/third-item-c-collection.js','utf8'),{document,location,fetch:lateFetch,addEventListener:(type,fn)=>{lateEvents[type]=fn;}});
 const oldSearch=input.emit('input');await flush();
 scope.value='overview';input.value='早期防御';await scope.emit('change');
 finishSearch();await oldSearch;
 assert.equal(a.hidden,false);assert.equal(b.hidden,true);
})().catch(error=>{console.error(error);process.exitCode=1;});
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_shared_material_navigation_is_scoped_and_preserves_person_compare_routes(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for shared evidence navigation')
    script = tmp_path / 'material-navigation.cjs'
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let click;
const location={hash:'#compare/SYNTHETIC-A/SYNTHETIC-B'};
const context={document:{addEventListener:(type,handler)=>{assert.equal(type,'click');click=handler;}},location};
vm.runInNewContext(fs.readFileSync('reader/third-item-c-public.js','utf8'),context);
const otherTarget={dataset:{cEvidence:'FACT'},scrollIntoView:()=>{throw Error('must not open another panel');}};
const root={querySelectorAll:selector=>{assert.equal(selector,'.third-c-evidence-list [data-c-evidence]');return [target];}};
const details={tagName:'DETAILS',open:false,parentElement:root};
const materialBody={open:false};
const target={dataset:{cEvidence:'FACT'},querySelector:()=>materialBody,parentElement:details,scrollIntoView:()=>{target.scrolled=true;},focus:()=>{target.focused=true;}};
let prevented=false;
const anchor={dataset:{cLocalEvidence:'FACT'},closest:selector=>{assert.equal(selector,'.third-c-public-reading');return root;}};
const event={button:0,target:{closest:()=>anchor},preventDefault:()=>{prevented=true;}};
click(event);
assert.ok(prevented&&details.open&&target.scrolled&&target.focused);
assert.ok(materialBody.open,'the material body must open as well as its ancestors');
assert.equal(location.hash,'#compare/SYNTHETIC-A/SYNTHETIC-B');
assert.ok(!otherTarget.scrolled);
prevented=false;click({...event,ctrlKey:true});assert.equal(prevented,false,'modified clicks keep the canonical collection URL');
anchor.dataset.cLocalEvidence='MISSING';click(event);assert.equal(prevented,false,'missing local material keeps the canonical URL fallback');
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
