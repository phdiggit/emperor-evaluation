from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
ADR_PATH = ROOT / "docs" / "adr" / "ADR-schema-change-candidate-review-bundle.md"
BUNDLE_VERSION = "schema-change-candidate-review-bundle-v1"
BUNDLE_STATUS = "Proposed / Candidate review bundle only"
SQL_CLIENT = "p" + "sql"
SHELL_PROCESS_TOKEN = "sub" + "process"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
SCHEMA_INPUTS = (
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
)
SOURCE_INPUTS = (
    "docs/adr/ADR-schema-change-candidate-review-bundle.md",
    "db/schema.sql",
    "db/postgres/001_init.sql",
)
OPTIONAL_CONTEXT_INPUTS = (
    "docs/adr/ADR-schema-change-pr-prep-pack.md",
    "docs/adr/ADR-guarded-executable-migration-pr.md",
    "docs/adr/ADR-production-migration-pr-scaffold.md",
)
SUPPORTED_MODES = (
    "contract-report",
    "candidate-bundle-report",
    "render-candidate-json",
    "render-pr-body-template",
    "lint-candidate-bundle-report",
    "adr-check",
)
REQUIRED_FLAGS = {
    "schema_change_candidate_review_bundle_only": True,
    "schema_change_pr_approved": False,
    "production_migration_approved": False,
    "production_migration_executed": False,
    "production_seed_executed": False,
    "schema_files_modified": False,
    "schema_file_hashes_read_only": True,
    "migration_sql_executable_in_this_pr": False,
    "migration_sql_artifact_emitted": False,
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
    "candidate_checklist",
)
FORBIDDEN_ACTIONS = (
    "modify_formal_schema",
    "emit_executable_migration_sql_artifact",
    "emit_apply_ready_schema_patch_artifact",
    "execute_migration_sql",
    "execute_production_seed",
    "connect_production_db",
    "read_production_dsn",
    "forge_human_signoff",
    "claim_schema_change_pr_approval",
)
CANDIDATE_REVIEW_SECTIONS = (
    "candidate schema files",
    "current schema file fingerprints",
    "candidate review checklist",
    "explicit approval placeholders",
    "rollback restore review placeholders",
    "remaining separate opt-in work",
)
SOURCE_INPUT_CHECKLIST = (
    "read ADR for candidate review bundle contract",
    "read db/schema.sql for hash and line count only",
    "read db/postgres/001_init.sql for hash and line count only",
    "do not read data or exports as migration inputs",
)
FUTURE_REQUIRED_PRS = (
    "future schema-changing PR requires explicit user approval",
    "future live apply PR requires separate explicit opt-in",
    "future seed apply PR requires separate explicit opt-in",
)
LINT_RULES = (
    "schema_change_candidate_review_bundle_only_true",
    "schema_change_pr_approved_false",
    "production_migration_approved_false",
    "production_migration_executed_false",
    "production_seed_executed_false",
    "schema_files_modified_false",
    "schema_file_hashes_read_only_true",
    "migration_sql_executable_in_this_pr_false",
    "migration_sql_artifact_emitted_false",
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
    "schema_fingerprints_present",
    "schema_fingerprints_read_only",
    "candidate_review_sections_present",
    "blocked_by_default_template_true",
    "allowed_outputs_present",
    "forbidden_actions_present",
    "no_connection_material_values",
    "no_sql_client_instruction",
    "no_shell_out_instruction",
    "no_approval_ready_or_signoff_claim",
)
ADR_RULES = (
    ("status_is_candidate_review_bundle_only", "Proposed / Candidate review bundle only"),
    ("declares_bundle_only", "schema_change_candidate_review_bundle_only=true"),
    ("schema_change_pr_approved_false", "schema_change_pr_approved=false"),
    ("production_migration_approved_false", "production_migration_approved=false"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("schema_file_hashes_read_only_true", "schema_file_hashes_read_only=true"),
    ("migration_sql_executable_in_this_pr_false", "migration_sql_executable_in_this_pr=false"),
    ("migration_sql_artifact_emitted_false", "migration_sql_artifact_emitted=false"),
    ("production_db_connected_false", "production_db_connected=false"),
    ("production_dsn_read_false", "production_dsn_read=false"),
    ("ready_for_schema_change_pr_false", "ready_for_schema_change_pr=false"),
    ("ready_for_production_migration_false", "ready_for_production_migration=false"),
    ("future_schema_change_pr_required", "future_schema_change_pr_required=true"),
    ("future_live_apply_pr_required", "future_live_apply_pr_required=true"),
    ("future_seed_apply_pr_required", "future_seed_apply_pr_required=true"),
    ("declares_no_schema_modification", "No schema modification"),
    ("declares_no_executable_sql_artifact", "No executable migration SQL artifact"),
    ("declares_no_db_connection", "No DB connection"),
    ("declares_no_dsn_access", "No DSN access"),
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
    "sign-off recorded",
    "production migration ready",
)


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "bundle_version": BUNDLE_VERSION,
        "status": BUNDLE_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "required_flags": dict(REQUIRED_FLAGS),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "source_inputs": list(SOURCE_INPUTS),
        "optional_context_inputs": list(OPTIONAL_CONTEXT_INPUTS),
        "source_input_checklist": list(SOURCE_INPUT_CHECKLIST),
        "candidate_review_sections": list(CANDIDATE_REVIEW_SECTIONS),
        "future_required_prs": list(FUTURE_REQUIRED_PRS),
        "validation_commands": validation_commands(),
    }


def render_candidate_json() -> dict[str, Any]:
    return {
        "mode": "render-candidate-json",
        "pr_number": 278,
        "title": "platform: add schema-change candidate review bundle",
        "scope": "schema_change_candidate_review_bundle_only",
        **REQUIRED_FLAGS,
        "db_touching": False,
        "dsn_required": False,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "candidate_review_sections": list(CANDIDATE_REVIEW_SECTIONS),
        "source_input_checklist": list(SOURCE_INPUT_CHECKLIST),
        "blocked_by_default_pr_body_template": True,
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "future_required_prs": list(FUTURE_REQUIRED_PRS),
        "validation_commands": validation_commands(),
        "warnings": [
            "candidate review bundle only; future schema-changing PR still requires explicit user approval",
            "schema files are read only for hash and line count",
            "schema file contents are not exported by this bundle",
            "future live apply and seed apply require separate explicit opt-in",
            "ready_for_schema_change_pr=false in this PR",
            "ready_for_production_migration=false in this PR",
        ],
    }


def build_candidate_bundle_report() -> dict[str, Any]:
    candidate_json = render_candidate_json()
    lint_report = lint_candidate_bundle_report(candidate_json)
    failed = list(lint_report["failed"])
    return {
        "mode": "candidate-bundle-report",
        "bundle_version": BUNDLE_VERSION,
        "bundle_status": BUNDLE_STATUS,
        **{key: candidate_json[key] for key in REQUIRED_FLAGS},
        "db_touching": candidate_json["db_touching"],
        "dsn_required": candidate_json["dsn_required"],
        "candidate_json_sha256": sha256_text(report_as_json(candidate_json)),
        "pr_body_template_sha256": sha256_text(render_pr_body_template()),
        "candidate_bundle_lint_passed": bool(lint_report["passed"]),
        "candidate_bundle_lint_failed": failed,
        "candidate_bundle_gate_summary": {
            "passed": [rule["rule"] for rule in lint_report["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "schema_file_fingerprints": list(candidate_json["schema_file_fingerprints"]),
        "candidate_review_sections": list(candidate_json["candidate_review_sections"]),
        "blocking_failures": failed,
        "warnings": list(candidate_json["warnings"]),
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


def render_pr_body_template() -> str:
    lines = [
        "## Scope",
        "",
        "This future PR is intended to be a schema-changing PR only after explicit user approval.",
        "",
        "## Explicit approval gate",
        "",
        "- Explicit user approval for schema file modification: NOT RECORDED IN THIS PR",
        "- Human schema reviewer sign-off: PLACEHOLDER ONLY",
        "- Migration operator sign-off: PLACEHOLDER ONLY",
        "- Rollback owner sign-off: PLACEHOLDER ONLY",
        "- Final maintainer sign-off: PLACEHOLDER ONLY",
        "",
        "## Candidate schema files",
        "",
        "- db/schema.sql: CURRENT HASH ONLY / FUTURE DIFF NOT INCLUDED IN THIS PR",
        "- db/postgres/001_init.sql: CURRENT HASH ONLY / FUTURE DIFF NOT INCLUDED IN THIS PR",
        "",
        "## Candidate review checklist",
        "",
        "- Exact schema diff must be reviewed in a later PR.",
        "- Executable migration SQL must not be emitted by this PR.",
        "- Live apply must be separate opt-in.",
        "- Seed apply must be separate opt-in.",
        "",
        "## Non-execution guarantees for this candidate review bundle",
        "",
        "- This PR does not modify schema files.",
        "- This PR does not execute SQL.",
        "- This PR does not connect to PostgreSQL.",
        "- This PR does not read production DSN.",
        "- ready_for_schema_change_pr=false.",
        "- ready_for_production_migration=false.",
        "",
        "## Remaining separate opt-in work",
        "",
        "- Future schema-changing PR requires explicit user approval.",
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


def lint_candidate_bundle_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_candidate_json()
    text = report_as_json(report).lower()
    checks = {
        "schema_change_candidate_review_bundle_only_true": report.get("schema_change_candidate_review_bundle_only") is True,
        "schema_change_pr_approved_false": report.get("schema_change_pr_approved") is False,
        "production_migration_approved_false": report.get("production_migration_approved") is False,
        "production_migration_executed_false": report.get("production_migration_executed") is False,
        "production_seed_executed_false": report.get("production_seed_executed") is False,
        "schema_files_modified_false": report.get("schema_files_modified") is False,
        "schema_file_hashes_read_only_true": report.get("schema_file_hashes_read_only") is True,
        "migration_sql_executable_in_this_pr_false": report.get("migration_sql_executable_in_this_pr") is False,
        "migration_sql_artifact_emitted_false": report.get("migration_sql_artifact_emitted") is False,
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
        "schema_fingerprints_present": bool(report.get("schema_file_fingerprints")),
        "schema_fingerprints_read_only": all(
            item.get("read_only") is True and set(item) == {"path", "read_only", "sha256", "line_count"}
            for item in report.get("schema_file_fingerprints", [])
        ),
        "candidate_review_sections_present": bool(report.get("candidate_review_sections")),
        "blocked_by_default_template_true": report.get("blocked_by_default_pr_body_template") is True,
        "allowed_outputs_present": set(report.get("allowed_outputs", [])) == set(ALLOWED_OUTPUTS),
        "forbidden_actions_present": set(report.get("forbidden_actions", [])) == set(FORBIDDEN_ACTIONS),
        "no_connection_material_values": not contains_connection_material(text),
        "no_sql_client_instruction": SQL_CLIENT not in text,
        "no_shell_out_instruction": "shell out" not in text and SHELL_PROCESS_TOKEN not in text,
        "no_approval_ready_or_signoff_claim": not contains_approval_ready_or_signoff_claim(report),
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    return {
        "mode": "lint-candidate-bundle-report",
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
        {"rule": "status_is_candidate_review_bundle_only", "passed": status_value(content) == BUNDLE_STATUS},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_candidate_review_bundle_only"
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


def contains_approval_ready_or_signoff_claim(report: Mapping[str, Any]) -> bool:
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
        "python -m pytest tests/test_schema_change_candidate_review_bundle.py",
        "python scripts/platform/schema_change_candidate_review_bundle.py --contract-report",
        "python scripts/platform/schema_change_candidate_review_bundle.py --candidate-bundle-report",
        "python scripts/platform/schema_change_candidate_review_bundle.py --render-candidate-json",
        "python scripts/platform/schema_change_candidate_review_bundle.py --render-pr-body-template",
        "python scripts/platform/schema_change_candidate_review_bundle.py --lint-candidate-bundle-report",
        "python scripts/platform/schema_change_candidate_review_bundle.py --adr-check",
    ]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build schema-change candidate review bundle reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--candidate-bundle-report", action="store_true")
    mode.add_argument("--render-candidate-json", action="store_true")
    mode.add_argument("--render-pr-body-template", action="store_true")
    mode.add_argument("--lint-candidate-bundle-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.render_pr_body_template:
        sys.stdout.write(render_pr_body_template())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.candidate_bundle_report:
        report = build_candidate_bundle_report()
    elif args.render_candidate_json:
        report = render_candidate_json()
    elif args.lint_candidate_bundle_report:
        report = lint_candidate_bundle_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"candidate-bundle-report", "lint-candidate-bundle-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
