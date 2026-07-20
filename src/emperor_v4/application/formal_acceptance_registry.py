from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.contracts.assertion import assertion_draft_from_payload
from emperor_v4.contracts.source import (
    LinkedPassageRef,
    SOURCE_CACHE_CONTRACT_V2,
    SourceDocumentDraft,
    SourcePassage,
)
from emperor_v4.persistence.core_registry import (
    CoreRegistryBatch,
    EpisodeDispositionRecord,
    SourceDocumentRecord,
)
from emperor_v4.persistence.postgres_registry import (
    PostgresCoreRegistry,
    historical_episode_packet_from_payload,
)


def _source_records(
    dsn: str, passage_refs: Sequence[str]
) -> tuple[tuple[SourceDocumentRecord, ...], tuple[SourcePassage, ...]]:
    import psycopg

    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload FROM v4_source_cache.passages "
                "WHERE passage_id = ANY(%s) ORDER BY passage_id",
                (list(passage_refs),),
            )
            passage_payloads = [dict(row[0]) for row in cursor.fetchall()]
            found = {str(row["passage_id"]) for row in passage_payloads}
            missing = sorted(set(passage_refs) - found)
            if missing:
                raise ValueError(f"Source Cache missing passage refs: {missing}")
            document_keys = sorted(
                {
                    (str(row["document_id"]), str(row["content_version"]))
                    for row in passage_payloads
                }
            )
            cursor.execute(
                "SELECT payload, content_version FROM v4_source_cache.document_revisions "
                "WHERE (document_cache_id, content_version) IN "
                "(SELECT * FROM unnest(%s::text[], %s::text[])) "
                "ORDER BY document_cache_id, content_version",
                (
                    [key[0] for key in document_keys],
                    [key[1] for key in document_keys],
                ),
            )
            document_rows = [(dict(row[0]), str(row[1])) for row in cursor.fetchall()]
    if len(document_rows) != len(document_keys):
        raise ValueError("Source Cache document revisions do not close")
    documents = tuple(
        SourceDocumentRecord(
            document=SourceDocumentDraft(
                document_cache_id=str(payload["document_cache_id"]),
                work_identity=str(payload["work_identity"]),
                edition_identity=(
                    str(payload["edition_identity"])
                    if payload.get("edition_identity") is not None
                    else None
                ),
                title=str(payload["title"]),
                url=str(payload["url"]) if payload.get("url") else None,
                source_role=str(payload["source_role"]),
                retrieved_at=(
                    str(payload["retrieved_at"]) if payload.get("retrieved_at") else None
                ),
                content_hash=(
                    str(payload["content_hash"]) if payload.get("content_hash") else None
                ),
                http_metadata=dict(payload.get("http_metadata") or {}),
                license_or_access_note=(
                    str(payload["license_or_access_note"])
                    if payload.get("license_or_access_note")
                    else None
                ),
            ),
            revision_ref=revision_ref,
        )
        for payload, revision_ref in document_rows
    )
    passages = tuple(
        SourcePassage(
            passage_cache_id=str(payload["passage_id"]),
            document_cache_id=str(payload["document_id"]),
            locator=str(payload["locator"]),
            raw_text=str(payload["raw_text"]),
            context_before=str(payload.get("context_before") or ""),
            context_after=str(payload.get("context_after") or ""),
            content_hash=str(payload["content_hash"]),
            selection_reason=tuple(payload.get("selection_reason") or ()),
            contract_version=SOURCE_CACHE_CONTRACT_V2,
            content_version=str(payload["content_version"]),
            section_id=str(payload["section_id"]),
            section_heading=str(payload["section_heading"]),
            span_start=int(payload["span_start"]),
            span_end=int(payload["span_end"]),
            passage_kind=str(payload["passage_kind"]),
            linked_passages=tuple(
                LinkedPassageRef(
                    passage_ref=str(item["passage_ref"]),
                    relation=str(item["relation"]),
                )
                for item in payload.get("linked_passages") or ()
            ),
            overlap_group=(
                str(payload["overlap_group"]) if payload.get("overlap_group") else None
            ),
            window_policy_version=str(payload["window_policy_version"]),
        )
        for payload in passage_payloads
    )
    return documents, passages


def build_core_registry_batch(
    *,
    dsn: str,
    acceptance_payload: Mapping[str, Any],
    scored_report: Mapping[str, Any],
) -> CoreRegistryBatch:
    if not (acceptance_payload.get("declarations") or {}).get(
        "formal_fact_acceptance"
    ):
        raise ValueError("formal fact acceptance is required")
    trace = scored_report.get("assertion_episode_reu_trace") or {}
    if not trace.get("formal_acceptance_performed"):
        raise ValueError("scored report does not contain a formal acceptance trace")
    assertions = tuple(
        assertion_draft_from_payload(row)
        for unit in acceptance_payload.get("units") or ()
        for row in unit.get("assertion_drafts") or ()
    )
    passage_refs = sorted({row.source_passage_ref for row in assertions})
    source_documents, source_passages = _source_records(dsn, passage_refs)
    episodes = tuple(
        historical_episode_packet_from_payload(row)
        for row in trace.get("episodes") or ()
    )
    dispositions = tuple(
        EpisodeDispositionRecord(
            episode_id=episode.episode_id,
            assertion_ref=link.assertion_ref,
            disposition=(
                "core_of_episode" if link.representative else "context_for_episode"
            ),
            reason="formal acceptance trace lineage",
        )
        for episode in episodes
        for link in episode.assertion_links
    )
    return CoreRegistryBatch(
        source_documents=source_documents,
        source_passages=source_passages,
        assertions=assertions,
        episodes=episodes,
        episode_dispositions=dispositions,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist current formal acceptance facts")
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--scored-report", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_V4_DSN")
    args = parser.parse_args()
    from dotenv import load_dotenv

    load_dotenv()
    dsn = os.environ.get(args.dsn_env, "")
    if not dsn:
        raise ValueError(f"missing DSN environment variable: {args.dsn_env}")
    acceptance = json.loads(args.acceptance.read_text(encoding="utf-8"))
    scored = json.loads(args.scored_report.read_text(encoding="utf-8"))
    batch = build_core_registry_batch(
        dsn=dsn,
        acceptance_payload=acceptance,
        scored_report=scored,
    )
    registry = PostgresCoreRegistry(dsn)
    first = registry.apply(batch)
    rerun = registry.apply(batch)
    audit = {
        "status": "current_facts_persisted_idempotent",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_fingerprint": str(acceptance.get("report_sha256") or ""),
        "first_run": asdict(first),
        "idempotent_rerun": asdict(rerun),
        "formal_score_write": False,
    }
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
