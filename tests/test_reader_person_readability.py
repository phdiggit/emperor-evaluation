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
  assert.equal(result.status,'current',id+': overview reference is stale');
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


def test_representative_projection_keeps_authored_lifecycle():
    row = {
        'representative_parent_ids': ['P1'],
        'parent_chains': [{'parent_id': 'P1', 'evidence_title': '受任与反馈',
                           'lifecycle_narrative': '先授实权，后来军情未能上达。',
                           'source_refs': ['docs/synthetic.md']}],
    }
    projected = axis_projection(row, [])['representative_contexts'][0]
    for key in ('evidence_title', 'lifecycle_narrative', 'source_refs'):
        assert projected[key] == row['parent_chains'][0][key]
    assert 'direction' not in projected


def test_talent_context_uses_authored_items_and_compact_metadata(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('reader/index.template.html','utf8').split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify({records:[],source_availability:{}})}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.c={parent_id:'synthetic',evidence_title:'用人经历',direction:'MIXED',evidence_detail:['行政分工：负责人按专业分任。','军事任用：反馈后调整权限。','<script>：必须转义。'],lifecycle_narrative:'完整过程中的额外限制仍需保留。',boundary_review:{c5_excluded:'处罚比例另行判断。'},source_refs:['docs/synthetic.md']};
const original=JSON.stringify(ctx.c);
let html=vm.runInContext("formalContextStory(c,'synthetic',{axisCode:'C3'})",ctx);
assert.equal((html.match(/class="talent-evidence-item"/g)||[]).length,ctx.c.evidence_detail.length);
assert.ok(html.includes('<h5>行政分工</h5>'));
assert.ok(html.includes('负责人按专业分任。'));
assert.ok(html.includes('&lt;script&gt;'));
assert.ok(!html.includes('<script>'));
assert.equal((html.match(/<summary>/g)||[]).length,1);
const footer=html.indexOf('<details class="metadata talent-context-sources">');
assert.ok(footer>html.indexOf('军事任用'));
assert.ok(html.indexOf('正负混合')>footer);
assert.ok(html.indexOf('处罚比例另行判断。')>footer);
assert.ok(html.includes(ctx.c.lifecycle_narrative));
assert.ok(html.includes('docs/synthetic.md'));
assert.equal(JSON.stringify(ctx.c),original);
delete ctx.c.evidence_detail;
html=vm.runInContext("formalContextStory(c,'synthetic',{axisCode:'C3'})",ctx);
assert.ok(html.includes(ctx.c.lifecycle_narrative));
''')


def test_talent_layout_preserves_all_current_cases_and_keeps_metadata_secondary(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const template=fs.readFileSync('reader/index.template.html','utf8');
const source=template.split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const artifact=fs.readFileSync('reader/index.html','utf8');
const data=JSON.parse(artifact.match(/<script[^>]*id="reader-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify(data)}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
for(const record of data.records.filter(r=>!r.supplementary)){
 const r=JSON.parse(fs.readFileSync('reader/data/people/'+record.ruler_id+'.json','utf8')).record;
 for(const c of r.axes.C3.representative_contexts||[]){
  ctx.c=c;
  const html=vm.runInContext("formalContextStory(c,c.parent_id,{axisCode:'C3'})",ctx);
  const footer=html.indexOf('<details class="metadata talent-context-sources">');
  assert.ok(footer>=0,record.ruler_id);
  assert.ok(!html.slice(0,footer).includes('context-direction'),record.ruler_id);
  assert.equal((html.match(/class="talent-evidence-item"/g)||[]).length,(c.evidence_detail||[]).length,record.ruler_id);
  const plain=html.replace(/<[^>]*>/g,'');
  for(const item of c.evidence_detail||[]){
   ctx.item=item;
   const body=vm.runInContext("(()=>{const t=profilePublicPattern(item),i=t.indexOf('：');return esc(i>0&&i<=48?t.slice(i+1):t)})()",ctx);
   assert.ok(plain.includes(body),record.ruler_id+': missing authored evidence');
  }
 }
 ctx.r=r;
 const axis=vm.runInContext("axisEvidence(r,'C3')",ctx);
 if(r.axes.C3.counterpattern){
  const judgment=axis.indexOf('<details class="metadata adjudication">');
  assert.ok(judgment>=0,record.ruler_id);
  assert.ok(!axis.slice(0,judgment).includes('<div class="label">反例与限制</div>'),record.ruler_id);
 }
}
''')


def test_power_style_cases_are_readable_without_an_extra_disclosure(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('reader/index.template.html','utf8').split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const artifact=fs.readFileSync('reader/index.html','utf8');
const data=JSON.parse(artifact.match(/<script[^>]*id="reader-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify(data)}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
for(const entry of data.records.filter(r=>!r.supplementary)){
 ctx.r=JSON.parse(fs.readFileSync('reader/data/people/'+entry.ruler_id+'.json','utf8')).record;
 const before=JSON.stringify(ctx.r);
 const html=vm.runInContext("axisEvidence(r,'C5')",ctx);
 const points=ctx.r.axes.C5.public_evidence_points;
 assert.equal((html.match(/class="power-evidence-case"/g)||[]).length,points.length,entry.ruler_id);
 assert.ok(!html.includes('<details class="public-evidence-points">'),entry.ruler_id);
 const footer=html.indexOf('<details class="metadata power-context-index">');
 assert.ok(footer>html.indexOf('power-evidence-points'),entry.ruler_id);
 const readable=html.slice(0,footer).replace(/<[^>]*>/g,'');
 for(const point of points){
  ctx.title=point.title;
  assert.ok(readable.includes(vm.runInContext('esc(profilePublicPattern(title))',ctx)),entry.ruler_id);
  for(const detail of point.details){
   ctx.detail=detail;
   assert.ok(readable.includes(vm.runInContext('esc(profilePublicPattern(detail))',ctx)),entry.ruler_id);
  }
 }
 assert.equal(JSON.stringify(ctx.r),before);
}
''')


@pytest.mark.parametrize('axis', ['C1', 'C3', 'M4', 'M5'])
def test_formal_context_process_matches_current_source_for_entire_axis(axis):
    import json
    import yaml
    from reader.build import ROOT, FORMAL_CONTEXT_FIELDS, load_json
    from emperor_v4.evaluation.profile_parent_schema import representative_parent_chains

    project = yaml.safe_load((ROOT / 'config/project.yml').read_text(encoding='utf-8'))
    spec = project['profile_assessment']['settled_axes'][axis]
    for row in load_json(ROOT / spec['json'])['records']:
        projected = axis_projection(row, [])
        expected = [{key: context[key] for key in FORMAL_CONTEXT_FIELDS if key in context}
                    for context in representative_parent_chains(row)]
        assert projected['representative_contexts'] == expected, row['ruler_id']
        record = json.loads((ROOT / 'reader/data/people' / (row['ruler_id'] + '.json')).read_text(encoding='utf-8'))['record']
        assert record['axes'][axis]['representative_contexts'] == expected, row['ruler_id']
        for context in expected:
            if axis == 'C3':
                assert context.get('lifecycle_narrative'), (row['ruler_id'], context['parent_id'])
            elif axis == 'M4':
                assert context.get('coalition_task') and context.get('exit_result'), (row['ruler_id'], context['parent_id'])
            elif axis == 'M5':
                assert context.get('process_narrative'), (row['ruler_id'], context['parent_id'])
            else:
                assert context.get('cycle_basis'), (row['ruler_id'], context['parent_id'])


def test_strategy_context_preserves_process_and_separates_non_scoring_material(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('reader/index.template.html','utf8').split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify({records:[],source_availability:{}})}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.c={parent_id:'positive',direction:'POSITIVE',consumption_status:'SCORING_PARENT',evidence_title:'选择 <与> 反馈',cycle_basis:'先确定可执行目标。\n\n反馈到达后收缩投入。',boundary_review:{归责:'执行由臣下承担。'},source_refs:['docs/synthetic.md']};
const before=JSON.stringify(ctx.c);
let html=vm.runInContext("formalContextStory(c,c.parent_id,{axisCode:'C1'})",ctx);
assert.ok(html.includes('<h4 class="public-context-title">选择 &lt;与&gt; 反馈</h4>'));
const footer=html.indexOf('<details class="metadata strategy-context-sources">');
for(const sentence of ['先确定可执行目标。','反馈到达后收缩投入。'])assert.ok(html.indexOf(sentence)<footer);
assert.ok(html.indexOf('context-direction')>footer);
assert.ok(html.indexOf('计分情境')>footer);
assert.ok(html.indexOf('执行由臣下承担。')>footer);
assert.ok(html.includes('docs/synthetic.md'));
assert.equal(JSON.stringify(ctx.c),before);
ctx.a={counterpattern:{positive_parent_refs:['positive'],counter_parent_refs:[]},context_lookup:{positive:ctx.c},representative_contexts:[ctx.c,{parent_id:'boundary',consumption_status:'BACKGROUND_VALIDATION',direction:'LIMITATION',cycle_basis:'此事有共享归责，不能认定独立周期。'}]};
html=vm.runInContext("contexts(a,true,'C1')",ctx);
const boundary=html.indexOf('<details class="metadata strategy-boundary-contexts">');
assert.ok(boundary>0);
assert.ok(html.indexOf('此事有共享归责')>boundary);
assert.equal((html.match(/先确定可执行目标/g)||[]).length,1);
assert.ok(!html.slice(0,boundary).includes('此事有共享归责'));
ctx.a.representative_contexts.push({parent_id:'additional',consumption_status:'SCORING_PARENT',direction:'POSITIVE',cycle_basis:'另一计分过程仍须显示。'});
html=vm.runInContext("contexts(a,true,'C1')",ctx);
assert.ok(html.includes('其他计分代表情境'));
assert.ok(html.indexOf('另一计分过程')<html.indexOf('strategy-boundary-contexts'));
''')


def test_strategy_layout_keeps_every_current_representative_process(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const template=fs.readFileSync('reader/index.template.html','utf8');
const source=template.split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const artifact=fs.readFileSync('reader/index.html','utf8');
const data=JSON.parse(artifact.match(/<script[^>]*id="reader-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify(data)}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
for(const entry of data.records.filter(r=>!r.supplementary)){
 const record=JSON.parse(fs.readFileSync('reader/data/people/'+entry.ruler_id+'.json','utf8')).record;
 ctx.a=record.axes.C1;
 const before=JSON.stringify(ctx.a);
 const html=vm.runInContext("contexts(a,true,'C1')",ctx);
 for(const c of ctx.a.representative_contexts||[]){
  assert.ok(html.includes(c.parent_id),entry.ruler_id+': '+c.parent_id);
  ctx.c=c;
  const own=vm.runInContext("formalContextStory(c,c.parent_id,{axisCode:'C1'})",ctx);
  const footer=own.indexOf('<details class="metadata strategy-context-sources">');
  assert.ok(footer>=0,entry.ruler_id);
  const plain=own.slice(0,footer).replace(/<[^>]*>/g,'');
  for(const sentence of c.cycle_basis.split(/[。；\n]/).filter(s=>s.trim())){
   ctx.s=sentence.trim();
   const expected=vm.runInContext('esc(profilePublicPattern(s))',ctx);
   assert.ok(plain.includes(expected),entry.ruler_id+': missing '+c.parent_id+': '+expected);
  }
 }
 assert.equal(JSON.stringify(ctx.a),before);
}
''')


def test_organization_context_uses_authored_sections_and_compact_metadata(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('reader/index.template.html','utf8').split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify({records:[],source_availability:{}})}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.c={parent_id:'synthetic-organization',title:'运输 <与> 前线',process_narrative:'任务分解：运输与前线分别负责。\n故障后重配权限，后续恢复交付。',attribution_basis:'方案由专业人员提出，本人实际授权。',secondary_projection_reason:'不把战果直接计入组织能力。',source_refs:['docs/synthetic.md']};
const before=JSON.stringify(ctx.c);
const html=vm.runInContext("formalContextStory(c,c.parent_id,{axisCode:'M5'})",ctx);
assert.ok(html.includes('<h4 class="public-context-title">运输 &lt;与&gt; 前线</h4>'));
assert.ok(html.includes('<h5>任务分解</h5>'));
assert.ok(html.includes('运输与前线分别负责。'));
assert.ok(html.includes('故障后重配权限，后续恢复交付。'));
const footer=html.indexOf('<details class="metadata organization-context-sources">');
assert.ok(footer>html.indexOf('后续恢复交付'));
assert.ok(html.indexOf(ctx.c.attribution_basis)>footer);
assert.ok(html.indexOf(ctx.c.secondary_projection_reason)>footer);
assert.ok(!html.includes('context-direction'));
assert.equal(JSON.stringify(ctx.c),before);
''')


def test_organization_layout_preserves_current_processes_and_separates_counter_summary(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const template=fs.readFileSync('reader/index.template.html','utf8');
const source=template.split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const artifact=fs.readFileSync('reader/index.html','utf8');
const data=JSON.parse(artifact.match(/<script[^>]*id="reader-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify(data)}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
const normalize=s=>s.replace(/[\s：]/g,'');
for(const entry of data.records.filter(r=>!r.supplementary)){
 ctx.r=JSON.parse(fs.readFileSync('reader/data/people/'+entry.ruler_id+'.json','utf8')).record;
 const a=ctx.r.axes.M5,before=JSON.stringify(a);
 const axis=vm.runInContext("axisEvidence(r,'M5')",ctx);
 assert.equal((axis.match(/class="context-story formal-context-story organization-context-story"/g)||[]).length,a.representative_contexts.length,entry.ruler_id);
 const judgment=axis.indexOf('<details class="metadata adjudication">');
 assert.ok(judgment>0,entry.ruler_id);
 assert.ok(axis.indexOf('<div class="label">反例与判断边界</div>')>judgment,entry.ruler_id);
 for(const c of a.representative_contexts){
  ctx.c=c;
  const html=vm.runInContext("formalContextStory(c,c.parent_id,{axisCode:'M5'})",ctx);
  const footer=html.indexOf('<details class="metadata organization-context-sources">');
  assert.ok(footer>=0,entry.ruler_id);
  const plain=normalize(html.slice(0,footer).replace(/<[^>]*>/g,''));
  for(const line of c.process_narrative.split(/\n+/).filter(s=>s.trim())){
   ctx.line=line.trim();
   assert.ok(plain.includes(normalize(vm.runInContext('esc(profilePublicPattern(line))',ctx))),entry.ruler_id+': '+c.parent_id);
  }
  if(!c.direction)assert.ok(!html.includes('context-direction'),entry.ruler_id);
 }
 assert.equal(JSON.stringify(a),before);
}
''')


def test_coalition_context_renders_complete_formal_process_and_limits(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('reader/index.template.html','utf8').split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify({records:[],source_availability:{}})}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
const fields=['coalition_task','group_structure','interests_and_security_expectations','personal_choice','status_and_resource_configuration','political_credit_and_delivery','feedback_and_conflict_handling','exit_result','counterevidence','lifecycle_reasoning'];
ctx.c={parent_id:'synthetic',direction:'MIXED',source_refs:['docs/synthetic.md'],boundary_review:{c3:'集团合作不代替个人识别判断。'}};
for(const key of fields)ctx.c[key]=key+'：<合成> & 正式原文。';
const before=JSON.stringify(ctx.c);
let html=vm.runInContext("formalContextStory(c,'synthetic')",ctx);
for(const key of fields)assert.ok(html.includes(key+'：&lt;合成&gt; &amp; 正式原文。'),key);
assert.ok(html.includes(ctx.c.boundary_review.c3));
assert.ok(html.includes('该情境的来源与原始标注'));
assert.ok(!html.includes('未提供可展示的过程正文'));
assert.equal(JSON.stringify(ctx.c),before);
ctx.c={parent_id:'empty',direction:'POSITIVE'};
html=vm.runInContext("formalContextStory(c,'empty')",ctx);
assert.ok(html.includes('未提供可展示的过程正文'));
// Empty optional reasoning does not suppress an otherwise complete process.
ctx.c={coalition_task:'共同承担任务。',exit_result:'合作终止。',lifecycle_reasoning:''};
html=vm.runInContext("formalContextStory(c)",ctx);
assert.ok(html.includes(ctx.c.coalition_task)&&html.includes(ctx.c.exit_result));
assert.ok(!html.includes('完整过程的判断依据'));
// Every published coalition field, including counterevidence, reaches the same
// renderer used by person and comparison views. No historical counts are fixed.
for(const file of fs.readdirSync('reader/data/people').filter(f=>f.startsWith('RULER-')&&f.endsWith('.json'))){
 const r=JSON.parse(fs.readFileSync('reader/data/people/'+file,'utf8')).record;
 const a=r.axes?.M4;if(!a)continue;
 for(const c of a.representative_contexts||[]){
  ctx.c=c;html=vm.runInContext("formalContextStory(c)",ctx);
  for(const key of fields)if(c[key]){
   ctx.value=c[key];
   assert.ok(html.includes(vm.runInContext('prose(value)',ctx)),file+': '+c.parent_id+': '+key);
  }
 }
}
''')


def test_overview_reference_report_tracks_projection_changes():
    from reader.build import person_note_reference_issues
    records = [{'ruler_id': 'synthetic', 'net': {'component_details': {
        'finance': [{'reader_public_c': {'public_story': '民生逐步恢复。'}}]}}}]
    path = ['net', 'component_details', 'finance', 0, 'reader_public_c', 'public_story']
    block = {'text': '民生有所恢复。', 'evidence': [{'path': path, 'quote': '逐步恢复'}]}
    notes = {'records': {'synthetic': {'overview': {key: dict(block) for key in ('outcome', 'profile', 'impact')}}}}
    assert not person_note_reference_issues(records, notes)
    records[0]['net']['component_details']['finance'][0]['reader_public_c']['public_story'] = '材料已撤回。'
    assert person_note_reference_issues(records, notes) == [('synthetic', key, path) for key in ('outcome', 'profile', 'impact')]
    path[3] = 5
    assert person_note_reference_issues(records, notes)


def test_axis_grade_explanation_is_visible_before_nested_evidence_for_current_pool(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const fs=require('node:fs'),vm=require('node:vm');
const template=fs.readFileSync('reader/index.template.html','utf8');
const source=template.split('<script>')[1].split("document.getElementById('home-nav').onclick")[0];
const artifact=fs.readFileSync('reader/index.html','utf8');
const data=JSON.parse(artifact.match(/<script[^>]*id="reader-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
const element={addEventListener(){},classList:{toggle(){}}};
const ctx={document:{getElementById(id){return id==='reader-data'?{textContent:JSON.stringify(data)}:element}},location:{hostname:'localhost',hash:''},window:{}};
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.primary='局部任务中曾经授予负责人真实的执行权限，并取得阶段性交付。';
ctx.basis='整体仍反复出现信息受阻与责任失配，局部成功不足以改变全期判断。'+ctx.primary;
assert.equal(vm.runInContext('profileDistinctGradeBasis(primary,primary)',ctx),'');
assert.ok(vm.runInContext('profileDistinctGradeBasis(basis,primary)',ctx),'unique prefix must survive repeated factual ending');
ctx.r={ruler_id:'synthetic',axes:{M5:{axis_grade:'G1',position:'MID',typical_pattern:ctx.primary,grade_basis:ctx.basis,position_basis:'仍有正常负责人继续工作。',limitations:['只限已观察任务。'],source_refs:[]}}};
ctx.code='M5';
const original=JSON.stringify(ctx.r);
for(const suffix of ['', '-compare-0']){
 ctx.suffix=suffix;
 const html=vm.runInContext('axisEvidence(r,code,suffix)',ctx);
 const at=html.indexOf('<section class="axis-grade-explanation">');
 const further=html.indexOf('<details class="axis-further-check">');
 assert.ok(at>=0&&at<further,'grade reason must precede further evidence');
 assert.ok(html.indexOf(vm.runInContext('prose(profilePublicPattern(basis))',ctx))<further);
 assert.ok(html.includes(ctx.r.axes.M5.position_basis));
}
assert.equal(JSON.stringify(ctx.r),original);
for(const state of ['EVIDENCE_INSUFFICIENT_CLOSED','REASSESSMENT_REQUIRED']){
 ctx.r.axes.M5.adjudication_state=state;
 const html=vm.runInContext('axisEvidence(r,code)',ctx);
 assert.ok(html.includes('<div class="label">当前状态的依据</div>'));
 assert.ok(!html.includes('<div class="label">当前等级的整体依据</div>'));
}
delete ctx.r.axes.M5.adjudication_state;
ctx.r.axes.M5.grade_basis=ctx.primary;
assert.ok(!vm.runInContext('axisEvidence(r,code)',ctx).includes('axis-grade-explanation'));
delete ctx.r.axes.M5.grade_basis;
assert.ok(!vm.runInContext('axisEvidence(r,code)',ctx).includes('axis-grade-explanation'));
let checked=0;
for(const file of fs.readdirSync('reader/data/people').filter(f=>f.startsWith('RULER-')&&f.endsWith('.json'))){
 ctx.r=JSON.parse(fs.readFileSync('reader/data/people/'+file,'utf8')).record;
 if(!ctx.r.axes)continue;
 const before=JSON.stringify(ctx.r);
 for(const [code,a] of Object.entries(ctx.r.axes)){
  if(code==='M1'&&a.public_reading)continue;
  ctx.code=code;ctx.a=a;
  const expected=vm.runInContext("profileDistinctGradeBasis(a.grade_basis,a.typical_pattern||a.not_applicable_reason||'')",ctx);
  for(const suffix of ['', '-compare-0']){
   ctx.suffix=suffix;
   const html=vm.runInContext('axisEvidence(r,code,suffix)',ctx);
   if(expected){
    ctx.expected=expected;
    const content=vm.runInContext("['C1','C5','M5'].includes(code)?powerProse(expected):prose(expected)",ctx);
    const label=vm.runInContext("ungraded(a)||pending(a)||a.applicability_status==='NOT_APPLICABLE'||a.output_mode==='NOT_APPLICABLE'?'当前状态的依据':'当前等级的整体依据'",ctx);
    assert.ok(html.includes('<section class="axis-grade-explanation"><div class="label">'+label+'</div>'+content),file+': '+code);
    assert.ok(html.indexOf('axis-grade-explanation')<html.indexOf('<details class="axis-further-check">'),file+': '+code);
   }
  }
  checked++;
 }
 assert.equal(JSON.stringify(ctx.r),before);
}
assert.ok(checked>0);
console.log(JSON.stringify({axisRecordsChecked:checked}));
''')


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
ctx.c={parent_id:'P1',evidence_title:'授职与反馈',lifecycle_narrative:'一度取得交付，后来反馈受阻。',source_refs:['docs/史料通读产物/synthetic.md']};
const contextHtml=vm.runInContext("formalContextStory(c,'P1')",ctx);
assert.ok(contextHtml.includes(ctx.c.evidence_title));
assert.ok(contextHtml.includes(ctx.c.lifecycle_narrative));
assert.ok(contextHtml.includes('项目史料通读'));
assert.ok(!contextHtml.includes('来源原文'));
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


def test_pending_overview_can_cite_pool_status_without_allowing_scores(tmp_path):
    _run_reading_notes_node(tmp_path, r'''
const record={ruler_id:'synthetic',settlement_readiness:'PENDING_TEST'};
const block={text:'当前分项尚未齐备，未入榜不能按零分理解。',evidence:[{path:['settlement_readiness'],quote:record.settlement_readiness}]};
api.validateBlock(block);
assert.equal(api.assessBlock(block,record).status,'current');
assert.deepEqual(api.sourceFor(record,['settlement_readiness']),{path:'config/common/canonical-ruler-pool.json',label:'正式评价池就绪状态'});
assert.equal(api.validPath(['total_score']),false);
assert.equal(api.validPath(['ruler_id']),false);
''')


def test_note_coverage_follows_current_main_pool():
    from reader.build import person_note_reference_issues
    records = [{'ruler_id': 'main'}, {'ruler_id': 'extra', 'supplementary': True}]
    assert person_note_reference_issues(records, {'records': {}}) == [('main', 'coverage', [])]
