from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PACKAGE_VERSION = "g6-formal-evidence-boundary-package-v1"
G6_GATE = "G6_FORMAL_EVIDENCE_RELEASE"
G6_APPROVAL_STATUS = "required_not_approved"
G6_APPROVAL_TOKEN_PLACEHOLDER = "USER_APPROVED_G6_FORMAL_EVIDENCE_RELEASE_ISSUE292"
G5_EXECUTION_PLAN_SHA256 = "590b083e27e8d6f9b93c3742936ef043e17262abc041a0132d4bcf5364d0edbd"
G5_RESULT_PR = 302
G5_RESULT_HEAD_SHA = "df28a1ae8494bf881b0338e7ce0da414c9aa9a7d"
G5_RESULT_MERGE_COMMIT = "aff8220f1e617c15075d9fc3a495a1b10b72af2e"
SUPPORTED_MODES = ("contract-report", "boundary-md")


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "gate": G6_GATE,
        "gate_status": G6_APPROVAL_STATUS,
        "approval_token_placeholder": G6_APPROVAL_TOKEN_PLACEHOLDER,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_write_business_tables": True,
        "g1_to_g5_completion": {
            "g1_canonical_manifest_approved": True,
            "g2_mapping_approved": True,
            "g3_src_hosts_execute_observe_succeeded": True,
            "g4_write_source_cutover_succeeded": True,
            "g5_runtime_execute_observe_succeeded": True,
            "g5_execution_plan_sha256": G5_EXECUTION_PLAN_SHA256,
            "g5_result_pr": G5_RESULT_PR,
            "g5_result_head_sha": G5_RESULT_HEAD_SHA,
            "g5_result_merge_commit": G5_RESULT_MERGE_COMMIT,
        },
        "current_state": {
            "canonical_write_source": "postgresql",
            "jsonl_write_frozen": True,
            "postgres_unique_write_source": True,
            "production_credentials_enabled": True,
            "rabbitmq_live": True,
            "network_ingestion_live": True,
            "production_runtime_live": True,
            "g6_approved": False,
            "formal_evidence_released": False,
            "formal_scoring_released": False,
            "formal_ranking_released": False,
            "epic_2_entered": False,
        },
        "g6_would_allow_after_explicit_approval": [
            "formal_evidence_release_execution_package",
            "source_backed_candidate_evidence_review",
            "candidate_to_formal_evidence_audit_report",
            "formal_evidence_release_marker_after_successful_observation",
            "durable_checkpoint_and_docs_writeback_after_observed_release",
        ],
        "g6_does_not_allow": [
            "formal_scoring_or_score_release",
            "formal_ranking_or_leaderboard_release",
            "scoring_rule_change",
            "scoring_algorithm_change",
            "source_document_passage_merge_policy_write",
            "evidence_cluster_anchor_relationship_business_table_write_without_followup_gate",
            "destructive_canonical_or_history_cleanup",
            "epic_2_scope_entry_without_separate_ready_review",
        ],
        "g6_preconditions": [
            "explicit_user_g6_approval_recorded",
            "g1_to_g5_completion_observed",
            "formal_evidence_candidate_workset_declared",
            "source_backing_and_manual_adjudication_requirements_declared",
            "rollback_or_supersession_plan_declared",
            "post_apply_observation_queries_defined",
            "no_plaintext_secrets_in_tracked_files_or_github_text",
        ],
        "followup_gate_boundaries": {
            "source_documents_passages": {
                "status": "blocked_by_followup_gate",
                "requires": "source_document_passage_merge_policy",
            },
            "evidence_clusters_anchors_relationships": {
                "status": "blocked_by_followup_gate",
                "requires": "resolver_outputs_manual_review_and_relationship_gate",
            },
            "scoring_rules": {"status": "blocked_until_g7"},
            "scoring_algorithm": {"status": "blocked_until_g8"},
            "formal_score_or_ranking_publication": {"status": "blocked_until_g9"},
            "destructive_cleanup": {"status": "blocked_until_g10"},
            "epic_2_entry": {"status": "blocked_until_separate_ready_review"},
        },
        "next_required_user_gate": "G6",
    }


def render_boundary_md() -> str:
    report = build_contract_report()
    lines = [
        "# G6 Formal Evidence Boundary Package",
        "",
        f"- gate: `{report['gate']}`",
        f"- gate_status: `{report['gate_status']}`",
        "- G1-G5 are complete and observed.",
        "- This package is report-only and does not approve or execute formal evidence release.",
        "",
        "## Current State",
        "",
    ]
    for key, value in report["current_state"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## G6 Would Allow After Approval", ""])
    for item in report["g6_would_allow_after_explicit_approval"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## G6 Does Not Allow", ""])
    for item in report["g6_does_not_allow"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Preconditions", ""])
    for item in report["g6_preconditions"]:
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

    parser = argparse.ArgumentParser(description="Build the Epic 1 G6 formal evidence boundary package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--boundary-md", action="store_true")
    args = parser.parse_args(argv)

    if args.boundary_md:
        sys.stdout.write(render_boundary_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
