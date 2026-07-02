from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_payload_skeleton.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_payload_skeleton_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_profile() -> dict:
    return {
        "person": "武则天",
        "query_profile_id": "QRY-WZT",
        "source_targets": ["旧唐书 狄仁杰传", "旧唐书 酷吏传"],
        "object_layers": {
            "core_positive_objects": ["姚崇"],
            "negative_or_reversal_objects": ["来俊臣"],
            "adjacent_split_objects": ["武周革命"],
        },
        "query_bundles": ["武则天 姚崇 旧唐书 任用", "武则天 来俊臣 酷吏"],
    }


def sample_excerpt_report() -> dict:
    return {
        "person": "武则天",
        "status": "complete",
        "excerpts": [
            {
                "object_name": "姚崇",
                "query": "武则天 姚崇 旧唐书 任用",
                "page_title": "旧唐书/卷96",
                "page_url": "https://zh.wikisource.org/zh-hans/旧唐书/卷96",
                "passages": [{"matched_term": "姚崇", "text": "姚崇入仕。"}],
            }
        ],
    }


def test_build_payload_skeleton_uses_excerpt_sources_and_placeholders() -> None:
    tool = load_tool()

    payload = tool.build_payload_skeleton(sample_profile(), excerpt_report=sample_excerpt_report())

    by_name = {obj["name"]: obj for obj in payload["objects"]}
    source_by_title = {source["title"]: source for source in payload["sources"]}
    assert [obj["name"] for obj in payload["objects"]] == ["姚崇", "来俊臣"]
    assert by_name["姚崇"]["links"][0]["src_key"].startswith("SRC-WS-")
    assert by_name["来俊臣"]["links"][0]["src_key"].startswith("TODO-SRC-")
    assert source_by_title["旧唐书"]["author"] == "刘昫等"
    assert source_by_title["旧唐书"]["dynasty"] == "后晋"
    assert by_name["姚崇"]["attrs"][0]["attr_code"] == "talent_quality"
    assert not any(
        term in obj["note"]
        for obj in payload["objects"]
        for term in ["规则", "方向", "评分"]
    )
    assert payload["review"]["candidate_excerpts"]["姚崇"][0]["page_title"] == "旧唐书/卷96"


def test_build_payload_skeleton_can_include_adjacent() -> None:
    tool = load_tool()

    payload = tool.build_payload_skeleton(sample_profile(), excerpt_report={}, include_adjacent=True)

    assert [obj["name"] for obj in payload["objects"]] == ["姚崇", "来俊臣", "武周革命"]
