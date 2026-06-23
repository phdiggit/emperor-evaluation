from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "docs" / "第五项B评分映射总标尺对齐审计.md"
SCORE_MAP_DRAFT_EXPORT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "正式定档草案"
    / "第五项B评分标尺与档位映射草案.md"
)


def test_i5b_global_scale_audit_is_marked_superseded_by_v32() -> None:
    audit_content = AUDIT_PATH.read_text(encoding="utf-8")
    score_map_content = SCORE_MAP_DRAFT_EXPORT_PATH.read_text(encoding="utf-8")

    assert "第五项B评分映射总标尺对齐审计" in audit_content
    assert "V3.2 取代说明" in audit_content
    assert "旧结论已被 V3.2 取代" in audit_content
    assert "当前评分映射草案入口为 canonical export" in audit_content
    assert "正式 45 分映射、人审和发布门槛尚未完成" in audit_content
    assert "不是总标尺缺失" in audit_content
    assert "正式 45 分映射需另开专门 PR" in audit_content

    assert "## 四、V3.2 对齐边界" in score_map_content
    assert "第五项B《用人与授权》正式上限为 45 分" in score_map_content
    assert "内部100制相对试算指数" in score_map_content
    assert "不是 V3.2 正式得分率" in score_map_content
    assert "待总标尺确认" not in score_map_content
