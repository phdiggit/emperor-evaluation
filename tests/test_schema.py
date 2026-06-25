import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "schema.sql"
POSTGRES_SCHEMA_PATH = ROOT / "db" / "postgres" / "001_init.sql"


REQUIRED_FORMAL_TABLES = [
    "persons",
    "person_aliases",
    "subitems",
    "src_hosts",
    "src_docs",
    "doc_revs",
    "passages",
    "passage_people",
    "query_profiles",
    "search_tasks",
    "search_hits",
    "cand_matches",
    "evd_cards",
    "evd_src_links",
    "clusters",
    "anchors",
    "cluster_evd",
    "review_items",
    "jobs",
    "job_runs",
    "job_deps",
    "outbox",
    "imports",
    "import_rows",
]


def created_tables(sql: str) -> set[str]:
    return set(re.findall(r"CREATE TABLE\s+([a-z_]+)\s*\(", sql, flags=re.IGNORECASE))


def test_schema_exists_and_matches_postgres_formal_schema() -> None:
    assert SCHEMA_PATH.exists()
    assert POSTGRES_SCHEMA_PATH.exists()

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    postgres_schema = POSTGRES_SCHEMA_PATH.read_text(encoding="utf-8")

    assert schema == postgres_schema
    assert created_tables(schema) >= set(REQUIRED_FORMAL_TABLES)


def test_schema_contains_formal_constraints_indexes_and_anchor_table() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    for field in [
        "id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY",
        "payload JSONB NOT NULL DEFAULT '{}'::jsonb",
        "search_vec TSVECTOR GENERATED ALWAYS",
        "hit_position INTEGER",
        "match_confidence NUMERIC(5,4)",
        "anchor_type TEXT NOT NULL",
        "review_status TEXT NOT NULL DEFAULT 'pending'",
    ]:
        assert field in schema

    for index_or_constraint in [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        "passage_search_gin",
        "passage_norm_trgm",
        "cmatch_task_status_idx",
        "anchor_type_review_idx",
        "CONSTRAINT anchor_code_uk UNIQUE (code)",
        "CONSTRAINT anchor_type_ck CHECK",
    ]:
        assert index_or_constraint in schema
