from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY_PATH = ROOT / "exports" / "markdown_views" / "第五项B" / "人工审核" / "入口" / "第五项B三人专人审核入口.md"
OLD_DOC_PATH = ROOT / "docs" / "第五项B三人专人审核入口.md"


def test_i5b_three_person_review_entry_doc_exists_and_covers_people() -> None:
    assert not OLD_DOC_PATH.exists()
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "# 第五项B三人专人审核入口" in content
    assert "旧 `docs/` 同名文件已退役" in content
    for heading in ["### 李世民", "### 刘秀", "### 刘庄"]:
        assert heading in content
    for person in ["李世民", "刘秀", "刘庄"]:
        assert f"exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/人物详情/{person}.md" in content
        assert f"exports/markdown_views/第五项B/人工审核/证据链/净证据池/第五项B_{person}人工审核净证据池.md" in content


def test_i5b_three_person_review_entry_doc_points_to_new_paths_only_for_active_entries() -> None:
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "审核入口视图：`exports/markdown_views/第五项B/人工审核/入口/`" in content
    assert "以下旧路径若在历史分支或本地残留中出现" in content
    for path in [
        "exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/第五项B三人自动结算草案.md",
        "exports/markdown_views/第五项B/人工审核/自动裁判链/规则敏感点/第五项B自动结算规则敏感点清单.md",
        "exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B三人正式定档落地表.md",
        "exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B评分标尺与档位映射草案.md",
        "exports/markdown_views/第五项B/人工审核/证据链/证据卡/第五项B人工审核证据卡索引.md",
        "exports/markdown_views/第五项B/人工审核/证据链/证据簇/第五项B人工审核证据簇索引.md",
    ]:
        assert path in content
    assert "exports/markdown_views/第五项B/机器审计/证据链/" in content
    assert "不作为业务审核主入口" in content
    assert "人工审核主表隐藏 `evidence_id/source_id/cluster_id` 等机器字段" in content


def test_i5b_three_person_review_entry_doc_declares_legacy_paths_disabled() -> None:
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "## 旧路径禁用" in content
    assert "不作为当前审核入口" in content
    for path in [
        "exports/markdown_views/第五项B_李世民净证据池.md",
        "exports/markdown_views/第五项B_刘秀净证据池.md",
        "exports/markdown_views/第五项B_刘庄净证据池.md",
        "exports/markdown_views/第五项B三人自动结算草案.md",
        "exports/markdown_views/第五项B自动结算草案_李世民.md",
        "exports/markdown_views/第五项B自动结算草案_刘秀.md",
        "exports/markdown_views/第五项B自动结算草案_刘庄.md",
    ]:
        assert f"`{path}`" in content


def test_i5b_three_person_review_entry_doc_contains_context_dependent_rules() -> None:
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "数据质量核验栏位" in content
    assert "回源状态、上下文充分性、相邻项剥离、证据方向一致性、规则命中异常" in content
    assert "人工只核验数据质量、史料回源状态、上下文充分性、相邻项剥离、规则命中和算法版本" in content


def test_i5b_three_person_review_entry_doc_is_plain_review_markdown_not_scoring() -> None:
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "不是正式评分表" in content
    assert "不生成正式分数" in content
    assert "不生成最终排名" in content
    assert "不逐人改写自动结算方向" in content
    assert "不得把本文档、自动结算草案、证据链视图或 warning 直接转写成正式分数、最终排名、正式档位或裁判结论" in content
    assert "manual_score_override" not in content
    assert "human_final_score" not in content
    assert "<details" not in content
    assert "<summary" not in content
    assert "</details>" not in content
