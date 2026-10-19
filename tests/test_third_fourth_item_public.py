from __future__ import annotations

import json
import copy
import pytest
from pathlib import Path

from emperor_v4.evaluation.third_fourth_item_public import (
    PUBLIC_FORBIDDEN_RE,
    verify_public_projection,
)
from emperor_v4.evaluation import third_fourth_item_public as public
from emperor_v4.evaluation.third_fourth_public_language import translate, language_domain


ROOT = Path(__file__).resolve().parents[1]


def test_named_projects_preserve_exclusions_and_ordinary_enumeration():
    from emperor_v4.evaluation.third_fourth_public_language import named_project_prose
    text = '同一成果由第一项计入，第三项不重复计分；第二项独立结果不另加分。'
    result = named_project_prose(text)
    assert result == '同一成果由“政权奠基与统一贡献”计入，“军事与边疆”不重复计分；第二项独立结果不另加分。'
    assert named_project_prose(result) == result
    assert named_project_prose('第三项军事与边疆净收益') == '军事与边疆净收益'


def test_generated_military_labels_keep_civilization_domain_unchanged():
    text = '第一项已计入，同链去重。'
    assert public._clean_public_text(text) == '“政权奠基与统一贡献”已计入，同一完整行动避免重复计分。'
    with language_domain('civilization'):
        assert public._clean_public_text(text) == text


def test_zero_ml_projection_preserves_unresolved_basis_without_inventing_gate_failure():
    basis = "负向结果已证，尚缺同一战略链的本方成本与本人责任复核。"
    projection = public._ml_projection({"grade": "ML0", "basis": basis}, "SYNTHETIC-RULER")
    assert basis in projection["public_adjudication_summary"]
    assert "现有材料没有同时确认" not in projection["public_adjudication_summary"]


def test_explicit_cross_item_codes_do_not_use_military_meanings():
    with language_domain('civilization'):
        assert translate('第二项B2负责反馈；第二项C3负责人身安全。') == '第二项反馈纠错与权力约束负责反馈；第二项社会安全负责人身安全。'
    assert translate('人物M1独立表达。') == '人物画像军事判断与统帅能力独立表达。'


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
    payloads[component]['records'][0]['public_adjudication_summary'] = '多个、与形成完整证据。'
    with pytest.raises(ValueError, match='公开文案与当前来源转述不一致'):
        if component == 'fourth':
            public._verify_fourth(payloads[component])
        else:
            public._verify_third(payloads)


def test_projection_is_deterministic_and_does_not_change_source_payload():
    payloads = public._load_payloads(ROOT)
    third = {key: value for key, value in payloads.items() if key != 'fourth'}
    for source, refresh in ((third, public._refresh_third), (payloads['fourth'], public._refresh_fourth)):
        projected = refresh(copy.deepcopy(source))
        assert public._signature(projected) == public._signature(source)
        assert refresh(copy.deepcopy(projected)) == projected


def test_third_fourth_public_projection_covers_the_current_pool_without_score_drift():
    report = verify_public_projection(ROOT)

    assert report["status"] == "PASS"
    assert report["third_item"]["record_count"] == report["fourth_item"]["record_count"]
    assert report["third_item"]["source_record_counts"]["total"] == report["third_item"]["record_count"]
    assert report["fourth_item"]["package_count"] > 0


def test_fourth_public_zero_states_distinguish_reviewed_empty_from_balanced_zero():
    payload = public._refresh_fourth(copy.deepcopy(public._load_payloads(ROOT)["fourth"]))
    axes = [
        axis
        for row in payload["records"]
        for axis in row.get("axis_results") or []
    ]
    reviewed = [axis for axis in axes if axis.get("disposition") == "NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW"]
    balanced = [axis for axis in axes if axis.get("disposition") == "OBSERVED_OFFSETTING_OR_BALANCED_EFFECTS"]
    assert reviewed and balanced
    assert all(axis["public_level_label"] == "复核后未确认独立净变化" for axis in reviewed)
    assert all("结果方向未单列" not in axis["public_adjudication_summary"] for axis in reviewed)
    assert all(axis['signed_adjustment'] == 0 for axis in reviewed)
    # Authored explanations may change independently of the zero-state contract.
    # Do not freeze one historical template as the required public judgment.
    for axis in reviewed:
        if axis.get('public_reading'):
            reading = axis['public_reading']
            if reading['schema'] == 'fourth-item-c-sources-and-score-v1':
                assert reading['zero_reason'].strip()
            else:
                assert axis['public_adjudication_summary'] == reading['story'] + reading['decision']
            assert all(item['public_role'] == '不单独计分，保留相关事实'
                       for item in axis['public_evidence_items'])
        else:
            assert axis['public_adjudication_summary'].strip()
    assert all(axis["public_level_label"] == "正负相抵，净调整为0" for axis in balanced)


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


def test_governance_qualifiers_override_local_civilization_and_military_codes():
    for domain in ('civilization', 'military'):
        with language_domain(domain):
            assert translate('第二项制度A处理法令；B2反馈结果另证。') == '第二项制度建设处理法令；反馈纠错与权力约束结果另证。'
    with language_domain('civilization'):
        assert translate('主结果归C。') == '主结果归知识与文化生态。'
    with language_domain('military'):
        assert translate('B2与C。') == '战略成果价值与军事体系。'


def test_fourth_public_package_projection_does_not_duplicate_sentence_punctuation():
    payload = public._refresh_fourth(copy.deepcopy(public._load_payloads(ROOT)["fourth"]))
    packages = payload["accepted_packages"]
    assert packages
    for package in packages:
        assert "。。" not in package["public_adjudication_summary"]
        for item in package["public_evidence_items"]:
            assert "。。" not in item["public_basis"]


def test_fourth_public_packages_publish_source_coverage_without_inventing_strength():
    payload = public._refresh_fourth(copy.deepcopy(public._load_payloads(ROOT)["fourth"]))
    packages = payload["accepted_packages"]
    assert packages
    expected = {"来源覆盖：充分", "来源覆盖：局部但足够", "来源覆盖：不足"}
    seen = set()
    for package in packages:
        evidence = package["public_evidence_items"]
        assert len(evidence) == 1
        coverage = evidence[0].get("public_source_coverage")
        assert coverage in expected
        seen.add(coverage)
    assert seen == expected


def test_third_public_evidence_does_not_fake_source_coverage():
    payloads = public._load_payloads(ROOT)
    projected = public._refresh_third(copy.deepcopy({key: value for key, value in payloads.items() if key != "fourth"}))
    items = [
        item
        for key in ("AB", "C", "D", "credit", "ML", "total")
        for row in projected[key]["records"]
        for item in row.get("public_evidence_items") or []
    ]
    assert items
    assert all("public_source_coverage" not in item for item in items)


def test_reader_consumes_explicit_public_evidence_for_third_and_fourth_items():
    projected = []
    for path in (ROOT / "reader/data/people").glob("*.json"):
        detail = json.loads(path.read_text(encoding="utf-8"))
        groups = ((detail.get("record") or {}).get("net") or {}).get("component_details", {})
        for group in ("strategic", "military", "civilization"):
            projected.extend(
                item for item in groups.get(group, [])
                if item.get("reader_kind") == "judgment"
            )

    assert projected
    for item in projected:
        evidence = item.get("reader_public_evidence_items")
        assert item.get("public_component_label")
        assert item.get("reader_summary")
        assert isinstance(evidence, list) and evidence
        assert evidence == item["public_evidence_items"]
        assert "reader_full_basis" not in item
        for entry in evidence:
            for field in ("public_label", "public_role", "public_basis", "public_boundary"):
                assert not PUBLIC_FORBIDDEN_RE.search(entry[field])


def test_reader_translation_helpers_are_formatters_only_for_third_and_fourth_public_text():
    for name in ("reader/home-interactions.js", "reader/person-readability.js"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "replace(/\\bML" not in text
        assert "replace(/\\bCIV" not in text
        assert "replace(/\\bDA" not in text


def test_reader_keeps_formal_fourth_zero_distinctions_visible_at_major_level():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "reader/home-interactions.js").read_text(encoding="utf-8")
    start = source.index("function fourthAdjustmentNote")
    end = source.index("function netHref", start)
    block = source[start:end]
    assert "BALANCED" in block and "CIV0" in block
    assert "NO_ELIGIBLE" in block
    assert "部分分项的已确认正负变化相抵" in block
    assert "未确认可单独计入的净变化" in block
    assert "0不表示相关领域没有史料" in block
