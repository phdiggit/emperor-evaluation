from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_completion_verification_handoff as handoff  # noqa: E402


PACKAGE_VERSION = "post-g10-followup-gates-readiness-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
HANDOFF_ISSUE = 335
HANDOFF_PR = 340
HANDOFF_MERGE_COMMIT = "7d0c07a270ddb625d4150f0958c927da258ef66c"
SUPPORTED_MODES = ("gates-report", "gates-md")
NEXT_REQUIRED_WORK = "select_one_followup_gate_and_open_separate_ready_review"
PACKAGE_CHANGED_PATHS = (
    "db/postgres/README.md",
    "docs/数据结构与生成库/史源数据平台迁移决策.md",
    "docs/文档与脚本登记/scripts_registry.json",
    "scripts/platform/platform_chain_checkpoint.py",
    "scripts/platform/post_g10_followup_gates_readiness.py",
    "tests/test_platform_chain_checkpoint.py",
    "tests/test_post_g10_followup_gates_readiness.py",
)

FOLLOWUP_GATES: tuple[dict[str, Any], ...] = (
    {
        "gate_id": "epic5_per_subitem_g9_publication_gate",
        "scope": "per-subitem G9 score and ranking publication for explicitly selected subitems",
        "current_status": "requires_separate_ready_review",
        "required_before": "new_subitem_formal_scores_or_rankings",
    },
    {
        "gate_id": "epic5_cross_subitem_leaderboard_publication_gate",
        "scope": "cross-subitem leaderboard publication",
        "current_status": "requires_separate_ready_review",
        "required_before": "cross_subitem_leaderboard_release",
    },
    {
        "gate_id": "epic5_stage_or_final_total_table_publication_gate",
        "scope": "stage total table or final total table publication",
        "current_status": "requires_separate_ready_review",
        "required_before": "stage_or_final_total_table_release",
    },
    {
        "gate_id": "g10_destructive_cleanup_gate",
        "scope": "any destructive cleanup, deletion, move, or archive action deferred by G10",
        "current_status": "requires_separate_ready_review",
        "required_before": "new_file_move_delete_archive",
    },
    {
        "gate_id": "source_document_passage_merge_policy_gate",
        "scope": "source document and passage merge policy changes or business-table writes",
        "current_status": "requires_separate_ready_review",
        "required_before": "source_passage_business_table_write",
    },
    {
        "gate_id": "evidence_cluster_anchor_relationship_followup_gates",
        "scope": "evidence, cluster, anchor, and relationship follow-up writes or merge policies",
        "current_status": "requires_separate_ready_review",
        "required_before": "evidence_cluster_anchor_relationship_write",
    },
    {
        "gate_id": "epic2_separate_ready_review",
        "scope": "Epic 2 entry or active-epic transition",
        "current_status": "requires_separate_ready_review",
        "required_before": "epic2_entry",
    },
    {
        "gate_id": "epic3_separate_ready_review",
        "scope": "Epic 3 entry or active-epic transition",
        "current_status": "requires_separate_ready_review",
        "required_before": "epic3_entry",
    },
)

BLOCKED_OUTPUTS = (
    "new_subitem_formal_scores",
    "new_subitem_formal_rankings",
    "stage_total_table",
    "final_total_table",
    "cross_subitem_leaderboard",
    "new_file_move_delete_archive",
    "source_passage_business_table_write",
    "evidence_cluster_anchor_relationship_write",
    "epic2_entry",
    "epic3_entry",
)


def _handoff_report() -> dict[str, Any]:
    return handoff.build_completion_report()


def _gate_rows() -> list[dict[str, Any]]:
    return [
        {
            **gate,
            "separate_ready_review_required": True,
            "approved_in_this_package": False,
            "executed_in_this_package": False,
        }
        for gate in FOLLOWUP_GATES
    ]


def build_gates_report() -> dict[str, Any]:
    handoff_report = _handoff_report()
    handoff_state = handoff_report["current_state"]
    gates = _gate_rows()
    all_gates_blocked_for_separate_review = all(
        gate["current_status"] == "requires_separate_ready_review"
        and gate["separate_ready_review_required"]
        and not gate["approved_in_this_package"]
        and not gate["executed_in_this_package"]
        for gate in gates
    )
    ready = (
        handoff_state["g10_4_completion_verification_handoff_ready"]
        and handoff_report["next_required_work"] == "post_g10_ready_for_followup_gates"
        and handoff_report["prerequisite_pr"] == 344
        and all_gates_blocked_for_separate_review
    )

    return {
        "mode": "gates-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "handoff_issue": HANDOFF_ISSUE,
        "handoff_pr": HANDOFF_PR,
        "handoff_merge_commit": HANDOFF_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_batch_payloads": True,
        "does_not_read_generated_export_contents": True,
        "does_not_write_business_tables": True,
        "does_not_move_delete_or_archive_files": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "does_not_publish_leaderboards": True,
        "does_not_enter_epic2_or_epic3": True,
        "current_state": {
            "current_phase": "post_g10_ready_for_followup_gates_ready",
            "active_epic": EPIC_ISSUE,
            "post_g10_ready_for_followup_gates_ready": ready,
            "post_g10_followup_gates_package": PACKAGE_VERSION,
            "post_g10_handoff_pr": HANDOFF_PR,
            "post_g10_handoff_merge_commit": HANDOFF_MERGE_COMMIT,
            "post_g10_followup_gate_count": len(gates),
            "post_g10_followup_gates_requiring_separate_review": len(gates),
            "post_g10_next_action": NEXT_REQUIRED_WORK,
            "epic5_per_subitem_g9_publication_gate_approved": False,
            "epic5_cross_subitem_leaderboard_publication_gate_approved": False,
            "epic5_stage_or_final_total_table_publication_gate_approved": False,
            "g10_destructive_cleanup_gate_approved": False,
            "source_document_passage_merge_policy_gate_approved": False,
            "evidence_cluster_anchor_relationship_followup_gates_approved": False,
            "epic2_separate_ready_review_approved": False,
            "epic3_separate_ready_review_approved": False,
            "g10_destructive_cleanup_started": False,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "handoff_summary": {
            "g10_4_completion_verification_handoff_ready": handoff_state[
                "g10_4_completion_verification_handoff_ready"
            ],
            "next_required_work": handoff_report["next_required_work"],
            "registry_dangling_references": handoff_state["g10_registry_dangling_references"],
            "g10_report_complete": handoff_state["g10_report_complete"],
            "g10_destructive_cleanup_started": handoff_state["g10_destructive_cleanup_started"],
        },
        "followup_gates": gates,
        "changed_paths_manifest": list(PACKAGE_CHANGED_PATHS),
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "next_required_work": NEXT_REQUIRED_WORK,
    }


def render_gates_md() -> str:
    report = build_gates_report()
    state = report["current_state"]
    lines = [
        "# Post-G10 Follow-Up Gates Readiness",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- handoff_issue: `#{report['handoff_issue']}`",
        f"- handoff_pr: `#{report['handoff_pr']}`",
        f"- current_phase: `{state['current_phase']}`",
        f"- post_g10_ready_for_followup_gates_ready: `{str(state['post_g10_ready_for_followup_gates_ready']).lower()}`",
        f"- post_g10_followup_gate_count: `{state['post_g10_followup_gate_count']}`",
        f"- post_g10_next_action: `{state['post_g10_next_action']}`",
        "",
        "## Follow-Up Gates",
        "",
    ]
    for gate in report["followup_gates"]:
        lines.append(
            f"- `{gate['gate_id']}`: `{gate['current_status']}`, "
            f"required_before=`{gate['required_before']}`"
        )

    lines.extend(["", "## Blocked Outputs", ""])
    for item in report["blocked_outputs"]:
        lines.append(f"- `{item}`")

    lines.extend(["", "## Changed Paths Manifest", ""])
    for path in report["changed_paths_manifest"]:
        lines.append(f"- `{path}`")

    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the post-G10 follow-up gates readiness report.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--gates-report", action="store_true")
    mode.add_argument("--gates-md", action="store_true")
    args = parser.parse_args(argv)

    if args.gates_md:
        sys.stdout.write(render_gates_md())
        return 0

    sys.stdout.write(report_as_json(build_gates_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
