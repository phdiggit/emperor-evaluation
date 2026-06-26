from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.shared.scoring_engine_contracts import (  # noqa: E402
    EvidenceProfile,
    FormalGradeResult,
    NoOverridePolicy,
    ScorePublicationResult,
    ScoreRange,
    SubitemProfile,
)


PACKAGE_VERSION = "epic5-scoring-engine-interface-contract-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
SCOPE_PR = 313
SCOPE_MERGE_COMMIT = "07af05b3b80311bb19ba642c815a2ea7a517767f"
SUPPORTED_MODES = ("contract-report", "interface-md")


CONTRACT_OBJECTS = [
    {
        "name": "ScoreRange",
        "purpose": "Bound a deterministic candidate value inside a subitem score cap.",
        "class": ScoreRange,
    },
    {
        "name": "SubitemProfile",
        "purpose": "Describe subitem cap, versions, gate status, and total/leaderboard release locks.",
        "class": SubitemProfile,
    },
    {
        "name": "EvidenceProfile",
        "purpose": "Carry normalized positive/negative evidence profile signals without scoring side effects.",
        "class": EvidenceProfile,
    },
    {
        "name": "NoOverridePolicy",
        "purpose": "Lock person-specific override, manual final grade, and manual final score to false.",
        "class": NoOverridePolicy,
    },
    {
        "name": "FormalGradeResult",
        "purpose": "Bind a formal grade, score range, deterministic candidate value, and algorithm version.",
        "class": FormalGradeResult,
    },
    {
        "name": "ScorePublicationResult",
        "purpose": "Represent only a G9-approved subitem value and subitem-internal rank.",
        "class": ScorePublicationResult,
    },
]


def _field_names(contract_class: type[object]) -> list[str]:
    return [field.name for field in fields(contract_class)]


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "scope_pr": SCOPE_PR,
        "scope_merge_commit": SCOPE_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_write_business_tables": True,
        "does_not_publish_scores": True,
        "current_state": {
            "current_phase": "epic5_minimum_interface_contract_package_ready",
            "active_epic": EPIC_ISSUE,
            "epic5_boundary_scope_pr": SCOPE_PR,
            "epic5_boundary_scope_merge_commit": SCOPE_MERGE_COMMIT,
            "epic5_minimum_interface_contract_ready": True,
            "positive_benefit_total": 1500,
            "stage_or_final_total_table_released": False,
            "cross_subitem_leaderboard_released": False,
            "new_subitem_formal_scores_released": False,
            "epic_2_entered": False,
            "epic_3_entered": False,
        },
        "contract_objects": [
            {
                "name": item["name"],
                "purpose": item["purpose"],
                "fields": _field_names(item["class"]),
            }
            for item in CONTRACT_OBJECTS
        ],
        "validation_invariants": [
            "score_range_lower_non_negative",
            "score_range_upper_not_above_subitem_cap",
            "candidate_value_inside_score_range",
            "formal_grade_algorithm_version_matches_subitem_profile",
            "person_specific_override_disallowed",
            "manual_final_grade_disallowed",
            "manual_final_score_disallowed",
            "publication_requires_g9",
            "publication_score_equals_deterministic_candidate",
            "publication_rank_positive",
            "subitem_g9_does_not_release_stage_or_final_total_table",
            "subitem_g9_does_not_release_cross_subitem_leaderboard",
        ],
        "report_templates": {
            "impact_report": [
                "subitem_profile",
                "evidence_profile_summary",
                "formal_grade_result_without_publication_value_when_g8_only",
                "boundary_invariants",
                "blocked_publication_outputs",
            ],
            "publication_report": [
                "subitem_profile",
                "formal_grade_result",
                "score_publication_result",
                "no_override_policy",
                "stage_or_final_total_table_released_false",
                "cross_subitem_leaderboard_released_false",
            ],
        },
        "blocked_outputs": [
            "new_subitem_formal_scores_without_per_subitem_g9",
            "stage_total_table",
            "final_total_table",
            "cross_subitem_leaderboard",
            "rule_display_dictionary_canonical_write",
            "source_document_passage_business_table_write",
            "evidence_cluster_anchor_relationship_business_table_write",
            "epic_2_or_epic_3_entry",
        ],
        "next_required_work": "epic5_pilot_subitem_profile_contract_package",
    }


def render_interface_md() -> str:
    report = build_contract_report()
    lines = [
        "# Epic5 Scoring Engine Interface Contract",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- scope_pr: `#{report['scope_pr']}`",
        f"- scope_merge_commit: `{report['scope_merge_commit']}`",
        "- This package defines interfaces only; it does not publish scores.",
        "",
        "## Contract Objects",
        "",
    ]
    for item in report["contract_objects"]:
        fields_text = ", ".join(f"`{field}`" for field in item["fields"])
        lines.append(f"- `{item['name']}`: {item['purpose']} Fields: {fields_text}.")

    lines.extend(["", "## Validation Invariants", ""])
    for item in report["validation_invariants"]:
        lines.append(f"- `{item}`")

    lines.extend(["", "## Blocked Outputs", ""])
    for item in report["blocked_outputs"]:
        lines.append(f"- `{item}`")

    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the Epic5 scoring engine interface contract package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--interface-md", action="store_true")
    args = parser.parse_args(argv)

    if args.interface_md:
        sys.stdout.write(render_interface_md())
        return 0

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
