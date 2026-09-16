"""First-item reader source slices stay isolated per person."""

import shutil
import subprocess

import pytest


def test_first_item_source_caches_are_scoped_by_ruler_and_accept_formal_aliases(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for first-item reader behavior")

    script = tmp_path / "first_item_source_scope.cjs"
    script.write_text(
        r'''
const fs = require("node:fs");
const assert = require("node:assert/strict");

const specs = [
  {
    path: process.argv[2],
    loaderStart: "  function rawUrl",
    loaderEnd: "\n  function bulletForName",
    cacheName: "docCache",
    loaderName: "loadDoc",
    parserStart: "  function bulletForName",
    parserEnd: "\n  function itemMap",
    parserName: "bullets",
  },
  {
    path: process.argv[3],
    loaderStart: "  function firstItemRawUrl",
    loaderEnd: "\n  function firstItemBulletsForName",
    cacheName: "firstItemDocCache",
    loaderName: "loadFirstItemDoc",
    parserStart: "  function firstItemBulletsForName",
    parserEnd: "\n  function firstItemPublicText",
    parserName: "firstItemBullets",
  },
  {
    path: process.argv[4],
    loaderStart: "  function firstItemRawUrl",
    loaderEnd: "\n  function firstItemBulletsForName",
    cacheName: "firstItemDocCache",
    loaderName: "loadFirstItemDoc",
    parserStart: "  function firstItemBulletsForName",
    parserEnd: "\n  function firstItemPublicText",
    parserName: "firstItemBullets",
  },
];

(async () => {
  for (const spec of specs) {
    const source = fs.readFileSync(spec.path, "utf8");
    const loaderStart = source.indexOf(spec.loaderStart);
    const loaderEnd = source.indexOf(spec.loaderEnd, loaderStart);
    assert.ok(loaderStart >= 0 && loaderEnd > loaderStart, `${spec.path}: loader fragment not found`);

    const requests = [];
    const fakeFetch = async url => {
      requests.push(String(url));
      return {ok: true, text: async () => `response:${requests.length}`};
    };
    const currentRecord = () => ({ruler_id: "fallback"});
    const loader = new Function(
      "fetch",
      "currentRecord",
      `const ${spec.cacheName} = new Map();${source.slice(loaderStart, loaderEnd)};return ${spec.loaderName};`,
    )(fakeFetch, currentRecord);

    const first = await loader("docs/first-item.md", {ruler_id: "RULER-A"});
    const second = await loader("docs/first-item.md", {ruler_id: "RULER-B"});
    assert.notEqual(await first, await second, `${spec.path}: two rulers reused one source promise`);
    assert.equal(requests.length, 2, `${spec.path}: source cache was not keyed by ruler`);

    const parserStart = source.indexOf(spec.parserStart);
    const parserEnd = source.indexOf(spec.parserEnd, parserStart);
    assert.ok(parserStart >= 0 && parserEnd > parserStart, `${spec.path}: parser fragment not found`);
    const parse = new Function(`${source.slice(parserStart, parserEnd)};return ${spec.parserName};`)();
    const fields = parse("### 1. 正式名\n\n- **事实**：正式材料\n", ["展示名", "正式名"]);
    assert.equal(fields["事实"], "正式材料", `${spec.path}: formal-name fallback failed`);
  }

  const publicSource = fs.readFileSync(specs[0].path, "utf8");
  const publicStart = publicSource.indexOf("  function publicFact");
  const publicEnd = publicSource.indexOf("\n  function outcomePercent", publicStart);
  assert.ok(publicStart >= 0 && publicEnd > publicStart, "public reader helpers not found");
  const publicHelpers = new Function(
    `${publicSource.slice(publicStart, publicEnd)};return {publicOutcomeText,publicCommanderText};`,
  )();
  const outcome = publicHelpers.publicOutcomeText(
    "从秦国在关中、巴蜀、汉中等既有核心区域起步，先后取得韩、赵、魏、楚、燕、齐，完成六国统一。",
  );
  assert.equal(outcome, "从秦国在关中、巴蜀、汉中等既有核心区域起步，先后取得韩、赵、魏、楚、燕、齐，完成六国统一。");
  assert.doesNotMatch(outcome, /单位|控制信用|有效控制信用/);
  const technicalOutcome = publicHelpers.publicOutcomeText("从甲地起步，取得乙地；个人分得123控制信用。");
  assert.doesNotMatch(technicalOutcome, /单位|控制信用|有效控制信用/);

  const commander = publicHelpers.publicCommanderText(
    "统帅证据：甲君的具体军事统帅信用已闭合到将领甲、将领乙等责任中心；甲君的最高层决策与将帅选择由B2等轴承接，现有登记不足以证明其本人承担具体战争统帅责任，因此C为0。",
  );
  assert.match(commander, /亲自统领具体战役/);
  assert.doesNotMatch(commander, /统帅证据|责任中心|B2|C为0|\/D[0-4]/);

  const battleStart = publicSource.indexOf("  function normalizeResultGrade");
  const battleEnd = publicSource.indexOf("\n  function renderBattles", battleStart);
  assert.ok(battleStart >= 0 && battleEnd > battleStart, "battle-list helpers not found");
  const parseBattles = new Function(
    "D_GRADES",
    `${publicSource.slice(battleStart, battleEnd)};return structuredBattleAnchors;`,
  )(["D", "C", "B", "A", "S"]);
  assert.deepEqual(
    parseBattles("甲战｜前线作战｜A｜D3；乙战｜战略统筹｜S｜—；丙战｜前线作战｜A｜D2").map(item => ({
      name: item.name,
      role: item.role,
      result: item.result,
      difficulty: item.difficulty,
    })),
    [
      {name: "乙战", role: "战略统筹", result: "S", difficulty: ""},
      {name: "甲战", role: "前线作战", result: "A", difficulty: "A"},
      {name: "丙战", role: "前线作战", result: "A", difficulty: "B"},
    ],
  );
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
''',
        encoding="utf-8",
    )
    files = [
        "reader/first-item-reading.js",
        "reader/home-interactions.js",
        "reader/person-readability.js",
    ]
    result = subprocess.run(
        [node, str(script), *files],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
