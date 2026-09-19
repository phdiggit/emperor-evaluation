from pathlib import Path
import json
import shutil
import subprocess

import pytest

from emperor_v4.evaluation.first_item_c_public import (
    load_first_item_c_public, parse_declared_battles, project_commander,
    public_commander_for_name,
)

ROOT = Path(__file__).resolve().parents[1]


def test_battles_require_explicit_roles_and_preserve_declared_order():
    rows = parse_declared_battles('乙战｜战略统筹｜A｜—；甲战｜前线作战｜S-｜D3。')
    assert rows == [
        {'name': '乙战', 'role': '战略统筹', 'result': 'A', 'difficulty': ''},
        {'name': '甲战', 'role': '前线作战', 'result': 'S−', 'difficulty': 'A'},
    ]
    with pytest.raises(ValueError, match='禁止从判词补猜'):
        parse_declared_battles('甲战取得大捷，由谁指挥尚不明确。')
    with pytest.raises(ValueError, match='重复'):
        parse_declared_battles('甲战｜前线作战｜A｜D2；甲战｜战略统筹｜A｜—')


def test_narrative_never_creates_battle_entries_or_replaces_missing_public_prose():
    fields = {'公开裁决依据': '曾在甲战中取胜，但不证明亲自指挥。',
              '公开责任边界': '只能确认统筹，不能据此推出临阵指挥。',
              '结算依据': '甲战S/D3可能属于将领。'}
    assert project_commander(fields)['public_battles'] == []
    del fields['公开裁决依据']
    with pytest.raises(ValueError, match='禁止用内部判词回退'):
        project_commander(fields)


def test_current_reader_commander_fields_match_current_formal_source():
    public = load_first_item_c_public(ROOT)
    seen = set()
    for path in (ROOT / 'reader/data/people').glob('*.json'):
        record = json.loads(path.read_text(encoding='utf-8'))['record']
        net = record.get('net') or {}
        if net.get('first_item_status') != 'APPLICABLE':
            continue
        item = next(item for item in net['component_details']['first'] if item['label'] == 'C军事统帅与战争解题')
        expected = public_commander_for_name(public, record['ruler_name'])
        assert item['reader_public_commander'] == expected
        assert item['reader_summary'] == expected['public_basis']
        assert item['reader_boundary'] == expected['public_boundary']
        seen.add(record['ruler_id'])
    assert seen


def test_all_browser_paths_render_basis_and_boundary_even_with_battles(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for browser behavior')
    script = tmp_path / 'commander.cjs'
    script.write_text(r'''
const fs=require('node:fs'), assert=require('node:assert/strict');
const source=fs.readFileSync('reader/home-interactions.js','utf8');
const fn=source.match(/function firstCommanderMarkup\(item\) {[\s\S]*?\n}\n/)[0];
const escape=text=>String(text).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const render=new Function('esc','prose',fn+';return firstCommanderMarkup;')(escape,text=>'<p>'+escape(text)+'</p>');
const publicData={public_basis:'正面表现不能掩盖失败。',public_boundary:'不属于本人指挥。<原句>',
 public_battles:[{name:'甲战',role:'战略统筹',result:'A',difficulty:''}]};
const html=render({reader_public_commander:publicData});
assert.ok(html.includes(publicData.public_basis));
assert.ok(html.includes(escape(publicData.public_boundary)));
assert.ok(html.includes('战略统筹'));
assert.ok(html.includes('难度未单列'));
assert.ok(!html.includes('前线作战'));
assert.ok(!render({reader_public_commander:{...publicData,public_battles:[]}}).includes('first-item-battles'));
assert.ok(render({reader_summary:'甲战取得大捷'}).includes('公开说明尚未同步'));
for(const path of ['reader/home-interactions.js','reader/person-readability.js','reader/first-item-reading.js']){
 const text=fs.readFileSync(path,'utf8');
 assert.ok(text.includes('firstCommanderMarkup(item)'));
 assert.ok(!/fallbackBattleAnchors|structuredBattleAnchors|publicCommanderText/.test(text));
}
const lazy=fs.readFileSync('reader/lazy-details.js','utf8');
const begin=lazy.indexOf('  function simplifyFirstItemSourceLinks(');
const finish=lazy.indexOf('\n  async function loadRecord',begin+1);
const makeSource=keep=>({removed:false,hasAttribute:key=>keep&&key==='data-formal-public-source',
 querySelector:()=>({textContent:'裁决依据与来源'}),remove(){this.removed=true;}});
const current=makeSource(true),legacy=makeSource(false);
const document={querySelector:()=>({querySelectorAll:()=>[current,legacy],querySelector:()=>({})})};
new Function('document',lazy.slice(begin,finish)+';simplifyFirstItemSourceLinks();')(document);
assert.equal(current.removed,false);
assert.equal(legacy.removed,false);
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
