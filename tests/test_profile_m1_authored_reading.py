"""Authored M1 reading, provenance and projections; no frozen ruler verdicts."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_m1_public import SCHEMA, validate_public_reading, markdown_reading, archive_projection, comparison_projection, load_archive_context
from emperor_v4.evaluation.profile_registry import profile_axis_entry

ROOT = Path(__file__).resolve().parents[1]


def synthetic():
    reading = dict(schema_version=SCHEMA, headline='战区统筹有明确表现。', summary='具名行动支持这一判断。',
                   grade_reason='两组不同任务体现持续组织。', position_reason='表现仍有稳定性限制。',
                   higher_grade_limit='更高层次的直接作战表现仍缺依据。',
                   cases=[dict(episode_ref='CASE-SYNTHETIC', title='合成行动', action='本人配置两路军队。',
                               result='两路行动完成会合。', meaning='显示协同组织能力。', boundary='现场接战由将领指挥。',
                               sources=[dict(ref='docs/example.md', label='行动材料')])])
    return dict(axis_grade='G3', position='MID', confidence='MEDIUM',
                m1_role_projection=dict(items=[dict(capability_episode_ref='CASE-SYNTHETIC', source_refs=['docs/example.md'])]),
                public_reading=reading)


def test_validation_and_markdown_preserve_authored_prose_and_verdict():
    row = synthetic()
    before = deepcopy(row)
    validate_public_reading(row)
    output = '\n'.join(markdown_reading(row))
    assert row == before
    assert row['public_reading']['summary'] in output
    assert row['public_reading']['cases'][0]['action'] in output
    assert '为什么评为 B 档' in output
    assert '材料底池' not in output


@pytest.mark.parametrize('change', ['episode', 'source', 'boilerplate', 'missing_case_field'])
def test_unbound_or_internal_prose_fails_closed(change):
    row = synthetic()
    case = row['public_reading']['cases'][0]
    if change == 'episode': case['episode_ref'] = 'UNDECLARED'
    if change == 'source': case['sources'][0]['ref'] = 'docs/unknown.md'
    if change == 'boilerplate': row['public_reading']['summary'] = '材料底池已经登记。'
    if change == 'missing_case_field': del case['action']
    with pytest.raises(ValueError):
        validate_public_reading(row)


def test_current_authored_reading_is_shared_with_cache_and_markdown():
    entry = profile_axis_entry('M1')
    data = load_json(ROOT / entry['json'])
    markdown = (ROOT / entry['markdown']).read_text(encoding='utf-8')
    context = load_archive_context(ROOT)
    pool = load_json(ROOT / 'config/common/canonical-ruler-pool.json')
    assert {r['ruler_id'] for r in data['records']} == {r['ruler_id'] for r in pool['records'] if r['pool_status']=='INCLUDED'}
    for row in data['records']:
        assert row.get('public_reading')
        validate_public_reading(row)
        cache = json.loads((ROOT / 'reader/data/people' / (row['ruler_id'] + '.json')).read_text(encoding='utf-8'))['record']['axes']['M1']
        assert cache['public_reading'] == row['public_reading']
        if row['public_reading'].get('career_review'):
            assert cache['m1_archive_links'] == archive_projection(row, ROOT, context)
        else:
            assert cache['m1_archive_links'] == archive_projection(row, ROOT, context)
        peers=cache['m1_archive_links']['comparisons']
        assert len(peers)==2
        assert len({p['href'] for p in peers})==2
        assert all(p['href'].endswith('/profile/M1') and p['grade'] in p['label'] for p in peers)
        for key in ('axis_grade', 'position', 'radar_value'):
            assert cache[key] == row[key]
        assert row['public_reading']['grade_reason'] in markdown


def test_comparison_labels_follow_current_same_axis_verdict_and_axis_route():
    own = dict(axis_grade='G3', position='MID')
    peer = dict(ruler_id='RULER-SYNTHETIC', ruler_name='合成参照', axis_grade='G3', position='HIGH')
    result = comparison_projection(own, peer, '独立的本人表现支持更高位置。')
    assert result['grade'] == 'B+'
    assert result['relation'] == '同档高位参照'
    assert result['href'].endswith('/profile/M1')
    peer['position'] = 'MID'
    assert comparison_projection(own, peer, '相同位置。')['relation'] == '同档同位'
    peer['position'] = 'LOW'
    assert comparison_projection(own, peer, '较低位置。')['grade'] == 'B−'
    assert comparison_projection(own, peer, '较低位置。')['relation'] == '同档低位参照'


def test_same_position_exception_is_only_allowed_without_a_current_peer(tmp_path):
    row = synthetic()
    row.update(ruler_id='OWN', ruler_name='本人')
    peer = dict(ruler_id='PEER', ruler_name='参照', axis_grade='G3', position='HIGH')
    row['public_reading']['comparisons'] = [dict(ruler_id='PEER', basis='明确的本人表现。', comparison_role='NO_SAME_POSITION_PEER')]
    context = dict(battles={}, indexed_ids=set(), commanders={}, peers={'OWN':row,'PEER':peer})
    result=archive_projection(row,tmp_path,context)
    assert '本位无其他样本' in result['comparisons'][0]['label']
    context['peers']['SAME'] = dict(ruler_id='SAME',ruler_name='同位',axis_grade='G3',position='MID')
    with pytest.raises(ValueError,match='邻位例外'):
        archive_projection(row,tmp_path,context)
    row['public_reading']['comparisons'][0]['comparison_role']='SAME_POSITION'
    with pytest.raises(ValueError,match='同档同位'):
        archive_projection(row,tmp_path,context)
    row['public_reading']['comparisons'][0]['comparison_role']='POSITION_CONTRAST'
    context['peers']['PEER']['axis_grade']='G2'
    with pytest.raises(ValueError,match='同档异位'):
        archive_projection(row,tmp_path,context)


def test_direct_axis_focus_handles_hydration_and_stale_renders(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for direct axis routing')
    template = (ROOT / 'reader/index.template.html').read_text(encoding='utf-8')
    source = template[template.index('function focusProfileAxis('):template.index('function profilePage(')]
    page = template[template.index('function profilePage('):template.index('function impactPage(')]
    assert page.index('screen.innerHTML=') < page.index('focusProfileAxis();')
    script = tmp_path / 'profile-axis-focus.cjs'
    script.write_text('const assert=require("node:assert/strict");let target=null,frames=[],scrolled=0;\n'
                     + 'const DATA={axis_order:["M1","C1"]};const location={hash:"#person/SYNTHETIC/profile/M1"};\n'
                     + 'const document={getElementById:id=>target?.id===id?target:null};const requestAnimationFrame=fn=>frames.push(fn);\n'
                     + source + '\n'
                     + 'focusProfileAxis();assert.equal(frames.length,0);'
                     + 'target={id:"reason-M1",open:false,scrollIntoView(){scrolled++}};focusProfileAxis();assert.equal(target.open,true);frames.shift()();assert.equal(scrolled,1);'
                     + 'focusProfileAxis();target={id:"reason-M1"};frames.shift()();assert.equal(scrolled,1);'
                     + 'location.hash="#person/SYNTHETIC/profile";focusProfileAxis();assert.equal(frames.length,0);'
                     + 'location.hash="#person/SYNTHETIC/profile/UNKNOWN";focusProfileAxis();assert.equal(frames.length,0);', encoding='utf-8')
    result = subprocess.run([node, str(script)], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_archive_resolution_preserves_person_only_sources_and_ignores_talent_grade(tmp_path, monkeypatch):
    from emperor_v4.evaluation import battle_registry_store, formal_json_store
    row = synthetic()
    row['m1_role_projection']['profile_ref'] = 'PROFILE-SYNTHETIC'
    row['public_reading']['career_review'] = [dict(title='其他军事表现', basis='分别查看本人行动。', battle_refs=['WAR-SYNTHETIC', 'PERSON-ACTION-SYNTHETIC'])]
    directory = tmp_path / 'reader/data/military'
    directory.mkdir(parents=True)
    (directory / 'battles-index.json').write_text(json.dumps({'records': [{'id': 'WAR-SYNTHETIC'}]}), encoding='utf-8')
    commanders = {'records': [{'profile_ref': 'PROFILE-SYNTHETIC', 'name': '合成人物', 'grade': 'UNRELATED-GRADE'}]}
    path = directory / 'commanders-index.json'
    path.write_text(json.dumps(commanders), encoding='utf-8')
    monkeypatch.setattr(battle_registry_store, 'load_battle_registry', lambda path: {'records': [
        {'war_event_id': 'WAR-SYNTHETIC', 'canonical_label': '合成战争'},
        {'war_event_id': 'PERSON-ACTION-SYNTHETIC', 'canonical_label': '本人方案采纳',
         'settlement_scope': 'PERSON_RESULT_ONLY', 'public_outcome_registered': False, 'source_refs': ['https://example.org/source']},
    ]})
    monkeypatch.setattr(formal_json_store, 'load_json', lambda path: {'records': []})
    before = deepcopy(row)
    result = archive_projection(row, tmp_path)
    assert row == before
    assert result['career'][0]['links'][0]['href'] == 'military.html#battle=WAR-SYNTHETIC'
    assert result['career'][0]['links'][1]['href'] == 'https://example.org/source'
    assert 'UNRELATED-GRADE' not in json.dumps(result)
    commanders['records'][0]['grade'] = 'ANOTHER-UNRELATED-GRADE'
    path.write_text(json.dumps(commanders), encoding='utf-8')
    assert archive_projection(row, tmp_path) == result
    row['public_reading']['career_review'][0]['battle_refs'] = ['UNKNOWN']
    with pytest.raises(ValueError, match='不存在'):
        archive_projection(row, tmp_path)


def test_person_and_comparison_use_lossless_authored_renderer(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for shared reader behavior')
    template = (ROOT / 'reader/index.template.html').read_text(encoding='utf-8')
    source = template[template.index('function m1AuthoredEvidence('):template.index('function profilePanel(')]
    row = synthetic()
    row['m1_archive_links'] = {'commander': {'label': '本人武将档案', 'href': 'military.html#commander=SYNTHETIC'},
                             'career': [{'title': '合成生涯说明', 'basis': '其他行动的具体作用。',
                                         'links': [{'label': '合成战役档案', 'href': 'military.html#battle=SYNTHETIC'}]}],
                             'comparisons': [{'name': '合成参照人物', 'label': '同档同位 · 合成参照人物 B', 'basis': '本人角色与复验分别比较。', 'href': 'index.html#person/SYNTHETIC/profile/M1'}]}
    script = tmp_path / 'm1-reading.cjs'
    script.write_text('const assert=require("node:assert/strict");\n'
                     + 'const axis=' + json.dumps(row, ensure_ascii=False) + ';\n'
                     + 'const DATA={axis_specs:{M1:{name:"军事判断与统帅能力",contract:"rule.md",json:"formal.json",markdown:"formal.md"}}};\n'
                     + 'const esc=x=>String(x??"");const prose=x=>"<p>"+esc(x)+"</p>";const link=(p,l)=>"<a>"+l+"</a>";\n'
                     + 'const grade=()=>"B";const conf=x=>x;const letters={G3:"B"};\n'
                     + source + '\n'
                     + 'for(const suffix of ["","-compare-left","-compare-right"]){const html=axisEvidence({axes:{M1:axis}},"M1",suffix);'
                     + 'assert.ok(html.includes("reason-M1"+suffix));assert.ok(!html.includes("材料底池"));'
                     + 'assert.ok(!html.includes("进一步核对"));'
                     + 'assert.ok(html.includes("military.html#commander=SYNTHETIC"));assert.ok(html.includes("military.html#battle=SYNTHETIC"));'
                     + 'assert.ok(html.includes("其他行动的具体作用。"));assert.ok(html.includes("本人角色与复验分别比较。"));'
                     + 'assert.ok(html.includes("合成参照人物 B"));assert.ok(html.includes("index.html#person/SYNTHETIC/profile/M1"));'
                     + 'for(const value of [axis.public_reading.summary,axis.public_reading.cases[0].action,axis.public_reading.grade_reason])'
                     + 'assert.equal(html.split(value).length-1,1);}', encoding='utf-8')
    result = subprocess.run([node, str(script)], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_current_full_pool_renders_authored_prose_and_comparisons_without_generic_scope(tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Node.js required for full-pool shared rendering')
    template=(ROOT/'reader/index.template.html').read_text(encoding='utf-8')
    source=template[template.index('function m1AuthoredEvidence('):template.index('function profilePanel(')]
    entry=profile_axis_entry('M1')
    rows=load_json(ROOT/entry['json'])['records']
    ids_path=tmp_path/'ids.json'
    ids_path.write_text(json.dumps([r['ruler_id'] for r in rows]),encoding='utf-8')
    script=tmp_path/'m1-pool.cjs'
    script.write_text('const fs=require("node:fs"),assert=require("node:assert/strict");\n'
       +'const DATA={axis_specs:{M1:{name:"军事判断与统帅能力",contract:"rule.md",json:"formal.json",markdown:"reading.md"}}};\n'
       +'const esc=x=>String(x??"");const prose=x=>x?"<p>"+esc(x)+"</p>":"";const link=(p,l)=>"<a href=\\\""+p+"\\\">"+l+"</a>";\n'
       +'const letters={G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};const grade=a=>letters[a.axis_grade]+{LOW:"−",MID:"",HIGH:"+"}[a.position];const conf=x=>x;\n'
       +source+'\n'
       +'for(const id of JSON.parse(fs.readFileSync(process.argv[2],"utf8"))){const r=JSON.parse(fs.readFileSync("reader/data/people/"+id+".json","utf8")).record;const a=r.axes.M1,p=a.public_reading;'
       +'for(const suffix of ["","-compare-0","-compare-1"]){const html=axisEvidence(r,"M1",suffix);assert.ok(html.includes(p.grade_reason));assert.ok(html.includes(p.position_reason));'
       +'assert.ok(!html.includes("材料底池与本人能力证据"));for(const peer of a.m1_archive_links.comparisons){assert.ok(html.includes(peer.label));assert.ok(html.includes(peer.href));}'
       +'for(const c of p.cases)assert.ok(html.includes(c.title));}}',encoding='utf-8')
    result=subprocess.run([node,str(script),str(ids_path)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
