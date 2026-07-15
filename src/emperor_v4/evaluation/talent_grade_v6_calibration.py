from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


POLICY_VERSION = "talent-grade-v6-calibration-v1"
VALID_GRADES = {"historic", "top", "important", "usable", "ordinary"}


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


def _promotion_items(*packages: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for package in packages:
        for item in _rows(package.get("items"), "promotion items"):
            snapshot = item.get("person_profile_snapshot")
            person = str(item.get("person") or "").strip()
            if not person or not isinstance(snapshot, Mapping):
                continue
            if person in result:
                raise ValueError(f"duplicate promoted person: {person}")
            result[person] = item
    return result


def _decision_index(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if payload.get("policy_version") != POLICY_VERSION:
        raise ValueError("talent calibration policy_version mismatch")
    raw_decisions = payload.get("decisions")
    if raw_decisions is None:
        groups = payload.get("groups") or {}
        raw_decisions = []
        for person in groups.get("retain_top", ()):
            raw_decisions.append(
                {
                    "person": person,
                    "calibrated_grade": "top",
                    "failure_codes": [],
                    "review_basis": (
                        "按V6合并同一职责链和共同参与后，仍有至少两个独立重大成果簇，"
                        "其中至少一个达到国家级、基础制度级或决定性战区级。"
                    ),
                }
            )
        raw_decisions.extend(groups.get("downgrade_important", ()))
        raw_decisions.extend(groups.get("supplemental", ()))
    result: dict[str, Mapping[str, Any]] = {}
    for item in _rows(raw_decisions, "calibration decisions"):
        person = str(item.get("person") or "").strip()
        grade = str(item.get("calibrated_grade") or "").strip()
        if not person or person in result or grade not in VALID_GRADES:
            raise ValueError("calibration decisions require unique person and valid grade")
        if not str(item.get("review_basis") or "").strip():
            raise ValueError(f"calibration decision lacks review_basis: {person}")
        result[person] = item
    return result


def build_talent_grade_v6_calibration(
    authorized_promotion: Mapping[str, Any],
    supplemental_promotion: Mapping[str, Any],
    decision_payload: Mapping[str, Any],
) -> dict[str, Any]:
    promoted = _promotion_items(authorized_promotion, supplemental_promotion)
    supplemental_names = {
        str(item.get("person") or "").strip()
        for item in _rows(supplemental_promotion.get("items"), "supplemental items")
    }
    review_names = {
        person
        for person, item in promoted.items()
        if (item["person_profile_snapshot"] or {}).get("talent_grade") == "top"
    } | supplemental_names
    decisions = _decision_index(decision_payload)
    if set(decisions) != review_names:
        missing = sorted(review_names - decisions.keys())
        extra = sorted(decisions.keys() - review_names)
        raise ValueError(f"calibration coverage mismatch; missing={missing}, extra={extra}")

    items: list[dict[str, Any]] = []
    all_original_grades: Counter[str] = Counter()
    all_calibrated_grades: Counter[str] = Counter()
    for person, promotion in promoted.items():
        snapshot = promotion["person_profile_snapshot"]
        original_grade = str(snapshot["talent_grade"])
        all_original_grades[original_grade] += 1
        decision = decisions.get(person)
        calibrated_grade = (
            str(decision["calibrated_grade"]) if decision else original_grade
        )
        all_calibrated_grades[calibrated_grade] += 1
        if decision is None:
            continue
        failure_codes = sorted(
            {str(value) for value in decision.get("failure_codes", ()) if value}
        )
        retained = calibrated_grade == original_grade
        gate_matrix = {
            "two_independent_major_clusters": (
                "second_independent_major_cluster_missing" not in failure_codes
            ),
            "national_or_foundational_or_decisive_theater_cluster": (
                "national_scale_result_missing" not in failure_codes
            ),
            "clear_implemented_result": (
                "implemented_result_missing" not in failure_codes
            ),
            "high_personal_attribution": (
                "high_personal_attribution_missing" not in failure_codes
            ),
            "contemporary_first_tier_comparison": (
                "first_tier_comparison_failed" not in failure_codes
                and "v6_top_gate_not_fully_satisfied" not in failure_codes
            ),
        }
        item = {
            "calibration_ref": "TGCAL-" + _hash(
                [POLICY_VERSION, snapshot["canonical_person_ref"]]
            )[:24].upper(),
            "person": person,
            "person_ref": snapshot["canonical_person_ref"],
            "base_profile_ref": snapshot["profile_ref"],
            "base_snapshot_version": snapshot["snapshot_version"],
            "original_grade": original_grade,
            "original_grade_version": snapshot["talent_grade_version"],
            "calibrated_grade": calibrated_grade,
            "decision": "retained" if retained else "downgraded",
            "gate_matrix": gate_matrix,
            "failure_codes": failure_codes,
            "review_basis": str(decision["review_basis"]).strip(),
            "source_basis": str(
                (promotion.get("talent_evaluation") or {}).get("basis") or ""
            ).strip(),
            "review_status": "human_frozen",
        }
        item["semantic_fingerprint"] = _hash(item)
        items.append(item)

    items.sort(key=lambda item: item["person"])
    report: dict[str, Any] = {
        "schema_version": "talent-grade-v6-calibration-report-v1",
        "policy_version": POLICY_VERSION,
        "status": "human_frozen_report_only",
        "summary": {
            "reviewed_profile_count": len(items),
            "retained_count": sum(item["decision"] == "retained" for item in items),
            "downgraded_count": sum(item["decision"] == "downgraded" for item in items),
            "original_grade_counts": dict(sorted(all_original_grades.items())),
            "calibrated_grade_counts": dict(sorted(all_calibrated_grades.items())),
            "model_call_count": 0,
            "database_write_count": 0,
        },
        "items": items,
        "declarations": {
            "original_v3_grade_overwritten": False,
            "distribution_used_as_quota": False,
            "formal_scoring_allowed": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report
