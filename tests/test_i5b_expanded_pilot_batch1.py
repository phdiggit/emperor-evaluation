from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUERY_PROFILE_BATCH_PATH = ROOT / "data" / "query_profile_batches" / "i5b_expanded_pilot_batch1_20260619.jsonl"
SEARCH_LOG_BATCH_PATH = ROOT / "data" / "search_log_batches" / "i5b_expanded_pilot_batch1_20260619.jsonl"
SOURCE_BATCH_PATH = ROOT / "data" / "source_batches" / "i5b_expanded_pilot_batch1_20260619.jsonl"
EVIDENCE_BATCH_PATH = ROOT / "data" / "evidence_card_batches" / "i5b_expanded_pilot_batch1_20260619.jsonl"
CLUSTER_BATCH_PATH = ROOT / "data" / "evidence_cluster_batches" / "i5b_expanded_pilot_batch1_20260619.jsonl"
REVIEW_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B扩展试点第一批证据卡与证据簇草案.md"


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows


def test_expanded_pilot_batch1_query_profiles_are_three_person_intake_only() -> None:
    rows = load_jsonl(QUERY_PROFILE_BATCH_PATH)

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
    rows = load_jsonl(SEARCH_LOG_BATCH_PATH)

    assert len(rows) == 12
    assert {row["person"] for row in rows} == {"刘邦", "雍正", "朱元璋"}
    assert {row["status"] for row in rows} == {"lead_needs_source_review"}
    for row in rows:
        assert row["subitem"] == "第五项B"
        assert row["linked_source_ids"] == []
        assert row["linked_evidence_ids"] == []
        assert "score" not in row
        assert "rank" not in row


def test_expanded_pilot_batch1_sources_are_the_new_persons_only() -> None:
    rows = load_jsonl(SOURCE_BATCH_PATH)

    assert len(rows) == 7
    assert {row["source_id"] for row in rows} == {
        "SRC-QSL-YZ-J1-001",
        "SRC-SYNL-YZ-J30-001",
        "SRC-SYNL-YZ-J89-001",
        "SRC-MTZL-J008-001",
        "SRC-MTZL-J024-001",
        "SRC-MS-J308-001",
        "SRC-MS-J132-001",
    }


def test_expanded_pilot_batch1_evidence_cards_are_source_backed() -> None:
    rows = load_jsonl(EVIDENCE_BATCH_PATH)

    assert len(rows) == 8
    assert {row["person"] for row in rows} == {"雍正", "朱元璋"}
    assert {row["cluster_candidate_id"] for row in rows} == {
        "ADJ-I5B-YONGZHENG-POS-TALENT-FEEDBACK-001",
        "ADJ-I5B-YONGZHENG-NEG-TRUST-ECOSYSTEM-001",
        "ADJ-I5B-ZHUYUANZHANG-POS-TALENT-AUTHORIZATION-001",
        "ADJ-I5B-ZHUYUANZHANG-NEG-MERIT-PURGE-001",
    }
    for row in rows:
        assert row["subitem"] == "第五项B"
        assert row["verification_status"] == "source_verified"
        assert row["cluster_candidate_id"]
        assert "score" not in row
        assert "rank" not in row


def test_expanded_pilot_batch1_clusters_are_draft_review_rows() -> None:
    rows = load_jsonl(CLUSTER_BATCH_PATH)

    assert len(rows) == 4
    assert {row["person"] for row in rows} == {"雍正", "朱元璋"}
    assert {row["status"] for row in rows} == {"batch_draft"}
    for row in rows:
        assert row["subitem"] == "第五项B"
        assert row["candidate_strength"] in {2, 3}
        assert row["adjudication_status"] == "source_verified_pending_human_adjudication"


def test_expanded_pilot_batch1_review_export_contains_cards_and_clusters() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_md.py")],
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
        "EVD-I5B-YONGZHENG-POS-SHIREN-001",
        "EVD-I5B-ZHUYUANZHANG-NEG-HULAN-001",
        "ADJ-I5B-LIUBANG-POS-TALENT-AUTHORIZATION-001",
        "ADJ-I5B-YONGZHENG-POS-TALENT-FEEDBACK-001",
        "ADJ-I5B-ZHUYUANZHANG-NEG-MERIT-PURGE-001",
        "cluster_candidate_id",
        "batch_draft",
    ]:
        assert needle in content
