from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "i5b-scoring-detail-report-v1"
MANIFEST_SCHEMA_VERSION = "i5b-scoring-detail-manifest-v1"
CATALOG_SCHEMA_VERSION = "i5b-scoring-detail-catalog-v1"
SELECTION_SCHEMA_VERSION = "i5b-scoring-detail-selection-v1"
SELECTION_REPORT_SCHEMA_VERSION = "i5b-scoring-detail-selection-report-v1"
DISPLAY_SCHEMA_VERSION = "i5b-scoring-detail-display-v1"
RULE_ORDER = (
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
)
RULE_LABELS = {
    "talent_discovery": "人才发现",
    "appointment_delegation": "任用授权",
    "team_building": "团队建设",
    "tolerate_talent": "容才",
    "anti_nepotism": "反任人唯亲",
}
DISPLAY_NAME_ALIASES = {
    "馬周": "马周",
    "房玄齡": "房玄龄",
    "李勣": "李绩",
    "李𪟝": "李绩",
}
ROLE_LABELS = {
    "decision": "决策",
    "administration": "行政",
    "military": "军事",
    "correction": "纠错",
}
SIDE_LABELS = {"positive": "正向", "negative": "负向"}
ADAPTERS = {
    "joint_projection_report",
    "appointment_parity_report",
    "appointment_expanded_shadow",
    "team_scored_shadow_report",
    "team_roster_shadow",
    "team_historical_scored_shadow",
    "institution_policy_formal_shadow",
    "institution_policy_judge",
    "appointment_candidate_inventory_audit",
    "appointment_episode_assertion_support",
    "rule_lane_shadow",
    "source_rebind_record",
    "source_rebind_batch",
    "material_budget_report",
    "formal_acceptance_report",
}


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _rounded(value: object) -> str:
    return str(_decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _rows(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} may contain only objects")
    return list(value)


def _factor_contract_audit(
    *, rule_code: str, policy: Mapping[str, Any], detail: Mapping[str, Any]
) -> dict[str, Any]:
    required = {str(value) for value in policy.get("v4_factor_inputs") or ()}
    observed = {
        str(key)
        for material in detail.get("materials") or ()
        for key in (
            (
                (material.get("numeric_projection") or {}).get(
                    "v4_factor_projection"
                )
                or {}
            ).get("factor_choices")
            or {}
        )
    }
    missing = sorted(required - observed)
    materials = list(detail.get("materials") or ())
    top_level_complete = all(
        bool(material.get("factor_option_codes")) for material in materials
    )
    return {
        "status": (
            "not_declared"
            if not required
            else "current_contract"
            if not missing
            else "legacy_projection_diagnostic_only"
        ),
        "required_v4_factor_inputs": sorted(required),
        "observed_factor_inputs": sorted(observed),
        "missing_v4_factor_inputs": missing,
        "legacy_projection_diagnostic_only": bool(required),
        "top_level_factor_contract_complete": top_level_complete,
        "blocks_historical_completion": False,
        "rule_code": rule_code,
    }


def _source_detail(
    *, adapter: str, rule_code: str, ruler: str, payload: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, str] | None]:
    if adapter == "material_budget_report":
        if (
            payload.get("schema_version") != "i5b-material-budget-shadow-report-v1"
            or payload.get("ruler") != ruler
        ):
            raise ValueError("material budget source identity mismatch")
        matches = [
            row for row in payload.get("rules") or () if row.get("rule_code") == rule_code
        ]
        if len(matches) != 1:
            raise ValueError(f"{rule_code} material budget row missing or duplicated")
        budget_rule = matches[0]
        signals = {
            "positive_signal": str(budget_rule["positive_signal"]),
            "negative_signal": str(budget_rule["negative_signal"]),
            "rule_raw_net": str(budget_rule["rule_raw_net"]),
        }
        unscored_materials = [
            {
                "material": row.get("subject") or row.get("person"),
                "material_id": row.get("material_id"),
                "rule_evidence_unit_ref": row.get("rule_evidence_unit_ref"),
                "material_score": row.get("material_magnitude"),
                "factor_values": dict(row.get("factor_values") or {}),
                "factor_option_codes": dict(
                    row.get("factor_option_codes") or {}
                ),
                "fact": str(row.get("fact") or ""),
            }
            for row in budget_rule.get("supporting_only_materials") or ()
            if row.get("material_magnitude") is not None
            and row.get("factor_values")
        ]
        if rule_code == "team_building":
            negative_by_person = {
                str(row["person"]): row
                for row in budget_rule.get("negative_members") or ()
            }
            members = []
            for row in budget_rule.get("positive_members") or ():
                negative = negative_by_person.pop(str(row["person"]), None)
                members.append(
                    {
                        "person": row["person"],
                        "grade": row["talent_grade"],
                        "talent_value": row["talent_value"],
                        "talent_grade_basis": row.get("talent_grade_basis"),
                        "roles": list(row.get("role_families") or ()),
                        "positive_weighted_value": str(row["talent_value"]),
                        "negative_weighted_value": "0",
                        "window_negative_class": (
                            negative.get("negative_class") if negative else None
                        ),
                        "window_negative_severity": (
                            negative.get("negative_severity") if negative else None
                        ),
                        "supporting_unit_refs": list(
                            row.get("supporting_unit_refs") or ()
                        ),
                    }
                )
            for row in budget_rule.get("negative_members") or ():
                matching = next(
                    (item for item in members if item["person"] == row["person"]),
                    None,
                )
                if matching is None:
                    matching = {
                        "person": row["person"],
                        "grade": row.get("talent_grade"),
                        "talent_value": row.get("talent_value"),
                        "talent_grade_basis": row.get("talent_grade_basis"),
                        "roles": list(row.get("role_families") or ()),
                        "positive_weighted_value": "0",
                        "supporting_unit_refs": list(
                            row.get("supporting_unit_refs") or ()
                        ),
                    }
                    members.append(matching)
                matching.update(
                    {
                        "negative_weighted_value": str(row["negative_value"]),
                        "window_negative_class": row.get("negative_class"),
                        "window_negative_severity": row.get("negative_severity"),
                    }
                )
            return {
                "members": members,
                "governance_results": list(
                    budget_rule.get("governance_results") or ()
                ),
                "factors": {
                    "functional_complementarity": budget_rule.get(
                        "functional_complementarity"
                    ),
                    "continuity_structure": budget_rule.get("long_term_stability"),
                },
                "calculation": {
                    "positive_pool": budget_rule.get("positive_pool"),
                    "negative_pool": budget_rule.get("negative_pool"),
                    "positive_signal": budget_rule.get("positive_signal"),
                    "negative_signal": budget_rule.get("negative_signal"),
                    "rule_raw_net": budget_rule.get("rule_raw_net"),
                },
                "unscored_materials": unscored_materials,
            }, signals

        selected = [dict(row) for row in budget_rule.get("settled_materials") or ()]
        by_side = {
            side: [row for row in selected if row.get("side") == side]
            for side in ("positive", "negative")
        }
        weighted: dict[str, Decimal] = {}
        if selected and all("actual_signal_contribution" in row for row in selected):
            weighted = {
                str(row["material_id"]): _decimal(row["actual_signal_contribution"])
                for row in selected
            }
        elif rule_code == "appointment_delegation":
            for side, rows in by_side.items():
                scale = Decimal("1.5") if side == "positive" else Decimal("1")
                if any(
                    "object_aggregate_magnitude" not in row
                    or "object_internal_contribution" not in row
                    for row in rows
                ):
                    ordered = sorted(
                        rows,
                        key=lambda row: (
                            -_decimal(row["material_magnitude"]),
                            str(row["material_id"]),
                        ),
                    )
                    for rank, row in enumerate(ordered, start=1):
                        weighted[str(row["material_id"])] = (
                            scale
                            * _decimal(row["material_magnitude"])
                            / Decimal(rank).sqrt()
                        )
                    continue
                grouped: dict[str, list[dict[str, Any]]] = {}
                for row in rows:
                    grouped.setdefault(str(row.get("object_ref")), []).append(row)
                object_totals = {
                    object_ref: _decimal(group[0]["object_aggregate_magnitude"])
                    for object_ref, group in grouped.items()
                }
                ordered_objects = sorted(
                    grouped,
                    key=lambda object_ref: (-object_totals[object_ref], object_ref),
                )
                rank = 0
                previous: Decimal | None = None
                for index, object_ref in enumerate(ordered_objects, start=1):
                    total = object_totals[object_ref]
                    if previous is None or total != previous:
                        rank = index
                    for row in grouped[object_ref]:
                        row["object_aggregate_magnitude"] = str(total)
                        row["object_rank"] = rank
                        weighted[str(row["material_id"])] = (
                            scale
                            * _decimal(row["object_internal_contribution"])
                            / Decimal(rank).sqrt()
                        )
                    previous = total
        else:
            for side, rows in by_side.items():
                if all("object_internal_contribution" in row for row in rows):
                    for row in rows:
                        weighted[str(row["material_id"])] = _decimal(
                            row["object_internal_contribution"]
                        )
                    continue
                grouped: dict[str, list[dict[str, Any]]] = {}
                for row in rows:
                    grouped.setdefault(
                        str(row.get("settlement_object_ref") or row.get("object_ref")),
                        [],
                    ).append(row)
                for group in grouped.values():
                    ordered = sorted(
                        group,
                        key=lambda row: (
                            -_decimal(row["material_magnitude"]),
                            str(row["material_id"]),
                        ),
                    )
                    strongest = _decimal(ordered[0]["material_magnitude"])
                    object_value = min(
                        strongest
                        + Decimal("0.35")
                        * sum(
                            (
                                _decimal(row["material_magnitude"])
                                for row in ordered[1:]
                            ),
                            Decimal("0"),
                        ),
                        strongest * Decimal("1.5"),
                        Decimal("4"),
                    )
                    weighted[str(ordered[0]["material_id"])] = object_value
                    for row in ordered[1:]:
                        weighted[str(row["material_id"])] = Decimal("0")
        materials = [
            {
                "unit_ref": row["material_id"],
                "material_id": row["material_id"],
                "rule_evidence_unit_ref": row.get("rule_evidence_unit_ref"),
                "subject": row["subject"],
                "object_ref": row.get("object_ref"),
                "side": row["side"],
                "material_score": row["material_magnitude"],
                "weighted_signal": str(weighted[str(row["material_id"])]),
                "aggregation_text": (
                    "同一责任对象材料合并后按对象排名"
                    if rule_code == "appointment_delegation"
                    else "结算预算内材料"
                ),
                **(
                    {
                        "object_aggregate_magnitude": row.get(
                            "object_aggregate_magnitude"
                        ),
                        "object_rank": row.get("object_rank"),
                    }
                    if rule_code == "appointment_delegation"
                    else {}
                ),
                "projection_basis": row.get("fact"),
                "numeric_projection": {
                    "factor_option_codes": dict(
                        row.get("factor_option_codes") or {}
                    ),
                    "deterministic_dimension_values": dict(
                        row.get("factor_values") or {}
                    ),
                    "v4_factor_projection": dict(
                        row.get("v4_factor_projection") or {}
                    ),
                },
                "talent_quality_basis": dict(
                    row.get("talent_quality_basis") or {}
                ),
            }
            for row in selected
        ]
        detail = {
            "materials": materials,
            "unscored_materials": unscored_materials,
            "positive_budget": budget_rule.get("positive_budget"),
            "negative_budget": budget_rule.get("negative_budget"),
            "governance_results": list(
                budget_rule.get("governance_results") or ()
            ),
        }
        talent_quality_basis_rows = [
            {
                "subject": row.get("subject"),
                "talent_quality_basis": dict(row["talent_quality_basis"]),
                "selection_status": "settled",
                "material_score": row.get("material_magnitude"),
                "factor_values": dict(row.get("factor_values") or {}),
                "factor_option_codes": dict(
                    row.get("factor_option_codes") or {}
                ),
            }
            for row in selected
            if row.get("talent_quality_basis")
        ]
        talent_quality_basis_rows.extend(
            {
                "subject": row.get("subject"),
                "talent_quality_basis": dict(row["talent_quality_basis"]),
                "selection_status": row.get("selection_status"),
                "material_score": row.get("material_magnitude"),
                "factor_values": dict(row.get("factor_values") or {}),
                "factor_option_codes": dict(
                    row.get("factor_option_codes") or {}
                ),
            }
            for row in budget_rule.get("supporting_only_materials") or ()
            if row.get("talent_quality_basis")
        )
        if talent_quality_basis_rows:
            detail["talent_quality_basis_rows"] = talent_quality_basis_rows
        if budget_rule.get("candidate_boundary_audit"):
            detail["candidate_boundary_audit"] = dict(
                budget_rule["candidate_boundary_audit"]
            )
        return detail, signals

    if adapter == "formal_acceptance_report":
        if (
            payload.get("schema_version") != "i5b-formal-fact-acceptance-v3"
            or payload.get("rule_code") != rule_code
            or payload.get("ruler") != ruler
        ):
            raise ValueError("formal acceptance source identity mismatch")
        return {
            "accepted_assertions": [
                {
                    **dict(assertion),
                    "unit_ref": unit.get("unit_ref"),
                    "unit_subject": unit.get("subject"),
                }
                for unit in payload.get("units") or ()
                for assertion in unit.get("assertion_drafts") or ()
                if assertion.get("formal_acceptance_disposition")
                in {"accept", "accept_with_uncertainty"}
            ]
        }, None

    if adapter == "joint_projection_report":
        if payload.get("rule_code") != rule_code:
            raise ValueError(f"{rule_code} joint projection source rule mismatch")
        contributions = [
            row
            for row in _rows(payload.get("score_contributions") or (), "score contributions")
            if row.get("ruler") == ruler
        ]
        contribution = contributions[0] if contributions else None
        detail = {
            "materials": [
                row for row in payload.get("materials") or () if row.get("ruler") == ruler
            ],
            "insufficient_projections": [
                row
                for row in payload.get("insufficient_projections") or ()
                if row.get("ruler") == ruler
            ],
            "object_side_aggregates": [
                row
                for row in payload.get("object_side_aggregates") or ()
                if row.get("ruler") == ruler
            ],
            "score_contribution": contribution,
        }
        signals = None if contribution is None else {
            "positive_signal": str(contribution["positive_signal"]),
            "negative_signal": str(contribution["negative_signal"]),
            "rule_raw_net": str(contribution["rule_raw_net"]),
        }
        return detail, signals

    if adapter == "appointment_parity_report":
        aggregates = [
            row for row in payload.get("ruler_aggregates") or () if row.get("ruler") == ruler
        ]
        aggregate = aggregates[0] if aggregates else None
        detail = {
            "ruler_aggregate": aggregate,
            "judgments": [
                row for row in payload.get("judgments") or () if row.get("ruler") == ruler
            ],
            "assertion_episode_reu_trace": dict(
                payload.get("assertion_episode_reu_trace") or {}
            ),
        }
        signals = None if aggregate is None else {
            "positive_signal": str(aggregate["positive_signal"]),
            "negative_signal": str(aggregate["negative_signal"]),
            "rule_raw_net": str(aggregate["rule_raw_net"]),
        }
        return detail, signals

    if adapter == "appointment_expanded_shadow":
        if payload.get("ruler") != ruler:
            raise ValueError("appointment expanded shadow ruler mismatch")
        detail = {
            "aggregation_policy": payload.get("aggregation_policy"),
            "positive_lane_scale": payload.get("positive_lane_scale"),
            "object_decay": payload.get("object_decay"),
            "materials": list(payload.get("materials") or ()),
            "excluded_net_additions": list(payload.get("excluded_net_additions") or ()),
        }
        return detail, {
            "positive_signal": str(payload["positive_signal"]),
            "negative_signal": str(payload["negative_signal"]),
            "rule_raw_net": str(payload["rule_raw_net"]),
        }

    if adapter == "team_scored_shadow_report":
        if payload.get("rule_code") != rule_code:
            raise ValueError("team scored shadow source rule mismatch")
        windows = [row for row in payload.get("windows") or () if row.get("ruler") == ruler]
        return {"windows": windows}, None

    if adapter == "team_roster_shadow":
        if payload.get("ruler") != ruler:
            raise ValueError("team roster shadow ruler mismatch")
        calculation = payload.get("calculation") or {}
        detail = {
            "window": payload.get("window"),
            "members": list(payload.get("members") or ()),
            "blocked_or_excluded": list(payload.get("blocked_or_excluded") or ()),
            "not_yet_disposed_named_gaps": list(
                payload.get("not_yet_disposed_named_gaps") or ()
            ),
            "factors": dict(payload.get("factors") or {}),
            "calculation": dict(calculation),
        }
        return detail, {
            "positive_signal": str(calculation["positive_signal"]),
            "negative_signal": str(calculation["negative_signal"]),
            "rule_raw_net": str(calculation["rule_raw_net"]),
        }

    if adapter == "team_historical_scored_shadow":
        if payload.get("rule_code") != rule_code or payload.get("ruler") != ruler:
            raise ValueError("team historical shadow source identity mismatch")
        raw = payload.get("raw_signal") or {}
        detail = {
            "window": payload.get("window"),
            "members": [
                {
                    **dict(row),
                    "grade": (
                        row.get("effective_talent_grade")
                        or row.get("accepted_talent_grade")
                    ),
                    "origin": "formally_accepted_historical",
                    "roles": list(row.get("role_families") or ()),
                    "window_negative_class": row.get("negative_talent_class"),
                    "window_negative_severity": row.get("negative_talent_severity"),
                }
                for row in payload.get("members") or ()
            ],
            "factors": dict(payload.get("factors") or {}),
            "factor_diagnostics": dict(payload.get("factor_diagnostics") or {}),
            "score_contribution": dict(payload.get("score_contribution") or {}),
            "assertion_episode_reu_trace": dict(
                payload.get("assertion_episode_reu_trace") or {}
            ),
        }
        return detail, {
            "positive_signal": str(raw["positive_signal"]),
            "negative_signal": str(raw["negative_signal"]),
            "rule_raw_net": str(raw["rule_raw_net"]),
        }

    if adapter == "institution_policy_formal_shadow":
        if payload.get("rule_code") != rule_code:
            raise ValueError("institution policy shadow source rule mismatch")
        trace = dict(payload.get("assertion_episode_reu_trace") or {})
        episodes = list(trace.get("episodes") or ())
        return {
            "assertion_episode_reu_trace": trace,
            "insufficient_projections": list(
                payload.get("insufficient_projections") or ()
            ),
            "observations": [
                {
                    "time_context": "626—649制度事实",
                    "v4_frozen_observation": (
                        f"{episode.get('action')}；结果对象："
                        f"{'、'.join(episode.get('outcome') or ())}"
                    ),
                    "episode_id": episode.get("episode_id"),
                    "formal_fact": True,
                    "numeric_projection": False,
                }
                for episode in episodes
            ],
        }, None

    if adapter == "institution_policy_judge":
        if payload.get("ruler") != ruler:
            raise ValueError("institution policy judge source ruler mismatch")
        decisions = list(payload.get("decisions") or ())
        summary = dict(payload.get("summary") or {})
        if summary.get("judged_candidate_count") != len(decisions):
            raise ValueError("institution policy judge count mismatch")
        if summary.get("unresolved_candidate_count") != 0:
            raise ValueError("institution policy judge contains unresolved candidates")
        return {
            "judged_candidate_count": summary.get("judged_candidate_count"),
            "unresolved_candidate_count": summary.get("unresolved_candidate_count"),
        }, None

    if adapter == "appointment_candidate_inventory_audit":
        if payload.get("rule_code") != rule_code or payload.get("ruler") != ruler:
            raise ValueError("appointment candidate inventory identity mismatch")
        candidates = list(payload.get("candidate_inventory") or ())

        def person_names(candidate: Mapping[str, Any]) -> list[str]:
            names = []
            for item in candidate.get("candidate_persons") or ():
                name = item.get("name") if isinstance(item, Mapping) else item
                display_name = DISPLAY_NAME_ALIASES.get(str(name), str(name))
                if name and name != ruler and display_name not in names:
                    names.append(display_name)
            return names

        source_rebind = [
            candidate
            for candidate in candidates
            if candidate.get("final_disposition") == "advance_to_source_rebind"
        ]
        source_rebind_people = sorted(
            {
                name
                for candidate in source_rebind
                for name in person_names(candidate)
            }
        )
        existing_components = [
            candidate
            for candidate in candidates
            if candidate.get("final_disposition") == "existing_workset_component"
        ]
        disposition_counts: dict[str, int] = {}
        for candidate in candidates:
            disposition = str(candidate.get("final_disposition") or "")
            disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        return {
            "candidate_disposition_counts": disposition_counts,
            "candidate_count": len(candidates),
            "judged_candidate_count": sum(
                1 for candidate in candidates if candidate.get("final_disposition")
            ),
            "unresolved_candidate_count": len(source_rebind),
            "source_rebind_group_count": len(source_rebind),
            "source_rebind_people": source_rebind_people,
            "existing_workset_people": sorted(
                {
                    name
                    for candidate in existing_components
                    for name in person_names(candidate)
                }
            ),
            "formal_candidate_codes": list(payload.get("formal_candidate_codes") or ()),
            "candidate_disposition_complete": payload.get(
                "historical_coverage_complete"
            ),
            "formal_scoring_allowed": payload.get("formal_scoring_allowed"),
            "candidate_routes": [
                {
                    "persons": person_names(candidate),
                    "disposition": candidate.get("final_disposition"),
                    "summary": candidate.get("candidate_event_summary"),
                    "rationale": candidate.get("final_rationale"),
                }
                for candidate in candidates
            ],
        }, None

    if adapter == "appointment_episode_assertion_support":
        if payload.get("rule_code") != rule_code or payload.get("ruler") != ruler:
            raise ValueError("appointment episode assertion support identity mismatch")
        return {
            "accepted_assertion_outcomes": {
                str(assertion.get("assertion_code")): str(
                    (assertion.get("qualifiers") or {}).get("outcome")
                    or assertion.get("object")
                    or ""
                )
                for unit in payload.get("units") or ()
                for assertion in unit.get("assertion_drafts") or ()
                if assertion.get("assertion_code")
            }
        }, None

    if adapter == "rule_lane_shadow":
        if payload.get("ruler") != ruler:
            raise ValueError("rule lane shadow ruler mismatch")
        lane = payload.get(rule_code) or {}
        current = lane.get("strict_current") or {}
        if not current:
            raise ValueError(f"{rule_code} lane shadow lacks strict_current")
        return dict(lane), {
            "positive_signal": str(current["positive_signal"]),
            "negative_signal": str(current["negative_signal"]),
            "rule_raw_net": str(current["rule_raw_net"]),
        }

    if adapter == "source_rebind_record":
        return {
            "subject": payload.get("subject"),
            "observations": list(payload.get("observations") or ()),
            "factor_projection": dict(payload.get("factor_projection") or {}),
            "projection_decision": dict(payload.get("projection_decision") or {}),
        }, None

    if adapter == "source_rebind_batch":
        return {
            "candidate_inventory": dict(payload.get("candidate_inventory") or {}),
            "projection_units": list(payload.get("projection_units") or ()),
            "unresolved_priority_people": list(
                payload.get("unresolved_priority_people") or ()
            ),
        }, None

    raise ValueError(f"unsupported scoring detail adapter: {adapter}")


def build_i5b_scoring_detail(
    *,
    manifest: Mapping[str, Any],
    rule_net: Mapping[str, Any],
    scoring_policy: Mapping[str, Any],
    display_catalog: Mapping[str, Any],
    detail_sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("scoring detail manifest schema mismatch")
    budget_net = rule_net.get("schema_version") == "i5b-material-budget-shadow-report-v1"
    if not budget_net and rule_net.get("schema_version") != "i5b-ruler-rule-net-report-v1":
        raise ValueError("scoring detail requires a ruler rule net or material budget report")
    if scoring_policy.get("schema_version") != "i5b-scoring-policy-v1":
        raise ValueError("scoring detail scoring policy mismatch")
    if display_catalog.get("schema_version") != DISPLAY_SCHEMA_VERSION:
        raise ValueError("scoring detail display catalog mismatch")
    ruler = str(rule_net.get("ruler") or "")
    if budget_net:
        weights = scoring_policy["item_raw_signal"]["rule_weights"]
        if manifest.get("historical_coverage_status_overrides"):
            raise ValueError(
                "material budget detail may not override historical coverage status"
            )
        net_rows = {
            row["rule_code"]: {
                **dict(row),
                "calculation_status": "material_budget_shadow_complete",
                "historical_coverage_status": (
                    "coverage_complete"
                    if row.get("candidate_disposition_complete") is True
                    and row.get("source_projection_coverage_complete") is not False
                    else "coverage_incomplete"
                ),
                "rule_weight": str(weights[row["rule_code"]]),
                "weighted_raw_contribution": str(
                    _decimal(row["rule_raw_net"])
                    * _decimal(weights[row["rule_code"]])
                ),
                "limitations": (
                    [
                        "本轮为 all-eligible shadow：所有通过 Gate 的独立材料均进入聚合，未执行 strongest-N 截断。",
                        "该模式只用于本轮质量审查，不改写正式计分政策、45分映射或排名。",
                    ]
                    + (
                        ["部分材料投影未闭合，保留旧材料并记录缺口；本轮历史覆盖尚未完成。"]
                        if row.get("source_projection_coverage_complete") is False
                        else []
                    )
                    if row.get("settlement_mode") == "all_eligible_shadow"
                    else [
                        "事件型分项只结算 Gate 后最终材料分最高的预算内单元；其余合格材料保留为支持证据。",
                        "未用满预算不扣分，场景标签不作为计分槽位。",
                    ]
                ),
                "sensitivity_scenarios": [],
                "source_refs": [str(manifest.get("ruler_rule_net") or "")],
                "material_refs": [
                    item.get("rule_evidence_unit_ref")
                    for item in row.get("settled_materials") or ()
                ]
                + [
                    ref
                    for member in row.get("positive_members") or ()
                    for ref in member.get("supporting_unit_refs") or ()
                ],
            }
            for row in rule_net.get("rules") or ()
        }
    else:
        net_rows = {row["rule_code"]: row for row in rule_net.get("rules") or ()}
    if set(net_rows) != set(RULE_ORDER):
        raise ValueError("scoring detail requires exactly five rule net rows")

    configured = _rows(manifest.get("detail_sources") or (), "detail_sources")
    if len(configured) != len(detail_sources):
        raise ValueError("loaded scoring detail sources do not match manifest")
    by_rule: dict[str, list[dict[str, Any]]] = {code: [] for code in RULE_ORDER}
    for spec, loaded in zip(configured, detail_sources, strict=True):
        rule_code = str(spec.get("rule_code") or "")
        adapter = str(spec.get("adapter") or "")
        role = str(spec.get("role") or "")
        if rule_code not in by_rule or adapter not in ADAPTERS:
            raise ValueError("scoring detail source rule or adapter is invalid")
        if role not in {"primary", "supporting"}:
            raise ValueError("scoring detail source role must be primary or supporting")
        payload = loaded.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("scoring detail source payload must be an object")
        detail, signals = _source_detail(
            adapter=adapter, rule_code=rule_code, ruler=ruler, payload=payload
        )
        by_rule[rule_code].append(
            {
                "role": role,
                "adapter": adapter,
                "path": str(spec.get("path") or ""),
                "schema_version": payload.get("schema_version"),
                "status": payload.get("status"),
                "source_sha256": _hash(payload),
                "signals": signals,
                "detail": detail,
            }
        )

    rules: list[dict[str, Any]] = []
    for rule_code in RULE_ORDER:
        sources = by_rule[rule_code]
        primary = [source for source in sources if source["role"] == "primary"]
        if len(primary) != 1 or primary[0]["signals"] is None:
            raise ValueError(f"{rule_code} requires exactly one signal-bearing primary source")
        net = net_rows[rule_code]
        comparisons = {
            key: _rounded(primary[0]["signals"][key]) == _rounded(net[key])
            for key in ("positive_signal", "negative_signal", "rule_raw_net")
        }
        if not all(comparisons.values()):
            raise ValueError(f"{rule_code} primary detail does not reconcile to rule net")
        policy = scoring_policy["rules"][rule_code]
        factor_contract = _factor_contract_audit(
            rule_code=rule_code,
            policy=policy,
            detail=primary[0]["detail"],
        )
        translated_factors = _translate_factor_catalog(
            rule_code=rule_code,
            factor_catalog={
                key: value
                for key, value in policy.items()
                if isinstance(value, Mapping)
                and key not in {"formulas", "factor_roles"}
            },
            display_catalog=display_catalog,
        )
        rules.append(
            {
                "rule_code": rule_code,
                "rule_label": RULE_LABELS[rule_code],
                "calculation_status": net["calculation_status"],
                "historical_coverage_status": net["historical_coverage_status"],
                "positive_signal": net["positive_signal"],
                "negative_signal": net["negative_signal"],
                "rule_raw_net": net["rule_raw_net"],
                "rule_weight": net["rule_weight"],
                "weighted_raw_contribution": net["weighted_raw_contribution"],
                "formula": policy.get("formula") or policy.get("formulas") or {
                    "positive": policy.get("positive_formula"),
                    "negative": policy.get("negative_formula"),
                },
                "projection_mode": policy.get("projection_mode"),
                "aggregation_policy": policy.get("aggregation_policy"),
                "factor_contract": factor_contract,
                "factor_catalog": {
                    key: value
                    for key, value in policy.items()
                    if isinstance(value, Mapping)
                    and key not in {"formulas", "factor_roles"}
                },
                "factor_catalog_zh": translated_factors,
                "limitations": list(net.get("limitations") or ()),
                "sensitivity_scenarios": list(net.get("sensitivity_scenarios") or ()),
                "source_refs": list(net.get("source_refs") or ()),
                "material_refs": list(net.get("material_refs") or ()),
                "detail_reconciliation": {
                    "status": "reconciled",
                    "primary_adapter": primary[0]["adapter"],
                    "checks": comparisons,
                },
                "detail_sources": sources,
            }
        )

    historical_coverage_complete = all(
        row["historical_coverage_status"] == "coverage_complete" for row in rules
    )
    factor_contracts_current = all(
        not row["factor_contract"]["blocks_historical_completion"] for row in rules
    )
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "report_only_scoring_detail_export"
            if historical_coverage_complete and factor_contracts_current
            else "report_only_scoring_detail_incomplete_or_stale"
        ),
        "ruler": ruler,
        "ruler_ref": rule_net.get("ruler_ref"),
        "input_version": rule_net.get("input_version") or rule_net.get("task_code"),
        "summary": (
            {
                "declared_workset_weighted_raw_signal": rule_net["summary"][
                    "weighted_raw_signal"
                ],
                "historical_coverage_complete_rule_count": sum(
                    row["historical_coverage_status"] == "coverage_complete"
                    for row in rules
                ),
                "rule_count": 5,
                "formal_45_point_score": None,
            }
            if budget_net
            else dict(rule_net.get("summary") or {})
        ),
        "rules": rules,
        "evidence_factor_policy": dict(scoring_policy.get("evidence_factor") or {}),
        "evidence_factor_catalog_zh": _translate_factor_catalog(
            rule_code=None,
            factor_catalog={
                key: value
                for key, value in (scoring_policy.get("evidence_factor") or {}).items()
                if isinstance(value, Mapping) and key != "v4_ownership"
            },
            display_catalog=display_catalog,
        ),
        "declarations": {
            "all_primary_details_reconciled": True,
            "historical_coverage_complete": historical_coverage_complete,
            "current_factor_contracts_satisfied": factor_contracts_current,
            "completion_claim_allowed": (
                historical_coverage_complete and factor_contracts_current
            ),
            "formal_45_point_score": None,
            "tier": None,
            "ranking": None,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_scoring_allowed": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report


def _translate_factor_catalog(
    *,
    rule_code: str | None,
    factor_catalog: Mapping[str, Mapping[str, Any]],
    display_catalog: Mapping[str, Any],
) -> list[dict[str, Any]]:
    translations: dict[str, Any] = dict(display_catalog.get("common_factors") or {})
    if rule_code is not None:
        translations.update(
            ((display_catalog.get("rules") or {}).get(rule_code) or {}).get("factors")
            or {}
        )
    translated: list[dict[str, Any]] = []
    for factor_code, values in factor_catalog.items():
        factor_display = translations.get(factor_code)
        if not isinstance(factor_display, Mapping):
            raise ValueError(f"missing Chinese factor translation: {factor_code}")
        option_display = factor_display.get("options") or {}
        options = []
        for option_code, value in values.items():
            display = option_display.get(option_code)
            if not isinstance(display, Mapping):
                raise ValueError(
                    f"missing Chinese option translation: {factor_code}.{option_code}"
                )
            options.append(
                {
                    "option_code": option_code,
                    "label_zh": str(display.get("label_zh") or ""),
                    "description_zh": str(display.get("description_zh") or ""),
                    "value": value,
                    **{
                        key: item
                        for key, item in display.items()
                        if key not in {"label_zh", "description_zh"}
                    },
                }
            )
        translated.append(
            {
                "factor_code": factor_code,
                "label_zh": str(factor_display.get("label_zh") or ""),
                "description_zh": str(factor_display.get("description_zh") or ""),
                "options": options,
            }
        )
    return translated


def _text(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, (list, tuple)):
        return "、".join(str(item) for item in value)
    if isinstance(value, Mapping):
        return "；".join(
            f"{key}={_text(value[key])}" for key in sorted(value, key=str)
        )
    return str(value)


def _choice_text(
    material: Mapping[str, Any],
    factor_catalog_zh: Sequence[Mapping[str, Any]],
    evidence_factor_catalog_zh: Sequence[Mapping[str, Any]],
) -> str:
    projection = material.get("numeric_projection") or {}
    values = (
        projection.get("deterministic_dimension_values")
        or projection.get("dimension_values")
        or {}
    )
    choices = (
        projection.get("factor_option_codes")
        or projection.get("choices")
        or material.get("choices")
        or {}
    )
    if isinstance(choices, Mapping):
        factor_labels = {
            "attribution_factor": "皇帝归责强度",
            "source_factor": "史源完整度",
            "context_factor": "规则机制贴合度",
        }
        factor_labels.update({
            factor["factor_code"]: factor["label_zh"]
            for factor in (*factor_catalog_zh, *evidence_factor_catalog_zh)
        })
        return "；".join(
            f"{factor_labels.get(key, key)} {_rounded(values[key])}"
            if key in values
            else f"{factor_labels.get(key, key)} {_text(choice)}"
            for key, choice in choices.items()
        )
    return ""


def _display_materials(
    detail: Mapping[str, Any],
    fact_summaries: Mapping[str, str] | None = None,
) -> list[Mapping[str, Any]]:
    fact_summaries = fact_summaries or {}
    aggregates = {
        (aggregate.get("object_ref"), aggregate.get("side")): aggregate
        for aggregate in detail.get("object_side_aggregates") or ()
    }
    materials = []
    for source_material in detail.get("materials") or ():
        material = dict(source_material)
        material["fact_summary"] = material.get("projection_basis") or fact_summaries.get(
            str(material.get("unit_ref") or "")
        )
        aggregate = aggregates.get(
            (material.get("object_ref"), material.get("side"))
        )
        if aggregate:
            material["aggregation_text"] = "对象侧聚合"
            material["weighted_signal"] = aggregate.get("object_side_score")
        materials.append(material)

    rank_decay = (
        (detail.get("ruler_aggregate") or {}).get("rank_decay_detail") or {}
    )
    ranked_objects = {
        (item.get("person"), side): item
        for side in ("positive", "negative")
        for item in (rank_decay.get(side) or {}).get("objects") or ()
    }
    for judgment in detail.get("judgments") or ():
        for material in judgment.get("factor_materials") or ():
            choices = material.get("factor_choices") or {}
            ranked = ranked_objects.get(
                (judgment.get("person"), material.get("side"))
            ) or {}
            materials.append(
                {
                    **dict(material),
                    "person": judgment.get("person"),
                    "unit_ref": judgment.get("rule_evidence_unit_ref"),
                    "material_score": material.get("signed_material_score"),
                    "object_rank": ranked.get("rank"),
                    "object_weight": ranked.get("weight"),
                    "lane_scale": ranked.get("lane_scale"),
                    "weighted_signal": ranked.get("weighted_value"),
                    "aggregation_text": (
                        f"对象第{ranked.get('rank')}名；衰减{ranked.get('weight')}；"
                        f"通道系数×{ranked.get('lane_scale')}"
                        if ranked
                        else None
                    ),
                    "fact_summary": fact_summaries.get(
                        f"{judgment.get('rule_evidence_unit_ref')}|{material.get('side')}"
                    )
                    or fact_summaries.get(
                        str(judgment.get("rule_evidence_unit_ref") or "")
                    ),
                    "numeric_projection": {
                        "factor_option_codes": {
                            key: value.get("option_code")
                            for key, value in choices.items()
                        },
                        "deterministic_dimension_values": {
                            key: value.get("deterministic_value")
                            for key, value in choices.items()
                        },
                    },
                }
            )
    return materials


def _md_cell(value: object) -> str:
    return _text(value).replace("|", "\\|").replace("\n", " ")


def _display_name(value: object) -> str:
    text = _text(value)
    return DISPLAY_NAME_ALIASES.get(text, text)


def _role_text(values: object) -> str:
    if not isinstance(values, (list, tuple)):
        return _text(values)
    return "、".join(ROLE_LABELS.get(str(value), str(value)) for value in values)


def _side_text(value: object) -> str:
    text = _text(value)
    return SIDE_LABELS.get(text, text)


def _factor_option(
    row: Mapping[str, Any], factor_code: str, option_code: object
) -> Mapping[str, Any]:
    return next(
        (
            option
            for factor in row.get("factor_catalog_zh") or ()
            if factor.get("factor_code") == factor_code
            for option in factor.get("options") or ()
            if option.get("option_code") == option_code
        ),
        {},
    )


def _team_member_grade_text(row: Mapping[str, Any], member: Mapping[str, Any]) -> str:
    grade = member.get("grade")
    option = _factor_option(row, "talent_quality_factor", grade)
    return (
        f"{option.get('label_zh', grade)} (`{grade}`) / `{option.get('value', '—')}`"
    )


def _team_member_negative_pool_text(
    row: Mapping[str, Any], member: Mapping[str, Any]
) -> str:
    if not _decimal(member.get("negative_weighted_value") or 0):
        return "—"
    risk_class = member.get("window_negative_class")
    severity = member.get("window_negative_severity")
    severity_value = _factor_option(
        row, "negative_talent_severity_value", severity
    ).get("value")
    class_label = {
        "sycophant": "谄媚迎合",
        "favorite": "私宠亲信",
        "power_abuser": "滥权",
        "framer": "构陷",
        "extractive_official": "聚敛",
        "cruel_official": "酷烈执法",
        "incompetent_harmful": "无能致害",
        "traitorous_actor": "谋逆或严重背叛",
        "mixed_or_disputed": "混合或有争议",
    }.get(str(risk_class), str(risk_class))
    return (
        f"{_rounded(member.get('negative_weighted_value'))}"
        f"（{class_label}；严重度 {severity_value}）"
    )


def _team_multiplier_lines(
    row: Mapping[str, Any], detail: Mapping[str, Any]
) -> list[str]:
    factors = detail.get("factors") or {}
    pairs = (
        (
            "职能互补系数",
            "role_complementarity_factor",
            factors.get("functional_complementarity"),
        ),
        (
            "长期稳定系数",
            "long_term_stability_factor",
            factors.get("continuity_structure"),
        ),
    )
    lines = []
    for label, factor_code, option_code in pairs:
        option = _factor_option(row, factor_code, option_code)
        lines.append(
            f"- {label}：{option.get('label_zh', option_code)} = "
            f"`{option.get('value', '—')}`"
        )
    return lines


def _team_aggregation_lines(
    row: Mapping[str, Any], detail: Mapping[str, Any]
) -> list[str]:
    members = detail.get("members") or ()
    positive_pool = sum(
        (_decimal(member.get("positive_weighted_value") or 0) for member in members),
        Decimal("0"),
    )
    negative_pool = sum(
        (_decimal(member.get("negative_weighted_value") or 0) for member in members),
        Decimal("0"),
    )
    factors = detail.get("factors") or {}
    complementarity = _factor_option(
        row,
        "role_complementarity_factor",
        factors.get("functional_complementarity"),
    ).get("value")
    stability = _factor_option(
        row,
        "long_term_stability_factor",
        factors.get("continuity_structure"),
    ).get("value")
    return [
        f"- 正池：`{_rounded(positive_pool)}` × `{complementarity}` × `{stability}` "
        f"= `{row['positive_signal']}`",
        f"- 负池：`{_rounded(negative_pool)}` = `{row['negative_signal']}`"
        "（不乘正向团队结构系数）",
    ]


def _appointment_episode_facts(
    detail: Mapping[str, Any],
    assertion_outcomes: Mapping[str, str],
) -> list[dict[str, Any]]:
    judgments = {
        str(judgment.get("rule_evidence_unit_ref")): judgment
        for judgment in detail.get("judgments") or ()
    }
    trace = detail.get("assertion_episode_reu_trace") or {}
    projections: dict[str, list[tuple[str, str]]] = {}
    for unit in trace.get("rule_evidence_units") or ():
        judgment = judgments.get(str(unit.get("unit_code"))) or {}
        projection = (
            _display_name(judgment.get("person")),
            str(judgment.get("side") or "positive"),
        )
        for member in unit.get("members") or ():
            if member.get("member_type") == "episode":
                projections.setdefault(str(member.get("member_ref")), []).append(
                    projection
                )
    facts = []
    for episode in trace.get("episodes") or ():
        action = str(episode.get("action") or "")
        accepted_outcomes = [
            assertion_outcomes.get(str(link.get("assertion_ref")))
            for link in episode.get("assertion_links") or ()
        ]
        accepted_outcomes = [value for value in accepted_outcomes if value]
        for person, side in projections.get(str(episode.get("episode_id"))) or [
            ("—", "positive")
        ]:
            facts.append(
                {
                    "person": person,
                    "side": side,
                    "action": action,
                    "outcome": "、".join(accepted_outcomes)
                    or "、".join(episode.get("outcome") or ()),
                }
            )
    return facts


def _appointment_assertion_outcomes(row: Mapping[str, Any]) -> dict[str, str]:
    return next(
        (
            dict(source["detail"].get("accepted_assertion_outcomes") or {})
            for source in row.get("detail_sources") or ()
            if source.get("adapter") == "appointment_episode_assertion_support"
        ),
        {},
    )


def _appointment_episode_summaries(
    facts: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for fact in facts:
        key = f"{fact.get('unit_ref')}|{fact.get('side')}"
        text = str(fact.get("action") or "")
        if fact.get("outcome"):
            text += f"；结果：{fact['outcome']}"
        grouped.setdefault(key, []).append(text)
    return {key: "；".join(values) for key, values in grouped.items()}


def _appointment_inventory_audit(
    row: Mapping[str, Any], counted_people: set[str]
) -> list[str]:
    audit = next(
        (
            source["detail"]
            for source in row.get("detail_sources") or ()
            if source.get("adapter") == "appointment_candidate_inventory_audit"
        ),
        None,
    )
    expanded = next(
        (
            source["detail"]
            for source in row.get("detail_sources") or ()
            if source.get("adapter") == "appointment_expanded_shadow"
        ),
        {},
    )
    if not audit:
        return []
    prior_people = {
        _display_name(material.get("person"))
        for material in expanded.get("materials") or ()
        if material.get("person")
    }
    missing_prior = sorted(prior_people - counted_people)
    disposition_counts = audit.get("candidate_disposition_counts") or {}
    lines = [
        "### 数据去向审计",
        "",
        "| 审计项 | 当前结果 | 人工判断 |",
        "|---|---|---|",
        (
            "| 旧人审工作集未接入当前数值链 | "
            f"{('、'.join(missing_prior) if missing_prior else '无')} | "
            "不能因新正式链覆盖写入而静默丢失；须在626—649窗口重新接受后合并。 |"
        ),
        (
            "| 待回源候选 | "
            f"{audit.get('source_rebind_group_count')}个事件组，"
            f"{len(audit.get('source_rebind_people') or ())}名对象 | "
            f"{('、'.join(audit.get('source_rebind_people') or ()) or '无')}；"
            "冻结后仍有待回源项时不得宣告覆盖闭合。 |"
        ),
        (
            "| 候选冻结处置 | "
            f"{audit.get('judged_candidate_count')}/{audit.get('candidate_count')}已judge，"
            f"未决{audit.get('unresolved_candidate_count')} | "
            "仅在逐项处置闭合且人工冻结接受后声明覆盖完成。 |"
        ),
    ]
    return lines


def _team_member_fact_text(
    detail: Mapping[str, Any], member: Mapping[str, Any]
) -> str:
    talent_basis = str(member.get("talent_grade_basis") or "").replace(
        "故不降important", "故保留top，不降至important"
    )
    parts = [talent_basis]
    if member.get("window_negative_class"):
        unit_refs = set(member.get("supporting_unit_refs") or ())
        risk_facts = []
        for episode in (
            (detail.get("assertion_episode_reu_trace") or {}).get("episodes") or ()
        ):
            if (episode.get("lineage") or {}).get("unit_ref") not in unit_refs:
                continue
            action = episode.get("action")
            outcomes = "、".join(episode.get("outcome") or ())
            fact = f"负向事实：{action}"
            if outcomes:
                fact += f"；结果：{outcomes}"
            if fact not in risk_facts:
                risk_facts.append(fact)
        parts.extend(risk_facts)
    return "；".join(part for part in parts if part)


def _unscored_material_rows(row: Mapping[str, Any]) -> list[dict[str, str]]:
    materials: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in row["detail_sources"]:
        if source.get("adapter") != "material_budget_report":
            continue
        for item in source["detail"].get("unscored_materials") or ():
            material_id = str(item.get("material_id") or item.get("material"))
            if material_id in seen:
                continue
            seen.add(material_id)
            materials.append(
                {
                    "material": _display_name(item.get("material")),
                    "fact": str(item.get("fact") or ""),
                    "factor_assignment": _choice_text(
                        {
                            "numeric_projection": {
                                "factor_option_codes": item.get(
                                    "factor_option_codes"
                                )
                                or {},
                                "deterministic_dimension_values": item.get(
                                    "factor_values"
                                )
                                or {},
                            }
                        },
                        row.get("factor_catalog_zh") or (),
                        row.get("evidence_factor_catalog_zh") or (),
                    ),
                    "material_score": _rounded(item.get("material_score")),
                }
            )
    return materials


def render_i5b_scoring_detail_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    selection_summary = report.get("selection_summary")
    complete_selection = not selection_summary or selection_summary[
        "selected_all_five_rules"
    ]
    weighted_signal_label = "五条规则加权信号" if complete_selection else "所选规则加权信号小计"
    weighted_signal = (
        summary["declared_workset_weighted_raw_signal"]
        if complete_selection
        else selection_summary["selected_rule_weighted_raw_signal"]
    )
    coverage_complete_count = sum(
        row["historical_coverage_status"] == "coverage_complete"
        for row in report["rules"]
    )
    lines = [
        f"# {_text(report['ruler'])}当前计分详情",
        "",
        "> 本报告仅展示当前声明工作集的 shadow raw signal，不是45分、档位或排名。",
        "",
        "## 汇总",
        "",
        "| Rule | 正向 | 负向 | 净值 | 权重 | 加权贡献 | 历史覆盖 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["rules"]:
        lines.append(
            f"| {row['rule_label']} | {row['positive_signal']} | "
            f"{row['negative_signal']} | {row['rule_raw_net']} | {row['rule_weight']} | "
            f"{row['weighted_raw_contribution']} | "
            f"{'完成' if row['historical_coverage_status'] == 'coverage_complete' else '未完成'} |"
        )
    lines += [
        "",
        f"- {weighted_signal_label}：`{weighted_signal}`",
        f"- 历史覆盖完成：`{coverage_complete_count}/{len(report['rules'])}`",
        "- 正式45分、tier、排名：均未生成",
        "",
        "### 通用证据因子",
        "",
        f"- 公式：`{_text(report['evidence_factor_policy'].get('formula'))}`",
        f"- 取值范围：`{_text(report['evidence_factor_policy'].get('minimum'))}` 至 "
        f"`{_text(report['evidence_factor_policy'].get('maximum'))}`",
    ]

    for row in report["rules"]:
        primary = next(source for source in row["detail_sources"] if source["role"] == "primary")
        detail = primary["detail"]
        lines += [
            "",
            f"## {row['rule_label']}",
            "",
            f"- 当前净值：`{row['positive_signal']} - {row['negative_signal']} = {row['rule_raw_net']}`",
            f"- 加权贡献：`{row['rule_raw_net']} × {row['rule_weight']} = {row['weighted_raw_contribution']}`",
        ]
        if row["factor_contract"]["missing_v4_factor_inputs"]:
            lines.append(
                "- 旧投影诊断字段未提供（不阻断顶层规则因子计分）："
                f"`{_text(row['factor_contract']['missing_v4_factor_inputs'])}`"
            )

        episode_facts = (
            _appointment_episode_facts(
                detail, _appointment_assertion_outcomes(row)
            )
            if row["rule_code"] == "appointment_delegation"
            else []
        )
        if episode_facts:
            lines += [
                "",
                "### 计入 HistoricalEpisode",
                "",
                "| 对象 | 方向 | 事件动作 | 可归责结果 |",
                "|---|---|---|---|",
            ]
            for fact in episode_facts:
                lines.append(
                    f"| {_display_name(fact.get('person'))} | "
                    f"{_side_text(fact.get('side'))} | "
                    f"{_md_cell(fact.get('action'))} | "
                    f"{_md_cell(fact.get('outcome'))} |"
                )

        materials = _display_materials(
            detail,
            _appointment_episode_summaries(episode_facts),
        )
        if materials:
            fact_column_label = (
                "HistoricalEpisode 汇总"
                if episode_facts
                else "计分事实"
            )
            appointment_columns = row["rule_code"] == "appointment_delegation"
            lines += ["", "### 计分聚合" if episode_facts else "### 计入材料", ""]
            if appointment_columns:
                lines += [
                    f"| 对象 | 方向 | 材料分 | 对象合并分 / 排名 | 实际计入信号 | 因子取值 | {fact_column_label} |",
                    "|---|---|---:|---:|---:|---|---|",
                ]
            else:
                lines += [
                    f"| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 | {fact_column_label} |",
                    "|---|---|---:|---:|---|---|",
                ]
            for material in materials:
                subject = _display_name(
                    material.get("person") or material.get("subject") or "—"
                )
                score = material.get("material_score") or material.get("absolute_material_score")
                weighted = material.get("weighted_signal") or material.get(
                    "weighted_value"
                ) or "—"
                prefix = (
                    f"| {subject} | {_side_text(material.get('side'))} | "
                    f"{_rounded(score)} | "
                )
                if appointment_columns:
                    aggregate = material.get("object_aggregate_magnitude")
                    rank = material.get("object_rank")
                    prefix += (
                        f"{_rounded(aggregate) if aggregate is not None else '—'}"
                        f" / {f'第{rank}名' if rank is not None else '—'} | "
                    )
                lines.append(
                    prefix
                    + f"{_rounded(weighted)} | "
                    f"{_choice_text(material, row['factor_catalog_zh'], report['evidence_factor_catalog_zh'])} | "
                    f"{_md_cell(material.get('fact_summary'))} |"
                )

        if row["rule_code"] == "talent_discovery":
            quality_rows = detail.get("talent_quality_basis_rows") or ()
            if quality_rows:
                lines += [
                    "",
                    "### 人才发现候选优先级",
                    "",
                    "| 顺序 | 人物 | 人才档 | 发现程度 | 材料分 | 结算结果 | 政策 / 文治依据 |",
                    "|---:|---|---|---:|---:|---|---|",
                ]
                ordered_quality_rows = sorted(
                    quality_rows,
                    key=lambda item: (
                        -_decimal(item.get("material_score") or 0),
                        str(item.get("subject") or ""),
                    ),
                )
                for rank, material in enumerate(ordered_quality_rows, start=1):
                    basis = material["talent_quality_basis"]
                    grade_label = {
                        "ordinary": "普通",
                        "usable": "可用",
                        "important": "重要",
                        "top": "顶级",
                        "historic": "历史级",
                    }.get(str(basis.get("talent_grade")), _text(basis.get("talent_grade")))
                    discovery_value = (material.get("factor_values") or {}).get(
                        "discovery_level"
                    )
                    lines.append(
                        f"| {rank} | {_md_cell(material.get('subject'))} | "
                        f"{grade_label} | "
                        f"{_rounded(discovery_value) if discovery_value is not None else '—'} | "
                        f"{_rounded(material.get('material_score'))} | "
                        f"{'计入' if material.get('selection_status') == 'settled' else '合格，预算外'} | "
                        f"{_md_cell(basis.get('policy_civil_outcome_basis'))} |"
                    )

        governance_results = detail.get("governance_results") or ()
        if governance_results:
            lines += [
                "",
                "### 政策 / 文治成果",
                "",
                "| 已落实成果 |",
                "|---|",
            ]
            for result in governance_results:
                lines.append(
                    f"| {_md_cell(result.get('result'))} |"
                )
            boundary = detail.get("candidate_boundary_audit") or {}
            if boundary:
                lines += [
                    "",
                    "### 候选扫描与材料预算边界",
                    "",
                    f"- 状态：`{boundary['status']}`",
                    f"- 原始 unresolved：`{boundary['raw_unresolved_candidate_count']}`",
                    f"- 同源去重后边界候选：`{boundary['deduplicated_boundary_candidate_count']}`",
                    f"- 当前正向结算边界：`{boundary['current_positive_settlement_floor']}`",
                    f"- 候选：{_text(boundary['deduplicated_boundary_candidates'])}",
                    "- 不要求穷尽搜索；只处理可能改变当前 strongest-N 边界的下一批。",
                ]

        members = detail.get("members") or ()
        if members:
            lines += [
                "",
                "### 计入材料",
                "",
                "| 人物 | 正池贡献 | 负池贡献 | 人才档 / 基础系数 | 角色 | 计分事实 |",
                "|---|---:|---:|---|---|---|",
            ]
            for member in members:
                lines.append(
                    f"| {member['person']} | "
                    f"{_rounded(member.get('positive_weighted_value'))} | "
                    f"{_team_member_negative_pool_text(row, member)} | "
                    f"{_team_member_grade_text(row, member)} | "
                    f"{_role_text(member.get('roles'))} | "
                    f"{_md_cell(_team_member_fact_text(detail, member))} |"
                )

        if row["rule_code"] == "team_building" and detail.get("factors"):
            lines += ["", "### 当前计分系数", ""]
            lines.extend(_team_multiplier_lines(row, detail))
            lines += ["", "### 聚合对账", ""]
            lines.extend(_team_aggregation_lines(row, detail))
        if detail.get("calculation"):
            lines += ["", "### 计算展开", ""]
            lines.extend(
                f"- `{key}`：`{_text(value)}`" for key, value in detail["calculation"].items()
            )
        if detail.get("strict_current"):
            current = detail["strict_current"]
            if current.get("factor_choice"):
                lines += ["", "### 当前因子选择", ""]
                lines.extend(
                    f"- `{key}`：`{value}`" for key, value in current["factor_choice"].items()
                )
            if current.get("rejection_reason"):
                lines += ["", f"- 当前拒绝原因：{current['rejection_reason']}"]
        if detail.get("sensitivity"):
            lines += ["", f"- 条件敏感性（不计入当前净值）：`{_text(detail['sensitivity'])}`"]

        if row["rule_code"] == "appointment_delegation":
            counted_people = {
                _display_name(material.get("person") or material.get("subject"))
                for material in materials
                if material.get("person") or material.get("subject")
            }
            counted_people.update(
                _display_name(review.get("material"))
                for source in row.get("detail_sources") or ()
                if source.get("adapter") == "material_budget_report"
                for review in source["detail"].get("unscored_materials") or ()
                if review.get("material")
            )
            audit_lines = _appointment_inventory_audit(row, counted_people)
            if audit_lines:
                lines += [""] + audit_lines

        if row["limitations"]:
            lines += ["", "### 限制", ""]
            lines.extend(f"- {value}" for value in row["limitations"])
        unscored = _unscored_material_rows(row)
        if unscored:
            lines += [
                "",
                "### 未计入材料",
                "",
                "| 材料 | 因子赋值 | 材料分 | 事实 |",
                "|---|---|---:|---|",
            ]
            lines.extend(
                f"| {_md_cell(item['material'])} | "
                f"{_md_cell(item['factor_assignment'])} | "
                f"{item['material_score']} | {_md_cell(item['fact'])} |"
                for item in unscored
            )

    source_review_quality = report.get("source_review_quality") or {}
    if source_review_quality:
        policy_review = source_review_quality.get("policy_review") or {}
        disposition_counts = {
            disposition: sum(
                len(row.get("passage_refs") or ())
                for row in policy_review.get("dispositions") or ()
                if row.get("disposition") == disposition
            )
            for disposition in ("counted", "supporting", "excluded")
        }
        lines += [
            "",
            "## 新回源质量闭合",
            "",
            f"- 当前计分实际引用：`{source_review_quality.get('source_passage_count', 0)}` 条精确 passage",
            f"- 皇帝政策精确回源池：`{policy_review.get('exact_policy_passage_count', 0)}` 条",
            f"- 政策处置：计分 `{disposition_counts['counted']}`，支撑 `{disposition_counts['supporting']}`，排除 `{disposition_counts['excluded']}`",
            "- 人物完整生涯与当前皇帝 episode 分离："
            + (
                "已通过"
                if (source_review_quality.get("quality_declarations") or {}).get(
                    "full_career_profile_ruler_window_separation"
                )
                else "旧版输入未声明"
            ),
        ]
        candidate_reviews = policy_review.get("candidate_reviews") or ()
        if candidate_reviews:
            disposition_labels = {
                "counted": "计入",
                "supporting": "支撑",
                "excluded": "排除",
                "insufficient": "证据不足",
            }
            lines += [
                "",
                "### 政策候选 Judge",
                "",
                "| 政策候选 | 结论 | Judge理由 |",
                "|---|---|---|",
            ]
            lines.extend(
                f"| {_md_cell(item['label'])} | "
                f"{disposition_labels.get(item['disposition'], item['disposition'])} | "
                f"{_md_cell(item['reason'])} |"
                for item in candidate_reviews
            )

    lines += [
        "",
        "## 安全声明",
        "",
        "- 本次导出模型调用：0",
        "- 本次导出数据库写入：0",
        "- 未执行动态映射，未生成正式评分或排名",
        "",
    ]
    return "\n".join(lines)


def _person_matches(candidate: object, person: str) -> bool:
    text = str(candidate or "")
    if text == person or text == f"{person}身后信用":
        return True
    if len(person) < 2:
        return False
    parts = re.split(r"[、，,／/；;与和]", text)
    return any(part.strip().startswith(person) for part in parts)


def _person_refs(report: Mapping[str, Any], person: str) -> set[str]:
    refs: set[str] = set()
    for rule in report["rules"]:
        for source in rule["detail_sources"]:
            detail = source["detail"]
            for member in detail.get("members") or ():
                if not _person_matches(member.get("person"), person):
                    continue
                person_ref = str(member.get("person_ref") or "")
                if person_ref.startswith("PER-V4-"):
                    refs.add(person_ref)
                profile_ref = str(member.get("profile_ref") or "")
                if profile_ref.startswith("PROFILE-PER-V4-"):
                    refs.add(profile_ref.split("@", 1)[0].removeprefix("PROFILE-"))
            for material in detail.get("materials") or ():
                if not _person_matches(
                    material.get("person") or material.get("subject"), person
                ):
                    continue
                object_ref = str(material.get("object_ref") or "")
                if object_ref.startswith("PER-V4-"):
                    refs.add(object_ref)
    return refs


def _episode_matches_person(
    episode: Mapping[str, Any], person: str, person_refs: set[str]
) -> bool:
    participant_refs = {
        str(row.get("person_ref") or "")
        for row in episode.get("participants") or ()
    }
    if participant_refs & person_refs:
        return True
    searchable = {
        "action": episode.get("action"),
        "responsibility": episode.get("responsibility"),
        "outcome": episode.get("outcome"),
        "consequence": episode.get("consequence"),
    }
    return person in json.dumps(searchable, ensure_ascii=False, sort_keys=True)


def _participation_factor_assignment(
    rule: Mapping[str, Any], item: Mapping[str, Any]
) -> str:
    if item.get("numeric_projection"):
        material = item
    elif item.get("factor_values"):
        material = {
            "numeric_projection": {
                "factor_option_codes": item.get("factor_option_codes") or {},
                "deterministic_dimension_values": item.get("factor_values") or {},
            }
        }
    else:
        grade = item.get("grade") or item.get("talent_grade")
        value = item.get("talent_value")
        grade_label = {
            "ordinary": "普通",
            "usable": "可用",
            "important": "重要",
            "top": "顶级",
            "historic": "历史级",
        }.get(str(grade), _text(grade))
        return (
            f"人才档 {grade_label}；基础系数 {_text(value)}"
            if grade or value is not None
            else "—"
        )
    return _choice_text(
        material,
        rule.get("factor_catalog_zh") or (),
        rule.get("evidence_factor_catalog_zh") or (),
    )


def _accepted_assertion_index(
    report: Mapping[str, Any], selected_rules: set[str]
) -> dict[str, Mapping[str, Any]]:
    return {
        str(assertion["assertion_code"]): assertion
        for rule in report["rules"]
        if rule["rule_code"] in selected_rules
        for source in rule["detail_sources"]
        for assertion in source["detail"].get("accepted_assertions") or ()
        if assertion.get("assertion_code")
    }


def _person_participations(
    report: Mapping[str, Any], person: str, selected_rules: set[str]
) -> list[dict[str, Any]]:
    participations: list[dict[str, Any]] = []
    person_refs = _person_refs(report, person)
    assertion_index = _accepted_assertion_index(report, selected_rules)
    for rule in report["rules"]:
        rule_code = rule["rule_code"]
        if rule_code not in selected_rules:
            continue
        for source in rule["detail_sources"]:
            detail = source["detail"]
            role = source["role"]

            def add(kind: str, item: object) -> None:
                item_mapping = item if isinstance(item, Mapping) else {}
                participations.append(
                    {
                        "ruler": report["ruler"],
                        "rule_code": rule_code,
                        "rule_label": rule["rule_label"],
                        "source_role": role,
                        "source_adapter": source["adapter"],
                        "source_path": source["path"],
                        "participation_kind": kind,
                        "rule_raw_net": rule["rule_raw_net"],
                        "rule_weight": rule["rule_weight"],
                        "individual_score_claimed": False,
                        "detail": item,
                        "factor_assignment": _participation_factor_assignment(
                            rule, item_mapping
                        ),
                    }
                )

            for material in detail.get("materials") or ():
                candidate = material.get("person") or material.get("subject")
                if _person_matches(candidate, person):
                    add("counted_material" if role == "primary" else "supporting_material", material)
            for material in detail.get("unscored_materials") or ():
                if _person_matches(material.get("material"), person):
                    add("unscored_material", material)
            for member in detail.get("members") or ():
                if _person_matches(member.get("person"), person):
                    add("team_member", member)
            for excluded in detail.get("excluded_net_additions") or ():
                if _person_matches(excluded.get("person"), person):
                    add("excluded_net_addition", excluded)
            for blocked in detail.get("blocked_or_excluded") or ():
                if _person_matches(blocked.get("person"), person):
                    add("blocked_or_excluded", blocked)
            for gap in detail.get("not_yet_disposed_named_gaps") or ():
                if _person_matches(gap, person):
                    add("not_yet_disposed_named_gap", {"person": gap})
            for insufficient in detail.get("insufficient_projections") or ():
                if _person_matches(insufficient.get("subject"), person):
                    add("insufficient_projection", insufficient)
            if _person_matches(detail.get("subject"), person) and detail.get("observations"):
                add(
                    "source_rebind_record",
                    {
                        "subject": detail["subject"],
                        "observations": detail["observations"],
                        "factor_projection": detail.get("factor_projection"),
                    },
                )
            for unit in detail.get("projection_units") or ():
                if _person_matches(unit.get("subject"), person):
                    add("source_rebind_record", unit)
            trace = detail.get("assertion_episode_reu_trace") or {}
            for episode in trace.get("episodes") or ():
                if _episode_matches_person(episode, person, person_refs):
                    enriched_episode = dict(episode)
                    enriched_episode["accepted_assertions"] = [
                        assertion_index[str(link.get("assertion_ref"))]
                        for link in episode.get("assertion_links") or ()
                        if str(link.get("assertion_ref")) in assertion_index
                    ]
                    add("historical_episode", enriched_episode)

    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for participation in participations:
        detail = participation["detail"]
        identity = str(
            detail.get("episode_id")
            or detail.get("unit_ref")
            or detail.get("material_code")
            or detail.get("material_id")
            or detail.get("material")
            or detail.get("person")
            or ""
        )
        key = (
            participation["rule_code"],
            participation["participation_kind"],
            identity,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(participation)
    return unique


def _filtered_ruler_report(
    report: Mapping[str, Any], selected_rules: set[str]
) -> dict[str, Any]:
    filtered = dict(report)
    filtered["rules"] = [
        row for row in report["rules"] if row["rule_code"] in selected_rules
    ]
    selected_weighted = sum(
        (
            _decimal(row["rule_raw_net"]) * _decimal(row["rule_weight"])
            for row in filtered["rules"]
        ),
        Decimal("0"),
    )
    filtered["selection_summary"] = {
        "selected_rule_count": len(filtered["rules"]),
        "selected_rule_weighted_raw_signal": _rounded(selected_weighted),
        "selected_all_five_rules": len(filtered["rules"]) == len(RULE_ORDER),
    }
    return filtered


def build_i5b_scoring_detail_selection(
    *,
    catalog: Mapping[str, Any],
    selection: Mapping[str, Any],
    ruler_reports: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if catalog.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise ValueError("scoring detail catalog schema mismatch")
    if selection.get("schema_version") != SELECTION_SCHEMA_VERSION:
        raise ValueError("scoring detail selection schema mismatch")
    catalog_rulers = [str(row.get("ruler") or "") for row in catalog.get("entries") or ()]
    if not catalog_rulers or len(set(catalog_rulers)) != len(catalog_rulers):
        raise ValueError("scoring detail catalog rulers must be non-empty and unique")
    if set(catalog_rulers) != set(ruler_reports):
        raise ValueError("loaded ruler reports do not match scoring detail catalog")
    if any(ruler_reports[ruler].get("ruler") != ruler for ruler in catalog_rulers):
        raise ValueError("scoring detail catalog ruler does not match loaded report")

    rulers = [str(value) for value in selection.get("rulers") or ()]
    people = [str(value) for value in selection.get("people") or ()]
    rules = [str(value) for value in selection.get("rules") or RULE_ORDER]
    if len(set(rulers)) != len(rulers) or len(set(people)) != len(people):
        raise ValueError("scoring detail selections must be unique")
    unknown_rulers = [value for value in rulers if value not in ruler_reports]
    unknown_rules = [value for value in rules if value not in RULE_ORDER]
    if unknown_rulers or unknown_rules:
        raise ValueError(
            f"unknown scoring detail selection: rulers={unknown_rulers}, rules={unknown_rules}"
        )
    if not rulers and not people:
        raise ValueError("select at least one ruler or person")
    selected_rules = set(rules)
    person_scope = str(selection.get("person_scope") or "catalog")
    if person_scope not in {"catalog", "selected_rulers"}:
        raise ValueError("person_scope must be catalog or selected_rulers")
    scoped_rulers = catalog_rulers if person_scope == "catalog" else rulers
    if person_scope == "selected_rulers" and people and not rulers:
        raise ValueError("selected_rulers person scope requires ruler selections")

    selected_ruler_reports = [
        _filtered_ruler_report(ruler_reports[ruler], selected_rules) for ruler in rulers
    ]
    person_rows: list[dict[str, Any]] = []
    unmatched_people: list[str] = []
    for person in people:
        participations = [
            participation
            for ruler in scoped_rulers
            for participation in _person_participations(
                ruler_reports[ruler], person, selected_rules
            )
        ]
        if not participations:
            unmatched_people.append(person)
        person_rows.append(
            {
                "person": person,
                "participation_count": len(participations),
                "participations": participations,
                "individual_score": None,
                "individual_score_claimed": False,
            }
        )
    if unmatched_people and bool(selection.get("strict", True)):
        raise ValueError(f"selected people have no matching participation: {unmatched_people}")

    report: dict[str, Any] = {
        "schema_version": SELECTION_REPORT_SCHEMA_VERSION,
        "status": "report_only_selected_scoring_detail_export",
        "selection": {
            "rulers": rulers,
            "people": people,
            "rules": rules,
            "person_scope": person_scope,
            "strict": bool(selection.get("strict", True)),
        },
        "selected_ruler_reports": selected_ruler_reports,
        "people": person_rows,
        "unmatched_people": unmatched_people,
        "declarations": {
            "partial_rule_selection_not_claimed_as_complete_item_score": True,
            "person_participation_not_aggregated_as_person_score": True,
            "formal_45_point_score": None,
            "tier": None,
            "ranking": None,
            "model_call_count": 0,
            "database_write_count": 0,
        },
    }
    report["report_sha256"] = _hash(report)
    return report


def render_i5b_scoring_detail_selection_markdown(report: Mapping[str, Any]) -> str:
    selection = report["selection"]
    ruler_sections = (
        []
        if report["people"]
        else [
            render_i5b_scoring_detail_markdown(ruler_report).rstrip()
            for ruler_report in report["selected_ruler_reports"]
        ]
    )
    if not report["people"]:
        return "\n\n".join(ruler_sections) + "\n"

    binding_warnings: dict[tuple[str, str, str], dict[str, str]] = {}
    for person in report["people"]:
        episodes = [
            row
            for row in person["participations"]
            if row["participation_kind"] == "historical_episode"
        ]
        episode_reus = {
            (
                row["rule_code"],
                str((row["detail"].get("lineage") or {}).get("unit_ref") or ""),
            )
            for row in episodes
        }
        episode_rules = {row["rule_code"] for row in episodes}
        for row in person["participations"]:
            if row["participation_kind"] != "counted_material":
                continue
            detail = row["detail"]
            reu = str(detail.get("rule_evidence_unit_ref") or "")
            if not reu or row["rule_code"] not in episode_rules:
                continue
            if (row["rule_code"], reu) in episode_reus:
                continue
            material_id = str(
                detail.get("material_id")
                or detail.get("material_code")
                or detail.get("unit_ref")
                or ""
            )
            binding_warnings[(row["ruler"], row["rule_code"], material_id)] = {
                "ruler": row["ruler"],
                "rule_label": row["rule_label"],
                "material": str(
                    detail.get("subject")
                    or detail.get("material")
                    or detail.get("person")
                    or "未命名材料"
                ),
            }

    lines = [
        "# 臣子计分材料参与详情",
        "",
        f"- 臣子：{_text(selection['people'])}",
        f"- 规则：{_text([RULE_LABELS[code] for code in selection['rules']])}",
        "",
        "> 臣子条目只表示材料参与，不构成臣子个人分数。",
    ]
    if binding_warnings:
        lines += ["", "## 数据问题", ""]
        lines.extend(
            f"- {item['ruler']}的“{item['material']}”已经计入{item['rule_label']}，"
            "但没有对应的同规则历史事件，当前不应视为证据链闭合。"
            for item in binding_warnings.values()
        )
    for person in report["people"]:
        material_rows = [
            row
            for row in person["participations"]
            if row["participation_kind"] != "historical_episode"
        ]
        episode_rows = [
            row
            for row in person["participations"]
            if row["participation_kind"] == "historical_episode"
        ]
        lines += [
            "",
            f"## 臣子：{person['person']}",
            "",
            f"参与项数量：`{person['participation_count']}`；个人分数：未生成。",
        ]
        if material_rows:
            lines += [
                "",
                "### 材料",
                "",
                "| 规则 | 状态 | 材料 | 因子赋值 | 材料分 | 对象合并分 / 排名 | 实际计入信号 | 事实 |",
                "|---|---|---|---|---:|---:|---:|---|",
            ]
        for participation in material_rows:
            detail = participation["detail"]
            material = (
                detail.get("subject")
                or detail.get("material")
                or detail.get("person")
                or "未命名材料"
            )
            score = (
                detail.get("material_score")
                or detail.get("absolute_material_score")
                or "—"
            )
            aggregate = detail.get("object_aggregate_magnitude")
            rank = detail.get("object_rank")
            aggregate_text = (
                f"{_rounded(aggregate)} / 第{rank}名"
                if aggregate is not None and rank is not None
                else "—"
            )
            weighted = detail.get("weighted_signal")
            weighted_text = (
                _rounded(weighted) if weighted is not None and weighted != "" else "—"
            )
            status = {
                "counted_material": "计入",
                "supporting_material": "支持材料",
                "unscored_material": "未计入",
                "team_member": "团队画像",
                "excluded_net_addition": "排除净增",
                "blocked_or_excluded": "阻断或排除",
                "not_yet_disposed_named_gap": "待处置",
                "insufficient_projection": "证据不足",
                "source_rebind_record": "来源回绑",
            }.get(participation["participation_kind"], "其他")
            lines.append(
                f"| {_md_cell(participation['rule_label'])} | {status} | "
                f"{_md_cell(material)} | "
                f"{_md_cell(participation['factor_assignment'])} | "
                f"{_text(score)} | "
                f"{aggregate_text} | {weighted_text} | "
                f"{_md_cell(detail.get('fact') or detail.get('projection_basis'))} |"
            )
        if episode_rows:
            lines += [
                "",
                "### 历史事件",
                "",
                "| 规则 | 动作 | 结果 | 史源摘录 |",
                "|---|---|---|---|",
            ]
        for participation in episode_rows:
            episode = participation["detail"]
            evidence_quotes = []
            for assertion in episode.get("accepted_assertions") or ():
                attribution = assertion.get("source_attribution") or {}
                quoted_text = str(attribution.get("quoted_text") or "").strip()
                if not quoted_text:
                    continue
                work = str(attribution.get("work") or "史源").strip()
                excerpt = f"《{work}》{quoted_text}"
                if excerpt not in evidence_quotes:
                    evidence_quotes.append(excerpt)
            source_display = "；".join(evidence_quotes)
            if not source_display:
                source_display = str(
                    (episode.get("lineage") or {}).get("source_url") or ""
                )
            lines.append(
                f"| {_md_cell(participation['rule_label'])} | "
                f"{_md_cell(episode.get('action'))} | "
                f"{_md_cell(episode.get('outcome'))} | "
                f"{_md_cell(source_display or '当前材料未附原文摘录')} |"
            )
    sections = ruler_sections + ["\n".join(lines)]
    return "\n\n".join(sections)
