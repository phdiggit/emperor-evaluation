from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.episode import (
    AssertionLink,
    EpisodeParticipant,
    HistoricalEpisodePacket,
)
from emperor_v4.domain.versioning import evidence_payload_hash, semantic_payload_hash
from emperor_v4.persistence.core_registry import (
    CoreRegistryBatch,
    CoreRegistryWriteResult,
    ReviewArtifactRecord,
)
from emperor_v4.persistence.postgres_schema_governance import (
    canonical_assertion_id,
    canonical_person_ref,
    canonical_section_id,
)


ADVISORY_LOCK_ID = int.from_bytes(
    sha256(b"emperor-v4-g3a-core-registry").digest()[:8], "big", signed=True
)


def _json_value(value: object) -> object:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _payload(value: object) -> object:
    return _json_value(asdict(value))


def historical_episode_packet_from_payload(
    payload: Mapping[str, Any],
) -> HistoricalEpisodePacket:
    """从数据库 JSONB 活动版本恢复确定性领域契约。"""

    return HistoricalEpisodePacket(
        episode_id=str(payload["episode_id"]),
        episode_type=str(payload["episode_type"]),
        episode_status=str(payload["episode_status"]),
        evaluation_context=str(payload["evaluation_context"]),
        semantic_version=int(payload["semantic_version"]),
        evidence_version=int(payload["evidence_version"]),
        semantic_fingerprint=str(payload["semantic_fingerprint"]),
        time_start=(str(payload["time_start"]) if payload.get("time_start") else None),
        time_end=(str(payload["time_end"]) if payload.get("time_end") else None),
        time_precision=str(payload["time_precision"]),
        locations=tuple(str(item) for item in payload.get("locations") or ()),
        participants=tuple(
            EpisodeParticipant(
                person_ref=str(item["person_ref"]),
                role_codes=tuple(str(role) for role in item.get("role_codes") or ()),
                role_status=str(item.get("role_status") or "unresolved"),
            )
            for item in payload.get("participants") or ()
        ),
        action=str(payload["action"]),
        responsibility=(
            str(payload["responsibility"])
            if payload.get("responsibility") is not None
            else None
        ),
        outcome=tuple(str(item) for item in payload.get("outcome") or ()),
        consequence=tuple(str(item) for item in payload.get("consequence") or ()),
        assertion_links=tuple(
            AssertionLink(
                assertion_ref=str(item["assertion_ref"]),
                source_passage_ref=str(item["source_passage_ref"]),
                relation=str(item["relation"]),
                supported_fields=tuple(
                    str(field) for field in item.get("supported_fields") or ()
                ),
                evidence_status=str(item.get("evidence_status") or "draft"),
                representative=bool(item.get("representative", False)),
            )
            for item in payload.get("assertion_links") or ()
        ),
        conflicts=tuple(str(item) for item in payload.get("conflicts") or ()),
        uncertainties=tuple(str(item) for item in payload.get("uncertainties") or ()),
        completeness={
            str(key): str(value)
            for key, value in (payload.get("completeness") or {}).items()
        },
        lineage={
            str(key): str(value)
            for key, value in (payload.get("lineage") or {}).items()
        },
        provenance={
            str(key): str(value)
            for key, value in (payload.get("provenance") or {}).items()
        },
    )


def _assertion_semantic_key(assertion: AssertionDraft) -> str:
    if assertion.passage_support is not None:
        return assertion.passage_support.assertion_semantic_key
    return sha256(
        json.dumps(
            {
                "assertion_type": assertion.assertion_type,
                "subject": assertion.subject,
                "predicate": assertion.predicate,
                "object": assertion.object,
                "time_expression": assertion.time_expression,
                "location_expression": assertion.location_expression,
                "qualifiers": dict(assertion.qualifiers),
                "polarity": assertion.polarity,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class PostgresCoreRegistry:
    """G3A PostgreSQL 同步事务写入；调用方负责提供已授权 V4 DSN。"""

    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("PostgresCoreRegistry 需要显式 DSN")
        self._dsn = dsn

    def apply(self, batch: CoreRegistryBatch) -> CoreRegistryWriteResult:
        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover - 取决于可选运行环境
            raise RuntimeError("PostgresCoreRegistry 需要 psycopg") from exc

        writes = {
            "source_documents": 0,
            "source_passages": 0,
            "assertions": 0,
            "historical_episodes": 0,
            "historical_episode_versions": 0,
            "episode_participants": 0,
            "episode_assertion_dispositions": 0,
            "review_artifacts": 0,
            "boundary_review_cache": 0,
        }
        with psycopg.connect(self._dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (ADVISORY_LOCK_ID,))

                for record in batch.source_documents:
                    payload = _payload(record.document)
                    cursor.execute(
                        """
                        INSERT INTO source_documents (
                            document_id, content_version, work_identity, edition_identity,
                            title, canonical_url, source_role, retrieved_at, content_hash,
                            license_or_access_note, payload
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (document_id, content_version) DO NOTHING
                        RETURNING 1
                        """,
                        (
                            record.document.document_cache_id,
                            record.content_version,
                            record.document.work_identity,
                            record.document.edition_identity,
                            record.document.title,
                            record.document.url,
                            record.document.source_role,
                            record.document.retrieved_at,
                            record.document.content_hash,
                            record.document.license_or_access_note,
                            Jsonb(payload),
                        ),
                    )
                    inserted = cursor.fetchone() is not None
                    if not inserted:
                        self._assert_payload(
                            cursor,
                            "SELECT payload FROM source_documents WHERE document_id = %s AND content_version = %s",
                            (record.document.document_cache_id, record.content_version),
                            payload,
                            "SourceDocument",
                        )
                    writes["source_documents"] += int(inserted)

                for passage in batch.source_passages:
                    if not passage.is_contract_v2:
                        raise ValueError("G3A 只持久化 SourcePassage v2")
                    payload = _payload(passage)
                    cursor.execute(
                        """
                        INSERT INTO source_passages (
                            passage_id, document_id, document_content_version, section_id,
                            section_heading, span_start, span_end, passage_kind, content_hash,
                            window_policy_version, payload
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (passage_id) DO NOTHING
                        RETURNING 1
                        """,
                        (
                            passage.passage_cache_id,
                            passage.document_cache_id,
                            passage.content_version,
                            canonical_section_id(passage.section_id),
                            passage.section_heading,
                            passage.span_start,
                            passage.span_end,
                            passage.passage_kind,
                            passage.content_hash,
                            passage.window_policy_version,
                            Jsonb(payload),
                        ),
                    )
                    inserted = cursor.fetchone() is not None
                    if not inserted:
                        self._assert_payload(
                            cursor,
                            "SELECT payload FROM source_passages WHERE passage_id = %s",
                            (passage.passage_cache_id,),
                            payload,
                            "SourcePassage",
                        )
                    writes["source_passages"] += int(inserted)

                for assertion in batch.assertions:
                    payload = _payload(assertion)
                    assertion_id = canonical_assertion_id(assertion.assertion_code)
                    cursor.execute(
                        """
                        INSERT INTO assertions (
                            assertion_id, source_passage_id, assertion_type,
                            assertion_semantic_key, payload
                        ) VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (assertion_id) DO NOTHING
                        RETURNING 1
                        """,
                        (
                            assertion_id,
                            assertion.source_passage_ref,
                            assertion.assertion_type,
                            _assertion_semantic_key(assertion),
                            Jsonb(payload),
                        ),
                    )
                    inserted = cursor.fetchone() is not None
                    if not inserted:
                        self._assert_payload(
                            cursor,
                            "SELECT payload FROM assertions WHERE assertion_id = %s",
                            (assertion_id,),
                            payload,
                            "Assertion",
                        )
                    writes["assertions"] += int(inserted)

                for packet in batch.episodes:
                    identity_anchor = str(
                        batch.episode_identity_anchors.get(packet.episode_id)
                        or packet.episode_id
                    )
                    episode_writes = self._write_episode(
                        cursor, packet, identity_anchor, Jsonb
                    )
                    writes["historical_episodes"] += episode_writes[0]
                    writes["historical_episode_versions"] += episode_writes[1]
                    writes["episode_participants"] += episode_writes[2]

                for disposition in batch.episode_dispositions:
                    assertion_id = canonical_assertion_id(disposition.assertion_ref)
                    cursor.execute(
                        """
                        INSERT INTO episode_assertion_dispositions (
                            episode_id, semantic_version, evidence_version, assertion_id,
                            disposition, reason, follow_up
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (
                            episode_id, semantic_version, evidence_version, assertion_id, disposition
                        ) DO NOTHING
                        RETURNING 1
                        """,
                        (
                            disposition.episode_id,
                            disposition.semantic_version,
                            disposition.evidence_version,
                            assertion_id,
                            disposition.disposition,
                            disposition.reason,
                            disposition.follow_up,
                        ),
                    )
                    inserted = cursor.fetchone() is not None
                    if not inserted:
                        cursor.execute(
                            """
                            SELECT reason, follow_up
                            FROM episode_assertion_dispositions
                            WHERE episode_id = %s AND semantic_version = %s
                              AND evidence_version = %s AND assertion_id = %s
                              AND disposition = %s
                            """,
                            (
                                disposition.episode_id,
                                disposition.semantic_version,
                                disposition.evidence_version,
                                assertion_id,
                                disposition.disposition,
                            ),
                        )
                        row = cursor.fetchone()
                        if row != (disposition.reason, disposition.follow_up):
                            raise ValueError("EpisodeDisposition 稳定身份发生冲突")
                    writes["episode_assertion_dispositions"] += int(inserted)

                for artifact in batch.review_artifacts:
                    writes["review_artifacts"] += self._write_artifact(
                        cursor, artifact, Jsonb
                    )

                for entry in batch.boundary_cache_entries:
                    cursor.execute(
                        """
                        INSERT INTO boundary_review_cache (
                            cache_key, input_hash, policy_version, schema_version,
                            model_family, artifact_id
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (cache_key) DO NOTHING
                        RETURNING 1
                        """,
                        (
                            entry.cache_key,
                            entry.input_hash,
                            entry.policy_version,
                            entry.schema_version,
                            entry.model_family,
                            entry.artifact_id,
                        ),
                    )
                    inserted = cursor.fetchone() is not None
                    if not inserted:
                        cursor.execute(
                            """
                            SELECT input_hash, policy_version, schema_version, model_family, artifact_id
                            FROM boundary_review_cache WHERE cache_key = %s
                            """,
                            (entry.cache_key,),
                        )
                        if cursor.fetchone() != (
                            entry.input_hash,
                            entry.policy_version,
                            entry.schema_version,
                            entry.model_family,
                            entry.artifact_id,
                        ):
                            raise ValueError("BoundaryReviewCache 稳定身份发生冲突")
                    writes["boundary_review_cache"] += int(inserted)

        return CoreRegistryWriteResult(
            table_writes=writes,
            business_write_count=sum(writes.values()),
        )

    def active_packets_by_identity(
        self, identity_anchors: tuple[str, ...]
    ) -> Mapping[str, HistoricalEpisodePacket]:
        if not identity_anchors:
            return {}
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - 取决于可选运行环境
            raise RuntimeError("PostgresCoreRegistry 需要 psycopg") from exc

        with psycopg.connect(self._dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT episode.identity_anchor, version.payload
                    FROM historical_episodes AS episode
                    JOIN historical_episode_versions AS version
                      ON version.episode_id = episode.episode_id
                     AND version.semantic_version = episode.active_semantic_version
                     AND version.evidence_version = episode.active_evidence_version
                    WHERE episode.identity_anchor = ANY(%s)
                    """,
                    (list(identity_anchors),),
                )
                return {
                    str(anchor): historical_episode_packet_from_payload(
                        _json_value(payload)
                    )
                    for anchor, payload in cursor.fetchall()
                }

    @staticmethod
    def _assert_payload(
        cursor: Any,
        query: str,
        params: tuple[object, ...],
        expected: object,
        label: str,
    ) -> None:
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row is None or _json_value(row[0]) != expected:
            raise ValueError(f"{label} 稳定身份发生冲突")

    @staticmethod
    def _write_episode(
        cursor: Any,
        packet: HistoricalEpisodePacket,
        identity_anchor: str,
        jsonb_type: Any,
    ) -> tuple[int, int, int]:
        if packet.semantic_version < 1 or packet.evidence_version < 1:
            raise ValueError("HistoricalEpisode version 必须从 1 开始")
        payload = _payload(packet)
        semantic_hash = semantic_payload_hash(packet)
        evidence_hash = evidence_payload_hash(packet)
        input_version = packet.provenance.get("input_version")
        input_hash = packet.provenance.get("input_hash")
        if not input_version or not input_hash:
            raise ValueError("HistoricalEpisode persistence 必须声明 input_version/input_hash")
        for link in packet.assertion_links:
            cursor.execute(
                "SELECT source_passage_id FROM assertions WHERE assertion_id = %s",
                (canonical_assertion_id(link.assertion_ref),),
            )
            row = cursor.fetchone()
            if row != (link.source_passage_ref,):
                raise ValueError("HistoricalEpisode lineage 引用了未知或不匹配的 Assertion")

        cursor.execute(
            """
            SELECT active_semantic_version, active_evidence_version,
                   evaluation_context, identity_anchor
            FROM historical_episodes
            WHERE episode_id = %s
            FOR UPDATE
            """,
            (packet.episode_id,),
        )
        current_row = cursor.fetchone()
        evaluation_context_ref = canonical_person_ref(packet.evaluation_context)
        episode_write = 0
        if current_row is None:
            if (packet.semantic_version, packet.evidence_version) != (1, 1):
                raise ValueError("首次 Episode 持久化必须从 semantic/evidence v1 开始")
            cursor.execute(
                """
                INSERT INTO historical_episodes (
                    episode_id, identity_anchor, evaluation_context, active_semantic_version,
                    active_evidence_version, active_semantic_fingerprint
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    packet.episode_id,
                    identity_anchor,
                    evaluation_context_ref,
                    packet.semantic_version,
                    packet.evidence_version,
                    packet.semantic_fingerprint,
                ),
            )
            episode_write = 1
        else:
            current_semantic, current_evidence, evaluation_context, current_anchor = current_row
            if evaluation_context != evaluation_context_ref:
                raise ValueError("HistoricalEpisode evaluation_context 不得变化")
            if current_anchor != identity_anchor:
                raise ValueError("HistoricalEpisode identity_anchor 不得变化")
            cursor.execute(
                """
                SELECT semantic_payload_hash, evidence_payload_hash
                FROM historical_episode_versions
                WHERE episode_id = %s AND semantic_version = %s AND evidence_version = %s
                """,
                (packet.episode_id, current_semantic, current_evidence),
            )
            current_hashes = cursor.fetchone()
            if current_hashes is None:
                raise ValueError("HistoricalEpisode 活动版本缺失")
            semantic_step = packet.semantic_version - int(current_semantic)
            evidence_step = packet.evidence_version - int(current_evidence)
            if semantic_step == 0 and evidence_step == 0:
                pass
            elif semantic_step == 0:
                if evidence_step != 1 or current_hashes[0] != semantic_hash:
                    raise ValueError("Evidence revision 版本或语义不连续")
                if current_hashes[1] == evidence_hash:
                    raise ValueError("Evidence version 不得在无证据变化时递增")
            elif semantic_step == 1:
                if evidence_step not in {0, 1} or current_hashes[0] == semantic_hash:
                    raise ValueError("Semantic revision 版本或语义不连续")
            else:
                raise ValueError("HistoricalEpisode version 必须连续递增")

        cursor.execute(
            """
            INSERT INTO historical_episode_versions (
                episode_id, semantic_version, evidence_version, semantic_fingerprint,
                semantic_payload_hash, evidence_payload_hash, episode_status,
                input_version, input_hash, payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (episode_id, semantic_version, evidence_version) DO NOTHING
            RETURNING 1
            """,
            (
                packet.episode_id,
                packet.semantic_version,
                packet.evidence_version,
                packet.semantic_fingerprint,
                semantic_hash,
                evidence_hash,
                packet.episode_status,
                input_version,
                input_hash,
                jsonb_type(payload),
            ),
        )
        version_inserted = cursor.fetchone() is not None
        if not version_inserted:
            PostgresCoreRegistry._assert_payload(
                cursor,
                """
                SELECT payload FROM historical_episode_versions
                WHERE episode_id = %s AND semantic_version = %s AND evidence_version = %s
                """,
                (packet.episode_id, packet.semantic_version, packet.evidence_version),
                payload,
                "HistoricalEpisode version",
            )

        participant_writes = 0
        for participant in packet.participants:
            person_ref = canonical_person_ref(participant.person_ref)
            for role_code in participant.role_codes:
                cursor.execute(
                    """
                    INSERT INTO episode_participants (
                        episode_id, semantic_version, person_ref, role_code, role_status
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (episode_id, semantic_version, person_ref, role_code) DO NOTHING
                    RETURNING 1
                    """,
                    (
                        packet.episode_id,
                        packet.semantic_version,
                        person_ref,
                        role_code,
                        participant.role_status,
                    ),
                )
                inserted = cursor.fetchone() is not None
                if not inserted:
                    cursor.execute(
                        """
                        SELECT role_status FROM episode_participants
                        WHERE episode_id = %s AND semantic_version = %s
                          AND person_ref = %s AND role_code = %s
                        """,
                        (
                            packet.episode_id,
                            packet.semantic_version,
                            person_ref,
                            role_code,
                        ),
                    )
                    if cursor.fetchone() != (participant.role_status,):
                        raise ValueError("EpisodeParticipant 稳定身份发生冲突")
                participant_writes += int(inserted)

        if current_row is not None and (
            packet.semantic_version,
            packet.evidence_version,
        ) != (int(current_row[0]), int(current_row[1])):
            cursor.execute(
                """
                UPDATE historical_episodes
                SET active_semantic_version = %s,
                    active_evidence_version = %s,
                    active_semantic_fingerprint = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE episode_id = %s
                """,
                (
                    packet.semantic_version,
                    packet.evidence_version,
                    packet.semantic_fingerprint,
                    packet.episode_id,
                ),
            )
            episode_write = 1

        return (episode_write, int(version_inserted), participant_writes)

    @staticmethod
    def _write_artifact(
        cursor: Any, artifact: ReviewArtifactRecord, jsonb_type: Any
    ) -> int:
        payload = _json_value(dict(artifact.payload))
        cursor.execute(
            """
            INSERT INTO review_artifacts (
                artifact_id, artifact_type, artifact_status, basis_hash,
                policy_version, schema_version, idempotency_key, payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (artifact_id) DO NOTHING
            RETURNING 1
            """,
            (
                artifact.artifact_id,
                artifact.artifact_type,
                artifact.status,
                artifact.basis_hash,
                artifact.policy_version,
                artifact.schema_version,
                artifact.idempotency_key,
                jsonb_type(payload),
            ),
        )
        inserted = cursor.fetchone() is not None
        if not inserted:
            cursor.execute(
                """
                SELECT artifact_type, artifact_status, basis_hash, policy_version,
                       schema_version, idempotency_key, payload
                FROM review_artifacts WHERE artifact_id = %s
                """,
                (artifact.artifact_id,),
            )
            row = cursor.fetchone()
            expected = (
                artifact.artifact_type,
                artifact.status,
                artifact.basis_hash,
                artifact.policy_version,
                artifact.schema_version,
                artifact.idempotency_key,
                payload,
            )
            if row is None or tuple(row[:-1]) + (_json_value(row[-1]),) != expected:
                raise ValueError("ReviewArtifact 稳定身份发生冲突")
        return int(inserted)
