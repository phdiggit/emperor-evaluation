from __future__ import annotations

from copy import deepcopy
import json
import pytest

from emperor_v4.evaluation.formal_json_store import load_json, write_json
from emperor_v4.evaluation.formal_reading_texts import FINANCE_SCHEMAS
from emperor_v4.evaluation.second_item_c_public import FORMAL_PATHS, PUBLIC_FORBIDDEN_RE, _refresh_payload, _scoring_signature, _clean, verify_source_bindings
from emperor_v4.evaluation.second_item_c_source_display import material_excerpts, reading_source


def test_c_material_citation_keeps_human_context_and_excludes_repository_links():
    public = reading_source({
        'path': 'docs/settlement.json#ruler_id=synthetic',
        'field_path': ['material_basis', 0, 'original_text'],
        'source_kind': '史料原文',
        'source_title': '《合成史书》卷三财政民生卡',
        'source_locator': 'material_basis / 0 / original_text；南郡；原文 https://example.org/volume-3',
        'source_url': 'https://github.com/example/repo/blob/main/data.jsonl',
        'public_source_context': '合成用例，臣下奏报南郡灾情。',
        'exact_quote': '南郡饥，民流亡。',
    })
    assert public == {
        'source_kind': '史料原文',
        'source_title': '《合成史书》卷三',
        'source_locator': '南郡',
        'source_urls': ['https://example.org/volume-3'],
        'source_context': '合成用例，臣下奏报南郡灾情。',
        'exact_quote': '南郡饥，民流亡。',
    }

def test_cross_item_axis_uses_its_own_meaning():
    assert _clean('第四项A独占身份后果，A记录制度。') == '第四项国家共同体与社会整合独占身份后果，制度建设记录制度。'
    assert '教育可及与人才流动' in _clean('第四项B')
    assert '知识生产与文化生态' in _clean('第四项C')


def test_grouped_material_retains_each_authored_passage_and_context():
    common = dict(source_kind='史料原文', source_title='《合成史书》卷三',
                  source_locator='material_basis / 0 / original_text', exact_quote='民饥。')
    report = dict(title='《合成史书》卷三', url='https://example.org/volume-3', text='南郡民饥。',
                  context='州臣就南郡灾情上奏。')
    reply = dict(title='《合成诏令》卷一', url='https://example.org/volume-1', text='朕命赈之。',
                 context='皇帝答复同一奏报，所涉为南郡。')
    sources = [dict(common, public_source_passages=[report]),
               dict(common, public_source_passages=[report, reply])]
    assert material_excerpts(sources) == [report, reply]
    assert material_excerpts([common, sources[1]]) == [dict(title='', url='', text='民饥。'), report, reply]


def _state_row(axis: str) -> dict:
    return {
        "ruler_id": f"SYNTHETIC-{axis}",
        "ruler_name": "合成甲",
        "main_band": f"{axis}-3",
        "loss_grade": "L1",
        "score": 12.5,
        "adjudication_reason": "主要阶段形成可运行结果，另有局部损害。",
        "material_limitations": ["战争成本和制度设计不在本轴重复计算。"],
        "state_adjudication": {
            "loss_review": {
                "grade": "L1",
                "main_representativeness": "主要阶段形成可运行结果。",
                "basis": "局部地区出现实际损害。",
            }
        },
    }


def _c4_row() -> dict:
    return {
        "ruler_id": "SYNTHETIC-C4",
        "ruler_name": "合成甲",
        "score": 3.0,
        "recovery_path_basis": {
            "C1": {"start_band": "C1-2", "highest_achieved_band": "C1-3", "retained_increment": True},
            "C2": {"start_band": "C2-3", "highest_achieved_band": "C2-3", "retained_increment": False},
            "C3": {"start_band": "C3-2", "highest_achieved_band": "C3-2", "retained_increment": False},
        },
        "recovery_chain_attributions": {
            "C1": {"grade": "SHARED", "basis": "共同掌权，无法拆分。"},
        },
        "recovery_attribution": {"grade": "SHARED", "basis": "共同掌权。"},
        "deterioration_path_basis": {
            "C1": {"attributable_drop": 0, "attribution_factor": 0},
            "C2": {"attributable_drop": 0, "attribution_factor": 0},
            "C3": {"attributable_drop": 0, "attribution_factor": 0},
        },
        "deterioration_penalty": 0.0,
        "destructive_amplification_grade": "DA0",
        "active_civilian_cost_review": {
            "choice_and_civilian_basis": "未发现独立额外民力对象。",
            "absorbed_and_excluded_basis": "纯军事投入不在本轴重复计算。",
        },
    }


def test_c_public_projection_keeps_scoring_fields_and_exposes_every_required_role():
    for axis, row in [("C1", _state_row("C1"))]:
        row.update(public_source_note='合成来源说明。', public_story='合成人物的具体经历。', public_adjudication_summary='当前证据只支持已证范围。',
                   public_boundary='只计本轴对象。', public_loss_label='已证损害，尚不能确认更大范围。',
                   public_evidence_items=[{'id':'C1-PUBLIC-SYNTHETIC','public_label':'实际结果',
                     'public_role':'主要状态','public_basis':'合成史料对应的事实。','public_boundary':None,
                     'source_refs':[{'path':'synthetic.json','source_title':'合成史料','source_locator':'合成章节',
                                    'source_kind':'合成引文'}]}])
        payload = {"records": [row]}
        before = deepcopy(payload)
        projected = _refresh_payload(axis, payload)
        expected_roles = {"主要状态"}
        actual = projected["records"][0]
        assert {item["public_role"] for item in actual["public_evidence_items"]} == expected_roles
        assert _scoring_signature(projected) == _scoring_signature(before)
        assert not PUBLIC_FORBIDDEN_RE.search(actual["public_adjudication_summary"])
        assert all(
            not PUBLIC_FORBIDDEN_RE.search(item[field])
            for item in actual["public_evidence_items"]
            for field in ("public_label", "public_role", "public_basis")
        )
        assert actual['public_story'] == before['records'][0]['public_story']
        assert actual['public_evidence_items'] == before['records'][0]['public_evidence_items']
        assert _refresh_payload(axis, deepcopy(projected)) == projected


def test_refresh_rejects_missing_authored_fields_instead_of_guessing():
    with pytest.raises(ValueError, match='直接维护'):
        _refresh_payload('C1', {'scores':[_state_row('C1')]})


@pytest.mark.parametrize('axis', ['C1', 'C2', 'C3', 'C4'])
def test_calculation_is_generated_read_only_from_current_fields(axis):
    from emperor_v4.evaluation.second_item_c_reading import calculation, calculation_record
    row = _c4_row() if axis == 'C4' else _state_row(axis)
    before = deepcopy(row)
    expanded = calculation_record(axis, row)
    assert expanded.pop('public_calculation') == calculation(axis, row)
    assert expanded == row == before
    expanded['ruler_name'] = '消费端修改'
    assert row == before
    row['score'] += 1
    assert calculation_record(axis, row)['public_calculation'] == calculation(axis, row)
    row['public_calculation'] = '旧副本'
    with pytest.raises(ValueError, match='生成副本'):
        calculation_record(axis, row)


def test_source_binding_resolves_exact_quote_and_same_person():
    person = 'SYNTHETIC-SOURCE'
    row = {'ruler_id':person, 'ruler_name':'合成乙',
           'material_basis':[{'original_text':'此为独立构造的原文；否定和数量均须保留。'}]}
    ref = {'axis':'C1', 'ruler_id':person,
           'path':FORMAL_PATHS['C1'].as_posix()+'#ruler_id='+person,
           'field_path':['material_basis',0,'original_text'],
           'exact_quote':row['material_basis'][0]['original_text']}
    row['public_evidence_items'] = [{'source_refs':[ref]}]
    row['public_related_source_refs'] = []
    data = {'C1':{'scores':[row]}}
    assert verify_source_bindings(data) == 1
    altered = deepcopy(data)
    altered['C1']['scores'][0]['public_evidence_items'][0]['source_refs'][0]['exact_quote'] = '删去了限制。'
    with pytest.raises(ValueError, match='摘录与原字段不一致'):
        verify_source_bindings(altered)
    altered = deepcopy(data)
    altered['C1']['scores'][0]['public_evidence_items'][0]['source_refs'][0]['ruler_id'] = 'OTHER'
    with pytest.raises(ValueError, match='人物或轴引用无效'):
        verify_source_bindings(altered)


def test_related_materials_are_locatable_without_becoming_claim_support():
    person = 'SYNTHETIC-MATERIAL'
    quote = '独立构造的材料，尚未用于证明具体事实。'
    ref = {'axis':'C1', 'ruler_id':person,
           'path':FORMAL_PATHS['C1'].as_posix()+'#ruler_id='+person,
           'field_path':['material_basis',0,'original_text'], 'exact_quote':quote}
    row = {'ruler_id':person, 'ruler_name':'合成材料',
           'material_basis':[{'original_text':quote}],
           'public_evidence_items':[{'source_refs':[]}], 'public_related_source_refs':[ref]}
    assert verify_source_bindings({'C1':{'scores':[row]}}) == 1
    row['material_basis'][0]['original_text'] = '不能靠改写摘录伪装为原文。'
    with pytest.raises(ValueError, match='摘录与原字段不一致'):
        verify_source_bindings({'C1':{'scores':[row]}})


def test_only_complete_contiguous_card_prose_is_shared_with_the_story():
    from emperor_v4.evaluation.reading_layout import evidence_repeated_in_story

    row = {
        "public_story": "春季减轻征收。\n\n秋季仓储增加。年末仍有局部饥荒。",
        "public_evidence_items": [
            {"id": "same", "public_basis": "春季减轻征收。秋季仓储增加。"},
            {"id": "partial", "public_basis": "仓储增加。"},
            {"id": "discontinuous", "public_basis": "春季减轻征收。年末仍有局部饥荒。"},
            {"id": "extra", "public_basis": "秋季仓储增加。新增储粮主要用于赈济。"},
        ],
    }
    assert evidence_repeated_in_story(row) == ["same"]


def test_state_display_keeps_a_qualification_absent_from_the_story():
    from emperor_v4.evaluation.second_item_c_reading import display_state_finding

    row = {
        "public_story": "春季减轻征收。秋季仓储增加。年末仍有局部饥荒。",
        "public_adjudication_summary": "秋季仓储增加。",
        "public_loss_label": "年末局部饥荒另有直接依据。",
    }
    assert display_state_finding("C1", row) == ("", row["public_loss_label"])
    row["public_adjudication_summary"] += "仅采用东部州县的结果。"
    assert display_state_finding("C1", row) == (row["public_adjudication_summary"], row["public_loss_label"])


def test_repeated_low_finding_keeps_individual_evidence_and_limits():
    from emperor_v4.evaluation.second_item_c_reading import display_evidence_basis

    label = "现有证据尚不足以确认另一段应单独计入的较差状态"
    row = {"loss_grade": "L0", "public_loss_label": label}
    item = {
        "evidence_mode": "ASSESSMENT",
        "source_binding_kind": "MATERIAL_COLLECTION",
        "public_basis": label + "；这不表示任内没有局部压力或损害。",
    }
    assert display_evidence_basis("C2", row, item) == ""
    direct = {**item, "source_binding_kind": "CLAIM_SUPPORT"}
    assert display_evidence_basis("C2", row, direct) == item["public_basis"]
    limited = {**item, "public_basis": item["public_basis"] + "动员损失限于西部。"}
    assert display_evidence_basis("C2", row, limited) == limited["public_basis"]


def test_axis_guide_shares_only_the_whole_final_boundary_paragraph():
    from emperor_v4.evaluation.second_item_c_reading import COMMON_AXIS_BOUNDARIES, specific_public_boundary

    common = COMMON_AXIS_BOUNDARIES["C1"]
    individual = "目前只核实了河内一地的家庭处境。"
    assert specific_public_boundary("C1", common) == ""
    assert specific_public_boundary("C1", individual + "\n\n" + common) == individual
    combined = individual + common
    assert specific_public_boundary("C1", combined) == combined
    assert specific_public_boundary("C2", common) == common


def test_routed_c_quote_resolves_cross_axis_and_detects_source_edits(tmp_path):
    schema = {axis: next(s for s in FINANCE_SCHEMAS if f'-{axis}-' in s) for axis in ('C1', 'C4')}
    paths = {axis: tmp_path / FORMAL_PATHS[axis].name for axis in schema}
    ruler = {'ruler_id': 'SYNTHETIC', 'ruler_name': '合成甲', 'polity': '合成朝'}
    quote = '原字段记录了两处受损，第三处未见材料。'
    source = {**ruler, 'material_basis': [{'original_text': quote}],
              'public_evidence_items': [], 'public_related_source_refs': []}
    ref = {'axis': 'C1', 'ruler_id': ruler['ruler_id'],
           'path': FORMAL_PATHS['C1'].as_posix() + '#ruler_id=SYNTHETIC',
           'field_path': ['material_basis', 0, 'original_text'], 'exact_quote': quote}
    citing = {**ruler, 'public_evidence_items': [{'source_refs': [deepcopy(ref)]}],
              'public_related_source_refs': [{**ref, 'public_excerpt': '这条另有公开摘录。'}]}
    payloads = {
        axis: {'schema_id': schema[axis], 'public_projection_axis': axis, 'scores': [row]}
        for axis, row in [('C1', source), ('C4', citing)]
    }
    for axis, payload in payloads.items():
        write_json(paths[axis], payload, ruler_polities={}, route=True)
    stored = json.loads((paths['C4'].with_suffix('') / '合成朝.json').read_bytes())
    stored_ref = stored['collections']['scores']['records'][0]['public_related_source_refs'][0]
    assert set(stored_ref['exact_quote']) == {'sha256'}
    assert load_json(paths['C4'], polities=iter(['合成朝'])) == payloads['C4']

    source['material_basis'][0]['original_text'] = '原字段改为只记录一处受损。'
    write_json(paths['C1'], payloads['C1'], ruler_polities={})
    with pytest.raises(ValueError, match='摘录与原字段不一致.*合成甲/C1/.*original_text'):
        load_json(paths['C4'])


def test_material_collection_cannot_masquerade_as_direct_claim_support():
    from emperor_v4.evaluation.second_item_c_public import _verify_payload
    row = _state_row('C1')
    row.update(public_story='合成的裁决叙述。', public_adjudication_summary='按已证范围判断。',
               public_boundary='仅本轴。', public_loss_label='尚未确认独立损害。',
               public_source_note='仅汇集材料，不建立逐条证明关系。',
               public_related_source_refs=[{'path':'synthetic.json'}],
               public_evidence_items=[{'id':'C1-PUBLIC-SYNTHETIC-MATERIAL',
                 'public_label':'裁决叙述','public_role':'主要状态','public_basis':'合成事实的现行判断。',
                 'public_boundary':None,'public_scope':'仅作材料汇集。',
                 'source_refs':[], 'source_binding_kind':'MATERIAL_COLLECTION','evidence_mode':'ASSESSMENT'}])
    payload = _refresh_payload('C1', {'records':[row]})
    report = _verify_payload('C1', payload)
    assert report['claim_support_item_count'] == 0
    assert report['material_collection_item_count'] == 1
    assert 'public_calculation' not in payload['records'][0]
    embedded = deepcopy(payload)
    embedded['records'][0]['public_calculation'] = '重新内嵌的生成副本'
    with pytest.raises(ValueError, match='生成副本'):
        _verify_payload('C1', embedded)
    assert 'public_calculation' not in _refresh_payload('C1', embedded)['records'][0]
    payload['records'][0]['public_evidence_items'][0]['evidence_mode'] = 'DIRECT'
    with pytest.raises(ValueError, match='材料汇集不能冒充逐条事实证明'):
        _verify_payload('C1', payload)


def test_upstream_language_keeps_negation_numbers_and_unresolved_evidence():
    source = '不把自然灾害归责本人。L2另扣4.5分；仍未闭合F3。'
    text = _clean(source)
    assert '不把自然灾害认定为本人造成' in text
    assert '4.5分' in text
    assert '仍未证实主要兵团组织严重毁损' in text
    with pytest.raises(ValueError, match='未明确转述'):
        _clean('未确认NEW_UNKNOWN_CODE，不能下结论。')
    with pytest.raises(ValueError, match='按原句明确转述'):
        _clean('字段重裁中仍有实质证据，不能直接删掉。')


def test_c4_authored_roles_and_boundaries_survive_refresh():
    from emperor_v4.evaluation.second_item_c_reading import RECOVERY_SECTIONS, recovery_story, recovery_public_record
    row = _c4_row()
    row['public_reading_sections'] = [dict(id=sid,title=title,body='恢复与本人责任分别有材料支持。') for sid,title in RECOVERY_SECTIONS]
    row.update(public_source_note='合成来源说明。', public_story=recovery_story(row['public_reading_sections']), public_adjudication_summary='独立损害与恢复分别结算。',
               public_boundary='已经计入的负担不重复计分。', public_loss_label='净调整。',
               public_evidence_items=[{'id':'C4-PUBLIC-SYNTHETIC-'+str(index),
                 'public_label':role,'public_role':role,'public_basis':text,'public_boundary':None,
                 'source_refs':[{'path':'synthetic.json','source_title':'合成材料',
                                 'source_locator':'合成位置','source_kind':'合成依据'}]}
                 for index,(role,text) in enumerate([
                   ('恢复','本人期内已保留的恢复。'),('责任范围','共同掌权，不能独占成果。'),
                   ('状态恶化','只计本人造成的可比下降。'),('额外代价','只计独立剩余负担。')])])
    before = deepcopy(row)
    actual = _refresh_payload('C4', {'records':[row]})['records'][0]
    assert 'public_story' not in actual
    assert recovery_public_record(actual)['public_story'] == before['public_story']
    for key in ('public_adjudication_summary','public_boundary','public_loss_label','public_evidence_items','public_reading_sections'):
        assert actual[key] == before[key]
    assert 'source_refs' in actual['public_evidence_items'][0]


def test_recovery_story_comes_from_current_sections_without_mutating_them():
    from emperor_v4.evaluation.second_item_c_reading import recovery_public_record
    row = _synthetic_recovery_reading()
    expected = row.pop('public_story')
    before = deepcopy(row)
    result = recovery_public_record(row)
    assert result['public_story'] == expected
    result['public_reading_sections'][0]['body'] = '消费端修改。'
    assert row == before
    row['public_reading_sections'][0]['body'] = '修订后的恢复说明。'
    assert '修订后的恢复说明。' in recovery_public_record(row)['public_story']
    row['public_story'] = '失配的旧副本。'
    with pytest.raises(ValueError, match='与分栏不同值'):
        recovery_public_record(row)


def _synthetic_recovery_reading(current=True):
    from emperor_v4.evaluation.second_item_c_reading import RECOVERY_SECTIONS, recovery_anchor_line, recovery_story
    row = {'ruler_name':'合成恢复对象', 'recovery_formula_version':'GOVERNANCE-STATE-RECOVERY-V4' if current else 'legacy',
           'positive_score_retained':8.0, 'deterioration_penalty':2.0, 'destructive_amplification_penalty':0.0, 'score':6.0,
           'recovery_path_basis':{a:{'start_band':a+'-2', 'highest_achieved_band':a+'-4'} for a in ('C1','C2','C3')}}
    row['public_reading_sections'] = [{'id':sid,'title':title,'body':'独立构造的说明。'} for sid,title in RECOVERY_SECTIONS]
    row['public_reading_sections'][1]['body'] = '\n\n'.join(recovery_anchor_line(a,row) for a in ('C1','C2','C3'))
    row['public_reading_sections'][5]['body'] = '保留恢复 +8分 − 本人恶化 2分 − 独立额外成本 0分 = 净调整 +6.0分。'
    row['public_story'] = recovery_story(row['public_reading_sections'])
    return row


def test_recovery_sections_require_complete_source_text_and_declared_anchors():
    from emperor_v4.evaluation.second_item_c_reading import verify_recovery_reading, recovery_story
    row = _synthetic_recovery_reading()
    before = deepcopy(row)
    verify_recovery_reading(row)
    assert row == before
    row['score'] = 7.0
    with pytest.raises(ValueError, match='净调整与正式数值不同值'):
        verify_recovery_reading(row)
    row = deepcopy(before)
    row['public_reading_sections'][1]['body'] = row['public_reading_sections'][1]['body'].replace('上升2档','上升1档')
    row['public_story'] = recovery_story(row['public_reading_sections'])
    with pytest.raises(ValueError, match='正式路径不同值'):
        verify_recovery_reading(row)
    row = _synthetic_recovery_reading()
    row['public_reading_sections'].pop()
    with pytest.raises(ValueError, match='分栏缺失'):
        verify_recovery_reading(row)


def test_legacy_recovery_cannot_present_adopted_high_point_as_current_handoff():
    from emperor_v4.evaluation.second_item_c_reading import verify_recovery_reading, recovery_story
    row = _synthetic_recovery_reading(current=False)
    assert '原恢复计算采用点' in row['public_reading_sections'][1]['body']
    with pytest.raises(ValueError, match='原机制边界'):
        verify_recovery_reading(row)
    row['public_reading_sections'][0]['body'] = '池外记录沿用原机制，采用点与交班终点分别说明。'
    row['public_story'] = recovery_story(row['public_reading_sections'])
    verify_recovery_reading(row)
