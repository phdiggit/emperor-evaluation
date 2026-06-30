from __future__ import annotations

# Lifecycle: transitional absorption test for #379.
# Retire or fold into the generic canonical-store contract after I5B
# source/evidence stores are stable and legacy batches are absorbed; do not
# clone this pattern into one validator/test per batch or per person.

import json
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BATCH_DIR = DATA / "batches" / "i5b_typical_batch_b1_qin_han"
BATCH_ID = "i5b_typical_batch_b1_qin_han_20260628"

B1_SOURCE_PACK_IDS = {
    "SP-I5B-B1-YINGZHENG-LISI-001",
    "SP-I5B-B1-YINGZHENG-WANGJIAN-001",
    "SP-I5B-B1-YINGZHENG-FENSHU-001",
    "SP-I5B-B1-LIUHENG-ZHANGSHIZHI-001",
    "SP-I5B-B1-LIUHENG-FENGTANG-001",
    "SP-I5B-B1-LIUHENG-JIAYI-001",
}
B1_SEARCH_IDS = {
    "SRCH-I5B-YINGZHENG-POS-LISI-001",
    "SRCH-I5B-YINGZHENG-POS-WANGJIAN-001",
    "SRCH-I5B-YINGZHENG-NEG-FENSHU-001",
    "SRCH-I5B-YINGZHENG-NEG-ZHAOGAO-001",
    "SRCH-I5B-YINGZHENG-CUT-ADJACENT-001",
    "SRCH-I5B-LIUHENG-POS-ZHANGSHIZHI-001",
    "SRCH-I5B-LIUHENG-POS-FENGTANG-001",
    "SRCH-I5B-LIUHENG-POS-JIAYI-001",
    "SRCH-I5B-LIUHENG-NEG-JIAYI-001",
    "SRCH-I5B-LIUHENG-POS-OLDMINISTERS-001",
    "SRCH-I5B-LIUHENG-NEG-DENGTONG-001",
    "SRCH-I5B-LIUHENG-CUT-ADJACENT-001",
}
B1_PROCESSING_SEARCH_IDS = {
    "SRCH-I5B-YINGZHENG-CUT-ADJACENT-001",
    "SRCH-I5B-LIUHENG-CUT-ADJACENT-001",
}
B1_ANCHOR_IDS = {
    search_id.replace("SRCH-I5B-", "ANCH-I5B-B1-")
    for search_id in B1_SEARCH_IDS - B1_PROCESSING_SEARCH_IDS
}
B1_ANCHOR_COVERAGE_IDS = {search_id.replace("SRCH-I5B-", "ANCOV-I5B-B1-") for search_id in B1_SEARCH_IDS}
B1_LANE_COVERAGE_IDS = {search_id.replace("SRCH-I5B-", "LCOV-I5B-B1-") for search_id in B1_SEARCH_IDS}


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def rows_by_id(path: Path, key: str) -> dict[str, dict[str, object]]:
    return {str(row[key]): row for row in read_jsonl(path)}


def test_batch_b1_folder_is_traceability_manifest_only() -> None:
    assert (BATCH_DIR / "manifest.yml").exists()
    assert not (BATCH_DIR / "source_evidence_specs.jsonl").exists()
    assert not (BATCH_DIR / "source_pack.jsonl").exists()
    assert not (BATCH_DIR / "source_review_log.jsonl").exists()


def test_batch_b1_manifest_points_to_canonical_stores() -> None:
    manifest = yaml.safe_load((BATCH_DIR / "manifest.yml").read_text(encoding="utf-8"))

    assert manifest["lifecycle_status"] == "absorbed_to_canonical"
    assert manifest["persistent_research_data"] == {
        "source_packs": "data/source_packs.jsonl",
        "query_lane_coverage": "data/query_lane_coverage.jsonl",
        "object_anchor_coverage": "data/object_anchor_coverage.jsonl",
        "anchors": "data/anchors.jsonl",
        "batch_traceability_manifest": "data/batches/i5b_typical_batch_b1_qin_han/manifest.yml",
    }
    refs = manifest["canonical_row_refs"]
    assert set(refs["source_pack_ids"]) == B1_SOURCE_PACK_IDS
    assert set(refs["search_ids"]) == B1_SEARCH_IDS
    assert set(refs["anchor_ids"]) == B1_ANCHOR_IDS
    assert set(refs["anchor_coverage_ids"]) == B1_ANCHOR_COVERAGE_IDS
    assert set(refs["lane_coverage_ids"]) == B1_LANE_COVERAGE_IDS
    assert set(refs["query_profile_ids"]) == {
        "QRY-I5B-YINGZHENG-20260628",
        "QRY-I5B-LIUHENG-20260628",
    }


def test_batch_b1_source_packs_live_in_canonical_store() -> None:
    source_packs = rows_by_id(DATA / "source_packs.jsonl", "source_pack_id")
    sources = rows_by_id(DATA / "sources.jsonl", "source_id")
    search_logs = rows_by_id(DATA / "search_logs.jsonl", "search_id")
    cards = rows_by_id(DATA / "evidence_cards.jsonl", "evidence_id")
    clusters = rows_by_id(DATA / "evidence_clusters.jsonl", "cluster_id")

    b1_rows = [source_packs[row_id] for row_id in B1_SOURCE_PACK_IDS]
    assert {row["batch_id"] for row in b1_rows} == {BATCH_ID}
    assert Counter(row["person"] for row in b1_rows) == {"嬴政": 3, "刘恒": 3}

    for row in b1_rows:
        assert row["source_batch"] == "data/source_packs.jsonl"
        assert row["schema_version"] == "1.0"
        assert row["source_id"] in sources
        assert row["source_locator"]
        assert row["source_url"]
        assert row["excerpt_short"]
        assert row["excerpt_context"]
        assert row["context_summary"]
        assert row["context_scope"]
        assert row["adjacent_item_split"]
        for search_id in row["linked_search_ids"]:
            assert search_id in search_logs
        for evidence_id in row["linked_evidence_ids"]:
            assert evidence_id in cards
        for cluster_id in row["linked_cluster_ids"]:
            assert cluster_id in clusters


def test_batch_b1_lane_coverage_lives_in_canonical_store() -> None:
    lanes = rows_by_id(DATA / "query_lane_coverage.jsonl", "lane_coverage_id")
    search_logs = rows_by_id(DATA / "search_logs.jsonl", "search_id")

    b1_rows = [lanes[row_id] for row_id in B1_LANE_COVERAGE_IDS]
    assert {row["batch_id"] for row in b1_rows} == {BATCH_ID}
    assert Counter(row["lane_group"] for row in b1_rows) == {
        "positive": 6,
        "negative": 4,
        "adjacent": 2,
    }
    assert Counter(row["coverage_status"] for row in b1_rows) == {
        "converted_to_card": 7,
        "pending_review": 5,
    }

    for row in b1_rows:
        assert row["source_batch"] == "data/query_lane_coverage.jsonl"
        assert row["query_profile_id"] in {
            "QRY-I5B-YINGZHENG-20260628",
            "QRY-I5B-LIUHENG-20260628",
        }
        assert row["query_terms"]
        assert row["covered_lane_ids"]
        assert len(row["search_ids"]) == 1
        assert row["search_ids"][0] in B1_SEARCH_IDS
        assert search_logs[row["search_ids"][0]]["source_batch"] == "data/query_lane_coverage.jsonl"
        assert set(row["anchor_coverage_ids"]).issubset(B1_ANCHOR_COVERAGE_IDS)
        if row["coverage_status"] == "converted_to_card":
            assert row["linked_evidence_ids"]
            assert row["source_pack_ids"]
            assert row["unresolved_reason"] == ""
        else:
            assert row["linked_evidence_ids"] == []
            assert row["source_pack_ids"] == []
            assert row["unresolved_reason"]


def test_batch_b1_object_anchor_coverage_lives_in_canonical_store() -> None:
    coverage = rows_by_id(DATA / "object_anchor_coverage.jsonl", "anchor_coverage_id")
    anchors = rows_by_id(DATA / "anchors.jsonl", "anchor_id")

    b1_rows = [coverage[row_id] for row_id in B1_ANCHOR_COVERAGE_IDS]
    assert {row["batch_id"] for row in b1_rows} == {BATCH_ID}

    for row in b1_rows:
        assert row["source_batch"] == "data/object_anchor_coverage.jsonl"
        assert row["linked_review_id"].startswith("REV-I5B-")
        assert row["linked_search_id"] in B1_SEARCH_IDS
        if row["linked_search_id"] in B1_PROCESSING_SEARCH_IDS:
            assert row["anchor_ids"] == []
            assert row["processing_outcome"] == "adjacent_only"
            assert row["no_anchor_reason"]
        else:
            assert len(row["anchor_ids"]) == 1
            assert row["anchor_ids"][0] in B1_ANCHOR_IDS
            assert row["anchor_ids"][0] in anchors
            assert row["no_anchor_reason"] == ""
        if row["review_status"] == "source_verified_evidence_created":
            assert row["linked_evidence_ids"]
            assert row["linked_source_pack_ids"]
        else:
            assert row["linked_evidence_ids"] == []
            assert row["linked_source_pack_ids"] == []


def test_batch_b1_anchors_keep_minimal_metadata_without_scoring() -> None:
    anchors = rows_by_id(DATA / "anchors.jsonl", "anchor_id")

    for anchor_id in B1_ANCHOR_IDS:
        row = anchors[anchor_id]
        assert row["anchor_type"] == "object"
        assert row["anchor_scope"] == "i5b_b1_qin_han_review_anchor"
        assert row["source_batch"] == "data/anchors.jsonl"
        assert row["object_name"]
        assert row["object_type"]
        assert row["object_level"]
        assert row["anchor_role"]
        assert row["usable_for"]
        assert row["cross_item_risks"]
        assert row["consensus_level"]
        assert row["anchor_status"]
        assert row["source_or_review_ref"] == row["linked_review_id"]
        assert "automatic scoring rule" in row["note"]


def test_batch_b1_medium_negative_clusters_explain_candidate_strength_floor() -> None:
    clusters = rows_by_id(DATA / "evidence_clusters.jsonl", "cluster_id")

    for cluster_id in {
        "ADJ-I5B-YINGZHENG-NEG-EXPRESSION-SAFETY-001",
        "ADJ-I5B-LIUHENG-NEG-JIAYI-TALENT-CHANNEL-001",
    }:
        cluster = clusters[cluster_id]
        assert cluster["polarity"] == "negative"
        assert cluster["candidate_strength"] == 3
        assert len(cluster["linked_evidence_ids"]) == 1
        rationale = cluster["candidate_strength_rationale"]
        assert "candidate_strength>=3" in rationale
        assert "single-card source-verified cluster" in rationale
        assert "medium negative" in rationale


def test_batch_b1_keeps_dengtong_and_zhaogao_unresolved_gates() -> None:
    lanes = rows_by_id(DATA / "query_lane_coverage.jsonl", "lane_coverage_id")
    coverage = rows_by_id(DATA / "object_anchor_coverage.jsonl", "anchor_coverage_id")
    anchors = rows_by_id(DATA / "anchors.jsonl", "anchor_id")
    search_logs = rows_by_id(DATA / "search_logs.jsonl", "search_id")

    dengtong_lane = lanes["LCOV-I5B-B1-LIUHENG-NEG-DENGTONG-001"]
    assert dengtong_lane["coverage_status"] == "pending_review"
    assert dengtong_lane["linked_evidence_ids"] == []
    assert search_logs["SRCH-I5B-LIUHENG-NEG-DENGTONG-001"]["result_status"] == "lead_needs_source_review"
    assert coverage["ANCOV-I5B-B1-LIUHENG-NEG-DENGTONG-001"]["anchor_ids"] == [
        "ANCH-I5B-B1-LIUHENG-NEG-DENGTONG-001"
    ]
    assert anchors["ANCH-I5B-B1-LIUHENG-NEG-DENGTONG-001"]["anchor_status"] == "unresolved_lead_gate_not_scoring"

    zhaogao_lane = lanes["LCOV-I5B-B1-YINGZHENG-NEG-ZHAOGAO-001"]
    assert zhaogao_lane["coverage_status"] == "pending_review"
    assert zhaogao_lane["linked_evidence_ids"] == []
    zhaogao_search = search_logs["SRCH-I5B-YINGZHENG-NEG-ZHAOGAO-001"]
    assert zhaogao_search["result_status"] == "lead_needs_source_review"
    assert "high-risk unresolved lead gate" in zhaogao_search["result_summary"]
    zhaogao_anchor = anchors["ANCH-I5B-B1-YINGZHENG-NEG-ZHAOGAO-001"]
    assert zhaogao_anchor["anchor_status"] == "unresolved_lead_gate_not_scoring"
    assert zhaogao_anchor["anchor_role"] == "negative_gate"
