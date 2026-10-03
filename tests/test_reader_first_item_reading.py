"""Active first-item reader source slices stay isolated per person."""

import shutil
import subprocess

import pytest


def test_first_item_source_cache_is_scoped_by_ruler_and_accepts_formal_aliases(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for first-item reader behavior")

    script = tmp_path / "first_item_source_scope.cjs"
    script.write_text(
        r'''
const fs = require("node:fs");
const assert = require("node:assert/strict");

const source = fs.readFileSync(process.argv[2], "utf8");
const loaderStart = source.indexOf("  function firstItemRawUrl");
const loaderEnd = source.indexOf("\n  function firstItemBulletsForName", loaderStart);
assert.ok(loaderStart >= 0 && loaderEnd > loaderStart, "active first-item loader fragment not found");

const requests = [];
const fakeFetch = async url => {
  requests.push(String(url));
  return {ok: true, text: async () => `response:${requests.length}`};
};
const validatedRawUrl = ref => "../" + ref + "?raw=1";
const loader = new Function(
  "fetch",
  "validatedRawUrl",
  `const firstItemDocCache = new Map();${source.slice(loaderStart, loaderEnd)};return loadFirstItemDoc;`,
)(fakeFetch, validatedRawUrl);

const parserStart = source.indexOf("  function firstItemBulletsForName");
const parserEnd = source.indexOf("\n  function firstItemPublicText", parserStart);
assert.ok(parserStart >= 0 && parserEnd > parserStart, "active first-item parser fragment not found");
const parse = new Function(`${source.slice(parserStart, parserEnd)};return firstItemBullets;`)();

const textStart = source.indexOf("function firstPublicText(value)");
const textEnd = source.indexOf("\n\nfunction firstB1Markup", textStart);
assert.ok(textStart >= 0 && textEnd > textStart, "first public text helper not found");
const firstPublicText = new Function(
  `${source.slice(textStart, textEnd)};return firstPublicText;`,
)();

const publicStart = source.indexOf("  function firstPublicOutcomeText");
const publicEnd = source.indexOf("\n\n  function firstPublicOutcomeParts", publicStart);
assert.ok(publicStart >= 0 && publicEnd > publicStart, "active public outcome helper not found");
const publicOutcomeText = new Function(
  "firstPublicText",
  `${source.slice(publicStart, publicEnd)};return firstPublicOutcomeText;`,
)(firstPublicText);

(async () => {
  const first = await loader("docs/first-item.md", {ruler_id: "RULER-A"});
  const second = await loader("docs/first-item.md", {ruler_id: "RULER-B"});
  assert.notEqual(first, second, "two rulers reused one source promise");
  assert.equal(requests.length, 2, "source cache was not keyed by ruler");

  const fields = parse("### 1. 正式名\n\n- **事实**：正式材料\n", ["展示名", "正式名"]);
  assert.equal(fields["事实"], "正式材料", "formal-name fallback failed");

  const outcome = publicOutcomeText(
    "从秦国在关中、巴蜀、汉中等既有核心区域起步，先后取得韩、赵、魏、楚、燕、齐，完成六国统一。",
  );
  assert.equal(outcome, "从秦国在关中、巴蜀、汉中等既有核心区域起步，先后取得韩、赵、魏、楚、燕、齐，完成六国统一。");
  assert.doesNotMatch(outcome, /单位|控制信用|有效控制信用/);

  const technicalOutcome = publicOutcomeText("从甲地起步，取得乙地；个人分得123控制信用。");
  assert.equal(technicalOutcome, "从甲地起步，取得乙地；个人分得123控制信用。");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
''',
        encoding="utf-8",
    )
    result = subprocess.run(
        [node, str(script), "reader/home-interactions.js"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
