from pathlib import Path

import pytest

from reader.build import (
    _attach_b2_public_reader,
    _attach_reader,
    _attach_second_item_c_public_reader,
    axis_projection,
)


def test_fourth_reader_uses_unique_axis_record_without_duplicate_projection():
    from reader.build import _attach_formal_public_reader

    axis = dict(axis='B', public_adjudication_summary='本轴完整裁决与限制。',
                public_evidence_items=[dict(public_label='事实', public_basis='本人采用的材料。', public_boundary='不含后任。')],
                public_boundary='只限本人窗口。')
    row = dict(axis_results=[axis], public_adjudication_summary='总体概述不能代替本轴。',
               public_axis_projections={'B': dict(public_adjudication_summary='过期副本。')})
    projected = _attach_formal_public_reader({}, record=row, axis='B')
    assert projected['reader_summary'] == axis['public_adjudication_summary']
    assert projected['reader_public_evidence_items'] == axis['public_evidence_items']
    projected['reader_public_evidence_items'][0]['public_basis'] = '消费端修改。'
    assert axis['public_evidence_items'][0]['public_basis'] == '本人采用的材料。'
    with pytest.raises(ValueError, match='one authoritative'):
        _attach_formal_public_reader({}, record=row, axis='A')
    row['axis_results'].append(dict(axis))
    with pytest.raises(ValueError, match='one authoritative'):
        _attach_formal_public_reader({}, record=row, axis='B')


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
            "public_story": "主要阶段出现有据可查的实际结果。",
            "public_boundary": "只采用本人时期材料。",
            "public_loss_label": "已证损害，程度范围仍有限定。",
            "public_calculation": "合成用例的换算说明。",
            "public_related_source_refs": [],
            "public_source_note": "本合成用例只检验上游字段逐字投影。",
            "public_adjudication_summary": "当前主要状态与低谷均有独立公开说明。",
            "public_evidence_items": evidence,
        },
    )

    assert projected["reader_public_c"]["public_evidence_items"] == evidence
    assert "reader_full_basis" not in projected
    assert projected['reader_public_c']['public_story'] == projected['reader_story']
    assert projected['reader_how'] == '合成用例的换算说明。'


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
const build=fs.readFileSync('reader/build.py','utf8');
assert.ok(build.includes('"person-reading-notes.js"'));
assert.ok(build.includes('runtime_script_blocks()'));
const copy=JSON.parse(fs.readFileSync('reader/public-copy.json','utf8'));
assert.ok(!copy.some(row=>String(row.to||'').includes('person-reading-notes.js')));
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


def test_representative_projection_passes_existing_formal_fields_without_inference():
    from copy import deepcopy
    row = {
        "axis_code": "C2",
        "source_refs": [],
        "representative_parent_ids": ["P1"],
        "parent_chains": [
            {
                "parent_id": "P1",
                "direction": "MIXED_POSITIVE",
                "intensity": "MI2_LIFECYCLE",
                "attribution": "共享归责，以正式记录为准。",
                "limitations": ["不外推未观察阶段。"],
                "cycle_anchor_refs": ["docs/example.md#L1"],
                "basis": "合成代表情境。",
            }
        ],
    }
    before = deepcopy(row)
    projected = axis_projection(row, [])["representative_contexts"][0]
    source = row["parent_chains"][0]
    for key in ("direction", "intensity", "attribution", "limitations", "cycle_anchor_refs", "basis"):
        assert projected[key] == source[key]
    assert "material_intensity" not in projected
    assert row == before


def test_reader_keeps_authored_total_and_labels_adopted_sources(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const template=fs.readFileSync('reader/index.template.html','utf8');
const source=template.split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify({records:[],source_availability:{}})}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.h={public_total_basis:'合成对象的独立定档理由：旧国家终结，但后继重建不归本人。',public_grade:'B',dimensions:{scope:{grade:'S'}}};
assert.equal(vm.runInContext('impactTotalPublicText(h)',ctx),ctx.h.public_total_basis);
ctx.r={ruler_id:'synthetic',impact:{source_refs:[{kind:'IMPORTED_ADJUDICATION',document:'旧裁决清单.md',section:'合成对象',adopted_excerpt:'保留下来的项目判断。',adoption_limit:'原史未逐句复核。'}],source_trace:{limit:'原文件无法恢复。'}}};
const sourceHtml=vm.runInContext('impactSourceList(r,[0])',ctx);
assert.ok(sourceHtml.includes('项目采纳段落（非古籍原文）'));
assert.ok(sourceHtml.includes('保留下来的项目判断。'));
assert.ok(sourceHtml.includes('原文件无法恢复。'));
assert.ok(sourceHtml.includes('原史未逐句复核。'));
assert.ok(!sourceHtml.includes('href='));
''')


def test_impact_source_cards_expose_scoped_evidence_and_failures_for_current_pool(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const template=fs.readFileSync('reader/index.template.html','utf8');
const source=template.split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const artifact=fs.readFileSync('reader/index.html','utf8');
const data=JSON.parse(artifact.match(/<script[^>]*id="reader-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify(data)}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.r={ruler_id:'SYNTHETIC',ruler_name:'合成对象',impact:{source_refs:[
 {kind:'LOCAL_FORMAL_RECORD',path:'docs/历史审计合成.json',ruler_id:'SYNTHETIC',collection:'scores',field_paths:['state_anchors'],parent_ids:['P1'],evidence_note:'只核对这一事实。',use_scope:'SPATIAL_FACT_CHECK_ONLY'},
 {kind:'HISTORICAL_WEB_SOURCE',title:'目录材料',url:'https://example.org/catalogue',evidence_note:'只有目录，未读正文。',verification_mode:'RETRIEVED_CATALOGUE_OR_ABSTRACT_OFFLINE_NOTE'},
],related_fact_entries:[{kind:'LOCAL_FORMAL_RECORD',path:'docs/unbound.json',ruler_id:'SYNTHETIC'}]}};
let html=vm.runInContext('impactSourceList(r,[0])',ctx);
for(const text of ['历史审计合成.json','scores','state_anchors','P1','只核对这一事实。','仅用于空间事实核对','尚未直接绑定外部原典'])assert.ok(html.includes(text),text);
assert.ok(!html.includes('unbound.json'),'person-level related source must not leak into chain evidence');
html=vm.runInContext('impactSourceList(r,[1])',ctx);
assert.ok(html.includes('只有目录，未读正文。'));
assert.ok(html.includes('仅核对目录或摘要的离线记录'));
assert.ok(!html.includes('尚未直接绑定外部原典'));
html=vm.runInContext('impactSourceList(r,[])',ctx);
assert.ok(html.includes('未为本节单独绑定来源'));
assert.ok(!html.includes('历史审计合成.json'));
for(const indices of [[-1],[9],['0'],null,'bad']){
 ctx.indices=indices;html=vm.runInContext('impactSourceList(r,indices)',ctx);
 if(indices===null)assert.ok(html.includes('未为本节单独绑定来源'));
 else assert.ok(html.includes('来源编号失效'));
}
ctx.r.impact.source_refs[1].verification_mode='FUTURE_MODE';
html=vm.runInContext('impactSourceList(r,[1])',ctx);
assert.ok(html.includes('未识别（FUTURE_MODE）'));
html=vm.runInContext('impactSourceOverview(r)',ctx);
assert.ok(html.includes('不自动充当本节证据'));
assert.ok(html.includes('unbound.json'));
// Full-pool parity uses live authored fields, with no frozen source counts.
let sources=0,chains=0;
for(const file of fs.readdirSync('reader/data/people').filter(f=>f.startsWith('RULER-')||f.startsWith('HIMPACT-'))){
 if(!file.endsWith('.json'))continue;
 ctx.r=JSON.parse(fs.readFileSync('reader/data/people/'+file,'utf8')).record;
 const h=ctx.r.impact;if(!h)continue;
 const before=JSON.stringify(h);
 html=vm.runInContext('impactSourceOverview(r)',ctx);
 for(const s of h.source_refs||[]){
  ctx.s=s;const card=vm.runInContext('impactSourceCard(s,r)',ctx);
  for(const key of ['evidence_note','adopted_excerpt'])if(s[key]){
   ctx.value=s[key];const expected=vm.runInContext(key==='adopted_excerpt'?'esc(value)':'prose(value)',ctx);
   assert.ok(card.includes(expected),file+': '+key);
  }
  for(const key of ['verification_mode','use_scope'])if(s[key]){
   assert.ok(data.impact_source_display[key][s[key]],file+': unknown '+key);
   assert.ok(card.includes(data.impact_source_display[key][s[key]]));
  }
  sources++;
 }
 for(const c of h.macro_chains||[]){
  ctx.indices=c.source_ref_indices;
  const card=vm.runInContext('impactSourceList(r,indices)',ctx);
  assert.ok(!card.includes('来源编号失效'),file+': '+c.chain_id);
  assert.equal(card.includes('尚未直接绑定外部原典'),!c.source_ref_indices.some(i=>h.source_refs[i].kind==='HISTORICAL_WEB_SOURCE'));
  chains++;
 }
 assert.equal(JSON.stringify(h),before);
}
assert.ok(sources>0&&chains>0);
''')
