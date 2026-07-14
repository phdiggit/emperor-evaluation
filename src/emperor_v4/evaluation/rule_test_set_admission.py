from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from math import ceil
from typing import Any, Mapping


SCHEMA_VERSION = "rule-test-set-admission-v1"
REPORT_SCHEMA_VERSION = "rule-test-set-admission-report-v1"
REQUIRED_RULES = {
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
}
ADMISSION_DECISIONS = {
    "completed_not_qualified",
    "ready_to_build_open_set",
    "contract_required",
    "blocked_on_prerequisite",
}
INPUT_TYPES = {"episode", "rule_evidence_unit", "ruler_time_window", "hybrid"}
TEST_UNIT_TYPES = {"rule_evidence_unit", "ruler_time_window"}
SHARED_ASSETS = {
    "evidence_coverage_contract",
    "fixed_revision_source_lineage",
    "codex_win_batch_execution",
    "duration_and_token_audit",
    "open_then_sealed_protocol",
    "qualification_thresholds",
}


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def evaluate_rule_test_set_admission(policy: Mapping[str, Any]) -> dict[str, Any]:
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Rule 测试集准入 schema_version 非法")
    if policy.get("item_code") != "i5b_talent_and_delegation":
        raise ValueError("Rule 测试集准入只允许第五项 B")

    shared = policy.get("shared_policy") or {}
    if set(shared.get("reusable_assets") or ()) != SHARED_ASSETS:
        raise ValueError("Rule 测试集准入共享资产不完整")
    thresholds = shared.get("qualification_thresholds") or {}
    if thresholds != {
        "decision_status_accuracy_min": 1.0,
        "factor_exact_match_rate_min": 0.85,
        "false_abstention_max": 0,
        "material_side_structure_exact_rate_min": 1.0,
        "unsafe_false_resolution_max": 0,
        "nonadjacent_error_max": 0,
        "direction_error_max": 0,
    }:
        raise ValueError("Rule 测试集准入门槛不得弱于现有资格门")

    profiles = policy.get("sizing_profiles") or {}
    if not profiles:
        raise ValueError("Rule 测试集准入缺少规模档位")
    for profile_code, profile in profiles.items():
        open_units = int(profile.get("open_development_units") or 0)
        sealed_units = int(profile.get("sealed_holdout_units") or 0)
        if min(open_units, sealed_units) < 4:
            raise ValueError(f"{profile_code} 的开放或 sealed 单元少于 4")

    performance = policy.get("performance_baseline") or {}
    units_per_call = int(performance.get("units_per_call") or 0)
    max_workers = int(performance.get("max_workers") or 0)
    duration_per_wave = float(
        performance.get("duration_per_parallel_wave_sec") or 0
    )
    tokens_per_call = int(performance.get("tokens_per_call") or 0)
    if min(units_per_call, max_workers, tokens_per_call) < 1 or duration_per_wave <= 0:
        raise ValueError("Rule 测试集准入性能基线非法")

    rules = tuple(policy.get("rules") or ())
    if {row.get("rule_code") for row in rules} != REQUIRED_RULES:
        raise ValueError("Rule 测试集准入必须完整覆盖第五项 B 五个 rule")
    if sorted(int(row.get("priority") or 0) for row in rules) != list(
        range(1, len(rules) + 1)
    ):
        raise ValueError("Rule 测试集准入优先级必须连续且唯一")

    decision_counts: Counter[str] = Counter()
    rows = []
    total_calls = 0
    total_waves = 0
    total_tokens = 0
    ready_open_units = 0
    ready_open_calls = 0
    ready_open_waves = 0
    ready_open_tokens = 0
    for rule in sorted(rules, key=lambda row: int(row["priority"])):
        rule_code = str(rule["rule_code"])
        decision = str(rule.get("admission_decision") or "")
        input_type = str(rule.get("input_type") or "")
        test_unit_type = str(rule.get("test_unit_type") or "")
        if decision not in ADMISSION_DECISIONS:
            raise ValueError(f"{rule_code} admission_decision 非法")
        if input_type not in INPUT_TYPES or test_unit_type not in TEST_UNIT_TYPES:
            raise ValueError(f"{rule_code} 输入或统计单元非法")
        decision_counts[decision] += 1

        profile_code = rule.get("sizing_profile")
        planned_open = 0
        planned_sealed = 0
        calls = 0
        waves = 0
        tokens = 0
        if decision != "completed_not_qualified":
            if profile_code not in profiles:
                raise ValueError(f"{rule_code} 未绑定有效规模档位")
            profile = profiles[profile_code]
            planned_open = int(profile["open_development_units"])
            planned_sealed = int(profile["sealed_holdout_units"])
            open_calls = ceil(planned_open / units_per_call)
            sealed_calls = ceil(planned_sealed / units_per_call)
            calls = open_calls + sealed_calls
            waves = ceil(open_calls / max_workers) + ceil(sealed_calls / max_workers)
            tokens = calls * tokens_per_call
            total_calls += calls
            total_waves += waves
            total_tokens += tokens
            if decision == "ready_to_build_open_set":
                ready_open_units += planned_open
                ready_open_calls += open_calls
                ready_open_waves += ceil(open_calls / max_workers)
                ready_open_tokens += open_calls * tokens_per_call
        elif profile_code is not None:
            raise ValueError(f"{rule_code} 已完成组合不得继续预排 sealed")

        prerequisites = tuple(rule.get("prerequisites") or ())
        missing_prerequisites = [
            str(row.get("code") or "")
            for row in prerequisites
            if row.get("status") != "satisfied"
        ]
        if decision == "ready_to_build_open_set" and missing_prerequisites:
            raise ValueError(f"{rule_code} 尚有前置项却标记为可构建开放集")
        if decision == "blocked_on_prerequisite" and not missing_prerequisites:
            raise ValueError(f"{rule_code} 阻断状态缺少真实前置阻断")

        rows.append(
            {
                "priority": int(rule["priority"]),
                "rule_code": rule_code,
                "admission_decision": decision,
                "current_stage": rule["current_stage"],
                "input_type": input_type,
                "test_unit_type": test_unit_type,
                "existing_regression_units": int(
                    rule.get("existing_regression_units") or 0
                ),
                "sizing_profile": profile_code,
                "planned_open_development_units": planned_open,
                "planned_sealed_holdout_units": planned_sealed,
                "missing_prerequisites": missing_prerequisites,
                "rule_specific_requirements": list(
                    rule.get("rule_specific_requirements") or ()
                ),
                "known_blockers": list(rule.get("known_blockers") or ()),
                "next_action": rule["next_action"],
                "model_performance_estimate": {
                    "model_call_count": calls,
                    "parallel_wave_count": waves,
                    "wall_clock_duration_sec": round(waves * duration_per_wave, 3),
                    "total_tokens": tokens,
                    "source_and_human_gold_review_excluded": True,
                },
            }
        )

    next_rule = next(
        (
            row["rule_code"]
            for row in rows
            if row["admission_decision"] == "ready_to_build_open_set"
        ),
        None,
    )
    basis = {
        "policy_version": policy.get("policy_version"),
        "rule_order": [row["rule_code"] for row in rows],
        "rule_decisions": {
            row["rule_code"]: row["admission_decision"] for row in rows
        },
        "sizing_profiles": profiles,
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "rule_test_set_admission_ready",
        "item_code": policy["item_code"],
        "policy_version": policy.get("policy_version"),
        "report_sha256": _canonical_hash(basis),
        "summary": {
            "rule_count": len(rows),
            "completed_not_qualified_count": decision_counts[
                "completed_not_qualified"
            ],
            "ready_to_build_open_set_count": decision_counts[
                "ready_to_build_open_set"
            ],
            "contract_required_count": decision_counts["contract_required"],
            "blocked_on_prerequisite_count": decision_counts[
                "blocked_on_prerequisite"
            ],
            "next_rule_for_open_test_set": next_rule,
            "currently_ready_open_development_units": ready_open_units,
            "currently_authorized_sealed_holdout_units": 0,
            "planned_future_open_development_units": sum(
                row["planned_open_development_units"] for row in rows
            ),
            "planned_future_sealed_holdout_units": sum(
                row["planned_sealed_holdout_units"] for row in rows
            ),
        },
        "shared_policy": {
            "reusable_assets": sorted(SHARED_ASSETS),
            "qualification_thresholds": thresholds,
            "default_execution_order": [
                "freeze_rule_contract",
                "build_open_development_set",
                "calibrate_only_on_open_set",
                "freeze_policy_and_sealed_gold",
                "run_sealed_once",
                "open_and_report_without_post_tuning",
            ],
            "thirty_two_units_not_required_by_default": True,
        },
        "rules": rows,
        "currently_ready_open_model_performance_estimate": {
            "model_call_count": ready_open_calls,
            "parallel_wave_count": ready_open_waves,
            "wall_clock_duration_sec": round(
                ready_open_waves * duration_per_wave, 3
            ),
            "total_tokens": ready_open_tokens,
            "source_and_human_gold_review_excluded": True,
        },
        "full_pipeline_model_performance_upper_bound": {
            "model_call_count": total_calls,
            "parallel_wave_count_across_sequential_rules": total_waves,
            "wall_clock_duration_sec": round(total_waves * duration_per_wave, 3),
            "total_tokens": total_tokens,
            "source_and_human_gold_review_excluded": True,
        },
        "formal_scoring_allowed": False,
        "database_write_count": 0,
    }
