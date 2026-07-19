from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.persistence.postgres_schema_governance import canonical_person_ref


SCHEMA_VERSION = "i5b-formal-fact-acceptance-v3"
_ACCEPTED_DECISIONS = frozenset({"accept", "accept_with_uncertainty"})
_EXISTING_DECISIONS = _ACCEPTED_DECISIONS | {"reject"}


def _hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"missing required field: {field}")
    return text


def _ruler_name(value: object) -> str:
    if isinstance(value, Mapping):
        return _required_text(value.get("name"), field="ruler.name")
    return _required_text(value, field="ruler")


def _strings(*values: object) -> list[str]:
    result: list[str] = []
    for value in values:
        for item in value or ():
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
    return result


def _neutral_qualifiers(
    assertion: Mapping[str, Any], *, ruler_ref: str
) -> dict[str, Any]:
    """Project accepted facts onto the shared Assertion contract only."""

    source = assertion.get("qualifiers") or {}
    focal_refs = [
        canonical_person_ref(value)
        for value in _strings(
            source.get("candidate_focal_person_refs"),
            (source.get("focal_person_ref"),) if source.get("focal_person_ref") else (),
        )
    ]
    focal_refs = [
        value
        for value in dict.fromkeys(focal_refs)
        if value.startswith("PER-") and value != ruler_ref
    ]
    return {
        "responsibility_family": source.get("responsibility_family"),
        "office_or_domain": source.get("office_or_domain"),
        "outcome": source.get("outcome"),
        "cost_or_damage": source.get("cost_or_damage"),
        "focal_person_ref": focal_refs[0] if len(focal_refs) == 1 else None,
        "candidate_focal_person_refs": focal_refs,
        "event_scope": source.get("event_scope"),
        "normalized_time": source.get("normalized_time"),
        "evaluation_context": ruler_ref,
        "episode_type": "political_action",
        "candidate_participant_roles": [
            [ruler_ref, "ruler"],
            *[[ref, "focal_person"] for ref in focal_refs],
        ],
    }


def _neutralize_unit_assertions(
    units: list[dict[str, Any]], *, ruler_ref: str
) -> None:
    for unit in units:
        for assertion in unit.get("assertion_drafts") or ():
            assertion["qualifiers"] = _neutral_qualifiers(
                assertion, ruler_ref=ruler_ref
            )


def _existing_decisions(
    reviewed_assertions: Mapping[str, Any],
    acceptance_decisions: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], set[str]]:
    drafts: dict[str, Mapping[str, Any]] = {}
    for unit in reviewed_assertions.get("units") or ():
        if unit.get("review_disposition") != "reviewed_ready_for_episode_shadow":
            raise ValueError(f"unit is not review-complete: {unit.get('unit_ref')}")
        for assertion in unit.get("assertion_drafts") or ():
            assertion_code = _required_text(
                assertion.get("assertion_code"), field="assertion_code"
            )
            if assertion_code in drafts:
                raise ValueError(f"duplicate reviewed assertion: {assertion_code}")
            drafts[assertion_code] = assertion

    decisions: dict[str, Mapping[str, Any]] = {}
    for row in acceptance_decisions.get("existing_assertion_decisions") or ():
        assertion_code = _required_text(
            row.get("assertion_code"), field="existing_assertion_decisions.assertion_code"
        )
        if assertion_code in decisions:
            raise ValueError(f"duplicate existing assertion decision: {assertion_code}")
        decision = _required_text(
            row.get("decision"), field=f"existing decision for {assertion_code}"
        )
        if decision not in _EXISTING_DECISIONS:
            raise ValueError(
                f"unsupported existing assertion decision {decision}: {assertion_code}"
            )
        decisions[assertion_code] = row

    reviewed_refs = set(drafts)
    decided_refs = set(decisions)
    if reviewed_refs != decided_refs:
        missing = sorted(reviewed_refs - decided_refs)
        unexpected = sorted(decided_refs - reviewed_refs)
        raise ValueError(
            "existing assertion decision coverage does not close: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return decisions, reviewed_refs


def _accepted_existing_units(
    reviewed_assertions: Mapping[str, Any],
    decisions: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    units: list[dict[str, Any]] = []
    accepted_count = 0
    uncertain_count = 0
    for source_unit in reviewed_assertions.get("units") or ():
        unit = deepcopy(dict(source_unit))
        accepted_drafts: list[dict[str, Any]] = []
        for source_assertion in source_unit.get("assertion_drafts") or ():
            assertion_code = str(source_assertion["assertion_code"])
            decision_row = decisions[assertion_code]
            disposition = str(decision_row["decision"])
            if disposition not in _ACCEPTED_DECISIONS:
                continue
            event_node_ref = _required_text(
                decision_row.get("event_node_ref"),
                field=f"event_node_ref for {assertion_code}",
            )
            assertion = deepcopy(dict(source_assertion))
            assertion["ambiguity_flags"] = _strings(
                assertion.get("ambiguity_flags"),
                decision_row.get("ambiguity_flags"),
                decision_row.get("retained_uncertainties"),
            )
            assertion["remaining_uncertainties"] = _strings(
                assertion.get("remaining_uncertainties"),
                decision_row.get("remaining_uncertainties"),
                decision_row.get("retained_uncertainties"),
            )
            assertion["event_node_ref"] = event_node_ref
            assertion["formal_acceptance_disposition"] = disposition
            assertion["formal_acceptance_basis"] = "existing_assertion_decision"
            accepted_drafts.append(assertion)
            accepted_count += 1
            uncertain_count += int(disposition == "accept_with_uncertainty")
        if not accepted_drafts:
            continue
        unit["assertion_drafts"] = accepted_drafts
        unit["assertion_draft_count"] = len(accepted_drafts)
        unit["review_disposition"] = "formally_accepted"
        unit["formal_acceptance_basis"] = "existing_assertion_decisions"
        unit["formal_acceptance_disposition"] = (
            "accepted_with_uncertainty"
            if any(
                row["formal_acceptance_disposition"] == "accept_with_uncertainty"
                for row in accepted_drafts
            )
            else "accepted"
        )
        units.append(unit)
    return units, accepted_count, uncertain_count


def _accepted_new_units(
    *,
    acceptance_decisions: Mapping[str, Any],
    unit_specs: Mapping[str, Mapping[str, Any]],
    ruler_ref: str,
    existing_assertion_refs: set[str],
) -> tuple[list[dict[str, Any]], int, int]:
    assertions_by_candidate: dict[str, list[Mapping[str, Any]]] = {}
    seen_assertions = set(existing_assertion_refs)
    for row in acceptance_decisions.get("accepted_assertions") or ():
        assertion_code = _required_text(
            row.get("assertion_code"), field="accepted_assertions.assertion_code"
        )
        if assertion_code in seen_assertions:
            raise ValueError(f"duplicate formal assertion: {assertion_code}")
        seen_assertions.add(assertion_code)
        decision = _required_text(
            row.get("decision"), field=f"new assertion decision for {assertion_code}"
        )
        if decision not in _ACCEPTED_DECISIONS:
            raise ValueError(
                f"new assertion must be accept or accept_with_uncertainty: {assertion_code}"
            )
        _required_text(
            row.get("event_node_ref"), field=f"event_node_ref for {assertion_code}"
        )
        candidate_code = _required_text(
            row.get("candidate_code"), field=f"candidate_code for {assertion_code}"
        )
        assertions_by_candidate.setdefault(candidate_code, []).append(row)

    groups_by_candidate: dict[str, Mapping[str, Any]] = {}
    for group in acceptance_decisions.get("accepted_candidate_groups") or ():
        candidate_code = _required_text(
            group.get("candidate_code"), field="accepted_candidate_groups.candidate_code"
        )
        if candidate_code in groups_by_candidate:
            raise ValueError(f"duplicate accepted candidate group: {candidate_code}")
        groups_by_candidate[candidate_code] = group
    if set(groups_by_candidate) != set(assertions_by_candidate):
        raise ValueError("accepted candidate group coverage does not close")

    units: list[dict[str, Any]] = []
    accepted_count = 0
    uncertain_count = 0
    for candidate_code, group in groups_by_candidate.items():
        spec = unit_specs.get(candidate_code)
        if spec is None:
            raise ValueError(f"missing unit spec: {candidate_code}")
        decision_rows = assertions_by_candidate[candidate_code]
        expected_refs = sorted(str(value) for value in group.get("assertion_refs") or ())
        actual_refs = sorted(str(value["assertion_code"]) for value in decision_rows)
        if actual_refs != expected_refs:
            raise ValueError(f"accepted assertion refs do not close: {candidate_code}")
        declared_event_refs = {
            str(node.get("event_node_ref"))
            for node in group.get("minimum_sufficient_event_nodes") or ()
            if node.get("event_node_ref")
        }
        focal_refs = list(spec.get("candidate_focal_person_refs") or ())
        group_uncertainties = _strings(group.get("remaining_uncertainties"))
        assertion_drafts: list[dict[str, Any]] = []
        for row in decision_rows:
            event_node_ref = str(row["event_node_ref"])
            if declared_event_refs and event_node_ref not in declared_event_refs:
                raise ValueError(
                    f"assertion event_node_ref is not declared by group: {row['assertion_code']}"
                )
            disposition = str(row["decision"])
            ambiguity_flags = _strings(
                group_uncertainties, row.get("ambiguity_flags")
            )
            remaining_uncertainties = _strings(
                group_uncertainties, row.get("remaining_uncertainties")
            )
            semantic_key = "ASK-" + _hash(
                [row["assertion_code"], row["passage_id"], row["predicate"], row["object"]]
            )[:24].upper()
            assertion_drafts.append(
                {
                    "ambiguity_flags": ambiguity_flags,
                    "assertion_code": str(row["assertion_code"]),
                    "assertion_type": "event_fact",
                    "candidate_episode_key": candidate_code,
                    "confidence": float(row.get("confidence", 0.95)),
                    "event_node_ref": event_node_ref,
                    "extraction_provenance": {
                        "provider": "human_fact_acceptance_decision_v1",
                        "provider_assertion_code": str(row["assertion_code"]),
                    },
                    "formal_acceptance_disposition": disposition,
                    "location_expression": None,
                    "object": str(row["object"]),
                    "passage_support": {
                        "assertion_semantic_key": semantic_key,
                        "binding_provenance": {
                            "provider": "human_fact_acceptance_decision_v1",
                            "provider_assertion_semantic_key": semantic_key,
                        },
                        "support_mode": "single_passage",
                        "supported_fields": [
                            "identity",
                            "action",
                            "outcome",
                            "attribution",
                        ],
                    },
                    "polarity": "asserted",
                    "predicate": str(row["predicate"]),
                    "qualifiers": {
                        "outcome": str(row["outcome"]),
                        "responsibility_family": spec.get("responsibility_family"),
                        "office_or_domain": spec.get("office_or_domain"),
                        "cost_or_damage": spec.get("cost_or_damage"),
                        "event_scope": spec.get("event_scope"),
                        "normalized_time": spec.get("normalized_time"),
                        "candidate_focal_person_refs": focal_refs,
                        "candidate_participant_roles": [
                            [ruler_ref, "ruler"],
                            *[
                                [canonical_person_ref(ref), "focal_person"]
                                for ref in focal_refs
                                if canonical_person_ref(ref).startswith("PER-")
                                and canonical_person_ref(ref) != ruler_ref
                            ],
                        ],
                        "evaluation_context": ruler_ref,
                        "episode_type": "political_action",
                    },
                    "remaining_uncertainties": remaining_uncertainties,
                    "source_attribution": {
                        "attribution_type": "原文直接引述",
                        "quoted_text": str(row["quoted_text"]),
                        "speaker": str(row["subject"]),
                        "work": str(spec.get("source_work") or ""),
                    },
                    "source_passage_ref": str(row["passage_id"]),
                    "subject": str(row["subject"]),
                    "time_expression": spec.get("time_expression"),
                }
            )
            accepted_count += 1
            uncertain_count += int(disposition == "accept_with_uncertainty")
        unit_disposition = (
            "accepted_with_uncertainty"
            if any(
                row["formal_acceptance_disposition"] == "accept_with_uncertainty"
                for row in assertion_drafts
            )
            else "accepted"
        )
        units.append(
            {
                "unit_ref": str(spec["unit_ref"]),
                "subject": str(spec["subject"]),
                "assertion_draft_count": len(assertion_drafts),
                "assertion_drafts": assertion_drafts,
                "review_disposition": "formally_accepted",
                "formal_acceptance_disposition": unit_disposition,
                "formal_acceptance_basis": candidate_code,
                "duplicate_settlement_boundary": str(
                    group.get("duplicate_settlement_boundary") or ""
                ),
                "remaining_uncertainties": group_uncertainties,
                "projection_disposition": str(spec["projection_disposition"]),
            }
        )
    return units, accepted_count, uncertain_count


def build_formal_fact_acceptance(
    *,
    reviewed_assertions: Mapping[str, Any],
    acceptance_decisions: Mapping[str, Any],
    unit_specs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a fail-closed formal package from reviewed facts and explicit decisions."""
    profile_code = _required_text(
        reviewed_assertions.get("profile_code"), field="reviewed_assertions.profile_code"
    )
    scope = reviewed_assertions.get("scope") or {}
    rule_code = _required_text(scope.get("rule_code"), field="scope.rule_code")
    ruler = _ruler_name(scope.get("ruler"))
    ruler_ref = canonical_person_ref(
        _required_text(scope.get("ruler_ref"), field="scope.ruler_ref")
    )
    if _required_text(
        acceptance_decisions.get("rule_code"), field="acceptance_decisions.rule_code"
    ) != rule_code:
        raise ValueError("acceptance decision rule mismatch")
    if _ruler_name(acceptance_decisions.get("ruler")) != ruler:
        raise ValueError("acceptance decision ruler mismatch")
    decision_profile = acceptance_decisions.get("profile_code")
    if decision_profile is not None and str(decision_profile) != profile_code:
        raise ValueError("acceptance decision profile mismatch")
    if int(
        (reviewed_assertions.get("summary") or {}).get(
            "pending_blocking_review_unit_count", -1
        )
    ) != 0:
        raise ValueError("reviewed assertions still contain blocking units")

    decisions, existing_assertion_refs = _existing_decisions(
        reviewed_assertions, acceptance_decisions
    )
    existing_units, existing_accepted, existing_uncertain = _accepted_existing_units(
        reviewed_assertions, decisions
    )
    new_units, new_accepted, new_uncertain = _accepted_new_units(
        acceptance_decisions=acceptance_decisions,
        unit_specs=unit_specs,
        ruler_ref=ruler_ref,
        existing_assertion_refs=existing_assertion_refs,
    )
    units = existing_units + new_units
    _neutralize_unit_assertions(units, ruler_ref=ruler_ref)
    assertion_count = existing_accepted + new_accepted
    uncertain_count = existing_uncertain + new_uncertain
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "profile_code": profile_code,
        "rule_code": rule_code,
        "ruler": ruler,
        "status": "formally_accepted_for_core_registry",
        "scope": deepcopy(scope),
        "declarations": {
            "draft_only": False,
            "explicit_assertion_decisions_complete": True,
            "explicit_event_node_mapping": True,
            "formal_fact_acceptance": True,
            "ready_for_episode_shadow": True,
            "score_or_ranking_write": False,
        },
        "summary": {
            "assertion_count": assertion_count,
            "accepted_assertion_count": assertion_count - uncertain_count,
            "accepted_with_uncertainty_assertion_count": uncertain_count,
            "accepted_unit_count": len(units),
            "existing_reviewed_assertion_count": len(existing_assertion_refs),
            "existing_accepted_assertion_count": existing_accepted,
            "newly_accepted_assertion_count": new_accepted,
            "rejected_existing_assertion_count": len(existing_assertion_refs)
            - existing_accepted,
            "pending_blocking_review_unit_count": 0,
            "database_write_count": 0,
            "formal_scoring_allowed": False,
        },
        "input_refs": {
            "reviewed_assertion_report_sha256": reviewed_assertions.get("report_sha256"),
            "acceptance_decision_report_sha256": acceptance_decisions.get("report_sha256"),
        },
        "units": units,
    }
    payload["report_sha256"] = _hash(payload)
    return payload


def merge_formal_fact_acceptance(
    *, base: Mapping[str, Any], increment: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge a reviewed increment without rewriting prior accepted facts."""
    identity_fields = ("schema_version", "profile_code", "rule_code", "ruler")
    if any(base.get(field) != increment.get(field) for field in identity_fields):
        raise ValueError("formal acceptance increment identity mismatch")
    if base.get("scope") != increment.get("scope"):
        raise ValueError("formal acceptance increment scope mismatch")
    base_units = list(base.get("units") or ())
    increment_units = list(increment.get("units") or ())
    base_unit_refs = {str(row.get("unit_ref")) for row in base_units}
    increment_unit_refs = {str(row.get("unit_ref")) for row in increment_units}
    if base_unit_refs & increment_unit_refs:
        raise ValueError("formal acceptance increment duplicates unit_ref")
    base_assertions = {
        str(assertion.get("assertion_code"))
        for unit in base_units
        for assertion in unit.get("assertion_drafts") or ()
    }
    increment_assertions = {
        str(assertion.get("assertion_code"))
        for unit in increment_units
        for assertion in unit.get("assertion_drafts") or ()
    }
    if base_assertions & increment_assertions:
        raise ValueError("formal acceptance increment duplicates assertion")
    units = deepcopy(base_units) + deepcopy(increment_units)
    uncertain = sum(
        assertion.get("formal_acceptance_disposition") == "accept_with_uncertainty"
        for unit in units
        for assertion in unit.get("assertion_drafts") or ()
    )
    assertion_count = sum(len(unit.get("assertion_drafts") or ()) for unit in units)
    payload = deepcopy(dict(base))
    payload["status"] = "formally_accepted_for_core_registry"
    payload["units"] = units
    payload["summary"] = {
        "assertion_count": assertion_count,
        "accepted_assertion_count": assertion_count - uncertain,
        "accepted_with_uncertainty_assertion_count": uncertain,
        "accepted_unit_count": len(units),
        "existing_reviewed_assertion_count": int(
            (base.get("summary") or {}).get("existing_reviewed_assertion_count", 0)
        ),
        "existing_accepted_assertion_count": int(
            (base.get("summary") or {}).get("accepted_assertion_count", 0)
        ),
        "newly_accepted_assertion_count": int(
            (increment.get("summary") or {}).get("assertion_count", 0)
        ),
        "rejected_existing_assertion_count": int(
            (base.get("summary") or {}).get("rejected_existing_assertion_count", 0)
        ),
        "pending_blocking_review_unit_count": 0,
        "database_write_count": 0,
        "formal_scoring_allowed": False,
    }
    payload["input_refs"] = {
        "base_formal_acceptance_sha256": base.get("report_sha256"),
        "increment_formal_acceptance_sha256": increment.get("report_sha256"),
    }
    payload.pop("report_sha256", None)
    payload["report_sha256"] = _hash(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a formal fact acceptance package")
    parser.add_argument("--reviewed", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--unit-specs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-acceptance", type=Path)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build_formal_fact_acceptance(
        reviewed_assertions=load(args.reviewed),
        acceptance_decisions=load(args.decisions),
        unit_specs=load(args.unit_specs),
    )
    if args.base_acceptance:
        result = merge_formal_fact_acceptance(
            base=load(args.base_acceptance), increment=result
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
