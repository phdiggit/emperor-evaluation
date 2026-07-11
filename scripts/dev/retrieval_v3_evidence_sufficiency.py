from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Mapping, Sequence


def text(value: Any) -> str:
    return str(value or "").strip()


def _coverage_by_emperor(coverage: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in coverage.get("objects") or []:
        grouped[text(row.get("emperor_name"))].append(row)
    return grouped


def _score_details_by_emperor(details: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        text(row.get("emperor_name")): row
        for row in details.values()
        if isinstance(row, Mapping) and text(row.get("emperor_name"))
    }


def build_evidence_sufficiency(
    *, coverage: Mapping[str, Any], score_details: Mapping[str, Any], emperors: Sequence[str]
) -> dict[str, Any]:
    coverage_rows = _coverage_by_emperor(coverage)
    details_by_emperor = _score_details_by_emperor(score_details)
    rows: list[dict[str, Any]] = []
    for emperor in emperors:
        objects = coverage_rows.get(text(emperor), [])
        detail = details_by_emperor.get(text(emperor), {})
        calc = detail.get("calc_detail") or {}
        materials = [row for row in calc.get("materials") or [] if isinstance(row, Mapping)]
        claim_keys = {text(row.get("claim_key")) for row in materials if text(row.get("claim_key"))}
        event_groups = {
            text(key) for row in materials for key in row.get("event_group_keys") or [] if text(key)
        }
        source_documents = {
            text(code) for row in materials for code in row.get("source_document_codes") or [] if text(code)
        }
        ungrouped_claims = {
            text(row.get("claim_key"))
            for row in materials
            if text(row.get("claim_key")) and not (row.get("event_group_keys") or [])
        }
        object_scores = calc.get("object_side_scores") or {}
        positive_objects = set((object_scores.get("positive") or {}).keys())
        negative_objects = set((object_scores.get("negative") or {}).keys())
        expected_count = sum(int(row.get("expected_event_count") or 0) for row in objects)
        covered_expected = sum(int(row.get("covered_expected_event_count") or 0) for row in objects)
        if expected_count == 0:
            status = "unassessed_missing_expected_event_inventory"
            blockers = ["expected_event_inventory_missing"]
        elif ungrouped_claims:
            status = "provisional_event_group_incomplete"
            blockers = ["scored_claims_missing_event_group"]
        else:
            status = "ready_for_calibration"
            blockers = []
        rows.append({
            "emperor_name": text(emperor),
            "confidence_status": status,
            "calibration_blockers": blockers,
            "score_adjustment_applied": False,
            "raw_claim_count": sum(int(row.get("active_claim_count") or 0) for row in objects),
            "claim_event_group_membership_count": sum(int(row.get("event_group_count") or 0) for row in objects),
            "scored_material_count": len(materials),
            "scored_claim_count": len(claim_keys),
            "scored_event_group_count": len(event_groups),
            "ungrouped_scored_claim_count": len(ungrouped_claims),
            "independent_scored_source_document_count": len(source_documents),
            "scored_object_count": len(positive_objects | negative_objects),
            "positive_scored_object_count": len(positive_objects),
            "negative_scored_object_count": len(negative_objects),
            "expected_event_count": expected_count,
            "covered_expected_event_count": covered_expected,
            "expected_event_coverage": (
                round(covered_expected / expected_count, 4) if expected_count else None
            ),
        })
    return {
        "ok": True,
        "mode": "diagnostic_only_no_score_adjustment",
        "score_adjustment_applied": False,
        "claim_quantity_is_score_factor": False,
        "effective_evidence_definition": (
            "unique scored event groups with independent source-document and object diversity; "
            "raw claim count is diagnostic only"
        ),
        "confidence_formula_status": (
            "blocked_until_expected-event inventory and scored event-group lineage are complete"
        ),
        "emperors": rows,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 证据充分度诊断", "",
        "> 本报告不修改正式分数；raw claim 数量不作为加分因子。", "",
        "| 皇帝 | 状态 | raw claims | scored materials | scored claims | event groups | ungrouped | source docs | objects | expected coverage |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("emperors") or []:
        coverage = row.get("expected_event_coverage")
        lines.append(
            f"| {row.get('emperor_name')} | {row.get('confidence_status')} | {row.get('raw_claim_count')} | "
            f"{row.get('scored_material_count')} | {row.get('scored_claim_count')} | "
            f"{row.get('scored_event_group_count')} | {row.get('ungrouped_scored_claim_count')} | "
            f"{row.get('independent_scored_source_document_count')} | {row.get('scored_object_count')} | "
            f"{coverage if coverage is not None else 'unassessed'} |"
        )
    lines.extend(["", "## 约束", "", "- score_adjustment_applied: `false`", "- claim_quantity_is_score_factor: `false`"])
    return "\n".join(lines) + "\n"
