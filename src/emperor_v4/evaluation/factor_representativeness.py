from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from math import ceil
from typing import Any, Mapping


SCHEMA_VERSION = "appointment-delegation-factor-representativeness-v1"
GROUPS = {"historical_opened", "new_open_development", "future_sealed"}
SLOT_TYPES = {"existing_unit", "planned_slot"}
AXES = (
    "era_family",
    "role_family",
    "outcome_structure",
    "attribution_challenge",
    "continuity_challenge",
    "source_challenge",
    "coverage_challenge",
)
MULTI_AXES = ("authorization_arcs",)
FORBIDDEN_SEALED_FIELDS = {
    "gold",
    "gold_option",
    "expected_factor_options",
    "factor_gold",
}


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, Mapping):
        if FORBIDDEN_SEALED_FIELDS.intersection(value):
            return True
        return any(_contains_forbidden_field(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_field(item) for item in value)
    return False


def evaluate_factor_representativeness_plan(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Factor representativeness schema_version 非法")
    if manifest.get("rule_code") != "appointment_delegation":
        raise ValueError("Factor representativeness 仅适用于 appointment_delegation")

    policy = manifest.get("policy") or {}
    group_quotas = policy.get("group_quotas") or {}
    stratum_minimums = policy.get("stratum_minimums") or {}
    entries = tuple(manifest.get("sample_entries") or ())
    if set(group_quotas) != GROUPS or not entries:
        raise ValueError("Factor representativeness group quota 或样本为空")
    if set(stratum_minimums) != set(AXES + MULTI_AXES):
        raise ValueError("Factor representativeness 分层轴不完整")

    entry_ids: set[str] = set()
    bound_identities: set[tuple[str, str]] = set()
    group_counts: Counter[str] = Counter()
    bound_group_counts: Counter[str] = Counter()
    stratum_counts = {axis: Counter() for axis in AXES + MULTI_AXES}
    opened_stratum_counts = {axis: Counter() for axis in AXES + MULTI_AXES}
    sealed_identity_exposure_count = 0

    for entry in entries:
        entry_id = str(entry.get("entry_id") or "")
        group = str(entry.get("group") or "")
        slot_type = str(entry.get("slot_type") or "")
        if not entry_id or entry_id in entry_ids:
            raise ValueError("Factor representativeness entry_id 缺失或重复")
        if group not in GROUPS or slot_type not in SLOT_TYPES:
            raise ValueError("Factor representativeness group 或 slot_type 非法")
        entry_ids.add(entry_id)
        group_counts[group] += 1

        identity = entry.get("candidate_identity")
        if slot_type == "existing_unit":
            if not isinstance(identity, Mapping):
                raise ValueError("existing_unit 必须绑定候选身份")
            identity_key = (
                str(identity.get("ruler_code") or ""),
                str(identity.get("person_code") or ""),
            )
            if not all(identity_key) or identity_key in bound_identities:
                raise ValueError("候选身份缺失或在样本间重复")
            bound_identities.add(identity_key)
            bound_group_counts[group] += 1
        elif identity is not None:
            raise ValueError("planned_slot 在回源审查前不得预填候选身份")

        if group == "future_sealed":
            if identity is not None:
                sealed_identity_exposure_count += 1
            if _contains_forbidden_field(entry):
                raise ValueError("future_sealed 槽位不得包含 Gold 或预期档位")

        strata = entry.get("strata") or {}
        if set(strata) != set(AXES + MULTI_AXES):
            raise ValueError(f"{entry_id} 的分层轴不完整")
        for axis in AXES:
            value = str(strata.get(axis) or "")
            if value not in stratum_minimums[axis]:
                raise ValueError(f"{entry_id} 的 {axis} 值非法")
            stratum_counts[axis][value] += 1
            if group == "historical_opened":
                opened_stratum_counts[axis][value] += 1
        for axis in MULTI_AXES:
            values = tuple(strata.get(axis) or ())
            if not values or len(values) != len(set(values)):
                raise ValueError(f"{entry_id} 的 {axis} 为空或重复")
            for value in values:
                if value not in stratum_minimums[axis]:
                    raise ValueError(f"{entry_id} 的 {axis} 值非法")
                stratum_counts[axis][value] += 1
                if group == "historical_opened":
                    opened_stratum_counts[axis][value] += 1

    group_checks = {
        group: group_counts[group] == int(group_quotas[group])
        for group in sorted(GROUPS)
    }
    stratum_checks: dict[str, dict[str, bool]] = {}
    missing_strata: list[dict[str, Any]] = []
    for axis in AXES + MULTI_AXES:
        axis_checks = {}
        for value, minimum in sorted(stratum_minimums[axis].items()):
            actual = stratum_counts[axis][value]
            passed = actual >= int(minimum)
            axis_checks[value] = passed
            if not passed:
                missing_strata.append(
                    {
                        "axis": axis,
                        "value": value,
                        "actual": actual,
                        "minimum": int(minimum),
                        "gap": int(minimum) - actual,
                    }
                )
        stratum_checks[axis] = axis_checks

    performance = manifest.get("performance_baseline") or {}
    units_per_call = int(performance.get("units_per_call") or 0)
    max_workers = int(performance.get("max_workers") or 0)
    duration_per_call = float(performance.get("duration_per_call_sec") or 0)
    tokens_per_call = int(performance.get("tokens_per_call") or 0)
    if min(units_per_call, max_workers, tokens_per_call) < 1 or duration_per_call <= 0:
        raise ValueError("Factor representativeness 性能基线非法")
    independent_unit_count = (
        group_counts["new_open_development"] + group_counts["future_sealed"]
    )
    estimated_calls = ceil(independent_unit_count / units_per_call)
    estimated_waves = ceil(estimated_calls / max_workers)

    plan_ready = (
        all(group_checks.values())
        and not missing_strata
        and sealed_identity_exposure_count == 0
    )
    report_basis = {
        "manifest_code": manifest.get("manifest_code"),
        "entry_ids": sorted(entry_ids),
        "group_counts": dict(sorted(group_counts.items())),
        "stratum_counts": {
            axis: dict(sorted(counts.items()))
            for axis, counts in stratum_counts.items()
        },
        "policy_version": policy.get("policy_version"),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "factor_representativeness_sampling_plan_ready"
            if plan_ready
            else "factor_representativeness_sampling_plan_incomplete"
        ),
        "rule_code": "appointment_delegation",
        "manifest_code": manifest.get("manifest_code"),
        "policy_version": policy.get("policy_version"),
        "plan_sha256": _canonical_hash(report_basis),
        "summary": {
            "portfolio_unit_count": len(entries),
            "historical_opened_regression_unit_count": group_counts[
                "historical_opened"
            ],
            "new_independent_unit_count": independent_unit_count,
            "new_open_development_unit_count": group_counts[
                "new_open_development"
            ],
            "future_sealed_unit_count": group_counts["future_sealed"],
            "bound_candidate_count": sum(bound_group_counts.values()),
            "unbound_candidate_count": len(entries) - sum(bound_group_counts.values()),
            "sealed_identity_exposure_count": sealed_identity_exposure_count,
            "missing_stratum_count": len(missing_strata),
        },
        "group_counts": dict(sorted(group_counts.items())),
        "group_quota_checks": group_checks,
        "historical_opened_stratum_counts": {
            axis: dict(sorted(counts.items()))
            for axis, counts in opened_stratum_counts.items()
        },
        "planned_portfolio_stratum_counts": {
            axis: dict(sorted(counts.items()))
            for axis, counts in stratum_counts.items()
        },
        "stratum_minimum_checks": stratum_checks,
        "missing_strata": missing_strata,
        "performance_estimate": {
            "basis": "sealed_holdout_v2_observed_single_batch",
            "units_per_call": units_per_call,
            "max_workers": max_workers,
            "estimated_model_call_count": estimated_calls,
            "estimated_parallel_wave_count": estimated_waves,
            "estimated_model_wall_clock_sec": round(
                estimated_waves * duration_per_call, 3
            ),
            "estimated_total_tokens": estimated_calls * tokens_per_call,
            "human_source_and_gold_review_excluded": True,
        },
        "sampling_plan_ready": plan_ready,
        "candidate_sourcing_ready": False,
        "candidate_sourcing_blocker": (
            "20 个匿名槽位仍须分别完成候选绑定、V4 回源和人工结构审查"
        ),
        "qualification_claim_allowed": False,
        "database_write_count": 0,
        "formal_score_write_count": 0,
    }
