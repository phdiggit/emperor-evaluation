from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Protocol

from emperor_v4.contracts.source import (
    SOURCE_CACHE_CONTRACT_V2,
    SourceCacheRequest,
    SourceRevisionContent,
)
from emperor_v4.domain.source_segmentation import (
    PassageSeed,
    SourceSection,
    WindowPolicy,
    slice_source_section,
)


SERVICE_VERSION = "v4-source-cache-service:v1"
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class SourceCacheIdempotencyConflict(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedSourceSection:
    revision: SourceRevisionContent
    work_identity: str
    edition_identity: str
    source_role: str
    license_or_access_note: str
    section_id: str
    section_heading: str
    document_span_start: int
    seeds: tuple[PassageSeed, ...]
    window_policy: WindowPolicy

    def __post_init__(self) -> None:
        required = (
            self.work_identity,
            self.edition_identity,
            self.source_role,
            self.license_or_access_note,
            self.section_id,
            self.section_heading,
        )
        if not all(required) or not self.seeds:
            raise ValueError("PreparedSourceSection 缺少来源身份、章节或 passage seeds")
        if self.document_span_start < 0:
            raise ValueError("PreparedSourceSection document_span_start 不得为负")


@dataclass(frozen=True, slots=True)
class SourceMaterialBatch:
    sections: tuple[PreparedSourceSection, ...]
    provider_code: str
    network_request_count: int = 0
    errors: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.provider_code or self.network_request_count < 0:
            raise ValueError("SourceMaterialBatch provider/audit 无效")


@dataclass(frozen=True, slots=True)
class CachedSourceCacheResult:
    input_fingerprint: str
    response: Mapping[str, Any]


class SourceMaterialProvider(Protocol):
    def load(self, request: SourceCacheRequest) -> SourceMaterialBatch: ...


class SourceCacheRepository(Protocol):
    def get(self, idempotency_key: str) -> CachedSourceCacheResult | None: ...

    def put(
        self,
        idempotency_key: str,
        input_fingerprint: str,
        response: Mapping[str, Any],
        source_revisions: Mapping[str, SourceRevisionContent],
    ) -> int: ...

    def get_revision(
        self,
        document_cache_id: str,
        content_version: str,
    ) -> SourceRevisionContent | None: ...


@dataclass(frozen=True, slots=True)
class SourceCacheServiceRun:
    response: Mapping[str, Any]
    cache_hit: bool
    provider_call_count: int
    repository_write_count: int
    network_request_count: int


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _fingerprint(value: Any) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def source_cache_input_fingerprint(request: SourceCacheRequest) -> str:
    return _fingerprint(
        {
            "idempotency_key": request.idempotency_key,
            "subject": asdict(request.subject),
            "evaluation_context": request.evaluation_context,
            "source_hints": request.source_hints,
            "required_source_families": request.required_source_families,
            "mode": request.mode,
            "source_policy_version": request.source_policy_version,
        }
    )


def _document_id(item: PreparedSourceSection) -> str:
    identity = (
        item.work_identity,
        item.edition_identity,
        item.revision.title,
        item.revision.revision_ref,
    )
    return "SCD-" + _fingerprint(identity)[:20].upper()


def source_content_version(revision: SourceRevisionContent) -> str:
    return f"revision:{revision.revision_ref}:{revision.content_hash}"


def _document_payload(item: PreparedSourceSection, document_id: str) -> dict[str, Any]:
    return {
        "document_cache_id": document_id,
        "work_identity": item.work_identity,
        "edition_identity": item.edition_identity,
        "title": item.revision.title,
        "url": item.revision.url,
        "source_role": item.source_role,
        "retrieved_at": item.revision.retrieved_at,
        "content_hash": item.revision.content_hash,
        "http_metadata": {
            "source_host": item.revision.source_host,
            "source_document_ref": item.revision.source_document_ref,
            "revision_ref": item.revision.revision_ref,
            "revision_timestamp": item.revision.revision_timestamp,
        },
        "license_or_access_note": item.license_or_access_note,
    }


def _passage_payload(item: Any) -> dict[str, Any]:
    return {
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
        "linked_passages": [asdict(link) for link in item.linked_passages],
        "overlap_group": item.overlap_group,
        "window_policy_version": item.window_policy_version,
    }


def ensure_source_cache(
    request: SourceCacheRequest,
    *,
    provider: SourceMaterialProvider,
    repository: SourceCacheRepository,
    service_release_sha: str,
) -> SourceCacheServiceRun:
    if not _COMMIT_SHA_RE.fullmatch(service_release_sha):
        raise ValueError("service_release_sha 必须是 40 位小写 Git commit SHA")
    input_fingerprint = source_cache_input_fingerprint(request)
    cached = repository.get(request.idempotency_key)
    if cached is not None:
        if cached.input_fingerprint != input_fingerprint:
            raise SourceCacheIdempotencyConflict(
                "同一 Source Cache idempotency_key 对应不同有效输入"
            )
        return SourceCacheServiceRun(
            response=cached.response,
            cache_hit=True,
            provider_call_count=0,
            repository_write_count=0,
            network_request_count=0,
        )

    batch = provider.load(request)
    documents: dict[str, dict[str, Any]] = {}
    source_revisions: dict[str, SourceRevisionContent] = {}
    passages: dict[str, dict[str, Any]] = {}
    observed_families: set[str] = set()
    for item in batch.sections:
        document_id = _document_id(item)
        document = _document_payload(item, document_id)
        previous_document = documents.setdefault(document_id, document)
        if previous_document != document:
            raise ValueError(f"同一 V4 document identity 出现冲突: {document_id}")
        previous_revision = source_revisions.setdefault(document_id, item.revision)
        if previous_revision != item.revision:
            raise ValueError(f"同一 V4 document identity 出现原文冲突: {document_id}")
        observed_families.add(item.source_role)
        section = SourceSection(
            document_cache_id=document_id,
            content_version=source_content_version(item.revision),
            section_id=item.section_id,
            section_heading=item.section_heading,
            raw_text=item.revision.raw_text,
            document_span_start=item.document_span_start,
        )
        for passage in slice_source_section(section, item.seeds, item.window_policy):
            payload = _passage_payload(passage)
            previous_passage = passages.setdefault(passage.passage_cache_id, payload)
            if previous_passage != payload:
                raise ValueError(
                    f"同一 V4 passage identity 出现冲突: {passage.passage_cache_id}"
                )

    missing_families = sorted(
        set(request.required_source_families) - observed_families
    )
    errors = [dict(item) for item in batch.errors]
    status = "succeeded" if not missing_families and not errors else "succeeded_with_warnings"
    coverage = {
        "subject_ref": request.subject.person_or_ruler_ref,
        "required_source_families": sorted(request.required_source_families),
        "observed_source_families": sorted(observed_families),
        "missing_source_families": missing_families,
        "document_count": len(documents),
        "passage_count": len(passages),
    }
    provenance = {
        "provider": batch.provider_code,
        "source_policy_version": request.source_policy_version,
        "request_mode": request.mode,
        "service_version": SERVICE_VERSION,
        "service_release_sha": service_release_sha,
        "network_request_count": batch.network_request_count,
        "database_write_count": 0,
        "model_call_count": 0,
    }
    output_payload = {
        "input_fingerprint": input_fingerprint,
        "documents": sorted(documents.values(), key=lambda row: row["document_cache_id"]),
        "passages": sorted(passages.values(), key=lambda row: row["passage_id"]),
        "coverage": coverage,
        "errors": errors,
        "provenance": provenance,
    }
    response = {
        "request_id": request.request_id,
        "contract": SOURCE_CACHE_CONTRACT_V2,
        "status": status,
        **output_payload,
        "output_fingerprint": _fingerprint(output_payload),
    }
    repository_write_count = repository.put(
        request.idempotency_key,
        input_fingerprint,
        response,
        source_revisions,
    )
    return SourceCacheServiceRun(
        response=response,
        cache_hit=False,
        provider_call_count=1,
        repository_write_count=repository_write_count,
        network_request_count=batch.network_request_count,
    )
