from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
import json
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import formal_ddl_rehearsal, formal_schema_draft


LIVE_REHEARSAL_VERSION = "isolated-formal-ddl-live-rehearsal-v1"
PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
DEFAULT_SCHEMA_PREFIX = "emperor_eval_formal_live"
SCHEMA_REHEARSAL_META_TABLE = formal_ddl_rehearsal.SCHEMA_REHEARSAL_META_TABLE
EXPECTED_TABLES = (*formal_schema_draft.PHASE_1_BASE_TABLES, SCHEMA_REHEARSAL_META_TABLE)
FORBIDDEN_TABLES = (
    *formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES,
    *formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES,
)
RESERVED_SCHEMA_NAMES = {"", "public", "postgres", "pg_catalog", "information_schema"}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ResolvedDsn:
    dsn: str | None
    source: str

    @property
    def present(self) -> bool:
        return bool(self.dsn)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "live_rehearsal_version": LIVE_REHEARSAL_VERSION,
        "formal_ddl_rehearsal_version": formal_ddl_rehearsal.REHEARSAL_VERSION,
        "status": "Proposed",
        "apply_mode": "explicit --apply only",
        "dsn_env": PRIMARY_ENV_DSN,
        "driver": "psycopg",
        "schema_prefix_default": DEFAULT_SCHEMA_PREFIX,
        "phase_1_expected_tables": list(EXPECTED_TABLES),
        "phase_2_forbidden_tables": list(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES),
        "phase_3_forbidden_tables": list(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES),
        "verification_plan": [
            "render isolated formal DDL for a random schema",
            "lint rendered SQL before any database connection",
            "execute rendered SQL in one isolated schema",
            "verify phase 1 tables and schema_rehearsal_meta exist",
            "verify phase 2 relationship tables are absent",
            "verify phase 3 downstream tables are absent",
        ],
        "cleanup_plan": [
            "drop only the random isolated schema when requested",
            "verify the random isolated schema no longer exists after drop",
            "report cleanup status without printing connection details",
        ],
        "non_goals": [
            "does not modify canonical JSONL",
            "does not modify db/schema.sql",
            "does not modify db/postgres/001_init.sql",
            "does not read .env",
            "does not generate seed artifact",
            "does not switch the JSONL write source",
            "does not write production target tables",
            "does not write public schema objects",
        ],
        "strict_boundaries": [
            "contract_report_and_check_do_not_connect",
            "contract_report_and_check_do_not_read_dotenv",
            "apply_reads_only_primary_dsn_environment_variable",
            "apply_requires_explicit_opt_in",
            "apply_uses_random_isolated_schema",
            "apply_reuses_formal_ddl_rehearsal_render_sql",
            "apply_reuses_formal_ddl_rehearsal_lint_sql",
            "no_seed_artifact",
            "no_production_target_table_writes",
        ],
        "future_work": [
            "seed artifact contract and dry seed planner in a separate PR",
            "no production migration in this PR",
        ],
        "limitations": [
            "requires a caller-provided PostgreSQL DSN only in apply mode",
            "does not validate production migration readiness",
            "does not create phase 2 relationship tables",
            "does not create phase 3 downstream tables",
        ],
    }
    _assert_no_blocked_terms(report)
    return report


def check_environment(
    *,
    env: Mapping[str, str] | None = None,
    driver_available: bool | None = None,
) -> dict[str, Any]:
    resolved = resolve_dsn(env=env)
    if driver_available is None:
        driver_available = is_psycopg_available()
    return {
        "mode": "check",
        "dsn_present": resolved.present,
        "dsn_source": resolved.source,
        "driver": "psycopg",
        "driver_available": driver_available,
        "will_apply": False,
        "default_tests_require_postgres": False,
    }


def resolve_dsn(*, env: Mapping[str, str] | None = None) -> ResolvedDsn:
    if env is None:
        env = os.environ
    if env.get(PRIMARY_ENV_DSN):
        return ResolvedDsn(env[PRIMARY_ENV_DSN], f"env:{PRIMARY_ENV_DSN}")
    return ResolvedDsn(None, "skip")


def integration_skip_reason(
    resolved: ResolvedDsn | None = None,
    *,
    driver_available: bool | None = None,
) -> str | None:
    if resolved is None:
        resolved = resolve_dsn()
    if not resolved.dsn:
        return f"{PRIMARY_ENV_DSN} is not set"
    if driver_available is None:
        driver_available = is_psycopg_available()
    if not driver_available:
        return "psycopg is not installed"
    return None


def apply_live_rehearsal(
    dsn: str,
    *,
    schema_prefix: str = DEFAULT_SCHEMA_PREFIX,
    drop_schema_after: bool = True,
    token: str | None = None,
) -> dict[str, Any]:
    schema = generate_schema_name(schema_prefix, token=token)
    sql = formal_ddl_rehearsal.render_sql(schema)
    lint = formal_ddl_rehearsal.lint_sql(sql, schema)
    sql_lint_passed = bool(lint["passed"])
    if not sql_lint_passed:
        return _base_apply_report(
            schema=schema,
            schema_prefix=schema_prefix,
            dsn_present=bool(dsn),
            driver_available=is_psycopg_available(),
            sql_lint_passed=False,
            failed=["sql_lint_failed"],
            limitations=["lint failed before database connection"],
        )

    report = _base_apply_report(
        schema=schema,
        schema_prefix=schema_prefix,
        dsn_present=bool(dsn),
        driver_available=True,
        sql_lint_passed=True,
    )
    conn = None
    cleanup_failed = False
    try:
        import psycopg

        conn = psycopg.connect(dsn)
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                report["created_schema"] = schema_exists(cur, schema)
                existing_expected = table_names_in_schema(cur, schema, EXPECTED_TABLES)
                existing_forbidden = table_names_in_schema(cur, schema, FORBIDDEN_TABLES)
                report["existing_expected_tables"] = existing_expected
                report["missing_expected_tables"] = [
                    table for table in EXPECTED_TABLES if table not in set(existing_expected)
                ]
                report["existing_forbidden_tables"] = existing_forbidden
                report["phase_1_table_count"] = len(
                    set(existing_expected) & set(formal_schema_draft.PHASE_1_BASE_TABLES)
                )
                report["phase_2_forbidden_table_count"] = len(
                    set(existing_forbidden) & set(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES)
                )
                report["phase_3_forbidden_table_count"] = len(
                    set(existing_forbidden) & set(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES)
                )
                if drop_schema_after:
                    cur.execute(f"DROP SCHEMA IF EXISTS {quote_identifier(schema)} CASCADE")
                    report["dropped"] = True
                    report["schema_exists_after_drop"] = schema_exists(cur, schema)
                    report["cleanup_verified"] = not report["schema_exists_after_drop"]

        _finalize_apply_report(report)
    except Exception as exc:
        report["failed"].append(type(exc).__name__)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                cleanup_failed = True
            if drop_schema_after:
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"DROP SCHEMA IF EXISTS {quote_identifier(schema)} CASCADE")
                        report["dropped"] = True
                        report["schema_exists_after_drop"] = schema_exists(cur, schema)
                        report["cleanup_verified"] = not report["schema_exists_after_drop"]
                    conn.commit()
                except Exception:
                    cleanup_failed = True
        if cleanup_failed:
            report["failed"].append("cleanup_failed")
        _finalize_apply_report(report)
    finally:
        if conn is not None:
            conn.close()
    return report


def build_apply_skip_report(
    *,
    reason: str,
    schema_prefix: str = DEFAULT_SCHEMA_PREFIX,
    dsn_present: bool,
    driver_available: bool,
) -> dict[str, Any]:
    return {
        "mode": "apply",
        "schema": None,
        "schema_prefix": validate_schema_prefix(schema_prefix),
        "dsn_present": dsn_present,
        "driver_available": driver_available,
        "sql_lint_passed": False,
        "created_schema": False,
        "expected_tables": list(EXPECTED_TABLES),
        "existing_expected_tables": [],
        "missing_expected_tables": list(EXPECTED_TABLES),
        "forbidden_tables": list(FORBIDDEN_TABLES),
        "existing_forbidden_tables": [],
        "phase_1_table_count": 0,
        "phase_2_forbidden_table_count": 0,
        "phase_3_forbidden_table_count": 0,
        "dropped": False,
        "schema_exists_after_drop": None,
        "cleanup_verified": False,
        "passed": False,
        "failed": [reason],
        "limitations": ["apply skipped before database connection"],
    }


def generate_schema_name(prefix: str = DEFAULT_SCHEMA_PREFIX, *, token: str | None = None) -> str:
    prefix = validate_schema_prefix(prefix)
    if token is None:
        token = secrets.token_hex(6)
    if not re.fullmatch(r"[0-9a-f]{10,12}", token):
        raise ValueError("schema token must be 10 to 12 lowercase hex characters")
    schema = f"{prefix}_{token}"
    return validate_schema_name(schema)


def validate_schema_prefix(prefix: str) -> str:
    return validate_schema_name(prefix, label="schema prefix")


def validate_schema_name(schema: str, *, label: str = "schema name") -> str:
    if not schema or not _IDENTIFIER_RE.fullmatch(schema):
        raise ValueError(f"invalid isolated rehearsal {label}: {schema!r}")
    if schema.lower() in RESERVED_SCHEMA_NAMES:
        raise ValueError(f"isolated rehearsal {label} is reserved: {schema!r}")
    return schema


def quote_identifier(value: str) -> str:
    value = validate_schema_name(value)
    return '"' + value.replace('"', '""') + '"'


def schema_exists(cursor: Any, schema: str) -> bool:
    cursor.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
        (schema,),
    )
    row = cursor.fetchone()
    return bool(row and row[0])


def table_names_in_schema(cursor: Any, schema: str, table_names: Sequence[str]) -> list[str]:
    if not table_names:
        return []
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_name = ANY(%s)
        ORDER BY table_name
        """,
        (schema, list(table_names)),
    )
    return [str(row[0]) for row in cursor.fetchall()]


def is_psycopg_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run an opt-in isolated formal DDL live rehearsal.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true", help="print the live rehearsal contract report")
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--apply", action="store_true", help="apply rehearsal SQL to a random isolated schema")
    parser.add_argument("--schema-prefix", default=DEFAULT_SCHEMA_PREFIX, help="prefix for the random isolated schema")
    parser.add_argument(
        "--drop-schema-after",
        action="store_true",
        default=True,
        help="drop the random isolated schema after apply; enabled by default",
    )
    args = parser.parse_args(argv)

    if args.contract_report:
        result = build_contract_report()
        sys.stdout.write(report_as_json(result))
        sys.stdout.write("\n")
        return 0

    if args.check:
        result = check_environment()
        sys.stdout.write(report_as_json(result))
        sys.stdout.write("\n")
        return 0

    try:
        schema_prefix = validate_schema_prefix(args.schema_prefix)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    resolved = resolve_dsn()
    driver_available = is_psycopg_available()
    reason = integration_skip_reason(resolved, driver_available=driver_available)
    if reason:
        result = build_apply_skip_report(
            reason=reason,
            schema_prefix=schema_prefix,
            dsn_present=resolved.present,
            driver_available=driver_available,
        )
        sys.stdout.write(report_as_json(result))
        sys.stdout.write("\n")
        return 2

    result = apply_live_rehearsal(
        resolved.dsn or "",
        schema_prefix=schema_prefix,
        drop_schema_after=args.drop_schema_after,
    )
    sys.stdout.write(report_as_json(result))
    sys.stdout.write("\n")
    return 0 if result["passed"] else 1


def _base_apply_report(
    *,
    schema: str,
    schema_prefix: str,
    dsn_present: bool,
    driver_available: bool,
    sql_lint_passed: bool,
    failed: Sequence[str] | None = None,
    limitations: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "mode": "apply",
        "schema": schema,
        "schema_prefix": schema_prefix,
        "dsn_present": dsn_present,
        "driver_available": driver_available,
        "sql_lint_passed": sql_lint_passed,
        "created_schema": False,
        "expected_tables": list(EXPECTED_TABLES),
        "existing_expected_tables": [],
        "missing_expected_tables": list(EXPECTED_TABLES),
        "forbidden_tables": list(FORBIDDEN_TABLES),
        "existing_forbidden_tables": [],
        "phase_1_table_count": 0,
        "phase_2_forbidden_table_count": 0,
        "phase_3_forbidden_table_count": 0,
        "dropped": False,
        "schema_exists_after_drop": None,
        "cleanup_verified": False,
        "passed": False,
        "failed": list(failed or []),
        "limitations": list(limitations or []),
    }


def _finalize_apply_report(report: dict[str, Any]) -> None:
    missing_expected = report["missing_expected_tables"]
    existing_forbidden = report["existing_forbidden_tables"]
    failures = list(report["failed"])
    if not report["created_schema"]:
        failures.append("schema_not_created")
    if missing_expected:
        failures.append("expected_tables_missing")
    if existing_forbidden:
        failures.append("forbidden_tables_created")
    if report["dropped"] and report["schema_exists_after_drop"]:
        failures.append("schema_still_exists_after_drop")
    if report["dropped"] and not report["cleanup_verified"]:
        failures.append("cleanup_not_verified")
    report["failed"] = sorted(set(failures))
    report["passed"] = not report["failed"]


def _assert_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = report_as_json(report).lower()
    for term in formal_schema_draft.BLOCKED_REPORT_TERMS:
        if term in text:
            raise AssertionError(f"report unexpectedly contains {term!r}")


if __name__ == "__main__":
    raise SystemExit(main())
