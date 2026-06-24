from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import (  # noqa: E402
    cutover_readiness_matrix,
    formal_migration_proposal,
    production_migration_admission,
)
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


PACKAGE_VERSION = "production-migration-dry-run-package-v1"
ADR_PATH = ROOT / "docs" / "adr" / "ADR-production-migration-dry-run-package.md"
PACKAGE_STATUS = "Proposed"
SUPPORTED_MODES = ["contract-report", "package-report", "adr-check"]
PACKAGE_SECTIONS = (
    "Status",
    "Context",
    "Decision",
    "Dry-run Package Contents",
    "Schema Diff Outline",
    "Migration SQL Draft Outline",
    "Operator Checklist",
    "Validation Command Matrix",
    "Rollback Checklist",
    "Seed Artifact Checksum Review",
    "Explicit Non-goals",
    "Consequences",
)
DRY_RUN_PACKAGE_CONTENTS = (
    "schema diff outline",
    "migration SQL draft outline",
    "operator checklist",
    "validation command matrix",
    "rollback checklist",
    "seed artifact checksum review checklist",
)
SCHEMA_DIFF_OUTLINE = (
    "compare current formal schema draft with current db schema files",
    "report intended target tables",
    "report deferred Phase 2/3 tables",
    "report no executable schema change in this PR",
)
MIGRATION_SQL_DRAFT_OUTLINE = (
    "SQL draft is proposal text only",
    "SQL is not executed",
    "SQL is not written to db/postgres/001_init.sql",
    "SQL is not written to db/schema.sql",
)
OPERATOR_CHECKLIST = (
    "confirm backup point",
    "confirm maintenance window",
    "confirm rollback owner",
    "confirm seed artifact checksum",
    "confirm post-migration verification queries",
    "confirm emergency stop condition",
)
VALIDATION_COMMAND_MATRIX = (
    "pytest -q tests/test_production_migration_dry_run_package.py",
    "python scripts/platform/production_migration_dry_run_package.py --contract-report",
    "python scripts/platform/production_migration_dry_run_package.py --package-report",
    "python scripts/platform/production_migration_dry_run_package.py --adr-check",
    "python scripts/platform/production_migration_admission.py --admission-report",
    "python scripts/platform/formal_migration_proposal.py --proposal-report",
    "python scripts/platform/cutover_readiness_matrix.py --readiness-report",
)
ROLLBACK_CHECKLIST = (
    "backup point is named before any later migration PR",
    "restore path is named before any later migration PR",
    "rollback owner is named before any later migration PR",
    "verification queries are listed before any later migration PR",
    "emergency stop condition is listed before any later migration PR",
)
SEED_ARTIFACT_CHECKSUM_REVIEW = (
    "seed artifact checksum must be reviewed before any later seed step",
    "checksum review is manual confirmation only in this PR",
    "this PR does not write seed artifact files",
    "this PR does not apply seed data",
)
FORBIDDEN_CURRENT_PR_ACTIONS = (
    "no production migration",
    "no production seed",
    "no public schema write",
    "no production DB connection",
    "no data artifact write",
    "no export artifact write",
    "no schema file edits",
    "no seed artifact write",
)
NON_GOALS = (
    "does not execute production migration",
    "does not execute production seed",
    "does not modify formal schema files",
    "does not connect to production database",
    "does not write production tables",
    "does not write data paths",
    "does not write exports paths",
    "does not change evaluation metrics",
    "does not change business conclusions",
)
BOUNDARIES = (
    "package report is offline by default",
    "admission report is read through offline report API",
    "formal migration proposal is read through offline report API",
    "cutover readiness matrix is read with database evidence disabled",
    "canonical JSONL remains source-of-truth",
    "future production migration requires separate approved PR",
    "reports are stdout JSON only",
)
LIMITATIONS = (
    "dry-run package only",
    "no production database evidence is collected",
    "no formal schema file is updated",
    "no seed artifact is written",
    "no production action is executed",
)
FUTURE_WORK = (
    "PR #271 migration SQL draft renderer",
    "separate schema diff renderer",
    "separate production migration PR approval",
)
PACKAGE_GATES = (
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "package_status_is_proposed",
    "dry_run_package_only_true",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "future_production_migration_pr_required",
    "schema_diff_outline_declared",
    "migration_sql_draft_outline_declared",
    "operator_checklist_declared",
    "validation_command_matrix_declared",
    "rollback_checklist_declared",
    "seed_artifact_checksum_review_declared",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
)
ADR_RULES = (
    ("status_is_proposed", "Status is Proposed"),
    ("declares_dry_run_package_only", "dry_run_package_only=true"),
    ("production_migration_executed_false", "production_migration_executed=false"),
    ("production_seed_executed_false", "production_seed_executed=false"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("future_production_migration_pr_required", "future production migration PR required"),
    ("declares_no_production_migration", "no production migration"),
    ("declares_no_production_seed", "no production seed"),
    ("declares_no_schema_file_edits", "no schema file edits"),
    ("declares_schema_diff_outline", "## Schema Diff Outline"),
    ("declares_migration_sql_draft_outline", "## Migration SQL Draft Outline"),
    ("declares_operator_checklist", "## Operator Checklist"),
    ("declares_validation_command_matrix", "## Validation Command Matrix"),
    ("declares_rollback_checklist", "## Rollback Checklist"),
    ("declares_seed_artifact_checksum_review", "## Seed Artifact Checksum Review"),
)
ADR_BLOCKED_PHRASES = (
    "production_migration_executed=true",
    "production_migration_executed = true",
    "production_seed_executed=true",
    "production_seed_executed = true",
    "schema_files_modified=true",
    "schema_files_modified = true",
    "production migration ready",
    "production migration executed",
    "production seed executed",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "status": PACKAGE_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "source_reports": [
            "production_migration_admission.build_admission_report()",
            "formal_migration_proposal.build_proposal_report()",
            "cutover_readiness_matrix.build_readiness_report(include_db_evidence=False, env={})",
            "docs/adr/ADR-production-migration-dry-run-package.md",
        ],
        "package_sections": list(PACKAGE_SECTIONS),
        "dry_run_package_contents": list(DRY_RUN_PACKAGE_CONTENTS),
        "forbidden_current_pr_actions": list(FORBIDDEN_CURRENT_PR_ACTIONS),
        "validation_command_matrix": list(VALIDATION_COMMAND_MATRIX),
        "operator_checklist": list(OPERATOR_CHECKLIST),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "limitations": list(LIMITATIONS),
        "future_work": list(FUTURE_WORK),
    }
    assert_no_blocked_terms(report)
    return report


def build_package_report(
    adr_path: Path = ADR_PATH,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_errors: list[str] = []
    if admission_report is None:
        try:
            admission_report = production_migration_admission.build_admission_report()
        except Exception:
            admission_report = {}
            source_errors.append("production_migration_admission_available")
    if proposal_report is None:
        try:
            proposal_report = formal_migration_proposal.build_proposal_report()
        except Exception:
            proposal_report = {}
            source_errors.append("formal_migration_proposal_available")
    if readiness_report is None:
        try:
            readiness_report = cutover_readiness_matrix.build_readiness_report(
                include_db_evidence=False,
                env={},
            )
        except Exception:
            readiness_report = {}
            source_errors.append("cutover_readiness_report_available")

    adr_check = build_adr_check(adr_path)
    gates = build_package_gates(admission_report, proposal_report, readiness_report, adr_check, source_errors)
    failed = [gate_item["gate"] for gate_item in gates if not gate_item["passed"]]
    report = {
        "mode": "package-report",
        "package_version": PACKAGE_VERSION,
        "adr_path": relative_path(adr_path),
        "package_status": PACKAGE_STATUS,
        "dry_run_package_only": True,
        "production_migration_executed": False,
        "production_seed_executed": False,
        "schema_files_modified": False,
        "future_production_migration_pr_required": True,
        "admission_status": admission_report.get("admission_status"),
        "proposal_status": proposal_report.get("proposal_status"),
        "readiness_state": readiness_report.get("readiness_state"),
        "schema_diff_outline": list(SCHEMA_DIFF_OUTLINE),
        "migration_sql_draft_outline": list(MIGRATION_SQL_DRAFT_OUTLINE),
        "operator_checklist": list(OPERATOR_CHECKLIST),
        "validation_command_matrix": list(VALIDATION_COMMAND_MATRIX),
        "rollback_checklist": list(ROLLBACK_CHECKLIST),
        "seed_artifact_checksum_review": list(SEED_ARTIFACT_CHECKSUM_REVIEW),
        "forbidden_current_pr_actions": list(FORBIDDEN_CURRENT_PR_ACTIONS),
        "gates": gates,
        "blocking_failures": failed,
        "warnings": (
            list(admission_report.get("warnings", []))
            + list(proposal_report.get("warnings", []))
            + list(readiness_report.get("warnings", []))
        ),
    }
    assert_no_blocked_terms(report)
    return report


def build_package_gates(
    admission_report: Mapping[str, Any],
    proposal_report: Mapping[str, Any],
    readiness_report: Mapping[str, Any],
    adr_check: Mapping[str, Any],
    source_errors: Sequence[str],
) -> list[dict[str, Any]]:
    rule_map = {rule["rule"]: bool(rule["passed"]) for rule in adr_check.get("checked_rules", [])}
    return [
        gate("production_migration_admission_available", "production_migration_admission_available" not in source_errors and admission_report.get("mode") == "admission-report"),
        gate("formal_migration_proposal_available", "formal_migration_proposal_available" not in source_errors and proposal_report.get("mode") == "proposal-report"),
        gate("cutover_readiness_report_available", "cutover_readiness_report_available" not in source_errors and readiness_report.get("mode") == "readiness-report"),
        gate("package_status_is_proposed", PACKAGE_STATUS == "Proposed"),
        gate("dry_run_package_only_true", True),
        gate("production_migration_executed_false", True),
        gate("production_seed_executed_false", True),
        gate("schema_files_modified_false", True),
        gate("future_production_migration_pr_required", True),
        gate("schema_diff_outline_declared", rule_map.get("declares_schema_diff_outline", False)),
        gate("migration_sql_draft_outline_declared", rule_map.get("declares_migration_sql_draft_outline", False)),
        gate("operator_checklist_declared", rule_map.get("declares_operator_checklist", False)),
        gate("validation_command_matrix_declared", rule_map.get("declares_validation_command_matrix", False)),
        gate("rollback_checklist_declared", rule_map.get("declares_rollback_checklist", False)),
        gate("seed_artifact_checksum_review_declared", rule_map.get("declares_seed_artifact_checksum_review", False)),
        gate("no_data_or_exports_artifact_written", True),
        gate("no_blocked_report_terms", bool(adr_check.get("no_blocked_report_terms"))),
    ]


def gate(name: str, passed: bool) -> dict[str, Any]:
    return {"gate": name, "passed": bool(passed)}


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


def status_value(content: str) -> str | None:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "## status":
            for candidate in lines[index + 1 :]:
                if candidate.strip():
                    return candidate.strip().rstrip(".")
    return None


def blocked_terms_in_text(text: str) -> list[str]:
    normalized = text.lower()
    return [term for term in BLOCKED_REPORT_TERMS if term.lower() in normalized]


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def assert_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False, sort_keys=True).lower()
    for term in BLOCKED_REPORT_TERMS:
        if term.lower() in text:
            raise AssertionError(f"reserved report term found: {term}")


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build production migration dry-run package reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--package-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
    elif args.package_report:
        report = build_package_report()
    else:
        report = build_adr_check()
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"package-report", "adr-check"} and (
        report.get("failed") or report.get("blocking_failures")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
