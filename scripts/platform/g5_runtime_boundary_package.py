from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PACKAGE_VERSION = "g5-runtime-boundary-package-v1"
G5_GATE = "G5_RUNTIME_CREDENTIALS_NETWORK_INGESTION"
G5_APPROVAL_STATUS = "required_not_approved"
G5_APPROVAL_TOKEN_PLACEHOLDER = "USER_APPROVED_G5_RUNTIME_CREDENTIALS_NETWORK_ISSUE292"
G3_EXECUTION_PLAN_SHA256 = "1138f4f0ef95e20e0026185f6530ad4671dc61aba13be330a466b20890ae315d"
G4_CUTOVER_PLAN_SHA256 = "32d02b0d9ac77a7876fa503fb261f052a22bffe84dead3af865af23fe4806a4a"
G4_RESULT_PR = 299
G4_RESULT_HEAD_SHA = "e13c91ef3e93d9e67153c6123d7b01460f3c303e"
G4_RESULT_MERGE_COMMIT = "dc5a89e4406ecb5425db8dc32172fcc3e45893df"
SUPPORTED_MODES = ("contract-report", "boundary-md")


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "gate": G5_GATE,
        "gate_status": G5_APPROVAL_STATUS,
        "approval_token_placeholder": G5_APPROVAL_TOKEN_PLACEHOLDER,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "g1_to_g4_completion": {
            "g1_canonical_manifest_approved": True,
            "g2_mapping_approved": True,
            "g3_src_hosts_execute_observe_succeeded": True,
            "g3_execution_plan_sha256": G3_EXECUTION_PLAN_SHA256,
            "g4_write_source_cutover_succeeded": True,
            "g4_cutover_plan_sha256": G4_CUTOVER_PLAN_SHA256,
            "g4_result_pr": G4_RESULT_PR,
            "g4_result_head_sha": G4_RESULT_HEAD_SHA,
            "g4_result_merge_commit": G4_RESULT_MERGE_COMMIT,
        },
        "current_state": {
            "canonical_write_source": "postgresql",
            "jsonl_write_frozen": True,
            "postgres_unique_write_source": True,
            "production_runtime_live": False,
            "rabbitmq_live": False,
            "network_ingestion_live": False,
            "production_credentials_enabled": False,
            "formal_evidence_released": False,
            "formal_scoring_released": False,
            "formal_ranking_released": False,
            "epic_2_entered": False,
        },
        "g5_would_allow_after_explicit_approval": [
            "operator_scoped_production_credentials_read",
            "approved_postgresql_runtime_connection",
            "rabbitmq_queue_exchange_binding_smoke",
            "outbox_dispatcher_worker_runtime_smoke",
            "network_ingestion_pilot_against_approved_source_allowlist",
            "runtime_observability_and_audit_reports",
        ],
        "g5_does_not_allow": [
            "formal_evidence_promotion",
            "formal_scoring_or_ranking_release",
            "scoring_rule_or_algorithm_change",
            "source_document_passage_merge_policy_write",
            "evidence_cluster_anchor_relationship_business_table_write",
            "destructive_canonical_or_history_cleanup",
            "epic_2_scope_entry_without_separate_ready_review",
        ],
        "g5_preconditions": [
            "explicit_user_g5_approval_recorded",
            "operator_owned_secret_injection_only_no_committed_credentials",
            "approved_postgresql_dsn_scope_and_read_write_role",
            "approved_rabbitmq_url_vhost_queue_exchange_binding",
            "approved_network_source_allowlist_and_rate_limits",
            "runtime_kill_switch_and_rollback_steps_documented",
            "post_apply_observation_queries_defined",
            "logs_and_audit_outputs_exclude_plaintext_secrets",
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
            "formal_evidence": {"status": "blocked_until_g6"},
            "scoring_rules": {"status": "blocked_until_g7"},
            "scoring_algorithm": {"status": "blocked_until_g8"},
            "formal_publication": {"status": "blocked_until_g9"},
            "destructive_cleanup": {"status": "blocked_until_g10"},
        },
        "next_required_user_gate": "G5",
    }


def render_boundary_md() -> str:
    report = build_contract_report()
    lines = [
        "# G5 Runtime Boundary Package",
        "",
        f"- gate: `{report['gate']}`",
        f"- gate_status: `{report['gate_status']}`",
        "- G1-G4 are complete and observed.",
        "- This package is report-only and does not execute G5.",
        "",
        "## Current State",
        "",
    ]
    for key, value in report["current_state"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## G5 Would Allow After Approval", ""])
    for item in report["g5_would_allow_after_explicit_approval"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## G5 Does Not Allow", ""])
    for item in report["g5_does_not_allow"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Preconditions", ""])
    for item in report["g5_preconditions"]:
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

    parser = argparse.ArgumentParser(description="Build the Epic 1 G5 runtime boundary package.")
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
