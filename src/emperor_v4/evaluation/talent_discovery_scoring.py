from __future__ import annotations

from typing import Any, Mapping

from emperor_v4.evaluation.limited_factor_scoring import (
    SCORE_CONTRIBUTION_SCHEMA_VERSION,
    LimitedFactorProfile,
    canonical_hash,
    evaluate,
    score,
    validate_manifest,
)


RULE_CODE = "talent_discovery"
RULE_VERSION = "talent-discovery-v1-shadow"
FACTOR_SCHEMA_VERSION = "talent-discovery-factors-v1"
JUDGMENT_POLICY_VERSION = "talent-discovery-deterministic-judgment-v1"
SCORING_FORMULA_VERSION = "talent-discovery-shadow-mean-v1"
FACTOR_NAMES = (
    "recognition_novelty",
    "recognition_basis",
    "barrier_crossing",
    "conversion_to_use",
)

PROFILE = LimitedFactorProfile(
    rule_code=RULE_CODE,
    rule_version=RULE_VERSION,
    factor_schema_version=FACTOR_SCHEMA_VERSION,
    judgment_policy_version=JUDGMENT_POLICY_VERSION,
    scoring_formula_version=SCORING_FORMULA_VERSION,
    factor_names=FACTOR_NAMES,
    report_status="talent_discovery_scored_shadow_ready",
    supporting_only_rules=("appointment_delegation",),
    excluded_from_other_rules_reason=(
        "本贡献只结算人才进入统治者有效视野的发现链；职位匹配、授权质量与后续战果归 appointment_delegation 或相应结果规则，不重复结算。"
    ),
)


def validate_scored_demo_manifest(manifest: Mapping[str, Any]) -> None:
    validate_manifest(manifest, PROFILE)


def evaluate_judgment(
    unit: Mapping[str, Any],
    episode_by_ref: Mapping[str, Mapping[str, Any]],
    assertion_by_ref: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return evaluate(unit, episode_by_ref, assertion_by_ref, PROFILE)


def score_judgment(judgment: Mapping[str, Any]) -> dict[str, Any] | None:
    return score(judgment, PROFILE)
