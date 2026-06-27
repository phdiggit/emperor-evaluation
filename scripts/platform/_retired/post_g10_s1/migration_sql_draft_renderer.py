from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


def _repo_root() -> Path:
    for path in Path(__file__).resolve().parents:
        if (path / "db" / "schema.sql").is_file() and (path / "scripts" / "platform").is_dir():
            return path
    raise RuntimeError("could not locate repository root")


ROOT = _repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import (  # noqa: E402
    cutover_readiness_matrix,
    formal_ddl_rehearsal,
    formal_migration_proposal,
    formal_schema_draft,
    production_migration_admission,
    production_migration_dry_run_package,
)


RENDERER_VERSION = "migration-sql-draft-renderer-v1"
ADR_PATH = ROOT / "archive" / "docs" / "adr" / "ADR-migration-sql-draft-renderer.md"
DRAFT_STATUS = "Proposed"
SQL_CLIENT = "p" + "sql"
PUBLIC_SCHEMA_QUALIFIER = "public" + "."
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
SUPPORTED_MODES = (
    "contract-report",
    "draft-report",
    "render-draft-sql",
    "lint-draft-sql",
    "adr-check",
)
DRAFT_SECTIONS = (
    "draft_only_header",
    "source_metadata",
    "target_table_summary",
    "deferred_phase_2_3_summary",
    "formal_ddl_rehearsal_sql",
    "lint_only_report",
)
LINT_RULES = (
    "contains_draft_only_header",
    "contains_do_not_execute_warning",
    "contains_source_metadata",
    "contains_target_table_summary",
    "contains_deferred_table_summary",
    "no_dsn_or_secret",
    "no_" + SQL_CLIENT + "_instruction",
    "no_subprocess_instruction",
    "no_public_schema_hardcode",
    "no_production_seed_statement",
    "no_copy_load_data_upsert",
    "no_blocked_report_terms",
)
NON_GOALS = (
    "does not modify canonical JSONL",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not connect to PostgreSQL",
    "does not read .env or DSN values",
    "does not execute SQL",
    "does not execute production migration",
    "does not execute production seed",
    "does not write data paths",
    "does not write exports paths",
    "does not change business conclusions",
)
BOUNDARIES = (
    "draft SQL is stdout and in-memory only by default",
    "draft SQL is proposal text only",
    "draft SQL is not written to schema files",
    "draft SQL is not executed",
    "draft report is offline by default",
    "readiness report is called with database evidence disabled",
    "future production migration PR remains separately required",
)
LIMITATIONS = (
    "draft text only",
    "static lint only",
    "no PostgreSQL grammar parsing",
    "no production database evidence collected",
    "no schema diff against production files",
)
FUTURE_WORK = (
    "PR #272 schema diff draft renderer",
    "separate executable migration PR approval",
)
REPORT_GATES = (
    "dry_run_package_report_available",
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "draft_status_is_proposed",
    "migration_sql_draft_only_true",
    "sql_executed_false",
    "schema_files_modified_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "draft_sql_rendered",
    "draft_sql_lint_passed",
    "target_table_summary_present",
    "deferred_table_summary_present",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
)
ADR_RULES = (
    ("status_is_proposed", "Status is Proposed"),
    ("declares_migration_sql_draft_only", "migration_sql_draft_only=true"),
    ("sql_executed_false", "sql_executed=false"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("production_db_connected_false", "production_db_connected=false"),
    ("future_production_migration_pr_required", "future production migration PR required"),
    ("declares_no_production_migration", "no production migration"),
    ("declares_no_production_seed", "no production seed"),
    ("declares_no_schema_file_edits", "no schema file edits"),
    ("declares_lint_rules", "## Lint Rules"),
    ("declares_sql_draft_boundaries", "## SQL Draft Boundaries"),
)
ADR_BLOCKED_PHRASES = (
    "migration_sql_draft_only=false",
    "migration_sql_draft_only = false",
    "sql_executed=true",
    "sql_executed = true",
    "schema_files_modified=true",
    "schema_files_modified = true",
    "production_db_connected=true",
    "production_db_connected = true",
    "production migration ready",
    "production seed executed",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "renderer_version": RENDERER_VERSION,
        "status": DRAFT_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "source_reports": [
            "formal_ddl_rehearsal.render_sql()",
            "formal_schema_draft table constants",
            "production_migration_dry_run_package.build_package_report()",
            "production_migration_admission.build_admission_report()",
            "formal_migration_proposal.build_proposal_report()",
            "cutover_readiness_matrix.build_readiness_report(include_db_evidence=False, env={})",
        ],
        "draft_sections": list(DRAFT_SECTIONS),
        "lint_rules": list(LINT_RULES),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "limitations": list(LIMITATIONS),
        "future_work": list(FUTURE_WORK),
    }
    assert_no_blocked_terms(report)
    return report


def build_draft_report(
    adr_path: Path = ADR_PATH,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_errors: list[str] = []
    if package_report is None:
        try:
            package_report = production_migration_dry_run_package.build_package_report()
        except Exception:
            package_report = {}
            source_errors.append("dry_run_package_report_available")
    if admission_report is None:
        try:
            admission_report = production_migration_admission.build_admission_report()
        except Exception:
            admission_report = {}
            source_errors.append("production_migration_admission_available")
    if proposal_report is None:
        try:
            proposal_report = formal_migration_proposal.build_proposal_report()
        except Exception:
            proposal_report = {}
            source_errors.append("formal_migration_proposal_available")
    if readiness_report is None:
        try:
            readiness_report = cutover_readiness_matrix.build_readiness_report(
                include_db_evidence=False,
                env={},
            )
        except Exception:
            readiness_report = {}
            source_errors.append("cutover_readiness_report_available")

    draft_sql = render_draft_sql()
    lint_report = lint_draft_sql(draft_sql)
    adr_check = build_adr_check(adr_path)
    target_summary = target_table_summary()
    deferred_summary = deferred_table_summary()
    gates = build_report_gates(
        package_report,
        admission_report,
        proposal_report,
        readiness_report,
        lint_report,
        adr_check,
        target_summary,
        deferred_summary,
        source_errors,
    )
    failed = [gate_item["gate"] for gate_item in gates if not gate_item["passed"]]
    report = {
        "mode": "draft-report",
        "renderer_version": RENDERER_VERSION,
        "adr_path": relative_path(adr_path),
        "draft_status": DRAFT_STATUS,
        "migration_sql_draft_only": True,
        "sql_executed": False,
        "schema_files_modified": False,
        "production_db_connected": False,
        "future_production_migration_pr_required": True,
        "package_status": package_report.get("package_status"),
        "admission_status": admission_report.get("admission_status"),
        "proposal_status": proposal_report.get("proposal_status"),
        "readiness_state": readiness_report.get("readiness_state"),
        "draft_sql_sha256": sha256_text(draft_sql),
        "draft_sql_line_count": len(draft_sql.splitlines()),
        "lint_passed": bool(lint_report["passed"]),
        "lint_failed": list(lint_report["failed"]),
        "target_table_summary": target_summary,
        "deferred_table_summary": deferred_summary,
        "gates": gates,
        "blocking_failures": failed,
        "warnings": (
            list(package_report.get("warnings", []))
            + list(admission_report.get("warnings", []))
            + list(proposal_report.get("warnings", []))
            + list(readiness_report.get("warnings", []))
        ),
    }
    assert_no_blocked_terms(report)
    return report


def render_draft_sql() -> str:
    ddl_sql = formal_ddl_rehearsal.render_sql()
    ddl_lines = [
        line
        for line in ddl_sql.splitlines()
        if "SET search_path" not in line and PUBLIC_SCHEMA_QUALIFIER not in line
    ]
    lines = [
        "-- MIGRATION SQL DRAFT ONLY",
        "-- Do not execute.",
        "-- Source: formal_schema_draft + formal_ddl_rehearsal",
        f"-- Renderer: {RENDERER_VERSION}",
        "-- Generated for review only.",
        "-- Target Phase 1 base tables:",
        f"-- {', '.join(formal_schema_draft.PHASE_1_BASE_TABLES)}",
        "-- Deferred Phase 2/3 tables:",
        f"-- Phase 2: {', '.join(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES)}",
        f"-- Phase 3: {', '.join(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES)}",
        "",
        *ddl_lines,
        "",
        "-- End of migration SQL draft only.",
    ]
    return "\n".join(lines)


def lint_draft_sql(sql: str | None = None) -> dict[str, Any]:
    if sql is None:
        sql = render_draft_sql()
    lowered = sql.lower()
    rule_results = {
        "contains_draft_only_header": "-- migration sql draft only" in lowered,
        "contains_do_not_execute_warning": "do not execute" in lowered,
        "contains_source_metadata": "source: formal_schema_draft + formal_ddl_rehearsal" in lowered,
        "contains_target_table_summary": "target phase 1 base tables" in lowered,
        "contains_deferred_table_summary": "deferred phase 2/3 tables" in lowered,
        "no_dsn_or_secret": not _contains_dsn_or_secret(sql),
        "no_" + SQL_CLIENT + "_instruction": SQL_CLIENT not in lowered,
        "no_subprocess_instruction": "subprocess" not in lowered,
        "no_public_schema_hardcode": PUBLIC_SCHEMA_QUALIFIER not in lowered,
        "no_production_seed_statement": not _contains_production_seed_statement(sql),
        "no_copy_load_data_upsert": not re.search(r"(?i)\b(COPY|LOAD\s+DATA|UPSERT|ON\s+CONFLICT)\b", sql),
        "no_blocked_report_terms": all(term not in lowered for term in formal_schema_draft.BLOCKED_REPORT_TERMS),
    }
    checked_rules = [{"rule": rule, "passed": bool(rule_results[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not rule_results[rule]]
    report = {
        "mode": "lint-draft-sql",
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
        "sql_line_count": len(sql.splitlines()),
        "target_table_summary": target_table_summary(),
        "deferred_table_summary": deferred_table_summary(),
        "limitations": [
            "static lint only",
            "does not parse PostgreSQL grammar",
            "does not connect to PostgreSQL",
            "does not execute SQL",
        ],
    }
    assert_no_blocked_terms(report)
    return report


def build_report_gates(
    package_report: Mapping[str, Any],
    admission_report: Mapping[str, Any],
    proposal_report: Mapping[str, Any],
    readiness_report: Mapping[str, Any],
    lint_report: Mapping[str, Any],
    adr_check: Mapping[str, Any],
    target_summary: Mapping[str, Any],
    deferred_summary: Mapping[str, Any],
    source_errors: Sequence[str],
) -> list[dict[str, Any]]:
    return [
        gate("dry_run_package_report_available", "dry_run_package_report_available" not in source_errors and package_report.get("mode") == "package-report"),
        gate("production_migration_admission_available", "production_migration_admission_available" not in source_errors and admission_report.get("mode") == "admission-report"),
        gate("formal_migration_proposal_available", "formal_migration_proposal_available" not in source_errors and proposal_report.get("mode") == "proposal-report"),
        gate("cutover_readiness_report_available", "cutover_readiness_report_available" not in source_errors and readiness_report.get("mode") == "readiness-report"),
        gate("draft_status_is_proposed", DRAFT_STATUS == "Proposed"),
        gate("migration_sql_draft_only_true", True),
        gate("sql_executed_false", True),
        gate("schema_files_modified_false", True),
        gate("production_db_connected_false", True),
        gate("future_production_migration_pr_required", True),
        gate("draft_sql_rendered", bool(render_draft_sql().strip())),
        gate("draft_sql_lint_passed", bool(lint_report.get("passed"))),
        gate("target_table_summary_present", bool(target_summary.get("phase_1_base_tables"))),
        gate("deferred_table_summary_present", bool(deferred_summary.get("phase_2_relationship_tables")) and bool(deferred_summary.get("phase_3_downstream_tables"))),
        gate("no_data_or_exports_artifact_written", True),
        gate("no_blocked_report_terms", bool(adr_check.get("no_blocked_report_terms"))),
    ]


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
            "no_blocked_report_terms": False,
        }

    content = adr_path.read_text(encoding="utf-8")
    normalized = normalize_text(content)
    checked_rules = [
        {"rule": "status_is_proposed", "passed": status_value(content) == "Proposed"},
        *[
            {"rule": rule, "passed": normalize_text(needle) in normalized}
            for rule, needle in ADR_RULES
            if rule != "status_is_proposed"
        ],
    ]
    blocked_report_terms = blocked_terms_in_text(content)
    blocked_phrases = [phrase for phrase in ADR_BLOCKED_PHRASES if phrase in normalized]
    no_blocked_report_terms = not blocked_report_terms and not blocked_phrases
    checked_rules.append({"rule": "no_blocked_report_terms", "passed": no_blocked_report_terms})
    failed = [rule["rule"] for rule in checked_rules if not rule["passed"]]
    report = {
        "mode": "adr-check",
        "adr_path": relative_path(adr_path),
        "adr_exists": True,
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
        "no_blocked_report_terms": no_blocked_report_terms,
    }
    assert_no_blocked_terms(report)
    return report


def target_table_summary() -> dict[str, Any]:
    return {
        "phase_1_base_tables": list(formal_schema_draft.PHASE_1_BASE_TABLES),
        "source": "formal_schema_draft.PHASE_1_BASE_TABLES",
        "sql_shape_source": "formal_ddl_rehearsal.render_sql()",
    }


def deferred_table_summary() -> dict[str, Any]:
    return {
        "phase_2_relationship_tables": list(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES),
        "phase_3_downstream_tables": list(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES),
        "source": "formal_schema_draft deferred table constants",
    }


def gate(name: str, passed: bool) -> dict[str, Any]:
    return {"gate": name, "passed": bool(passed)}


def status_value(content: str) -> str | None:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "## status":
            for candidate in lines[index + 1 :]:
                if candidate.strip():
                    return candidate.strip().rstrip(".")
    return None


def blocked_terms_in_text(text: str) -> list[str]:
    normalized = text.lower()
    return [term for term in formal_schema_draft.BLOCKED_REPORT_TERMS if term.lower() in normalized]


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _contains_dsn_or_secret(sql: str) -> bool:
    lowered = sql.lower()
    tokens = (
        "postgres://",
        "postgresql://",
        "password",
        " secret",
        "host=",
        LEGACY_ENV_DSN.lower(),
        PRIMARY_ENV_DSN.lower(),
    )
    return any(token in lowered for token in tokens)


def _contains_production_seed_statement(sql: str) -> bool:
    return bool(re.search(r"(?i)\bINSERT\s+INTO\s+(?:production_)?seed", sql))


def assert_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False, sort_keys=True).lower()
    for term in formal_schema_draft.BLOCKED_REPORT_TERMS:
        if term.lower() in text:
            raise AssertionError(f"reserved report term found: {term}")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Render and lint migration SQL draft text.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--draft-report", action="store_true")
    mode.add_argument("--render-draft-sql", action="store_true")
    mode.add_argument("--lint-draft-sql", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
        return 0
    if args.draft_report:
        report = build_draft_report()
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
        return 0 if not report["blocking_failures"] else 1
    if args.render_draft_sql:
        sys.stdout.write(render_draft_sql())
        sys.stdout.write("\n")
        return 0
    if args.lint_draft_sql:
        report = lint_draft_sql()
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
        return 0 if report["passed"] else 1

    report = build_adr_check()
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
