from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import cutover_readiness_matrix, formal_migration_proposal  # noqa: E402
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


ADMISSION_VERSION = "production-migration-admission-v1"
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-production-migration-pr-admission.md"
ADMISSION_STATUS = "Proposed"
SUPPORTED_MODES = ["contract-report", "admission-report", "adr-check"]
ADMISSION_SECTIONS = (
    "Status",
    "Context",
    "Decision",
    "Allowed Future Production Migration PR File Scope",
    "Forbidden In This Admission PR",
    "Required Machine Gates",
    "Required Human Gates",
    "Required Rollback Plan",
    "Explicit Non-goals",
    "Consequences",
)
ALLOWED_FUTURE_FILE_SCOPE = (
    "db/schema.sql",
    "db/postgres/001_init.sql",
    "migration-specific docs or ADR",
    "migration validation tests",
)
FORBIDDEN_CURRENT_PR_ACTIONS = (
    "no production migration",
    "no production seed",
    "no public schema write",
    "no production DB connection",
    "no data artifact write",
    "no export artifact write",
    "no schema file edits",
)
MACHINE_GATES = (
    "schema diff generated",
    "migration SQL linted",
    "full validation suite green",
    "cutover readiness matrix green",
    "dry apply rehearsal green",
    "rollback / restore rehearsal green",
    "seed artifact checksum reviewed",
)
HUMAN_GATES = (
    "schema reviewer sign-off",
    "data/source-of-truth reviewer sign-off",
    "rollback owner sign-off",
    "operator sign-off",
    "final maintainer sign-off",
)
ROLLBACK_PLAN_REQUIREMENTS = (
    "backup point identified",
    "restore path documented",
    "rollback timing documented",
    "verification queries documented",
    "emergency stop condition documented",
)
NON_GOALS = (
    "does not execute production migration",
    "does not execute production seed",
    "does not modify formal schema files",
    "does not connect to production database",
    "does not write data paths",
    "does not write exports paths",
    "does not change business conclusions",
)
BOUNDARIES = (
    "admission report is offline by default",
    "formal migration proposal is read through offline report API",
    "cutover readiness matrix is read with database evidence disabled",
    "canonical JSONL remains source-of-truth",
    "production migration requires separate approved PR",
    "reports are stdout JSON only",
)
LIMITATIONS = (
    "admission card only",
    "no production database evidence is collected",
    "no formal schema file is updated",
    "no seed artifact is written",
)
FUTURE_WORK = (
    "PR #270 production migration dry-run package",
    "separate schema diff rendering",
    "separate migration SQL draft",
    "separate operator checklist",
    "separate production migration PR approval",
)
ADMISSION_GATES = (
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "proposal_status_is_proposed",
    "admission_status_is_proposed",
    "admission_only_true",
    "production_migration_executed_false",
    "future_production_migration_pr_required",
    "allowed_future_file_scope_declared",
    "current_pr_forbids_schema_file_edits",
    "current_pr_forbids_production_migration",
    "current_pr_forbids_production_seed",
    "current_pr_forbids_public_schema_write",
    "machine_gates_declared",
    "human_gates_declared",
    "rollback_plan_declared",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
)
ADR_RULES = (
    ("status_is_proposed", "Status is Proposed"),
    ("declares_admission_only", "admission_only=true"),
    ("production_migration_executed_false", "production_migration_executed=false"),
    ("future_production_migration_pr_required", "future production migration PR required"),
    ("declares_no_production_migration", "no production migration in this PR"),
    ("declares_no_production_seed", "no production seed in this PR"),
    ("declares_no_schema_file_edits", "no schema file edits in this PR"),
    ("declares_allowed_future_file_scope", "Allowed Future Production Migration PR File Scope"),
    ("declares_required_machine_gates", "Required Machine Gates"),
    ("declares_required_human_gates", "Required Human Gates"),
    ("declares_rollback_plan", "Required Rollback Plan"),
)
ADR_BLOCKED_PHRASES = (
    "production_migration_executed=true",
    "production_migration_executed = true",
    "ready_for_production_migration=true",
    "ready_for_production_migration = true",
    "production migration ready",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "admission_version": ADMISSION_VERSION,
        "status": ADMISSION_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "source_reports": [
            "formal_migration_proposal.build_proposal_report()",
            "cutover_readiness_matrix.build_readiness_report(include_db_evidence=False, env={})",
            "archive/docs/adr/ADR-production-migration-pr-admission.md",
        ],
        "admission_sections": list(ADMISSION_SECTIONS),
        "allowed_future_file_scope": list(ALLOWED_FUTURE_FILE_SCOPE),
        "forbidden_current_pr_actions": list(FORBIDDEN_CURRENT_PR_ACTIONS),
        "machine_gates": list(MACHINE_GATES),
        "human_gates": list(HUMAN_GATES),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "limitations": list(LIMITATIONS),
        "future_work": list(FUTURE_WORK),
    }
    assert_no_blocked_terms(report)
    return report


def build_admission_report(
    adr_path: Path = ADR_PATH,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_errors: list[str] = []
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
    gates = build_admission_gates(proposal_report, readiness_report, adr_check, source_errors)
    failed = [gate_item["gate"] for gate_item in gates if not gate_item["passed"]]
    report = {
        "mode": "admission-report",
        "admission_version": ADMISSION_VERSION,
        "adr_path": relative_path(adr_path),
        "proposal_status": proposal_report.get("proposal_status"),
        "readiness_state": readiness_report.get("readiness_state"),
        "ready_for_next_stage": not failed,
        "ready_for_production_migration": False,
        "admission_status": ADMISSION_STATUS,
        "admission_only": True,
        "production_migration_executed": False,
        "future_production_migration_pr_required": True,
        "allowed_future_file_scope": list(ALLOWED_FUTURE_FILE_SCOPE),
        "forbidden_current_pr_actions": list(FORBIDDEN_CURRENT_PR_ACTIONS),
        "machine_gates": list(MACHINE_GATES),
        "human_gates": list(HUMAN_GATES),
        "rollback_plan_requirements": list(ROLLBACK_PLAN_REQUIREMENTS),
        "gates": gates,
        "blocking_failures": failed,
        "warnings": list(proposal_report.get("warnings", [])) + list(readiness_report.get("warnings", [])),
    }
    assert_no_blocked_terms(report)
    return report


def build_admission_gates(
    proposal_report: Mapping[str, Any],
    readiness_report: Mapping[str, Any],
    adr_check: Mapping[str, Any],
    source_errors: Sequence[str],
) -> list[dict[str, Any]]:
    rule_map = {rule["rule"]: bool(rule["passed"]) for rule in adr_check.get("checked_rules", [])}
    return [
        gate("formal_migration_proposal_available", "formal_migration_proposal_available" not in source_errors and proposal_report.get("mode") == "proposal-report"),
        gate("cutover_readiness_report_available", "cutover_readiness_report_available" not in source_errors and readiness_report.get("mode") == "readiness-report"),
        gate("proposal_status_is_proposed", proposal_report.get("proposal_status") == "Proposed"),
        gate("admission_status_is_proposed", ADMISSION_STATUS == "Proposed"),
        gate("admission_only_true", True),
        gate("production_migration_executed_false", True),
        gate("future_production_migration_pr_required", True),
        gate("allowed_future_file_scope_declared", rule_map.get("declares_allowed_future_file_scope", False)),
        gate("current_pr_forbids_schema_file_edits", rule_map.get("declares_no_schema_file_edits", False)),
        gate("current_pr_forbids_production_migration", rule_map.get("declares_no_production_migration", False)),
        gate("current_pr_forbids_production_seed", rule_map.get("declares_no_production_seed", False)),
        gate("current_pr_forbids_public_schema_write", "no public schema write" in FORBIDDEN_CURRENT_PR_ACTIONS),
        gate("machine_gates_declared", rule_map.get("declares_required_machine_gates", False)),
        gate("human_gates_declared", rule_map.get("declares_required_human_gates", False)),
        gate("rollback_plan_declared", rule_map.get("declares_rollback_plan", False)),
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

    parser = argparse.ArgumentParser(description="Build production migration PR admission reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--admission-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
    elif args.admission_report:
        report = build_admission_report()
    else:
        report = build_adr_check()
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"admission-report", "adr-check"} and (
        report.get("failed") or report.get("blocking_failures")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
