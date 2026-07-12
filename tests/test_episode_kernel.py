from __future__ import annotations

from dataclasses import replace

import pytest

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.boundary import (
    ContextAssertionLink,
    EpisodeBoundaryGroup,
    EpisodeBoundaryReviewResult,
    EpisodeRelation,
)
from emperor_v4.contracts.episode import EpisodeParticipant
from emperor_v4.domain.episode import (
    build_episode_packet,
    group_episode_candidates,
    group_episode_candidates_with_hints,
)
from emperor_v4.domain.boundary import (
    cluster_propositions,
    materialize_boundary_review,
    plan_boundary_reviews,
)


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


def _with_claim(assertion: AssertionDraft, claim_key: str) -> AssertionDraft:
    return replace(assertion, extraction_provenance={"claim_key": claim_key})


def test_proposition_cluster_collapses_passage_fanout_without_losing_lineage():
    first = _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1")
    second = _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-1")

    clusters = cluster_propositions([first, second])

    assert len(clusters) == 1
    assert clusters[0].assertion_refs == ("A-1", "A-2")
    assert clusters[0].evidence_refs == ("P-1", "P-2")


def test_review_unit_cache_invalidates_only_changed_focal_person():
    lijing = [
        _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1"),
        _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-1"),
    ]
    hou = [
        _with_claim(
            _assertion("A-3", passage="P-3", person="侯君集"), "CLAIM-2"
        )
    ]
    first_plan = plan_boundary_reviews([*lijing, *hou])
    cached_keys = {item.cache_key for item in first_plan.review_units}
    changed_lijing = _with_claim(
        _assertion("A-4", passage="P-4", time="贞观四年"), "CLAIM-3"
    )

    second_plan = plan_boundary_reviews(
        [*lijing, *hou, changed_lijing], cached_review_keys=cached_keys
    )

    assert len(first_plan.proposition_clusters) == 2
    assert len(first_plan.review_units) == 2
    assert second_plan.model_call_count == 1
    assert len(second_plan.cache_hit_unit_codes) == 1
    assert len(second_plan.cache_miss_unit_codes) == 1

    synonymous_evidence = _with_claim(
        _assertion("A-5", passage="P-5"), "CLAIM-1"
    )
    evidence_only_plan = plan_boundary_reviews(
        [*lijing, *hou, synonymous_evidence], cached_review_keys=cached_keys
    )
    assert evidence_only_plan.model_call_count == 0


def test_boundary_review_keeps_atomic_episodes_and_materializes_relation():
    appointment = _with_claim(
        _assertion("A-1", passage="P-1", time="贞观三年"), "CLAIM-1"
    )
    renewal = _with_claim(
        _assertion("A-2", passage="P-2", time="贞观四年"), "CLAIM-2"
    )
    review = EpisodeBoundaryReviewResult(
        review_unit_ref="RU-1",
        episode_groups=(
            EpisodeBoundaryGroup("E1", ("A-1",), "首次授权", 0.95),
            EpisodeBoundaryGroup("E2", ("A-2",), "重新授权", 0.95),
        ),
        relations=(
            EpisodeRelation("E1", "E2", "renews_authority", ("A-2",), 0.9),
        ),
        context_assertions=(
            ContextAssertionLink("A-1", ("E2",), "前次授权为后续背景"),
        ),
        unresolved_assertion_refs=(),
    )

    packets, relations = materialize_boundary_review([appointment, renewal], review)

    assert len(packets) == 2
    assert len(relations) == 1
    assert relations[0].relation_type == "renews_authority"
    assert relations[0].from_episode_ref != relations[0].to_episode_ref


def test_boundary_review_rejects_assertion_in_two_episode_cores():
    with pytest.raises(ValueError, match="最多只能属于一个"):
        EpisodeBoundaryReviewResult(
            review_unit_ref="RU-1",
            episode_groups=(
                EpisodeBoundaryGroup("E1", ("A-1",), "first", 0.9),
                EpisodeBoundaryGroup("E2", ("A-1",), "second", 0.9),
            ),
            relations=(),
            context_assertions=(),
            unresolved_assertion_refs=(),
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


def test_cross_phase_chain_stays_split_when_responsibility_domains_do_not_overlap():
    appointment = _assertion(
        "A-1",
        passage="P-1",
        ruler="李治",
        person="苏定方",
        time="显庆二年",
        domain="伊丽道行军总管",
        summary="命苏定方讨沙钵罗可汗",
    )
    appointment = replace(
        appointment,
        predicate="任命",
        qualifiers={**appointment.qualifiers, "event_scope": "边疆"},
    )
    outcome = _assertion(
        "A-2",
        passage="P-2",
        ruler="李治",
        person="苏定方",
        time="显庆二年（657年）",
        domain="西突厥战事",
        summary="苏定方击败沙钵罗可汗",
    )
    outcome = replace(
        outcome,
        subject="苏定方",
        predicate="战役",
        object="沙钵罗可汗",
        qualifiers={**outcome.qualifiers, "event_scope": "边疆"},
    )

    groups = group_episode_candidates([appointment, outcome])

    assert len(groups) == 2


def test_same_source_topic_does_not_merge_distinct_regnal_year_tasks():
    first = replace(
        _assertion(
            "A-1",
            passage="P-1",
            ruler="李治",
            person="苏定方",
            time="显庆二年",
            domain="西域战事",
            summary="苏定方在西域作战",
        ),
        predicate="战役",
        source_attribution={"document_code": "D-1", "source_slice_ref": "S-SAME"},
    )
    second = replace(
        _assertion(
            "A-2",
            passage="P-2",
            ruler="李治",
            person="苏定方",
            time="显庆四年",
            domain="西域战事",
            summary="苏定方再次在西域作战",
        ),
        predicate="战役",
        source_attribution={"document_code": "D-1", "source_slice_ref": "S-SAME"},
    )

    assert len(group_episode_candidates([first, second])) == 2


def test_terminal_followup_does_not_merge_unrelated_earlier_appointment():
    appointment = _assertion(
        "A-1",
        passage="P-1",
        ruler="刘邦",
        person="萧何",
        time="至南郑时",
        domain="大将军任用",
        summary="萧何举荐韩信为大将",
    )
    followup = _assertion(
        "A-2",
        passage="P-2",
        ruler="刘邦",
        person="萧何",
        time="韩信被诛后",
        domain="相国封卫处置",
        summary="韩信被诛后萧何辞让封赏",
    )

    assert len(group_episode_candidates([appointment, followup])) == 2


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
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )
    packet = replace(
        proposed,
        episode_status="accepted",
        evaluation_context="PER-LI-SHIMIN",
        participants=(
            EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
            EpisodeParticipant("PER-LI-JING", ("commander",), "resolved"),
        ),
        assertion_links=tuple(
            replace(link, evidence_status="accepted")
            for link in proposed.assertion_links
        ),
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


@pytest.mark.parametrize(
    "change, message",
    [
        ({"evaluation_context": "李世民"}, "canonical person"),
        (
            {
                "participants": (
                    EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "unresolved"),
                )
            },
            "participant 必须全部 resolved",
        ),
    ],
)
def test_accepted_episode_rejects_unresolved_identity(change: dict, message: str):
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )
    valid = replace(
        proposed,
        evaluation_context="PER-LI-SHIMIN",
        participants=(
            EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
        ),
        assertion_links=tuple(
            replace(link, evidence_status="accepted")
            for link in proposed.assertion_links
        ),
    )

    with pytest.raises(ValueError, match=message):
        replace(valid, episode_status="accepted", **change)


def test_accepted_episode_rejects_draft_evidence():
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )

    with pytest.raises(ValueError, match="evidence 必须全部 accepted"):
        replace(
            proposed,
            episode_status="accepted",
            evaluation_context="PER-LI-SHIMIN",
            participants=(
                EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
            ),
        )


def test_accepted_episode_rejects_missing_completeness_slot():
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )
    incomplete = dict(proposed.completeness)
    incomplete.pop("outcome")

    with pytest.raises(ValueError, match="completeness 缺少槽位"):
        replace(
            proposed,
            episode_status="accepted",
            evaluation_context="PER-LI-SHIMIN",
            participants=(
                EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
            ),
            assertion_links=tuple(
                replace(link, evidence_status="accepted")
                for link in proposed.assertion_links
            ),
            completeness=incomplete,
        )


def test_accepted_with_uncertainty_rejects_empty_uncertainty():
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )

    with pytest.raises(ValueError, match="必须保留不确定性"):
        replace(
            proposed,
            episode_status="accepted_with_uncertainty",
            evaluation_context="PER-LI-SHIMIN",
            participants=(
                EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
            ),
            assertion_links=tuple(
                replace(link, evidence_status="accepted")
                for link in proposed.assertion_links
            ),
        )


def test_explicit_boundary_hint_merges_related_actions_without_using_summary_identity():
    appointment = _assertion("A-1", passage="P-1")
    outcome = replace(_assertion("A-2", passage="P-2"), predicate="奏捷反馈")

    groups = group_episode_candidates_with_hints(
        [appointment, outcome],
        {"A-1": "LIJING-DAIZHOU", "A-2": "LIJING-DAIZHOU"},
    )

    assert len(groups) == 1
    assert groups[0].boundary_hint == "LIJING-DAIZHOU"
    assert {item.assertion_code for item in groups[0].assertions} == {"A-1", "A-2"}


def test_gold_boundary_hint_does_not_change_semantic_fingerprint():
    first = _assertion("A-1", passage="P-1")
    second = _assertion("A-2", passage="P-2")

    groups = group_episode_candidates_with_hints(
        [first, second],
        {"A-1": "FIRST-AUTHORIZATION", "A-2": "SECOND-AUTHORIZATION"},
    )

    assert len(groups) == 2
    assert len({group.key.fingerprint for group in groups}) == 1


def test_hinted_packet_is_stable_under_assertion_input_order():
    appointment = _assertion("A-2", passage="P-2")
    outcome = replace(_assertion("A-1", passage="P-1"), predicate="奏捷反馈")
    hints = {"A-1": "LIJING-DAIZHOU", "A-2": "LIJING-DAIZHOU"}

    first = build_episode_packet(
        group_episode_candidates_with_hints([appointment, outcome], hints)[0]
    )
    second = build_episode_packet(
        group_episode_candidates_with_hints([outcome, appointment], hints)[0]
    )

    assert first.episode_id == second.episode_id
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.action == second.action == "任命统兵 | 奏捷反馈"
    assert first.assertion_links == second.assertion_links


def test_boundary_hint_cannot_merge_across_rulers():
    first = _assertion("A-1", passage="P-1")
    second = _assertion("A-2", passage="P-2", ruler="李治")

    with pytest.raises(ValueError, match="跨 evaluation context"):
        group_episode_candidates_with_hints(
            [first, second],
            {"A-1": "SAME-HINT", "A-2": "SAME-HINT"},
        )
