from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "data" / "review_packages" / "i5b_expanded_pilot_batch1_human_review_package_20260619.jsonl"
EXPORT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "试点闭环"
    / "第五项B扩展试点第一批人工会审准备包.md"
)
FORBIDDEN_KEYS = {"score", "rank", "final_grade", "final_score", "leaderboard", "total_ranking"}
FORBIDDEN_TEXT = ["score", "rank", "final_grade", "final_score", "leaderboard", "total_ranking"]


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def test_human_review_package_contains_three_people_and_one_agenda_row() -> None:
    rows = load_jsonl(PACKAGE_PATH)
    person_rows = [row for row in rows if row.get("row_type") != "batch_review_agenda"]
    agenda_rows = [row for row in rows if row.get("row_type") == "batch_review_agenda"]

    assert {row["person"] for row in person_rows} == {"刘邦", "雍正", "朱元璋"}
    assert len(person_rows) == 3
    assert len(agenda_rows) == 1
    assert agenda_rows[0]["status"] == "human_review_package_draft"


def test_each_person_row_is_a_single_human_review_package_draft() -> None:
    rows = load_jsonl(PACKAGE_PATH)
    person_rows = [row for row in rows if row.get("row_type") != "batch_review_agenda"]

    for row in person_rows:
        assert row["status"] == "human_review_package_draft"
        assert row["current_readiness_recommendation"] == "ready_for_human_review_without_scoring"
        for required_key in [
            "core_rule_question",
            "negative_intercept_gate",
            "cross_item_split_gate",
            "possible_human_review_paths",
            "forbidden_shortcuts",
            "not_for_scoring_statement",
        ]:
            assert row[required_key]
        assert isinstance(row["possible_human_review_paths"], list)
        assert isinstance(row["forbidden_shortcuts"], list)
        for forbidden_key in FORBIDDEN_KEYS:
            assert forbidden_key not in row


def test_agenda_row_is_rule_only_and_non_scoring() -> None:
    rows = load_jsonl(PACKAGE_PATH)
    agenda_row = next(row for row in rows if row.get("row_type") == "batch_review_agenda")

    shared_rule_questions = " ".join(str(item) for item in agenda_row["shared_rule_questions"])
    decision_points = " ".join(str(item) for item in agenda_row["decision_points_for_user"])
    assert "用户只审规则/算法，不审具体案例细节" in (shared_rule_questions + " " + decision_points)
    assert agenda_row["shared_negative_intercept_gate"]
    assert agenda_row["shared_cross_item_split_gate"]
    assert agenda_row["workflow_lessons"]
    assert agenda_row["not_for_scoring_statement"]
    for forbidden_key in FORBIDDEN_KEYS:
        assert forbidden_key not in agenda_row


def test_human_review_package_export_is_review_only_and_not_polluted() -> None:
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
    assert "# 第五项B扩展试点第一批人工会审准备包" in content
    assert "不定档，不出分，不排名，不出总榜。" in content
    assert "刘邦" in content
    assert "雍正" in content
    assert "朱元璋" in content
    assert "批次级会审议程" in content
    assert "\u8d1f\u8bc1\u62e6\u622a\u5173\u53e3" in content
    assert "\u76f8\u90bb\u9879\u5265\u79bb\u5173\u53e3" in content
    assert "下一步建议" in content
    assert "只进入规则、边界与裁判路径会审" in content
    for forbidden in FORBIDDEN_TEXT:
        assert forbidden not in content
