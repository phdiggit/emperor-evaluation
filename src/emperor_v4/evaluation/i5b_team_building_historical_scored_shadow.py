from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.i5b_assertion_episode_trace import (
    build_assertion_episode_trace,
)
from emperor_v4.evaluation.team_building_v8_scored_shadow import (
    resolve_effective_person_profiles,
)


SCHEMA_VERSION = "i5b-team-building-historical-scored-shadow-v2"
POLICY_VERSION = "team-building-historical-profile-aligned-raw-signal-v2"
CORE_ROLES = ("decision", "administration", "military", "correction")


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


def _decimal(value: object, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"{label} must be decimal-compatible") from exc


def _rounded(value: Decimal) -> str:
    if value == 0:
        return "0.000000000000"
    return str(value.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP))


def _maximum_role_matching(members: Sequence[Mapping[str, Any]]) -> int:
    role_sets = [set(row.get("role_families") or ()) for row in members]

    def visit(role_index: int, used: set[int]) -> int:
        if role_index == len(CORE_ROLES):
            return len(used)
        best = visit(role_index + 1, used)
        role = CORE_ROLES[role_index]
        for member_index, roles in enumerate(role_sets):
            if member_index not in used and role in roles:
                best = max(best, visit(role_index + 1, used | {member_index}))
        return best

    return visit(0, set())


def build_team_building_historical_scored_shadow(
    *,
    roster_payload: Mapping[str, Any],
    formal_acceptance: Mapping[str, Any],
    scoring_policy: Mapping[str, Any],
    authorized_promotion: Mapping[str, Any],
    supplemental_promotion: Mapping[str, Any],
    calibrations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if roster_payload.get("task_code") != "I5B-HC-TEAM-BUILDING-001":
        raise ValueError("team-building historical closeout task_code mismatch")
    if roster_payload.get("historical_coverage_complete") is not True:
        raise ValueError("candidate universe must be completely dispositioned")
    if formal_acceptance.get("rule_code") != "team_building":
        raise ValueError("formal acceptance rule mismatch")
    if not (formal_acceptance.get("declarations") or {}).get(
        "formal_fact_acceptance"
    ):
        raise ValueError("formal fact acceptance is required")

    candidates = _rows(roster_payload.get("candidate_universe"), "candidate universe")
    if not candidates or any(not row.get("final_disposition") for row in candidates):
        raise ValueError("every frozen candidate requires one final disposition")
    names = [str(row["person"]) for row in candidates]
    if len(names) != len(set(names)):
        raise ValueError("candidate universe contains duplicate people")

    members = [deepcopy(dict(row)) for row in _rows(
        roster_payload.get("accepted_members"), "accepted members"
    )]
    accepted_names = {
        str(row["person"])
        for row in candidates
        if str(row["final_disposition"]).startswith("accept_")
    }
    if accepted_names != {str(row["person"]) for row in members}:
        raise ValueError("accepted member roster does not match candidate dispositions")
    if any(row.get("acceptance_basis") != "independent_primary_source_review" for row in members):
        raise ValueError("V3 or suggestion-pool hints may not establish formal members")
    if any(row.get("negative_review_completed") is not True for row in members):
        raise ValueError("each accepted member requires completed negative review")

    profiles, latest_talent_policy_version = resolve_effective_person_profiles(
        authorized_promotion,
        supplemental_promotion,
        calibrations,
    )

    team_policy = ((scoring_policy.get("rules") or {}).get("team_building") or {})
    talent_values = {
        key: _decimal(value, f"talent value {key}")
        for key, value in (team_policy.get("talent_quality_factor") or {}).items()
    }
    severity_values = {
        key: _decimal(value, f"negative severity {key}")
        for key, value in (
            team_policy.get("negative_talent_severity_value") or {}
        ).items()
    }
    class_values = {
        key: _decimal(value, f"negative class {key}")
        for key, value in (
            team_policy.get("negative_talent_class_relevance") or {}
        ).items()
    }
    complementarity_values = {
        key: _decimal(value, f"complementarity {key}")
        for key, value in (
            team_policy.get("role_complementarity_factor") or {}
        ).items()
    }
    continuity_values = {
        key: _decimal(value, f"continuity {key}")
        for key, value in (
            team_policy.get("long_term_stability_factor") or {}
        ).items()
    }

    for member in members:
        person_ref = str(member["person_ref"])
        if person_ref not in profiles:
            raise ValueError(f"accepted member lacks current person profile: {person_ref}")
        profile = profiles[person_ref]
        if profile["negative_review_completed"] is not True:
            raise ValueError("current person profile requires completed negative review")
        member["roster_declared_talent_grade"] = member.pop(
            "accepted_talent_grade", None
        )
        member["effective_talent_grade"] = profile["effective_grade"]
        member["talent_grade_basis"] = profile["effective_grade_basis"]
        member["talent_calibration_policy_version"] = profile[
            "calibration_policy_version"
        ]
        member["profile_ref"] = profile["profile_ref"]
        member["roster_declared_negative_talent_class"] = member.pop(
            "negative_talent_class", None
        )
        member["roster_declared_negative_talent_severity"] = member.pop(
            "negative_talent_severity", None
        )
        member["negative_talent_class"] = profile["negative_talent_class"]
        member["negative_talent_severity"] = profile["negative_talent_severity"]
        grade = str(member["effective_talent_grade"])
        member["talent_value"] = talent_values[grade]
        risk_class = member.get("negative_talent_class")
        risk_severity = member.get("negative_talent_severity")
        if (risk_class is None) != (risk_severity is None):
            raise ValueError("negative profile axes must be jointly present or absent")
        member["negative_value"] = (
            Decimal("0")
            if risk_class is None
            else severity_values[str(risk_severity)] * class_values[str(risk_class)]
        )

    positive_order = sorted(
        members, key=lambda row: (-row["talent_value"], row["person_ref"])
    )
    positive_pool = Decimal("0")
    for rank, member in enumerate(positive_order, start=1):
        weight = Decimal("1") / Decimal(rank).sqrt()
        member["positive_rank"] = rank
        member["positive_weight"] = weight
        member["positive_weighted_value"] = member["talent_value"] * weight
        positive_pool += member["positive_weighted_value"]

    negative_order = sorted(
        (row for row in members if row["negative_value"] > 0),
        key=lambda row: (-row["negative_value"], row["person_ref"]),
    )
    negative_pool = Decimal("0")
    for rank, member in enumerate(negative_order, start=1):
        weight = Decimal("1") / Decimal(rank).sqrt()
        member["negative_rank"] = rank
        member["negative_weight"] = weight
        member["negative_weighted_value"] = member["negative_value"] * weight
        negative_pool += member["negative_weighted_value"]

    matching = _maximum_role_matching(members)
    complementarity = (
        "balanced_four"
        if matching == 4
        else "strong_three"
        if matching == 3
        else "ordinary_two"
        if matching == 2
        else "homogeneous"
    )
    covered_roles = sorted(
        set().union(*(set(row["role_families"]) for row in members))
        & set(CORE_ROLES)
    )
    continuity = str(roster_payload["structural_observation"]["continuity_structure"])
    complementarity_factor = complementarity_values[complementarity]
    continuity_factor = continuity_values[continuity]
    positive_signal = positive_pool * complementarity_factor * continuity_factor
    negative_signal = negative_pool * complementarity_factor * continuity_factor
    rule_raw_net = positive_signal - negative_signal

    historic_count = sum(row["effective_talent_grade"] == "historic" for row in members)
    high_count = sum(
        row["effective_talent_grade"] in {"historic", "top"} for row in members
    )
    qualified_count = sum(
        row["effective_talent_grade"] in {"historic", "top", "important"}
        for row in members
    )
    talent_depth = (
        "multi_historic"
        if historic_count >= 2
        else "multi_top"
        if high_count >= 2
        else "adequate_mixed"
        if qualified_count >= 2
        else "thin"
    )
    material_risks = [
        row
        for row in members
        if row.get("negative_talent_severity") in {"material", "major", "historic"}
    ]
    negative_exposure = (
        "historic_or_systemic_exposure"
        if any(row.get("negative_talent_severity") == "historic" for row in members)
        else "material_exposure"
        if material_risks
        else "bounded_minor"
        if any(row.get("negative_talent_severity") == "minor" for row in members)
        else "none_observed"
    )

    trace_units = [
        {
            "unit_ref": str(row["unit_ref"]),
            "side": str(row["side"]),
            "projection_basis": str(row["projection_basis"]),
        }
        for row in _rows(roster_payload.get("evidence_units"), "evidence units")
    ]
    trace = build_assertion_episode_trace(
        rule_code="team_building",
        trace_units=trace_units,
        assertion_payload=formal_acceptance,
    )
    window_ref = "TEAM-WINDOW-LISHIMIN-626-649@historical-freeze-v1"
    contribution_seed = [
        POLICY_VERSION,
        window_ref,
        formal_acceptance.get("report_sha256"),
        roster_payload.get("report_sha256"),
    ]
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "task_code": roster_payload["task_code"],
        "status": "team_building_historical_scored_shadow_complete",
        "rule_code": "team_building",
        "ruler": "李世民",
        "window": {"start": 626, "end": 649, "date_precision": "year"},
        "window_ref": window_ref,
        "historical_coverage_complete": True,
        "factors": {
            "talent_depth": talent_depth,
            "core_role_coverage": "four_core" if len(covered_roles) == 4 else "partial",
            "functional_complementarity": complementarity,
            "continuity_structure": continuity,
            "confidant_dependency": roster_payload["structural_observation"][
                "confidant_dependency"
            ],
            "negative_profile_exposure": negative_exposure,
        },
        "factor_diagnostics": {
            "accepted_member_count": len(members),
            "historic_count": historic_count,
            "historic_or_top_count": high_count,
            "qualified_member_count": qualified_count,
            "covered_core_roles": covered_roles,
            "maximum_independent_role_matching": matching,
            "candidate_universe_count": len(candidates),
        },
        "members": [
            {
                key: _rounded(value) if isinstance(value, Decimal) else value
                for key, value in row.items()
            }
            for row in sorted(members, key=lambda item: item["person_ref"])
        ],
        "raw_signal": {
            "positive_pool": _rounded(positive_pool),
            "negative_pool": _rounded(negative_pool),
            "role_complementarity_factor": _rounded(complementarity_factor),
            "long_term_stability_factor": _rounded(continuity_factor),
            "positive_signal": _rounded(positive_signal),
            "negative_signal": _rounded(negative_signal),
            "rule_raw_net": _rounded(rule_raw_net),
        },
        "score_contribution": {
            "contribution_ref": "SC-TEAM-" + _hash(contribution_seed)[:24].upper(),
            "rule_code": "team_building",
            "primary_owner": "ruler_time_window",
            "primary_owner_ref": window_ref,
            "dedup_key": _hash(["team_building", *contribution_seed]),
            "excluded_reuse": ["member_discovery_events", "member_appointment_events"],
            "rule_raw_net": _rounded(rule_raw_net),
            "score_rate": None,
            "score": None,
            "tier": None,
            "ranking": None,
        },
        "assertion_episode_reu_trace": trace,
        "summary": {
            "formal_assertion_count": formal_acceptance["summary"]["assertion_count"],
            "episode_count": trace["episode_count"],
            "rule_evidence_unit_count": trace["rule_evidence_unit_count"],
            "score_contribution_count": 1,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
        },
        "declarations": {
            "v3_data_or_25_person_pool_used_as_fact": False,
            "formal_facts_consumed": True,
            "report_only": True,
            "formal_scoring_allowed": False,
            "dynamic_mapping_applied": False,
            "score_45": None,
            "tier": None,
            "ranking": None,
        },
        "input_refs": {
            "candidate_roster_sha256": roster_payload.get("report_sha256"),
            "formal_acceptance_sha256": formal_acceptance.get("report_sha256"),
            "source_cache_output_fingerprint": roster_payload.get(
                "source_cache_output_fingerprint"
            ),
            "latest_talent_policy_version": latest_talent_policy_version,
            "effective_profile_set_fingerprint": _hash(
                [
                    {
                        "person_ref": row["person_ref"],
                        "profile_ref": row["profile_ref"],
                        "effective_talent_grade": row["effective_talent_grade"],
                        "talent_calibration_policy_version": row[
                            "talent_calibration_policy_version"
                        ],
                    }
                    for row in sorted(members, key=lambda item: item["person_ref"])
                ]
            ),
        },
    }
    result["report_sha256"] = _hash(result)
    return result
