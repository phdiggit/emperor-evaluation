from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "文档与脚本登记" / "scripts_registry.json"

EXPECTED_I5B_DEV_MODULES = {
    "i5b_chain_runner": {
        "implementation": "scripts/dev/i5b_chain_runner.py",
        "required_tests": ["tests/test_i5b_chain_runner.py"],
    },
    "source_excerpt_pool": {
        "implementation": "scripts/dev/source_excerpt_pool.py",
        "required_tests": ["tests/test_source_excerpt_pool.py"],
    },
    "source_excerpt_pool_package": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/__init__.py",
        "required_tests": ["tests/test_source_excerpt_pool.py"],
    },
    "source_excerpt_pool_common": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/common.py",
        "required_tests": ["tests/test_source_excerpt_pool.py"],
    },
    "source_excerpt_pool_cache": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/cache.py",
        "required_tests": ["tests/test_source_excerpt_pool.py"],
    },
    "source_excerpt_pool_profile": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/profile.py",
        "required_tests": ["tests/test_source_excerpt_pool.py"],
    },
    "source_excerpt_pool_source_pack": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/source_pack.py",
        "required_tests": ["tests/test_source_excerpt_pool.py", "tests/test_i5b_source_pack_audit.py"],
    },
    "source_excerpt_pool_source_pack_fetcher": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/source_pack_fetcher.py",
        "required_tests": ["tests/test_i5b_source_pack_fetcher.py"],
    },
    "source_excerpt_pool_wikisource": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/wikisource.py",
        "required_tests": ["tests/test_source_excerpt_pool.py"],
    },
    "source_excerpt_pool_builder": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/builder.py",
        "required_tests": ["tests/test_source_excerpt_pool.py"],
    },
    "source_excerpt_pool_reporting": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/reporting.py",
        "required_tests": ["tests/test_source_excerpt_pool.py"],
    },
    "source_excerpt_pool_cli": {
        "implementation": "scripts/dev/source_excerpt_pool_lib/cli.py",
        "required_tests": ["tests/test_source_excerpt_pool.py"],
    },
    "object_pool_importer": {
        "implementation": "scripts/dev/object_pool_importer.py",
        "required_tests": ["tests/test_object_pool_importer.py"],
    },
    "object_pool_aliases": {
        "implementation": "scripts/dev/object_pool_aliases.py",
        "required_tests": ["tests/test_object_pool_importer.py"],
    },
    "i5b_object_pool_detail": {
        "implementation": "scripts/dev/i5b_object_pool_detail.py",
        "required_tests": ["tests/test_i5b_object_pool_detail.py"],
    },
    "i5b_object_pool_integrity_audit": {
        "implementation": "scripts/dev/i5b_object_pool_integrity_audit.py",
        "required_tests": ["tests/test_i5b_object_pool_integrity_audit.py"],
    },
    "i5b_object_pool_integrity_common": {
        "implementation": "scripts/dev/i5b_object_pool_integrity_common.py",
        "required_tests": ["tests/test_i5b_object_pool_integrity_audit.py"],
    },
    "i5b_object_pool_integrity_core": {
        "implementation": "scripts/dev/i5b_object_pool_integrity_core.py",
        "required_tests": ["tests/test_i5b_object_pool_integrity_audit.py"],
    },
    "i5b_object_pool_integrity_shadow": {
        "implementation": "scripts/dev/i5b_object_pool_integrity_shadow.py",
        "required_tests": ["tests/test_i5b_object_pool_integrity_audit.py"],
    },
    "evidence_cluster_workbench": {
        "implementation": "scripts/dev/evidence_cluster_workbench.py",
        "required_tests": ["tests/test_evidence_cluster_workbench.py"],
    },
    "i5b_calc_breakdown": {
        "implementation": "scripts/dev/i5b_calc_breakdown.py",
        "required_tests": ["tests/test_i5b_calc_breakdown.py"],
    },
    "i5b_factor_consistency_audit": {
        "implementation": "scripts/dev/i5b_factor_consistency_audit.py",
        "required_tests": ["tests/test_i5b_factor_consistency_audit.py"],
    },
    "i5b_factor_table_sync": {
        "implementation": "scripts/dev/i5b_factor_table_sync.py",
        "required_tests": ["tests/test_i5b_factor_table_sync.py"],
    },
    "scoring_rule_table_sync": {
        "implementation": "scripts/dev/scoring_rule_table_sync.py",
        "required_tests": ["tests/test_scoring_rule_table_sync.py"],
    },
    "rule_material_policy": {
        "implementation": "scripts/dev/rule_material_policy.py",
        "required_tests": ["tests/test_rule_material_policy.py", "tests/test_rule_material_policy_schema.py"],
    },
    "i5b_health_check": {
        "implementation": "scripts/dev/i5b_health_check.py",
        "required_tests": ["tests/test_i5b_health_check.py"],
    },
    "i5b_pending_material_worklist": {
        "implementation": "scripts/dev/i5b_pending_material_worklist.py",
        "required_tests": ["tests/test_i5b_pending_material_worklist.py"],
    },
    "i5b_pending_factor_patch": {
        "implementation": "scripts/dev/i5b_pending_factor_patch.py",
        "required_tests": ["tests/test_i5b_pending_factor_patch.py"],
    },
    "i5b_pending_factor_patch_apply": {
        "implementation": "scripts/dev/i5b_pending_factor_patch_apply.py",
        "required_tests": ["tests/test_i5b_pending_factor_patch_apply.py"],
    },
    "i5b_finite_value_audit": {
        "implementation": "scripts/dev/i5b_finite_value_audit.py",
        "required_tests": ["tests/test_i5b_finite_value_audit.py", "tests/test_i5b_finite_values.py"],
    },
    "i5b_fact_relation_candidate_sync": {
        "implementation": "scripts/dev/i5b_fact_relation_candidate_sync.py",
        "required_tests": ["tests/test_i5b_fact_relation_candidate_sync.py"],
    },
    "i5b_fact_relation_gap_summary": {
        "implementation": "scripts/dev/i5b_fact_relation_gap_summary.py",
        "required_tests": ["tests/test_i5b_fact_relation_gap_summary.py"],
    },
    "i5b_hard_merit_handoff": {
        "implementation": "scripts/dev/i5b_hard_merit_handoff.py",
        "required_tests": ["tests/test_i5b_hard_merit_handoff.py"],
    },
    "i5b_authority_eval_handoff": {
        "implementation": "scripts/dev/i5b_authority_eval_handoff.py",
        "required_tests": ["tests/test_i5b_authority_eval_handoff.py"],
    },
    "i5b_authority_eval_distribution_audit": {
        "implementation": "scripts/dev/i5b_authority_eval_distribution_audit.py",
        "required_tests": ["tests/test_i5b_authority_eval_distribution_audit.py"],
    },
    "i5b_authority_eval_attr_sync": {
        "implementation": "scripts/dev/i5b_authority_eval_attr_sync.py",
        "required_tests": ["tests/test_i5b_authority_eval_attr_sync.py"],
    },
    "i5b_rule_evidence_unit_preview": {
        "implementation": "scripts/dev/i5b_rule_evidence_unit_preview.py",
        "required_tests": ["tests/test_i5b_rule_evidence_unit_preview.py"],
    },
    "i5b_rule_evidence_unit_issue_summary": {
        "implementation": "scripts/dev/i5b_rule_evidence_unit_issue_summary.py",
        "required_tests": ["tests/test_i5b_rule_evidence_unit_issue_summary.py"],
    },
    "i5b_rule_evidence_unit_candidate_builder": {
        "implementation": "scripts/dev/i5b_rule_evidence_unit_candidate_builder.py",
        "required_tests": ["tests/test_i5b_rule_evidence_unit_candidate_builder.py"],
    },
    "i5b_rule_evidence_unit_db_sync": {
        "implementation": "scripts/dev/i5b_rule_evidence_unit_db_sync.py",
        "required_tests": ["tests/test_i5b_rule_evidence_unit_db_sync.py"],
    },
    "i5b_factor_recalculator": {
        "implementation": "scripts/dev/i5b_factor_recalculator.py",
        "required_tests": ["tests/test_i5b_factor_recalculator.py"],
    },
    "i5b_rule_object_coverage_audit": {
        "implementation": "scripts/dev/i5b_rule_object_coverage_audit.py",
        "required_tests": ["tests/test_i5b_rule_object_coverage_audit.py"],
    },
    "i5b_talent_discovery_audit": {
        "implementation": "scripts/dev/i5b_talent_discovery_audit.py",
        "required_tests": ["tests/test_i5b_talent_discovery_audit.py"],
    },
    "i5b_payload_skeleton": {
        "implementation": "scripts/dev/i5b_payload_skeleton.py",
        "required_tests": ["tests/test_i5b_payload_skeleton.py"],
    },
    "i5b_object_payload_audit": {
        "implementation": "scripts/dev/i5b_object_payload_audit.py",
        "required_tests": ["tests/test_i5b_object_payload_audit.py"],
    },
    "i5b_object_payload_import_batch": {
        "implementation": "scripts/dev/i5b_object_payload_import_batch.py",
        "required_tests": ["tests/test_i5b_object_payload_import_batch.py"],
    },
    "i5b_next_stage_control_board": {
        "implementation": "scripts/dev/i5b_next_stage_control_board.py",
        "required_tests": ["tests/test_i5b_next_stage_control_board.py"],
    },
    "i5b_next_stage_queue_runner": {
        "implementation": "scripts/dev/i5b_next_stage_queue_runner.py",
        "required_tests": ["tests/test_i5b_next_stage_queue_runner.py"],
    },
    "i5b_source_key_audit": {
        "implementation": "scripts/dev/i5b_source_key_audit.py",
        "required_tests": ["tests/test_i5b_source_key_audit.py"],
    },
    "i5b_source_pack_audit": {
        "implementation": "scripts/dev/i5b_source_pack_audit.py",
        "required_tests": ["tests/test_i5b_source_pack_audit.py"],
    },
    "i5b_source_pack_handoff": {
        "implementation": "scripts/dev/i5b_source_pack_handoff.py",
        "required_tests": ["tests/test_i5b_source_pack_handoff.py"],
    },
    "i5b_source_pack_fetcher": {
        "implementation": "scripts/dev/i5b_source_pack_fetcher.py",
        "required_tests": ["tests/test_i5b_source_pack_fetcher.py"],
    },
    "i5b_source_pack_worker": {
        "implementation": "scripts/dev/i5b_source_pack_worker.py",
        "required_tests": ["tests/test_i5b_source_pack_worker.py"],
    },
    "i5b_source_pack_status": {
        "implementation": "scripts/dev/i5b_source_pack_status.py",
        "required_tests": ["tests/test_i5b_source_pack_status.py"],
    },
    "i5b_source_pack_control_board": {
        "implementation": "scripts/dev/i5b_source_pack_control_board.py",
        "required_tests": ["tests/test_i5b_source_pack_control_board.py"],
    },
    "i5b_query_profile_refiner": {
        "implementation": "scripts/dev/i5b_query_profile_refiner.py",
        "required_tests": ["tests/test_i5b_query_profile_refiner.py"],
    },
    "i5b_query_profile_refiner_daemon": {
        "implementation": "scripts/dev/i5b_query_profile_refiner_daemon.py",
        "required_tests": ["tests/test_i5b_query_profile_refiner_daemon.py"],
    },
    "i5b_source_pack_runtime_supervisor": {
        "implementation": "scripts/dev/i5b_source_pack_runtime_supervisor.py",
        "required_tests": ["tests/test_i5b_source_pack_runtime_supervisor.py"],
    },
    "i5b_source_pack_pipeline_daemon": {
        "implementation": "scripts/dev/i5b_source_pack_pipeline_daemon.py",
        "required_tests": ["tests/test_i5b_source_pack_pipeline_daemon.py"],
    },
    "i5b_query_profile_seed_builder": {
        "implementation": "scripts/dev/i5b_query_profile_seed_builder.py",
        "required_tests": ["tests/test_i5b_query_profile_seed_builder.py"],
    },
}


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_i5b_dev_automation_tools_are_registered() -> None:
    modules = {module["id"]: module for module in load_registry()["modules"]}

    for module_id, expected in EXPECTED_I5B_DEV_MODULES.items():
        module = modules[module_id]
        assert module["category"] == "dev"
        assert module["status"] == "active"
        assert module["legacy_wrapper"] is None
        assert module["implementation"] == expected["implementation"]
        assert module["required_tests"] == expected["required_tests"]


def test_deprecated_i5b_calc_logs_helper_is_not_registered_active_tool() -> None:
    modules = {module["id"]: module for module in load_registry()["modules"]}

    assert "i5b_calc_logs" not in modules
    assert not (ROOT / "scripts" / "dev" / "i5b_calc_logs.py").exists()
