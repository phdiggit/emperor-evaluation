from __future__ import annotations

import re
from pathlib import Path

import pytest

from emperor_v4.persistence.postgres_source_cache import (
    SOURCE_CACHE_CONTENT_TABLES,
    SOURCE_CACHE_TABLES,
    SourceCacheSchemaStateError,
    decide_source_cache_schema_action,
)
from emperor_v4.persistence.postgres_claim_extractor import (
    CLAIM_EXTRACTOR_TABLES,
    CLAIM_RESULT_STATUSES,
    ClaimExtractorSchemaStateError,
    claim_result_status_constraint_is_current,
    decide_claim_extractor_schema_action,
)
from emperor_v4.persistence.postgres_person_profile import (
    PERSON_PROFILE_BASE_TABLES,
    PERSON_PROFILE_PRE_CALIBRATION_TABLES,
    PERSON_PROFILE_TABLES,
    PersonProfileSchemaStateError,
    decide_person_profile_schema_action,
    catalog_migration_path as person_profile_catalog_migration_path,
    current_profile_view_migration_path,
    multi_policy_calibration_migration_path,
    optional_capability_migration_path,
    talent_calibration_migration_path,
    migration_path as person_profile_migration_path,
)


SCHEMA = Path(__file__).parents[1] / "db" / "postgres" / "001_g3a_episode_core.sql"
SOURCE_CACHE_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "002_v4_source_cache_service.sql"
)
SOURCE_CACHE_JOBS_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "003_v4_source_cache_jobs.sql"
)
CLAIM_EXTRACTOR_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "004_v4_claim_extractor_service.sql"
)
CLAIM_EXTRACTOR_STATUS_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "005_v4_claim_extractor_result_status.sql"
)
PERSON_PROFILE_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "006_v4_person_profile_team_window.sql"
)
PERSON_PROFILE_CATALOG_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "007_v4_person_profile_catalog.sql"
)
PERSON_PROFILE_OPTIONAL_CAPABILITY_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "008_v4_person_profile_optional_capability.sql"
)
PERSON_PROFILE_TALENT_CALIBRATION_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "009_v4_talent_grade_calibration.sql"
)
PERSON_PROFILE_CURRENT_VIEW_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "010_v4_person_profile_current_readable.sql"
)
PERSON_PROFILE_MULTI_POLICY_SCHEMA = (
    Path(__file__).parents[1]
    / "db"
    / "postgres"
    / "011_v4_talent_grade_multi_policy.sql"
)
EXPECTED_TABLES = {
    "source_documents",
    "source_passages",
    "assertions",
    "historical_episodes",
    "historical_episode_versions",
    "episode_participants",
    "episode_assertion_dispositions",
    "review_artifacts",
    "boundary_review_cache",
}
FORBIDDEN_TABLES = {
    "episode_relations",
    "rule_evidence_units",
    "rule_projections",
    "judgments",
    "score_contributions",
    "outbox",
    "workers",
}


def _sql() -> str:
    return SCHEMA.read_text(encoding="utf-8")


def test_g3a_migration_has_only_authorized_tables() -> None:
    sql = _sql()
    tables = set(
        re.findall(r"CREATE TABLE\s+([a-z_]+)", sql, flags=re.I)
    )

    assert tables == EXPECTED_TABLES
    assert not tables & FORBIDDEN_TABLES


def test_g3a_migration_is_transactional_and_non_destructive() -> None:
    sql = _sql().upper()

    assert sql.lstrip().startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "DROP TABLE" not in sql
    assert "TRUNCATE" not in sql
    assert "DELETE FROM" not in sql


def test_g3a_schema_encodes_idempotency_and_version_lineage() -> None:
    sql = _sql()

    assert "PRIMARY KEY (document_id, content_version)" in sql
    assert "PRIMARY KEY (episode_id, semantic_version, evidence_version)" in sql
    assert "identity_anchor TEXT NOT NULL UNIQUE" in sql
    assert "CREATE INDEX assertions_passage_semantic_idx" in sql
    assert "UNIQUE (source_passage_id, assertion_semantic_key)" not in sql
    assert "idempotency_key TEXT NOT NULL UNIQUE" in sql
    assert "cache_key TEXT PRIMARY KEY" in sql
    assert (
        "UNIQUE (input_hash, policy_version, schema_version, model_family)"
        not in sql
    )
    assert "semantic_payload_hash TEXT NOT NULL" in sql
    assert "evidence_payload_hash TEXT NOT NULL" in sql
    assert "historical_episodes_active_version_fk" in sql
    assert "DEFERRABLE INITIALLY DEFERRED" in sql


def test_relation_outputs_are_artifacts_not_core_fact_tables() -> None:
    sql = _sql()

    assert "'relation_review_artifact'" in sql
    assert "'relation_proposal'" in sql
    assert "'accepted'" not in sql


def test_source_cache_service_uses_separate_pre_acceptance_schema() -> None:
    sql = SOURCE_CACHE_SCHEMA.read_text(encoding="utf-8")
    tables = set(
        re.findall(
            r"CREATE TABLE\s+v4_source_cache\.([a-z_]+)",
            sql,
            flags=re.I,
        )
    )

    assert tables == SOURCE_CACHE_CONTENT_TABLES
    assert "CREATE SCHEMA IF NOT EXISTS v4_source_cache" in sql
    assert "REFERENCES source_documents" not in sql
    assert "assertions" not in tables


def test_source_cache_service_migration_is_transactional_and_non_destructive() -> None:
    sql = SOURCE_CACHE_SCHEMA.read_text(encoding="utf-8").upper()

    assert sql.lstrip().startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "DROP " not in sql
    assert "TRUNCATE" not in sql
    assert "DELETE FROM" not in sql
    assert "PRIMARY KEY (DOCUMENT_CACHE_ID, CONTENT_VERSION)" in sql
    assert "IDEMPOTENCY_KEY TEXT PRIMARY KEY" in sql
    assert "RAW_CONTENT TEXT NOT NULL" in sql


def test_source_cache_schema_bootstrap_reuses_only_complete_shape() -> None:
    assert decide_source_cache_schema_action(()) == "apply"
    assert decide_source_cache_schema_action(SOURCE_CACHE_CONTENT_TABLES) == "upgrade"
    assert decide_source_cache_schema_action(SOURCE_CACHE_TABLES) == "reuse"
    with pytest.raises(SourceCacheSchemaStateError, match="不完整"):
        decide_source_cache_schema_action({"requests"})


def test_source_cache_jobs_migration_has_lease_and_idempotency_contract() -> None:
    sql = SOURCE_CACHE_JOBS_SCHEMA.read_text(encoding="utf-8")
    upper = sql.upper()
    tables = set(
        re.findall(
            r"CREATE TABLE\s+v4_source_cache\.([a-z_]+)",
            sql,
            flags=re.I,
        )
    )

    assert tables == {"jobs", "job_runs"}
    assert "IDEMPOTENCY_KEY TEXT NOT NULL UNIQUE" in upper
    assert "FOR UPDATE" not in upper
    assert "LEASE_EXPIRES_AT TIMESTAMPTZ" in upper
    assert "UNIQUE (JOB_ID, ATTEMPT_NUMBER)" in upper
    assert "DROP " not in upper
    assert "TRUNCATE" not in upper
    assert "DELETE FROM" not in upper


def test_claim_extractor_migration_is_isolated_idempotent_and_lease_aware() -> None:
    sql = CLAIM_EXTRACTOR_SCHEMA.read_text(encoding="utf-8")
    upper = sql.upper()
    tables = set(
        re.findall(
            r"CREATE TABLE\s+v4_claim_extractor\.([a-z_]+)",
            sql,
            flags=re.I,
        )
    )
    assert tables == CLAIM_EXTRACTOR_TABLES
    assert "IDEMPOTENCY_KEY TEXT PRIMARY KEY" in upper
    assert (
        "UNIQUE (SOURCE_PASSAGE_REF, ASSERTION_SEMANTIC_KEY, INPUT_FINGERPRINT)"
        in upper
    )
    assert "LEASE_EXPIRES_AT TIMESTAMPTZ" in upper
    assert (
        "DROP " not in upper
        and "TRUNCATE" not in upper
        and "DELETE FROM" not in upper
    )
    assert decide_claim_extractor_schema_action(()) == "apply"
    assert decide_claim_extractor_schema_action(CLAIM_EXTRACTOR_TABLES) == "reuse"
    with pytest.raises(ClaimExtractorSchemaStateError, match="不完整"):
        decide_claim_extractor_schema_action({"requests"})


def test_claim_extractor_result_status_upgrade_is_versioned_and_complete() -> None:
    initial = CLAIM_EXTRACTOR_SCHEMA.read_text(encoding="utf-8")
    upgrade = CLAIM_EXTRACTOR_STATUS_SCHEMA.read_text(encoding="utf-8")

    assert all(f"'{status}'" in initial for status in CLAIM_RESULT_STATUSES)
    assert all(f"'{status}'" in upgrade for status in CLAIM_RESULT_STATUSES)
    assert upgrade.lstrip().startswith("BEGIN;")
    assert upgrade.rstrip().endswith("COMMIT;")
    assert "DROP CONSTRAINT IF EXISTS requests_result_status_check" in upgrade
    assert claim_result_status_constraint_is_current(
        "CHECK (result_status IN ('succeeded', 'succeeded_with_gaps', "
        "'succeeded_no_relevant_facts'))"
    )
    assert not claim_result_status_constraint_is_current(
        "CHECK (result_status = 'succeeded')"
    )


def test_person_profile_migration_is_isolated_versioned_and_non_destructive() -> None:
    sql = PERSON_PROFILE_SCHEMA.read_text(encoding="utf-8")
    upper = sql.upper()
    tables = set(
        re.findall(
            r"CREATE TABLE\s+v4_person_profile\.([a-z_]+)", sql, flags=re.I
        )
    )

    assert person_profile_migration_path() == PERSON_PROFILE_SCHEMA
    assert tables == PERSON_PROFILE_BASE_TABLES
    assert upper.lstrip().startswith("BEGIN;")
    assert upper.rstrip().endswith("COMMIT;")
    assert "DROP TABLE" not in upper
    assert "TRUNCATE" not in upper
    assert "DELETE FROM" not in upper
    assert "RETRIEVAL_V3" not in upper
    assert "REVOKE ALL ON SCHEMA V4_PERSON_PROFILE FROM PUBLIC" in upper
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA V4_PERSON_PROFILE FROM PUBLIC" in upper
    assert upper.count("IDEMPOTENCY_KEY TEXT NOT NULL UNIQUE") == 7
    assert "PRIMARY KEY (PROFILE_REF, SNAPSHOT_VERSION)" in upper
    assert "PRIMARY KEY (WINDOW_REF, WINDOW_POLICY_VERSION)" in upper
    assert "PRIMARY KEY (WINDOW_REF, WINDOW_POLICY_VERSION, PERSON_REF)" in upper
    assert "ACCEPTED_USER_AUTHORIZED_V3_IDENTITY" in upper
    assert "NEGATIVE_TALENT_CLASS IS NULL AND NEGATIVE_TALENT_SEVERITY IS NULL" in upper


def test_person_profile_catalog_is_a_direct_readable_immutable_projection() -> None:
    sql = PERSON_PROFILE_CATALOG_SCHEMA.read_text(encoding="utf-8")
    upper = sql.upper()

    assert person_profile_catalog_migration_path() == PERSON_PROFILE_CATALOG_SCHEMA
    assert "CREATE TABLE V4_PERSON_PROFILE.PERSON_PROFILE_CATALOG" in upper
    for column in (
        "CANONICAL_NAME TEXT NOT NULL",
        "TALENT_GRADE_BASIS TEXT NOT NULL",
        "NEGATIVE_RISK_STATUS TEXT NOT NULL",
        "NEGATIVE_TALENT_BASIS TEXT NOT NULL",
        "NEGATIVE_TALENT_CONFIDENCE NUMERIC(6, 5) NOT NULL",
    ):
        assert column in upper
    assert "PERSON_PROFILE_CATALOG_IMMUTABLE" in upper
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper


def test_person_profile_optional_capability_migration_preserves_array_shape() -> None:
    sql = PERSON_PROFILE_OPTIONAL_CAPABILITY_SCHEMA.read_text(encoding="utf-8")
    upper = sql.upper()

    assert optional_capability_migration_path() == PERSON_PROFILE_OPTIONAL_CAPABILITY_SCHEMA
    assert upper.count("CHECK (JSONB_TYPEOF(CAPABILITY_DOMAINS) = 'ARRAY')") == 2
    assert "JSONB_ARRAY_LENGTH" not in upper
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper


def test_talent_grade_calibration_is_versioned_immutable_and_readable() -> None:
    sql = PERSON_PROFILE_TALENT_CALIBRATION_SCHEMA.read_text(encoding="utf-8")
    upper = sql.upper()

    assert talent_calibration_migration_path() == PERSON_PROFILE_TALENT_CALIBRATION_SCHEMA
    assert "CREATE TABLE V4_PERSON_PROFILE.TALENT_GRADE_CALIBRATIONS" in upper
    assert "CREATE VIEW V4_PERSON_PROFILE.PERSON_PROFILE_CURRENT" in upper
    assert "ORIGINAL_GRADE TEXT NOT NULL" in upper
    assert "CALIBRATED_GRADE TEXT NOT NULL" in upper
    assert "TALENT_GRADE_CALIBRATIONS_IMMUTABLE" in upper
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper


def test_person_profile_current_puts_business_fields_before_technical_fields() -> None:
    sql = PERSON_PROFILE_CURRENT_VIEW_SCHEMA.read_text(encoding="utf-8")
    upper = sql.upper()

    assert current_profile_view_migration_path() == PERSON_PROFILE_CURRENT_VIEW_SCHEMA
    leading_columns = (
        "CATALOG.CANONICAL_NAME",
        "AS EFFECTIVE_TALENT_GRADE",
        "CATALOG.NEGATIVE_RISK_STATUS",
        "AS EFFECTIVE_TALENT_GRADE_BASIS",
        "CATALOG.NEGATIVE_TALENT_BASIS",
        "CATALOG.NEGATIVE_TALENT_CLASS",
        "CATALOG.NEGATIVE_TALENT_SEVERITY",
        "AS INHERITED_TALENT_GRADE",
        "AS INHERITED_TALENT_GRADE_BASIS",
    )
    positions = [upper.index(column) for column in leading_columns]
    assert positions == sorted(positions)
    assert "CATALOG.*" not in upper
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper


def test_talent_calibration_supports_versioned_promotions_without_duplicate_view_rows() -> None:
    sql = PERSON_PROFILE_MULTI_POLICY_SCHEMA.read_text(encoding="utf-8")
    upper = sql.upper()

    assert multi_policy_calibration_migration_path() == PERSON_PROFILE_MULTI_POLICY_SCHEMA
    assert "'RETAINED', 'DOWNGRADED', 'UPGRADED'" in upper
    assert "LEFT JOIN LATERAL" in upper
    assert "ORDER BY CANDIDATE.CREATED_AT DESC, CANDIDATE.POLICY_VERSION DESC" in upper
    assert "LIMIT 1" in upper
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper


def test_person_profile_schema_bootstrap_fails_closed_on_partial_shape() -> None:
    assert decide_person_profile_schema_action(()) == "apply"
    assert (
        decide_person_profile_schema_action(PERSON_PROFILE_BASE_TABLES)
        == "extend_catalog"
    )
    assert (
        decide_person_profile_schema_action(PERSON_PROFILE_PRE_CALIBRATION_TABLES)
        == "extend_calibration"
    )
    assert decide_person_profile_schema_action(PERSON_PROFILE_TABLES) == "reuse"
    with pytest.raises(PersonProfileSchemaStateError, match="shape mismatch"):
        decide_person_profile_schema_action({"person_profile_snapshots"})
