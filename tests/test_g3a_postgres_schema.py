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
