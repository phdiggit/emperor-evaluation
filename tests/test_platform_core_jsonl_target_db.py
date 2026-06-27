from __future__ import annotations

import sys
import types

from scripts.platform.core.jsonl_target_db import (
    FetchOneCountStatement,
    RowCountStatement,
    make_create_target_prototype_tables,
    make_insert_target_rows,
)


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.rowcount = 0
        self._row: tuple[int, ...] = ()

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str) -> None:
        self.executed.append(sql)
        if "INSERT first_rows" in sql:
            self.rowcount = 3
        elif "INSERT second_rows" in sql:
            self.rowcount = 5
        elif "SELECT counters" in sql:
            self._row = (7, 11)

    def fetchone(self) -> tuple[int, ...]:
        return self._row


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_obj = cursor
        self.committed = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True


def install_fake_psycopg(monkeypatch, cursor: FakeCursor) -> FakeConnection:
    connection = FakeConnection(cursor)
    fake_psycopg = types.SimpleNamespace(connect=lambda dsn: connection)
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    return connection


def quote_identifier(value: str) -> str:
    return f'"{value}"'


def test_create_target_prototype_tables_sets_schema_search_path_and_executes_sql(monkeypatch) -> None:
    cursor = FakeCursor()
    connection = install_fake_psycopg(monkeypatch, cursor)
    create_tables = make_create_target_prototype_tables(
        "CREATE TABLE example (id BIGINT);",
        quote_identifier=quote_identifier,
        create_schema=True,
    )

    create_tables("postgresql://example/db", schema="target_schema")

    assert cursor.executed == [
        'CREATE SCHEMA IF NOT EXISTS "target_schema";',
        'SET search_path TO "target_schema", public;',
        "CREATE TABLE example (id BIGINT);",
    ]
    assert connection.committed is True


def test_insert_target_rows_returns_rowcount_and_fetchone_counts(monkeypatch) -> None:
    cursor = FakeCursor()
    connection = install_fake_psycopg(monkeypatch, cursor)
    insert_rows = make_insert_target_rows(
        quote_identifier=quote_identifier,
        rowcount_statements=(
            RowCountStatement("first_rows", "INSERT first_rows"),
            RowCountStatement("second_rows", "INSERT second_rows"),
        ),
        fetchone_statements=(
            FetchOneCountStatement(("blocked_rows", "manual_review_rows"), "SELECT counters"),
        ),
    )

    result = insert_rows("postgresql://example/db", schema="target_schema")

    assert result == {
        "first_rows": 3,
        "second_rows": 5,
        "blocked_rows": 7,
        "manual_review_rows": 11,
    }
    assert cursor.executed == [
        'SET search_path TO "target_schema", public;',
        "INSERT first_rows",
        "INSERT second_rows",
        "SELECT counters",
    ]
    assert connection.committed is True
