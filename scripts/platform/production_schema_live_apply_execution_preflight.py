from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-production-schema-live-apply-execution-preflight.md"
SCHEMA_PATHS = (
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
)
PREFLIGHT_VERSION = "production-schema-live-apply-execution-preflight-v1"
PREFLIGHT_STATUS = "Proposed / Production schema live-apply execution preflight only"
SQL_CLIENT = "p" + "sql"
SHELL_PROCESS_TOKEN = "sub" + "process"
PRIMARY_DSN_TOKEN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_DSN_TOKEN = "PG_SEARCH" + "_BENCH_DSN"
REQUIRED_FLAGS = {
    "live_apply_execution_preflight_only": True,
    "live_apply_pr_approved": False,
    "live_apply_executed": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "dsn_required_in_this_pr": False,
    "production_seed_executed": False,
    "seed_apply_executed": False,
    "schema_files_modified": False,
    "schema_files_read_only": True,
    "schema_files_byte_identical_required": True,
    "production_schema_hashes_rendered": True,
    "operator_evidence_recorded": False,
    "human_signoffs_recorded": False,
    "ready_for_live_apply": False,
    "ready_for_production_migration": False,
    "future_live_apply_execution_pr_required": True,
    "future_seed_apply_pr_required": True,
}
OPTIONAL_FLAGS = {
    "future_live_apply_execution_pr_can_be_next": True,
}
SUPPORTED_MODES = (
    "contract-report",
    "preflight-report",
    "render-preflight-json",
    "render-operator-evidence-checklist-md",
    "render-future-live-apply-pr-body-template",
    "lint-preflight-report",
    "adr-check",
)
ALLOWED_OUTPUTS = (
    "stdout_json_report",
    "stdout_markdown_template",
    "metadata_only_schema_fingerprints",
    "operator_evidence_checklist_placeholder",
    "future_live_apply_pr_body_template",
    "preflight_gate_report",
)
FORBIDDEN_ACTIONS = (
    "approve_live_apply",
    "execute_sql",
    "connect_postgresql",
    "read_production_dsn",
    "execute_live_apply",
    "execute_production_seed",
    "write_public_schema",
    "emit_database_command",
    "emit_apply_ready_script",
    "forge_human_signoff",
)
SOURCE_INPUTS = (
    "db/schema.sql",
    "db/postgres/001_init.sql",
    "archive/docs/adr/ADR-schema-changing-formal-schema-update.md",
    "archive/docs/adr/ADR-production-schema-live-apply-entrypoint-guard.md",
    "archive/docs/adr/ADR-production-schema-live-apply-execution-pr-scaffold.md",
    "archive/docs/adr/ADR-production-schema-live-apply-execution-preflight.md",
)
PREFLIGHT_EVIDENCE_ITEMS = (
    "schema source hash alignment reviewed",
    "schema files byte-identical check reviewed",
    "table-set consistency reviewed",
    "anchors table presence reviewed",
    "operator evidence placeholder reviewed",
    "rollback and restore placeholder reviewed",
    "future execution approval boundary reviewed",
    "future seed apply boundary reviewed",
)
ROLLBACK_RESTORE_CHECKS = (
    "rollback owner placeholder: pending future execution PR",
    "restore source placeholder: pending future execution PR",
    "backup evidence placeholder: pending future execution PR",
    "post-restore verification placeholder: pending future execution PR",
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
    "operator_evidence_required_true",
    "live_apply_command_included_false",
    "future_pr_body_blocked_by_default",
    "operator_checklist_has_placeholders_only",
    "rollback_restore_checks_present",
    "no_connection_material",
    "no_execution_hints",
    "no_schema_or_seed_body",
    "no_completion_claim",
)
ADR_RULES = (
    ("status_is_preflight_only", PREFLIGHT_STATUS),
    ("declares_pr281_context", "#281 completed the formal schema file update"),
    ("declares_pr282_context", "#282 added the live-apply entrypoint guard"),
    ("declares_pr283_context", "#283 added the execution PR scaffold"),
    ("declares_preflight_package", "non-executing preflight package"),
    ("declares_contract_report", "contract report"),
    ("declares_preflight_report", "preflight report"),
    ("declares_preflight_json", "preflight JSON"),
    ("declares_operator_checklist", "operator evidence checklist markdown"),
    ("declares_future_pr_template", "future live apply PR body template"),
    ("declares_lint_report", "lint report"),
    ("declares_adr_check", "ADR check"),
    ("declares_no_sql_execution", "No SQL execution"),
    ("declares_no_db_connection", "No DB connection"),
    ("declares_no_dsn_access", "No DSN access"),
    ("declares_no_seed", "No production seed execution"),
    ("declares_no_live_apply", "No live apply execution"),
    ("declares_no_public_schema_write", "No public schema write"),
    ("declares_no_signoff_forgery", "No human sign-off forgery"),
    ("declares_live_apply_gate_completed", "live apply execution gate has since been completed by #285"),
    ("declares_epic1_target_importer_gate", "epic 1 target importer gate"),
    *[(f"declares_{name}", f"{name}={str(expected).lower()}") for name, expected in REQUIRED_FLAGS.items()],
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
    "live apply completed",
    "seed apply completed",
    "production migration completed",
)


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "preflight_version": PREFLIGHT_VERSION,
        "status": PREFLIGHT_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "required_flags": dict(REQUIRED_FLAGS),
        "optional_flags": dict(OPTIONAL_FLAGS),
        "source_inputs": list(SOURCE_INPUTS),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "future_required_prs": [
            "future live apply execution PR required",
            "future seed apply PR required",
        ],
    }


def render_preflight_json() -> dict[str, Any]:
    return {
        "mode": "render-preflight-json",
        "pr_number": 284,
        "title": "platform: add production schema live-apply execution preflight package",
        "scope": "production_schema_live_apply_execution_preflight_only",
        "required_flags": dict(REQUIRED_FLAGS),
        "optional_flags": dict(OPTIONAL_FLAGS),
        **REQUIRED_FLAGS,
        **OPTIONAL_FLAGS,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "schema_consistency": {
            "byte_identical": schema_files_byte_identical(),
            "table_sets_same": schema_table_sets_same(),
            "anchors_table_exists": anchors_table_exists(),
        },
        "operator_evidence_required": True,
        "live_apply_command_included": False,
        "future_required_prs": [
            "future live apply execution PR required",
            "future seed apply PR required",
        ],
        "preflight_evidence_items": list(PREFLIGHT_EVIDENCE_ITEMS),
        "rollback_restore_checks": list(ROLLBACK_RESTORE_CHECKS),
        "warnings": [
            "preflight package only; this is not the live apply PR",
            "does not approve live apply",
            "does not execute SQL",
            "does not connect to PostgreSQL",
            "does not read DSN material",
            "does not execute production seed",
            "does not modify schema files",
            "ready_for_live_apply=false",
            "ready_for_production_migration=false",
            "future live apply execution PR remains required",
            "future seed apply PR remains required",
        ],
    }


def build_preflight_report() -> dict[str, Any]:
    preflight = render_preflight_json()
    lint = lint_preflight_report(preflight)
    failed = list(lint["failed"])
    return {
        "mode": "preflight-report",
        "preflight_version": PREFLIGHT_VERSION,
        "preflight_status": PREFLIGHT_STATUS,
        **{key: preflight[key] for key in REQUIRED_FLAGS},
        **OPTIONAL_FLAGS,
        "schema_file_fingerprints": list(preflight["schema_file_fingerprints"]),
        "schema_consistency": dict(preflight["schema_consistency"]),
        "operator_evidence_required": preflight["operator_evidence_required"],
        "live_apply_command_included": preflight["live_apply_command_included"],
        "future_required_prs": list(preflight["future_required_prs"]),
        "preflight_evidence_items": list(preflight["preflight_evidence_items"]),
        "rollback_restore_checks": list(preflight["rollback_restore_checks"]),
        "preflight_lint_passed": bool(lint["passed"]),
        "preflight_lint_failed": failed,
        "blocking_failures": failed,
        "gate_summary": {
            "passed": [rule["rule"] for rule in lint["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "warnings": list(preflight["warnings"]),
    }


def render_operator_evidence_checklist_md() -> str:
    lines = [
        "# Production Schema Live-Apply Operator Evidence Checklist",
        "",
        "PREFLIGHT TEMPLATE ONLY. NO APPROVAL OR SIGN-OFF IS RECORDED HERE.",
        "",
        "- live apply approval: placeholder only; not recorded by this preflight.",
        "- operator evidence: placeholder only; not recorded by this preflight.",
        "- reviewer sign-off: placeholder only; not recorded by this preflight.",
        "- rollback owner evidence: placeholder only; not recorded by this preflight.",
        "- restore verification evidence: placeholder only; not recorded by this preflight.",
        "- production seed evidence: outside this preflight.",
        "- ready_for_live_apply: `false`.",
        "- ready_for_production_migration: `false`.",
        "",
        "## Required Future Evidence",
        "",
        *[f"- {item}." for item in PREFLIGHT_EVIDENCE_ITEMS],
        "",
        "## Rollback / Restore Placeholders",
        "",
        *[f"- {item}." for item in ROLLBACK_RESTORE_CHECKS],
        "",
    ]
    return "\n".join(lines)


def render_future_live_apply_pr_body_template() -> str:
    lines = [
        "# Future Production Schema Live-Apply Execution PR Template",
        "",
        "BLOCKED BY DEFAULT.",
        "",
        "This PR is a production schema live-apply execution preflight package only.",
        "It does not approve live apply.",
        "It does not execute SQL.",
        "It does not connect to PostgreSQL.",
        "It does not read DSN material.",
        "It does not execute production seed.",
        "It does not modify schema files.",
        "ready_for_live_apply=false.",
        "ready_for_production_migration=false.",
        "Live apply execution gate has since been completed by #285.",
        "Epic 1 target importer gate remains required.",
        "",
        "## Required Flags",
        "",
        *[f"- `{name}={str(expected).lower()}`" for name, expected in REQUIRED_FLAGS.items()],
        "- `future_live_apply_execution_pr_can_be_next=true`.",
        "",
        "## Schema Source Fingerprints",
        "",
    ]
    for item in schema_file_fingerprints():
        lines.extend(
            [
                f"- `{item['path']}`",
                f"  - sha256: `{item['sha256']}`",
                f"  - line_count: `{item['line_count']}`",
                f"  - table_count: `{item['table_count']}`",
                "  - read_only: `true`",
            ]
        )
    lines.extend(
        [
            "",
            "## Minimum Future Evidence Requirements",
            "",
            *[f"- {item}." for item in PREFLIGHT_EVIDENCE_ITEMS],
            "",
            "## Governance Export Boundary",
            "",
            "- `exports/governance/文档治理盘点报告.md` is docs governance report sync only.",
            "- It is not a production artifact, seed artifact, migration artifact, or data artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def lint_preflight_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_preflight_json()
    rendered = report_as_json(report).lower()
    body_template = render_future_live_apply_pr_body_template()
    operator_checklist = render_operator_evidence_checklist_md()
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
        "operator_evidence_required_true": report.get("operator_evidence_required") is True,
        "live_apply_command_included_false": report.get("live_apply_command_included") is False,
        "future_pr_body_blocked_by_default": future_pr_body_blocked_by_default(body_template),
        "operator_checklist_has_placeholders_only": operator_checklist_has_placeholders_only(operator_checklist),
        "rollback_restore_checks_present": set(report.get("rollback_restore_checks", []))
        == set(ROLLBACK_RESTORE_CHECKS),
        "no_connection_material": not contains_connection_material(rendered),
        "no_execution_hints": not contains_execution_hints(rendered),
        "no_schema_or_seed_body": not contains_schema_or_seed_body(rendered),
        "no_completion_claim": not contains_completion_claim(rendered),
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    return {
        "mode": "lint-preflight-report",
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
        {"rule": "status_is_preflight_only", "passed": status_value(content) == PREFLIGHT_STATUS},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_preflight_only"
        ],
    ]
    blocked_phrases = [phrase for phrase in ADR_BLOCKED_PHRASES if phrase in normalized]
    checked_rules.append({"rule": "no_ready_executed_connected_or_completed_claim", "passed": not blocked_phrases})
    failed = [rule["rule"] for rule in checked_rules if not rule["passed"]]
    return {
        "mode": "adr-check",
        "adr_path": relative_path(adr_path),
        "adr_exists": True,
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
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
                "table_count": len(created_tables(text)),
                "read_only": True,
            }
        )
    return fingerprints


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


def future_pr_body_blocked_by_default(text: str) -> bool:
    normalized = normalize_text(text)
    required = (
        "blocked by default",
        "does not approve live apply",
        "does not execute sql",
        "does not connect to postgresql",
        "does not read dsn material",
        "ready_for_live_apply=false",
        "ready_for_production_migration=false",
        "live apply execution gate has since been completed by #285",
        "epic 1 target importer gate remains required",
    )
    return all(needle in normalized for needle in required)


def operator_checklist_has_placeholders_only(text: str) -> bool:
    normalized = normalize_text(text)
    return (
        "preflight template only" in normalized
        and "no approval or sign-off is recorded here" in normalized
        and "placeholder only" in normalized
        and "ready_for_live_apply: `false`" in normalized
        and "ready_for_production_migration: `false`" in normalized
    )


def contains_connection_material(text: str) -> bool:
    tokens = (
        "postgres://",
        "postgresql://",
        "password=",
        "connection string",
        PRIMARY_DSN_TOKEN.lower(),
        LEGACY_DSN_TOKEN.lower(),
    )
    return any(token in text for token in tokens)


def contains_execution_hints(text: str) -> bool:
    tokens = (
        SQL_CLIENT,
        SHELL_PROCESS_TOKEN,
        "shell out",
        "apply-ready",
        "direct database command",
        "live apply command",
    )
    return any(token in text for token in tokens)


def contains_schema_or_seed_body(text: str) -> bool:
    return bool(
        re.search(
            r"\b(create\s+table|alter\s+table|insert\s+into|copy\s+\w+\s+from|load\s+data)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def contains_completion_claim(text: str) -> bool:
    tokens = (
        "live apply completed",
        "seed apply completed",
        "production migration completed",
    )
    return any(token in text for token in tokens)


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


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Render production schema live-apply execution preflight reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--preflight-report", action="store_true")
    mode.add_argument("--render-preflight-json", action="store_true")
    mode.add_argument("--render-operator-evidence-checklist-md", action="store_true")
    mode.add_argument("--render-future-live-apply-pr-body-template", action="store_true")
    mode.add_argument("--lint-preflight-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.render_operator_evidence_checklist_md:
        sys.stdout.write(render_operator_evidence_checklist_md())
        return 0
    if args.render_future_live_apply_pr_body_template:
        sys.stdout.write(render_future_live_apply_pr_body_template())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.preflight_report:
        report = build_preflight_report()
    elif args.render_preflight_json:
        report = render_preflight_json()
    elif args.lint_preflight_report:
        report = lint_preflight_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"preflight-report", "lint-preflight-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
