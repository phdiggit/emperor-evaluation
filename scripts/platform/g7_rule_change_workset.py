from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PACKAGE_VERSION = "g7-rule-change-workset-v1"
WORKSET_ID = "issue-292-g7-rule-change-workset-1"
G7_SCOPE_PR = 306
G7_SCOPE_MERGE_COMMIT = "cc8d62c53dc25be7cd808bb56b74d35592e97073"
G6_OBSERVATION_PR = 305
G6_OBSERVATION_MERGE_COMMIT = "96c231afe80ebeebcdf7cce76958e3302af9799b"
SUPPORTED_MODES = ("workset-report", "workset-md")


def build_workset_report() -> dict[str, Any]:
    return {
        "mode": "workset-report",
        "package_version": PACKAGE_VERSION,
        "workset_id": WORKSET_ID,
        "gate": "G7_SCORING_RULE_CHANGE",
        "gate_status": "approved_workset_ready",
        "g7_scope_pr": G7_SCOPE_PR,
        "g7_scope_merge_commit": G7_SCOPE_MERGE_COMMIT,
        "g6_observation_pr": G6_OBSERVATION_PR,
        "g6_observation_merge_commit": G6_OBSERVATION_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_read_rule_sources": True,
        "does_not_modify_rule_sources": True,
        "does_not_write_business_tables": True,
        "candidate_rule_paths": [
            {
                "path": "docs/皇帝综合评价体系评分标准.md",
                "role": "top_level_standard",
                "change_requires_explicit_diff_summary": True,
            },
            {
                "path": "docs/分项规则/**",
                "role": "subitem_rule_sources",
                "change_requires_subitem_impact_scope": True,
            },
            {
                "path": "docs/证据规则/**",
                "role": "evidence_rule_sources",
                "change_requires_adjudication_boundary_summary": True,
            },
        ],
        "rule_change_pr_required_sections": [
            "changed_rule_paths",
            "before_after_rule_diff_summary",
            "impact_scope_statement",
            "boundary_regression_tests",
            "algorithm_and_publication_gates_remain_blocked",
        ],
        "workset_review_checklist": [
            "rule_source_paths_are_explicit",
            "diff_summary_does_not_replace_full_rule_text",
            "impact_scope_names_affected_subitems_without_output_values",
            "tests_cover_allowed_and_blocked_boundaries",
            "no_business_data_or_export_files_are_modified",
        ],
        "blocked_until_followup_gate": {
            "formal_algorithm_release": "G8",
            "formal_output_values_or_publication": "G9",
            "destructive_cleanup": "G10",
            "epic_2_entry": "separate_ready_review",
            "source_passages_business_tables": "followup_source_document_passage_gate",
            "evidence_cluster_anchor_relationship_tables": "followup_relationship_gate",
        },
        "ready_for_next_pr": "g7_rule_change_implementation_pr",
        "next_required_user_gate": "G8",
    }


def render_workset_md() -> str:
    report = build_workset_report()
    lines = [
        "# G7 Rule Change Workset",
        "",
        f"- workset_id: `{report['workset_id']}`",
        f"- gate_status: `{report['gate_status']}`",
        "- This package declares the required artifacts for the next rule-change PR.",
        "- This package does not read or modify rule sources.",
        "",
        "## Candidate Rule Paths",
        "",
    ]
    for item in report["candidate_rule_paths"]:
        lines.append(f"- `{item['path']}`: `{item['role']}`")
    lines.extend(["", "## Required Sections", ""])
    for item in report["rule_change_pr_required_sections"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Review Checklist", ""])
    for item in report["workset_review_checklist"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Blocked Until Follow-Up Gate", ""])
    for key, value in report["blocked_until_followup_gate"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the Epic 1 G7 rule change workset.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--workset-report", action="store_true")
    mode.add_argument("--workset-md", action="store_true")
    args = parser.parse_args(argv)

    if args.workset_md:
        sys.stdout.write(render_workset_md())
        return 0

    sys.stdout.write(report_as_json(build_workset_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
