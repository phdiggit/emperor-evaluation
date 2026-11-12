"""Synthetic rendering checks: responsibility, missing data and adverse aliases."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_personal_archive_preserves_responsibility_boundaries(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader rendering")
    script = tmp_path / "military.cjs"
    script.write_text(r'''
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const app = {innerHTML:''};
const sandbox = {URL,document:{getElementById:()=>app,querySelector:()=>null},window:{addEventListener(){}}, console};
let source = fs.readFileSync(process.argv[2], 'utf8').replace(/\r\n/g, '\n');
source = source.replace('\n  route();\n})();', `
  battleIndex = {result_ref_to_battle:{}};
  this.api = {achievementBlock, resultLabel, directionName, militaryReadingParts, militaryProse, battleNarrative, async render(profile) {
    battleIndex = {result_ref_to_battle:{}};
    commanderByProfile.set('test',{source:'synthetic.json',name:'测试',profile_ref:'test'});
    cache.set('../synthetic.json',Promise.resolve({profiles:[{...profile,profile_ref:'test'}]}));
    await renderCommander('test',0);
    return app.innerHTML;
  }};
})();`);
// The IIFE uses lexical this from the VM global.
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(path.dirname(process.argv[2]),'source-links.js'),'utf8'),sandbox);
vm.runInContext(source, sandbox);
assert.equal(sandbox.api.directionName('mixed_review'), '正负并存');
assert.equal(sandbox.api.resultLabel('mixed_review'), '得失量级');
const raw='甲率军守城，城池未失；不复制整场战役A；乙独立增援。仅采用本条已有本人角色与成果范围；不继承整场战役、其他将领或其他周期。';
const parts=sandbox.api.militaryReadingParts(raw);
assert.equal(parts.original,raw);
assert(parts.facts.join('').includes('城池未失')&&parts.facts.join('').includes('乙独立增援'));
assert(parts.boundaries.join('').includes('不继承'));
const prose=sandbox.api.militaryProse(raw);
assert(prose.includes('不能把整场战役的A档直接作为本人的评价'));
assert(prose.includes('查看原始表述')&&prose.includes(raw));
assert(!prose.split('<details')[0].includes('不复制'));
assert.equal(sandbox.api.militaryReadingParts('正负并存的正负并存登记。').text,'正负并存登记。');
assert(sandbox.api.militaryProse('<img src=x onerror=1>攻城失败。').includes('&lt;img'));
assert(!sandbox.api.militaryReadingParts('没有攻下城池，不应把撤退当作胜利。').boundaries.length);
const item = {canonical_label:'设计方案',campaign_tier:'B',parent_campaign_tier:'S+',parent_combat_difficulty:'D4',result_direction:'positive'};
const html = sandbox.api.achievementBlock(item);
const main = html.split('<details>')[0];
assert(main.includes('个人任务难度未单列'));
assert(!main.includes('D4'));
assert(html.includes('整场难度 D4'));
const failure = {campaign_ref:'personal-loss',capability_episode_ref:'episode-loss',canonical_label:'一次失败',campaign_tier:'A',combat_difficulty:'D3',result_direction:'mixed_review'};
(async()=>{
  const rendered = await sandbox.api.render({person:'测试',military_grade:'capable',consumed_achievements:[item],negative_or_mixed_command_records:[failure],failure_accountability:[{...failure}],major_adverse_episode_refs:['episode-loss']});
  assert(!rendered.includes('待补事件说明'));
  assert.equal((rendered.match(/class="achievement"/g)||[]).length,2);
  assert(!rendered.includes('最高关联整场'));
  assert(rendered.includes('个人得失量级 A'));
  assert(!rendered.includes('synthetic.json'));
  assert(!rendered.includes('href=""'));
  assert(!rendered.includes('/blob/'));
})().catch(error=>{console.error(error);process.exitCode=1;});
''', encoding="utf-8")
    result = subprocess.run([node, str(script), str(ROOT / "reader/military-archive.js")], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
