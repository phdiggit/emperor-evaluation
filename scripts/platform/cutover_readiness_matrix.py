from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import (  # noqa: E402
    formal_ddl_live_rehearsal,
    formal_ddl_rehearsal,
    formal_schema_draft,
    isolated_seed_dry_apply,
    isolated_seed_rollback_restore,
    seed_artifact_db_preflight,
    seed_artifact_plan,
    seed_artifact_renderer,
    seed_artifact_validation_matrix,
)
from scripts.platform.core.db_env import (  # noqa: E402
    is_psycopg_available,
    primary_env_check_report,
)


MATRIX_VERSION = "cutover-readiness-matrix-v1"
PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
NEXT_STAGE = "formal_migration_proposal_update"
READINESS_DIMENSIONS = (
    "schema_contract",
    "ddl_rehearsal",
    "ddl_live_rehearsal",
    "seed_plan",
    "seed_artifact_renderer",
    "seed_artifact_validation",
    "db_preflight_contract",
    "isolated_seed_dry_apply",
    "rollback_restore_rehearsal",
    "source_of_truth",
    "scope_safety",
    "production_guardrails",
)
REQUIRED_GATES = (
    "formal_schema_draft_contract_available",
    "phase_1_tables_defined",
    "phase_2_3_tables_deferred",
    "ddl_rehearsal_emit_lint_available",
    "live_rehearsal_contract_available",
    "seed_plan_contract_available",
    "seed_artifact_renderable",
    "seed_manifest_hash_consistent",
    "seed_artifact_validation_passed",
    "db_preflight_contract_available",
    "isolated_dry_apply_contract_available",
    "rollback_restore_contract_available",
    "source_of_truth_is_canonical_jsonl",
    "no_production_migration_in_this_pr",
    "no_production_seed_in_this_pr",
    "no_public_schema_write",
    "no_repo_artifact_write",
    "no_data_or_exports_write",
    "no_blocked_report_terms",
)
OPTIONAL_DB_GATES = (
    "db_preflight_live_passed_or_skipped",
    "isolated_dry_apply_live_passed_or_skipped",
    "rollback_restore_live_passed_or_skipped",
)
DECISION_STATES = ("passed", "skipped", "warning", "failed", "not_applicable")
NON_GOALS = (
    "does not modify canonical JSONL",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not read .env",
    "does not write data",
    "does not write exports",
    "does not write repository seed artifacts",
    "does not switch the JSONL write source",
    "does not apply seed artifacts to production targets",
    "does not update formal schema files",
)
BOUNDARIES = (
    "contract-report and check are offline only",
    "readiness-report is offline by default",
    "only EMPEROR_EVAL_PG_DSN is recognized for opt-in database evidence",
    "database evidence requires --readiness-report --include-db-evidence",
    "optional database evidence uses random isolated schemas through prior tools",
    "canonical JSONL remains the source of truth",
    "reports are stdout JSON only",
)
LIMITATIONS = (
    "readiness matrix for the next proposal stage only",
    "optional database evidence is not required for offline stage readiness",
    "formal schema files remain unchanged",
    "production cutover requires a separate approved PR",
)
FUTURE_WORK = (
    "write the matrix result into a migration proposal or cutover ADR",
    "keep formal schema changes in a separately approved PR",
    "keep any production seed action in a separately approved PR",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "matrix_version": MATRIX_VERSION,
        "status": "Proposed",
        "supported_modes": ["contract-report", "check", "readiness-report"],
        "readiness_dimensions": list(READINESS_DIMENSIONS),
        "required_gates": list(REQUIRED_GATES),
        "optional_db_evidence": {
            "enabled_by_default": False,
            "requires_flag": "--include-db-evidence",
            "dsn_env": PRIMARY_ENV_DSN,
            "gates": list(OPTIONAL_DB_GATES),
        },
        "decision_states": list(DECISION_STATES),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "limitations": list(LIMITATIONS),
        "future_work": list(FUTURE_WORK),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def check_environment(
    env: Mapping[str, str] | None = None,
    driver_available: bool | None = None,
) -> dict[str, Any]:
    report = primary_env_check_report(
        env=env,
        driver_available=driver_available,
        extra_fields={
            "will_connect_by_default": False,
            "include_db_evidence_required_for_connection": True,
            "will_write_db": False,
            "will_modify_repo": False,
        },
    )
    assert_report_has_no_blocked_terms(report)
    return report


def build_readiness_report(
    include_db_evidence: bool = False,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    offline = collect_offline_evidence()
    db_evidence = collect_db_evidence(include_db_evidence, env=env)
    gates = build_gates(offline, db_evidence)
    dimensions = build_dimensions(offline, db_evidence, gates)
    decision = evaluate_decision(gates, dimensions, db_evidence)
    report = {
        "mode": "readiness-report",
        "matrix_version": MATRIX_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source_of_truth": "canonical JSONL remains source-of-truth",
        "readiness_state": "passed" if decision["ready_for_next_stage"] else "failed",
        "ready_for_next_stage": decision["ready_for_next_stage"],
        "ready_for_production_migration": False,
        "dimensions": dimensions,
        "gates": gates,
        "evidence_summary": summarize_offline_evidence(offline),
        "db_evidence": db_evidence,
        "decision": decision,
        "failed": [gate["gate"] for gate in gates if gate["required"] and not gate["passed"]],
        "warnings": collect_warnings(dimensions, db_evidence),
        "non_goals": list(NON_GOALS),
        "boundaries": list(BOUNDARIES),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def collect_offline_evidence() -> dict[str, Any]:
    formal_schema_contract = formal_schema_draft.build_contract_report()
    ddl_contract = formal_ddl_rehearsal.build_contract_report()
    ddl_sql = formal_ddl_rehearsal.render_sql()
    ddl_lint = formal_ddl_rehearsal.lint_sql(ddl_sql)
    live_contract = formal_ddl_live_rehearsal.build_contract_report()
    seed_plan_contract = seed_artifact_plan.build_contract_report()
    seed_plan_dry_run = seed_artifact_plan.build_dry_run_report(ROOT)
    renderer_contract = seed_artifact_renderer.build_contract_report()
    artifact = seed_artifact_renderer.build_seed_artifact(ROOT)
    manifest = seed_artifact_renderer.build_seed_manifest(artifact, ROOT)
    try:
        validation = seed_artifact_validation_matrix.validate_artifact_and_manifest(artifact, manifest)
    except Exception as exc:
        validation = {
            "artifact_valid": False,
            "manifest_valid": False,
            "table_gate_valid": False,
            "source_boundary_valid": False,
            "passed": False,
            "failed": [f"{type(exc).__name__}_while_validating_seed_artifact"],
            "checked_rules": [],
        }
    db_preflight_contract = seed_artifact_db_preflight.build_contract_report()
    dry_apply_contract = isolated_seed_dry_apply.build_contract_report()
    rollback_contract = isolated_seed_rollback_restore.build_contract_report()
    evidence = {
        "formal_schema_contract": formal_schema_contract,
        "ddl_contract": ddl_contract,
        "ddl_lint": ddl_lint,
        "live_contract": live_contract,
        "seed_plan_contract": seed_plan_contract,
        "seed_plan_dry_run": seed_plan_dry_run,
        "renderer_contract": renderer_contract,
        "artifact": artifact,
        "manifest": manifest,
        "validation": validation,
        "db_preflight_contract": db_preflight_contract,
        "dry_apply_contract": dry_apply_contract,
        "rollback_contract": rollback_contract,
    }
    assert_report_has_no_blocked_terms(evidence)
    return evidence


def collect_db_evidence(
    include_db_evidence: bool,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if env is None:
        env = os.environ
    if not include_db_evidence:
        return {
            "state": "skipped",
            "reason": "not_requested",
            "required": False,
            "passed": False,
            "reports": {},
            "failed": [],
            "warnings": [],
        }

    dsn_present = bool(env.get(PRIMARY_ENV_DSN))
    driver_available = is_psycopg_available()
    if not dsn_present:
        return {
            "state": "skipped",
            "reason": "no_dsn",
            "required": False,
            "passed": False,
            "dsn_present": False,
            "driver_available": driver_available,
            "reports": {},
            "failed": [],
            "warnings": [f"{PRIMARY_ENV_DSN} is not set"],
        }
    if not driver_available:
        return {
            "state": "skipped",
            "reason": "driver_unavailable",
            "required": False,
            "passed": False,
            "dsn_present": True,
            "driver_available": False,
            "reports": {},
            "failed": [],
            "warnings": ["psycopg is not installed"],
        }

    reports = {
        "db_preflight": seed_artifact_db_preflight.run_preflight(
            seed_artifact_db_preflight.DEFAULT_SCHEMA_PREFIX,
            env=env,
        ),
        "isolated_dry_apply": isolated_seed_dry_apply.run_dry_apply(
            isolated_seed_dry_apply.DEFAULT_SCHEMA_PREFIX,
            env=env,
        ),
        "rollback_restore": isolated_seed_rollback_restore.run_rehearsal(
            isolated_seed_rollback_restore.DEFAULT_SCHEMA_PREFIX,
            env=env,
        ),
    }
    failed = [
        name
        for name, report in reports.items()
        if not bool(report.get("passed"))
    ]
    state = "passed" if not failed else "warning"
    db_evidence = {
        "state": state,
        "reason": "completed" if not failed else "optional_evidence_failed",
        "required": False,
        "passed": not failed,
        "dsn_present": True,
        "driver_available": True,
        "reports": reports,
        "failed": failed,
        "warnings": [f"{name} did not pass" for name in failed],
    }
    assert_report_has_no_blocked_terms(db_evidence)
    return db_evidence


def build_gate(
    name: str,
    passed: bool,
    required: bool,
    reason: str,
    evidence_source: str,
) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "required": bool(required),
        "reason": reason,
        "evidence_source": evidence_source,
    }


def build_dimension(
    name: str,
    state: str,
    required: bool,
    evidence: list[str],
    blocking_failures: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    if state not in DECISION_STATES:
        raise ValueError(f"unknown readiness state: {state}")
    return {
        "name": name,
        "state": state,
        "required": bool(required),
        "evidence": evidence,
        "blocking_failures": list(blocking_failures or []),
        "warnings": list(warnings or []),
    }


def build_gates(offline: Mapping[str, Any], db_evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    artifact = offline["artifact"]
    manifest = offline["manifest"]
    validation = offline["validation"]
    formal_schema_contract = offline["formal_schema_contract"]
    seed_plan_contract = offline["seed_plan_contract"]
    gates = [
        build_gate(
            "formal_schema_draft_contract_available",
            is_contract_report(formal_schema_contract),
            True,
            "formal schema draft contract report is available",
            "formal_schema_draft.build_contract_report",
        ),
        build_gate(
            "phase_1_tables_defined",
            bool(formal_schema_draft.PHASE_1_BASE_TABLES),
            True,
            "phase 1 table set is non-empty",
            "formal_schema_draft.PHASE_1_BASE_TABLES",
        ),
        build_gate(
            "phase_2_3_tables_deferred",
            bool(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES)
            and bool(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES),
            True,
            "phase 2 relationship and phase 3 downstream tables remain deferred",
            "formal_schema_draft table constants",
        ),
        build_gate(
            "ddl_rehearsal_emit_lint_available",
            is_contract_report(offline["ddl_contract"]) and bool(offline["ddl_lint"].get("passed")),
            True,
            "DDL rehearsal contract and lint pass are available",
            "formal_ddl_rehearsal.build_contract_report/render_sql/lint_sql",
        ),
        build_gate(
            "live_rehearsal_contract_available",
            is_contract_report(offline["live_contract"]),
            True,
            "live rehearsal contract report is available",
            "formal_ddl_live_rehearsal.build_contract_report",
        ),
        build_gate(
            "seed_plan_contract_available",
            is_contract_report(seed_plan_contract) and offline["seed_plan_dry_run"].get("writes_performed") is False,
            True,
            "seed plan contract and dry plan are available",
            "seed_artifact_plan.build_contract_report/build_dry_run_report",
        ),
        build_gate(
            "seed_artifact_renderable",
            bool(artifact.get("table_payloads")) and artifact.get("artifact_written_to_repo") is False,
            True,
            "seed artifact renders in memory without repository artifact write",
            "seed_artifact_renderer.build_seed_artifact",
        ),
        build_gate(
            "seed_manifest_hash_consistent",
            validation.get("manifest_valid") is True,
            True,
            "seed manifest hash and counts validate against artifact",
            "seed_artifact_renderer.build_seed_manifest",
        ),
        build_gate(
            "seed_artifact_validation_passed",
            validation.get("passed") is True,
            True,
            "seed artifact validation matrix passed",
            "seed_artifact_validation_matrix.validate_artifact_and_manifest",
        ),
        build_gate(
            "db_preflight_contract_available",
            is_contract_report(offline["db_preflight_contract"]),
            True,
            "DB preflight contract report is available without connection",
            "seed_artifact_db_preflight.build_contract_report",
        ),
        build_gate(
            "isolated_dry_apply_contract_available",
            is_contract_report(offline["dry_apply_contract"]),
            True,
            "isolated seed dry apply contract report is available without connection",
            "isolated_seed_dry_apply.build_contract_report",
        ),
        build_gate(
            "rollback_restore_contract_available",
            is_contract_report(offline["rollback_contract"]),
            True,
            "rollback/restore contract report is available without connection",
            "isolated_seed_rollback_restore.build_contract_report",
        ),
        build_gate(
            "source_of_truth_is_canonical_jsonl",
            source_of_truth_is_canonical_jsonl(artifact)
            and source_of_truth_is_canonical_jsonl(manifest)
            and source_of_truth_is_canonical_jsonl(seed_plan_contract),
            True,
            "canonical JSONL remains the declared source of truth",
            "seed artifact and seed plan reports",
        ),
        build_gate(
            "no_production_migration_in_this_pr",
            True,
            True,
            "matrix does not update formal schema files or run a production cutover",
            "cutover_readiness_matrix guardrail",
        ),
        build_gate(
            "no_production_seed_in_this_pr",
            artifact.get("artifact_applied_to_db") is False,
            True,
            "artifact is not applied to production targets",
            "seed_artifact_renderer.build_seed_artifact",
        ),
        build_gate(
            "no_public_schema_write",
            True,
            True,
            "default matrix report does not write database objects",
            "cutover_readiness_matrix guardrail",
        ),
        build_gate(
            "no_repo_artifact_write",
            artifact.get("artifact_written_to_repo") is False
            and manifest.get("artifact_written_to_repo") is False,
            True,
            "seed artifact and manifest remain in memory/stdout only",
            "seed artifact renderer flags",
        ),
        build_gate(
            "no_data_or_exports_write",
            True,
            True,
            "matrix writes no data or export paths",
            "cutover_readiness_matrix guardrail",
        ),
        build_gate(
            "no_blocked_report_terms",
            True,
            True,
            "reserved report terms are absent",
            "assert_report_has_no_blocked_terms",
        ),
    ]
    if db_evidence.get("state") != "skipped" or db_evidence.get("reason") == "no_dsn":
        db_passed_or_skipped = db_evidence.get("state") in {"passed", "skipped"}
        for name in OPTIONAL_DB_GATES:
            gates.append(
                build_gate(
                    name,
                    db_passed_or_skipped,
                    False,
                    "optional database evidence passed or was explicitly skipped",
                    "collect_db_evidence",
                )
            )
    return gates


def build_dimensions(
    offline: Mapping[str, Any],
    db_evidence: Mapping[str, Any],
    gates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failed_required = {gate["gate"] for gate in gates if gate["required"] and not gate["passed"]}
    db_state = str(db_evidence.get("state", "skipped"))
    return [
        dimension_from_gates("schema_contract", ["formal_schema_draft_contract_available"], failed_required),
        dimension_from_gates(
            "ddl_rehearsal",
            ["ddl_rehearsal_emit_lint_available"],
            failed_required,
            evidence=["formal DDL rehearsal contract and lint"],
        ),
        dimension_from_gates(
            "ddl_live_rehearsal",
            ["live_rehearsal_contract_available"],
            failed_required,
            evidence=["live rehearsal contract only"],
        ),
        dimension_from_gates(
            "seed_plan",
            ["seed_plan_contract_available"],
            failed_required,
            evidence=["seed plan contract and dry plan"],
        ),
        dimension_from_gates(
            "seed_artifact_renderer",
            ["seed_artifact_renderable", "seed_manifest_hash_consistent"],
            failed_required,
            evidence=["in-memory artifact", "in-memory manifest"],
        ),
        dimension_from_gates(
            "seed_artifact_validation",
            ["seed_artifact_validation_passed"],
            failed_required,
            evidence=list(offline["validation"].get("failed", [])) or ["validation matrix passed"],
        ),
        dimension_from_gates(
            "db_preflight_contract",
            ["db_preflight_contract_available"],
            failed_required,
            evidence=["DB preflight contract only"],
        ),
        dimension_from_gates(
            "isolated_seed_dry_apply",
            ["isolated_dry_apply_contract_available"],
            failed_required,
            evidence=["isolated dry apply contract only"],
        ),
        dimension_from_gates(
            "rollback_restore_rehearsal",
            ["rollback_restore_contract_available"],
            failed_required,
            evidence=["rollback/restore contract only"],
        ),
        dimension_from_gates(
            "source_of_truth",
            ["source_of_truth_is_canonical_jsonl"],
            failed_required,
            evidence=["canonical JSONL source boundary"],
        ),
        dimension_from_gates(
            "scope_safety",
            ["no_repo_artifact_write", "no_data_or_exports_write", "no_blocked_report_terms"],
            failed_required,
            evidence=["stdout JSON only", "no data/export writes"],
        ),
        dimension_from_gates(
            "production_guardrails",
            ["no_production_migration_in_this_pr", "no_production_seed_in_this_pr", "no_public_schema_write"],
            failed_required,
            evidence=["separate approval required for production changes"],
            warnings=list(db_evidence.get("warnings", [])) if db_state == "warning" else [],
        ),
    ]


def dimension_from_gates(
    name: str,
    gate_names: Sequence[str],
    failed_required: set[str],
    *,
    evidence: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    failures = [gate for gate in gate_names if gate in failed_required]
    return build_dimension(
        name,
        "failed" if failures else "passed",
        True,
        evidence or list(gate_names),
        blocking_failures=failures,
        warnings=warnings or [],
    )


def evaluate_decision(
    gates: Sequence[Mapping[str, Any]],
    dimensions: Sequence[Mapping[str, Any]],
    db_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    required_gates_passed = all(gate["passed"] for gate in gates if gate["required"])
    blocking_failures = [
        failure
        for dimension in dimensions
        for failure in dimension.get("blocking_failures", [])
    ]
    ready_for_next_stage = required_gates_passed and not blocking_failures
    return {
        "stage": "cutover_readiness_matrix",
        "ready_for_next_stage": ready_for_next_stage,
        "ready_for_production_migration": False,
        "next_stage": NEXT_STAGE,
        "production_migration_false_reasons": [
            "production cutover requires a separate approved PR",
            "formal schema files are not modified here",
            "production seed application is not performed here",
        ],
        "db_evidence_state": db_evidence.get("state", "skipped"),
    }


def summarize_offline_evidence(offline: Mapping[str, Any]) -> dict[str, Any]:
    artifact = offline["artifact"]
    manifest = offline["manifest"]
    validation = offline["validation"]
    return {
        "formal_schema_draft": offline["formal_schema_contract"].get("draft_version"),
        "ddl_rehearsal": offline["ddl_contract"].get("rehearsal_version"),
        "ddl_lint_passed": bool(offline["ddl_lint"].get("passed")),
        "live_rehearsal": offline["live_contract"].get("live_rehearsal_version"),
        "seed_plan": offline["seed_plan_contract"].get("seed_plan_version"),
        "renderer": offline["renderer_contract"].get("renderer_version"),
        "artifact_tables": sorted(artifact.get("table_payloads", {}).keys()),
        "manifest_version": manifest.get("manifest_version"),
        "validation_passed": bool(validation.get("passed")),
        "validation_failed": list(validation.get("failed", [])),
        "db_preflight": offline["db_preflight_contract"].get("preflight_version"),
        "isolated_dry_apply": offline["dry_apply_contract"].get("dry_apply_version"),
        "rollback_restore": offline["rollback_contract"].get("rehearsal_version"),
    }


def collect_warnings(
    dimensions: Sequence[Mapping[str, Any]],
    db_evidence: Mapping[str, Any],
) -> list[str]:
    warnings = [
        warning
        for dimension in dimensions
        for warning in dimension.get("warnings", [])
    ]
    warnings.extend(db_evidence.get("warnings", []))
    return sorted(set(warnings))


def is_contract_report(report: Mapping[str, Any]) -> bool:
    return report.get("mode") == "contract-report" and report.get("status", "Proposed") != "Failed"


def source_of_truth_is_canonical_jsonl(report: Mapping[str, Any]) -> bool:
    text = json.dumps(report.get("source_of_truth", ""), ensure_ascii=False).lower()
    return "canonical jsonl" in text and "source-of-truth" in text


def assert_report_has_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False, sort_keys=True).lower()
    for term in formal_schema_draft.BLOCKED_REPORT_TERMS:
        if term.lower() in text:
            raise AssertionError(f"reserved report term found: {term}")


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build cutover readiness matrix reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--readiness-report", action="store_true")
    parser.add_argument("--include-db-evidence", action="store_true")
    args = parser.parse_args(argv)

    if args.include_db_evidence and not args.readiness_report:
        parser.error("--include-db-evidence requires --readiness-report")

    if args.contract_report:
        report = build_contract_report()
    elif args.check:
        report = check_environment()
    else:
        report = build_readiness_report(include_db_evidence=args.include_db_evidence)
    print(report_as_json(report))
    if report.get("mode") == "readiness-report" and report.get("failed"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
