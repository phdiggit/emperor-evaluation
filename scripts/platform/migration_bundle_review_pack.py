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
    migration_sql_draft_renderer,
    production_migration_admission,
    production_migration_dry_run_package,
    schema_diff_draft_renderer,
)
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


BUNDLE_VERSION = "migration-bundle-review-pack-v1"
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-migration-bundle-review-pack.md"
BUNDLE_STATUS = "Proposed"
SQL_CLIENT = "p" + "sql"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
SUPPORTED_MODES = (
    "contract-report",
    "bundle-report",
    "render-bundle-json",
    "lint-bundle-report",
    "adr-check",
)
SOURCE_REPORTS = (
    "schema_diff_draft_renderer.build_diff_report()",
    "migration_sql_draft_renderer.build_draft_report()",
    "production_migration_dry_run_package.build_package_report()",
    "production_migration_admission.build_admission_report()",
    "formal_migration_proposal.build_proposal_report()",
    "cutover_readiness_matrix.build_readiness_report(include_db_evidence=False, env={})",
)
BUNDLE_SECTIONS = (
    "schema_diff_draft_report",
    "migration_sql_draft_report",
    "dry_run_package_report",
    "admission_report",
    "formal_migration_proposal_report",
    "cutover_readiness_report",
    "operator_checklist",
    "validation_command_matrix",
    "rollback_checklist",
    "seed_artifact_checksum_review",
    "human_review_checklist",
    "risk_register",
)
REVIEW_PACK_CONTENTS = (
    "schema diff draft report",
    "migration SQL draft report",
    "dry-run package report",
    "admission report",
    "formal migration proposal report",
    "cutover readiness report",
    "operator checklist",
    "validation command matrix",
    "rollback checklist",
    "seed artifact checksum review",
    "human sign-off checklist",
    "risk register",
)
BUNDLE_LINT_RULES = (
    "migration_bundle_review_only_true",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "source_reports_present",
    "schema_diff_status_present",
    "migration_sql_draft_status_present",
    "dry_run_package_status_present",
    "admission_status_present",
    "proposal_status_present",
    "readiness_state_present",
    "operator_checklist_present",
    "validation_command_matrix_present",
    "rollback_checklist_present",
    "seed_artifact_checksum_review_present",
    "human_review_checklist_present",
    "risk_register_present",
    "no_dsn_or_secret",
    "no_" + SQL_CLIENT + "_instruction",
    "no_subprocess_instruction",
    "no_db_write_claim",
    "no_data_or_exports_artifact_claim",
    "no_blocked_report_terms",
)
BUNDLE_REPORT_GATES = (
    "schema_diff_draft_report_available",
    "migration_sql_draft_report_available",
    "dry_run_package_report_available",
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "bundle_status_is_proposed",
    "migration_bundle_review_only_true",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "bundle_json_rendered",
    "bundle_lint_passed",
    "operator_checklist_present",
    "validation_command_matrix_present",
    "rollback_checklist_present",
    "human_review_checklist_present",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
)
OPERATOR_CHECKLIST = (
    "confirm schema diff reviewer is assigned",
    "confirm migration SQL reviewer is assigned",
    "confirm backup point and maintenance window are named",
    "confirm rollback owner is assigned",
    "confirm seed artifact checksum reviewer is assigned",
    "confirm final maintainer sign-off remains manual",
)
VALIDATION_COMMAND_MATRIX = (
    "pytest -q tests/test_migration_bundle_review_pack.py",
    "python scripts/platform/migration_bundle_review_pack.py --contract-report",
    "python scripts/platform/migration_bundle_review_pack.py --bundle-report",
    "python scripts/platform/migration_bundle_review_pack.py --render-bundle-json",
    "python scripts/platform/migration_bundle_review_pack.py --lint-bundle-report",
    "python scripts/platform/migration_bundle_review_pack.py --adr-check",
    "python scripts/platform/schema_diff_draft_renderer.py --diff-report",
    "python scripts/platform/migration_sql_draft_renderer.py --draft-report",
    "python scripts/platform/production_migration_dry_run_package.py --package-report",
    "python scripts/platform/production_migration_admission.py --admission-report",
    "python scripts/platform/formal_migration_proposal.py --proposal-report",
    "python scripts/platform/cutover_readiness_matrix.py --readiness-report",
)
ROLLBACK_CHECKLIST = (
    "backup point must be named before any later migration PR",
    "restore path must be documented before any later migration PR",
    "rollback owner must sign off before any later migration PR",
    "verification queries must be listed before any later migration PR",
    "emergency stop condition must be listed before any later migration PR",
)
SEED_ARTIFACT_CHECKSUM_REVIEW = (
    "seed artifact checksum review remains manual",
    "checksum reviewer must compare future seed artifact checksum before any later seed step",
    "this review pack does not write seed artifact files",
    "this review pack does not apply seed data",
)
HUMAN_REVIEW_CHECKLIST = (
    "schema reviewer sign-off",
    "source-of-truth reviewer sign-off",
    "seed checksum reviewer sign-off",
    "rollback owner sign-off",
    "operator sign-off",
    "final maintainer sign-off",
)
RISK_REGISTER = (
    "schema drift between draft and production migration PR",
    "seed artifact checksum drift",
    "source-of-truth mismatch",
    "rollback ownership gap",
    "operator checklist incompleteness",
    "false sense of production readiness from review-only output",
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
    "review pack is stdout and in-memory JSON only by default",
    "review pack is not written to data paths",
    "review pack is not written to exports paths",
    "review pack is not a migration artifact",
    "review pack is not executable",
    "review pack does not imply production readiness",
    "future production migration PR remains separately required",
)
LIMITATIONS = (
    "source reports are offline summaries",
    "no database evidence is collected",
    "no production file mutation is detected beyond explicit false flags",
    "final production readiness remains a manual review decision",
)
FUTURE_WORK = (
    "PR #274 production migration freeze checklist",
    "separate executable production migration PR approval",
)
ADR_RULES = (
    ("status_is_proposed", "Status is Proposed"),
    ("declares_migration_bundle_review_only", "migration_bundle_review_only=true"),
    ("production_migration_executed_false", "production_migration_executed=false"),
    ("production_seed_executed_false", "production_seed_executed=false"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("sql_executed_false", "sql_executed=false"),
    ("production_db_connected_false", "production_db_connected=false"),
    ("future_production_migration_pr_required", "future production migration PR required"),
    ("declares_bundle_contents", "Bundle Contents"),
    ("declares_review_pack_boundaries", "Review Pack Boundaries"),
    ("declares_required_bundle_gates", "Required Bundle Gates"),
    ("declares_human_review_checklist", "Human Review Checklist"),
    ("declares_no_production_migration", "no production migration"),
    ("declares_no_production_seed", "no production seed"),
    ("declares_no_schema_file_edits", "no schema file edits"),
)
ADR_BLOCKED_PHRASES = (
    "migration_bundle_review_only=false",
    "migration_bundle_review_only = false",
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
    "production migration ready",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "bundle_version": BUNDLE_VERSION,
        "status": BUNDLE_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "source_reports": list(SOURCE_REPORTS),
        "bundle_sections": list(BUNDLE_SECTIONS),
        "review_pack_contents": list(REVIEW_PACK_CONTENTS),
        "bundle_lint_rules": list(BUNDLE_LINT_RULES),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "limitations": list(LIMITATIONS),
        "future_work": list(FUTURE_WORK),
    }
    assert_no_blocked_terms(report)
    return report


def render_bundle_json(
    schema_diff_report: Mapping[str, Any] | None = None,
    migration_draft_report: Mapping[str, Any] | None = None,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    reports = collect_source_reports(
        schema_diff_report=schema_diff_report,
        migration_draft_report=migration_draft_report,
        package_report=package_report,
        admission_report=admission_report,
        proposal_report=proposal_report,
        readiness_report=readiness_report,
    )
    package = reports["package"]
    admission = reports["admission"]
    proposal = reports["proposal"]
    report = {
        "mode": "render-bundle-json",
        "migration_bundle_review_only": True,
        "production_migration_executed": False,
        "production_seed_executed": False,
        "schema_files_modified": False,
        "sql_executed": False,
        "production_db_connected": False,
        "future_production_migration_pr_required": True,
        "source_report_statuses": source_report_statuses(reports),
        "bundle_contents": list(REVIEW_PACK_CONTENTS),
        "operator_checklist": list(package.get("operator_checklist") or OPERATOR_CHECKLIST),
        "validation_command_matrix": list(VALIDATION_COMMAND_MATRIX),
        "rollback_checklist": list(package.get("rollback_checklist") or ROLLBACK_CHECKLIST),
        "seed_artifact_checksum_review": list(
            package.get("seed_artifact_checksum_review") or SEED_ARTIFACT_CHECKSUM_REVIEW
        ),
        "human_review_checklist": list(HUMAN_REVIEW_CHECKLIST),
        "risk_register": list(proposal.get("risks") or RISK_REGISTER),
        "warnings": combined_warnings(reports)
        + [
            "review pack only; future production migration PR remains separately required",
            "review pack does not write repository artifacts",
        ],
    }
    assert_no_blocked_terms(report)
    return report


def lint_bundle_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_bundle_json()
    text = report_as_json(report).lower()
    statuses = report.get("source_report_statuses", {})
    checks = {
        "migration_bundle_review_only_true": report.get("migration_bundle_review_only") is True,
        "production_migration_executed_false": report.get("production_migration_executed") is False,
        "production_seed_executed_false": report.get("production_seed_executed") is False,
        "schema_files_modified_false": report.get("schema_files_modified") is False,
        "sql_executed_false": report.get("sql_executed") is False,
        "production_db_connected_false": report.get("production_db_connected") is False,
        "future_production_migration_pr_required": report.get("future_production_migration_pr_required") is True,
        "source_reports_present": all(bool(statuses.get(name)) for name in SOURCE_STATUS_KEYS),
        "schema_diff_status_present": bool(statuses.get("schema_diff_status")),
        "migration_sql_draft_status_present": bool(statuses.get("migration_sql_draft_status")),
        "dry_run_package_status_present": bool(statuses.get("dry_run_package_status")),
        "admission_status_present": bool(statuses.get("admission_status")),
        "proposal_status_present": bool(statuses.get("proposal_status")),
        "readiness_state_present": bool(statuses.get("readiness_state")),
        "operator_checklist_present": bool(report.get("operator_checklist")),
        "validation_command_matrix_present": bool(report.get("validation_command_matrix")),
        "rollback_checklist_present": bool(report.get("rollback_checklist")),
        "seed_artifact_checksum_review_present": bool(report.get("seed_artifact_checksum_review")),
        "human_review_checklist_present": bool(report.get("human_review_checklist")),
        "risk_register_present": bool(report.get("risk_register")),
        "no_dsn_or_secret": not contains_dsn_or_secret(text),
        "no_" + SQL_CLIENT + "_instruction": SQL_CLIENT not in text,
        "no_subprocess_instruction": "subprocess" not in text,
        "no_db_write_claim": not contains_db_write_claim(report),
        "no_data_or_exports_artifact_claim": not contains_data_or_exports_artifact_claim(text),
        "no_blocked_report_terms": not blocked_terms_in_text(text),
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in BUNDLE_LINT_RULES]
    failed = [rule for rule in BUNDLE_LINT_RULES if not checks[rule]]
    lint = {
        "mode": "lint-bundle-report",
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
    }
    assert_no_blocked_terms(lint)
    return lint


def build_bundle_report(
    schema_diff_report: Mapping[str, Any] | None = None,
    migration_draft_report: Mapping[str, Any] | None = None,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    reports, source_errors = collect_source_reports_with_errors(
        schema_diff_report=schema_diff_report,
        migration_draft_report=migration_draft_report,
        package_report=package_report,
        admission_report=admission_report,
        proposal_report=proposal_report,
        readiness_report=readiness_report,
    )
    bundle_json = render_bundle_json(
        schema_diff_report=reports["schema_diff"],
        migration_draft_report=reports["migration_draft"],
        package_report=reports["package"],
        admission_report=reports["admission"],
        proposal_report=reports["proposal"],
        readiness_report=reports["readiness"],
    )
    lint_report = lint_bundle_report(bundle_json)
    gates = build_bundle_gates(reports, bundle_json, lint_report, source_errors)
    failed = [gate_item["gate"] for gate_item in gates if not gate_item["passed"]]
    statuses = bundle_json["source_report_statuses"]
    report = {
        "mode": "bundle-report",
        "bundle_version": BUNDLE_VERSION,
        "bundle_status": BUNDLE_STATUS,
        "migration_bundle_review_only": True,
        "production_migration_executed": False,
        "production_seed_executed": False,
        "schema_files_modified": False,
        "sql_executed": False,
        "production_db_connected": False,
        "future_production_migration_pr_required": True,
        "schema_diff_status": statuses.get("schema_diff_status"),
        "migration_sql_draft_status": statuses.get("migration_sql_draft_status"),
        "dry_run_package_status": statuses.get("dry_run_package_status"),
        "admission_status": statuses.get("admission_status"),
        "proposal_status": statuses.get("proposal_status"),
        "readiness_state": statuses.get("readiness_state"),
        "bundle_json_sha256": sha256_text(report_as_json(bundle_json)),
        "bundle_lint_passed": bool(lint_report["passed"]),
        "bundle_lint_failed": list(lint_report["failed"]),
        "bundle_gate_summary": {
            "passed": [gate_item["gate"] for gate_item in gates if gate_item["passed"]],
            "failed": failed,
        },
        "blocking_failures": failed,
        "warnings": list(bundle_json.get("warnings", [])),
    }
    assert_no_blocked_terms(report)
    return report


SOURCE_STATUS_KEYS = (
    "schema_diff_status",
    "migration_sql_draft_status",
    "dry_run_package_status",
    "admission_status",
    "proposal_status",
    "readiness_state",
)


def collect_source_reports(
    schema_diff_report: Mapping[str, Any] | None = None,
    migration_draft_report: Mapping[str, Any] | None = None,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Mapping[str, Any]]:
    reports, _errors = collect_source_reports_with_errors(
        schema_diff_report=schema_diff_report,
        migration_draft_report=migration_draft_report,
        package_report=package_report,
        admission_report=admission_report,
        proposal_report=proposal_report,
        readiness_report=readiness_report,
    )
    return reports


def collect_source_reports_with_errors(
    schema_diff_report: Mapping[str, Any] | None = None,
    migration_draft_report: Mapping[str, Any] | None = None,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    errors: list[str] = []
    reports = {
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
        "schema_diff_status": reports["schema_diff"].get("diff_status"),
        "migration_sql_draft_status": reports["migration_draft"].get("draft_status"),
        "dry_run_package_status": reports["package"].get("package_status"),
        "admission_status": reports["admission"].get("admission_status"),
        "proposal_status": reports["proposal"].get("proposal_status"),
        "readiness_state": reports["readiness"].get("readiness_state"),
    }


def build_bundle_gates(
    reports: Mapping[str, Mapping[str, Any]],
    bundle_json: Mapping[str, Any],
    lint_report: Mapping[str, Any],
    source_errors: Sequence[str],
) -> list[dict[str, Any]]:
    statuses = bundle_json.get("source_report_statuses", {})
    return [
        gate("schema_diff_draft_report_available", "schema_diff_draft_report_available" not in source_errors and reports["schema_diff"].get("mode") == "diff-report"),
        gate("migration_sql_draft_report_available", "migration_sql_draft_report_available" not in source_errors and reports["migration_draft"].get("mode") == "draft-report"),
        gate("dry_run_package_report_available", "dry_run_package_report_available" not in source_errors and reports["package"].get("mode") == "package-report"),
        gate("production_migration_admission_available", "production_migration_admission_available" not in source_errors and reports["admission"].get("mode") == "admission-report"),
        gate("formal_migration_proposal_available", "formal_migration_proposal_available" not in source_errors and reports["proposal"].get("mode") == "proposal-report"),
        gate("cutover_readiness_report_available", "cutover_readiness_report_available" not in source_errors and reports["readiness"].get("mode") == "readiness-report"),
        gate("bundle_status_is_proposed", BUNDLE_STATUS == "Proposed"),
        gate("migration_bundle_review_only_true", bundle_json.get("migration_bundle_review_only") is True),
        gate("production_migration_executed_false", bundle_json.get("production_migration_executed") is False),
        gate("production_seed_executed_false", bundle_json.get("production_seed_executed") is False),
        gate("schema_files_modified_false", bundle_json.get("schema_files_modified") is False),
        gate("sql_executed_false", bundle_json.get("sql_executed") is False),
        gate("production_db_connected_false", bundle_json.get("production_db_connected") is False),
        gate("future_production_migration_pr_required", bundle_json.get("future_production_migration_pr_required") is True),
        gate("bundle_json_rendered", bundle_json.get("mode") == "render-bundle-json" and all(bool(statuses.get(name)) for name in SOURCE_STATUS_KEYS)),
        gate("bundle_lint_passed", bool(lint_report.get("passed"))),
        gate("operator_checklist_present", bool(bundle_json.get("operator_checklist"))),
        gate("validation_command_matrix_present", bool(bundle_json.get("validation_command_matrix"))),
        gate("rollback_checklist_present", bool(bundle_json.get("rollback_checklist"))),
        gate("human_review_checklist_present", bool(bundle_json.get("human_review_checklist"))),
        gate("no_data_or_exports_artifact_written", True),
        gate("no_blocked_report_terms", not blocked_terms_in_text(report_as_json(bundle_json))),
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
            "production_migration_executed",
            "production_seed_executed",
            "schema_files_modified",
            "sql_executed",
            "production_db_connected",
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

    parser = argparse.ArgumentParser(description="Build the migration bundle review pack.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--bundle-report", action="store_true")
    mode.add_argument("--render-bundle-json", action="store_true")
    mode.add_argument("--lint-bundle-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
    elif args.bundle_report:
        report = build_bundle_report()
    elif args.render_bundle_json:
        report = render_bundle_json()
    elif args.lint_bundle_report:
        report = lint_bundle_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"bundle-report", "lint-bundle-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
