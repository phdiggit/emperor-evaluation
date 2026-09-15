from reader.build import _attach_reader, axis_projection


def test_c4_projection_uses_declared_representative_contexts():
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


def test_net_explanation_projection_uses_formal_text():
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
    projected = _attach_reader(
        item,
        kind="judgment",
        record=formal,
        how="固定公式换算为12.5分。",
    )
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



def test_history_impact_reader_uses_formal_dimension_fields_without_audit_copy():
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    template = (root / "reader" / "index.template.html").read_text(encoding="utf-8")
    public_js = (root / "reader" / "person-readability.js").read_text(encoding="utf-8")
    build = (root / "reader" / "build.py").read_text(encoding="utf-8")

    assert "h.scope_assessment||h.scope_review" in template
    assert "scopeReview.actual_changes" in template
    assert "scopeReview.baseline_and_exclusions" in template
    assert "source_review_scope" not in template
    assert "source_trace?.limit" not in template
    assert "${prose(r.impact.historical_source_notes)}" not in template
    assert "s.evidence_note" not in template
    assert "impact_dimension_grades" in template
    assert "impact_dimension_grades=impact_config" in build
    assert "historySections(r,idSuffix='',compact=false)" in template
    assert "historySections(r,`-compare-${i}`,true)" in template
    assert "impact-evidence-fold" in template
    assert "foldHistoricalImpact" not in public_js
    assert "historyReaderText(value)" in public_js
    assert "scopeGradeMeaning" in template
    assert "scopeUpperMeaning" in template
    assert "scopeChainFacts" in template
    assert "scopeFactClauses" in template
    assert "scopeCausalTerms" in template
    assert "scopeRelevantChains" in template
    assert "scopeChains.flatMap(c=>c.source_ref_indices||[])" in template
    assert "不可替代|可替代|拍板|臣僚|团队|前制" in template
    assert "scopeReview.actual_changes||scopeChainFacts(chains)" in template
    assert "为什么是 ${esc(scopeGrade)}" in template
    assert "为什么没有更高" in template
    assert "补证与边界|补证|复核|重审|修订|更新" in template


def test_historical_impact_contract_version_metadata_matches_current_contract():
    import json
    import yaml

    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    project = yaml.safe_load((root / "config" / "project.yml").read_text(encoding="utf-8"))
    router = json.loads((root / "docs" / "评分结算" / "历史影响" / "01-历史影响正式结算.json").read_text(encoding="utf-8"))

    assert project["historical_impact_assessment"]["contract_version"] == "FORMAL-V1.5"
    assert router["payload_metadata"]["contract_version"] == "FORMAL-V1.5"
