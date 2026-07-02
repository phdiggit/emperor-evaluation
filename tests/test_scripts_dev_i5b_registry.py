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
    "i5b_health_check": {
        "implementation": "scripts/dev/i5b_health_check.py",
        "required_tests": ["tests/test_i5b_health_check.py"],
    },
    "i5b_fact_relation_candidate_sync": {
        "implementation": "scripts/dev/i5b_fact_relation_candidate_sync.py",
        "required_tests": ["tests/test_i5b_fact_relation_candidate_sync.py"],
    },
    "i5b_fact_relation_gap_summary": {
        "implementation": "scripts/dev/i5b_fact_relation_gap_summary.py",
        "required_tests": ["tests/test_i5b_fact_relation_gap_summary.py"],
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
    "i5b_source_key_audit": {
        "implementation": "scripts/dev/i5b_source_key_audit.py",
        "required_tests": ["tests/test_i5b_source_key_audit.py"],
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
