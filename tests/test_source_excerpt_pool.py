from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "source_excerpt_pool.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("source_excerpt_pool_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_profile() -> dict:
    return {
        "person": "刘秀",
        "query_profile_id": "QRY-TEST",
        "source_targets": ["后汉书 光武帝纪", "资治通鉴 汉纪"],
        "object_layers": {
            "core_positive_objects": ["冯异", "云台功臣"],
            "supplemental_objects": ["铫期等功臣团队"],
            "negative_or_reversal_objects": ["度田事件相关官员"],
            "adjacent_split_objects": ["统一战争"],
        },
        "query_bundles": [
            "刘秀 冯异 后汉书 将兵 授权",
            "刘秀 云台二十八将 功臣 保全 后汉书",
            "刘秀 度田 牵连 官员 用人边界",
        ],
    }


def test_derive_search_terms_splits_group_hint() -> None:
    tool = load_tool()

    terms = tool.derive_search_terms("铫期等功臣团队")

    assert "铫期" in terms
    assert "功臣" in terms


def test_derive_search_terms_splits_reversal_suffixes() -> None:
    tool = load_tool()

    assert "岳飞" in tool.derive_search_terms("岳飞冤狱")
    assert "李纲" in tool.derive_search_terms("李纲罢斥")
    assert "胡铨" in tool.derive_search_terms("胡铨贬谪")


def test_candidate_objects_exclude_adjacent_by_default() -> None:
    tool = load_tool()

    candidates = tool.iter_candidate_objects(sample_profile())

    names = {candidate.raw_name for candidate in candidates}
    assert "统一战争" not in names
    assert "冯异" in names


def test_build_search_plans_uses_matching_query_bundles() -> None:
    tool = load_tool()

    plans = tool.build_search_plans(sample_profile(), max_queries_per_object=2)

    by_object = {(plan.object_name, plan.query) for plan in plans}
    assert ("冯异", "刘秀 冯异 后汉书 将兵 授权") in by_object
    assert ("云台功臣", "刘秀 云台二十八将 功臣 保全 后汉书") in by_object
    assert ("度田事件相关官员", "刘秀 度田 牵连 官员 用人边界") in by_object


def test_search_plans_prioritize_distinctive_query_terms() -> None:
    tool = load_tool()
    profile = sample_profile()
    profile["person"] = "赵构"
    profile["object_layers"] = {"core_positive_objects": ["岳飞"]}
    profile["query_bundles"] = ["高宗 岳飞 十二金字牌 班师"]

    [plan] = tool.build_search_plans(profile)

    assert plan.search_terms[:2] == ("十二金字牌", "班师")
    assert "岳飞" in plan.search_terms


def test_extract_passages_returns_context_windows() -> None:
    tool = load_tool()
    text = "甲乙丙丁刘秀召冯异入见，后令其将兵。戊己庚辛"

    passages = tool.extract_passages(text, ["冯异"], context_chars=6, max_passages=1)

    assert passages[0]["matched_term"] == "冯异"
    assert "刘秀召冯异入见" in passages[0]["text"]
    assert "后令其" in passages[0]["text"]


def test_offline_report_contains_plans_without_excerpts() -> None:
    tool = load_tool()

    report = tool.build_excerpt_pool(sample_profile(), offline=True, max_queries=2)

    assert report["offline"] is True
    assert report["title_filters"] == ["后汉书", "後漢書", "资治通鉴", "資治通鑑"]
    assert len(report["search_plans"]) == 2
    assert report["excerpts"] == []


def test_title_filter_rejects_non_target_page() -> None:
    tool = load_tool()
    filters = tool.source_title_filters(sample_profile())

    assert tool.title_matches_source_filters("後漢書/卷17", filters) is True
    assert tool.title_matches_source_filters("東漢演義/30", filters) is False


def test_song_source_filters_keep_song_history_not_song_romance() -> None:
    tool = load_tool()
    profile = {
        **sample_profile(),
        "source_targets": ["宋史 岳飞传", "建炎以来系年要录", "续资治通鉴 宋纪"],
    }
    filters = tool.source_title_filters(profile)

    assert "宋史" in filters
    assert "建炎以來繫年要錄" in filters
    assert "續資治通鑑" in filters
    assert "資治通鑑" not in filters
    assert tool.title_matches_source_filters("宋史/卷365", filters) is True
    assert tool.title_matches_source_filters("宋史演義/075", filters) is False


def test_ming_qing_shilu_filters_match_dynastic_records() -> None:
    tool = load_tool()
    profile = {
        **sample_profile(),
        "source_targets": ["明太宗实录", "明实录相关条目", "清世宗实录", "清实录 太宗朝"],
    }
    filters = tool.source_title_filters(profile)

    assert "明实录" in filters
    assert "清實錄" in filters
    assert tool.title_matches_source_filters("明太宗實錄/卷001", filters) is True
    assert tool.title_matches_source_filters("明實錄/太祖高皇帝實錄/卷001", filters) is True
    assert tool.title_matches_source_filters("清世宗實錄/卷010", filters) is True
    assert tool.title_matches_source_filters("清實錄/世宗憲皇帝實錄/卷010", filters) is True
