from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = ROOT / "data" / "batches" / "i5b_typical_batch_b1_qin_han"
QUERY_SOURCE_SPEC_PATH = BATCH_DIR / "source_evidence_specs.jsonl"
SOURCE_PACK_PATH = BATCH_DIR / "source_pack.jsonl"
SOURCE_REVIEW_LOG_PATH = BATCH_DIR / "source_review_log.jsonl"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def rows_by_id(path: Path, key: str) -> dict[str, dict[str, object]]:
    return {str(row[key]): row for row in read_jsonl(path)}


def test_batch_b1_persistent_research_assets_are_only_yingzheng_and_liuheng() -> None:
    spec_rows = read_jsonl(QUERY_SOURCE_SPEC_PATH)
    source_pack_rows = read_jsonl(SOURCE_PACK_PATH)
    review_rows = read_jsonl(SOURCE_REVIEW_LOG_PATH)

    assert {row["person"] for row in spec_rows} == {"嬴政", "刘恒"}
    assert {row["person"] for row in source_pack_rows} == {"嬴政", "刘恒"}
    assert {row["person"] for row in review_rows} == {"嬴政", "刘恒"}
    assert Counter(row["person"] for row in source_pack_rows) == {
        "嬴政": 3,
        "刘恒": 3,
    }
    assert Counter(row["person"] for row in review_rows) == {
        "嬴政": 5,
        "刘恒": 7,
    }
    assert {row["lead_status"] for row in review_rows} == {
        "source_verified_evidence_created",
        "lead_needs_source_review",
    }


def test_batch_b1_source_pack_rows_preserve_locator_excerpt_and_context() -> None:
    source_pack_rows = read_jsonl(SOURCE_PACK_PATH)

    for row in source_pack_rows:
        assert row["batch_id"] == "i5b_typical_batch_b1_qin_han_20260628"
        assert row["source_pack_id"]
        assert row["source_id"]
        assert row["source_locator"]
        assert row["source_url"]
        assert row["excerpt_short"]
        assert row["excerpt_context"]
        assert row["context_summary"]
        assert row["context_scope"]
        assert row["adjacent_item_split"]
        assert row["linked_search_ids"]
        assert row["linked_evidence_ids"]
        assert row["linked_cluster_ids"]
        assert row["review_status"] == "source_verified_evidence_created"


def test_batch_b1_review_log_keeps_converted_and_still_review_leads() -> None:
    review_rows = rows_by_id(SOURCE_REVIEW_LOG_PATH, "search_id")

    converted = {
        "SRCH-I5B-YINGZHENG-POS-LISI-001": "EVD-I5B-YINGZHENG-POS-LISI-KEQING-001",
        "SRCH-I5B-YINGZHENG-POS-WANGJIAN-001": "EVD-I5B-YINGZHENG-POS-WANGJIAN-AUTH-001",
        "SRCH-I5B-YINGZHENG-NEG-FENSHU-001": "EVD-I5B-YINGZHENG-NEG-FENSHU-001",
        "SRCH-I5B-LIUHENG-POS-ZHANGSHIZHI-001": "EVD-I5B-LIUHENG-POS-ZHANGSHIZHI-RONGJIAN-001",
        "SRCH-I5B-LIUHENG-POS-FENGTANG-001": "EVD-I5B-LIUHENG-POS-FENGTANG-WEISHANG-001",
        "SRCH-I5B-LIUHENG-POS-JIAYI-001": "EVD-I5B-LIUHENG-POS-JIAYI-TALENT-001",
        "SRCH-I5B-LIUHENG-NEG-JIAYI-001": "EVD-I5B-LIUHENG-NEG-JIAYI-SHUYUAN-001",
    }
    for search_id, evidence_id in converted.items():
        row = review_rows[search_id]
        assert row["lead_status"] == "source_verified_evidence_created"
        assert evidence_id in row["linked_evidence_ids"]
        assert row["source_pack_ids"]
        assert row["next_action"] == "human_review_after_cluster"

    still_review = {
        "SRCH-I5B-YINGZHENG-NEG-ZHAOGAO-001",
        "SRCH-I5B-YINGZHENG-CUT-ADJACENT-001",
        "SRCH-I5B-LIUHENG-POS-OLDMINISTERS-001",
        "SRCH-I5B-LIUHENG-NEG-DENGTONG-001",
        "SRCH-I5B-LIUHENG-CUT-ADJACENT-001",
    }
    for search_id in still_review:
        row = review_rows[search_id]
        assert row["lead_status"] == "lead_needs_source_review"
        assert row["linked_source_ids"] == []
        assert row["linked_evidence_ids"] == []
        assert row["source_pack_ids"] == []


def test_batch_b1_canonical_rows_trace_to_source_pack_and_search_logs() -> None:
    source_pack_rows = read_jsonl(SOURCE_PACK_PATH)
    review_rows = rows_by_id(SOURCE_REVIEW_LOG_PATH, "search_id")
    search_logs = rows_by_id(ROOT / "data" / "search_logs.jsonl", "search_id")
    cards = rows_by_id(ROOT / "data" / "evidence_cards.jsonl", "evidence_id")
    clusters = rows_by_id(ROOT / "data" / "evidence_clusters.jsonl", "cluster_id")
    sources = rows_by_id(ROOT / "data" / "sources.jsonl", "source_id")
    query_profiles = rows_by_id(ROOT / "data" / "query_profiles.jsonl", "query_profile_id")

    assert {
        "QRY-I5B-YINGZHENG-20260628",
        "QRY-I5B-LIUHENG-20260628",
    }.issubset(query_profiles)
    assert {row["source_id"] for row in source_pack_rows}.issubset(sources)

    for source_pack in source_pack_rows:
        for evidence_id in source_pack["linked_evidence_ids"]:
            card = cards[evidence_id]
            assert card["source_id"] == source_pack["source_id"]
            assert card["source_locator"]
            assert card["quote_context"]
            assert card["context_summary"]
            assert card["adjudication_bridge"]
        for cluster_id in source_pack["linked_cluster_ids"]:
            cluster = clusters[cluster_id]
            assert set(source_pack["linked_evidence_ids"]).intersection(
                cluster["linked_evidence_ids"]
            )
        for search_id in source_pack["linked_search_ids"]:
            assert search_logs[search_id]["result_status"] == "evidence_found_card_created"
            assert review_rows[search_id]["lead_status"] == "source_verified_evidence_created"

    still_review = {
        "SRCH-I5B-YINGZHENG-NEG-ZHAOGAO-001",
        "SRCH-I5B-YINGZHENG-CUT-ADJACENT-001",
        "SRCH-I5B-LIUHENG-POS-OLDMINISTERS-001",
        "SRCH-I5B-LIUHENG-NEG-DENGTONG-001",
        "SRCH-I5B-LIUHENG-CUT-ADJACENT-001",
    }
    for search_id in still_review:
        assert search_logs[search_id]["result_status"] == "lead_needs_source_review"
        assert search_logs[search_id]["linked_evidence_id"] == ""


def test_batch_b1_keeps_high_risk_and_backfilled_negative_lanes_visible() -> None:
    review_rows = rows_by_id(SOURCE_REVIEW_LOG_PATH, "search_id")
    search_logs = rows_by_id(ROOT / "data" / "search_logs.jsonl", "search_id")
    query_profiles = rows_by_id(ROOT / "data" / "query_profiles.jsonl", "query_profile_id")

    dengtong = search_logs["SRCH-I5B-LIUHENG-NEG-DENGTONG-001"]
    assert dengtong["result_status"] == "lead_needs_source_review"
    assert dengtong["linked_evidence_id"] == ""
    assert "邓通" in dengtong["query_terms"]
    assert "近幸" in dengtong["query_terms"]
    assert "任人唯亲" in dengtong["query_terms"]
    assert "不建卡，不得入分" in dengtong["note"]
    assert review_rows["SRCH-I5B-LIUHENG-NEG-DENGTONG-001"]["lead_status"] == "lead_needs_source_review"

    liuheng_profile = query_profiles["QRY-I5B-LIUHENG-20260628"]
    assert "SRCH-I5B-LIUHENG-NEG-DENGTONG-001" in liuheng_profile["priority_search_ids"]
    assert any("邓通" in term and "近幸偏私" in term for term in liuheng_profile["negative_terms"])

    zhaogao = search_logs["SRCH-I5B-YINGZHENG-NEG-ZHAOGAO-001"]
    assert zhaogao["result_status"] == "lead_needs_source_review"
    assert "high-risk unresolved lead gate" in zhaogao["result_summary"]
    assert "high-risk unresolved lead gate" in review_rows["SRCH-I5B-YINGZHENG-NEG-ZHAOGAO-001"]["lead_decision"]
