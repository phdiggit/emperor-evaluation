from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY_PATH = ROOT / "docs" / "第五项B三人专人审核入口.md"


def test_i5b_three_person_review_entry_doc_exists_and_covers_people() -> None:
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "# 第五项B三人专人审核入口" in content
    for heading in ["## 3. 李世民审核入口", "## 4. 刘秀审核入口", "## 5. 刘庄审核入口"]:
        assert heading in content
    for person in ["李世民", "刘秀", "刘庄"]:
        assert f"exports/markdown_views/第五项B/自动结算草案/人物详情/{person}.md" in content
        assert f"exports/markdown_views/第五项B/人工审核/净证据池/第五项B_{person}人工审核净证据池.md" in content


def test_i5b_three_person_review_entry_doc_points_to_new_paths_only_for_active_entries() -> None:
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "审核时只使用 `exports/markdown_views/第五项B/` 下的新产物" in content
    assert "不要再使用 `exports/markdown_views/` 根目录下旧平铺产物" in content
    for path in [
        "exports/markdown_views/第五项B/自动结算草案/第五项B三人自动结算草案.md",
        "exports/markdown_views/第五项B/规则敏感点/第五项B自动结算规则敏感点清单.md",
        "exports/markdown_views/第五项B/正式定档草案/第五项B三人正式定档落地表.md",
        "exports/markdown_views/第五项B/正式定档草案/第五项B评分标尺与档位映射草案.md",
        "exports/markdown_views/第五项B/人工审核/证据卡/第五项B人工审核证据卡索引.md",
        "exports/markdown_views/第五项B/人工审核/证据簇/第五项B人工审核证据簇索引.md",
    ]:
        assert path in content
    assert "exports/markdown_views/第五项B/机器审计/" in content
    assert "不作为业务审核主入口" in content
    assert "人工审核主表隐藏 `evidence_id/source_id/cluster_id` 等机器字段" in content


def test_i5b_three_person_review_entry_doc_declares_legacy_paths_disabled() -> None:
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "## 6. 旧路径禁用清单" in content
    assert "应不存在" in content
    assert "不作为专人审核依据" in content
    for path in [
        "exports/markdown_views/第五项B_李世民净证据池.md",
        "exports/markdown_views/第五项B_刘秀净证据池.md",
        "exports/markdown_views/第五项B_刘庄净证据池.md",
        "exports/markdown_views/第五项B三人自动结算草案.md",
        "exports/markdown_views/第五项B自动结算草案_李世民.md",
        "exports/markdown_views/第五项B自动结算草案_刘秀.md",
        "exports/markdown_views/第五项B自动结算草案_刘庄.md",
    ]:
        assert f"{path}`：应不存在，禁用。" in content


def test_i5b_three_person_review_entry_doc_contains_context_dependent_rules() -> None:
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "## 7. 上下文依赖证据处理规则" in content
    assert "需上下文 / 需回源" in content
    assert "`context_required = true` 且 `context_status` 未达 `supplied` 或 `source_verified` 的证据，不得直接进入稳定裁判" in content
    assert "`context_effect = reverse` 的证据，应回看其证据方向、强度和裁判桥接说明" in content
    assert "`context_effect = split_only` 的证据，只能用于相邻项剥离，不得直接回填第五项B正负分" in content


def test_i5b_three_person_review_entry_doc_is_plain_review_markdown_not_scoring() -> None:
    content = ENTRY_PATH.read_text(encoding="utf-8")

    assert "不是正式评分表" in content
    assert "不生成正式分数" in content
    assert "不生成最终排名" in content
    assert "不改写自动结算结论" in content
    assert "分数映射仍不得直接启用" in content
    assert "**正向证据是否可采纳**：待人工确认" in content
    assert "<details" not in content
    assert "<summary" not in content
    assert "</details>" not in content
