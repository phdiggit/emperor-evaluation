from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH_PATH = ROOT / "docs" / "第五项B三人试点人工复核工作台.md"


def test_i5b_human_review_workbench_doc_exists_and_covers_current_trial_people() -> None:
    content = WORKBENCH_PATH.read_text(encoding="utf-8")

    assert "# 第五项B三人试点人工复核工作台" in content
    assert "## 0. 使用说明" in content
    assert "## 1. 人工复核总览" in content
    for heading in ["## 2. 李世民", "## 3. 刘秀", "## 4. 刘庄"]:
        assert heading in content


def test_i5b_human_review_workbench_doc_is_review_only_not_scoring() -> None:
    content = WORKBENCH_PATH.read_text(encoding="utf-8")

    assert "不是正式评分表" in content
    assert "不生成正式分数" in content
    assert "不生成最终排名" in content
    assert "不替代人工裁判" in content
    assert "正式定档必须由人工确认" in content


def test_i5b_human_review_workbench_doc_keeps_display_warning_and_split_boundaries() -> None:
    content = WORKBENCH_PATH.read_text(encoding="utf-8")

    assert "display-only" in content
    assert "不自动压制、不自动升档、不构成正式结论" in content
    assert "cross_item_split_signals" in content
    assert "相邻项剥离" in content
    assert "不得把战功、治绩、盛世光环、政权安全、司法残酷、边疆收益等跨项内容回填到第五项B" in content


def test_i5b_human_review_workbench_doc_uses_plain_markdown_without_html_details() -> None:
    content = WORKBENCH_PATH.read_text(encoding="utf-8")

    assert "<details" not in content
    assert "<summary" not in content
    assert "</details>" not in content
    assert "……（共" not in content
    for old_wide_table_marker in ["| cluster_id |", "| polarity |", "| cluster_type |"]:
        assert old_wide_table_marker not in content
