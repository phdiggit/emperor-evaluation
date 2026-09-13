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


def test_home_interactions_reenhance_dynamic_views_after_route_return():
    script = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "enhanceHomeRows();" in script
    assert "enhancePersonNet();" in script
    assert "new MutationObserver(() =>" in script
    assert ".observe(screen, {childList: true, subtree: true})" in script
    assert ".observe(rows" not in script


def test_net_overview_components_link_to_person_specific_major_pages():
    script = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert '"治国净收益": "second"' in script
    assert '"军事与边疆": "third"' in script
    assert '"奠基与统一附加": "first"' in script
    assert '"文明与国家整合": "fourth"' in script
    assert "function enhanceNetOverview(record)" in script
    assert 'sourceLink.textContent = "查看完整净收益计分页 →"' in script
    assert "#net/${encodeURIComponent(record.ruler_id)}" in script


def test_person_net_construction_is_compact_and_routes_to_dedicated_detail_pages():
    script = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "function compactNetReading(record)" in script
    assert 'details.className = "net-summary-group"' in script
    assert "查看这组完整计分逻辑 →" in script
    assert "打开完整净收益计分页 →" in script
    assert 'first: "first"' in script
    assert 'method: "second"' in script
    assert 'strategic: "third"' in script
    assert 'civilization: "fourth"' in script


def test_net_detail_page_prefers_single_person_logic_over_whole_settlement_documents():
    script = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "当前人物结算逻辑" in script
    assert "当前人物的完整裁决原文" in script
    assert "原始正式文档与史料（审计）" in script
    assert "这些链接指向整份正式文件，供核对使用" in script
    assert "上面的“当前人物结算逻辑”才是面向读者的单人解释" in script
    assert "正式结算与来源" not in script


def test_first_item_detail_page_explains_variables_and_formulas_without_pinning_real_ruler_values():
    script = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert "U = 有效控制信用" in script
    assert "A = 120 × (min(1000, U) / 1000)^0.65" in script
    assert "B1 = 起点难度分 + 对手难度分 + 完成效率分" in script
    assert "B2 = 并行执行分 + 专业覆盖／组织杠杆分 + 异质整合分" in script
    assert "C先按正式证据判统帅档位" in script
    assert "F = 0.20 × 637 × (S1 / 240)^1.25" in script
    assert "U=740" not in script
    assert "嬴政" not in script


def test_net_hash_route_extends_existing_router_without_replacing_other_views():
    script = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8")
    assert 'location.hash.startsWith("#net/")' in script
    assert "const baseRoute = route;" in script
    assert 'window.removeEventListener("hashchange", baseRoute)' in script
    assert "baseRoute();" in script
