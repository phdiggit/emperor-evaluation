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


def test_source_links_use_local_files_in_preview_and_pin_published_sources(tmp_path):
    import shutil
    import subprocess
    from pathlib import Path
    import pytest
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    root = Path(__file__).resolve().parents[1]
    source = (root/'reader/index.template.html').read_text(encoding='utf-8')
    start = source.index('const localReaderHost=')
    end = source.index('const href=', start)
    fragment = source[start:end]
    script = tmp_path/'source-links.cjs'
    script.write_text(
        "const assert=require('node:assert/strict');\n"
        + 'const fragment='+__import__('json').dumps(fragment)+';\n'
        + "const make=new Function('location','DATA',fragment+'return {base:sourceRepoBase(),raw:validatedRawUrl(\"docs/test.md\")};');\n"
        + "const data={source_repository:'example/project',source_revision:'a'.repeat(40)};\n"
        + "for(const hostname of ['localhost','127.0.0.1','[::1]']){const result=make({hostname},data);assert.equal(result.base,'');assert.equal(result.raw,'../docs/test.md?raw=1');}\n"
        + "const result=make({hostname:'example.github.io'},data);assert.ok(result.base.includes('/blob/'+data.source_revision+'/'));assert.ok(result.raw.includes(data.source_revision+'/docs/test.md'));\n",
        encoding='utf-8',
    )
    result = subprocess.run([node,str(script)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode == 0,result.stderr


def test_surface_updates_coalesce_without_observing_their_own_writes(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for scheduler behavior')
    script = tmp_path / 'surface-scheduler.cjs'
    script.write_text(r'''const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('reader/home-interactions.js','utf8');
const begin=source.indexOf('  function runReaderEnhancer(');
const end=source.indexOf('  ensureNetStyles();',begin);
const queue=[],observers=[];
let renders=0,fail=false;
class Observer {
 constructor(callback){this.callback=callback;this.active=false;observers.push(this);}
 observe(){this.active=true;}
 disconnect(){this.active=false;}
 emit(){if(this.active)this.callback([]);}
}
const context={window:{},screen:{},MutationObserver:Observer,
 requestAnimationFrame:callback=>queue.push(callback),
 enhanceHomeRows:()=>{renders++;observers[0].emit();if(fail)throw Error('render failed');},
 enhancePersonNet:()=>observers[0].emit()};
vm.createContext(context);
vm.runInContext(source.slice(begin,end)+'\nenhanceReaderSurface();',context);
assert.equal(renders,1);
assert.equal(queue.length,0,'render-owned changes must not schedule another render');
observers[0].emit();observers[0].emit();context.window.ReaderSurfaceEnhancer.schedule();
assert.equal(queue.length,1,'a burst of external changes has one render');
queue.shift()();assert.equal(renders,2);assert.equal(queue.length,0);
fail=true;observers[0].emit();assert.throws(()=>queue.shift()(),/render failed/);
fail=false;observers[0].emit();assert.equal(queue.length,1,'observation resumes after an error');
queue.shift()();assert.equal(renders,4);assert.equal(queue.length,0);
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
