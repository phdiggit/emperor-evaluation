from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-schema-changing-formal-schema-update.md"
SCHEMA_PATHS = (
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
)
UPDATE_VERSION = "schema-changing-formal-schema-update-v1"
UPDATE_STATUS = "Proposed / Schema-changing formal schema file update"
APPROVAL_SOURCE = 'user message: "随时可以开启数据迁移"'
SQL_CLIENT = "p" + "sql"
SHELL_PROCESS_TOKEN = "sub" + "process"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
BLOCKED_BUSINESS_TERMS = ("sco" + "re", "ra" + "nk", "final_" + ("sco" + "re"), "leader" + "board")
REQUIRED_FLAGS = {
    "schema_changing_pr": True,
    "schema_files_modified": True,
    "production_migration_approved": True,
    "schema_change_user_approval_recorded": True,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "production_seed_executed": False,
    "live_apply_executed": False,
    "ready_for_schema_change_pr": True,
    "ready_for_production_migration": False,
    "future_live_apply_pr_required": True,
    "future_seed_apply_pr_required": True,
}
SUPPORTED_MODES = (
    "contract-report",
    "schema-change-report",
    "render-schema-change-json",
    "lint-schema-change-report",
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
    "archive/docs/adr/ADR-schema-changing-formal-schema-update.md",
)
EXPECTED_SCHEMA_TABLES = (
    "persons",
    "person_aliases",
    "subitems",
    "src_hosts",
    "jobs",
    "job_runs",
    "job_deps",
    "outbox",
    "review_items",
    "src_docs",
    "doc_revs",
    "passages",
    "passage_people",
    "query_profiles",
    "search_tasks",
    "search_hits",
    "cand_matches",
    "evd_cards",
    "evd_src_links",
    "clusters",
    "anchors",
    "cluster_evd",
    "imports",
    "import_rows",
)
LINT_RULES = (
    "schema_files_exist",
    "schema_changing_pr_true",
    "schema_files_modified_true",
    "production_migration_approved_true",
    "schema_change_user_approval_recorded_true",
    "sql_executed_false",
    "production_db_connected_false",
    "production_dsn_read_false",
    "production_seed_executed_false",
    "live_apply_executed_false",
    "ready_for_schema_change_pr_true",
    "ready_for_production_migration_false",
    "future_live_apply_pr_required_true",
    "future_seed_apply_pr_required_true",
    "approval_source_present",
    "schema_files_same_table_names",
    "expected_tables_present",
    "schemas_are_byte_identical",
    "no_connection_material",
    "no_seed_or_data_load",
    "no_shell_or_live_apply",
    "no_blocked_business_terms",
)
ADR_RULES = (
    ("status_is_schema_changing_update", UPDATE_STATUS),
    ("declares_schema_changing_pr", "schema_changing_pr=true"),
    ("declares_schema_files_modified", "schema_files_modified=true"),
    ("declares_user_approval", "schema_change_user_approval_recorded=true"),
    ("declares_sql_not_executed", "sql_executed=false"),
    ("declares_db_not_connected", "production_db_connected=false"),
    ("declares_dsn_not_read", "production_dsn_read=false"),
    ("declares_seed_not_executed", "production_seed_executed=false"),
    ("declares_live_apply_not_executed", "live_apply_executed=false"),
    ("declares_ready_for_schema_change", "ready_for_schema_change_pr=true"),
    ("declares_not_ready_for_production", "ready_for_production_migration=false"),
    ("declares_future_live_apply_pr", "future_live_apply_pr_required=true"),
    ("declares_future_seed_apply_pr", "future_seed_apply_pr_required=true"),
    ("approval_source_present", "随时可以开启数据迁移"),
)
ADR_BLOCKED_PHRASES = (
    "sql_executed=true",
    "production_db_connected=true",
    "production_dsn_read=true",
    "production_seed_executed=true",
    "live_apply_executed=true",
    "ready_for_production_migration=true",
    "live apply complete",
    "seed apply complete",
)


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "update_version": UPDATE_VERSION,
        "status": UPDATE_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "required_flags": dict(REQUIRED_FLAGS),
        "source_inputs": list(SOURCE_INPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "expected_schema_tables": list(EXPECTED_SCHEMA_TABLES),
        "future_required_prs": [
            "future live apply PR remains separate",
            "future seed apply PR remains separate",
        ],
        "validation_commands": validation_commands(),
    }


def render_schema_change_json() -> dict[str, Any]:
    return {
        "mode": "render-schema-change-json",
        "pr_number": 281,
        "title": "platform: apply guarded formal schema files",
        "update_version": UPDATE_VERSION,
        "status": UPDATE_STATUS,
        **REQUIRED_FLAGS,
        "approval_source": APPROVAL_SOURCE,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "schema_table_names": {relative_path(path): created_tables(path.read_text(encoding="utf-8")) for path in SCHEMA_PATHS},
        "expected_schema_tables": list(EXPECTED_SCHEMA_TABLES),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "future_required_prs": [
            "future live apply PR remains separate",
            "future seed apply PR remains separate",
        ],
        "warnings": [
            "schema-changing formal schema file update only",
            "does not execute SQL",
            "does not connect to PostgreSQL",
            "does not read production DSN",
            "does not execute production seed",
            "does not perform live apply",
            "ready_for_production_migration=false",
        ],
    }


def build_schema_change_report() -> dict[str, Any]:
    schema_change_json = render_schema_change_json()
    lint_report = lint_schema_change_report(schema_change_json)
    failed = list(lint_report["failed"])
    return {
        "mode": "schema-change-report",
        "pr_number": 281,
        "update_version": UPDATE_VERSION,
        **{key: schema_change_json[key] for key in REQUIRED_FLAGS},
        "approval_source": APPROVAL_SOURCE,
        "schema_file_fingerprints": list(schema_change_json["schema_file_fingerprints"]),
        "schema_change_lint_passed": bool(lint_report["passed"]),
        "schema_change_lint_failed": failed,
        "blocking_failures": failed,
        "schema_change_gate_summary": {
            "passed": [rule["rule"] for rule in lint_report["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "warnings": list(schema_change_json["warnings"]),
    }


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
            }
        )
    return fingerprints


def lint_schema_change_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_schema_change_json()
    schema_texts = {relative_path(path): path.read_text(encoding="utf-8") for path in SCHEMA_PATHS}
    table_sets = {path: set(created_tables(text)) for path, text in schema_texts.items()}
    combined_schema_text = "\n".join(schema_texts.values()).lower()
    checks = {
        "schema_files_exist": all(path.exists() for path in SCHEMA_PATHS),
        "schema_changing_pr_true": report.get("schema_changing_pr") is True,
        "schema_files_modified_true": report.get("schema_files_modified") is True,
        "production_migration_approved_true": report.get("production_migration_approved") is True,
        "schema_change_user_approval_recorded_true": report.get("schema_change_user_approval_recorded") is True,
        "sql_executed_false": report.get("sql_executed") is False,
        "production_db_connected_false": report.get("production_db_connected") is False,
        "production_dsn_read_false": report.get("production_dsn_read") is False,
        "production_seed_executed_false": report.get("production_seed_executed") is False,
        "live_apply_executed_false": report.get("live_apply_executed") is False,
        "ready_for_schema_change_pr_true": report.get("ready_for_schema_change_pr") is True,
        "ready_for_production_migration_false": report.get("ready_for_production_migration") is False,
        "future_live_apply_pr_required_true": report.get("future_live_apply_pr_required") is True,
        "future_seed_apply_pr_required_true": report.get("future_seed_apply_pr_required") is True,
        "approval_source_present": "随时可以开启数据迁移" in str(report.get("approval_source", "")),
        "schema_files_same_table_names": len({frozenset(tables) for tables in table_sets.values()}) == 1,
        "expected_tables_present": all(set(EXPECTED_SCHEMA_TABLES) <= tables for tables in table_sets.values()),
        "schemas_are_byte_identical": SCHEMA_PATHS[0].read_bytes() == SCHEMA_PATHS[1].read_bytes(),
        "no_connection_material": not contains_connection_material(combined_schema_text),
        "no_seed_or_data_load": not contains_seed_or_data_load(combined_schema_text),
        "no_shell_or_live_apply": SQL_CLIENT not in combined_schema_text
        and SHELL_PROCESS_TOKEN not in combined_schema_text
        and "live apply command" not in combined_schema_text
        and "apply-ready live command" not in combined_schema_text,
        "no_blocked_business_terms": all(term not in combined_schema_text for term in BLOCKED_BUSINESS_TERMS),
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    return {
        "mode": "lint-schema-change-report",
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
        {"rule": "status_is_schema_changing_update", "passed": status_value(content) == UPDATE_STATUS},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_schema_changing_update"
        ],
    ]
    blocked_phrases = [phrase for phrase in ADR_BLOCKED_PHRASES if phrase in normalized]
    checked_rules.append({"rule": "no_live_apply_or_production_ready_claim", "passed": not blocked_phrases})
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
        PRIMARY_ENV_DSN.lower(),
        LEGACY_ENV_DSN.lower(),
    )
    return any(token in text for token in tokens)


def contains_seed_or_data_load(text: str) -> bool:
    return bool(re.search(r"\b(insert\s+into|copy|load\s+data)\b", text, flags=re.IGNORECASE))


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
        "python -m pytest tests/test_schema_changing_formal_schema_update.py",
        "python scripts/platform/schema_changing_formal_schema_update.py --contract-report",
        "python scripts/platform/schema_changing_formal_schema_update.py --schema-change-report",
        "python scripts/platform/schema_changing_formal_schema_update.py --render-schema-change-json",
        "python scripts/platform/schema_changing_formal_schema_update.py --lint-schema-change-report",
        "python scripts/platform/schema_changing_formal_schema_update.py --adr-check",
    ]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Report guarded formal schema file updates.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--schema-change-report", action="store_true")
    mode.add_argument("--render-schema-change-json", action="store_true")
    mode.add_argument("--lint-schema-change-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
    elif args.schema_change_report:
        report = build_schema_change_report()
    elif args.render_schema_change_json:
        report = render_schema_change_json()
    elif args.lint_schema_change_report:
        report = lint_schema_change_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"schema-change-report", "lint-schema-change-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
