from __future__ import annotations

from dataclasses import replace

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.domain.episode import build_episode_packet, group_episode_candidates
from emperor_v4.domain.versioning import apply_episode_revision


def _assertion(code: str, passage: str, *, domain: str = "军务") -> AssertionDraft:
    return AssertionDraft(
        assertion_code=code,
        source_passage_ref=passage,
        assertion_type="event_fact",
        subject="李世民",
        predicate="任命",
        object="李靖",
        time_expression="贞观三年",
        location_expression=None,
        qualifiers={
            "evaluation_context": "李世民",
            "candidate_participant_roles": (("李世民", "ruler"), ("李靖", "commander")),
            "episode_type": "appointment_delegation",
            "office_or_domain": domain,
            "outcome": "成功",
        },
        polarity="asserted",
        source_attribution={"document_code": f"D-{passage}"},
        candidate_episode_key=None,
        confidence=0.9,
    )


def _packet(*assertions: AssertionDraft):
    return build_episode_packet(group_episode_candidates(assertions)[0])


def test_unchanged_rerun_requires_no_write_or_model_call():
    current = _packet(_assertion("A-1", "P-1"))

    decision = apply_episode_revision(current, current)

    assert decision.packet is current
    assert not decision.write_required
    assert not decision.model_call_required


def test_synonymous_evidence_only_increments_evidence_version():
    current = _packet(_assertion("A-1", "P-1"))
    observed = _packet(_assertion("A-1", "P-1"), _assertion("A-2", "P-2"))

    decision = apply_episode_revision(current, observed)

    assert decision.packet.episode_id == current.episode_id
    assert decision.packet.semantic_version == current.semantic_version
    assert decision.packet.evidence_version == current.evidence_version + 1
    assert not decision.judgment_invalidation_required


def test_responsibility_change_increments_semantic_version_and_invalidates():
    current = _packet(_assertion("A-1", "P-1"))
    observed = _packet(_assertion("A-2", "P-2", domain="财政"))

    decision = apply_episode_revision(current, observed)

    assert decision.packet.episode_id == current.episode_id
    assert decision.packet.semantic_version == current.semantic_version + 1
    assert decision.judgment_invalidation_required


def test_conflicting_evidence_only_increments_evidence_but_requires_review():
    support = _assertion("A-1", "P-1")
    current = _packet(support)
    dispute = replace(_assertion("A-2", "P-2"), polarity="disputed")
    observed = _packet(support, dispute)

    decision = apply_episode_revision(current, observed)

    assert not decision.semantic_changed
    assert decision.packet.evidence_version == current.evidence_version + 1
    assert decision.packet.episode_status == "needs_evidence_review"
    assert decision.judgment_invalidation_required
