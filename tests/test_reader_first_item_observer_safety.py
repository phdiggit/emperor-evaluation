from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_first_item_observers_only_write_when_dom_text_changes():
    reading = (ROOT / "reader" / "first-item-reading.js").read_text(encoding="utf-8")
    boundary = (ROOT / "reader" / "first-item-boundary-notes.js").read_text(encoding="utf-8")

    assert "function setText(node, value)" in reading
    assert "node.textContent !== value" in reading
    assert "setText(main, firstDescriptions.detail)" in reading
    assert "setText(score, scoreText)" in reading
    assert "setText(p, \"本项可以追溯到即位前的创业／统一责任" in reading
    assert "if (main) main.textContent = firstDescriptions.detail" not in reading

    assert 'card.dataset.commanderZeroReader === "done"' in boundary
    assert 'card.dataset.commanderZeroReader = "done"' in boundary
    assert "if (next !== text) small.textContent = next" in boundary


def test_first_item_observer_scripts_are_loaded_once():
    public_copy = (ROOT / "reader" / "public-copy.json").read_text(encoding="utf-8")
    lazy = (ROOT / "reader" / "lazy-details.js").read_text(encoding="utf-8")
    assert public_copy.count("first-item-reading.js") == 1
    assert public_copy.count("first-item-boundary-notes.js") == 1
    assert 'script.src = "first-item-reading.js"' not in lazy
    assert 'script.src = "first-item-boundary-notes.js"' not in lazy
