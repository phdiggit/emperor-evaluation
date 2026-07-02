from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_source_key_audit.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_source_key_audit_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_payload() -> dict:
    return {
        "item_code": "I5B",
        "subitem": "第五项B",
        "emperor": {"period": "东汉", "name": "刘秀", "title": "光武帝", "note": "东汉皇帝。"},
        "sources": [
            {
                "src_key": "SRC-HHS-016",
                "title": "后汉书",
                "author": "",
                "dynasty": "南朝宋",
                "volume": "卷16",
                "locator": "邓寇列传",
                "url": "https://zh.wikisource.org/zh-hans/后汉书/卷16",
                "note": "邓禹传。",
            }
        ],
        "objects": [
            {
                "obj_type": "person",
                "period": "东汉",
                "name": "邓禹",
                "note": "东汉开国功臣。",
                "links": [
                    {
                        "src_key": "SRC-HHS-016",
                        "rule_code": "talent_discovery",
                        "direction": "positive",
                        "note": "邓禹以功臣身份见于本传。",
                    }
                ],
                "attrs": [
                    {
                        "attr_code": "talent_quality",
                        "src_key": "SRC-HHS-016",
                        "value_text": "顶级人才",
                        "note": "邓禹为东汉重要功臣。",
                    }
                ],
            }
        ],
    }


def test_wikisource_title_from_url() -> None:
    tool = load_tool()

    assert tool.wikisource_title_from_url("https://zh.wikisource.org/zh-hans/旧唐书/卷89") == "旧唐书/卷89"


def test_audit_payload_sources_online_warns_when_person_terms_missing() -> None:
    tool = load_tool()
    payload = tool.importer.parse_payload(valid_payload())

    report = tool.audit_payload_sources(
        (payload,),
        online=True,
        fetch_text=lambda title: "冯异列传正文。",
    )

    assert report["ok"] is True
    assert report["warning_count"] == 1
    assert report["issues"][0]["code"] == "object_terms_not_found"


def test_audit_payload_sources_accepts_matching_person_terms() -> None:
    tool = load_tool()
    payload = tool.importer.parse_payload(valid_payload())

    report = tool.audit_payload_sources(
        (payload,),
        online=True,
        fetch_text=lambda title: "邓禹列传正文。",
    )

    assert report["ok"] is True
    assert report["warning_count"] == 0
