import json
from pathlib import Path
import shutil
import subprocess

import pytest

from emperor_v4.evaluation.first_item_b1_cost_public import load_first_item_b1_cost_public, project_b1, project_cost
from emperor_v4.evaluation.first_item_c_public import public_commander_for_name

ROOT = Path(__file__).resolve().parents[1]


def test_b1_requires_declared_prose_and_keeps_multiple_stages():
    fields = {'公开起点说明':'资源有限。', '公开对手说明':'对手有稳定组织。',
              '公开效率说明':'第一阶段三年；第二阶段五年，不合并计时。', 'B1结算':'R1 + O2',
              '公开阅读问题':'这段合成取得过程经历了什么？','公开阅读正文':'合成对象先后完成两个目标，各有自己的条件与工期。'}
    assert project_b1(fields)['public_efficiency_basis'] == fields['公开效率说明']
    del fields['公开效率说明']
    fields['效率'] = '实际八年。'
    with pytest.raises(ValueError, match='禁止阅读层'):
        project_b1(fields)


def test_cost_requires_every_gap_and_safe_explicit_links():
    row = {'public_reading':{'burden':'实际组织守军与运输。','losses':'损失已确认，但总量不明。','grade_basis':'持续方向级投入。','boundary':'不计敌方损失。'},'public_responsibility_window':'本人负责时期。',
           'public_source_note':'战事材料与原文入口分列。','source_refs':['docs/source.md#合成战事'],
           'public_source_records':[{'path':'docs/source.md#合成战事','label':'合成战事材料','kind':'战事材料汇集'}],
           'public_unresolved_gaps':['后段缺乏材料。'], 'unresolved_gaps':['内部缺口'],
           'public_source_links':[{'label':'来源','url':'https://example.org/source'}],
           'cost_band':'C3','cost_position':'MID','evidence_status':'LOWER_BOUND'}
    projected = project_cost(row)
    assert [section['text'] for section in projected['public_sections']] == list(row['public_reading'].values())
    assert '损失已确认，但总量不明。' in projected['public_basis']
    assert project_cost(row)['public_level_label'] == '中等成本（第3级／0—7级）'
    assert '同一级内' in project_cost(row)['public_position_note']
    with pytest.raises(ValueError, match='逐条保留'):
        project_cost({**row, 'public_unresolved_gaps':[]})
    with pytest.raises(ValueError, match='分别维护'):
        project_cost({**row, 'public_reading':{'burden':'只保留投入。'}})
    with pytest.raises(ValueError, match='完整保留'):
        project_cost({**row, 'public_source_records':[]})
    with pytest.raises(ValueError, match='补证过程'):
        project_cost({**row, 'public_reading':{**row['public_reading'], 'losses':'补核原文入口后仍未知。'}})
    row['public_source_links'][0]['url']='javascript:alert(1)'
    with pytest.raises(ValueError, match='协议'):
        project_cost(row)


def test_current_reader_and_cache_match_formal_public_fields():
    b1, cost = load_first_item_b1_cost_public(ROOT)
    for path in (ROOT/'reader/data/people').glob('*.json'):
        record=json.loads(path.read_text(encoding='utf-8'))['record']
        net=record.get('net') or {}
        if net.get('first_item_status') != 'APPLICABLE':
            continue
        items={item['label']:item for item in net['component_details']['first']}
        cache=json.loads((ROOT/'reader/data/first-item'/path.name).read_text(encoding='utf-8'))
        for label,key,source in [('B1创业难度与效率','b1',b1),('军事成本扣分','cost',cost)]:
            expected=public_commander_for_name(source,record['ruler_name'])
            assert items[label]['reader_public_'+key] == expected
            assert cache['public_'+key] == expected


def test_browser_preserves_stages_long_basis_gaps_and_links(tmp_path):
    node=shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script=tmp_path/'public.cjs'
    script.write_text(r'''
const fs=require('node:fs'), assert=require('node:assert/strict');
const source=fs.readFileSync('reader/home-interactions.js','utf8');
const helpers=source.slice(source.indexOf('function firstB1Markup'),source.indexOf('function firstCommanderMarkup'));
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
const {b1,cost}=new Function('esc','prose','link',helpers+';return {b1:firstB1Markup,cost:firstCostMarkup}')(esc,s=>'<p>'+esc(s)+'</p>',(ref,label)=>'<a href="'+esc(ref)+'">'+esc(label)+'</a>');
const stages='先完成甲段。后完成乙段；两段分别计时，不据此推定总年数。';
assert.ok(b1({reader_public_b1:{public_efficiency_basis:stages}}).includes(stages));
const entryStart=source.indexOf('function firstB1ReadingMarkup'), entryEnd=source.indexOf('// Formal public fields are shared',entryStart);
const entry=new Function('esc','prose','link','firstB1Markup',source.slice(entryStart,entryEnd)+'return firstB1ReadingMarkup;')(esc,s=>'<p>'+esc(s)+'</p>',ref=>'<a>'+esc(ref)+'</a>',b1);
const entryHtml=entry({value:25,reader_public_b1:{public_question:'合成问题？',public_story:'正文保留完整含义。',public_efficiency_basis:stages,public_method:'合成规则。',public_calculation:'合成计算。',start_points:5,opponent_points:0,efficiency_points:20,public_sources:['docs/source.md']}},{});
for(const text of ['合成问题？','正文保留完整含义。',stages,'合成计算。','docs/source.md'])assert.ok(entryHtml.includes(text));
assert.ok(entryHtml.indexOf('正文保留完整含义。')<entryHtml.indexOf('<details class="first-b1-facts">'));
assert.ok(entryHtml.indexOf('<details class="first-b1-facts">')<entryHtml.indexOf('<details class="first-b1-method">'));
assert.ok(!entryHtml.includes('<details open'));
const basis='完整依据。'.repeat(100)+'末尾责任限制不得删除。';
const html=cost({reader_public_cost:{public_level_label:'中等成本（第3级／0—7级）',public_sections:[{title:'实际损失与已知限度',text:basis}],public_responsibility_window:'只含本人时期。',public_unresolved_gaps:['上限尚不明确。'],public_source_links:[{label:'具名史料',url:'https://example.org/source'}]}});
assert.ok(html.includes('中等成本（第3级／0—7级）'));
assert.ok(html.indexOf(basis)>html.indexOf('<details class="first-cost-evidence">'));
for(const text of [basis,'只含本人时期。','上限尚不明确。','https://example.org/source']) assert.ok(html.includes(text));
const structured=cost({reader_public_cost:{public_sections:[{title:'战争负担',text:'主力实际执行运输。'},{title:'实际损失与已知限度',text:basis}],public_source_records:[{path:'docs/source.md#合成战事',label:'具名材料',kind:'战事材料汇集',source_url:'https://example.org/original'}],public_source_note:'摘要不能冒充原文。'}});
for(const text of ['<h4>战争负担</h4>','主力实际执行运输。',basis,'docs/source.md#合成战事','具名材料','https://example.org/original'])assert.ok(structured.includes(text));
assert.ok(structured.indexOf('具名材料')>structured.indexOf('<details class="first-cost-sources">'));
''',encoding='utf-8')
    result=subprocess.run([node,str(script)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    assert result.returncode == 0,result.stderr


def test_b1_collection_covers_every_current_formal_entry():
    from html.parser import HTMLParser

    class Entries(HTMLParser):
        def __init__(self):
            super().__init__()
            self.entries = {}
            self.current = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'article' and 'first-b1-reading' in attrs.get('class',''):
                self.current = attrs['id']
                self.entries[self.current] = []

        def handle_endtag(self, tag):
            if tag == 'article':
                self.current = None

        def handle_data(self, value):
            if self.current:
                self.entries[self.current].append(value)

    parser = Entries()
    parser.feed((ROOT/'reader/first-item-b1.html').read_text(encoding='utf-8'))
    formal, _ = load_first_item_b1_cost_public(ROOT)
    assert set(parser.entries) == set(formal)
    for name, chunks in parser.entries.items():
        text = ''.join(chunks)
        assert formal[name]['public_question'] in text
        assert formal[name]['public_story'] in text
