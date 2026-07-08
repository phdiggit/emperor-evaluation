from __future__ import annotations

import os
import re
from typing import Any


DEFAULT_PG_SCHEMA = "retrieval_v3"
DEFAULT_PG_SCHEMA_ENV = "EMPEROR_EVAL_RETRIEVAL_PG_SCHEMA"
DEFAULT_V3_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V3_DSN"

_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RetrievalPgSchemaError(ValueError):
    pass


def pg_schema_name(value: str | None = None) -> str:
    schema = (value or os.environ.get(DEFAULT_PG_SCHEMA_ENV) or DEFAULT_PG_SCHEMA).strip()
    if not _SCHEMA_RE.fullmatch(schema):
        raise RetrievalPgSchemaError(f"invalid PostgreSQL schema name: {schema!r}")
    return schema


def pg_prefix(schema_name: str | None = None) -> str:
    schema = pg_schema_name(schema_name)
    match = re.fullmatch(r"retrieval_v(\d+)", schema)
    if match:
        return f"rv{match.group(1)}"
    return re.sub(r"[^A-Za-z0-9_]+", "_", schema).strip("_") or "retrieval"


def render_sql(sql: str, *, schema_name: str | None = None) -> str:
    schema = pg_schema_name(schema_name)
    prefix = pg_prefix(schema)
    return sql.replace("retrieval_v2", schema).replace("rv2_", f"{prefix}_")


def table_label(table_name: str, *, schema_name: str | None = None) -> str:
    return f"{pg_schema_name(schema_name)}.{table_name}"


class SchemaCursor:
    def __init__(self, cursor: Any, *, schema_name: str | None = None) -> None:
        self._cursor = cursor
        self._schema_name = pg_schema_name(schema_name)

    def execute(self, query: Any, params: Any = None) -> Any:
        if isinstance(query, str):
            query = render_sql(query, schema_name=self._schema_name)
        if params is None:
            return self._cursor.execute(query)
        return self._cursor.execute(query, params)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


def schema_cursor(cursor: Any, *, schema_name: str | None = None) -> SchemaCursor:
    return SchemaCursor(cursor, schema_name=schema_name)
