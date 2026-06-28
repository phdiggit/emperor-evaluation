from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from shared import config_loaders
from export.dimension_adapters.i5b_people_delegation import adapter as auto

WORKBENCH_PATH = auto.REVIEW_WORKBENCH_EXPORT_PATH
OLD_DOC_PATH = ROOT / "docs" / "第五项B三人试点人工复核工作台.md"
_EXPORTS_REFRESHED = False


def read_workbench_content() -> str:
    global _EXPORTS_REFRESHED
    if not _EXPORTS_REFRESHED:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "export" / "export_md.py"), "--profile", "i5b-auto"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        _EXPORTS_REFRESHED = True
    return WORKBENCH_PATH.read_text(encoding="utf-8")


def test_i5b_human_review_workbench_doc_exists_and_covers_active_people() -> None:
    assert not OLD_DOC_PATH.exists()
    content = read_workbench_content()
    workflow_config = auto.active_workflow_config()
    workflow_subject = auto.active_workflow_subject(workflow_config)
    group_label = auto.active_group_label(workflow_config)
    targets = config_loaders.get_i5b_active_person_targets()

    assert "# " + workflow_subject + "人工复核工作台" in content
    assert f"- **活动人物组**：{group_label}" in content
    assert "旧 `docs/` 同名文件已退役" in content
    assert "## 使用边界" in content
    assert "## 人工复核总览" in content
    for heading in [f"## {person}" for person in targets]:
        assert heading in content


def test_i5b_human_review_workbench_doc_is_review_only_not_scoring() -> None:
    content = read_workbench_content()

    assert "不生成正式分数" in content
    assert "正式分数、排名或总榜" in content
    assert "本视图不直接推出正式结论" in content
    assert "不做单人人工 override" in content


def test_i5b_human_review_workbench_doc_keeps_display_warning_and_split_boundaries() -> None:
    content = read_workbench_content()

    assert "display-only" in content
    assert "不自动压制、不自动升档、不构成正式结论" in content
    assert "相邻项剥离" in content
    assert "数据质量核验栏位" in content
    assert "规则命中和算法版本核验" in content
    assert "manual_score_override" not in content
    assert "human_final_score" not in content


def test_i5b_human_review_workbench_doc_uses_plain_markdown_without_html_details() -> None:
    content = read_workbench_content()

    assert "<details" not in content
    assert "<summary" not in content
    assert "</details>" not in content
    assert "……（共" not in content
    for old_wide_table_marker in ["| cluster_id |", "| polarity |", "| cluster_type |"]:
        assert old_wide_table_marker not in content
