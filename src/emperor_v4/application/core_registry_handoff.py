from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from typing import Any, Mapping

from emperor_v4.contracts.source import (
    LinkedPassageRef,
    SourceDocumentDraft,
    SourcePassage,
)
from emperor_v4.domain.boundary import materialize_boundary_review, plan_boundary_reviews
from emperor_v4.evaluation.blind_holdout import assertions_from_blind_input
from emperor_v4.evaluation.boundary_review import review_result_from_payload
from emperor_v4.evaluation.graph_holdout import validate_boundary_review_freeze
from emperor_v4.persistence import (
    BoundaryReviewCacheEntry,
    CoreRegistryBatch,
    EpisodeDispositionRecord,
    ReviewArtifactRecord,
    SourceDocumentRecord,
)


def _canonical_hash(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def build_g3a_core_registry_batch(
    blind_input: Mapping[str, Any], boundary_review: Mapping[str, Any]
) -> CoreRegistryBatch:
    """把冻结的 Source v2/Boundary proposal 转为 G3A Core 批次，不携带 Relation。"""

    validate_boundary_review_freeze(blind_input, boundary_review)
    input_hash = _canonical_hash(blind_input)
    dataset_code = str(blind_input.get("dataset_code") or "")
    if not dataset_code:
        raise ValueError("G3A handoff 需要 dataset_code")

    documents_by_id = {
        str(row["document_cache_id"]): row
        for row in blind_input.get("source_documents") or ()
    }
    passages = tuple(_source_passage(row) for row in blind_input["source_passages"])
    document_versions = {
        (passage.document_cache_id, str(passage.content_version))
        for passage in passages
    }
    source_documents = []
    for document_id, content_version in sorted(document_versions):
        row = documents_by_id.get(document_id)
        if row is None:
            raise ValueError("SourcePassage 引用了输入中不存在的 SourceDocument")
        source_documents.append(
            SourceDocumentRecord(
                document=SourceDocumentDraft(
                    document_cache_id=document_id,
                    work_identity=str(row.get("work_identity") or ""),
                    edition_identity=(
                        str(row["edition_identity"])
                        if row.get("edition_identity")
                        else None
                    ),
                    title=str(row.get("title") or ""),
                    url=str(row["url"]) if row.get("url") else None,
                    source_role=str(row.get("source_role") or ""),
                    retrieved_at=(
                        str(row["retrieved_at"]) if row.get("retrieved_at") else None
                    ),
                    content_hash=(
                        str(row["content_hash"]) if row.get("content_hash") else None
                    ),
                    http_metadata=row.get("http_metadata") or {},
                    license_or_access_note=(
                        str(row["license_or_access_note"])
                        if row.get("license_or_access_note")
                        else None
                    ),
                ),
                content_version=content_version,
            )
        )

    assertions = assertions_from_blind_input(blind_input)
    plan = plan_boundary_reviews(assertions)
    units = {item.review_unit_code: item for item in plan.review_units}
    clusters = {item.proposition_code: item for item in plan.proposition_clusters}
    review_rows = tuple(boundary_review.get("review_results") or ())
    reviews = tuple(review_result_from_payload(row) for row in review_rows)
    if {review.review_unit_ref for review in reviews} != set(units):
        raise ValueError("G3A handoff 的 Boundary review 未覆盖全部 ReviewUnit")

    packets = []
    dispositions = []
    artifacts = []
    cache_entries = []
    identity_anchors = {}
    for review, review_row in zip(reviews, review_rows, strict=True):
        unit = units[review.review_unit_ref]
        result = materialize_boundary_review(
            assertions,
            review,
            review_unit=unit,
            proposition_clusters=tuple(
                clusters[ref] for ref in unit.proposition_cluster_refs
            ),
        )
        packet_by_core = {
            frozenset(link.assertion_ref for link in packet.assertion_links): packet
            for packet in result.episode_packets
        }
        local_to_packet = {
            group.local_episode_code: packet_by_core[frozenset(group.core_assertion_refs)]
            for group in review.episode_groups
        }
        hydrated_packets = {
            packet.episode_id: replace(
                packet,
                provenance={
                    **packet.provenance,
                    "input_version": dataset_code,
                    "input_hash": input_hash,
                },
            )
            for packet in result.episode_packets
        }
        packets.extend(hydrated_packets.values())
        for group in review.episode_groups:
            packet = hydrated_packets[local_to_packet[group.local_episode_code].episode_id]
            if not group.atomic_event_key:
                raise ValueError("G3B handoff 需要稳定 atomic_event_key")
            identity_anchor = _canonical_hash(
                {
                    "evaluation_context": packet.evaluation_context,
                    "atomic_event_key": group.atomic_event_key,
                }
            )
            if identity_anchor in identity_anchors.values():
                raise ValueError("G3B handoff 生成重复 identity_anchor")
            identity_anchors[packet.episode_id] = identity_anchor

        for disposition in review.assertion_dispositions:
            if disposition.disposition not in {
                "core_of_episode",
                "context_for_episode",
            }:
                continue
            for local_ref in disposition.episode_refs:
                packet = hydrated_packets[local_to_packet[local_ref].episode_id]
                dispositions.append(
                    EpisodeDispositionRecord(
                        episode_id=packet.episode_id,
                        semantic_version=packet.semantic_version,
                        evidence_version=packet.evidence_version,
                        assertion_ref=disposition.assertion_ref,
                        disposition=disposition.disposition,
                        reason=disposition.reason,
                        follow_up=disposition.follow_up,
                    )
                )

        artifact_hash = _canonical_hash(
            {
                "dataset_code": dataset_code,
                "review_unit_ref": review.review_unit_ref,
                "review": review_row,
            }
        )
        artifact = ReviewArtifactRecord(
            artifact_id=f"BRA-{artifact_hash[:20].upper()}",
            artifact_type="boundary_review",
            status="proposed",
            basis_hash=input_hash,
            policy_version=review.boundary_policy_version,
            schema_version=review.output_schema_version,
            payload={"dataset_code": dataset_code, "review": review_row},
        )
        artifacts.append(artifact)
        cache_entries.append(
            BoundaryReviewCacheEntry(
                cache_key=review.review_unit_cache_key,
                input_hash=input_hash,
                policy_version=review.boundary_policy_version,
                schema_version=review.output_schema_version,
                model_family=review.model_family,
                artifact_id=artifact.artifact_id,
            )
        )

    if len({packet.episode_id for packet in packets}) != len(packets):
        raise ValueError("G3A handoff 生成重复 Episode ID")
    return CoreRegistryBatch(
        source_documents=tuple(source_documents),
        source_passages=passages,
        assertions=assertions,
        episodes=tuple(packets),
        episode_dispositions=tuple(dispositions),
        review_artifacts=tuple(artifacts),
        boundary_cache_entries=tuple(cache_entries),
        episode_identity_anchors=identity_anchors,
    )


def _source_passage(row: Mapping[str, Any]) -> SourcePassage:
    return SourcePassage(
        passage_cache_id=str(row.get("passage_code") or ""),
        document_cache_id=str(row.get("document_code") or ""),
        locator=str(row.get("locator") or ""),
        raw_text=str(row.get("raw_text") or ""),
        context_before=str(row.get("context_before") or ""),
        context_after=str(row.get("context_after") or ""),
        content_hash=str(row.get("content_hash") or ""),
        selection_reason=tuple(row.get("selection_reason") or ()),
        contract_version=str(row.get("contract_version") or ""),
        content_version=(
            str(row["content_version"]) if row.get("content_version") else None
        ),
        section_id=str(row["section_id"]) if row.get("section_id") else None,
        section_heading=(
            str(row["section_heading"]) if row.get("section_heading") else None
        ),
        span_start=(int(row["span_start"]) if row.get("span_start") is not None else None),
        span_end=(int(row["span_end"]) if row.get("span_end") is not None else None),
        passage_kind=(
            str(row["passage_kind"]) if row.get("passage_kind") else None
        ),
        linked_passages=tuple(
            LinkedPassageRef(
                passage_ref=str(item.get("passage_ref") or ""),
                relation=str(item.get("relation") or ""),
            )
            for item in row.get("linked_passages") or ()
        ),
        overlap_group=(
            str(row["overlap_group"]) if row.get("overlap_group") else None
        ),
        window_policy_version=(
            str(row["window_policy_version"])
            if row.get("window_policy_version")
            else None
        ),
    )
