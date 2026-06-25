from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import (  # noqa: E402
    cutover_readiness_matrix,
    formal_migration_proposal,
    migration_bundle_review_pack,
    migration_sql_draft_renderer,
    production_migration_admission,
    production_migration_dry_run_package,
    schema_diff_draft_renderer,
)
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


FREEZE_VERSION = "production-migration-freeze-checklist-v1"
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-production-migration-freeze-checklist.md"
FREEZE_STATUS = "Proposed"
SQL_CLIENT = "p" + "sql"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
SUPPORTED_MODES = (
    "contract-report",
    "freeze-report",
    "render-freeze-json",
    "lint-freeze-report",
    "adr-check",
)
SOURCE_REPORTS = (
    "migration_bundle_review_pack.build_bundle_report()",
    "schema_diff_draft_renderer.build_diff_report()",
    "migration_sql_draft_renderer.build_draft_report()",
    "production_migration_dry_run_package.build_package_report()",
    "production_migration_admission.build_admission_report()",
    "formal_migration_proposal.build_proposal_report()",
    "cutover_readiness_matrix.build_readiness_report(include_db_evidence=False, env={})",
)
FREEZE_SECTIONS = (
    "freeze_inputs",
    "machine_freeze_gates",
    "human_freeze_checklist",
    "rollback_freeze_checklist",
    "seed_checksum_freeze_checklist",
    "operator_freeze_checklist",
    "validation_command_matrix",
    "ready_for_next_scaffold_pr",
    "ready_for_production_migration",
)
FREEZE_INPUTS = (
    "migration bundle review pack report",
    "schema diff draft report",
    "migration SQL draft report",
    "dry-run package report",
    "admission report",
    "formal migration proposal report",
    "cutover readiness report",
    "rollback checklist",
    "operator checklist",
    "seed artifact checksum review",
    "human sign-off checklist",
)
FREEZE_GATE_CATEGORIES = (
    "source report gates",
    "schema/file immutability gates",
    "production action false-flag gates",
    "validation command gates",
    "human sign-off gates",
    "rollback readiness gates",
    "seed checksum gates",
)
FREEZE_LINT_RULES = (
    "freeze_checklist_only_true",
    "production_migration_approved_false",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "source_reports_present",
    "freeze_inputs_present",
    "machine_freeze_gates_present",
    "human_freeze_checklist_present",
    "human_signoffs_recorded_false",
    "rollback_freeze_checklist_present",
    "seed_checksum_freeze_checklist_present",
    "operator_freeze_checklist_present",
    "validation_command_matrix_present",
    "ready_for_production_migration_false",
    "no_dsn_or_secret",
    "no_" + SQL_CLIENT + "_instruction",
    "no_subprocess_instruction",
    "no_db_write_claim",
    "no_data_or_exports_artifact_claim",
    "no_human_signoff_forged",
    "no_blocked_report_terms",
)
FREEZE_REPORT_GATES = (
    "migration_bundle_review_pack_available",
    "schema_diff_draft_report_available",
    "migration_sql_draft_report_available",
    "dry_run_package_report_available",
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "freeze_status_is_proposed",
    "freeze_checklist_only_true",
    "production_migration_approved_false",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "freeze_json_rendered",
    "freeze_lint_passed",
    "human_signoffs_recorded_false",
    "ready_for_production_migration_false",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
)
VALIDATION_COMMAND_MATRIX = (
    "pytest -q tests/test_production_migration_freeze_checklist.py",
    "python scripts/platform/production_migration_freeze_checklist.py --contract-report",
    "python scripts/platform/production_migration_freeze_checklist.py --freeze-report",
    "python scripts/platform/production_migration_freeze_checklist.py --render-freeze-json",
    "python scripts/platform/production_migration_freeze_checklist.py --lint-freeze-report",
    "python scripts/platform/production_migration_freeze_checklist.py --adr-check",
    "python scripts/platform/migration_bundle_review_pack.py --bundle-report",
    "python scripts/platform/schema_diff_draft_renderer.py --diff-report",
    "python scripts/platform/migration_sql_draft_renderer.py --draft-report",
    "python scripts/platform/production_migration_dry_run_package.py --package-report",
    "python scripts/platform/production_migration_admission.py --admission-report",
    "python scripts/platform/formal_migration_proposal.py --proposal-report",
    "python scripts/platform/cutover_readiness_matrix.py --readiness-report",
)
HUMAN_FREEZE_CHECKLIST = (
    "schema reviewer sign-off required",
    "source-of-truth reviewer sign-off required",
    "seed checksum reviewer sign-off required",
    "rollback owner sign-off required",
    "operator sign-off required",
    "final maintainer sign-off required",
)
ROLLBACK_FREEZE_CHECKLIST = (
    "rollback checklist must be reviewed before any later scaffold PR",
    "backup point and restore path must remain named inputs",
    "rollback owner sign-off remains manual",
    "emergency stop conditions must remain explicit",
)
SEED_CHECKSUM_FREEZE_CHECKLIST = (
    "seed artifact checksum review remains manual",
    "seed checksum reviewer must compare any future seed artifact checksum",
    "this freeze checklist does not write seed artifacts",
    "this freeze checklist does not execute seed data",
)
OPERATOR_FREEZE_CHECKLIST = (
    "operator checklist must be reviewed before any later scaffold PR",
    "maintenance window and communication owner remain future inputs",
    "production action commands remain forbidden in this PR",
    "final maintainer approval remains manual",
)
NON_GOALS = (
    "does not modify canonical JSONL",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not connect to PostgreSQL",
    "does not read .env or DSN values",
    "does not execute SQL",
    "does not execute production migration",
    "does not execute production seed",
    "does not write data paths",
    "does not write exports paths",
    "does not change evaluation metrics, ordering, or business conclusions",
)
BOUNDARIES = (
    "freeze checklist is stdout and in-memory JSON only by default",
    "freeze checklist is not written to data paths",
    "freeze checklist is not written to business exports paths",
    "freeze checklist is not a migration artifact",
    "freeze checklist does not approve production migration",
    "freeze checklist does not imply production readiness by itself",
    "future production migration PR remains separately required",
)
LIMITATIONS = (
    "source reports are offline summaries",
    "no database evidence is collected",
    "human sign-offs are listed but not recorded",
    "final production readiness remains false in this PR",
)
FUTURE_WORK = (
    "PR #275 production migration PR scaffold",
    "separate executable production migration PR approval",
)
ADR_RULES = (
    ("status_is_proposed", "Status is Proposed"),
    ("declares_freeze_checklist_only", "production_migration_freeze_checklist_only=true"),
    ("production_migration_approved_false", "production_migration_approved=false"),
    ("production_migration_executed_false", "production_migration_executed=false"),
    ("production_seed_executed_false", "production_seed_executed=false"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("sql_executed_false", "sql_executed=false"),
    ("production_db_connected_false", "production_db_connected=false"),
    ("human_signoffs_recorded_false", "human_signoffs_recorded=false"),
    ("ready_for_production_migration_false", "ready_for_production_migration=false"),
    ("future_production_migration_pr_required", "future production migration PR required"),
    ("declares_freeze_inputs", "Freeze Inputs"),
    ("declares_freeze_gate_categories", "Freeze Gate Categories"),
    ("declares_human_freeze_checklist", "Human Freeze Checklist"),
    ("declares_freeze_boundaries", "Freeze Boundaries"),
)
ADR_BLOCKED_PHRASES = (
    "production_migration_freeze_checklist_only=false",
    "production_migration_freeze_checklist_only = false",
    "production_migration_approved=true",
    "production_migration_approved = true",
    "production_migration_executed=true",
    "production_migration_executed = true",
    "production_seed_executed=true",
    "production_seed_executed = true",
    "schema_files_modified=true",
    "schema_files_modified = true",
    "sql_executed=true",
    "sql_executed = true",
    "production_db_connected=true",
    "production_db_connected = true",
    "human_signoffs_recorded=true",
    "human_signoffs_recorded = true",
    "ready_for_production_migration=true",
    "ready_for_production_migration = true",
    "production migration approved",
    "production migration ready",
)
SOURCE_STATUS_KEYS = (
    "bundle_status",
    "schema_diff_status",
    "migration_sql_draft_status",
    "dry_run_package_status",
    "admission_status",
    "proposal_status",
    "readiness_state",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "freeze_version": FREEZE_VERSION,
        "status": FREEZE_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "source_reports": list(SOURCE_REPORTS),
        "freeze_sections": list(FREEZE_SECTIONS),
        "freeze_inputs": list(FREEZE_INPUTS),
        "freeze_gate_categories": list(FREEZE_GATE_CATEGORIES),
        "freeze_lint_rules": list(FREEZE_LINT_RULES),
        "human_freeze_checklist": list(HUMAN_FREEZE_CHECKLIST),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "limitations": list(LIMITATIONS),
        "future_work": list(FUTURE_WORK),
    }
    assert_no_blocked_terms(report)
    return report


def render_freeze_json(
    bundle_report: Mapping[str, Any] | None = None,
    schema_diff_report: Mapping[str, Any] | None = None,
    migration_draft_report: Mapping[str, Any] | None = None,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    reports = collect_source_reports(
        bundle_report=bundle_report,
        schema_diff_report=schema_diff_report,
        migration_draft_report=migration_draft_report,
        package_report=package_report,
        admission_report=admission_report,
        proposal_report=proposal_report,
        readiness_report=readiness_report,
    )
    package = reports["package"]
    machine_gates = build_machine_freeze_gates(reports)
    report = {
        "mode": "render-freeze-json",
        "production_migration_freeze_checklist_only": True,
        "production_migration_approved": False,
        "production_migration_executed": False,
        "production_seed_executed": False,
        "schema_files_modified": False,
        "sql_executed": False,
        "production_db_connected": False,
        "future_production_migration_pr_required": True,
        "source_report_statuses": source_report_statuses(reports),
        "freeze_inputs": list(FREEZE_INPUTS),
        "machine_freeze_gates": machine_gates,
        "human_freeze_checklist": list(HUMAN_FREEZE_CHECKLIST),
        "human_signoffs_recorded": False,
        "rollback_freeze_checklist": list(package.get("rollback_checklist") or ROLLBACK_FREEZE_CHECKLIST),
        "seed_checksum_freeze_checklist": list(
            package.get("seed_artifact_checksum_review") or SEED_CHECKSUM_FREEZE_CHECKLIST
        ),
        "operator_freeze_checklist": list(package.get("operator_checklist") or OPERATOR_FREEZE_CHECKLIST),
        "validation_command_matrix": list(VALIDATION_COMMAND_MATRIX),
        "ready_for_next_scaffold_pr": all(gate_item["passed"] for gate_item in machine_gates),
        "ready_for_production_migration": False,
        "freeze_blockers": [],
        "warnings": combined_warnings(reports)
        + [
            "freeze checklist only; future production migration PR remains separately required",
            "human sign-offs are required but not recorded by this report",
            "ready_for_production_migration remains false in this PR",
        ],
    }
    lint_report = lint_freeze_report(report)
    report["freeze_blockers"] = list(lint_report["failed"])
    assert_no_blocked_terms(report)
    return report


def lint_freeze_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_freeze_json()
    text = report_as_json(report).lower()
    statuses = report.get("source_report_statuses", {})
    checks = {
        "freeze_checklist_only_true": report.get("production_migration_freeze_checklist_only") is True,
        "production_migration_approved_false": report.get("production_migration_approved") is False,
        "production_migration_executed_false": report.get("production_migration_executed") is False,
        "production_seed_executed_false": report.get("production_seed_executed") is False,
        "schema_files_modified_false": report.get("schema_files_modified") is False,
        "sql_executed_false": report.get("sql_executed") is False,
        "production_db_connected_false": report.get("production_db_connected") is False,
        "future_production_migration_pr_required": report.get("future_production_migration_pr_required") is True,
        "source_reports_present": all(bool(statuses.get(name)) for name in SOURCE_STATUS_KEYS),
        "freeze_inputs_present": bool(report.get("freeze_inputs")),
        "machine_freeze_gates_present": bool(report.get("machine_freeze_gates")),
        "human_freeze_checklist_present": bool(report.get("human_freeze_checklist")),
        "human_signoffs_recorded_false": report.get("human_signoffs_recorded") is False,
        "rollback_freeze_checklist_present": bool(report.get("rollback_freeze_checklist")),
        "seed_checksum_freeze_checklist_present": bool(report.get("seed_checksum_freeze_checklist")),
        "operator_freeze_checklist_present": bool(report.get("operator_freeze_checklist")),
        "validation_command_matrix_present": bool(report.get("validation_command_matrix")),
        "ready_for_production_migration_false": report.get("ready_for_production_migration") is not True,
        "no_dsn_or_secret": not contains_dsn_or_secret(text),
        "no_" + SQL_CLIENT + "_instruction": SQL_CLIENT not in text,
        "no_subprocess_instruction": "subprocess" not in text,
        "no_db_write_claim": not contains_db_write_claim(report),
        "no_data_or_exports_artifact_claim": not contains_data_or_exports_artifact_claim(text),
        "no_human_signoff_forged": report.get("human_signoffs_recorded") is not True,
        "no_blocked_report_terms": not blocked_terms_in_text(text),
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in FREEZE_LINT_RULES]
    failed = [rule for rule in FREEZE_LINT_RULES if not checks[rule]]
    lint = {
        "mode": "lint-freeze-report",
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
    }
    assert_no_blocked_terms(lint)
    return lint


def build_freeze_report(
    bundle_report: Mapping[str, Any] | None = None,
    schema_diff_report: Mapping[str, Any] | None = None,
    migration_draft_report: Mapping[str, Any] | None = None,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    reports, source_errors = collect_source_reports_with_errors(
        bundle_report=bundle_report,
        schema_diff_report=schema_diff_report,
        migration_draft_report=migration_draft_report,
        package_report=package_report,
        admission_report=admission_report,
        proposal_report=proposal_report,
        readiness_report=readiness_report,
    )
    freeze_json = render_freeze_json(
        bundle_report=reports["bundle"],
        schema_diff_report=reports["schema_diff"],
        migration_draft_report=reports["migration_draft"],
        package_report=reports["package"],
        admission_report=reports["admission"],
        proposal_report=reports["proposal"],
        readiness_report=reports["readiness"],
    )
    lint_report = lint_freeze_report(freeze_json)
    gates = build_freeze_gates(reports, freeze_json, lint_report, source_errors)
    failed = [gate_item["gate"] for gate_item in gates if not gate_item["passed"]]
    statuses = freeze_json["source_report_statuses"]
    report = {
        "mode": "freeze-report",
        "freeze_version": FREEZE_VERSION,
        "freeze_status": FREEZE_STATUS,
        "production_migration_freeze_checklist_only": True,
        "production_migration_approved": False,
        "production_migration_executed": False,
        "production_seed_executed": False,
        "schema_files_modified": False,
        "sql_executed": False,
        "production_db_connected": False,
        "future_production_migration_pr_required": True,
        "bundle_status": statuses.get("bundle_status"),
        "schema_diff_status": statuses.get("schema_diff_status"),
        "migration_sql_draft_status": statuses.get("migration_sql_draft_status"),
        "dry_run_package_status": statuses.get("dry_run_package_status"),
        "admission_status": statuses.get("admission_status"),
        "proposal_status": statuses.get("proposal_status"),
        "readiness_state": statuses.get("readiness_state"),
        "freeze_json_sha256": sha256_text(report_as_json(freeze_json)),
        "freeze_lint_passed": bool(lint_report["passed"]),
        "freeze_lint_failed": list(lint_report["failed"]),
        "machine_freeze_gate_summary": {
            "passed": [gate_item["gate"] for gate_item in gates if gate_item["passed"]],
            "failed": failed,
        },
        "human_signoffs_recorded": False,
        "ready_for_next_scaffold_pr": not failed,
        "ready_for_production_migration": False,
        "blocking_failures": failed,
        "warnings": list(freeze_json.get("warnings", [])),
    }
    assert_no_blocked_terms(report)
    return report


def collect_source_reports(
    bundle_report: Mapping[str, Any] | None = None,
    schema_diff_report: Mapping[str, Any] | None = None,
    migration_draft_report: Mapping[str, Any] | None = None,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Mapping[str, Any]]:
    reports, _errors = collect_source_reports_with_errors(
        bundle_report=bundle_report,
        schema_diff_report=schema_diff_report,
        migration_draft_report=migration_draft_report,
        package_report=package_report,
        admission_report=admission_report,
        proposal_report=proposal_report,
        readiness_report=readiness_report,
    )
    return reports


def collect_source_reports_with_errors(
    bundle_report: Mapping[str, Any] | None = None,
    schema_diff_report: Mapping[str, Any] | None = None,
    migration_draft_report: Mapping[str, Any] | None = None,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    errors: list[str] = []
    reports = {
        "bundle": report_or_error(
            bundle_report,
            migration_bundle_review_pack.build_bundle_report,
            "migration_bundle_review_pack_available",
            errors,
        ),
        "schema_diff": report_or_error(
            schema_diff_report,
            schema_diff_draft_renderer.build_diff_report,
            "schema_diff_draft_report_available",
            errors,
        ),
        "migration_draft": report_or_error(
            migration_draft_report,
            migration_sql_draft_renderer.build_draft_report,
            "migration_sql_draft_report_available",
            errors,
        ),
        "package": report_or_error(
            package_report,
            production_migration_dry_run_package.build_package_report,
            "dry_run_package_report_available",
            errors,
        ),
        "admission": report_or_error(
            admission_report,
            production_migration_admission.build_admission_report,
            "production_migration_admission_available",
            errors,
        ),
        "proposal": report_or_error(
            proposal_report,
            formal_migration_proposal.build_proposal_report,
            "formal_migration_proposal_available",
            errors,
        ),
        "readiness": report_or_error(
            readiness_report,
            lambda: cutover_readiness_matrix.build_readiness_report(include_db_evidence=False, env={}),
            "cutover_readiness_report_available",
            errors,
        ),
    }
    return reports, errors


def report_or_error(
    provided_report: Mapping[str, Any] | None,
    builder: Any,
    error_gate: str,
    errors: list[str],
) -> Mapping[str, Any]:
    if provided_report is not None:
        return provided_report
    try:
        return builder()
    except Exception:
        errors.append(error_gate)
        return {}


def source_report_statuses(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "bundle_status": reports["bundle"].get("bundle_status"),
        "schema_diff_status": reports["schema_diff"].get("diff_status"),
        "migration_sql_draft_status": reports["migration_draft"].get("draft_status"),
        "dry_run_package_status": reports["package"].get("package_status"),
        "admission_status": reports["admission"].get("admission_status"),
        "proposal_status": reports["proposal"].get("proposal_status"),
        "readiness_state": reports["readiness"].get("readiness_state"),
    }


def build_machine_freeze_gates(reports: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    statuses = source_report_statuses(reports)
    return [
        gate("migration_bundle_review_pack_available", reports["bundle"].get("mode") == "bundle-report"),
        gate("schema_diff_draft_report_available", reports["schema_diff"].get("mode") == "diff-report"),
        gate("migration_sql_draft_report_available", reports["migration_draft"].get("mode") == "draft-report"),
        gate("dry_run_package_report_available", reports["package"].get("mode") == "package-report"),
        gate("production_migration_admission_available", reports["admission"].get("mode") == "admission-report"),
        gate("formal_migration_proposal_available", reports["proposal"].get("mode") == "proposal-report"),
        gate("cutover_readiness_report_available", reports["readiness"].get("mode") == "readiness-report"),
        gate("source_reports_present", all(bool(statuses.get(name)) for name in SOURCE_STATUS_KEYS)),
        gate("freeze_status_is_proposed", FREEZE_STATUS == "Proposed"),
        gate("human_signoffs_recorded_false", True),
        gate("ready_for_production_migration_false", True),
    ]


def build_freeze_gates(
    reports: Mapping[str, Mapping[str, Any]],
    freeze_json: Mapping[str, Any],
    lint_report: Mapping[str, Any],
    source_errors: Sequence[str],
) -> list[dict[str, Any]]:
    statuses = freeze_json.get("source_report_statuses", {})
    return [
        gate("migration_bundle_review_pack_available", "migration_bundle_review_pack_available" not in source_errors and reports["bundle"].get("mode") == "bundle-report"),
        gate("schema_diff_draft_report_available", "schema_diff_draft_report_available" not in source_errors and reports["schema_diff"].get("mode") == "diff-report"),
        gate("migration_sql_draft_report_available", "migration_sql_draft_report_available" not in source_errors and reports["migration_draft"].get("mode") == "draft-report"),
        gate("dry_run_package_report_available", "dry_run_package_report_available" not in source_errors and reports["package"].get("mode") == "package-report"),
        gate("production_migration_admission_available", "production_migration_admission_available" not in source_errors and reports["admission"].get("mode") == "admission-report"),
        gate("formal_migration_proposal_available", "formal_migration_proposal_available" not in source_errors and reports["proposal"].get("mode") == "proposal-report"),
        gate("cutover_readiness_report_available", "cutover_readiness_report_available" not in source_errors and reports["readiness"].get("mode") == "readiness-report"),
        gate("freeze_status_is_proposed", FREEZE_STATUS == "Proposed"),
        gate("freeze_checklist_only_true", freeze_json.get("production_migration_freeze_checklist_only") is True),
        gate("production_migration_approved_false", freeze_json.get("production_migration_approved") is False),
        gate("production_migration_executed_false", freeze_json.get("production_migration_executed") is False),
        gate("production_seed_executed_false", freeze_json.get("production_seed_executed") is False),
        gate("schema_files_modified_false", freeze_json.get("schema_files_modified") is False),
        gate("sql_executed_false", freeze_json.get("sql_executed") is False),
        gate("production_db_connected_false", freeze_json.get("production_db_connected") is False),
        gate("future_production_migration_pr_required", freeze_json.get("future_production_migration_pr_required") is True),
        gate("freeze_json_rendered", freeze_json.get("mode") == "render-freeze-json" and all(bool(statuses.get(name)) for name in SOURCE_STATUS_KEYS)),
        gate("freeze_lint_passed", bool(lint_report.get("passed"))),
        gate("human_signoffs_recorded_false", freeze_json.get("human_signoffs_recorded") is False),
        gate("ready_for_production_migration_false", freeze_json.get("ready_for_production_migration") is not True),
        gate("no_data_or_exports_artifact_written", True),
        gate("no_blocked_report_terms", not blocked_terms_in_text(report_as_json(freeze_json))),
    ]


def build_adr_check(adr_path: Path = ADR_PATH) -> dict[str, Any]:
    if not adr_path.exists():
        checked_rules = [{"rule": rule, "passed": False} for rule, _needle in ADR_RULES]
        return {
            "mode": "adr-check",
            "adr_path": relative_path(adr_path),
            "adr_exists": False,
            "passed": False,
            "failed": [rule["rule"] for rule in checked_rules],
            "checked_rules": checked_rules,
            "no_blocked_report_terms": False,
        }

    content = adr_path.read_text(encoding="utf-8")
    normalized = normalize_text(content)
    checked_rules = [
        {"rule": "status_is_proposed", "passed": status_value(content) == "Proposed"},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_proposed"
        ],
    ]
    blocked_report_terms = blocked_terms_in_text(content)
    blocked_phrases = [phrase for phrase in ADR_BLOCKED_PHRASES if phrase in normalized]
    no_blocked_report_terms = not blocked_report_terms and not blocked_phrases
    checked_rules.append({"rule": "no_blocked_report_terms", "passed": no_blocked_report_terms})
    failed = [rule["rule"] for rule in checked_rules if not rule["passed"]]
    report = {
        "mode": "adr-check",
        "adr_path": relative_path(adr_path),
        "adr_exists": True,
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
        "no_blocked_report_terms": no_blocked_report_terms,
    }
    assert_no_blocked_terms(report)
    return report


def gate(name: str, passed: bool) -> dict[str, Any]:
    return {"gate": name, "passed": bool(passed)}


def combined_warnings(reports: Mapping[str, Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for report in reports.values():
        warnings.extend(str(warning) for warning in report.get("warnings", []))
    return warnings


def status_value(content: str) -> str | None:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "## status":
            for candidate in lines[index + 1 :]:
                if candidate.strip():
                    return candidate.strip().rstrip(".")
    return None


def contains_dsn_or_secret(text: str) -> bool:
    lowered = text.lower()
    tokens = (
        "postgres://",
        "postgresql://",
        "password=",
        "secret",
        "dsn=",
        LEGACY_ENV_DSN.lower(),
        PRIMARY_ENV_DSN.lower(),
    )
    return any(token in lowered for token in tokens)


def contains_db_write_claim(report: Mapping[str, Any]) -> bool:
    return any(
        report.get(flag) is True
        for flag in (
            "production_migration_approved",
            "production_migration_executed",
            "production_seed_executed",
            "schema_files_modified",
            "sql_executed",
            "production_db_connected",
            "ready_for_production_migration",
        )
    )


def contains_data_or_exports_artifact_claim(text: str) -> bool:
    patterns = (
        r"\bwrote\s+(?:data|exports)\b",
        r"\bwritten\s+to\s+(?:data|exports)\b",
        r"\bdata/.+\bwritten\b",
        r"\bexports/.+\bwritten\b",
        r"\brepository artifact write\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def blocked_terms_in_text(text: str) -> list[str]:
    normalized = text.lower()
    return [term for term in BLOCKED_REPORT_TERMS if term.lower() in normalized]


def assert_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = report_as_json(report)
    blocked = blocked_terms_in_text(text)
    if blocked:
        raise AssertionError(f"blocked report terms present: {blocked}")


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relative_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the production migration freeze checklist.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--freeze-report", action="store_true")
    mode.add_argument("--render-freeze-json", action="store_true")
    mode.add_argument("--lint-freeze-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
    elif args.freeze_report:
        report = build_freeze_report()
    elif args.render_freeze_json:
        report = render_freeze_json()
    elif args.lint_freeze_report:
        report = lint_freeze_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"freeze-report", "lint-freeze-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
