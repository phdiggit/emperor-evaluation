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
  this.api = {achievementBlock, resultLabel, directionName, militaryReadingParts, militaryProse, battleNarrative, battleMembers, battleAssessment, phaseSections, setInferencePolicy(policy) {
    battleIndex.personnel_inference_reading = policy;
  }, async render(profile) {
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
const namedAction = '率本部从东岸渡河。守住渡口后移交军粮。';
const participant = {actor_name:'具名甲',role_code:'independent_direction',
  person_command_result:[{basis:namedAction,result_tier:'A',combat_difficulty:'D2',result_direction:'POSITIVE'}]};
const battle = {members:[participant]};
const reading = sandbox.api.battleNarrative(battle,{reading_context:{actions:[
  {person:participant.actor_name,text:namedAction}
]}});
assert.ok(reading.html.includes('率本部从东岸渡河。'));
const memberOnly = sandbox.api.battleMembers(battle,true,reading.shownActions);
assert.ok(memberOnly.includes('具名甲') && memberOnly.includes('D2'));
assert.ok(!memberOnly.includes('率本部从东岸渡河。'));
assert.ok(sandbox.api.battleMembers({members:[participant,{...participant,actor_ref:'another'}]},true,reading.shownActions)
  .includes('率本部从东岸渡河。'));
const extra = {...participant,person_command_result:[{...participant.person_command_result[0],
  basis:namedAction+'移交范围仅限东岸仓口。'}]};
assert.ok(sandbox.api.battleMembers({members:[extra]},true,reading.shownActions).includes('移交范围仅限东岸仓口。'));
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
const account='援军接通了城内补给。';
const assessment=sandbox.api.battleAssessment({
  campaign_tier:'B', combat_difficulty:'D2', result_direction:'victory',
  observable_result:account, tier_basis:account, combat_difficulty_basis:'险路限制运粮。'
},{reading_context:{process:account}});
assert(!assessment.includes(account));
assert(!assessment.includes('结果档依据'));
assert(assessment.includes('险路限制运粮。'));
assert(assessment.includes('战役登记结果量级 B'));
const phases=sandbox.api.phaseSections([
  {phase_id:'P1',evaluation_subject_phase:'守城阶段',cost_axes:{P:'守军伤亡已登记。'}},
  {phase_id:'P2',evaluation_subject_phase:'援军阶段',cost_axes:{M:'援军调动已登记。'}}
]);
assert.equal(phases.split('各阶段的成本按实际承担主体列示').length-1,1);
assert(phases.indexOf('id="P1"')<phases.indexOf('id="P2"'));
assert(phases.includes('守军伤亡已登记。')&&phases.includes('援军调动已登记。'));
const policy = {
  title:'人员损害读法',observed_title:'原载损害',observed_note:'原载说明须分清对象。',
  missing_observed:'本阶段未单列观察值。',legacy_title:'旧推定依据',legacy_note:'旧估值用于追溯。',
  current_title:'现行采用',current_note:'现行确认须另核对下界。'
};
sandbox.api.setInferencePolicy(policy);
const inference = sandbox.api.phaseSections([
  {phase_id:'P1',P_inference:{P_observed:'本阶段原文记载的损失。',basis:'甲阶段的旧估依据。'}},
  {phase_id:'P2',P_inference:{basis:'乙阶段的旧估依据。'}}
]);
for(const text of [policy.observed_note,policy.current_note,policy.legacy_note])assert.equal(inference.split(text).length,2);
for(const text of ['本阶段原文记载的损失。','甲阶段的旧估依据。','乙阶段的旧估依据。',policy.missing_observed])
  assert.ok(inference.includes(text));
assert.ok(inference.indexOf('乙阶段的旧估依据。')<inference.indexOf(policy.current_note));
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
  const blocked = await sandbox.api.render({person:'测试',military_grade:'capable',
    rule_path:'elite_blocked_by_failure_pressure',stability_gate:{stability_cap_applied:true,
      major_positive_context_count:1,major_adverse_context_count:1}});
  assert.equal(blocked.split('重大失败限制了精英级路径。').length,2);
  assert.ok(!blocked.includes('重大失败已限制最终总档。')&&blocked.includes('1 项重大不利情境'));
})().catch(error=>{console.error(error);process.exitCode=1;});
''', encoding="utf-8")
    result = subprocess.run([node, str(script), str(ROOT / "reader/military-archive.js")], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
