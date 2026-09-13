from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_home_table_interactions_are_in_generated_reader():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    assert "function enhanceHomeRows()" in html
    assert '1: "person-outcome"' in html
    assert '2: "person-capability"' in html
    assert '3: "person-impact"' in html
    assert "data-home-polity" in html
    assert "data-home-grade" in html
    assert "home-jump-cell" in html


def test_home_interactions_keep_compare_control_separate():
    script = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "if (event.target.closest(interactiveSelector)) return;" in script
    assert "openPersonSection(row.dataset.homePerson" in script
    assert "applyPolityFilter" in script
    assert "applyImpactFilter" in script
