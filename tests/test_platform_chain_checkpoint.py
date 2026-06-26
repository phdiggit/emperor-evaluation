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
        "current_phase": "issue311-i5b-dictionary-externalization-contract-ready",
        "active_epic": 312,
        "active_epic_title": "Scoring_Engine_Cross_Subitem_Generalization",
        "last_completed_epic": 211,
        "last_completed_pr": 310,
        "last_completed_merge_commit": "831aae51845763ddd2e8944b95e5397320aeff1b",
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
        "i5b_runtime_adapter_migrated": False,
        "i5b_postgres_dictionary_tables_created": False,
        "i5b_canonical_dictionary_write_performed": False,
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
    assert "jsonl_query_search_target_mapper" in report["apply_capable_tools"]
    assert "jsonl_sources_target_mapper" in report["apply_capable_tools"]
    assert "jsonl_evidence_cards_target_mapper" in report["apply_capable_tools"]
    assert "jsonl_evidence_clusters_resolver" in report["apply_capable_tools"]
    assert "jsonl_anchors_target_mapper" in report["apply_capable_tools"]
    assert "anchors_resolver_contract" in report["contract_only_tools"]
    assert "issue311_dictionary_snapshot_loader_validator_package" in report["next_epic_gates"]
    assert "epic5_per_subitem_g8_algorithm_release_gate" in report["next_epic_gates"]
    assert "epic5_cross_subitem_leaderboard_publication_gate" in report["next_epic_gates"]
    assert "issue_311_rule_display_dictionary_governance_gate" in report["next_epic_gates"]
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
    assert '"i5b_runtime_adapter_migrated": false' in text
    assert '"i5b_postgres_dictionary_tables_created": false' in text
    assert '"i5b_canonical_dictionary_write_performed": false' in text
    assert "epic5_scope_does_not_publish_new_subitem_scores_or_cross_subitem_leaderboard" in text
    assert "epic5_interface_contract_does_not_publish_new_subitem_scores_or_cross_subitem_leaderboard" in text
    assert "epic5_pilot_profile_contract_does_not_publish_evidence_profiles_formal_scores_or_leaderboards" in text
    assert "epic5_pilot_evidence_profile_contract_does_not_lookup_sources_or_publish_formal_grade_results" in text
    assert "epic5_formal_grade_result_contract_does_not_publish_scores_or_rankings" in text
    assert "epic5_score_publication_result_contract_does_not_release_person_scores_or_leaderboards" in text
    assert "epic5_deterministic_rerun_report_contract_does_not_publish_scores_or_rankings" in text
    assert "issue311_dictionary_contract_does_not_create_tables_or_migrate_runtime_adapter" in text

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
