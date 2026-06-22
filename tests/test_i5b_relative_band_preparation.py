from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_PATH = ROOT / "data" / "relative_band_batches" / "i5b_expanded_pilot_batch1_relative_band_preparation_20260619.jsonl"
EXPORT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "正式定档草案"
    / "第五项B扩展试点第一批相对档位准备草案.md"
)
FORBIDDEN_KEYS = {"score", "rank", "final_grade", "final_score", "leaderboard", "total_ranking", "formal_grade", "official_grade"}
FORBIDDEN_TEXT = ["score", "rank", "final_grade", "final_score", "leaderboard", "total_ranking", "formal_grade", "official_grade"]


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def test_relative_band_preparation_contains_three_people_and_one_batch_summary_row() -> None:
    rows = load_jsonl(BATCH_PATH)
    person_rows = [row for row in rows if row.get("row_type") != "batch_relative_band_summary"]
    summary_rows = [row for row in rows if row.get("row_type") == "batch_relative_band_summary"]

    assert {row["person"] for row in person_rows} == {"刘邦", "雍正", "朱元璋"}
    assert len(person_rows) == 3
    assert len(summary_rows) == 1
    assert summary_rows[0]["status"] == "relative_band_preparation_draft"


def test_each_person_row_uses_the_allowed_rule_language_only() -> None:
    rows = load_jsonl(BATCH_PATH)
    person_rows = [row for row in rows if row.get("row_type") != "batch_relative_band_summary"]

    for row in person_rows:
        assert row["status"] == "relative_band_preparation_draft"
        assert row["next_step_recommendation"] == "ready_for_human_rule_confirmation"
        for required_key in [
            "relative_band_draft_id",
            "input_review_package_id",
            "current_review_stage",
            "rule_based_positioning_summary",
            "positive_base_status",
            "negative_gate_status",
            "cross_item_split_status",
            "relative_band_path_options",
            "human_confirmation_questions",
            "blocked_shortcuts",
            "not_for_scoring_statement",
        ]:
            assert row[required_key]
        assert isinstance(row["relative_band_path_options"], list)
        assert isinstance(row["human_confirmation_questions"], list)
        assert isinstance(row["blocked_shortcuts"], list)
        assert any("relative_band_path_A" in item for item in row["relative_band_path_options"])
        assert any("relative_band_path_B" in item for item in row["relative_band_path_options"])
        for forbidden_key in FORBIDDEN_KEYS:
            assert forbidden_key not in row


def test_batch_summary_row_keeps_the_shared_rule_boundary_limited() -> None:
    rows = load_jsonl(BATCH_PATH)
    summary_row = next(row for row in rows if row.get("row_type") == "batch_relative_band_summary")

    assert summary_row["batch_relative_band_draft_id"] == "BATCH-RBD-I5B-20260619"
    assert summary_row["shared_positioning_rules"]
    assert summary_row["shared_negative_gate_rules"]
    assert summary_row["shared_cross_item_split_rules"]
    assert summary_row["user_decision_questions"]
    assert summary_row["next_workflow_options"]
    assert summary_row["not_for_scoring_statement"]
    for forbidden_key in FORBIDDEN_KEYS:
        assert forbidden_key not in summary_row


def test_relative_band_preparation_export_is_review_only_and_not_polluted() -> None:
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
    assert "# 第五项B扩展试点第一批相对档位准备草案" in content
    assert "不定档，不出分，不排名，不出总榜。" in content
    assert "刘邦" in content
    assert "雍正" in content
    assert "朱元璋" in content
    assert "批次级规则准备摘要" in content
    assert "relative_band_path_A" in content
    assert "relative_band_path_B" in content
    assert "ready_for_human_rule_confirmation" in content
    for forbidden in FORBIDDEN_TEXT:
        assert forbidden not in content
