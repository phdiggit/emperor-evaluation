from reader.build import (
    _attach_b2_public_reader,
    _attach_reader,
    _attach_second_item_c_public_reader,
    axis_projection,
)


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
        summary=formal["grade_basis"],
        highlights=[node["mechanism"] for node in formal["M_positive_profile"]],
        boundary="\n\n".join(formal["material_limitations"]),
        source_refs=formal["source_refs"],
        how="固定公式换算为12.5分。",
    )
    assert projected["reader_kind"] == "judgment"
    assert projected["reader_summary"] == formal["grade_basis"]
    assert "reader_full_basis" not in projected
    assert projected["reader_highlights"] == ["已闭合的正向机制"]
    assert projected["reader_boundary"] == "现有材料仍有明确边界"
    assert projected["reader_how"] == "固定公式换算为12.5分。"
    assert projected["reader_source_refs"] == [
        "docs/评分结算/测试.json",
        "docs/史料通读产物/测试.md#L10",
    ]


def test_b2_reader_projection_consumes_all_explicit_public_evidence():
    evidence = [
        {
            "id": f"B2-PUBLIC-{index}",
            "public_label": f"机制{index}",
            "public_direction": "正向",
            "public_tags": ["反馈与纠错"],
            "public_basis": f"机制{index}形成实际结果。",
            "public_boundary": "同一机制只作一次判断。",
        }
        for index in range(4)
    ]
    projected = _attach_b2_public_reader(
        {"label": "B2反馈与约束", "value": 38.0, "source": "docs/评分结算/测试.json"},
        record={
            "ruler_name": "合成甲",
            "public_adjudication_summary": "主要反馈机制能够改变决策，整体判断为中档（中位）。",
            "public_evidence_items": evidence,
        },
    )

    assert projected["reader_summary"].startswith("主要反馈机制")
    assert projected["reader_public_evidence_items"] == evidence
    assert len(projected["reader_highlights"]) == 4
    assert "reader_full_basis" not in projected


def test_c_reader_projection_consumes_all_explicit_public_evidence():
    evidence = [
        {
            "id": f"C1-PUBLIC-{index}",
            "public_label": label,
            "public_role": role,
            "public_basis": f"{label}的正式公开依据。",
            "public_boundary": "本轴只展示本轴结果，不重复计算其他结果。",
        }
        for index, (label, role) in enumerate(
            [("主要状态", "主要状态"), ("低谷与损失", "低谷"), ("评价边界", "边界")]
        )
    ]
    projected = _attach_second_item_c_public_reader(
        {"label": "C1民生", "value": 32.0, "source": "docs/评分结算/测试.json"},
        axis="C1",
        record={
            "ruler_name": "合成甲",
            "public_adjudication_summary": "当前主要状态与低谷均有独立公开说明。",
            "public_evidence_items": evidence,
        },
    )

    assert projected["reader_public_evidence_items"] == evidence
    assert len(projected["reader_highlights"]) == len(evidence)
    assert "reader_full_basis" not in projected


def test_historical_impact_contract_version_metadata_matches_current_contract():
    import json
    import yaml

    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    project = yaml.safe_load((root / "config" / "project.yml").read_text(encoding="utf-8"))
    router = json.loads((root / "docs" / "评分结算" / "历史影响" / "01-历史影响正式结算.json").read_text(encoding="utf-8"))

    project_version = project["historical_impact_assessment"]["contract_version"]
    router_version = router["payload_metadata"]["contract_version"]
    assert project_version == router_version
    assert project_version.startswith("FORMAL-V")


def _run_reading_notes_node(tmp_path, body):
    import shutil
    import subprocess
    from pathlib import Path
    import pytest

    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for reader behavior')
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / 'person-notes.cjs'
    script.write_text("const assert=require('node:assert/strict');\n"
                      "const api=require(process.cwd()+'/reader/person-reading-notes.js');\n" + body,
                      encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=root, capture_output=True,
                            text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_person_note_locators_are_local_and_never_pin_scores(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const record={axes:{C5:{typical_pattern:'合成事项：复核改变了一项决定。',axis_grade:'G3'}},net:{total_score:10}};
const block={text:'一段根据明确事件撰写的提要。',evidence:[{path:['axes','C5','typical_pattern'],quote:'复核改变了一项决定'}]};
api.validateBlock(block);
const before=JSON.stringify(record);
assert.equal(api.assessBlock(block,record).status,'current');
assert.equal(JSON.stringify(record),before);
record.axes.C5.axis_grade='G4';record.net.total_score=20;
assert.equal(api.assessBlock(block,record).status,'current','a lawful regrade must not freeze a factual note');
record.axes.C5.typical_pattern='这项材料已撤回。';
record.axes.C1={typical_pattern:'复核改变了一项决定'};
assert.equal(api.assessBlock(block,record).status,'needs_review','same words on another axis are not a valid source');
assert.equal(api.assessBlock(block,{}).status,'needs_review');
for(const path of [['axes','C5','axis_grade'],['net','total_score'],['__proto__','anything'],
 ['impact','constructor','name'],['axes','C5'],['net','reader_governance_summary']])assert.equal(api.validPath(path),false);
assert.equal(api.resolve({},['constructor']),undefined);
''')


def test_person_notes_require_complete_sections_and_plain_prose(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const b=()=>({text:'合成的事实与边界。',evidence:[{path:['impact','public_boundary'],quote:'合成来源'}]});
const payload={schema_id:'reader-person-overviews-v2',records:{'RULER-SYNTHETIC':{
 overview:{outcome:b(),profile:b(),impact:b()}}}};
api.validateNotes(payload);
const copy=JSON.parse(JSON.stringify(payload));delete copy.records['RULER-SYNTHETIC'].overview.impact;
assert.throws(()=>api.validateNotes(copy),/three overview/);
for(const extra of ['axes','strength','weight','role','limits']){
 const invalid=JSON.parse(JSON.stringify(payload));invalid.records['RULER-SYNTHETIC'][extra]={};
 assert.throws(()=>api.validateNotes(invalid),/Only overview/);
 assert.throws(()=>api.validateBlock({...b(),[extra]:'自行分类'}),/prose/);
}
assert.throws(()=>api.validateBlock({...b(),evidence:[{...b().evidence[0],strength:'强'}]}),/locator/);
assert.throws(()=>api.validateBlock({...b(),evidence:[]}),/needs evidence/);
assert.throws(()=>api.validateBlock({...b(),text:'<img src=x>'}),/prose/);
assert.throws(()=>api.validateBlock({...b(),text:'使用MI3替代事实。'}),/prose/);
for(const code of ['C5','C1','M1','M2','M4','M5'])assert.throws(()=>api.validateBlock({...b(),text:code+'是内部编号。'}),/prose/);
// Locator quotations remain the unmodified source wording, including internal codes.
api.validateBlock({text:'使用中文名称。',evidence:[{path:['axes','C5','typical_pattern'],quote:'C5原始记录'}]});
assert.throws(()=>api.validateNotes({...payload,schema_id:'unknown'}),/schema/);
''')


def test_person_notes_use_current_sources_without_snapshot_expectations(tmp_path):
    """Check typed sources/identity. A withdrawn anchor marks only its prose stale."""
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs');
const payload=api.validateNotes(JSON.parse(fs.readFileSync('reader/person-reading-notes.json','utf8')));
let current=0,needsReview=0;
for(const [id,notes] of Object.entries(payload.records)){
 const record=JSON.parse(fs.readFileSync('reader/data/people/'+id+'.json','utf8')).record;
 assert.equal(record.ruler_id,id);
 const before=JSON.stringify(record);
 for(const block of Object.values(notes.overview)){
  const result=api.assessBlock(block,record);
  assert.ok(['current','needs_review'].includes(result.status));
  if(result.status==='current')current++;else needsReview++;
  for(const ref of block.evidence){
   if(ref.path[0]==='net'){
    const item=record.net?.component_details?.[ref.path[2]]?.[ref.path[3]];
    if(item)assert.ok(typeof item.source==='string' && item.source.startsWith('docs/'));
   }
  }
 }
 assert.equal(JSON.stringify(record),before);
}
// Counts are reported, not fixed against a historical editorial batch.
console.log(JSON.stringify({current,needsReview}));
const copy=JSON.parse(fs.readFileSync('reader/public-copy.json','utf8'));
assert.ok(copy.some(row=>row.to.includes('src="person-reading-notes.js"')));
''')


def test_c5_projection_passes_formal_strength_without_filling_missing_values():
    from copy import deepcopy
    row = {
        "axis_code": "C5", "source_refs": [],
        "counterpattern": {"negative_parent_refs": ["P1", "P2", "P3"]},
        "parent_chains": [
            {"parent_id": "P1", "intensity": "MI2_LIFECYCLE", "direction": "NEGATIVE", "basis": "合成记录甲。"},
            {"parent_id": "P2", "material_intensity": "FUTURE_CODE", "basis": "合成记录乙。"},
            {"parent_id": "P3", "basis": "叙述包含多年、跨阶段甚至MI4，但未裁定强度。"},
        ],
    }
    before = deepcopy(row)
    lookup = axis_projection(row, [])['context_lookup']
    for source in row['parent_chains']:
        projected = lookup[source['parent_id']]
        for key in ('intensity', 'material_intensity', 'direction', 'basis'):
            assert (key in projected) == (key in source)
            if key in source:
                assert projected[key] == source[key]
    assert row == before


def test_c5_current_contexts_match_formal_strength_and_prose():
    """Source equality, not any frozen value or distribution of real rulers."""
    from pathlib import Path
    from emperor_v4.evaluation.formal_json_store import load_json
    from emperor_v4.evaluation.profile_parent_schema import parent_chains
    import yaml
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / 'config/project.yml').read_text(encoding='utf-8'))
    source = root / config['profile_assessment']['settled_axes']['C5']['json']
    for row in load_json(source)['records']:
        lookup = axis_projection(row, []).get('context_lookup', {})
        originals = {p['parent_id']: p for p in parent_chains(row)}
        for parent_id, projected in lookup.items():
            original = originals[parent_id]
            for key in ('intensity', 'material_intensity', 'direction', 'basis', 'cycle_basis'):
                assert (key in projected) == (key in original)
                if key in original:
                    assert projected[key] == original[key]
