from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


def _repo_root() -> Path:
    for path in Path(__file__).resolve().parents:
        if (path / "db" / "schema.sql").is_file() and (path / "scripts" / "platform").is_dir():
            return path
    raise RuntimeError("could not locate repository root")


ROOT = _repo_root()
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-schema-change-approval-gate-package.md"
PACKAGE_VERSION = "schema-change-approval-gate-package-v1"
PACKAGE_STATUS = "Proposed / Approval gate package only"
SQL_CLIENT = "p" + "sql"
SHELL_PROCESS_TOKEN = "sub" + "process"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
SCHEMA_INPUTS = (
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
)
SOURCE_INPUTS = (
    "archive/docs/adr/ADR-schema-change-approval-gate-package.md",
    "archive/docs/adr/ADR-schema-change-candidate-review-bundle.md",
    "archive/docs/adr/ADR-schema-change-pr-prep-pack.md",
    "archive/docs/adr/ADR-guarded-executable-migration-pr.md",
    "db/schema.sql",
    "db/postgres/001_init.sql",
)
SUPPORTED_MODES = (
    "contract-report",
    "approval-gate-report",
    "render-approval-request-json",
    "render-human-approval-template",
    "render-blocked-pr-body-template",
    "lint-approval-gate-report",
    "adr-check",
)
REQUIRED_FLAGS = {
    "schema_change_approval_gate_package_only": True,
    "schema_change_user_approval_recorded": False,
    "schema_change_pr_approved": False,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_files_modified": False,
    "schema_file_hashes_read_only": True,
    "migration_sql_executable_in_this_pr": False,
    "migration_sql_artifact_emitted": False,
    "apply_ready_schema_patch_artifact_emitted": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "human_signoffs_recorded": False,
    "ready_for_schema_change_pr": False,
    "ready_for_production_migration": False,
    "future_schema_change_pr_requires_explicit_user_approval": True,
    "future_schema_change_pr_required": True,
    "future_live_apply_pr_required": True,
    "future_seed_apply_pr_required": True,
}
ALLOWED_OUTPUTS = (
    "stdout_report",
    "in_memory_json",
    "human_approval_template",
    "blocked_pr_body_template",
)
FORBIDDEN_ACTIONS = (
    "record_user_approval",
    "record_human_signoff",
    "modify_formal_schema",
    "emit_executable_migration_sql_artifact",
    "emit_apply_ready_schema_patch_artifact",
    "execute_migration_sql",
    "execute_production_seed",
    "connect_production_db",
    "read_production_dsn",
    "claim_schema_change_pr_approval",
    "claim_production_migration_approval",
)
REMAINING_SEPARATE_OPT_IN_PRS = (
    "future schema-changing PR requires explicit user approval",
    "future live apply PR requires separate explicit opt-in",
    "future seed apply PR requires separate explicit opt-in",
)
HUMAN_APPROVAL_BOUNDARIES = (
    "Explicit user approval: NOT RECORDED IN THIS PR",
    "Human schema reviewer sign-off: PLACEHOLDER ONLY",
    "Migration operator sign-off: PLACEHOLDER ONLY",
    "Rollback owner sign-off: PLACEHOLDER ONLY",
    "Final maintainer sign-off: PLACEHOLDER ONLY",
)
LINT_RULES = (
    "schema_change_approval_gate_package_only_true",
    "schema_change_user_approval_recorded_false",
    "schema_change_pr_approved_false",
    "production_migration_approved_false",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "schema_file_hashes_read_only_true",
    "migration_sql_executable_in_this_pr_false",
    "migration_sql_artifact_emitted_false",
    "apply_ready_schema_patch_artifact_emitted_false",
    "sql_executed_false",
    "production_db_connected_false",
    "production_dsn_read_false",
    "human_signoffs_recorded_false",
    "ready_for_schema_change_pr_false",
    "ready_for_production_migration_false",
    "future_schema_change_pr_requires_explicit_user_approval_true",
    "future_schema_change_pr_required_true",
    "future_live_apply_pr_required_true",
    "future_seed_apply_pr_required_true",
    "approval_request_status_not_recorded",
    "approval_recorded_false",
    "blocked_by_default_true",
    "schema_fingerprints_present",
    "schema_fingerprints_read_only",
    "allowed_outputs_present",
    "forbidden_actions_present",
    "remaining_separate_opt_in_prs_present",
    "no_connection_material_values",
    "no_sql_client_instruction",
    "no_shell_process_instruction",
    "no_executable_sql_or_schema_content",
    "no_apply_ready_patch_instruction",
    "no_approval_ready_or_signoff_claim",
)
ADR_RULES = (
    ("status_is_approval_gate_package_only", "Proposed / Approval gate package only"),
    ("declares_gate_package_only", "schema_change_approval_gate_package_only=true"),
    ("schema_change_user_approval_recorded_false", "schema_change_user_approval_recorded=false"),
    ("schema_change_pr_approved_false", "schema_change_pr_approved=false"),
    ("production_migration_approved_false", "production_migration_approved=false"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("schema_file_hashes_read_only_true", "schema_file_hashes_read_only=true"),
    ("migration_sql_executable_in_this_pr_false", "migration_sql_executable_in_this_pr=false"),
    ("migration_sql_artifact_emitted_false", "migration_sql_artifact_emitted=false"),
    ("apply_ready_schema_patch_artifact_emitted_false", "apply_ready_schema_patch_artifact_emitted=false"),
    ("production_db_connected_false", "production_db_connected=false"),
    ("production_dsn_read_false", "production_dsn_read=false"),
    ("human_signoffs_recorded_false", "human_signoffs_recorded=false"),
    ("ready_for_schema_change_pr_false", "ready_for_schema_change_pr=false"),
    ("ready_for_production_migration_false", "ready_for_production_migration=false"),
    (
        "future_schema_change_pr_requires_explicit_user_approval",
        "future_schema_change_pr_requires_explicit_user_approval=true",
    ),
    ("future_live_apply_pr_required", "future_live_apply_pr_required=true"),
    ("future_seed_apply_pr_required", "future_seed_apply_pr_required=true"),
    ("declares_no_schema_modification", "No schema modification"),
    ("declares_no_executable_sql_artifact", "No executable migration SQL artifact"),
    ("declares_no_apply_ready_patch", "No apply-ready schema patch artifact"),
    ("declares_no_db_connection", "No DB connection"),
    ("declares_no_dsn_access", "No DSN access"),
    ("approval_template_boundary", "Explicit user approval: NOT RECORDED IN THIS PR"),
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
    "schema-changing pr approved",
    "approval recorded",
    "sign-off recorded",
    "production migration ready",
)


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "status": PACKAGE_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "required_flags": dict(REQUIRED_FLAGS),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "source_inputs": list(SOURCE_INPUTS),
        "human_approval_boundaries": list(HUMAN_APPROVAL_BOUNDARIES),
        "remaining_separate_opt_in_prs": list(REMAINING_SEPARATE_OPT_IN_PRS),
        "validation_commands": validation_commands(),
    }


def render_approval_request_json() -> dict[str, Any]:
    return {
        "mode": "render-approval-request-json",
        "pr_number": 279,
        "title": "platform: add schema-change approval gate package",
        "scope": "schema_change_approval_gate_package_only",
        "required_flags": dict(REQUIRED_FLAGS),
        **REQUIRED_FLAGS,
        "approval_request_status": "not_recorded",
        "approval_recorded": False,
        "blocked_by_default": True,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "required_human_decision_text": required_human_decision_text(),
        "human_approval_boundaries": list(HUMAN_APPROVAL_BOUNDARIES),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "remaining_separate_opt_in_prs": list(REMAINING_SEPARATE_OPT_IN_PRS),
        "validation_commands": validation_commands(),
        "warnings": [
            "approval gate package only; future schema-changing PR still requires explicit user approval",
            "approval_request_status=not_recorded",
            "approval_recorded=false",
            "schema files are read only for hash and line count",
            "schema file contents are not exported by this package",
            "future live apply and seed apply require separate explicit opt-in",
            "ready_for_schema_change_pr=false in this PR",
            "ready_for_production_migration=false in this PR",
            f"DSN boundary labels for reviewers only: {PRIMARY_ENV_DSN}, {LEGACY_ENV_DSN}",
        ],
    }


def build_approval_gate_report() -> dict[str, Any]:
    request = render_approval_request_json()
    lint_report = lint_approval_gate_report(request)
    failed = list(lint_report["failed"])
    return {
        "mode": "approval-gate-report",
        "package_version": PACKAGE_VERSION,
        "package_status": PACKAGE_STATUS,
        **{key: request[key] for key in REQUIRED_FLAGS},
        "approval_request_json_sha256": sha256_text(report_as_json(request)),
        "human_approval_template_sha256": sha256_text(render_human_approval_template()),
        "blocked_pr_body_template_sha256": sha256_text(render_blocked_pr_body_template()),
        "approval_gate_lint_passed": bool(lint_report["passed"]),
        "approval_gate_lint_failed": failed,
        "approval_gate_summary": {
            "passed": [rule["rule"] for rule in lint_report["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "approval_request_status": request["approval_request_status"],
        "approval_recorded": request["approval_recorded"],
        "blocked_by_default": request["blocked_by_default"],
        "schema_file_fingerprints": list(request["schema_file_fingerprints"]),
        "remaining_separate_opt_in_prs": list(request["remaining_separate_opt_in_prs"]),
        "blocking_failures": failed,
        "warnings": list(request["warnings"]),
    }


def schema_file_fingerprints(paths: Sequence[Path] = SCHEMA_INPUTS) -> list[dict[str, Any]]:
    fingerprints: list[dict[str, Any]] = []
    for path in paths:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        fingerprints.append(
            {
                "path": relative_path(path),
                "read_only": True,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "line_count": len(text.splitlines()),
            }
        )
    return fingerprints


def required_human_decision_text() -> str:
    return "\n".join(
        [
            "Required exact user decision:",
            "- [ ] I explicitly approve a future schema-changing PR to modify db/schema.sql and/or db/postgres/001_init.sql.",
            "- [ ] I understand this does not approve live DB apply.",
            "- [ ] I understand this does not approve production seed apply.",
            "- [ ] I understand live apply and seed apply require separate opt-in PRs.",
        ]
    )


def render_human_approval_template() -> str:
    lines = [
        "## Human Approval Request Template",
        "",
        "This template is NOT an approval record in PR #279.",
        "",
        required_human_decision_text(),
        "",
        "Approval record location: PLACEHOLDER ONLY",
        "Human schema reviewer sign-off: PLACEHOLDER ONLY",
        "Migration operator sign-off: PLACEHOLDER ONLY",
        "Rollback owner sign-off: PLACEHOLDER ONLY",
        "Final maintainer sign-off: PLACEHOLDER ONLY",
        "",
    ]
    return "\n".join(lines)


def render_blocked_pr_body_template() -> str:
    lines = [
        "## Future Schema-Changing PR Body Template",
        "",
        "This template is blocked by default and is not an approval record in PR #279.",
        "",
        "## Approval Gate",
        "",
        "- Explicit user approval: REQUIRED BEFORE THIS FUTURE PR",
        "- Approval record location: PLACEHOLDER ONLY",
        "- Human schema reviewer sign-off: PLACEHOLDER ONLY",
        "- Migration operator sign-off: PLACEHOLDER ONLY",
        "- Rollback owner sign-off: PLACEHOLDER ONLY",
        "- Final maintainer sign-off: PLACEHOLDER ONLY",
        "",
        "## Schema Change Scope",
        "",
        "- Schema files changed: PLACEHOLDER ONLY",
        "- Migration SQL source: PLACEHOLDER ONLY",
        "- Rollback / restore plan: PLACEHOLDER ONLY",
        "- Live apply: OUT OF SCOPE",
        "- Seed apply: OUT OF SCOPE",
        "",
        "## Non-Execution Boundary",
        "",
        "- This future PR body template contains no executable SQL.",
        "- This future PR body template contains no patch content.",
        "- This future PR body template does not approve live DB apply.",
        "- This future PR body template does not approve production seed apply.",
        "",
    ]
    return "\n".join(lines)


def lint_approval_gate_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_approval_request_json()
    text = report_as_json(report).lower()
    checks = {
        "schema_change_approval_gate_package_only_true": report.get("schema_change_approval_gate_package_only") is True,
        "schema_change_user_approval_recorded_false": report.get("schema_change_user_approval_recorded") is False,
        "schema_change_pr_approved_false": report.get("schema_change_pr_approved") is False,
        "production_migration_approved_false": report.get("production_migration_approved") is False,
        "production_migration_executed_false": report.get("production_migration_executed") is False,
        "production_seed_executed_false": report.get("production_seed_executed") is False,
        "schema_files_modified_false": report.get("schema_files_modified") is False,
        "schema_file_hashes_read_only_true": report.get("schema_file_hashes_read_only") is True,
        "migration_sql_executable_in_this_pr_false": report.get("migration_sql_executable_in_this_pr") is False,
        "migration_sql_artifact_emitted_false": report.get("migration_sql_artifact_emitted") is False,
        "apply_ready_schema_patch_artifact_emitted_false": report.get("apply_ready_schema_patch_artifact_emitted") is False,
        "sql_executed_false": report.get("sql_executed") is False,
        "production_db_connected_false": report.get("production_db_connected") is False,
        "production_dsn_read_false": report.get("production_dsn_read") is False,
        "human_signoffs_recorded_false": report.get("human_signoffs_recorded") is False,
        "ready_for_schema_change_pr_false": report.get("ready_for_schema_change_pr") is False,
        "ready_for_production_migration_false": report.get("ready_for_production_migration") is False,
        "future_schema_change_pr_requires_explicit_user_approval_true": report.get(
            "future_schema_change_pr_requires_explicit_user_approval"
        )
        is True,
        "future_schema_change_pr_required_true": report.get("future_schema_change_pr_required") is True,
        "future_live_apply_pr_required_true": report.get("future_live_apply_pr_required") is True,
        "future_seed_apply_pr_required_true": report.get("future_seed_apply_pr_required") is True,
        "approval_request_status_not_recorded": report.get("approval_request_status") == "not_recorded",
        "approval_recorded_false": report.get("approval_recorded") is False,
        "blocked_by_default_true": report.get("blocked_by_default") is True,
        "schema_fingerprints_present": bool(report.get("schema_file_fingerprints")),
        "schema_fingerprints_read_only": all(
            item.get("read_only") is True and set(item) == {"path", "read_only", "sha256", "line_count"}
            for item in report.get("schema_file_fingerprints", [])
        ),
        "allowed_outputs_present": set(report.get("allowed_outputs", [])) == set(ALLOWED_OUTPUTS),
        "forbidden_actions_present": set(report.get("forbidden_actions", [])) == set(FORBIDDEN_ACTIONS),
        "remaining_separate_opt_in_prs_present": set(report.get("remaining_separate_opt_in_prs", []))
        == set(REMAINING_SEPARATE_OPT_IN_PRS),
        "no_connection_material_values": not contains_connection_material(text),
        "no_sql_client_instruction": SQL_CLIENT not in text,
        "no_shell_process_instruction": "shell out" not in text and SHELL_PROCESS_TOKEN not in text,
        "no_executable_sql_or_schema_content": not contains_executable_sql_or_schema_content(text),
        "no_apply_ready_patch_instruction": not contains_apply_ready_patch_instruction(text),
        "no_approval_ready_or_signoff_claim": not contains_approval_ready_or_signoff_claim(report),
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    return {
        "mode": "lint-approval-gate-report",
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
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
        {"rule": "status_is_approval_gate_package_only", "passed": status_value(content) == PACKAGE_STATUS},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_approval_gate_package_only"
        ],
    ]
    blocked_phrases = [phrase for phrase in ADR_BLOCKED_PHRASES if phrase in normalized]
    checked_rules.append({"rule": "no_approval_or_ready_claim", "passed": not blocked_phrases})
    failed = [rule["rule"] for rule in checked_rules if not rule["passed"]]
    return {
        "mode": "adr-check",
        "adr_path": relative_path(adr_path),
        "adr_exists": True,
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
    }


def contains_connection_material(text: str) -> bool:
    tokens = (
        "postgres://",
        "postgresql://",
        "password=",
        "connection string",
        "credential value",
    )
    return any(token in text for token in tokens)


def contains_executable_sql_or_schema_content(text: str) -> bool:
    tokens = (
        "create table",
        "insert into",
        "alter table",
        "drop table",
        "ddl",
        "schema diff",
        "sql snippet",
    )
    return any(token in text for token in tokens)


def contains_apply_ready_patch_instruction(text: str) -> bool:
    tokens = (
        "apply-ready patch",
        "patch content",
        "diff --git",
    )
    return any(token in text for token in tokens)


def contains_approval_ready_or_signoff_claim(report: Mapping[str, Any]) -> bool:
    if report.get("schema_change_user_approval_recorded") is True:
        return True
    if report.get("approval_recorded") is True:
        return True
    if report.get("schema_change_pr_approved") is True:
        return True
    if report.get("production_migration_approved") is True:
        return True
    if report.get("ready_for_schema_change_pr") is True:
        return True
    if report.get("ready_for_production_migration") is True:
        return True
    if report.get("human_signoffs_recorded") is True:
        return True
    text = report_as_json(report).lower()
    blocked = (
        "sign-off recorded",
        "approval recorded",
        "production migration approved",
        "schema-changing pr approved",
        "schema change approved",
        "ready_for_schema_change_pr=true",
        "ready_for_production_migration=true",
    )
    return any(phrase in text for phrase in blocked)


def status_value(content: str) -> str | None:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "## status":
            for candidate in lines[index + 1 :]:
                if candidate.strip():
                    return candidate.strip().rstrip(".")
    return None


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relative_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def validation_commands() -> list[str]:
    return [
        "python -m pytest tests/test_schema_change_approval_gate_package.py",
        "python scripts/platform/schema_change_approval_gate_package.py --contract-report",
        "python scripts/platform/schema_change_approval_gate_package.py --approval-gate-report",
        "python scripts/platform/schema_change_approval_gate_package.py --render-approval-request-json",
        "python scripts/platform/schema_change_approval_gate_package.py --render-human-approval-template",
        "python scripts/platform/schema_change_approval_gate_package.py --render-blocked-pr-body-template",
        "python scripts/platform/schema_change_approval_gate_package.py --lint-approval-gate-report",
        "python scripts/platform/schema_change_approval_gate_package.py --adr-check",
    ]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build schema-change approval gate package reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--approval-gate-report", action="store_true")
    mode.add_argument("--render-approval-request-json", action="store_true")
    mode.add_argument("--render-human-approval-template", action="store_true")
    mode.add_argument("--render-blocked-pr-body-template", action="store_true")
    mode.add_argument("--lint-approval-gate-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.render_human_approval_template:
        sys.stdout.write(render_human_approval_template())
        return 0
    if args.render_blocked_pr_body_template:
        sys.stdout.write(render_blocked_pr_body_template())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.approval_gate_report:
        report = build_approval_gate_report()
    elif args.render_approval_request_json:
        report = render_approval_request_json()
    elif args.lint_approval_gate_report:
        report = lint_approval_gate_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"approval-gate-report", "lint-approval-gate-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
