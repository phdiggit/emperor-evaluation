from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
QUERY_PROFILES_PATH = ROOT / "data" / "query_profiles.jsonl"
SEARCH_LOGS_PATH = ROOT / "data" / "search_logs.jsonl"
SOURCES_PATH = ROOT / "data" / "sources.jsonl"
EVIDENCE_CARDS_PATH = ROOT / "data" / "evidence_cards.jsonl"
EVIDENCE_CLUSTERS_PATH = ROOT / "data" / "evidence_clusters.jsonl"
REVIEW_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B" / "机器审计" / "证据链" / "证据卡" / "第五项B扩展试点第一批证据卡与证据簇草案.md"
CLUSTER_ADJUDICATION_BATCH_PATH = (
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "adjudication_cluster.jsonl"
)
CLUSTER_ADJUDICATION_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B" / "机器审计" / "证据链" / "证据簇" / "第五项B扩展试点第一批证据簇结算草案.md"

EXPANDED_SOURCE_IDS = {
    "SRC-QSL-YZ-J1-001",
    "SRC-SYNL-YZ-J30-001",
    "SRC-SYNL-YZ-J89-001",
    "SRC-MTZL-J008-001",
    "SRC-MTZL-J024-001",
    "SRC-MS-J308-001",
    "SRC-MS-J132-001",
    "SRC-SJ-J8-GAOZU-SANJIE-001",
    "SRC-SJ-J55-ZHANGLIANG-LIUBANG-POS-001",
    "SRC-SJ-J56-CHENPING-LIUBANG-POS-001",
    "SRC-SJ-J8-HANXIN-QIWANG-LIUBANG-POS-001",
    "SRC-SJ-J92-HANXIN-LIUBANG-NEG-001",
    "SRC-SJ-J90-PENGYUE-LIUBANG-NEG-001",
    "SRC-SJ-J91-YINGBU-LIUBANG-NEG-001",
    "SRC-SJ-J53-XIAOHE-SAFETY-LIUBANG-SUPP-001",
    "SRC-SJ-J56-CHENPING-CONTINUITY-LIUBANG-SUPP-001",
    "SRC-SJ-J56-FANKUAI-SAFETY-LIUBANG-SUPP-001",
}
EXPANDED_QUERY_PROFILE_IDS = (
    "QRY-I5B-LIUBANG-20260619",
    "QRY-I5B-YONGZHENG-20260619",
    "QRY-I5B-ZHUYUANZHANG-20260619",
)
EXPANDED_EVIDENCE_IDS = {
    "EVD-I5B-LIUBANG-POS-SANJIE-001",
    "EVD-I5B-LIUBANG-POS-ZHANGLIANG-RONGJIAN-001",
    "EVD-I5B-LIUBANG-POS-CHENPING-001",
    "EVD-I5B-LIUBANG-POS-HANXIN-QIWANG-001",
    "EVD-I5B-LIUBANG-NEG-HANXIN-001",
    "EVD-I5B-LIUBANG-NEG-PENGYUE-001",
    "EVD-I5B-LIUBANG-NEG-YINGBU-CHILL-001",
    "EVD-I5B-LIUBANG-SUPP-XIAOHE-SAFETY-001",
    "EVD-I5B-LIUBANG-SUPP-CHENPING-CONTINUITY-001",
    "EVD-I5B-LIUBANG-SUPP-FANKUAI-SAFETY-001",
    "EVD-I5B-YONGZHENG-POS-SHIREN-001",
    "EVD-I5B-YONGZHENG-POS-RONGJIAN-001",
    "EVD-I5B-YONGZHENG-NEG-YIJI-001",
    "EVD-I5B-YONGZHENG-NEG-YISHIXINGTAI-001",
    "EVD-I5B-ZHUYUANZHANG-POS-SHIREN-001",
    "EVD-I5B-ZHUYUANZHANG-POS-SHOUQUAN-001",
    "EVD-I5B-ZHUYUANZHANG-NEG-HULAN-001",
    "EVD-I5B-ZHUYUANZHANG-NEG-LANYU-001",
}
EXPANDED_SEARCH_IDS = (
    "SRCH-I5B-LIUBANG-POS-SHIREN-001",
    "SRCH-I5B-LIUBANG-POS-SHOUQUAN-001",
    "SRCH-I5B-LIUBANG-NEG-GONGCHEN-001",
    "SRCH-I5B-LIUBANG-CUT-ADJACENT-001",
    "SRCH-I5B-YONGZHENG-POS-SHOUQUAN-001",
    "SRCH-I5B-YONGZHENG-POS-ZHIDU-001",
    "SRCH-I5B-YONGZHENG-NEG-BIAODA-ANQUAN-001",
    "SRCH-I5B-YONGZHENG-CUT-ADJACENT-001",
    "SRCH-I5B-ZHUYUANZHANG-POS-SHIREN-001",
    "SRCH-I5B-ZHUYUANZHANG-POS-SHOUQUAN-001",
    "SRCH-I5B-ZHUYUANZHANG-NEG-HULAN-001",
    "SRCH-I5B-ZHUYUANZHANG-CUT-ADJACENT-001",
)
YONGZHENG_20260619_SEARCH_IDS = {
    "SRCH-I5B-YONGZHENG-POS-SHOUQUAN-001",
    "SRCH-I5B-YONGZHENG-POS-ZHIDU-001",
    "SRCH-I5B-YONGZHENG-NEG-BIAODA-ANQUAN-001",
    "SRCH-I5B-YONGZHENG-CUT-ADJACENT-001",
}


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows


def rows_by_ids(path: Path, id_field: str, row_ids: tuple[str, ...]) -> list[dict[str, object]]:
    index = {row.get(id_field): row for row in load_jsonl(path)}
    return [index[row_id] for row_id in row_ids if row_id in index]


def test_expanded_pilot_batch1_query_profiles_are_three_person_intake_only() -> None:
    rows = rows_by_ids(QUERY_PROFILES_PATH, "query_profile_id", EXPANDED_QUERY_PROFILE_IDS)

    assert len(rows) == 3
    assert {row["person"] for row in rows} == {"刘邦", "雍正", "朱元璋"}
    assert {row["status"] for row in rows} == {"batch_pending_merge"}
    for row in rows:
        assert row["profile_scope"] == "person_level"
        assert row["profile_role"] == "person_level_query_profile"
        assert row["subitem"] == "第五项B"
        assert "score" not in row
        assert "rank" not in row

def test_expanded_pilot_batch1_search_logs_are_three_person_intake_only() -> None:
    rows = rows_by_ids(SEARCH_LOGS_PATH, "search_id", EXPANDED_SEARCH_IDS)

    assert len(rows) == 12
    assert {row["person"] for row in rows} == {"刘邦", "雍正", "朱元璋"}
    for row in rows:
        assert row["subitem"] == "第五项B"
        assert "score" not in row
        assert "rank" not in row

    newly_absorbed = [row for row in rows if row["search_id"] in YONGZHENG_20260619_SEARCH_IDS]
    assert len(newly_absorbed) == 4
    assert {row["query_profile_id"] for row in newly_absorbed} == {"QRY-I5B-YONGZHENG-20260619"}
    assert {row["status"] for row in newly_absorbed} == {"lead_needs_source_review"}
    for row in newly_absorbed:
        assert row["linked_source_ids"] == []
        assert row["linked_evidence_ids"] == []


def test_expanded_pilot_batch1_sources_are_the_three_person_intake_only() -> None:
    rows = [row for row in load_jsonl(SOURCES_PATH) if row.get("source_id") in EXPANDED_SOURCE_IDS]

    assert len(rows) == 17
    assert {row["source_id"] for row in rows} == EXPANDED_SOURCE_IDS


def test_expanded_pilot_batch1_evidence_cards_are_source_backed() -> None:
    rows = [
        row
        for row in load_jsonl(EVIDENCE_CARDS_PATH)
        if row.get("evidence_id") in EXPANDED_EVIDENCE_IDS
    ]

    assert len(rows) == 18
    assert {row["person"] for row in rows} == {"刘邦", "雍正", "朱元璋"}

    counts = Counter((row["person"], row["polarity"]) for row in rows)
    assert counts[("刘邦", "positive")] == 5
    assert counts[("刘邦", "negative")] == 5
    assert counts[("雍正", "positive")] == 2
    assert counts[("雍正", "negative")] == 2
    assert counts[("朱元璋", "positive")] == 2
    assert counts[("朱元璋", "negative")] == 2

    assert {row["cluster_candidate_id"] for row in rows} == {
        "ADJ-I5B-LIUBANG-POS-TALENT-AUTHORIZATION-001",
        "ADJ-I5B-LIUBANG-NEG-MERIT-SUBJECT-SAFETY-001",
        "ADJ-I5B-YONGZHENG-POS-TALENT-FEEDBACK-001",
        "ADJ-I5B-YONGZHENG-NEG-TRUST-ECOSYSTEM-001",
        "ADJ-I5B-ZHUYUANZHANG-POS-TALENT-AUTHORIZATION-001",
        "ADJ-I5B-ZHUYUANZHANG-NEG-MERIT-PURGE-001",
    }
    for row in rows:
        assert row["subitem"] == "第五项B"
        assert row["verification_status"] == "source_verified"
        assert row["object_anchor"]
        assert row["evidence_role"]
        assert row["cluster_candidate_id"]
        assert row["mitigation_flag"]
        assert row["upper_bound_flag"]
        assert row["cluster_role"]
        assert "score" not in row
        assert "rank" not in row


def test_expanded_pilot_batch1_clusters_are_draft_review_rows() -> None:
    rows = [
        row
        for row in load_jsonl(EVIDENCE_CLUSTERS_PATH)
        if row.get("subitem") == "第五项B" and row.get("person") in {"刘邦", "雍正", "朱元璋"}
    ]

    assert len(rows) == 6
    assert {row["person"] for row in rows} == {"刘邦", "雍正", "朱元璋"}
    counts = Counter(row["person"] for row in rows)
    assert counts["刘邦"] == 2
    assert counts["雍正"] == 2
    assert counts["朱元璋"] == 2
    assert {row["status"] for row in rows} == {"batch_draft"}
    for row in rows:
        assert row["subitem"] == "第五项B"
        assert row["candidate_strength"] in {2, 3}
        assert row["adjudication_status"] == "source_verified_pending_human_adjudication"


@pytest.mark.export_full
@pytest.mark.integration
def test_expanded_pilot_batch1_review_export_contains_cards_and_clusters() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export" / "export_md.py"), "--profile", "i5b-expanded-batch1"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert REVIEW_EXPORT_PATH.exists()
    content = REVIEW_EXPORT_PATH.read_text(encoding="utf-8")
    assert "# 第五项B扩展试点第一批证据卡与证据簇草案" in content
    for needle in [
        "EVD-I5B-LIUBANG-POS-SANJIE-001",
        "EVD-I5B-LIUBANG-NEG-YINGBU-CHILL-001",
        "ADJ-I5B-LIUBANG-POS-TALENT-AUTHORIZATION-001",
        "ADJ-I5B-LIUBANG-NEG-MERIT-SUBJECT-SAFETY-001",
        "三杰分工与吾能用之",
        "功臣安全与授权预期",
        "EVD-I5B-YONGZHENG-POS-SHIREN-001",
        "EVD-I5B-ZHUYUANZHANG-NEG-HULAN-001",
        "簇候选ID",
        "批次草案",
    ]:
        assert needle in content


def test_expanded_pilot_batch1_cluster_adjudication_rows_are_three_person_drafts() -> None:
    rows = load_jsonl(CLUSTER_ADJUDICATION_BATCH_PATH)

    assert len(rows) == 3
    assert {row["person"] for row in rows} == {"刘邦", "雍正", "朱元璋"}
    assert {row["status"] for row in rows} == {"cluster_adjudication_draft"}

    for row in rows:
        assert row["item"] == "第五项"
        assert row["subitem"] == "第五项B"
        assert row["positive_cluster_ids"]
        assert row["negative_cluster_ids"]
        assert row["positive_core_summary"]
        assert row["negative_core_summary"]
        assert row["adjacent_item_split_summary"]
        assert row["negative_intercept_status"]
        assert row["adjacent_item_split_status"]
        assert row["rule_pressure_summary"]
        assert row["net_adjudication_draft"]
        assert row["supplement_gap_list"]
        assert "score" not in row
        assert "rank" not in row
        assert "final_grade" not in row
        assert "final_score" not in row
        assert "leaderboard" not in row
        assert "total_ranking" not in row


@pytest.mark.export_full
@pytest.mark.integration
def test_expanded_pilot_batch1_cluster_adjudication_export_is_review_only() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export" / "export_md.py"), "--profile", "i5b-expanded-batch1"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert CLUSTER_ADJUDICATION_EXPORT_PATH.exists()
    content = CLUSTER_ADJUDICATION_EXPORT_PATH.read_text(encoding="utf-8")
    assert "# 第五项B扩展试点第一批证据簇结算草案" in content
    for needle in [
        "刘邦",
        "雍正",
        "朱元璋",
        "负证拦截",
        "相邻项剥离",
        "补证缺口",
        "只作草案，不输出终局结果",
    ]:
        assert needle in content
    for forbidden in ["正式定档", "正式出分", "排名", "总榜", "leaderboard", "total_ranking", "final_score", "final_grade"]:
        assert forbidden not in content
