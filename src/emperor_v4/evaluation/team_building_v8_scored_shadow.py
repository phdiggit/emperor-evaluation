from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "team-building-v8-scored-shadow-report-v3"
POLICY_VERSION = "team-building-v8-person-profile-raw-signal-v3"
STRUCTURAL_SCHEMA_VERSION = "team-building-structural-observation-v3"
STRUCTURAL_POLICY_VERSION = "team-building-v8-full-structural-observation-v2"
CORE_ROLES = ("decision", "administration", "military", "correction")
WINDOW_UNITS = (
    "TB-O01", "TB-O02", "TB-O03", "TB-O04", "TB-O05", "TB-O06",
    "TB-O07", "TB-O08", "TB-S01", "TB-S02", "TB-S03", "TB-S04",
)


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
    except Exception as exc:  # pragma: no cover - defensive contract guard
        raise ValueError(f"{label} must be decimal-compatible") from exc


def _rounded(value: Decimal) -> str:
    if value == 0:
        return "0.000000000000"
    return str(value.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP))


def _negative_review_state(
    evaluation: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> tuple[str, bool]:
    review_completed = evaluation.get("review_completed")
    if isinstance(review_completed, bool):
        return str(evaluation.get("finding_status") or ""), review_completed
    supplemental_version = str(snapshot.get("negative_talent_version") or "")
    required = {
        "authority_consensus", "basis", "confidence", "evidence_coverage",
        "fact_support", "class", "severity",
    }
    if (
        supplemental_version == "negative-talent-v1-gatekeeper-supplement-v1"
        and required <= set(evaluation)
        and bool(str(evaluation.get("basis") or "").strip())
        and (evaluation.get("class") is None) == (evaluation.get("severity") is None)
    ):
        status = "established" if evaluation.get("class") is not None else "reviewed_no_finding"
        return status, True
    return str(evaluation.get("finding_status") or ""), False


def _maximum_role_matching(members: Sequence[Mapping[str, Any]]) -> int:
    role_sets = [set(member.get("role_families") or ()) & set(CORE_ROLES) for member in members]

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


def _structural_factors(
    members: Sequence[Mapping[str, Any]], observation: Mapping[str, Any]
) -> dict[str, Any]:
    covered_roles = sorted(
        set().union(*(set(member.get("role_families") or ()) for member in members))
        & set(CORE_ROLES)
    )
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
    core_coverage = (
        "four_core"
        if len(covered_roles) == 4
        else "three_core"
        if len(covered_roles) == 3
        else "two_core"
        if len(covered_roles) == 2
        else "one_or_none"
    )
    if observation.get("frozen_workset_member_set_complete") is not True:
        raise ValueError("team structural observation must freeze a complete member set")
    continuity = str(observation.get("continuity_structure") or "")
    if continuity not in {
        "durable_multi_stage",
        "managed_turnover",
        "stable_window",
        "stable_but_narrow",
        "fragmented",
        "forced_turnover_collapse",
    }:
        raise ValueError("team continuity structure is missing or invalid")
    if not tuple(observation.get("source_refs") or ()):
        raise ValueError("team structural observation requires source refs")

    anchors = {
        role: [index for index, member in enumerate(members) if role in member["role_families"]]
        for role in CORE_ROLES
    }
    unique_anchor_counts: dict[int, int] = {}
    for indexes in anchors.values():
        if len(indexes) == 1:
            unique_anchor_counts[indexes[0]] = unique_anchor_counts.get(indexes[0], 0) + 1
    maximum_unique_roles = max(unique_anchor_counts.values(), default=0)
    confidant = str(observation.get("confidant_dependency") or "")
    if confidant not in {
        "distributed",
        "bounded_anchor",
        "elevated_single_person",
        "single_point",
        "centralized_ruler_bottleneck_without_confidant",
        "insufficient_evidence",
    }:
        raise ValueError("confidant dependency requires an explicit valid observation")
    return {
        "covered_core_roles": covered_roles,
        "maximum_independent_role_matching": matching,
        "core_role_coverage": core_coverage,
        "functional_complementarity": complementarity,
        "continuity_structure": continuity,
        "confidant_dependency": confidant,
        "unique_anchor_role_counts": {
            str(members[index]["person_ref"]): count
            for index, count in sorted(unique_anchor_counts.items())
        },
    }


def resolve_effective_person_profiles(
    authorized_promotion: Mapping[str, Any],
    supplemental_promotion: Mapping[str, Any],
    calibrations: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], str]:
    if not calibrations:
        raise ValueError("team scored shadow requires talent calibrations")
    latest_talent_policy_version = str(calibrations[-1]["policy_version"])
    profiles: dict[str, dict[str, Any]] = {}
    for package in (authorized_promotion, supplemental_promotion):
        for item in _rows(package.get("items"), "profile promotion items"):
            snapshot = dict(item["person_profile_snapshot"])
            negative_evaluation = item.get("negative_evaluation") or {}
            negative_status, negative_completed = _negative_review_state(
                negative_evaluation, snapshot
            )
            person_ref = str(snapshot["canonical_person_ref"])
            if person_ref in profiles:
                raise ValueError("duplicate canonical profile person")
            profiles[person_ref] = {
                "person": str(item["person"]),
                "snapshot": snapshot,
                "effective_grade": str(snapshot["talent_grade"]),
                "effective_grade_basis": str(
                    (item.get("talent_evaluation") or {}).get("basis") or ""
                ),
                "calibration_policy_version": None,
                "profile_ref": str(snapshot["profile_ref"]),
                "negative_talent_class": snapshot.get("negative_talent_class"),
                "negative_talent_severity": snapshot.get("negative_talent_severity"),
                "negative_finding_status": negative_status,
                "negative_review_completed": negative_completed,
            }
    for calibration in calibrations:
        policy_version = str(calibration["policy_version"])
        for item in _rows(calibration.get("items"), "calibration items"):
            profile = profiles[str(item["person_ref"])]
            profile["effective_grade"] = str(item["calibrated_grade"])
            profile["effective_grade_basis"] = str(item["review_basis"])
            profile["calibration_policy_version"] = policy_version
    return profiles, latest_talent_policy_version


def build_team_building_v8_scored_shadow(
    team_window_promotion: Mapping[str, Any],
    authorized_promotion: Mapping[str, Any],
    supplemental_promotion: Mapping[str, Any],
    calibrations: Sequence[Mapping[str, Any]],
    scoring_policy: Mapping[str, Any],
    structural_observations: Mapping[str, Any],
) -> dict[str, Any]:
    if structural_observations.get("schema_version") != STRUCTURAL_SCHEMA_VERSION:
        raise ValueError("team structural observation schema mismatch")
    if (
        structural_observations.get("observation_policy_version")
        != STRUCTURAL_POLICY_VERSION
    ):
        raise ValueError("team structural observation policy mismatch")
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
        for key, value in (team_policy.get("negative_talent_severity_value") or {}).items()
    }
    class_values = {
        key: _decimal(value, f"negative class {key}")
        for key, value in (team_policy.get("negative_talent_class_relevance") or {}).items()
    }
    complementarity_values = {
        key: _decimal(value, f"complementarity {key}")
        for key, value in (team_policy.get("role_complementarity_factor") or {}).items()
    }
    continuity_values = {
        key: _decimal(value, f"continuity {key}")
        for key, value in (team_policy.get("long_term_stability_factor") or {}).items()
    }
    if set(talent_values) != {"ordinary", "usable", "important", "top", "historic"}:
        raise ValueError("team talent mapping is incomplete")

    windows = {
        str(item["unit_ref"]): item
        for item in _rows(team_window_promotion.get("items"), "team window items")
    }
    observation_index = {
        str(item["unit_ref"]): item
        for item in _rows(structural_observations.get("units"), "structural observation units")
    }
    if set(windows) != set(WINDOW_UNITS):
        raise ValueError("team window promotion must cover the frozen 12-window cohort")
    if set(observation_index) != set(WINDOW_UNITS):
        raise ValueError("team structural observations must cover all 12 windows")
    results: list[dict[str, Any]] = []
    for unit_ref in WINDOW_UNITS:
        item = windows[unit_ref]
        window = item["team_window_snapshot"]
        raw_members = _rows(window["members"], "team window members")
        observation = observation_index.get(unit_ref)
        if observation is None:
            raise ValueError(f"missing structural observation for {unit_ref}")
        structures = _structural_factors(raw_members, observation)
        members: list[dict[str, Any]] = []
        for member in raw_members:
            profile = profiles[str(member["person_ref"])]
            snapshot = profile["snapshot"]
            risk_class = snapshot.get("negative_talent_class")
            risk_severity = snapshot.get("negative_talent_severity")
            if (risk_class is None) != (risk_severity is None):
                raise ValueError("negative profile axes must be jointly present or absent")
            negative_value = (
                Decimal("0")
                if risk_class is None
                else severity_values[str(risk_severity)] * class_values[str(risk_class)]
            )
            members.append(
                {
                    "person": profile["person"],
                    "person_ref": member["person_ref"],
                    "profile_ref": member["profile_ref"],
                    "role_families": list(member["role_families"]),
                    "effective_talent_grade": profile["effective_grade"],
                    "talent_value": talent_values[profile["effective_grade"]],
                    "talent_calibration_policy_version": profile["calibration_policy_version"],
                    "negative_finding_status": profile["negative_finding_status"],
                    "negative_review_completed": profile["negative_review_completed"],
                    "negative_talent_class": risk_class,
                    "negative_talent_severity": risk_severity,
                    "negative_value": negative_value,
                }
            )

        positive_pool = sum(
            (member["talent_value"] for member in members), Decimal("0")
        )
        negative_pool = sum(
            (member["negative_value"] for member in members), Decimal("0")
        )

        historic_count = sum(member["effective_talent_grade"] == "historic" for member in members)
        high_count = sum(member["effective_talent_grade"] in {"historic", "top"} for member in members)
        qualified_count = sum(member["effective_talent_grade"] in {"historic", "top", "important"} for member in members)
        talent_depth = (
            "multi_historic"
            if historic_count >= 2
            else "multi_top"
            if high_count >= 2
            else "adequate_mixed"
            if qualified_count >= 2
            else "thin"
        )
        material_risk_members = [
            member
            for member in members
            if member["negative_talent_severity"] in {"material", "major", "historic"}
        ]
        unique_anchor_counts = structures["unique_anchor_role_counts"]
        if not all(member["negative_review_completed"] for member in members):
            raise ValueError("negative profile exposure requires completed per-person review")
        if any(member["negative_talent_severity"] == "historic" for member in members):
            negative_exposure = "historic_or_systemic_exposure"
        elif any(unique_anchor_counts.get(member["person_ref"], 0) >= 2 for member in material_risk_members):
            negative_exposure = "core_role_concentration"
        elif material_risk_members:
            negative_exposure = "material_exposure"
        elif any(member["negative_talent_severity"] == "minor" for member in members):
            negative_exposure = "bounded_minor"
        else:
            negative_exposure = "none_observed"

        complementarity_factor = complementarity_values[structures["functional_complementarity"]]
        continuity_factor = continuity_values[structures["continuity_structure"]]
        positive_signal = positive_pool * complementarity_factor * continuity_factor
        negative_signal = negative_pool * complementarity_factor * continuity_factor
        rule_raw_net = positive_signal - negative_signal
        effective_profile_set_fingerprint = _hash(
            [
                {
                    "person_ref": member["person_ref"],
                    "profile_ref": member["profile_ref"],
                    "effective_talent_grade": member["effective_talent_grade"],
                    "talent_calibration_policy_version": member[
                        "talent_calibration_policy_version"
                    ],
                    "negative_talent_class": member["negative_talent_class"],
                    "negative_talent_severity": member["negative_talent_severity"],
                }
                for member in sorted(members, key=lambda row: row["person_ref"])
            ]
        )
        contribution_seed = [POLICY_VERSION, window["window_ref"], window["profile_snapshot_version"]]
        result = {
            "unit_ref": unit_ref,
            "ruler": item["ruler"],
            "window_ref": window["window_ref"],
            "window": {"start": window["start"], "end": window["end"], "date_precision": window["date_precision"]},
            "dataset_role": "opened_regression" if unit_ref.startswith("TB-S") else "open_development",
            "factors": {
                "talent_depth": talent_depth,
                "core_role_coverage": structures["core_role_coverage"],
                "functional_complementarity": structures["functional_complementarity"],
                "continuity_structure": structures["continuity_structure"],
                "confidant_dependency": structures["confidant_dependency"],
                "negative_profile_exposure": negative_exposure,
            },
            "factor_diagnostics": {
                "historic_count": historic_count,
                "historic_or_top_count": high_count,
                "qualified_member_count": qualified_count,
                **structures,
            },
            "members": [
                {
                    key: _rounded(value) if isinstance(value, Decimal) else value
                    for key, value in member.items()
                }
                for member in sorted(members, key=lambda row: row["person_ref"])
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
                "primary_owner_ref": window["window_ref"],
                "dedup_key": _hash(["team_building", *contribution_seed]),
                "supporting_only_rules": [],
                "excluded_reuse": ["member_discovery_events", "member_appointment_events"],
                "rule_raw_net": _rounded(rule_raw_net),
                "score_rate": None,
                "score": None,
                "tier": None,
            },
            "lineage": {
                "window_policy_version": window["window_policy_version"],
                "roster_version": window["roster_version"],
                "profile_snapshot_version": window["profile_snapshot_version"],
                "talent_policy_version": latest_talent_policy_version,
                "negative_profile_mapping_version": team_policy["negative_profile_mapping_version"],
                "structural_observation_version": structural_observations[
                    "observation_policy_version"
                ],
                "structural_observation_source_refs": list(observation["source_refs"]),
                "effective_profile_set_fingerprint": effective_profile_set_fingerprint,
            },
        }
        result["semantic_fingerprint"] = _hash(result)
        results.append(result)

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": "full_cohort_scored_shadow_raw_signal_only",
        "rule_code": "team_building",
        "summary": {
            "window_count": len(results),
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_scoring_allowed": False,
            "dynamic_mapping_applied": False,
        },
        "windows": results,
        "declarations": {
            "frozen_workset_member_set_complete_implies_historical_roster_coverage": False,
            "historical_roster_coverage_claimed": False,
            "opened_sealed_used_as_new_qualification": False,
            "talent_and_political_risk_axes_mixed": False,
            "member_event_scores_recounted": False,
            "symmetric_structure_multiplier_inherited_for_shadow": True,
            "symmetric_structure_multiplier_revalidation_required": True,
            "score_rate": None,
            "score": None,
            "tier": None,
        },
    }
    report["report_sha256"] = _hash(report)
    return report
