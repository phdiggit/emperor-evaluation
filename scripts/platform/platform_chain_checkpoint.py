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
    "current_phase": "platform-schema-live-data-not-cutover",
    "canonical_write_source": "jsonl",
    "postgres_schema_live": True,
    "postgres_business_data_migrated": False,
    "sqlite_build_operational": True,
    "full_pytest_operational": True,
    "jsonl_write_frozen": False,
    "postgres_unique_write_source": False,
    "production_runtime_live": False,
    "formal_scoring_released": False,
    "formal_ranking_released": False,
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
                "boundary": "offline_g1_manifest_candidate_only",
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
            "no_target_business_table_writes",
            "no_downstream_business_conclusions",
            "offline_contracts_do_not_read_dotenv_or_dsn",
            "apply_smoke_uses_primary_dsn_only_when_opted_in",
            "apply_smoke_uses_random_isolated_schema_and_drop_cleanup",
        ],
        "next_epic_gates": [
            "epic_1_g1_canonical_manifest_approval",
            "epic_1_target_importer_parser_resolver",
            "epic_1_write_source_cutover_decision",
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
