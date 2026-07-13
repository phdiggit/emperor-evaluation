from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from emperor_v4.adapters import (
    adapt_claim_extractor_snapshot,
    adapt_source_cache_snapshot,
    adapt_source_cache_v2_response,
)
from emperor_v4.contracts.assertion import AssertionDraft, PassageSupport
from emperor_v4.contracts.source import (
    SOURCE_CACHE_CONTRACT_V2,
    LinkedPassageRef,
    SourcePassage,
    text_content_hash,
)
from emperor_v4.domain.source_segmentation import (
    PassageLinkSeed,
    PassageSeed,
    SourceSection,
    WindowPolicy,
    slice_source_section,
)
from emperor_v4.domain.identity import canonical_person
from emperor_v4.domain.boundary import draft_rule_evidence_unit
from emperor_v4.evaluation.blind_holdout import validate_blind_kernel_input
from emperor_v4.evaluation.passage_support import (
    canonical_payload_hash,
    materialize_passage_scoped_blind_input,
)


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


def test_legacy_claim_adapter_produces_one_assertion_per_passage_lineage():
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


def _single_multi_passage_claim_snapshot() -> tuple[dict, dict]:
    snapshot = deepcopy(_fixture("claim-extractor-response.json"))
    person = next(
        item
        for item in snapshot["people"]
        if any(
            len(claim.get("source_passage_refs") or ()) > 1
            for claim in item["payload"]["claims"]
        )
    )
    claim = next(
        claim
        for claim in person["payload"]["claims"]
        if len(claim.get("source_passage_refs") or ()) > 1
    )
    person["payload"]["claims"] = [claim]
    snapshot["people"] = [person]
    snapshot["adapter_target_contract"] = "assertion-extraction-contract-v2"
    return snapshot, claim


def test_v2_claim_adapter_rejects_unbound_multi_passage_fanout():
    snapshot, claim = _single_multi_passage_claim_snapshot()

    with pytest.raises(ValueError, match="未完整且唯一覆盖"):
        adapt_claim_extractor_snapshot(snapshot)


def test_v2_claim_adapter_splits_atomic_components_with_passage_scoped_payloads():
    snapshot, claim = _single_multi_passage_claim_snapshot()
    first_ref, second_ref = claim["source_passage_refs"]
    claim["passage_support_bindings"] = [
        {
            "source_passage_ref": first_ref,
            "support_mode": "atomic_component",
            "assertion_semantic_key": "wei-zheng-house",
            "supported_fields": ["identity", "action", "outcome"],
            "fact_overrides": {
                "action_type": "营造居所",
                "outcome": "为魏徵营造居所",
            },
        },
        {
            "source_passage_ref": second_ref,
            "support_mode": "atomic_component",
            "assertion_semantic_key": "wei-zheng-funeral",
            "supported_fields": ["identity", "action", "outcome"],
            "fact_overrides": {
                "action_type": "赠谥",
                "outcome": "废朝并赠官谥文贞",
            },
        },
    ]

    adapted = adapt_claim_extractor_snapshot(snapshot)

    assert [item.predicate for item in adapted] == ["营造居所", "赠谥"]
    assert {item.passage_support.support_mode for item in adapted} == {
        "atomic_component"
    }
    assert len({item.passage_support.assertion_semantic_key for item in adapted}) == 2
    assert all(
        "legacy_multi_passage_claim_fanned_out" not in item.ambiguity_flags
        for item in adapted
    )


def test_v2_claim_adapter_accepts_explicit_equivalent_evidence_only_when_semantics_match():
    snapshot, claim = _single_multi_passage_claim_snapshot()
    claim["passage_support_bindings"] = [
        {
            "source_passage_ref": passage_ref,
            "support_mode": "equivalent_evidence",
            "assertion_semantic_key": "same-wei-zheng-event",
            "supported_fields": ["identity", "action", "responsibility", "outcome"],
        }
        for passage_ref in claim["source_passage_refs"]
    ]
    adapted = adapt_claim_extractor_snapshot(snapshot)
    assert len(adapted) == 2
    assert len({item.passage_support.assertion_semantic_key for item in adapted}) == 1

    claim["passage_support_bindings"][1]["fact_overrides"] = {
        "action_type": "另一原子行动"
    }
    with pytest.raises(ValueError, match="逐 passage 语义不一致"):
        adapt_claim_extractor_snapshot(snapshot)


def test_passage_support_contract_rejects_core_binding_without_identity_and_action():
    with pytest.raises(ValueError, match="identity 和 action"):
        PassageSupport(
            support_mode="atomic_component",
            assertion_semantic_key="component-1",
            supported_fields=("outcome",),
        )


def test_passage_support_review_materializes_strict_blind_input_before_episode_review():
    snapshot, claim = _single_multi_passage_claim_snapshot()
    snapshot.pop("adapter_target_contract")
    snapshot["dataset_code"] = "passage-support-smoke"
    snapshot["canonical_people"] = []
    snapshot["collection_provenance"] = {
        "network_request_count": 0,
        "database_write_count": 0,
    }
    bindings = [
        {
            "source_passage_ref": passage_ref,
            "support_mode": "atomic_component",
            "assertion_semantic_key": f"component-{index}",
            "supported_fields": ["identity", "action", "outcome"],
            "fact_overrides": {
                "action_type": f"原子行动{index}",
                "outcome": f"原子结果{index}",
            },
        }
        for index, passage_ref in enumerate(claim["source_passage_refs"], start=1)
    ]
    review = {
        "status": "frozen_before_episode_review",
        "reviewed_without_episode_gold_or_candidates": True,
        "source_snapshot_sha256": canonical_payload_hash(snapshot),
        "claim_support_reviews": [
            {
                "claim_code": claim["claim_code"],
                "passage_support_bindings": bindings,
            }
        ],
    }

    result = materialize_passage_scoped_blind_input(snapshot, review)

    assert result["assertion_input_contract"] == "passage-scoped-assertion-v2"
    assert [row["predicate"] for row in result["assertions"]] == [
        "原子行动1",
        "原子行动2",
    ]
    assert all(row["passage_support"] for row in result["assertions"])

    review["source_snapshot_sha256"] = "wrong"
    with pytest.raises(ValueError, match="snapshot hash"):
        materialize_passage_scoped_blind_input(snapshot, review)


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


def test_source_cache_v2_slicer_preserves_section_span_links_and_stable_identity():
    text = "太宗命甲总军。甲受军务。甲班师奏捷。"
    section = SourceSection(
        document_cache_id="D-V2",
        content_version="sha256:document-v1",
        section_id="卷一/任将",
        section_heading="任将",
        raw_text=text,
        document_span_start=100,
    )
    seeds = (
        PassageSeed(
            seed_code="appointment",
            anchor_start=text.index("太宗"),
            anchor_end=text.index("。") + 1,
            passage_kind="atomic",
            selection_reason=("appointment",),
            links=(PassageLinkSeed("outcome", "outcome"),),
        ),
        PassageSeed(
            seed_code="responsibility",
            anchor_start=text.index("甲受"),
            anchor_end=text.index("。", text.index("甲受")) + 1,
            passage_kind="context",
            selection_reason=("responsibility",),
        ),
        PassageSeed(
            seed_code="outcome",
            anchor_start=text.index("甲班"),
            anchor_end=len(text),
            passage_kind="atomic",
            selection_reason=("outcome",),
        ),
    )
    policy = WindowPolicy(version="section-sentence-v2")

    first = slice_source_section(section, seeds, policy)
    second = slice_source_section(section, seeds, policy)

    assert first == second
    assert all(item.is_contract_v2 for item in first)
    assert all(item.section_heading == "任将" for item in first)
    assert all(item.span_start >= 100 for item in first)
    appointment = next(item for item in first if item.selection_reason == ("appointment",))
    outcome = next(item for item in first if item.selection_reason == ("outcome",))
    assert appointment.linked_passages == (
        LinkedPassageRef(outcome.passage_cache_id, "outcome"),
    )

    response = {
        "contract": SOURCE_CACHE_CONTRACT_V2,
        "documents": [
            {
                "document_cache_id": "D-V2",
                "work_identity": "测试史书",
                "edition_identity": "测试本",
                "title": "测试史书/卷一",
                "url": "https://example.invalid/work/1",
                "source_role": "primary",
                "retrieved_at": "2026-07-13T00:00:00+08:00",
                "content_hash": "sha256:document-v1",
                "http_metadata": {},
                "license_or_access_note": "test fixture",
            }
        ],
        "passages": [
            {
                "passage_id": item.passage_cache_id,
                "document_id": item.document_cache_id,
                "locator": item.locator,
                "raw_text": item.raw_text,
                "context_before": item.context_before,
                "context_after": item.context_after,
                "content_hash": item.content_hash,
                "selection_reason": list(item.selection_reason),
                "content_version": item.content_version,
                "section_id": item.section_id,
                "section_heading": item.section_heading,
                "span_start": item.span_start,
                "span_end": item.span_end,
                "passage_kind": item.passage_kind,
                "linked_passages": [
                    {
                        "passage_ref": link.passage_ref,
                        "relation": link.relation,
                    }
                    for link in item.linked_passages
                ],
                "overlap_group": item.overlap_group,
                "window_policy_version": item.window_policy_version,
            }
            for item in first
        ],
    }
    adapted = adapt_source_cache_v2_response(response)
    assert adapted.passages == first
    assert adapted.contract_gaps == ()


def test_source_passage_v2_rejects_invalid_span_and_self_link():
    common = {
        "passage_cache_id": "P-V2",
        "document_cache_id": "D-V2",
        "locator": "卷一:0-2",
        "raw_text": "原文",
        "context_before": "",
        "context_after": "",
        "content_hash": text_content_hash("原文"),
        "selection_reason": ("test",),
        "contract_version": SOURCE_CACHE_CONTRACT_V2,
        "content_version": "v1",
        "section_id": "卷一",
        "section_heading": "卷一",
        "span_start": 0,
        "span_end": 2,
        "passage_kind": "atomic",
        "window_policy_version": "policy-v2",
    }
    with pytest.raises(ValueError, match="span 长度"):
        SourcePassage(**{**common, "span_end": 3})
    with pytest.raises(ValueError, match="不得链接自身"):
        SourcePassage(
            **common,
            linked_passages=(LinkedPassageRef("P-V2", "continuation"),),
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


def test_passage_scoped_blind_input_rejects_legacy_unscoped_fanout():
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    payload["assertion_input_contract"] = "passage-scoped-assertion-v2"
    payload["assertions"][0]["ambiguity_flags"] = [
        "legacy_multi_passage_claim_fanned_out"
    ]

    with pytest.raises(ValueError, match="legacy multi-passage fan-out"):
        validate_blind_kernel_input(payload)
