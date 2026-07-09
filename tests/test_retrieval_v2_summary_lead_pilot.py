from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_object_source_cache as object_cache
from scripts.dev import retrieval_v2_summary_lead_pilot as pilot
from tests.test_retrieval_v2_summary_lead_discovery import HU_WEIYONG_HTML, LAN_YU_HTML, LI_SHANCHANG_HTML


def write_jobs(tmp_path: Path) -> Path:
    fixtures = [
        ("li.html", "李善长", "https://zh.wikipedia.org/wiki/李善長", "获罪身死", LI_SHANCHANG_HTML),
        ("hu.html", "胡惟庸", "https://zh.wikipedia.org/wiki/胡惟庸", "胡惟庸案", HU_WEIYONG_HTML),
        ("lan.html", "蓝玉", "https://zh.wikipedia.org/wiki/蓝玉", "被杀", LAN_YU_HTML),
    ]
    rows = []
    for file_name, person, url, section, html in fixtures:
        html_path = tmp_path / file_name
        html_path.write_text(html, encoding="utf-8")
        rows.append({"person": person, "url": url, "section": section, "input_html": str(html_path)})
    jobs_path = tmp_path / "summary_jobs.jsonl"
    jobs_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return jobs_path


def test_summary_lead_pilot_builds_claim_plan_without_judge_or_db(tmp_path, monkeypatch) -> None:
    page_texts = {
        "國朝獻徵錄/卷11": "李善长知逆谋不发举。帝遂并其妻女弟侄家口七十馀人诛之。",
        "明史/卷127": "李善长坐胡惟庸党，朱元璋命并其家口诛之。",
        "明史/卷308": "胡惟庸谋反伏诛，党与坐死者甚众。",
        "明史/卷132": "蓝玉谋反，狱成，族诛。",
    }

    def fake_fetch(title: str, *, timeout: int, fetch_context=None) -> str:
        return page_texts[title]

    monkeypatch.setattr(object_cache, "fetch_wikisource_plain_text", fake_fetch)
    report = pilot.run_pilot(
        input_jobs_jsonl=write_jobs(tmp_path),
        output_root=tmp_path / "pilot",
        emperor_name="朱元璋",
        pages_per_query=0,
        context_chars=80,
        max_slices_per_document=3,
    )

    assert report["summary_pages_as_evidence"] is False
    assert report["judge_invocation_enabled"] is False
    assert report["write_db"] is False
    assert report["consumption_enabled"] is False
    assert report["summary"]["job_count"] == 3
    assert report["summary"]["lead_count"] == 3
    assert report["object_cache_totals"]["search_hits"] == 0
    assert report["object_cache_totals"]["fetch_errors"] == 0
    assert report["source_titles_by_object"]["李善长"] == ["國朝獻徵錄/卷11", "明史/卷127"]
    assert report["claim_plan"]["uncovered_slice_count"] >= 3
    assert set(report["claim_plan"]["by_object"]) == {"李善长", "胡惟庸", "蓝玉"}

    candidates = json.loads((tmp_path / "pilot" / "claim_candidates.uncovered.json").read_text(encoding="utf-8"))
    assert all("wikipedia.org" not in json.dumps(row, ensure_ascii=False) for row in candidates["source_documents"])
    assert any(row["object_name"] == "李善长" and "妻女弟侄" in row["text"] for row in candidates["candidate_slices"])
    assert "judge_invocation_enabled: `false`" in (tmp_path / "pilot" / "pilot_report.md").read_text(encoding="utf-8")
