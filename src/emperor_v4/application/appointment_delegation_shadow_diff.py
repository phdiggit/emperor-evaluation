from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.application.appointment_delegation_shadow_runner import (
    run_appointment_delegation_shadow_manifest,
)
from emperor_v4.evaluation.appointment_delegation_scoring import (
    FACTOR_NAMES,
    OBSERVATION_TO_FACTOR,
    canonical_hash,
)


SHADOW_DIFF_POLICY_VERSION = "appointment-delegation-shadow-diff-v1"


def _index(rows: list[Mapping[str, Any]], key: str) -> dict[str, Mapping[str, Any]]:
    indexed = {str(row[key]): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"shadow diff {key} 重复")
    return indexed


def _validate_request(request: Mapping[str, Any]) -> None:
    if (
        request.get("schema_version") != 1
        or request.get("status") != "frozen_shadow_diff_request"
        or request.get("policy_version") != SHADOW_DIFF_POLICY_VERSION
        or not str(request.get("request_code") or "")
        or not str(request.get("baseline_manifest_path") or "")
        or not str(request.get("candidate_manifest_code") or "")
        or not str(request.get("candidate_task_code") or "")
    ):
        raise ValueError("shadow diff request 身份或版本非法")
    runtime = request.get("runtime_policy") or {}
    if (
        runtime.get("mode") != "offline_report_only_shadow"
        or runtime.get("model_calls_allowed") is not False
        or runtime.get("database_writes_allowed") is not False
        or runtime.get("formal_acceptance_allowed") is not False
    ):
        raise ValueError("shadow diff 只允许离线、零模型、零写入、非正式接受")
    changes = tuple(request.get("factor_observation_changes") or ())
    expected = tuple(request.get("expected_changed_unit_refs") or ())
    if not changes or not expected or len(expected) != len(set(expected)):
        raise ValueError("shadow diff 必须声明候选变化和唯一的预期失效单元")


def _candidate_manifest(
    baseline: Mapping[str, Any], request: Mapping[str, Any]
) -> dict[str, Any]:
    candidate = deepcopy(baseline)
    units = {
        str(row["unit_ref"]): row for row in candidate["rule_evidence_units"]
    }
    changed_pairs: set[tuple[str, str]] = set()
    for change in request["factor_observation_changes"]:
        unit_ref = str(change.get("unit_ref") or "")
        factor_name = str(change.get("factor_name") or "")
        if unit_ref not in units or factor_name not in FACTOR_NAMES:
            raise ValueError("shadow diff change 指向未知评分单元或因子")
        pair = (unit_ref, factor_name)
        if pair in changed_pairs:
            raise ValueError("shadow diff change 重复覆盖同一评分单元因子")
        changed_pairs.add(pair)
        current = units[unit_ref]["factor_observations"][factor_name]
        if current.get("value") != change.get("expected_previous_value"):
            raise ValueError("shadow diff change 的 expected_previous_value 已漂移")
        replacement = change.get("replacement") or {}
        if replacement.get("value") not in OBSERVATION_TO_FACTOR:
            raise ValueError("shadow diff replacement value 非法")
        units[unit_ref]["factor_observations"][factor_name] = deepcopy(replacement)
    candidate["manifest_code"] = str(request["candidate_manifest_code"])
    candidate["task_code"] = str(request["candidate_task_code"])
    return candidate


def run_appointment_delegation_shadow_diff(
    request_path: Path | str,
) -> dict[str, Any]:
    path = Path(request_path)
    request = yaml.safe_load(path.read_text(encoding="utf-8"))
    _validate_request(request)
    repo_root = path.resolve().parents[2]
    configured_baseline_path = Path(str(request["baseline_manifest_path"]))
    baseline_path = (
        configured_baseline_path
        if configured_baseline_path.is_absolute()
        else repo_root / configured_baseline_path
    )
    if not baseline_path.is_file():
        raise ValueError("shadow diff baseline manifest 不存在")
    baseline_manifest = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
    candidate_manifest = _candidate_manifest(baseline_manifest, request)

    baseline = run_appointment_delegation_shadow_manifest(
        baseline_manifest, baseline_path
    )
    candidate = run_appointment_delegation_shadow_manifest(
        candidate_manifest, baseline_path
    )
    baseline_judgments = _index(baseline["judgments"], "rule_evidence_unit_ref")
    candidate_judgments = _index(candidate["judgments"], "rule_evidence_unit_ref")
    if set(baseline_judgments) != set(candidate_judgments):
        raise ValueError("shadow diff 候选改变了评分单元集合")
    baseline_contributions = _index(
        baseline["score_contributions"], "rule_evidence_unit_ref"
    )
    candidate_contributions = _index(
        candidate["score_contributions"], "rule_evidence_unit_ref"
    )

    changed = sorted(
        unit_ref
        for unit_ref in baseline_judgments
        if baseline_judgments[unit_ref] != candidate_judgments[unit_ref]
    )
    expected = sorted(str(ref) for ref in request["expected_changed_unit_refs"])
    if changed != expected:
        raise ValueError("shadow diff 实际失效单元与 expected_changed_unit_refs 不一致")
    reused = sorted(set(baseline_judgments) - set(changed))
    if any(
        baseline_contributions.get(ref) != candidate_contributions.get(ref)
        for ref in reused
    ):
        raise ValueError("shadow diff 未变化单元的 ScoreContribution 未精确复用")

    change_rows = []
    for unit_ref in changed:
        before = baseline_judgments[unit_ref]
        after = candidate_judgments[unit_ref]
        before_contribution = baseline_contributions.get(unit_ref)
        after_contribution = candidate_contributions.get(unit_ref)
        change_rows.append(
            {
                "rule_evidence_unit_ref": unit_ref,
                "ruler": after["ruler"],
                "person": after["person"],
                "before_judgment_ref": before["judgment_id"],
                "after_judgment_ref": after["judgment_id"],
                "factor_value_changes": {
                    name: {
                        "before": before["factor_values"][name],
                        "after": after["factor_values"][name],
                    }
                    for name in FACTOR_NAMES
                    if before["factor_values"][name] != after["factor_values"][name]
                },
                "direction": {"before": before["direction"], "after": after["direction"]},
                "normalized_contribution": {
                    "before": (
                        before_contribution["normalized_contribution"]
                        if before_contribution
                        else None
                    ),
                    "after": (
                        after_contribution["normalized_contribution"]
                        if after_contribution
                        else None
                    ),
                },
            }
        )

    baseline_aggregates = _index(baseline["ruler_aggregates"], "ruler")
    candidate_aggregates = _index(candidate["ruler_aggregates"], "ruler")
    aggregate_deltas = [
        {
            "ruler": ruler,
            "shadow_contribution_sum_before": baseline_aggregates[ruler][
                "shadow_contribution_sum"
            ],
            "shadow_contribution_sum_after": candidate_aggregates[ruler][
                "shadow_contribution_sum"
            ],
            "delta": round(
                candidate_aggregates[ruler]["shadow_contribution_sum"]
                - baseline_aggregates[ruler]["shadow_contribution_sum"],
                4,
            ),
        }
        for ruler in sorted(baseline_aggregates)
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "appointment_delegation_shadow_diff_ready_for_human_review",
        "request_code": request["request_code"],
        "policy_version": SHADOW_DIFF_POLICY_VERSION,
        "result_scope": "shadow_demo_only",
        "baseline_manifest_sha256": baseline["input_manifest_sha256"],
        "candidate_manifest_sha256": candidate["input_manifest_sha256"],
        "summary": {
            "unit_count": len(baseline_judgments),
            "changed_judgment_count": len(changed),
            "exactly_reused_judgment_count": len(reused),
            "changed_score_contribution_count": sum(
                baseline_contributions.get(ref) != candidate_contributions.get(ref)
                for ref in changed
            ),
            "exactly_reused_score_contribution_count": len(reused),
            "unexpected_invalidation_count": 0,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
        },
        "changed_units": change_rows,
        "exactly_reused_unit_refs": reused,
        "ruler_aggregate_deltas": aggregate_deltas,
        "review_gate": {
            "comparison_integrity_passed": True,
            "human_factor_review_required": True,
            "human_formula_review_required": True,
            "formal_acceptance_performed": False,
            "formal_scoring_enabled": False,
        },
        "side_effect_audit": {
            "offline": True,
            "report_only": True,
            "model_call_count": 0,
            "database_write_count": 0,
        },
    }
    report["report_sha256"] = canonical_hash(report)
    return report
