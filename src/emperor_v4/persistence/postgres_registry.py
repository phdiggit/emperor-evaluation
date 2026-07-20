from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping

from emperor_v4.contracts.episode import (
    AssertionLink,
    EpisodeParticipant,
    HistoricalEpisodePacket,
)
from emperor_v4.persistence.core_registry import CoreRegistryBatch, CoreRegistryWriteResult
from emperor_v4.persistence.canonical_refs import (
    canonical_assertion_id,
    canonical_person_ref,
    canonical_section_id,
)


ADVISORY_LOCK_ID = int.from_bytes(
    sha256(b"emperor-v4-current-fact-registry").digest()[:8], "big", signed=True
)


def _json_value(value: object) -> object:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _payload(value: object) -> dict[str, Any]:
    return _json_value(asdict(value))  # type: ignore[return-value]


def historical_episode_packet_from_payload(
    payload: Mapping[str, Any],
) -> HistoricalEpisodePacket:
    return HistoricalEpisodePacket(
        episode_id=str(payload["episode_id"]),
        episode_type=str(payload["episode_type"]),
        episode_status=str(payload["episode_status"]),
        evaluation_context=str(payload["evaluation_context"]),
        semantic_fingerprint=str(payload["semantic_fingerprint"]),
        time_start=(str(payload["time_start"]) if payload.get("time_start") else None),
        time_end=(str(payload["time_end"]) if payload.get("time_end") else None),
        time_precision=str(payload["time_precision"]),
        locations=tuple(payload.get("locations") or ()),
        participants=tuple(
            EpisodeParticipant(
                person_ref=str(item["person_ref"]),
                role_codes=tuple(item.get("role_codes") or ()),
                role_status=str(item.get("role_status") or "unresolved"),
            )
            for item in payload.get("participants") or ()
        ),
        action=str(payload["action"]),
        responsibility=(
            str(payload["responsibility"]) if payload.get("responsibility") else None
        ),
        outcome=tuple(payload.get("outcome") or ()),
        consequence=tuple(payload.get("consequence") or ()),
        assertion_links=tuple(
            AssertionLink(
                assertion_ref=str(item["assertion_ref"]),
                source_passage_ref=str(item["source_passage_ref"]),
                relation=str(item["relation"]),
                supported_fields=tuple(item.get("supported_fields") or ()),
                evidence_status=str(item.get("evidence_status") or "draft"),
                representative=bool(item.get("representative")),
            )
            for item in payload.get("assertion_links") or ()
        ),
        conflicts=tuple(payload.get("conflicts") or ()),
        uncertainties=tuple(payload.get("uncertainties") or ()),
        completeness=dict(payload.get("completeness") or {}),
        lineage=dict(payload.get("lineage") or {}),
        provenance=dict(payload.get("provenance") or {}),
    )


class PostgresCoreRegistry:
    """Current-only PostgreSQL registry; Git is the history carrier."""

    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("PostgresCoreRegistry 需要显式 DSN")
        self._dsn = dsn

    def apply(self, batch: CoreRegistryBatch) -> CoreRegistryWriteResult:
        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PostgresCoreRegistry 需要 psycopg") from exc

        writes = {
            "source_documents": 0,
            "source_passages": 0,
            "assertions": 0,
            "historical_episodes": 0,
            "episode_participants": 0,
            "episode_assertion_dispositions": 0,
            "historical_outcome_clusters": 0,
            "outcome_cluster_members": 0,
            "outcome_episode_links": 0,
            "rule_evidence_units": 0,
            "rule_evidence_members": 0,
        }
        with psycopg.connect(self._dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (ADVISORY_LOCK_ID,))
                for record in batch.source_documents:
                    document = record.document
                    payload = _payload(document)
                    cursor.execute(
                        """
                        INSERT INTO source_documents (
                            document_id, revision_ref, work_identity, edition_identity,
                            title, canonical_url, source_role, retrieved_at, content_hash,
                            license_or_access_note, payload
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (document_id) DO UPDATE SET
                            revision_ref = EXCLUDED.revision_ref,
                            work_identity = EXCLUDED.work_identity,
                            edition_identity = EXCLUDED.edition_identity,
                            title = EXCLUDED.title,
                            canonical_url = EXCLUDED.canonical_url,
                            source_role = EXCLUDED.source_role,
                            retrieved_at = EXCLUDED.retrieved_at,
                            content_hash = EXCLUDED.content_hash,
                            license_or_access_note = EXCLUDED.license_or_access_note,
                            payload = EXCLUDED.payload,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE source_documents.payload IS DISTINCT FROM EXCLUDED.payload
                           OR source_documents.revision_ref IS DISTINCT FROM EXCLUDED.revision_ref
                        RETURNING 1
                        """,
                        (
                            document.document_cache_id,
                            record.revision_ref,
                            document.work_identity,
                            document.edition_identity,
                            document.title,
                            document.url,
                            document.source_role,
                            document.retrieved_at,
                            document.content_hash,
                            document.license_or_access_note,
                            Jsonb(payload),
                        ),
                    )
                    writes["source_documents"] += int(cursor.fetchone() is not None)
                for passage in batch.source_passages:
                    payload = _payload(passage)
                    cursor.execute(
                        """
                        INSERT INTO source_passages (
                            passage_id, document_id, revision_ref, section_id,
                            section_heading, span_start, span_end, passage_kind,
                            content_hash, payload
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (passage_id) DO UPDATE SET
                            document_id = EXCLUDED.document_id,
                            revision_ref = EXCLUDED.revision_ref,
                            section_id = EXCLUDED.section_id,
                            section_heading = EXCLUDED.section_heading,
                            span_start = EXCLUDED.span_start,
                            span_end = EXCLUDED.span_end,
                            passage_kind = EXCLUDED.passage_kind,
                            content_hash = EXCLUDED.content_hash,
                            payload = EXCLUDED.payload,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE source_passages.payload IS DISTINCT FROM EXCLUDED.payload
                        RETURNING 1
                        """,
                        (
                            passage.passage_cache_id,
                            passage.document_cache_id,
                            str(passage.content_version or ""),
                            canonical_section_id(str(passage.section_id)),
                            passage.section_heading,
                            passage.span_start,
                            passage.span_end,
                            passage.passage_kind,
                            passage.content_hash,
                            Jsonb(payload),
                        ),
                    )
                    writes["source_passages"] += int(cursor.fetchone() is not None)
                for assertion in batch.assertions:
                    payload = _payload(assertion)
                    assertion_id = canonical_assertion_id(assertion.assertion_code)
                    semantic_key = (
                        assertion.passage_support.assertion_semantic_key
                        if assertion.passage_support
                        else assertion.assertion_code
                    )
                    cursor.execute(
                        """
                        INSERT INTO assertions (
                            assertion_id, source_passage_id, assertion_type,
                            assertion_semantic_key, payload
                        ) VALUES (%s,%s,%s,%s,%s)
                        ON CONFLICT (assertion_id) DO UPDATE SET
                            source_passage_id = EXCLUDED.source_passage_id,
                            assertion_type = EXCLUDED.assertion_type,
                            assertion_semantic_key = EXCLUDED.assertion_semantic_key,
                            payload = EXCLUDED.payload,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE assertions.payload IS DISTINCT FROM EXCLUDED.payload
                        RETURNING 1
                        """,
                        (
                            assertion_id,
                            assertion.source_passage_ref,
                            assertion.assertion_type,
                            semantic_key,
                            Jsonb(payload),
                        ),
                    )
                    writes["assertions"] += int(cursor.fetchone() is not None)
                for packet in batch.episodes:
                    for link in packet.assertion_links:
                        cursor.execute(
                            "SELECT source_passage_id FROM assertions WHERE assertion_id = %s",
                            (canonical_assertion_id(link.assertion_ref),),
                        )
                        assertion_row = cursor.fetchone()
                        if assertion_row is None or str(assertion_row[0]) != link.source_passage_ref:
                            raise ValueError("HistoricalEpisode lineage 引用不闭合")
                    anchor = str(
                        batch.episode_identity_anchors.get(packet.episode_id)
                        or packet.episode_id
                    )
                    payload = _payload(packet)
                    input_fingerprint = str(packet.provenance.get("input_hash") or "") or sha256(
                        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    ).hexdigest()
                    cursor.execute(
                        "SELECT episode_id FROM historical_episodes WHERE identity_anchor = %s",
                        (anchor,),
                    )
                    row = cursor.fetchone()
                    if row is not None and row[0] != packet.episode_id:
                        raise ValueError("identity_anchor 已绑定其他 Episode")
                    cursor.execute(
                        "SELECT identity_anchor FROM historical_episodes WHERE episode_id = %s",
                        (packet.episode_id,),
                    )
                    episode_row = cursor.fetchone()
                    if episode_row is not None and str(episode_row[0]) != anchor:
                        raise ValueError("Episode identity_anchor 不得变化")
                    cursor.execute(
                        """
                        INSERT INTO historical_episodes (
                            episode_id, identity_anchor, evaluation_context,
                            semantic_fingerprint, episode_status, input_fingerprint, payload
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (episode_id) DO UPDATE SET
                            evaluation_context = EXCLUDED.evaluation_context,
                            semantic_fingerprint = EXCLUDED.semantic_fingerprint,
                            episode_status = EXCLUDED.episode_status,
                            input_fingerprint = EXCLUDED.input_fingerprint,
                            payload = EXCLUDED.payload,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE historical_episodes.payload IS DISTINCT FROM EXCLUDED.payload
                           OR historical_episodes.identity_anchor IS DISTINCT FROM EXCLUDED.identity_anchor
                        RETURNING 1
                        """,
                        (
                            packet.episode_id,
                            anchor,
                            canonical_person_ref(packet.evaluation_context),
                            packet.semantic_fingerprint,
                            packet.episode_status,
                            input_fingerprint,
                            Jsonb(payload),
                        ),
                    )
                    episode_changed = cursor.fetchone() is not None
                    writes["historical_episodes"] += int(episode_changed)
                    if episode_changed:
                        cursor.execute(
                            "DELETE FROM episode_participants WHERE episode_id = %s",
                            (packet.episode_id,),
                        )
                        writes["episode_participants"] += cursor.rowcount
                        for participant in packet.participants:
                            for role_code in participant.role_codes:
                                cursor.execute(
                                    """
                                    INSERT INTO episode_participants (
                                        episode_id, person_ref, role_code, role_status
                                    ) VALUES (%s,%s,%s,%s)
                                    """,
                                    (
                                        packet.episode_id,
                                        canonical_person_ref(participant.person_ref),
                                        role_code,
                                        participant.role_status,
                                    ),
                                )
                                writes["episode_participants"] += 1
                for disposition in batch.episode_dispositions:
                    cursor.execute(
                        """
                        INSERT INTO episode_assertion_dispositions (
                            episode_id, assertion_id, disposition, reason, follow_up
                        ) VALUES (%s,%s,%s,%s,%s)
                        ON CONFLICT (episode_id, assertion_id, disposition) DO UPDATE SET
                            reason = EXCLUDED.reason,
                            follow_up = EXCLUDED.follow_up
                        WHERE episode_assertion_dispositions.reason IS DISTINCT FROM EXCLUDED.reason
                           OR episode_assertion_dispositions.follow_up IS DISTINCT FROM EXCLUDED.follow_up
                        RETURNING 1
                        """,
                        (
                            disposition.episode_id,
                            canonical_assertion_id(disposition.assertion_ref),
                            disposition.disposition,
                            disposition.reason,
                            disposition.follow_up,
                        ),
                    )
                    writes["episode_assertion_dispositions"] += int(
                        cursor.fetchone() is not None
                    )
                for cluster in batch.outcome_clusters:
                    for episode_ref in cluster.episode_refs:
                        cursor.execute(
                            "SELECT 1 FROM historical_episodes WHERE episode_id = %s",
                            (episode_ref,),
                        )
                        if cursor.fetchone() is None:
                            raise ValueError(
                                "HistoricalOutcomeCluster 引用未知 Episode"
                            )
                    cursor.execute(
                        """
                        INSERT INTO historical_outcome_clusters (
                            outcome_ref, outcome_kind, independent_key, canonical_label,
                            result_status, result_direction, scale_level,
                            semantic_fingerprint, input_fingerprint, acceptance_status,
                            payload
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (outcome_ref) DO UPDATE SET
                            outcome_kind = EXCLUDED.outcome_kind,
                            independent_key = EXCLUDED.independent_key,
                            canonical_label = EXCLUDED.canonical_label,
                            result_status = EXCLUDED.result_status,
                            result_direction = EXCLUDED.result_direction,
                            scale_level = EXCLUDED.scale_level,
                            semantic_fingerprint = EXCLUDED.semantic_fingerprint,
                            input_fingerprint = EXCLUDED.input_fingerprint,
                            acceptance_status = EXCLUDED.acceptance_status,
                            payload = EXCLUDED.payload, updated_at = CURRENT_TIMESTAMP
                        WHERE historical_outcome_clusters.payload IS DISTINCT FROM EXCLUDED.payload
                           OR historical_outcome_clusters.semantic_fingerprint IS DISTINCT FROM EXCLUDED.semantic_fingerprint
                        RETURNING 1
                        """,
                        (
                            cluster.outcome_ref,
                            cluster.outcome_kind,
                            cluster.independent_key,
                            cluster.canonical_label,
                            cluster.result_status,
                            cluster.result_direction,
                            cluster.scale_level,
                            cluster.semantic_fingerprint,
                            cluster.input_fingerprint,
                            cluster.acceptance_status,
                            Jsonb(dict(cluster.payload)),
                        ),
                    )
                    changed = cursor.fetchone() is not None
                    writes["historical_outcome_clusters"] += int(changed)
                    if changed:
                        cursor.execute(
                            "DELETE FROM outcome_cluster_members WHERE outcome_ref = %s",
                            (cluster.outcome_ref,),
                        )
                        writes["outcome_cluster_members"] += cursor.rowcount
                        for member in cluster.members:
                            cursor.execute(
                                "INSERT INTO outcome_cluster_members VALUES (%s,%s,%s,%s,%s)",
                                (
                                    cluster.outcome_ref,
                                    canonical_person_ref(member.actor_ref),
                                    member.actor_kind,
                                    member.role_code,
                                    member.contribution_scope,
                                ),
                            )
                            writes["outcome_cluster_members"] += 1
                        cursor.execute(
                            "DELETE FROM outcome_episode_links WHERE outcome_ref = %s",
                            (cluster.outcome_ref,),
                        )
                        writes["outcome_episode_links"] += cursor.rowcount
                        for episode_ref in cluster.episode_refs:
                            cursor.execute(
                                "INSERT INTO outcome_episode_links VALUES (%s,%s,%s)",
                                (cluster.outcome_ref, episode_ref, "core_result_chain"),
                            )
                            writes["outcome_episode_links"] += 1
                for unit in batch.rule_evidence_units:
                    cursor.execute(
                        """
                        INSERT INTO rule_evidence_units (
                            unit_ref, rule_code, evaluation_context, direction,
                            semantic_fingerprint, status, payload
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (unit_ref) DO UPDATE SET
                            rule_code = EXCLUDED.rule_code,
                            evaluation_context = EXCLUDED.evaluation_context,
                            direction = EXCLUDED.direction,
                            semantic_fingerprint = EXCLUDED.semantic_fingerprint,
                            status = EXCLUDED.status, payload = EXCLUDED.payload,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE rule_evidence_units.payload IS DISTINCT FROM EXCLUDED.payload
                           OR rule_evidence_units.semantic_fingerprint IS DISTINCT FROM EXCLUDED.semantic_fingerprint
                        RETURNING 1
                        """,
                        (unit.unit_ref, unit.rule_code, canonical_person_ref(unit.evaluation_context),
                         unit.direction, unit.semantic_fingerprint, unit.status, Jsonb(dict(unit.payload))),
                    )
                    changed = cursor.fetchone() is not None
                    writes["rule_evidence_units"] += int(changed)
                    if changed:
                        cursor.execute("DELETE FROM rule_evidence_members WHERE unit_ref = %s", (unit.unit_ref,))
                        writes["rule_evidence_members"] += cursor.rowcount
                        for member in unit.members:
                            cursor.execute(
                                "INSERT INTO rule_evidence_members VALUES (%s,%s,%s,%s)",
                                (unit.unit_ref, member.member_ref, member.member_type, member.member_role),
                            )
                            writes["rule_evidence_members"] += 1
        return CoreRegistryWriteResult(writes, sum(writes.values()))

    def active_packets_by_identity(
        self, identity_anchors: tuple[str, ...]
    ) -> Mapping[str, HistoricalEpisodePacket]:
        if not identity_anchors:
            return {}
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PostgresCoreRegistry 需要 psycopg") from exc
        with psycopg.connect(self._dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT identity_anchor, payload FROM historical_episodes "
                    "WHERE identity_anchor = ANY(%s)",
                    (list(identity_anchors),),
                )
                return {
                    str(anchor): historical_episode_packet_from_payload(
                        _json_value(payload)  # type: ignore[arg-type]
                    )
                    for anchor, payload in cursor.fetchall()
                }
