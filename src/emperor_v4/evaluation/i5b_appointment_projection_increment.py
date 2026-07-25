from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping


OBSERVATION_KEYS = (
    "attributable_outcome",
    "authority_clarity",
    "feedback_handling",
    "person_task_fit",
)
FACTOR_KEYS = (
    "appointment_effect",
    "appointment_importance",
    "attribution_factor",
    "context_factor",
    "continuity_factor",
    "source_factor",
)


def build_projection_increment(
    *,
    base: Mapping[str, Any],
    formal_acceptance: Mapping[str, Any],
    decisions: Mapping[str, Any],
) -> dict[str, Any]:
    if decisions.get("schema_version") != "i5b-appointment-projection-decisions-v1":
        raise ValueError("appointment projection decision schema mismatch")
    formal_by_candidate = {
        str(unit.get("formal_acceptance_basis")): unit
        for unit in formal_acceptance.get("units") or ()
    }
    units = deepcopy(list(base.get("units") or ()))
    seen_groups = {str(unit.get("canonical_event_group")) for unit in units}
    for row in decisions.get("units") or ():
        candidate = str(row.get("candidate_code") or "")
        if not candidate or candidate in seen_groups:
            raise ValueError("projection candidate missing or duplicate")
        formal = formal_by_candidate.get(candidate)
        if formal is None or formal.get("projection_disposition") != "projected":
            raise ValueError(f"projection candidate lacks projected formal unit: {candidate}")
        refs = [
            str(assertion["assertion_code"])
            for assertion in formal.get("assertion_drafts") or ()
        ]
        options = row.get("factor_options") or {}
        if set(options) != set(FACTOR_KEYS):
            raise ValueError(f"projection factor decisions incomplete: {candidate}")
        reason = str(row.get("reason") or "")
        if not reason:
            raise ValueError(f"projection decision lacks reason: {candidate}")
        factors = {
            factor: {
                "assertion_refs": refs,
                "option_code": str(options[factor]),
                "reason": reason,
            }
            for factor in FACTOR_KEYS
        }
        observations = {
            key: {
                "assertion_refs": refs,
                "reason": reason,
                "value": "positive_signal",
            }
            for key in OBSERVATION_KEYS
        }
        units.append(
            {
                "canonical_event_group": candidate,
                "factor_materials": [
                    {
                        "event_group": candidate,
                        "factors": factors,
                        "material_code": str(row["material_code"]),
                        "side": "positive",
                    }
                ],
                "factor_observations": observations,
                "object_ref": str(row["object_ref"]),
                "person": str(row["person"]),
                "primary_settlement_rule": "appointment_delegation",
                "projection_basis": "human_frozen_formal_assertions_v2",
                "ruler": "李世民",
                "side": "positive",
                "status": "human_frozen_historical_closeout_input",
                "unit_ref": str(formal["unit_ref"]),
            }
        )
        seen_groups.add(candidate)
    payload = deepcopy(dict(base))
    payload["input_version"] = str(decisions["input_version"])
    payload["status"] = "human_frozen_historical_closeout_input"
    payload["units"] = units
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge reviewed appointment projection decisions")
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--formal-acceptance", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build_projection_increment(
        base=load(args.base),
        formal_acceptance=load(args.formal_acceptance),
        decisions=load(args.decisions),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
