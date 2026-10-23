from __future__ import annotations

import copy
import pytest
from pathlib import Path

from emperor_v4.evaluation import third_fourth_item_public as public
from emperor_v4.evaluation.third_fourth_public_language import translate, language_domain


ROOT = Path(__file__).resolve().parents[1]


def test_projection_preserves_source_containers_and_only_replaces_owned_derived_fields():
    row = dict(score=7, public_reading=dict(story='人工正文'),
               public_b_source_catalog={'S':dict(path='source.md')},
               public_basis='当前归责说明', public_adjudication_summary='旧投影', public_axis_projections={})
    before = copy.deepcopy(row)
    projection = dict(public_adjudication_summary='新投影')
    public._apply_projection(row, projection)
    assert row == {k:v for k,v in dict(before, **projection).items() if k!='public_axis_projections'}
    row['public_reading']['story'] = '人工编辑'
    assert projection == dict(public_adjudication_summary='新投影')


def test_noop_projection_refresh_keeps_source_and_derived_field_order():
    import json
    row = dict(score=7, public_adjudication_summary='当前投影', public_reading=dict(story='人工正文'))
    before = json.dumps(row, ensure_ascii=False)
    public._apply_projection(row, dict(public_reading=copy.deepcopy(row['public_reading']),
                                      public_adjudication_summary='当前投影'))
    assert json.dumps(row, ensure_ascii=False) == before


@pytest.mark.parametrize('field', ['public_reading','public_b_source_catalog','public_c_result_reading','public_exclusion_reading'])
def test_projection_rejects_implicit_source_overwrite_without_partial_mutation(field):
    row = {field:dict(text='人工维护'), 'public_adjudication_summary':'旧投影'}
    before = copy.deepcopy(row)
    with pytest.raises(ValueError, match='不得改写人工来源'):
        public._apply_projection(row, {field:dict(text='不同正文')})
    assert row == before


def test_projection_rejects_unknown_fields_and_requires_explicit_retirement():
    row = dict(public_reading=dict(story='旧重复正文'), public_adjudication_summary='旧投影')
    public._apply_projection(row, {}, retired_sources={'public_reading'})
    assert row == {}
    with pytest.raises(ValueError, match='未声明维护归属'):
        public._apply_projection(dict(public_unknown='尚未登记的正文'), {})
    with pytest.raises(ValueError, match='未声明字段或评分字段'):
        public._apply_projection({},dict(score=8))
    with pytest.raises(ValueError, match='声明无效'):
        public._apply_projection({}, {}, retired_sources={'score'})


def test_third_refresh_never_persists_c_derived_public_fields(monkeypatch):
    payloads = {key: dict(records=[dict(ruler_id='synthetic', score=7)])
                for key in ('AB', 'C', 'D', 'credit', 'total')}
    payloads['ML'] = dict(records=[])
    payloads['credit']['contract'] = {}
    authored = dict(story='权威叙述与限制。', axes=dict(C1=dict(basis='本人材料。')))
    row = payloads['C']['records'][0]
    row.update(public_reading=copy.deepcopy(authored), public_evidence_items=[dict(public_basis='旧副本。')],
               public_adjudication_summary='过期汇总。', public_axis_projections={'C1': {}})
    for name in ('_credit_projection', '_ab_projection', '_d_projection', '_third_projection'):
        monkeypatch.setattr(public, name, lambda *args, **kwargs: {})
    monkeypatch.setattr(public, '_third_projection', lambda *args: dict(
        public_adjudication_summary='可重建汇总。', public_evidence_items=[],
        public_military_cost={}, public_military_net_loss=dict(public_boundary='本人窗口。')))
    public._refresh_third(payloads)
    assert row == dict(ruler_id='synthetic', score=7, public_reading=authored)
    total = payloads['total']['records'][0]
    assert not public._THIRD_TOTAL_DERIVED_FIELDS.intersection(total)
    assert total['public_military_net_loss']['public_boundary'] == '本人窗口。'
    first = copy.deepcopy(payloads)
    public._refresh_third(payloads)
    assert payloads == first


def _synthetic_third_components():
    return dict(
        row=dict(ruler_id='synthetic', score=7, global_cost_credit_profile=dict(basis='持续动员的代价。'),
                 military_net_loss_basis='本人窗口内尚无完整损失依据。',
                 public_adjudication_summary='过期汇总。', public_military_cost={}, public_evidence_items=[]),
        ab=dict(ruler_id='synthetic', public_adjudication_summary='本期安全结果。'),
        credit=dict(ruler_id='synthetic'), c=dict(ruler_id='synthetic', public_reading=dict(story='本期体系交付。')),
        d=dict(ruler_id='synthetic'), ml=None,
    )


def test_third_total_reading_uses_current_components_without_mutating_sources():
    sources = _synthetic_third_components()
    before = copy.deepcopy(sources)
    result = public.third_public_record(**sources)
    assert sources == before
    assert '过期' not in result['public_adjudication_summary']
    assert result['public_evidence_items'][0]['public_basis'] == '本期安全结果。'
    assert result['public_evidence_items'][1]['public_basis'] == '本期体系交付。'
    assert '本人窗口内尚无完整损失依据。' in result['public_military_net_loss']['public_adjudication_summary']
    assert result['score'] == before['row']['score']
    result['global_cost_credit_profile']['basis'] = '消费端改动。'
    result['public_evidence_items'][0]['public_basis'] = '消费端改动。'
    assert sources == before
    sources['c']['public_reading']['story'] = '修订后的体系交付。'
    assert public.third_public_record(**sources)['public_evidence_items'][1]['public_basis'] == '修订后的体系交付。'


@pytest.mark.parametrize('key', ['ab', 'credit', 'c', 'd', 'ml'])
def test_third_total_reading_rejects_cross_subject_components(key):
    sources = _synthetic_third_components()
    sources[key] = dict(ruler_id='another-subject')
    with pytest.raises(ValueError, match='来源人物不一致'):
        public.third_public_record(**sources)


def test_fourth_refresh_keeps_one_public_projection_per_axis(monkeypatch):
    from emperor_v4.evaluation import fourth_item_a_public, fourth_item_b_public

    def reading(row, axis, packages):
        return dict(story=axis['public_reading']['story'], decision='合成裁决。', boundary='本人范围。')

    monkeypatch.setattr(fourth_item_a_public, 'axis_reading', reading)
    monkeypatch.setattr(fourth_item_b_public, 'axis_reading', reading)
    monkeypatch.setattr(public, '_fourth_axis_projection', lambda row, axis, packages, parent: dict(public._projection(
        summary=row['public_reading']['story'], items=[public._item(
            'FOURTH-AXIS', 'synthetic', axis, axis, '现行事实', '合成事实。', '本人范围。')],
        boundary='本人范围。', level_label='合成等级', component_label=axis),
        public_reading=copy.deepcopy(row['public_reading'])))
    row = dict(ruler_id='synthetic', axis_results=[dict(
        axis=axis, package_refs=[], disposition='NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW',
        direction='MIXED', signed_adjustment=0, public_reading=dict(story={'A':'共同体独立正文。','B':'教育独立正文。','C':'知识独立正文。'}[axis])) for axis in 'ABC'])
    row['public_axis_projections'] = {'A': {'public_reading': {'story': '过期副本。'}}}
    before = public._signature(row)
    public._apply_projection(row, public._fourth_projection(row, {}))
    assert public._signature(row) == before
    assert 'public_axis_projections' not in row
    assert 'public_adjudication_summary' not in row
    assert 'public_evidence_items' not in row
    assert [axis['public_reading']['story'] for axis in row['axis_results']] == ['共同体独立正文。','教育独立正文。','知识独立正文。']
    saved = copy.deepcopy(row)
    reading = public.fourth_public_record(row)
    assert row == saved
    assert reading['public_adjudication_summary'] == '；'.join(axis['public_adjudication_summary'] for axis in row['axis_results'])
    assert reading['public_evidence_items'] == [e for axis in row['axis_results'] for e in axis['public_evidence_items']]
    reading['public_evidence_items'][0]['public_basis'] = '消费端变更。'
    assert row == saved
    first = copy.deepcopy(row)
    public._apply_projection(row, public._fourth_projection(row, {}))
    assert row == first


def test_fourth_summary_uses_axis_order_and_never_a_stale_root_copy():
    texts = {'A':'共同体当前正文。', 'B':'教育当前正文。', 'C':'知识当前正文。'}
    axes = [dict(axis=axis, public_adjudication_summary=texts[axis],
                 public_evidence_items=[dict(id=axis, public_basis=f'{axis}依据。')]) for axis in 'CAB']
    row = dict(ruler_id='synthetic', axis_results=axes, public_adjudication_summary='过期汇总。', public_evidence_items=[])
    before = copy.deepcopy(row)
    result = public.fourth_public_record(row)
    assert result['public_adjudication_summary'] == '共同体当前正文。；教育当前正文。；知识当前正文。'
    assert [e['id'] for e in result['public_evidence_items']] == list('ABC')
    assert row == before


def test_ab_projection_reads_a_from_credit_and_keeps_b_in_its_axis(monkeypatch):
    import json
    def projection(label, story):
        return public._projection(summary=story, items=[public._item(
            'THIRD-AB', 'synthetic', label, label, '现行裁决叙述', story, '合成范围。')],
            boundary='合成范围。', level_label='合成等级', component_label=label)

    credit = dict(axes={axis: projection('安全结果', '当前接班与交班事实。') for axis in ('A1', 'A2')})
    row = dict(ruler_id='synthetic', public_b_source_catalog={}, axes={axis: dict(score_rate=0) for axis in ('A1', 'A2', 'B1', 'B2', 'B4')})
    # A stale duplicate must not override the source or survive a refresh.
    row['axes']['A1']['public_reading'] = dict(story='已经过期的事实。')
    row['public_axis_projections'] = {'A1': {'public_reading': {'story': '另一份过期副本。'}}}
    monkeypatch.setattr(public, 'b_reading_projection', lambda axis, ab, source: dict(
        evidence_items=[], sources=[], story='当前控制事实。', boundary='合成范围。',
        decision='当前控制裁决。', rate_note='合成得分率'))
    original_credit = copy.deepcopy(credit)
    public._apply_projection(row, public._ab_projection(row, credit))
    assert credit == original_credit
    assert 'public_axis_projections' not in row
    assert all(not any(k.startswith('public_') for k in row['axes'][axis]) for axis in ('A1', 'A2'))
    assert all(row['axes'][axis]['public_reading']['story'] == '当前控制事实。' for axis in ('B1', 'B2', 'B4'))
    assert '当前接班与交班事实。' in row['public_adjudication_summary']
    assert '过期' not in str(row)
    first = copy.deepcopy(row)
    serialized = json.dumps(row, ensure_ascii=False)
    public._apply_projection(row, public._ab_projection(row, credit))
    assert row == first
    assert json.dumps(row, ensure_ascii=False) == serialized


def test_zero_ml_projection_preserves_unresolved_basis_without_inventing_gate_failure():
    basis = "负向结果已证，尚缺同一战略链的本方成本与本人责任复核。"
    projection = public._ml_projection({"grade": "ML0", "basis": basis}, "SYNTHETIC-RULER")
    assert basis in projection["public_adjudication_summary"]
    assert "现有材料没有同时确认" not in projection["public_adjudication_summary"]


def test_public_translation_preserves_conditions_and_unknown_text_fails_closed():
    text = translate('不因C7自动升ML；EN3或多方向EN2须分别证明。')
    assert text == '不因军事成本第7级自动升重大军事净毁损等级；全国或多数核心防务体系崩溃或多方向主要方向耐久恶化须分别证明。'
    with pytest.raises(ValueError, match='禁止删词'):
        translate('尚不能依据UNREVIEWED_CODE得出结论。')


def test_translation_uses_domain_and_keeps_negation_and_quantities():
    assert translate('多个F3不足以自动判F4') == '多个主要方向兵团组织严重毁损不足以自动判国家主力组织瓦解'
    with language_domain('civilization'):
        assert translate('H3限制P2') == '重大负向限制第3级限制正向变化第2级'
    with language_domain('capability'):
        assert translate('C4') == '军事体系整体第4级'
    assert translate('C4') == '军事成本第4级'


@pytest.mark.parametrize('component', ['total', 'fourth'])
def test_verifier_rejects_chinese_text_drift_without_internal_codes(component):
    payloads = public._load_payloads(ROOT)
    # One aligned subject is sufficient to exercise drift rejection; do not revalidate the pool.
    rid = payloads['total']['records'][0]['ruler_id']
    for key, payload in payloads.items():
        payload['records'] = [r for r in payload['records'] if r['ruler_id'] == rid]
        if key == 'fourth':
            payload['accepted_packages'] = [p for p in payload['accepted_packages'] if p['ruler_id'] == rid]
    payloads[component]['records'][0]['public_adjudication_summary'] = '多个、与形成完整证据。'
    with pytest.raises(ValueError, match='公开文案与当前来源转述不一致'):
        if component == 'fourth':
            public._verify_fourth(payloads[component])
        else:
            from emperor_v4.evaluation.third_item_c_contract_reading import load_context
            public._verify_third(payloads, c_review_context=load_context(ROOT))


@pytest.mark.parametrize('disposition,expected', [
    ('NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW', '复核后未确认独立净变化'),
    ('OBSERVED_OFFSETTING_OR_BALANCED_EFFECTS', '正负相抵，净调整为0'),
])
def test_fourth_public_zero_states_distinguish_reviewed_empty_from_balanced_zero(disposition, expected):
    from emperor_v4.evaluation.fourth_item_a_public import SCHEMA
    prose = {key: '合成事实及其归责范围。' for key in (
        'title', 'story', 'baseline', 'responsibility', 'level_basis',
        'coverage', 'duration', 'boundary', 'source_note')}
    prose.update(schema=SCHEMA, sources=[])
    package = dict(package_code='SYNTHETIC', ruler_id='SYNTHETIC', axis='A',
                   direction='MIXED', source_coverage='INSUFFICIENT', source_refs=[],
                   positive_component_level='R1', negative_component_level='R1', public_reading=prose)
    if disposition == 'NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW':
        package['scoring_eligibility'] = 'REVOKED'
    row = dict(ruler_id='SYNTHETIC', package_refs=['SYNTHETIC'], disposition=disposition,
               direction='MIXED', signed_adjustment=0)
    before = copy.deepcopy((row, package))
    projection = public._fourth_axis_projection(row, 'A', {'SYNTHETIC': package})
    assert projection['public_level_label'] == expected
    assert (row, package) == before
    if package.get('scoring_eligibility') == 'REVOKED':
        assert projection['public_evidence_items'][0]['public_role'] == '不单独计分，保留相关事实'


def test_revoked_c_material_uses_authored_facts_without_repeating_old_result_claims():
    package = dict(package_code='SYNTHETIC-EXCLUDED-C', ruler_id='SYNTHETIC', axis='C',
                   direction='POSITIVE', scoring_eligibility='REVOKED',
                   source_coverage='INSUFFICIENT', attributable_change='旧表述已经实现广泛改善。',
                   source_refs=[], public_c_result_reading=dict(result='设置过一个机构。', responsibility='本人只授权设置。', scope='尚无知识产出。', source_refs=[]),
                   public_exclusion_reading=dict(story='设置过一个机构。', reason='尚未证实实际知识产出。'))
    before = copy.deepcopy(package)
    projection = public._package_projection(package)
    assert package == before
    assert projection['public_evidence_items'][0]['public_role'] == '不单独计分，保留相关事实'
    assert projection['public_level_label'] == '不单独计分，保留相关事实'
    assert '旧表述已经实现广泛改善' not in projection['public_adjudication_summary']
    assert '设置过一个机构' in projection['public_adjudication_summary']
    assert projection['public_exclusion_reading'] == package['public_exclusion_reading']
    public._apply_projection(package, projection)
    assert public._package_projection(package) == projection


def test_revoked_c_material_requires_an_explicit_public_explanation():
    package = dict(package_code='SYNTHETIC-EXCLUDED-C', ruler_id='SYNTHETIC', axis='C',
                   direction='NEGATIVE', scoring_eligibility='REVOKED', source_coverage='INSUFFICIENT',
                   source_refs=[], public_c_result_reading=dict(result='发生过处置。',responsibility='本人下令。',scope='未证明知识结果。',source_refs=[]))
    with pytest.raises(ValueError, match='公开事实与不计分说明'):
        public._package_projection(package)


def test_c_result_requires_authored_responsibility_and_exact_source_binding():
    package = dict(package_code='SYNTHETIC-C', ruler_id='SYNTHETIC', axis='C',
                   direction='POSITIVE', relative_change_level='R2', source_coverage='ADEQUATE',
                   source_refs=['https://example.org/source'], public_c_result_reading=dict(
                       result='已完成知识产品并供专业查用。', responsibility='本人授权，学者实际编纂。',
                       scope='不将作者的全部成就归给本人。', source_refs=['https://example.org/source']))
    before = copy.deepcopy(package)
    projection = public._package_projection(package)
    assert package == before
    assert '本人授权，学者实际编纂。' in projection['public_adjudication_summary']
    del package['public_c_result_reading']['responsibility']
    with pytest.raises(ValueError, match='responsibility'):
        public._package_projection(package)
    package = copy.deepcopy(before)
    package['public_c_result_reading']['source_refs'] = ['https://example.org/unrelated']
    with pytest.raises(ValueError, match='来源未同步'):
        public._package_projection(package)
