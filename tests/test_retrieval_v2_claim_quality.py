from __future__ import annotations

from scripts.dev import retrieval_v2_claim_quality as tool


def test_slice_claim_eligibility_keeps_action_near_object_claimable() -> None:
    row = {
        "object_name": "李世民",
        "matched_aliases": ["秦王"],
        "source_shape": "object_biography_candidate",
        "section_heading": "尉迟敬德",
        "text": "高祖命秦王为西讨元帅，诸将皆受节制。",
    }

    eligibility = tool.slice_claim_eligibility(row)

    assert "wrong_person_section_risk" in eligibility["risk_flags"]
    assert eligibility["claim_eligible"] is True
    assert eligibility["mention_role"] == "primary"
    assert eligibility["near_object_anchors"]["action"] is True


def test_slice_claim_eligibility_rejects_incidental_wrong_section_mentions() -> None:
    row = {
        "object_name": "李文忠",
        "matched_aliases": ["李文忠"],
        "source_shape": "object_biography_candidate",
        "section_heading": "邓愈",
        "text": "愈为人简重慎密，诸将早贵未有如愈与李文忠者。",
    }

    eligibility = tool.slice_claim_eligibility(row)

    assert eligibility["claim_eligible"] is False
    assert eligibility["support_level_hint"] == "context"
    assert eligibility["reasons"] == ["wrong_person_section_risk", "no_action_or_outcome_near_object"]


def test_canonical_near_duplicate_group_ignores_summary_wording() -> None:
    first = {
        "emperor_name": "朱元璋",
        "object_name": "汤和",
        "direction": "positive",
        "claim_summary": "朱元璋命汤和守常州。",
        "fact_payload": {
            "action_type": "授权",
            "event_scope": "军事",
            "office_or_domain": "常州镇守",
            "time_context": "洪武初",
            "outcome": "守常州",
        },
    }
    second = {**first, "claim_summary": "太祖令汤和镇守常州。"}

    assert tool.canonical_event_key(first) != tool.canonical_event_key(second)
    assert tool.near_duplicate_group_key(first) == tool.near_duplicate_group_key(second)
    assert tool.claim_quality_payload(first)["claim_grain"] == "event_chain"
