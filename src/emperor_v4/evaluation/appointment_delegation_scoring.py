from __future__ import annotations

from typing import Any, Mapping

from emperor_v4.evaluation.limited_factor_scoring import (
    FACTOR_POINTS,
    FACTOR_VALUES,
    OBSERVATION_TO_FACTOR,
    SCORE_CONTRIBUTION_SCHEMA_VERSION,
    LimitedFactorProfile,
    canonical_hash,
    evaluate,
    score,
    validate_manifest,
)


RULE_CODE = "appointment_delegation"
RULE_VERSION = "appointment-delegation-v1-shadow"
FACTOR_SCHEMA_VERSION = "appointment-delegation-factors-v1"
JUDGMENT_POLICY_VERSION = "appointment-delegation-deterministic-judgment-v1"
SCORING_FORMULA_VERSION = "appointment-delegation-shadow-mean-v1"
FACTOR_NAMES = (
    "person_task_fit",
    "authority_clarity",
    "feedback_handling",
    "attributable_outcome",
)

PROFILE = LimitedFactorProfile(
    rule_code=RULE_CODE,
    rule_version=RULE_VERSION,
    factor_schema_version=FACTOR_SCHEMA_VERSION,
    judgment_policy_version=JUDGMENT_POLICY_VERSION,
    scoring_formula_version=SCORING_FORMULA_VERSION,
    factor_names=FACTOR_NAMES,
    report_status="appointment_delegation_scored_shadow_ready",
    excluded_from_other_rules_reason=(
        "本 demo 只结算 appointment_delegation 用人素质，不结算战果本身。"
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
