from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from emperor_v4.application.claim_extractor_service import (
    CachedClaimExtractionResult,
)


CLAIM_EXTRACTOR_SCHEMA = "v4_claim_extractor"
CLAIM_EXTRACTOR_TABLES = frozenset(
    {"requests", "assertion_drafts", "request_assertions", "jobs", "job_runs"}
)
CLAIM_RESULT_STATUSES = frozenset(
    {
        "succeeded",
        "succeeded_with_gaps",
        "succeeded_no_relevant_facts",
    }
)


class ClaimExtractorSchemaStateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ClaimExtractorSchemaBootstrapResult:
    action: Literal["applied", "reused"]
    table_count: int
    database_write_count: int


def migration_paths() -> tuple[Path, ...]:
    root = Path(__file__).resolve().parents[3] / "db" / "postgres"
    return (
        root / "004_v4_claim_extractor_service.sql",
        root / "005_v4_claim_extractor_result_status.sql",
    )


def migration_path() -> Path:
    """兼容旧调用：返回初始 schema migration。"""

    return migration_paths()[0]


def decide_claim_extractor_schema_action(
    existing_tables: Iterable[str],
) -> Literal["apply", "reuse"]:
    existing = frozenset(existing_tables)
    if not existing:
        return "apply"
    if existing == CLAIM_EXTRACTOR_TABLES:
        return "reuse"
    raise ClaimExtractorSchemaStateError(
        "V4 Claim Extractor schema 不完整: "
        f"missing={sorted(CLAIM_EXTRACTOR_TABLES-existing)}, "
        f"unexpected={sorted(existing-CLAIM_EXTRACTOR_TABLES)}"
    )


def claim_result_status_constraint_is_current(
    definition: str | None,
) -> bool:
    if not definition:
        return False
    normalized = definition.casefold()
    return all(f"'{status}'" in normalized for status in CLAIM_RESULT_STATUSES)


def _psycopg() -> tuple[Any, Any]:
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("V4 Claim Extractor PostgreSQL 需要 psycopg") from exc
    return psycopg, Jsonb


def _result_status_constraint(cursor: Any) -> str | None:
    cursor.execute(
        """
        SELECT pg_catalog.pg_get_constraintdef(con.oid)
        FROM pg_catalog.pg_constraint AS con
        JOIN pg_catalog.pg_class AS rel ON rel.oid = con.conrelid
        JOIN pg_catalog.pg_namespace AS nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = %s
          AND rel.relname = 'requests'
          AND con.conname = 'requests_result_status_check'
        """,
        (CLAIM_EXTRACTOR_SCHEMA,),
    )
    row = cursor.fetchone()
    return None if row is None else str(row[0])


def bootstrap_claim_extractor_schema(
    dsn: str,
) -> ClaimExtractorSchemaBootstrapResult:
    if not dsn.strip():
        raise ValueError("Claim Extractor bootstrap 需要显式 V4 DSN")
    psycopg, _ = _psycopg()
    applied = False
    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_catalog.pg_tables "
                "WHERE schemaname=%s ORDER BY tablename",
                (CLAIM_EXTRACTOR_SCHEMA,),
            )
            action = decide_claim_extractor_schema_action(
                row[0] for row in cursor.fetchall()
            )
            if action == "apply":
                cursor.execute(
                    migration_paths()[0].read_text(encoding="utf-8")
                )
                applied = True

            constraint = _result_status_constraint(cursor)
            if not claim_result_status_constraint_is_current(constraint):
                cursor.execute(
                    migration_paths()[1].read_text(encoding="utf-8")
                )
                applied = True

            cursor.execute(
                "SELECT tablename FROM pg_catalog.pg_tables "
                "WHERE schemaname=%s",
                (CLAIM_EXTRACTOR_SCHEMA,),
            )
            if {row[0] for row in cursor.fetchall()} != CLAIM_EXTRACTOR_TABLES:
                raise ClaimExtractorSchemaStateError(
                    "Claim Extractor migration 后表集合不一致"
                )
            if not claim_result_status_constraint_is_current(
                _result_status_constraint(cursor)
            ):
                raise ClaimExtractorSchemaStateError(
                    "Claim Extractor result_status 约束未升级"
                )
    return ClaimExtractorSchemaBootstrapResult(
        action="applied" if applied else "reused",
        table_count=len(CLAIM_EXTRACTOR_TABLES),
        database_write_count=1 if applied else 0,
    )


class PostgresClaimExtractionRepository:
    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("PostgresClaimExtractionRepository 需要显式 V4 DSN")
        self.dsn = dsn

    def get(
        self,
        idempotency_key: str,
    ) -> CachedClaimExtractionResult | None:
        psycopg, _ = _psycopg()
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT input_fingerprint,response "
                    "FROM v4_claim_extractor.requests "
                    "WHERE idempotency_key=%s",
                    (idempotency_key,),
                )
                row = cursor.fetchone()
        return (
            None
            if row is None
            else CachedClaimExtractionResult(str(row[0]), row[1])
        )

    def put(
        self,
        idempotency_key: str,
        input_fingerprint: str,
        response: Mapping[str, Any],
    ) -> int:
        psycopg, Jsonb = _psycopg()
        writes = 0
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO v4_claim_extractor.requests
                    (idempotency_key,request_id,input_fingerprint,profile_code,contract_version,result_status,output_fingerprint,response)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (idempotency_key) DO NOTHING RETURNING 1""",
                    (
                        idempotency_key,
                        response["request_id"],
                        input_fingerprint,
                        response["profile_code"],
                        response["contract"],
                        response["status"],
                        response["output_fingerprint"],
                        Jsonb(response),
                    ),
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        "SELECT input_fingerprint,response "
                        "FROM v4_claim_extractor.requests "
                        "WHERE idempotency_key=%s",
                        (idempotency_key,),
                    )
                    existing = cursor.fetchone()
                    if (
                        existing is None
                        or str(existing[0]) != input_fingerprint
                        or existing[1] != response
                    ):
                        raise ValueError(
                            "PostgreSQL Claim extraction 幂等冲突"
                        )
                    return 0
                writes += 1
                for assertion in response["assertions"]:
                    support = assertion["passage_support"]
                    cursor.execute(
                        """INSERT INTO v4_claim_extractor.assertion_drafts
                        (assertion_code,source_passage_ref,assertion_semantic_key,input_fingerprint,payload)
                        VALUES (%s,%s,%s,%s,%s) ON CONFLICT (assertion_code) DO NOTHING RETURNING 1""",
                        (
                            assertion["assertion_code"],
                            assertion["source_passage_ref"],
                            support["assertion_semantic_key"],
                            input_fingerprint,
                            Jsonb(assertion),
                        ),
                    )
                    if cursor.fetchone() is not None:
                        writes += 1
                    else:
                        cursor.execute(
                            "SELECT input_fingerprint,payload "
                            "FROM v4_claim_extractor.assertion_drafts "
                            "WHERE assertion_code=%s",
                            (assertion["assertion_code"],),
                        )
                        existing = cursor.fetchone()
                        if (
                            existing is None
                            or str(existing[0]) != input_fingerprint
                            or existing[1] != assertion
                        ):
                            raise ValueError(
                                "PostgreSQL Assertion draft identity 冲突"
                            )
                    cursor.execute(
                        "INSERT INTO v4_claim_extractor.request_assertions "
                        "VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING 1",
                        (idempotency_key, assertion["assertion_code"]),
                    )
                    writes += 1 if cursor.fetchone() is not None else 0
        return writes
