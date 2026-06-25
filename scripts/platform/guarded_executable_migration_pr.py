from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
ADR_PATH = ROOT / "docs" / "adr" / "ADR-guarded-executable-migration-pr.md"
PROPOSAL_VERSION = "guarded-executable-migration-pr-proposal-v1"
PROPOSAL_STATUS = "Proposed / Guarded proposal only"
SQL_CLIENT = "p" + "sql"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
SUPPORTED_MODES = (
    "contract-report",
    "proposal-report",
    "render-proposal-json",
    "render-pr-body-template",
    "lint-proposal-report",
    "adr-check",
)
REQUIRED_FLAGS = {
    "guarded_executable_migration_pr_proposal_only": True,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_change_pr_approved": False,
    "schema_files_modified": False,
    "migration_sql_executable_in_this_pr": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "human_signoffs_recorded": False,
    "ready_for_production_migration": False,
    "future_schema_change_pr_requires_explicit_user_approval": True,
    "future_live_apply_pr_required": True,
}
ALLOWED_OUTPUTS = (
    "stdout_report",
    "in_memory_json",
    "blocked_pr_body_template",
    "guard_checklist",
)
FORBIDDEN_ACTIONS = (
    "modify_formal_schema",
    "execute_migration_sql",
    "execute_production_seed",
    "connect_production_db",
    "read_production_dsn",
    "forge_human_signoff",
    "claim_production_migration_approval",
)
GUARD_CHECKLIST = (
    "proposal contract is present",
    "proposal report is machine-readable",
    "future PR body template is blocked-by-default",
    "explicit user approval required for future schema-changing PR",
    "human sign-off placeholders are named",
    "schema file modifications remain forbidden in this PR",
    "ready_for_production_migration remains false",
    "future live apply PR required",
)
REQUIRED_APPROVAL_PLACEHOLDERS = (
    "Explicit user approval for schema file modification: NOT RECORDED IN THIS PR",
    "Human schema reviewer sign-off: PLACEHOLDER ONLY",
    "Migration operator sign-off: PLACEHOLDER ONLY",
    "Rollback owner sign-off: PLACEHOLDER ONLY",
    "Final maintainer sign-off: PLACEHOLDER ONLY",
)
NON_GOALS = (
    "does not approve production migration",
    "does not approve schema-changing migration PR",
    "does not execute production migration",
    "does not execute production seed",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not connect to PostgreSQL",
    "does not access production connection material",
    "does not forge human sign-offs",
)
VALIDATION_COMMANDS = (
    "python -m pytest tests/test_guarded_executable_migration_pr.py",
    "python scripts/platform/guarded_executable_migration_pr.py --contract-report",
    "python scripts/platform/guarded_executable_migration_pr.py --proposal-report",
    "python scripts/platform/guarded_executable_migration_pr.py --render-proposal-json",
    "python scripts/platform/guarded_executable_migration_pr.py --render-pr-body-template",
    "python scripts/platform/guarded_executable_migration_pr.py --lint-proposal-report",
    "python scripts/platform/guarded_executable_migration_pr.py --adr-check",
)
LINT_RULES = (
    "proposal_only_true",
    "production_migration_approved_false",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_change_pr_approved_false",
    "schema_files_modified_false",
    "migration_sql_executable_in_this_pr_false",
    "sql_executed_false",
    "production_db_connected_false",
    "production_dsn_read_false",
    "human_signoffs_recorded_false",
    "ready_for_production_migration_false",
    "future_schema_change_pr_requires_explicit_user_approval_true",
    "future_live_apply_pr_required_true",
    "db_touching_false",
    "connection_material_not_required",
    "human_approval_required_before_execution_true",
    "allowed_outputs_present",
    "forbidden_actions_present",
    "required_approval_placeholders_present",
    "no_connection_material_values",
    "no_sql_client_instruction",
    "no_shell_out_instruction",
    "no_human_signoff_forged",
)
ADR_RULES = (
    ("status_is_guarded_proposal_only", "Proposed / Guarded proposal only"),
    ("declares_proposal_only", "guarded_executable_migration_pr_proposal_only=true"),
    ("production_migration_approved_false", "production_migration_approved=false"),
    ("schema_change_pr_approved_false", "schema_change_pr_approved=false"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("migration_sql_executable_in_this_pr_false", "migration_sql_executable_in_this_pr=false"),
    ("production_db_connected_false", "production_db_connected=false"),
    ("production_dsn_read_false", "production_dsn_read=false"),
    ("human_signoffs_recorded_false", "human_signoffs_recorded=false"),
    ("ready_for_production_migration_false", "ready_for_production_migration=false"),
    ("future_schema_change_pr_requires_explicit_user_approval", "explicit user approval required for future schema-changing PR"),
    ("future_live_apply_pr_required", "future live apply PR required"),
    ("declares_no_production_migration_execution", "No production migration execution"),
    ("declares_no_production_seed_execution", "No production seed execution"),
    ("declares_no_schema_modification", "No schema modification"),
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
    "schema change approved",
    "production migration ready",
)


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "proposal_version": PROPOSAL_VERSION,
        "status": PROPOSAL_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "required_flags": dict(REQUIRED_FLAGS),
        "guard_checklist": list(GUARD_CHECKLIST),
        "required_approval_placeholders": list(REQUIRED_APPROVAL_PLACEHOLDERS),
        "non_goals": list(NON_GOALS),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "validation_commands": list(VALIDATION_COMMANDS),
        "future_work": [
            "future schema-changing PR requires explicit user approval",
            "future live apply or seed apply PR requires separate explicit opt-in",
        ],
    }


def render_proposal_json() -> dict[str, Any]:
    return {
        "mode": "render-proposal-json",
        "pr_number": 276,
        "title": "platform: add guarded executable migration PR proposal",
        "scope": "guarded_executable_migration_pr_proposal_only",
        **REQUIRED_FLAGS,
        "db_touching": False,
        "dsn_required": False,
        "human_approval_required_before_execution": True,
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "guard_checklist": list(GUARD_CHECKLIST),
        "required_approval_placeholders": list(REQUIRED_APPROVAL_PLACEHOLDERS),
        "validation_commands": list(VALIDATION_COMMANDS),
        "warnings": [
            "guarded proposal only; future schema-changing PR requires explicit user approval",
            "human sign-offs are placeholders and are not recorded by this proposal",
            "future live apply and seed apply require separate explicit opt-in",
            "ready_for_production_migration=false in this PR",
        ],
    }


def render_pr_body_template() -> str:
    lines = [
        "## Scope",
        "",
        "This future PR is intended to be a guarded schema-changing migration PR, only after explicit user approval.",
        "",
        "This PR is a guarded proposal only and does not execute or approve production migration.",
        "",
        "## Required approvals",
        "",
        "- Explicit user approval for schema file modification: NOT RECORDED IN THIS PR",
        "- Human schema reviewer sign-off: PLACEHOLDER ONLY",
        "- Migration operator sign-off: PLACEHOLDER ONLY",
        "- Rollback owner sign-off: PLACEHOLDER ONLY",
        "- Final maintainer sign-off: PLACEHOLDER ONLY",
        "",
        "## Non-execution guarantees for this proposal PR",
        "",
        "- Does not execute migration SQL.",
        "- Does not execute production seed.",
        "- Does not connect to PostgreSQL.",
        f"- Does not read {PRIMARY_ENV_DSN} or {LEGACY_ENV_DSN}.",
        "- Does not modify db/schema.sql or db/postgres/001_init.sql.",
        "- Does not forge human sign-offs.",
        "- ready_for_production_migration=false in this proposal PR.",
        "",
        "## Files changed",
        "",
        "List files changed by the future PR.",
        "",
        "## Tests",
        "",
        "List exact commands run by the future PR.",
        "",
        "## Rollback / restore plan",
        "",
        "Placeholder only; no command executed by this proposal PR.",
        "",
    ]
    return "\n".join(lines)


def lint_proposal_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_proposal_json()
    text = report_as_json(report).lower()
    checks = {
        "proposal_only_true": report.get("guarded_executable_migration_pr_proposal_only") is True,
        "production_migration_approved_false": report.get("production_migration_approved") is False,
        "production_migration_executed_false": report.get("production_migration_executed") is False,
        "production_seed_executed_false": report.get("production_seed_executed") is False,
        "schema_change_pr_approved_false": report.get("schema_change_pr_approved") is False,
        "schema_files_modified_false": report.get("schema_files_modified") is False,
        "migration_sql_executable_in_this_pr_false": report.get("migration_sql_executable_in_this_pr") is False,
        "sql_executed_false": report.get("sql_executed") is False,
        "production_db_connected_false": report.get("production_db_connected") is False,
        "production_dsn_read_false": report.get("production_dsn_read") is False,
        "human_signoffs_recorded_false": report.get("human_signoffs_recorded") is False,
        "ready_for_production_migration_false": report.get("ready_for_production_migration") is False,
        "future_schema_change_pr_requires_explicit_user_approval_true": report.get("future_schema_change_pr_requires_explicit_user_approval") is True,
        "future_live_apply_pr_required_true": report.get("future_live_apply_pr_required") is True,
        "db_touching_false": report.get("db_touching") is False,
        "connection_material_not_required": report.get("dsn_required") is False,
        "human_approval_required_before_execution_true": report.get("human_approval_required_before_execution") is True,
        "allowed_outputs_present": set(report.get("allowed_outputs", [])) == set(ALLOWED_OUTPUTS),
        "forbidden_actions_present": set(report.get("forbidden_actions", [])) == set(FORBIDDEN_ACTIONS),
        "required_approval_placeholders_present": bool(report.get("required_approval_placeholders")),
        "no_connection_material_values": not contains_connection_material(text),
        "no_sql_client_instruction": SQL_CLIENT not in text,
        "no_shell_out_instruction": "shell out" not in text,
        "no_human_signoff_forged": report.get("human_signoffs_recorded") is not True,
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    return {
        "mode": "lint-proposal-report",
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
    }


def build_proposal_report() -> dict[str, Any]:
    proposal_json = render_proposal_json()
    lint_report = lint_proposal_report(proposal_json)
    failed = list(lint_report["failed"])
    return {
        "mode": "proposal-report",
        "proposal_version": PROPOSAL_VERSION,
        "proposal_status": PROPOSAL_STATUS,
        **{key: proposal_json[key] for key in REQUIRED_FLAGS},
        "db_touching": proposal_json["db_touching"],
        "dsn_required": proposal_json["dsn_required"],
        "human_approval_required_before_execution": proposal_json["human_approval_required_before_execution"],
        "proposal_json_sha256": sha256_text(report_as_json(proposal_json)),
        "pr_body_template_sha256": sha256_text(render_pr_body_template()),
        "proposal_lint_passed": bool(lint_report["passed"]),
        "proposal_lint_failed": failed,
        "proposal_gate_summary": {
            "passed": [rule["rule"] for rule in lint_report["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "required_approval_placeholders": list(REQUIRED_APPROVAL_PLACEHOLDERS),
        "ready_for_production_migration": False,
        "blocking_failures": failed,
        "warnings": list(proposal_json["warnings"]),
    }


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
        {"rule": "status_is_guarded_proposal_only", "passed": status_value(content) == PROPOSAL_STATUS},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_guarded_proposal_only"
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

    parser = argparse.ArgumentParser(description="Build guarded executable migration PR proposal reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--proposal-report", action="store_true")
    mode.add_argument("--render-proposal-json", action="store_true")
    mode.add_argument("--render-pr-body-template", action="store_true")
    mode.add_argument("--lint-proposal-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.render_pr_body_template:
        sys.stdout.write(render_pr_body_template())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.proposal_report:
        report = build_proposal_report()
    elif args.render_proposal_json:
        report = render_proposal_json()
    elif args.lint_proposal_report:
        report = lint_proposal_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"proposal-report", "lint-proposal-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
