from __future__ import annotations

from dataclasses import replace

import pytest

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.domain.episode import build_episode_packet, group_episode_candidates


def _assertion(
    code: str,
    *,
    passage: str,
    ruler: str = "李世民",
    person: str = "李靖",
    time: str = "贞观三年",
    domain: str = "北方战区",
    summary: str = "任李靖统兵",
    polarity: str = "asserted",
) -> AssertionDraft:
    return AssertionDraft(
        assertion_code=code,
        source_passage_ref=passage,
        assertion_type="event_fact",
        subject=ruler,
        predicate="任命统兵",
        object=person,
        time_expression=time,
        location_expression="北境",
        qualifiers={
            "evaluation_context": ruler,
            "candidate_participant_roles": ((ruler, "ruler"), (person, "commander")),
            "episode_type": "appointment_delegation",
            "office_or_domain": domain,
            "outcome": "完成任务",
            "legacy_claim_summary": summary,
        },
        polarity=polarity,
        source_attribution={"document_code": f"D-{passage}"},
        candidate_episode_key=None,
        confidence=0.9,
    )


def test_same_structured_event_merges_across_source_wording():
    first = _assertion("A-1", passage="P-1", summary="命李靖出师")
    second = _assertion("A-2", passage="P-2", summary="以李靖为行军总管")

    groups = group_episode_candidates([first, second])

    assert len(groups) == 1
    assert {item.assertion_code for item in groups[0].assertions} == {"A-1", "A-2"}


@pytest.mark.parametrize(
    "changed",
    [
        {"ruler": "李治"},
        {"time": "贞观四年"},
        {"domain": "西方战区"},
        {"person": "侯君集"},
    ],
)
def test_context_time_responsibility_or_participant_change_splits(changed: dict):
    first = _assertion("A-1", passage="P-1")
    second = _assertion("A-2", passage="P-2", **changed)

    assert len(group_episode_candidates([first, second])) == 2


def test_new_authorization_action_splits_even_with_same_context_and_time():
    first = _assertion("A-1", passage="P-1")
    second = replace(_assertion("A-2", passage="P-2"), predicate="撤销授权")

    assert len(group_episode_candidates([first, second])) == 2


def test_new_synonymous_evidence_does_not_change_episode_identity():
    first = _assertion("A-1", passage="P-1")
    second = _assertion("A-2", passage="P-2", summary="异源同义措辞")

    one = build_episode_packet(group_episode_candidates([first])[0])
    two = build_episode_packet(group_episode_candidates([first, second])[0])

    assert one.episode_id == two.episode_id
    assert one.semantic_fingerprint == two.semantic_fingerprint
    assert len(two.assertion_links) == 2


def test_conflicting_evidence_is_preserved_in_packet():
    support = _assertion("A-1", passage="P-1")
    dispute = replace(
        _assertion("A-2", passage="P-2", polarity="disputed"),
        qualifiers=support.qualifiers,
    )

    packet = build_episode_packet(group_episode_candidates([support, dispute])[0])

    assert packet.conflicts == ("A-2",)
    assert packet.completeness["conflict_resolution"] == "conflicted"
    assert {link.relation for link in packet.assertion_links} == {
        "supports",
        "contradicts",
    }


def test_accepted_episode_has_passage_lineage_and_slot_completeness():
    packet = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0],
        episode_status="accepted",
    )

    assert packet.assertion_links[0].source_passage_ref == "P-1"
    assert packet.completeness == {
        "identity": "complete",
        "time": "complete",
        "action": "complete",
        "responsibility": "complete",
        "outcome": "complete",
        "consequence": "not_applicable",
        "source_diversity": "partial",
        "conflict_resolution": "complete",
    }
