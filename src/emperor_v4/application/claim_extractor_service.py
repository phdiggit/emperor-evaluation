from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Protocol

from emperor_v4.adapters.claim_extraction_profile import (
    ClaimExtractionProfile,
    render_claim_extraction_request,
)
from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.extraction import (
    ASSERTION_EXTRACTION_CONTRACT_V2,
    ClaimExtractionRequest,
)


SERVICE_VERSION = "v4-claim-extractor-service:v1"
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ROUTING_QUALIFIER_KEYS = frozenset(
    {
        "evaluation_context",
        "focal_person_ref",
        "candidate_focal_person_refs",
        "candidate_participant_roles",
        "episode_type",
        "responsibility_family",
    }
)
_PROFILE_RESPONSIBILITY_FAMILY = {
    "talent_discovery_chain_v1": "talent_discovery",
}


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def json_equivalent(left: Any, right: Any) -> bool:
    return _stable(left) == _stable(right)


def _json_normalized(value: Any) -> Any:
    return json.loads(_stable(value))


def _fingerprint(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def historical_qualifiers(
    qualifiers: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        str(key): value
        for key, value in qualifiers.items()
        if str(key) not in _ROUTING_QUALIFIER_KEYS
    }


def assertion_semantic_payload(assertion: AssertionDraft) -> tuple[Any, ...]:
    """返回跨 evidence/profile 比较使用的历史事实语义。"""

    return (
        assertion.assertion_type,
        assertion.subject,
        assertion.predicate,
        assertion.object,
        assertion.time_expression,
        assertion.location_expression,
        _stable(historical_qualifiers(assertion.qualifiers)),
        assertion.polarity,
    )


def canonical_assertion_semantic_key(assertion: AssertionDraft) -> str:
    return "ASK-" + _fingerprint(assertion_semantic_payload(assertion))[:24].upper()


def canonical_assertion_code(
    assertion: AssertionDraft,
    semantic_key: str,
) -> str:
    return "ASTD-" + _fingerprint(
        {
            "source_passage_ref": assertion.source_passage_ref,
            "assertion_semantic_key": semantic_key,
        }
    )[:24].upper()


def enrich_assertion_routing(
    assertion: AssertionDraft,
    *,
    request: ClaimExtractionRequest,
    profile: ClaimExtractionProfile,
) -> AssertionDraft:
    """从可信 job subject 补齐 Episode 路由字段，不让模型自造身份。"""

    subject = request.subject
    evaluation_context = str(
        subject.get("evaluation_context")
        or subject.get("ruler_ref")
        or subject.get("ruler")
        or ""
    ).strip()
    focal_person_ref = str(
        subject.get("person_ref")
        or subject.get("person_or_ruler_ref")
        or ""
    ).strip()
    qualifiers = dict(assertion.qualifiers)
    if evaluation_context:
        qualifiers["evaluation_context"] = evaluation_context
    if focal_person_ref:
        qualifiers["focal_person_ref"] = focal_person_ref
        qualifiers["candidate_focal_person_refs"] = (focal_person_ref,)
    if evaluation_context or focal_person_ref:
        roles = []
        if evaluation_context:
            roles.append((evaluation_context, "ruler"))
        roles.append((focal_person_ref or assertion.subject, "focal_person"))
        qualifiers["candidate_participant_roles"] = tuple(roles)
    responsibility_family = _PROFILE_RESPONSIBILITY_FAMILY.get(profile.code)
    if responsibility_family and not qualifiers.get("responsibility_family"):
        qualifiers["responsibility_family"] = responsibility_family
    return replace(assertion, qualifiers=qualifiers)


def canonicalize_assertion_draft(assertion: AssertionDraft) -> AssertionDraft:
    if assertion.passage_support is None:
        raise ValueError("v2 Claim Extractor Assertion 缺少 PassageSupport")
    semantic_key = canonical_assertion_semantic_key(assertion)
    support = replace(
        assertion.passage_support,
        assertion_semantic_key=semantic_key,
        binding_provenance={
            **dict(assertion.passage_support.binding_provenance),
            "provider_assertion_semantic_key": (
                assertion.passage_support.assertion_semantic_key
            ),
        },
    )
    return replace(
        assertion,
        assertion_code=canonical_assertion_code(assertion, semantic_key),
        extraction_provenance={
            **dict(assertion.extraction_provenance),
            "provider_assertion_code": assertion.assertion_code,
        },
        passage_support=support,
    )


def canonical_assertion_storage_payload(
    assertion: Mapping[str, Any],
) -> Mapping[str, Any]:
    """canonical draft 表只存历史事实；profile/皇帝路由保留在 request response。"""

    payload = dict(assertion)
    payload["qualifiers"] = historical_qualifiers(
        assertion.get("qualifiers") or {}
    )
    return _json_normalized(payload)


def assertion_identity_payload(
    assertion: Mapping[str, Any],
) -> Mapping[str, Any]:
    """数据库冲突比较忽略模型置信度和运行 provenance，只比较事实。"""

    support = assertion.get("passage_support") or {}
    return _json_normalized(
        {
            "assertion_code": assertion.get("assertion_code"),
            "source_passage_ref": assertion.get("source_passage_ref"),
            "assertion_type": assertion.get("assertion_type"),
            "subject": assertion.get("subject"),
            "predicate": assertion.get("predicate"),
            "object": assertion.get("object"),
            "time_expression": assertion.get("time_expression"),
            "location_expression": assertion.get("location_expression"),
            "qualifiers": historical_qualifiers(
                assertion.get("qualifiers") or {}
            ),
            "polarity": assertion.get("polarity"),
            "passage_support": {
                "support_mode": support.get("support_mode"),
                "assertion_semantic_key": support.get(
                    "assertion_semantic_key"
                ),
                "supported_fields": support.get("supported_fields") or [],
            },
        }
    )


def claim_extraction_input_fingerprint(
    request: ClaimExtractionRequest,
    profile: ClaimExtractionProfile,
) -> str:
    rendered = render_claim_extraction_request(
        profile=profile,
        subject=request.subject,
        passages=request.passages,
    )
    return _fingerprint(
        {
            "idempotency_key": request.idempotency_key,
            "profile_input_fingerprint": rendered["input_fingerprint"],
        }
    )


@dataclass(frozen=True, slots=True)
class ClaimExtractionBatch:
    assertions: tuple[AssertionDraft, ...]
    provider_code: str
    model_call_count: int = 0
    coverage_gaps: tuple[str, ...] = ()
    provider_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider_code or self.model_call_count < 0:
            raise ValueError("Claim extraction batch provider/model audit 无效")
        gaps = tuple(self.coverage_gaps)
        if any(not str(item).strip() for item in gaps) or len(gaps) != len(
            set(gaps)
        ):
            raise ValueError("Claim extraction coverage_gaps 必须非空且唯一")


class ClaimExtractionProvider(Protocol):
    def extract(self, request_payload: Mapping[str, Any]) -> ClaimExtractionBatch: ...


@dataclass(frozen=True, slots=True)
class CachedClaimExtractionResult:
    input_fingerprint: str
    response: Mapping[str, Any]


class ClaimExtractionRepository(Protocol):
    def get(self, idempotency_key: str) -> CachedClaimExtractionResult | None: ...

    def put(
        self,
        idempotency_key: str,
        input_fingerprint: str,
        response: Mapping[str, Any],
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class ClaimExtractionServiceRun:
    response: Mapping[str, Any]
    cache_hit: bool
    provider_call_count: int
    model_call_count: int
    repository_write_count: int


def ensure_claim_extraction(
    request: ClaimExtractionRequest,
    *,
    profile: ClaimExtractionProfile,
    provider: ClaimExtractionProvider,
    repository: ClaimExtractionRepository,
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
        profile=profile,
        subject=request.subject,
        passages=request.passages,
    )
    batch = provider.extract(rendered)
    if not batch.assertions and not batch.coverage_gaps:
        raise ValueError("Claim Extractor 空结果必须声明 coverage_gaps")

    passage_refs = {
        str(row.get("passage_id") or row.get("passage_code"))
        for row in request.passages
    }
    semantic_rows: dict[tuple[Any, ...], list[AssertionDraft]] = {}
    support_key_rows: dict[str, list[AssertionDraft]] = {}
    for assertion in batch.assertions:
        if assertion.source_passage_ref not in passage_refs:
            raise ValueError("Claim Extractor Assertion 越出请求 passages")
        if assertion.passage_support is None:
            raise ValueError("v2 Claim Extractor Assertion 缺少 PassageSupport")
        semantic_rows.setdefault(assertion_semantic_payload(assertion), []).append(
            assertion
        )
        support_key_rows.setdefault(
            assertion.passage_support.assertion_semantic_key,
            [],
        ).append(assertion)

    for semantic, items in semantic_rows.items():
        if len(items) <= 1:
            continue
        support_keys = {
            item.passage_support.assertion_semantic_key for item in items
        }
        support_modes = {item.passage_support.support_mode for item in items}
        if len(support_keys) != 1 or support_modes != {"equivalent_evidence"}:
            raise ValueError(
                f"重复语义必须声明共享 equivalent_evidence: {semantic}"
            )

    for support_key, items in support_key_rows.items():
        modes = {item.passage_support.support_mode for item in items}
        if len(items) == 1 and modes == {"equivalent_evidence"}:
            raise ValueError(
                f"单条证据不得声明 equivalent_evidence: {support_key}"
            )
        if len(items) > 1 and (
            modes != {"equivalent_evidence"}
            or len({assertion_semantic_payload(item) for item in items}) != 1
        ):
            raise ValueError(
                "equivalent_evidence 语义 payload 必须完全一致: "
                f"{support_key}"
            )

    assertions = tuple(
        canonicalize_assertion_draft(
            enrich_assertion_routing(item, request=request, profile=profile)
        )
        for item in batch.assertions
    )
    canonical_codes = [item.assertion_code for item in assertions]
    if len(canonical_codes) != len(set(canonical_codes)):
        raise ValueError("Claim Extractor canonical Assertion identity 重复")

    assertion_payloads = [asdict(item) for item in assertions]
    coverage_gaps = list(batch.coverage_gaps)
    status = (
        "succeeded"
        if not coverage_gaps
        else "succeeded_with_gaps"
        if assertion_payloads
        else "succeeded_no_relevant_facts"
    )
    response: dict[str, Any] = {
        "contract": ASSERTION_EXTRACTION_CONTRACT_V2,
        "request_id": request.request_id,
        "profile_code": profile.code,
        "status": status,
        "assertions": assertion_payloads,
        "provenance": {
            "provider": batch.provider_code,
            "service_version": SERVICE_VERSION,
            "service_release_sha": service_release_sha,
            "input_fingerprint": input_fingerprint,
            "identity_policy": "server_canonical_assertion_identity:v1",
            "routing_policy": "trusted_request_subject_routing:v1",
        },
    }
    if coverage_gaps:
        response["coverage_gaps"] = coverage_gaps
    if batch.provider_metadata:
        response["runtime_audit"] = dict(batch.provider_metadata)
    response["output_fingerprint"] = _fingerprint(response)

    writes = repository.put(
        request.idempotency_key,
        input_fingerprint,
        response,
    )
    return ClaimExtractionServiceRun(
        response,
        False,
        1,
        batch.model_call_count,
        writes,
    )
