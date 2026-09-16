import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def bootstrap_data():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    encoded = html.split('<script type="application/json" id="reader-data">')[1].split("</script>")[0]
    return json.loads(encoded)


def test_first_item_reader_uses_build_time_source_cache_once():
    lazy = (ROOT / "reader/lazy-details.js").read_text(encoding="utf-8")
    public_copy = (ROOT / "reader/public-copy.json").read_text(encoding="utf-8")
    assert "data/first-item/" in lazy
    assert "First-item source cache unavailable" in lazy
    assert 'script.src = "first-item-reading.js"' not in lazy
    assert 'script.src = "first-item-boundary-notes.js"' not in lazy
    assert public_copy.count('first-item-reading.js') == 1
    assert public_copy.count('first-item-boundary-notes.js') == 1


def test_first_item_reader_cache_matches_current_applicable_pool():
    data = bootstrap_data()
    applicable = {
        row["ruler_id"]: row["ruler_name"]
        for row in data["records"]
        if (row.get("net") or {}).get("first_item_status") == "APPLICABLE"
    }
    cache_dir = ROOT / "reader/data/first-item"
    cached = {path.stem: path for path in cache_dir.glob("*.json")}
    assert applicable
    assert set(cached) == set(applicable)
    expected_documents = {"A统一贡献", "B1创业难度与效率", "B2组织与整合", "C军事统帅与战争解题"}
    for ruler_id, name in applicable.items():
        payload = json.loads(cached[ruler_id].read_text(encoding="utf-8"))
        assert payload["ruler_id"] == ruler_id
        assert payload["ruler_name"] == name
        assert payload["formal_name"]
        assert set(payload["documents"]) == expected_documents
        for markdown in payload["documents"].values():
            assert f". {payload['formal_name']}\n" in markdown
    contract = (cache_dir / "contract.md").read_text(encoding="utf-8")
    assert "### 4.1 并行执行能力" in contract
    assert "### 4.2 专业覆盖与组织杠杆" in contract
    assert "### 4.3 异质整合能力" in contract
    assert "## 7. 逐人主链边界" in contract
    assert "## 8. 执行与审计" in contract


def test_reader_name_alias_for_wanyan_sheng_is_explicit():
    builder = (ROOT / "reader/build_first_item_reader_cache.py").read_text(encoding="utf-8")
    assert '"完颜晟": "完颜吴乞买"' in builder
