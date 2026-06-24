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
)


PREFLIGHT_VERSION = "seed-artifact-db-preflight-v1"
PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
DEFAULT_SCHEMA_PREFIX = "emperor_eval_seed_preflight"
EXPECTED_SCHEMA_TABLES = (
    *formal_schema_draft.PHASE_1_BASE_TABLES,
    formal_ddl_rehearsal.SCHEMA_REHEARSAL_META_TABLE,
)
FORBIDDEN_SCHEMA_TABLES = (
    *formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES,
    *formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES,
)
PREFLIGHT_CHECKS = (
    "ddl_lint_passed_before_connect",
    "random_isolated_schema_used",
    "schema_created",
    "expected_schema_tables_exist",
    "forbidden_schema_tables_absent",
    "artifact_tables_match_expected_schema_tables",
    "artifact_has_no_phase_2_tables",
    "artifact_has_no_phase_3_tables",
    "artifact_blocked_tables_include_phase_2_3",
    "row_count_plan_is_dry_only",
    "no_seed_application_performed",
    "cleanup_verified",
    "no_blocked_report_terms",
)
NO_SEED_FLAGS = {
    "seed_application_performed": False,
    "insert_performed": False,
    "copy_performed": False,
    "upsert_performed": False,
    "db_row_write_performed": False,
}
NON_GOALS = (
    "does not modify canonical JSONL",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not read .env",
    "does not use shell database clients",
    "does not write production target tables",
    "does not write public schema objects",
    "does not apply seed artifacts",
    "does not write repository artifact files",
)
STRICT_BOUNDARIES = (
    "contract_report_and_check_do_not_connect",
    "contract_report_and_check_do_not_read_dotenv",
    "check_reads_only_primary_dsn_presence",
    "preflight_requires_explicit_opt_in",
    "preflight_reads_only_primary_dsn_environment_variable",
    "preflight_uses_random_isolated_schema",
    "preflight_reuses_formal_ddl_rehearsal_render_sql",
    "preflight_reuses_seed_artifact_renderer_in_memory",
    "artifact_never_enters_database",
    "row_count_plan_is_dry_estimate_only",
    "no_production_target_table_writes",
)
LIMITATIONS = (
    "requires a caller-provided PostgreSQL DSN only in preflight mode",
    "prototype artifact only",
    "row counts are dry estimates from the rendered artifact",
    "does not validate production migration readiness",
    "does not create phase 2 relationship tables",
    "does not create phase 3 downstream tables",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "preflight_version": PREFLIGHT_VERSION,
        "status": "Proposed",
        "dsn_env": PRIMARY_ENV_DSN,
        "driver": "psycopg",
        "apply_mode": "explicit --preflight only",
        "schema_prefix_default": DEFAULT_SCHEMA_PREFIX,
        "expected_schema_tables": list(EXPECTED_SCHEMA_TABLES),
        "forbidden_schema_tables": list(FORBIDDEN_SCHEMA_TABLES),
        "artifact_expected_tables": list(EXPECTED_SCHEMA_TABLES),
        "preflight_checks": list(PREFLIGHT_CHECKS),
        "non_goals": list(NON_GOALS),
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "future_work": [
            "isolated seed dry apply prototype in a later approved PR",
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
        "will_apply_seed": False,
        "default_tests_require_postgres": False,
    }


def run_preflight(
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
        report = _base_preflight_report(
            schema=schema,
            schema_prefix=schema_prefix,
            dsn_present=True,
            driver_available=True,
            ddl_lint_passed=False,
            failed=["ddl_lint_failed_before_connect"],
            limitations=["DDL lint failed before database connection"],
        )
        validate_preflight_result(report)
        return report

    artifact = seed_artifact_renderer.build_seed_artifact(ROOT)
    artifact_payload_tables = sorted(str(name) for name in artifact.get("table_payloads", {}))
    artifact_blocked_tables = sorted(str(name) for name in artifact.get("blocked_seed_tables", ()))
    row_count_plan = build_row_count_plan(artifact)

    report = _base_preflight_report(
        schema=schema,
        schema_prefix=schema_prefix,
        dsn_present=True,
        driver_available=True,
        ddl_lint_passed=True,
    )
    report.update(
        {
            "artifact_payload_tables": artifact_payload_tables,
            "artifact_extra_tables": sorted(set(artifact_payload_tables) - set(EXPECTED_SCHEMA_TABLES)),
            "artifact_missing_tables": sorted(set(EXPECTED_SCHEMA_TABLES) - set(artifact_payload_tables)),
            "artifact_blocked_tables": artifact_blocked_tables,
            "row_count_plan": row_count_plan,
        }
    )

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
                    EXPECTED_SCHEMA_TABLES,
                )
                existing_forbidden = formal_ddl_live_rehearsal.table_names_in_schema(
                    cur,
                    schema,
                    FORBIDDEN_SCHEMA_TABLES,
                )
                report["existing_expected_schema_tables"] = existing_expected
                report["missing_expected_schema_tables"] = [
                    table for table in EXPECTED_SCHEMA_TABLES if table not in set(existing_expected)
                ]
                report["existing_forbidden_schema_tables"] = existing_forbidden
                if drop_schema_after:
                    cur.execute(
                        f"DROP SCHEMA IF EXISTS {formal_ddl_live_rehearsal.quote_identifier(schema)} CASCADE"
                    )
                    report["dropped"] = True
                    report["schema_exists_after_drop"] = formal_ddl_live_rehearsal.schema_exists(cur, schema)
                    report["cleanup_verified"] = not report["schema_exists_after_drop"]
        validate_preflight_result(report)
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
        validate_preflight_result(report)
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
    report = _base_preflight_report(
        schema=None,
        schema_prefix=formal_ddl_live_rehearsal.validate_schema_prefix(schema_prefix),
        dsn_present=dsn_present,
        driver_available=driver_available,
        ddl_lint_passed=False,
        failed=[reason],
        limitations=["preflight skipped before database connection"],
    )
    validate_preflight_result(report)
    return report


def validate_preflight_result(report: dict[str, Any]) -> dict[str, Any]:
    failures = list(report.get("failed", []))
    if report["schema"] is None or not report["ddl_lint_passed"]:
        if any(report[field] is not False for field in NO_SEED_FLAGS):
            failures.append("seed_application_flag_not_false")
        report["failed"] = sorted(set(str(item) for item in failures))
        report["passed"] = False
        assert_report_has_no_blocked_terms(report)
        return report

    if report["schema"] is not None and report["schema"] == report["schema_prefix"]:
        failures.append("random_isolated_schema_not_used")
    if report["schema"] is not None and not str(report["schema"]).startswith(f"{report['schema_prefix']}_"):
        failures.append("schema_prefix_mismatch")
    if report["ddl_lint_passed"] and not report["schema_created"]:
        failures.append("schema_not_created")
    if report["missing_expected_schema_tables"]:
        failures.append("expected_schema_tables_missing")
    if report["existing_forbidden_schema_tables"]:
        failures.append("forbidden_schema_tables_exist")
    if report["artifact_extra_tables"] or report["artifact_missing_tables"]:
        failures.append("artifact_tables_do_not_match_expected_schema_tables")
    if set(report["artifact_payload_tables"]) & set(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES):
        failures.append("artifact_contains_phase_2_tables")
    if set(report["artifact_payload_tables"]) & set(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES):
        failures.append("artifact_contains_phase_3_tables")
    if not set(FORBIDDEN_SCHEMA_TABLES) <= set(report["artifact_blocked_tables"]):
        failures.append("artifact_blocked_tables_missing_phase_2_3")
    if not report["row_count_plan"]["dry_only"]:
        failures.append("row_count_plan_not_dry_only")
    if any(report[field] is not False for field in NO_SEED_FLAGS):
        failures.append("seed_application_flag_not_false")
    if report["dropped"] and report["schema_exists_after_drop"]:
        failures.append("schema_still_exists_after_drop")
    if report["dropped"] and not report["cleanup_verified"]:
        failures.append("cleanup_not_verified")
    report["failed"] = sorted(set(str(item) for item in failures))
    report["passed"] = not report["failed"]
    assert_report_has_no_blocked_terms(report)
    return report


def build_row_count_plan(artifact: Mapping[str, Any]) -> dict[str, Any]:
    row_count_summary = artifact.get("row_count_summary", {})
    if not isinstance(row_count_summary, Mapping):
        row_count_summary = {}
    payloads = artifact.get("table_payloads", {})
    dry_flags = []
    if isinstance(payloads, Mapping):
        dry_flags = [
            bool(payload.get("dry_estimate"))
            for payload in payloads.values()
            if isinstance(payload, Mapping)
        ]
    return {
        "dry_only": bool(dry_flags) and all(dry_flags),
        "table_row_counts": dict(row_count_summary),
        "total_estimated_rows": sum(
            int(value)
            for value in row_count_summary.values()
            if isinstance(value, int)
        ),
        "db_row_write_performed": False,
    }


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

    parser = argparse.ArgumentParser(description="Run an opt-in seed artifact DB preflight contract.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true", help="print the preflight contract report")
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--preflight", action="store_true", help="run the isolated DB preflight")
    parser.add_argument("--schema-prefix", default=DEFAULT_SCHEMA_PREFIX, help="prefix for the random isolated schema")
    parser.add_argument(
        "--drop-schema-after",
        action="store_true",
        default=True,
        help="drop the random isolated schema after preflight; enabled by default",
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
            report = run_preflight(args.schema_prefix, drop_schema_after=args.drop_schema_after)
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


def _base_preflight_report(
    *,
    schema: str | None,
    schema_prefix: str,
    dsn_present: bool,
    driver_available: bool,
    ddl_lint_passed: bool,
    failed: Sequence[str] | None = None,
    limitations: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "mode": "preflight",
        "preflight_version": PREFLIGHT_VERSION,
        "schema": schema,
        "schema_prefix": schema_prefix,
        "dsn_present": dsn_present,
        "driver_available": driver_available,
        "ddl_lint_passed": ddl_lint_passed,
        "schema_created": False,
        "expected_schema_tables": list(EXPECTED_SCHEMA_TABLES),
        "existing_expected_schema_tables": [],
        "missing_expected_schema_tables": list(EXPECTED_SCHEMA_TABLES),
        "forbidden_schema_tables": list(FORBIDDEN_SCHEMA_TABLES),
        "existing_forbidden_schema_tables": [],
        "artifact_expected_tables": list(EXPECTED_SCHEMA_TABLES),
        "artifact_payload_tables": [],
        "artifact_extra_tables": [],
        "artifact_missing_tables": list(EXPECTED_SCHEMA_TABLES),
        "artifact_blocked_tables": [],
        "row_count_plan": {
            "dry_only": True,
            "table_row_counts": {},
            "total_estimated_rows": 0,
            "db_row_write_performed": False,
        },
        **NO_SEED_FLAGS,
        "dropped": False,
        "schema_exists_after_drop": None,
        "cleanup_verified": False,
        "passed": False,
        "failed": list(failed or []),
        "limitations": list(limitations or LIMITATIONS),
    }


if __name__ == "__main__":
    raise SystemExit(main())
