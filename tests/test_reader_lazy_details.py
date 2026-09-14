import importlib.util
import json
import pytest
import shutil
import subprocess
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]


def test_person_and_net_loaders_refresh_http_cache_but_reuse_page_memory(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for loader behavior")
    script = tmp_path / "freshness.cjs"
    script.write_text(r'''
const fs = require('node:fs');
const assert = require('node:assert/strict');
async function check(file, name, end) {
  const text = fs.readFileSync(file,'utf8').replace(/\r\n/g,'\n');
  const code = text.slice(text.indexOf('  async function '+name+'('), text.indexOf(end,text.indexOf('  async function '+name+'(')));
  let requests = 0;
  const fetch = async (_, options) => {
    requests++;
    const version = options?.cache === 'force-cache' ? 'old' : 'current';
    return {ok:true,json:async()=>({record:{ruler_id:'synthetic',version}})};
  };
  const byId = new Map(), DATA = {source_availability:{}};
  const loader = new Function('fetch','byId','DATA', 'const pendingLoads=new Map(),pendingNetRecords=new Map();'+code+';return '+name)(fetch,byId,DATA);
  const summary = {ruler_id:'synthetic',detail_ref:'data/synthetic.json'};
  const [a,b] = await Promise.all([loader(summary),loader(summary)]);
  assert.equal(a.version,'current');
  assert.equal(b.version,'current');
  assert.equal(requests,1);
  await loader(byId.get('synthetic'));
  assert.equal(requests,1);
}
(async()=>{
  await check(process.argv[2],'loadRecord','\n  person =');
  await check(process.argv[3],'loadNetRecord','\n  async function renderNetRoute');
})().catch(error=>{console.error(error);process.exitCode=1});
''',encoding="utf-8")
    result = subprocess.run([node,str(script),str(ROOT/"reader/lazy-details.js"),str(ROOT/"reader/home-interactions.js")],capture_output=True,text=True,encoding="utf-8")
    assert result.returncode == 0, result.stderr


def serve_module():
    spec = importlib.util.spec_from_file_location("reader_serve_lazy", ROOT / "reader/serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bootstrap_data():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    encoded = html.split('<script type="application/json" id="reader-data">')[1].split("</script>")[0]
    return json.loads(encoded)


def test_local_reader_server_serves_detail_shards_as_raw_json():
    data = bootstrap_data()
    summary = data["records"][0]
    detail_path = ROOT / "reader" / summary["detail_ref"]
    assert detail_path.is_file()

    server_module = serve_module()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(server_module.ReaderHandler, directory=str(ROOT)),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        relative = "/reader/" + "/".join(
            quote(part) for part in Path(summary["detail_ref"]).parts
        )
        url = f"http://127.0.0.1:{server.server_port}{relative}"
        with urlopen(url) as response:
            assert response.headers.get_content_type() == "application/json"
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["record"]["ruler_id"] == summary["ruler_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("relative", [
    "reader/data/military/battles-index.json",
    "reader/data/military/commanders-index.json",
])
def test_local_reader_server_serves_military_indexes_as_json(relative):
    server_module = serve_module()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(server_module.ReaderHandler, directory=str(ROOT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/{relative}") as response:
            assert response.headers.get_content_type() == "application/json"
            assert json.loads(response.read()) == json.loads((ROOT / relative).read_text(encoding="utf-8"))
        index = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        source = index["records"][0]["source"]
        encoded = "/".join(quote(part) for part in Path(source).parts)
        with urlopen(f"http://127.0.0.1:{server.server_port}/{encoded}?raw=1") as response:
            assert response.headers.get_content_type() == "application/json"
            assert json.loads(response.read()) == json.loads((ROOT / source).read_text(encoding="utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
