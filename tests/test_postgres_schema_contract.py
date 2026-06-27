import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "postgres" / "001_init.sql"

REQUIRED_TABLES = [
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


def schema_text() -> str:
    assert SCHEMA_PATH.exists()
    return SCHEMA_PATH.read_text(encoding="utf-8")


def created_tables(sql: str) -> set[str]:
    return set(re.findall(r"CREATE TABLE\s+([a-z_]+)\s*\(", sql, flags=re.IGNORECASE))


def changed_paths(*pathspecs: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--short", "--", *pathspecs],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line[3:] for line in result.stdout.splitlines() if line.strip()]


def test_postgres_schema_exists_and_contains_required_tables() -> None:
    sql = schema_text()

    assert created_tables(sql) >= set(REQUIRED_TABLES)


def test_postgres_schema_uses_short_physical_table_names() -> None:
    sql = schema_text()
    tables = created_tables(sql)

    assert "source_documents" not in tables
    assert "source_passages" not in tables
    assert "evidence_source_links" not in tables
    assert "shit_" not in sql.lower()


def test_postgres_schema_contains_required_extensions_and_search_indexes() -> None:
    sql = schema_text()
    upper_sql = sql.upper()

    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in sql
    assert "GIN" in upper_sql
    assert "gin_trgm_ops" in sql
    assert "search_vec" in sql
    assert "TSVECTOR" in upper_sql


def test_postgres_schema_contains_core_constraints() -> None:
    sql = schema_text()
    upper_sql = sql.upper()

    for keyword in ["UNIQUE", "PRIMARY KEY", "FOREIGN KEY", "CHECK"]:
        assert keyword in upper_sql

    assert re.search(r"CONSTRAINT\s+job_idem_uk\s+UNIQUE\s*\(\s*idem_key\s*\)", sql)
    assert "CONSTRAINT eslink_pk PRIMARY KEY (evd_id, passage_id, role, span_start)" in sql
    assert "CONSTRAINT clusterevd_pk PRIMARY KEY (cluster_id, evd_id)" in sql


def test_postgres_schema_contains_task_and_outbox_contract() -> None:
    sql = schema_text()

    for table in ["jobs", "job_runs", "job_deps", "outbox"]:
        assert table in created_tables(sql)

    for status in [
        "queued",
        "ready",
        "running",
        "retry_wait",
        "succeeded",
        "failed",
        "dead_lettered",
        "blocked",
        "cancelled",
    ]:
        assert status in sql

    for kind in ["search", "fetch", "parse", "match", "draft", "review_notify"]:
        assert kind in sql

    assert "WHERE status IN ('ready', 'retry_wait')" in sql
    assert "WHERE published_at IS NULL" in sql


def test_postgres_schema_contains_anchor_contract_and_neutral_matching_fields() -> None:
    sql = schema_text()

    assert "CREATE TABLE anchors (" in sql
    assert "anchor_type_review_idx" in sql
    assert "hit_position INTEGER" in sql
    assert "match_confidence NUMERIC(5,4)" in sql
    assert "rank INTEGER" not in sql
    assert "score NUMERIC" not in sql


def test_postgres_schema_avoids_varchar_and_keeps_data_untouched() -> None:
    assert "VARCHAR(" not in schema_text().upper()

    allowed_data_changes = {
        "data/configs/project_config.yml",
        "data/batches/i5b_typical_batch_a/",
        "data/evidence_cards.jsonl",
        "data/evidence_clusters.jsonl",
        "data/query_profiles.jsonl",
        "data/search_logs.jsonl",
        "data/sources.jsonl",
    }
    assert [path for path in changed_paths("data") if path not in allowed_data_changes] == []
