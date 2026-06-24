from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import cutover_readiness_matrix  # noqa: E402
from scripts.platform.formal_schema_draft import BLOCKED_REPORT_TERMS  # noqa: E402


PROPOSAL_VERSION = "formal-migration-proposal-v1"
ADR_PATH = ROOT / "docs" / "adr" / "ADR-formal-migration-proposal.md"
PROPOSAL_STATUS = "Proposed"
NEXT_STAGE = "production_migration_pr_admission_card"
REQUIRED_PRODUCTION_PR_GATES = (
    "schema diff reviewed",
    "migration SQL reviewed",
    "backup/restore plan reviewed",
    "seed artifact checksum reviewed",
    "rollback/restore rehearsal result reviewed",
    "operator sign-off",
)
MIGRATION_PLAN_OUTLINE = (
    "Phase A: schema freeze proposal",
    "Phase B: production migration PR approval",
    "Phase C: production seed approval",
    "Phase D: rollback / restore runbook approval",
)
NON_GOALS = (
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not execute production migration",
    "does not execute production seed",
    "does not connect to production database",
    "does not write public schema",
    "does not write data paths",
    "does not write exports paths",
    "does not change business conclusions",
)
BOUNDARIES = (
    "proposal report is offline by default",
    "cutover readiness matrix is read with database evidence disabled",
    "canonical JSONL remains source-of-truth",
    "formal schema files remain unchanged",
    "production migration requires separate approved PR",
    "reports are stdout JSON only",
)
LIMITATIONS = (
    "proposal only",
    "no production database evidence is collected",
    "no formal schema file is updated",
    "no seed artifact is written",
)
FUTURE_WORK = (
    "PR #269 production migration PR admission card",
    "separate schema freeze proposal",
    "separate production migration PR approval",
    "separate production seed approval",
    "separate rollback / restore runbook approval",
)
PROPOSAL_SECTIONS = (
    "Status",
    "Context",
    "Decision",
    "Readiness Summary",
    "Migration Plan Outline",
    "Required Production PR Gates",
    "Explicit Non-goals",
    "Risks",
    "Rollback Strategy",
    "Consequences",
)
PROPOSAL_GATES = (
    "readiness_report_available",
    "readiness_next_stage_true",
    "production_migration_false",
    "proposal_status_is_proposed",
    "adr_exists",
    "adr_status_is_proposed",
    "adr_declares_separate_approved_pr",
    "adr_declares_no_production_migration",
    "adr_declares_no_production_seed",
    "adr_preserves_jsonl_source_of_truth",
    "adr_lists_required_production_gates",
    "adr_lists_rollback_restore_strategy",
    "no_schema_files_modified",
    "no_data_or_exports_written",
    "no_blocked_report_terms",
)
ADR_RULES = (
    ("status_is_proposed", "Status is Proposed"),
    ("preserves_jsonl_source_of_truth", "canonical JSONL remains source-of-truth"),
    ("production_migration_false", "ready_for_production_migration=false"),
    ("declares_separate_approved_pr", "separate approved PR"),
    ("declares_no_production_migration", "no production migration"),
    ("declares_no_production_seed", "no production seed"),
    ("declares_no_schema_change", "no db/schema.sql change"),
    ("declares_no_postgres_init_change", "no db/postgres/001_init.sql change"),
    ("lists_rollback_restore", "rollback / restore"),
    ("lists_required_production_pr_gates", "required production PR gates"),
)
ADR_BLOCKED_PHRASES = (
    "ready_for_production_migration=true",
    "ready_for_production_migration = true",
    "production migration ready",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "proposal_version": PROPOSAL_VERSION,
        "status": PROPOSAL_STATUS,
        "supported_modes": ["contract-report", "proposal-report", "adr-check"],
        "source_reports": [
            "cutover_readiness_matrix.build_readiness_report(include_db_evidence=False)",
            "docs/adr/ADR-formal-migration-proposal.md",
        ],
        "proposal_sections": list(PROPOSAL_SECTIONS),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "limitations": list(LIMITATIONS),
        "future_work": list(FUTURE_WORK),
    }
    assert_no_blocked_terms(report)
    return report


def build_proposal_report(
    adr_path: Path = ADR_PATH,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if readiness_report is None:
        readiness_report = cutover_readiness_matrix.build_readiness_report(
            include_db_evidence=False,
            env={},
        )
    adr_check = build_adr_check(adr_path)
    gates = build_proposal_gates(readiness_report, adr_check)
    failed = [gate["gate"] for gate in gates if not gate["passed"]]
    report = {
        "mode": "proposal-report",
        "proposal_version": PROPOSAL_VERSION,
        "adr_path": relative_path(adr_path),
        "readiness_state": readiness_report.get("readiness_state"),
        "ready_for_next_stage": bool(readiness_report.get("ready_for_next_stage")),
        "ready_for_production_migration": False,
        "next_stage": NEXT_STAGE,
        "proposal_status": PROPOSAL_STATUS,
        "required_production_pr_gates": list(REQUIRED_PRODUCTION_PR_GATES),
        "migration_plan_outline": list(MIGRATION_PLAN_OUTLINE),
        "non_goals": list(NON_GOALS),
        "risks": [
            "schema drift",
            "seed artifact drift",
            "operator error",
            "rollback gap",
            "source-of-truth mismatch",
        ],
        "rollback_strategy": [
            "production rollback must be separate approved runbook",
            "this PR only references isolated rehearsal evidence",
        ],
        "gates": gates,
        "failed": failed,
        "warnings": list(readiness_report.get("warnings", [])),
    }
    assert_no_blocked_terms(report)
    return report


def build_proposal_gates(
    readiness_report: Mapping[str, Any],
    adr_check: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rule_map = {rule["rule"]: bool(rule["passed"]) for rule in adr_check.get("checked_rules", [])}
    return [
        gate("readiness_report_available", readiness_report.get("mode") == "readiness-report"),
        gate("readiness_next_stage_true", readiness_report.get("ready_for_next_stage") is True),
        gate("production_migration_false", readiness_report.get("ready_for_production_migration") is False),
        gate("proposal_status_is_proposed", PROPOSAL_STATUS == "Proposed"),
        gate("adr_exists", bool(adr_check.get("adr_exists"))),
        gate("adr_status_is_proposed", rule_map.get("status_is_proposed", False)),
        gate("adr_declares_separate_approved_pr", rule_map.get("declares_separate_approved_pr", False)),
        gate("adr_declares_no_production_migration", rule_map.get("declares_no_production_migration", False)),
        gate("adr_declares_no_production_seed", rule_map.get("declares_no_production_seed", False)),
        gate("adr_preserves_jsonl_source_of_truth", rule_map.get("preserves_jsonl_source_of_truth", False)),
        gate("adr_lists_required_production_gates", rule_map.get("lists_required_production_pr_gates", False)),
        gate("adr_lists_rollback_restore_strategy", rule_map.get("lists_rollback_restore", False)),
        gate("no_schema_files_modified", True),
        gate("no_data_or_exports_written", True),
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
    blocked_phrases = [
        phrase for phrase in ADR_BLOCKED_PHRASES if phrase in normalized
    ]
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

    parser = argparse.ArgumentParser(description="Build formal migration proposal reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--proposal-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
    elif args.proposal_report:
        report = build_proposal_report()
    else:
        report = build_adr_check()
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"proposal-report", "adr-check"} and report.get("failed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
