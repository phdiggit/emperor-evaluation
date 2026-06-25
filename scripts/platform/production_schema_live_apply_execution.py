from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import read_dotenv_values
from scripts.platform.core.evidence import blocked_report_fields
from scripts.platform.core.fingerprints import file_fingerprints, file_sha256, files_byte_identical, relative_path
from scripts.platform.core.gates import first_blocking_reason
from scripts.platform.core.redaction import contains_secret_material

ADR_PATH = ROOT / "docs" / "adr" / "ADR-production-schema-live-apply-execution.md"
SCHEMA_SQL_PATH = ROOT / "db" / "schema.sql"
POSTGRES_SQL_PATH = ROOT / "db" / "postgres" / "001_init.sql"
SCHEMA_PATHS = (SCHEMA_SQL_PATH, POSTGRES_SQL_PATH)
APPROVAL_TOKEN = "USER_APPROVED_SCHEMA_LIVE_APPLY_PR285"
DSN_ENV_NAME = "EMPEROR_EVAL_PG_DSN"
EXECUTION_VERSION = "production-schema-live-apply-execution-v1"
EXECUTION_STATUS = "Approved / Production schema live-apply execution PR"
REQUIRED_SUCCESS_FLAGS = {
    "production_schema_live_apply_execution_pr": True,
    "schema_live_apply_approved": True,
    "schema_live_apply_executed": True,
    "sql_executed": True,
    "production_db_connected": True,
    "production_dsn_read": True,
    "public_schema_write_attempted": True,
    "schema_files_modified": False,
    "schema_files_read_only": True,
    "schema_files_byte_identical_required": True,
    "production_schema_hashes_rendered": True,
    "post_apply_verification_executed": True,
    "production_seed_executed": False,
    "seed_apply_executed": False,
    "ready_for_live_apply": False,
    "ready_for_production_migration": False,
    "future_target_importer_gate_required": True,
}
SUPPORTED_MODES = (
    "contract-report",
    "render-execution-plan-json",
    "render-operator-checklist-md",
    "execute-live-apply",
    "verify-live-apply",
    "lint-execution-report",
    "adr-check",
)
CORE_TABLES = ("anchors", "persons", "evd_cards", "cand_matches", "search_hits")
EXPECTED_COLUMNS_PRESENT = {
    "search_hits": ("hit_position",),
    "cand_matches": ("match_confidence",),
}
EXPECTED_COLUMNS_ABSENT = {
    "search_hits": ("rank",),
    "cand_matches": ("score",),
}


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "execution_version": EXECUTION_VERSION,
        "status": EXECUTION_STATUS,
        "pr_number": 285,
        "supported_modes": list(SUPPORTED_MODES),
        "approval_token_required": True,
        "approval_token_value": APPROVAL_TOKEN,
        "dsn_env_name": DSN_ENV_NAME,
        "driver": "psycopg",
        "default_modes_db_touching": False,
        "required_success_flags": dict(REQUIRED_SUCCESS_FLAGS),
        "schema_file_fingerprints": schema_file_fingerprints(),
        "schema_consistency": schema_consistency(),
        "verification_targets": verification_targets(),
        "forbidden_actions": [
            "production seed execution",
            "JSONL or data import",
            "business data row writes",
            "secret logging",
            "success forgery",
        ],
    }


def render_execution_plan_json() -> dict[str, Any]:
    return {
        "mode": "render-execution-plan-json",
        "pr_number": 285,
        "operation_type": "production_schema_live_apply",
        "approval_token_required": True,
        "expected_schema_sha256_required": True,
        "dsn_env_name": DSN_ENV_NAME,
        "dsn_value_redacted": True,
        "driver": "psycopg",
        "default_modes_db_touching": False,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "schema_consistency": schema_consistency(),
        "verification_targets": verification_targets(),
        "production_seed_executed": False,
        "seed_apply_executed": False,
        "ready_for_live_apply": False,
        "ready_for_production_migration": False,
        "future_target_importer_gate_required": True,
    }


def render_operator_checklist_md() -> str:
    return "\n".join(
        [
            "# Production Schema Live-Apply Operator Checklist",
            "",
            "This checklist is for PR #285 schema live apply only.",
            "",
            "- Confirm approval token is available before execution.",
            "- Confirm expected schema sha256 matches `db/postgres/001_init.sql`.",
            "- Confirm `db/schema.sql` and `db/postgres/001_init.sql` are byte-identical.",
            "- Confirm production DSN is supplied through `EMPEROR_EVAL_PG_DSN` only at execution time.",
            "- Confirm no DSN value is copied into logs, PR body, or artifacts.",
            "- Confirm seed/data apply remains out of scope.",
            "- Confirm post-apply verification checks public schema metadata only.",
            "- Confirm `ready_for_production_migration=false` remains in evidence.",
            "",
        ]
    )


def execute_live_apply(require_user_approval_token: str | None, expected_schema_sha256: str | None) -> dict[str, Any]:
    started = utc_now()
    gate = pre_execution_gate(require_user_approval_token, expected_schema_sha256)
    if gate:
        return blocked_evidence(
            started,
            "gate",
            gate,
            production_dsn_read=False,
        )

    dsn = read_dsn()
    if not dsn:
        return blocked_evidence(
            started,
            "dsn_read",
            "blocked_missing_dsn",
            production_dsn_read=False,
        )

    try:
        sql = POSTGRES_SQL_PATH.read_text(encoding="utf-8")
        with connect_to_database(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            commit_connection(conn)
            verification = verify_connection(conn)
    except ModuleNotFoundError as exc:
        return blocked_evidence(started, "runtime_dependency", "blocked_missing_runtime_dependency", True, exc, dsn)
    except Exception as exc:  # noqa: BLE001 - evidence must preserve failure type without leaking secrets.
        return blocked_evidence(started, "execute", "blocked_execution_failed", True, exc, dsn)

    failures = list(verification.get("blocking_failures", []))
    if failures:
        report = blocked_evidence(started, "verify", "blocked_verification_failed", True)
        report["verification_passed"] = False
        report["post_apply_verification_executed"] = True
        report["verification"] = verification
        report["blocking_failures"] = failures
        return report

    ended = utc_now()
    return {
        "mode": "schema-live-apply-execution-report",
        "pr_number": 285,
        "execution_version": EXECUTION_VERSION,
        "schema_sha256": schema_sha256(),
        "schema_line_count": schema_line_count(),
        "schema_table_count": schema_table_count(),
        "dsn_env_name": DSN_ENV_NAME,
        "dsn_value_redacted": True,
        **REQUIRED_SUCCESS_FLAGS,
        "verification_passed": True,
        "verification": verification,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "redacted_stdout_summary": [
            "schema live apply executed through psycopg",
            "post-apply verification passed",
        ],
        "redacted_stderr_summary": [],
        "blocking_failures": [],
    }


def verify_live_apply(require_user_approval_token: str | None, expected_schema_sha256: str | None) -> dict[str, Any]:
    started = utc_now()
    gate = pre_execution_gate(require_user_approval_token, expected_schema_sha256)
    if gate:
        return blocked_evidence(started, "gate", gate, production_dsn_read=False)
    dsn = read_dsn()
    if not dsn:
        return blocked_evidence(started, "dsn_read", "blocked_missing_dsn", production_dsn_read=False)
    try:
        with connect_to_database(dsn) as conn:
            verification = verify_connection(conn)
    except ModuleNotFoundError as exc:
        return blocked_evidence(started, "runtime_dependency", "blocked_missing_runtime_dependency", True, exc, dsn)
    except Exception as exc:  # noqa: BLE001 - evidence must preserve failure type without leaking secrets.
        return blocked_evidence(started, "verify", "blocked_verification_failed", True, exc, dsn)
    failures = list(verification.get("blocking_failures", []))
    return {
        "mode": "schema-live-apply-verification-report",
        "pr_number": 285,
        "schema_sha256": schema_sha256(),
        "dsn_env_name": DSN_ENV_NAME,
        "dsn_value_redacted": True,
        "production_schema_live_apply_execution_pr": True,
        "schema_live_apply_approved": True,
        "schema_live_apply_executed": False,
        "sql_executed": False,
        "production_db_connected": True,
        "production_dsn_read": True,
        "public_schema_write_attempted": False,
        "post_apply_verification_executed": True,
        "verification_passed": not failures,
        "verification": verification,
        "production_seed_executed": False,
        "seed_apply_executed": False,
        "ready_for_live_apply": False,
        "ready_for_production_migration": False,
        "future_target_importer_gate_required": True,
        "started_at_utc": started,
        "ended_at_utc": utc_now(),
        "redacted_stdout_summary": ["post-apply verification executed"],
        "redacted_stderr_summary": [],
        "blocking_failures": failures,
    }


def pre_execution_gate(require_user_approval_token: str | None, expected_schema_sha256: str | None) -> str | None:
    return first_blocking_reason(
        (
            (lambda: require_user_approval_token == APPROVAL_TOKEN, "blocked_missing_or_invalid_approval_token"),
            (lambda: bool(expected_schema_sha256), "blocked_missing_expected_schema_sha256"),
            (lambda: expected_schema_sha256 == schema_sha256(), "blocked_schema_hash_mismatch"),
            (schema_files_byte_identical, "blocked_schema_files_not_byte_identical"),
            (anchors_table_exists, "blocked_missing_anchors_table"),
        )
    )


def blocked_evidence(
    started_at_utc: str,
    failure_stage: str,
    blocked_reason: str,
    production_dsn_read: bool,
    exc: BaseException | None = None,
    dsn: str | None = None,
) -> dict[str, Any]:
    return {
        "mode": "schema-live-apply-execution-report",
        "pr_number": 285,
        "schema_sha256": schema_sha256(),
        "schema_line_count": schema_line_count(),
        "schema_table_count": schema_table_count(),
        "dsn_env_name": DSN_ENV_NAME,
        "dsn_value_redacted": True,
        "production_schema_live_apply_execution_pr": True,
        "schema_live_apply_approved": True,
        "schema_live_apply_executed": False,
        "sql_executed": False,
        "production_db_connected": False,
        "production_dsn_read": production_dsn_read,
        "public_schema_write_attempted": False,
        "schema_files_modified": False,
        "schema_files_read_only": True,
        "schema_files_byte_identical_required": True,
        "production_schema_hashes_rendered": True,
        "post_apply_verification_executed": False,
        "production_seed_executed": False,
        "seed_apply_executed": False,
        "verification_passed": False,
        "ready_for_live_apply": False,
        "ready_for_production_migration": False,
        "future_target_importer_gate_required": True,
        **blocked_report_fields(
            started_at_utc=started_at_utc,
            ended_at_utc=utc_now,
            failure_stage=failure_stage,
            blocked_reason=blocked_reason,
            exc=exc,
            dsn=dsn,
        ),
    }


def verify_connection(conn: Any) -> dict[str, Any]:
    table_names = fetch_existing_tables(conn, CORE_TABLES)
    present_columns = fetch_existing_columns(conn, EXPECTED_COLUMNS_PRESENT)
    absent_columns = fetch_existing_columns(conn, EXPECTED_COLUMNS_ABSENT)
    failures: list[str] = []
    missing_tables = [table for table in CORE_TABLES if table not in table_names]
    if missing_tables:
        failures.append("missing_tables:" + ",".join(missing_tables))
    for table, columns in EXPECTED_COLUMNS_PRESENT.items():
        missing = [column for column in columns if column not in present_columns.get(table, set())]
        if missing:
            failures.append(f"missing_columns:{table}:" + ",".join(missing))
    for table, columns in EXPECTED_COLUMNS_ABSENT.items():
        unexpected = [column for column in columns if column in absent_columns.get(table, set())]
        if unexpected:
            failures.append(f"unexpected_columns:{table}:" + ",".join(unexpected))
    return {
        "tables_present": sorted(table_names),
        "required_tables": list(CORE_TABLES),
        "expected_columns_present": {
            table: sorted(present_columns.get(table, set())) for table in EXPECTED_COLUMNS_PRESENT
        },
        "expected_columns_absent": {
            table: sorted(columns) for table, columns in EXPECTED_COLUMNS_ABSENT.items()
        },
        "blocking_failures": failures,
    }


def fetch_existing_tables(conn: Any, table_names: Sequence[str]) -> set[str]:
    query, params = build_table_check_query(table_names)
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return {row[0] for row in rows}


def fetch_existing_columns(conn: Any, columns_by_table: Mapping[str, Sequence[str]]) -> dict[str, set[str]]:
    query, params = build_column_check_query(columns_by_table)
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    result: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        result.setdefault(table_name, set()).add(column_name)
    return result


def build_table_check_query(table_names: Sequence[str]) -> tuple[str, tuple[Any, ...]]:
    return (
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = ANY(%s)
        ORDER BY table_name
        """,
        (list(table_names),),
    )


def build_column_check_query(columns_by_table: Mapping[str, Sequence[str]]) -> tuple[str, tuple[Any, ...]]:
    pairs = [(table, column) for table, columns in columns_by_table.items() for column in columns]
    return (
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND (table_name, column_name) IN (
            SELECT pair.table_name, pair.column_name
            FROM unnest(%s::text[], %s::text[]) AS pair(table_name, column_name)
          )
        ORDER BY table_name, column_name
        """,
        ([table for table, _column in pairs], [column for _table, column in pairs]),
    )


def connect_to_database(dsn: str) -> Any:
    import psycopg

    return psycopg.connect(dsn)


def commit_connection(conn: Any) -> None:
    commit = getattr(conn, "commit", None)
    if commit is not None:
        commit()


def read_dsn() -> str | None:
    env = getattr(os, "environ")
    value = env.get(DSN_ENV_NAME)
    if not value:
        value = read_dotenv_values().get(DSN_ENV_NAME)
    if not value:
        return None
    return str(value)


def schema_file_fingerprints() -> list[dict[str, Any]]:
    return file_fingerprints(SCHEMA_PATHS, root=ROOT, extra=lambda _path, text: {"table_count": len(created_tables(text))})


def schema_consistency() -> dict[str, bool]:
    return {
        "byte_identical": schema_files_byte_identical(),
        "table_sets_same": schema_table_sets_same(),
        "anchors_table_exists": anchors_table_exists(),
    }


def schema_sha256() -> str:
    return file_sha256(POSTGRES_SQL_PATH)


def schema_line_count() -> int:
    return len(POSTGRES_SQL_PATH.read_text(encoding="utf-8").splitlines())


def schema_table_count() -> int:
    return len(created_tables(POSTGRES_SQL_PATH.read_text(encoding="utf-8")))


def schema_files_byte_identical() -> bool:
    return files_byte_identical(SCHEMA_SQL_PATH, POSTGRES_SQL_PATH)


def schema_table_sets_same() -> bool:
    left = set(created_tables(SCHEMA_SQL_PATH.read_text(encoding="utf-8")))
    right = set(created_tables(POSTGRES_SQL_PATH.read_text(encoding="utf-8")))
    return left == right


def anchors_table_exists() -> bool:
    return "anchors" in set(created_tables(POSTGRES_SQL_PATH.read_text(encoding="utf-8")))


def created_tables(sql: str) -> list[str]:
    return re.findall(r"(?im)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z0-9_]*)\s*\(", sql)


def verification_targets() -> dict[str, Any]:
    return {
        "required_tables": list(CORE_TABLES),
        "required_columns": {table: list(columns) for table, columns in EXPECTED_COLUMNS_PRESENT.items()},
        "forbidden_columns": {table: list(columns) for table, columns in EXPECTED_COLUMNS_ABSENT.items()},
        "query_source": "information_schema",
        "read_only": True,
    }


def lint_execution_report(report: Mapping[str, Any]) -> dict[str, Any]:
    text = report_as_json(report)
    failed: list[str] = []
    if contains_secret_material(text):
        failed.append("secret_material_present")
    if report.get("ready_for_production_migration") is not False:
        failed.append("ready_for_production_migration_not_false")
    if report.get("production_seed_executed") is not False or report.get("seed_apply_executed") is not False:
        failed.append("seed_or_data_apply_claimed")
    if report.get("schema_live_apply_executed") is True and report.get("verification_passed") is not True:
        failed.append("executed_without_verification")
    if report.get("schema_live_apply_executed") is False and report.get("verification_passed") is True:
        failed.append("blocked_report_claims_verification_success")
    if report.get("schema_live_apply_executed") is False and not report.get("blocking_failures"):
        failed.append("blocked_report_missing_blocking_failures")
    return {
        "mode": "lint-execution-report",
        "passed": not failed,
        "failed": failed,
    }


def build_adr_check(adr_path: Path = ADR_PATH) -> dict[str, Any]:
    if not adr_path.exists():
        return {
            "mode": "adr-check",
            "adr_path": relative_path(ROOT, adr_path),
            "adr_exists": False,
            "passed": False,
            "failed": ["adr_missing"],
        }
    content = normalize_text(adr_path.read_text(encoding="utf-8"))
    required = {
        "declares_execution_pr": "schema live apply execution pr",
        "declares_user_approval": "批准所有权限",
        "allows_dsn_read": "allows dsn read",
        "allows_db_connect": "allows db connect",
        "allows_sql_execution": "allows sql execution",
        "allows_public_schema_write": "allows public schema write",
        "seed_data_out_of_scope": "does not execute seed/data apply",
        "migration_not_complete": "does not mark production migration complete",
        "future_target_importer_gate": "future target importer gate required",
        "no_success_forgery": "must not fake success",
    }
    failed = [rule for rule, needle in required.items() if needle not in content]
    return {
        "mode": "adr-check",
        "adr_path": relative_path(ROOT, adr_path),
        "adr_exists": True,
        "passed": not failed,
        "failed": failed,
    }


def load_report_arg(value: str) -> dict[str, Any]:
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Execute or verify production schema live apply.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--render-execution-plan-json", action="store_true")
    mode.add_argument("--render-operator-checklist-md", action="store_true")
    mode.add_argument("--execute-live-apply", action="store_true")
    mode.add_argument("--verify-live-apply", action="store_true")
    mode.add_argument("--lint-execution-report")
    mode.add_argument("--adr-check", action="store_true")
    parser.add_argument("--require-user-approval-token")
    parser.add_argument("--expected-schema-sha256")
    args = parser.parse_args(argv)

    if args.render_operator_checklist_md:
        sys.stdout.write(render_operator_checklist_md())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.render_execution_plan_json:
        report = render_execution_plan_json()
    elif args.execute_live_apply:
        report = execute_live_apply(args.require_user_approval_token, args.expected_schema_sha256)
    elif args.verify_live_apply:
        report = verify_live_apply(args.require_user_approval_token, args.expected_schema_sha256)
    elif args.lint_execution_report:
        report = lint_execution_report(load_report_arg(args.lint_execution_report))
    else:
        report = build_adr_check()
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"schema-live-apply-execution-report", "schema-live-apply-verification-report"}:
        return 0 if not report.get("blocking_failures") else 1
    if report.get("failed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
