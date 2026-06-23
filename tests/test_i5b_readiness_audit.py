from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BATCH_PATH = ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "readiness_audit.jsonl"
EXPORT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "试点闭环"
    / "第五项B扩展试点第一批人工裁判准备审计.md"
)


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def test_readiness_audit_batch_has_three_people_and_optional_summary_row() -> None:
    rows = load_jsonl(BATCH_PATH)
    person_rows = [row for row in rows if row.get("row_type") != "batch_rule_pressure_summary"]
    summary_rows = [row for row in rows if row.get("row_type") == "batch_rule_pressure_summary"]

    assert len(person_rows) == 3
    assert {row["person"] for row in person_rows} == {"刘邦", "雍正", "朱元璋"}
    assert {row["status"] for row in person_rows} == {"readiness_audit_draft"}
    assert len(summary_rows) == 1
    assert summary_rows[0]["batch_rule_pressure_id"] == "BATCH-RDY-I5B-20260619"
    assert summary_rows[0]["status"] == "readiness_audit_draft"

    for row in person_rows:
        assert row["item"] == "第五项"
        assert row["subitem"] == "第五项B"
        assert row["current_draft_status"] == "post_supplement_adjudication_draft"
        assert row["stabilized_findings"]
        assert row["unstable_findings"]
        assert row["must_human_review_points"]
        assert row["rule_pressure_points"]
        assert row["cross_item_split_risks"]
        assert row["negative_intercept_review_needed"]
        assert row["remaining_evidence_gaps"]
        assert row["recommended_next_step"] in {
            "ready_for_human_review_without_scoring",
            "needs_targeted_micro_supplement",
            "needs_rule_boundary_review",
        }
        assert "score" not in row
        assert "rank" not in row
        assert "final_grade" not in row
        assert "final_score" not in row
        assert "leaderboard" not in row
        assert "total_ranking" not in row


def test_readiness_audit_records_expected_readiness_calls() -> None:
    rows = load_jsonl(BATCH_PATH)
    lookup = {row.get("person"): row for row in rows if row.get("row_type") != "batch_rule_pressure_summary"}

    assert lookup["刘邦"]["recommended_next_step"] == "ready_for_human_review_without_scoring"
    assert lookup["雍正"]["recommended_next_step"] == "needs_rule_boundary_review"
    assert lookup["朱元璋"]["recommended_next_step"] == "needs_targeted_micro_supplement"

    assert "岳钟琪" in str(lookup["雍正"]["stabilized_findings"])
    assert "not-carded" in str(lookup["雍正"]["remaining_evidence_gaps"])
    assert "韩信" in str(lookup["刘邦"]["cross_item_split_risks"])
    assert "刘基" in str(lookup["朱元璋"]["must_human_review_points"])


@pytest.mark.export_full
@pytest.mark.integration
def test_readiness_audit_export_is_review_only() -> None:
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
    assert "# 第五项B扩展试点第一批人工裁判准备审计" in content
    assert "不定档，不出分，不排名，不出总榜。" in content
    assert "批次级规则压力总结" in content
    for needle in [
        "刘邦",
        "雍正",
        "朱元璋",
        "人工裁判准备",
        "\u5efa\u8bae\u4e0b\u4e00\u6b65",
        "\u5269\u4f59\u8bc1\u636e\u7f3a\u53e3",
        "BATCH-RDY-I5B-20260619",
    ]:
        assert needle in content
    for forbidden in ["score", "rank", "final_grade", "final_score", "leaderboard", "total_ranking"]:
        assert forbidden not in content
