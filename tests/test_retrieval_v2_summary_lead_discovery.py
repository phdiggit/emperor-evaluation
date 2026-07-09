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

HU_WEIYONG_HTML = """
<html>
  <body>
    <h1>胡惟庸</h1>
    <h2>胡惟庸案</h2>
    <p>洪武十三年，胡惟庸以谋反伏诛，其党羽坐死者甚众。</p>
    <h2>延伸阅读</h2>
    <p><a href="https://zh.wikisource.org/wiki/%E6%98%8E%E5%8F%B2/%E5%8D%B7308#%E8%83%A1%E6%83%9F%E5%BA%B8">明史卷三百八</a></p>
  </body>
</html>
"""

LAN_YU_HTML = """
<html>
  <body>
    <h1>蓝玉</h1>
    <h2>被杀</h2>
    <p>洪武二十六年，蓝玉坐谋反，被族诛，牵连者甚众。</p>
    <p><a href="https://zh.wikisource.org/wiki/%E6%98%8E%E5%8F%B2/%E5%8D%B7132#%E8%97%8D%E7%8E%89">明史卷一百三十二</a></p>
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


def test_batch_jobs_cover_multiple_negative_case_leads(tmp_path) -> None:
    fixtures = [
        ("li.html", "李善长", "https://zh.wikipedia.org/wiki/李善長", "获罪身死", LI_SHANCHANG_HTML, ["國朝獻徵錄/卷11", "明史/卷127"]),
        ("hu.html", "胡惟庸", "https://zh.wikipedia.org/wiki/胡惟庸", "胡惟庸案", HU_WEIYONG_HTML, ["明史/卷308"]),
        ("lan.html", "蓝玉", "https://zh.wikipedia.org/wiki/蓝玉", "被杀", LAN_YU_HTML, ["明史/卷132"]),
    ]
    jobs_path = tmp_path / "jobs.jsonl"
    job_rows = []
    for file_name, person, url, section, html, _titles in fixtures:
        html_path = tmp_path / file_name
        html_path.write_text(html, encoding="utf-8")
        job_rows.append({"person": person, "url": url, "sections": [section], "input_html": str(html_path)})
    jobs_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in job_rows), encoding="utf-8")

    leads, seeds, report = tool.discover_jobs(tool.read_jsonl(jobs_path), timeout=3, lead_terms=tool.DEFAULT_LEAD_TERMS)

    assert report["job_count"] == 3
    assert report["lead_count"] == 3
    assert report["seed_count"] == 3
    assert report["resolvable_source_document_hint_count"] == 4
    assert [seed["name"] for seed in seeds] == ["李善长", "胡惟庸", "蓝玉"]
    assert [[hint["wikisource_title"] for hint in seed["source_document_hints"]] for seed in seeds] == [
        ["國朝獻徵錄/卷11", "明史/卷127"],
        ["明史/卷308"],
        ["明史/卷132"],
    ]
    assert all(lead["evidence_policy"] == "lead_only_not_provenance" for lead in leads)


def test_batch_seed_output_feeds_object_source_cache_without_search(tmp_path) -> None:
    jobs_path = tmp_path / "jobs.jsonl"
    html_path = tmp_path / "lan.html"
    html_path.write_text(LAN_YU_HTML, encoding="utf-8")
    jobs_path.write_text(
        json.dumps(
            {
                "person": "蓝玉",
                "url": "https://zh.wikipedia.org/wiki/蓝玉",
                "section": "被杀",
                "input_html": str(html_path),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    seeds_path = tmp_path / "seeds.jsonl"

    tool.main(
        [
            "--input-jobs-jsonl",
            str(jobs_path),
            "--output-seeds-jsonl",
            str(seeds_path),
        ]
    )
    seed = json.loads(seeds_path.read_text(encoding="utf-8").splitlines()[0])

    def fail_search(query: str, *, limit: int, timeout: int) -> list[dict[str, str]]:
        raise AssertionError(f"search should not be called: {query}")

    docs, hits = object_cache.discover_source_documents(
        seed,
        search_fn=fail_search,
        pages_per_query=0,
        timeout=3,
        source_hint_limit=1,
        max_search_names=1,
        include_emperor_annals=True,
    )

    assert hits == []
    assert [row["source_title"] for row in docs] == ["明史/卷132"]
    assert docs[0]["source_document_hint"]["evidence_policy"] == "lead_only_not_provenance"


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
