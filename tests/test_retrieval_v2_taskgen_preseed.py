from __future__ import annotations

from scripts.dev import retrieval_v2_taskgen_preseed as tool


def sample_context() -> dict:
    return {
        "target_code": "TGT-I5B-LY",
        "emperor_name": "李渊",
        "rule_code": "delegation",
        "target_payload": {"period": "唐"},
    }


def test_build_presearch_queries_prefers_title_and_source_hints() -> None:
    queries = tool.build_presearch_queries(
        sample_context(),
        emp_metadata={"title": "唐高祖", "period": "唐"},
        max_queries=5,
    )

    assert queries[0] == "唐高祖 舊唐書"
    assert "唐高祖 新唐書" in queries
    assert "李渊 舊唐書" in queries


def test_build_taskgen_preseed_converts_search_hits_to_documents() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        assert limit == 2
        assert timeout == 3
        return [
            {"title": "舊唐書", "url": "https://example.test/root", "snippet": "root"},
            {"title": " 舊唐書/卷一 ", "url": "https://example.test/old", "snippet": f"hit {query}"},
            {"title": "舊唐書/卷一", "url": "https://example.test/duplicate", "snippet": "duplicate"},
        ]

    preseed = tool.build_taskgen_preseed(
        sample_context(),
        emp_metadata={"title": "唐高祖", "period": "唐"},
        max_queries=1,
        pages_per_query=2,
        timeout=3,
        search_fn=fake_search,
    )

    assert preseed["target_profile"]["aliases"] == ["唐高祖"]
    assert preseed["source_documents"] == [
        {
            "document_code": "DOC-PRE-TGT-I5B-LY-01",
            "title": "舊唐書/卷一",
            "wikisource_title": "舊唐書/卷一",
            "url": "https://example.test/old",
            "source_kind": "wikisource_page",
            "why_selected": "script presearch hit for 唐高祖 舊唐書",
            "search_snippet": "hit 唐高祖 舊唐書",
        }
    ]
    assert preseed["search_plan"]["codex_search_recommended"] is False
    assert preseed["clean_audit"]["presearch_hit_count"] == 3
    assert preseed["clean_audit"]["presearch_old_object_pool_read"] is False


def test_build_taskgen_preseed_derives_canonical_shiji_volume_from_annotation_hit() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        return [
            {
                "title": "史記三家註",
                "url": "https://example.test/shiji-notes",
                "snippet": "卷五 秦本紀第五 卷六 秦始皇本紀第六 卷七 項羽本紀第七",
            },
            {
                "title": "大越史記全書/外紀卷之一",
                "url": "https://example.test/wrong-root",
                "snippet": "大越史記外紀全書卷之一終",
            },
        ]

    preseed = tool.build_taskgen_preseed(
        {
            "target_code": "TGT-I5B-QIN",
            "emperor_name": "嬴政",
            "rule_code": "delegation",
            "target_payload": {"period": "秦", "title": "秦始皇"},
        },
        emp_metadata={"title": "秦始皇", "period": "秦"},
        max_queries=1,
        pages_per_query=2,
        timeout=3,
        search_fn=fake_search,
    )

    assert [row["title"] for row in preseed["source_documents"]] == ["史記/卷006"]
    hit = preseed["search_plan"]["presearch_hits"][0]
    assert hit["derived_source_titles"] == ["史記/卷006"]


def test_probable_source_document_allows_canonical_siku_volume_variant() -> None:
    assert tool.is_probable_source_document_title("宋史/卷313") is True
    assert tool.is_probable_source_document_title("宋史(四庫全書本)/卷313") is True
    assert tool.is_probable_source_document_title("資治通鑑(四部叢刊本)/卷第六十四") is False
    assert tool.is_probable_source_document_title("宋史演義/034") is False


def test_source_root_filter_rejects_adjacent_or_later_histories() -> None:
    assert tool.source_root_allowed("舊唐書/卷67", tool.source_roots_for_hint("舊唐書")) is True
    assert tool.source_root_allowed("舊五代史/卷145", tool.source_roots_for_hint("舊唐書")) is False
    assert tool.source_root_allowed("新五代史/卷04", tool.source_roots_for_hint("新唐書")) is False
    assert tool.source_root_allowed("後漢書/卷1上", tool.source_roots_for_hint("漢書")) is False
    assert tool.source_root_allowed("全隋文/卷八", tool.source_roots_for_hint("隋書")) is False
    assert tool.source_root_allowed("大越史記全書/外紀卷之一", tool.source_roots_for_hint("史記")) is False
    assert tool.source_root_allowed("康熙朝實錄/卷之22", tool.source_roots_for_hint("清實錄")) is True
    assert tool.source_root_allowed("宋史(四庫全書本)/卷283", tool.source_roots_for_hint("宋史")) is True


def test_source_roots_for_hint_can_use_target_metadata_for_reign_records() -> None:
    kangxi_roots = tool.source_roots_for_hint(
        "清實錄",
        emp_metadata={"emperor_name": "玄烨", "title": "清圣祖", "era": "康熙"},
    )
    yongzheng_roots = tool.source_roots_for_hint(
        "清實錄",
        emp_metadata={"emperor_name": "胤禛", "title": "清世宗", "era": "雍正"},
    )
    yongle_roots = tool.source_roots_for_hint(
        "明實錄",
        emp_metadata={"emperor_name": "朱棣", "title": "明成祖", "era": "永樂"},
    )

    assert "康熙朝實錄" in kangxi_roots
    assert "雍正朝實錄" not in kangxi_roots
    assert "雍正朝實錄" in yongzheng_roots
    assert "大明太宗文皇帝實錄" in yongle_roots
    assert "大明太祖高皇帝實錄" not in yongle_roots


def test_source_hints_in_query_prefers_longest_nested_hint() -> None:
    hints = ["宋史", "續資治通鑑長編", "資治通鑑"]

    assert tool.source_hints_in_query("宋太祖 續資治通鑑長編", hints) == ["續資治通鑑長編"]
    assert tool.allowed_source_roots_for_query(
        "宋太祖 續資治通鑑長編",
        {"target_payload": {"period": "宋"}},
    ) == ["續資治通鑑長編"]


def test_build_taskgen_preseed_filters_source_root_mismatch() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        return [
            {"title": "舊五代史/卷145", "url": "https://example.test/wrong", "snippet": "wrong"},
            {"title": "舊唐書/卷一", "url": "https://example.test/right", "snippet": "right"},
        ]

    preseed = tool.build_taskgen_preseed(
        sample_context(),
        emp_metadata={"title": "唐高祖", "period": "唐"},
        max_queries=1,
        pages_per_query=2,
        timeout=3,
        search_fn=fake_search,
    )

    assert [row["title"] for row in preseed["source_documents"]] == ["舊唐書/卷一"]
    rejected = [hit for hit in preseed["search_plan"]["presearch_hits"] if hit.get("rejected_reason")]
    assert rejected[0]["title"] == "舊五代史/卷145"
    assert rejected[0]["allowed_source_roots"] == ["舊唐書"]


def test_build_taskgen_preseed_uses_allowed_root_page_only_as_fallback() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        return [
            {"title": "三國志", "url": "https://example.test/sgz", "snippet": "魏書武帝紀"},
            {"title": "三國志(四庫全書本)", "url": "https://example.test/siku", "snippet": "blocked"},
            {"title": "三國演義", "url": "https://example.test/yanyi", "snippet": "blocked"},
        ]

    preseed = tool.build_taskgen_preseed(
        {
            "target_code": "TGT-I5B-CC",
            "emperor_name": "曹操",
            "rule_code": "delegation",
            "target_payload": {"period": "东汉", "title": "魏武帝"},
        },
        emp_metadata={"period": "东汉", "title": "魏武帝"},
        max_queries=1,
        pages_per_query=3,
        timeout=3,
        search_fn=fake_search,
    )

    assert preseed["source_documents"] == [
        {
            "document_code": "DOC-PRE-TGT-I5B-CC-ROOT-01",
            "title": "三國志",
            "wikisource_title": "三國志",
            "url": "https://example.test/sgz",
            "source_kind": "wikisource_root_page",
            "why_selected": "script presearch root fallback for 魏武帝 三國志",
            "search_snippet": "魏書武帝紀",
        }
    ]
    assert preseed["search_plan"]["presearch_hits"][0]["root_fallback_candidate"] is True


def test_expand_task_sources_for_objects_searches_object_names() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        queries.append(query)
        assert limit == 1
        assert timeout == 3
        source_root = query.rsplit(" ", 1)[-1]
        return [{"title": f"{source_root}/{query}", "url": "https://example.test/object", "snippet": "object hit"}]

    task = {
        "target_code": "TGT-I5B-LY",
        "source_documents": [{"document_code": "DOC-PRE-01", "title": "舊唐書/卷一"}],
        "object_seeds": [
            {"name": "李世民", "aliases": [{"alias": "秦王", "strength": "strong"}]},
            {"object_name": "李孝恭"},
            {"primary_name": "裴寂"},
        ],
        "search_plan": {"presearch_hits": []},
        "generation_notes": [],
        "clean_audit": {},
    }

    expanded = tool.expand_task_sources_for_objects(
        task,
        sample_context(),
        emp_metadata={"period": "唐"},
        max_objects=2,
        pages_per_object=1,
        timeout=3,
        search_fn=fake_search,
    )

    assert queries == [
        "李世民 舊唐書",
        "李世民 新唐書",
        "秦王 舊唐書",
        "秦王 新唐書",
        "李孝恭 舊唐書",
        "李孝恭 新唐書",
    ]
    assert len(expanded["source_documents"]) == 7
    assert expanded["search_plan"]["object_source_presearch"]["hits"][0]["object_name"] == "李世民"
    assert expanded["search_plan"]["object_source_presearch"]["source_hint_limit"] == 2
    assert expanded["clean_audit"]["object_source_presearch"] is True


def test_object_source_presearch_expands_script_variants() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        queries.append(query)
        return [{"title": "舊唐書/卷六十四", "url": "https://example.test/object", "snippet": "object hit"}]

    task = {
        "target_code": "TGT-I5B-TS",
        "source_documents": [],
        "object_seeds": [{"name": "張亮"}],
        "search_plan": {},
    }

    tool.expand_task_sources_for_objects(
        task,
        sample_context(),
        emp_metadata={"period": "唐"},
        max_objects=1,
        pages_per_object=1,
        timeout=3,
        source_hint_limit=1,
        search_fn=fake_search,
    )

    assert queries == ["張亮 舊唐書", "张亮 舊唐書"]


def test_object_source_presearch_derives_volume_from_root_hit_snippet() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        return [
            {
                "title": "三國志",
                "url": "https://example.test/sgz",
                "snippet": "卷十六 魏書十六 任峻 蘇則 卷十七 魏書十七 二張樂于徐傳 張 遼 樂進 于禁 徐晃",
            }
        ]

    task = {
        "target_code": "TGT-I5B-CC",
        "source_documents": [{"document_code": "DOC-ROOT", "title": "三國志", "source_kind": "wikisource_root_page"}],
        "object_seeds": [{"name": "张辽", "aliases": [{"alias": "文远", "strength": "strong"}]}],
        "search_plan": {},
    }

    expanded = tool.expand_task_sources_for_objects(
        task,
        {"target_code": "TGT-I5B-CC", "target_payload": {"period": "三國"}},
        emp_metadata={"period": "三國"},
        max_objects=1,
        pages_per_object=1,
        timeout=3,
        source_hint_limit=1,
        search_fn=fake_search,
    )

    assert any(row["title"] == "三國志/卷17" for row in expanded["source_documents"])
    hit = expanded["search_plan"]["object_source_presearch"]["hits"][0]
    assert hit["derived_source_titles"] == ["三國志/卷17"]


def test_expand_task_sources_for_objects_filters_source_root_mismatch() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        return [
            {"title": "舊五代史/卷145", "url": "https://example.test/wrong", "snippet": "wrong"},
            {"title": "舊唐書/卷66", "url": "https://example.test/right", "snippet": "right"},
        ]

    task = {
        "target_code": "TGT-I5B-LY",
        "source_documents": [{"document_code": "DOC-PRE-01", "title": "舊唐書/卷一"}],
        "object_seeds": [{"name": "房玄齡"}],
        "search_plan": {},
    }

    expanded = tool.expand_task_sources_for_objects(
        task,
        sample_context(),
        emp_metadata={"period": "唐"},
        max_objects=1,
        pages_per_object=2,
        timeout=3,
        search_fn=fake_search,
    )

    assert [row["title"] for row in expanded["source_documents"]] == ["舊唐書/卷一", "舊唐書/卷66"]
    rejected = [
        hit
        for hit in expanded["search_plan"]["object_source_presearch"]["hits"]
        if hit.get("rejected_reason")
    ]
    assert rejected[0]["title"] == "舊五代史/卷145"
