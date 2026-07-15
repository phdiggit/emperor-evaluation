from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.contracts.assertion import AssertionDraft, PassageSupport
from emperor_v4.contracts.episode import HistoricalEpisodePacket
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


SCHEMA_VERSION = "formal-acceptance-core-registry-audit-v1"


def _hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def reusable_prior_first_run(
    *,
    prior_audit: Mapping[str, Any] | None,
    formal_acceptance_sha256: str,
    scored_report_sha256: str,
    superseded_prior_episode_input_hash: str | None = None,
) -> Mapping[str, Any] | None:
    """Return prior first-run evidence only when the complete input pair matches."""
    if prior_audit is None:
        return None
    prior_refs = prior_audit.get("input_refs") or {}
    current_refs = (
        formal_acceptance_sha256,
        scored_report_sha256,
        superseded_prior_episode_input_hash or "",
    )
    recorded_refs = (
        str(prior_refs.get("formal_acceptance_sha256") or ""),
        str(prior_refs.get("scored_report_sha256") or ""),
        str(prior_refs.get("superseded_prior_episode_input_hash") or ""),
    )
    if recorded_refs != current_refs:
        initial_explicit_correction = (
            bool(superseded_prior_episode_input_hash)
            and recorded_refs[2] == ""
        )
        if initial_explicit_correction:
            return None
        raise ValueError(
            "existing persistence audit input hashes do not match current inputs"
        )
    first_run = prior_audit.get("first_run") or {}
    if int(first_run.get("business_write_count", 0)) <= 0:
        return None
    return dict(first_run)


def assertion_from_payload(payload: Mapping[str, Any]) -> AssertionDraft:
    support_payload = payload.get("passage_support")
    support = (
        PassageSupport(
            support_mode=str(support_payload["support_mode"]),
            assertion_semantic_key=str(support_payload["assertion_semantic_key"]),
            supported_fields=tuple(support_payload.get("supported_fields") or ()),
            binding_provenance=dict(
                support_payload.get("binding_provenance") or {}
            ),
        )
        if support_payload
        else None
    )
    return AssertionDraft(
        assertion_code=str(payload["assertion_code"]),
        source_passage_ref=str(payload["source_passage_ref"]),
        assertion_type=str(payload["assertion_type"]),
        subject=str(payload["subject"]),
        predicate=str(payload["predicate"]),
        object=str(payload["object"]),
        time_expression=(
            str(payload["time_expression"])
            if payload.get("time_expression") is not None
            else None
        ),
        location_expression=(
            str(payload["location_expression"])
            if payload.get("location_expression") is not None
            else None
        ),
        qualifiers=dict(payload.get("qualifiers") or {}),
        polarity=str(payload["polarity"]),
        source_attribution=dict(payload.get("source_attribution") or {}),
        candidate_episode_key=(
            str(payload["candidate_episode_key"])
            if payload.get("candidate_episode_key") is not None
            else None
        ),
        confidence=float(payload["confidence"]),
        ambiguity_flags=tuple(payload.get("ambiguity_flags") or ()),
        extraction_provenance=dict(payload.get("extraction_provenance") or {}),
        passage_support=support,
    )


def build_episode_split_supersessions(
    *,
    prior_active_packets: Sequence[HistoricalEpisodePacket],
    new_trace_episodes: Sequence[Mapping[str, Any] | HistoricalEpisodePacket],
    superseded_input_hash: str,
    current_input_version: str,
    current_input_hash: str,
) -> tuple[HistoricalEpisodePacket, ...]:
    """Version prior active Episodes as split after an explicit trace correction."""

    if not superseded_input_hash or not current_input_version or not current_input_hash:
        raise ValueError("episode supersession requires complete versioned input refs")
    new_packets = tuple(
        row
        if isinstance(row, HistoricalEpisodePacket)
        else historical_episode_packet_from_payload(row)
        for row in new_trace_episodes
    )
    if not prior_active_packets or not new_packets:
        raise ValueError("episode supersession requires prior and successor packets")
    new_by_id = {packet.episode_id: packet for packet in new_packets}
    if len(new_by_id) != len(new_packets):
        raise ValueError("successor trace episode ids must be unique")
    successor_ids_by_assertion: dict[str, set[str]] = {}
    for packet in new_packets:
        for link in packet.assertion_links:
            successor_ids_by_assertion.setdefault(link.assertion_ref, set()).add(
                packet.episode_id
            )
    ambiguous_refs = sorted(
        ref for ref, successor_ids in successor_ids_by_assertion.items()
        if len(successor_ids) != 1
    )
    if ambiguous_refs:
        raise ValueError(
            f"assertion refs map to multiple successor episodes: {ambiguous_refs}"
        )

    split_packets: list[HistoricalEpisodePacket] = []
    for prior in prior_active_packets:
        prior_refs = {link.assertion_ref for link in prior.assertion_links}
        if not prior_refs:
            raise ValueError(f"prior episode has no assertion lineage: {prior.episode_id}")
        missing_refs = sorted(
            ref for ref in prior_refs if ref not in successor_ids_by_assertion
        )
        if missing_refs:
            raise ValueError(
                f"prior episode successor mapping does not close: "
                f"{prior.episode_id}/{missing_refs}"
            )
        successor_ids = sorted(
            {
                successor_id
                for ref in prior_refs
                for successor_id in successor_ids_by_assertion[ref]
            }
        )
        if not successor_ids:
            raise ValueError(f"prior episode has no successor: {prior.episode_id}")
        successor_ids_json = json.dumps(
            successor_ids, ensure_ascii=False, separators=(",", ":")
        )
        prior_lineage = dict(prior.lineage)
        already_split = (
            prior.episode_status == "split"
            and prior_lineage.get("superseded_input_hash") == superseded_input_hash
            and prior_lineage.get("successor_episode_ids") == successor_ids_json
            and prior.provenance.get("input_version") == current_input_version
            and prior.provenance.get("input_hash") == current_input_hash
        )
        if already_split:
            split_packets.append(prior)
            continue
        if prior.provenance.get("input_hash") != superseded_input_hash:
            raise ValueError(
                f"prior active episode input hash mismatch: {prior.episode_id}"
            )
        lineage = {
            **prior_lineage,
            "superseded_input_hash": superseded_input_hash,
            "successor_episode_ids": successor_ids_json,
        }
        provenance = {
            **dict(prior.provenance),
            "builder": "formal_acceptance_episode_split_supersession_v1",
            "input_version": current_input_version,
            "input_hash": current_input_hash,
        }
        semantic_version = prior.semantic_version + 1
        fingerprint = _hash(
            {
                "episode_id": prior.episode_id,
                "semantic_version": semantic_version,
                "status": "split",
                "successor_episode_ids": successor_ids,
                "assertion_refs": sorted(prior_refs),
                "current_input_version": current_input_version,
                "current_input_hash": current_input_hash,
            }
        )
        split_packets.append(
            replace(
                prior,
                episode_status="split",
                semantic_version=semantic_version,
                semantic_fingerprint=fingerprint,
                lineage=lineage,
                provenance=provenance,
            )
        )
    return tuple(split_packets)


def _active_episode_packets_for_supersession(
    dsn: str, superseded_input_hash: str
) -> tuple[HistoricalEpisodePacket, ...]:
    import psycopg

    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT version.payload
                FROM historical_episodes AS episode
                JOIN historical_episode_versions AS version
                  ON version.episode_id = episode.episode_id
                 AND version.semantic_version = episode.active_semantic_version
                 AND version.evidence_version = episode.active_evidence_version
                WHERE version.input_hash = %s
                   OR version.payload -> 'lineage' ->> 'superseded_input_hash' = %s
                ORDER BY episode.episode_id
                """,
                (superseded_input_hash, superseded_input_hash),
            )
            packets = tuple(
                historical_episode_packet_from_payload(dict(row[0]))
                for row in cursor.fetchall()
            )
    if not packets:
        raise ValueError(
            "no active prior episode packets match the explicit supersession input hash"
        )
    return packets


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
                    str(payload["retrieved_at"])
                    if payload.get("retrieved_at")
                    else None
                ),
                content_hash=(
                    str(payload["content_hash"])
                    if payload.get("content_hash")
                    else None
                ),
                http_metadata=dict(payload.get("http_metadata") or {}),
                license_or_access_note=(
                    str(payload["license_or_access_note"])
                    if payload.get("license_or_access_note")
                    else None
                ),
            ),
            content_version=content_version,
        )
        for payload, content_version in document_rows
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
                str(payload["overlap_group"])
                if payload.get("overlap_group")
                else None
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
    prior_active_packets: Sequence[HistoricalEpisodePacket] = (),
    superseded_input_hash: str | None = None,
) -> CoreRegistryBatch:
    if not (acceptance_payload.get("declarations") or {}).get(
        "formal_fact_acceptance"
    ):
        raise ValueError("formal fact acceptance is required")
    trace = scored_report.get("assertion_episode_reu_trace") or {}
    if not trace.get("formal_acceptance_performed"):
        raise ValueError("scored report does not contain a formal acceptance trace")
    assertions = tuple(
        assertion_from_payload(row)
        for unit in acceptance_payload.get("units") or ()
        for row in unit.get("assertion_drafts") or ()
    )
    if len(assertions) != int(
        (acceptance_payload.get("summary") or {}).get("assertion_count", -1)
    ):
        raise ValueError("formal assertion count mismatch")
    passage_refs = sorted({row.source_passage_ref for row in assertions})
    source_documents, source_passages = _source_records(dsn, passage_refs)
    new_episodes = tuple(
        historical_episode_packet_from_payload(row)
        for row in trace.get("episodes") or ()
    )
    if bool(prior_active_packets) != bool(superseded_input_hash):
        raise ValueError(
            "prior active packets and superseded input hash must be supplied together"
        )
    split_packets = (
        build_episode_split_supersessions(
            prior_active_packets=prior_active_packets,
            new_trace_episodes=new_episodes,
            superseded_input_hash=str(superseded_input_hash),
            current_input_version=str(
                acceptance_payload.get("schema_version") or "unknown"
            ),
            current_input_hash=str(acceptance_payload.get("report_sha256") or ""),
        )
        if prior_active_packets
        else ()
    )
    episodes = tuple(split_packets) + new_episodes
    split_ids = {packet.episode_id for packet in split_packets}
    dispositions = tuple(
        EpisodeDispositionRecord(
            episode_id=episode.episode_id,
            semantic_version=episode.semantic_version,
            evidence_version=episode.evidence_version,
            assertion_ref=link.assertion_ref,
            disposition=(
                "core_of_episode" if link.representative else "context_for_episode"
            ),
            reason=(
                "formal acceptance split supersession lineage"
                if episode.episode_id in split_ids
                else "formal acceptance trace lineage"
            ),
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
    parser = argparse.ArgumentParser(description="Persist a formal acceptance trace")
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--scored-report", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_V4_DSN")
    parser.add_argument("--supersede-prior-episode-input-hash")
    args = parser.parse_args()
    from dotenv import load_dotenv

    load_dotenv()
    dsn = os.environ.get(args.dsn_env, "")
    if not dsn:
        raise ValueError(f"missing DSN environment variable: {args.dsn_env}")
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    acceptance = load(args.acceptance)
    scored = load(args.scored_report)
    prior_audit = load(args.audit_output) if args.audit_output.exists() else None
    prior_first_run = reusable_prior_first_run(
        prior_audit=prior_audit,
        formal_acceptance_sha256=str(acceptance.get("report_sha256") or ""),
        scored_report_sha256=str(scored.get("report_sha256") or ""),
        superseded_prior_episode_input_hash=(
            args.supersede_prior_episode_input_hash
        ),
    )
    prior_packets = (
        _active_episode_packets_for_supersession(
            dsn, args.supersede_prior_episode_input_hash
        )
        if args.supersede_prior_episode_input_hash
        else ()
    )
    batch = build_core_registry_batch(
        dsn=dsn,
        acceptance_payload=acceptance,
        scored_report=scored,
        prior_active_packets=prior_packets,
        superseded_input_hash=args.supersede_prior_episode_input_hash,
    )
    registry = PostgresCoreRegistry(dsn)
    first = registry.apply(batch)
    rerun = registry.apply(batch)
    initial_write = prior_first_run or asdict(first)
    audit = {
        "schema_version": SCHEMA_VERSION,
        "status": "formal_acceptance_persisted_idempotent",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_refs": {
            "formal_acceptance_sha256": acceptance.get("report_sha256"),
            "scored_report_sha256": scored.get("report_sha256"),
            "superseded_prior_episode_input_hash": (
                args.supersede_prior_episode_input_hash
            ),
        },
        "batch_counts": {
            "source_documents": len(batch.source_documents),
            "source_passages": len(batch.source_passages),
            "assertions": len(batch.assertions),
            "historical_episodes": len(batch.episodes),
            "episode_assertion_dispositions": len(batch.episode_dispositions),
            "split_superseded_episode_count": len(prior_packets),
        },
        "first_run": initial_write,
        "verification_run": asdict(first),
        "idempotent_rerun": asdict(rerun),
        "declarations": {
            "model_call_count": 0,
            "score_or_ranking_write": False,
            "v3_database_write": False,
        },
    }
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
