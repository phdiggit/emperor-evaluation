from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH_PATH = ROOT / "exports" / "markdown_views" / "第五项B" / "人工审核" / "入口" / "第五项B三人试点人工复核工作台.md"
OLD_DOC_PATH = ROOT / "docs" / "第五项B三人试点人工复核工作台.md"


def test_i5b_human_review_workbench_doc_exists_and_covers_current_trial_people() -> None:
    assert not OLD_DOC_PATH.exists()
    content = WORKBENCH_PATH.read_text(encoding="utf-8")

    assert "# 第五项B三人试点人工复核工作台" in content
    assert "旧 `docs/` 同名文件已退役" in content
    assert "## 使用边界" in content
    assert "## 人工复核总览" in content
    for heading in ["## 李世民", "## 刘秀", "## 刘庄"]:
        assert heading in content


def test_i5b_human_review_workbench_doc_is_review_only_not_scoring() -> None:
    content = WORKBENCH_PATH.read_text(encoding="utf-8")

    assert "不生成正式分数" in content
    assert "正式分数、排名或总榜" in content
    assert "本视图不直接推出正式结论" in content
    assert "不做单人人工 override" in content


def test_i5b_human_review_workbench_doc_keeps_display_warning_and_split_boundaries() -> None:
    content = WORKBENCH_PATH.read_text(encoding="utf-8")

    assert "display-only" in content
    assert "不自动压制、不自动升档、不构成正式结论" in content
    assert "相邻项剥离" in content
    assert "数据质量核验栏位" in content
    assert "规则命中和算法版本核验" in content
    assert "manual_score_override" not in content
    assert "human_final_score" not in content


def test_i5b_human_review_workbench_doc_uses_plain_markdown_without_html_details() -> None:
    content = WORKBENCH_PATH.read_text(encoding="utf-8")

    assert "<details" not in content
    assert "<summary" not in content
    assert "</details>" not in content
    assert "……（共" not in content
    for old_wide_table_marker in ["| cluster_id |", "| polarity |", "| cluster_type |"]:
        assert old_wide_table_marker not in content
