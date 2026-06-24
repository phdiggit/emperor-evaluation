from __future__ import annotations

import argparse
import importlib.util
import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import read_dotenv_values


INIT_SQL_PATH = ROOT / "db" / "postgres" / "001_init.sql"
PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH_BENCH_DSN"
DEFAULT_SCHEMA = "emperor_eval_bootstrap_check"
REQUIRED_TABLES = (
    "persons",
    "src_docs",
    "doc_revs",
    "passages",
    "jobs",
    "outbox",
    "imports",
)


@dataclass(frozen=True)
class ResolvedDsn:
    dsn: str | None
    source: str

    @property
    def present(self) -> bool:
        return bool(self.dsn)


def resolve_dsn(
    explicit_dsn: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    env_path: Path = ROOT / ".env",
) -> ResolvedDsn:
    if explicit_dsn:
        return ResolvedDsn(explicit_dsn, "--dsn")
    if env is None:
        env = os.environ
    for name in (PRIMARY_ENV_DSN, LEGACY_ENV_DSN):
        if env.get(name):
            return ResolvedDsn(env[name], f"env:{name}")
    dotenv = read_dotenv_values(env_path)
    for name in (PRIMARY_ENV_DSN, LEGACY_ENV_DSN):
        if dotenv.get(name):
            return ResolvedDsn(dotenv[name], f".env:{name}")
    return ResolvedDsn(None, "skip")


def check_environment(
    resolved: ResolvedDsn | None = None,
    *,
    driver_available: bool | None = None,
) -> dict[str, object]:
    if resolved is None:
        resolved = resolve_dsn()
    if driver_available is None:
        driver_available = is_psycopg_available()
    return {
        "mode": "check",
        "dsn_present": resolved.present,
        "dsn_source": resolved.source,
        "driver": "psycopg",
        "driver_available": driver_available,
        "default_tests_require_postgres": False,
        "will_apply": False,
    }


def integration_skip_reason(
    resolved: ResolvedDsn | None = None,
    *,
    driver_available: bool | None = None,
) -> str | None:
    if resolved is None:
        resolved = resolve_dsn()
    if not resolved.dsn:
        return f"{PRIMARY_ENV_DSN} or {LEGACY_ENV_DSN} is not set"
    if driver_available is None:
        driver_available = is_psycopg_available()
    if not driver_available:
        return "psycopg is not installed"
    return None


def render_bootstrap_sql(schema: str = DEFAULT_SCHEMA, init_sql_path: Path = INIT_SQL_PATH) -> str:
    schema_ident = quote_identifier(schema)
    init_sql = init_sql_path.read_text(encoding="utf-8")
    return "\n".join(
        [
            "CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;",
            f"CREATE SCHEMA IF NOT EXISTS {schema_ident};",
            f"SET search_path TO {schema_ident}, public;",
            "",
            init_sql,
        ]
    )


def apply_bootstrap(
    dsn: str,
    schema: str = DEFAULT_SCHEMA,
    *,
    drop_schema_after: bool = False,
) -> dict[str, object]:
    run_pg_sql(dsn, render_bootstrap_sql(schema))
    dropped = False
    if drop_schema_after:
        drop_schema(dsn, schema)
        dropped = True
    return {
        "mode": "apply",
        "schema": schema,
        "applied": True,
        "drop_schema_after": drop_schema_after,
        "dropped": dropped,
    }


def inspect_bootstrap_contract(dsn: str, schema: str = DEFAULT_SCHEMA) -> dict[str, object]:
    schema_literal = sql_literal(schema)
    tables_array = ", ".join(sql_literal(table) for table in REQUIRED_TABLES)
    sql = f"""
SELECT jsonb_pretty(jsonb_build_object(
    'schema_exists', EXISTS (
        SELECT 1 FROM information_schema.schemata WHERE schema_name = {schema_literal}
    ),
    'required_tables', (
        SELECT COALESCE(jsonb_agg(table_name ORDER BY table_name), '[]'::jsonb)
        FROM information_schema.tables
        WHERE table_schema = {schema_literal}
          AND table_name IN ({tables_array})
    ),
    'pg_trgm_available', EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'
    ),
    'passages_search_vec_generated', EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = {schema_literal}
          AND table_name = 'passages'
          AND column_name = 'search_vec'
          AND is_generated = 'ALWAYS'
    ),
    'passage_search_gin_index', EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = {schema_literal}
          AND tablename = 'passages'
          AND indexname = 'passage_search_gin'
          AND indexdef ILIKE '%USING gin (search_vec)%'
    ),
    'passage_norm_trgm_index', EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = {schema_literal}
          AND tablename = 'passages'
          AND indexname = 'passage_norm_trgm'
          AND indexdef ILIKE '%gin_trgm_ops%'
    ),
    'jobs_idem_unique_constraint', EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_schema = {schema_literal}
          AND table_name = 'jobs'
          AND constraint_name = 'job_idem_uk'
          AND constraint_type = 'UNIQUE'
    ),
    'outbox_partial_index', EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = {schema_literal}
          AND tablename = 'outbox'
          AND indexname = 'outbox_ready_idx'
          AND indexdef ILIKE '%WHERE%published_at IS NULL%'
    )
));
"""
    output = run_pg_sql(dsn, sql)
    return json.loads(output)


def schema_exists(dsn: str, schema: str) -> bool:
    output = run_pg_sql(
        dsn,
        f"SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = {sql_literal(schema)});",
    )
    return output.strip().lower() in {"t", "true", "1"}


def drop_schema(dsn: str, schema: str) -> None:
    run_pg_sql(dsn, f"DROP SCHEMA IF EXISTS {quote_identifier(schema)} CASCADE;")


def run_pg_sql(dsn: str, sql: str) -> str:
    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                return ""
            row = cur.fetchone()
            if row is None:
                return ""
            value: Any = row[0]
            return "" if value is None else str(value)


def is_psycopg_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None


def quote_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"invalid PostgreSQL identifier: {value!r}")
    return '"' + value.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Check or apply the PostgreSQL schema bootstrap contract.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--sql-only", action="store_true", help="print the SQL wrapper without connecting")
    mode.add_argument("--apply", action="store_true", help="apply the schema contract to an isolated schema")
    parser.add_argument("--dsn", help=f"PostgreSQL DSN; overrides {PRIMARY_ENV_DSN} and {LEGACY_ENV_DSN}")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help=f"isolated schema name, default: {DEFAULT_SCHEMA}")
    parser.add_argument("--drop-schema-after", action="store_true", help="drop the isolated schema after apply")
    args = parser.parse_args(argv)

    if args.drop_schema_after and not args.apply:
        parser.error("--drop-schema-after requires --apply")

    if args.sql_only:
        sys.stdout.write(render_bootstrap_sql(args.schema))
        if not sys.stdout.closed:
            sys.stdout.write("\n")
        return 0

    resolved = resolve_dsn(args.dsn)
    if args.apply:
        reason = integration_skip_reason(resolved)
        if reason:
            sys.stderr.write(f"skip: {reason}\n")
            return 2
        result = apply_bootstrap(
            resolved.dsn or "",
            args.schema,
            drop_schema_after=args.drop_schema_after,
        )
    else:
        result = check_environment(resolved)

    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
