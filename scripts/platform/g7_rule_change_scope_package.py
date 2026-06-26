from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PACKAGE_VERSION = "g7-rule-change-scope-package-v1"
G7_GATE = "G7_SCORING_RULE_CHANGE"
G7_APPROVAL_STATUS = "approved_scope_package_ready"
G7_APPROVAL_REFERENCE = "https://github.com/phdiggit/emperor-evaluation/issues/292"
G6_OBSERVATION_PR = 305
G6_OBSERVATION_MERGE_COMMIT = "96c231afe80ebeebcdf7cce76958e3302af9799b"
G6_EXECUTION_PLAN_SHA256 = "27c93eca232ce4654533cfdc28795be0e366574d182b0e8378ba41ffc242b858"
G6_MARKER_CODE = "G6-FORMAL-EVIDENCE-RELEASE-ISSUE292"
SUPPORTED_MODES = ("contract-report", "scope-md")


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "gate": G7_GATE,
        "gate_status": G7_APPROVAL_STATUS,
        "g7_approval_reference": G7_APPROVAL_REFERENCE,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_write_business_tables": True,
        "does_not_modify_rule_sources": True,
        "g1_to_g6_completion": {
            "g1_canonical_manifest_approved": True,
            "g2_mapping_approved": True,
            "g3_src_hosts_execute_observe_succeeded": True,
            "g4_write_source_cutover_succeeded": True,
            "g5_runtime_execute_observe_succeeded": True,
            "g6_formal_evidence_marker_observed": True,
            "g6_execution_plan_sha256": G6_EXECUTION_PLAN_SHA256,
            "g6_marker_code": G6_MARKER_CODE,
            "g6_observation_pr": G6_OBSERVATION_PR,
            "g6_observation_merge_commit": G6_OBSERVATION_MERGE_COMMIT,
        },
        "current_state": {
            "canonical_write_source": "postgresql",
            "jsonl_write_frozen": True,
            "postgres_unique_write_source": True,
            "production_credentials_enabled": True,
            "rabbitmq_live": True,
            "network_ingestion_live": True,
            "production_runtime_live": True,
            "formal_evidence_released": True,
            "g7_approved": True,
            "g7_rule_change_scope_package_ready": True,
            "formal_algorithm_released": False,
            "formal_score_values_released": False,
            "formal_ranking_released": False,
            "epic_2_entered": False,
        },
        "g7_allows": [
            "prepare_explicit_rule_change_workset",
            "review_subitem_rule_definition_diffs",
            "document_rule_change_impact_without_score_values",
            "add_tests_for_rule_text_and_boundary_invariants",
            "durable_checkpoint_and_docs_writeback_after_reviewed_rule_change",
        ],
        "g7_does_not_allow": [
            "formal_algorithm_release",
            "formal_score_values_release",
            "formal_ranking_or_leaderboard_release",
            "source_document_passage_merge_policy_write",
            "evidence_cluster_anchor_relationship_business_table_write_without_followup_gate",
            "destructive_canonical_or_history_cleanup",
            "epic_2_scope_entry_without_separate_ready_review",
        ],
        "g7_required_artifacts_for_rule_change_pr": [
            "changed_rule_paths",
            "before_after_rule_diff_summary",
            "impact_scope_statement",
            "regression_tests_for_rule_boundaries",
            "confirmation_that_algorithm_and_score_publication_remain_blocked",
        ],
        "candidate_rule_paths": [
            "docs/皇帝综合评价体系评分标准.md",
            "docs/分项规则/**",
            "docs/证据规则/**",
        ],
        "protected_paths_without_followup_gate": [
            "data/**",
            "archive/data/**",
            "exports/**",
            "source_passages_business_tables",
            "evidence_cluster_anchor_relationship_business_tables",
        ],
        "followup_gate_boundaries": {
            "formal_algorithm": {"status": "blocked_until_g8"},
            "formal_score_values_or_ranking_publication": {"status": "blocked_until_g9"},
            "destructive_cleanup": {"status": "blocked_until_g10"},
            "source_documents_passages": {"status": "blocked_by_followup_gate"},
            "evidence_clusters_anchors_relationships": {"status": "blocked_by_followup_gate"},
            "epic_2_entry": {"status": "blocked_until_separate_ready_review"},
        },
        "next_required_user_gate": "G8",
    }


def render_scope_md() -> str:
    report = build_contract_report()
    lines = [
        "# G7 Rule Change Scope Package",
        "",
        f"- gate: `{report['gate']}`",
        f"- gate_status: `{report['gate_status']}`",
        "- G1-G6 are complete and observed.",
        "- This package is report-only and does not modify rule sources.",
        "",
        "## Current State",
        "",
    ]
    for key, value in report["current_state"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## G7 Allows", ""])
    for item in report["g7_allows"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## G7 Does Not Allow", ""])
    for item in report["g7_does_not_allow"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Required Artifacts For A Rule Change PR", ""])
    for item in report["g7_required_artifacts_for_rule_change_pr"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Follow-Up Gates", ""])
    for key, value in report["followup_gate_boundaries"].items():
        lines.append(f"- `{key}`: `{value['status']}`")
    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the Epic 1 G7 rule change scope package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--scope-md", action="store_true")
    args = parser.parse_args(argv)

    if args.scope_md:
        sys.stdout.write(render_scope_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
