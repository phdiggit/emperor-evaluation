from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


POLICY_VERSION = "talent-grade-v10-targeted-correction-v1"
PRIOR_POLICY_VERSION = "talent-grade-v9-high-tier-calibration-v1"
EXPECTED_TRANSITIONS = {
    "陈群": ("historic", "top"),
    "苏定方": ("top", "historic"),
}
GRADE_RANK = {"important": 2, "top": 3, "historic": 4}


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


def build_talent_grade_v10_targeted_correction(
    prior_calibration: Mapping[str, Any],
    decision_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if prior_calibration.get("policy_version") != PRIOR_POLICY_VERSION:
        raise ValueError("V10 correction requires the frozen V9 calibration")
    if decision_payload.get("policy_version") != POLICY_VERSION:
        raise ValueError("V10 correction policy_version mismatch")

    prior_items = {
        str(item["person"]): item
        for item in _rows(prior_calibration.get("items"), "prior calibration items")
    }
    decisions = {
        str(item.get("person") or "").strip(): item
        for item in _rows(decision_payload.get("decisions"), "correction decisions")
    }
    if set(decisions) != set(EXPECTED_TRANSITIONS):
        raise ValueError("V10 correction must cover exactly Chen Qun and Su Dingfang")

    items: list[dict[str, Any]] = []
    for person in sorted(decisions):
        decision = decisions[person]
        prior = prior_items.get(person)
        if prior is None:
            raise ValueError(f"V9 calibration item is missing: {person}")
        original_grade, calibrated_grade = EXPECTED_TRANSITIONS[person]
        if (
            decision.get("current_grade") != original_grade
            or prior.get("calibrated_grade") != original_grade
            or decision.get("calibrated_grade") != calibrated_grade
        ):
            raise ValueError(f"V10 transition mismatch: {person}")
        required_text = (
            "achievement_summary",
            "consistency_summary",
            "legacy_summary",
            "review_basis",
        )
        if any(not str(decision.get(key) or "").strip() for key in required_text):
            raise ValueError(f"V10 correction evidence is incomplete: {person}")
        if not tuple(decision.get("source_refs") or ()):
            raise ValueError(f"V10 correction source refs are missing: {person}")

        rank_delta = GRADE_RANK[calibrated_grade] - GRADE_RANK[original_grade]
        item = {
            "calibration_ref": "TGCAL-" + _hash(
                [POLICY_VERSION, prior["person_ref"]]
            )[:24].upper(),
            "person": person,
            "person_ref": prior["person_ref"],
            "base_profile_ref": prior["base_profile_ref"],
            "base_snapshot_version": prior["base_snapshot_version"],
            "original_grade": original_grade,
            "original_grade_version": PRIOR_POLICY_VERSION,
            "calibrated_grade": calibrated_grade,
            "decision": "upgraded" if rank_delta > 0 else "downgraded",
            "primary_lanes": list(decision.get("primary_lanes") or ()),
            "achievement_summary": str(decision["achievement_summary"]),
            "consistency_summary": str(decision["consistency_summary"]),
            "legacy_summary": str(decision["legacy_summary"]),
            "gate_matrix": {
                "historic_gate_passed": calibrated_grade == "historic",
                "top_gate_passed": True,
            },
            "failure_codes": (
                []
                if calibrated_grade == "historic"
                else ["historic_state_foundational_structure_gate_not_met"]
            ),
            "correction_codes": sorted(
                {str(value) for value in decision.get("correction_codes") or ()}
            ),
            "review_basis": str(decision["review_basis"]),
            "source_basis": str(prior.get("source_basis") or ""),
            "source_refs": list(decision["source_refs"]),
            "review_status": "human_frozen",
        }
        item["semantic_fingerprint"] = _hash(item)
        items.append(item)

    before_counts = dict(prior_calibration["summary"]["after_grade_counts"])
    after_counts = dict(before_counts)
    for item in items:
        after_counts[item["original_grade"]] -= 1
        after_counts[item["calibrated_grade"]] += 1
    transitions = Counter(
        f"{item['original_grade']}->{item['calibrated_grade']}" for item in items
    )
    report: dict[str, Any] = {
        "schema_version": "talent-grade-v10-targeted-correction-report-v1",
        "policy_version": POLICY_VERSION,
        "prior_policy_version": PRIOR_POLICY_VERSION,
        "status": "human_frozen_report_only",
        "summary": {
            "reviewed_profile_count": len(items),
            "upgraded_count": 1,
            "downgraded_count": 1,
            "transition_counts": dict(sorted(transitions.items())),
            "before_grade_counts": dict(sorted(before_counts.items())),
            "after_grade_counts": dict(sorted(after_counts.items())),
            "model_call_count": 0,
            "database_write_count": 0,
        },
        "items": items,
        "declarations": {
            "v9_rows_overwritten": False,
            "distribution_used_as_quota": False,
            "political_risk_used_as_talent_penalty": False,
            "pyongyang_campaign_classified_as_battle_defeat": False,
            "institution_longevity_treated_as_net_success": False,
            "formal_scoring_allowed": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report
