from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readability_layer_is_embedded_in_generated_reader():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    assert "#rows tr.home-click-row" in html
    assert "@media (max-width: 700px)" in html
    assert "function foldHomeStatus()" in html
    assert "function compactComparisonEvidence()" in html
    assert "function simplifyDifferenceToggle()" in html


def test_public_reader_copy_stays_reader_facing():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    assert "三重视角" in html
    assert "阅读指南" in html
    assert "这个分数怎么来的？" in html
    assert "换一套合理权重，名次会变化多少？" in html
    assert "表示证据与归责判断的稳定程度，不表示影响大小。" in html
    assert "M2经终局核对仍无可证能力者列E，并保留范围说明。" not in html


def test_comparison_runtime_uses_short_public_toggle_label():
    script = (ROOT / "reader/readability.js").read_text(encoding="utf-8")
    assert 'node.textContent = "只看不同项"' in script
    assert 'label.textContent = "展开依据"' in script
    assert 'toggle.textContent = "数据状态"' in script
