import importlib.util
import json
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]


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
    assert server_module.is_reader_detail_shard(detail_path)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(server_module.ReaderHandler, directory=str(ROOT))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        relative = "/reader/" + "/".join(quote(part) for part in Path(summary["detail_ref"]).parts)
        url = f"http://127.0.0.1:{server.server_port}{relative}"
        with urlopen(url) as response:
            assert response.headers.get_content_type() == "application/json"
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["record"]["ruler_id"] == summary["ruler_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_lazy_loader_is_embedded_before_readability_enhancements():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    lazy = html.index("const pendingLoads = new Map()")
    home = html.index("function enhanceHomeRows()")
    readability = html.index("const baseReaderText = readerText")
    person = html.index("const normalized = value =>")
    assert lazy < home < readability < person
    assert "正在加载两位人物的完整对照资料" in html
