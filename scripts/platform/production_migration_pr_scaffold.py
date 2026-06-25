from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
ADR_PATH = ROOT / "docs" / "adr" / "ADR-production-migration-pr-scaffold.md"
SCAFFOLD_VERSION = "production-migration-pr-scaffold-v1"
SCAFFOLD_STATUS = "Proposed / Scaffold only"
SQL_CLIENT = "p" + "sql"
SUPPORTED_MODES = (
    "contract-report",
    "scaffold-report",
    "render-scaffold-json",
    "lint-scaffold-report",
    "adr-check",
)
REQUIRED_FLAGS = {
    "production_migration_pr_scaffold_only": True,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_files_modified": False,
    "sql_executed": False,
    "production_db_connected": False,
    "human_signoffs_recorded": False,
    "ready_for_production_migration": False,
    "future_executable_migration_pr_required": True,
}
ALLOWED_OUTPUTS = (
    "stdout_report",
    "in_memory_json",
    "scaffold_checklist",
)
FORBIDDEN_ACTIONS = (
    "modify_formal_schema",
    "execute_migration_sql",
    "execute_production_seed",
    "connect_production_db",
    "read_production_dsn",
    "forge_human_signoff",
)
SCAFFOLD_CHECKLIST = (
    "scaffold contract is present",
    "scaffold report is machine-readable",
    "human sign-off placeholders are named",
    "risk checklist is named",
    "validation checklist is named",
    "forbidden production actions are named",
    "ready_for_production_migration remains false",
    "future executable migration PR required",
)
HUMAN_SIGNOFF_PLACEHOLDERS = (
    "schema reviewer sign-off placeholder",
    "source-of-truth reviewer sign-off placeholder",
    "migration operator sign-off placeholder",
    "rollback owner sign-off placeholder",
    "seed reviewer sign-off placeholder",
    "final maintainer sign-off placeholder",
)
RISK_CHECKLIST = (
    "freeze checklist is not execution approval",
    "schema changes remain out of scope",
    "production seed remains out of scope",
    "database connectivity remains out of scope",
    "human sign-offs are placeholders only",
    "future executable migration PR remains separately required",
)
VALIDATION_COMMANDS = (
    "python -m pytest tests/test_production_migration_pr_scaffold.py",
    "python scripts/platform/production_migration_pr_scaffold.py --contract-report",
    "python scripts/platform/production_migration_pr_scaffold.py --scaffold-report",
    "python scripts/platform/production_migration_pr_scaffold.py --render-scaffold-json",
    "python scripts/platform/production_migration_pr_scaffold.py --lint-scaffold-report",
    "python scripts/platform/production_migration_pr_scaffold.py --adr-check",
)
NON_GOALS = (
    "does not approve production migration",
    "does not execute production migration",
    "does not execute production seed",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not connect to PostgreSQL",
    "does not access production connection material",
    "does not forge human sign-offs",
)
LINT_RULES = (
    "scaffold_only_true",
    "production_migration_approved_false",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "human_signoffs_recorded_false",
    "ready_for_production_migration_false",
    "future_executable_migration_pr_required_true",
    "db_touching_false",
    "connection_material_not_required",
    "human_approval_required_before_execution_true",
    "allowed_outputs_present",
    "forbidden_actions_present",
    "human_placeholders_present",
    "no_connection_material_values",
    "no_sql_client_instruction",
    "no_shell_out_instruction",
    "no_human_signoff_forged",
)
ADR_RULES = (
    ("status_is_scaffold_only", "Proposed / Scaffold only"),
    ("declares_scaffold_only", "production_migration_pr_scaffold_only=true"),
    ("production_migration_approved_false", "production_migration_approved=false"),
    ("production_migration_executed_false", "production_migration_executed=false"),
    ("production_seed_executed_false", "production_seed_executed=false"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("sql_executed_false", "sql_executed=false"),
    ("production_db_connected_false", "production_db_connected=false"),
    ("human_signoffs_recorded_false", "human_signoffs_recorded=false"),
    ("ready_for_production_migration_false", "ready_for_production_migration=false"),
    ("future_executable_migration_pr_required", "future executable migration PR required"),
    ("declares_no_production_migration_execution", "No production migration execution"),
    ("declares_no_production_seed_execution", "No production seed execution"),
    ("declares_no_db_connection", "No DB connection"),
    ("declares_no_dsn_access", "No DSN access"),
    ("declares_no_human_signoff_forged", "No human sign-off forged"),
)
ADR_BLOCKED_PHRASES = (
    *(
        f"{name}=false"
        for name, expected in REQUIRED_FLAGS.items()
        if expected is True
    ),
    *(
        f"{name} = false"
        for name, expected in REQUIRED_FLAGS.items()
        if expected is True
    ),
    *(
        f"{name}=true"
        for name, expected in REQUIRED_FLAGS.items()
        if expected is False
    ),
    *(
        f"{name} = true"
        for name, expected in REQUIRED_FLAGS.items()
        if expected is False
    ),
    "production migration approved",
    "production migration ready",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "scaffold_version": SCAFFOLD_VERSION,
        "status": SCAFFOLD_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "required_flags": dict(REQUIRED_FLAGS),
        "scaffold_checklist": list(SCAFFOLD_CHECKLIST),
        "human_signoff_placeholders": list(HUMAN_SIGNOFF_PLACEHOLDERS),
        "risk_checklist": list(RISK_CHECKLIST),
        "non_goals": list(NON_GOALS),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "validation_commands": list(VALIDATION_COMMANDS),
        "future_work": [
            "future executable migration PR requires explicit user approval",
            "future seed or live apply PR requires separate explicit opt-in",
        ],
    }
    return report


def render_scaffold_json() -> dict[str, Any]:
    report = {
        "mode": "render-scaffold-json",
        "pr_number": 275,
        "title": "platform: add production migration PR scaffold",
        "scope": "production_migration_pr_scaffold_only",
        **REQUIRED_FLAGS,
        "db_touching": False,
        "dsn_required": False,
        "human_approval_required_before_execution": True,
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "human_signoff_placeholders": list(HUMAN_SIGNOFF_PLACEHOLDERS),
        "risk_checklist": list(RISK_CHECKLIST),
        "validation_commands": list(VALIDATION_COMMANDS),
        "warnings": [
            "scaffold only; future executable migration PR remains separately required",
            "human sign-offs are placeholders and are not recorded by this scaffold",
            "ready_for_production_migration=false in this PR",
        ],
    }
    return report


def lint_scaffold_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_scaffold_json()
    text = report_as_json(report).lower()
    checks = {
        "scaffold_only_true": report.get("production_migration_pr_scaffold_only") is True,
        "production_migration_approved_false": report.get("production_migration_approved") is False,
        "production_migration_executed_false": report.get("production_migration_executed") is False,
        "production_seed_executed_false": report.get("production_seed_executed") is False,
        "schema_files_modified_false": report.get("schema_files_modified") is False,
        "sql_executed_false": report.get("sql_executed") is False,
        "production_db_connected_false": report.get("production_db_connected") is False,
        "human_signoffs_recorded_false": report.get("human_signoffs_recorded") is False,
        "ready_for_production_migration_false": report.get("ready_for_production_migration") is False,
        "future_executable_migration_pr_required_true": report.get("future_executable_migration_pr_required") is True,
        "db_touching_false": report.get("db_touching") is False,
        "connection_material_not_required": report.get("dsn_required") is False,
        "human_approval_required_before_execution_true": report.get("human_approval_required_before_execution") is True,
        "allowed_outputs_present": set(report.get("allowed_outputs", [])) == set(ALLOWED_OUTPUTS),
        "forbidden_actions_present": set(report.get("forbidden_actions", [])) == set(FORBIDDEN_ACTIONS),
        "human_placeholders_present": bool(report.get("human_signoff_placeholders")),
        "no_connection_material_values": not contains_connection_material(text),
        "no_sql_client_instruction": SQL_CLIENT not in text,
        "no_shell_out_instruction": "shell out" not in text,
        "no_human_signoff_forged": report.get("human_signoffs_recorded") is not True,
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    return {
        "mode": "lint-scaffold-report",
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
    }


def build_scaffold_report() -> dict[str, Any]:
    scaffold_json = render_scaffold_json()
    lint_report = lint_scaffold_report(scaffold_json)
    failed = list(lint_report["failed"])
    report = {
        "mode": "scaffold-report",
        "scaffold_version": SCAFFOLD_VERSION,
        "scaffold_status": SCAFFOLD_STATUS,
        **{key: scaffold_json[key] for key in REQUIRED_FLAGS},
        "db_touching": scaffold_json["db_touching"],
        "dsn_required": scaffold_json["dsn_required"],
        "human_approval_required_before_execution": scaffold_json["human_approval_required_before_execution"],
        "scaffold_json_sha256": sha256_text(report_as_json(scaffold_json)),
        "scaffold_lint_passed": bool(lint_report["passed"]),
        "scaffold_lint_failed": failed,
        "scaffold_gate_summary": {
            "passed": [rule["rule"] for rule in lint_report["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "human_signoff_placeholders": list(HUMAN_SIGNOFF_PLACEHOLDERS),
        "ready_for_production_migration": False,
        "blocking_failures": failed,
        "warnings": list(scaffold_json["warnings"]),
    }
    return report


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
        }

    content = adr_path.read_text(encoding="utf-8")
    normalized = normalize_text(content)
    checked_rules = [
        {"rule": "status_is_scaffold_only", "passed": status_value(content) == SCAFFOLD_STATUS},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_scaffold_only"
        ],
    ]
    blocked_phrases = [phrase for phrase in ADR_BLOCKED_PHRASES if phrase in normalized]
    checked_rules.append({"rule": "no_approval_or_execution_claim", "passed": not blocked_phrases})
    failed = [rule["rule"] for rule in checked_rules if not rule["passed"]]
    return {
        "mode": "adr-check",
        "adr_path": relative_path(adr_path),
        "adr_exists": True,
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
    }


def status_value(content: str) -> str | None:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "## status":
            for candidate in lines[index + 1 :]:
                if candidate.strip():
                    return candidate.strip().rstrip(".")
    return None


def contains_connection_material(text: str) -> bool:
    tokens = (
        "postgres://",
        "postgresql://",
        "password=",
        "connection string",
        "credential value",
    )
    return any(token in text for token in tokens)


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

    parser = argparse.ArgumentParser(description="Build the production migration PR scaffold reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--scaffold-report", action="store_true")
    mode.add_argument("--render-scaffold-json", action="store_true")
    mode.add_argument("--lint-scaffold-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
    elif args.scaffold_report:
        report = build_scaffold_report()
    elif args.render_scaffold_json:
        report = render_scaffold_json()
    elif args.lint_scaffold_report:
        report = lint_scaffold_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"scaffold-report", "lint-scaffold-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
