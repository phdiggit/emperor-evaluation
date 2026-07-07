from __future__ import annotations

from scripts.dev import retrieval_v2_source_gap_feedback as tool


def sample_task() -> dict:
    return {
        "target_code": "TGT-I5B-MTZ",
        "emperor_name": "朱元璋",
        "target_payload": {"period": "明"},
        "source_strategy": {"source_hints": ["明史"]},
        "object_seeds": [{"name": "胡惟庸"}, {"name": "汤和"}, {"name": "徐达"}],
        "source_documents": [{"document_code": "DOC-BASE", "title": "明史/卷2", "text": "太祖本纪。"}],
        "search_plan": {},
        "generation_notes": [],
        "clean_audit": {},
    }


def test_source_gap_feedback_refines_task_for_gap_objects() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        queries.append(query)
        assert limit == 1
        assert timeout == 3
        return [
            {
                "title": "明史/卷308",
                "url": "https://example.test/mingshi-308",
                "snippet": "胡惟庸宠任专擅",
                "text": "帝以胡惟庸为才，宠任之。惟庸独相数岁，生杀黜陟，或不奏径行。",
            }
        ]

    gap_rows = [
        {
            "object_name": "胡惟庸",
            "gap_type": "source_missing",
            "recommended_action": "run_object_source_refiner",
        }
    ]

    refined, stats = tool.refine_task_from_source_gap_feedback(
        sample_task(),
        gap_rows,
        max_objects=2,
        pages_per_object=1,
        timeout=3,
        search_fn=fake_search,
    )

    assert queries == ["胡惟庸 明史"]
    assert stats["searched_object_names"] == ["胡惟庸"]
    assert stats["added_source_document_count"] == 1
    assert any(row["title"] == "明史/卷308" for row in refined["source_documents"])


def test_do_not_refine_without_source_refiner_action() -> None:
    refined, stats = tool.refine_task_from_source_gap_feedback(
        sample_task(),
        [{"object_name": "胡惟庸", "gap_type": "source_missing", "recommended_action": "manual_review"}],
    )

    assert refined["source_documents"] == sample_task()["source_documents"]
    assert stats["added_source_document_count"] == 0
    assert stats["searched_object_names"] == []


def test_object_claim_undercoverage_feedback_refines_task() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        queries.append(query)
        return [
            {
                "title": "明史/卷126",
                "url": "https://example.test/mingshi-126",
                "snippet": "汤和征南提督海运镇北平",
                "text": "汤和征南，提督海运，镇北平。",
            }
        ]

    refined, stats = tool.refine_task_from_source_gap_feedback(
        sample_task(),
        [
            {
                "object_name": "汤和",
                "gap_type": "object_claim_undercoverage",
                "queue": "source_pack_refinement",
                "recommended_action": "run_object_source_refiner",
                "do_not_add_recall_terms": True,
            }
        ],
        pages_per_object=1,
        timeout=3,
        search_fn=fake_search,
    )

    assert queries == ["汤和 明史"]
    assert stats["searched_object_names"] == ["汤和"]
    assert any(row["title"] == "明史/卷126" for row in refined["source_documents"])


def test_source_gap_search_expands_object_biography_queries() -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        queries.append(query)
        if query.endswith("奸臣"):
            return [{"title": "明史/卷308", "snippet": "胡惟庸奸臣传"}]
        return [{"title": "明史/卷127", "snippet": "李善长传"}]

    search = tool.source_gap_search_fn(
        [
            {
                "object_name": "胡惟庸",
                "recommended_action": "run_object_source_refiner",
                "required_source_type": ["object_biography"],
            }
        ],
        base_search=fake_search,
    )

    assert search is not None
    pages = search("胡惟庸 明史", limit=2, timeout=3)

    assert queries[0] == "胡惟庸 明史 奸臣"
    assert [row["title"] for row in pages] == ["明史/卷308", "明史/卷127"]


def test_focused_candidates_keeps_only_gap_object_and_referenced_sources() -> None:
    candidates = {
        "candidate_slices": [
            {"object_name": "胡惟庸", "document_code": "DOC-HWY", "text": "胡惟庸宠任。"},
            {"object_name": "徐达", "document_code": "DOC-XD", "text": "徐达北征。"},
        ],
        "source_documents": [
            {"document_code": "DOC-HWY", "title": "明史/卷308"},
            {"document_code": "DOC-XD", "title": "明史/卷125"},
        ],
        "object_seeds": [{"name": "胡惟庸"}, {"name": "徐达"}],
        "stats": {"candidate_slices": 2},
    }

    focused = tool.focused_candidates(candidates, object_names=["胡惟庸"])

    assert [row["object_name"] for row in focused["candidate_slices"]] == ["胡惟庸"]
    assert [row["document_code"] for row in focused["source_documents"]] == ["DOC-HWY"]
    assert [row["name"] for row in focused["object_seeds"]] == ["胡惟庸"]
    assert focused["coverage"]["object_slice_counts"] == {"胡惟庸": 1}
    assert focused["coverage"]["ready_for_judgement"] is True
