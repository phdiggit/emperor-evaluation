from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-schema-change-pr-prep-pack.md"
PREP_PACK_VERSION = "schema-change-pr-prep-pack-v1"
PREP_PACK_STATUS = "Proposed / Preparation pack only"
SQL_CLIENT = "p" + "sql"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
SUPPORTED_MODES = (
    "contract-report",
    "prep-pack-report",
    "render-prep-json",
    "render-pr-body-template",
    "lint-prep-pack-report",
    "adr-check",
)
REQUIRED_FLAGS = {
    "schema_change_pr_prep_pack_only": True,
    "schema_change_pr_approved": False,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_files_modified": False,
    "migration_sql_executable_in_this_pr": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "human_signoffs_recorded": False,
    "ready_for_schema_change_pr": False,
    "ready_for_production_migration": False,
    "future_schema_change_pr_required": True,
    "future_live_apply_pr_required": True,
    "future_seed_apply_pr_required": True,
}
ALLOWED_OUTPUTS = (
    "stdout_report",
    "in_memory_json",
    "blocked_pr_body_template",
    "prep_checklist",
)
FORBIDDEN_ACTIONS = (
    "modify_formal_schema",
    "emit_executable_migration_sql_artifact",
    "execute_migration_sql",
    "execute_production_seed",
    "connect_production_db",
    "read_production_dsn",
    "forge_human_signoff",
    "claim_schema_change_pr_approval",
)
GUARD_CHECKLIST = (
    "prep pack contract is present",
    "prep pack report is machine-readable",
    "future PR body template is blocked-by-default",
    "schema file changes remain placeholders",
    "required user approval remains not recorded",
    "rollback and restore plan remains placeholder only",
    "ready_for_schema_change_pr remains false",
    "future live and seed apply PRs remain required",
)
REQUIRED_APPROVAL_PLACEHOLDERS = (
    "Explicit user approval for schema file modification: NOT RECORDED IN THIS PR",
    "Human schema reviewer sign-off: PLACEHOLDER ONLY",
    "Migration operator sign-off: PLACEHOLDER ONLY",
    "Rollback owner sign-off: PLACEHOLDER ONLY",
    "Final maintainer sign-off: PLACEHOLDER ONLY",
)
SCHEMA_CHANGE_PLACEHOLDER_SECTIONS = (
    "intended schema files placeholder",
    "proposed schema change summary placeholder",
    "migration SQL source placeholder",
    "schema review checklist placeholder",
)
ROLLBACK_RESTORE_PLACEHOLDERS = (
    "rollback owner placeholder",
    "restore point placeholder",
    "rollback validation placeholder",
    "emergency stop condition placeholder",
)
NON_GOALS = (
    "does not approve production migration",
    "does not approve schema-changing PR",
    "does not execute production migration",
    "does not execute production seed",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not emit executable migration SQL artifact",
    "does not connect to PostgreSQL",
    "does not access production connection material",
    "does not forge human sign-offs",
)
VALIDATION_COMMANDS = (
    "python -m pytest tests/test_schema_change_pr_prep_pack.py",
    "python scripts/platform/schema_change_pr_prep_pack.py --contract-report",
    "python scripts/platform/schema_change_pr_prep_pack.py --prep-pack-report",
    "python scripts/platform/schema_change_pr_prep_pack.py --render-prep-json",
    "python scripts/platform/schema_change_pr_prep_pack.py --render-pr-body-template",
    "python scripts/platform/schema_change_pr_prep_pack.py --lint-prep-pack-report",
    "python scripts/platform/schema_change_pr_prep_pack.py --adr-check",
)
LINT_RULES = (
    "schema_change_pr_prep_pack_only_true",
    "schema_change_pr_approved_false",
    "production_migration_approved_false",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "migration_sql_executable_in_this_pr_false",
    "sql_executed_false",
    "production_db_connected_false",
    "production_dsn_read_false",
    "human_signoffs_recorded_false",
    "ready_for_schema_change_pr_false",
    "ready_for_production_migration_false",
    "future_schema_change_pr_required_true",
    "future_live_apply_pr_required_true",
    "future_seed_apply_pr_required_true",
    "db_touching_false",
    "connection_material_not_required",
    "human_approval_required_before_schema_change_true",
    "required_approval_placeholders_present",
    "schema_change_placeholders_present",
    "rollback_restore_placeholders_present",
    "allowed_outputs_present",
    "forbidden_actions_present",
    "no_connection_material_values",
    "no_sql_client_instruction",
    "no_shell_out_instruction",
    "no_schema_change_approval_claim",
    "no_human_signoff_forged",
)
ADR_RULES = (
    ("status_is_preparation_pack_only", "Proposed / Preparation pack only"),
    ("declares_prep_pack_only", "schema_change_pr_prep_pack_only=true"),
    ("schema_change_pr_approved_false", "schema_change_pr_approved=false"),
    ("production_migration_approved_false", "production_migration_approved=false"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("migration_sql_executable_in_this_pr_false", "migration_sql_executable_in_this_pr=false"),
    ("production_db_connected_false", "production_db_connected=false"),
    ("production_dsn_read_false", "production_dsn_read=false"),
    ("ready_for_schema_change_pr_false", "ready_for_schema_change_pr=false"),
    ("ready_for_production_migration_false", "ready_for_production_migration=false"),
    ("future_schema_change_pr_required", "future_schema_change_pr_required=true"),
    ("future_live_apply_pr_required", "future_live_apply_pr_required=true"),
    ("future_seed_apply_pr_required", "future_seed_apply_pr_required=true"),
    ("declares_no_production_migration_execution", "No production migration execution"),
    ("declares_no_production_seed_execution", "No production seed execution"),
    ("declares_no_schema_modification", "No schema modification"),
    ("declares_no_db_connection", "No DB connection"),
    ("declares_no_dsn_access", "No DSN access"),
    ("declares_no_sql_execution", "No executable SQL in this PR"),
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
    "schema-changing PR approved",
    "production migration ready",
)


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "prep_pack_version": PREP_PACK_VERSION,
        "status": PREP_PACK_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "required_flags": dict(REQUIRED_FLAGS),
        "guard_checklist": list(GUARD_CHECKLIST),
        "required_approval_placeholders": list(REQUIRED_APPROVAL_PLACEHOLDERS),
        "schema_change_placeholder_sections": list(SCHEMA_CHANGE_PLACEHOLDER_SECTIONS),
        "rollback_restore_placeholders": list(ROLLBACK_RESTORE_PLACEHOLDERS),
        "non_goals": list(NON_GOALS),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "validation_commands": list(VALIDATION_COMMANDS),
        "future_work": [
            "future schema-changing PR requires explicit user approval",
            "future live apply PR requires separate explicit opt-in",
            "future seed apply PR requires separate explicit opt-in",
        ],
    }


def render_prep_json() -> dict[str, Any]:
    return {
        "mode": "render-prep-json",
        "pr_number": 277,
        "title": "platform: add schema-change PR preparation pack",
        "scope": "schema_change_pr_prep_pack_only",
        **REQUIRED_FLAGS,
        "db_touching": False,
        "dsn_required": False,
        "human_approval_required_before_schema_change": True,
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "guard_checklist": list(GUARD_CHECKLIST),
        "required_approval_placeholders": list(REQUIRED_APPROVAL_PLACEHOLDERS),
        "schema_change_placeholder_sections": list(SCHEMA_CHANGE_PLACEHOLDER_SECTIONS),
        "rollback_restore_placeholders": list(ROLLBACK_RESTORE_PLACEHOLDERS),
        "validation_commands": list(VALIDATION_COMMANDS),
        "warnings": [
            "preparation pack only; future schema-changing PR still requires explicit user approval",
            "schema file changes are placeholders and are not made by this PR",
            "human sign-offs are placeholders and are not recorded by this pack",
            "future live apply and seed apply require separate explicit opt-in",
            "ready_for_schema_change_pr=false in this PR",
            "ready_for_production_migration=false in this PR",
        ],
    }


def render_pr_body_template() -> str:
    lines = [
        "## Scope",
        "",
        "This future PR is intended to be a schema-changing PR only after explicit user approval.",
        "",
        "This preparation PR does not approve production migration or a schema-changing PR.",
        "",
        "## Explicit approval gate",
        "",
        "- Explicit user approval for schema file modification: NOT RECORDED IN THIS PR",
        "- Human schema reviewer sign-off: PLACEHOLDER ONLY",
        "- Migration operator sign-off: PLACEHOLDER ONLY",
        "- Rollback owner sign-off: PLACEHOLDER ONLY",
        "- Final maintainer sign-off: PLACEHOLDER ONLY",
        "",
        "## Intended schema files",
        "",
        "- db/schema.sql: PLACEHOLDER ONLY",
        "- db/postgres/001_init.sql: PLACEHOLDER ONLY",
        "",
        "## Proposed schema change summary",
        "",
        "Placeholder only; exact schema file changes remain outside this preparation PR.",
        "",
        "## Migration SQL source",
        "",
        "Placeholder only; no executable SQL artifact is emitted by this preparation PR.",
        "",
        "## Rollback / restore plan",
        "",
        "Placeholder only; no rollback or restore command is executed by this preparation PR.",
        "",
        "## Non-execution guarantees for this preparation PR",
        "",
        "This preparation PR does not modify db/schema.sql or db/postgres/001_init.sql.",
        "This preparation PR does not execute migration SQL.",
        "This preparation PR does not connect to PostgreSQL.",
        "This preparation PR does not read production DSN.",
        "This preparation PR does not forge human sign-offs.",
        "ready_for_schema_change_pr=false in this preparation PR.",
        "ready_for_production_migration=false in this preparation PR.",
        "",
        "## Tests",
        "",
        "List exact commands run by the future PR.",
        "",
        "## Remaining separate opt-in work",
        "",
        "- Future live apply PR remains separate.",
        "- Future seed apply PR remains separate.",
        "",
        "## Production verification terms",
        "",
        "Use neutral platform terms such as metric_records, metric_releases, and downstream_release_tables.",
        "",
        f"Boundary tokens for reviewers: {PRIMARY_ENV_DSN}, {LEGACY_ENV_DSN}.",
        "",
    ]
    return "\n".join(lines)


def lint_prep_pack_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_prep_json()
    text = report_as_json(report).lower()
    checks = {
        "schema_change_pr_prep_pack_only_true": report.get("schema_change_pr_prep_pack_only") is True,
        "schema_change_pr_approved_false": report.get("schema_change_pr_approved") is False,
        "production_migration_approved_false": report.get("production_migration_approved") is False,
        "production_migration_executed_false": report.get("production_migration_executed") is False,
        "production_seed_executed_false": report.get("production_seed_executed") is False,
        "schema_files_modified_false": report.get("schema_files_modified") is False,
        "migration_sql_executable_in_this_pr_false": report.get("migration_sql_executable_in_this_pr") is False,
        "sql_executed_false": report.get("sql_executed") is False,
        "production_db_connected_false": report.get("production_db_connected") is False,
        "production_dsn_read_false": report.get("production_dsn_read") is False,
        "human_signoffs_recorded_false": report.get("human_signoffs_recorded") is False,
        "ready_for_schema_change_pr_false": report.get("ready_for_schema_change_pr") is False,
        "ready_for_production_migration_false": report.get("ready_for_production_migration") is False,
        "future_schema_change_pr_required_true": report.get("future_schema_change_pr_required") is True,
        "future_live_apply_pr_required_true": report.get("future_live_apply_pr_required") is True,
        "future_seed_apply_pr_required_true": report.get("future_seed_apply_pr_required") is True,
        "db_touching_false": report.get("db_touching") is False,
        "connection_material_not_required": report.get("dsn_required") is False,
        "human_approval_required_before_schema_change_true": report.get("human_approval_required_before_schema_change") is True,
        "required_approval_placeholders_present": bool(report.get("required_approval_placeholders")),
        "schema_change_placeholders_present": bool(report.get("schema_change_placeholder_sections")),
        "rollback_restore_placeholders_present": bool(report.get("rollback_restore_placeholders")),
        "allowed_outputs_present": set(report.get("allowed_outputs", [])) == set(ALLOWED_OUTPUTS),
        "forbidden_actions_present": set(report.get("forbidden_actions", [])) == set(FORBIDDEN_ACTIONS),
        "no_connection_material_values": not contains_connection_material(text),
        "no_sql_client_instruction": SQL_CLIENT not in text,
        "no_shell_out_instruction": "shell out" not in text,
        "no_schema_change_approval_claim": report.get("schema_change_pr_approved") is not True,
        "no_human_signoff_forged": report.get("human_signoffs_recorded") is not True,
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    return {
        "mode": "lint-prep-pack-report",
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
    }


def build_prep_pack_report() -> dict[str, Any]:
    prep_json = render_prep_json()
    lint_report = lint_prep_pack_report(prep_json)
    failed = list(lint_report["failed"])
    return {
        "mode": "prep-pack-report",
        "prep_pack_version": PREP_PACK_VERSION,
        "prep_pack_status": PREP_PACK_STATUS,
        **{key: prep_json[key] for key in REQUIRED_FLAGS},
        "db_touching": prep_json["db_touching"],
        "dsn_required": prep_json["dsn_required"],
        "human_approval_required_before_schema_change": prep_json[
            "human_approval_required_before_schema_change"
        ],
        "prep_json_sha256": sha256_text(report_as_json(prep_json)),
        "pr_body_template_sha256": sha256_text(render_pr_body_template()),
        "prep_pack_lint_passed": bool(lint_report["passed"]),
        "prep_pack_lint_failed": failed,
        "prep_pack_gate_summary": {
            "passed": [rule["rule"] for rule in lint_report["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "required_approval_placeholders": list(REQUIRED_APPROVAL_PLACEHOLDERS),
        "schema_change_placeholder_sections": list(SCHEMA_CHANGE_PLACEHOLDER_SECTIONS),
        "rollback_restore_placeholders": list(ROLLBACK_RESTORE_PLACEHOLDERS),
        "blocking_failures": failed,
        "warnings": list(prep_json["warnings"]),
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
        {"rule": "status_is_preparation_pack_only", "passed": status_value(content) == PREP_PACK_STATUS},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_preparation_pack_only"
        ],
    ]
    blocked_phrases = [phrase for phrase in ADR_BLOCKED_PHRASES if phrase in normalized]
    checked_rules.append({"rule": "no_approval_or_execution_ready_claim", "passed": not blocked_phrases})
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

    parser = argparse.ArgumentParser(description="Build schema-change PR preparation pack reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--prep-pack-report", action="store_true")
    mode.add_argument("--render-prep-json", action="store_true")
    mode.add_argument("--render-pr-body-template", action="store_true")
    mode.add_argument("--lint-prep-pack-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.render_pr_body_template:
        sys.stdout.write(render_pr_body_template())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.prep_pack_report:
        report = build_prep_pack_report()
    elif args.render_prep_json:
        report = render_prep_json()
    elif args.lint_prep_pack_report:
        report = lint_prep_pack_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"prep-pack-report", "lint-prep-pack-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
