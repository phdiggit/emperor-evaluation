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
const start = source.indexOf('  function publicText(');
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
vm.runInContext(source.slice(start, end) + '\nthis.renderFacts=publicFacts; this.renderText=publicText; this.renderList=publicEvidenceList;', context);
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
          const text = String(evidence[i][key] || '').trim();
          if (text) assert.ok(rendered[i].includes(text), `${name}/${item.label}/${key}`);
          if (text) assert.ok(cards[i].textContent.includes(text), `${name}/${item.label}/${key}/card`);
        }
      }
      assert.equal(context.renderText(item.reader_boundary), String(item.reader_boundary || '').trim());
      checked++;
    }
  }
}
assert.ok(checked > 0);
// Both the displayed evidence and the outer boundary must use the same lossless formatter.
assert.match(source, /makeDetails\("范围与边界", publicText\(item\.reader_boundary/);
assert.match(source, /reading\.append\(publicEvidenceList\(evidence\)\)/);
assert.match(source, /if \(label === "A制度建设" \|\| label === "B1官僚治理"\) continue/);
console.log('verified public components:', checked);
''', encoding='utf-8')
    subprocess.run([node, str(script), str(ROOT)], check=True, capture_output=True, text=True, encoding='utf-8')
