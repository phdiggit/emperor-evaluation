from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


TEST_SET_SCHEMA_VERSION = "i5b-factor-test-set-v1"
WORKLIST_SCHEMA_VERSION = "i5b-factor-worklist-v1"
RESPONSE_SCHEMA_VERSION = "i5b-factor-response-v1"
GOLD_SCHEMA_VERSION = "i5b-factor-gold-v1"
REPORT_SCHEMA_VERSION = "i5b-factor-qualification-report-v1"
BATCH_PLAN_SCHEMA_VERSION = "i5b-factor-batch-plan-v1"
ALLOWED_DATASET_ROLES = {"open_development", "sealed_holdout"}
ALLOWED_APPLICABILITY = {
    "applicable",
    "not_applicable",
    "insufficient_evidence",
}
FORBIDDEN_KEYS = {
    "score",
    "raw_score",
    "ranking",
    "numeric_value",
    "factor_value",
    "deterministic_value",
}


def _hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _assert_no_forbidden_keys(payload: object) -> None:
    if isinstance(payload, Mapping):
        found = FORBIDDEN_KEYS & set(payload)
        if found:
            raise ValueError(f"第五项因子响应包含禁止字段: {sorted(found)}")
        for value in payload.values():
            _assert_no_forbidden_keys(value)
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for value in payload:
            _assert_no_forbidden_keys(value)


def validate_i5b_factor_test_set(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != TEST_SET_SCHEMA_VERSION:
        raise ValueError("第五项测试集 manifest 版本非法")
    rule_code = manifest.get("rule_code")
    policy_version = manifest.get("factor_policy_version")
    dataset_role = manifest.get("dataset_role")
    if not rule_code or not policy_version:
        raise ValueError("第五项测试集缺少 rule/policy 版本")
    if dataset_role not in ALLOWED_DATASET_ROLES:
        raise ValueError("第五项测试集 dataset_role 非法")
    applicability = set(manifest.get("applicability_options") or ())
    if applicability != ALLOWED_APPLICABILITY:
        raise ValueError("第五项测试集 applicability 值域非法")
    catalog = manifest.get("factor_option_catalog") or {}
    if len(catalog) < 4:
        raise ValueError("第五项测试集至少需要四个有限因子")
    for factor_name, options in catalog.items():
        if not factor_name or not isinstance(options, Mapping) or len(options) < 4:
            raise ValueError("第五项因子值域过窄或格式非法")
        if "not_applicable" not in options or "insufficient_evidence" not in options:
            raise ValueError("每个第五项因子必须支持不适用和证据不足退出")
    units = tuple(manifest.get("units") or ())
    expected_count = int(manifest.get("expected_unit_count") or 0)
    if not units or len(units) != expected_count:
        raise ValueError("第五项测试集单元数量不符合冻结声明")
    unit_refs = [row.get("unit_ref") for row in units]
    if None in unit_refs or len(set(unit_refs)) != len(unit_refs):
        raise ValueError("第五项测试集 unit_ref 缺失或重复")
    for unit in units:
        if unit.get("context_kind") not in {
            "episode",
            "rule_evidence_unit",
            "aggregate_context",
            "ruler_time_window",
        }:
            raise ValueError(f"{unit.get('unit_ref')} context_kind 非法")
        evidence = tuple(unit.get("evidence") or ())
        if not evidence:
            raise ValueError(f"{unit['unit_ref']} 缺少 evidence")
        refs = [row.get("assertion_ref") for row in evidence]
        if None in refs or len(set(refs)) != len(refs):
            raise ValueError(f"{unit['unit_ref']} assertion_ref 缺失或重复")
        for row in evidence:
            source = row.get("source") or {}
            if not row.get("summary") or not source.get("source_ref"):
                raise ValueError(f"{unit['unit_ref']} evidence lineage 不完整")
    if dataset_role == "sealed_holdout":
        freeze = manifest.get("sealed_freeze") or {}
        if not freeze.get("identity_and_gold_frozen_before_model"):
            raise ValueError("sealed 测试集必须声明身份与 Gold 先冻结")
        if int(freeze.get("allowed_model_runs") or 0) != 1:
            raise ValueError("sealed 测试集必须且只能授权一次模型运行")


def build_i5b_factor_worklist(manifest: Mapping[str, Any]) -> dict[str, Any]:
    validate_i5b_factor_test_set(manifest)
    tasks = []
    for unit in sorted(manifest["units"], key=lambda row: row["unit_ref"]):
        tasks.append(
            {
                key: unit[key]
                for key in (
                    "unit_ref",
                    "ruler",
                    "subject",
                    "context_kind",
                    "evaluation_window",
                    "context_summary",
                    "evidence",
                    "profile_snapshots",
                    "member_set",
                    "coverage_tags",
                )
                if key in unit
            }
        )
    basis = {
        "rule_code": manifest["rule_code"],
        "dataset_role": manifest["dataset_role"],
        "factor_policy_version": manifest["factor_policy_version"],
        "factor_option_catalog": manifest["factor_option_catalog"],
        "rule_boundary": manifest["rule_boundary"],
        "evidence_coverage": manifest["evidence_coverage"],
        "tasks": tasks,
    }
    worklist_sha256 = _hash(basis)
    return {
        "schema_version": WORKLIST_SCHEMA_VERSION,
        "status": "i5b_factor_worklist_ready",
        "task_code": manifest["task_code"],
        "rule_code": manifest["rule_code"],
        "dataset_role": manifest["dataset_role"],
        "factor_policy_version": manifest["factor_policy_version"],
        "input_boundary": {
            "gold_options_exposed": False,
            "numeric_values_exposed": False,
            "scores_or_rankings_exposed": False,
            "source_lineage_required": True,
        },
        "rule_boundary": manifest["rule_boundary"],
        "evidence_coverage": manifest["evidence_coverage"],
        "applicability_options": sorted(ALLOWED_APPLICABILITY),
        "factor_option_catalog": manifest["factor_option_catalog"],
        "output_contract": {
            "response_schema_version": RESPONSE_SCHEMA_VERSION,
            "factor_names": sorted(manifest["factor_option_catalog"]),
            "factor_fields": ["option_code", "reason", "assertion_refs"],
            "forbidden_keys": sorted(FORBIDDEN_KEYS),
        },
        "tasks": tasks,
        "worklist_sha256": worklist_sha256,
    }


def build_i5b_factor_batch_plan(
    worklist: Mapping[str, Any], *, max_units_per_batch: int = 4
) -> dict[str, Any]:
    if worklist.get("schema_version") != WORKLIST_SCHEMA_VERSION:
        raise ValueError("第五项 worklist 版本非法")
    if max_units_per_batch < 1 or max_units_per_batch > 4:
        raise ValueError("第五项每批评分单元必须在 1 到 4 之间")
    tasks = tuple(worklist.get("tasks") or ())
    batches = []
    for offset in range(0, len(tasks), max_units_per_batch):
        batch_tasks = list(tasks[offset : offset + max_units_per_batch])
        batch = {**{key: value for key, value in worklist.items() if key != "tasks"}}
        batch["tasks"] = batch_tasks
        batch["batch_worklist_sha256"] = _hash(
            {
                "parent_worklist_sha256": worklist["worklist_sha256"],
                "unit_refs": [row["unit_ref"] for row in batch_tasks],
            }
        )
        batches.append(
            {
                "batch_index": len(batches) + 1,
                "unit_refs": [row["unit_ref"] for row in batch_tasks],
                "worklist": batch,
            }
        )
    return {
        "schema_version": BATCH_PLAN_SCHEMA_VERSION,
        "status": "i5b_factor_batch_plan_ready",
        "rule_code": worklist["rule_code"],
        "dataset_role": worklist["dataset_role"],
        "parent_worklist_sha256": worklist["worklist_sha256"],
        "max_units_per_batch": max_units_per_batch,
        "batch_count": len(batches),
        "batches": batches,
    }


def validate_i5b_factor_response(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> None:
    _assert_no_forbidden_keys(response)
    if (
        response.get("schema_version") != RESPONSE_SCHEMA_VERSION
        or response.get("status") != "i5b_factor_response_complete"
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("rule_code") != worklist.get("rule_code")
        or response.get("dataset_role") != worklist.get("dataset_role")
        or response.get("factor_policy_version")
        != worklist.get("factor_policy_version")
    ):
        raise ValueError("第五项因子响应版本或 worklist 身份非法")
    expected = {row["unit_ref"]: row for row in worklist.get("tasks") or ()}
    results = tuple(response.get("results") or ())
    if {row.get("unit_ref") for row in results} != set(expected):
        raise ValueError("第五项因子响应未完整唯一覆盖 worklist")
    factor_catalog = worklist["factor_option_catalog"]
    for result in results:
        unit_ref = result["unit_ref"]
        applicability = result.get("applicability")
        if applicability not in ALLOWED_APPLICABILITY:
            raise ValueError(f"{unit_ref} applicability 非法")
        factors = result.get("factors") or {}
        if set(factors) != set(factor_catalog):
            raise ValueError(f"{unit_ref} 未完整覆盖有限因子")
        allowed_refs = {
            row["assertion_ref"] for row in expected[unit_ref]["evidence"]
        }
        for factor_name, factor in factors.items():
            if set(factor) != {"option_code", "reason", "assertion_refs"}:
                raise ValueError(f"{unit_ref}/{factor_name} 字段非法")
            if factor["option_code"] not in factor_catalog[factor_name]:
                raise ValueError(f"{unit_ref}/{factor_name} option_code 非法")
            refs = tuple(factor.get("assertion_refs") or ())
            if not refs or not set(refs) <= allowed_refs or not factor.get("reason"):
                raise ValueError(f"{unit_ref}/{factor_name} 理由或 lineage 非法")
        terminal = (
            "not_applicable"
            if applicability == "not_applicable"
            else "insufficient_evidence"
            if applicability == "insufficient_evidence"
            else None
        )
        if terminal and any(
            row["option_code"] != terminal for row in factors.values()
        ):
            raise ValueError(f"{unit_ref} 退出状态与因子选项不一致")


def merge_i5b_factor_responses(
    worklist: Mapping[str, Any], responses: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    results = [row for response in responses for row in response.get("results") or ()]
    merged = {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "status": "i5b_factor_response_complete",
        "worklist_sha256": worklist["worklist_sha256"],
        "rule_code": worklist["rule_code"],
        "dataset_role": worklist["dataset_role"],
        "factor_policy_version": worklist["factor_policy_version"],
        "response_origin": f"{worklist['dataset_role']}_agent_run",
        "provider": "codex_chatgpt_login",
        "model": responses[0].get("model") if responses else None,
        "blind_run_declarations": {
            "factor_gold_accessed": False,
            "numeric_factor_values_supplied": False,
            "scoring_performed": False,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
        },
        "results": results,
    }
    validate_i5b_factor_response(worklist, merged)
    return merged


def evaluate_i5b_factor_qualification(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    gold: Mapping[str, Any],
) -> dict[str, Any]:
    validate_i5b_factor_response(worklist, response)
    if (
        gold.get("schema_version") != GOLD_SCHEMA_VERSION
        or gold.get("rule_code") != worklist.get("rule_code")
        or gold.get("dataset_role") != worklist.get("dataset_role")
        or gold.get("factor_policy_version") != worklist.get("factor_policy_version")
        or gold.get("worklist_sha256") != worklist.get("worklist_sha256")
    ):
        raise ValueError("第五项因子 Gold 版本或 worklist 身份非法")
    expected = {row["unit_ref"]: row for row in gold.get("units") or ()}
    actual = {row["unit_ref"]: row for row in response["results"]}
    if set(expected) != set(actual):
        raise ValueError("第五项因子 Gold 未完整覆盖 response")
    factor_names = sorted(worklist["factor_option_catalog"])
    applicability_correct = 0
    factor_correct = 0
    factor_count = 0
    unsafe_false_applicable = 0
    mismatches = []
    breakdown = {
        name: {"correct": 0, "incorrect": 0, "exact_rate": 0.0}
        for name in factor_names
    }
    for unit_ref in sorted(expected):
        wanted = expected[unit_ref]
        observed = actual[unit_ref]
        if wanted["applicability"] == observed["applicability"]:
            applicability_correct += 1
        else:
            mismatches.append(
                {
                    "unit_ref": unit_ref,
                    "field": "applicability",
                    "expected": wanted["applicability"],
                    "actual": observed["applicability"],
                }
            )
        if (
            wanted["applicability"] in {"not_applicable", "insufficient_evidence"}
            and observed["applicability"] == "applicable"
        ):
            unsafe_false_applicable += 1
        for factor_name in factor_names:
            factor_count += 1
            expected_option = wanted["factors"][factor_name]
            actual_option = observed["factors"][factor_name]["option_code"]
            if expected_option == actual_option:
                factor_correct += 1
                breakdown[factor_name]["correct"] += 1
            else:
                breakdown[factor_name]["incorrect"] += 1
                mismatches.append(
                    {
                        "unit_ref": unit_ref,
                        "field": factor_name,
                        "expected": expected_option,
                        "actual": actual_option,
                    }
                )
    unit_count = len(expected)
    applicability_rate = applicability_correct / unit_count
    factor_rate = factor_correct / factor_count
    for row in breakdown.values():
        row["exact_rate"] = row["correct"] / unit_count
    gate_passed = (
        applicability_rate == 1.0
        and factor_rate >= 0.85
        and unsafe_false_applicable == 0
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "i5b_factor_test_set_evaluated",
        "rule_code": worklist["rule_code"],
        "dataset_role": worklist["dataset_role"],
        "factor_policy_version": worklist["factor_policy_version"],
        "worklist_sha256": worklist["worklist_sha256"],
        "summary": {
            "unit_count": unit_count,
            "applicability_exact_count": applicability_correct,
            "applicability_exact_rate": applicability_rate,
            "factor_comparison_count": factor_count,
            "factor_exact_count": factor_correct,
            "factor_exact_rate": factor_rate,
            "unsafe_false_applicable_count": unsafe_false_applicable,
            "qualification_gate_passed": gate_passed,
        },
        "factor_breakdown": breakdown,
        "mismatches": mismatches,
        "formal_scoring_allowed": False,
        "database_write_count": 0,
    }
