from pathlib import Path
import json
import shutil
import subprocess

import pytest

from emperor_v4.evaluation.first_item_c_public import (
    load_first_item_c_public, parse_declared_battles, project_commander,
    public_commander_for_name,
)

ROOT = Path(__file__).resolve().parents[1]


def synthetic_fields():
    return {'公开裁决依据': '正面表现不能掩盖失败。', '公开责任边界': '只确认本人统筹。',
            '公开阅读问题': '失利后怎样重新组织？', '公开阅读正文': '主帅重整队伍，再次进军。',
            '评价窗口': '本次建基战争。', '本人责任与独立案例': '一个完整任务，受挫与恢复合看。',
            '统一链受挫清单': '[]', 'C结算': '20/40（C-3-LOW）。'}


def test_battles_require_explicit_roles_and_preserve_declared_order():
    rows = parse_declared_battles('乙战｜战略统筹｜A｜—；甲战｜前线作战｜S-｜D3。')
    assert rows == [
        {'name': '乙战', 'role': '战略统筹', 'result': 'A', 'difficulty': ''},
        {'name': '甲战', 'role': '前线作战', 'result': 'S−', 'difficulty': 'A'},
    ]
    with pytest.raises(ValueError, match='禁止从判词补猜'):
        parse_declared_battles('甲战取得大捷，由谁指挥尚不明确。')
    with pytest.raises(ValueError, match='重复'):
        parse_declared_battles('甲战｜前线作战｜A｜D2；甲战｜战略统筹｜A｜—')


def test_narrative_never_creates_battle_entries_or_replaces_missing_public_prose():
    fields = synthetic_fields()
    fields['结算依据'] = '甲战S/D3可能属于将领。'
    assert project_commander(fields)['public_battles'] == []
    del fields['公开裁决依据']
    with pytest.raises(ValueError, match='禁止用内部判词回退'):
        project_commander(fields)


@pytest.mark.parametrize('field', ['公开阅读问题', '公开阅读正文', '评价窗口', '本人责任与独立案例', '统一链受挫清单'])
def test_missing_declared_reading_input_fails_closed(field):
    fields = synthetic_fields()
    del fields[field]
    with pytest.raises(ValueError):
        project_commander(fields)


def test_setbacks_are_explicit_and_grade_points_follow_contract():
    fields = synthetic_fields()
    fields['统一链受挫清单'] = json.dumps([{'name': '甲战前段', 'direction': '成败混合', 'process': '受挫后重组，损失保留。'}], ensure_ascii=False)
    projected = project_commander(fields)
    assert projected['public_setbacks'][0]['process'] == '受挫后重组，损失保留。'
    assert projected['total_points'] == 20
    fields['C结算'] = '23/40（C-3-LOW）。'
    with pytest.raises(ValueError, match='不同值'):
        project_commander(fields)
    fields = synthetic_fields()
    fields['统一链受挫清单'] = '[{"name":"甲战","direction":"UNKNOWN","process":"不猜结果。"}]'
    with pytest.raises(ValueError, match='方向未知'):
        project_commander(fields)


def test_total_view_keeps_repeated_public_fields_in_their_component():
    from emperor_v4.evaluation.first_item_markdown_settlement import _component_fields_by_person
    text = '''### 1. 合成人物

**B2｜组织：6/30**
- **公开阅读问题**：怎样分工？
- **材料来源**：组织证据。

**C｜统帅：20/40**
- **公开阅读问题**：怎样反击？
- **材料来源**：战争证据。
'''
    assert _component_fields_by_person(text, 'B2')['合成人物']['公开阅读问题'] == '怎样分工？'
    assert _component_fields_by_person(text, 'C')['合成人物']['材料来源'] == '战争证据。'


def test_current_reader_commander_fields_match_current_formal_source():
    public = load_first_item_c_public(ROOT)
    seen = set()
    for path in (ROOT / 'reader/data/people').glob('*.json'):
        record = json.loads(path.read_text(encoding='utf-8'))['record']
        net = record.get('net') or {}
        if net.get('first_item_status') != 'APPLICABLE':
            continue
        item = next(item for item in net['component_details']['first'] if item['label'] == 'C军事统帅与战争解题')
        expected = public_commander_for_name(public, record['ruler_name'])
        assert item['reader_public_commander'] == expected
        assert item['reader_summary'] == expected['public_story']
        assert item['reader_boundary'] == expected['public_boundary']
        seen.add(record['ruler_id'])
    assert seen


def test_all_browser_paths_render_basis_and_boundary_even_with_battles(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for browser behavior')
    script = tmp_path / 'commander.cjs'
    script.write_text(r'''
const fs=require('node:fs'), assert=require('node:assert/strict');
const source=fs.readFileSync('reader/home-interactions.js','utf8');
const fn=source.match(/function firstCommanderMarkup\(item, record\) {[\s\S]*?\n}\n/)[0];
const escape=text=>String(text).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const render=new Function('esc','prose','link',fn+';return firstCommanderMarkup;')(escape,text=>'<p>'+escape(text)+'</p>',()=>'<a>来源</a>');
const publicData={public_basis:'正面表现不能掩盖失败。',public_boundary:'不属于本人指挥。<原句>',
 public_question:'主帅怎样应对受挫？',public_story:'本人重整队伍再次进军。',public_window:'本次战争。',public_cases:'一个复合周期。',total_points:20,
 public_setbacks:[{name:'甲战前段',direction:'受阻',process:'目标未完成，损失保留。'}],public_method:'按当前合同评价。',public_sources:[],
 public_battles:[{name:'甲战',role:'战略统筹',result:'A',difficulty:''}]};
const html=render({reader_public_commander:publicData});
assert.ok(html.includes(publicData.public_basis));
assert.ok(html.includes(escape(publicData.public_boundary)));
assert.ok(html.includes('战略统筹'));
assert.ok(html.includes('任务难度：未单列'));
assert.ok(html.includes('不是人物画像等级'));
assert.ok(!html.includes('前线作战'));
assert.ok(html.indexOf(publicData.public_story)<html.indexOf('first-c-facts'));
assert.ok(html.indexOf('first-c-facts')<html.indexOf('first-c-method'));
assert.ok(html.includes('目标未完成，损失保留。'));
assert.ok(!/<details[^>]*\bopen\b/.test(html));
assert.ok(!render({reader_public_commander:{...publicData,public_battles:[]}}).includes('first-item-battles'));
assert.ok(render({reader_summary:'甲战取得大捷'}).includes('公开说明尚未同步'));
''', encoding='utf-8')
    result = subprocess.run([node, str(script)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
