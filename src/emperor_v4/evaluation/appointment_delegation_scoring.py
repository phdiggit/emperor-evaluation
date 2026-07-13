from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


RULE_CODE = "appointment_delegation"
RULE_VERSION = "appointment-delegation-v1-shadow"
FACTOR_SCHEMA_VERSION = "appointment-delegation-factors-v1"
JUDGMENT_POLICY_VERSION = "appointment-delegation-deterministic-judgment-v1"
SCORE_CONTRIBUTION_SCHEMA_VERSION = "score-contribution-v1"
SCORING_FORMULA_VERSION = "appointment-delegation-shadow-mean-v1"

FACTOR_NAMES = (
    "person_task_fit",
    "authority_clarity",
    "feedback_handling",
    "attributable_outcome",
)
FACTOR_VALUES = frozenset(
    {"positive", "mixed", "negative", "unknown", "not_applicable"}
)
OBSERVATION_TO_FACTOR = {
    "positive_signal": "positive",
    "mixed_signal": "mixed",
    "negative_signal": "negative",
    "evidence_gap": "unknown",
    "not_applicable": "not_applicable",
}
FACTOR_POINTS = {"positive": 1, "mixed": 0, "negative": -1}


def canonical_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _require_exact_keys(
    payload: Mapping[str, Any], expected: Sequence[str], label: str
) -> None:
    if set(payload) != set(expected):
        raise ValueError(f"{label} 必须完整且唯一覆盖有限因子")


def validate_scored_demo_manifest(manifest: Mapping[str, Any]) -> None:
    if (
        manifest.get("schema_version") != 1
        or manifest.get("status") != "frozen_shadow_demo_input"
        or manifest.get("rule_code") != RULE_CODE
        or manifest.get("rule_version") != RULE_VERSION
        or manifest.get("factor_schema_version") != FACTOR_SCHEMA_VERSION
        or manifest.get("judgment_policy_version") != JUDGMENT_POLICY_VERSION
        or manifest.get("scoring_formula_version") != SCORING_FORMULA_VERSION
    ):
        raise ValueError("scored demo manifest 版本或状态非法")

    runtime = manifest.get("runtime_policy") or {}
    if (
        runtime.get("mode") != "offline_report_only_shadow"
        or runtime.get("model_calls_allowed") is not False
        or runtime.get("database_writes_allowed") is not False
        or runtime.get("formal_acceptance_allowed") is not False
    ):
        raise ValueError("scored demo 只允许离线、零模型、零数据库写入的 shadow 运行")

    passages = tuple(manifest.get("source_passages") or ())
    assertions = tuple(manifest.get("assertions") or ())
    episodes = tuple(manifest.get("historical_episodes") or ())
    units = tuple(manifest.get("rule_evidence_units") or ())
    if not passages or not assertions or not episodes or not units:
        raise ValueError("scored demo 缺少 SourcePassage、Assertion、Episode 或评分单元")

    def unique(rows: Sequence[Mapping[str, Any]], key: str, label: str) -> dict[str, Mapping[str, Any]]:
        indexed = {str(row.get(key)): row for row in rows}
        if "None" in indexed or len(indexed) != len(rows):
            raise ValueError(f"{label} identity 缺失或重复")
        return indexed

    passage_by_ref = unique(passages, "passage_ref", "SourcePassage")
    assertion_by_ref = unique(assertions, "assertion_ref", "Assertion")
    episode_by_ref = unique(episodes, "episode_ref", "HistoricalEpisode")
    unique(units, "unit_ref", "RuleEvidenceUnit")

    for passage in passages:
        if not all(passage.get(key) for key in ("source_title", "locator", "url")):
            raise ValueError("SourcePassage lineage 缺少书名、定位或 URL")
    for assertion in assertions:
        if assertion.get("source_passage_ref") not in passage_by_ref:
            raise ValueError("Assertion 指向未知 SourcePassage")
        confidence = assertion.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("Assertion confidence 非法")
    for episode in episodes:
        refs = tuple(episode.get("assertion_refs") or ())
        if not refs or any(ref not in assertion_by_ref for ref in refs):
            raise ValueError("HistoricalEpisode Assertion lineage 不完整")
        if not all(episode.get(key) for key in ("ruler", "person", "semantic_fingerprint")):
            raise ValueError("HistoricalEpisode 语义身份不完整")

    consumed_episodes: list[str] = []
    for unit in units:
        if unit.get("rule_code") != RULE_CODE:
            raise ValueError("RuleEvidenceUnit rule_code 非法")
        episode_refs = tuple(unit.get("episode_refs") or ())
        if not episode_refs or any(ref not in episode_by_ref for ref in episode_refs):
            raise ValueError("RuleEvidenceUnit 指向未知 HistoricalEpisode")
        consumed_episodes.extend(episode_refs)
        episode_assertions = {
            ref
            for episode_ref in episode_refs
            for ref in episode_by_ref[episode_ref]["assertion_refs"]
        }
        observations = unit.get("factor_observations") or {}
        _require_exact_keys(observations, FACTOR_NAMES, "factor_observations")
        for factor_name, observation in observations.items():
            value = observation.get("value")
            if value not in OBSERVATION_TO_FACTOR:
                raise ValueError(f"{factor_name} observation value 非法")
            if not str(observation.get("reason") or "").strip():
                raise ValueError(f"{factor_name} observation 缺少 reason")
            refs = tuple(observation.get("assertion_refs") or ())
            if len(refs) != len(set(refs)) or any(ref not in episode_assertions for ref in refs):
                raise ValueError(f"{factor_name} Assertion lineage 重复或越界")
            if value not in {"evidence_gap", "not_applicable"} and not refs:
                raise ValueError(f"{factor_name} 信号必须有 Assertion 支持")

    duplicates = sorted(
        ref for ref in set(consumed_episodes) if consumed_episodes.count(ref) > 1
    )
    if duplicates:
        raise ValueError(f"HistoricalEpisode 被重复消费: {duplicates}")


def _direction(factor_values: Mapping[str, str]) -> str:
    active = [value for value in factor_values.values() if value != "not_applicable"]
    if not active:
        return "neutral_context"
    if "unknown" in active:
        return "blocked_evidence"
    if "mixed" in active or ({"positive", "negative"} <= set(active)):
        return "mixed"
    return "positive" if set(active) == {"positive"} else "negative"


def evaluate_judgment(
    unit: Mapping[str, Any],
    episode_by_ref: Mapping[str, Mapping[str, Any]],
    assertion_by_ref: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    observations = unit["factor_observations"]
    factor_values = {
        name: OBSERVATION_TO_FACTOR[observations[name]["value"]]
        for name in FACTOR_NAMES
    }
    direction = _direction(factor_values)
    supporting_assertions = sorted(
        {
            ref
            for observation in observations.values()
            for ref in observation.get("assertion_refs") or ()
        }
    )
    passage_refs = sorted(
        {assertion_by_ref[ref]["source_passage_ref"] for ref in supporting_assertions}
    )
    confidence = (
        round(
            sum(float(assertion_by_ref[ref]["confidence"]) for ref in supporting_assertions)
            / len(supporting_assertions),
            4,
        )
        if supporting_assertions
        else 0.0
    )
    blockers = (
        [name for name, value in factor_values.items() if value == "unknown"]
        if direction == "blocked_evidence"
        else []
    )
    semantic_input = {
        "unit_ref": unit["unit_ref"],
        "episode_semantic_fingerprints": [
            episode_by_ref[ref]["semantic_fingerprint"]
            for ref in unit["episode_refs"]
        ],
        "factor_values": factor_values,
        "rule_version": RULE_VERSION,
        "factor_schema_version": FACTOR_SCHEMA_VERSION,
        "judgment_policy_version": JUDGMENT_POLICY_VERSION,
    }
    fingerprint = canonical_hash(semantic_input)
    return {
        "judgment_id": f"JDG-{fingerprint[:20].upper()}",
        "input_semantic_fingerprint": fingerprint,
        "rule_code": RULE_CODE,
        "rule_version": RULE_VERSION,
        "factor_schema_version": FACTOR_SCHEMA_VERSION,
        "judgment_policy_version": JUDGMENT_POLICY_VERSION,
        "ruler": unit["ruler"],
        "person": unit["person"],
        "rule_evidence_unit_ref": unit["unit_ref"],
        "episode_refs": list(unit["episode_refs"]),
        "applicability": (
            "blocked_evidence"
            if direction == "blocked_evidence"
            else "supporting_only"
            if direction == "neutral_context"
            else "applicable"
        ),
        "direction": None if direction == "blocked_evidence" else direction,
        "factor_values": factor_values,
        "factor_reasons": {
            name: observations[name]["reason"] for name in FACTOR_NAMES
        },
        "confidence": confidence,
        "blockers": blockers,
        "supporting_assertion_refs": supporting_assertions,
        "supporting_source_passage_refs": passage_refs,
        "review_status": "needs_review" if blockers else "shadow_accepted",
        "result_scope": "shadow_demo_only",
        "model_call_count": 0,
    }


def score_judgment(judgment: Mapping[str, Any]) -> dict[str, Any] | None:
    if judgment.get("review_status") != "shadow_accepted":
        return None
    values = judgment["factor_values"]
    active = {name: value for name, value in values.items() if value != "not_applicable"}
    if not active:
        return None
    points = {name: FACTOR_POINTS[value] for name, value in active.items()}
    raw = sum(points.values())
    normalized = round(raw / len(points), 4)
    semantic_input = {
        "judgment_ref": judgment["judgment_id"],
        "judgment_fingerprint": judgment["input_semantic_fingerprint"],
        "scoring_formula_version": SCORING_FORMULA_VERSION,
        "evaluation_scope": "shadow_demo_only",
    }
    fingerprint = canonical_hash(semantic_input)
    return {
        "score_contribution_id": f"SC-{fingerprint[:20].upper()}",
        "score_contribution_schema_version": SCORE_CONTRIBUTION_SCHEMA_VERSION,
        "contribution_status": "shadow",
        "judgment_ref": judgment["judgment_id"],
        "ruler": judgment["ruler"],
        "person": judgment["person"],
        "rule_evidence_unit_ref": judgment["rule_evidence_unit_ref"],
        "primary_settlement_rule": RULE_CODE,
        "supporting_only_rules": [],
        "factor_points": points,
        "raw_factor_sum": raw,
        "applicable_factor_count": len(points),
        "normalized_contribution": normalized,
        "scoring_formula_version": SCORING_FORMULA_VERSION,
        "duplicate_settlement_check": "passed",
        "excluded_from_other_rules_reason": "本 demo 只结算 appointment_delegation 用人素质，不结算战果本身。",
        "lineage": {
            "episode_refs": judgment["episode_refs"],
            "assertion_refs": judgment["supporting_assertion_refs"],
            "source_passage_refs": judgment["supporting_source_passage_refs"],
        },
        "semantic_fingerprint": fingerprint,
    }
