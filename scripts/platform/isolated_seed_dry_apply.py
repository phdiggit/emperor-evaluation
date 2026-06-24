from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import (  # noqa: E402
    formal_ddl_live_rehearsal,
    formal_ddl_rehearsal,
    formal_schema_draft,
    seed_artifact_renderer,
    seed_artifact_validation_matrix,
)


DRY_APPLY_VERSION = "isolated-seed-dry-apply-v1"
PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
DEFAULT_SCHEMA_PREFIX = "emperor_eval_seed_dry_apply"
EXPECTED_TABLES = (
    *formal_schema_draft.PHASE_1_BASE_TABLES,
    formal_ddl_rehearsal.SCHEMA_REHEARSAL_META_TABLE,
)
FORBIDDEN_TABLES = (
    *formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES,
    *formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES,
)
VALIDATION_RULES = (
    "ddl_lint_passed_before_connect",
    "artifact_validation_passed_before_insert",
    "random_isolated_schema_used",
    "schema_created",
    "expected_tables_exist",
    "phase_2_3_tables_absent",
    "only_phase_1_tables_inserted",
    "row_counts_match_artifact",
    "schema_rehearsal_meta_inserted",
    "no_public_schema_touch",
    "no_production_schema_touch",
    "no_repo_artifact_written",
    "no_data_or_exports_written",
    "cleanup_verified",
    "no_blocked_report_terms",
)
NO_PRODUCTION_WRITE_FLAGS = {
    "public_schema_touched": False,
    "production_schema_touched": False,
    "production_seed_applied": False,
    "repo_artifact_written": False,
    "data_written": False,
    "exports_written": False,
}
NON_GOALS = (
    "does not modify canonical JSONL",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not read .env",
    "does not use shell database clients",
    "does not switch the JSONL write source",
    "does not write production target tables",
    "does not write repository artifact files",
)
BOUNDARIES = (
    "contract_report_and_check_do_not_connect",
    "contract_report_and_check_do_not_read_dotenv",
    "check_reads_only_primary_dsn_presence",
    "dry_apply_requires_explicit_opt_in",
    "dry_apply_reads_only_primary_dsn_environment_variable",
    "dry_apply_uses_random_isolated_schema",
    "dry_apply_reuses_formal_ddl_rehearsal_render_sql",
    "dry_apply_reuses_formal_ddl_rehearsal_lint_sql",
    "dry_apply_validates_artifact_before_connect",
    "dry_apply_inserts_only_allowed_phase_1_tables",
    "dry_apply_cleans_up_random_schema_when_requested",
)
LIMITATIONS = (
    "requires a caller-provided PostgreSQL DSN only in dry-apply mode",
    "prototype artifact only",
    "minimal payload envelopes only",
    "does not validate production migration readiness",
    "does not create phase 2 relationship tables",
    "does not create phase 3 downstream tables",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "dry_apply_version": DRY_APPLY_VERSION,
        "status": "Proposed",
        "dsn_env": PRIMARY_ENV_DSN,
        "driver": "psycopg",
        "apply_mode": "explicit --dry-apply only",
        "source_artifact": "in-memory prototype seed artifact from seed_artifact_renderer.build_seed_artifact",
        "expected_tables": list(EXPECTED_TABLES),
        "forbidden_tables": list(FORBIDDEN_TABLES),
        "write_strategy": {
            "target": "random isolated schema only",
            "allowed_insert_tables": list(EXPECTED_TABLES),
            "stable_code_shape": "<table_name>:<record_key>",
            "schema_rehearsal_meta_columns": ["schema_name", "draft_version", "source_of_truth", "payload"],
        },
        "validation_rules": list(VALIDATION_RULES),
        "no_production_write_flags": dict(NO_PRODUCTION_WRITE_FLAGS),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "future_work": [
            "isolated seed rollback and restore rehearsal in a later approved PR",
            "production seed application remains out of scope",
        ],
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def check_environment(
    env: Mapping[str, str] | None = None,
    driver_available: bool | None = None,
) -> dict[str, Any]:
    if env is None:
        env = os.environ
    if driver_available is None:
        driver_available = is_psycopg_available()
    return {
        "mode": "check",
        "dsn_present": bool(env.get(PRIMARY_ENV_DSN)),
        "dsn_source": f"env:{PRIMARY_ENV_DSN}" if env.get(PRIMARY_ENV_DSN) else "skip",
        "driver": "psycopg",
        "driver_available": driver_available,
        "will_connect": False,
        "will_write_isolated_schema": False,
        "will_write_public_schema": False,
        "will_apply_production_seed": False,
    }


def run_dry_apply(
    schema_prefix: str,
    drop_schema_after: bool = True,
    *,
    env: Mapping[str, str] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    if env is None:
        env = os.environ
    schema_prefix = formal_ddl_live_rehearsal.validate_schema_prefix(schema_prefix)
    dsn = env.get(PRIMARY_ENV_DSN)
    driver_available = is_psycopg_available()

    if not dsn:
        return build_skip_report(
            reason=f"{PRIMARY_ENV_DSN} is not set",
            schema_prefix=schema_prefix,
            dsn_present=False,
            driver_available=driver_available,
        )
    if not driver_available:
        return build_skip_report(
            reason="psycopg is not installed",
            schema_prefix=schema_prefix,
            dsn_present=True,
            driver_available=False,
        )

    schema = formal_ddl_live_rehearsal.generate_schema_name(schema_prefix, token=token)
    sql = formal_ddl_rehearsal.render_sql(schema)
    lint = formal_ddl_rehearsal.lint_sql(sql, schema)
    if not lint.get("passed"):
        report = _base_dry_apply_report(
            schema=schema,
            schema_prefix=schema_prefix,
            dsn_present=True,
            driver_available=True,
            ddl_lint_passed=False,
            artifact_valid=False,
            failed=["ddl_lint_passed_before_connect"],
            limitations=["DDL lint failed before database connection"],
        )
        validate_dry_apply_result(report)
        return report

    artifact = seed_artifact_renderer.build_seed_artifact(ROOT)
    manifest = seed_artifact_renderer.build_seed_manifest(artifact, ROOT)
    artifact_validation = seed_artifact_validation_matrix.validate_artifact_and_manifest(artifact, manifest)
    if not artifact_validation["passed"]:
        report = _base_dry_apply_report(
            schema=schema,
            schema_prefix=schema_prefix,
            dsn_present=True,
            driver_available=True,
            ddl_lint_passed=True,
            artifact_valid=False,
            failed=["artifact_validation_passed_before_insert", *artifact_validation["failed"]],
            limitations=["artifact validation failed before database connection"],
        )
        validate_dry_apply_result(report)
        return report

    expected_rows_by_table = build_expected_rows_by_table(artifact)
    report = _base_dry_apply_report(
        schema=schema,
        schema_prefix=schema_prefix,
        dsn_present=True,
        driver_available=True,
        ddl_lint_passed=True,
        artifact_valid=True,
    )
    report["expected_rows_by_table"] = expected_rows_by_table

    conn = None
    cleanup_failed = False
    try:
        import psycopg

        conn = psycopg.connect(dsn)
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                report["schema_created"] = formal_ddl_live_rehearsal.schema_exists(cur, schema)
                existing_expected = formal_ddl_live_rehearsal.table_names_in_schema(
                    cur,
                    schema,
                    EXPECTED_TABLES,
                )
                existing_forbidden = formal_ddl_live_rehearsal.table_names_in_schema(
                    cur,
                    schema,
                    FORBIDDEN_TABLES,
                )
                report["existing_expected_tables"] = existing_expected
                report["missing_expected_tables"] = [
                    table for table in EXPECTED_TABLES if table not in set(existing_expected)
                ]
                report["existing_forbidden_tables"] = existing_forbidden

                inserted_rows = insert_artifact_rows(cur, schema, artifact)
                report["inserted_rows_by_table"] = inserted_rows
                report["inserted_tables"] = [
                    table for table in EXPECTED_TABLES if inserted_rows.get(table, 0) > 0
                ]
                actual_rows = count_rows_by_table(cur, schema, EXPECTED_TABLES)
                report["actual_rows_by_table"] = actual_rows
                report["row_count_matches"] = actual_rows == expected_rows_by_table

                if drop_schema_after:
                    cur.execute(
                        f"DROP SCHEMA IF EXISTS {formal_ddl_live_rehearsal.quote_identifier(schema)} CASCADE"
                    )
                    report["dropped"] = True
                    report["schema_exists_after_drop"] = formal_ddl_live_rehearsal.schema_exists(cur, schema)
                    report["cleanup_verified"] = not report["schema_exists_after_drop"]
        report["dry_apply_performed"] = True
        validate_dry_apply_result(report)
    except Exception as exc:
        report["failed"].append(type(exc).__name__)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                cleanup_failed = True
            if drop_schema_after and schema is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"DROP SCHEMA IF EXISTS {formal_ddl_live_rehearsal.quote_identifier(schema)} CASCADE"
                        )
                        report["dropped"] = True
                        report["schema_exists_after_drop"] = formal_ddl_live_rehearsal.schema_exists(cur, schema)
                        report["cleanup_verified"] = not report["schema_exists_after_drop"]
                    conn.commit()
                except Exception:
                    cleanup_failed = True
        if cleanup_failed:
            report["failed"].append("cleanup_failed")
        validate_dry_apply_result(report)
    finally:
        if conn is not None:
            conn.close()

    return report


def build_skip_report(
    *,
    reason: str,
    schema_prefix: str = DEFAULT_SCHEMA_PREFIX,
    dsn_present: bool,
    driver_available: bool,
) -> dict[str, Any]:
    report = _base_dry_apply_report(
        schema=None,
        schema_prefix=formal_ddl_live_rehearsal.validate_schema_prefix(schema_prefix),
        dsn_present=dsn_present,
        driver_available=driver_available,
        ddl_lint_passed=False,
        artifact_valid=False,
        failed=[reason],
        limitations=["dry apply skipped before database connection"],
    )
    validate_dry_apply_result(report)
    return report


def insert_artifact_rows(cursor: Any, schema: str, artifact: Mapping[str, Any]) -> dict[str, int]:
    table_payloads = artifact.get("table_payloads", {})
    if not isinstance(table_payloads, Mapping):
        raise ValueError("artifact table_payloads must be a mapping")

    inserted: dict[str, int] = {table: 0 for table in EXPECTED_TABLES}
    for table_name in EXPECTED_TABLES:
        payload = table_payloads.get(table_name)
        if not isinstance(payload, Mapping):
            raise ValueError(f"artifact payload missing for table: {table_name}")
        rows = payload.get("rows", [])
        if not isinstance(rows, list):
            raise ValueError(f"artifact rows must be a list for table: {table_name}")
        if table_name == formal_ddl_rehearsal.SCHEMA_REHEARSAL_META_TABLE:
            inserted[table_name] = insert_schema_rehearsal_meta(cursor, schema, rows)
        else:
            inserted[table_name] = insert_phase_1_rows(cursor, schema, table_name, rows)
    return inserted


def insert_phase_1_rows(cursor: Any, schema: str, table_name: str, rows: Sequence[Mapping[str, Any]]) -> int:
    table_sql = quote_allowed_table(schema, table_name)
    statement = f"INSERT INTO {table_sql} (code, payload) VALUES (%s, %s::jsonb)"
    for index, row in enumerate(rows):
        code = stable_code(table_name, row, index)
        cursor.execute(statement, (code, json.dumps(dict(row), ensure_ascii=False, sort_keys=True)))
    return len(rows)


def insert_schema_rehearsal_meta(cursor: Any, schema: str, rows: Sequence[Mapping[str, Any]]) -> int:
    table_sql = quote_allowed_table(schema, formal_ddl_rehearsal.SCHEMA_REHEARSAL_META_TABLE)
    statement = (
        f"INSERT INTO {table_sql} "
        "(schema_name, draft_version, source_of_truth, payload) VALUES (%s, %s, %s, %s::jsonb)"
    )
    for row in rows:
        cursor.execute(
            statement,
            (
                schema,
                formal_schema_draft.DRAFT_VERSION,
                seed_artifact_renderer.SOURCE_OF_TRUTH,
                json.dumps(dict(row), ensure_ascii=False, sort_keys=True),
            ),
        )
    return len(rows)


def count_rows_by_table(cursor: Any, schema: str, table_names: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in table_names:
        cursor.execute(f"SELECT COUNT(*) FROM {quote_allowed_table(schema, table_name)}")
        row = cursor.fetchone()
        counts[table_name] = int(row[0]) if row else 0
    return counts


def build_expected_rows_by_table(artifact: Mapping[str, Any]) -> dict[str, int]:
    row_count_summary = artifact.get("row_count_summary", {})
    if not isinstance(row_count_summary, Mapping):
        return {table: 0 for table in EXPECTED_TABLES}
    return {
        table: int(row_count_summary.get(table, 0))
        for table in EXPECTED_TABLES
    }


def stable_code(table_name: str, row: Mapping[str, Any], index: int) -> str:
    record_key = row.get("record_key")
    if not record_key:
        record_key = f"row:{index}"
    return f"{table_name}:{record_key}"


def quote_allowed_table(schema: str, table_name: str) -> str:
    if table_name not in EXPECTED_TABLES:
        raise ValueError(f"table is not allowed for isolated seed dry apply: {table_name!r}")
    return (
        f"{formal_ddl_live_rehearsal.quote_identifier(schema)}."
        f"{formal_ddl_live_rehearsal.quote_identifier(table_name)}"
    )


def validate_dry_apply_result(report: dict[str, Any]) -> dict[str, Any]:
    failures = list(report.get("failed", []))
    if report["schema"] is None or not report["ddl_lint_passed"] or not report["artifact_valid"]:
        for flag, expected in NO_PRODUCTION_WRITE_FLAGS.items():
            if report.get(flag) is not expected:
                failures.append(f"{flag}_not_false")
        report["failed"] = sorted(set(str(item) for item in failures))
        report["passed"] = False
        assert_report_has_no_blocked_terms(report)
        return report

    if report["schema"] == report["schema_prefix"]:
        failures.append("random_isolated_schema_not_used")
    if not str(report["schema"]).startswith(f"{report['schema_prefix']}_"):
        failures.append("schema_prefix_mismatch")
    if not report["schema_created"]:
        failures.append("schema_not_created")
    if report["missing_expected_tables"]:
        failures.append("expected_tables_missing")
    if report["existing_forbidden_tables"]:
        failures.append("forbidden_tables_exist")
    if set(report["inserted_rows_by_table"]) - set(EXPECTED_TABLES):
        failures.append("non_phase_1_table_inserted")
    if report["actual_rows_by_table"] != report["expected_rows_by_table"]:
        failures.append("row_counts_do_not_match_artifact")
    if report["inserted_rows_by_table"].get(formal_ddl_rehearsal.SCHEMA_REHEARSAL_META_TABLE) != 1:
        failures.append("schema_rehearsal_meta_not_inserted")
    if report["dropped"] and report["schema_exists_after_drop"]:
        failures.append("schema_still_exists_after_drop")
    if report["dropped"] and not report["cleanup_verified"]:
        failures.append("cleanup_not_verified")
    for flag, expected in NO_PRODUCTION_WRITE_FLAGS.items():
        if report.get(flag) is not expected:
            failures.append(f"{flag}_not_false")
    report["failed"] = sorted(set(str(item) for item in failures))
    report["passed"] = not report["failed"]
    assert_report_has_no_blocked_terms(report)
    return report


def is_psycopg_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def assert_report_has_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = report_as_json(report).lower()
    for term in formal_schema_draft.BLOCKED_REPORT_TERMS:
        if term in text:
            raise AssertionError(f"report unexpectedly contains {term!r}")


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run an opt-in isolated seed dry apply prototype.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true", help="print the dry-apply contract report")
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--dry-apply", action="store_true", help="insert prototype seed rows into a random isolated schema")
    parser.add_argument("--schema-prefix", default=DEFAULT_SCHEMA_PREFIX, help="prefix for the random isolated schema")
    parser.add_argument(
        "--drop-schema-after",
        action="store_true",
        default=True,
        help="drop the random isolated schema after dry apply; enabled by default",
    )
    args = parser.parse_args(argv)

    try:
        if args.contract_report:
            report = build_contract_report()
            exit_code = 0
        elif args.check:
            report = check_environment()
            exit_code = 0
        else:
            report = run_dry_apply(args.schema_prefix, drop_schema_after=args.drop_schema_after)
            if not report["dsn_present"] or not report["driver_available"]:
                exit_code = 2
            else:
                exit_code = 0 if report["passed"] else 1
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return exit_code


def _base_dry_apply_report(
    *,
    schema: str | None,
    schema_prefix: str,
    dsn_present: bool,
    driver_available: bool,
    ddl_lint_passed: bool,
    artifact_valid: bool,
    failed: Sequence[str] | None = None,
    limitations: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "mode": "dry-apply",
        "dry_apply_version": DRY_APPLY_VERSION,
        "schema": schema,
        "schema_prefix": schema_prefix,
        "dsn_present": dsn_present,
        "driver_available": driver_available,
        "ddl_lint_passed": ddl_lint_passed,
        "artifact_valid": artifact_valid,
        "schema_created": False,
        "expected_tables": list(EXPECTED_TABLES),
        "existing_expected_tables": [],
        "missing_expected_tables": list(EXPECTED_TABLES),
        "forbidden_tables": list(FORBIDDEN_TABLES),
        "existing_forbidden_tables": [],
        "inserted_tables": [],
        "inserted_rows_by_table": {table: 0 for table in EXPECTED_TABLES},
        "expected_rows_by_table": {table: 0 for table in EXPECTED_TABLES},
        "actual_rows_by_table": {table: 0 for table in EXPECTED_TABLES},
        "row_count_matches": False,
        **NO_PRODUCTION_WRITE_FLAGS,
        "dry_apply_performed": False,
        "dropped": False,
        "schema_exists_after_drop": None,
        "cleanup_verified": False,
        "passed": False,
        "failed": list(failed or []),
        "limitations": list(limitations or LIMITATIONS),
    }


if __name__ == "__main__":
    raise SystemExit(main())
