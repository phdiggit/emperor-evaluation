from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.adapters.claim_extraction_profile import (
    ClaimExtractionProfile,
)
from emperor_v4.adapters.claim_extractor_codex import (
    CodexCliClaimExtractionProvider,
    parse_codex_claim_output,
)
from emperor_v4.adapters.source_cache_wikisource import (
    WikisourceSourceMaterialProvider,
)
from emperor_v4.adapters.wikisource import WikisourcePageSnapshot
from emperor_v4.application.claim_extractor_service import (
    ClaimExtractionBatch,
    ensure_claim_extraction,
)
from emperor_v4.contracts.extraction import ClaimExtractionRequest
from emperor_v4.contracts.source import SourceCacheRequest, SourceCacheSubject
from emperor_v4.persistence.claim_extractor import (
    InMemoryClaimExtractionRepository,
)
from emperor_v4.runtime.claim_extractor import (
    claim_worker_lease_seconds,
    request_profile_from_mapping,
)


ROOT = Path(__file__).parents[1]
PROFILES = ROOT / "config" / "claim-extraction-profiles.yml"
OUTPUT_SCHEMA = ROOT / "config" / "claim-extraction-output.schema.json"


def _claim_payload() -> dict:
    return {
        "assertions": [
            {
                "assertion_code": "A-LOCAL-1",
                "source_passage_ref": "SP-1",
                "assertion_type": "event_fact",
                "subject": "太宗",
                "predicate": "召见",
                "object": "魏徵",
                "time_expression": None,
                "location_expression": None,
                "qualifiers": {
                    "responsibility_family": "talent_discovery"
                },
                "polarity": "asserted",
                "source_attribution": {},
                "confidence": 0.9,
                "ambiguity_flags": [],
                "passage_support": {
                    "support_mode": "single_passage",
                    "assertion_semantic_key": "太宗-召见-魏徵",
                    "supported_fields": ["identity", "action"],
                },
            }
        ],
        "coverage_gaps": ["缺少后续任用结果"],
    }


def _request(profile_code: str = "political_action_atomic_v1"):
    return ClaimExtractionRequest(
        request_id="CER-SCALE-1",
        idempotency_key="claim-scale-contract:1",
        profile_code=profile_code,
        subject={
            "person_ref": "PER-WEIZHENG",
            "ruler": "李世民",
            "aliases": ["魏徵"],
        },
        passages=(
            {
                "passage_id": "SP-1",
                "raw_text": "太宗召徵。",
            },
        ),
        requested_at="2026-07-14T00:00:00+08:00",
    )


def _profile(code: str = "political_action_atomic_v1"):
    return ClaimExtractionProfile(
        code=code,
        output_contract="assertion-extraction-contract-v2",
        purpose="抽取测试事实",
        required_chains=(),
        prohibitions=("不做评分",),
    )


def test_claim_worker_selects_profile_from_each_job_payload() -> None:
    payload = {
        "request_id": "CER-PROFILE-1",
        "idempotency_key": "claim-profile:1",
        "profile_code": "talent_discovery_chain_v1",
        "subject": {"person_ref": "PER-WEIZHENG"},
        "passages": [{"passage_id": "SP-1", "raw_text": "太宗召徵。"}],
        "requested_at": "2026-07-14T00:00:00+08:00",
    }

    request, profile = request_profile_from_mapping(PROFILES, payload)

    assert request.profile_code == "talent_discovery_chain_v1"
    assert profile.code == request.profile_code
    assert profile.required_chains


def test_claim_worker_lease_must_cover_model_timeout() -> None:
    assert claim_worker_lease_seconds(timeout_seconds=600) == 720
    assert claim_worker_lease_seconds(
        timeout_seconds=600,
        configured_lease_seconds=900,
    ) == 900
    with pytest.raises(ValueError, match="覆盖 provider timeout"):
        claim_worker_lease_seconds(
            timeout_seconds=600,
            configured_lease_seconds=600,
        )


def test_claim_service_accepts_explicit_empty_result_without_retry_loop() -> None:
    class EmptyProvider:
        calls = 0

        def extract(self, request_payload):
            self.calls += 1
            return ClaimExtractionBatch(
                assertions=(),
                provider_code="empty-fixture:v1",
                coverage_gaps=("no_relevant_fact_in_requested_profile",),
            )

    provider = EmptyProvider()
    repository = InMemoryClaimExtractionRepository()
    first = ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=provider,
        repository=repository,
        service_release_sha="a" * 40,
    )
    second = ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=provider,
        repository=repository,
        service_release_sha="a" * 40,
    )

    assert first.response["status"] == "succeeded_no_relevant_facts"
    assert first.response["assertions"] == []
    assert first.response["coverage_gaps"] == [
        "no_relevant_fact_in_requested_profile"
    ]
    assert second.cache_hit is True
    assert provider.calls == 1


def test_claim_service_rejects_silent_empty_result() -> None:
    class SilentProvider:
        def extract(self, request_payload):
            return ClaimExtractionBatch((), "silent-fixture:v1")

    with pytest.raises(ValueError, match="空结果必须声明"):
        ensure_claim_extraction(
            _request(),
            profile=_profile(),
            provider=SilentProvider(),
            repository=InMemoryClaimExtractionRepository(),
            service_release_sha="a" * 40,
        )


def test_codex_parser_preserves_gaps_and_runtime_audit() -> None:
    batch = parse_codex_claim_output(
        _claim_payload(),
        provider_code="codex:test",
        provider_metadata={"elapsed_seconds": 1.25, "prompt_chars": 300},
    )

    assert batch.coverage_gaps == ("缺少后续任用结果",)
    assert batch.provider_metadata["elapsed_seconds"] == 1.25
    assert batch.assertions[0].qualifiers["responsibility_family"] == (
        "talent_discovery"
    )


def test_claim_service_replaces_provider_ids_and_adds_trusted_routing() -> None:
    class PayloadProvider:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def extract(self, request_payload):
            return parse_codex_claim_output(
                self.payload,
                provider_code="codex:test",
            )

    first_payload = _claim_payload()
    second_payload = deepcopy(first_payload)
    second_payload["assertions"][0]["assertion_code"] = "MODEL-RANDOM-2"
    second_payload["assertions"][0]["passage_support"][
        "assertion_semantic_key"
    ] = "模型另一种措辞"
    second_payload["assertions"][0]["confidence"] = 0.72
    third_payload = deepcopy(first_payload)
    third_payload["assertions"][0].pop("assertion_code")

    first = ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=PayloadProvider(first_payload),
        repository=InMemoryClaimExtractionRepository(),
        service_release_sha="a" * 40,
    ).response["assertions"][0]
    second = ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=PayloadProvider(second_payload),
        repository=InMemoryClaimExtractionRepository(),
        service_release_sha="a" * 40,
    ).response["assertions"][0]
    third = ensure_claim_extraction(
        _request("talent_discovery_chain_v1"),
        profile=_profile("talent_discovery_chain_v1"),
        provider=PayloadProvider(third_payload),
        repository=InMemoryClaimExtractionRepository(),
        service_release_sha="a" * 40,
    ).response["assertions"][0]

    assert first["assertion_code"] == second["assertion_code"]
    assert first["assertion_code"] == third["assertion_code"]
    assert first["assertion_code"].startswith("ASTD-")
    assert (
        first["passage_support"]["assertion_semantic_key"]
        == second["passage_support"]["assertion_semantic_key"]
        == third["passage_support"]["assertion_semantic_key"]
    )
    assert first["extraction_provenance"]["provider_assertion_code"] == (
        "A-LOCAL-1"
    )
    assert second["extraction_provenance"]["provider_assertion_code"] == (
        "MODEL-RANDOM-2"
    )
    assert third["extraction_provenance"]["provider_assertion_code"] == (
        "provider-row-0001"
    )
    assert third["qualifiers"]["evaluation_context"] == "李世民"
    assert third["qualifiers"]["focal_person_ref"] == "PER-WEIZHENG"
    assert third["qualifiers"]["candidate_participant_roles"] == (
        ("李世民", "ruler"),
        ("PER-WEIZHENG", "focal_person"),
    )


def test_codex_provider_rejects_oversized_prompt_before_process_start() -> None:
    provider = CodexCliClaimExtractionProvider(
        codex_bin="never-executed",
        model="fixture-model",
        reasoning_effort="medium",
        output_schema_path=OUTPUT_SCHEMA,
        max_prompt_chars=32,
    )

    with pytest.raises(ValueError, match="prompt 超限"):
        provider.extract(
            {
                "profile_code": "political_action_atomic_v1",
                "passages": [
                    {"passage_id": "SP-1", "raw_text": "原文" * 100}
                ],
            }
        )


def test_claim_output_schema_supports_structured_qualifiers_and_empty_set() -> None:
    schema = json.loads(OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    assertions = schema["properties"]["assertions"]
    item_schema = assertions["items"]
    qualifiers = item_schema["properties"]["qualifiers"]["properties"]

    assert "minItems" not in assertions
    assert assertions["maxItems"] == 64
    assert "assertion_code" not in item_schema["required"]
    assert {
        "responsibility_family",
        "office_or_domain",
        "outcome",
        "normalized_time",
    } <= set(qualifiers)


def test_wikisource_provider_selects_subject_plan_and_fetches_page_once(
    tmp_path: Path,
) -> None:
    sections = []
    for section_id in ("任命", "结果"):
        sections.append(
            {
                "page_code": "history-001",
                "page_title": "测试史书/卷一",
                "expected_revision_id": 7,
                "work_identity": "测试史书",
                "edition_identity": "测试版本",
                "source_role": "primary",
                "license_or_access_note": "test",
                "section_id": section_id,
                "section_heading": section_id,
                "passages": [
                    {
                        "seed_code": section_id,
                        "anchor_start": "甲",
                        "anchor_end": "。",
                        "passage_kind": "atomic",
                        "selection_reason": [section_id],
                    }
                ],
                "window_policy": {
                    "version": "test-window-v1",
                    "sentence_radius_before": 0,
                    "sentence_radius_after": 0,
                    "context_chars_before": 0,
                    "context_chars_after": 0,
                },
            }
        )
    plan = {
        "schema_version": 1,
        "provider": "wikisource_revision_plan",
        "subject_ref": "PER-A",
        "sections": sections,
    }
    (tmp_path / "a.yml").write_text(
        yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (tmp_path / "b.yml").write_text(
        yaml.safe_dump(
            {**plan, "subject_ref": "PER-B"},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    calls = []
    raw_text = "甲。"

    def fetch(**kwargs):
        calls.append(kwargs)
        return WikisourcePageSnapshot(
            page_code="history-001",
            requested_title="测试史书/卷一",
            canonical_title="测试史书/卷一",
            canonical_url="https://example.invalid/history-001",
            revision_id=7,
            revision_timestamp="2026-07-14T00:00:00Z",
            retrieved_at="2026-07-14T00:00:01Z",
            raw_text=raw_text,
            content_hash=sha256(raw_text.encode("utf-8")).hexdigest(),
        )

    request = SourceCacheRequest(
        request_id="SRC-PLAN-1",
        idempotency_key="source-plan:1",
        subject=SourceCacheSubject("PER-A", "甲", ()),
        evaluation_context={"purpose": "test"},
        source_hints=("测试史书/卷一",),
        required_source_families=("primary_text",),
        mode="ensure",
        source_policy_version="test-source-policy-v1",
        requested_at="2026-07-14T00:00:00+08:00",
    )

    batch = WikisourceSourceMaterialProvider(
        plan_path=tmp_path,
        fetch=fetch,
    ).load(request)

    assert len(batch.sections) == 2
    assert batch.network_request_count == 1
    assert len(calls) == 1
