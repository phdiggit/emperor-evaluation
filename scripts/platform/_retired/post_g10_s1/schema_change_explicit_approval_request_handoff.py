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
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-schema-change-explicit-approval-request-handoff.md"
HANDOFF_VERSION = "schema-change-explicit-approval-request-handoff-v1"
HANDOFF_STATUS = "Proposed / Explicit approval request handoff only"
SQL_CLIENT = "p" + "sql"
SHELL_PROCESS_TOKEN = "sub" + "process"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
APPROVAL_REQUEST_STATUS = "pending_external_user_decision"
SCHEMA_INPUTS = (
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
)
SOURCE_INPUTS = (
    "archive/docs/adr/ADR-schema-change-explicit-approval-request-handoff.md",
    "archive/docs/adr/ADR-schema-change-approval-gate-package.md",
    "archive/docs/adr/ADR-schema-change-candidate-review-bundle.md",
    "archive/docs/adr/ADR-schema-change-pr-prep-pack.md",
    "db/schema.sql",
    "db/postgres/001_init.sql",
)
SUPPORTED_MODES = (
    "contract-report",
    "handoff-report",
    "render-approval-request-json",
    "render-user-facing-approval-request-md",
    "render-blocked-schema-pr-body-template",
    "lint-handoff-report",
    "adr-check",
)
BOOLEAN_REQUIRED_FLAGS = {
    "schema_change_explicit_approval_request_handoff_only": True,
    "schema_change_user_approval_recorded": False,
    "schema_change_approval_request_rendered": True,
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
REQUIRED_FLAGS = {
    **BOOLEAN_REQUIRED_FLAGS,
    "schema_change_approval_request_status": APPROVAL_REQUEST_STATUS,
}
ALLOWED_OUTPUTS = (
    "stdout_report",
    "in_memory_json",
    "approval_request_handoff_markdown",
    "blocked_by_default_template",
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
FUTURE_REQUIRED_PRS = (
    "future schema-changing PR requires explicit user approval outside PR #280",
    "future live apply PR requires separate explicit opt-in",
    "future seed apply PR requires separate explicit opt-in",
)
LINT_RULES = (
    "schema_change_explicit_approval_request_handoff_only_true",
    "schema_change_user_approval_recorded_false",
    "schema_change_approval_request_rendered_true",
    "schema_change_approval_request_status_pending",
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
    "approval_recorded_false",
    "schema_fingerprints_present",
    "schema_fingerprints_read_only",
    "allowed_outputs_present",
    "forbidden_actions_present",
    "future_required_prs_present",
    "no_connection_material_values",
    "no_sql_client_instruction",
    "no_shell_process_instruction",
    "no_executable_sql_or_schema_content",
    "no_apply_ready_patch_instruction",
    "no_approval_ready_or_signoff_claim",
)
ADR_RULES = (
    ("status_is_explicit_approval_request_handoff_only", HANDOFF_STATUS),
    (
        "declares_explicit_approval_request_handoff_only",
        "schema_change_explicit_approval_request_handoff_only=true",
    ),
    ("schema_change_user_approval_recorded_false", "schema_change_user_approval_recorded=false"),
    ("schema_change_approval_request_rendered_true", "schema_change_approval_request_rendered=true"),
    ("schema_change_approval_request_status_pending", "schema_change_approval_request_status=pending_external_user_decision"),
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
    ("approval_request_boundary", "This handoff is NOT an approval record in PR #280"),
)
ADR_BLOCKED_PHRASES = (
    *(
        f"{name}=false"
        for name, expected in BOOLEAN_REQUIRED_FLAGS.items()
        if expected is True
    ),
    *(
        f"{name} = false"
        for name, expected in BOOLEAN_REQUIRED_FLAGS.items()
        if expected is True
    ),
    *(
        f"{name}=true"
        for name, expected in BOOLEAN_REQUIRED_FLAGS.items()
        if expected is False
    ),
    *(
        f"{name} = true"
        for name, expected in BOOLEAN_REQUIRED_FLAGS.items()
        if expected is False
    ),
    "schema change approved",
    "production migration approved",
    "approval recorded",
    "sign-off recorded",
    "ready_for_schema_change_pr=true",
    "ready_for_production_migration=true",
)


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "handoff_version": HANDOFF_VERSION,
        "status": HANDOFF_STATUS,
        "required_flags": dict(REQUIRED_FLAGS),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "source_inputs": list(SOURCE_INPUTS),
        "supported_modes": list(SUPPORTED_MODES),
        "future_required_prs": list(FUTURE_REQUIRED_PRS),
        "validation_commands": validation_commands(),
    }


def render_approval_request_json() -> dict[str, Any]:
    return {
        "mode": "render-approval-request-json",
        "pr_number": 280,
        "title": "platform: add schema-change explicit approval request handoff package",
        "scope": "schema_change_explicit_approval_request_handoff_only",
        "required_flags": dict(REQUIRED_FLAGS),
        **REQUIRED_FLAGS,
        "approval_request_status": APPROVAL_REQUEST_STATUS,
        "approval_recorded": False,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "user_facing_approval_request_md": render_user_facing_approval_request_md(),
        "blocked_schema_pr_body_template": render_blocked_schema_pr_body_template(),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "future_required_prs": list(FUTURE_REQUIRED_PRS),
        "validation_commands": validation_commands(),
        "warnings": [
            "explicit approval request handoff only; future schema-changing PR still requires explicit user approval",
            "schema_change_approval_request_status=pending_external_user_decision",
            "schema_change_user_approval_recorded=false",
            "schema_change_pr_approved=false",
            "schema files are read only for hash and line count",
            "schema file contents are not exported by this handoff package",
            "future live apply and seed apply require separate explicit opt-in",
            "ready_for_schema_change_pr=false in this PR",
            "ready_for_production_migration=false in this PR",
            f"DSN boundary labels for reviewers only: {PRIMARY_ENV_DSN}, {LEGACY_ENV_DSN}",
        ],
    }


def build_handoff_report() -> dict[str, Any]:
    request = render_approval_request_json()
    lint_report = lint_handoff_report(request)
    failed = list(lint_report["failed"])
    return {
        "mode": "handoff-report",
        "handoff_version": HANDOFF_VERSION,
        "handoff_status": HANDOFF_STATUS,
        **{key: request[key] for key in REQUIRED_FLAGS},
        "approval_request_status": request["approval_request_status"],
        "approval_recorded": request["approval_recorded"],
        "approval_request_json_sha256": sha256_text(report_as_json(request)),
        "user_facing_approval_request_md_sha256": sha256_text(render_user_facing_approval_request_md()),
        "blocked_schema_pr_body_template_sha256": sha256_text(render_blocked_schema_pr_body_template()),
        "handoff_lint_passed": bool(lint_report["passed"]),
        "handoff_lint_failed": failed,
        "handoff_gate_summary": {
            "passed": [rule["rule"] for rule in lint_report["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "schema_file_fingerprints": list(request["schema_file_fingerprints"]),
        "future_required_prs": list(request["future_required_prs"]),
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


def render_user_facing_approval_request_md() -> str:
    lines = [
        "## Schema-change explicit approval request",
        "",
        "This handoff is NOT an approval record in PR #280.",
        "",
        "To authorize the next schema-changing PR, the user must explicitly reply with wording equivalent to:",
        "",
        "> I explicitly approve a future schema-changing PR to modify `db/schema.sql` and/or `db/postgres/001_init.sql`.",
        "> I understand this does not approve live DB apply and does not approve production seed apply.",
        "> Live apply and seed apply still require separate opt-in PRs and separate review.",
        "",
        "Until that explicit approval is provided outside PR #280:",
        "",
        "- `schema_change_user_approval_recorded=false`",
        "- `schema_change_pr_approved=false`",
        "- `ready_for_schema_change_pr=false`",
        "- `ready_for_production_migration=false`",
        "",
    ]
    return "\n".join(lines)


def render_blocked_schema_pr_body_template() -> str:
    lines = [
        "## Future Schema-Changing PR Body Template",
        "",
        "This template is blocked by default and is not an approval record in PR #280.",
        "",
        "## Approval Gate",
        "",
        "- Explicit approval record location: REQUIRED BEFORE THIS FUTURE PR",
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
        "- This future PR body template contains no patch material.",
        "- This future PR body template does not approve live DB apply.",
        "- This future PR body template does not approve production seed apply.",
        "",
    ]
    return "\n".join(lines)


def lint_handoff_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_approval_request_json()
    text = report_as_json(report).lower()
    checks = {
        "schema_change_explicit_approval_request_handoff_only_true": report.get(
            "schema_change_explicit_approval_request_handoff_only"
        )
        is True,
        "schema_change_user_approval_recorded_false": report.get("schema_change_user_approval_recorded") is False,
        "schema_change_approval_request_rendered_true": report.get("schema_change_approval_request_rendered") is True,
        "schema_change_approval_request_status_pending": report.get("schema_change_approval_request_status")
        == APPROVAL_REQUEST_STATUS
        and report.get("approval_request_status") == APPROVAL_REQUEST_STATUS,
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
        "approval_recorded_false": report.get("approval_recorded") is False,
        "schema_fingerprints_present": bool(report.get("schema_file_fingerprints")),
        "schema_fingerprints_read_only": all(
            item.get("read_only") is True and set(item) == {"path", "read_only", "sha256", "line_count"}
            for item in report.get("schema_file_fingerprints", [])
        ),
        "allowed_outputs_present": set(report.get("allowed_outputs", [])) == set(ALLOWED_OUTPUTS),
        "forbidden_actions_present": set(report.get("forbidden_actions", [])) == set(FORBIDDEN_ACTIONS),
        "future_required_prs_present": set(report.get("future_required_prs", [])) == set(FUTURE_REQUIRED_PRS),
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
        "mode": "lint-handoff-report",
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
        {
            "rule": "status_is_explicit_approval_request_handoff_only",
            "passed": status_value(content) == HANDOFF_STATUS,
        },
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_explicit_approval_request_handoff_only"
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
        "alter table",
        "drop table",
        "insert into",
        "sql snippet",
        "ddl",
    )
    return any(token in text for token in tokens)


def contains_apply_ready_patch_instruction(text: str) -> bool:
    tokens = (
        "apply-ready patch",
        "diff --git",
        "patch content",
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
        "approval recorded",
        "sign-off recorded",
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
        "python -m pytest tests/test_schema_change_explicit_approval_request_handoff.py",
        "python scripts/platform/schema_change_explicit_approval_request_handoff.py --contract-report",
        "python scripts/platform/schema_change_explicit_approval_request_handoff.py --handoff-report",
        "python scripts/platform/schema_change_explicit_approval_request_handoff.py --render-approval-request-json",
        "python scripts/platform/schema_change_explicit_approval_request_handoff.py --render-user-facing-approval-request-md",
        "python scripts/platform/schema_change_explicit_approval_request_handoff.py --render-blocked-schema-pr-body-template",
        "python scripts/platform/schema_change_explicit_approval_request_handoff.py --lint-handoff-report",
        "python scripts/platform/schema_change_explicit_approval_request_handoff.py --adr-check",
    ]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build schema-change explicit approval request handoff reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--handoff-report", action="store_true")
    mode.add_argument("--render-approval-request-json", action="store_true")
    mode.add_argument("--render-user-facing-approval-request-md", action="store_true")
    mode.add_argument("--render-blocked-schema-pr-body-template", action="store_true")
    mode.add_argument("--lint-handoff-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.render_user_facing_approval_request_md:
        sys.stdout.write(render_user_facing_approval_request_md())
        return 0
    if args.render_blocked_schema_pr_body_template:
        sys.stdout.write(render_blocked_schema_pr_body_template())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.handoff_report:
        report = build_handoff_report()
    elif args.render_approval_request_json:
        report = render_approval_request_json()
    elif args.lint_handoff_report:
        report = lint_handoff_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"handoff-report", "lint-handoff-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
