from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_first_item_newcomer_chain_is_loaded_progressively():
    lazy = (ROOT / "reader/lazy-details.js").read_text(encoding="utf-8")
    assert 'script.src = "first-item-reading.js"' in lazy
    assert 'script.dataset.firstItemReading = "true"' in lazy


def test_first_item_newcomer_chain_keeps_s1_before_add_on_and_links_military_archive():
    source = (ROOT / "reader/first-item-reading.js").read_text(encoding="utf-8")
    assert "第一项净分 S1" in source
    assert "总榜附加" in source
    assert "先看结论" in source
    assert "统一成果（A）" in source
    assert "创业难度与效率（B1）" in source
    assert "组织整合（B2）" in source
    assert "本人统帅与战争解题（C）" in source
    assert 'fetch("data/military/commanders-index.json"' in source
    assert "military.html#commander=" in source
    assert "military.html#search=" in source
    assert "查看相关战役与个人责任" in source


def test_first_item_reader_javascript_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for JavaScript syntax check")
    for relative in ("reader/lazy-details.js", "reader/first-item-reading.js"):
        result = subprocess.run(
            [node, "--check", str(ROOT / relative)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert result.returncode == 0, result.stderr
