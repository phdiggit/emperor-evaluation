"""Reader projection and serving behavior; never pin current adjudication snapshots."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "reader" / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_projection_preserves_reasons_and_deduplicates_sources():
    row = {
        "position_basis": "position reason",
        "source_refs": ["docs/a.md"],
        "counterpattern": {"positive_parent_refs": ["p"]},
        "parent_chains": [{
            "parent_id": "p",
            "cycle_basis": "fact",
            "source_refs": ["docs/a.md", "docs/b.md#L3"],
        }],
    }
    result = module("build").axis_projection(row, ["position_basis", "counterpattern"])
    assert result["position_basis"] == row["position_basis"]
    assert result["source_refs"] == ["docs/a.md", "docs/b.md#L3"]
    assert result["context_lookup"]["p"]["cycle_basis"] == "fact"


def test_overview_keeps_upstream_prudent_rank_projection():
    projection = {
        "best": 2, "worst": 4,
        "method": "OWN_PRUDENT_INTERVAL_VS_OTHER_FORMAL_SCORES",
        "other_scores_fixed": True, "is_joint_rank_interval": False,
    }
    summary = module("build").record_summary({
        "ruler_id": "synthetic", "ruler_name": "示例", "polity": "示例政权",
        "impact": {"dimensions": {}}, "axes": {},
        "net": {"rank": 3, "total_score": 90.0, "prudent_rank_projection": projection},
    })
    assert summary["net"]["prudent_rank_projection"] == projection


def test_unresolved_context_fails_instead_of_silently_losing_evidence():
    with pytest.raises(ValueError, match="Unresolved context"):
        module("build").axis_projection(
            {"counterpattern": {"positive_parent_refs": ["missing"]}},
            [],
        )


def test_method_public_projection_preserves_all_nodes_and_boundaries():
    builder = module("build")
    tail = "正面表现。" * 80 + "但不能据此认定全部责任。"
    nodes = [{"public_label": f"制度{i}", "public_adjudication_basis": tail,
              "public_boundary": f"限制{i}不能删除。", "public_scope": "只含本段。",
              "public_reception": "后续接收尚不确定。"} for i in range(7)]
    a_evidence = [{
        "public_label": node["public_label"],
        "public_direction": "正向",
        "public_basis": "\n\n".join((node["public_adjudication_basis"], node["public_scope"], node["public_reception"])),
        "public_boundary": node["public_boundary"],
    } for node in nodes]
    result = builder._attach_method_public_reader(
        {}, axis="A", record={
            "public_adjudication_summary": tail,
            "public_boundary": "制度建设人物级边界。",
            "public_evidence_items": a_evidence,
        })
    assert result["reader_summary"] == tail
    assert result["reader_public_evidence_items"] == a_evidence
    assert result["reader_boundary"] == "制度建设人物级边界。"
    b1_evidence = [{
        "public_label": "运行链",
        "public_basis": tail,
        "public_boundary": "仅作背景。",
    }]
    result = builder._attach_method_public_reader(
        {}, axis="B1", record={
            "public_adjudication_summary": tail,
            "public_boundary": "仅作背景。",
            "public_evidence_items": b1_evidence,
        })
    assert result["reader_public_evidence_items"] == b1_evidence
    assert result["reader_boundary"] == "仅作背景。"
    with pytest.raises(ValueError, match="public summary"):
        builder._attach_method_public_reader({}, axis="A", record={"adjudication_reason":tail})


def test_document_preserves_duplicate_and_explicit_anchors():
    page = module("serve").document_page(
        "# 标题\n\n## **中文** `代码`\n\n## **中文** `代码`\n\n<a id=\"person-synthetic\"></a>\n"
    ).decode()
    assert 'id="中文-代码"' in page
    assert 'id="中文-代码-1"' in page
    assert 'href="#中文-代码"' in page
    assert 'id="person-synthetic"' in page


def test_document_disallows_active_html_and_remote_images():
    page = module("serve").document_page(
        "# Safe\n\n<script>alert(1)</script>\n\n![image](https://example.com/image.png)\n"
    ).decode()
    assert "<script>alert(1)</script>" not in page
    assert "<img" not in page


def test_source_path_accepts_existing_line_citation_formats():
    builder = module("build")
    assert builder.source_file("docs/中文.md:42") == "docs/中文.md"
    assert builder.source_file("docs/中文.md#L42-L45") == "docs/中文.md"


def test_json_http_view_preserves_raw_and_uses_logical_loader(tmp_path, monkeypatch):
    from functools import partial
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import urlopen

    server_module = module("serve")
    original = b'{"router":true}'
    (tmp_path / "source.json").write_bytes(original)
    logical = {"records": [{"ruler_id": "synthetic", "value": 0}]}
    monkeypatch.setattr(server_module, "load_json", lambda path: logical)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(server_module.ReaderHandler, directory=str(tmp_path)),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/source.json"
        with urlopen(url) as response:
            assert response.headers.get_content_type() == "text/html"
            body = response.read().decode()
            embedded = body.split('id="json-data">')[1].split("</script>")[0]
            assert json.loads(embedded) == logical
        with urlopen(url + "?raw=1") as response:
            assert response.read() == original
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

def test_home_simple_cards_use_three_full_column_targets():
    template = (ROOT / "reader" / "index.template.html").read_text(encoding="utf-8")
    start = template.index(" const simple=()=>")
    end = template.index(" const full=()=>", start)
    simple = template[start:end]
    assert 'home-eval-card home-eval-net' in simple
    assert 'home-eval-card home-eval-profile' in simple
    assert 'home-eval-card home-eval-impact' in simple
    assert 'data-home-section="person-outcome"' in simple
    assert 'data-home-section="person-capability"' in simple
    assert 'data-home-section="person-impact"' in simple
    assert "homeProfileSummary(r)" in simple
    assert "home-profile-static" in simple
    assert "homePrudentRank(r.net)" in simple
    assert "home-simple-action" not in simple
    assert "home-simple-compare" not in simple
    assert "data-home-grade" not in simple

    css = (ROOT / "reader" / "readability.css").read_text(encoding="utf-8")
    assert "Home result-card redesign" in css
    assert ".home-eval-net:hover" in css
    assert ".home-impact-mark .impact-grade" in css


def test_home_system_columns_route_to_distinct_reading_paths():
    source = (ROOT / "reader" / "home-interactions.js").read_text(encoding="utf-8")
    assert 'section === "person-outcome"' in source
    assert '#net/${encoded}/all' in source
    assert 'section === "person-capability"' in source
    assert '#person/${encoded}/profile' in source
    assert 'section === "person-impact"' in source
    assert '#person/${encoded}/impact' in source
    template = (ROOT / "reader" / "index.template.html").read_text(encoding="utf-8")
    assert "const personView=" in template
    assert "function profilePage(r)" in template
    assert "function impactPage(r)" in template
    assert "personSystemNav(r,'overview')" in template


def test_reader_explains_rank_uncertainty_without_overloading_compare_row():
    template = (ROOT / "reader" / "index.template.html").read_text(encoding="utf-8")
    compare_start = template.index("function compare(){")
    compare_end = template.index("function guide()", compare_start)
    compare = template[compare_start:compare_end]
    for phrase in ("正式绩效", "审慎位置投影", "治理背景（非计分）", "史料与权重说明", "审慎位置固定权重"):
        assert phrase in compare
    for phrase in ("正式名次、审慎位置与治理背景", "不是统计置信区间", "不是所有人物同时变化后的联合名次区间", "与史料不确定性是两条不同问题", "当前不计分、不加难度奖励", "net-position-summary"):
        assert phrase in template


def test_net_detail_uses_same_system_navigation_as_profile_and_impact():
    source = (ROOT / "reader" / "home-interactions.js").read_text(encoding="utf-8")
    start = source.index("function renderNetShell")
    end = source.index("function renderNetLanding", start)
    block = source[start:end]
    assert 'typeof personSystemNav === "function"' in block
    assert 'personSystemNav(record, "net")' in block
    assert "${systemNav}${majorNav(record, active)}" in block
