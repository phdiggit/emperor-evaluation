from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping


SOURCE_CACHE_CONTRACT_V1 = "source-cache-contract-v1"
SOURCE_CACHE_CONTRACT_V2 = "source-cache-contract-v2"
SOURCE_CACHE_REQUEST_MODES = frozenset({"ensure", "supplement", "refresh"})
PASSAGE_KINDS = frozenset({"atomic", "context", "navigation_noise"})
PASSAGE_LINK_RELATIONS = frozenset(
    {"antecedent", "continuation", "responsibility", "outcome"}
)


def text_content_hash(text: str) -> str:
    """返回 passage 原文的稳定 SHA-256，不包含可变摘要或数据库 ID。"""

    return sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceCacheSubject:
    person_or_ruler_ref: str
    canonical_name: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.person_or_ruler_ref or not self.canonical_name:
            raise ValueError("SourceCacheSubject 必须声明稳定引用和规范名")
        if any(not item for item in self.aliases):
            raise ValueError("SourceCacheSubject aliases 不得包含空值")


@dataclass(frozen=True, slots=True)
class SourceCacheRequest:
    request_id: str
    idempotency_key: str
    subject: SourceCacheSubject
    evaluation_context: Mapping[str, Any]
    source_hints: tuple[str, ...]
    required_source_families: tuple[str, ...]
    mode: str
    source_policy_version: str
    requested_at: str

    def __post_init__(self) -> None:
        required = {
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "source_policy_version": self.source_policy_version,
            "requested_at": self.requested_at,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError("SourceCacheRequest 缺少字段: " + ", ".join(missing))
        if self.mode not in SOURCE_CACHE_REQUEST_MODES:
            raise ValueError(f"未知 Source Cache mode: {self.mode}")
        if any(not item for item in self.source_hints):
            raise ValueError("SourceCacheRequest source_hints 不得包含空值")
        if any(not item for item in self.required_source_families):
            raise ValueError("SourceCacheRequest required_source_families 不得包含空值")


@dataclass(frozen=True, slots=True)
class SourceRevisionContent:
    source_host: str
    source_document_ref: str
    title: str
    url: str
    revision_ref: str
    revision_timestamp: str
    retrieved_at: str
    raw_text: str
    content_hash: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.source_host,
                self.source_document_ref,
                self.title,
                self.url,
                self.revision_ref,
                self.revision_timestamp,
                self.retrieved_at,
                self.raw_text,
                self.content_hash,
            )
        ):
            raise ValueError("SourceRevisionContent 缺少来源、版本或原文")
        if self.content_hash != text_content_hash(self.raw_text):
            raise ValueError("SourceRevisionContent content_hash 与 raw_text 不一致")


@dataclass(frozen=True, slots=True)
class ContractGap:
    object_type: str
    object_ref: str
    missing_fields: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class SourceDocumentDraft:
    """适配阶段的文献草案。

    旧服务缺少的字段保留为 ``None``，由 ``missing_required_fields`` 暴露，
    不以适配器生成的 fingerprint 冒充原始文献 content hash。
    """

    document_cache_id: str
    work_identity: str
    edition_identity: str | None
    title: str
    url: str | None
    source_role: str
    retrieved_at: str | None
    content_hash: str | None
    http_metadata: Mapping[str, Any] = field(default_factory=dict)
    license_or_access_note: str | None = None

    def missing_required_fields(self) -> tuple[str, ...]:
        values = {
            "document_cache_id": self.document_cache_id,
            "work_identity": self.work_identity,
            "edition_identity": self.edition_identity,
            "title": self.title,
            "url": self.url,
            "source_role": self.source_role,
            "retrieved_at": self.retrieved_at,
            "content_hash": self.content_hash,
            "license_or_access_note": self.license_or_access_note,
        }
        return tuple(name for name, value in values.items() if value in (None, ""))


@dataclass(frozen=True, slots=True)
class LinkedPassageRef:
    passage_ref: str
    relation: str

    def __post_init__(self) -> None:
        if not self.passage_ref:
            raise ValueError("LinkedPassageRef 必须声明 passage_ref")
        if self.relation not in PASSAGE_LINK_RELATIONS:
            raise ValueError(f"未知 linked passage relation: {self.relation}")


@dataclass(frozen=True, slots=True)
class SourcePassage:
    passage_cache_id: str
    document_cache_id: str
    locator: str
    raw_text: str
    context_before: str
    context_after: str
    content_hash: str
    selection_reason: tuple[str, ...]
    contract_version: str = SOURCE_CACHE_CONTRACT_V1
    content_version: str | None = None
    section_id: str | None = None
    section_heading: str | None = None
    span_start: int | None = None
    span_end: int | None = None
    passage_kind: str | None = None
    linked_passages: tuple[LinkedPassageRef, ...] = ()
    overlap_group: str | None = None
    window_policy_version: str | None = None

    def __post_init__(self) -> None:
        required = {
            "passage_cache_id": self.passage_cache_id,
            "document_cache_id": self.document_cache_id,
            "locator": self.locator,
            "raw_text": self.raw_text,
            "content_hash": self.content_hash,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"SourcePassage 缺少必填字段: {', '.join(missing)}")
        if self.content_hash != text_content_hash(self.raw_text):
            raise ValueError("SourcePassage content_hash 与 raw_text 不一致")
        if self.contract_version not in {
            SOURCE_CACHE_CONTRACT_V1,
            SOURCE_CACHE_CONTRACT_V2,
        }:
            raise ValueError(f"未知 SourcePassage contract: {self.contract_version}")
        if self.contract_version == SOURCE_CACHE_CONTRACT_V2:
            required_v2 = {
                "content_version": self.content_version,
                "section_id": self.section_id,
                "section_heading": self.section_heading,
                "span_start": self.span_start,
                "span_end": self.span_end,
                "passage_kind": self.passage_kind,
                "window_policy_version": self.window_policy_version,
            }
            missing_v2 = [
                name for name, value in required_v2.items() if value in (None, "")
            ]
            if missing_v2:
                raise ValueError(
                    "SourcePassage v2 缺少必填字段: " + ", ".join(missing_v2)
                )
            if self.passage_kind not in PASSAGE_KINDS:
                raise ValueError(f"未知 passage_kind: {self.passage_kind}")
            if (
                not isinstance(self.span_start, int)
                or not isinstance(self.span_end, int)
                or self.span_start < 0
                or self.span_end <= self.span_start
            ):
                raise ValueError("SourcePassage v2 span 必须是有效半开区间")
            if self.span_end - self.span_start != len(self.raw_text):
                raise ValueError("SourcePassage v2 span 长度与 raw_text 不一致")
            link_keys = [
                (item.passage_ref, item.relation) for item in self.linked_passages
            ]
            if len(link_keys) != len(set(link_keys)):
                raise ValueError("SourcePassage v2 linked_passages 不得重复")
            if any(item.passage_ref == self.passage_cache_id for item in self.linked_passages):
                raise ValueError("SourcePassage v2 不得链接自身")
            if self.passage_kind == "navigation_noise" and self.linked_passages:
                raise ValueError("navigation_noise 不得建立历史证据链接")

    @property
    def is_contract_v2(self) -> bool:
        return self.contract_version == SOURCE_CACHE_CONTRACT_V2
