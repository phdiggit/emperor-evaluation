"""Public verdict prose survives browser rendering without semantic rewriting."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_second_overview_scores_render_final_text_without_alias_patch(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for reader behavior')
    script = tmp_path / 'second-overview-scores.cjs'
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/second-item-reading.js','utf8');
function section(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert.ok(a>=0&&b>a);return source.slice(a,b);}
const score={dataset:{},textContent:''},description={dataset:{},textContent:'',classList:{contains:()=>false}};
const card={classList:{add(){}},getAttribute:()=> '#net/synthetic/second',
 querySelector:selector=>selector==='.big'?score:null,querySelectorAll:()=>[description]};
const context={location:{hash:'#net/synthetic/all'},document:{querySelectorAll:()=>[card]}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('reader/second-item-display.js','utf8'),context);
vm.runInContext(section('  const {','  function ensureStyles(')
 +section('  function ensureLandingCard(','  function ensureSecondSummary(')
 +section('  function pendingSecondLabel(','  function enhanceNetRoute('),context);
for(const [value,expected] of [[0,'0.0 分'],[-2.5,'-2.5 分'],[12.25,'12.3 分'],[null,'—']]){
 context.ensureLandingCard({}, {totalScore:value});
 assert.equal(score.textContent,expected);
}
const cells=[{dataset:{},textContent:'治国成效'}, {dataset:{}}, {dataset:{},textContent:''}];
context.screenEl={querySelectorAll:()=>[{cells}]};
const settled={detail_loaded:true,net:{second_item_score:0,component_details:{}}};
const pending={detail_loaded:true,settlement_readiness:'PENDING_SECOND_ITEM_FORMAL_SETTLEMENT'};
context.enhanceCompare([settled,pending]);
assert.equal(cells[1].innerHTML,'<b>0.0 分</b>');
assert.equal(cells[2].textContent,'待正式结算');
settled.net.second_item_score=-2.5;
context.enhanceCompare([settled,pending]);
assert.equal(cells[1].innerHTML,'<b>-2.5 分</b>');
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_second_public_facts_preserve_sentences_boundaries_and_current_records(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for reader behavior')
    script = tmp_path / 'second-public-text.cjs'
    script.write_text(r'''
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = process.argv[2];
const source = fs.readFileSync(path.join(root, 'reader/second-item-public-alias.js'), 'utf8');
const start = source.indexOf('  const PUBLIC_GRADE');
const end = source.indexOf('  function patchMetricBodies(', start);
assert.ok(start > 0 && end > start);
const context = {document:{createElement(tag){
  return {tag, children:[], ownText:'', dataset:{},
    append(...nodes){this.children.push(...nodes);},
    replaceChildren(...nodes){this.children=[...nodes];},
    get childNodes(){return this.children;},
    set textContent(value){this.ownText=value;},
    get textContent(){return this.ownText+this.children.map(node=>node.textContent).join('');}
  };
}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'reader/second-item-display.js'), 'utf8'), context);
context.document.createDocumentFragment=()=>context.document.createElement('fragment');
vm.runInContext(source.slice(start, end) + '\nthis.renderB2=b2Reading; this.renderFacts=publicFacts; this.renderText=publicText; this.renderList=publicEvidenceList; this.enumText=publicEnumText; this.financeText=publicFinanceText; this.boundaryText=publicBoundaryText; this.financeText=publicFinanceText; this.financeBoundaryText=publicFinanceBoundaryText;', context);
const b2Text='部分意见获采，但晚期保护失败；不据缺证推定不存在。';
const b2=context.renderB2({reader_summary:b2Text,reader_public_evidence_items:[
 {id:'synthetic-positive',public_label:'一条机制',public_direction:'正向主导',public_tags:['部分阶段不另计'],public_basis:'当面劝阻后改变决定，后来又有受罚。',public_boundary:'只合并该次前后过程。',source_refs:[{source_title:'合成史源',source_locator:'合成定位',exact_quote:'合成原引文'}]},
 {id:'synthetic-background',public_label:'背景',public_direction:'正向',public_tags:['背景材料'],public_basis:'只证明设置渠道，尚未证明实际纠正。',public_boundary:'整条不计。',source_refs:[]}
]});
for(const text of [b2Text,'正向主导','部分阶段不另计','只合并该次前后过程。','合成原引文','尚未证明实际纠正','背景材料'])assert.ok(b2.textContent.includes(text),text);
for (const raw of ['第五档；不等于损害轻微。','后任结果不得倒灌。','<不是HTML> & “原句”。']) assert.equal(context.financeText(raw),raw);
assert.equal(context.financeBoundaryText('第五档；第五档；'),'第五档；第五档；');
const fragments = [
  '保留恢复的责任范围：本人主导。',
  '未过较高档门，但不等于没有改善。',
  '阻断更高档，但不足以下调当前档。',
  '只证明运转，不重复结算其他收益。',
  '‘已平。’',
  '否。',
  '<不是HTML> & “短句也必须保留。”',
];
for (const text of fragments) {
  const shownText = context.renderText(text);
  const item = {reader_public_evidence_items:[{public_label:'依据',public_basis:text,public_boundary:'不重复计入。'}]};
  assert.deepEqual(Array.from(context.renderFacts(item)), [context.renderText('依据；'+shownText+'；边界：不重复计入。')]);
  const card = context.renderList(item.reader_public_evidence_items).children[0];
  assert.equal(card.children[1].textContent, shownText);
  assert.equal(card.children[2].tag, 'details');
  assert.ok(card.children[2].textContent.includes('不重复计入。'));
}
// Every current second-item judgment now has a dedicated renderer. The generic
// helpers above are tested with representative fragments only; record-wide
// semantics are covered by the formal public-projection validators and the
// renderer ownership assertions below.
// Public cards use declared reader wording plus presentation-only cleanup; formal source text remains in the audit fold.
''', encoding='utf-8')
    completed = subprocess.run([node, str(script), str(ROOT)], check=False, capture_output=True, text=True, encoding='utf-8')
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_public_values_are_real_text_and_structural_updates_respect_ownership(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for reader behavior')
    script = tmp_path / 'public-dom-text.cjs'
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const alias=fs.readFileSync('reader/second-item-public-alias.js','utf8');
const labels=fs.readFileSync('reader/second-item-public-labels.js','utf8');
const structural=fs.readFileSync('reader/second-item-reading.js','utf8');
function section(source,start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert.ok(a>=0&&b>a);return source.slice(a,b);}
let mutations=0;
class Text {
 constructor(value){this.nodeType=3;this.value=value;}
 get nodeValue(){return this.value;}set nodeValue(value){this.value=value;mutations++;}
 get textContent(){return this.value;}
}
class Element {
 constructor(tag){this.nodeType=1;this.tag=tag;this.childNodes=[];this.dataset={};this.className='';this.classList={add(){}};}
 get textContent(){return this.childNodes.map(n=>n.textContent).join('');}
 set textContent(value){mutations++;this.childNodes=value?[new Text(value)]:[];}
 append(...nodes){mutations++;for(const n of nodes){this.childNodes.push(n);n.parent=this;}}
 insertBefore(node,before){mutations++;const i=this.childNodes.indexOf(before);this.childNodes.splice(i<0?this.childNodes.length:i,0,node);node.parent=this;}
 get firstChild(){return this.childNodes[0]||null;}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
 querySelectorAll(selector){const name=selector.replace(':scope > ','');return this.childNodes.filter(n=>n.nodeType===1&&(name.startsWith('.')?n.className.split(' ').includes(name.slice(1)):n.tag===name));}
 remove(){mutations++;this.parent.childNodes.splice(this.parent.childNodes.indexOf(this),1);}
}
const context={Node:{TEXT_NODE:3},document:{createElement:tag=>new Element(tag),createTextNode:value=>new Text(value)}};
vm.createContext(context);
vm.runInContext(section(alias,'  function setPublicText(','  function patchMethodGrades(')
 +section(labels,'  function patchLabelNode(','  function ensureStyles(')
 +section(structural,'  function setNodeText(','  function safeText(')
 +section(structural,'  function replaceCompactNote(','  function formatCompactGroup('),context);
const value=new Element('b'),span=new Element('span'),strong=new Element('strong'),note=new Element('small'),link=new Element('a');
strong.textContent='内部标题（A）';note.className='second-item-scale-note';note.textContent='旧注释';link.textContent='来源';span.append(strong,note,link);
context.setPublicGrade(span,value,'B',['公开注释','限制不能删除']);
context.patchLabelNode(span,'公开标题');
assert.equal(value.textContent,'B');assert.equal(strong.textContent,'公开标题');
assert.equal(note.textContent,'公开注释｜限制不能删除');assert.ok(span.childNodes.includes(link));
context.setNodeText(value,'旧指数');context.setNodeText(strong,'内部标题（A）');
context.replaceCompactNote(span,'旧注释');
assert.equal(value.textContent,'B');assert.equal(strong.textContent,'公开标题');assert.equal(note.textContent,'公开注释｜限制不能删除');
const compact=new Element('span');compact.append(new Text('原始代号 '),note,link);
context.patchLabelNode(compact,'公开名称');context.setRowLabel(compact,'原始代号');
assert.equal(compact.childNodes[0].textContent,'公开名称 ');assert.ok(compact.childNodes.includes(note));assert.ok(compact.childNodes.includes(link));
const score=new Element('b'),copy=new Element('p');
context.writePublicScore(score,'0.0 分');context.writePublicCopy(copy,'公开说明，不能省略限制。');
context.setNodeText(score,'旧值');context.setNodeText(copy,'旧文案');
assert.equal(score.textContent,'0.0 分');assert.equal(copy.textContent,'公开说明，不能省略限制。');
// Public ownership does not freeze future public updates.
context.writePublicScore(score,'12.3 分');assert.equal(score.textContent,'12.3 分');
const idle=mutations;
for(let i=0;i<10;i++){
 context.setPublicGrade(span,value,'B',['公开注释','限制不能删除']);context.patchLabelNode(span,'公开标题');
 context.patchLabelNode(compact,'公开名称');context.setRowLabel(compact,'原始代号');
 context.writePublicScore(score,'12.3 分');context.setNodeText(score,'旧值');
 context.writePublicCopy(copy,'公开说明，不能省略限制。');context.setNodeText(copy,'旧文案');
}
assert.equal(mutations,idle,'repeated observer passes must settle without text churn');
for(const source of [alias,labels]){
 assert.doesNotMatch(source,/font-size\s*:\s*0(?:\D|$)/);
 assert.doesNotMatch(source,/content\s*:\s*attr\(data-public-/);
}
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
