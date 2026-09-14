"""Serve the reading layer and its UTF-8 source documents locally."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import html
import re
import unicodedata
import json
import sys
from io import BytesIO
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs

from markdown_it import MarkdownIt


ROOT = Path(__file__).resolve().parents[1]
DETAILS_DIR = ROOT / 'reader/data'
sys.path.insert(0, str(ROOT / 'src'))
from emperor_v4.evaluation.formal_json_store import load_json


class SafeBlocks(HTMLParser):
    """Keep document anchors and disclosure controls, never scripts or raw attributes."""
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"details", "summary", "a", "br"}:
            safe = "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in attrs
                           if tag == "a" and k in {"id", "name"} and v)
            self.parts.append(f"<{tag}{safe}>")

    def handle_endtag(self, tag):
        if tag in {"details", "summary", "a"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(html.escape(data))


def document_page(text):
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    def safe_block(tokens, index, options, env):
        safe = SafeBlocks()
        safe.feed(tokens[index].content)
        return "".join(safe.parts)
    parser.renderer.rules["html_block"] = safe_block
    parser.renderer.rules["html_inline"] = safe_block
    # Source documents remain offline, including when they reference remote images.
    parser.renderer.rules["image"] = lambda tokens, i, options, env: html.escape(tokens[i].content)
    tokens = parser.parse(text)
    headings = []
    used_anchors = set(re.findall(r'<a\s+(?:id|name)=[\"\']([^\"\']+)', text))
    for i, token in enumerate(tokens):
        if token.nesting == 1 and token.map:
            token.attrSet("data-source-line", str(token.map[0] + 1))
        if token.type == "heading_open":
            title_text = "".join(child.content for child in tokens[i+1].children or []
                                 if child.type in {"text", "code_inline"})
            slug = "".join(c for c in title_text.lower()
                           if c in "-_ " or unicodedata.category(c)[0] not in "PSZC").replace(" ", "-")
            base = slug or "section"
            anchor = base
            suffix = 0
            while anchor in used_anchors:
                suffix += 1
                anchor = f"{base}-{suffix}"
            used_anchors.add(anchor)
            token.attrSet("id", anchor)
            token.attrSet("data-legacy-anchor", f"section-{len(headings)}")
            headings.append((anchor, title_text))
    title = headings[0][1] if headings else "正式阅读页"
    toc = "".join(f'<a href="#{a}">{html.escape(re.sub(r"（RULER-[^）]+）", "", t))}</a>' for a, t in headings)
    template = (ROOT / "reader/document.template.html").read_text(encoding="utf-8")
    return (template.replace("__TITLE__", html.escape(title))
            .replace("__SOURCE_LINE_COUNT__", str(len(text.splitlines())))
            .replace("__CONTENTS__", toc)
            .replace("__BODY__", parser.renderer.render(tokens, parser.options, {}))).encode("utf-8")


def json_page(payload):
    template = (ROOT / 'reader/json.template.html').read_text(encoding='utf-8')
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return template.replace('__JSON_DATA__', data).encode('utf-8')


def is_reader_detail_shard(path):
    try:
        path.resolve().relative_to(DETAILS_DIR.resolve())
        return path.suffix.lower() == '.json'
    except ValueError:
        return False


class ReaderHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        parsed = urlsplit(self.path)
        path = Path(self.translate_path(parsed.path))
        # Generated reader detail shards are browser data, not source-document views.
        # Serve them as raw JSON so the same lazy-loading path works locally and on Pages.
        if path.suffix.lower() == '.json' and path.is_file() and not is_reader_detail_shard(path) and 'raw' not in parse_qs(parsed.query):
            data = json_page(load_json(path))
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            return BytesIO(data)
        if path.suffix.lower() == ".md" and path.is_file() and "raw" not in parse_qs(parsed.query):
            data = document_page(path.read_text(encoding="utf-8-sig"))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return BytesIO(data)
        return super().send_head()

    def guess_type(self, path):
        suffix = Path(path).suffix.lower()
        if suffix in {".md", ".txt", ".yml", ".yaml"}:
            return "text/plain; charset=utf-8"
        mime = super().guess_type(path)
        if mime.startswith("text/") or suffix in {".json", ".js", ".svg"}:
            return f"{mime}; charset=utf-8"
        return mime

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), partial(ReaderHandler, directory=str(ROOT))
    )
    print(f"Reader: http://127.0.0.1:{args.port}/reader/index.html", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
