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
