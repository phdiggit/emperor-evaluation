"""Full formal coverage and C navigation behavior, without frozen judgments."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

import pytest
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.third_fourth_item_public import FOURTH_PATH
from emperor_v4.evaluation.fourth_item_c_public import axis_reading

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    spec=importlib.util.spec_from_file_location('fourth_c_'+name,ROOT/'reader'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def collection():
    html=(ROOT/'reader/fourth-item-c.html').read_text(encoding='utf-8')
    marker='<script id="fourth-c-data" type="application/json">'
    start=html.index(marker)+len(marker)
    return html,json.loads(html[start:html.index('</script>',start)])


def test_collection_covers_formal_records_and_links_only_available_reader_routes():
    html,rows=collection()
    payload=load_json(ROOT/FOURTH_PATH)
    formal={r['ruler_id']:r for r in payload['records']}
    packages={p['package_code']:p for p in payload['accepted_packages']}
    pool=load_json(ROOT/'config/common/canonical-ruler-pool.json')['records']
    included={r.get('source_item_ids',{}).get('fourth_item',r['ruler_id']):r for r in pool if r['pool_status']=='INCLUDED'}
    assert len(rows)==len(formal) and {r['ruler_id'] for r in rows}==set(formal)
    assert rows==sorted(rows,key=lambda r:(r['ruler_name'],r['ruler_id']))
    for r in rows:
        f=formal[r['ruler_id']];a=next(a for a in f['axis_results'] if a['axis']=='C')
        assert r['item']['reader_public_fourth_c']==axis_reading(f,a,packages)
        assert r['item']['reader_c_collection_id']==r['ruler_id']
        scope=included.get(r['ruler_id'])
        assert bool(r['person_href'])==bool(scope)
        assert bool(r['detail_href'])==bool(scope and scope['settlement_readiness']=='COMPOSITE_READY')
        if scope:
            rid=quote(scope['ruler_id'],safe='')
            assert r['person_href']==f'index.html#person/{rid}'
            if r['detail_href']: assert r['detail_href']==f'index.html#net/{rid}/fourth/c'
    for path in (ROOT/'reader/data/people').glob('*.json'):
        person=json.loads(path.read_text(encoding='utf-8'))['record']
        if person['supplementary']: continue
        assert person['fourth_c_collection_ref'] in formal
        summary=module('build').record_summary(person)
        assert summary['fourth_c_collection_ref']==person['fourth_c_collection_ref']


def run_node(tmp_path,source):
    node=shutil.which('node')
    if not node: pytest.skip('Node.js required for navigation behavior')
    path=tmp_path/'behavior.cjs';path.write_text(source,encoding='utf-8')
    result=subprocess.run([node,str(path),str(ROOT)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr


def test_collection_search_hash_recovery_and_shared_entry_links(tmp_path):
    run_node(tmp_path,r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),path=require('path');
const root=process.argv[2],html=fs.readFileSync(path.join(root,'reader/fourth-item-c.html'),'utf8');
const raw=html.split('<script id="fourth-c-data" type="application/json">')[1].split('</script>')[0],data=JSON.parse(raw);
const decode=s=>s.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&amp;/g,'&');
let entries=[];const events={},nodes={};
for(const id of ['search','count','location-note'])nodes[id]={value:'',textContent:'',addEventListener:(event,cb)=>{events[id+':'+event]=cb;}};
nodes['fourth-c-data']={textContent:raw};
nodes.entries={set innerHTML(text){entries=[...text.matchAll(/<article class="person" id="([^"]+)">([\s\S]*?)(?=<article class="person" id=|$)/g)].map(m=>({id:decode(m[1]),textContent:decode(m[2].replace(/<[^>]*>/g,'')),hidden:false,scrolled:0,contains(target){return target===this;},scrollIntoView(){this.scrolled++;}}));}};
const location={hostname:'127.0.0.1',hash:'#'+encodeURIComponent(data[0].ruler_id)};
const states=new Map();
const history={get state(){return states.get(location.hash);},replaceState(state){states.set(location.hash,state);}};
const document={
 getElementById:id=>nodes[id]??entries.find(entry=>entry.id===id),
 querySelectorAll:()=>entries.map(entry=>Object.assign(entry,{querySelector(selector){
  assert.equal(selector,'.fourth-c-public-reading');
  return {before(reading){entry.reading=reading;}};
 }})),
 createElement:tag=>({tag,open:false,append(){}})
};
const ctx={URL,location,history,document,addEventListener:(event,cb)=>{events[event]=cb;}};
vm.createContext(ctx);
for(const script of html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)){
 if(script[1].includes('application/json'))continue;
 const src=script[1].match(/\bsrc="([^"]+)"/)?.[1];
 if(src)vm.runInContext(fs.readFileSync(path.join(root,'reader',src),'utf8'),ctx);
 else vm.runInContext(script[2],ctx);
}
assert.equal(entries.length,data.length);assert.equal(entries[0].scrolled,1);
assert.equal(entries[0].reading.open,true);
assert.equal(entries[1].reading.open,false);
nodes.search.value=data[0].ruler_name;events['search:input']();assert.equal(entries[0].hidden,false);
nodes.search.value='__NO_SUCH_SYNTHETIC_TERM__';events['search:input']();assert.equal(nodes.count.textContent,0);
ctx.location.hash='#'+encodeURIComponent(data[1].ruler_id);events.hashchange();
assert.equal(nodes.search.value,'');assert.equal(nodes.count.textContent,data.length);assert.equal(entries[1].hidden,false);assert.equal(entries[1].scrolled,1);
assert.equal(entries[1].reading.open,true);
ctx.location.hash='#'+encodeURIComponent(data[0].ruler_id);events.hashchange();
assert.equal(nodes.search.value,'__NO_SUCH_SYNTHETIC_TERM__');assert.equal(nodes.count.textContent,0);assert.equal(entries[0].hidden,true);
ctx.location.hash='#%E0%A4%A';events.hashchange();assert(nodes['location-note'].textContent.length>0);
for(const r of data){const nav=ctx.FourthItemCReading.entryLinks(r,{collection:true});if(r.person_href)assert(nav.includes(r.person_href));else assert(!nav.includes('#person/'));if(r.detail_href)assert(nav.includes(r.detail_href));else assert(!nav.includes('#net/'));}
const nav=ctx.FourthItemCReading.entryLinks({ruler_id:'canonical id',fourth_c_collection_ref:'formal id',net:{}});
assert(nav.includes('fourth-item-c.html#formal%20id'));assert(nav.includes('#net/canonical%20id/fourth/c'));
const pending=ctx.FourthItemCReading.entryLinks({ruler_id:'pending',fourth_c_collection_ref:'formal',net:null});
assert(pending.includes('fourth-item-c.html#formal'));assert(!pending.includes('#net/'));
''')


def test_fourth_detail_focus_scrolls_to_c_card_and_preserves_group_focus(tmp_path):
    run_node(tmp_path,r'''
const fs=require('fs'),assert=require('assert/strict'),path=require('path');
const text=fs.readFileSync(path.join(process.argv[2],'reader/home-interactions.js'),'utf8');
const begin=text.indexOf('  function renderGenericMajor('),end=text.indexOf('\n  function majorNav(',begin),code=text.slice(begin,end);
let c=0,group=0;
const card={scrollIntoView(){c++;}},old={scrollIntoView(){group++;}},container={innerHTML:''};
const document={getElementById(id){if(id==='net-major-body')return container;if(id==='net-group-c')return card;assert.equal(id,'net-group-civilization');return old;}};
const fn=new Function('document','requestAnimationFrame','netMajorSpecs','genericNetGroup',code+';return renderGenericMajor;')(document,cb=>cb(),{fourth:{groups:['civilization']}},()=>'<article>完整正文</article>');
fn({net:{component_details:{civilization:[]}}},'fourth','c');assert.equal(c,1);assert.equal(group,0);
fn({net:{component_details:{civilization:[]}}},'fourth','civilization');assert.equal(c,1);assert.equal(group,1);
''')
