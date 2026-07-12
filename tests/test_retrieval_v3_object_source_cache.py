from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.dev import retrieval_v3_object_source_cache as tool
from scripts.dev import retrieval_v3_object_source_cache_hint_worklist as hint_worklist
from scripts.dev import retrieval_v3_object_source_cache_patch as seed_patch
from scripts.dev import retrieval_v3_object_source_cache_seed as seed_tool

ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_build_cache_separates_emperor_context_and_object_biography(tmp_path: Path, monkeypatch) -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        if "朱元璋" in query:
            return [{"title": "明史/卷1", "url": "https://example.test/mingshi1", "snippet": "太祖本紀 朱元璋"}]
        return [{"title": "明史/卷308", "url": "https://example.test/mingshi308", "snippet": "胡惟庸傳 胡惟庸"}]

    def fake_fetch(document: dict, *, cache_dir: Path, timeout: int) -> tuple[str, dict]:
        title = document["wikisource_title"]
        if title == "明史/卷1":
            return "太祖朱元璋任胡惟庸为相，后胡惟庸谋反伏诛。", {"source_key": f"wikisource:{title}", "cache_status": "embedded"}
        return "列传第一百九十六奸臣 胡惟庸。帝宠任胡惟庸。胡惟庸专擅威福，内外封事有害己者辄匿闻。", {
            "source_key": f"wikisource:{title}",
            "cache_status": "embedded",
        }

    monkeypatch.setattr(tool, "fetch_document_text", fake_fetch)

    manifest = tool.build_cache(
        [
            {"name": "朱元璋", "aliases": ["太祖"], "is_emperor": True, "source_hints": ["明史"], "priority": 20},
            {"name": "胡惟庸", "source_hints": ["明史"], "priority": 30},
        ],
        output_root=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        search_fn=fake_search,
        pages_per_query=1,
        source_hint_limit=1,
        max_search_names=1,
    )

    docs = read_jsonl(tmp_path / "out" / "source_documents.jsonl")
    coverage = {row["person_name"]: row for row in read_jsonl(tmp_path / "out" / "person_coverage.jsonl")}

    assert manifest["mode"] == "offline_no_agent"
    assert manifest["agent_invocation_enabled"] is False
    assert {row["source_role"] for row in docs} == {"emperor_context", "object_biography_or_mentions"}
    assert coverage["朱元璋"]["has_emperor_context_source"] is True
    assert coverage["胡惟庸"]["has_biography_source"] is True
    assert coverage["胡惟庸"]["needs_agent_review"] is False
    assert read_jsonl(tmp_path / "out" / "agent_review_queue.jsonl") == []


def test_build_cache_marks_agent_slot_without_invocation_for_unmatched_source(tmp_path: Path, monkeypatch) -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        return [{"title": "明史/卷126", "url": "https://example.test/mingshi126", "snippet": "列傳"}]

    def fake_fetch(document: dict, *, cache_dir: Path, timeout: int) -> tuple[str, dict]:
        return "太祖命诸将征伐，未见目标人名。", {"source_key": "wikisource:明史/卷126", "cache_status": "embedded"}

    monkeypatch.setattr(tool, "fetch_document_text", fake_fetch)

    tool.build_cache(
        [{"name": "常遇春", "source_hints": ["明史"], "priority": 30}],
        output_root=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        search_fn=fake_search,
        pages_per_query=1,
        source_hint_limit=1,
        max_search_names=1,
    )

    coverage = read_jsonl(tmp_path / "out" / "person_coverage.jsonl")[0]
    agent_rows = read_jsonl(tmp_path / "out" / "agent_review_queue.jsonl")

    assert coverage["claim_closure_risk"] == "source_fetched_but_no_person_mention"
    assert coverage["needs_agent_review"] is True
    assert coverage["agent_status"] == "not_requested"
    assert agent_rows[0]["person_name"] == "常遇春"
    assert agent_rows[0]["agent_status"] == "not_requested"
    assert agent_rows[0]["agent_expected_output_schema"] == "object_source_cache_agent_review_v1"


def test_emperor_context_does_not_require_person_mention_for_agent_review() -> None:
    coverage = tool.coverage_for_seed(
        {"name": "朱元璋", "is_emperor": True, "source_hints": ["明史"]},
        [
            {
                "person_name": "朱元璋",
                "source_role": "emperor_context",
                "source_shape": "emperor_annals_or_context_candidate",
                "title": "明史/卷1",
            }
        ],
        [],
    )

    assert coverage["has_emperor_context_source"] is True
    assert coverage["claim_closure_risk"] == ""
    assert coverage["needs_agent_review"] is False


def test_mention_slices_match_chinese_alias_split_by_whitespace() -> None:
    rows = tool.build_mention_slices(
        {"name": "李绩", "aliases": ["李勣"]},
        {
            "document_cache_code": "OSD-LIJI",
            "source_title": "旧唐书/卷67",
            "source_role": "object_biography_or_mentions",
        },
        "卷六十七 列傳第十七 李 靖 客師 令問 彥芳 李 𪟝 孫敬業。太宗委任之。",
        context_chars=40,
        max_slices_per_document=3,
    )

    assert len(rows) == 1
    assert "李𪟝" in rows[0]["matched_aliases"]
    assert rows[0]["person_name"] == "李绩"


def test_summary_lead_terms_prioritize_negative_source_window() -> None:
    full_text = (
        "李善长 [ 编辑 ] 李善长少读书有智计，佐太祖定天下，封韩国公。"
        "中间叙功臣封爵、议礼、营建、告归等事，文字继续铺开，使前后窗口分离。"
        "又记洪武初年诸臣进退，仍未涉及获罪。"
        "获罪身死 [ 编辑 ] 胡惟庸事发后，朱元璋赐死李善长，株连三族。"
    )
    rows = tool.build_mention_slices(
        {
            "name": "李善长",
            "summary_leads": [{"lead_terms": ["赐死", "株连三族"]}],
        },
        {
            "document_cache_code": "OSD-LSC-MINGSHI127",
            "source_title": "明史/卷127",
            "source_role": "object_biography_or_mentions",
        },
        full_text,
        context_chars=18,
        max_slices_per_document=1,
    )

    assert len(rows) == 1
    assert rows[0]["slice_kind"] == "summary_lead_term_anchor"
    assert rows[0]["lead_terms"] == ["赐死", "株连三族"]
    assert "赐死李善长" in rows[0]["raw_text"]
    assert "少读书有智计" not in rows[0]["raw_text"]


def test_summary_lead_terms_expand_to_classical_negative_variants() -> None:
    full_text = (
        "李善长 [ 编辑 ] 李善长少读书有智计，佐太祖定天下，封韩国公。"
        "太祖曾谓善长法有连坐三条，命其裁定律令。"
        "中间叙功臣封爵、议礼、营建、告归等事，文字继续铺开，使前后窗口分离。"
        "获罪身死 [ 编辑 ] 二十三年，善长坐惟庸党死，妻女弟侄七十余人徙边。"
    )
    rows = tool.build_mention_slices(
        {
            "name": "李善长",
            "summary_leads": [{"lead_terms": ["株连", "三族"]}],
        },
        {
            "document_cache_code": "OSD-LSC-MINGSHI127",
            "source_title": "明史/卷127",
            "source_role": "object_biography_or_mentions",
        },
        full_text,
        context_chars=20,
        max_slices_per_document=1,
    )

    assert len(rows) == 1
    assert rows[0]["slice_kind"] == "summary_lead_term_anchor"
    assert "善长" in rows[0]["matched_aliases"]
    assert set(rows[0]["lead_terms"]) >= {"党死", "妻女弟侄"}
    assert "坐惟庸党死" in rows[0]["raw_text"]
    assert "少读书有智计" not in rows[0]["raw_text"]


def test_summary_lead_anchors_support_historical_name_character_variants() -> None:
    rows = tool.build_mention_slices(
        {
            "name": "叶昇",
            "summary_leads": [{"lead_terms": ["被杀", "连坐"]}],
        },
        {
            "document_cache_code": "OSD-YES-MINGSHI131",
            "source_title": "明史/卷131",
            "source_role": "object_biography_or_mentions",
        },
        "叶升 [ 编辑 ] 二十五年，坐交通胡惟庸事觉，诛死，籍其家。",
        context_chars=30,
        max_slices_per_document=2,
    )

    assert len(rows) == 1
    assert rows[0]["slice_kind"] == "summary_lead_term_anchor"
    assert "叶升" in rows[0]["matched_aliases"]
    assert set(rows[0]["lead_terms"]) >= {"诛", "诛死", "籍其家"}


def test_summary_lead_anchor_rejects_adjacent_person_section() -> None:
    rows = tool.build_mention_slices(
        {
            "name": "叶昇",
            "summary_leads": [{"lead_terms": ["诛杀"]}],
        },
        {
            "document_cache_code": "OSD-YES-MINGSHI131",
            "source_title": "明史/卷131",
            "source_role": "object_biography_or_mentions",
        },
        "黄彬 [ 编辑 ] 黄彬坐胡惟庸党死，爵除。叶升 [ 编辑 ] 叶升二十五年坐交通胡惟庸事觉，诛死，籍其家。",
        context_chars=40,
        max_slices_per_document=1,
    )

    assert len(rows) == 1
    assert rows[0]["slice_kind"] == "summary_lead_term_anchor"
    assert "叶升二十五年" in rows[0]["raw_text"]
    assert "诛死" in rows[0]["lead_terms"]


def test_person_alias_anchor_prioritizes_matching_biography_section() -> None:
    rows = tool.build_mention_slices(
        {"name": "傅友德"},
        {
            "document_cache_code": "OSD-FYD-MINGSHI129",
            "source_title": "明史/卷129",
            "source_role": "object_biography_or_mentions",
        },
        "冯胜 [ 编辑 ] 冯胜与傅友德同征。傅友德 [ 编辑 ] 傅友德又明年赐死。",
        context_chars=20,
        max_slices_per_document=1,
    )

    assert len(rows) == 1
    assert rows[0]["section_heading"] == "傅友德"
    assert "傅友德又明年赐死" in rows[0]["raw_text"]


def test_discovery_expands_non_emperor_biography_queries() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        queries.append(query)
        if query.endswith("奸臣"):
            return [{"title": "明史/卷308", "url": "https://example.test/308", "snippet": "胡惟庸奸臣传"}]
        return [{"title": "明史演義/01", "url": "https://example.test/noise", "snippet": "noise"}]

    docs, hits = tool.discover_source_documents(
        {"name": "胡惟庸", "source_hints": ["明史"]},
        search_fn=fake_search,
        pages_per_query=1,
        timeout=3,
        source_hint_limit=1,
        max_search_names=1,
        include_emperor_annals=True,
    )

    assert "胡惟庸 明史 奸臣" in queries
    assert [row["source_title"] for row in docs] == ["明史/卷308"]
    assert any(hit.get("expanded_query") for hit in hits)


def test_discovery_can_use_source_document_hints_without_search() -> None:
    def fail_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        raise AssertionError(f"search should not be called: {query}")

    docs, hits = tool.discover_source_documents(
        {
            "name": "胡惟庸",
            "source_hints": ["明史"],
            "source_document_hints": [
                {
                    "title": "明史",
                    "volume": "卷三百八",
                    "locator": "奸臣胡惟庸传",
                    "url": "https://zh.wikisource.org/wiki/明史/卷308",
                }
            ],
        },
        search_fn=fail_search,
        pages_per_query=0,
        timeout=3,
        source_hint_limit=1,
        max_search_names=1,
        include_emperor_annals=True,
    )

    assert hits == []
    assert [row["source_title"] for row in docs] == ["明史/卷308"]
    assert docs[0]["source_document_hint"]["locator"] == "奸臣胡惟庸传"


def test_discovery_accepts_explicit_public_ocr_source_document_hint() -> None:
    docs, hits = tool.discover_source_documents(
        {
            "name": "朱檀",
            "aliases": ["鲁王"],
            "source_hints": ["明史"],
            "source_document_hints": [
                {
                    "title": "御制纪非录",
                    "locator": "御制纪非录正文 宗室条 朱檀 鲁王",
                    "url": "https://example.test/jifeilu",
                    "source_kind": "public_ocr_page",
                    "fetch_mode": "url",
                }
            ],
        },
        search_fn=lambda *_args, **_kwargs: [],
        pages_per_query=0,
        timeout=3,
        source_hint_limit=1,
        max_search_names=1,
        include_emperor_annals=True,
    )

    assert hits == []
    assert docs[0]["source_title"] == "御制纪非录"
    assert docs[0]["wikisource_title"] == ""
    assert docs[0]["fetch_mode"] == "url"
    assert docs[0]["source_kind"] == "public_ocr_page"


def test_fetched_public_ocr_document_does_not_become_wikisource(tmp_path: Path, monkeypatch) -> None:
    document = {
        "title": "御制纪非录",
        "source_title": "御制纪非录",
        "url": "https://example.test/jifeilu",
        "source_kind": "public_ocr_page",
        "fetch_mode": "url",
        "source_document_hint": {
            "ocr_aliases": ["魚王"],
            "section_start_aliases": ["魚王"],
            "ocr_requires_image_review": True,
        },
    }
    monkeypatch.setattr(tool, "fetch_document_text", lambda *_args, **_kwargs: ("魯王只是他处提及。魚王为恶。", {"source_key": "url:test", "cache_status": "miss"}))

    fetched, slices = tool.fetch_and_slice_document(
        {"name": "朱檀", "aliases": ["鲁王"]}, document, cache_dir=tmp_path, timeout=1, context_chars=20, max_slices_per_document=2
    )

    assert fetched["wikisource_title"] == ""
    assert len(slices) == 1
    assert slices[0]["matched_aliases"] == ["魚王"]
    assert "魯王" not in slices[0]["matched_aliases"]
    assert slices[0]["raw_text"] == "魚王为恶。"
    assert "ocr_requires_image_review" not in slices[0]


def test_discovery_keeps_script_variant_query_with_single_search_name() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        queries.append(query)
        if query == "湯和 明史 本傳":
            return [{"title": "明史/卷126", "url": "https://example.test/126", "snippet": "湯和列傳"}]
        return []

    docs, hits = tool.discover_source_documents(
        {"name": "汤和", "source_hints": ["明史"]},
        search_fn=fake_search,
        pages_per_query=1,
        timeout=3,
        source_hint_limit=1,
        max_search_names=1,
        include_emperor_annals=True,
    )

    assert "湯和 明史" in queries
    assert "湯和 明史 本傳" in queries
    assert [row["source_title"] for row in docs] == ["明史/卷126"]
    assert any(hit.get("script_variant_query") for hit in hits)


def test_directory_text_can_derive_volume_title_for_object_name() -> None:
    titles = tool.derived_volume_titles_from_directory_text(
        title="明史",
        directory_text="卷一百二十五 列傳第十三 徐達 常遇春\n卷一百二十六 列傳第十四 鄧愈 湯和",
        allowed_roots=["明史"],
        search_names=["汤和"],
    )

    assert titles == ["明史/卷126"]


def test_biography_signal_accepts_group_biography_heading() -> None:
    assert tool.has_biography_signal(
        {"name": "乐进"},
        {"wikisource_title": "三國志/卷17"},
        "魏書十七 張樂于張徐傳 樂進字文謙，陽平衛國人也。",
    )


def test_biography_signal_accepts_source_hint_locator() -> None:
    assert tool.has_biography_signal(
        {"name": "吴汉"},
        {
            "wikisource_title": "後漢書/卷18",
            "source_document_hint": {"title": "后汉书", "volume": "卷十八", "locator": "吴盖陈臧列传第八，吴汉传"},
        },
        "卷首未必在前八百字完整列出目标人名。",
    )


def test_title_from_source_document_hint_prefers_locator_then_volume() -> None:
    assert seed_tool.title_from_source_document_hint({"locator": "三國志/卷10", "title": "三國志"}) == "三國志/卷10"
    assert seed_tool.title_from_source_document_hint({"title": "后汉书", "volume": "卷十七"}) == "後漢書/卷17"
    assert seed_tool.title_from_source_document_hint({"locator": "旧唐书/卷96，姚崇宋璟传", "title": "旧唐书"}) == "舊唐書/卷96"
    assert seed_tool.title_from_source_document_hint({"locator": "後漢書/卷10上", "title": "後漢書"}) == "後漢書/卷10上"
    assert seed_tool.title_from_source_document_hint({"title": "後漢書", "volume": "卷10上"}) == "後漢書/卷10上"
    assert seed_tool.source_document_hint_title_candidates({"locator": "北史 (四庫全書本)/卷063", "title": "北史"})[:2] == [
        "北史(四庫全書本)/卷063",
        "北史/卷063",
    ]
    assert "三國志/魏志/卷06" in seed_tool.source_document_hint_title_candidates(
        {"locator": "三國志 (四庫全書本)/魏志/卷06", "title": "三國志"}
    )
    assert "三國志/卷6" in seed_tool.source_document_hint_title_candidates(
        {"locator": "三國志 (四庫全書本)/魏志/卷06", "title": "三國志"}
    )
    assert (
        seed_tool.title_from_source_document_hint(
            {"url": "https://zh.wikisource.org/wiki/%E5%BE%8C%E6%BC%A2%E6%9B%B8/%E5%8D%B718"}
        )
        == "後漢書/卷18"
    )
    assert (
        seed_tool.title_from_source_document_hint(
            {"url": "https://zh.wikisource.org/zh-hans/%E8%88%8A%E5%94%90%E6%9B%B8/%E5%8D%B751", "title": "旧唐书", "volume": "卷51"}
        )
        == "舊唐書/卷51"
    )
    assert seed_tool.title_from_source_document_hint({"url": "https://zh.wikisource.org/zh-hans/%E6%98%8E%E5%8F%B2", "title": "明史"}) == "明史"


def test_discovery_uses_seed_source_document_hints_before_search() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        return []

    docs, hits = tool.discover_source_documents(
        {
            "name": "夏侯惇",
            "source_hints": ["三國志"],
            "source_document_hints": [{"title": "三國志", "locator": "三國志/卷10"}],
        },
        search_fn=fake_search,
        pages_per_query=1,
        timeout=3,
        source_hint_limit=1,
        max_search_names=1,
        include_emperor_annals=True,
    )

    assert hits == []
    assert [row["source_title"] for row in docs] == ["三國志/卷10"]
    assert docs[0]["source_document_hint"]["locator"] == "三國志/卷10"
    assert docs[0]["wikisource_title_candidates"] == ["三國志/卷10", "三国志/卷10"]


def test_discovery_prioritizes_source_target_refs_for_biography_location() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        queries.append(query)
        if query == "李孝恭 舊唐書 宗室传":
            return [{"title": "舊唐書", "url": "https://example.test/jts", "snippet": "卷六十 宗室 河間王李孝恭傳"}]
        return []

    docs, hits = tool.discover_source_documents(
        {
            "name": "李孝恭",
            "source_hints": ["舊唐書", "新唐書"],
            "source_target_refs": ["旧唐书 宗室传 李孝恭"],
        },
        search_fn=fake_search,
        pages_per_query=1,
        timeout=3,
        source_hint_limit=2,
        max_search_names=1,
        include_emperor_annals=True,
    )

    assert queries[0] == "李孝恭 舊唐書 宗室传"
    assert [row["source_title"] for row in docs] == ["舊唐書/卷60"]
    assert docs[0]["source_target_ref"] == "旧唐书 宗室传 李孝恭"
    assert hits[0]["query_kind"] == "source_target_ref"
    assert hits[0]["derived_source_titles"] == ["舊唐書/卷60"]


def test_discovery_uses_source_target_ref_directory_before_search(monkeypatch) -> None:
    def fake_fetch(title: str, *, timeout: int, fetch_context: object | None = None) -> str:
        assert title == "明史"
        return "卷一百二十五 列傳第十三 徐達 常遇春\n卷一百二十八 列傳第十六 劉基 宋濂"

    def fake_search(query: str, *, limit: int, timeout: int, fetch_context: object | None = None) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(tool, "fetch_wikisource_plain_text", fake_fetch)

    docs, hits = tool.discover_source_documents(
        {
            "name": "刘基",
            "aliases": ["劉基"],
            "source_hints": ["明史"],
            "source_target_refs": ["明史 刘基传、宋濂传、李善长传、徐达传、常遇春传"],
        },
        search_fn=fake_search,
        pages_per_query=1,
        timeout=3,
        source_hint_limit=1,
        max_search_names=1,
        include_emperor_annals=True,
        fetch_context=object(),
    )

    assert [row["source_title"] for row in docs] == ["明史/卷128"]
    assert docs[0]["why_selected"] == "object source cache source_target_ref directory for 刘基"
    assert any(hit.get("query_kind") == "source_target_ref_directory" for hit in hits)


def test_discovery_adds_title_candidates_for_search_hits() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        return [{"title": "三國志(四庫全書本)/魏志/卷23", "url": "https://example.test/sgz23", "snippet": "曹仁傳"}]

    docs, _hits = tool.discover_source_documents(
        {"name": "曹仁", "source_hints": ["三國志"]},
        search_fn=fake_search,
        pages_per_query=1,
        timeout=3,
        source_hint_limit=1,
        max_search_names=1,
        include_emperor_annals=True,
    )

    assert docs[0]["source_title"] == "三國志(四庫全書本)/魏志/卷23"
    assert "三國志/卷23" in docs[0]["wikisource_title_candidates"]


def test_existing_source_hint_with_mention_closes_claim_source() -> None:
    document = {
        "person_name": "夏侯惇",
        "wikisource_title": "三國志/卷10",
        "source_role": "object_biography_or_mentions",
        "source_document_hint": {"title": "三國志", "locator": "三國志/卷10"},
    }

    assert tool.source_shape({"name": "夏侯惇"}, document, "太祖以夏侯惇為將。", 1) == "object_existing_source_candidate"
    coverage = tool.coverage_for_seed({"name": "夏侯惇"}, [{**document, "source_shape": "object_existing_source_candidate"}], [{"person_name": "夏侯惇"}])
    assert coverage["claim_closure_risk"] == ""
    assert coverage["needs_agent_review"] is False


def test_mention_slices_record_nearest_section_heading() -> None:
    full_text = (
        "邓愈 [ 编辑 ] 邓愈从太祖征伐，守洪都有功。兵兴诸将早贵，未有如愈与李文忠者。"
        "中间叙事继续铺开，使两个窗口不合并。又记军令严明，士卒不敢犯民。"
        "又记屯田、招抚、转运、守备诸事，文字继续展开，拉开两个命中点的距离。"
        "李文忠 [ 编辑 ] 李文忠从太祖攻建德、严州，屡破敌军。"
    )
    rows = tool.build_mention_slices(
        {"name": "李文忠"},
        {
            "document_cache_code": "OSD-LWZ",
            "source_title": "明史/卷126",
            "source_role": "object_biography_or_mentions",
        },
        full_text,
        context_chars=16,
        max_slices_per_document=4,
    )

    assert [row["section_heading"] for row in rows] == ["李文忠", "邓愈"]


def test_reslice_cache_rebuilds_slices_from_cached_text(tmp_path: Path) -> None:
    input_root = tmp_path / "old"
    output_root = tmp_path / "new"
    page_text = tmp_path / "page.txt"
    full_text = "邓愈 [ 编辑 ] 邓愈从太祖征伐，未有如愈与李文忠者。"
    page_text.write_text(full_text, encoding="utf-8")
    tool.write_jsonl(input_root / "person_seeds.jsonl", [{"name": "李文忠"}])
    tool.write_jsonl(
        input_root / "source_documents.jsonl",
        [
            {
                "document_cache_code": "OSD-LWZ",
                "person_cache_code": tool.person_cache_code({"name": "李文忠"}),
                "person_name": "李文忠",
                "source_title": "明史/卷126",
                "source_role": "object_biography_or_mentions",
                "source_shape": "object_biography_candidate",
                "shared_cache_text_path": str(page_text),
            }
        ],
    )
    tool.write_jsonl(
        input_root / "mention_slices.jsonl",
        [
            {
                "slice_cache_code": "OSS-OLD-STABLE",
                "document_cache_code": "OSD-LWZ",
                "person_name": "李文忠",
                "quote_hash": tool.sha256_text(tool.compact_text(full_text)),
            }
        ],
    )
    tool.write_jsonl(input_root / "search_hits.jsonl", [])

    manifest = tool.reslice_cache(input_root=input_root, output_root=output_root, context_chars=100)
    slices = [json.loads(line) for line in (output_root / "mention_slices.jsonl").read_text(encoding="utf-8").splitlines()]

    assert manifest["mode"] == "offline_reslice_existing_cache"
    assert manifest["totals"]["mention_slices"] == 1
    assert slices[0]["slice_cache_code"] == "OSS-OLD-STABLE"
    assert slices[0]["section_heading"] == "邓愈"


def test_annotate_cache_slices_preserves_slice_code(tmp_path: Path) -> None:
    input_root = tmp_path / "old"
    output_root = tmp_path / "annotated"
    page_text = tmp_path / "page.txt"
    full_text = "邓愈 [ 编辑 ] 邓愈从太祖征伐，未有如愈与李文忠者。"
    page_text.write_text(full_text, encoding="utf-8")
    tool.write_jsonl(input_root / "person_seeds.jsonl", [{"name": "李文忠"}])
    tool.write_jsonl(
        input_root / "source_documents.jsonl",
        [
            {
                "document_cache_code": "OSD-LWZ",
                "person_cache_code": tool.person_cache_code({"name": "李文忠"}),
                "person_name": "李文忠",
                "source_title": "明史/卷126",
                "source_role": "object_biography_or_mentions",
                "source_shape": "object_biography_candidate",
                "shared_cache_text_path": str(page_text),
            }
        ],
    )
    tool.write_jsonl(
        input_root / "mention_slices.jsonl",
        [
            {
                "slice_cache_code": "OSS-OLD-STABLE",
                "document_cache_code": "OSD-LWZ",
                "person_cache_code": tool.person_cache_code({"name": "李文忠"}),
                "person_name": "李文忠",
                "locator": "chars:0-35",
                "matched_aliases": ["李文忠"],
                "raw_text": full_text,
                "quote_hash": tool.sha256_text(tool.compact_text(full_text)),
            }
        ],
    )
    for name in ["person_coverage.jsonl", "search_hits.jsonl", "agent_review_queue.jsonl"]:
        tool.write_jsonl(input_root / name, [])

    manifest = tool.annotate_cache_slices(input_root=input_root, output_root=output_root)
    slices = [json.loads(line) for line in (output_root / "mention_slices.jsonl").read_text(encoding="utf-8").splitlines()]

    assert manifest["mode"] == "offline_annotate_existing_slices"
    assert slices[0]["slice_cache_code"] == "OSS-OLD-STABLE"
    assert slices[0]["section_heading"] == "邓愈"


def test_biography_hint_without_literal_mention_gets_locator_backed_slice(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch(document: dict, *, cache_dir: Path, timeout: int) -> tuple[str, dict]:
        return "列传第一 后妃上 昭容。其文辞明习，内掌诏命。", {"source_key": "wikisource:旧唐书/卷51"}

    monkeypatch.setattr(tool, "fetch_document_text", fake_fetch)
    document = {
        "document_cache_code": "OSD-SGWR",
        "person_cache_code": "PSC-SGWR",
        "person_name": "上官婉儿",
        "source_title": "旧唐书/卷51",
        "wikisource_title": "旧唐书/卷51",
        "source_role": "object_biography_or_mentions",
        "source_document_hint": {"title": "旧唐书", "volume": "卷51", "locator": "列传第一 后妃上 上官昭容"},
    }

    fetched_doc, slices = tool.fetch_and_slice_document(
        {"name": "上官婉儿", "source_document_hints": [document["source_document_hint"]]},
        document,
        cache_dir=tmp_path,
        timeout=1,
        context_chars=80,
        max_slices_per_document=4,
    )

    assert fetched_doc["source_shape"] == "object_biography_candidate"
    assert fetched_doc["mention_slice_count"] == 1
    assert slices[0]["slice_kind"] == "source_document_hint_locator"
    assert "上官昭容" in slices[0]["matched_aliases"]


def test_managed_fetch_tries_title_candidates_until_non_empty(tmp_path: Path, monkeypatch) -> None:
    seen_titles: list[str] = []

    def fake_fetch(title: str, *, timeout: int, fetch_context: object) -> str:
        seen_titles.append(title)
        return "" if title == "旧唐书/卷96" else "姚崇与宋璟同传。"

    monkeypatch.setattr(tool, "fetch_wikisource_plain_text", fake_fetch)
    document = {
        "document_cache_code": "OSD-YC",
        "person_cache_code": "PSC-YC",
        "person_name": "姚崇",
        "source_title": "旧唐书/卷96",
        "wikisource_title": "旧唐书/卷96",
        "wikisource_title_candidates": ["旧唐书/卷96", "舊唐書/卷96"],
        "source_role": "object_biography_or_mentions",
        "source_document_hint": {"title": "旧唐书", "volume": "卷96", "locator": "列传第四十六 姚崇 宋璟"},
    }

    fetched_doc, slices = tool.fetch_and_slice_document(
        {"name": "姚崇"},
        document,
        cache_dir=tmp_path,
        timeout=1,
        context_chars=80,
        max_slices_per_document=4,
        fetch_context=object(),
    )

    assert seen_titles == ["旧唐书/卷96", "舊唐書/卷96"]
    assert fetched_doc["wikisource_title"] == "舊唐書/卷96"
    assert fetched_doc["source_key"] == "wikisource:舊唐書/卷96"
    assert slices[0]["matched_aliases"] == ["姚崇"]


def test_discovery_uses_directory_index_when_root_hit_snippet_is_insufficient(monkeypatch) -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        queries.append(query)
        if query == "汤和 明史":
            return [{"title": "明史", "url": "https://example.test/mingshi", "snippet": "明史目錄 本紀 列傳"}]
        return []

    def fake_fetch_plain_text(title: str, *, timeout: int, fetch_context) -> str:
        assert title == "明史"
        return "卷一百二十五 列傳第十三 徐達 常遇春\n卷一百二十六 列傳第十四 鄧愈 湯和"

    monkeypatch.setattr(tool, "fetch_wikisource_plain_text", fake_fetch_plain_text)

    docs, hits = tool.discover_source_documents(
        {"name": "汤和", "source_hints": ["明史"]},
        search_fn=fake_search,
        pages_per_query=1,
        timeout=3,
        source_hint_limit=1,
        max_search_names=1,
        include_emperor_annals=True,
        fetch_context=object(),
    )

    assert queries[0] == "汤和 明史"
    assert [row["source_title"] for row in docs] == ["明史/卷126"]
    assert any(hit.get("directory_index_source_titles") == ["明史/卷126"] for hit in hits)


def test_seed_from_runs_collects_task_objects_and_gap_objects(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    person_dir = run_root / "TGT-1"
    person_dir.mkdir(parents=True)
    (person_dir / "task.final.json").write_text(
        json.dumps(
            {
                "source_strategy": {"source_hints": ["明史"]},
                "emperor_name": "朱元璋",
                "target_payload": {"period": "明", "title": "明太祖"},
                "object_seeds": [
                    {"name": "汤和", "aliases": [{"alias": "信国公", "strength": "medium"}]},
                    {"name": "常遇春"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (person_dir / "judge_result.final.json").write_text(
        json.dumps(
            {
                "coverage_gaps": [
                    {"gap_type": "object_claim_undercoverage", "object_name": "邓愈"},
                    {"gap_type": "alias_missing", "object_name": "汤和"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = tool.extract_seed_rows_from_runs([run_root])
    by_name = {row["name"]: row for row in rows}

    assert set(by_name) == {"朱元璋", "汤和", "常遇春", "邓愈"}
    assert by_name["朱元璋"]["is_emperor"] is True
    assert by_name["朱元璋"]["priority"] == 20
    assert by_name["朱元璋"]["source_hints"] == ["明史"]
    assert by_name["汤和"]["source_hints"] == ["明史"]
    assert by_name["汤和"]["title"] == "明太祖"
    assert "信国公" in by_name["汤和"]["aliases"]
    assert by_name["邓愈"]["priority"] == 50


def test_merge_object_pool_alias_rows_respects_period_and_emperor_scope() -> None:
    seeds = [
        tool.normalize_seed(
            {
                "name": "汤和",
                "period": "明",
                "target_emperors": ["朱元璋"],
                "aliases": ["湯和"],
                "source_hints": ["明史"],
            },
            seed_source="test",
        )
    ]
    merged = tool.merge_object_pool_alias_rows(
        seeds,
        [
            {
                "period": "明",
                "canonical_name": "汤和",
                "alias_text": "信国公",
                "alias_kind": "title",
                "scope": "global",
            },
            {
                "period": "明",
                "canonical_name": "汤和",
                "alias_text": "中山侯",
                "alias_kind": "title",
                "scope": "emperor",
                "scope_emp_name": "朱元璋",
            },
            {
                "period": "明",
                "canonical_name": "汤和",
                "alias_text": "其他朝专用名",
                "alias_kind": "alias",
                "scope": "emperor",
                "scope_emp_name": "朱棣",
            },
            {
                "period": "清",
                "canonical_name": "汤和",
                "alias_text": "错朝别名",
                "alias_kind": "alias",
                "scope": "global",
            },
        ],
    )

    row = merged[0]
    assert "raw_obj_aliases" in row["seed_sources"]
    assert "信国公" in row["aliases"]
    assert "中山侯" in row["aliases"]
    assert "其他朝专用名" not in row["aliases"]
    assert "错朝别名" not in row["aliases"]
    assert {item["alias"] for item in row["object_pool_aliases"]} == {"信国公", "中山侯"}


def test_seed_audit_reports_missing_and_resolvable_source_hints() -> None:
    seeds = [
        tool.normalize_seed(
            {
                "name": "汤和",
                "period": "明",
                "aliases": ["信国公"],
                "source_hints": ["明史"],
                "source_document_hints": [{"title": "明史", "volume": "卷一百二十六"}],
                "object_pool_aliases": [{"alias": "中山侯"}],
            },
            seed_source="test",
        ),
        tool.normalize_seed({"name": "胡惟庸", "period": "明"}, seed_source="test"),
        {"aliases": ["无名"]},
    ]

    report = tool.seed_audit_report(seeds)
    md = tool.render_seed_audit_markdown(report)

    assert report["totals"]["persons"] == 3
    assert report["totals"]["with_source_hints"] == 1
    assert report["totals"]["with_resolvable_source_document_hints"] == 1
    assert report["totals"]["with_object_pool_aliases"] == 1
    assert report["totals"]["invalid_rows"] == 1
    assert report["issue_counts"]["no_source_hints"] == 1
    assert report["issue_counts"]["no_source_document_hints"] == 1
    assert report["issue_counts"]["missing_person_name"] == 1
    assert "胡惟庸" in md


def test_seed_aliases_include_stage_base_name_and_locator_titles() -> None:
    stage_seed = tool.normalize_seed(
        {
            "name": "姚崇早期",
            "source_document_hints": [{"locator": "列传第四十六 姚崇 宋璟", "title": "旧唐书", "volume": "卷96"}],
        },
        seed_source="test",
    )
    locator_seed = tool.normalize_seed(
        {
            "name": "上官婉儿",
            "source_document_hints": [{"locator": "列传第一 后妃上 上官昭容", "title": "旧唐书", "volume": "卷51"}],
        },
        seed_source="test",
    )
    title_seed = tool.normalize_seed(
        {
            "name": "刘据",
            "source_document_hints": [{"locator": "武五子传，戾太子据", "title": "汉书", "volume": "卷六十三"}],
        },
        seed_source="test",
    )

    assert "姚崇" in stage_seed["aliases"]
    assert "姚崇" in stage_seed["expanded_aliases"]
    assert "上官昭容" in locator_seed["aliases"]
    assert "上官昭容" in locator_seed["expanded_aliases"]
    assert "戾太子据" in title_seed["aliases"]
    assert "戾太子" in title_seed["expanded_aliases"]


def test_schema_draft_keeps_agent_slot_and_file_backed_paths() -> None:
    sql = tool.PGSQL_SCHEMA_DRAFT

    assert "object_source_cache_persons" in sql
    assert "object_source_cache_documents" in sql
    assert "shared_cache_text_path text not null default ''" in sql
    assert "needs_agent_review boolean not null default false" in sql
    assert "agent_status text not null default 'not_requested'" in sql


def test_overlay_task_merges_usable_cache_documents(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    (cache_root / "source_documents.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "document_cache_code": "OSD-HWY",
                        "person_cache_code": "PSC-HWY",
                        "person_name": "胡惟庸",
                        "source_title": "明史/卷308",
                        "wikisource_title": "明史/卷308",
                        "source_kind": "wikisource_page",
                        "source_role": "object_biography_or_mentions",
                        "source_shape": "object_biography_candidate",
                        "mention_slice_count": 2,
                        "text_chars": 1200,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "document_cache_code": "OSD-MTZ",
                        "person_cache_code": "PSC-MTZ",
                        "person_name": "朱元璋",
                        "source_title": "明史/卷1",
                        "wikisource_title": "明史/卷1",
                        "source_kind": "wikisource_page",
                        "source_role": "emperor_context",
                        "source_shape": "emperor_annals_or_context_candidate",
                        "mention_slice_count": 1,
                        "text_chars": 2400,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "document_cache_code": "OSD-TH-BAD",
                        "person_cache_code": "PSC-TH",
                        "person_name": "汤和",
                        "source_title": "明史/卷999",
                        "wikisource_title": "明史/卷999",
                        "source_role": "object_biography_or_mentions",
                        "source_shape": "unmatched_fetched_source",
                        "mention_slice_count": 0,
                        "text_chars": 100,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task = {
        "emperor_name": "朱元璋",
        "target_profile": {"aliases": ["明太祖"]},
        "object_seeds": [{"name": "胡惟庸"}, {"name": "汤和"}],
        "source_documents": [{"document_code": "DOC-BASE", "title": "明史/卷2", "text": "太祖本纪。"}],
        "search_plan": {},
        "clean_audit": {},
    }

    overlaid, stats = tool.overlay_task_from_cache(task, cache_root=cache_root)

    titles = [row["title"] for row in overlaid["source_documents"]]
    assert titles == ["明史/卷2", "明史/卷308", "明史/卷1"]
    assert stats["added_source_document_count"] == 2
    assert stats["agent_invocation_enabled"] is False
    assert "胡惟庸" in stats["matched_object_names"]
    assert "朱元璋" in stats["matched_object_names"]
    assert "明史/卷999" not in titles
    assert overlaid["clean_audit"]["object_source_cache_overlay_agent_invoked"] is False


def test_overlay_task_keeps_same_volume_for_different_object_owners(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    (cache_root / "source_documents.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "document_cache_code": "OSD-LWZ",
                        "person_cache_code": "PSC-LWZ",
                        "person_name": "李文忠",
                        "source_title": "明史/卷126",
                        "wikisource_title": "明史/卷126",
                        "source_role": "object_biography_or_mentions",
                        "source_shape": "object_biography_candidate",
                        "mention_slice_count": 4,
                        "text_chars": 12000,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "document_cache_code": "OSD-MY",
                        "person_cache_code": "PSC-MY",
                        "person_name": "沐英",
                        "source_title": "明史/卷126",
                        "wikisource_title": "明史/卷126",
                        "source_role": "object_biography_or_mentions",
                        "source_shape": "object_biography_candidate",
                        "mention_slice_count": 4,
                        "text_chars": 12000,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task = {
        "emperor_name": "朱元璋",
        "object_seeds": [{"name": "李文忠"}, {"name": "沐英"}],
        "source_documents": [{"document_code": "DOC-BASE", "title": "明史/卷126", "text": "既有共享卷。"}],
    }

    overlaid, stats = tool.overlay_task_from_cache(task, cache_root=cache_root)

    owner_docs = [
        row.get("object_source_cache", {}).get("person_name")
        for row in overlaid["source_documents"]
        if row.get("object_source_cache")
    ]
    assert owner_docs == ["李文忠", "沐英"]
    assert stats["added_source_document_count"] == 2


def test_overlay_task_can_exclude_emperor_context(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    (cache_root / "source_documents.jsonl").write_text(
        json.dumps(
            {
                "document_cache_code": "OSD-MTZ",
                "person_cache_code": "PSC-MTZ",
                "person_name": "朱元璋",
                "source_title": "明史/卷1",
                "wikisource_title": "明史/卷1",
                "source_role": "emperor_context",
                "source_shape": "emperor_annals_or_context_candidate",
                "mention_slice_count": 1,
                "text_chars": 2400,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    overlaid, stats = tool.overlay_task_from_cache(
        {"emperor_name": "朱元璋", "object_seeds": [], "source_documents": []},
        cache_root=cache_root,
        include_emperor_context=False,
    )

    assert overlaid["source_documents"] == []
    assert stats["added_source_document_count"] == 0


def test_review_audit_classifies_remaining_slots(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    (cache_root / "person_coverage.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "person_name": "曹仁",
                        "person_cache_code": "PSC-CR",
                        "needs_agent_review": True,
                        "claim_closure_risk": "source_fetched_but_no_person_mention",
                        "agent_review_reason": "source_shape_or_alias_conflict",
                        "source_shapes": ["unmatched_fetched_source"],
                        "source_document_count": 1,
                        "mention_slice_count": 0,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "person_name": "潘美",
                        "person_cache_code": "PSC-PM",
                        "needs_agent_review": True,
                        "claim_closure_risk": "mentions_without_biography_source",
                        "agent_review_reason": "biography_shape_uncertain",
                        "source_shapes": ["object_mention_candidate"],
                        "source_document_count": 1,
                        "mention_slice_count": 1,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (cache_root / "source_documents.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "person_name": "曹仁",
                        "wikisource_title": "三国志/卷2",
                        "source_shape": "unmatched_fetched_source",
                        "text_chars": 0,
                        "mention_slice_count": 0,
                        "why_selected": "object source cache source_document_hint for 曹仁",
                        "source_document_hint": {"locator": "三國志 (四庫全書本)/吳志/卷02", "title": "三國志"},
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "person_name": "潘美",
                        "wikisource_title": "宋史/卷258",
                        "source_shape": "object_mention_candidate",
                        "text_chars": 9447,
                        "mention_slice_count": 1,
                        "why_selected": "object source cache search for 潘美",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (cache_root / "mention_slices.jsonl").write_text("", encoding="utf-8")

    audit = tool.build_review_audit(cache_root)

    assert audit["totals"]["review_rows"] == 2
    assert audit["classification_counts"]["title_route_collapse"] == 1
    assert audit["classification_counts"]["mention_without_biography_shape"] == 1
    assert audit["issue_tag_counts"]["fourku_locator_collapsed"] == 1
    assert audit["issue_tag_counts"]["subpath_locator_collapsed"] == 1
    assert "| 曹仁 | source_fetched_but_no_person_mention | title_route_collapse |" in tool.render_review_audit_markdown(audit)


def test_review_audit_cli_writes_reports(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    (cache_root / "person_coverage.jsonl").write_text(
        json.dumps(
            {
                "person_name": "刘据",
                "person_cache_code": "PSC-LJ",
                "needs_agent_review": True,
                "claim_closure_risk": "source_fetched_but_no_person_mention",
                "source_shapes": ["unmatched_fetched_source"],
                "source_document_count": 1,
                "mention_slice_count": 0,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (cache_root / "source_documents.jsonl").write_text("", encoding="utf-8")
    (cache_root / "mention_slices.jsonl").write_text("", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "dev" / "retrieval_v3_object_source_cache.py"),
            "review-audit",
            "--cache-root",
            str(cache_root),
            "--output-json",
            str(tmp_path / "audit.json"),
            "--output-md",
            str(tmp_path / "audit.md"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["totals"]["review_rows"] == 1
    assert json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))["review_rows"][0]["person_name"] == "刘据"
    assert "# retrieval_v3 object source cache review audit" in (tmp_path / "audit.md").read_text(encoding="utf-8")


def test_merge_rescue_cache_replaces_rescue_people(tmp_path: Path) -> None:
    base = tmp_path / "base"
    rescue = tmp_path / "rescue"
    out = tmp_path / "merged"
    base.mkdir()
    rescue.mkdir()
    (base / "person_coverage.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"person_name": "甲", "needs_agent_review": False}, ensure_ascii=False),
                json.dumps({"person_name": "乙", "needs_agent_review": True}, ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (rescue / "person_coverage.jsonl").write_text(
        json.dumps({"person_name": "乙", "needs_agent_review": False}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for file_name in ["source_documents.jsonl", "mention_slices.jsonl", "agent_review_queue.jsonl", "fetch_errors.jsonl", "search_hits.jsonl"]:
        (base / file_name).write_text(
            "\n".join(
                [
                    json.dumps({"person_name": "甲", "value": "base-a"}, ensure_ascii=False),
                    json.dumps({"person_name": "乙", "value": "base-b"}, ensure_ascii=False),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (rescue / file_name).write_text(json.dumps({"person_name": "乙", "value": "rescue-b"}, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = tool.merge_rescue_cache(base, rescue, out)

    coverage = read_jsonl(out / "person_coverage.jsonl")
    docs = read_jsonl(out / "source_documents.jsonl")
    assert [row["person_name"] for row in coverage] == ["甲", "乙"]
    assert [row["value"] for row in docs] == ["base-a", "rescue-b"]
    assert summary["totals"]["base_review_rows"] == 1
    assert summary["totals"]["merged_review_rows"] == 0
    assert (out / "rescue_merge_summary.json").is_file()
    assert (out / "rescue_merge_report.md").is_file()


def test_merge_rescue_cli_writes_merged_cache(tmp_path: Path) -> None:
    base = tmp_path / "base"
    rescue = tmp_path / "rescue"
    out = tmp_path / "merged"
    base.mkdir()
    rescue.mkdir()
    (base / "person_coverage.jsonl").write_text(json.dumps({"person_name": "甲", "needs_agent_review": True}, ensure_ascii=False) + "\n", encoding="utf-8")
    (rescue / "person_coverage.jsonl").write_text(json.dumps({"person_name": "甲", "needs_agent_review": False}, ensure_ascii=False) + "\n", encoding="utf-8")
    for file_name in ["source_documents.jsonl", "mention_slices.jsonl", "agent_review_queue.jsonl", "fetch_errors.jsonl", "search_hits.jsonl"]:
        (base / file_name).write_text("", encoding="utf-8")
        (rescue / file_name).write_text("", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "dev" / "retrieval_v3_object_source_cache.py"),
            "merge-rescue",
            "--base-cache-root",
            str(base),
            "--rescue-cache-root",
            str(rescue),
            "--output-root",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["totals"]["merged_review_rows"] == 0
    assert read_jsonl(out / "person_coverage.jsonl")[0]["needs_agent_review"] is False


def test_source_hint_worklist_summarizes_review_actions(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    (cache_root / "person_coverage.jsonl").write_text(
        json.dumps(
            {
                "person_name": "刘苍",
                "person_cache_code": "PSC-LC",
                "needs_agent_review": True,
                "claim_closure_risk": "source_fetched_but_no_person_mention",
                "agent_review_reason": "source_shape_or_alias_conflict",
                "source_shapes": ["unmatched_fetched_source"],
                "source_document_count": 1,
                "mention_slice_count": 0,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (cache_root / "source_documents.jsonl").write_text(
        json.dumps(
            {
                "person_name": "刘苍",
                "wikisource_title": "後漢書/卷2",
                "source_shape": "unmatched_fetched_source",
                "text_chars": 100,
                "mention_slice_count": 0,
                "why_selected": "object source cache source_document_hint for 刘苍",
                "source_document_hint": {"locator": "後漢書/卷2", "title": "後漢書"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (cache_root / "mention_slices.jsonl").write_text("", encoding="utf-8")
    seed_jsonl = tmp_path / "seed.jsonl"
    seed_jsonl.write_text(
        json.dumps({"name": "刘苍", "aliases": ["刘苍"], "source_document_hints": [{"locator": "後漢書/卷2"}]}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    worklist = hint_worklist.build_source_hint_worklist(cache_root, seed_jsonl=seed_jsonl)

    item = worklist["workitems"][0]
    assert item["person_name"] == "刘苍"
    assert item["recommended_action"] == "alias_or_title_review"
    assert item["current_aliases"] == ["刘苍"]
    assert item["documents"][0]["title"] == "後漢書/卷2"
    assert "### 刘苍" in hint_worklist.render_source_hint_worklist_markdown(worklist)


def test_source_hint_worklist_cli_writes_outputs(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    (cache_root / "person_coverage.jsonl").write_text(
        json.dumps(
            {
                "person_name": "曹仁",
                "person_cache_code": "PSC-CR",
                "needs_agent_review": True,
                "claim_closure_risk": "source_fetched_but_no_person_mention",
                "source_shapes": ["unmatched_fetched_source"],
                "source_document_count": 1,
                "mention_slice_count": 0,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (cache_root / "source_documents.jsonl").write_text("", encoding="utf-8")
    (cache_root / "mention_slices.jsonl").write_text("", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "dev" / "retrieval_v3_object_source_cache_hint_worklist.py"),
            "--cache-root",
            str(cache_root),
            "--output-json",
            str(tmp_path / "worklist.json"),
            "--output-md",
            str(tmp_path / "worklist.md"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["totals"]["workitems"] == 1
    assert json.loads((tmp_path / "worklist.json").read_text(encoding="utf-8"))["workitems"][0]["person_name"] == "曹仁"
    assert "# retrieval_v3 object source hint correction worklist" in (tmp_path / "worklist.md").read_text(encoding="utf-8")


def test_seed_patch_applies_worklist_suggested_patch() -> None:
    seeds = [
        {
            "name": "曹仁",
            "aliases": ["曹仁"],
            "expanded_aliases": ["曹仁"],
            "source_hints": ["三國志"],
            "source_document_hints": [{"title": "三國志", "locator": "三國志/卷02"}],
        }
    ]
    patch_rows = seed_patch.iter_patch_rows(
        {
            "workitems": [
                {
                    "person_name": "曹仁",
                    "suggested_patch": {
                        "new_aliases": ["子孝"],
                        "add_source_hints": ["魏書"],
                        "replace_source_document_hints": [{"title": "三國志", "locator": "三國志/魏志/卷09"}],
                    },
                }
            ]
        }
    )

    output, report = seed_patch.apply_seed_patches(seeds, patch_rows)
    row = output[0]

    assert "子孝" in row["aliases"]
    assert "魏書" in row["source_hints"]
    assert row["source_document_hints"] == [{"title": "三國志", "locator": "三國志/魏志/卷09"}]
    assert "object_source_cache_patch" in row["seed_sources"]
    assert report["totals"]["applied_people"] == 1
    assert report["totals"]["alias_added_count"] == 1
    assert report["totals"]["source_document_hint_replaced_count"] == 1


def test_seed_patch_cli_writes_output_and_report(tmp_path: Path) -> None:
    seed_jsonl = tmp_path / "seed.jsonl"
    seed_jsonl.write_text(
        json.dumps(
            {
                "name": "潘美",
                "aliases": ["潘美"],
                "source_document_hints": [{"title": "宋史", "locator": "宋史/卷258"}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    patch_json = tmp_path / "patch.json"
    patch_json.write_text(
        json.dumps(
            {
                "patches": [
                    {
                        "person_name": "潘美",
                        "add_source_document_hints": [{"title": "宋史", "locator": "宋史/卷259"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "dev" / "retrieval_v3_object_source_cache_patch.py"),
            "apply",
            "--seed-jsonl",
            str(seed_jsonl),
            "--patch-json",
            str(patch_json),
            "--output-jsonl",
            str(tmp_path / "seed.patched.jsonl"),
            "--report-json",
            str(tmp_path / "patch_report.json"),
            "--report-md",
            str(tmp_path / "patch_report.md"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["totals"]["source_document_hint_added_count"] == 1
    patched = read_jsonl(tmp_path / "seed.patched.jsonl")
    assert [hint["locator"] for hint in patched[0]["source_document_hints"]] == ["宋史/卷258", "宋史/卷259"]
    assert "# retrieval_v3 object source cache seed patch report" in (tmp_path / "patch_report.md").read_text(encoding="utf-8")


def test_seed_patch_cli_rejects_missing_person(tmp_path: Path) -> None:
    seed_jsonl = tmp_path / "seed.jsonl"
    seed_jsonl.write_text(json.dumps({"name": "潘美"}, ensure_ascii=False) + "\n", encoding="utf-8")
    patch_json = tmp_path / "patch.json"
    patch_json.write_text(
        json.dumps({"patches": [{"person_name": "不存在", "new_aliases": ["某"]}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "dev" / "retrieval_v3_object_source_cache_patch.py"),
            "apply",
            "--seed-jsonl",
            str(seed_jsonl),
            "--patch-json",
            str(patch_json),
            "--output-jsonl",
            str(tmp_path / "seed.patched.jsonl"),
            "--report-json",
            str(tmp_path / "patch_report.json"),
            "--report-md",
            str(tmp_path / "patch_report.md"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "patch people missing from seed" in completed.stderr
    assert not (tmp_path / "seed.patched.jsonl").exists()


def test_run_build_shards_writes_resumable_summary(tmp_path: Path) -> None:
    seeds = [{"name": "甲"}, {"name": "乙"}, {"name": "丙"}]

    def fake_run(cmd, *, text, capture_output, check, timeout):
        assert text is True
        assert capture_output is True
        assert check is False
        assert timeout == 10
        seed_path = Path(cmd[cmd.index("--seed-jsonl") + 1])
        output_root = Path(cmd[cmd.index("--output-root") + 1])
        rows = read_jsonl(seed_path)
        output_root.mkdir(parents=True)
        coverage_rows = [
            {
                "person_name": row["name"],
                "needs_agent_review": row["name"] == "丙",
                "has_source_document": True,
                "has_biography_source": row["name"] != "丙",
            }
            for row in rows
        ]
        (output_root / "person_coverage.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in coverage_rows),
            encoding="utf-8",
        )
        (output_root / "source_documents.jsonl").write_text("", encoding="utf-8")
        (output_root / "mention_slices.jsonl").write_text("", encoding="utf-8")
        (output_root / "agent_review_queue.jsonl").write_text(
            json.dumps({"person_name": "丙"}, ensure_ascii=False) + "\n" if any(row["name"] == "丙" for row in rows) else "",
            encoding="utf-8",
        )
        (output_root / "fetch_errors.jsonl").write_text("", encoding="utf-8")
        manifest = {
            "totals": {
                "persons": len(rows),
                "source_documents": len(rows),
                "mention_slices": 0,
                "coverage_needs_agent_review": sum(1 for row in rows if row["name"] == "丙"),
                "search_hits": 0,
                "fetch_errors": 0,
                "elapsed_seconds": 0.1,
            }
        }
        (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"ok": True, "manifest": manifest}), stderr="")

    summary = tool.run_build_shards(
        seeds,
        output_root=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        build_cli_args=["--pages-per-query", "1"],
        shard_size=2,
        shard_timeout=10,
        script_path=Path("tool.py"),
        python_executable=sys.executable,
        run_fn=fake_run,
    )

    assert summary["totals"]["shard_count"] == 2
    assert summary["totals"]["completed"] == 2
    assert summary["totals"]["persons"] == 3
    assert summary["totals"]["coverage_needs_agent_review"] == 1
    assert summary["merged_counts"]["person_coverage"] == 3
    assert (tmp_path / "out" / "shard_summary.json").is_file()
    assert (tmp_path / "out" / "shard_report.md").is_file()
    assert (tmp_path / "out" / "shard_progress.jsonl").is_file()
    assert [row["person_name"] for row in read_jsonl(tmp_path / "out" / "person_coverage.jsonl")] == ["甲", "乙", "丙"]


def test_cli_reports_missing_dsn_without_traceback(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "dev" / "retrieval_v3_object_source_cache.py"),
            "seed-from-db",
            "--output-jsonl",
            str(tmp_path / "seed.jsonl"),
            "--dsn-env",
            "OBJECT_SOURCE_CACHE_TEST_MISSING_DSN",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "missing PostgreSQL DSN env var: OBJECT_SOURCE_CACHE_TEST_MISSING_DSN" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_terminal_outcome_terms_from_discovery_summary_are_search_anchors_only() -> None:
    terms = tool.terminal_outcome_terms_from_text("晚年被下狱，随后赐死并牵连亲族。")
    assert "赐死" in terms
    assert "下狱" in terms
