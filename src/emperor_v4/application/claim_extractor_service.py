from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Protocol

from emperor_v4.adapters.claim_extraction_profile import ClaimExtractionProfile, render_claim_extraction_request
from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.extraction import ASSERTION_EXTRACTION_CONTRACT_V2, ClaimExtractionRequest


SERVICE_VERSION = "v4-claim-extractor-service:v1"
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def claim_extraction_input_fingerprint(request: ClaimExtractionRequest, profile: ClaimExtractionProfile) -> str:
    rendered = render_claim_extraction_request(
        profile=profile, subject=request.subject, passages=request.passages,
    )
    return _fingerprint({
        "idempotency_key": request.idempotency_key,
        "profile_input_fingerprint": rendered["input_fingerprint"],
    })


@dataclass(frozen=True, slots=True)
class ClaimExtractionBatch:
    assertions: tuple[AssertionDraft, ...]
    provider_code: str
    model_call_count: int = 0


class ClaimExtractionProvider(Protocol):
    def extract(self, request_payload: Mapping[str, Any]) -> ClaimExtractionBatch: ...


@dataclass(frozen=True, slots=True)
class CachedClaimExtractionResult:
    input_fingerprint: str
    response: Mapping[str, Any]


class ClaimExtractionRepository(Protocol):
    def get(self, idempotency_key: str) -> CachedClaimExtractionResult | None: ...
    def put(self, idempotency_key: str, input_fingerprint: str, response: Mapping[str, Any]) -> int: ...


@dataclass(frozen=True, slots=True)
class ClaimExtractionServiceRun:
    response: Mapping[str, Any]
    cache_hit: bool
    provider_call_count: int
    model_call_count: int
    repository_write_count: int


def ensure_claim_extraction(
    request: ClaimExtractionRequest, *, profile: ClaimExtractionProfile,
    provider: ClaimExtractionProvider, repository: ClaimExtractionRepository,
    service_release_sha: str,
) -> ClaimExtractionServiceRun:
    if not _COMMIT_SHA_RE.fullmatch(service_release_sha):
        raise ValueError("service_release_sha 必须是 40 位小写 Git commit SHA")
    if request.profile_code != profile.code:
        raise ValueError("Claim extraction request/profile 不一致")
    input_fingerprint = claim_extraction_input_fingerprint(request, profile)
    cached = repository.get(request.idempotency_key)
    if cached is not None:
        if cached.input_fingerprint != input_fingerprint:
            raise ValueError("Claim extraction 幂等键已绑定不同输入")
        return ClaimExtractionServiceRun(cached.response, True, 0, 0, 0)
    rendered = render_claim_extraction_request(
        profile=profile, subject=request.subject, passages=request.passages,
    )
    batch = provider.extract(rendered)
    if not batch.assertions:
        raise ValueError("Claim Extractor 不得以空 Assertion 集合伪装成功")
    passage_refs = {str(row.get("passage_id") or row.get("passage_code")) for row in request.passages}
    assertion_codes: set[str] = set()
    for assertion in batch.assertions:
        if assertion.assertion_code in assertion_codes:
            raise ValueError("Claim Extractor assertion_code 重复")
        assertion_codes.add(assertion.assertion_code)
        if assertion.source_passage_ref not in passage_refs:
            raise ValueError("Claim Extractor Assertion 越出请求 passages")
        if assertion.passage_support is None:
            raise ValueError("v2 Claim Extractor Assertion 缺少 PassageSupport")
    assertion_payloads = [asdict(item) for item in batch.assertions]
    response = {
        "contract": ASSERTION_EXTRACTION_CONTRACT_V2,
        "request_id": request.request_id,
        "profile_code": profile.code,
        "status": "succeeded",
        "assertions": assertion_payloads,
        "provenance": {
            "provider": batch.provider_code,
            "service_version": SERVICE_VERSION,
            "service_release_sha": service_release_sha,
            "input_fingerprint": input_fingerprint,
        },
    }
    response["output_fingerprint"] = _fingerprint(response)
    writes = repository.put(request.idempotency_key, input_fingerprint, response)
    return ClaimExtractionServiceRun(response, False, 1, batch.model_call_count, writes)
