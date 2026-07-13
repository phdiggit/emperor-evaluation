from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from emperor_v4.contracts.source import (
    ContractGap,
    SOURCE_CACHE_CONTRACT_V2,
    LinkedPassageRef,
    SourceDocumentDraft,
    SourcePassage,
    text_content_hash,
)


@dataclass(frozen=True, slots=True)
class AdaptedSourceCache:
    documents: tuple[SourceDocumentDraft, ...]
    passages: tuple[SourcePassage, ...]
    contract_gaps: tuple[ContractGap, ...]


def adapt_source_cache_v2_response(
    response: Mapping[str, Any],
) -> AdaptedSourceCache:
    if response.get("contract") != SOURCE_CACHE_CONTRACT_V2:
        raise ValueError("不是 source-cache-contract-v2 响应")
    documents = []
    document_ids = set()
    for item in response.get("documents") or ():
        document = SourceDocumentDraft(
            document_cache_id=str(item.get("document_cache_id") or ""),
            work_identity=str(item.get("work_identity") or ""),
            edition_identity=(
                str(item["edition_identity"])
                if item.get("edition_identity")
                else None
            ),
            title=str(item.get("title") or ""),
            url=(str(item["url"]) if item.get("url") else None),
            source_role=str(item.get("source_role") or ""),
            retrieved_at=(
                str(item["retrieved_at"]) if item.get("retrieved_at") else None
            ),
            content_hash=(
                str(item["content_hash"]) if item.get("content_hash") else None
            ),
            http_metadata=item.get("http_metadata") or {},
            license_or_access_note=(
                str(item["license_or_access_note"])
                if item.get("license_or_access_note")
                else None
            ),
        )
        if document.document_cache_id in document_ids:
            raise ValueError(f"v2 document id 重复: {document.document_cache_id}")
        document_ids.add(document.document_cache_id)
        if missing := document.missing_required_fields():
            raise ValueError(f"SourceDocument v2 缺少字段: {missing}")
        documents.append(document)

    passages = []
    passage_ids = set()
    for item in response.get("passages") or ():
        raw_text = str(item.get("raw_text") or "")
        passage = SourcePassage(
            passage_cache_id=str(item.get("passage_id") or ""),
            document_cache_id=str(item.get("document_id") or ""),
            locator=str(item.get("locator") or ""),
            raw_text=raw_text,
            context_before=str(item.get("context_before") or ""),
            context_after=str(item.get("context_after") or ""),
            content_hash=str(item.get("content_hash") or ""),
            selection_reason=tuple(item.get("selection_reason") or ()),
            contract_version=SOURCE_CACHE_CONTRACT_V2,
            content_version=str(item.get("content_version") or ""),
            section_id=str(item.get("section_id") or ""),
            section_heading=str(item.get("section_heading") or ""),
            span_start=item.get("span_start"),
            span_end=item.get("span_end"),
            passage_kind=str(item.get("passage_kind") or ""),
            linked_passages=tuple(
                LinkedPassageRef(
                    passage_ref=str(link.get("passage_ref") or ""),
                    relation=str(link.get("relation") or ""),
                )
                for link in item.get("linked_passages") or ()
            ),
            overlap_group=(
                str(item["overlap_group"]) if item.get("overlap_group") else None
            ),
            window_policy_version=str(item.get("window_policy_version") or ""),
        )
        if passage.passage_cache_id in passage_ids:
            raise ValueError(f"v2 passage id 重复: {passage.passage_cache_id}")
        passage_ids.add(passage.passage_cache_id)
        if passage.document_cache_id not in document_ids:
            raise ValueError(
                f"v2 passage 引用了未知 document: {passage.document_cache_id}"
            )
        passages.append(passage)

    by_id = {item.passage_cache_id: item for item in passages}
    for passage in passages:
        for link in passage.linked_passages:
            target = by_id.get(link.passage_ref)
            if target is None:
                raise ValueError(f"linked passage 不存在: {link.passage_ref}")
            if (
                target.document_cache_id != passage.document_cache_id
                or target.content_version != passage.content_version
            ):
                raise ValueError("linked passages 必须来自同一文档 content version")
    return AdaptedSourceCache(
        documents=tuple(documents),
        passages=tuple(passages),
        contract_gaps=(),
    )


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
