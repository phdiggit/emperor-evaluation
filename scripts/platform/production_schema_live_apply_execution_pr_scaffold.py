from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
ADR_PATH = ROOT / "docs" / "adr" / "ADR-production-schema-live-apply-execution-pr-scaffold.md"
SCHEMA_PATHS = (
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
)
SCAFFOLD_VERSION = "production-schema-live-apply-execution-pr-scaffold-v1"
SCAFFOLD_STATUS = "Proposed / Production schema live-apply execution PR scaffold only"
SQL_CLIENT = "p" + "sql"
SHELL_PROCESS_TOKEN = "sub" + "process"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
REQUIRED_FLAGS = {
    "live_apply_execution_pr_scaffold_only": True,
    "schema_files_modified": False,
    "schema_files_read_only": True,
    "schema_files_byte_identical_required": True,
    "production_schema_hashes_rendered": True,
    "live_apply_pr_approved": False,
    "live_apply_executed": False,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "production_seed_executed": False,
    "seed_apply_executed": False,
    "operator_evidence_recorded": False,
    "human_signoffs_recorded": False,
    "ready_for_live_apply": False,
    "ready_for_production_migration": False,
    "future_live_apply_execution_pr_required": True,
    "future_seed_apply_pr_required": True,
}
SUPPORTED_MODES = (
    "contract-report",
    "execution-scaffold-report",
    "render-execution-request-json",
    "render-future-pr-body-template",
    "render-operator-evidence-template-md",
    "lint-execution-scaffold-report",
    "adr-check",
)
ALLOWED_OUTPUTS = (
    "stdout_json_report",
    "in_memory_json",
    "future_pr_body_template",
    "operator_evidence_manifest_template",
    "rollback_restore_placeholder",
    "schema_metadata_fingerprints",
)
FORBIDDEN_ACTIONS = (
    "execute_sql",
    "connect_postgresql",
    "read_production_dsn",
    "execute_production_seed",
    "execute_live_apply",
    "write_public_schema",
    "emit_direct_db_command",
    "forge_human_signoff",
)
SOURCE_INPUTS = (
    "db/schema.sql",
    "db/postgres/001_init.sql",
    "docs/adr/ADR-production-schema-live-apply-execution-pr-scaffold.md",
    "docs/adr/ADR-production-schema-live-apply-entrypoint-guard.md",
    "docs/adr/ADR-schema-changing-formal-schema-update.md",
)
FUTURE_COMMAND_CHECKLIST = (
    "future execution command placeholder only",
    "exact database command intentionally omitted",
    "operator must review command in a separate future PR",
    "future PR must attach independent approval evidence",
    "future seed apply PR remains separate",
)
ROLLBACK_RESTORE_PLACEHOLDERS = (
    "rollback owner placeholder: pending future execution PR",
    "restore source placeholder: pending future execution PR",
    "backup verification placeholder: pending future execution PR",
    "post-restore validation placeholder: pending future execution PR",
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
    "future_body_blocked_by_default",
    "operator_template_has_no_recorded_approval",
    "rollback_restore_placeholders_present",
    "future_command_checklist_is_placeholder_only",
    "no_connection_material",
    "no_execution_hints",
    "no_seed_or_data_load",
    "no_completion_claim",
)
ADR_RULES = (
    ("status_is_execution_pr_scaffold_only", SCAFFOLD_STATUS),
    ("declares_pr281_chain", "PR #281 has entered the schema-changing file-update chain"),
    ("declares_pr282_guard", "PR #282 added the production schema live-apply entrypoint guard"),
    ("declares_scaffold_only", "live-apply execution PR scaffold only"),
    ("declares_future_pr_body_template", "future PR body template"),
    ("declares_operator_evidence_template", "operator evidence manifest template"),
    ("declares_rollback_restore_placeholder", "rollback / restore placeholder"),
    ("declares_schema_source_fingerprints", "schema source fingerprints"),
    ("declares_no_sql_execution", "No SQL execution"),
    ("declares_no_db_connection", "No DB connection"),
    ("declares_no_dsn_access", "No DSN access"),
    ("declares_no_seed", "No production seed execution"),
    ("declares_no_live_apply", "No live apply execution"),
    ("declares_no_public_schema_write", "No public schema write"),
    ("declares_no_signoff_forgery", "No sign-off forgery"),
    ("declares_future_live_apply_pr", "Future live apply execution PR remains required"),
    ("declares_future_seed_apply_pr", "Future seed apply PR remains required"),
    ("declares_operator_boundary", "templates are not execution approval"),
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
    "production migration completed",
    "production migration complete",
    "seed apply completed",
    "seed apply complete",
    "live apply completed",
    "live apply complete",
)


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "scaffold_version": SCAFFOLD_VERSION,
        "status": SCAFFOLD_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "required_flags": dict(REQUIRED_FLAGS),
        "source_inputs": list(SOURCE_INPUTS),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "validation_commands": validation_commands(),
        "future_required_prs": [
            "future live apply execution PR required",
            "future seed apply PR required",
        ],
    }


def render_execution_request_json() -> dict[str, Any]:
    return {
        "mode": "render-execution-request-json",
        "pr_number": 283,
        "title": "platform: add production schema live-apply execution PR scaffold",
        "scope": "production_schema_live_apply_execution_pr_scaffold_only",
        "required_flags": dict(REQUIRED_FLAGS),
        **REQUIRED_FLAGS,
        "schema_file_fingerprints": schema_file_fingerprints(),
        "schema_consistency": {
            "byte_identical": schema_files_byte_identical(),
            "table_sets_same": schema_table_sets_same(),
            "anchors_table_exists": anchors_table_exists(),
        },
        "future_pr_body_template_sha256": sha256_text(render_future_pr_body_template()),
        "operator_evidence_template_sha256": sha256_text(render_operator_evidence_template_md()),
        "rollback_restore_placeholders": list(ROLLBACK_RESTORE_PLACEHOLDERS),
        "future_execution_command_checklist": list(FUTURE_COMMAND_CHECKLIST),
        "warnings": [
            "execution PR scaffold only; this is not the live apply PR",
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


def build_execution_scaffold_report() -> dict[str, Any]:
    request = render_execution_request_json()
    lint = lint_execution_scaffold_report(request)
    failed = list(lint["failed"])
    return {
        "mode": "execution-scaffold-report",
        "scaffold_version": SCAFFOLD_VERSION,
        "scaffold_status": SCAFFOLD_STATUS,
        **{key: request[key] for key in REQUIRED_FLAGS},
        "schema_file_fingerprints": list(request["schema_file_fingerprints"]),
        "schema_consistency": dict(request["schema_consistency"]),
        "future_pr_body_template_sha256": request["future_pr_body_template_sha256"],
        "operator_evidence_template_sha256": request["operator_evidence_template_sha256"],
        "rollback_restore_placeholders": list(request["rollback_restore_placeholders"]),
        "future_execution_command_checklist": list(request["future_execution_command_checklist"]),
        "execution_scaffold_lint_passed": bool(lint["passed"]),
        "execution_scaffold_lint_failed": failed,
        "blocking_failures": failed,
        "gate_summary": {
            "passed": [rule["rule"] for rule in lint["checked_rules"] if rule["passed"]],
            "failed": failed,
        },
        "warnings": list(request["warnings"]),
    }


def render_future_pr_body_template() -> str:
    fingerprints = schema_file_fingerprints()
    lines = [
        "# Future Production Schema Live-Apply Execution PR Template",
        "",
        "BLOCKED BY DEFAULT.",
        "",
        "This PR is a production schema live-apply execution PR scaffold only.",
        "It does not approve live apply.",
        "It does not execute SQL.",
        "It does not connect to PostgreSQL.",
        "It does not read DSN material.",
        "It does not execute production seed.",
        "It does not modify schema files.",
        "`ready_for_live_apply=false`.",
        "`ready_for_production_migration=false`.",
        "Future live apply execution PR remains required.",
        "Future seed apply PR remains required.",
        "",
        "## Required Flags",
        "",
        *[f"- `{name}={str(expected).lower()}`" for name, expected in REQUIRED_FLAGS.items()],
        "",
        "## Schema Source Fingerprints",
        "",
    ]
    for item in fingerprints:
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
            "## Operator Evidence Manifest Placeholder",
            "",
            "- approval evidence: placeholder only; not recorded by this scaffold.",
            "- human sign-offs: placeholder only; not recorded by this scaffold.",
            "- execution evidence: placeholder only; not recorded by this scaffold.",
            "",
            "## Rollback / Restore Placeholder",
            "",
            *[f"- {item}." for item in ROLLBACK_RESTORE_PLACEHOLDERS],
            "",
            "## Future Execution Command Checklist",
            "",
            *[f"- {item}." for item in FUTURE_COMMAND_CHECKLIST],
            "",
            "## Governance Export Boundary",
            "",
            "- `exports/governance/文档治理盘点报告.md` is docs governance report sync only.",
            "- It is not a production artifact, seed artifact, migration artifact, or data artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def render_operator_evidence_template_md() -> str:
    lines = [
        "# Operator Evidence Manifest Template",
        "",
        "TEMPLATE ONLY. NO APPROVAL IS RECORDED HERE.",
        "",
        "- live apply approval: not recorded by this scaffold.",
        "- execution operator: placeholder only.",
        "- reviewer sign-off: placeholder only.",
        "- rollback owner: placeholder only.",
        "- restore evidence: placeholder only.",
        "- production seed evidence: not recorded by this scaffold.",
        "- ready_for_live_apply: `false`.",
        "- ready_for_production_migration: `false`.",
        "",
        "## Future Evidence Slots",
        "",
        "- Future execution PR approval evidence slot.",
        "- Future execution PR operator transcript slot.",
        "- Future rollback / restore validation evidence slot.",
        "- Future seed apply PR evidence slot.",
        "",
    ]
    return "\n".join(lines)


def lint_execution_scaffold_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_execution_request_json()
    rendered = report_as_json(report).lower()
    body_template = render_future_pr_body_template()
    operator_template = render_operator_evidence_template_md()
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
        "future_body_blocked_by_default": future_body_blocked_by_default(body_template),
        "operator_template_has_no_recorded_approval": operator_template_has_no_recorded_approval(operator_template),
        "rollback_restore_placeholders_present": set(report.get("rollback_restore_placeholders", []))
        == set(ROLLBACK_RESTORE_PLACEHOLDERS),
        "future_command_checklist_is_placeholder_only": set(report.get("future_execution_command_checklist", []))
        == set(FUTURE_COMMAND_CHECKLIST),
        "no_connection_material": not contains_connection_material(rendered),
        "no_execution_hints": not contains_execution_hints(rendered),
        "no_seed_or_data_load": not contains_seed_or_data_load(rendered),
        "no_completion_claim": not contains_completion_claim(rendered),
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    return {
        "mode": "lint-execution-scaffold-report",
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
        {"rule": "status_is_execution_pr_scaffold_only", "passed": status_value(content) == SCAFFOLD_STATUS},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_execution_pr_scaffold_only"
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


def future_body_blocked_by_default(text: str) -> bool:
    normalized = normalize_text(text)
    required = (
        "blocked by default",
        "does not approve live apply",
        "does not execute sql",
        "does not connect to postgresql",
        "does not read dsn material",
        "ready_for_live_apply=false",
        "ready_for_production_migration=false",
        "future live apply execution pr remains required",
        "future seed apply pr remains required",
    )
    return all(needle in normalized for needle in required)


def operator_template_has_no_recorded_approval(text: str) -> bool:
    normalized = normalize_text(text)
    return (
        "template only" in normalized
        and "no approval is recorded here" in normalized
        and "placeholder only" in normalized
        and "ready_for_live_apply: `false`" in normalized
    )


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
        "direct db command",
    )
    return any(token in text for token in tokens)


def contains_seed_or_data_load(text: str) -> bool:
    return bool(re.search(r"\b(insert\s+into|copy\s+\w+\s+from|load\s+data)\b", text, flags=re.IGNORECASE))


def contains_completion_claim(text: str) -> bool:
    tokens = (
        "production migration completed",
        "production migration complete",
        "seed apply completed",
        "seed apply complete",
        "live apply completed",
        "live apply complete",
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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relative_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def validation_commands() -> list[str]:
    return [
        "python -m pytest tests/test_production_schema_live_apply_execution_pr_scaffold.py",
        "python scripts/platform/production_schema_live_apply_execution_pr_scaffold.py --contract-report",
        "python scripts/platform/production_schema_live_apply_execution_pr_scaffold.py --execution-scaffold-report",
        "python scripts/platform/production_schema_live_apply_execution_pr_scaffold.py --render-execution-request-json",
        "python scripts/platform/production_schema_live_apply_execution_pr_scaffold.py --render-future-pr-body-template",
        "python scripts/platform/production_schema_live_apply_execution_pr_scaffold.py --render-operator-evidence-template-md",
        "python scripts/platform/production_schema_live_apply_execution_pr_scaffold.py --lint-execution-scaffold-report",
        "python scripts/platform/production_schema_live_apply_execution_pr_scaffold.py --adr-check",
    ]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Render production schema live-apply execution PR scaffold reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--execution-scaffold-report", action="store_true")
    mode.add_argument("--render-execution-request-json", action="store_true")
    mode.add_argument("--render-future-pr-body-template", action="store_true")
    mode.add_argument("--render-operator-evidence-template-md", action="store_true")
    mode.add_argument("--lint-execution-scaffold-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.render_future_pr_body_template:
        sys.stdout.write(render_future_pr_body_template())
        return 0
    if args.render_operator_evidence_template_md:
        sys.stdout.write(render_operator_evidence_template_md())
        return 0
    if args.contract_report:
        report = build_contract_report()
    elif args.execution_scaffold_report:
        report = build_execution_scaffold_report()
    elif args.render_execution_request_json:
        report = render_execution_request_json()
    elif args.lint_execution_scaffold_report:
        report = lint_execution_scaffold_report()
    else:
        report = build_adr_check()

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if report.get("mode") in {"execution-scaffold-report", "lint-execution-scaffold-report", "adr-check"} and (
        report.get("blocking_failures") or report.get("failed")
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
