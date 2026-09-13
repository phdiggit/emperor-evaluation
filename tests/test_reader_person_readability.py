from pathlib import Path

from reader.build import axis_projection


ROOT = Path(__file__).resolve().parents[1]


def test_c4_projection_uses_declared_representative_contexts_without_fixed_ruler_values():
    row = {
        "axis_code": "C4",
        "source_refs": [],
        "representative_parent_ids": ["P1"],
        "parent_chains": [
            {
                "parent_id": "P1",
                "title": "代表性制度情境",
                "mechanism": "一段用于测试展示投影的制度机制。",
                "direction": "MIXED",
            },
            {
                "parent_id": "P2",
                "title": "非代表情境",
                "mechanism": "不应进入代表性展示投影。",
                "direction": "POSITIVE",
            },
        ],
    }
    projection = axis_projection(row, [])
    assert projection["representative_contexts"] == [
        {
            "parent_id": "P1",
            "title": "代表性制度情境",
            "mechanism": "一段用于测试展示投影的制度机制。",
            "direction": "MIXED",
        }
    ]


def test_c5_projection_keeps_existing_public_evidence_without_re_adjudication():
    row = {
        "axis_code": "C5",
        "source_refs": [],
        "public_evidence_points": [
            {
                "title": "代表性证据",
                "details": ["已有正式记录中的第一条说明。", "已有正式记录中的第二条说明。"],
            }
        ],
        "parent_chains": [],
    }
    projection = axis_projection(row, [])
    assert projection["public_evidence_points"] == row["public_evidence_points"]


def test_person_readability_layer_is_embedded_and_uses_dynamic_fields():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    assert "function enhanceAxis(details, axisCode, axis)" in html
    assert "function publicAxisMetadata()" in html
    assert "function rewriteHistoryChains(impact)" in html
    assert "function enhanceImpact(record)" in html
    assert "function foldNetLedger()" in html
    assert "function normalizeEvidenceCardHeadings()" in html
    assert "function addNetSourceLinks(record)" in html
    assert "const impactPublicText = value =>" in html
    assert "const historyPublicText = value =>" in html
    assert "C5越接近S，表示越能在压力和个人利益面前约束自身权力" in html
    assert "它描述权力风格，不计入八项能力雷达" in html
    assert "公开等级：${grade(axis)}" in html
    assert "专业信息与正式记录" in html
    assert "基础影响量级" in html
    assert "最终等级" in html
    assert "joint_footprint_basis" in html
    assert "representative_contexts" in html
    assert "public_evidence_points" in html


def test_evidence_cards_share_one_heading_style_without_fixed_ruler_data():
    script = (ROOT / "reader/person-readability.js").read_text(encoding="utf-8")
    css = (ROOT / "reader/readability.css").read_text(encoding="utf-8")
    assert '["净收益构成", "人物画像依据", "历史影响依据"]' in script
    assert 'replacement = document.createElement("h2")' in script
    assert 'replacement.className = "evidence-card-title"' in script
    assert ".evidence-card-title" in css


def test_net_components_link_to_existing_formal_sources_without_fixed_ruler_data():
    script = (ROOT / "reader/person-readability.js").read_text(encoding="utf-8")
    assert 'Object.entries(record.net?.component_details || {})' in script
    assert 'link(item.source, "评分依据 ↗", record)' in script
    assert 'link(item.applied_source, "采用值来源 ↗", record)' in script
    assert 'toggle.textContent = "完整计分明细与依据"' in script
    assert '对应的正式评分依据' in script
