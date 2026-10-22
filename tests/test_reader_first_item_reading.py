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

const specs = [{
  path: process.argv[2],
  loaderStart: "  function firstItemRawUrl",
  loaderEnd: "\n  function firstItemBulletsForName",
  cacheName: "firstItemDocCache",
  loaderName: "loadFirstItemDoc",
  parserStart: "  function firstItemBulletsForName",
  parserEnd: "\n  function firstItemPublicText",
  parserName: "firstItemBullets",
}];

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

})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
''',
        encoding="utf-8",
    )
    files = [
        "reader/home-interactions.js",
    ]
    result = subprocess.run(
        [node, str(script), *files],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
