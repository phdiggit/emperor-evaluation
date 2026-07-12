from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from emperor_v4.contracts.source import (
    ContractGap,
    SourceDocumentDraft,
    SourcePassage,
    text_content_hash,
)


@dataclass(frozen=True, slots=True)
class AdaptedSourceCache:
    documents: tuple[SourceDocumentDraft, ...]
    passages: tuple[SourcePassage, ...]
    contract_gaps: tuple[ContractGap, ...]


def _selection_reason(item: Mapping[str, Any]) -> tuple[str, ...]:
    reasons: list[str] = []
    for key in (
        "matched_aliases",
        "matched_outcome_terms",
        "matched_role_families",
        "matched_rule_terms",
    ):
        reasons.extend(f"{key}:{value}" for value in item.get(key, []) if value)
    return tuple(reasons)


def adapt_source_cache_snapshot(snapshot: Mapping[str, Any]) -> AdaptedSourceCache:
    if snapshot.get("legacy_contract") != "retrieval-v3-object-source-claim-plan":
        raise ValueError("不是受支持的 V3 source cache fixture")

    documents: dict[str, SourceDocumentDraft] = {}
    passages: dict[str, SourcePassage] = {}
    gaps: list[ContractGap] = []

    for person in snapshot.get("people", []):
        payload = person.get("payload", {})
        for item in payload.get("source_documents", []):
            document_id = item.get("document_code", "")
            title = item.get("title", "")
            document = SourceDocumentDraft(
                document_cache_id=document_id,
                work_identity=title.split("/", 1)[0],
                edition_identity=None,
                title=title,
                url=item.get("url") or None,
                source_role=item.get("source_role", ""),
                retrieved_at=None,
                content_hash=None,
                http_metadata={},
                license_or_access_note=None,
            )
            previous = documents.setdefault(document_id, document)
            if previous != document:
                raise ValueError(f"同一 document_code 出现冲突内容: {document_id}")

        for item in payload.get("candidate_slices", []):
            raw_text = item.get("text", "")
            passage = SourcePassage(
                passage_cache_id=item.get("slice_code", ""),
                document_cache_id=item.get("document_code", ""),
                locator=item.get("locator", ""),
                raw_text=raw_text,
                context_before="",
                context_after="",
                content_hash=text_content_hash(raw_text),
                selection_reason=_selection_reason(item),
            )
            previous = passages.setdefault(passage.passage_cache_id, passage)
            if previous != passage:
                raise ValueError(
                    f"同一 slice_code 出现冲突内容: {passage.passage_cache_id}"
                )

    for document in documents.values():
        missing = document.missing_required_fields()
        if missing:
            gaps.append(
                ContractGap(
                    object_type="SourceDocument",
                    object_ref=document.document_cache_id,
                    missing_fields=missing,
                    reason="legacy_v3_output_did_not_export_required_source_metadata",
                )
            )

    unknown_documents = sorted(
        {
            passage.document_cache_id
            for passage in passages.values()
            if passage.document_cache_id not in documents
        }
    )
    if unknown_documents:
        raise ValueError(f"passage 引用了未知 document: {', '.join(unknown_documents)}")

    return AdaptedSourceCache(
        documents=tuple(documents.values()),
        passages=tuple(passages.values()),
        contract_gaps=tuple(gaps),
    )
