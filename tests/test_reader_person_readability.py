from pathlib import Path

from reader.build import _attach_reader, axis_projection


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


def test_net_explanation_projection_uses_formal_text_without_fixed_ruler_values():
    item = {
        "label": "测试判断项",
        "value": 12.5,
        "unit": "分",
        "source": "docs/评分结算/测试.json",
    }
    formal = {
        "grade_basis": "第一句正式裁决。第二句继续说明。第三句属于完整原文。",
        "M_positive_profile": [{"mechanism": "已闭合的正向机制"}],
        "material_limitations": ["现有材料仍有明确边界"],
        "source_refs": ["docs/史料通读产物/测试.md#L10"],
    }
    projected = _attach_reader(item, kind="judgment", record=formal, how="固定公式换算为12.5分。")
    assert projected["reader_kind"] == "judgment"
    assert projected["reader_summary"] == "第一句正式裁决。第二句继续说明。"
    assert projected["reader_full_basis"] == formal["grade_basis"]
    assert projected["reader_highlights"] == ["已闭合的正向机制"]
    assert projected["reader_boundary"] == "现有材料仍有明确边界"
    assert projected["reader_how"] == "固定公式换算为12.5分。"
    assert projected["reader_source_refs"] == [
        "docs/评分结算/测试.json",
        "docs/史料通读产物/测试.md#L10",
    ]


def test_person_readability_layer_is_embedded_and_uses_dynamic_fields():
    html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
    assert "function enhanceAxis(details, axisCode, axis)" in html
    assert "function publicAxisMetadata()" in html
    assert "function rewriteHistoryChains(impact)" in html
    assert "function enhanceImpact(record)" in html
    assert "function foldNetLedger()" in html
    assert "function normalizeEvidenceCardHeadings()" in html
    assert "function buildNetReading(record)" in html
    assert "const impactPublicText = value =>" in html
    assert "const historyPublicText = value =>" in html
    assert "const netPublicText = value =>" in html
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


def test_net_reader_separates_judgment_calculation_and_audit_sources():
    script = (ROOT / "reader/person-readability.js").read_text(encoding="utf-8")
    assert 'item.reader_kind === "judgment"' in script
    assert 'item.reader_kind === "calculation"' in script
    assert "为什么这样评" in script
    assert "这一组怎么算出来？" in script
    assert "这个分怎么算？" in script
    assert "正式记录与史料" in script
    assert "正式评分记录 ↗" in script
    assert "采用值记录 ↗" in script
    assert "完整计分账本（审计视图）" in script
    assert "小计、折算和总计属于计算过程" in script
    assert "评分依据 ↗" not in script


def test_generated_net_components_have_reader_roles_without_pinning_ruler_values():
    import json

    detail_files = sorted((ROOT / "reader/data/people").glob("*.json"))
    assert detail_files
    found = False
    for path in detail_files:
        record = json.loads(path.read_text(encoding="utf-8"))["record"]
        if not record.get("net"):
            continue
        items = [
            item
            for group in record["net"].get("component_details", {}).values()
            for item in group
        ]
        assert items
        assert all(item.get("reader_kind") in {"judgment", "calculation"} for item in items)
        assert any(item.get("reader_summary") for item in items if item.get("reader_kind") == "judgment")
        assert any(item.get("reader_how") for item in items)
        found = True
        break
    assert found
