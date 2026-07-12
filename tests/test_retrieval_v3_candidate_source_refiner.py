from __future__ import annotations

from scripts.dev import retrieval_v3_candidate_source_refiner as tool


def sample_task() -> dict:
    return {
        "target_code": "TGT-I5B-CC",
        "emperor_name": "曹操",
        "rule_code": "delegation",
        "object_seeds": [
            {"name": "荀彧", "aliases": [{"alias": "文若", "strength": "strong"}]},
            {"name": "乐进"},
        ],
        "source_documents": [{"document_code": "DOC-001", "title": "三國志/卷一", "text": "太祖起兵。"}],
        "search_plan": {},
        "generation_notes": [],
        "clean_audit": {},
    }


def test_candidate_gap_object_names_reads_coverage_and_gap_rows() -> None:
    candidates = {
        "coverage": {"objects_without_slices": ["荀彧"]},
        "coverage_gaps": [
            {"gap_type": "alias_missing", "object_name": "荀彧"},
            {"gap_type": "source_missing", "object_name": "乐进"},
            {"gap_type": "fetch_error", "object_name": ""},
        ],
    }

    assert tool.candidate_gap_object_names(candidates) == ["荀彧", "乐进"]


def test_judge_gap_object_names_reads_source_actionable_rows() -> None:
    judge_result = {
        "coverage_gaps": [
            {"gap_type": "predicate_missing", "object_name": "张辅"},
            {"gap_type": "object_claim_undercoverage", "object_name": "汤和"},
            {"gap_type": "negative_undercoverage", "object_name": "解缙"},
            {"gap_type": "mixed_claim_not_split", "object_name": "纪纲"},
        ]
    }

    assert tool.judge_gap_object_names(judge_result) == ["张辅", "汤和", "解缙"]


def test_refine_task_sources_for_candidate_gaps_searches_only_gap_objects() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        queries.append(query)
        assert limit == 1
        assert timeout == 3
        return [
            {
                "title": f"三國志/{query}",
                "url": "https://example.test/source",
                "snippet": "hit",
                "text": "太祖以荀彧为司马，委以军国之事。",
            }
        ]

    candidates = {
        "coverage": {"objects_without_slices": ["荀彧"]},
        "coverage_gaps": [{"gap_type": "alias_missing", "object_name": "荀彧"}],
    }
    refined, stats = tool.refine_task_sources_for_candidate_gaps(
        sample_task(),
        candidates,
        max_objects=4,
        pages_per_object=1,
        timeout=3,
        search_fn=fake_search,
    )

    assert queries == ["荀彧 三國志", "文若 三國志"]
    assert stats["gap_object_names"] == ["荀彧"]
    assert stats["added_source_document_count"] == 2
    assert len(refined["source_documents"]) == 3
    assert refined["source_documents"][1]["text"] == "太祖以荀彧为司马，委以军国之事。"
    assert refined["search_plan"]["candidate_gap_source_presearch"]["searched_object_names"] == ["荀彧"]
    assert refined["clean_audit"]["candidate_gap_source_presearch"] is True


def test_refine_task_sources_for_judge_gaps_can_search_object_without_seed() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        queries.append(query)
        return [{"title": "三國志/卷十", "url": "https://example.test/sgz10", "snippet": "郭嘉"}]

    task = sample_task()
    task["object_seeds"] = [{"name": "荀彧"}]
    refined, stats = tool.refine_task_sources_for_candidate_gaps(
        task,
        {"coverage_gaps": [{"gap_type": "predicate_missing", "object_name": "郭嘉"}]},
        stage="judge",
        max_objects=4,
        pages_per_object=1,
        timeout=3,
        search_fn=fake_search,
    )

    assert queries == ["郭嘉 三國志"]
    assert stats["stage"] == "judge"
    assert stats["searched_object_names"] == ["郭嘉"]
    assert refined["search_plan"]["judge_gap_source_presearch"]["gap_object_names"] == ["郭嘉"]


def test_refine_task_sources_for_candidate_gaps_accepts_external_object_names() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        queries.append(query)
        return [
            {
                "title": "三國志/卷十",
                "url": "https://example.test/sgz10",
                "snippet": "荀彧",
                "text": "太祖命荀彧为司马，委以军国之事。",
            }
        ]

    refined, stats = tool.refine_task_sources_for_candidate_gaps(
        sample_task(),
        {"coverage": {"objects_without_slices": []}, "coverage_gaps": []},
        object_names=["荀彧"],
        max_objects=4,
        pages_per_object=1,
        timeout=3,
        search_fn=fake_search,
    )

    assert queries == ["荀彧 三國志", "文若 三國志"]
    assert stats["gap_object_names"] == ["荀彧"]
    assert stats["added_source_document_count"] == 1
    assert refined["search_plan"]["candidate_gap_source_presearch"]["searched_object_names"] == ["荀彧"]


def test_refine_task_sources_for_candidate_gaps_filters_source_root_mismatch() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        return [
            {"title": "舊五代史/卷145", "url": "https://example.test/wrong", "snippet": "wrong"},
            {"title": "三國志/卷十", "url": "https://example.test/right", "snippet": "right"},
        ]

    task = sample_task()
    task["target_payload"] = {"period": "三國"}
    candidates = {
        "coverage": {"objects_without_slices": ["荀彧"]},
        "coverage_gaps": [{"gap_type": "alias_missing", "object_name": "荀彧"}],
    }
    refined, stats = tool.refine_task_sources_for_candidate_gaps(
        task,
        candidates,
        max_objects=1,
        pages_per_object=2,
        timeout=3,
        search_fn=fake_search,
    )

    assert [row["title"] for row in refined["source_documents"]] == ["三國志/卷一", "三國志/卷十"]
    assert stats["added_source_document_count"] == 1
    rejected = [
        hit
        for hit in refined["search_plan"]["candidate_gap_source_presearch"]["hits"]
        if hit.get("rejected_reason")
    ]
    assert rejected[0]["title"] == "舊五代史/卷145"


def test_refine_task_sources_for_candidate_gaps_derives_volume_from_root_hit() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        return [
            {
                "title": "三國志",
                "url": "https://example.test/sgz",
                "snippet": "卷十六 魏書十六 任峻 蘇則 卷十七 魏書十七 二張樂于徐傳 張 遼 樂進 于禁 徐晃",
            }
        ]

    task = sample_task()
    task["target_payload"] = {"period": "三國"}
    task["object_seeds"] = [{"name": "張遼", "aliases": [{"alias": "文遠", "strength": "strong"}]}]
    candidates = {
        "coverage": {"objects_without_slices": ["張遼"]},
        "coverage_gaps": [{"gap_type": "source_missing", "object_name": "張遼"}],
    }
    refined, stats = tool.refine_task_sources_for_candidate_gaps(
        task,
        candidates,
        max_objects=1,
        pages_per_object=1,
        timeout=3,
        source_hint_limit=1,
        search_fn=fake_search,
    )

    assert any(row["title"] == "三國志/卷17" for row in refined["source_documents"])
    assert stats["added_source_document_count"] == 1
    hit = refined["search_plan"]["candidate_gap_source_presearch"]["hits"][0]
    assert hit["derived_source_titles"] == ["三國志/卷17"]


def test_refine_task_sources_for_candidate_gaps_derives_volume_from_source_hit() -> None:
    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        return [
            {
                "title": "史記正義 (四庫全書本)/卷102",
                "url": "https://example.test/shiji-zhengyi",
                "snippet": "史記 卷102 張釋之馮唐列傳第四十二 魏尚坐上功首虜差六級 文帝令馮唐持節赦魏尚",
            }
        ]

    task = sample_task()
    task["target_code"] = "TGT-I5B-LH"
    task["emperor_name"] = "刘恒"
    task["target_payload"] = {"period": "西汉"}
    task["source_strategy"] = {"source_hints": ["史記"]}
    task["source_documents"] = [{"document_code": "DOC-001", "title": "史記/卷010", "text": "孝文本紀。"}]
    task["object_seeds"] = [{"name": "冯唐"}]
    candidates = {
        "coverage": {"objects_without_slices": ["冯唐"]},
        "coverage_gaps": [{"gap_type": "alias_missing", "object_name": "冯唐"}],
    }
    refined, stats = tool.refine_task_sources_for_candidate_gaps(
        task,
        candidates,
        max_objects=1,
        pages_per_object=1,
        timeout=3,
        source_hint_limit=1,
        search_fn=fake_search,
    )

    assert any(row["title"] == "史記/卷102" for row in refined["source_documents"])
    assert stats["added_source_document_count"] == 1
    hit = next(
        row
        for row in refined["search_plan"]["candidate_gap_source_presearch"]["hits"]
        if row.get("derived_source_titles")
    )
    assert hit["derived_source_titles"] == ["史記/卷102"]


def test_source_hints_prefer_target_period_before_existing_documents() -> None:
    task = sample_task()
    task["target_payload"] = {"period": "三國"}
    task["source_documents"] = [{"title": "欽定古今圖書集成/明倫彙編"}]

    assert tool.source_hints_from_task(task, max_hints=2) == ["三國志", "資治通鑑"]


def test_source_hints_use_three_kingdoms_marker_for_cao_wei_targets() -> None:
    task = sample_task()
    task["target_payload"] = {"period": "东汉", "title": "魏武帝"}

    assert tool.source_hints_from_task(task, max_hints=2) == ["三國志", "後漢書"]
