from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable


PERSON_PROFILE_SCHEMA = "v4_person_profile"
PERSON_PROFILE_BASE_TABLES = {
    "import_batches",
    "person_identity_registry",
    "person_legacy_refs",
    "person_profile_snapshots",
    "person_profile_lineage",
    "ruler_team_window_snapshots",
    "ruler_team_window_members",
}
PERSON_PROFILE_PRE_CALIBRATION_TABLES = PERSON_PROFILE_BASE_TABLES | {
    "person_profile_catalog"
}
PERSON_PROFILE_TABLES = PERSON_PROFILE_PRE_CALIBRATION_TABLES | {
    "talent_grade_calibrations"
}


class PersonProfileSchemaStateError(RuntimeError):
    pass


def migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "006_v4_person_profile_team_window.sql"
    )


def catalog_migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "007_v4_person_profile_catalog.sql"
    )


def optional_capability_migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "008_v4_person_profile_optional_capability.sql"
    )


def talent_calibration_migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "009_v4_talent_grade_calibration.sql"
    )


def current_profile_view_migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "010_v4_person_profile_current_readable.sql"
    )


def multi_policy_calibration_migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "011_v4_talent_grade_multi_policy.sql"
    )


def decide_person_profile_schema_action(existing_tables: Iterable[str]) -> str:
    existing = set(existing_tables)
    if not existing:
        return "apply"
    if existing == PERSON_PROFILE_BASE_TABLES:
        return "extend_catalog"
    if existing == PERSON_PROFILE_PRE_CALIBRATION_TABLES:
        return "extend_calibration"
    if existing == PERSON_PROFILE_TABLES:
        return "reuse"
    missing = sorted(PERSON_PROFILE_TABLES - existing)
    unexpected = sorted(existing - PERSON_PROFILE_TABLES)
    raise PersonProfileSchemaStateError(
        f"V4 person profile schema shape mismatch; missing={missing}, unexpected={unexpected}"
    )


def bootstrap_person_profile_schema(dsn: str, *, dry_run: bool) -> dict[str, Any]:
    if not dsn.strip():
        raise ValueError("person profile schema bootstrap requires an explicit V4 DSN")
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("person profile schema bootstrap requires psycopg") from exc
    migration = migration_path()
    catalog_migration = catalog_migration_path()
    optional_capability_migration = optional_capability_migration_path()
    talent_calibration_migration = talent_calibration_migration_path()
    current_profile_view_migration = current_profile_view_migration_path()
    multi_policy_calibration_migration = multi_policy_calibration_migration_path()
    base_sql = migration.read_text(encoding="utf-8")
    catalog_sql = catalog_migration.read_text(encoding="utf-8")
    optional_capability_sql = optional_capability_migration.read_text(encoding="utf-8")
    talent_calibration_sql = talent_calibration_migration.read_text(encoding="utf-8")
    current_profile_view_sql = current_profile_view_migration.read_text(encoding="utf-8")
    multi_policy_calibration_sql = multi_policy_calibration_migration.read_text(
        encoding="utf-8"
    )
    sql = (
        base_sql
        + "\n"
        + catalog_sql
        + "\n"
        + optional_capability_sql
        + "\n"
        + talent_calibration_sql
        + "\n"
        + current_profile_view_sql
        + "\n"
        + multi_policy_calibration_sql
    )
    migration_sha256 = sha256(sql.encode("utf-8")).hexdigest()
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
                existing = [row[0] for row in cursor.fetchall()]
                action = decide_person_profile_schema_action(existing)
                if action == "reuse":
                    cursor.execute(
                        """
                        SELECT conname, pg_get_constraintdef(oid)
                        FROM pg_constraint
                        WHERE connamespace = %s::regnamespace
                          AND conname IN (
                              'person_profile_snapshots_capability_domains_check',
                              'person_profile_catalog_capability_domains_check'
                          )
                        ORDER BY conname
                        """,
                        (PERSON_PROFILE_SCHEMA,),
                    )
                    capability_constraints = cursor.fetchall()
                    if len(capability_constraints) != 2:
                        raise PersonProfileSchemaStateError(
                            "V4 person profile capability constraints are missing"
                        )
                    optional_capability_upgrade = any(
                        "jsonb_array_length" in definition
                        for _, definition in capability_constraints
                    )
                    cursor.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = 'person_profile_current'
                        ORDER BY ordinal_position
                        LIMIT 7
                        """,
                        (PERSON_PROFILE_SCHEMA,),
                    )
                    current_view_columns = [row[0] for row in cursor.fetchall()]
                    current_view_upgrade = current_view_columns != [
                        "canonical_name",
                        "effective_talent_grade",
                        "negative_risk_status",
                        "effective_talent_grade_basis",
                        "negative_talent_basis",
                        "negative_talent_class",
                        "negative_talent_severity",
                    ]
                    cursor.execute(
                        """
                        SELECT pg_get_constraintdef(oid)
                        FROM pg_constraint
                        WHERE connamespace = %s::regnamespace
                          AND conname = 'talent_grade_calibrations_decision_check'
                        """,
                        (PERSON_PROFILE_SCHEMA,),
                    )
                    decision_constraint = cursor.fetchone()
                    multi_policy_upgrade = (
                        decision_constraint is None
                        or "'upgraded'" not in decision_constraint[0]
                    )
                    if optional_capability_upgrade and multi_policy_upgrade:
                        action = "upgrade_optional_capability_and_multi_policy"
                    elif multi_policy_upgrade:
                        action = "upgrade_multi_policy"
                    elif optional_capability_upgrade and current_view_upgrade:
                        action = "upgrade_optional_capability_and_current_view"
                    elif optional_capability_upgrade:
                        action = "upgrade_optional_capability"
                    elif current_view_upgrade:
                        action = "upgrade_current_view"
                if action in {"apply", "extend_catalog", "extend_calibration"} and not dry_run:
                    cursor.execute(
                        sql
                        if action == "apply"
                        else catalog_sql + "\n" + optional_capability_sql + "\n" + talent_calibration_sql + "\n" + current_profile_view_sql + "\n" + multi_policy_calibration_sql
                        if action == "extend_catalog"
                        else optional_capability_sql + "\n" + talent_calibration_sql + "\n" + current_profile_view_sql + "\n" + multi_policy_calibration_sql
                    )
                    database_write_count = 1
                elif action == "upgrade_optional_capability" and not dry_run:
                    cursor.execute(optional_capability_sql)
                    database_write_count = 1
                elif action == "upgrade_current_view" and not dry_run:
                    cursor.execute(current_profile_view_sql)
                    database_write_count = 1
                elif (
                    action == "upgrade_optional_capability_and_current_view"
                    and not dry_run
                ):
                    cursor.execute(optional_capability_sql + "\n" + current_profile_view_sql)
                    database_write_count = 1
                elif action == "upgrade_multi_policy" and not dry_run:
                    cursor.execute(multi_policy_calibration_sql)
                    database_write_count = 1
                elif (
                    action == "upgrade_optional_capability_and_multi_policy"
                    and not dry_run
                ):
                    cursor.execute(optional_capability_sql + "\n" + multi_policy_calibration_sql)
                    database_write_count = 1
                else:
                    database_write_count = 0
    except PersonProfileSchemaStateError:
        raise
    except Exception:
        raise RuntimeError("V4 person profile database operation failed") from None
    return {
        "schema": PERSON_PROFILE_SCHEMA,
        "action": (
            "would_apply"
            if dry_run and action == "apply"
            else "would_extend_catalog"
            if dry_run and action == "extend_catalog"
            else "would_extend_calibration"
            if dry_run and action == "extend_calibration"
            else "would_upgrade_optional_capability"
            if dry_run and action == "upgrade_optional_capability"
            else "would_upgrade_current_view"
            if dry_run and action == "upgrade_current_view"
            else "would_upgrade_optional_capability_and_current_view"
            if dry_run and action == "upgrade_optional_capability_and_current_view"
            else "would_upgrade_multi_policy"
            if dry_run and action == "upgrade_multi_policy"
            else "would_upgrade_optional_capability_and_multi_policy"
            if dry_run and action == "upgrade_optional_capability_and_multi_policy"
            else action
        ),
        "migration_path": migration.as_posix(),
        "catalog_migration_path": catalog_migration.as_posix(),
        "optional_capability_migration_path": optional_capability_migration.as_posix(),
        "talent_calibration_migration_path": talent_calibration_migration.as_posix(),
        "current_profile_view_migration_path": current_profile_view_migration.as_posix(),
        "multi_policy_calibration_migration_path": multi_policy_calibration_migration.as_posix(),
        "migration_sha256": migration_sha256,
        "expected_tables": sorted(PERSON_PROFILE_TABLES),
        "existing_tables": sorted(existing),
        "database_write_count": database_write_count,
        "dry_run": dry_run,
    }
