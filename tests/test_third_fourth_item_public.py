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
    assert all("经复核后未形成可单独计入的净变化" in axis["public_adjudication_summary"] for axis in reviewed)
    assert all(axis["public_level_label"] == "正负相抵，净调整为0" for axis in balanced)


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
