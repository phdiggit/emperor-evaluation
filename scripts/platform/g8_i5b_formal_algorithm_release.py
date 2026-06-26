from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


from export.dimension_adapters.i5b_people_delegation import adapter as i5b_adapter  # noqa: E402
from export.dimension_adapters.i5b_people_delegation.formal_algorithm import (  # noqa: E402
    FORMAL_ALGORITHM_VERSION,
    FORMAL_GRADE_ENUM,
    FORMAL_RULE_VERSION,
    FORMAL_SUBITEM_MAX_SCORE,
    compute_formal_algorithm_result,
    formal_algorithm_mapping_rows,
)


PACKAGE_VERSION = "g8-i5b-formal-algorithm-release-v1"
G8_APPROVAL_COMMENT = 4809210729
G7_RULE_CHANGE_PR = 308
G7_RULE_CHANGE_MERGE_COMMIT = "ae5d9730ab716c110e521b0bf9076a4470e0123c"
ISSUE = 211
PARENT_ROADMAP = 287


def build_algorithm_report() -> dict[str, Any]:
    return {
        "mode": "algorithm-report",
        "package_version": PACKAGE_VERSION,
        "issue": ISSUE,
        "parent_roadmap": PARENT_ROADMAP,
        "gate": "G8_FORMAL_ALGORITHM_RELEASE",
        "gate_status": "approved_algorithm_released",
        "g8_approval_comment": G8_APPROVAL_COMMENT,
        "g7_rule_change_pr": G7_RULE_CHANGE_PR,
        "g7_rule_change_merge_commit": G7_RULE_CHANGE_MERGE_COMMIT,
        "formal_algorithm_version": FORMAL_ALGORITHM_VERSION,
        "formal_rule_version": FORMAL_RULE_VERSION,
        "formal_grade_enum": list(FORMAL_GRADE_ENUM),
        "formal_subitem_max_score": str(FORMAL_SUBITEM_MAX_SCORE),
        "mapping_rows": formal_algorithm_mapping_rows(),
        "deterministic_rerun_contract": {
            "inputs": [
                "auto_band_direction",
                "confidence",
                "coverage_dimension_count",
                "positive_three_core_coverage",
                "negative_boundary_tier",
                "negative_boundary_blocking",
                "has_extreme_negative_core",
            ],
            "person_specific_override_allowed": False,
            "manual_final_grade_allowed": False,
            "manual_final_score_allowed": False,
        },
        "release_state": {
            "formal_algorithm_released": True,
            "formal_score_values_released": False,
            "formal_ranking_released": False,
        },
        "followup_gate_boundaries": {
            "formal_score_values_or_ranking_publication": "G9",
            "destructive_cleanup": "G10",
            "source_passages_business_tables": "followup_source_document_passage_gate",
            "evidence_cluster_anchor_relationship_tables": "followup_relationship_gate",
            "epic_2_entry": "separate_ready_review",
        },
    }


def _stable_digest(payload: object) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def build_impact_report(person_reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    formal_results = [compute_formal_algorithm_result(report) for report in person_reports]
    grade_counts = Counter(result["formal_grade"] for result in formal_results)
    direction_counts = Counter(str(report.get("auto_band_direction") or "") for report in person_reports)
    regression_payload = [
        {
            "auto_band_direction": report.get("auto_band_direction"),
            "confidence": report.get("confidence"),
            "coverage_dimension_count": report.get("coverage_dimension_count"),
            "positive_three_core_coverage": report.get("positive_three_core_coverage"),
            "negative_boundary_tier": report.get("negative_boundary_tier"),
            "negative_boundary_blocking": report.get("negative_boundary_blocking"),
            "formal_grade": result["formal_grade"],
            "score_range_45": result["score_range_45"],
        }
        for report, result in zip(person_reports, formal_results, strict=True)
    ]
    return {
        "mode": "impact-report",
        "package_version": PACKAGE_VERSION,
        "formal_algorithm_version": FORMAL_ALGORITHM_VERSION,
        "evaluated_person_count": len(person_reports),
        "formal_grade_distribution": {grade: grade_counts.get(grade, 0) for grade in FORMAL_GRADE_ENUM},
        "auto_band_direction_distribution": dict(sorted(direction_counts.items())),
        "deterministic_rerun_fingerprint": _stable_digest(regression_payload),
        "person_level_rows_suppressed_until_g9": True,
        "formal_score_values_released": False,
        "formal_ranking_released": False,
        "contains_person_formal_score_values": False,
        "contains_ranking_or_leaderboard": False,
    }


def build_current_impact_report() -> dict[str, Any]:
    config = i5b_adapter.config_loaders.get_i5b_trial_config()
    targets = list(config.get("targets") or [])
    evidence_cards = i5b_adapter.read_jsonl(i5b_adapter.DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = i5b_adapter.read_jsonl(i5b_adapter.DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    person_reports = [i5b_adapter.evaluate_person(person, evidence_clusters, evidence_lookup) for person in targets]
    return build_impact_report(person_reports)


def render_algorithm_md() -> str:
    report = build_algorithm_report()
    lines = [
        "# G8 Fifth Item B Formal Algorithm Release",
        "",
        f"- package_version: `{PACKAGE_VERSION}`",
        f"- algorithm_version: `{FORMAL_ALGORITHM_VERSION}`",
        f"- rule_version: `{FORMAL_RULE_VERSION}`",
        f"- gate_status: `{report['gate_status']}`",
        "- formal_score_values_released: `false`",
        "- formal_ranking_released: `false`",
        "",
        "## Formal Grade Enum",
        "",
    ]
    for grade in FORMAL_GRADE_ENUM:
        lines.append(f"- `{grade}`")
    lines.extend(["", "## Gate Boundaries", ""])
    for key, value in report["followup_gate_boundaries"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the G8-approved Fifth Item B formal algorithm release reports.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--algorithm-report", action="store_true")
    mode.add_argument("--impact-report", action="store_true")
    mode.add_argument("--algorithm-md", action="store_true")
    args = parser.parse_args(argv)

    if args.impact_report:
        sys.stdout.write(report_as_json(build_current_impact_report()))
        sys.stdout.write("\n")
        return 0
    if args.algorithm_md:
        sys.stdout.write(render_algorithm_md())
        return 0

    sys.stdout.write(report_as_json(build_algorithm_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
