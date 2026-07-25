from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


PROJECTION_SHADOW_POLICY_VERSION = "appointment-delegation-projection-shadow-v1"
JUDGMENT_SHADOW_POLICY_VERSION = "appointment-delegation-judgment-readiness-v1"
JUDGMENT_SHADOW_SCHEMA_VERSION = "appointment-delegation-judgment-shadow-output-v1"

OBSERVATION_DIMENSIONS = (
    "person_task_fit",
    "authority_clarity",
    "feedback_handling",
    "attributable_outcome",
)
OBSERVATION_VALUES = frozenset(
    {
        "positive_signal",
        "negative_signal",
        "mixed_signal",
        "evidence_gap",
        "not_applicable",
    }
)
REVIEW_DISPOSITIONS = frozenset(
    {"judgment_shadow_ready", "blocked_evidence", "blocked_rule_boundary"}
)
DIRECTIONS = frozenset({"positive", "negative", "mixed"})

_FORBIDDEN_KEYS = frozenset(
    {
        "score",
        "scores",
        "score_contribution",
        "judgment_id",
        "formal_projection_id",
        "formal_judgment_id",
        "factor_values",
        "historical_gold",
        "rule_gold",
    }
)


def _hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _reject_forbidden(payload: object, path: str = "$") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).strip().casefold()
            if normalized in _FORBIDDEN_KEYS or normalized.startswith("gold_"):
                if normalized == "gold_accessed" and value is False:
                    continue
                raise ValueError(f"Projection/Judgment shadow 输入包含禁止字段: {path}.{key}")
            _reject_forbidden(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_forbidden(value, f"{path}[{index}]")


def build_projection_shadow_worklist(
    rule_evidence_final: Mapping[str, Any],
) -> dict[str, Any]:
    """把通过 Gate 的 RuleEvidenceUnit draft 投影为中立、不可接受的 shadow 输入。"""

    _reject_forbidden(rule_evidence_final)
    if (
        rule_evidence_final.get("status") != "rule_evidence_unit_shadow_ready"
        or rule_evidence_final.get("shadow_gate_passed") is not True
        or rule_evidence_final.get("unresolved_component_count") != 0
        or rule_evidence_final.get("duplicate_consumption_episode_refs") != []
        or rule_evidence_final.get("formal_acceptance_performed") is not False
        or rule_evidence_final.get("formal_rule_evidence_unit_count") != 0
        or rule_evidence_final.get("formal_projection_count") != 0
        or rule_evidence_final.get("judgment_count") != 0
        or rule_evidence_final.get("score_count") != 0
        or rule_evidence_final.get("database_write_count") != 0
    ):
        raise ValueError("Projection shadow 输入未通过 RuleEvidenceUnit Gate 或存在副作用")

    units = tuple(rule_evidence_final.get("rule_evidence_unit_drafts") or ())
    if not units or len(units) != rule_evidence_final.get("draft_unit_count"):
        raise ValueError("Projection shadow 输入 draft 数量不一致")

    projections = []
    seen_inputs: set[tuple[str, str, str, str]] = set()
    for unit in sorted(units, key=lambda row: str(row["unit_code"])):
        if unit.get("status") != "draft" or unit.get("rule_code") != "appointment_delegation":
            raise ValueError("Projection shadow 只接受 appointment_delegation draft")
        input_key = (
            str(unit["unit_code"]),
            str(unit["rule_code"]),
            str(unit["rule_version"]),
            str(unit["evaluation_context"]),
        )
        if input_key in seen_inputs:
            raise ValueError("同一 RuleEvidenceUnit draft 被重复投影")
        seen_inputs.add(input_key)
        semantic = {
            "input_type": "rule_evidence_unit_draft",
            "input_ref": unit["unit_code"],
            "input_semantic_fingerprint": unit["semantic_fingerprint"],
            "rule_code": unit["rule_code"],
            "rule_version": unit["rule_version"],
            "evaluation_context": unit["evaluation_context"],
            "projection_policy_version": PROJECTION_SHADOW_POLICY_VERSION,
        }
        fingerprint = _hash(semantic)
        projections.append(
            {
                "projection_code": f"RPS-{fingerprint[:20].upper()}",
                **semantic,
                "projection_semantic_fingerprint": fingerprint,
                "applicability_status": "applicable",
                "projection_status": "draft",
                "projection_payload": {
                    "ruler_ref": unit["ruler_ref"],
                    "person_ref": unit["person_ref"],
                    "decision_arc_family": unit["decision_arc_family"],
                    "members": unit["members"],
                    "included_link_refs": unit["included_link_refs"],
                    "evidence_assertion_refs": unit["evidence_assertion_refs"],
                    "question_readiness": unit["question_readiness"],
                },
            }
        )

    basis = {
        "source_rule_evidence_task_code": rule_evidence_final.get("task_code"),
        "source_rule_evidence_final_sha256": _hash(rule_evidence_final),
        "projection_codes": [row["projection_code"] for row in projections],
        "projection_shadow_policy_version": PROJECTION_SHADOW_POLICY_VERSION,
        "judgment_shadow_policy_version": JUDGMENT_SHADOW_POLICY_VERSION,
    }
    worklist_hash = _hash(basis)
    return {
        "schema_version": 1,
        "status": "projection_judgment_shadow_worklist_ready",
        "task_code": f"G3D-PJ-SHADOW-{worklist_hash[:20].upper()}",
        "worklist_sha256": worklist_hash,
        **basis,
        "judgment_shadow_schema_version": JUDGMENT_SHADOW_SCHEMA_VERSION,
        "observation_dimensions": list(OBSERVATION_DIMENSIONS),
        "observation_values": sorted(OBSERVATION_VALUES),
        "projection_count": len(projections),
        "projections": projections,
        "review_policy": {
            "evidence_gap_rule": "任一关键问题仍为 evidence_gap 时，不得生成 Judgment shadow candidate。",
            "signal_rule": "正负信号只描述证据观察，不等于正式 direction、factor value 或 score。",
            "direction_rule": "仅 readiness 完整时允许给出 shadow direction。",
        },
        "gold_accessed": False,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }


def validate_judgment_shadow_response(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Mapping[str, Any]]:
    _reject_forbidden(response)
    if (
        response.get("status") != "judgment_shadow_reviews_complete"
        or response.get("task_code") != worklist.get("task_code")
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("projection_shadow_policy_version")
        != PROJECTION_SHADOW_POLICY_VERSION
        or response.get("judgment_shadow_policy_version")
        != JUDGMENT_SHADOW_POLICY_VERSION
        or response.get("output_schema_version") != JUDGMENT_SHADOW_SCHEMA_VERSION
        or not str(response.get("reviewer") or "")
    ):
        raise ValueError("Judgment shadow response 与 worklist/policy/schema 不一致")
    if (
        response.get("reviewed_without_forbidden_inputs") is not True
        or response.get("gold_accessed") is not False
        or response.get("old_judgment_accessed") is not False
        or response.get("formal_acceptance_performed") is not False
        or response.get("scoring_performed") is not False
        or response.get("database_write_count") != 0
    ):
        raise ValueError("Judgment shadow reviewer 未声明隔离与零副作用")

    projection_by_code = {
        str(row["projection_code"]): row for row in worklist.get("projections") or ()
    }
    results = tuple(response.get("results") or ())
    result_by_code = {str(row.get("projection_code") or ""): row for row in results}
    if (
        "" in result_by_code
        or len(result_by_code) != len(results)
        or set(result_by_code) != set(projection_by_code)
    ):
        raise ValueError("Judgment shadow reviewer 未完整且唯一覆盖 Projection")

    for code, projection in projection_by_code.items():
        row = result_by_code[code]
        disposition = row.get("review_disposition")
        if disposition not in REVIEW_DISPOSITIONS:
            raise ValueError("Judgment shadow disposition 非法")
        if not str(row.get("review_reason") or "").strip():
            raise ValueError("Judgment shadow 缺少 review_reason")
        observations = row.get("observations") or {}
        if set(observations) != set(OBSERVATION_DIMENSIONS):
            raise ValueError("Judgment shadow observations 未完整覆盖有限维度")
        allowed_evidence = set(
            projection["projection_payload"]["evidence_assertion_refs"]
        )
        values = []
        for dimension in OBSERVATION_DIMENSIONS:
            observation = observations[dimension]
            value = observation.get("value")
            values.append(value)
            if value not in OBSERVATION_VALUES:
                raise ValueError("Judgment shadow observation value 非法")
            if not str(observation.get("reason") or "").strip():
                raise ValueError("Judgment shadow observation 缺少 reason")
            evidence = tuple(
                str(ref) for ref in observation.get("evidence_assertion_refs") or ()
            )
            if len(evidence) != len(set(evidence)) or not set(evidence) <= allowed_evidence:
                raise ValueError("Judgment shadow observation evidence 重复或越界")
            if value in {"positive_signal", "negative_signal", "mixed_signal"} and not evidence:
                raise ValueError("Judgment shadow 信号必须有 Assertion 支持")

        readiness = projection["projection_payload"]["question_readiness"]
        has_source_gap = "evidence_gap" in readiness.values()
        direction = row.get("shadow_direction")
        if disposition == "judgment_shadow_ready":
            if has_source_gap or "evidence_gap" in values:
                raise ValueError("存在 evidence_gap 时不得进入 Judgment shadow")
            if direction not in DIRECTIONS:
                raise ValueError("ready Judgment shadow 缺少合法方向")
            signal_values = set(values) - {"not_applicable"}
            expected = (
                "mixed"
                if "mixed_signal" in signal_values
                or {"positive_signal", "negative_signal"} <= signal_values
                else "positive"
                if signal_values == {"positive_signal"}
                else "negative"
                if signal_values == {"negative_signal"}
                else None
            )
            if direction != expected:
                raise ValueError("Judgment shadow direction 与观察信号不一致")
        elif disposition == "blocked_evidence":
            if not has_source_gap or "evidence_gap" not in values or direction is not None:
                raise ValueError("blocked_evidence 必须保留源 readiness 与观察缺口且无方向")
        elif direction is not None:
            raise ValueError("blocked_rule_boundary 不得声明方向")
    return result_by_code


def materialize_judgment_shadow_review(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Any]:
    rows = validate_judgment_shadow_response(worklist, response)
    projection_by_code = {
        str(row["projection_code"]): row for row in worklist.get("projections") or ()
    }
    candidates = []
    blocked = []
    for code in sorted(projection_by_code):
        projection = projection_by_code[code]
        row = rows[code]
        payload = {
            "projection_code": code,
            "input_ref": projection["input_ref"],
            "review_disposition": row["review_disposition"],
            "shadow_direction": row.get("shadow_direction"),
            "observations": row["observations"],
            "review_reason": row["review_reason"],
            "status": "draft",
        }
        if row["review_disposition"] == "judgment_shadow_ready":
            candidates.append(payload)
        else:
            blocked.append(payload)

    gate_passed = bool(candidates) and all(
        row["review_disposition"] != "blocked_rule_boundary" for row in rows.values()
    )
    return {
        "schema_version": 1,
        "status": (
            "judgment_shadow_readiness_passed"
            if gate_passed
            else "judgment_shadow_readiness_failed_closed"
        ),
        "task_code": worklist.get("task_code"),
        "projection_draft_count": len(projection_by_code),
        "judgment_shadow_candidate_count": len(candidates),
        "blocked_evidence_count": sum(
            row["review_disposition"] == "blocked_evidence" for row in rows.values()
        ),
        "blocked_rule_boundary_count": sum(
            row["review_disposition"] == "blocked_rule_boundary"
            for row in rows.values()
        ),
        "positive_signal_observation_count": sum(
            observation["value"] == "positive_signal"
            for row in rows.values()
            for observation in row["observations"].values()
        ),
        "negative_signal_observation_count": sum(
            observation["value"] == "negative_signal"
            for row in rows.values()
            for observation in row["observations"].values()
        ),
        "mixed_signal_observation_count": sum(
            observation["value"] == "mixed_signal"
            for row in rows.values()
            for observation in row["observations"].values()
        ),
        "judgment_shadow_candidates": candidates,
        "blocked_reviews": blocked,
        "shadow_gate_passed": gate_passed,
        "formal_acceptance_performed": False,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }
