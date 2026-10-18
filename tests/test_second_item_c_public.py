from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import pytest

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_c_public import (
    FORMAL_PATHS,
    PUBLIC_FORBIDDEN_RE,
    _refresh_payload,
    _scoring_signature,
    verify_public_projection,
    _clean,
    verify_source_bindings,
)


def test_cross_item_axis_uses_its_own_meaning():
    assert _clean('第四项A独占身份后果，A记录制度。') == '第四项国家共同体与社会整合独占身份后果，制度建设记录制度。'
    assert '教育可及与人才流动' in _clean('第四项B')
    assert '知识生产与文化生态' in _clean('第四项C')


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
        row.update(public_story='合成人物的具体经历。', public_adjudication_summary='当前证据只支持已证范围。',
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
    payload['records'][0]['public_evidence_items'][0]['evidence_mode'] = 'DIRECT'
    with pytest.raises(ValueError, match='材料汇集不能冒充逐条事实证明'):
        _verify_payload('C1', payload)


def test_state_calculation_keeps_floor_and_minimum_proven_boundary():
    from emperor_v4.evaluation.second_item_c_reading import calculation
    from emperor_v4.evaluation.governance_state_recovery import FIXED_POINTS
    row = {'main_band':'C1-1', 'loss_grade':'L1', 'score':FIXED_POINTS['C1'][0]}
    text = calculation('C1', row)
    assert 'max（本轴最低分' in text
    assert '3%' in text
    assert '只在最后' in text
    assert '损害轻微' not in text


def test_current_c_public_projection_covers_the_same_formal_people():
    root = Path(__file__).resolve().parents[1]
    report = verify_public_projection(root)
    assert report["record_count"] == len(
        load_json(root / FORMAL_PATHS["C1"])["scores"]
    )
    assert set(report["axis_reports"]) == set(FORMAL_PATHS)


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
    row = _c4_row()
    row.update(public_story='恢复与本人责任分别有材料支持。', public_adjudication_summary='独立损害与恢复分别结算。',
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
    for key in ('public_story','public_adjudication_summary','public_boundary','public_loss_label','public_evidence_items'):
        assert actual[key] == before[key]
    assert 'source_refs' in actual['public_evidence_items'][0]
