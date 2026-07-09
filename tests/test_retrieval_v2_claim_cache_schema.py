from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "db" / "migrations" / "20260708_retrieval_v2_claim_cache.sql"


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


def test_claim_cache_schema_creates_minimal_claim_management_tables() -> None:
    tables = created_tables(migration_sql())

    assert tables == {
        "claim_cache",
        "claim_source_slices",
        "claim_evidence",
        "claim_route_cache",
        "person_profile_claim_links",
    }


def test_claim_cache_schema_uses_enums_for_finite_value_fields() -> None:
    sql = migration_sql()

    assert enum_types(sql) == {
        "rv2_claim_direction",
        "rv2_object_type",
        "rv2_claim_cache_type",
        "rv2_claim_fact_schema",
        "rv2_claim_cache_status",
        "rv2_claim_support_level",
        "rv2_claim_route_status",
        "rv2_profile_claim_field",
        "rv2_profile_claim_status",
    }
    assert commented_types(sql) == enum_types(sql)
    for enum_column in [
        "claim_type retrieval_v2.rv2_claim_cache_type",
        "fact_schema retrieval_v2.rv2_claim_fact_schema",
        "object_type retrieval_v2.rv2_object_type",
        "status retrieval_v2.rv2_claim_cache_status",
        "support_level retrieval_v2.rv2_claim_support_level",
        "candidate_direction retrieval_v2.rv2_claim_direction",
        "route_status retrieval_v2.rv2_claim_route_status",
        "profile_field retrieval_v2.rv2_profile_claim_field",
        "proposal_status retrieval_v2.rv2_profile_claim_status",
    ]:
        assert enum_column in sql
    assert "不用 text + check 承载状态机" in sql
    assert "status text" not in sql.lower()


def test_claim_cache_schema_comments_every_table_and_column() -> None:
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


def test_claim_cache_schema_keeps_cache_separate_from_scoring_tables() -> None:
    sql = migration_sql().lower()

    assert "insert into" not in sql
    assert "update retrieval_v2." not in sql
    assert "references retrieval_v2.claim_rule_bindings" in sql
    assert "references retrieval_v2.person_profiles" in sql
    assert "claim cache 是可复用材料层，不直接写评分结论" in sql
