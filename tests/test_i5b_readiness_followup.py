from __future__ import annotations

# File lifecycle: temporary.
# Retirement condition: remove this readiness follow-up guard once the
# follow-up package is superseded by a human-review decision, folded into
# generic review-item coverage, or moved to archive_only.

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RULE_BOUNDARY_PATH = ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "yongzheng_rule_boundary_review.jsonl"
SOURCES_PATH = ROOT / "data" / "sources.jsonl"
EVIDENCE_CARDS_PATH = ROOT / "data" / "evidence_cards.jsonl"
FOLLOWUP_BATCH_PATH = ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "readiness_followup.jsonl"
EXPORT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "试点闭环"
    / "第五项B扩展试点第一批readiness后续处理.md"
)
ZHUYUANZHANG_MICRO_SUPPLEMENT_SOURCE_IDS = (
    "SRC-MS-J128-LIUJI-SONGLIAN-001",
    "SRC-MS-J132-LANYU-001",
)
ZHUYUANZHANG_MICRO_SUPPLEMENT_EVIDENCE_IDS = (
    "EVD-I5B-ZHUYUANZHANG-MICRO-LIUJI-HIRE-001",
    "EVD-I5B-ZHUYUANZHANG-MICRO-LIUJI-RETREAT-001",
    "EVD-I5B-ZHUYUANZHANG-MICRO-SONGLIAN-HIRE-001",
    "EVD-I5B-ZHUYUANZHANG-MICRO-SONGLIAN-EXILE-001",
    "EVD-I5B-ZHUYUANZHANG-MICRO-LANYU-PURGE-001",
)


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def rows_by_ids(path: Path, id_field: str, row_ids: tuple[str, ...]) -> list[dict[str, object]]:
    index = {row.get(id_field): row for row in load_jsonl(path)}
    return [index[row_id] for row_id in row_ids if row_id in index]


def test_yongzheng_rule_boundary_review_exists_and_uses_allowed_next_step() -> None:
    rows = load_jsonl(RULE_BOUNDARY_PATH)

    assert len(rows) == 1
    row = rows[0]
    assert row["person"] == "雍正"
    assert row["status"] == "rule_boundary_review_draft"
    assert row["recommended_next_step"] in {
        "ready_for_human_review_without_scoring",
        "needs_targeted_micro_supplement",
        "keep_rule_boundary_review_open",
    }
    assert row["input_readiness_id"] == "RDY-I5B-YONGZHENG-20260619"
    assert row["boundary_questions"]
    assert row["resolved_boundary_points"]
    assert row["open_boundary_points"]
    assert row["not_carded_people_review"]
    assert row["cross_item_split_guardrails"]
    for forbidden in ["score", "rank", "final_grade", "final_score", "leaderboard", "total_ranking"]:
        assert forbidden not in row


def test_zhu_yuanzhang_micro_supplement_is_source_backed_and_covers_all_priority_people() -> None:
    source_rows = rows_by_ids(SOURCES_PATH, "source_id", ZHUYUANZHANG_MICRO_SUPPLEMENT_SOURCE_IDS)
    evidence_rows = rows_by_ids(EVIDENCE_CARDS_PATH, "evidence_id", ZHUYUANZHANG_MICRO_SUPPLEMENT_EVIDENCE_IDS)

    assert len(source_rows) == 2
    assert len(evidence_rows) >= 3
    assert {row["verification_status"] for row in evidence_rows} == {"source_verified"}
    assert {row["adjudication_status"] for row in evidence_rows} == {"source_verified_pending_human_adjudication"}

    evidence_ids_by_gap = " ".join(str(row["micro_gap_addressed"]) for row in evidence_rows)
    assert "刘基" in evidence_ids_by_gap
    assert "宋濂" in evidence_ids_by_gap
    assert "蓝玉" in evidence_ids_by_gap

    counts = Counter()
    for row in evidence_rows:
        assert row["person"] == "朱元璋"
        assert row["micro_supplement_for_readiness_id"] == "RDY-I5B-ZHUYUANZHANG-20260619"
        assert row["micro_gap_addressed"]
        assert row["scoring_effect"] == "不得直接入分，待人工裁判。"
        if "刘基" in str(row["micro_gap_addressed"]):
            counts["刘基"] += 1
        if "宋濂" in str(row["micro_gap_addressed"]):
            counts["宋濂"] += 1
        if "蓝玉" in str(row["micro_gap_addressed"]):
            counts["蓝玉"] += 1
        for forbidden in ["score", "rank", "final_grade", "final_score", "leaderboard", "total_ranking"]:
            assert forbidden not in row

    assert counts["刘基"] >= 1
    assert counts["宋濂"] >= 1
    assert counts["蓝玉"] >= 1
    assert any(row["polarity"] == "positive" for row in evidence_rows)
    assert any(row["polarity"] == "negative" for row in evidence_rows)


def test_readiness_followup_summary_covers_all_three_people() -> None:
    rows = load_jsonl(FOLLOWUP_BATCH_PATH)
    person_rows = [row for row in rows if row.get("row_type") != "batch_followup_summary"]
    summary_rows = [row for row in rows if row.get("row_type") == "batch_followup_summary"]

    assert {row["person"] for row in person_rows} == {"刘邦", "雍正", "朱元璋"}
    assert {row["status"] for row in person_rows} == {"readiness_followup_draft"}
    assert len(summary_rows) == 1
    assert summary_rows[0]["status"] == "readiness_followup_draft"

    lookup = {row["person"]: row for row in person_rows}
    assert lookup["刘邦"]["current_readiness_recommendation"] == "ready_for_human_review_without_scoring"
    assert lookup["雍正"]["current_readiness_recommendation"] == "ready_for_human_review_without_scoring"
    assert lookup["朱元璋"]["current_readiness_recommendation"] == "ready_for_human_review_without_scoring"


@pytest.mark.export_full
@pytest.mark.integration
def test_readiness_followup_export_is_review_only() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export" / "export_md.py"), "--profile", "i5b-expanded-batch1"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert EXPORT_PATH.exists()

    content = EXPORT_PATH.read_text(encoding="utf-8")
    assert "# 第五项B扩展试点第一批readiness后续处理" in content
    assert "不定档，不出分，不排名，不出总榜。" in content
    for needle in [
        "雍正规则边界复核",
        "朱元璋 micro supplement 证据卡",
        "readiness follow-up summary",
        "刘邦",
        "雍正",
        "朱元璋",
        "BATCH-FUP-I5B-20260619",
    ]:
        assert needle in content
    for forbidden in ["score", "rank", "final_grade", "final_score", "leaderboard", "total_ranking"]:
        assert forbidden not in content
