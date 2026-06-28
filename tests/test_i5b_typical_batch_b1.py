from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = ROOT / "data" / "batches" / "i5b_typical_batch_b1_qin_han"
QUERY_SOURCE_SPEC_PATH = BATCH_DIR / "source_evidence_specs.jsonl"
SOURCE_PACK_PATH = BATCH_DIR / "source_pack.jsonl"
SOURCE_REVIEW_LOG_PATH = BATCH_DIR / "source_review_log.jsonl"

REQUIRED_LANES = {
    ("positive", "识人拔擢"),
    ("positive", "授权专任"),
    ("positive", "容谏反馈"),
    ("positive", "人才通道 / 异质人才整合"),
    ("positive", "团队结构 / 长期人才网络"),
    ("positive", "功臣安全 / 授权可信度正面"),
    ("negative", "任人唯亲 / 近幸偏私"),
    ("negative", "权奸 / 酷吏 / 宦官 / 近臣任用风险"),
    ("negative", "功臣安全受损"),
    ("negative", "谏臣 / 表达安全受损"),
    ("negative", "系统性清洗 / 人才生态破坏"),
    ("negative", "同一对象反转"),
    ("adjacent", "战功 / 统一收益"),
    ("adjacent", "制度后效 / 行政成果"),
    ("adjacent", "政权安全 / 继承政治"),
    ("adjacent", "刑罚残酷 / 政治品格"),
    ("adjacent", "思想控制 / 认知路线"),
}
LANE_COVERAGE_STATUSES = {
    "covered",
    "converted_to_card",
    "pending_review",
    "excluded_with_reason",
    "not_applicable_with_reason",
}
ANCHOR_COVERAGE_STATUSES = {
    "anchor_recorded",
    "anchor_missing_with_reason",
    "archive_anchor_only",
    "promoted_to_shared_anchor",
}
ANCHOR_METADATA_FIELDS = {
    "object_name",
    "object_type",
    "object_level",
    "anchor_role",
    "usable_for",
    "cross_item_risks",
    "consensus_level",
    "anchor_status",
    "source_or_review_ref",
}


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def rows_by_id(path: Path, key: str) -> dict[str, dict[str, object]]:
    return {str(row[key]): row for row in read_jsonl(path)}


def assert_lane_report(report: list[dict[str, object]]) -> None:
    assert {(row["lane_group"], row["lane_name"]) for row in report} == REQUIRED_LANES
    for row in report:
        assert row["coverage_status"] in LANE_COVERAGE_STATUSES
        assert isinstance(row["search_ids"], list)
        assert isinstance(row["linked_evidence_ids"], list)
        assert isinstance(row["source_or_review_refs"], list)
        assert row["reason"]
        if row["coverage_status"] == "converted_to_card":
            assert row["linked_evidence_ids"]


def assert_anchor_metadata(metadata: dict[str, object]) -> None:
    assert ANCHOR_METADATA_FIELDS.issubset(metadata)
    assert metadata["object_name"]
    assert metadata["object_type"]
    assert metadata["object_level"]
    assert metadata["anchor_role"]
    assert isinstance(metadata["usable_for"], list)
    assert metadata["usable_for"]
    assert isinstance(metadata["cross_item_risks"], list)
    assert metadata["consensus_level"]
    assert metadata["anchor_status"]
    assert metadata["source_or_review_ref"]


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


def test_batch_b1_lane_reports_cover_positive_negative_and_adjacent_lanes() -> None:
    spec_rows = read_jsonl(QUERY_SOURCE_SPEC_PATH)

    for row in spec_rows:
        assert row["object_anchor_policy"]["object_anchor_use"] == "grading_auxiliary_not_auto_score"
        assert row["object_anchor_policy"]["person_specific_override"] == "none"
        assert row["object_anchor_policy"]["scoring_rule_change"] == "none"
        assert row["object_anchor_policy"]["batch_b1_historical_extreme_status"] == "not_promoted_by_this_batch"
        assert "at_least_3_strong_direct_i5b_top_object" in row["object_anchor_policy"][
            "single_core_extreme_positive_gate"
        ]
        assert_lane_report(row["lane_coverage_report"])
        assert_lane_report(row["query_profile"]["lane_coverage_report"])
        assert row["query_profile"]["object_anchor_policy"] == row["object_anchor_policy"]

        summary = row["lane_coverage_summary"]
        assert set(summary) == {"adjacent", "negative", "positive"}
        assert sum(summary["positive"].values()) == 6
        assert sum(summary["negative"].values()) == 6
        assert sum(summary["adjacent"].values()) == 5


def test_batch_b1_review_log_records_lane_and_object_anchor_metadata() -> None:
    review_rows = read_jsonl(SOURCE_REVIEW_LOG_PATH)

    for row in review_rows:
        assert row["lane_group"] in {"positive", "negative", "adjacent"}
        assert row["lane_name"]
        assert row["lane_coverage_status"] in LANE_COVERAGE_STATUSES
        assert row["covered_lane_ids"]
        assert row["anchor_coverage_status"] in ANCHOR_COVERAGE_STATUSES
        assert row["anchor_coverage_status"] == "anchor_recorded"

        metadata = row["object_anchor_metadata"]
        assert_anchor_metadata(metadata)
        assert metadata["source_or_review_ref"] == row["review_id"]

        if row["lead_status"] == "source_verified_evidence_created":
            assert row["lane_coverage_status"] == "converted_to_card"
            assert row["linked_evidence_ids"]
        else:
            assert row["lane_coverage_status"] == "pending_review"
            assert row["linked_source_ids"] == []
            assert row["linked_evidence_ids"] == []


def test_batch_b1_anchor_reports_cover_converted_cards_and_unresolved_leads() -> None:
    spec_rows = read_jsonl(QUERY_SOURCE_SPEC_PATH)
    review_rows_by_person = {
        person: [
            row for row in read_jsonl(SOURCE_REVIEW_LOG_PATH) if row["person"] == person
        ]
        for person in {"嬴政", "刘恒"}
    }

    for spec in spec_rows:
        person = spec["person"]
        expected_review_rows = {
            row["search_id"]: row for row in review_rows_by_person[person]
        }
        anchors = spec["anchor_coverage_report"]
        assert {anchor["search_id"] for anchor in anchors} == set(expected_review_rows)
        assert spec["anchor_coverage_summary"]["status_counts"] == {
            "anchor_recorded": len(expected_review_rows)
        }
        assert spec["anchor_coverage_summary"]["converted_card_count"] == sum(
            1 for row in expected_review_rows.values() if row["linked_evidence_ids"]
        )
        assert spec["anchor_coverage_summary"]["unresolved_lead_count"] == sum(
            1 for row in expected_review_rows.values() if not row["linked_evidence_ids"]
        )

        for anchor in anchors:
            review_row = expected_review_rows[anchor["search_id"]]
            assert anchor["review_id"] == review_row["review_id"]
            assert anchor["linked_evidence_ids"] == review_row["linked_evidence_ids"]
            assert anchor["anchor_coverage_status"] == "anchor_recorded"
            assert_anchor_metadata(anchor["object_anchor_metadata"])

        card_anchors = {
            card["evidence_id"]: card["object_anchor_metadata"]
            for card in spec["evidence_card_specs"]
        }
        converted_evidence_ids = {
            evidence_id
            for review_row in expected_review_rows.values()
            for evidence_id in review_row["linked_evidence_ids"]
        }
        assert set(card_anchors) == converted_evidence_ids
        for metadata in card_anchors.values():
            assert_anchor_metadata(metadata)


def test_batch_b1_query_profiles_and_search_logs_persist_lane_anchor_metadata() -> None:
    query_profiles = rows_by_id(ROOT / "data" / "query_profiles.jsonl", "query_profile_id")
    search_logs = rows_by_id(ROOT / "data" / "search_logs.jsonl", "search_id")

    for query_profile_id in {
        "QRY-I5B-YINGZHENG-20260628",
        "QRY-I5B-LIUHENG-20260628",
    }:
        profile = query_profiles[query_profile_id]
        assert_lane_report(profile["lane_coverage_report"])
        assert profile["object_anchor_policy"]["object_anchor_use"] == "grading_auxiliary_not_auto_score"
        assert profile["object_anchor_policy"]["person_specific_override"] == "none"
        assert profile["object_anchor_policy"]["scoring_rule_change"] == "none"
        assert profile["anchor_coverage_summary"]["status_counts"] == {
            "anchor_recorded": len(profile["priority_search_ids"])
        }

        for search_id in profile["priority_search_ids"]:
            search_log = search_logs[search_id]
            assert search_log["lane_coverage_status"] in LANE_COVERAGE_STATUSES
            assert search_log["anchor_coverage_status"] == "anchor_recorded"
            assert search_log["covered_lane_ids"]
            assert_anchor_metadata(search_log["object_anchor_metadata"])


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
    assert dengtong["lane_coverage_status"] == "pending_review"
    assert dengtong["object_anchor_metadata"]["object_name"] == "邓通近幸偏私风险"
    assert "任人唯亲 / 近幸偏私" in dengtong["object_anchor_metadata"]["usable_for"]

    liuheng_profile = query_profiles["QRY-I5B-LIUHENG-20260628"]
    assert "SRCH-I5B-LIUHENG-NEG-DENGTONG-001" in liuheng_profile["priority_search_ids"]
    assert any("邓通" in term and "近幸偏私" in term for term in liuheng_profile["negative_terms"])

    zhaogao = search_logs["SRCH-I5B-YINGZHENG-NEG-ZHAOGAO-001"]
    assert zhaogao["result_status"] == "lead_needs_source_review"
    assert "high-risk unresolved lead gate" in zhaogao["result_summary"]
    assert "high-risk unresolved lead gate" in review_rows["SRCH-I5B-YINGZHENG-NEG-ZHAOGAO-001"]["lead_decision"]
    assert zhaogao["lane_coverage_status"] == "pending_review"
    assert zhaogao["object_anchor_metadata"]["anchor_status"] == "unresolved_lead_gate_not_scoring"
    assert zhaogao["object_anchor_metadata"]["anchor_role"] == "negative_gate"
