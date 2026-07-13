from __future__ import annotations

from dataclasses import replace

import pytest

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.episode import (
    AssertionLink,
    EpisodeParticipant,
    HistoricalEpisodePacket,
)
from emperor_v4.contracts.source import (
    SOURCE_CACHE_CONTRACT_V2,
    SourceDocumentDraft,
    SourcePassage,
    text_content_hash,
)
from emperor_v4.domain.versioning import apply_episode_revision
from emperor_v4.persistence import (
    BoundaryReviewCacheEntry,
    CoreRegistryBatch,
    EpisodeDispositionRecord,
    InMemoryCoreRegistry,
    ReviewArtifactRecord,
    SourceDocumentRecord,
)


def _document() -> SourceDocumentRecord:
    return SourceDocumentRecord(
        document=SourceDocumentDraft(
            document_cache_id="DOC-1",
            work_identity="史记",
            edition_identity="wikisource-1",
            title="史记",
            url="https://example.invalid/shiji",
            source_role="primary",
            retrieved_at="2026-07-13T00:00:00Z",
            content_hash="doc-hash-1",
            license_or_access_note="public-domain",
        ),
        content_version="rev-1",
    )


def _passage(code: str, text: str, start: int) -> SourcePassage:
    return SourcePassage(
        passage_cache_id=code,
        document_cache_id="DOC-1",
        locator=f"section:{start}",
        raw_text=text,
        context_before="",
        context_after="",
        content_hash=text_content_hash(text),
        selection_reason=("appointment_delegation",),
        contract_version=SOURCE_CACHE_CONTRACT_V2,
        content_version="rev-1",
        section_id="SEC-1",
        section_heading="本纪",
        span_start=start,
        span_end=start + len(text),
        passage_kind="atomic",
        window_policy_version="window-v1",
    )


def _assertion(code: str, passage: str, *, predicate: str = "任命") -> AssertionDraft:
    return AssertionDraft(
        assertion_code=code,
        source_passage_ref=passage,
        assertion_type="event_fact",
        subject="PER-RULER",
        predicate=predicate,
        object="PER-OFFICIAL",
        time_expression="元年",
        location_expression=None,
        qualifiers={},
        polarity="asserted",
        source_attribution={"document_id": "DOC-1"},
        candidate_episode_key=None,
        confidence=0.95,
    )


def _packet(*links: tuple[str, str], responsibility: str = "军务") -> HistoricalEpisodePacket:
    return HistoricalEpisodePacket(
        episode_id="EP-1",
        episode_type="appointment_delegation",
        episode_status="proposed",
        evaluation_context="PER-RULER",
        semantic_version=1,
        evidence_version=1,
        semantic_fingerprint="semantic-1",
        time_start="元年",
        time_end=None,
        time_precision="year",
        locations=(),
        participants=(
            EpisodeParticipant("PER-RULER", ("ruler",), "resolved"),
            EpisodeParticipant("PER-OFFICIAL", ("office_holder",), "resolved"),
        ),
        action="任命",
        responsibility=responsibility,
        outcome=(),
        consequence=(),
        assertion_links=tuple(
            AssertionLink(
                assertion_ref=assertion_ref,
                source_passage_ref=passage_ref,
                relation="supports",
                supported_fields=("identity", "action", "responsibility"),
            )
            for assertion_ref, passage_ref in links
        ),
        conflicts=(),
        uncertainties=(),
        completeness={},
        lineage={"origin": "g3a-test"},
        provenance={"input_version": "fixture-v1", "input_hash": "input-hash-1"},
    )


def _initial_batch() -> CoreRegistryBatch:
    passage = _passage("SP-1", "帝命某掌军务", 0)
    assertion = _assertion("A-1", passage.passage_cache_id)
    episode = _packet((assertion.assertion_code, passage.passage_cache_id))
    artifact = ReviewArtifactRecord(
        artifact_id="ART-1",
        artifact_type="boundary_review",
        status="proposed",
        basis_hash="basis-1",
        policy_version="boundary-v1",
        schema_version="review-v1",
        payload={"episode_ids": [episode.episode_id]},
    )
    return CoreRegistryBatch(
        source_documents=(_document(),),
        source_passages=(passage,),
        assertions=(assertion,),
        episodes=(episode,),
        episode_dispositions=(
            EpisodeDispositionRecord(
                episode_id=episode.episode_id,
                semantic_version=1,
                evidence_version=1,
                assertion_ref=assertion.assertion_code,
                disposition="core_of_episode",
                reason="核心任命证据",
            ),
        ),
        review_artifacts=(artifact,),
        boundary_cache_entries=(
            BoundaryReviewCacheEntry(
                cache_key="cache-1",
                input_hash="input-hash-1",
                policy_version="boundary-v1",
                schema_version="review-v1",
                model_family="fixture",
                artifact_id=artifact.artifact_id,
            ),
        ),
    )


def test_initial_apply_and_unchanged_rerun_are_idempotent() -> None:
    registry = InMemoryCoreRegistry()
    batch = _initial_batch()

    first = registry.apply(batch)
    second = registry.apply(batch)

    assert first.business_write_count > 0
    assert first.model_call_count == 0
    assert second.business_write_count == 0
    assert second.model_call_count == 0
    assert all(count == 0 for count in second.table_writes.values())
    assert registry.counts()["historical_episode_versions"] == 1


def test_evidence_revision_only_adds_evidence_version_and_new_lineage() -> None:
    registry = InMemoryCoreRegistry()
    initial = _initial_batch()
    registry.apply(initial)
    current = initial.episodes[0]
    passage = _passage("SP-2", "又命某仍掌军务", 20)
    assertion = _assertion("A-2", passage.passage_cache_id)
    observed = replace(
        current,
        assertion_links=current.assertion_links
        + (
            AssertionLink(
                assertion_ref="A-2",
                source_passage_ref="SP-2",
                relation="supports",
                supported_fields=("identity", "action", "responsibility"),
            ),
        ),
    )
    revision = apply_episode_revision(current, observed).packet

    result = registry.apply(
        CoreRegistryBatch(
            source_passages=(passage,),
            assertions=(assertion,),
            episodes=(revision,),
            episode_dispositions=(
                EpisodeDispositionRecord(
                    episode_id="EP-1",
                    semantic_version=1,
                    evidence_version=2,
                    assertion_ref="A-2",
                    disposition="core_of_episode",
                    reason="新增同义证据",
                ),
            ),
        )
    )

    assert revision.semantic_version == 1
    assert revision.evidence_version == 2
    assert result.table_writes["historical_episode_versions"] == 1
    assert result.table_writes["episode_participants"] == 0
    assert registry.counts()["historical_episode_versions"] == 2


def test_semantic_revision_adds_new_semantic_participant_rows() -> None:
    registry = InMemoryCoreRegistry()
    initial = _initial_batch()
    registry.apply(initial)
    current = initial.episodes[0]
    observed = replace(current, responsibility="财政")
    revision = apply_episode_revision(current, observed).packet

    result = registry.apply(CoreRegistryBatch(episodes=(revision,)))

    assert revision.semantic_version == 2
    assert result.table_writes["historical_episode_versions"] == 1
    assert result.table_writes["episode_participants"] == 2


def test_failed_batch_is_atomic() -> None:
    registry = InMemoryCoreRegistry()
    registry.apply(_initial_batch())
    before = dict(registry.counts())
    bad_episode = replace(
        _initial_batch().episodes[0],
        episode_id="EP-BAD",
        assertion_links=(
            AssertionLink(
                assertion_ref="A-MISSING",
                source_passage_ref="SP-MISSING",
                relation="supports",
                supported_fields=("identity", "action"),
            ),
        ),
    )

    with pytest.raises(ValueError, match="lineage"):
        registry.apply(CoreRegistryBatch(episodes=(bad_episode,)))

    assert registry.counts() == before


def test_g3a_rejects_formal_or_accepted_relation_artifact() -> None:
    with pytest.raises(ValueError, match="artifact status"):
        ReviewArtifactRecord(
            artifact_id="REL-1",
            artifact_type="relation_proposal",
            status="accepted",
            basis_hash="basis",
            policy_version="relation-v1",
            schema_version="relation-v1",
            payload={},
        )


def test_stable_identity_conflict_fails_closed() -> None:
    registry = InMemoryCoreRegistry()
    initial = _initial_batch()
    registry.apply(initial)
    conflicting = replace(initial.assertions[0], predicate="罢免")

    with pytest.raises(ValueError, match="Assertion 稳定身份发生冲突"):
        registry.apply(CoreRegistryBatch(assertions=(conflicting,)))
