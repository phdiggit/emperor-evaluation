from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import read_dotenv_values
from scripts.platform.core.evidence import blocked_report_fields
from scripts.platform.core.fingerprints import (
    file_fingerprints,
    file_sha256,
    files_byte_identical,
    relative_path as core_relative_path,
    stable_json_sha256,
)
from scripts.platform.core.gates import first_blocking_reason
from scripts.platform.core.redaction import contains_secret_material, redact_text


ADR_PATH = ROOT / "docs" / "adr" / "ADR-production-seed-data-apply-execution.md"
SCHEMA_SQL_PATH = ROOT / "db" / "schema.sql"
POSTGRES_SQL_PATH = ROOT / "db" / "postgres" / "001_init.sql"
SCHEMA_PATHS = (SCHEMA_SQL_PATH, POSTGRES_SQL_PATH)
CANONICAL_DATA_ROOT = ROOT / "data"
DATA_ROOTS = (CANONICAL_DATA_ROOT,)
EXCLUDED_DISCOVERY_ROOTS = (ROOT / "data" / "batches", ROOT / "archive" / "data")
APPROVAL_TOKEN = "USER_APPROVED_PRODUCTION_SEED_DATA_APPLY_PR286"
DSN_ENV_NAME = "EMPEROR_EVAL_PG_DSN"
EXECUTION_VERSION = "production-seed-data-apply-audit-scaffold-v2"
EXECUTION_STATUS = "Audit-only / Canonical seed manifest discovery and import audit scaffold"
BLOCKED_MISSING_SEED_MANIFEST = "blocked_missing_seed_manifest"
BLOCKED_TARGET_IMPORTER_NOT_IMPLEMENTED = "blocked_target_business_importer_not_implemented_epic1"
REQUIRED_SCHEMA_LIVE_TABLES = ("imports", "import_rows", "persons", "src_docs", "passages", "evd_cards")
AUDIT_IMPORT_STATUS = "dry_run"
AUDIT_IMPORT_ROW_STATUS = "skipped"
MANIFEST_HASH_FIELDS = (
    "manifest_version",
    "manifest_kind",
    "approval_status",
    "approved_for_execution",
    "canonical_seed_source_identified",
    "candidate_source_count",
    "candidate_sources",
    "source_roots",
    "redaction",
    "operator_note",
)
SUPPORTED_MODES = (
    "contract-report",
    "render-seed-manifest-json",
    "render-execution-plan-json",
    "render-operator-checklist-md",
    "execute-seed-data-apply",
    "verify-seed-data-apply",
    "lint-execution-report",
    "adr-check",
)
SUCCESS_FLAGS_FALSE = {
    "seed_data_apply_executed": False,
    "production_data_rows_written": False,
    "import_audit_written": False,
    "verification_passed": False,
    "ready_for_production_migration": False,
}
PERMANENTLY_BLOCKED_SUCCESS_FLAGS = {
    "seed_data_apply_executed": False,
    "production_data_rows_written": False,
    "verification_passed": False,
    "ready_for_production_migration": False,
}


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "pr_number": 286,
        "execution_version": EXECUTION_VERSION,
        "status": EXECUTION_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "approval_token_required": True,
        "approval_token_value": APPROVAL_TOKEN,
        "schema_hash_required": True,
        "seed_manifest_hash_required": True,
        "dsn_env_name": DSN_ENV_NAME,
        "driver": "psycopg",
        "default_modes_db_touching": False,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "seed_manifest": build_seed_manifest(),
        "permanently_blocked_success_flags": dict(PERMANENTLY_BLOCKED_SUCCESS_FLAGS),
        "safe_blocked_flags": dict(SUCCESS_FLAGS_FALSE),
        "audit_scaffold_only": True,
        "audit_tables_are_not_business_targets": ["imports", "import_rows"],
        "target_business_importer_deferred_to": "Epic 1",
        "forbidden_actions": [
            "secret logging",
            "schema file modification",
            "source data modification",
            "success forgery",
            "invented seed rows",
            "business target table write claims",
        ],
    }


def build_seed_manifest() -> dict[str, Any]:
    candidates = discover_candidate_seed_files()
    excluded = discover_excluded_seed_files()
    manifest: dict[str, Any] = {
        "manifest_version": 1,
        "manifest_kind": "production_seed_data_apply",
        "approval_status": BLOCKED_MISSING_SEED_MANIFEST,
        "approved_for_execution": False,
        "canonical_seed_source_identified": False,
        "candidate_source_count": len(candidates),
        "candidate_sources": candidates,
        "source_roots": [relative_path(path) for path in DATA_ROOTS if path.exists()],
        "excluded_discovery_source_count": len(excluded),
        "excluded_discovery_sources": excluded,
        "excluded_source_roots": [relative_path(path) for path in EXCLUDED_DISCOVERY_ROOTS if path.exists()],
        "excluded_discovery_note": (
            "Batch and archive JSONL files are discovery-only and are not part of the "
            "canonical seed manifest envelope or manifest_sha256."
        ),
        "redaction": {
            "contains_row_payloads": False,
            "contains_secret_material": False,
        },
        "operator_note": (
            "No single canonical production seed/data manifest has been identified. "
            "Execution must fail closed until a later PR approves a specific manifest."
        ),
    }
    manifest["manifest_sha256"] = stable_sha256(seed_manifest_hash_basis(manifest))
    return manifest


def discover_candidate_seed_files() -> list[dict[str, Any]]:
    paths: list[Path] = []
    for root in DATA_ROOTS:
        if not root.exists():
            continue
        paths.extend(path for path in sorted(root.glob("*.jsonl")) if path.is_file())
    return seed_file_records(paths)


def discover_excluded_seed_files() -> list[dict[str, Any]]:
    paths: list[Path] = []
    for root in EXCLUDED_DISCOVERY_ROOTS:
        if not root.exists():
            continue
        paths.extend(path for path in sorted(root.rglob("*.jsonl")) if path.is_file())
    return seed_file_records(paths)


def seed_file_records(paths: Sequence[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        records.append(
            {
                "path": relative_path(path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw),
                "line_count": count_non_empty_lines(text),
                "detected_logical_kind": detect_logical_kind(path),
                "read_only": True,
            }
        )
    return records


def seed_manifest_hash_basis(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {field: manifest[field] for field in MANIFEST_HASH_FIELDS if field in manifest}


def render_execution_plan_json() -> dict[str, Any]:
    manifest = build_seed_manifest()
    return {
        "mode": "render-execution-plan-json",
        "pr_number": 286,
        "operation_type": "canonical_seed_manifest_discovery_import_audit_scaffold",
        "approval_token_required": True,
        "expected_schema_sha256_required": True,
        "expected_seed_manifest_sha256_required": True,
        "schema_live_apply_dependency": "reverify_before_execution",
        "dsn_env_name": DSN_ENV_NAME,
        "dsn_value_redacted": True,
        "driver": "psycopg",
        "default_modes_db_touching": False,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "seed_manifest_sha256": manifest["manifest_sha256"],
        "seed_manifest_approved_for_execution": manifest["approved_for_execution"],
        "audit_scaffold_only": True,
        "target_business_table_writes_executed": False,
        "target_business_importer_deferred_to": "Epic 1",
        "blocked_reason_if_executed_now": None
        if manifest["approved_for_execution"]
        else BLOCKED_MISSING_SEED_MANIFEST,
        **SUCCESS_FLAGS_FALSE,
    }


def render_operator_checklist_md() -> str:
    manifest = build_seed_manifest()
    return "\n".join(
        [
            "# Canonical Seed Manifest Import-Audit Scaffold Operator Checklist",
            "",
            "This checklist is for PR #286 follow-up narrowed to seed manifest discovery and import-audit scaffolding.",
            "",
            "- Confirm the explicit approval token is present before any audit-scaffold execution.",
            "- Confirm expected schema sha256 matches `db/postgres/001_init.sql`.",
            "- Confirm expected seed manifest sha256 matches the rendered manifest.",
            "- Confirm `db/schema.sql` and `db/postgres/001_init.sql` are byte-identical.",
            "- Confirm PR #285 schema live apply has passed or can be re-verified.",
            "- Confirm `EMPEROR_EVAL_PG_DSN` is supplied only at execution/verification time.",
            "- Confirm no DSN value is copied into logs, PR body, or artifacts.",
            "- Confirm source data files are read-only inputs.",
            "- Confirm `imports` and `import_rows` are audit tables, not business target migration tables.",
            "- Confirm target business table writes remain deferred to Epic 1.",
            f"- Current manifest approval status: `{manifest['approval_status']}`.",
            "",
        ]
    )


def execute_seed_data_apply(
    require_user_approval_token: str | None,
    expected_schema_sha256: str | None,
    expected_seed_manifest_sha256: str | None,
) -> dict[str, Any]:
    started = utc_now()
    manifest = build_seed_manifest()
    gate = pre_execution_gate(require_user_approval_token, expected_schema_sha256, expected_seed_manifest_sha256, manifest)
    if gate:
        return blocked_evidence(started, "gate", gate, manifest, production_dsn_read=False)

    dsn = read_dsn()
    if not dsn:
        return blocked_evidence(started, "dsn_read", "blocked_missing_dsn", manifest, production_dsn_read=False)

    try:
        with connect_to_database(dsn) as conn:
            schema_verification = verify_schema_live_dependency(conn)
            if schema_verification["blocking_failures"]:
                report = blocked_evidence(
                    started,
                    "schema_live_dependency",
                    "blocked_schema_live_apply_verification_failed",
                    manifest,
                    production_dsn_read=True,
                )
                report["schema_live_apply_verification"] = schema_verification
                report["blocking_failures"] = list(schema_verification["blocking_failures"])
                return report
            apply_result = apply_seed_manifest(conn, manifest)
            commit_connection(conn)
            verification = verify_seed_data_apply(conn, manifest, apply_result)
    except ModuleNotFoundError as exc:
        return blocked_evidence(started, "runtime_dependency", "blocked_missing_runtime_dependency", manifest, True, exc, dsn)
    except Exception as exc:  # noqa: BLE001 - evidence must preserve failure type without leaking secrets.
        return blocked_evidence(started, "execute", "blocked_execution_failed", manifest, True, exc, dsn)

    failures = list(verification.get("blocking_failures", []))
    if failures:
        report = blocked_evidence(started, "verify", "blocked_verification_failed", manifest, production_dsn_read=True)
        report["verification"] = verification
        report["blocking_failures"] = failures
        return report

    return {
        "mode": "seed-data-apply-audit-scaffold-report",
        "pr_number": 286,
        "execution_version": EXECUTION_VERSION,
        "schema_sha256": schema_sha256(),
        "seed_manifest_sha256": manifest["manifest_sha256"],
        "seed_manifest_approved_for_execution": manifest["approved_for_execution"],
        "audit_scaffold_only": True,
        "dsn_env_name": DSN_ENV_NAME,
        "dsn_value_redacted": True,
        "production_db_connected": True,
        "production_dsn_read": True,
        "source_data_files_modified": False,
        "schema_files_modified": False,
        **PERMANENTLY_BLOCKED_SUCCESS_FLAGS,
        "import_audit_written": bool(apply_result.get("import_audit_written")),
        "audit_verification_passed": True,
        "target_business_table_writes_executed": False,
        "target_business_importer_deferred_to": "Epic 1",
        "apply_result": sanitize_apply_result(apply_result),
        "verification": verification,
        "started_at_utc": started,
        "ended_at_utc": utc_now(),
        "redacted_stdout_summary": [
            "canonical seed manifest audit scaffold executed through psycopg",
            "import audit scaffold written",
            "audit verification passed",
            "business target importer remains deferred to Epic 1",
        ],
        "redacted_stderr_summary": [],
        "failure_stage": "target_business_importer",
        "blocked_reason": BLOCKED_TARGET_IMPORTER_NOT_IMPLEMENTED,
        "blocking_failures": [BLOCKED_TARGET_IMPORTER_NOT_IMPLEMENTED],
    }


def verify_seed_data_apply_report(
    require_user_approval_token: str | None,
    expected_schema_sha256: str | None,
    expected_seed_manifest_sha256: str | None,
) -> dict[str, Any]:
    started = utc_now()
    manifest = build_seed_manifest()
    gate = pre_execution_gate(require_user_approval_token, expected_schema_sha256, expected_seed_manifest_sha256, manifest)
    if gate:
        return blocked_evidence(started, "gate", gate, manifest, production_dsn_read=False)
    dsn = read_dsn()
    if not dsn:
        return blocked_evidence(started, "dsn_read", "blocked_missing_dsn", manifest, production_dsn_read=False)
    try:
        with connect_to_database(dsn) as conn:
            schema_verification = verify_schema_live_dependency(conn)
            verification = verify_seed_data_apply(conn, manifest, None)
    except ModuleNotFoundError as exc:
        return blocked_evidence(started, "runtime_dependency", "blocked_missing_runtime_dependency", manifest, True, exc, dsn)
    except Exception as exc:  # noqa: BLE001 - evidence must preserve failure type without leaking secrets.
        return blocked_evidence(started, "verify", "blocked_verification_failed", manifest, True, exc, dsn)

    failures = list(schema_verification.get("blocking_failures", [])) + list(verification.get("blocking_failures", []))
    return {
        "mode": "seed-data-apply-verification-report",
        "pr_number": 286,
        "schema_sha256": schema_sha256(),
        "seed_manifest_sha256": manifest["manifest_sha256"],
        "seed_manifest_approved_for_execution": manifest["approved_for_execution"],
        "dsn_env_name": DSN_ENV_NAME,
        "dsn_value_redacted": True,
        "production_db_connected": True,
        "production_dsn_read": True,
        "seed_data_apply_executed": False,
        "production_data_rows_written": False,
        "import_audit_written": False,
        "verification_passed": False,
        "ready_for_production_migration": False,
        "audit_verification_passed": not failures,
        "target_business_table_writes_executed": False,
        "target_business_importer_deferred_to": "Epic 1",
        "schema_live_apply_verification": schema_verification,
        "verification": verification,
        "started_at_utc": started,
        "ended_at_utc": utc_now(),
        "redacted_stdout_summary": ["import-audit scaffold verification executed"],
        "redacted_stderr_summary": [],
        "blocking_failures": failures + [BLOCKED_TARGET_IMPORTER_NOT_IMPLEMENTED],
    }


def pre_execution_gate(
    require_user_approval_token: str | None,
    expected_schema_sha256: str | None,
    expected_seed_manifest_sha256: str | None,
    manifest: Mapping[str, Any],
) -> str | None:
    return first_blocking_reason(
        (
            (lambda: require_user_approval_token == APPROVAL_TOKEN, "blocked_missing_or_invalid_approval_token"),
            (lambda: bool(expected_schema_sha256), "blocked_missing_expected_schema_sha256"),
            (lambda: expected_schema_sha256 == schema_sha256(), "blocked_schema_hash_mismatch"),
            (lambda: bool(expected_seed_manifest_sha256), "blocked_missing_expected_seed_manifest_sha256"),
            (
                lambda: expected_seed_manifest_sha256 == manifest.get("manifest_sha256"),
                "blocked_seed_manifest_hash_mismatch",
            ),
            (schema_files_byte_identical, "blocked_schema_files_not_byte_identical"),
            (lambda: bool(manifest.get("approved_for_execution")), BLOCKED_MISSING_SEED_MANIFEST),
        )
    )


def blocked_evidence(
    started_at_utc: str,
    failure_stage: str,
    blocked_reason: str,
    manifest: Mapping[str, Any],
    production_dsn_read: bool,
    exc: BaseException | None = None,
    dsn: str | None = None,
) -> dict[str, Any]:
    return {
        "mode": "seed-data-apply-execution-report",
        "pr_number": 286,
        "schema_sha256": schema_sha256(),
        "seed_manifest_sha256": manifest.get("manifest_sha256"),
        "seed_manifest_approved_for_execution": bool(manifest.get("approved_for_execution")),
        "dsn_env_name": DSN_ENV_NAME,
        "dsn_value_redacted": True,
        "production_db_connected": False,
        "production_dsn_read": production_dsn_read,
        "source_data_files_modified": False,
        "schema_files_modified": False,
        **SUCCESS_FLAGS_FALSE,
        "audit_scaffold_only": True,
        "target_business_table_writes_executed": False,
        **blocked_report_fields(
            started_at_utc=started_at_utc,
            ended_at_utc=utc_now,
            failure_stage=failure_stage,
            blocked_reason=blocked_reason,
            exc=exc,
            dsn=dsn,
        ),
    }


def apply_seed_manifest(conn: Any, manifest: Mapping[str, Any]) -> dict[str, Any]:
    candidates = list(manifest.get("candidate_sources", []))
    accepted_rows = sum(int(source.get("line_count", 0)) for source in candidates)
    import_code = import_code_for_manifest(manifest)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO imports (code, source_kind, source_ref, status, tool_version, input_hash, row_count, meta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (code) DO UPDATE
            SET ended_at = now(),
                status = EXCLUDED.status,
                tool_version = EXCLUDED.tool_version,
                input_hash = EXCLUDED.input_hash,
                row_count = EXCLUDED.row_count,
                meta = EXCLUDED.meta
            RETURNING id
            """,
            (
                import_code,
                "seed_manifest_import_audit_scaffold",
                "repo_seed_manifest",
                AUDIT_IMPORT_STATUS,
                EXECUTION_VERSION,
                manifest["manifest_sha256"],
                accepted_rows,
                json.dumps(audit_manifest_meta(manifest), ensure_ascii=False, sort_keys=True),
            ),
        )
        row = cur.fetchone()
        import_id = row[0] if row else None
        for source in candidates:
            source_path = str(source["path"])
            source_lines = int(source.get("line_count", 0))
            for line_no in range(1, source_lines + 1):
                cur.execute(
                    """
                    INSERT INTO import_rows (
                        code, import_id, source_file, line_no, payload_hash, import_status, target_table, payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (code) DO NOTHING
                    """,
                    (
                        f"{import_code}:{hashlib.sha256(f'{source_path}:{line_no}'.encode('utf-8')).hexdigest()[:20]}",
                        import_id,
                        source_path,
                        line_no,
                        audit_row_hash(manifest, source, line_no),
                        AUDIT_IMPORT_ROW_STATUS,
                        None,
                        json.dumps(
                            {
                                "source_file": source_path,
                                "line_no": line_no,
                                "audit_only": True,
                                "audit_import_status": AUDIT_IMPORT_STATUS,
                                "audit_row_status": AUDIT_IMPORT_ROW_STATUS,
                                "payload_hash_scope": "audit_row_identity_not_source_payload",
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )
    return {
        "import_code": import_code,
        "audit_rows_written": accepted_rows,
        "import_audit_written": True,
        "source_files": [source["path"] for source in candidates],
        "target_business_table_writes_executed": False,
    }


def verify_schema_live_dependency(conn: Any) -> dict[str, Any]:
    query, params = build_table_check_query(REQUIRED_SCHEMA_LIVE_TABLES)
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    present = {row[0] for row in rows}
    missing = [table for table in REQUIRED_SCHEMA_LIVE_TABLES if table not in present]
    return {
        "required_tables": list(REQUIRED_SCHEMA_LIVE_TABLES),
        "tables_present": sorted(present),
        "blocking_failures": ["missing_schema_live_tables:" + ",".join(missing)] if missing else [],
    }


def verify_seed_data_apply(
    conn: Any,
    manifest: Mapping[str, Any],
    apply_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    import_code = str(apply_result.get("import_code")) if apply_result else import_code_for_manifest(manifest)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT code, status, row_count
            FROM imports
            WHERE code = %s AND input_hash = %s
            """,
            (import_code, manifest["manifest_sha256"]),
        )
        import_row = cur.fetchone()
        cur.execute(
            """
            SELECT count(*)
            FROM import_rows
            WHERE import_id = (
                SELECT id FROM imports WHERE code = %s AND input_hash = %s
            )
            """,
            (import_code, manifest["manifest_sha256"]),
        )
        count_row = cur.fetchone()
    import_rows_count = int(count_row[0]) if count_row else 0
    failures: list[str] = []
    if not import_row:
        failures.append("missing_import_audit")
    elif import_row[1] != AUDIT_IMPORT_STATUS:
        failures.append("import_audit_status_not_dry_run")
    if apply_result and import_rows_count < int(apply_result.get("audit_rows_written", 0)):
        failures.append("import_rows_below_accepted_rows")
    return {
        "import_code": import_code,
        "import_audit_found": bool(import_row),
        "import_status": import_row[1] if import_row else None,
        "reported_row_count": int(import_row[2]) if import_row else 0,
        "import_rows_count": import_rows_count,
        "blocking_failures": failures,
        "audit_tables_only": ["imports", "import_rows"],
        "target_business_table_writes_executed": False,
        "read_only": True,
    }


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


def import_code_for_manifest(manifest: Mapping[str, Any]) -> str:
    return f"production_seed_data_apply_pr286_{str(manifest['manifest_sha256'])[:16]}"


def audit_row_hash(manifest: Mapping[str, Any], source: Mapping[str, Any], line_no: int) -> str:
    return stable_json_sha256(
        {
            "manifest_sha256": manifest.get("manifest_sha256"),
            "source_file": source.get("path"),
            "source_file_sha256": source.get("sha256"),
            "line_no": line_no,
            "scope": "audit_row_identity_not_source_payload",
        }
    )


def audit_manifest_meta(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "manifest_version": manifest.get("manifest_version"),
        "manifest_kind": manifest.get("manifest_kind"),
        "candidate_source_count": manifest.get("candidate_source_count"),
        "candidate_sources": manifest.get("candidate_sources", []),
        "excluded_discovery_source_count": manifest.get("excluded_discovery_source_count", 0),
        "excluded_discovery_note": manifest.get("excluded_discovery_note"),
        "audit_import_status": AUDIT_IMPORT_STATUS,
        "audit_row_status": AUDIT_IMPORT_ROW_STATUS,
        "audit_only": True,
        "business_target_migration": False,
        "redacted": True,
    }


def sanitize_apply_result(apply_result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "import_code": apply_result.get("import_code"),
        "audit_rows_written": apply_result.get("audit_rows_written"),
        "import_audit_written": apply_result.get("import_audit_written"),
        "source_files": apply_result.get("source_files", []),
        "target_business_table_writes_executed": False,
    }


def connect_to_database(dsn: str) -> Any:
    import psycopg

    return psycopg.connect(dsn)


def commit_connection(conn: Any) -> None:
    commit = getattr(conn, "commit", None)
    if commit is not None:
        commit()


def read_dsn() -> str | None:
    value = os.environ.get(DSN_ENV_NAME)
    if not value:
        value = read_dotenv_values().get(DSN_ENV_NAME)
    if not value:
        return None
    return str(value)


def schema_file_fingerprints() -> list[dict[str, Any]]:
    return file_fingerprints(SCHEMA_PATHS, root=ROOT)


def schema_sha256() -> str:
    return file_sha256(POSTGRES_SQL_PATH)


def schema_files_byte_identical() -> bool:
    return files_byte_identical(SCHEMA_SQL_PATH, POSTGRES_SQL_PATH)


def stable_sha256(payload: Mapping[str, Any]) -> str:
    return stable_json_sha256(payload, omit_key="manifest_sha256")


def count_non_empty_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def detect_logical_kind(path: Path) -> str:
    stem = path.stem.lower()
    if "evidence" in stem:
        return "evidence"
    if "source" in stem:
        return "source"
    if "search" in stem or "query" in stem:
        return "search"
    if "anchor" in stem:
        return "anchor"
    if "event" in stem:
        return "event"
    return "jsonl"


def lint_execution_report(report: Mapping[str, Any]) -> dict[str, Any]:
    text = report_as_json(report)
    failed: list[str] = []
    if contains_secret_material(text):
        failed.append("secret_material_present")
    for key in PERMANENTLY_BLOCKED_SUCCESS_FLAGS:
        if report.get(key) is True:
            failed.append(f"{key}_true_in_audit_scaffold")
    if report.get("seed_data_apply_executed") is False and report.get("verification_passed") is True:
        failed.append("blocked_report_claims_verification_success")
    if report.get("seed_data_apply_executed") is False and not report.get("blocking_failures"):
        failed.append("blocked_report_missing_blocking_failures")
    if report.get("seed_data_apply_executed") is True:
        for key in ("production_data_rows_written", "verification_passed"):
            if report.get(key) is not True:
                failed.append(f"executed_without_{key}")
    return {
        "mode": "lint-execution-report",
        "passed": not failed,
        "failed": failed,
    }


def build_adr_check(adr_path: Path = ADR_PATH) -> dict[str, Any]:
    if not adr_path.exists():
        return {
            "mode": "adr-check",
            "adr_path": relative_path(adr_path),
            "adr_exists": False,
            "passed": False,
            "failed": ["adr_missing"],
        }
    content = normalize_text(adr_path.read_text(encoding="utf-8"))
    required = {
        "declares_audit_scaffold": "import-audit scaffold",
        "declares_audit_only_status": "audit-only",
        "allows_dsn_read": "allows dsn read",
        "allows_db_connect": "allows db connect",
        "manifest_hash_gate": "expected_seed_manifest_sha256",
        "schema_live_dependency": "pr #285 schema live apply",
        "missing_manifest_fail_closed": BLOCKED_MISSING_SEED_MANIFEST,
        "audit_tables_boundary": "are audit tables",
        "business_target_deferred": "epic 1",
        "no_secret_logging": "does not log dsn",
        "no_source_data_modification": "does not modify source data",
        "no_success_forgery": "must not fake migration success",
    }
    failed = [rule for rule, needle in required.items() if needle not in content]
    return {
        "mode": "adr-check",
        "adr_path": relative_path(adr_path),
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


def relative_path(path: Path) -> str:
    return core_relative_path(ROOT, path)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Execute or verify production seed/data apply.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--render-seed-manifest-json", action="store_true")
    mode.add_argument("--render-execution-plan-json", action="store_true")
    mode.add_argument("--render-operator-checklist-md", action="store_true")
    mode.add_argument("--execute-seed-data-apply", action="store_true")
    mode.add_argument("--verify-seed-data-apply", action="store_true")
    mode.add_argument("--lint-execution-report")
    mode.add_argument("--adr-check", action="store_true")
    parser.add_argument("--require-user-approval-token")
    parser.add_argument("--expected-schema-sha256")
    parser.add_argument("--expected-seed-manifest-sha256")
    args = parser.parse_args(argv)

    if args.render_operator_checklist_md:
        sys.stdout.write(render_operator_checklist_md())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.render_seed_manifest_json:
        report = build_seed_manifest()
    elif args.render_execution_plan_json:
        report = render_execution_plan_json()
    elif args.execute_seed_data_apply:
        report = execute_seed_data_apply(
            args.require_user_approval_token,
            args.expected_schema_sha256,
            args.expected_seed_manifest_sha256,
        )
    elif args.verify_seed_data_apply:
        report = verify_seed_data_apply_report(
            args.require_user_approval_token,
            args.expected_schema_sha256,
            args.expected_seed_manifest_sha256,
        )
    elif args.lint_execution_report:
        report = lint_execution_report(load_report_arg(args.lint_execution_report))
    else:
        report = build_adr_check()
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {
        "seed-data-apply-execution-report",
        "seed-data-apply-audit-scaffold-report",
        "seed-data-apply-verification-report",
    }:
        return 0 if not report.get("blocking_failures") else 1
    if report.get("failed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
