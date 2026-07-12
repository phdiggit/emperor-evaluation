from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from emperor_v4.adapters import (
    adapt_claim_extractor_snapshot,
    adapt_source_cache_snapshot,
)
from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.source import SourcePassage, text_content_hash
from emperor_v4.domain.identity import canonical_person
from emperor_v4.domain.boundary import draft_rule_evidence_unit
from emperor_v4.evaluation.blind_holdout import validate_blind_kernel_input


FIXTURES = Path(__file__).parent / "fixtures" / "episode_pilot_v1"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_rule_evidence_unit_is_draft_only_and_does_not_score():
    unit = draft_rule_evidence_unit(
        rule_code="appointment_delegation",
        rule_version="1.0.0",
        aggregation_policy_version="delegation-chain-v1",
        evaluation_context="PER-LISHIMIN",
        episode_members={"EP-1": "appointment", "EP-2": "feedback"},
        relation_members={"REL-1": "revocation_link"},
        aggregation_reason="授职、结果与撤任共同消费",
    )

    assert unit.status == "draft"
    assert unit.episode_refs == ("EP-1", "EP-2")
    assert unit.rule_version == "1.0.0"
    assert unit.aggregation_policy_version == "delegation-chain-v1"
    assert unit.semantic_fingerprint
    assert not hasattr(unit, "score")

    changed_policy = draft_rule_evidence_unit(
        rule_code="appointment_delegation",
        rule_version="1.0.0",
        aggregation_policy_version="delegation-chain-v2",
        evaluation_context="PER-LISHIMIN",
        episode_members={"EP-1": "appointment", "EP-2": "feedback"},
        relation_members={"REL-1": "revocation_link"},
        aggregation_reason="同一成员按新策略聚合",
    )
    assert changed_policy.unit_code != unit.unit_code


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


def test_v4_shadow_claim_adapter_preserves_structured_actor_and_object_roles():
    adapted = adapt_claim_extractor_snapshot(
        _fixture("claim-extractor-gap-repair-response.json")
    )
    sanjie = [
        assertion
        for assertion in adapted
        if "CLM-LB-SANJIE" in assertion.assertion_code
    ]
    fankuai = [
        assertion
        for assertion in adapted
        if "CLM-CP-FANKUAI" in assertion.assertion_code
    ]

    sanjie_people = {
        person
        for assertion in sanjie
        for person, _ in assertion.qualifiers["candidate_participant_roles"]
    }
    fankuai_people = {
        person
        for assertion in fankuai
        for person, _ in assertion.qualifiers["candidate_participant_roles"]
    }

    assert sanjie_people == {"刘邦", "张良", "萧何", "韩信"}
    assert fankuai_people == {"刘邦", "陈平", "周勃", "樊哙"}


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


def test_canonical_person_identity_fingerprint_is_deterministic():
    first = canonical_person("PER-LIU-BANG", "刘邦", "西汉")
    second = canonical_person("PER-LIU-BANG", "刘邦", "西汉")

    assert first == second
    assert first.identity_status == "candidate"
    assert len(first.identity_fingerprint) == 64


def test_canonical_person_identity_fingerprint_does_not_depend_on_person_id():
    first = canonical_person("PER-A", "年羹尧", "清")
    duplicate_candidate = canonical_person("PER-B", "年羹尧", "清")

    assert first.identity_fingerprint == duplicate_candidate.identity_fingerprint


def test_claim_adapter_maps_structured_location_not_event_scope():
    snapshot = deepcopy(_fixture("claim-extractor-gap-repair-response.json"))
    claim = snapshot["people"][0]["payload"]["claims"][0]
    claim["fact_payload"]["event_scope"] = "军事"
    claim["fact_payload"]["location"] = "渭北"

    assertion = next(
        item
        for item in adapt_claim_extractor_snapshot(snapshot)
        if claim["claim_code"] in item.assertion_code
    )

    assert assertion.location_expression == "渭北"
    assert "missing_location_expression" not in assertion.ambiguity_flags


def test_claim_adapter_carries_boundary_partition_fields():
    snapshot = deepcopy(_fixture("claim-extractor-gap-repair-response.json"))
    claim = snapshot["people"][0]["payload"]["claims"][0]
    claim["fact_payload"]["normalized_time"] = {
        "start_sort_key": 629,
        "end_sort_key": 629,
        "precision": "year",
        "dynasty_or_era": "唐",
    }
    claim["fact_payload"]["responsibility_family"] = "military_command"

    assertion = next(
        item
        for item in adapt_claim_extractor_snapshot(snapshot)
        if claim["claim_code"] in item.assertion_code
    )

    assert assertion.qualifiers["normalized_time"]["start_sort_key"] == 629
    assert assertion.qualifiers["responsibility_family"] == "military_command"
    assert assertion.qualifiers["focal_person_ref"]
    assert assertion.extraction_provenance["claim_key"] == claim["claim_code"]


def test_claim_adapter_does_not_treat_event_scope_as_location():
    assertion = adapt_claim_extractor_snapshot(
        _fixture("claim-extractor-gap-repair-response.json")
    )[0]

    assert assertion.qualifiers["event_scope"]
    assert assertion.location_expression is None
    assert "missing_location_expression" in assertion.ambiguity_flags


def test_blind_kernel_input_rejects_oracle_fields_at_any_depth():
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    payload["assertions"][0]["qualifiers"]["episode_code"] = "FORBIDDEN"

    with pytest.raises(ValueError, match="Gold/oracle"):
        validate_blind_kernel_input(payload)
