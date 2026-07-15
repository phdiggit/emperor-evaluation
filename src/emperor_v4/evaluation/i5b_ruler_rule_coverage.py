from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.i5b_scoring_policy import RULE_ORDER


SCHEMA_VERSION = "i5b-ruler-rule-coverage-report-v1"
MANIFEST_SCHEMA_VERSION = "i5b-ruler-rule-coverage-manifest-v1"
POLICY_VERSION = "i5b-historical-coverage-gate-v1"
PROGRESS_STATES = {"not_started", "in_progress", "complete"}
COVERAGE_STATES = {
    "unassessed",
    "in_progress",
    "coverage_complete",
    "insufficient_evidence",
}
WORKSET_STATES = {
    "absent",
    "workset_projection_complete",
    "partial_workset_projection",
    "partial_insufficient_projection",
}


def _hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _rows(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} may contain only objects")
    return list(value)


def evaluate_i5b_ruler_rule_coverage(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("ruler-rule coverage manifest schema mismatch")
    if manifest.get("coverage_policy_version") != POLICY_VERSION:
        raise ValueError("ruler-rule coverage policy mismatch")
    ruler = str(manifest.get("ruler") or "")
    ruler_ref = str(manifest.get("ruler_ref") or "")
    if not ruler or not ruler_ref:
        raise ValueError("ruler-rule coverage manifest requires ruler identity")

    rows = _rows(manifest.get("rules"), "coverage rules")
    by_rule = {str(row.get("rule_code")): row for row in rows}
    if set(by_rule) != set(RULE_ORDER) or len(rows) != len(RULE_ORDER):
        raise ValueError("coverage manifest must contain exactly five I5B rules")

    results: list[dict[str, Any]] = []
    for rule_code in RULE_ORDER:
        row = by_rule[rule_code]
        workset_status = str(row.get("workset_projection_status") or "")
        coverage_status = str(row.get("historical_coverage_status") or "")
        inventory_status = str(row.get("candidate_inventory_status") or "")
        positive_search = str(row.get("positive_search_status") or "")
        negative_search = str(row.get("negative_search_status") or "")
        disposition_status = str(row.get("candidate_disposition_status") or "")
        review_status = str(row.get("review_status") or "")
        unresolved = [str(item) for item in row.get("unresolved") or []]
        coverage_outcome = row.get("coverage_outcome")
        inventory_ref = str(row.get("candidate_inventory_ref") or "")
        inventory_sha256 = str(row.get("candidate_inventory_sha256") or "")
        accepted_refs = [str(item) for item in row.get("accepted_unit_refs") or []]
        consumed_refs = [str(item) for item in row.get("consumed_unit_refs") or []]
        attestation_refs = [str(item) for item in row.get("attestation_refs") or []]
        existing_units = _rows(row.get("existing_workset_units") or [], "existing workset units")
        legacy_candidate_sources = _rows(
            row.get("legacy_candidate_sources") or [], "legacy candidate sources"
        )
        unit_refs = [str(item.get("unit_ref") or "") for item in existing_units]
        if any(not ref for ref in unit_refs) or len(set(unit_refs)) != len(unit_refs):
            raise ValueError(f"{rule_code} existing workset unit identities are invalid")
        if workset_status not in WORKSET_STATES:
            raise ValueError(f"{rule_code} workset projection status is invalid")
        if coverage_status not in COVERAGE_STATES:
            raise ValueError(f"{rule_code} historical coverage status is invalid")
        if any(
            state not in PROGRESS_STATES
            for state in (inventory_status, positive_search, negative_search, disposition_status)
        ):
            raise ValueError(f"{rule_code} coverage progress status is invalid")
        if review_status not in {"draft", "human_frozen"}:
            raise ValueError(f"{rule_code} coverage review status is invalid")
        if coverage_status == "coverage_complete":
            closed = (
                review_status == "human_frozen"
                and workset_status == "workset_projection_complete"
                and not unresolved
                and all(
                    state == "complete"
                    for state in (
                        inventory_status,
                        positive_search,
                        negative_search,
                        disposition_status,
                    )
                )
                and inventory_ref
                and len(inventory_sha256) == 64
                and accepted_refs == consumed_refs
                and attestation_refs
                and (
                    (accepted_refs and coverage_outcome == "materials_found")
                    or (
                        not accepted_refs
                        and coverage_outcome == "audited_no_applicable_material"
                    )
                )
            )
            if not closed:
                raise ValueError(
                    f"{rule_code} may be coverage_complete only after a frozen closed review"
                )
        results.append(
            {
                "rule_code": rule_code,
                "workset_projection_status": workset_status,
                "workset_refs": [str(item) for item in row.get("workset_refs") or []],
                "existing_workset_units": [dict(item) for item in existing_units],
                "legacy_candidate_sources": [dict(item) for item in legacy_candidate_sources],
                "historical_coverage_status": coverage_status,
                "coverage_outcome": coverage_outcome,
                "candidate_population_policy": str(
                    row.get("candidate_population_policy") or ""
                ),
                "candidate_inventory_ref": inventory_ref or None,
                "candidate_inventory_sha256": inventory_sha256 or None,
                "accepted_unit_refs": accepted_refs,
                "consumed_unit_refs": consumed_refs,
                "candidate_inventory_status": inventory_status,
                "positive_search_status": positive_search,
                "negative_search_status": negative_search,
                "candidate_disposition_status": disposition_status,
                "review_status": review_status,
                "attestation_refs": attestation_refs,
                "unresolved": unresolved,
                "eligible_for_historical_raw_signal": (
                    coverage_status == "coverage_complete"
                    and workset_status == "workset_projection_complete"
                ),
            }
        )

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": "historical_coverage_not_complete",
        "ruler": ruler,
        "ruler_ref": ruler_ref,
        "scope": dict(manifest.get("scope") or {}),
        "summary": {
            "rule_count": len(results),
            "workset_projection_complete_rule_count": sum(
                row["workset_projection_status"] == "workset_projection_complete"
                for row in results
            ),
            "historical_coverage_complete_rule_count": sum(
                row["historical_coverage_status"] == "coverage_complete"
                for row in results
            ),
            "eligible_rule_count": sum(
                row["eligible_for_historical_raw_signal"] for row in results
            ),
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_scoring_allowed": False,
        },
        "rules": results,
        "declarations": {
            "workset_projection_implies_historical_coverage": False,
            "missing_candidate_treated_as_zero": False,
            "opened_regression_used_as_new_qualification": False,
            "formal_scoring_allowed": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report
