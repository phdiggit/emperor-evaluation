"""Reader projection and document navigation; never pin historical adjudications."""
import importlib.util
from pathlib import Path
import json
import subprocess
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'reader' / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def bootstrap_payload():
    html = (ROOT / 'reader/index.html').read_text(encoding='utf-8')
    encoded = html.split('<script type="application/json" id="reader-data">')[1].split('</script>')[0]
    return html, encoded, json.loads(encoded)


def detail_payload(summary):
    return json.loads((ROOT / 'reader' / summary['detail_ref']).read_text(encoding='utf-8'))


def test_projection_preserves_reasons_and_deduplicates_sources():
    row = {'position_basis': 'position reason', 'source_refs': ['docs/a.md'],
           'counterpattern': {'positive_parent_refs': ['p']},
           'parent_chains': [{'parent_id': 'p', 'cycle_basis': 'fact',
                              'source_refs': ['docs/a.md', 'docs/b.md#L3']}]}
    result = module('build').axis_projection(row, ['position_basis', 'counterpattern'])
    assert result['position_basis'] == row['position_basis']
    assert result['source_refs'] == ['docs/a.md', 'docs/b.md#L3']
    assert result['context_lookup']['p']['cycle_basis'] == 'fact'


def test_unresolved_context_fails_instead_of_silently_losing_evidence():
    with pytest.raises(ValueError, match='Unresolved context'):
        module('build').axis_projection({'counterpattern': {'positive_parent_refs': ['missing']}}, [])


def test_document_preserves_chapter_duplicate_and_explicit_anchors():
    page = module('serve').document_page('# 标题\n\n## **中文** `代码`\n\n## **中文** `代码`\n\n<a id="person-synthetic"></a>\n').decode()
    assert 'id="中文-代码"' in page
    assert 'id="中文-代码-1"' in page
    assert 'href="#中文-代码"' in page
    assert 'id="person-synthetic"' in page
    assert 'data-source-line="3"' in page
    assert 'data-legacy-anchor="section-1"' in page


def test_document_disallows_active_html_and_remote_images():
    page = module('serve').document_page('# Safe\n\n<script>alert(1)</script>\n\n![image](https://example.com/image.png)\n').decode()
    assert '<script>alert(1)</script>' not in page
    assert '<img' not in page


def test_source_path_accepts_existing_line_citation_formats():
    builder = module('build')
    assert builder.source_file('docs/中文.md:42') == 'docs/中文.md'
    assert builder.source_file('docs/中文.md#L42-L45') == 'docs/中文.md'


def test_reference_checker_preserves_text_and_source_coordinates():
    checker = module('check_references')
    parser = checker.ArticleTree()
    parser.feed(module('serve').document_page('# Header\n\nA **bold** fact.\n').decode())
    article = parser.serialize()
    assert article['tag'] == 'article'
    assert 'A bold fact.' in article['textContent']
    heading = next(child for child in article['children'] if child['tag'] == 'h1')
    assert heading['attrs']['data-source-line'] == '1'
    assert heading['attrs']['data-legacy-anchor'] == 'section-0'


def test_current_reader_is_complete_and_current():
    builder = module('build')
    data = builder.build(check=True)
    config = builder.yaml.safe_load((ROOT / 'config/project.yml').read_text(encoding='utf-8'))
    by_id = {r['ruler_id']: r for r in data['records']}
    for code, spec in config['profile_assessment']['settled_axes'].items():
        for row in builder.load_json(ROOT / spec['json'])['records']:
            projected = by_id[row['ruler_id']]['axes'][code]
            for key in ('axis_grade', 'position', 'radar_value', 'position_basis', 'grade_basis'):
                assert projected.get(key) == row.get(key)
    ranking = builder.load_json(ROOT / config['scoring_contract']['composite_ranking_json'])
    assert data['weight_sensitivity'] == ranking['weight_sensitivity']
    for row in ranking['records']:
        assert by_id[row['ruler_id']]['net']['weight_sensitivity'] == row['weight_sensitivity']


def test_bootstrap_is_lightweight_and_every_record_has_a_detail_shard():
    html, _, data = bootstrap_payload()
    assert data['detail_schema_version'] == 'reader-person-detail-v1'
    assert len(html.encode('utf-8')) < 1_500_000
    assert len({r['detail_ref'] for r in data['records']}) == len(data['records'])

    for summary in data['records']:
        assert summary['detail_loaded'] is False
        assert summary['detail_ref'].startswith('data/people/')
        assert 'grade_basis' not in summary['impact']
        for axis in summary['axes'].values():
            assert 'grade_basis' not in axis
            assert 'typical_pattern' not in axis
            assert 'source_refs' not in axis
        payload = detail_payload(summary)
        assert payload['record']['ruler_id'] == summary['ruler_id']
        assert payload['record']['ruler_name'] == summary['ruler_name']
        assert isinstance(payload['source_availability'], dict)


def test_lazy_detail_loader_uses_static_shards_and_cache():
    script = (ROOT / 'reader/lazy-details.js').read_text(encoding='utf-8')
    assert 'fetch(record.detail_ref' in script
    assert 'pendingLoads.has(id)' in script
    assert 'byId.set(id, full)' in script
    assert 'Object.assign(DATA.source_availability' in script
    assert 'Promise.all(selected.map(loadRecord))' in script


def test_stale_check_does_not_write(monkeypatch):
    builder = module('build')
    read_bytes = Path.read_bytes
    output = ROOT / 'reader/index.html'
    monkeypatch.setattr(Path, 'read_bytes', lambda p: b'stale' if p == output else read_bytes(p))
    def forbid_write(*args, **kwargs):
        pytest.fail('read-only check attempted a write')
    monkeypatch.setattr(Path, 'write_text', forbid_write)
    with pytest.raises(ValueError, match='Reader is stale'):
        builder.build(check=True)


def test_reader_rendering_and_publication_boundaries(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for reader JavaScript checks')
    html, payload, data = bootstrap_payload()
    script = html.split('<script>')[1].split('</script>')[0]
    # Exercise pure rendering with full records loaded from the generated static shards.
    script = script.split("document.getElementById('home-nav').onclick")[0]
    main_summary = next(r for r in data['records'] if not r['supplementary'])
    other_summary = next(r for r in data['records'] if r['ruler_id'] != main_summary['ruler_id'])
    details = {
        main_summary['ruler_id']: detail_payload(main_summary),
        other_summary['ruler_id']: detail_payload(other_summary),
    }
    harness = "const assert=require('node:assert/strict');const elements=new Map();const location={hash:''};const document={getElementById(id){if(!elements.has(id))elements.set(id,{textContent:'',innerHTML:'',classList:{toggle(){}},addEventListener(){}});return elements.get(id)}};"
    harness += "const history={replaceState(a,b,hash){location.hash=hash}};"
    harness += 'document.getElementById("reader-data").textContent=' + json.dumps(payload) + ';\n' + script
    harness += '\nconst DETAIL_PAYLOADS=' + json.dumps(details, ensure_ascii=False) + ';\n'
    harness += '''
const graded={axis_grade:'G3',position:'MID',radar_value:50};
assert.equal(grade(graded),'B');
for(const a of [{...graded,adjudication_state:'EVIDENCE_INSUFFICIENT_CLOSED'}, {...graded,display_point_only:true}, {...graded,adjudication_state:'REASSESSMENT_REQUIRED'}, {...graded,position:null}, {...graded,output_mode:'NOT_APPLICABLE'}]) assert.equal(radarValue(a),null);
assert.equal(grade({...graded,adjudication_state:'EVIDENCE_INSUFFICIENT_CLOSED'}),'无档结案');
location.hash='#person/'+encodeURIComponent('RULER-SYNTHETIC-中文');
assert.equal(personId(),'RULER-SYNTHETIC-中文');
location.hash='#person/%E0%A4';assert.equal(personId(),'');location.hash='';
assert.equal(href('docs/a.md:42'),'../docs/a.md#L42');
assert.ok(link('https://example.com/source','source').includes('href="https://example.com/source"'));
DATA.source_availability['docs/missing.md']=false;
assert.ok(!link('docs/missing.md','source').includes('<a '));
assert.ok(link('docs/missing.md','source').includes('当前文件不可用'));
for(const r of DATA.records){assert.ok(r.detail_ref);assert.equal(r.detail_loaded,false);assert.ok(!screen.innerHTML.includes('[object Object]'));}
state.compare=[];compare();assert.equal(state.compare.length,0);assert.ok(screen.innerHTML.includes('搜索对照人物'));
const profileSummary=DATA.records.find(r=>!r.supplementary);
const profileRecord=DETAIL_PAYLOADS[profileSummary.ruler_id].record;
byId.set(profileRecord.ruler_id,profileRecord);Object.assign(DATA.source_availability,DETAIL_PAYLOADS[profileSummary.ruler_id].source_availability);
state.compare=[profileRecord.ruler_id];compare();assert.equal(state.compare.length,1);
person(profileRecord);
assert.ok(screen.innerHTML.includes('历史影响等级为什么这样定'));
const overview=screen.innerHTML.split('<section id="person-evidence"')[0];
for(const c of DATA.axis_order)assert.ok(overview.includes('data-reason="'+c+'"'));
assert.ok(!overview.includes('补充画像'));
assert.ok(!overview.includes('PS3'));
assert.ok(!axisRows(profileRecord,DATA.axis_order).includes(profileRecord.axes.C1.grade_basis));
const synthetic={...profileRecord,axes:{...profileRecord.axes,C1:{...profileRecord.axes.C1,typical_pattern:'visible behavior',grade_basis:'PS3 original ruling',position_basis:'exact position',limitations:'exact limitation'}}};
const evidence=axisEvidence(synthetic,'C1');
assert.ok(evidence.includes('PS3 original ruling'));assert.ok(evidence.includes('exact limitation'));
assert.ok(evidence.indexOf('PS3 original ruling')>evidence.indexOf('裁决详情'));
assert.equal(readerText('PS3 / AM4'),'可跨情境迁移的强模式 / 国家基本运行架构重构');
assert.ok(gradeHelp('impact').includes('不是能力或功绩等级'));
assert.ok(link('archive/source.md','source',profileRecord).includes('?person='));
home();assert.ok(document.getElementById('rows').innerHTML.includes('权力运用风格'));
const otherSummary=DATA.records.find(r=>r.ruler_id!==profileRecord.ruler_id);
const otherRecord=DETAIL_PAYLOADS[otherSummary.ruler_id].record;
byId.set(otherRecord.ruler_id,otherRecord);Object.assign(DATA.source_availability,DETAIL_PAYLOADS[otherSummary.ruler_id].source_availability);
state.compare=[profileRecord.ruler_id,otherRecord.ruler_id];state.differences=false;compare();
assert.ok(screen.innerHTML.includes('裁决详情'));
assert.ok(screen.innerHTML.includes('只看不同项'));
'''
    path = tmp_path / 'reader-test.cjs'
    path.write_text(harness, encoding='utf-8')
    result = subprocess.run([node, str(path)], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_json_embedding_and_reference_resolution(tmp_path):
    payload = {'records': [{'ruler_id': 'RULER-中文', 'score': 0,
                            'materials': [{'material_id': 'M-1', 'text': '</script>'}]}]}
    page = module('serve').json_page(payload).decode()
    encoded = page.split('id="json-data">')[1].split('</script>')[0]
    assert json.loads(encoded) == payload
    assert '</script>' not in encoded
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for reader JavaScript checks')
    function = page[page.index('function findRecords'):page.index('const params=')]
    script = "const assert=require('node:assert/strict');\n" + function
    script += 'const data=' + json.dumps(payload) + ';\n'
    script += '''
assert.equal(findRecords(data,'ruler_id=RULER-中文')[0].value.score,0);
assert.equal(findRecords(data,'RULER-中文')[0].path,'/records/0');
assert.equal(findRecords(data,'material_id=M-1')[0].value.text,'</script>');
assert.equal(findRecords(data,'ruler_id=RULER-中文/materials/0')[0].value.material_id,'M-1');
const traits={records:[{ruler_id:'test',traits:[{domain:'A1 task'},{domain:'A2 feedback'}]}]};
assert.equal(findRecords(traits,'ruler_id=test/traits/A2/0')[0].path,'/records/0/traits/1');
assert.equal(findRecords(traits,'ruler_id=test/traits/A3/0').length,0);
assert.equal(findRecords({rows:[{source_target_ref:'campaign-x'}]},'campaign-x').length,1);
assert.equal(findRecords(data,'records/0/score')[0].value,0);
assert.equal(findRecords(data,'records/9').length,0);
assert.equal(findRecords(data,'constructor/prototype').length,0);
assert.equal(findRecords({records:[{id:'x'},{id:'x'}]},'x').length,2);
'''
    path = tmp_path/'json-reader.cjs'
    path.write_text(script, encoding='utf-8')
    result = subprocess.run([node,str(path)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_fragment_resolution_is_unambiguous(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for reader JavaScript checks')
    page = (ROOT/'reader/document.template.html').read_text(encoding='utf-8')
    function = page[page.index('function resolveFragment'):page.index('function fragmentTarget')]
    script = "const assert=require('node:assert/strict');\n" + function + '''
const h={textContent:'WAR-EXAMPLE 合成情境',dataset:{legacyAnchor:'section-0'}};
const doc={getElementById:()=>null,querySelectorAll:()=>[h]};
assert.equal(resolveFragment('section-0',doc).target,h);
assert.equal(resolveFragment('WAR-EXAMPLE',doc).target,h);
const ambiguous={getElementById:()=>null,querySelectorAll:()=>[h,{...h}]};
assert.equal(resolveFragment('WAR-EXAMPLE',ambiguous).status,'ambiguous');
const empty={getElementById:()=>null,querySelectorAll:()=>[]};
assert.equal(resolveFragment('missing',empty).status,'missing');
'''
    path = tmp_path/'fragment-reader.cjs'
    path.write_text(script,encoding='utf-8')
    result = subprocess.run([node,str(path)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode == 0,result.stderr


def test_json_http_view_preserves_raw_and_uses_logical_loader(tmp_path, monkeypatch):
    from functools import partial
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import urlopen
    server_module = module('serve')
    original = b'{"router":true}'
    (tmp_path/'source.json').write_bytes(original)
    logical = {'records':[{'ruler_id':'synthetic','value':0}]}
    monkeypatch.setattr(server_module, 'load_json', lambda path: logical)
    server = ThreadingHTTPServer(('127.0.0.1',0), partial(server_module.ReaderHandler,directory=str(tmp_path)))
    thread = Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{server.server_port}/source.json'
        with urlopen(url) as response:
            assert response.headers.get_content_type() == 'text/html'
            body = response.read().decode()
            assert json.loads(body.split('id="json-data">')[1].split('</script>')[0]) == logical
        with urlopen(url+'?raw=1') as response:
            assert response.read() == original
    finally:
        server.shutdown();server.server_close();thread.join()
