from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import i5b_query_profile_seed_builder as tool


def half_baked_profile() -> dict:
    return {
        "person": "曹丕",
        "query_profile_id": "QRY-CAOPI",
        "source_group": "all_monarch_backfill",
        "source_targets": ["三国志 本纪与列传", "资治通鉴 魏纪"],
        "object_layers": {
            "core_positive_objects": ["任用授权待识别对象"],
            "negative_or_reversal_objects": ["功臣安全与处置对象"],
            "adjacent_split_objects": ["军事成败"],
        },
        "query_bundles": ["曹丕 魏文帝 任用 授权 宰相 大臣 三国志"],
    }


def test_seed_builder_uses_local_rows_to_make_review_only_profile_seed() -> None:
    profile = half_baked_profile()
    row = {"person": "曹丕", "action_status": "profile_needs_work"}
    source_rows = [
        (
            Path("data/query_lane_coverage.jsonl"),
            {
                "person": "曹丕",
                "lane_group": "positive",
                "query_terms": ["陈群", "司马懿", "任用"],
                "coverage_status": "converted_to_card",
                "lane_coverage_id": "LCOV-CAOPI-POS",
            },
        ),
        (
            Path("data/evidence_cards.jsonl"),
            {
                "person": "曹丕",
                "polarity": "negative",
                "trigger_terms": ["曹洪", "处置"],
                "verification_status": "source_verified",
                "evidence_id": "EVD-CAOPI-NEG",
            },
        ),
    ]

    report = tool.build_seed_report(profiles={"曹丕": profile}, status_rows=[row], source_rows=source_rows)

    assert report["workflow_code"] == "I5B"
    assert report["totals"]["persons"] == 1
    assert report["totals"]["candidate_objects"] == 3
    seed = report["seeds"][0]
    patch = seed["seed_profile_patch_candidate"]
    assert set(patch["replace_object_layers"]["core_positive_objects"]) == {"陈群", "司马懿"}
    assert patch["replace_object_layers"]["negative_or_reversal_objects"] == ["曹洪"]
    assert any("曹丕 陈群" in query for query in patch["append_query_bundles"])
    assert seed["requires_review"] is True


def test_seed_builder_cli_writes_markdown_without_touching_profile(tmp_path: Path) -> None:
    profile_path = tmp_path / "profiles.jsonl"
    original = json.dumps({**half_baked_profile(), "workflow_code": "I5A"}, ensure_ascii=False) + "\n"
    profile_path.write_text(original, encoding="utf-8")
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps({"rows": [{"person": "曹丕", "action_status": "profile_needs_work"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    candidate_path = tmp_path / "candidate.jsonl"
    candidate_path.write_text(
        json.dumps({"person": "曹丕", "lane_group": "positive", "query_terms": ["陈群"], "lane_coverage_id": "LCOV"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "seed.md"

    assert tool.main(
        [
            "--profile",
            str(profile_path),
            "--status-report",
            str(status_path),
            "--candidate-source",
            str(candidate_path),
            "--workflow-code",
            "I5A",
            "--output",
            str(output),
        ]
    ) == 0

    text = output.read_text(encoding="utf-8")
    assert "I5A 半成品检索包种子候选" in text
    assert "- workflow_code: `I5A`" in text
    assert "陈群" in text
    assert profile_path.read_text(encoding="utf-8") == original


def test_seed_builder_rejects_status_report_workflow_mismatch(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps({"workflow_code": "I5B", "rows": []}, ensure_ascii=False), encoding="utf-8")

    try:
        tool.load_status_rows(
            status_report=status_path,
            profile_path=tmp_path / "profiles.jsonl",
            source_pack_root=tmp_path / "packs",
            all_list=tmp_path / "all.yml",
            jobs_dir=tmp_path / "jobs",
            logs_dir=tmp_path / "logs",
            workflow_code="I5A",
        )
    except tool.ExcerptPoolError as exc:
        assert "status report workflow_code mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("workflow-mismatched status reports should be rejected")


def test_seed_builder_online_probe_uses_search_snippets(monkeypatch) -> None:
    profile = half_baked_profile()
    row = {"person": "曹丕", "action_status": "profile_needs_work"}

    def fake_search(query, **kwargs):
        assert "曹丕" in query
        return [{"title": "三國志/卷22", "snippet": "帝拜陈群为尚书，任司马懿参机密。"}]

    monkeypatch.setattr(tool, "search_wikisource", fake_search)

    report = tool.build_seed_report(
        profiles={"曹丕": profile},
        status_rows=[row],
        source_rows=[],
        online_probe=True,
        online_probe_queries_per_person=1,
        online_pages_per_query=1,
        request_delay_seconds=0,
    )

    objects = {item["object_name"] for item in report["seeds"][0]["candidate_objects"]}
    assert {"陈群", "司马懿"} <= objects
    assert report["seeds"][0]["requires_review"] is True


def test_seed_builder_source_discovery_uses_page_text(monkeypatch) -> None:
    profile = half_baked_profile()
    row = {"person": "曹丕", "action_status": "profile_needs_work"}

    def fake_search(query, **kwargs):
        assert "曹丕" in query
        return [{"title": "三國志/卷22", "snippet": ""}]

    def fake_fetch(title, **kwargs):
        assert title == "三國志/卷22"
        return "曹丕，文皇帝讳丕。帝拜陈群为尚书。任司马懿为侍中。司马懿谏曰。诛曹洪。"

    monkeypatch.setattr(tool, "search_wikisource", fake_search)
    monkeypatch.setattr(tool, "fetch_wikisource_plain_text", fake_fetch)

    report = tool.build_seed_report(
        profiles={"曹丕": profile},
        status_rows=[row],
        source_rows=[],
        source_discovery=True,
        source_discovery_queries_per_person=1,
        source_discovery_pages_per_query=1,
        source_discovery_max_pages_per_person=1,
        request_delay_seconds=0,
        cache_enabled=False,
    )

    candidates = report["seeds"][0]["candidate_objects"]
    objects = {item["object_name"] for item in candidates}
    assert {"陈群", "司马懿", "曹洪"} <= objects
    source_refs = [
        ref
        for item in candidates
        for ref in item["supporting_rows"]
        if ref["path"] == "source_discovery_page_text"
    ]
    assert source_refs
    assert any("拜陈群为尚书" in ref["context"] for ref in source_refs)


def test_source_discovery_queries_start_with_broad_source_queries() -> None:
    queries = tool._source_discovery_queries(half_baked_profile(), max_queries=4)

    assert queries[0] == "曹丕 三国志"
    assert queries[1] == "曹丕 资治通鉴"
    assert any(query.startswith("魏文帝 ") for query in queries)


def test_source_discovery_expands_source_index_pages(monkeypatch) -> None:
    profile = half_baked_profile()
    row = {"person": "曹丕", "action_status": "profile_needs_work"}
    fetched_titles: list[str] = []

    def fake_search(query, **kwargs):
        assert "曹丕" in query
        return [{"title": "三國志", "snippet": "卷 一 武帝 操 卷 二 文帝 丕 卷 三 明帝 叡"}]

    def fake_fetch(title, **kwargs):
        fetched_titles.append(title)
        if title == "三國志/卷02":
            return "曹丕，文皇帝讳丕。帝拜陈群为尚书。"
        return "曹操起兵。"

    monkeypatch.setattr(tool, "search_wikisource", fake_search)
    monkeypatch.setattr(tool, "fetch_wikisource_plain_text", fake_fetch)

    report = tool.build_seed_report(
        profiles={"曹丕": profile},
        status_rows=[row],
        source_rows=[],
        source_discovery=True,
        source_discovery_queries_per_person=1,
        source_discovery_pages_per_query=1,
        source_discovery_max_pages_per_person=2,
        request_delay_seconds=0,
        cache_enabled=False,
    )

    assert "三國志/卷02" in fetched_titles
    assert "三國志/卷01" not in fetched_titles
    objects = {item["object_name"] for item in report["seeds"][0]["candidate_objects"]}
    assert "陈群" in objects


def test_source_discovery_does_not_treat_single_given_name_as_anchor() -> None:
    profile = half_baked_profile()
    text = "建安年间，典籍称丕然有文。孙权以吕蒙为南郡太守。"

    candidates = tool.extract_source_discovery_candidates_from_text(
        text,
        profile=profile,
        page_title="资治通鉴/卷六十八",
        query="曹丕 资治通鉴",
        context_chars=40,
    )

    assert candidates == []


def test_source_discovery_yiwei_requires_office_tail() -> None:
    profile = half_baked_profile()
    text = "曹丕诏曰，以夏数为得天，故即用夏正。"

    candidates = tool.extract_source_discovery_candidates_from_text(
        text,
        profile=profile,
        page_title="三國志/卷02",
        query="曹丕 三国志",
        context_chars=40,
    )

    assert candidates == []
