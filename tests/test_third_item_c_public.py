"""C public-reading contracts, with synthetic grading and dynamic source parity."""
import copy
import html
import json
import hashlib
from pathlib import Path
import runpy
import shutil
import subprocess
import pytest
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.third_item_c_public import calculation, reading_projection, verify_sources, markdown
from emperor_v4.evaluation.third_fourth_item_public import THIRD_C_PATH, _c_projection, _signature

ROOT = Path(__file__).resolve().parents[1]


def test_window_correction_resolves_legacy_difference_only_with_matching_review():
    from emperor_v4.evaluation.third_item_c_contract_reading import _opponent_grade_conflict
    opponent = dict(ref='SYNTHETIC-OPPONENT', grade='O4',
                    binding_status='SOURCE_WINDOW_REVIEWED', assessment_ref='SYNTHETIC-WINDOW')
    reviewed = dict(opponent_adjudication_notes={opponent['ref']: dict(
        basis='合成守军有区域征补与接续援军。', window_ref='SYNTHETIC-WINDOW')})
    assert not _opponent_grade_conflict('O2', [opponent], reviewed)
    assert _opponent_grade_conflict('O2', [opponent], {})
    stale = copy.deepcopy(reviewed)
    stale['opponent_adjudication_notes'][opponent['ref']]['window_ref'] = 'OTHER-WINDOW'
    assert _opponent_grade_conflict('O2', [opponent], stale)
    candidate = dict(opponent, binding_status='PUBLIC_TASK_CANDIDATE')
    assert _opponent_grade_conflict('O2', [candidate], reviewed)
    assert not _opponent_grade_conflict('O4', [opponent], {})


def test_local_material_review_keeps_non_system_and_missing_process_distinct():
    from emperor_v4.evaluation.third_item_c_contract_reading import _unresolved_opponent
    source = dict(actual_window='合成窗口', source_passages=[])
    entry = dict(label='合成营内兵变', basis='未证独立区域征补。', classification='NON_SYSTEM')
    result = _unresolved_opponent(entry, 'SYNTHETIC-CHAIN', [], source)
    assert result['grade'] == '未证独立体系'
    assert result['grade_range'] == []
    assert result['binding_status'] != 'SOURCE_WINDOW_REVIEWED'
    gap = _unresolved_opponent(dict(entry, classification='SOURCE_GAP'), 'SYNTHETIC-CHAIN', [], source)
    assert gap['grade'] == '缺具体过程'
    assert gap['source']
    with pytest.raises(ValueError, match='未知'):
        _unresolved_opponent(dict(entry, classification='UNREVIEWED_GUESS'), 'SYNTHETIC-CHAIN', [], source)


def test_excluded_window_is_visible_without_becoming_an_active_chain():
    from emperor_v4.evaluation.third_item_c_contract_reading import markdown_review, html_review
    row = synthetic()
    row['public_reading']['excluded_chain_reviews'] = [dict(
        chain_id='SYNTHETIC-OTHER-WINDOW', label='合成后任战事', basis='事件发生在评价窗口结束后。')]
    refresh_review(row)
    review = row['public_reading']['contract_review']
    assert review['chains'] == []
    assert '合成后任战事' in markdown_review(review)
    assert '事件发生在评价窗口结束后。' in html_review(review)
    assert '不计分' in html_review(review)


def test_audit_uses_explicit_material_links_and_preserves_judgment_prose():
    from emperor_v4.evaluation.third_item_c_public import AUDIT_TERMS, AUDIT_LINK_NOTE
    from emperor_v4.evaluation.third_item_c_contract_reading import html_review
    row = synthetic()
    row['strategy_chain_refs'] = ['SYNTHETIC-TASK']
    row['strategy_chains'] = [dict(chain_id='SYNTHETIC-TASK', label='合成围城', terminal_result_class='UNKNOWN')]
    row['public_reading']['evidence_items'][0]['c_chain_refs'] = ['SYNTHETIC-TASK']
    for axis in row['public_reading']['axes'].values():
        axis['arguments'] = [dict(evidence_ref='SYNTHETIC-EVIDENCE', reason='合成事实支持本轴判断。')]
    refresh_review(row)
    before = copy.deepcopy(row)
    refs = []
    def link(ref):
        if ref != 'SYNTHETIC-EVIDENCE':
            raise ValueError('未绑定')
        refs.append(ref)
        return '<a href="#synthetic-material">合成防御</a>'
    rendered = html_review(row['public_reading']['contract_review'], evidence_link=link)
    assert refs and set(refs) == {'SYNTHETIC-EVIDENCE'}
    assert '合成事实支持本轴判断。' in rendered and 'href="#synthetic-material"' in rendered
    for term, meaning in AUDIT_TERMS:
        assert html.escape(term) in rendered and html.escape(meaning) in rendered
    assert html.escape(AUDIT_LINK_NOTE) in rendered
    assert row == before
    row['public_reading']['contract_review']['axes']['C1']['evidence_refs'] = ['MISSING']
    with pytest.raises(ValueError, match='未绑定'):
        html_review(row['public_reading']['contract_review'], evidence_link=link)


def test_source_binding_locates_facts_without_adopting_new_axis_arguments():
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review
    row = synthetic()
    cid, eid = 'SYNTHETIC-TASK', 'SYNTHETIC-EVIDENCE'
    row['strategy_chain_refs'] = [cid]
    row['strategy_chains'] = [dict(chain_id=cid, label='合成防御任务', terminal_result_class='UNKNOWN')]
    item = row['public_reading']['evidence_items'][0]
    item.update(c_chain_refs=[cid], source_passages=[dict(path='synthetic.md', quote='甲乙两地防守成功。')])
    source = dict(source_material_refs=[eid], return_explanation='结果类别尚缺独立证据。', specific_gaps=[], source_passages=[])
    row['public_reading']['source_reviews'] = {cid: source}
    before = copy.deepcopy(row)
    review = build_review(row, {'systems': {}, 'o_grades': {}})
    assert review['chains'][0]['evidence_refs'] == [eid]
    assert all(not values for values in review['chains'][0]['axis_links'].values())
    assert row == before
    source.pop('source_material_refs')
    source['boundary_material_refs'] = [eid]
    review = build_review(row, {'systems': {}, 'o_grades': {}})
    assert review['chains'][0]['evidence_refs'] == []
    assert review['chains'][0]['boundary_evidence_refs'] == [eid]
    source['source_material_refs'] = [eid]
    with pytest.raises(ValueError, match='不得混用'):
        build_review(row, {'systems': {}, 'o_grades': {}})
    source.pop('boundary_material_refs')
    item['kind'] = '现行评价判断'
    with pytest.raises(ValueError, match='总体评价'):
        build_review(row, {'systems': {}, 'o_grades': {}})
    item['kind'] = '既有史实摘要'
    item['source_passages'] = []
    with pytest.raises(ValueError, match='来源摘录'):
        build_review(row, {'systems': {}, 'o_grades': {}})
    item['c_chain_refs'] = []
    with pytest.raises(ValueError, match='显式关联本链'):
        build_review(row, {'systems': {}, 'o_grades': {}})


def test_authored_task_caption_changes_no_chain_or_score_and_rejects_unbound_title():
    row = synthetic()
    row['strategy_chain_refs'] = ['SYNTHETIC-TASK']
    row['strategy_chains'] = [dict(chain_id='SYNTHETIC-TASK', label='战略链：INTERNAL',
                                   terminal_result_class='UNKNOWN')]
    row['public_reading']['chain_titles'] = {'SYNTHETIC-TASK': '甲城围攻与援军作战'}
    chains = copy.deepcopy(row['strategy_chains'])
    points = row['C_score_points']
    refresh_review(row)
    assert row['public_reading']['contract_review']['chains'][0]['title'] == '甲城围攻与援军作战'
    assert row['strategy_chains'] == chains
    assert row['C_score_points'] == points
    row['public_reading']['chain_titles']['NOT-AN-ADMITTED-TASK'] = '乙城作战'
    with pytest.raises(ValueError, match='公开任务标题'):
        refresh_review(row)


def test_removing_wrong_window_result_recalculates_quality_instead_of_only_prose():
    from emperor_v4.evaluation.third_item_c_strategy_chain import _chain_profile
    from emperor_v4.evaluation.five_dynasties_third_item import _apply_c_within_band_position
    row = synthetic()
    row.update(combat_delivery_grade='C1-3', operational_sustainability_cap='C2-3',
               system_reliability_cap='C3-3', axis_floor_grade='C-3', raw_grade='C-3')
    chains = [dict(chain_id='SYNTHETIC-OWN', terminal_result_class='NEGATIVE_RETURN'),
              dict(chain_id='SYNTHETIC-OTHER-WINDOW', terminal_result_class='NEGATIVE_RETURN')]
    row['strategy_chain_outcome_profile'] = _chain_profile(chains)
    _apply_c_within_band_position(row)
    before_points = row['C_score_points']
    row['strategy_chain_outcome_profile'] = _chain_profile(chains[:1])
    _apply_c_within_band_position(row)
    assert row['C_score_outcome_position'] == .375
    assert row['C_score_points'] > before_points
    assert row['final_grade'] == 'C-3'


def synthetic():
    row = dict(ruler_id='SYNTHETIC', ruler_name='合成人物',
        combat_delivery_grade='C1-4', operational_sustainability_cap='C2-4', system_reliability_cap='C3-4',
        axis_floor_grade='C-4', raw_grade='C-4', gate_cap=3, final_grade='C-3', C_overall_grade='C-3',
        C_score_band=dict(lower_rate=60, upper_rate=74), C_score_rate=70.5, C_score_points=35.2,
        C_score_band_position=.75, C_score_axis_surplus_position=.75, C_score_outcome_position=.2,
        strategy_chain_outcome_profile=dict(selected_chain_count=1, return_class_counts=dict(LOW_RETURN=1)),
        public_reading=dict(story='两路军队完成防御，第三方向仍失守。', window='合成时期',
          responsibility='只评价本人实际掌权阶段的国家军队。', boundary='不将继任者战争计给本人。',
          source_note='这是独立构造的合成用例，没有真实人物。',
          axes={axis:dict(basis=text, evidence_refs=['SYNTHETIC-EVIDENCE']) for axis,text in
                zip(('C1','C2','C3'),('主要防御任务完成。','跨年补充能够维持。','不同将领可以完成防御。'))},
          evidence_items=[dict(id='SYNTHETIC-EVIDENCE', label='合成防御', kind='既有史实摘要',
             text='甲乙两地防守成功。', scope='合成窗口', sources=[dict(path='synthetic.md',label='合成来源')])]))
    refresh_review(row)
    return row


def refresh_review(row):
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review
    row['public_reading']['contract_review'] = build_review(row, {'systems': {}, 'o_grades': {}})


def test_gate_changes_final_grade_without_rewriting_axes_or_averaging():
    row=synthetic(); before=copy.deepcopy(row)
    result=reading_projection(row)
    assert result['calculation']['axis_grades']==[4,4,4]
    assert result['calculation']['raw_grade']==4
    assert result['calculation']['final_grade']==3
    assert result['calculation']['points']==35.2
    assert '资格' in result['calculation']['cap_reason']
    assert row==before


def test_combat_title_and_guide_explain_the_whole_battle_without_rescoring():
    from emperor_v4.evaluation.third_item_c_public import COMBAT_GUIDE
    row = synthetic()
    before = copy.deepcopy(row)
    data = reading_projection(row)
    assert data['axes']['C1']['label'] == '实战表现'
    assert data['axes']['C1']['assessment_guide'] == COMBAT_GUIDE
    assert not data['axes']['C2']['assessment_guide'] and not data['axes']['C3']['assessment_guide']
    for term in ('目标完成程度', '对手强度', '完整交战过程', '可证战果', '己方战损', '战后续战能力',
                 '主力毁灭', '军令崩溃', '连续失效', '失载', '改写出兵目标'):
        assert term in COMBAT_GUIDE
    assert '攻城未克不自动等于全役战败' in COMBAT_GUIDE
    assert '有野战胜利或主力撤回也不自动支持高档' in COMBAT_GUIDE
    assert COMBAT_GUIDE in markdown(row)
    assert row == before


@pytest.mark.parametrize('status', [
    'SOURCE_SUPPORTED', 'ADJACENT_BOUNDARY_UNRESOLVED', 'INHERITED_LIMITED_ASSESSMENT',
    'CONTRACT_BOUNDARY_AMBIGUOUS', 'MATERIAL_EVIDENCE_MISSING', 'SOURCE_CONFLICT', 'SPECIFIC_SOURCE_GAP',
])
def test_review_status_is_projected_from_its_own_axis_without_changing_grades(status):
    from emperor_v4.evaluation.third_item_c_public import REVIEW_LABELS
    row = synthetic()
    review = row['public_reading']['contract_review']['axes']['C1']
    review.update(status=status, status_text='合成分界核查的具体限制。')
    before = copy.deepcopy(row)
    data = reading_projection(row)
    assert data['axes']['C1']['review_status'] == status
    assert data['axes']['C1']['review_label'] == REVIEW_LABELS[status]
    assert data['axes']['C1']['review_text'] == review['status_text']
    assert data['axes']['C2']['review_status'] != status or status == 'MATERIAL_EVIDENCE_MISSING'
    assert data['calculation']['axis_grades'] == [4, 4, 4]
    assert row == before
    row['public_reading']['contract_review']['axes']['C1']['status'] = 'UNDEFINED'
    with pytest.raises(ValueError, match='未知分界论证状态'):
        reading_projection(row)


@pytest.mark.parametrize('position,value,label', [('LOW', .25, '低位'), ('MID', .5, '中位'), ('HIGH', .75, '高位')])
def test_explicit_position_displays_adopted_value_original_reason_and_max_rule(position, value, label):
    row = synthetic()
    row.update(combat_delivery_grade='C1-3', operational_sustainability_cap='C2-3',
               system_reliability_cap='C3-3', axis_floor_grade='C-3', raw_grade='C-3',
               C_score_axis_surplus_position=0, C_score_band_position=value,
               C_score_rate=60 + 14 * value, C_score_points=round((60 + 14 * value) / 2, 1))
    reason = '合成反证与正面事实须一并权衡；原文符号 < 与 & 原样保留。'
    row['C_score_within_band_adjudication'] = dict(position=position, reason=reason)
    before = copy.deepcopy(row)
    text = calculation(row)['position']
    assert reason in text and label in text
    assert f'以{value}替代结果质量位置q' in text
    assert f'p=max(0, {value})={value}' in text
    assert row == before
    row['C_score_within_band_adjudication']['reason'] = ''
    with pytest.raises(ValueError, match='原裁决理由'):
        calculation(row)


def test_missing_necessary_axis_has_no_score_or_zero_substitution():
    row = synthetic()
    row.update(operational_sustainability_cap='UNKNOWN', axis_floor_grade='UNKNOWN',
               raw_grade='UNKNOWN', final_grade='UNKNOWN', C_overall_grade='UNKNOWN',
               C_score_points=None, C_score_rate=None, C_score_band_position=None)
    result = calculation(row)
    assert result['axis_grades'] == [4, None, 4]
    assert result['points'] is None and result['final_grade'] is None
    assert '暂不计分' in result['total_label']
    row['C_score_points'] = 0
    with pytest.raises(ValueError, match='不得按零分合成'):
        calculation(row)


def test_unknown_axis_review_and_projection_preserve_known_axis_evidence():
    row = synthetic()
    row.update(system_reliability_cap='UNKNOWN', axis_floor_grade='UNKNOWN',
               raw_grade='UNKNOWN', final_grade='UNKNOWN', C_overall_grade='UNKNOWN',
               C_score_points=None, C_score_rate=None, C_score_band_position=None)
    refresh_review(row)
    result = reading_projection(row)
    assert result['axes']['C1']['grade'] == 4
    assert result['axes']['C3']['grade'] is None
    assert result['axes']['C3']['grade_label'] == '待定'
    assert result['contract_review']['axes']['C3']['criterion'] == '必要证据不足，暂不定档'
    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown
    rendered = _render_formal_markdown('C', [row])
    assert '暂不计分' in rendered
    assert row['public_reading']['axes']['C3']['basis'] in rendered


def test_authored_prose_survives_projection_and_missing_fields_fail_closed():
    row=synthetic(); data=reading_projection(row)
    assert data['story']==row['public_reading']['story']
    projected=_c_projection(row)
    assert projected['public_reading']==row['public_reading']
    assert projected['public_axis_projections']['C2']['public_adjudication_summary']==data['axes']['C2']['basis']
    row['public_reading']['story']='第一项已经计分，第三项不再计入。'
    with pytest.raises(ValueError,match='公开正文无效'):reading_projection(row)
    row['public_reading']['story']=data['story']
    del row['public_reading']['axes']['C2']
    with pytest.raises(ValueError,match='分别维护'): reading_projection(row)


def test_repeated_axis_summary_or_unbound_evidence_is_rejected():
    row=synthetic();row['public_reading']['axes']['C2']['basis']=row['public_reading']['axes']['C1']['basis']
    with pytest.raises(ValueError,match='复用'):reading_projection(row)
    row=synthetic();row['public_reading']['axes']['C3']['evidence_refs']=['MISSING']
    with pytest.raises(ValueError,match='绑定'):reading_projection(row)


def test_overall_judgment_is_not_presented_as_concrete_war_evidence():
    row=synthetic()
    row['public_reading']['evidence_items'][0]['id']='C-DECISION'
    row['public_reading']['evidence_items'][0]['kind']='现行评价判断'
    for a in row['public_reading']['axes'].values():a['evidence_refs']=['C-DECISION']
    data=reading_projection(row)
    assert all(not a['materials'] and a['evidence_note'] for a in data['axes'].values())


def test_axis_argument_requires_specific_binding_and_explanation():
    row=synthetic()
    row['public_reading']['axes']['C1']['arguments']=[dict(evidence_ref='SYNTHETIC-EVIDENCE',reason='成功防守证明主要任务实际完成。')]
    data=reading_projection(row)
    assert data['axes']['C1']['materials'][0]['text']=='甲乙两地防守成功。'
    assert data['axes']['C1']['materials'][0]['reason']=='成功防守证明主要任务实际完成。'
    row['public_reading']['axes']['C1']['arguments'][0]['evidence_ref']='UNBOUND'
    with pytest.raises(ValueError,match='逐轴论证'):reading_projection(row)


def test_source_passage_must_exist_under_its_declared_heading(tmp_path,monkeypatch):
    from emperor_v4.evaluation import battle_registry_store
    from emperor_v4.evaluation import third_item_c_contract_reading
    monkeypatch.setattr(battle_registry_store,'load_battle_registry',lambda path:{'records':[]})
    monkeypatch.setattr(third_item_c_contract_reading,'load_context',lambda root:{'systems':{},'o_grades':{}})
    row=synthetic()
    (tmp_path/'synthetic.md').write_text('### SYNTHETIC-EVENT 合成战争\n甲地防御成功。\n\n### OTHER 另一战争\n乙地失守。\n',encoding='utf-8')
    evidence=row['public_reading']['evidence_items'][0]
    evidence['source_passages']=[dict(path='synthetic.md#SYNTHETIC-EVENT',quote='甲地防御成功。')]
    assert verify_sources(tmp_path,{'records':[row]})==1
    evidence['source_passages'][0]['quote']='乙地失守。'
    with pytest.raises(ValueError,match='摘录与所引原记录不一致'):verify_sources(tmp_path,{'records':[row]})


def test_top_grade_and_inherited_cap_are_explicit():
    row=synthetic()
    for key in ('combat_delivery_grade','operational_sustainability_cap','system_reliability_cap'):
        row[key]=row[key][:-1]+'5'
    row.update(raw_grade='C-5',axis_floor_grade='C-5',gate_cap=5,final_grade='C-5',C_overall_grade='C-5',
               C_score_band=dict(lower_rate=90,upper_rate=100),C_score_rate=100,C_score_points=50,
               C_score_band_position=1,C_score_axis_surplus_position=1,C_score_outcome_position=1)
    refresh_review(row)
    assert '满分50分' in calculation(row)['position']
    row=synthetic();row['system_observation_status']='INHERITED_UNTESTED'
    assert '未经过实战检验' in calculation(row)['cap_reason']


def test_inconsistent_score_is_rejected_without_repairing_it():
    row=synthetic();row['C_score_points']=49
    before=copy.deepcopy(row)
    with pytest.raises(ValueError,match='正式得分'):calculation(row)
    assert row==before


def test_current_sources_markdown_and_collection_cover_formal_records_dynamically():
    payload=load_json(ROOT/THIRD_C_PATH)
    before=copy.deepcopy(payload)
    assert verify_sources(ROOT,payload)==len(payload['records'])
    build=runpy.run_path(str(ROOT/'reader/build.py'))
    collection, assets=build['build_third_c_collection'](ROOT)
    search_index = json.loads(assets['search.json'])
    assert set(search_index) == {row['ruler_id'] for row in payload['records']}
    assert set(assets) == {'search.json'} | {row['ruler_id'] + '.html' for row in payload['records']}
    assert 'None档' not in collection and 'null档' not in collection
    for row in payload['records']:
        assert f"id='{row['ruler_id']}'" in collection
        entry = collection.split(f"<article id='{row['ruler_id']}'", 1)[1].split('</article>', 1)[0]
        summary = entry.split('</summary>', 1)[0]
        detail = assets[row['ruler_id'] + '.html']
        assert "data-detail-url='data/third-item-c/" in entry
        assert '?v=' + hashlib.sha256(detail.encode('utf-8')).hexdigest()[:16] in entry
        assert 'third-c-material' not in entry
        assert 'third-c-detail-slot' in entry
        data=reading_projection(row)
        text=markdown(row)
        for term, meaning in data['audit_terms']:
            assert html.escape(term) in detail and html.escape(meaning) in detail
        assert data['story'] in text
        story_parts = [html.escape(part) for part in data['story'].split('\n\n') if part]
        story_positions = [detail.index(part) for part in story_parts]
        assert story_positions == sorted(story_positions)
        for axis in data['axes'].values():
            assert axis['basis'] in text
            assert axis['review_text'] in text
            assert html.escape(axis['review_label']) in summary
            assert f"data-review-status='{axis['review_status']}'" in summary
            assert html.escape(build['third_c_grade_meaning'](axis)) in summary
            assert all(html.escape(part) in detail for part in axis['basis'].split('\n\n'))
            if axis['assessment_guide']:
                for part in axis['assessment_guide'].split('\n\n'):
                    assert html.escape(part) in detail and html.escape(part) in collection
                    assert part in text
            for e in axis['materials']:
                assert f"data-c-material-ref='{html.escape(row['ruler_id'] + '--evidence--' + e['id'])}'" in detail
                if e.get('reason'):
                    assert all(html.escape(part) in detail for part in e['reason'].split('\n\n'))
        for e in data['evidence_items']:
            assert detail.count(f"data-c-evidence='{html.escape(e['id'])}'") == 1
            assert f"id='{html.escape(row['ruler_id'] + '--evidence--' + e['id'])}'" in detail
            for part in e['text'].split('\n\n'):
                assert html.escape(part) in detail
                assert part in search_index[row['ruler_id']]
            for source in e['sources']:
                assert html.escape(source['path']) in detail
            for passage in e.get('source_passages', []):
                assert html.escape(passage['quote']) in detail
        explicit = row.get('C_score_within_band_adjudication')
        if explicit:
            assert explicit['reason'] in text
            assert html.escape(explicit['reason']) in detail
        for chain in data['contract_review']['chains']:
            assert chain['chain_id'] in text and html.escape(chain['chain_id']) in detail
            assert all(ref in text and html.escape(ref) in detail for ref in chain['parent_refs'])
            for ref in chain['evidence_refs'] + chain.get('boundary_evidence_refs', []):
                assert f"data-c-material-ref='{html.escape(row['ruler_id'] + '--evidence--' + ref)}'" in detail
            for values in chain['axis_links'].values():
                for link in values:
                    assert html.escape(link['reason']) in detail
                    assert f"data-c-material-ref='{html.escape(row['ruler_id'] + '--evidence--' + link['evidence_ref'])}'" in detail
        for axis in data['contract_review']['axes'].values():
            assert axis['against_lower'] in text and html.escape(axis['against_lower']) in detail
            assert axis['against_upper'] in text and html.escape(axis['against_upper']) in detail
            for ref in axis['evidence_refs'] + axis.get('authored_finding_evidence_refs', []):
                assert f"data-c-material-ref='{html.escape(row['ruler_id'] + '--evidence--' + ref)}'" in detail
        assert _signature(_c_projection(row))=='{}'
    assert payload==before


def test_shared_renderer_displays_all_current_readings_without_semantic_replacement(tmp_path):
    if not shutil.which('node'):pytest.skip('Node required for rendering')
    records=[reading_projection(row) for row in load_json(ROOT/THIRD_C_PATH)['records']]
    source=tmp_path/'readings.json';source.write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8')
    script=tmp_path/'render.cjs'
    script.write_text(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const assertProse=(out,text)=>{for(const paragraph of String(text).split(/\n\n+/))assert.ok(out.includes(esc(paragraph)));};
const context={link:(path,label)=>`<a href="${esc(path)}">${esc(label)}</a>`};
vm.createContext(context);
vm.runInContext(fs.readFileSync('reader/third-item-c-public.js','utf8'),context);
const labels=fs.readFileSync('reader/second-item-public-labels.js','utf8');
vm.runInContext(labels.slice(labels.indexOf('  function currentPersonId()'),labels.indexOf('  function ensureStyles()'))+'\nthis.patchEntry=patchPersonNetEvidence;',context);
for(const data of JSON.parse(fs.readFileSync(process.argv[2],'utf8'))){
  const item={reader_public_third_c:data};
  const out=context.ThirdItemCReading.heading(item)+context.ThirdItemCReading.html(item,{});
  if(data.calculation.points===null){
    assert.ok(out.includes('暂不计分'));
    assert.ok(!out.includes('null档') && !out.includes('undefined'));
  }
  assertProse(out,data.story);
  assert.ok(out.includes('data-contract-reading'));
  for(const [term,meaning] of data.audit_terms){assertProse(out,term);assertProse(out,meaning);}
  assertProse(out,data.audit_link_note);
  for(const chain of data.contract_review.chains){
    assert.ok(out.includes(esc(chain.chain_id)));
    assert.ok(out.includes(esc(chain.title)));
    assertProse(out,chain.result_basis);
    for(const ref of [...chain.evidence_refs,...(chain.boundary_evidence_refs||[])])assert.ok(out.includes(`data-c-local-evidence="${esc(ref)}"`));
    if(chain.boundary_evidence_refs?.length)assert.ok(out.includes('范围核对材料（不作本人战事采用）'));
    for(const parent of chain.parent_refs)assert.ok(out.includes(esc(parent)));
    for(const gap of chain.gaps)assert.ok(out.includes(esc(gap)));
    for(const opponent of chain.opponents)assert.ok(out.includes(esc(opponent.basis)));
    for(const values of Object.values(chain.axis_links))for(const v of values){
      assertProse(out,v.reason);
      assert.ok(out.includes(`data-c-local-evidence="${esc(v.evidence_ref)}"`));
    }
  }
  for(const a of Object.values(data.contract_review.axes)){
    for(const key of ['status_text','against_lower','against_upper','counterevidence_review'])assert.ok(out.includes(esc(a[key])));
    for(const ref of [...a.evidence_refs,...(a.authored_finding_evidence_refs||[])]){
      assert.ok(out.includes(`data-c-local-evidence="${esc(ref)}"`));
      assert.ok(out.includes('third-item-c.html#'+encodeURIComponent(data.ruler_id+'--evidence--'+ref)));
    }
  }
  const overview=out.split('aria-label="三方面的正式判断">')[1].split('</div><details')[0];
  for(const a of Object.values(data.axes)){
    assert.ok(overview.includes(esc(a.review_label)));
    assert.ok(overview.includes(`data-review-status="${esc(a.review_status)}"`));
    assertProse(out,a.review_text);
    assertProse(out,a.basis);
    if(a.assessment_guide)assertProse(out,a.assessment_guide);
  }
  assertProse(out,data.review_note);
  for(const a of Object.values(data.axes))for(const e of a.materials){
    assertProse(out,e.text);
    if(e.reason)assert.ok(out.includes(esc(e.reason)));
    for(const p of e.source_passages||[])assert.ok(out.includes(esc(p.quote)));
  }
  for(const e of data.evidence_items){assert.ok(out.includes(esc(e.label)));assertProse(out,e.text);}
  for(const e of data.contract_review.excluded_chain_reviews||[]){assert.ok(out.includes(esc(e.label)));assertProse(out,e.basis);}
  for(const key of ['grade_path','cap_reason','outcome_text','position','formula'])assertProse(out,data.calculation[key]);
  const panel={dataset:{},querySelector:()=>({textContent:'统治绩效构成'}),innerHTML:''};
  context.document={getElementById:()=>({querySelectorAll:()=>[panel]})};
  context.location={hash:'#person/'+data.ruler_id};
  context.esc=esc;
  context.byId=new Map([[data.ruler_id,{detail_loaded:true,net:{component_details:{military:[item]}}}]]);
  context.patchEntry();
  assert.ok(panel.innerHTML.includes('data-third-c-public-overview'));
  assertProse(panel.innerHTML,data.story);
}
''',encoding='utf-8')
    subprocess.run(['node',str(script),str(source)],cwd=ROOT,check=True,capture_output=True,text=True)


def test_contract_chain_members_are_evidence_not_extra_scoring_units():
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review
    row=synthetic();before=copy.deepcopy(row)
    row['strategy_chain_refs']=['CHAIN'];row['strategy_chains']=[dict(chain_id='CHAIN',label='合成守城',member_parent_refs=['PARENT-A','PARENT-B'],terminal_result_class='UNKNOWN')]
    for field in ('combat_delivery_grade','system_reliability_cap'):row[field]=row[field][:-1]+'3'
    result=build_review(row,{'systems':{},'o_grades':{}})
    assert len(result['chains'])==1 and result['chains'][0]['parent_refs']==['PARENT-A','PARENT-B']
    assert result['chains'][0]['result_label']=='未明确分类'
    assert not result['chains'][0]['major_failure']
    assert '不满足提高到四档' in result['axes']['C1']['against_upper']
    assert result['axes']['C1']['status']!='PROVED'
    assert row['C_score_points']==before['C_score_points']


def test_opponent_candidate_conflict_is_visible_and_never_rewrites_a_grade():
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review,validate_review
    row=synthetic();row['strategy_chain_refs']=['CHAIN']
    row['strategy_chains']=[dict(chain_id='CHAIN',label='合成远征',member_parent_refs=['PARENT-A'],opponent_grade='O3',terminal_result_class='LOW_RETURN')]
    context={'systems':{'OPP':dict(opponent_label='合成区域机器',organization_grade='O4',basis='有持续征补和供给。',source_campaign_refs=['PARENT-A'])},'o_grades':{}}
    before=copy.deepcopy(row)
    result=build_review(row,context)
    c=result['chains'][0]
    assert c['opponent_conflict'] and c['opponents'][0]['binding_status']=='PUBLIC_TASK_CANDIDATE'
    assert c['legacy_opponent_grade']=='O3' and c['opponents'][0]['grade']=='O4'
    assert row==before
    row['public_reading']['contract_review']=result
    validate_review(row,context)
    row['public_reading']['contract_review']['chains'][0]['opponents'][0]['grade']='O6'
    with pytest.raises(ValueError,match='不一致'):validate_review(row,context)


def test_missing_contract_review_and_partial_chain_coverage_fail_closed():
    from emperor_v4.evaluation.third_item_c_contract_reading import validate_review
    row=synthetic();del row['public_reading']['contract_review']
    with pytest.raises(ValueError,match='缺少完整合同论证'):reading_projection(row)
    row=synthetic();row['strategy_chain_refs']=['UNEXPLAINED']
    with pytest.raises(ValueError,match='未完整覆盖'):validate_review(row)


def test_public_opponent_terms_are_allowed_without_accepting_internal_codes():
    from emperor_v4.evaluation.third_fourth_item_public import PUBLIC_FORBIDDEN_RE
    assert PUBLIC_FORBIDDEN_RE.search('对手O4与O6的实际窗口不同。') is None
    assert PUBLIC_FORBIDDEN_RE.search('RETRO4')
    assert PUBLIC_FORBIDDEN_RE.search('O7')
    assert PUBLIC_FORBIDDEN_RE.search('O4_UNKNOWN')


def test_capability_chain_and_unknown_return_are_not_current_results_or_failures():
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review
    row=synthetic();row['capability_only_strategy_chain_refs']=['CAP']
    row['capability_only_strategy_chains']=[dict(chain_id='CAP',label='合成先前战争',source_event_refs=['PARENT'],terminal_result_class='UNKNOWN')]
    result=build_review(row,{'systems':{},'o_grades':{}})
    assert result['chains'][0]['consumption']=='CAPABILITY_ONLY'
    assert '不进入当前回报质量' in result['chains'][0]['consumption_text']
    assert not result['chains'][0]['major_failure']
    assert result['axes']['C2']['status']=='MATERIAL_EVIDENCE_MISSING'


def test_parent_boundary_evidence_is_scoped_to_the_evaluated_ruler():
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review
    row=synthetic();row['strategy_chain_refs']=['CHAIN']
    row['strategy_chains']=[dict(chain_id='CHAIN',label='合成边防',member_parent_refs=['PARENT'])]
    entry=dict(evidence_status='CLOSED',source_refs=['synthetic.md'])
    context={'systems':{},'o_grades':{},'parent_cycles':{('OTHER-RULER','PARENT'):entry}}
    result=build_review(row,context)
    assert result['chains'][0]['parent_evidence'][0]['evidence_status']=='NOT_BOUND'
    context['parent_cycles'][(row['ruler_id'],'PARENT')]=entry
    assert build_review(row,context)['chains'][0]['parent_evidence'][0]['evidence_status']=='CLOSED'


def test_conflict_within_high_opponent_range_does_not_remove_high_difficulty():
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review
    row=synthetic();row['combat_delivery_grade']='C1-5'
    row['strategy_chain_refs']=[f'CHAIN-{i}' for i in range(3)]
    row['strategy_chains']=[dict(chain_id=c,label='合成高难战争',member_parent_refs=[f'TASK-{i}'],opponent_grade='O5') for i,c in enumerate(row['strategy_chain_refs'])]
    context={'systems':{f'OPP-{i}':dict(opponent_label='合成强敌',organization_grade='O6',basis='实际压迫核心目标。',source_campaign_refs=[f'TASK-{i}']) for i in range(3)},'o_grades':{}}
    row['c5_axis_gate']={'C1_O4_plus_opponent_systems':[dict(opponent_system_ref=f'OPP-{i}',opponent_label='合成强敌',organization_grade='O6',task_refs=[f'TASK-{i}']) for i in range(3)]}
    result=build_review(row,context)
    assert all(c['opponent_conflict'] for c in result['chains'])
    assert not any('至少三条' in text for text in result['axes']['C1']['limitations'])
    assert result['axes']['C1']['status']=='MATERIAL_EVIDENCE_MISSING'


def test_owned_opponent_phases_keep_one_identity_and_do_not_leak_between_people():
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review
    row=synthetic();row['strategy_chain_refs']=['CHAIN']
    row['strategy_chains']=[dict(chain_id='CHAIN',label='合成跨期防御',member_parent_refs=['TASK'])]
    windows={key:dict(subject_ruler_id=who,source_chain_refs=['CHAIN'],opponent_label='合成对手',organization_grade=g,actual_competition_window=window,basis='所引阶段的实际区域军政组织。',source_campaign_refs=['TASK'])
             for key,who,g,window in [('EARLY',row['ruler_id'],'O5','前段'),('LATE',row['ruler_id'],'O3','后段'),('OTHER','OTHER-RULER','O6','他人阶段')]}
    context={'systems':{'SAME-MACHINE':dict(opponent_label='合成国家',organization_grade='O5',basis='总体登记。',source_campaign_refs=['TASK'],window_assessments=windows)},'o_grades':{}}
    before=copy.deepcopy(row);result=build_review(row,context)
    values=result['chains'][0]['opponents']
    assert {(v['window'],v['grade']) for v in values}=={('前段','O5'),('后段','O3')}
    assert {v['ref'] for v in values}=={'SAME-MACHINE'}
    assert row==before


def test_public_capability_group_requires_prior_admission_and_cannot_duplicate_a_chain():
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review,validate_review
    row=synthetic();before=copy.deepcopy(row)
    group=dict(chain_id='PUBLIC-CAP',label='合成能力补证',source_parent_refs=['ADMITTED'],basis='同一目标及终局。')
    row['public_reading']['additional_capability_chains']=[group]
    with pytest.raises(ValueError,match='准入'):build_review(row,{'systems':{},'o_grades':{}})
    row['capability_only_parent_refs']=['ADMITTED']
    result=build_review(row,{'systems':{},'o_grades':{}})
    assert result['chains'][0]['consumption']=='CAPABILITY_ONLY'
    assert '未改写正式战略链台账' in result['chains'][0]['consumption_text']
    assert not result['chains'][0]['major_success']
    row['public_reading']['contract_review']=result;validate_review(row)
    assert row['strategy_chain_outcome_profile']==before['strategy_chain_outcome_profile']
    assert row['C_score_points']==before['C_score_points']
    row['capability_only_strategy_chains']=[dict(chain_id='EXISTING',source_parent_refs=['ADMITTED'])]
    row['capability_only_strategy_chain_refs']=['EXISTING']
    with pytest.raises(ValueError,match='重复'):build_review(row,{'systems':{},'o_grades':{}})


def test_object_review_with_ownership_conflict_is_not_an_admitted_high_window():
    from emperor_v4.evaluation.third_item_c_contract_reading import build_review
    row=synthetic();row['strategy_chain_refs']=['CHAIN']
    row['strategy_chains']=[dict(chain_id='CHAIN',label='合成交班任务',member_parent_refs=['TASK'])]
    row['public_reading']['source_reviews']={'CHAIN':dict(opponent_refs=['OPP'],admissibility_conflict=True,admissibility_conflict_basis='合成原段位于前任窗口。',actual_window='前任阶段',source_passages=[dict(path='synthetic.md',quote='合成引文。')],reviewed_parent_refs=['TASK'],return_explanation='前任阶段，不能计给本人。',specific_gaps=['本人并未接令或交手。'])}
    entry=dict(subject_ruler_id=row['ruler_id'],source_chain_refs=['CHAIN'],opponent_label='合成国家',organization_grade='O5',actual_competition_window='前任阶段',basis='实际对象可识别。',source_campaign_refs=['TASK'])
    context={'systems':{'OPP':dict(opponent_label='合成国家',organization_grade='O5',basis='总体。',source_campaign_refs=['TASK'],window_assessments={'PHASE':entry})},'o_grades':{}}
    result=build_review(row,context)
    assert result['chains'][0]['opponents'][0]['binding_status']=='SOURCE_OBJECT_ONLY'
    assert '合成原段位于前任窗口。' in result['chains'][0]['opponents'][0]['scope_note']
    assert '不参加本人高难任务证明' in result['chains'][0]['opponents'][0]['scope_note']
    assert result['chains'][0]['gaps']==['本人并未接令或交手。']
