from __future__ import annotations

import copy
import pytest
from pathlib import Path

from emperor_v4.evaluation import third_fourth_item_public as public
from emperor_v4.evaluation.third_fourth_public_language import translate, language_domain


ROOT = Path(__file__).resolve().parents[1]


def test_ab_projection_reads_a_from_credit_and_keeps_b_in_its_axis(monkeypatch):
    def projection(label, story):
        return public._projection(summary=story, items=[public._item(
            'THIRD-AB', 'synthetic', label, label, '现行裁决叙述', story, '合成范围。')],
            boundary='合成范围。', level_label='合成等级', component_label=label)

    credit = dict(axes={axis: projection('安全结果', '当前接班与交班事实。') for axis in ('A1', 'A2')})
    row = dict(ruler_id='synthetic', axes={axis: dict(score_rate=0) for axis in ('A1', 'A2', 'B1', 'B2', 'B4')})
    # A stale duplicate must not override the source or survive a refresh.
    row['axes']['A1']['public_reading'] = dict(story='已经过期的事实。')
    row['public_axis_projections'] = {'A1': {'public_reading': {'story': '另一份过期副本。'}}}
    monkeypatch.setattr(public, 'b_reading_projection', lambda axis, ab, source: dict(
        evidence_items=[], story='当前控制事实。', boundary='合成范围。',
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
    public._apply_projection(row, public._ab_projection(row, credit))
    assert row == first


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
            public._verify_third(payloads)


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
