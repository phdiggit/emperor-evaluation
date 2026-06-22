from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_PATH = ROOT / "data" / "adjudication_batches" / "i5b_expanded_pilot_batch1_post_supplement_adjudication_20260619.jsonl"
EXPORT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "试点闭环"
    / "第五项B扩展试点第一批补证后结算更新草案.md"
)


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def test_post_supplement_batch_is_three_person_drafts() -> None:
    rows = load_jsonl(BATCH_PATH)

    assert len(rows) == 3
    assert {row["person"] for row in rows} == {"刘邦", "雍正", "朱元璋"}
    assert {row["status"] for row in rows} == {"post_supplement_adjudication_draft"}

    counts = Counter(row["person"] for row in rows)
    assert counts == {"刘邦": 1, "雍正": 1, "朱元璋": 1}

    for row in rows:
        assert row["item"] == "第五项"
        assert row["subitem"] == "第五项B"
        assert row["pre_supplement_net_adjudication_summary"]
        assert row["supplement_evidence_ids"]
        assert row["supplement_positive_effect_summary"]
        assert row["supplement_negative_effect_summary"]
        assert row["post_supplement_negative_intercept_status"]
        assert row["post_supplement_adjacent_item_split_summary"]
        assert row["post_supplement_rule_pressure_summary"]
        assert row["post_supplement_net_adjudication_draft"]
        assert row["remaining_gap_list"]
        assert "score" not in row
        assert "rank" not in row
        assert "final_grade" not in row
        assert "final_score" not in row
        assert "leaderboard" not in row
        assert "total_ranking" not in row


def test_post_supplement_batch_uses_the_new_supplement_evidence_ids() -> None:
    rows = load_jsonl(BATCH_PATH)
    lookup = {row["person"]: row for row in rows}

    assert lookup["刘邦"]["supplement_evidence_ids"] == [
        "EVD-I5B-LIUBANG-SUPP-ZHANGLIANG-EXIT-001",
        "EVD-I5B-LIUBANG-SUPP-ZHANGLIANG-ADVISE-001",
        "EVD-I5B-LIUBANG-SUPP-FANKUAI-BUFFER-001",
    ]
    assert lookup["雍正"]["supplement_evidence_ids"] == [
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-AUTH-001",
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-REUSE-001",
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-CRITIQUE-001",
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-SENTENCE-001",
    ]
    assert lookup["朱元璋"]["supplement_evidence_ids"] == [
        "EVD-I5B-ZHUYUANZHANG-SUPP-LISHANG-001",
        "EVD-I5B-ZHUYUANZHANG-SUPP-XUDA-001",
        "EVD-I5B-ZHUYUANZHANG-SUPP-HUWENYONG-001",
        "EVD-I5B-ZHUYUANZHANG-SUPP-LISHANG-002",
    ]
    assert lookup["雍正"]["role_class_sweep_effect_summary"] != "not_applicable"
    assert "岳钟琪" in str(lookup["雍正"]["role_class_sweep_effect_summary"])
    assert "not_carded_reason" in str(lookup["雍正"]["role_class_sweep_effect_summary"])
    assert lookup["刘邦"]["role_class_sweep_effect_summary"] == "not_applicable"
    assert lookup["朱元璋"]["role_class_sweep_effect_summary"] == "not_applicable"


def test_post_supplement_export_is_review_only() -> None:
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
    assert "# 第五项B扩展试点第一批补证后结算更新草案" in content
    assert "不定档，不出分，不排名，不出总榜。" in content
    for needle in [
        "刘邦",
        "雍正",
        "朱元璋",
        "补证正向效应",
        "补证负向效应",
        "role-class sweep 效应",
        "负拦截状态",
        "相邻项切分摘要",
        "remaining gaps",
        "EVD-I5B-YONGZHENG-SUPP-YUEZHONGQI-AUTH-001",
        "岳钟琪",
    ]:
        assert needle in content
    for forbidden in ["score", "rank", "final_grade", "final_score", "leaderboard", "total_ranking"]:
        assert forbidden not in content
