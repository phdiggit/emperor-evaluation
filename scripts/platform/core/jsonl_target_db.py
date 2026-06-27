from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar


QuoteIdentifier = Callable[[str], str]
CursorCallback = Callable[[Any, str], Any]
T = TypeVar("T")


@dataclass(frozen=True)
class RowCountStatement:
    key: str
    sql: str


@dataclass(frozen=True)
class FetchOneCountStatement:
    keys: tuple[str, ...]
    sql: str


def run_with_target_schema_cursor(
    dsn: str,
    *,
    schema: str,
    quote_identifier: QuoteIdentifier,
    callback: Callable[[Any, str], T],
    create_schema: bool = False,
) -> T:
    import psycopg

    schema_ident = quote_identifier(schema)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            if create_schema:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_ident};")
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            result = callback(cur, schema_ident)
        conn.commit()
    return result


def execute_target_schema_sql(
    dsn: str,
    *,
    schema: str,
    sql: str,
    quote_identifier: QuoteIdentifier,
    create_schema: bool = False,
) -> None:
    def execute(cur: Any, _schema_ident: str) -> None:
        cur.execute(sql)

    run_with_target_schema_cursor(
        dsn,
        schema=schema,
        quote_identifier=quote_identifier,
        callback=execute,
        create_schema=create_schema,
    )


def make_create_target_prototype_tables(
    sql: str,
    *,
    quote_identifier: QuoteIdentifier,
    create_schema: bool = False,
) -> Callable[[str], None]:
    def create_target_prototype_tables(dsn: str, *, schema: str) -> None:
        execute_target_schema_sql(
            dsn,
            schema=schema,
            sql=sql,
            quote_identifier=quote_identifier,
            create_schema=create_schema,
        )

    return create_target_prototype_tables


def execute_count_statements(
    dsn: str,
    *,
    schema: str,
    quote_identifier: QuoteIdentifier,
    rowcount_statements: Sequence[RowCountStatement] = (),
    fetchone_statements: Sequence[FetchOneCountStatement] = (),
) -> dict[str, int]:
    def execute(cur: Any, _schema_ident: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for statement in rowcount_statements:
            cur.execute(statement.sql)
            counts[statement.key] = int(cur.rowcount)
        for statement in fetchone_statements:
            cur.execute(statement.sql)
            row = cur.fetchone() or ()
            for index, key in enumerate(statement.keys):
                value = row[index] if index < len(row) else 0
                counts[key] = int(value or 0)
        return counts

    return run_with_target_schema_cursor(
        dsn,
        schema=schema,
        quote_identifier=quote_identifier,
        callback=execute,
    )


def make_insert_target_rows(
    *,
    quote_identifier: QuoteIdentifier,
    rowcount_statements: Sequence[RowCountStatement] = (),
    fetchone_statements: Sequence[FetchOneCountStatement] = (),
) -> Callable[[str], dict[str, int]]:
    def insert_target_rows(dsn: str, *, schema: str) -> dict[str, int]:
        return execute_count_statements(
            dsn,
            schema=schema,
            quote_identifier=quote_identifier,
            rowcount_statements=rowcount_statements,
            fetchone_statements=fetchone_statements,
        )

    return insert_target_rows
