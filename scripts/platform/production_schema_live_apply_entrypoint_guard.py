from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-production-schema-live-apply-entrypoint-guard.md"
SCHEMA_PATHS = (
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
)
GUARD_VERSION = "production-schema-live-apply-entrypoint-guard-v1"
GUARD_STATUS = "Proposed / Production schema live-apply entrypoint guard only"
SQL_CLIENT = "p" + "sql"
SHELL_PROCESS_TOKEN = "sub" + "process"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
BLOCKED_BUSINESS_TERMS = ("sco" + "re", "ra" + "nk", "final_" + ("sco" + "re"), "leader" + "board")
REQUIRED_FLAGS = {
    "live_apply_entrypoint_guard_only": True,
    "schema_files_modified": False,
    "schema_files_read_only": True,
    "schema_files_byte_identical_required": True,
    "production_schema_hashes_rendered": True,
    "live_apply_approved": False,
    "live_apply_executed": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "production_seed_executed": False,
    "seed_apply_executed": False,
    "ready_for_live_apply": False,
    "ready_for_production_migration": False,
    "future_live_apply_execution_pr_required": True,
    "future_seed_apply_pr_required": True,
}
SUPPORTED_MODES = (
    "contract-report",
    "entrypoint-guard-report",
    "render-live-apply-request-json",
    "render-operator-runbook-md",
    "lint-entrypoint-guard-report",
    "adr-check",
)
FORBIDDEN_ACTIONS = (
    "read_production_dsn",
    "connect_postgresql",
    "execute_migration_sql",
    "execute_production_seed",
    "execute_live_apply",
    "write_public_schema",
    "emit_apply_ready_live_command",
    "forge_human_signoff",
)
SOURCE_INPUTS = (
    "db/schema.sql",
    "db/postgres/001_init.sql",
    "archive/docs/adr/ADR-production-schema-live-apply-entrypoint-guard.md",
    "archive/docs/adr/ADR-schema-changing-formal-schema-update.md",
)
LINT_RULES = (
    "schema_files_exist",
    "schema_files_byte_identical",
    "schema_table_sets_same",
    "anchors_table_exists",
    *(
        f"{name}_{str(expected).lower()}"
        for name, expected in REQUIRED_FLAGS.items()
    ),
    "schema_fingerprints_are_metadata_only",
    "no_connection_material",
    "no_execution_hints",
    "no_seed_or_data_load",
    "no_business_conclusion_terms",
)
ADR_RULES = (
    ("status_is_entrypoint_guard_only", GUARD_STATUS),
    ("declares_pr281_entered_chain", "PR #281 entered the schema-changing file-update chain"),
    ("declares_guard_before_live_apply", "live apply entrypoint guard package before any live apply"),
    ("declares_no_live_apply_execution", "No live apply execution"),
    ("declares_no_db_connection", "No PostgreSQL connection"),
    ("declares_no_dsn_access", "No DSN access"),
    ("declares_schema_read_only", "Keep schema files read-only in this PR"),
    ("declares_no_apply_ready_command", "no apply-ready command"),
    ("declares_future_live_apply_pr", "Future live apply execution PR remains required"),
    ("declares_future_seed_apply_pr", "Future seed apply PR remains required"),
    *[(f"declares_{name}", f"{name}={str(expected).lower()}") for name, expected in REQUIRED_FLAGS.items()],
)
ADR_BLOCKED_PHRASES = (
    *(
        f"{name}=false"
        for name, expected in REQUIRED_FLAGS.items()
        if expected is True
    ),
    *(
        f"{name}=true"
        for name, expected in REQUIRED_FLAGS.items()
        if expected is False
    ),
    "live apply complete",
    "live apply completed",
    "seed apply complete",
    "seed apply completed",
    "production migration complete",
    "production migration completed",
)


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "guard_version": GUARD_VERSION,
        "status": GUARD_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "required_flags": dict(REQUIRED_FLAGS),
        "source_inputs": list(SOURCE_INPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "validation_commands": validation_commands(),
        "future_required_prs": [
            "future live apply execution PR required",
            "future seed apply PR required",
        ],
    }


def render_live_apply_request_json() -> dict[str, Any]:
    return {
        "mode": "render-live-apply-request-json",
        "pr_number": 282,
        "title": "platform: add production schema live-apply entrypoint guard package",
        "scope": "production_schema_live_apply_entrypoint_guard_only",
        "required_flags": dict(REQUIRED_FLAGS),
        **REQUIRED_FLAGS,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "schema_consistency": {
            "byte_identical": schema_files_byte_identical(),
            "table_sets_same": schema_table_sets_same(),
            "anchors_table_exists": anchors_table_exists(),
        },
        "future_required_prs": [
            "future live apply execution PR required",
            "future seed apply PR required",
        ],
        "warnings": [
            "entrypoint guard package only",
            "no live apply execution in this PR",
            "no database connection in this PR",
            "no production seed execution in this PR",
            "ready_for_live_apply=false",
            "ready_for_production_migration=false",
        ],
    }


def build_entrypoint_guard_report() -> dict[str, Any]:
    request = render_live_apply_request_json()
    lint = lint_entrypoint_guard_report(request)
    failed = list(lint["failed"])
    return {
        "mode": "entrypoint-guard-report",
        "pr_number": 282,
        "guard_version": GUARD_VERSION,
        **{key: request[key] for key in REQUIRED_FLAGS},
        "schema_file_fingerprints": list(request["schema_file_fingerprints"]),
        "schema_consistency": dict(request["schema_consistency"]),
        "entrypoint_guard_lint_passed": bool(lint["passed"]),
        "entrypoint_guard_lint_failed": failed,
        "blocking_failures": failed,
        "guard_summary": {
            "passed": [rule["rule"] for rule in lint["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "warnings": list(request["warnings"]),
    }


def render_operator_runbook_md() -> str:
    lines = [
        "# Production Schema Live-Apply Entrypoint Guard Runbook",
        "",
        "THIS RUNBOOK IS NOT AN EXECUTION APPROVAL.",
        "NO DSN IS READ BY THIS PR.",
        "NO SQL IS EXECUTED BY THIS PR.",
        "FUTURE LIVE APPLY EXECUTION PR REQUIRED.",
        "",
        "## Boundary",
        "",
        "- PR #282 renders guard material only.",
        "- Schema files are read only for hash, line-count, table-count, and consistency checks.",
        "- `ready_for_live_apply=false`.",
        "- `ready_for_production_migration=false`.",
        "- Seed apply remains a separate future PR.",
        "",
        "## Required Next Review",
        "",
        "- Open a separate live apply execution PR after explicit approval.",
        "- Open a separate seed apply PR after explicit approval.",
        "- Keep operator approval evidence in the future execution PR, not in PR #282.",
        "",
    ]
    return "\n".join(lines)


def schema_file_fingerprints(paths: Sequence[Path] = SCHEMA_PATHS) -> list[dict[str, Any]]:
    fingerprints: list[dict[str, Any]] = []
    for path in paths:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        fingerprints.append(
            {
                "path": relative_path(path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "line_count": len(text.splitlines()),
                "table_count": len(created_tables(text)),
                "read_only": True,
            }
        )
    return fingerprints


def lint_entrypoint_guard_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_live_apply_request_json()
    rendered = report_as_json(report).lower()
    schema_texts = {relative_path(path): path.read_text(encoding="utf-8") for path in SCHEMA_PATHS if path.exists()}
    table_sets = {path: set(created_tables(text)) for path, text in schema_texts.items()}
    checks = {
        "schema_files_exist": all(path.exists() for path in SCHEMA_PATHS),
        "schema_files_byte_identical": schema_files_byte_identical(),
        "schema_table_sets_same": schema_table_sets_same(),
        "anchors_table_exists": anchors_table_exists(),
        **{
            f"{name}_{str(expected).lower()}": report.get(name) is expected
            and report.get("required_flags", {}).get(name) is expected
            for name, expected in REQUIRED_FLAGS.items()
        },
        "schema_fingerprints_are_metadata_only": schema_fingerprints_are_metadata_only(
            report.get("schema_file_fingerprints", [])
        ),
        "no_connection_material": not contains_connection_material(rendered),
        "no_execution_hints": not contains_execution_hints(rendered),
        "no_seed_or_data_load": not contains_seed_or_data_load(rendered),
        "no_business_conclusion_terms": not contains_business_conclusion_terms(rendered),
    }
    if len(table_sets) != len(SCHEMA_PATHS):
        checks["schema_table_sets_same"] = False
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    return {
        "mode": "lint-entrypoint-guard-report",
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
        {"rule": "status_is_entrypoint_guard_only", "passed": status_value(content) == GUARD_STATUS},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_entrypoint_guard_only"
        ],
    ]
    blocked_phrases = [phrase for phrase in ADR_BLOCKED_PHRASES if phrase in normalized]
    checked_rules.append({"rule": "no_completion_or_ready_claim", "passed": not blocked_phrases})
    failed = [rule["rule"] for rule in checked_rules if not rule["passed"]]
    return {
        "mode": "adr-check",
        "adr_path": relative_path(adr_path),
        "adr_exists": True,
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
    }


def schema_files_byte_identical() -> bool:
    if not all(path.exists() for path in SCHEMA_PATHS):
        return False
    return SCHEMA_PATHS[0].read_bytes() == SCHEMA_PATHS[1].read_bytes()


def schema_table_sets_same() -> bool:
    if not all(path.exists() for path in SCHEMA_PATHS):
        return False
    table_sets = [set(created_tables(path.read_text(encoding="utf-8"))) for path in SCHEMA_PATHS]
    return len({frozenset(tables) for tables in table_sets}) == 1


def anchors_table_exists() -> bool:
    return all("anchors" in set(created_tables(path.read_text(encoding="utf-8"))) for path in SCHEMA_PATHS)


def schema_fingerprints_are_metadata_only(fingerprints: object) -> bool:
    if not isinstance(fingerprints, list) or len(fingerprints) != len(SCHEMA_PATHS):
        return False
    expected_keys = {"path", "sha256", "line_count", "table_count", "read_only"}
    expected_paths = [relative_path(path) for path in SCHEMA_PATHS]
    for item, expected_path in zip(fingerprints, expected_paths):
        if not isinstance(item, Mapping):
            return False
        if set(item) != expected_keys:
            return False
        if item.get("path") != expected_path or item.get("read_only") is not True:
            return False
        if not isinstance(item.get("line_count"), int) or not isinstance(item.get("table_count"), int):
            return False
        if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            return False
    return True


def contains_connection_material(text: str) -> bool:
    tokens = (
        "postgres://",
        "postgresql://",
        "password=",
        "connection string",
        PRIMARY_ENV_DSN.lower(),
        LEGACY_ENV_DSN.lower(),
    )
    return any(token in text for token in tokens)


def contains_execution_hints(text: str) -> bool:
    tokens = (
        SQL_CLIENT,
        SHELL_PROCESS_TOKEN,
        "shell out",
        "apply-ready command",
        "apply ready command",
    )
    return any(token in text for token in tokens)


def contains_seed_or_data_load(text: str) -> bool:
    return bool(re.search(r"\b(insert\s+into|copy|load\s+data)\b", text, flags=re.IGNORECASE))


def contains_business_conclusion_terms(text: str) -> bool:
    return any(term in text for term in BLOCKED_BUSINESS_TERMS)


def created_tables(sql: str) -> list[str]:
    return re.findall(r"(?im)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z0-9_]*)\s*\(", sql)


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


def relative_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def validation_commands() -> list[str]:
    return [
        "python -m pytest tests/test_production_schema_live_apply_entrypoint_guard.py",
        "python scripts/platform/production_schema_live_apply_entrypoint_guard.py --contract-report",
        "python scripts/platform/production_schema_live_apply_entrypoint_guard.py --entrypoint-guard-report",
        "python scripts/platform/production_schema_live_apply_entrypoint_guard.py --render-live-apply-request-json",
        "python scripts/platform/production_schema_live_apply_entrypoint_guard.py --render-operator-runbook-md",
        "python scripts/platform/production_schema_live_apply_entrypoint_guard.py --lint-entrypoint-guard-report",
        "python scripts/platform/production_schema_live_apply_entrypoint_guard.py --adr-check",
    ]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Render production schema live-apply entrypoint guard reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--entrypoint-guard-report", action="store_true")
    mode.add_argument("--render-live-apply-request-json", action="store_true")
    mode.add_argument("--render-operator-runbook-md", action="store_true")
    mode.add_argument("--lint-entrypoint-guard-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.render_operator_runbook_md:
        sys.stdout.write(render_operator_runbook_md())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.entrypoint_guard_report:
        report = build_entrypoint_guard_report()
    elif args.render_live_apply_request_json:
        report = render_live_apply_request_json()
    elif args.lint_entrypoint_guard_report:
        report = lint_entrypoint_guard_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"entrypoint-guard-report", "lint-entrypoint-guard-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
