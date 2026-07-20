from __future__ import annotations

from dataclasses import replace

import pytest

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.episode import AssertionLink, EpisodeParticipant, HistoricalEpisodePacket
from emperor_v4.contracts.source import SOURCE_CACHE_CONTRACT_V2, SourceDocumentDraft, SourcePassage, text_content_hash
from emperor_v4.persistence import CoreRegistryBatch, EpisodeDispositionRecord, InMemoryCoreRegistry, SourceDocumentRecord


def _document() -> SourceDocumentRecord:
    return SourceDocumentRecord(
        SourceDocumentDraft("DOC-1", "史记", "wikisource-1", "史记", "https://example.invalid/shiji", "primary", "2026-07-13T00:00:00Z", "doc-hash-1", "public-domain"),
        revision_ref="rev-1",
    )


def _passage(code: str, text: str, start: int) -> SourcePassage:
    return SourcePassage(
        passage_cache_id=code, document_cache_id="DOC-1", locator=f"section:{start}",
        raw_text=text, context_before="", context_after="", content_hash=text_content_hash(text),
        selection_reason=("appointment_delegation",), contract_version=SOURCE_CACHE_CONTRACT_V2,
        content_version="rev-1", section_id="SEC-1", section_heading="本纪",
        span_start=start, span_end=start + len(text), passage_kind="atomic",
        window_policy_version="window-v1",
    )


def _assertion(code: str, passage: str, *, predicate: str = "任命") -> AssertionDraft:
    return AssertionDraft(code, passage, "event_fact", "PER-RULER", predicate, "PER-OFFICIAL", "元年", None, {}, "asserted", {"document_id": "DOC-1"}, None, 0.95)


def _packet(*links: tuple[str, str], responsibility: str = "军务") -> HistoricalEpisodePacket:
    return HistoricalEpisodePacket(
        episode_id="EP-1", episode_type="appointment_delegation", episode_status="proposed",
        evaluation_context="PER-RULER", semantic_fingerprint=f"semantic-{responsibility}",
        time_start="元年", time_end=None, time_precision="year", locations=(),
        participants=(EpisodeParticipant("PER-RULER", ("ruler",), "resolved"), EpisodeParticipant("PER-OFFICIAL", ("office_holder",), "resolved")),
        action="任命", responsibility=responsibility, outcome=(), consequence=(),
        assertion_links=tuple(AssertionLink(a, p, "supports", ("identity", "action", "responsibility")) for a, p in links),
        conflicts=(), uncertainties=(), completeness={}, lineage={"origin": "g3a-test"}, provenance={"input_hash": "input-hash-1"},
    )


def _initial_batch() -> CoreRegistryBatch:
    passage = _passage("SP-1", "帝命某掌军务", 0)
    assertion = _assertion("A-1", passage.passage_cache_id)
    episode = _packet((assertion.assertion_code, passage.passage_cache_id))
    return CoreRegistryBatch(
        source_documents=(_document(),), source_passages=(passage,), assertions=(assertion,), episodes=(episode,),
        episode_dispositions=(EpisodeDispositionRecord("EP-1", "A-1", "core_of_episode", "核心任命证据"),),
    )


def test_current_rows_are_idempotent_and_updated_in_place() -> None:
    registry = InMemoryCoreRegistry()
    first = registry.apply(_initial_batch())
    second = registry.apply(_initial_batch())
    changed = registry.apply(CoreRegistryBatch(episodes=(replace(_initial_batch().episodes[0], responsibility="财政"),)))
    assert first.business_write_count > 0
    assert second.business_write_count == 0
    assert changed.table_writes["historical_episodes"] == 1
    assert registry.snapshot_counts()["historical_episodes"] == 1


def test_evidence_update_replaces_current_episode_without_history_row() -> None:
    registry = InMemoryCoreRegistry()
    initial = _initial_batch()
    registry.apply(initial)
    passage = _passage("SP-2", "又命某仍掌军务", 20)
    assertion = _assertion("A-2", "SP-2")
    episode = replace(initial.episodes[0], assertion_links=initial.episodes[0].assertion_links + (AssertionLink("A-2", "SP-2", "supports", ("action",)),))
    result = registry.apply(CoreRegistryBatch(source_passages=(passage,), assertions=(assertion,), episodes=(episode,)))
    assert result.table_writes["historical_episodes"] == 1
    assert registry.snapshot_counts()["historical_episodes"] == 1


def test_failed_batch_is_atomic_and_anchor_cannot_move() -> None:
    registry = InMemoryCoreRegistry()
    initial = replace(_initial_batch(), episode_identity_anchors={"EP-1": "ANCHOR-1"})
    registry.apply(initial)
    before = dict(registry.snapshot_counts())
    with pytest.raises(ValueError, match="lineage"):
        registry.apply(CoreRegistryBatch(episodes=(replace(initial.episodes[0], episode_id="EP-BAD", assertion_links=(AssertionLink("A-X", "SP-X", "supports", ("action",)),)),)))
    with pytest.raises(ValueError, match="不得变化"):
        registry.apply(CoreRegistryBatch(episodes=initial.episodes, episode_identity_anchors={"EP-1": "ANCHOR-2"}))
    assert registry.snapshot_counts() == before
