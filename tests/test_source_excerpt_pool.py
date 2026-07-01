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


def test_fallback_queries_use_profile_source_titles() -> None:
    tool = load_tool()
    profile = {
        **sample_profile(),
        "person": "刘彻",
        "source_targets": ["史记 卫将军骠骑列传", "汉书 卫青霍去病传"],
        "object_layers": {"negative_or_reversal_objects": ["赵破奴"]},
        "query_bundles": [],
    }

    plans = tool.build_search_plans(profile)
    queries = [plan.query for plan in plans]

    assert any("赵破奴 史记" in query for query in queries)
    assert any("赵破奴 汉书" in query for query in queries)
    assert all("后汉书" not in query for query in queries)


def test_mixed_object_bundle_adds_single_object_fallback_queries() -> None:
    tool = load_tool()
    profile = {
        **sample_profile(),
        "person": "刘彻",
        "source_targets": ["汉书 平津侯主父列传", "史记 平准书"],
        "object_layers": {"core_positive_objects": ["公孙弘", "桑弘羊", "主父偃"]},
        "query_bundles": ["刘彻 公孙弘 桑弘羊 主父偃 汉书 任用"],
    }

    plans = tool.build_search_plans(profile)
    sang_queries = [plan.query for plan in plans if plan.object_name == "桑弘羊"]

    assert "刘彻 公孙弘 桑弘羊 主父偃 汉书 任用" in sang_queries
    assert any("刘彻 桑弘羊 汉书 任用 授权" == query for query in sang_queries)
    assert any("刘彻 桑弘羊 史记 任用 授权" == query for query in sang_queries)


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
    assert report["skipped_search_plans"]
    assert {item["reason"] for item in report["skipped_search_plans"]} == {"max_queries"}
    assert report["throttle"]["max_retries"] == tool.DEFAULT_MAX_RETRIES
    assert report["cache"]["enabled"] is True
    assert report["retry_events"] == []
    assert report["excerpts"] == []


def test_fetch_json_retries_429_with_retry_after(monkeypatch) -> None:
    tool = load_tool()
    calls = []
    sleeps = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, *, timeout):
        calls.append((request.full_url, timeout, request.get_header("User-agent")))
        if len(calls) == 1:
            raise tool.urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "0.25"},
                None,
            )
        return FakeResponse()

    monkeypatch.setattr(tool.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(tool.time, "sleep", lambda seconds: sleeps.append(seconds))
    context = tool.FetchContext(
        request_delay_seconds=0,
        max_retries=2,
        retry_backoff_seconds=3,
        retry_events=[],
    )

    payload = tool._fetch_json(
        "https://example.test/w/api.php",
        timeout=9,
        fetch_context=context,
        stage="search",
        label="刘彻 赵破奴",
    )

    assert payload == {"ok": True}
    assert len(calls) == 2
    assert calls[0][2] == tool.DEFAULT_USER_AGENT
    assert sleeps == [0.25]
    assert context.retry_events == [
        {
            "stage": "search",
            "label": "刘彻 赵破奴",
            "url": "https://example.test/w/api.php",
            "attempt": 1,
            "wait_seconds": 0.25,
            "reason": "<HTTPError 429: 'Too Many Requests'>",
            "status_code": 429,
        }
    ]


def test_fetch_json_retries_5xx_with_exponential_backoff(monkeypatch) -> None:
    tool = load_tool()
    calls = []
    sleeps = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, *, timeout):
        calls.append(request.full_url)
        if len(calls) < 3:
            raise tool.urllib.error.HTTPError(request.full_url, 503, "Service Unavailable", {}, None)
        return FakeResponse()

    monkeypatch.setattr(tool.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(tool.time, "sleep", lambda seconds: sleeps.append(seconds))
    context = tool.FetchContext(
        request_delay_seconds=0,
        max_retries=3,
        retry_backoff_seconds=2,
        retry_events=[],
    )

    payload = tool._fetch_json(
        "https://example.test/w/api.php",
        timeout=9,
        fetch_context=context,
        stage="fetch_page",
        label="漢書/卷055",
    )

    assert payload == {"ok": True}
    assert sleeps == [2, 4]
    assert [event["status_code"] for event in context.retry_events] == [503, 503]
    assert [event["wait_seconds"] for event in context.retry_events] == [2, 4]


def test_fetch_json_uses_persistent_api_cache(tmp_path, monkeypatch) -> None:
    tool = load_tool()
    calls = []
    sleeps = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"ok": true, "call": 1}'

    def fake_urlopen(request, *, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse()

    monkeypatch.setattr(tool.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(tool.time, "sleep", lambda seconds: sleeps.append(seconds))
    api_cache = tool.ApiCache(cache_dir=tmp_path / "cache")
    context = tool.FetchContext(
        request_delay_seconds=999,
        max_retries=0,
        retry_backoff_seconds=0,
        retry_events=[],
        api_cache=api_cache,
    )

    url = "https://example.test/w/api.php?action=query&list=search&srsearch=桑弘羊"
    first = tool._fetch_json(url, timeout=9, fetch_context=context, stage="search", label="桑弘羊")
    second = tool._fetch_json(url, timeout=9, fetch_context=context, stage="search", label="桑弘羊")

    assert first == {"ok": True, "call": 1}
    assert second == {"ok": True, "call": 1}
    assert len(calls) == 1
    assert sleeps == []
    assert api_cache.hits == 1
    assert api_cache.misses == 1
    assert api_cache.writes == 1
    assert list((tmp_path / "cache" / "search").glob("*.json"))


def test_fetch_wikisource_plain_text_uses_page_text_cache(tmp_path, monkeypatch) -> None:
    tool = load_tool()
    calls = []
    page_cache = tool.PageTextCache(cache_dir=tmp_path / "pages")
    context = tool.FetchContext(
        request_delay_seconds=0,
        max_retries=0,
        retry_backoff_seconds=0,
        retry_events=[],
        page_text_cache=page_cache,
    )

    def fake_fetch_json(url, *, timeout, fetch_context=None, stage="api", label="", user_agent=tool.DEFAULT_USER_AGENT):
        calls.append((url, stage, label))
        return {"parse": {"text": {"*": "<div>桑弘羊以计算用事，侍中。</div>"}}}

    monkeypatch.setattr(tool, "_fetch_json", fake_fetch_json)

    first = tool.fetch_wikisource_plain_text("史記/卷030", timeout=9, fetch_context=context)
    second = tool.fetch_wikisource_plain_text("史記/卷030", timeout=9, fetch_context=context)

    assert first == "桑弘羊以计算用事，侍中。"
    assert second == first
    assert len(calls) == 1
    assert page_cache.hits == 1
    assert page_cache.misses == 1
    assert page_cache.writes == 1
    assert list((tmp_path / "pages").glob("*.txt"))


def test_source_excerpt_cache_config_reads_project_config(tmp_path, monkeypatch) -> None:
    tool = load_tool()
    config_path = tmp_path / "project_config.yml"
    config_path.write_text(
        """
version: 2
tooling:
  source_excerpt_pool:
    cache:
      enabled: false
      directory: .cache/custom-wikisource-cache
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(tool, "ROOT", tmp_path)

    config = tool.load_source_excerpt_cache_config(config_path)

    assert config["enabled"] is False
    assert config["backend"] == "filesystem"
    assert config["directory"] == tmp_path / ".cache" / "custom-wikisource-cache"
    assert config["dsn_env"] == tool.DEFAULT_CACHE_DSN_ENV
    assert config["schema"] == tool.DEFAULT_CACHE_SCHEMA


def test_source_excerpt_cache_config_reads_postgres_backend(tmp_path, monkeypatch) -> None:
    tool = load_tool()
    config_path = tmp_path / "project_config.yml"
    config_path.write_text(
        """
version: 2
tooling:
  source_excerpt_pool:
    cache:
      enabled: true
      backend: postgres
      dsn_env: EMPEROR_EVAL_CACHE_PG_DSN
      schema: source_cache
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(tool, "ROOT", tmp_path)

    config = tool.load_source_excerpt_cache_config(config_path)

    assert config["backend"] == "postgres"
    assert "directory" not in config
    assert config["dsn_env"] == "EMPEROR_EVAL_CACHE_PG_DSN"
    assert config["schema"] == "source_cache"


def test_source_excerpt_cache_config_rejects_postgres_directory(tmp_path, monkeypatch) -> None:
    tool = load_tool()
    config_path = tmp_path / "project_config.yml"
    config_path.write_text(
        """
version: 2
tooling:
  source_excerpt_pool:
    cache:
      enabled: true
      backend: postgres
      directory: .cache/wikisource-cache
      dsn_env: EMPEROR_EVAL_CACHE_PG_DSN
      schema: source_cache
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(tool, "ROOT", tmp_path)

    try:
        tool.load_source_excerpt_cache_config(config_path)
    except tool.ExcerptPoolError as exc:
        assert "directory is only allowed for filesystem backend" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("postgres directory config should be rejected")


def test_offline_report_can_use_postgres_cache_without_connecting(monkeypatch) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "load_source_excerpt_cache_config",
        lambda: {
            "enabled": True,
            "backend": "postgres",
            "dsn_env": "EMPEROR_EVAL_CACHE_PG_DSN",
            "schema": "source_cache",
        },
    )
    monkeypatch.setattr(
        tool.psycopg,
        "connect",
        lambda dsn: (_ for _ in ()).throw(AssertionError("offline mode must not connect")),
    )

    report = tool.build_excerpt_pool(sample_profile(), offline=True, max_queries=1)

    assert report["cache"]["backend"] == "postgres"
    assert "directory" not in report["cache"]
    assert report["cache"]["dsn_env"] == "EMPEROR_EVAL_CACHE_PG_DSN"
    assert report["cache"]["schema"] == "source_cache"


def test_migrate_filesystem_cache_to_cache_imports_api_and_pages(tmp_path) -> None:
    tool = load_tool()
    source_dir = tmp_path / "wikisource-cache"
    api_dir = source_dir / "api" / "search"
    page_dir = source_dir / "pages"
    api_dir.mkdir(parents=True)
    page_dir.mkdir(parents=True)
    (api_dir / "abc.json").write_text(
        tool.json.dumps(
            {
                "schema_version": 1,
                "stage": "search",
                "label": "桑弘羊",
                "url": "https://example.test/search",
                "payload": {"query": {"search": []}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (page_dir / "page.txt").write_text("桑弘羊以计算用事。", encoding="utf-8")
    (page_dir / "page.json").write_text(
        tool.json.dumps(
            {
                "schema_version": 1,
                "title": "史記/卷030",
                "page_url": "https://example.test/page",
                "text_path": "page.txt",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class RecorderApiCache:
        writes = 0

        def __init__(self):
            self.rows = []

        def write(self, **kwargs):
            self.rows.append(kwargs)
            self.writes += 1

    class RecorderPageCache:
        writes = 0

        def __init__(self):
            self.rows = []

        def write(self, **kwargs):
            self.rows.append(kwargs)
            self.writes += 1

    api_cache = RecorderApiCache()
    page_cache = RecorderPageCache()

    report = tool.migrate_filesystem_cache_to_cache(source_dir, api_cache=api_cache, page_text_cache=page_cache)

    assert report["api"]["scanned"] == 1
    assert report["api"]["imported"] == 1
    assert api_cache.rows[0]["stage"] == "search"
    assert api_cache.rows[0]["payload"] == {"query": {"search": []}}
    assert report["page_text"]["scanned"] == 1
    assert report["page_text"]["imported"] == 1
    assert page_cache.rows[0]["title"] == "史記/卷030"
    assert page_cache.rows[0]["text"] == "桑弘羊以计算用事。"


def test_build_excerpt_pool_uses_custom_user_agent(monkeypatch) -> None:
    tool = load_tool()
    seen_user_agents = []

    def fake_fetch_json(url, *, timeout, fetch_context=None, stage="api", label="", user_agent=tool.DEFAULT_USER_AGENT):
        seen_user_agents.append(fetch_context.user_agent if fetch_context is not None else user_agent)
        if stage == "search":
            return {"query": {"search": []}}
        return {"parse": {"text": {"*": ""}}}

    monkeypatch.setattr(tool, "_fetch_json", fake_fetch_json)

    report = tool.build_excerpt_pool(
        sample_profile(),
        max_queries=1,
        user_agent="emperor-evaluation-test/0.1 (https://example.test/contact)",
    )

    assert report["throttle"]["user_agent"] == "emperor-evaluation-test/0.1 (https://example.test/contact)"
    assert seen_user_agents == ["emperor-evaluation-test/0.1 (https://example.test/contact)"]


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
