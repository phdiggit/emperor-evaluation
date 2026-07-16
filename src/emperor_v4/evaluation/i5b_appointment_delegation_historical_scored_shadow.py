from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.appointment_delegation_scoring import canonical_hash
from emperor_v4.evaluation.appointment_delegation_v3_parity import (
    FACTOR_NAMES,
    FACTOR_OPTIONS,
    FACTOR_SCHEMA_VERSION,
    JUDGMENT_POLICY_VERSION,
    SCORING_FORMULA_VERSION,
    aggregate_rulers,
    build_score_contribution,
    evaluate_factor_proposal,
    observation_fingerprint,
)
from emperor_v4.evaluation.i5b_assertion_episode_trace import (
    build_assertion_episode_trace,
)


SCHEMA_VERSION = "i5b-appointment-delegation-historical-scored-shadow-v1"


def _rows(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} may contain only objects")
    return list(value)


def _validate_factor_materials(
    unit: Mapping[str, Any], assertion_refs: set[str]
) -> None:
    materials = _rows(unit.get("factor_materials"), "factor_materials")
    if not materials:
        raise ValueError("appointment projection unit has no factor material")
    for material in materials:
        if material.get("side") not in {"positive", "negative"}:
            raise ValueError("appointment factor material side is invalid")
        factors = material.get("factors") or {}
        if set(factors) != set(FACTOR_NAMES):
            raise ValueError("appointment factor material does not close")
        for name in FACTOR_NAMES:
            factor = factors[name]
            if factor.get("option_code") not in FACTOR_OPTIONS[name]:
                raise ValueError(f"invalid appointment factor option: {name}")
            refs = {str(ref) for ref in factor.get("assertion_refs") or ()}
            if not refs or not refs <= assertion_refs:
                raise ValueError(f"appointment factor lineage is invalid: {name}")
            if not str(factor.get("reason") or "").strip():
                raise ValueError(f"appointment factor reason is missing: {name}")


def build_appointment_historical_scored_shadow(
    *,
    projection_payload: Mapping[str, Any],
    formal_acceptance: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        projection_payload.get("schema_version")
        != "i5b-appointment-delegation-historical-projection-input-v1"
        or projection_payload.get("status")
        != "human_frozen_historical_closeout_input"
        or projection_payload.get("rule_code") != "appointment_delegation"
    ):
        raise ValueError("appointment historical projection input is invalid")
    if not (formal_acceptance.get("declarations") or {}).get(
        "formal_fact_acceptance"
    ):
        raise ValueError("appointment historical scorer requires formal facts")

    formal_units = {
        str(row["unit_ref"]): row
        for row in _rows(formal_acceptance.get("units"), "formal units")
    }
    projection_units = _rows(projection_payload.get("units"), "projection units")
    if {str(row.get("unit_ref")) for row in projection_units} != set(formal_units):
        raise ValueError("appointment projection must close over formal units")

    trace_units: list[dict[str, Any]] = []
    judgments = []
    insufficient_projections: list[dict[str, Any]] = []
    for source_unit in projection_units:
        unit = deepcopy(dict(source_unit))
        unit_ref = str(unit["unit_ref"])
        assertion_refs = {
            str(row["assertion_code"])
            for row in formal_units[unit_ref].get("assertion_drafts") or ()
        }
        if unit.get("status") == "insufficient_projection":
            missing_inputs = sorted(
                {str(value) for value in unit.get("missing_inputs") or () if str(value)}
            )
            if not missing_inputs or unit.get("factor_materials") or unit.get(
                "factor_observations"
            ):
                raise ValueError(
                    "insufficient appointment projection must declare only missing inputs"
                )
            trace_units.append(
                {
                    "unit_ref": unit_ref,
                    "ruler": str(unit["ruler"]),
                    "subject": str(unit["person"]),
                    "side": str(unit["side"]),
                    "projection_basis": str(unit["projection_basis"]),
                }
            )
            insufficient_projections.append(
                {
                    "unit_ref": unit_ref,
                    "ruler": str(unit["ruler"]),
                    "person": str(unit["person"]),
                    "side": str(unit["side"]),
                    "object_ref": str(unit.get("object_ref") or ""),
                    "canonical_event_group": str(
                        unit.get("canonical_event_group") or ""
                    ),
                    "missing_inputs": missing_inputs,
                    "projection_basis": str(unit["projection_basis"]),
                }
            )
            continue
        if unit.get("status") not in {
            "projected",
            "human_frozen_historical_closeout_input",
        }:
            raise ValueError("appointment projection status is invalid")
        _validate_factor_materials(unit, assertion_refs)
        trace_units.append(
            {
                "unit_ref": unit_ref,
                "ruler": str(unit["ruler"]),
                "subject": str(unit["person"]),
                "side": str(unit["side"]),
                "projection_basis": str(unit["projection_basis"]),
            }
        )
        observation_unit = {
            "unit_ref": unit_ref,
            "ruler": str(unit["ruler"]),
            "person": str(unit["person"]),
            "factor_observations": deepcopy(unit["factor_observations"]),
        }
        proposal = {
            "unit_ref": unit_ref,
            "proposal_status": "human_reviewed_shadow",
            "reviewer": "i5b_two_rule_historical_closeout_review",
            "review_basis": "formal_fact_acceptance_and_v3_parity_mapping",
            "source_observation_fingerprint": observation_fingerprint(
                observation_unit
            ),
            "factor_materials": deepcopy(unit["factor_materials"]),
        }
        judgments.append(
            evaluate_factor_proposal(
                proposal,
                observation_unit,
                canonical_hash(formal_units[unit_ref]),
            )
        )

    trace = build_assertion_episode_trace(
        rule_code="appointment_delegation",
        trace_units=trace_units,
        assertion_payload=formal_acceptance,
    )
    contributions = [build_score_contribution(row) for row in judgments]
    aggregates = aggregate_rulers(contributions, ["李世民"])
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "appointment_delegation_historical_scored_shadow_complete",
        "rule_code": "appointment_delegation",
        "versions": {
            "factor_schema_version": FACTOR_SCHEMA_VERSION,
            "judgment_policy_version": JUDGMENT_POLICY_VERSION,
            "scoring_formula_version": SCORING_FORMULA_VERSION,
        },
        "input_refs": {
            "formal_acceptance_sha256": formal_acceptance.get("report_sha256"),
            "projection_input_version": projection_payload.get("input_version"),
        },
        "summary": {
            "formal_unit_count": len(formal_units),
            "judgment_count": len(judgments),
            "insufficient_projection_count": len(insufficient_projections),
            "score_contribution_count": len(contributions),
            "factor_material_count": sum(
                len(row["factor_materials"]) for row in judgments
            ),
            "traced_episode_count": trace["episode_count"],
            "traced_rule_evidence_unit_count": trace[
                "rule_evidence_unit_count"
            ],
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
        },
        "judgments": judgments,
        "insufficient_projections": insufficient_projections,
        "score_contributions": contributions,
        "ruler_aggregates": aggregates,
        "assertion_episode_reu_trace": trace,
        "declarations": {
            "formal_facts_consumed": True,
            "formal_scoring_allowed": False,
            "report_only": True,
            "cross_rule_duplicate_audit_required": True,
        },
    }
    report["report_sha256"] = canonical_hash(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build appointment-delegation historical scored shadow"
    )
    parser.add_argument("--projection", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    report = build_appointment_historical_scored_shadow(
        projection_payload=load(args.projection),
        formal_acceptance=load(args.acceptance),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
