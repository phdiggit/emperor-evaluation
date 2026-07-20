from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from emperor_v4.application.source_cache_service import (
    CachedSourceCacheResult,
    SourceCacheIdempotencyConflict,
    source_content_version,
)
from emperor_v4.contracts.source import SourceRevisionContent
from emperor_v4.persistence.canonical_refs import canonical_section_id


SOURCE_CACHE_SCHEMA = "v4_source_cache"
SOURCE_CACHE_CONTENT_TABLES = frozenset(
    {
        "requests",
        "document_revisions",
        "passages",
        "request_documents",
        "request_passages",
    }
)
SOURCE_CACHE_JOB_TABLES = frozenset({"jobs", "job_runs"})
SOURCE_CACHE_TABLES = SOURCE_CACHE_CONTENT_TABLES | SOURCE_CACHE_JOB_TABLES


class SourceCacheSchemaStateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SourceCacheSchemaBootstrapResult:
    action: Literal["applied", "reused"]
    table_count: int
    database_write_count: int


def migration_paths() -> tuple[Path, ...]:
    root = Path(__file__).resolve().parents[3] / "db" / "postgres"
    return (
        root / "002_v4_source_cache_service.sql",
        root / "003_v4_source_cache_jobs.sql",
    )


def migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "002_v4_source_cache_service.sql"
    )


def decide_source_cache_schema_action(
    existing_tables: Iterable[str],
) -> Literal["apply", "upgrade", "reuse"]:
    existing = frozenset(existing_tables)
    if not existing:
        return "apply"
    if existing == SOURCE_CACHE_CONTENT_TABLES:
        return "upgrade"
    if existing == SOURCE_CACHE_TABLES:
        return "reuse"
    raise SourceCacheSchemaStateError(
        "V4 Source Cache schema 不完整；"
        f"missing={sorted(SOURCE_CACHE_TABLES - existing)}, "
        f"unexpected={sorted(existing - SOURCE_CACHE_TABLES)}"
    )


def _psycopg() -> tuple[Any, Any]:
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as exc:  # pragma: no cover - 取决于可选运行环境
        raise RuntimeError("V4 Source Cache PostgreSQL 需要 psycopg") from exc
    return psycopg, Jsonb


def bootstrap_source_cache_schema(dsn: str) -> SourceCacheSchemaBootstrapResult:
    if not dsn.strip():
        raise ValueError("Source Cache bootstrap 需要显式 V4 DSN")
    psycopg, _ = _psycopg()
    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname = %s
                ORDER BY tablename
                """,
                (SOURCE_CACHE_SCHEMA,),
            )
            action = decide_source_cache_schema_action(
                str(row[0]) for row in cursor.fetchall()
            )
            if action == "apply":
                for path in migration_paths():
                    cursor.execute(path.read_text(encoding="utf-8"))
            elif action == "upgrade":
                cursor.execute(migration_paths()[1].read_text(encoding="utf-8"))
            cursor.execute(
                """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname = %s
                ORDER BY tablename
                """,
                (SOURCE_CACHE_SCHEMA,),
            )
            actual = {str(row[0]) for row in cursor.fetchall()}
            if actual != SOURCE_CACHE_TABLES:
                raise SourceCacheSchemaStateError(
                    "Source Cache migration 后表集合与合同不一致"
                )
    return SourceCacheSchemaBootstrapResult(
        action=(
            "applied"
            if action in {"apply", "upgrade"}
            else "reused"
        ),
        table_count=len(SOURCE_CACHE_TABLES),
        database_write_count=(
            1 if action in {"apply", "upgrade"} else 0
        ),
    )


def _content_versions(response: Mapping[str, Any]) -> dict[str, str]:
    versions: dict[str, set[str]] = {}
    for passage in response.get("passages") or ():
        versions.setdefault(str(passage["document_id"]), set()).add(
            str(passage["content_version"])
        )
    result = {}
    for document in response.get("documents") or ():
        document_id = str(document["document_cache_id"])
        candidates = versions.get(document_id) or set()
        if not candidates:
            revision_ref = str(
                (document.get("http_metadata") or {}).get("revision_ref") or ""
            )
            if revision_ref:
                candidates = {
                    f"revision:{revision_ref}:{document['content_hash']}"
                }
        if len(candidates) != 1:
            raise ValueError(
                f"Source Cache document 必须恰有一个 content_version: {document_id}"
            )
        result[document_id] = next(iter(candidates))
    return result


class PostgresSourceCacheRepository:
    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("PostgresSourceCacheRepository 需要显式 V4 DSN")
        self.dsn = dsn

    def get(self, idempotency_key: str) -> CachedSourceCacheResult | None:
        psycopg, _ = _psycopg()
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT input_fingerprint, response
                    FROM v4_source_cache.requests
                    WHERE idempotency_key = %s
                    """,
                    (idempotency_key,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return CachedSourceCacheResult(
            input_fingerprint=str(row[0]),
            response=row[1],
        )

    def put(
        self,
        idempotency_key: str,
        input_fingerprint: str,
        response: Mapping[str, Any],
        source_revisions: Mapping[str, SourceRevisionContent],
    ) -> int:
        psycopg, Jsonb = _psycopg()
        versions = _content_versions(response)
        writes = 0
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                provenance = response.get("provenance") or {}
                cursor.execute(
                    """
                    INSERT INTO v4_source_cache.requests (
                        idempotency_key, request_id, input_fingerprint,
                        contract_version, source_policy_version, request_mode,
                        result_status, output_fingerprint, response
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING 1
                    """,
                    (
                        idempotency_key,
                        response["request_id"],
                        input_fingerprint,
                        response["contract"],
                        provenance["source_policy_version"],
                        provenance["request_mode"],
                        response["status"],
                        response["output_fingerprint"],
                        Jsonb(response),
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    cursor.execute(
                        """
                        SELECT input_fingerprint, response
                        FROM v4_source_cache.requests
                        WHERE idempotency_key = %s
                        """,
                        (idempotency_key,),
                    )
                    existing = cursor.fetchone()
                    if existing is None or (
                        str(existing[0]) != input_fingerprint
                        or existing[1] != response
                    ):
                        raise SourceCacheIdempotencyConflict(
                            "PostgreSQL 幂等键已绑定不同 Source Cache 结果"
                        )
                    return 0
                writes += 1

                for document in response.get("documents") or ():
                    document_id = str(document["document_cache_id"])
                    revision = source_revisions.get(document_id)
                    if revision is None:
                        raise ValueError(
                            f"PostgreSQL Source Cache 缺少原文 revision: {document_id}"
                        )
                    if source_content_version(revision) != versions[document_id]:
                        raise ValueError(
                            f"PostgreSQL Source Cache revision/version 不一致: {document_id}"
                        )
                    cursor.execute(
                        """
                        INSERT INTO v4_source_cache.document_revisions (
                            document_cache_id, content_version, work_identity,
                            edition_identity, title, canonical_url, source_role,
                            source_host, source_document_ref, revision_ref,
                            revision_timestamp, retrieved_at, raw_content,
                            content_hash, payload
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (document_cache_id, content_version) DO NOTHING
                        RETURNING 1
                        """,
                        (
                            document_id,
                            versions[document_id],
                            document["work_identity"],
                            document["edition_identity"],
                            document["title"],
                            document["url"],
                            document["source_role"],
                            revision.source_host,
                            revision.source_document_ref,
                            revision.revision_ref,
                            revision.revision_timestamp,
                            revision.retrieved_at,
                            revision.raw_text,
                            document["content_hash"],
                            Jsonb(document),
                        ),
                    )
                    document_inserted = cursor.fetchone()
                    if document_inserted is not None:
                        writes += 1
                    else:
                        cursor.execute(
                            """
                            SELECT content_hash, raw_content, payload
                            FROM v4_source_cache.document_revisions
                            WHERE document_cache_id = %s AND content_version = %s
                            """,
                            (document_id, versions[document_id]),
                        )
                        existing_document = cursor.fetchone()
                        if existing_document is None or (
                            str(existing_document[0]) != document["content_hash"]
                            or str(existing_document[1]) != revision.raw_text
                            or existing_document[2] != document
                        ):
                            raise SourceCacheIdempotencyConflict(
                                "PostgreSQL document revision identity 出现冲突"
                            )

                for passage in response.get("passages") or ():
                    cursor.execute(
                        """
                        INSERT INTO v4_source_cache.passages (
                            passage_id, document_cache_id, document_content_version,
                            section_id, span_start, span_end, passage_kind,
                            content_hash, window_policy_version, payload
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (passage_id) DO NOTHING
                        RETURNING 1
                        """,
                        (
                            passage["passage_id"],
                            passage["document_id"],
                            passage["content_version"],
                            canonical_section_id(passage["section_id"]),
                            passage["span_start"],
                            passage["span_end"],
                            passage["passage_kind"],
                            passage["content_hash"],
                            passage["window_policy_version"],
                            Jsonb(passage),
                        ),
                    )
                    passage_inserted = cursor.fetchone()
                    if passage_inserted is not None:
                        writes += 1
                    else:
                        cursor.execute(
                            """
                            SELECT content_hash, payload
                            FROM v4_source_cache.passages
                            WHERE passage_id = %s
                            """,
                            (passage["passage_id"],),
                        )
                        existing_passage = cursor.fetchone()
                        if existing_passage is None or (
                            str(existing_passage[0]) != passage["content_hash"]
                            or existing_passage[1] != passage
                        ):
                            raise SourceCacheIdempotencyConflict(
                                "PostgreSQL passage identity 出现冲突"
                            )

                for document in response.get("documents") or ():
                    document_id = str(document["document_cache_id"])
                    cursor.execute(
                        """
                        INSERT INTO v4_source_cache.request_documents (
                            idempotency_key, document_cache_id, document_content_version
                        ) VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                        RETURNING 1
                        """,
                        (idempotency_key, document_id, versions[document_id]),
                    )
                    writes += 1 if cursor.fetchone() is not None else 0
                for passage in response.get("passages") or ():
                    cursor.execute(
                        """
                        INSERT INTO v4_source_cache.request_passages (
                            idempotency_key, passage_id
                        ) VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        RETURNING 1
                        """,
                        (idempotency_key, passage["passage_id"]),
                    )
                    writes += 1 if cursor.fetchone() is not None else 0
        return writes

    def get_revision(
        self,
        document_cache_id: str,
        content_version: str,
    ) -> SourceRevisionContent | None:
        psycopg, _ = _psycopg()
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT source_host, source_document_ref, title, canonical_url,
                           revision_ref, revision_timestamp, retrieved_at,
                           raw_content, content_hash
                    FROM v4_source_cache.document_revisions
                    WHERE document_cache_id = %s AND content_version = %s
                    """,
                    (document_cache_id, content_version),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return SourceRevisionContent(
            source_host=str(row[0]),
            source_document_ref=str(row[1]),
            title=str(row[2]),
            url=str(row[3]),
            revision_ref=str(row[4]),
            revision_timestamp=row[5].isoformat(),
            retrieved_at=row[6].isoformat(),
            raw_text=str(row[7]),
            content_hash=str(row[8]),
        )
