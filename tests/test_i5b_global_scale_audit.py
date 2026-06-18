from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "docs" / "第五项B评分映射总标尺对齐审计.md"
AUDIT_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B评分映射总标尺对齐审计.md"
SCORE_MAP_DRAFT_PATH = ROOT / "docs" / "第五项B评分标尺与档位映射草案.md"


def test_i5b_global_scale_audit_records_no_explicit_upper_bound() -> None:
    audit_content = AUDIT_PATH.read_text(encoding="utf-8")
    audit_export_content = AUDIT_EXPORT_PATH.read_text(encoding="utf-8")
    score_map_content = SCORE_MAP_DRAFT_PATH.read_text(encoding="utf-8")

    for content in (audit_content, audit_export_content):
        assert "第五项B评分映射总标尺对齐审计" in content
        assert "没有发现一个明确把第五项B换算成正式总分的全局满分上限、总标尺或第五项B专属分值封顶" in content
        assert "第五项B评分映射草案应继续保持“待总标尺确认”" in content
        assert "继续保留第五项B相对区间草案" in content
        assert "不进入正式出分任务" in content

    assert "## 四、全局总标尺核对" in score_map_content
    assert "未发现可直接把第五项B相对区间换算成正式总分的全局满分上限、总标尺或第五项B专属分值封顶" in score_map_content
    assert "待总标尺确认" in score_map_content
