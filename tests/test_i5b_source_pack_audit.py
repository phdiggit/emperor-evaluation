from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_source_pack_audit.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_source_pack_audit_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_pack(tmp_path: Path, *, with_text: bool = True, bad_excerpt_src_key: bool = False) -> Path:
    pack = tmp_path / "source-pack"
    (pack / "pages").mkdir(parents=True)
    (pack / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pack_id": "i5b-source-pack-test",
                "created_at": "2026-07-02T00:00:00+08:00",
                "source_scope": "I5B fixture",
                "status": "review_ready",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if with_text:
        (pack / "pages" / "hhs16.txt").write_text("邓禹列传正文。", encoding="utf-8")
    row = {
        "src_key": "SRC-HHS-016",
        "page_title": "后汉书/卷16",
        "title": "后汉书",
        "author": "范晔",
        "dynasty": "南朝宋",
        "locator": "后汉书/卷16",
        "url": "https://zh.wikisource.org/zh-hans/后汉书/卷16",
        "text_path": "pages/hhs16.txt" if with_text else "",
        "fetch_status": "cached",
        "review_status": "pending",
    }
    (pack / "src_docs.jsonl").write_text(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if bad_excerpt_src_key:
        excerpt = {
            "excerpt_id": "EXCERPT-001",
            "src_key": "SRC-MISSING",
            "object_name": "邓禹",
            "quote": "邓禹列传正文。",
        }
        (pack / "excerpts.jsonl").write_text(json.dumps(excerpt, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return pack


def test_audit_source_pack_accepts_valid_pack(tmp_path) -> None:
    tool = load_tool()

    report = tool.audit_source_pack(write_pack(tmp_path))

    assert report["ok"] is True
    assert report["block_count"] == 0
    assert report["warning_count"] == 0
    assert report["doc_count"] == 1


def test_audit_source_pack_blocks_missing_local_text(tmp_path) -> None:
    tool = load_tool()

    report = tool.audit_source_pack(write_pack(tmp_path, with_text=False))

    assert report["ok"] is False
    assert report["block_count"] == 1
    assert report["issues"][0]["code"] == "missing_source_text"


def test_audit_source_pack_blocks_excerpt_unknown_src_key(tmp_path) -> None:
    tool = load_tool()

    report = tool.audit_source_pack(write_pack(tmp_path, bad_excerpt_src_key=True))

    assert report["ok"] is False
    assert {issue["code"] for issue in report["issues"]} == {"excerpt_unknown_src_key"}
