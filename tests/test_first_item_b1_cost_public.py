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
              '公开效率说明':'第一阶段三年；第二阶段五年，不合并计时。', 'B1结算':'R1 + O2'}
    assert project_b1(fields)['public_efficiency_basis'] == fields['公开效率说明']
    del fields['公开效率说明']
    fields['效率'] = '实际八年。'
    with pytest.raises(ValueError, match='禁止阅读层'):
        project_b1(fields)


def test_cost_requires_every_gap_and_safe_explicit_links():
    row = {'public_basis':'损失已确认，但总量不明。','public_responsibility_window':'本人负责时期。',
           'public_unresolved_gaps':['后段缺乏材料。'], 'unresolved_gaps':['内部缺口'],
           'public_source_links':[{'label':'来源','url':'https://example.org/source'}],
           'cost_band':'C3','cost_position':'MID','evidence_status':'LOWER_BOUND'}
    assert project_cost(row)['public_basis'] == row['public_basis']
    with pytest.raises(ValueError, match='逐条保留'):
        project_cost({**row, 'public_unresolved_gaps':[]})
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
const {b1,cost}=new Function('esc','prose',helpers+';return {b1:firstB1Markup,cost:firstCostMarkup}')(esc,s=>'<p>'+esc(s)+'</p>');
const stages='先完成甲段。后完成乙段；两段分别计时，不据此推定总年数。';
assert.ok(b1({reader_public_b1:{public_efficiency_basis:stages}}).includes(stages));
const basis='完整依据。'.repeat(100)+'末尾责任限制不得删除。';
const html=cost({reader_public_cost:{public_basis:basis, public_responsibility_window:'只含本人时期。',public_unresolved_gaps:['上限尚不明确。'],public_source_links:[{label:'补充史料',url:'https://example.org/source'}]}});
for(const text of [basis,'只含本人时期。','上限尚不明确。','https://example.org/source']) assert.ok(html.includes(text));
for(const path of ['reader/home-interactions.js','reader/person-readability.js','reader/first-item-reading.js']) {
 const text=fs.readFileSync(path,'utf8');
 assert.ok(text.includes('firstB1Markup(item)'));
 assert.ok(text.includes('firstCostMarkup('));
}
''',encoding='utf-8')
    result=subprocess.run([node,str(script)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    assert result.returncode == 0,result.stderr
