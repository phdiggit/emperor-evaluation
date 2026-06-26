from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


CHECKPOINT_VERSION = "platform-chain-checkpoint-v1"
CURRENT_STATE = {
    "current_phase": "g5-runtime-executed-observed",
    "canonical_write_source": "postgresql",
    "postgres_schema_live": True,
    "postgres_business_data_migrated": False,
    "sqlite_build_operational": True,
    "full_pytest_operational": True,
    "jsonl_write_frozen": True,
    "postgres_unique_write_source": True,
    "production_runtime_live": True,
    "formal_evidence_released": False,
    "formal_scoring_released": False,
    "formal_ranking_released": False,
    "g1_canonical_manifest_approved": True,
    "g2_mapping_approved": True,
    "staging_diff_verification_ready": True,
    "g3_first_business_write_approved": True,
    "first_business_write_execution_package_ready": True,
    "first_business_write_executed": True,
    "g3_execution_plan_sha256": "1138f4f0ef95e20e0026185f6530ad4671dc61aba13be330a466b20890ae315d",
    "g3_execute_status": "succeeded",
    "g3_observe_status": "succeeded",
    "g3_src_hosts_rows_written": 1,
    "g3_src_hosts_zh_wikisource_observed": True,
    "g4_write_source_cutover_approved": True,
    "write_source_cutover_execution_package_ready": True,
    "g4_cutover_package_pr": 297,
    "g4_cutover_package_merge_commit": "e752c0f3f9a62bb03cc6853e7720b4c64139dffa",
    "g4_cutover_plan_sha256": "32d02b0d9ac77a7876fa503fb261f052a22bffe84dead3af865af23fe4806a4a",
    "g4_cutover_execute_attempted": True,
    "g4_cutover_execute_status": "succeeded",
    "g4_cutover_failure_stage": None,
    "g4_cutover_blocking_failures": [],
    "g4_cutover_observe_status": "succeeded",
    "g4_cutover_post_apply_observation_completed": True,
    "g4_cutover_operator_dsn_read": True,
    "g4_imports_cutover_marker_written": True,
    "g4_imports_cutover_marker_observed": True,
    "write_source_cutover_executed": True,
    "epic_1_g1_to_g4_complete": True,
    "g5_runtime_boundary_package_ready": True,
    "g5_approved": True,
    "g5_runtime_execution_package_ready": True,
    "g5_runtime_execution_plan_sha256": "590b083e27e8d6f9b93c3742936ef043e17262abc041a0132d4bcf5364d0edbd",
    "g5_runtime_marker_code": "G5-RUNTIME-SMOKE-ISSUE292",
    "g5_runtime_execute_attempted": True,
    "g5_runtime_execute_status": "succeeded",
    "g5_runtime_observe_status": "succeeded",
    "g5_runtime_post_apply_observation_completed": True,
    "g5_runtime_marker_written": True,
    "g5_runtime_marker_observed": True,
    "g5_postgres_runtime_smoke_passed": True,
    "g5_rabbitmq_smoke_passed": True,
    "g5_outbox_worker_smoke_passed": True,
    "g5_network_ingestion_pilot_passed": True,
    "production_credentials_enabled": True,
    "rabbitmq_live": True,
    "network_ingestion_live": True,
    "epic_2_entered": False,
}
COMPLETED_CHAIN = [
    "canonical_jsonl",
    "import_rows_dry_run",
    "jsonl_target_mapping_contract",
    "stg_jsonl_rows_mapper",
    "unknown_field_triage",
    "staging_resolver_contract",
    "query_search_target_mapper_prototype",
    "sources_target_mapper_prototype",
    "evidence_cards_target_mapper_prototype",
    "evidence_clusters_resolver_preparation",
    "anchors_schema_proposal",
    "anchors_resolver_contract",
    "anchors_target_mapper_prototype",
    "production_schema_live_apply",
    "production_seed_manifest_import_audit_scaffold",
    "canonical_manifest_candidate_gate",
    "jsonl_postgres_mapping_approval_package",
    "jsonl_staging_diff_verification",
    "g3_postgres_business_write_execution_package",
    "g4_write_source_cutover_execution_package",
    "g5_runtime_boundary_package",
    "g5_runtime_execution_package",
    "g5_runtime_execution_observation",
]
CONTRACT_ONLY_TOOLS = [
    "jsonl_unknown_field_triage",
    "jsonl_staging_resolver_contract",
    "anchors_schema_proposal",
    "anchors_resolver_contract",
]
APPLY_CAPABLE_TOOLS = [
    "jsonl_query_search_target_mapper",
    "jsonl_sources_target_mapper",
    "jsonl_evidence_cards_target_mapper",
    "jsonl_evidence_clusters_resolver",
    "jsonl_anchors_target_mapper",
]


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "checkpoint_version": CHECKPOINT_VERSION,
        "current_state": dict(CURRENT_STATE),
        "completed_chain": list(COMPLETED_CHAIN),
        "prototype_tools": [
            {
                "name": "canonical_manifest_gate",
                "path": "scripts/platform/canonical_manifest_gate.py",
                "contract": True,
                "apply": False,
                "boundary": "offline_g1_manifest_candidate_approved",
            },
            {
                "name": "jsonl_postgres_mapping_approval_package",
                "path": "scripts/platform/jsonl_postgres_mapping_approval_package.py",
                "contract": True,
                "apply": False,
                "boundary": "offline_g2_mapping_approval_package_only",
            },
            {
                "name": "jsonl_staging_diff_verification",
                "path": "scripts/platform/jsonl_staging_diff_verification.py",
                "contract": True,
                "apply": False,
                "boundary": "offline_1c_staging_dry_run_diff_verification",
            },
            {
                "name": "g3_postgres_business_write_execution",
                "path": "scripts/platform/g3_postgres_business_write_execution.py",
                "contract": True,
                "apply": True,
                "boundary": "g3_token_gated_src_hosts_only_write_package",
            },
            {
                "name": "g4_write_source_cutover_execution",
                "path": "scripts/platform/g4_write_source_cutover_execution.py",
                "contract": True,
                "apply": True,
                "boundary": "g4_token_gated_imports_marker_cutover_package",
            },
            {
                "name": "g5_runtime_boundary_package",
                "path": "scripts/platform/g5_runtime_boundary_package.py",
                "contract": True,
                "apply": False,
                "boundary": "offline_g5_preapproval_runtime_credentials_network_boundary_only",
            },
            {
                "name": "g5_runtime_execution",
                "path": "scripts/platform/g5_runtime_execution.py",
                "contract": True,
                "apply": True,
                "boundary": "g5_token_gated_runtime_credentials_rabbitmq_network_smoke_package",
            },
            {
                "name": "jsonl_staging_mapper",
                "path": "scripts/platform/jsonl_staging_mapper.py",
                "contract": True,
                "apply": True,
                "boundary": "isolated_staging_schema",
            },
            {
                "name": "jsonl_query_search_target_mapper",
                "path": "scripts/platform/jsonl_query_search_target_mapper.py",
                "contract": True,
                "apply": True,
                "boundary": "isolated_relaxed_target_schema",
            },
            {
                "name": "jsonl_sources_target_mapper",
                "path": "scripts/platform/jsonl_sources_target_mapper.py",
                "contract": True,
                "apply": True,
                "boundary": "isolated_relaxed_target_schema",
            },
            {
                "name": "jsonl_evidence_cards_target_mapper",
                "path": "scripts/platform/jsonl_evidence_cards_target_mapper.py",
                "contract": True,
                "apply": True,
                "boundary": "isolated_relaxed_target_schema",
            },
            {
                "name": "jsonl_evidence_clusters_resolver",
                "path": "scripts/platform/jsonl_evidence_clusters_resolver.py",
                "contract": True,
                "apply": True,
                "boundary": "isolated_relaxed_target_schema",
            },
            {
                "name": "jsonl_anchors_target_mapper",
                "path": "scripts/platform/jsonl_anchors_target_mapper.py",
                "contract": True,
                "apply": True,
                "boundary": "isolated_relaxed_target_schema",
            },
        ],
        "contract_only_tools": list(CONTRACT_ONLY_TOOLS),
        "apply_capable_tools": list(APPLY_CAPABLE_TOOLS),
        "strict_boundaries": [
            "no_canonical_jsonl_writes",
            "no_formal_schema_writes",
            "no_additional_target_business_table_writes_beyond_g3_src_hosts",
            "no_downstream_business_conclusions",
            "offline_contracts_do_not_read_dotenv_or_dsn",
            "apply_smoke_uses_primary_dsn_only_when_opted_in",
            "apply_smoke_uses_random_isolated_schema_and_drop_cleanup",
        ],
        "next_epic_gates": [
            "epic_1_g6_formal_evidence_release_gate",
            "epic_1_source_document_passage_merge_policy_gate",
            "epic_1_evidence_cluster_anchor_relationship_followup_gates",
        ],
        "baseline_repair_tracking": {
            "sqlite_build_operational": True,
            "full_pytest_operational": True,
            "sqlite_build_command": "python scripts/build/build_db.py",
            "full_pytest_command": "pytest -q",
            "sqlite_schema_source": "db/sqlite/001_cache.sql",
            "postgres_schema_boundary": "db/schema.sql remains PostgreSQL-oriented and is not executed by SQLite build",
        },
        "deprecated_route_markers": [
            "do_not_use_fixed_future_pr_numbers_for_architecture_route",
            "seed_data_apply_success_deferred_until_business_target_writes_exist",
        ],
        "known_ci_history": [
            {
                "symptom": "unified_validation_failed_before_focused_tests",
                "root_cause": "workflow_installed_pytest_without_requirements",
                "fix": "install_requirements_before_validate_all",
            }
        ],
        "limitations": [
            "checkpoint_is_status_only",
            "does_not_read_dotenv",
            "does_not_connect_to_database",
            "does_not_read_batch_or_archive_inputs",
            "does_not_generate_business_conclusions",
        ],
    }


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Report the current platform task-chain checkpoint.")
    parser.add_argument("--contract-report", action="store_true", help="print the platform checkpoint report")
    parser.parse_args(argv)

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
