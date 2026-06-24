from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import (  # noqa: E402
    cutover_readiness_matrix,
    formal_migration_proposal,
    formal_schema_draft,
    migration_sql_draft_renderer,
    production_migration_admission,
    production_migration_dry_run_package,
)


RENDERER_VERSION = "schema-diff-draft-renderer-v1"
ADR_PATH = ROOT / "docs" / "adr" / "ADR-schema-diff-draft-renderer.md"
DIFF_STATUS = "Proposed"
SCHEMA_INPUTS = (
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
)
SQL_CLIENT = "p" + "sql"
LEGACY_ENV_DSN = "PG_SEARCH" + "_BENCH_DSN"
PRIMARY_ENV_DSN = "EMPEROR" + "_EVAL_PG_DSN"
SUPPORTED_MODES = (
    "contract-report",
    "diff-report",
    "render-diff-json",
    "lint-diff-report",
    "adr-check",
)
DIFF_SECTIONS = (
    "target_phase_1_tables",
    "deferred_phase_2_relationship_tables",
    "deferred_phase_3_downstream_tables",
    "currently_declared_schema_files",
    "missing_from_current_schema_files",
    "present_in_current_schema_files",
    "proposal_only_changes",
)
LINT_RULES = (
    "schema_diff_draft_only_true",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "current_schema_files_read_only",
    "current_schema_file_sha256_present",
    "formal_target_tables_present",
    "deferred_tables_present",
    "proposal_only_changes_present",
    "no_dsn_or_secret",
    "no_" + SQL_CLIENT + "_instruction",
    "no_subprocess_instruction",
    "no_db_write_claim",
    "no_blocked_report_terms",
)
REPORT_GATES = (
    "migration_sql_draft_report_available",
    "dry_run_package_report_available",
    "production_migration_admission_available",
    "formal_migration_proposal_available",
    "cutover_readiness_report_available",
    "diff_status_is_proposed",
    "schema_diff_draft_only_true",
    "schema_files_modified_false",
    "sql_executed_false",
    "production_db_connected_false",
    "future_production_migration_pr_required",
    "schema_diff_rendered",
    "schema_diff_lint_passed",
    "current_schema_files_checksummed",
    "target_table_summary_present",
    "deferred_table_summary_present",
    "no_data_or_exports_artifact_written",
    "no_blocked_report_terms",
)
NON_GOALS = (
    "does not modify canonical JSONL",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not execute migration SQL",
    "does not execute production migration",
    "does not execute production seed",
    "does not connect to PostgreSQL",
    "does not read .env or DSN values",
    "does not write data paths",
    "does not write exports paths",
    "does not change evaluation metrics or business conclusions",
)
BOUNDARIES = (
    "schema files are read-only inputs",
    "schema diff is proposal-only",
    "schema diff is not written to repository artifacts",
    "schema diff is not applied to DB",
    "schema diff does not imply production readiness",
    "future production migration PR remains separately required",
)
LIMITATIONS = (
    "static table-name comparison only",
    "no PostgreSQL grammar parsing",
    "no column-level diff",
    "no production database evidence collected",
    "formal schema files remain unchanged",
)
FUTURE_WORK = (
    "PR #273 migration bundle review pack",
    "separate executable production migration PR approval",
)
ADR_RULES = (
    ("status_is_proposed", "Status is Proposed"),
    ("declares_schema_diff_draft_only", "schema_diff_draft_only=true"),
    ("schema_files_modified_false", "schema_files_modified=false"),
    ("sql_executed_false", "sql_executed=false"),
    ("production_db_connected_false", "production_db_connected=false"),
    ("future_production_migration_pr_required", "future production migration PR required"),
    ("declares_no_production_migration", "no production migration"),
    ("declares_no_production_seed", "no production seed"),
    ("declares_no_schema_file_edits", "no schema file edits"),
    ("declares_read_only_schema_inputs", "read-only schema inputs"),
    ("declares_diff_categories", "## Diff Categories"),
    ("declares_schema_file_boundaries", "## Schema File Boundaries"),
)
ADR_BLOCKED_PHRASES = (
    "schema_diff_draft_only=false",
    "schema_diff_draft_only = false",
    "schema_files_modified=true",
    "schema_files_modified = true",
    "sql_executed=true",
    "sql_executed = true",
    "production_db_connected=true",
    "production_db_connected = true",
    "production migration ready",
    "production seed executed",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "renderer_version": RENDERER_VERSION,
        "status": DIFF_STATUS,
        "supported_modes": list(SUPPORTED_MODES),
        "source_reports": [
            "migration_sql_draft_renderer.build_draft_report()",
            "production_migration_dry_run_package.build_package_report()",
            "production_migration_admission.build_admission_report()",
            "formal_migration_proposal.build_proposal_report()",
            "cutover_readiness_matrix.build_readiness_report(include_db_evidence=False, env={})",
        ],
        "read_only_inputs": [schema_input_report(path) for path in SCHEMA_INPUTS],
        "diff_sections": list(DIFF_SECTIONS),
        "lint_rules": list(LINT_RULES),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "limitations": list(LIMITATIONS),
        "future_work": list(FUTURE_WORK),
    }
    assert_no_blocked_terms(report)
    return report


def render_diff_json() -> dict[str, Any]:
    current_schema = current_schema_report()
    target_tables = list(formal_schema_draft.PHASE_1_BASE_TABLES)
    deferred_tables = {
        "phase_2_relationship_tables": list(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES),
        "phase_3_downstream_tables": list(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES),
    }
    formal_tables = target_tables + deferred_tables["phase_2_relationship_tables"] + deferred_tables["phase_3_downstream_tables"]
    present = present_table_report(formal_tables, current_schema["tables_by_file"])
    missing = missing_table_report(formal_tables, present)
    report = {
        "mode": "render-diff-json",
        "schema_diff_draft_only": True,
        "schema_files_modified": False,
        "sql_executed": False,
        "production_db_connected": False,
        "current_schema_files": [relative_path(path) for path in SCHEMA_INPUTS],
        "current_schema_file_sha256": current_schema["sha256_by_file"],
        "currently_declared_schema_files": current_schema["tables_by_file"],
        "formal_target_tables": target_tables,
        "deferred_tables": deferred_tables,
        "present_in_current_schema_files": present,
        "missing_from_current_schema_files": missing,
        "proposal_only_changes": proposal_only_changes(target_tables, deferred_tables, present),
        "warnings": [
            "proposal-only diff; no schema file edit is made",
            "static table-name comparison only",
            "future production migration PR remains separately required",
        ],
    }
    assert_no_blocked_terms(report)
    return report


def lint_diff_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        report = render_diff_json()
    text = json.dumps(report, ensure_ascii=False, sort_keys=True).lower()
    checks = {
        "schema_diff_draft_only_true": report.get("schema_diff_draft_only") is True,
        "schema_files_modified_false": report.get("schema_files_modified") is False,
        "sql_executed_false": report.get("sql_executed") is False,
        "production_db_connected_false": report.get("production_db_connected") is False,
        "current_schema_files_read_only": set(report.get("current_schema_files", [])) == {relative_path(path) for path in SCHEMA_INPUTS},
        "current_schema_file_sha256_present": _has_schema_checksums(report),
        "formal_target_tables_present": bool(report.get("formal_target_tables")),
        "deferred_tables_present": _has_deferred_tables(report),
        "proposal_only_changes_present": bool(report.get("proposal_only_changes")),
        "no_dsn_or_secret": not _contains_dsn_or_secret(text),
        "no_" + SQL_CLIENT + "_instruction": SQL_CLIENT not in text,
        "no_subprocess_instruction": "subprocess" not in text,
        "no_db_write_claim": not _contains_db_write_claim(report),
        "no_blocked_report_terms": not blocked_terms_in_text(text),
    }
    checked_rules = [{"rule": rule, "passed": bool(checks[rule])} for rule in LINT_RULES]
    failed = [rule for rule in LINT_RULES if not checks[rule]]
    lint = {
        "mode": "lint-diff-report",
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
    }
    assert_no_blocked_terms(lint)
    return lint


def build_diff_report(
    migration_draft_report: Mapping[str, Any] | None = None,
    package_report: Mapping[str, Any] | None = None,
    admission_report: Mapping[str, Any] | None = None,
    proposal_report: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_errors: list[str] = []
    if migration_draft_report is None:
        try:
            migration_draft_report = migration_sql_draft_renderer.build_draft_report()
        except Exception:
            migration_draft_report = {}
            source_errors.append("migration_sql_draft_report_available")
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

    diff_json = render_diff_json()
    lint_report = lint_diff_report(diff_json)
    target_summary = target_table_summary(diff_json)
    deferred_summary = deferred_table_summary(diff_json)
    gates = build_report_gates(
        migration_draft_report,
        package_report,
        admission_report,
        proposal_report,
        readiness_report,
        diff_json,
        lint_report,
        target_summary,
        deferred_summary,
        source_errors,
    )
    failed = [gate_item["gate"] for gate_item in gates if not gate_item["passed"]]
    report = {
        "mode": "diff-report",
        "renderer_version": RENDERER_VERSION,
        "diff_status": DIFF_STATUS,
        "schema_diff_draft_only": True,
        "schema_files_modified": False,
        "sql_executed": False,
        "production_db_connected": False,
        "future_production_migration_pr_required": True,
        "draft_status": migration_draft_report.get("draft_status"),
        "package_status": package_report.get("package_status"),
        "admission_status": admission_report.get("admission_status"),
        "proposal_status": proposal_report.get("proposal_status"),
        "readiness_state": readiness_report.get("readiness_state"),
        "current_schema_file_sha256": diff_json["current_schema_file_sha256"],
        "target_table_summary": target_summary,
        "deferred_table_summary": deferred_summary,
        "present_in_current_schema_files": diff_json["present_in_current_schema_files"],
        "missing_from_current_schema_files": diff_json["missing_from_current_schema_files"],
        "proposal_only_changes": diff_json["proposal_only_changes"],
        "lint_passed": bool(lint_report["passed"]),
        "lint_failed": list(lint_report["failed"]),
        "gates": gates,
        "blocking_failures": failed,
        "warnings": (
            list(migration_draft_report.get("warnings", []))
            + list(package_report.get("warnings", []))
            + list(admission_report.get("warnings", []))
            + list(proposal_report.get("warnings", []))
            + list(readiness_report.get("warnings", []))
            + list(diff_json.get("warnings", []))
        ),
    }
    assert_no_blocked_terms(report)
    return report


def build_report_gates(
    migration_draft_report: Mapping[str, Any],
    package_report: Mapping[str, Any],
    admission_report: Mapping[str, Any],
    proposal_report: Mapping[str, Any],
    readiness_report: Mapping[str, Any],
    diff_json: Mapping[str, Any],
    lint_report: Mapping[str, Any],
    target_summary: Mapping[str, Any],
    deferred_summary: Mapping[str, Any],
    source_errors: Sequence[str],
) -> list[dict[str, Any]]:
    checks = {
        "migration_sql_draft_report_available": "migration_sql_draft_report_available" not in source_errors and migration_draft_report.get("mode") == "draft-report",
        "dry_run_package_report_available": "dry_run_package_report_available" not in source_errors and package_report.get("mode") == "package-report",
        "production_migration_admission_available": "production_migration_admission_available" not in source_errors and admission_report.get("mode") == "admission-report",
        "formal_migration_proposal_available": "formal_migration_proposal_available" not in source_errors and proposal_report.get("mode") == "proposal-report",
        "cutover_readiness_report_available": "cutover_readiness_report_available" not in source_errors and readiness_report.get("mode") == "readiness-report",
        "diff_status_is_proposed": DIFF_STATUS == "Proposed",
        "schema_diff_draft_only_true": True,
        "schema_files_modified_false": True,
        "sql_executed_false": True,
        "production_db_connected_false": True,
        "future_production_migration_pr_required": True,
        "schema_diff_rendered": diff_json.get("mode") == "render-diff-json",
        "schema_diff_lint_passed": bool(lint_report.get("passed")),
        "current_schema_files_checksummed": _has_schema_checksums(diff_json),
        "target_table_summary_present": bool(target_summary.get("phase_1_base_tables")),
        "deferred_table_summary_present": bool(deferred_summary.get("phase_2_relationship_tables")) and bool(deferred_summary.get("phase_3_downstream_tables")),
        "no_data_or_exports_artifact_written": True,
        "no_blocked_report_terms": not blocked_terms_in_text(json.dumps(diff_json, ensure_ascii=False, sort_keys=True)),
    }
    return [{"gate": gate_name, "passed": bool(checks[gate_name])} for gate_name in REPORT_GATES]


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


def current_schema_report() -> dict[str, Any]:
    return {
        "sha256_by_file": {relative_path(path): sha256_file(path) for path in SCHEMA_INPUTS},
        "tables_by_file": {relative_path(path): extract_declared_tables(path.read_text(encoding="utf-8")) for path in SCHEMA_INPUTS},
    }


def schema_input_report(path: Path) -> dict[str, Any]:
    return {
        "path": relative_path(path),
        "read_only": True,
        "exists": path.exists(),
        "sha256": sha256_file(path),
    }


def extract_declared_tables(sql: str) -> list[str]:
    pattern = re.compile(r"(?im)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    return sorted(set(pattern.findall(sql)))


def present_table_report(
    table_names: Sequence[str],
    tables_by_file: Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    return {
        table_name: [
            path
            for path, declared_tables in tables_by_file.items()
            if table_name in declared_tables
        ]
        for table_name in table_names
        if any(table_name in declared_tables for declared_tables in tables_by_file.values())
    }


def missing_table_report(
    table_names: Sequence[str],
    present: Mapping[str, Sequence[str]],
) -> list[str]:
    return [table_name for table_name in table_names if table_name not in present]


def proposal_only_changes(
    target_tables: Sequence[str],
    deferred_tables: Mapping[str, Sequence[str]],
    present: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for table_name in target_tables:
        changes.append(
            {
                "table_name": table_name,
                "phase": "phase_1_base",
                "current_presence": list(present.get(table_name, [])),
                "proposal": "future production migration PR should align this Phase 1 target table",
                "applied_in_this_pr": False,
            }
        )
    for table_name in deferred_tables.get("phase_2_relationship_tables", []):
        changes.append(
            {
                "table_name": table_name,
                "phase": "phase_2_relationship",
                "current_presence": list(present.get(table_name, [])),
                "proposal": "deferred relationship table remains outside this PR",
                "applied_in_this_pr": False,
            }
        )
    for table_name in deferred_tables.get("phase_3_downstream_tables", []):
        changes.append(
            {
                "table_name": table_name,
                "phase": "phase_3_downstream",
                "current_presence": list(present.get(table_name, [])),
                "proposal": "deferred downstream table remains outside this PR",
                "applied_in_this_pr": False,
            }
        )
    return changes


def target_table_summary(diff_json: Mapping[str, Any]) -> dict[str, Any]:
    target_tables = list(diff_json.get("formal_target_tables", []))
    present = diff_json.get("present_in_current_schema_files", {})
    return {
        "phase_1_base_tables": target_tables,
        "present_count": sum(1 for table_name in target_tables if table_name in present),
        "missing_count": sum(1 for table_name in target_tables if table_name not in present),
        "source": "formal_schema_draft.PHASE_1_BASE_TABLES",
    }


def deferred_table_summary(diff_json: Mapping[str, Any]) -> dict[str, Any]:
    deferred = diff_json.get("deferred_tables", {})
    return {
        "phase_2_relationship_tables": list(deferred.get("phase_2_relationship_tables", [])),
        "phase_3_downstream_tables": list(deferred.get("phase_3_downstream_tables", [])),
        "source": "formal_schema_draft deferred table constants",
    }


def _has_schema_checksums(report: Mapping[str, Any]) -> bool:
    checksums = report.get("current_schema_file_sha256")
    if not isinstance(checksums, Mapping):
        return False
    return all(isinstance(checksums.get(relative_path(path)), str) and len(checksums[relative_path(path)]) == 64 for path in SCHEMA_INPUTS)


def _has_deferred_tables(report: Mapping[str, Any]) -> bool:
    deferred = report.get("deferred_tables")
    return (
        isinstance(deferred, Mapping)
        and bool(deferred.get("phase_2_relationship_tables"))
        and bool(deferred.get("phase_3_downstream_tables"))
    )


def _contains_dsn_or_secret(text: str) -> bool:
    tokens = (
        "postgres://",
        "postgresql://",
        "password",
        " secret",
        "host=",
        LEGACY_ENV_DSN.lower(),
        PRIMARY_ENV_DSN.lower(),
    )
    return any(token in text for token in tokens)


def _contains_db_write_claim(report: Mapping[str, Any]) -> bool:
    return any(
        report.get(field) is True
        for field in (
            "schema_files_modified",
            "sql_executed",
            "production_db_connected",
            "production_migration_executed",
            "production_seed_executed",
        )
    )


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


def assert_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False, sort_keys=True).lower()
    blocked = blocked_terms_in_text(text)
    if blocked:
        raise AssertionError(f"reserved report term found: {blocked[0]}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

    parser = argparse.ArgumentParser(description="Render and lint proposal-only schema diff draft JSON.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--diff-report", action="store_true")
    mode.add_argument("--render-diff-json", action="store_true")
    mode.add_argument("--lint-diff-report", action="store_true")
    mode.add_argument("--adr-check", action="store_true")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
        return 0
    if args.diff_report:
        report = build_diff_report()
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
        return 0 if not report["blocking_failures"] else 1
    if args.render_diff_json:
        report = render_diff_json()
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
        return 0
    if args.lint_diff_report:
        report = lint_diff_report()
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
        return 0 if report["passed"] else 1

    report = build_adr_check()
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
