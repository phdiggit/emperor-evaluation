from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_BATCH_PATH = ROOT / "data" / "source_batches" / "i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl"
EVIDENCE_BATCH_PATH = ROOT / "data" / "evidence_card_batches" / "i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl"
SWEEP_BATCH_PATH = ROOT / "data" / "sweep_batches" / "i5b_yongzheng_role_class_sweep_20260619.jsonl"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B扩展试点第一批定向补证.md"


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def test_targeted_supplement_sources_cover_only_the_new_supplement_set() -> None:
    rows = load_jsonl(SOURCE_BATCH_PATH)

    assert len(rows) == 6
    assert {row["source_id"] for row in rows} == {
        "SRC-QSG-YZ-J293-YUEZHONGQI-001",
        "SRC-QSG-YZ-J296-YUEZHONGQI-001",
        "SRC-QSG-YZ-J297-YUEZHONGQI-001",
        "SRC-MS-J127-LISHANG-001",
        "SRC-MTZL-J026-XUDA-001",
        "SRC-MS-J308-HUWENYONG-001",
    }


def test_targeted_supplement_evidence_cards_are_source_backed_and_gap_linked() -> None:
    rows = load_jsonl(EVIDENCE_BATCH_PATH)

    assert len(rows) == 11
    assert {row["person"] for row in rows} == {"刘邦", "雍正", "朱元璋"}

    counts = Counter(row["person"] for row in rows)
    assert counts["刘邦"] == 3
    assert counts["雍正"] == 4
    assert counts["朱元璋"] == 4

    for row in rows:
        assert row["verification_status"] == "source_verified"
        assert row["adjudication_status"] == "source_verified_pending_human_adjudication"
        assert row["supplement_for_adjudication_id"]
        assert row["supplement_gap_addressed"]
        assert row["cluster_candidate_id"]
        assert row["object_anchor"]
        assert row["evidence_role"]
        assert row["mitigation_flag"]
        assert row["upper_bound_flag"]
        assert row["cluster_role"]
        assert "score" not in row
        assert "rank" not in row
        assert "final_grade" not in row
        assert "final_score" not in row
        assert "leaderboard" not in row
        assert "total_ranking" not in row


def test_role_class_sweep_catches_yongzheng_fallthrough_roles() -> None:
    rows = load_jsonl(SWEEP_BATCH_PATH)

    assert len(rows) == 5
    assert {row["person"] for row in rows} == {"雍正"}
    assert {row["item"] for row in rows} == {"第五项B"}
    assert {row["subitem"] for row in rows} == {"第五项B"}
    assert {row["status"] for row in rows} == {"role_class_sweep_draft"}
    assert {row["source_status"] for row in rows} == {"source_verified"}

    expected_role_classes = {
        "near_minister_power_holder_trust_reversal",
        "provincial_administrator_authorization",
        "frontier_military_authorization",
        "feedback_memorial_network_object",
        "talent_safety_trust_reversal_object",
    }
    assert expected_role_classes <= {row["role_class"] for row in rows}

    frontier = next(row for row in rows if row["role_class"] == "frontier_military_authorization")
    assert frontier["carded_people"] == ["岳钟琪"]
    assert frontier["linked_evidence_ids"] == [
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-AUTH-001",
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-REUSE-001",
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-CRITIQUE-001",
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-SENTENCE-001",
    ]
    assert "岳钟琪" in frontier["candidate_people"]

    for row in rows:
        if row["not_carded_people"]:
            assert row["not_carded_reason"]


def test_targeted_supplement_export_is_review_only() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_md.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert EXPORT_PATH.exists()

    content = EXPORT_PATH.read_text(encoding="utf-8")
    assert "# 第五项B扩展试点第一批定向补证" in content
    assert "本文仅汇总定向补证材料" in content
    assert "不定档，不出分，不排名，不出总榜" in content
    assert "## 雍正 role-class sweep / 防漏扫查" in content
    for needle in [
        "EVD-I5B-LIUBANG-SUPP-ZHANGLIANG-EXIT-001",
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-SENTENCE-001",
        "EVD-I5B-ZHUYUANZHANG-SUPP-LISHANG-001",
        "SRC-QSG-YZ-J293-YUEZHONGQI-001",
        "SRC-MS-J127-LISHANG-001",
                "岳钟琪",
        "傅尔丹",
        "查郎阿",
        "not_carded_reason",
    ]:
        assert needle in content
    for forbidden in ["final_grade", "final_score", "leaderboard", "total_ranking"]:
        assert forbidden not in content
