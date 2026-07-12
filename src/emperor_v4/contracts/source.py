from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping


def text_content_hash(text: str) -> str:
    """返回 passage 原文的稳定 SHA-256，不包含可变摘要或数据库 ID。"""

    return sha256(text.encode("utf-8")).hexdigest()


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
class SourcePassage:
    passage_cache_id: str
    document_cache_id: str
    locator: str
    raw_text: str
    context_before: str
    context_after: str
    content_hash: str
    selection_reason: tuple[str, ...]

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
