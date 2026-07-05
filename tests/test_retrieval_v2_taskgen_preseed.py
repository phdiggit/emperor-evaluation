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


def test_build_presearch_queries_uses_profile_source_targets_without_period() -> None:
    queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-LIU-E",
            "emperor_name": "刘娥",
            "rule_code": "delegation",
            "target_payload": {
                "source_targets": [
                    "宋史 本纪与列传",
                    "续资治通鉴长编 / 建炎以来系年要录",
                    "续资治通鉴（辅助）",
                ]
            },
        },
        max_queries=4,
    )

    assert queries[:2] == ["刘娥 宋史", "刘娥 續資治通鑑長編"]


def test_build_presearch_queries_supports_northern_dynasty_source_hints() -> None:
    queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-BW",
            "emperor_name": "拓跋焘",
            "rule_code": "delegation",
            "target_payload": {"period": "北魏"},
        },
        emp_metadata={"title": "魏太武帝", "period": "北魏"},
        max_queries=4,
    )

    assert queries[:3] == ["魏太武帝 魏書", "魏太武帝 北史", "魏太武帝 資治通鑑"]


def test_build_presearch_queries_supports_five_dynasties_source_hints() -> None:
    queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-ZW",
            "emperor_name": "朱温",
            "rule_code": "delegation",
            "target_payload": {"period": "後梁"},
        },
        emp_metadata={"title": "梁太祖", "period": "後梁"},
        max_queries=4,
    )

    assert queries[:3] == ["梁太祖 舊五代史", "梁太祖 新五代史", "梁太祖 資治通鑑"]


def test_build_presearch_queries_supports_ten_kingdoms_source_hints() -> None:
    cases = [
        ("李昪", "南唐烈祖", "南唐"),
        ("王建", "前蜀高祖", "前蜀"),
        ("孟昶", "后蜀后主", "後蜀"),
        ("刘龑", "南汉高祖", "南漢"),
    ]
    for name, title, period in cases:
        queries = tool.build_presearch_queries(
            {
                "target_code": f"TGT-I5B-{name}",
                "emperor_name": name,
                "rule_code": "delegation",
                "target_payload": {"period": period},
            },
            emp_metadata={"title": title, "period": period},
            max_queries=4,
        )

        assert queries[:4] == [
            f"{title} 舊五代史",
            f"{title} 新五代史",
            f"{title} 資治通鑑",
            f"{title} 十國春秋",
        ]


def test_build_presearch_queries_supports_liao_source_hints() -> None:
    queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-YLLX",
            "emperor_name": "耶律隆绪",
            "rule_code": "delegation",
            "target_payload": {"period": "遼"},
        },
        emp_metadata={"title": "遼聖宗", "period": "遼"},
        max_queries=4,
    )

    assert queries[:3] == ["遼聖宗 遼史", "遼聖宗 契丹國志", "遼聖宗 續資治通鑑長編"]


def test_build_presearch_queries_supports_western_liao_without_song_changbian() -> None:
    queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-TBY",
            "emperor_name": "塔不烟",
            "rule_code": "delegation",
            "target_payload": {"period": "西遼"},
        },
        emp_metadata={"title": "感天皇后", "period": "西遼"},
        max_queries=4,
    )

    assert queries[:2] == ["感天皇后 遼史", "感天皇后 契丹國志"]
    assert all("續資治通鑑長編" not in query for query in queries)


def test_build_presearch_queries_avoids_ambiguous_standalone_titles() -> None:
    queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-XPSW",
            "emperor_name": "萧普速完",
            "rule_code": "delegation",
            "target_payload": {"period": "西遼"},
        },
        emp_metadata={"title": "承天太后", "period": "西遼"},
        max_queries=4,
    )

    assert queries[:2] == ["萧普速完 遼史", "萧普速完 契丹國志"]
    assert not any(query.startswith("承天太后 ") for query in queries)


def test_build_taskgen_preseed_drops_ambiguous_target_title_aliases() -> None:
    preseed = tool.build_taskgen_preseed(
        {
            "target_code": "TGT-I5B-XPSW",
            "emperor_name": "萧普速完",
            "rule_code": "delegation",
            "target_payload": {"period": "西遼"},
        },
        emp_metadata={"title": "承天太后", "period": "西遼"},
        search_fn=lambda query, *, limit, timeout: [],
    )

    assert preseed["target_profile"]["aliases"] == []
    assert preseed["target_profile"]["must_check_titles"] == []


def test_build_presearch_queries_supports_western_xia_source_hints() -> None:
    queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-LYH",
            "emperor_name": "李元昊",
            "rule_code": "delegation",
            "target_payload": {"period": "西夏"},
        },
        emp_metadata={"title": "夏景宗", "period": "西夏"},
        max_queries=4,
    )

    assert queries[:4] == [
        "夏景宗 宋史",
        "夏景宗 續資治通鑑長編",
        "夏景宗 遼史",
        "夏景宗 金史",
    ]
    assert all("晉書" not in query for query in queries)


def test_build_presearch_queries_supports_jin_and_yuan_source_hints() -> None:
    jin_queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-WYY",
            "emperor_name": "完颜雍",
            "rule_code": "delegation",
            "target_payload": {"period": "金"},
        },
        emp_metadata={"title": "金世宗", "period": "金"},
        max_queries=3,
    )
    yuan_queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-TMZ",
            "emperor_name": "铁木真",
            "rule_code": "delegation",
            "target_payload": {"period": "蒙古"},
        },
        emp_metadata={"title": "成吉思汗", "period": "蒙古"},
        max_queries=3,
    )

    assert jin_queries == ["金世宗 金史", "金世宗 大金國志", "金世宗 續資治通鑑"]
    assert yuan_queries == ["成吉思汗 元史", "成吉思汗 新元史", "成吉思汗 續資治通鑑"]


def test_build_presearch_queries_supports_sixteen_kingdoms_state_hints() -> None:
    queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-SH",
            "emperor_name": "石虎",
            "rule_code": "delegation",
            "target_payload": {"period": "後趙"},
        },
        emp_metadata={"title": "後趙太祖", "period": "後趙"},
        max_queries=3,
    )

    assert queries[:2] == ["後趙太祖 晉書", "後趙太祖 資治通鑑"]


def test_build_presearch_queries_supports_liu_song_without_songshi() -> None:
    queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-LYL",
            "emperor_name": "刘义隆",
            "rule_code": "delegation",
            "target_payload": {"period": "南朝宋"},
        },
        emp_metadata={"title": "宋文帝", "period": "南朝宋"},
        max_queries=4,
    )

    assert queries[:3] == ["宋文帝 宋書", "宋文帝 南史", "宋文帝 資治通鑑"]
    assert all("宋史" not in query for query in queries)


def test_build_presearch_queries_supports_southern_dynasties_source_hints() -> None:
    qi_queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-XDC",
            "emperor_name": "萧道成",
            "rule_code": "delegation",
            "target_payload": {"period": "南齊"},
        },
        emp_metadata={"title": "齊高帝", "period": "南齊"},
        max_queries=3,
    )
    liang_queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-XY",
            "emperor_name": "萧绎",
            "rule_code": "delegation",
            "target_payload": {"period": "南梁"},
        },
        emp_metadata={"title": "梁元帝", "period": "南梁"},
        max_queries=3,
    )
    chen_queries = tool.build_presearch_queries(
        {
            "target_code": "TGT-I5B-CBX",
            "emperor_name": "陈霸先",
            "rule_code": "delegation",
            "target_payload": {"period": "南陳"},
        },
        emp_metadata={"title": "陳武帝", "period": "南陳"},
        max_queries=3,
    )

    assert qi_queries == ["齊高帝 南齊書", "齊高帝 南史", "齊高帝 資治通鑑"]
    assert liang_queries == ["梁元帝 梁書", "梁元帝 南史", "梁元帝 資治通鑑"]
    assert chen_queries == ["陳武帝 陳書", "陳武帝 南史", "陳武帝 資治通鑑"]


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
    assert tool.is_probable_source_document_title("續資治通鑑長編(四庫全書本)/全覽17") is False
    assert tool.is_probable_source_document_title("遼史/附錄") is False
    assert tool.is_probable_source_document_title("續資治通鑑長編/提要") is False
    assert tool.is_probable_source_document_title("契丹國志/跋") is False
    assert tool.is_probable_source_document_title("元史/進元史表") is False
    assert tool.is_probable_source_document_title("續資治通鑑長編/李燾進續資治通鑑長編表") is False


def test_source_root_filter_rejects_adjacent_or_later_histories() -> None:
    assert tool.source_root_allowed("舊唐書/卷67", tool.source_roots_for_hint("舊唐書")) is True
    assert tool.source_root_allowed("舊五代史/卷145", tool.source_roots_for_hint("舊唐書")) is False
    assert tool.source_root_allowed("新五代史/卷04", tool.source_roots_for_hint("新唐書")) is False
    assert tool.source_root_allowed("後漢書/卷1上", tool.source_roots_for_hint("漢書")) is False
    assert tool.source_root_allowed("全隋文/卷八", tool.source_roots_for_hint("隋書")) is False
    assert tool.source_root_allowed("大越史記全書/外紀卷之一", tool.source_roots_for_hint("史記")) is False
    assert tool.source_root_allowed("康熙朝實錄/卷之22", tool.source_roots_for_hint("清實錄")) is True
    assert tool.source_root_allowed("宋史(四庫全書本)/卷283", tool.source_roots_for_hint("宋史")) is True
    assert tool.source_root_allowed("十國春秋/卷18", tool.source_roots_for_hint("十國春秋")) is True
    assert tool.source_root_allowed("舊唐書/卷67", tool.source_roots_for_hint("十國春秋")) is False


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
    hongxi_roots = tool.source_roots_for_hint(
        "明實錄",
        emp_metadata={"emperor_name": "朱高炽", "title": "明仁宗", "era": "洪熙"},
    )
    jingtai_roots = tool.source_roots_for_hint(
        "明實錄",
        emp_metadata={"emperor_name": "朱祁钰", "title": "明代宗", "era": "景泰"},
    )
    chenghua_roots = tool.source_roots_for_hint(
        "明實錄",
        emp_metadata={"emperor_name": "朱见深", "title": "明宪宗", "era": "成化"},
    )
    taichang_roots = tool.source_roots_for_hint(
        "明實錄",
        emp_metadata={"emperor_name": "朱常洛", "title": "明光宗", "era": "泰昌"},
    )
    tianqi_roots = tool.source_roots_for_hint(
        "明實錄",
        emp_metadata={"emperor_name": "朱由校", "title": "明熹宗", "era": "天启"},
    )
    tianming_roots = tool.source_roots_for_hint(
        "清實錄",
        emp_metadata={"emperor_name": "努尔哈赤", "title": "清太祖", "era": "天命"},
    )
    guangxu_roots = tool.source_roots_for_hint(
        "清實錄",
        emp_metadata={"emperor_name": "载湉", "title": "清德宗", "era": "光绪"},
    )

    assert "康熙朝實錄" in kangxi_roots
    assert "雍正朝實錄" not in kangxi_roots
    assert "雍正朝實錄" in yongzheng_roots
    assert "大明太宗文皇帝實錄" in yongle_roots
    assert "大明太祖高皇帝實錄" not in yongle_roots
    assert "大明仁宗昭皇帝實錄" in hongxi_roots
    assert "大明英宗睿皇帝實錄" in jingtai_roots
    assert "大明憲宗純皇帝實錄" in chenghua_roots
    assert "大明光宗貞皇帝實錄" in taichang_roots
    assert "明熹宗悊皇帝實錄" in tianqi_roots
    assert "清太祖高皇帝實錄" in tianming_roots
    assert "光緒朝實錄" in guangxu_roots
    assert "清實錄" not in guangxu_roots
    assert tool.source_root_allowed("清實錄/德宗景皇帝實錄/卷之一", guangxu_roots)
    assert not tool.source_root_allowed("清實錄/宣宗成皇帝實錄/卷二百二十三", guangxu_roots)


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
