"""Public verdict prose survives browser rendering without semantic rewriting."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


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
  return {tag, children:[], ownText:'',
    append(...nodes){this.children.push(...nodes);},
    set textContent(value){this.ownText=value;},
    get textContent(){return this.ownText+this.children.map(node=>node.textContent).join('');}
  };
}}};
vm.createContext(context);
vm.runInContext(source.slice(start, end) + '\nthis.renderFacts=publicFacts; this.renderText=publicText; this.renderList=publicEvidenceList; this.enumText=publicEnumText; this.financeText=publicFinanceText;', context);
for (const [raw,shown] of Object.entries({
  '五档':'A档','第五档':'A档','四档':'B档','第四档':'B档',
  '三档':'C档','第三档':'C档','二档':'D档','第二档':'D档',
  '一档':'E档','第一档':'E档','六档':'S档','第六档':'S档'
})) assert.equal(context.financeText(raw),shown);
assert.equal(context.financeText('中期支持五档，但长期阻断六档；主态维持四档。'),'中期支持A档，但长期阻断S档；主态维持B档。');
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
  assert.equal(context.renderText(text), text);
  const item = {reader_public_evidence_items:[{public_label:'依据',public_basis:text,public_boundary:'不重复计入。'}]};
  assert.deepEqual(Array.from(context.renderFacts(item)), ['依据；'+text+'；边界：不重复计入。']);
  const card = context.renderList(item.reader_public_evidence_items).children[0];
  assert.equal(card.children[1].textContent, text);
  assert.equal(card.children[2].tag, 'details');
  assert.ok(card.children[2].textContent.includes('不重复计入。'));
}
let checked = 0;
for (const name of fs.readdirSync(path.join(root,'reader/data/people'))) {
  const record = JSON.parse(fs.readFileSync(path.join(root,'reader/data/people',name),'utf8')).record;
  for (const group of ['method','finance','handoff']) {
    for (const item of record?.net?.component_details?.[group] || []) {
      const evidence = item.reader_public_evidence_items;
      if (!Array.isArray(evidence) || !evidence.length) continue;
      const rendered = Array.from(context.renderFacts(item));
      const cards = context.renderList(evidence).children;
      assert.equal(rendered.length, evidence.length);
      for (let i=0;i<evidence.length;i++) {
        for (const key of ['public_label','public_direction','public_basis','public_boundary']) {
          const raw = String(evidence[i][key] || '').trim();
          const shown = context.enumText(raw);
          if (shown) assert.ok(rendered[i].includes(shown), `${name}/${item.label}/${key}`);
          if (shown) assert.ok(cards[i].textContent.includes(shown), `${name}/${item.label}/${key}/card`);
        }
      }
      assert.equal(context.renderText(item.reader_boundary), context.enumText(String(item.reader_boundary || '').trim()));
      checked++;
    }
  }
}
assert.ok(checked > 0);
// Both the displayed evidence and the outer boundary must use the same lossless formatter.
assert.match(source, /const financeItem = \["C1民生","C2经济财政","C3社会安全","C4恢复与成本"\]\.includes\(label\)/);
assert.match(source, /makeDetails\("范围与边界", financeItem \? publicFinanceText\(item\.reader_boundary/);
assert.match(source, /: publicText\(item\.reader_boundary/);
assert.match(source, /body: publicFinanceText\(entry\?\.public_basis\)/);
assert.match(source, /label === "B2反馈与约束"/);
assert.match(source, /renderB2MaterialGroups\(evidence\)/);
assert.match(source, /if \(label === "A制度建设" \|\| label === "B1官僚治理"\) continue/);
console.log('verified public components:', checked);
''', encoding='utf-8')
    subprocess.run([node, str(script), str(ROOT)], check=True, capture_output=True, text=True, encoding='utf-8')


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
 +section(labels,'  function patchLabelNode(','  function currentPersonId(')
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


def test_a_and_b1_dedicated_renderers_only_consume_built_row_public_projection():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    a = (root / "reader/second-item-a-public.js").read_text(encoding="utf-8")
    b1 = (root / "reader/second-item-b1-public.js").read_text(encoding="utf-8")

    for source in (a, b1):
        assert "reader_public_evidence_items" in source
        assert "reader_summary" in source
        assert "reader_boundary" in source
        assert "fetch(" not in source
        assert "repoJson" not in source

    assert "public_institution_nodes" not in a
    assert "formalA" not in a

    for forbidden in (
        "PROFILE_KEYS",
        "M_positive_profile",
        "M_mixed_profile",
        "M_negative_profile",
        "formalB1",
        "adjudication_status",
        "absorbed_into_profile_id",
        "signed_weight",
    ):
        assert forbidden not in b1

    assert "public_direction" in b1
    assert "public_tags" in b1
    assert "并入同一运行链" in b1
    assert "不单独计入" in b1


def test_second_item_public_enum_mapping_and_dedicated_ownership():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    a = (root / "reader/second-item-a-public.js").read_text(encoding="utf-8")
    b1 = (root / "reader/second-item-b1-public.js").read_text(encoding="utf-8")
    assert 'SecondItemMaterialCards' in alias
    assert 'renderB2MaterialGroups(evidence)' in alias
    assert 'MATERIAL_STRENGTH_TAGS' in alias
    assert 'A制度建设":"制度建设"' in alias
    assert 'B1官僚治理":"官僚治理"' in alias
    assert 'B2反馈与约束":"反馈与约束"' in alias
    assert 'secondMethodDetailsMarkup(item, record)' not in a
    assert 'secondMethodDetailsMarkup(item, record)' not in b1
    assert 'secondPublicOwner = "A"' in a
    assert 'secondPublicOwner = "B1"' in b1
    assert 'SecondItemMaterialCards' in a
    assert 'SecondItemMaterialCards' in b1


def test_finance_public_cards_group_only_by_formal_public_role():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "function financeRoleKey(role)" in alias
    assert 'value === "主要状态"' in alias
    assert 'value === "低谷"' in alias
    assert 'value === "边界"' in alias
    assert 'value === "恢复" || value === "责任范围"' in alias
    assert 'value === "状态恶化" || value === "额外代价"' in alias
    assert "materialStrengthFromTags(entry" not in alias


def test_handoff_public_cards_group_only_by_formal_public_role():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    alias = (root / "reader/second-item-public-alias.js").read_text(encoding="utf-8")
    assert "function renderHandoffMaterialGroups(label, evidence)" in alias
    assert 'role === "事前安排"' in alias
    assert 'role === "交接结果" || role === "终局事实"' in alias
    assert 'role === "前任行政资产承接"' in alias
