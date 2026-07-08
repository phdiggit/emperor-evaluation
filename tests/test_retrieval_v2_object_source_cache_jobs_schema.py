from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "db" / "migrations" / "20260708_retrieval_v2_object_source_cache_jobs.sql"


def migration_sql() -> str:
    assert MIGRATION_PATH.exists()
    return MIGRATION_PATH.read_text(encoding="utf-8")


def created_tables(sql: str) -> set[str]:
    return set(re.findall(r"create table if not exists retrieval_v2\.([a-z_]+)\s*\(", sql, flags=re.IGNORECASE))


def created_table_columns(sql: str) -> dict[str, set[str]]:
    columns_by_table: dict[str, set[str]] = {}
    table_pattern = re.compile(
        r"create table if not exists retrieval_v2\.([a-z_]+)\s*\((.*?)\n\);",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in table_pattern.finditer(sql):
        table = match.group(1)
        columns: set[str] = set()
        for raw_line in match.group(2).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("constraint "):
                break
            columns.add(line.split()[0].rstrip(","))
        columns_by_table[table] = columns
    return columns_by_table


def commented_tables(sql: str) -> set[str]:
    return set(re.findall(r"comment on table retrieval_v2\.([a-z_]+)\s+is\s+", sql, flags=re.IGNORECASE))


def commented_columns(sql: str) -> set[tuple[str, str]]:
    return set(
        re.findall(
            r"comment on column retrieval_v2\.([a-z_]+)\.([a-z0-9_]+)\s+is\s+",
            sql,
            flags=re.IGNORECASE,
        )
    )


def enum_types(sql: str) -> set[str]:
    return set(re.findall(r"create type retrieval_v2\.(rv2_[a-z_]+)\s+as enum", sql, flags=re.IGNORECASE))


def commented_types(sql: str) -> set[str]:
    return set(re.findall(r"comment on type retrieval_v2\.(rv2_[a-z_]+)\s+is\s+", sql, flags=re.IGNORECASE))


def test_object_source_cache_jobs_schema_creates_queue_tables() -> None:
    assert created_tables(migration_sql()) == {
        "object_source_cache_jobs",
        "object_source_cache_job_runs",
    }


def test_object_source_cache_jobs_schema_uses_enums() -> None:
    sql = migration_sql()

    assert enum_types(sql) == {
        "rv2_object_source_cache_job_status",
        "rv2_object_source_cache_run_status",
    }
    assert commented_types(sql) == enum_types(sql)
    assert "status retrieval_v2.rv2_object_source_cache_job_status" in sql
    assert "status retrieval_v2.rv2_object_source_cache_run_status" in sql
    assert "不用 text + check 承载状态机" in sql


def test_object_source_cache_jobs_schema_comments_every_table_and_column() -> None:
    sql = migration_sql()
    tables = created_tables(sql)
    table_comments = commented_tables(sql)
    columns_by_table = created_table_columns(sql)
    column_comments = commented_columns(sql)

    assert tables - table_comments == set()
    assert table_comments - tables == set()

    missing_column_comments = sorted(
        f"{table}.{column}"
        for table, columns in columns_by_table.items()
        for column in columns
        if (table, column) not in column_comments
    )
    extra_column_comments = sorted(
        f"{table}.{column}"
        for table, column in column_comments
        if table not in columns_by_table or column not in columns_by_table[table]
    )

    assert missing_column_comments == []
    assert extra_column_comments == []


def test_object_source_cache_jobs_schema_does_not_touch_consumption_tables() -> None:
    sql = migration_sql().lower()

    assert "insert into" not in sql
    assert "claim_rule_bindings" not in sql
    assert "target_rule_score_clusters" not in sql
    assert "不接消费端，不触发评分" in sql
