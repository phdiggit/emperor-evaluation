from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import platform_chain_checkpoint


BLOCKED_FOLLOWUP_CLAIMS = ("g10_approved", "epic_2_entered\": true", "epic_3_entered\": true")
FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_checkpoint_report_has_complete_platform_chain() -> None:
    report = platform_chain_checkpoint.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["checkpoint_version"] == "platform-chain-checkpoint-v1"
    assert report["current_state"] == {
        "current_phase": "post_g10_s1_script_lifecycle_finalization_ready",
        "active_epic": 312,
        "active_epic_title": "Scoring_Engine_Cross_Subitem_Generalization",
        "last_completed_epic": 211,
        "last_completed_pr": 345,
        "last_completed_merge_commit": "16e8d84f281a1d4b9fef4896ae1f96517d75ba6f",
        "positive_benefit_total": 1500,
        "former_active_cap_1440": "obsolete",
        "canonical_write_source": "postgresql",
        "postgres_schema_live": True,
        "postgres_business_data_migrated": False,
        "sqlite_build_operational": True,
        "full_pytest_operational": True,
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_runtime_live": True,
        "formal_evidence_released": True,
        "formal_algorithm_released": True,
        "formal_scoring_released": True,
        "formal_score_values_released": True,
        "formal_ranking_released": True,
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
        "g6_formal_evidence_boundary_package_ready": True,
        "g6_approved": True,
        "g6_formal_evidence_execution_package_ready": True,
        "g6_formal_evidence_execution_plan_sha256": "27c93eca232ce4654533cfdc28795be0e366574d182b0e8378ba41ffc242b858",
        "g6_formal_evidence_marker_code": "G6-FORMAL-EVIDENCE-RELEASE-ISSUE292",
        "g6_formal_evidence_execute_attempted": True,
        "g6_formal_evidence_execute_status": "succeeded",
        "g6_formal_evidence_observe_status": "succeeded",
        "g6_formal_evidence_post_apply_observation_completed": True,
        "g6_formal_evidence_marker_written": True,
        "g6_formal_evidence_marker_observed": True,
        "g7_approved": True,
        "g7_rule_change_scope_package_ready": True,
        "g7_rule_change_workset_ready": True,
        "g7_i5b_three_core_rule_change_ready": True,
        "g8_approved": True,
        "g8_i5b_formal_algorithm_released": True,
        "g8_i5b_formal_algorithm_version": "i5b-formal-algorithm-v1",
        "g9_approved": True,
        "g9_approval_comment": 4809664701,
        "g9_i5b_formal_publication_released": True,
        "g9_i5b_formal_publication_package": "g9-i5b-formal-publication-release-v1",
        "stage_or_final_total_table_released": False,
        "cross_subitem_leaderboard_released": False,
        "epic5_boundary_scope_package_ready": True,
        "epic5_boundary_scope_package": "epic5-scoring-engine-boundary-scope-package-v1",
        "epic5_boundary_scope_pr": 313,
        "epic5_boundary_scope_merge_commit": "07af05b3b80311bb19ba642c815a2ea7a517767f",
        "epic5_minimum_interface_contract_ready": True,
        "epic5_interface_contract_package": "epic5-scoring-engine-interface-contract-v1",
        "epic5_interface_contract_pr": 314,
        "epic5_interface_contract_merge_commit": "e64f9f9089739555823cb9268d283e5632abc893",
        "epic5_pilot_subitem_profile_contract_ready": True,
        "epic5_pilot_subitem_profile_contract_package": "epic5-pilot-subitem-profile-contract-v1",
        "epic5_pilot_subitem_profile_contract_pr": 315,
        "epic5_pilot_subitem_profile_contract_merge_commit": "af12b0a5792539220244449c6ac013b311791695",
        "pilot_subitem_profiles_selected": [
            "second_governance_net_benefit",
            "third_military_border_net_benefit",
            "sixth_key_decision_capacity",
        ],
        "pilot_profile_count": 3,
        "epic5_pilot_subitem_evidence_profile_contract_ready": True,
        "epic5_pilot_subitem_evidence_profile_contract_package": "epic5-pilot-subitem-evidence-profile-contract-v1",
        "epic5_pilot_subitem_evidence_profile_contract_pr": 316,
        "epic5_pilot_subitem_evidence_profile_contract_merge_commit": "b72bc06fdd30c6c59b3a5508f7553058deb7c102",
        "evidence_profile_contract_count": 3,
        "epic5_formal_grade_result_contract_ready": True,
        "epic5_formal_grade_result_contract_package": "epic5-formal-grade-result-contract-v1",
        "epic5_formal_grade_result_contract_pr": 317,
        "epic5_formal_grade_result_contract_merge_commit": "2f7e8b0b0954eb322600019791a9255718ff6649",
        "formal_grade_result_contract_count": 3,
        "epic5_score_publication_result_contract_ready": True,
        "epic5_score_publication_result_contract_package": "epic5-score-publication-result-contract-v1",
        "epic5_score_publication_result_contract_pr": 318,
        "epic5_score_publication_result_contract_merge_commit": "c800570aead93c146e6598d7246f892bf74aab5f",
        "score_publication_result_contract_count": 3,
        "epic5_deterministic_rerun_report_contract_ready": True,
        "epic5_deterministic_rerun_report_contract_package": "epic5-deterministic-rerun-report-contract-v1",
        "epic5_deterministic_rerun_report_contract_pr": 319,
        "epic5_deterministic_rerun_report_contract_merge_commit": "427e1be38d1ad612435e043d501a9850c11bd7a2",
        "deterministic_rerun_report_contract_count": 3,
        "validator_contracts_built": True,
        "impact_report_templates_built": True,
        "publication_report_templates_built": True,
        "person_specific_evidence_profiles_built": False,
        "person_specific_formal_grade_results_built": False,
        "person_specific_score_publication_results_built": False,
        "formal_grade_results_released_for_new_subitems": False,
        "score_publication_result_templates_built": True,
        "new_subitem_formal_scores_released": False,
        "new_subitem_formal_rankings_released": False,
        "epic_2_entered": False,
        "epic_3_entered": False,
        "issue311_dictionary_contract_ready": True,
        "issue311_dictionary_contract_package": "i5b-rule-display-dictionary-contract-v1",
        "i5b_dictionary_snapshot_schema_defined": True,
        "i5b_dictionary_loader_contract_defined": True,
        "i5b_dictionary_validator_contract_defined": True,
        "issue311_dictionary_snapshot_loader_validator_ready": True,
        "issue311_dictionary_snapshot_loader_validator_package": "i5b-dictionary-snapshot-loader-validator-v1",
        "i5b_dictionary_snapshot_path": (
            "scripts/platform/i5b_dictionary_snapshots/i5b_rule_display_dictionary_snapshot_v1.json"
        ),
        "i5b_dictionary_snapshot_item_count": 5,
        "i5b_dictionary_snapshot_inventory_symbol_count": 14,
        "i5b_dictionary_snapshot_digest_validation_passed": True,
        "issue311_runtime_adapter_dictionary_readiness_ready": True,
        "issue311_runtime_adapter_dictionary_readiness_package": "i5b-runtime-adapter-dictionary-readiness-v1",
        "i5b_runtime_symbol_inventory_count": 14,
        "i5b_runtime_symbol_inventory_complete": True,
        "issue311_readthrough_loader_shim_ready": True,
        "issue311_readthrough_loader_shim_package": "i5b-runtime-dictionary-readthrough-shim-v1",
        "i5b_readthrough_loader_module": (
            "scripts/export/dimension_adapters/i5b_people_delegation/dictionary_readthrough.py"
        ),
        "issue311_rules_py_keyword_dictionary_read_ready": True,
        "i5b_rules_py_keyword_dictionary_readthrough_enabled": True,
        "i5b_rules_py_rule_sensitive_points_readthrough_enabled": True,
        "issue311_formal_algorithm_grade_dictionary_read_ready": True,
        "i5b_formal_algorithm_grade_dictionary_readthrough_enabled": True,
        "i5b_formal_algorithm_direction_mapping_readthrough_enabled": True,
        "issue311_rules_py_grade_direction_dictionary_read_ready": True,
        "i5b_rules_py_trial_score_map_readthrough_enabled": True,
        "i5b_rules_py_dimension_rules_readthrough_enabled": True,
        "issue311_display_dictionary_read_ready": True,
        "i5b_adapter_display_dictionary_readthrough_enabled": True,
        "i5b_runtime_adapter_migrated": True,
        "issue311_python_constant_cleanup_after_readthrough_ready": True,
        "i5b_python_constant_cleanup_audit_passed": True,
        "i5b_legacy_python_dictionary_text_removed": True,
        "issue311_rule_display_dictionary_governance_gate_ready": True,
        "i5b_dictionary_governance_policy_recorded": True,
        "i5b_future_postgres_dictionary_schema_gate_required": True,
        "i5b_future_canonical_dictionary_write_gate_required": True,
        "epic5_per_subitem_g8_algorithm_release_gate_contract_ready": True,
        "per_subitem_g8_gate_contract_count": 3,
        "per_subitem_g8_algorithm_release_performed": False,
        "i5b_postgres_dictionary_tables_created": False,
        "i5b_canonical_dictionary_write_performed": False,
        "g10_plan_issues": [331, 332, 333, 334, 341, 342, 335],
        "g10_cleanup_inventory_plan_ready": True,
        "g10_cleanup_inventory_package": "g10-cleanup-inventory-plan-v1",
        "g10_cleanup_inventory_candidate_count": 10,
        "g10_1_i5b_dictionary_final_cleanup_ready": True,
        "g10_i5b_dictionary_final_cleanup_package": "g10-i5b-dictionary-final-cleanup-v1",
        "g10_i5b_dictionary_final_cleanup_prerequisite_pr": 336,
        "g10_i5b_dictionary_final_cleanup_prerequisite_merge_commit": (
            "027a084a7045e68343177eb09236cf4f090324d4"
        ),
        "i5b_rule_runtime_text_readthrough_enabled": True,
        "i5b_formal_algorithm_display_readthrough_enabled": True,
        "i5b_adapter_auto_band_directions_readthrough_enabled": True,
        "i5b_remaining_python_text_classified": True,
        "i5b_snapshot_final_cleanup_digest_validation_passed": True,
        "i5b_no_legacy_runtime_copy_regressions": True,
        "g10_2_historical_asset_retirement_ready": True,
        "g10_historical_asset_retirement_package": "g10-historical-asset-retirement-v1",
        "g10_historical_asset_retirement_prerequisite_pr": 337,
        "g10_historical_asset_retirement_prerequisite_merge_commit": (
            "703cae862f9fb6363315c85cce629616c8ab5de1"
        ),
        "g10_changed_removed_archived_paths_manifested": True,
        "g10_actual_moved_deleted_archived_path_count": 0,
        "g10_destructive_path_actions_deferred": True,
        "g10_registry_dangling_active_entries": 0,
        "g10_default_validate_retired_script_invocations": 0,
        "g10_replacement_mapping_auditable": True,
        "g10_restore_instructions_complete": True,
        "g10_3_script_asset_risk_governance_ready": True,
        "g10_script_asset_risk_governance_package": "g10-script-asset-risk-governance-v1",
        "g10_script_asset_risk_governance_prerequisite_pr": 338,
        "g10_script_asset_risk_governance_prerequisite_merge_commit": (
            "54f7466f4aeb44d5a18bffb1c28a4eda23ca4954"
        ),
        "g10_transitional_scripts_without_sunset": 0,
        "g10_retired_scripts_in_default_validate_or_public_cli": 0,
        "g10_duplicate_capability_groups_reviewed": 5,
        "g10_duplicate_capability_groups_without_reason": 0,
        "g10_script_delta_ready_for_roadmap_comments": True,
        "g10_outcome_verification_tests_added": True,
        "g10_2b_low_risk_script_lifecycle_execution_ready": True,
        "g10_low_risk_script_lifecycle_execution_package": "g10-low-risk-script-lifecycle-execution-v1",
        "g10_low_risk_script_lifecycle_execution_prerequisite_pr": 339,
        "g10_low_risk_script_lifecycle_execution_prerequisite_merge_commit": (
            "83c2438e31842f08ed19a1a1b00e965ce1fa9451"
        ),
        "g10_low_risk_lifecycle_update_count": 6,
        "g10_low_risk_updated_registry_entries": 6,
        "g10_low_risk_actual_moved_deleted_archived_path_count": 0,
        "g10_low_risk_restore_instructions_complete": True,
        "g10_low_risk_transitional_scripts_without_sunset": 0,
        "g10_low_risk_retired_default_public_route_violations": 0,
        "g10_3b_script_governance_enforcement_ready": True,
        "g10_script_governance_enforcement_package": "g10-script-governance-enforcement-v1",
        "g10_script_governance_enforcement_prerequisite_pr": 343,
        "g10_script_governance_enforcement_prerequisite_merge_commit": (
            "25d10100c88f83e0f06a8cf98203ac1e4c511858"
        ),
        "g10_registry_lifecycle_guard_enabled": True,
        "g10_registry_lifecycle_guard_in_validate_all": True,
        "g10_script_lifecycle_bad_fixture_fails": True,
        "g10_script_lifecycle_current_registry_passes": True,
        "g10_duplicate_capability_exceptions_explicit": True,
        "g10_script_delta_updated_for_roadmap_and_epic": True,
        "g10_4_completion_verification_handoff_ready": True,
        "g10_completion_report_package": "g10-completion-verification-handoff-v1",
        "g10_completion_report_prerequisite_pr": 344,
        "g10_completion_report_prerequisite_merge_commit": (
            "b65618797c6f31bf83dd6723ca301e9bb27f8117"
        ),
        "g10_current_handoff_pr": 340,
        "g10_open_ready_prs_excluding_current_handoff": 0,
        "g10_validation_all_green": True,
        "g10_registry_dangling_references": 0,
        "g10_report_complete": True,
        "g10_low_risk_lifecycle_execution_complete": True,
        "g10_script_governance_guard_enabled": True,
        "g10_next_phase_after_handoff_merge": "post_g10_ready_for_followup_gates",
        "post_g10_ready_for_followup_gates_ready": True,
        "post_g10_followup_gates_package": "post-g10-followup-gates-readiness-v1",
        "post_g10_handoff_pr": 340,
        "post_g10_handoff_merge_commit": "7d0c07a270ddb625d4150f0958c927da258ef66c",
        "post_g10_followup_gate_count": 8,
        "post_g10_followup_gates_requiring_separate_review": 8,
        "post_g10_next_action": "finish_issue_346_ready_review_before_selecting_non_script_followup_gate",
        "post_g10_s1_script_lifecycle_finalization_ready": True,
        "post_g10_script_lifecycle_finalization_package": "post-g10-script-lifecycle-finalization-v1",
        "post_g10_script_lifecycle_finalization_prerequisite_pr": 345,
        "post_g10_script_lifecycle_finalization_prerequisite_merge_commit": (
            "16e8d84f281a1d4b9fef4896ae1f96517d75ba6f"
        ),
        "script_lifecycle_finalization_non_active_item_count": 30,
        "script_lifecycle_finalization_updated_registry_entries": 24,
        "script_lifecycle_finalization_retired_in_place_count": 30,
        "script_lifecycle_finalization_moved_to_documented_retired_location_count": 13,
        "script_lifecycle_finalization_retained_in_place_count": 17,
        "script_lifecycle_finalization_restore_instructions_complete": True,
        "script_lifecycle_finalization_actual_moved_deleted_archived_path_count": 13,
        "script_lifecycle_finalization_documented_retired_location": (
            "scripts/platform/_retired/post_g10_s1"
        ),
        "script_lifecycle_finalization_active_root_retired_script_files_before": 30,
        "script_lifecycle_finalization_active_root_retired_script_files_after": 17,
        "script_lifecycle_finalization_active_root_line_reduction": 8132,
        "script_lifecycle_finalization_large_script_threshold_lines": 500,
        "script_lifecycle_finalization_large_script_move_count": 13,
        "script_lifecycle_finalization_old_active_paths_removed": True,
        "script_lifecycle_finalization_active_helper_extraction_completed": True,
        "script_lifecycle_finalization_active_large_script_refactor_count": 4,
        "script_lifecycle_finalization_active_large_script_lines_before": 2647,
        "script_lifecycle_finalization_active_large_script_lines_after": 2624,
        "script_lifecycle_finalization_active_large_script_line_reduction": 23,
        "script_lifecycle_finalization_active_plan_hash_helpers_consolidated": 4,
        "script_lifecycle_finalization_active_secret_redaction_helpers_consolidated": 4,
        "script_lifecycle_finalization_replacement_paths_exist": True,
        "script_lifecycle_finalization_transitional_scripts_without_sunset": 0,
        "script_lifecycle_finalization_retired_default_public_route_violations": 0,
        "script_lifecycle_finalization_duplicate_capability_groups_without_reason": 0,
        "script_lifecycle_finalization_report_only_tests_replaced": True,
        "script_lifecycle_finalization_remaining_debt_count": 0,
        "script_governance_report_only_fallback_allowed": False,
        "epic5_per_subitem_g9_publication_gate_approved": False,
        "epic5_cross_subitem_leaderboard_publication_gate_approved": False,
        "epic5_stage_or_final_total_table_publication_gate_approved": False,
        "g10_destructive_cleanup_gate_approved": False,
        "source_document_passage_merge_policy_gate_approved": False,
        "evidence_cluster_anchor_relationship_followup_gates_approved": False,
        "epic2_separate_ready_review_approved": False,
        "epic3_separate_ready_review_approved": False,
        "g10_execution_started": True,
        "g10_cleanup_execution_started": True,
        "g10_destructive_cleanup_started": False,
    }
    assert report["completed_chain"] == platform_chain_checkpoint.COMPLETED_CHAIN
    assert "production_schema_live_apply" in report["completed_chain"]
    assert "production_seed_manifest_import_audit_scaffold" in report["completed_chain"]
    assert "canonical_manifest_candidate_gate" in report["completed_chain"]
    assert "jsonl_postgres_mapping_approval_package" in report["completed_chain"]
    assert "jsonl_staging_diff_verification" in report["completed_chain"]
    assert "g3_postgres_business_write_execution_package" in report["completed_chain"]
    assert "g4_write_source_cutover_execution_package" in report["completed_chain"]
    assert "g5_runtime_boundary_package" in report["completed_chain"]
    assert "g5_runtime_execution_package" in report["completed_chain"]
    assert "g5_runtime_execution_observation" in report["completed_chain"]
    assert "g6_formal_evidence_boundary_package" in report["completed_chain"]
    assert "g6_formal_evidence_execution_package" in report["completed_chain"]
    assert "g6_formal_evidence_marker_observation" in report["completed_chain"]
    assert "g7_rule_change_scope_package" in report["completed_chain"]
    assert "g7_rule_change_workset_package" in report["completed_chain"]
    assert "g7_i5b_three_core_rule_change" in report["completed_chain"]
    assert "g8_i5b_formal_algorithm_release" in report["completed_chain"]
    assert "g9_i5b_formal_publication_release" in report["completed_chain"]
    assert "epic5_scoring_engine_scope_package" in report["completed_chain"]
    assert "epic5_scoring_engine_interface_contract" in report["completed_chain"]
    assert "epic5_pilot_subitem_profile_contract" in report["completed_chain"]
    assert "epic5_pilot_subitem_evidence_profile_contract" in report["completed_chain"]
    assert "epic5_formal_grade_result_contract" in report["completed_chain"]
    assert "epic5_score_publication_result_contract" in report["completed_chain"]
    assert "epic5_deterministic_rerun_report_contract" in report["completed_chain"]
    assert "issue311_i5b_rule_display_dictionary_contract" in report["completed_chain"]
    assert "issue311_i5b_dictionary_snapshot_loader_validator" in report["completed_chain"]
    assert "issue311_i5b_runtime_adapter_dictionary_readiness" in report["completed_chain"]
    assert "issue311_i5b_readthrough_loader_shim" in report["completed_chain"]
    assert "issue311_i5b_rules_py_keyword_dictionary_read" in report["completed_chain"]
    assert "issue311_i5b_formal_algorithm_grade_dictionary_read" in report["completed_chain"]
    assert "issue311_i5b_rules_py_grade_direction_dictionary_read" in report["completed_chain"]
    assert "issue311_i5b_display_dictionary_read" in report["completed_chain"]
    assert "issue311_i5b_python_constant_cleanup_after_readthrough" in report["completed_chain"]
    assert "issue311_rule_display_dictionary_governance_gate" in report["completed_chain"]
    assert "epic5_per_subitem_g8_algorithm_release_gate_contract" in report["completed_chain"]
    assert "g10_cleanup_inventory_plan" in report["completed_chain"]
    assert "g10_i5b_dictionary_final_cleanup" in report["completed_chain"]
    assert "g10_historical_asset_retirement" in report["completed_chain"]
    assert "g10_script_asset_risk_governance" in report["completed_chain"]
    assert "g10_low_risk_script_lifecycle_execution" in report["completed_chain"]
    assert "g10_script_governance_enforcement" in report["completed_chain"]
    assert "g10_completion_verification_handoff" in report["completed_chain"]
    assert "post_g10_followup_gates_readiness" in report["completed_chain"]
    assert "post_g10_script_lifecycle_finalization" in report["completed_chain"]
    assert any(tool["name"] == "g6_formal_evidence_boundary_package" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g6_formal_evidence_execution" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g7_rule_change_scope_package" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g7_rule_change_workset" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g8_i5b_formal_algorithm_release" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g9_i5b_formal_publication_release" for tool in report["prototype_tools"])
    assert any(tool["name"] == "epic5_scoring_engine_scope_package" for tool in report["prototype_tools"])
    assert any(tool["name"] == "epic5_scoring_engine_interface_contract" for tool in report["prototype_tools"])
    assert any(tool["name"] == "epic5_pilot_subitem_profile_contract" for tool in report["prototype_tools"])
    assert any(tool["name"] == "epic5_pilot_subitem_evidence_profile_contract" for tool in report["prototype_tools"])
    assert any(tool["name"] == "epic5_formal_grade_result_contract" for tool in report["prototype_tools"])
    assert any(tool["name"] == "epic5_score_publication_result_contract" for tool in report["prototype_tools"])
    assert any(tool["name"] == "epic5_deterministic_rerun_report_contract" for tool in report["prototype_tools"])
    assert any(tool["name"] == "issue311_i5b_rule_display_dictionary_contract" for tool in report["prototype_tools"])
    assert any(tool["name"] == "issue311_i5b_dictionary_snapshot_loader_validator" for tool in report["prototype_tools"])
    assert any(tool["name"] == "issue311_i5b_runtime_adapter_dictionary_readiness" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g10_cleanup_inventory_plan" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g10_i5b_dictionary_final_cleanup" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g10_historical_asset_retirement" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g10_script_asset_risk_governance" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g10_low_risk_script_lifecycle_execution" for tool in report["prototype_tools"])
    assert any(tool["name"] == "validate_script_lifecycle_registry" for tool in report["prototype_tools"])
    assert any(tool["name"] == "g10_completion_verification_handoff" for tool in report["prototype_tools"])
    assert any(tool["name"] == "post_g10_followup_gates_readiness" for tool in report["prototype_tools"])
    assert any(tool["name"] == "post_g10_script_lifecycle_finalization" for tool in report["prototype_tools"])
    assert "jsonl_query_search_target_mapper" in report["apply_capable_tools"]
    assert "jsonl_sources_target_mapper" in report["apply_capable_tools"]
    assert "jsonl_evidence_cards_target_mapper" in report["apply_capable_tools"]
    assert "jsonl_evidence_clusters_resolver" in report["apply_capable_tools"]
    assert "jsonl_anchors_target_mapper" in report["apply_capable_tools"]
    assert "anchors_resolver_contract" in report["contract_only_tools"]
    assert "post_g10_ready_for_followup_gates" not in report["next_epic_gates"]
    assert "epic5_per_subitem_g9_publication_gate" in report["next_epic_gates"]
    assert "epic5_cross_subitem_leaderboard_publication_gate" in report["next_epic_gates"]
    assert report["baseline_repair_tracking"]["sqlite_build_operational"] is True
    assert report["baseline_repair_tracking"]["full_pytest_operational"] is True
    assert report["baseline_repair_tracking"]["sqlite_schema_source"] == "db/sqlite/001_cache.sql"
    assert "PostgreSQL" in report["baseline_repair_tracking"]["postgres_schema_boundary"]


def test_checkpoint_report_is_offline_and_does_not_touch_forbidden_paths(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in platform checkpoint")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env" or "batches" in self.parts or ("archive" in self.parts and "data" in self.parts):
            raise AssertionError(f"checkpoint must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = platform_chain_checkpoint.build_contract_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert "does_not_read_dotenv" in report["limitations"]
    assert "does_not_read_batch_or_archive_inputs" in report["limitations"]


def test_checkpoint_report_does_not_claim_followup_gates() -> None:
    text = platform_chain_checkpoint.report_as_json(platform_chain_checkpoint.build_contract_report()).lower()
    assert '"formal_score_values_released": true' in text
    assert '"formal_ranking_released": true' in text
    assert "g9_publication_released_without_g10_cleanup_or_business_table_writes" in text
    assert '"stage_or_final_total_table_released": false' in text
    assert '"cross_subitem_leaderboard_released": false' in text
    assert '"new_subitem_formal_scores_released": false' in text
    assert '"new_subitem_formal_rankings_released": false' in text
    assert '"person_specific_evidence_profiles_built": false' in text
    assert '"person_specific_formal_grade_results_built": false' in text
    assert '"person_specific_score_publication_results_built": false' in text
    assert '"formal_grade_results_released_for_new_subitems": false' in text
    assert '"score_publication_result_templates_built": true' in text
    assert '"validator_contracts_built": true' in text
    assert '"impact_report_templates_built": true' in text
    assert '"publication_report_templates_built": true' in text
    assert '"issue311_dictionary_contract_ready": true' in text
    assert '"issue311_display_dictionary_read_ready": true' in text
    assert '"i5b_adapter_display_dictionary_readthrough_enabled": true' in text
    assert '"i5b_runtime_adapter_migrated": true' in text
    assert '"issue311_python_constant_cleanup_after_readthrough_ready": true' in text
    assert '"i5b_python_constant_cleanup_audit_passed": true' in text
    assert '"i5b_legacy_python_dictionary_text_removed": true' in text
    assert '"issue311_rule_display_dictionary_governance_gate_ready": true' in text
    assert '"i5b_dictionary_governance_policy_recorded": true' in text
    assert '"i5b_future_postgres_dictionary_schema_gate_required": true' in text
    assert '"i5b_future_canonical_dictionary_write_gate_required": true' in text
    assert '"epic5_per_subitem_g8_algorithm_release_gate_contract_ready": true' in text
    assert '"per_subitem_g8_gate_contract_count": 3' in text
    assert '"per_subitem_g8_algorithm_release_performed": false' in text
    assert '"i5b_postgres_dictionary_tables_created": false' in text
    assert '"i5b_canonical_dictionary_write_performed": false' in text
    assert '"g10_cleanup_inventory_plan_ready": true' in text
    assert '"g10_1_i5b_dictionary_final_cleanup_ready": true' in text
    assert '"g10_i5b_dictionary_final_cleanup_package": "g10-i5b-dictionary-final-cleanup-v1"' in text
    assert '"i5b_rule_runtime_text_readthrough_enabled": true' in text
    assert '"i5b_formal_algorithm_display_readthrough_enabled": true' in text
    assert '"i5b_adapter_auto_band_directions_readthrough_enabled": true' in text
    assert '"i5b_remaining_python_text_classified": true' in text
    assert '"i5b_snapshot_final_cleanup_digest_validation_passed": true' in text
    assert '"i5b_no_legacy_runtime_copy_regressions": true' in text
    assert '"g10_2_historical_asset_retirement_ready": true' in text
    assert '"g10_historical_asset_retirement_package": "g10-historical-asset-retirement-v1"' in text
    assert '"g10_changed_removed_archived_paths_manifested": true' in text
    assert '"g10_actual_moved_deleted_archived_path_count": 0' in text
    assert '"g10_destructive_path_actions_deferred": true' in text
    assert '"g10_registry_dangling_active_entries": 0' in text
    assert '"g10_default_validate_retired_script_invocations": 0' in text
    assert '"g10_replacement_mapping_auditable": true' in text
    assert '"g10_restore_instructions_complete": true' in text
    assert '"g10_3_script_asset_risk_governance_ready": true' in text
    assert '"g10_script_asset_risk_governance_package": "g10-script-asset-risk-governance-v1"' in text
    assert '"g10_transitional_scripts_without_sunset": 0' in text
    assert '"g10_retired_scripts_in_default_validate_or_public_cli": 0' in text
    assert '"g10_duplicate_capability_groups_reviewed": 5' in text
    assert '"g10_duplicate_capability_groups_without_reason": 0' in text
    assert '"g10_script_delta_ready_for_roadmap_comments": true' in text
    assert '"g10_outcome_verification_tests_added": true' in text
    assert '"g10_2b_low_risk_script_lifecycle_execution_ready": true' in text
    assert '"g10_low_risk_script_lifecycle_execution_package": "g10-low-risk-script-lifecycle-execution-v1"' in text
    assert '"g10_low_risk_lifecycle_update_count": 6' in text
    assert '"g10_low_risk_updated_registry_entries": 6' in text
    assert '"g10_low_risk_actual_moved_deleted_archived_path_count": 0' in text
    assert '"g10_low_risk_restore_instructions_complete": true' in text
    assert '"g10_low_risk_transitional_scripts_without_sunset": 0' in text
    assert '"g10_low_risk_retired_default_public_route_violations": 0' in text
    assert '"g10_3b_script_governance_enforcement_ready": true' in text
    assert '"g10_script_governance_enforcement_package": "g10-script-governance-enforcement-v1"' in text
    assert '"g10_registry_lifecycle_guard_enabled": true' in text
    assert '"g10_registry_lifecycle_guard_in_validate_all": true' in text
    assert '"g10_script_lifecycle_bad_fixture_fails": true' in text
    assert '"g10_script_lifecycle_current_registry_passes": true' in text
    assert '"g10_duplicate_capability_exceptions_explicit": true' in text
    assert '"g10_script_delta_updated_for_roadmap_and_epic": true' in text
    assert '"g10_4_completion_verification_handoff_ready": true' in text
    assert '"g10_completion_report_package": "g10-completion-verification-handoff-v1"' in text
    assert '"g10_completion_report_prerequisite_pr": 344' in text
    assert '"g10_current_handoff_pr": 340' in text
    assert '"g10_open_ready_prs_excluding_current_handoff": 0' in text
    assert '"g10_validation_all_green": true' in text
    assert '"g10_registry_dangling_references": 0' in text
    assert '"g10_report_complete": true' in text
    assert '"g10_low_risk_lifecycle_execution_complete": true' in text
    assert '"g10_script_governance_guard_enabled": true' in text
    assert '"g10_next_phase_after_handoff_merge": "post_g10_ready_for_followup_gates"' in text
    assert '"post_g10_ready_for_followup_gates_ready": true' in text
    assert '"post_g10_followup_gates_package": "post-g10-followup-gates-readiness-v1"' in text
    assert '"post_g10_handoff_pr": 340' in text
    assert '"post_g10_followup_gate_count": 8' in text
    assert '"post_g10_followup_gates_requiring_separate_review": 8' in text
    assert '"post_g10_next_action": "finish_issue_346_ready_review_before_selecting_non_script_followup_gate"' in text
    assert '"post_g10_s1_script_lifecycle_finalization_ready": true' in text
    assert '"post_g10_script_lifecycle_finalization_package": "post-g10-script-lifecycle-finalization-v1"' in text
    assert '"post_g10_script_lifecycle_finalization_prerequisite_pr": 345' in text
    assert '"script_lifecycle_finalization_non_active_item_count": 30' in text
    assert '"script_lifecycle_finalization_updated_registry_entries": 24' in text
    assert '"script_lifecycle_finalization_retired_in_place_count": 30' in text
    assert '"script_lifecycle_finalization_moved_to_documented_retired_location_count": 13' in text
    assert '"script_lifecycle_finalization_retained_in_place_count": 17' in text
    assert '"script_lifecycle_finalization_restore_instructions_complete": true' in text
    assert '"script_lifecycle_finalization_actual_moved_deleted_archived_path_count": 13' in text
    assert (
        '"script_lifecycle_finalization_documented_retired_location": '
        '"scripts/platform/_retired/post_g10_s1"' in text
    )
    assert '"script_lifecycle_finalization_active_root_retired_script_files_before": 30' in text
    assert '"script_lifecycle_finalization_active_root_retired_script_files_after": 17' in text
    assert '"script_lifecycle_finalization_active_root_line_reduction": 8132' in text
    assert '"script_lifecycle_finalization_large_script_threshold_lines": 500' in text
    assert '"script_lifecycle_finalization_large_script_move_count": 13' in text
    assert '"script_lifecycle_finalization_old_active_paths_removed": true' in text
    assert '"script_lifecycle_finalization_active_helper_extraction_completed": true' in text
    assert '"script_lifecycle_finalization_active_large_script_refactor_count": 4' in text
    assert '"script_lifecycle_finalization_active_large_script_lines_before": 2647' in text
    assert '"script_lifecycle_finalization_active_large_script_lines_after": 2624' in text
    assert '"script_lifecycle_finalization_active_large_script_line_reduction": 23' in text
    assert '"script_lifecycle_finalization_active_plan_hash_helpers_consolidated": 4' in text
    assert '"script_lifecycle_finalization_active_secret_redaction_helpers_consolidated": 4' in text
    assert '"script_lifecycle_finalization_replacement_paths_exist": true' in text
    assert '"script_lifecycle_finalization_transitional_scripts_without_sunset": 0' in text
    assert '"script_lifecycle_finalization_retired_default_public_route_violations": 0' in text
    assert '"script_lifecycle_finalization_duplicate_capability_groups_without_reason": 0' in text
    assert '"script_lifecycle_finalization_report_only_tests_replaced": true' in text
    assert '"script_lifecycle_finalization_remaining_debt_count": 0' in text
    assert '"script_governance_report_only_fallback_allowed": false' in text
    assert '"epic5_per_subitem_g9_publication_gate_approved": false' in text
    assert '"epic5_cross_subitem_leaderboard_publication_gate_approved": false' in text
    assert '"epic5_stage_or_final_total_table_publication_gate_approved": false' in text
    assert '"g10_destructive_cleanup_gate_approved": false' in text
    assert '"source_document_passage_merge_policy_gate_approved": false' in text
    assert '"evidence_cluster_anchor_relationship_followup_gates_approved": false' in text
    assert '"epic2_separate_ready_review_approved": false' in text
    assert '"epic3_separate_ready_review_approved": false' in text
    assert '"g10_execution_started": true' in text
    assert '"g10_cleanup_execution_started": true' in text
    assert '"g10_destructive_cleanup_started": false' in text
    assert "epic5_scope_does_not_publish_new_subitem_scores_or_cross_subitem_leaderboard" in text
    assert "epic5_interface_contract_does_not_publish_new_subitem_scores_or_cross_subitem_leaderboard" in text
    assert "epic5_pilot_profile_contract_does_not_publish_evidence_profiles_formal_scores_or_leaderboards" in text
    assert "epic5_pilot_evidence_profile_contract_does_not_lookup_sources_or_publish_formal_grade_results" in text
    assert "epic5_formal_grade_result_contract_does_not_publish_scores_or_rankings" in text
    assert "epic5_score_publication_result_contract_does_not_release_person_scores_or_leaderboards" in text
    assert "epic5_deterministic_rerun_report_contract_does_not_publish_scores_or_rankings" in text
    assert "issue311_dictionary_contract_does_not_create_tables_or_migrate_runtime_adapter" in text
    assert "issue311_display_dictionary_read_keeps_exporter_output_parity" in text
    assert "issue311_python_constant_cleanup_after_readthrough_keeps_snapshot_and_runtime_parity" in text
    assert "issue311_rule_display_dictionary_governance_gate_does_not_create_tables_or_write_canonical" in text
    assert "epic5_per_subitem_g8_gate_contract_does_not_release_new_subitem_scores_or_rankings" in text
    assert "g10_cleanup_inventory_plan_does_not_move_delete_or_archive_files" in text
    assert "g10_i5b_dictionary_final_cleanup_does_not_create_tables_or_publish_scores" in text
    assert "g10_i5b_dictionary_final_cleanup_does_not_move_delete_or_archive_files" in text
    assert "g10_historical_asset_retirement_manifests_all_changed_removed_archived_paths" in text
    assert "g10_historical_asset_retirement_does_not_move_delete_or_archive_files" in text
    assert "g10_historical_asset_retirement_defers_data_and_generated_export_destructive_actions" in text
    assert "g10_script_asset_risk_governance_does_not_change_business_behavior" in text
    assert "g10_script_asset_risk_governance_does_not_move_delete_or_archive_files" in text
    assert "g10_script_asset_risk_governance_keeps_retired_scripts_out_of_default_validate" in text
    assert "g10_low_risk_script_lifecycle_execution_updates_registry_only" in text
    assert "g10_low_risk_script_lifecycle_execution_keeps_files_in_place" in text
    assert "g10_low_risk_script_lifecycle_execution_does_not_touch_data_archive_or_exports" in text
    assert "g10_low_risk_script_lifecycle_execution_requires_restore_instruction_per_item" in text
    assert "g10_script_governance_enforcement_adds_validate_all_guard" in text
    assert "g10_script_governance_enforcement_fails_bad_lifecycle_fixture" in text
    assert "g10_script_governance_enforcement_keeps_retired_scripts_out_of_default_public_routes" in text
    assert "g10_script_governance_enforcement_requires_duplicate_capability_reason_or_plan" in text
    assert "g10_completion_verification_handoff_does_not_expand_retirement_scope" in text
    assert "g10_completion_verification_handoff_does_not_move_delete_or_archive_files" in text
    assert "g10_completion_verification_handoff_does_not_publish_scores_or_rankings" in text
    assert "g10_completion_verification_handoff_requires_post_g10_followup_gates" in text
    assert "post_g10_followup_gates_readiness_does_not_execute_followup_gates" in text
    assert "post_g10_followup_gates_readiness_requires_separate_ready_review_per_gate" in text
    assert "post_g10_followup_gates_readiness_does_not_publish_scores_rankings_or_leaderboards" in text
    assert "post_g10_followup_gates_readiness_does_not_move_delete_archive_or_write_business_tables" in text
    assert "post_g10_followup_gates_readiness_does_not_enter_epic2_or_epic3" in text
    assert "post_g10_script_lifecycle_finalization_updates_registry_and_moves_large_retired_scripts" in text
    assert "post_g10_script_lifecycle_finalization_moves_only_to_documented_retired_location" in text
    assert "post_g10_script_lifecycle_finalization_extracts_active_plan_hash_and_redaction_helpers" in text
    assert "post_g10_script_lifecycle_finalization_does_not_touch_data_archive_or_exports" in text
    assert "post_g10_script_lifecycle_finalization_requires_restore_instruction_per_item" in text
    assert "post_g10_script_lifecycle_finalization_keeps_retired_scripts_out_of_default_public_routes" in text
    assert "post_g10_script_lifecycle_finalization_disallows_report_only_fallback" in text

    for term in BLOCKED_FOLLOWUP_CLAIMS:
        assert term not in text


def test_checkpoint_cli_prints_json(capsys) -> None:
    assert platform_chain_checkpoint.main(["--contract-report"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["known_ci_history"][0]["fix"] == "install_requirements_before_validate_all"


def test_checkpoint_source_is_contract_only() -> None:
    source = (ROOT / "scripts" / "platform" / "platform_chain_checkpoint.py").read_text(encoding="utf-8")

    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "psycopg" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
