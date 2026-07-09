from __future__ import annotations

import json

from scripts.dev import retrieval_v2_object_source_cache as object_cache
from scripts.dev import retrieval_v2_summary_lead_discovery as tool


LI_SHANCHANG_HTML = """
<html>
  <body>
    <h1>李善長</h1>
    <h2>生平<span>[编辑]</span></h2>
    <h3>获罪身死<span>[编辑]</span></h3>
    <p>
      洪武二十三年，朱元璋便将李善长赐死，将其妻女弟侄等全家七十余人一并处死，
      株連三族。
    </p>
    <p>
      参考原文见
      <a href="https://zh.wikisource.org/wiki/%E5%9C%8B%E6%9C%9D%E7%8D%BB%E5%BE%B5%E9%8C%84/%E5%8D%B711">國朝獻徵錄·卷之十一</a>
      与
      <a href="https://zh.wikisource.org/wiki/%E6%98%8E%E5%8F%B2/%E5%8D%B7127">明史卷一百二十七</a>。
    </p>
  </body>
</html>
"""


def test_summary_lead_discovers_wikisource_hints_from_wikipedia_section() -> None:
    leads, report = tool.discover_from_html(
        LI_SHANCHANG_HTML,
        person_name="李善长",
        discovery_url="https://zh.wikipedia.org/wiki/李善長",
        section_titles=["获罪身死"],
    )

    assert report["lead_count"] == 1
    assert report["source_document_hint_count"] == 2
    lead = leads[0]
    assert lead["evidence_policy"] == "lead_only_not_provenance"
    assert "株連" in lead["lead_terms"]
    assert "三族" in lead["lead_terms"]
    assert [row["wikisource_title"] for row in lead["source_document_hints"]] == [
        "國朝獻徵錄/卷11",
        "明史/卷127",
    ]


def test_summary_lead_seed_patch_feeds_object_source_cache_without_search() -> None:
    leads, _report = tool.discover_from_html(
        LI_SHANCHANG_HTML,
        person_name="李善长",
        discovery_url="https://zh.wikipedia.org/wiki/李善長",
        section_titles=["获罪身死"],
    )
    seed = tool.seed_patch_from_leads("李善长", leads)

    def fail_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        raise AssertionError(f"search should not be called: {query}")

    docs, hits = object_cache.discover_source_documents(
        seed,
        search_fn=fail_search,
        pages_per_query=0,
        timeout=3,
        source_hint_limit=2,
        max_search_names=1,
        include_emperor_annals=True,
    )

    assert hits == []
    assert [row["source_title"] for row in docs] == ["國朝獻徵錄/卷11", "明史/卷127"]
    assert all(row["source_document_hint"]["evidence_policy"] == "lead_only_not_provenance" for row in docs)


def test_summary_lead_uses_page_level_wikisource_links_when_section_has_only_internal_links() -> None:
    html = """
    <html><body>
      <h1>李善長</h1>
      <h3>获罪身死</h3>
      <p><a href="/wiki/胡惟庸">胡惟庸</a>案后，朱元璋赐死李善长并株連三族。</p>
      <h2>延伸阅读</h2>
      <p><a href="https://zh.wikisource.org/wiki/%E6%98%8E%E5%8F%B2/%E5%8D%B7127#%E6%9D%8E%E5%96%84%E9%95%B7">明史卷一百二十七</a></p>
    </body></html>
    """

    leads, report = tool.discover_from_html(
        html,
        person_name="李善长",
        discovery_url="https://zh.wikipedia.org/wiki/李善長",
        section_titles=["获罪身死"],
    )

    assert report["source_document_hint_count"] == 1
    assert leads[0]["source_document_hints"][0]["wikisource_title"] == "明史/卷127"


def test_cli_writes_leads_and_seed_jsonl(tmp_path, capsys) -> None:
    html_path = tmp_path / "li.html"
    leads_path = tmp_path / "leads.jsonl"
    seeds_path = tmp_path / "seeds.jsonl"
    report_path = tmp_path / "report.json"
    html_path.write_text(LI_SHANCHANG_HTML, encoding="utf-8")

    rc = tool.main(
        [
            "--url",
            "https://zh.wikipedia.org/wiki/李善長",
            "--input-html",
            str(html_path),
            "--person",
            "李善长",
            "--section",
            "获罪身死",
            "--output-leads-jsonl",
            str(leads_path),
            "--output-seeds-jsonl",
            str(seeds_path),
            "--output-report-json",
            str(report_path),
        ]
    )

    assert rc == 0
    assert json.loads(report_path.read_text(encoding="utf-8"))["resolvable_source_document_hint_count"] == 2
    assert json.loads(leads_path.read_text(encoding="utf-8").splitlines()[0])["lead_source_kind"] == "wikipedia_summary"
    assert json.loads(seeds_path.read_text(encoding="utf-8").splitlines()[0])["name"] == "李善长"
    assert json.loads(capsys.readouterr().out)["ok"] is True
