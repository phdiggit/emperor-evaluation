from __future__ import annotations

import re
from pathlib import Path


SCHEMA = Path(__file__).parents[1] / "db" / "postgres" / "001_g3a_episode_core.sql"
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
    tables = set(re.findall(r"CREATE TABLE\s+([a-z_]+)", sql, flags=re.I))

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
    assert "UNIQUE (input_hash, policy_version, schema_version, model_family)" not in sql
    assert "semantic_payload_hash TEXT NOT NULL" in sql
    assert "evidence_payload_hash TEXT NOT NULL" in sql
    assert "historical_episodes_active_version_fk" in sql
    assert "DEFERRABLE INITIALLY DEFERRED" in sql


def test_relation_outputs_are_artifacts_not_core_fact_tables() -> None:
    sql = _sql()

    assert "'relation_review_artifact'" in sql
    assert "'relation_proposal'" in sql
    assert "'accepted'" not in sql
