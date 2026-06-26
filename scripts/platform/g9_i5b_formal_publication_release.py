from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
    FORMAL_PUBLICATION_GATE,
    FORMAL_RULE_VERSION,
    FORMAL_SUBITEM_MAX_SCORE,
    build_formal_publication_rows,
)
from scripts.platform import g8_i5b_formal_algorithm_release as g8_release  # noqa: E402


PACKAGE_VERSION = "g9-i5b-formal-publication-release-v1"
G9_APPROVAL_COMMENT = 4809664701
G8_RELEASE_PR = 309
G8_RELEASE_HEAD_SHA = "7575c5571eaa3f5f6c5990fd67c170324b2344a3"
G8_RELEASE_MERGE_COMMIT = "05c24d084fb36a15c2539d41a0e5a8445e32d035"
ISSUE = 211
PARENT_ROADMAP = 287


def _stable_digest(payload: object) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def build_publication_report(person_reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    publication_rows = build_formal_publication_rows(list(person_reports))
    regression_payload = [
        {
            "person": row["person"],
            "auto_band_direction": row["auto_band_direction"],
            "formal_grade": row["formal_grade"],
            "formal_score_value_45": row["formal_score_value_45"],
            "formal_rank": row["formal_rank"],
            "algorithm_version": row["algorithm_version"],
            "rule_version": row["rule_version"],
        }
        for row in publication_rows
    ]
    return {
        "mode": "publication-report",
        "package_version": PACKAGE_VERSION,
        "issue": ISSUE,
        "parent_roadmap": PARENT_ROADMAP,
        "gate": f"{FORMAL_PUBLICATION_GATE}_FORMAL_SCORE_RANKING_PUBLICATION",
        "gate_status": "approved_formal_scores_and_ranking_released",
        "g9_approval_comment": G9_APPROVAL_COMMENT,
        "g8_release_pr": G8_RELEASE_PR,
        "g8_release_head_sha": G8_RELEASE_HEAD_SHA,
        "g8_release_merge_commit": G8_RELEASE_MERGE_COMMIT,
        "formal_algorithm_version": FORMAL_ALGORITHM_VERSION,
        "formal_rule_version": FORMAL_RULE_VERSION,
        "formal_subitem_max_score": str(FORMAL_SUBITEM_MAX_SCORE),
        "score_framework": g8_release.build_algorithm_report()["score_framework"],
        "publication_rows": publication_rows,
        "evaluated_person_count": len(publication_rows),
        "deterministic_rerun_fingerprint": _stable_digest(regression_payload),
        "release_state": {
            "formal_algorithm_released": True,
            "formal_score_values_released": True,
            "formal_ranking_released": True,
            "contains_person_formal_score_values": True,
            "contains_ranking_or_leaderboard": True,
            "contains_stage_or_final_total_table": False,
        },
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
            "ranking_basis": "formal_score_value_45_desc_then_grade_then_person",
            "person_specific_override_allowed": False,
            "manual_final_grade_allowed": False,
            "manual_final_score_allowed": False,
        },
        "remaining_gate_boundaries": {
            "stage_or_final_total_table": "not_in_this_pr",
            "destructive_cleanup": "G10",
            "source_passages_business_tables": "followup_source_document_passage_gate",
            "evidence_cluster_anchor_relationship_tables": "followup_relationship_gate",
            "epic_2_entry": "separate_ready_review",
        },
    }


def build_current_publication_report() -> dict[str, Any]:
    config = i5b_adapter.config_loaders.get_i5b_trial_config()
    targets = list(config.get("targets") or [])
    evidence_cards = i5b_adapter.read_jsonl(i5b_adapter.DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = i5b_adapter.read_jsonl(i5b_adapter.DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    person_reports = [i5b_adapter.evaluate_person(person, evidence_clusters, evidence_lookup) for person in targets]
    return build_publication_report(person_reports)


def render_publication_md() -> str:
    report = build_current_publication_report()
    lines = [
        "# G9 Fifth Item B Formal Score And Ranking Publication",
        "",
        f"- package_version: `{PACKAGE_VERSION}`",
        f"- algorithm_version: `{FORMAL_ALGORITHM_VERSION}`",
        f"- rule_version: `{FORMAL_RULE_VERSION}`",
        f"- gate_status: `{report['gate_status']}`",
        "- formal_score_values_released: `true`",
        "- formal_ranking_released: `true`",
        "- contains_stage_or_final_total_table: `false`",
        f"- positive_benefit_total: `{report['score_framework']['positive_benefit_total']}`",
        "",
        "## Publication Rows",
        "",
        "| rank | person | formal_grade | formal_score_value_45 | auto_band_direction |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["publication_rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["formal_rank"]),
                    str(row["person"]),
                    str(row["formal_grade"]),
                    str(row["formal_score_value_45"]),
                    str(row["auto_band_direction"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Remaining Boundaries", ""])
    for key, value in report["remaining_gate_boundaries"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the G9-approved Fifth Item B formal score/ranking reports.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--publication-report", action="store_true")
    mode.add_argument("--publication-md", action="store_true")
    args = parser.parse_args(argv)

    if args.publication_md:
        sys.stdout.write(render_publication_md())
        return 0

    sys.stdout.write(report_as_json(build_current_publication_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
