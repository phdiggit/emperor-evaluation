from scripts.dev import retrieval_v3_intake_orchestrator as tool


def test_wikipedia_summary_enrichment_only_emits_discovery_leads() -> None:
    rows, report = tool.enrich_wikipedia_summary_leads(
        [{"name": "冯胜", "aliases": []}],
        fetcher=lambda _name: {
            "status": "found",
            "title": "馮勝",
            "url": "https://zh.wikipedia.org/wiki/example",
            "extract": "馮勝后来被赐死。",
        },
    )
    assert report["objects_with_terminal_leads"] == ["冯胜"]
    assert rows[0]["summary_leads"][0]["lead_terms"] == ["赐死"]
    assert rows[0]["summary_leads"][0]["evidence_allowed"] is False
    assert "extract" not in rows[0]["wikipedia_discovery"]
    assert "馮勝" in rows[0]["aliases"]


def test_wikipedia_summary_retains_nonfatal_terminal_outcome() -> None:
    rows, report = tool.enrich_wikipedia_summary_leads(
        [{"name": "臧荼", "aliases": [], "expanded_aliases": []}],
        fetcher=lambda _name: {
            "status": "found",
            "title": "臧荼",
            "url": "https://zh.wikipedia.org/wiki/example",
            "extract": "汉高祖亲征，臧荼兵败被俘。",
        },
    )
    assert rows[0]["summary_leads"][0]["lead_terms"] == ["被俘"]
    assert report["objects_with_terminal_leads"] == ["臧荼"]
