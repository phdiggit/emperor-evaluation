from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


POLICY_VERSION = "talent-grade-v8-final-calibration-v1"
PRIOR_POLICY_VERSIONS = (
    "talent-grade-v6-calibration-v1",
    "talent-grade-v7-important-calibration-v1",
)
REVIEW_GRADES = {"historic", "usable", "ordinary"}
VALID_GRADES = {"historic", "top", "important", "usable", "ordinary"}
GRADE_RANK = {"ordinary": 0, "usable": 1, "important": 2, "top": 3, "historic": 4}


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


def build_talent_grade_v8_final_calibration(
    authorized_promotion: Mapping[str, Any],
    supplemental_promotion: Mapping[str, Any],
    prior_calibrations: Sequence[Mapping[str, Any]],
    decision_payload: Mapping[str, Any],
) -> dict[str, Any]:
    promoted: dict[str, Mapping[str, Any]] = {}
    for package in (authorized_promotion, supplemental_promotion):
        for item in _rows(package.get("items"), "promotion items"):
            person = str(item.get("person") or "").strip()
            snapshot = item.get("person_profile_snapshot")
            if not person or not isinstance(snapshot, Mapping) or person in promoted:
                raise ValueError("promotion items require unique person and snapshot")
            promoted[person] = item

    if tuple(item.get("policy_version") for item in prior_calibrations) != PRIOR_POLICY_VERSIONS:
        raise ValueError("prior talent calibration sequence mismatch")
    current_grades = {
        person: str(item["person_profile_snapshot"]["talent_grade"])
        for person, item in promoted.items()
    }
    latest_prior: dict[str, Mapping[str, Any]] = {}
    for calibration in prior_calibrations:
        for item in _rows(calibration.get("items"), "prior calibration items"):
            person = str(item["person"])
            current_grades[person] = str(item["calibrated_grade"])
            latest_prior[person] = {
                **item,
                "policy_version": calibration["policy_version"],
            }
    review_names = {
        person for person, grade in current_grades.items() if grade in REVIEW_GRADES
    }

    if decision_payload.get("policy_version") != POLICY_VERSION:
        raise ValueError("final calibration policy_version mismatch")
    decisions: dict[str, Mapping[str, Any]] = {}
    for decision in _rows(decision_payload.get("decisions"), "final decisions"):
        person = str(decision.get("person") or "").strip()
        grade = str(decision.get("calibrated_grade") or "").strip()
        basis = str(decision.get("review_basis") or "").strip()
        stated_current = str(decision.get("current_grade") or "").strip()
        if (
            not person
            or person in decisions
            or grade not in VALID_GRADES
            or not basis
            or stated_current != current_grades.get(person)
        ):
            raise ValueError("final decisions require valid current and calibrated grades")
        decisions[person] = decision
    if set(decisions) != review_names:
        missing = sorted(review_names - decisions.keys())
        extra = sorted(decisions.keys() - review_names)
        raise ValueError(f"final calibration coverage mismatch; missing={missing}, extra={extra}")

    before_counts = Counter(current_grades.values())
    final_grades = dict(current_grades)
    items: list[dict[str, Any]] = []
    for person in sorted(review_names):
        promotion = promoted[person]
        snapshot = promotion["person_profile_snapshot"]
        decision = decisions[person]
        original_grade = current_grades[person]
        calibrated_grade = str(decision["calibrated_grade"])
        final_grades[person] = calibrated_grade
        rank_delta = GRADE_RANK[calibrated_grade] - GRADE_RANK[original_grade]
        decision_kind = "upgraded" if rank_delta > 0 else "downgraded" if rank_delta < 0 else "retained"
        prior = latest_prior.get(person)
        item = {
            "calibration_ref": "TGCAL-" + _hash(
                [POLICY_VERSION, snapshot["canonical_person_ref"]]
            )[:24].upper(),
            "person": person,
            "person_ref": snapshot["canonical_person_ref"],
            "base_profile_ref": snapshot["profile_ref"],
            "base_snapshot_version": snapshot["snapshot_version"],
            "original_grade": original_grade,
            "original_grade_version": (
                str(prior["policy_version"])
                if prior is not None
                else str(snapshot["talent_grade_version"])
            ),
            "calibrated_grade": calibrated_grade,
            "decision": decision_kind,
            "gate_path": str(decision.get("gate_path") or "").strip(),
            "gate_matrix": {
                "historic_gate_passed": calibrated_grade == "historic",
                "top_gate_passed": calibrated_grade in {"historic", "top"},
                "important_gate_passed": calibrated_grade in {"historic", "top", "important"},
                "usable_gate_passed": calibrated_grade != "ordinary",
            },
            "failure_codes": sorted(
                {str(value) for value in decision.get("failure_codes", ()) if value}
            ),
            "review_basis": str(decision["review_basis"]).strip(),
            "source_basis": str(
                (promotion.get("talent_evaluation") or {}).get("basis") or ""
            ).strip(),
            "review_status": "human_frozen",
        }
        item["semantic_fingerprint"] = _hash(item)
        items.append(item)

    after_counts = Counter(final_grades.values())
    report: dict[str, Any] = {
        "schema_version": "talent-grade-v8-final-calibration-report-v1",
        "policy_version": POLICY_VERSION,
        "prior_policy_versions": list(PRIOR_POLICY_VERSIONS),
        "status": "human_frozen_report_only",
        "summary": {
            "reviewed_profile_count": len(items),
            "upgraded_count": sum(item["decision"] == "upgraded" for item in items),
            "retained_count": sum(item["decision"] == "retained" for item in items),
            "downgraded_count": sum(item["decision"] == "downgraded" for item in items),
            "before_grade_counts": dict(sorted(before_counts.items())),
            "after_grade_counts": dict(sorted(after_counts.items())),
            "top_to_historic_candidate_count": 0,
            "model_call_count": 0,
            "database_write_count": 0,
        },
        "items": items,
        "declarations": {
            "prior_grade_overwritten": False,
            "political_risk_used_as_talent_penalty": False,
            "missing_input_used_as_negative_ability_evidence": False,
            "distribution_used_as_quota": False,
            "formal_scoring_allowed": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report
