from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readability_layer_is_embedded_in_generated_reader():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    assert "#rows tr.home-click-row" in html
    assert "@media (max-width: 700px)" in html
    assert "function foldHomeStatus()" in html
    assert "function compactComparisonEvidence()" in html
    assert "function simplifyDifferenceToggle()" in html
    assert "function publicGradeHelp()" in html
    assert "function publicAxisMetadata()" in html
    assert "function translateResidualAxisCodes()" in html


def test_public_reader_copy_stays_reader_facing():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    assert "三重视角" in html
    assert "阅读指南" in html
    assert "这个分数怎么来的？" in html
    assert "换一套合理权重，名次会变化多少？" in html
    assert "表示证据与归责判断的稳定程度，不表示影响大小。" in html
    assert "只看不同项" in html
    assert "隐藏相同数值／等级" not in html
    assert "M2经终局核对仍无可证能力者列E，并保留范围说明。" not in html
    assert "材料级别 ${esc(a.axis_evidence_level" not in html
    assert "${pending(a)?'历史数值':'雷达投影'}" not in html
    assert "专业信息与正式记录" in html


def test_comparison_runtime_uses_public_labels_and_hides_internal_profile_projection():
    script = (ROOT / "reader/readability.js").read_text(encoding="utf-8")
    assert 'node.textContent = "只看不同项"' in script
    assert 'label.textContent = "展开依据"' in script
    assert 'toggle.textContent = "数据状态"' in script
    assert 'summary.textContent = "专业信息与正式记录"' in script
    assert 'status = `公开等级：${grade(axis)}`' in script
    assert "radar_value" not in script
    assert "axis_grade" not in script


def test_profile_runtime_translates_internal_direction_enums_without_fixed_ruler_data():
    script = (ROOT / "reader/readability.js").read_text(encoding="utf-8")
    assert 'MIXED_NEGATIVE\\b/g, "正负混合、以负向为主"' in script
    assert 'COUNTEREVIDENCE_FOUND\\b/g, "已找到明确反例"' in script
    assert 'AXIS_OUT_WITH_REASON\\b/g, "不计入本轴（有明确理由）"' in script
    assert "readerText = publicReaderText" in script


def test_profile_runtime_translates_workflow_terms_without_fixed_ruler_data():
    script = (ROOT / "reader/readability.js").read_text(encoding="utf-8")
    assert '父链/g, "证据链"' in script
    assert '裁档/g, "定档"' in script
    assert '下沿/g, "较低边界"' in script
    assert '复验/g, "复核"' in script
    assert '跨轴/g, "跨维度"' in script
    assert '消费点/g, "评价落点"' in script


def test_grade_help_explains_public_scales_without_fixed_ruler_data():
    script = (ROOT / "reader/readability.js").read_text(encoding="utf-8")
    assert "同一字母等级中的较低、中间和较高位置" in script
    assert "人物画像与历史影响使用不同尺度" in script
    assert "C5只评价权力运用风格与克制，不当作能力高低" in script
    assert "最终等级与四个维度分别判断，不做简单平均" in script
