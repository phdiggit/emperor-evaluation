from __future__ import annotations

import json
from pathlib import Path

import pytest

from emperor_v4.adapters import (
    adapt_claim_extractor_snapshot,
    adapt_source_cache_snapshot,
)
from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.source import SourcePassage, text_content_hash


FIXTURES = Path(__file__).parent / "fixtures" / "episode_pilot_v1"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_source_cache_adapter_preserves_passage_lineage_and_reports_legacy_gaps():
    adapted = adapt_source_cache_snapshot(_fixture("source-cache-response.json"))

    assert len(adapted.documents) == 11
    assert len(adapted.passages) == 28
    assert {gap.object_ref for gap in adapted.contract_gaps} == {
        document.document_cache_id for document in adapted.documents
    }
    assert all("content_hash" in gap.missing_fields for gap in adapted.contract_gaps)
    assert all(
        passage.document_cache_id
        in {document.document_cache_id for document in adapted.documents}
        for passage in adapted.passages
    )


def test_source_passage_hash_is_derived_only_from_raw_text():
    adapted = adapt_source_cache_snapshot(_fixture("source-cache-response.json"))

    assert all(
        passage.content_hash == text_content_hash(passage.raw_text)
        for passage in adapted.passages
    )


def test_claim_adapter_produces_one_assertion_per_passage_lineage():
    snapshot = _fixture("claim-extractor-response.json")
    expected_count = sum(
        len(claim["source_passage_refs"])
        for person in snapshot["people"]
        for claim in person["payload"]["claims"]
    )
    adapted = adapt_claim_extractor_snapshot(snapshot)

    assert len(adapted) == expected_count == 46
    assert len({assertion.assertion_code for assertion in adapted}) == expected_count
    assert all(assertion.source_passage_ref for assertion in adapted)
    assert all(assertion.candidate_episode_key is None for assertion in adapted)


def test_multi_passage_legacy_claim_is_fanned_out_without_losing_origin():
    adapted = adapt_claim_extractor_snapshot(_fixture("claim-extractor-response.json"))
    fanned_out = [
        assertion
        for assertion in adapted
        if "legacy_multi_passage_claim_fanned_out" in assertion.ambiguity_flags
    ]

    assert len(fanned_out) == 6
    assert len({item.extraction_provenance["legacy_claim_code"] for item in fanned_out}) == 3
    assert all("@PAS-" in item.assertion_code for item in fanned_out)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_assertion_contract_rejects_out_of_range_confidence(confidence: float):
    with pytest.raises(ValueError, match="confidence"):
        AssertionDraft(
            assertion_code="A-1",
            source_passage_ref="P-1",
            assertion_type="event_fact",
            subject="甲",
            predicate="任命",
            object="乙",
            time_expression=None,
            location_expression=None,
            qualifiers={},
            polarity="asserted",
            source_attribution={},
            candidate_episode_key=None,
            confidence=confidence,
        )


def test_passage_contract_rejects_hash_mismatch():
    with pytest.raises(ValueError, match="content_hash"):
        SourcePassage(
            passage_cache_id="P-1",
            document_cache_id="D-1",
            locator="卷一",
            raw_text="原文",
            context_before="",
            context_after="",
            content_hash="not-the-text-hash",
            selection_reason=(),
        )
