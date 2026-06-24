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
    isolated_seed_dry_apply,
    seed_artifact_renderer,
    seed_artifact_validation_matrix,
)


REHEARSAL_VERSION = "isolated-seed-rollback-restore-v1"
PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
if PRIMARY_ENV_DSN != isolated_seed_dry_apply.PRIMARY_ENV_DSN:
    raise AssertionError("rollback/restore rehearsal DSN env must match isolated dry-apply")
DEFAULT_SCHEMA_PREFIX = "emperor_eval_seed_rollback"
EXPECTED_TABLES = isolated_seed_dry_apply.EXPECTED_TABLES
FORBIDDEN_TABLES = isolated_seed_dry_apply.FORBIDDEN_TABLES
RESTORE_REHEARSAL_MODE = "isolated_recreate_from_artifact"
VALIDATION_RULES = (
    "artifact_validation_passed_before_rehearsal",
    "dry_apply_passed_before_snapshot",
    "initial_snapshot_has_expected_tables",
    "initial_snapshot_has_no_forbidden_tables",
    "rollback_drop_verified",
    "restore_reapply_verified",
    "restored_snapshot_matches_initial",
    "final_cleanup_verified",
    "no_public_schema_touch",
    "no_production_schema_touch",
    "no_production_restore",
    "no_repo_artifact_written",
    "no_data_or_exports_written",
    "no_blocked_report_terms",
)
NO_PRODUCTION_WRITE_FLAGS = {
    "public_schema_touched": False,
    "production_schema_touched": False,
    "production_restore_performed": False,
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
    "does not restore production data",
)
BOUNDARIES = (
    "contract_report_and_check_do_not_connect",
    "contract_report_and_check_do_not_read_dotenv",
    "check_reads_only_primary_dsn_presence",
    "rehearsal_requires_explicit_opt_in",
    "rehearsal_reads_only_primary_dsn_environment_variable",
    "rehearsal_validates_schema_prefix_before_connect",
    "rehearsal_uses_random_isolated_schema",
    "rehearsal_validates_artifact_before_connect",
    "rehearsal_lints_ddl_before_connect",
    "rollback_drops_only_random_isolated_schema",
    "restore_rehearsal_recreates_only_random_isolated_schema",
)
LIMITATIONS = (
    "requires a caller-provided PostgreSQL DSN only in rehearse mode",
    "prototype artifact only",
    "restore rehearsal recreates isolated schema from artifact",
    "does not validate production migration readiness",
    "does not create phase 2 relationship tables",
    "does not create phase 3 downstream tables",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "rehearsal_version": REHEARSAL_VERSION,
        "status": "Proposed",
        "dsn_env": PRIMARY_ENV_DSN,
        "driver": "psycopg",
        "apply_mode": "explicit --rehearse only",
        "snapshot_strategy": {
            "source": "in-memory prototype seed artifact and manifest",
            "fields": [
                "schema",
                "expected_tables",
                "row_counts_by_table",
                "forbidden_tables_present",
                "artifact_sha256",
                "manifest_sha256",
                "source_of_truth",
            ],
            "excluded": ["DSN", "host", "password", "full SQL", "business conclusions"],
        },
        "rollback_strategy": "drop random isolated schema cascade and verify absence",
        "restore_strategy": RESTORE_REHEARSAL_MODE,
        "verification_rules": list(VALIDATION_RULES),
        "no_production_write_flags": dict(NO_PRODUCTION_WRITE_FLAGS),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "future_work": [
            "cutover readiness matrix in a later approved PR",
            "production migration remains out of scope",
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
        "will_restore_production": False,
    }


def run_rehearsal(
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
        report = _base_rehearsal_report(
            schema_prefix=schema_prefix,
            primary_schema=schema,
            restore_schema=schema,
            dsn_present=True,
            driver_available=True,
            artifact_valid=False,
            dry_apply_passed=False,
            failed=["dry_apply_passed_before_snapshot"],
            limitations=["DDL lint failed before database connection"],
        )
        validate_rehearsal_result(report)
        return report

    artifact = seed_artifact_renderer.build_seed_artifact(ROOT)
    manifest = seed_artifact_renderer.build_seed_manifest(artifact, ROOT)
    artifact_validation = seed_artifact_validation_matrix.validate_artifact_and_manifest(artifact, manifest)
    if not artifact_validation["passed"]:
        report = _base_rehearsal_report(
            schema_prefix=schema_prefix,
            primary_schema=schema,
            restore_schema=schema,
            dsn_present=True,
            driver_available=True,
            artifact_valid=False,
            dry_apply_passed=False,
            failed=["artifact_validation_passed_before_rehearsal", *artifact_validation["failed"]],
            limitations=["artifact validation failed before database connection"],
        )
        validate_rehearsal_result(report)
        return report

    report = _base_rehearsal_report(
        schema_prefix=schema_prefix,
        primary_schema=schema,
        restore_schema=schema,
        dsn_present=True,
        driver_available=True,
        artifact_valid=True,
        dry_apply_passed=True,
    )
    conn = None
    cleanup_failed = False
    try:
        import psycopg

        conn = psycopg.connect(dsn)
        with conn:
            with conn.cursor() as cur:
                _apply_seed_to_schema(cur, sql, schema, artifact)
                report["initial_snapshot"] = capture_snapshot(cur, schema, artifact, manifest)

                cur.execute(f"DROP SCHEMA IF EXISTS {formal_ddl_live_rehearsal.quote_identifier(schema)} CASCADE")
                report["rollback_performed"] = True
                report["schema_exists_after_rollback"] = formal_ddl_live_rehearsal.schema_exists(cur, schema)

                _apply_seed_to_schema(cur, sql, schema, artifact)
                report["restore_performed"] = True
                report["restored_snapshot"] = capture_snapshot(cur, schema, artifact, manifest)
                report["snapshot_matches_after_restore"] = compare_snapshots(
                    report["initial_snapshot"],
                    report["restored_snapshot"],
                )

                if drop_schema_after:
                    cur.execute(
                        f"DROP SCHEMA IF EXISTS {formal_ddl_live_rehearsal.quote_identifier(schema)} CASCADE"
                    )
                    report["final_drop_performed"] = True
                    report["schema_exists_after_final_drop"] = formal_ddl_live_rehearsal.schema_exists(cur, schema)
                    report["cleanup_verified"] = not report["schema_exists_after_final_drop"]
        validate_rehearsal_result(report)
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
                        report["final_drop_performed"] = True
                        report["schema_exists_after_final_drop"] = formal_ddl_live_rehearsal.schema_exists(cur, schema)
                        report["cleanup_verified"] = not report["schema_exists_after_final_drop"]
                    conn.commit()
                except Exception:
                    cleanup_failed = True
        if cleanup_failed:
            report["failed"].append("cleanup_failed")
        validate_rehearsal_result(report)
    finally:
        if conn is not None:
            conn.close()

    return report


def capture_snapshot(
    cursor: Any,
    schema: str,
    artifact: Mapping[str, Any],
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if manifest is None:
        manifest = seed_artifact_renderer.build_seed_manifest(artifact, ROOT)
    forbidden_present = formal_ddl_live_rehearsal.table_names_in_schema(
        cursor,
        schema,
        FORBIDDEN_TABLES,
    )
    return {
        "schema": schema,
        "expected_tables": list(EXPECTED_TABLES),
        "row_counts_by_table": isolated_seed_dry_apply.count_rows_by_table(cursor, schema, EXPECTED_TABLES),
        "forbidden_tables_present": forbidden_present,
        "artifact_sha256": seed_artifact_renderer.sha256_text(seed_artifact_renderer.canonical_json(artifact)),
        "manifest_sha256": seed_artifact_renderer.sha256_text(seed_artifact_renderer.canonical_json(manifest)),
        "source_of_truth": artifact.get("source_of_truth"),
    }


def compare_snapshots(initial: Mapping[str, Any], restored: Mapping[str, Any]) -> bool:
    return dict(initial) == dict(restored)


def build_skip_report(
    *,
    reason: str,
    schema_prefix: str = DEFAULT_SCHEMA_PREFIX,
    dsn_present: bool,
    driver_available: bool,
) -> dict[str, Any]:
    report = _base_rehearsal_report(
        schema_prefix=formal_ddl_live_rehearsal.validate_schema_prefix(schema_prefix),
        primary_schema=None,
        restore_schema=None,
        dsn_present=dsn_present,
        driver_available=driver_available,
        artifact_valid=False,
        dry_apply_passed=False,
        failed=[reason],
        limitations=["rollback restore rehearsal skipped before database connection"],
    )
    validate_rehearsal_result(report)
    return report


def validate_rehearsal_result(report: dict[str, Any]) -> dict[str, Any]:
    failures = list(report.get("failed", []))
    if report["primary_schema"] is None or not report["artifact_valid"] or not report["dry_apply_passed"]:
        for flag, expected in NO_PRODUCTION_WRITE_FLAGS.items():
            if report.get(flag) is not expected:
                failures.append(f"{flag}_not_false")
        report["failed"] = sorted(set(str(item) for item in failures))
        report["passed"] = False
        assert_report_has_no_blocked_terms(report)
        return report

    if report["primary_schema"] == report["schema_prefix"]:
        failures.append("random_isolated_schema_not_used")
    if not str(report["primary_schema"]).startswith(f"{report['schema_prefix']}_"):
        failures.append("schema_prefix_mismatch")
    initial_snapshot = report.get("initial_snapshot")
    restored_snapshot = report.get("restored_snapshot")
    if not _snapshot_has_expected_tables(initial_snapshot):
        failures.append("initial_snapshot_has_expected_tables")
    if _snapshot_has_forbidden_tables(initial_snapshot):
        failures.append("initial_snapshot_has_no_forbidden_tables")
    if not report["rollback_performed"] or report["schema_exists_after_rollback"] is not False:
        failures.append("rollback_drop_verified")
    if not report["restore_performed"] or not _snapshot_has_expected_tables(restored_snapshot):
        failures.append("restore_reapply_verified")
    if report["snapshot_matches_after_restore"] is not True:
        failures.append("restored_snapshot_matches_initial")
    if report["final_drop_performed"] and report["schema_exists_after_final_drop"] is not False:
        failures.append("final_cleanup_verified")
    if report["final_drop_performed"] and report["cleanup_verified"] is not True:
        failures.append("final_cleanup_verified")
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

    parser = argparse.ArgumentParser(description="Run an opt-in isolated seed rollback/restore rehearsal.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true", help="print the rollback/restore contract report")
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--rehearse", action="store_true", help="rehearse rollback/restore in a random isolated schema")
    parser.add_argument("--schema-prefix", default=DEFAULT_SCHEMA_PREFIX, help="prefix for the random isolated schema")
    parser.add_argument(
        "--drop-schema-after",
        action="store_true",
        default=True,
        help="drop the random isolated schema after restore rehearsal; enabled by default",
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
            report = run_rehearsal(args.schema_prefix, drop_schema_after=args.drop_schema_after)
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


def _apply_seed_to_schema(cursor: Any, sql: str, schema: str, artifact: Mapping[str, Any]) -> None:
    cursor.execute(sql)
    isolated_seed_dry_apply.insert_artifact_rows(cursor, schema, artifact)


def _base_rehearsal_report(
    *,
    schema_prefix: str,
    primary_schema: str | None,
    restore_schema: str | None,
    dsn_present: bool,
    driver_available: bool,
    artifact_valid: bool,
    dry_apply_passed: bool,
    failed: Sequence[str] | None = None,
    limitations: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "mode": "rehearse",
        "rehearsal_version": REHEARSAL_VERSION,
        "restore_rehearsal_mode": RESTORE_REHEARSAL_MODE,
        "schema_prefix": schema_prefix,
        "primary_schema": primary_schema,
        "restore_schema": restore_schema,
        "dsn_present": dsn_present,
        "driver_available": driver_available,
        "artifact_valid": artifact_valid,
        "dry_apply_passed": dry_apply_passed,
        "initial_snapshot": None,
        "rollback_performed": False,
        "schema_exists_after_rollback": None,
        "restore_performed": False,
        "restored_snapshot": None,
        "snapshot_matches_after_restore": False,
        "final_drop_performed": False,
        "schema_exists_after_final_drop": None,
        "cleanup_verified": False,
        **NO_PRODUCTION_WRITE_FLAGS,
        "passed": False,
        "failed": list(failed or []),
        "limitations": list(limitations or LIMITATIONS),
    }


def _snapshot_has_expected_tables(snapshot: Any) -> bool:
    if not isinstance(snapshot, Mapping):
        return False
    row_counts = snapshot.get("row_counts_by_table")
    return isinstance(row_counts, Mapping) and set(row_counts) == set(EXPECTED_TABLES)


def _snapshot_has_forbidden_tables(snapshot: Any) -> bool:
    return isinstance(snapshot, Mapping) and bool(snapshot.get("forbidden_tables_present"))


if __name__ == "__main__":
    raise SystemExit(main())
