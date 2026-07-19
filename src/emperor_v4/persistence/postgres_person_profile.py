from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from emperor_v4.persistence.postgres_schema_governance import (
    ensure_schema_governance,
)


PERSON_PROFILE_SCHEMA = "v4_person_profile"
PERSON_PROFILE_TABLES = frozenset({"person_identity_registry", "person_profiles"})


class PersonProfileSchemaStateError(RuntimeError):
    pass


def migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "006_v4_person_profiles.sql"
    )


def decide_person_profile_schema_action(existing_tables: Iterable[str]) -> str:
    existing = set(existing_tables)
    if not existing:
        return "apply"
    if existing == PERSON_PROFILE_TABLES:
        return "reuse"
    raise PersonProfileSchemaStateError(
        "V4 person profile schema must contain only "
        f"{sorted(PERSON_PROFILE_TABLES)}; found={sorted(existing)}"
    )


def bootstrap_person_profile_schema(dsn: str, *, dry_run: bool) -> dict[str, Any]:
    if not dsn.strip():
        raise ValueError("person profile schema bootstrap requires an explicit V4 DSN")
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("person profile schema bootstrap requires psycopg") from exc

    migration = migration_path()
    migration_sql = migration.read_text(encoding="utf-8")
    migration_sha256 = sha256(migration_sql.encode("utf-8")).hexdigest()
    try:
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                    """,
                    (PERSON_PROFILE_SCHEMA,),
                )
                existing = {str(row[0]) for row in cursor.fetchall()}
                action = decide_person_profile_schema_action(existing)
                if action == "apply" and not dry_run:
                    cursor.execute(migration_sql)
                    database_write_count = 1
                else:
                    database_write_count = 0
                if not dry_run and ensure_schema_governance(cursor)[
                    "database_write_count"
                ]:
                    database_write_count = 1
    except PersonProfileSchemaStateError:
        raise
    except Exception:
        raise RuntimeError("V4 person profile database operation failed") from None

    return {
        "schema": PERSON_PROFILE_SCHEMA,
        "action": "would_apply" if dry_run and action == "apply" else action,
        "migration_path": migration.as_posix(),
        "migration_sha256": migration_sha256,
        "expected_tables": sorted(PERSON_PROFILE_TABLES),
        "existing_tables": sorted(existing),
        "database_write_count": database_write_count,
        "dry_run": dry_run,
    }
